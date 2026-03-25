from __future__ import annotations
import re
from typing import List, Tuple
from app.schemas.models import (
    UserProfileRaw, UserProfileNormalized,
    Constraints, ConstraintsHard, ConstraintsSoft,
    Blueprint, SessionTemplate, Exercise
)

def _extract_tags_from_text(text: str | None) -> List[str]:
    if not text:
        return []
    t = text.lower()
    tags = []
    if "rodilla" in t or "knee" in t:
        tags.append("knee_pain")
    if "espalda" in t or "lumbar" in t or "back" in t:
        tags.append("low_back_pain")
    return tags

def normalize_profile(raw: UserProfileRaw) -> UserProfileNormalized:
    injury_tags = _extract_tags_from_text(raw.injuries_text)
    medical_tags = [m.lower() for m in raw.medical_flags]

    # experiencia (simplificada)
    training_experience = "beginner" if raw.activity_level_choice in ["sedentary", "low"] else "intermediate"

    # rango de días seguro (simplificado)
    if raw.activity_level_choice in ["sedentary", "low"]:
        dmin, dmax = 2, min(4, raw.days_per_week_preferred)
    else:
        dmin, dmax = 3, min(5, raw.days_per_week_preferred)

    environment = "home" if "gym" not in [e.lower() for e in raw.equipment_available] else "gym"
    if environment == "gym" and len(raw.equipment_available) <= 1:
        environment = "mixed"

    # riesgo simple
    risk_level = "medium" if (raw.age >= 40 and raw.activity_level_choice in ["sedentary", "low"]) else "low"
    if "hypertension" in medical_tags or "diabetes" in medical_tags:
        risk_level = "high"

    return UserProfileNormalized(
        age=raw.age,
        sex=raw.sex,
        weight_kg=raw.weight_kg,
        height_cm=raw.height_cm,
        activity_level=raw.activity_level_choice,
        training_experience=training_experience,
        injury_tags=injury_tags,
        medical_tags=medical_tags,
        time_per_session_min=raw.time_per_session_min,
        days_per_week_target_min=dmin,
        days_per_week_target_max=dmax,
        environment=environment,
        equipment_tags=[e.lower() for e in raw.equipment_available],
        goal_primary=raw.goal_primary,
        risk_level=risk_level,
    )

def derive_constraints(n: UserProfileNormalized) -> Constraints:
    max_rpe = 7 if n.age >= 40 else 8
    if n.training_experience == "beginner" or n.activity_level in ["sedentary", "low"]:
        max_rpe = min(max_rpe, 6)

    forbidden = []
    if "knee_pain" in n.injury_tags:
        forbidden += ["high_impact", "deep_knee_flexion_heavy"]
    if "low_back_pain" in n.injury_tags:
        forbidden += ["spinal_loaded_heavy", "flexion_loaded"]
    if "hypertension" in n.medical_tags:
        forbidden += ["valsava_heavy", "max_effort_lifts"]

    max_sessions = n.days_per_week_target_max
    min_rest = max(2, 7 - max_sessions)

    hard = ConstraintsHard(
        max_sessions_per_week=max_sessions,
        max_intensity_rpe=max_rpe,
        min_rest_days_per_week=min_rest,
        forbidden_exercise_tags=forbidden,
        required_components=["warmup", "cooldown", "mobility_baseline"],
        progression_caps={
            "weekly_volume_increase_pct_max": 10,
            "intensity_step_max": 1,
            "deload_every_n_weeks": 4,
        }
    )

    soft = ConstraintsSoft(
        preferred_session_types=["strength", "mobility", "cardio_zone2"],
        disliked_exercise_tags=[],
        schedule_preferences={}
    )

    return Constraints(hard=hard, soft=soft)

def build_blueprint(n: UserProfileNormalized, c: Constraints) -> Blueprint:
    # baseline sessions
    baseline = 3 if n.activity_level in ["sedentary", "low"] else 4
    sessions_per_week = max(n.days_per_week_target_min, min(baseline, n.days_per_week_target_max))

    templates = [
        SessionTemplate(code="A", goal="strength_full_body", focus="movement_patterns"),
        SessionTemplate(code="B", goal="cardio_zone2_mobility", focus="aerobic_base"),
        SessionTemplate(code="C", goal="strength_core_balance", focus="stability"),
    ]

    return Blueprint(
        weeks_horizon=2,
        sessions_per_week=sessions_per_week,
        session_duration_min=n.time_per_session_min,
        intensity_target_rpe_min=4,
        intensity_target_rpe_max=c.hard.max_intensity_rpe,
        session_templates=templates,
        progression_plan_outline={
            "rule": "If adherence >= 80% and soreness <= moderate: +1 total set OR +5 min zone2 next week",
            "else": "Maintain or reduce volume"
        }
    )

def load_exercise_catalog() -> List[Exercise]:
    # Catálogo mínimo de ejemplo (luego lo expandes a JSON/DB)
    return [
        Exercise(
            id="ex_bw_squat_to_box",
            name="Sentadilla a caja (peso corporal)",
            modality="strength",
            equipment_tags=["none"],
            difficulty="easy",
            impact_level="low",
            contraindication_tags=["deep_knee_flexion_heavy"],
            muscle_groups=["legs"],
            alternatives_ids=["ex_sit_to_stand"]
        ),
        Exercise(
            id="ex_sit_to_stand",
            name="Sit-to-stand (silla)",
            modality="strength",
            equipment_tags=["chair"],
            difficulty="easy",
            impact_level="low",
            contraindication_tags=[],
            muscle_groups=["legs"],
            alternatives_ids=[]
        ),
        Exercise(
            id="ex_walk_zone2",
            name="Caminata (Zona 2)",
            modality="cardio",
            equipment_tags=["none"],
            difficulty="easy",
            impact_level="low",
            contraindication_tags=[],
            muscle_groups=[],
            alternatives_ids=[]
        ),
        Exercise(
            id="ex_mobility_hips",
            name="Movilidad de cadera",
            modality="mobility",
            equipment_tags=["none"],
            difficulty="easy",
            impact_level="low",
            contraindication_tags=[],
            muscle_groups=[],
            alternatives_ids=[]
        ),
    ]

def filter_exercises(n: UserProfileNormalized, c: Constraints) -> List[Exercise]:
    all_ex = load_exercise_catalog()
    pool = []
    eq = set(n.equipment_tags + ["none"])
    forbidden = set(c.hard.forbidden_exercise_tags)

    for ex in all_ex:
        if forbidden.intersection(set(ex.contraindication_tags)):
            continue
        if not set(ex.equipment_tags).intersection(eq):
            continue
        if n.training_experience == "beginner" and ex.difficulty == "hard":
            continue
        pool.append(ex)

    if not pool:
        pool = [e for e in all_ex if "none" in e.equipment_tags]
    return pool


def apply_iteration_feedback(
    user_message: str,
    constraints: Constraints,
    blueprint: Blueprint,
    exercise_pool: List[Exercise],
) -> Tuple[Constraints, Blueprint, List[Exercise], List[str]]:
    """
    Applies a small set of deterministic updates based on user feedback so that
    iteration requests can affect constraints/blueprint before the AI call.
    """
    message = (user_message or "").strip().lower()
    if not message:
        return constraints, blueprint, exercise_pool, []

    hard = constraints.hard.model_copy(deep=True)
    soft = constraints.soft.model_copy(deep=True)
    updated_blueprint = blueprint.model_copy(deep=True)
    updated_pool = list(exercise_pool)
    notes: List[str] = []

    minutes_match = re.search(r"(\d{2,3})\s*(min|mins|minutes|minutos)", message)
    if minutes_match:
        requested_minutes = max(10, min(120, int(minutes_match.group(1))))
        if requested_minutes != updated_blueprint.session_duration_min:
            updated_blueprint = updated_blueprint.model_copy(
                update={"session_duration_min": requested_minutes}
            )
            notes.append(f"session_duration_min updated to {requested_minutes}")

    days_match = re.search(r"(\d)\s*(day|days|días|dias)", message)
    if days_match:
        requested_days = max(1, min(hard.max_sessions_per_week, int(days_match.group(1))))
        if requested_days != updated_blueprint.sessions_per_week:
            hard = hard.model_copy(
                update={"min_rest_days_per_week": max(2, 7 - requested_days)}
            )
            updated_blueprint = updated_blueprint.model_copy(
                update={"sessions_per_week": requested_days}
            )
            notes.append(f"sessions_per_week updated to {requested_days}")

    preference_keywords = {
        "cardio": "cardio_zone2",
        "movilidad": "mobility",
        "mobility": "mobility",
        "fuerza": "strength",
        "strength": "strength",
    }
    preferred_updates = []
    for keyword, preference in preference_keywords.items():
        if keyword in message and preference not in preferred_updates:
            preferred_updates.append(preference)
    if preferred_updates:
        remaining = [p for p in soft.preferred_session_types if p not in preferred_updates]
        soft = soft.model_copy(update={"preferred_session_types": preferred_updates + remaining})
        notes.append(f"preferred_session_types reordered to prioritize {preferred_updates}")

    banned_name_keywords = {
        "sentadilla": "sentadilla",
        "squat": "sentadilla",
        "caminata": "caminata",
        "walk": "caminata",
        "cadera": "cadera",
        "hip": "cadera",
    }
    if any(token in message for token in ["sin ", "no ", "avoid", "evita", "evitar"]):
        banned_terms = {
            label for token, label in banned_name_keywords.items()
            if token in message
        }
        if banned_terms:
            filtered_pool = [
                ex for ex in updated_pool
                if not any(term in ex.name.lower() for term in banned_terms)
            ]
            if filtered_pool:
                updated_pool = filtered_pool
                notes.append(f"exercise_pool filtered to avoid {sorted(banned_terms)}")

    updated_constraints = constraints.model_copy(update={"hard": hard, "soft": soft})
    return updated_constraints, updated_blueprint, updated_pool, notes
