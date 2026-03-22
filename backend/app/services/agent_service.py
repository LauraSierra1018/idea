from __future__ import annotations

import os
from typing import List, Tuple
from dotenv import load_dotenv
from openai import OpenAI

from app.schemas.models import (
    UserProfileNormalized, Constraints, Blueprint, Exercise, PlanDraft
)
from app.core.validator import validate_plan  # <-- usamos el validador desde aquí

load_dotenv()
client = OpenAI()

def build_agent_instructions() -> str:
    return (
        "You are a planning agent.\n"
        "Hard rules:\n"
        "- You MUST follow hard constraints.\n"
        "- Output MUST match the provided JSON Schema exactly.\n"
        "- Set status to 'DRAFT'.\n"
        "- sessions_per_week MUST equal blueprint.sessions_per_week.\n"
        "- max_rpe MUST be <= constraints.hard.max_intensity_rpe.\n"
        "- rest_days_per_week MUST be >= constraints.hard.min_rest_days_per_week.\n"
        "- Do NOT include exercises that violate forbidden tags.\n"
        "- estimated_minutes should be close to blueprint.session_duration_min.\n"
        "If information is missing, add short questions in questions_to_finalize.\n"
    )

def compact_pool(pool: List[Exercise]) -> List[dict]:
    return [
        {
            "id": e.id,
            "name": e.name,
            "modality": e.modality,
            "difficulty": e.difficulty,
            "impact_level": e.impact_level,
            "equipment_tags": e.equipment_tags,
            "contraindication_tags": e.contraindication_tags,
            "alternatives_ids": e.alternatives_ids,
        }
        for e in pool
    ]

def _call_model_for_plan(*, model: str, system_prompt: str, user_content: str) -> PlanDraft:
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "PlanDraft",
                "schema": PlanDraft.model_json_schema(),
                "strict": True,
            }
        },
    )
    return PlanDraft.model_validate_json(resp.output_text)

def generate_plan_draft(
    *,
    plan_id: str,
    version: int,
    user_profile: UserProfileNormalized,
    constraints: Constraints,
    blueprint: Blueprint,
    exercise_pool: List[Exercise],
    model: str | None = None,
) -> PlanDraft:
    model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    payload = {
        "plan_id": plan_id,
        "version": version,
        "user_profile": user_profile.model_dump(),
        "constraints": constraints.model_dump(),
        "blueprint": blueprint.model_dump(),
        "exercise_pool": compact_pool(exercise_pool),
        "output_requirements": {
            "status": "DRAFT",
            "sessions_per_week": blueprint.sessions_per_week,
        },
    }

    system_prompt = build_agent_instructions()
    user_content = f"Create a safe draft plan using this context:\n{payload}"

    return _call_model_for_plan(model=model, system_prompt=system_prompt, user_content=user_content)

def generate_plan_draft_with_repair(
    *,
    plan_id: str,
    version: int,
    user_profile: UserProfileNormalized,
    constraints: Constraints,
    blueprint: Blueprint,
    exercise_pool: List[Exercise],
    model: str | None = None,
    max_attempts: int = 3,
) -> Tuple[PlanDraft, List[str]]:
    """
    Generates a PlanDraft and self-repairs using validator feedback.
    Returns: (plan, errors_last_attempt)
    - If success: errors_last_attempt = []
    - If fail after retries: returns last plan + last errors
    """
    model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    system_prompt = build_agent_instructions()

    # 1) First attempt: normal generation
    plan = generate_plan_draft(
        plan_id=plan_id,
        version=version,
        user_profile=user_profile,
        constraints=constraints,
        blueprint=blueprint,
        exercise_pool=exercise_pool,
        model=model,
    )

    ok, errors = validate_plan(plan, constraints, blueprint, exercise_pool)
    if ok:
        return plan, []

    # 2) Repair attempts
    base_context = {
        "plan_id": plan_id,
        "version": version,
        "user_profile": user_profile.model_dump(),
        "constraints": constraints.model_dump(),
        "blueprint": blueprint.model_dump(),
        "exercise_pool": compact_pool(exercise_pool),
        "output_requirements": {
            "status": "DRAFT",
            "sessions_per_week": blueprint.sessions_per_week,
        },
    }

    attempt = 2
    while attempt <= max_attempts:
        repair_prompt = {
            "context": base_context,
            "previous_plan": plan.model_dump(),
            "validation_errors": errors,
            "instruction": (
                "Fix ONLY what is necessary to satisfy validation_errors. "
                "Do not change unrelated parts. "
                "Return a corrected PlanDraft matching the schema."
            ),
        }

        plan = _call_model_for_plan(
            model=model,
            system_prompt=system_prompt,
            user_content=f"Repair the plan using this repair package:\n{repair_prompt}",
        )

        ok, errors = validate_plan(plan, constraints, blueprint, exercise_pool)
        if ok:
            return plan, []

        attempt += 1

    # If still failing, return last plan and last errors
    return plan, errors