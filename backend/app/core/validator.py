from __future__ import annotations

from typing import List, Tuple, Dict, Set
from app.schemas.models import PlanDraft, Constraints, Blueprint, Exercise

VALID_DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

def _pool_index(pool: List[Exercise]) -> Dict[str, Exercise]:
    return {e.id: e for e in pool}

def validate_plan(
    plan: PlanDraft,
    c: Constraints,
    b: Blueprint,
    exercise_pool: List[Exercise] | None = None,
    *,
    expect_status: str = "DRAFT",
    minutes_tolerance: int = 10,
) -> Tuple[bool, List[str]]:
    """
    Strict validator:
    - Checks global constraints
    - Checks session structure
    - Checks exercise content & IDs exist in pool
    - Checks weekly_schedule format
    Returns (ok, errors)
    """
    errors: List[str] = []

    # --------------------
    # 1) Global checks
    # --------------------
    if plan.status != expect_status:
        errors.append(f"status_must_be:{expect_status}")

    if plan.sessions_per_week != b.sessions_per_week:
        errors.append("sessions_per_week_mismatch")

    if plan.max_rpe > c.hard.max_intensity_rpe:
        errors.append("max_rpe_exceeds_constraint")

    if plan.rest_days_per_week < c.hard.min_rest_days_per_week:
        errors.append("insufficient_rest_days")

    # --------------------
    # 2) Sessions count
    # --------------------
    if len(plan.sessions) != b.sessions_per_week:
        errors.append("sessions_count_mismatch")

    # --------------------
    # 3) weekly_schedule checks
    # --------------------
    if len(plan.weekly_schedule) != b.sessions_per_week:
        errors.append("weekly_schedule_length_mismatch")
    else:
        used_days: Set[str] = set()
        for i, item in enumerate(plan.weekly_schedule):
            # Permit formats like "Lunes:A" or just "Lunes"
            day = item.split(":")[0].strip()
            if day not in VALID_DAYS:
                errors.append(f"weekly_schedule_invalid_day:{i}:{day}")
            if day in used_days:
                errors.append(f"weekly_schedule_repeated_day:{day}")
            used_days.add(day)

    # --------------------
    # 4) Session structure & timing
    # --------------------
    max_minutes_allowed = b.session_duration_min + minutes_tolerance
    for s in plan.sessions:
        if s.estimated_minutes > max_minutes_allowed:
            errors.append(f"session_too_long:{s.session_code}")

        # Must have some content in each block (not empty everywhere)
        total_ex = len(s.warmup) + len(s.main) + len(s.cooldown)
        if total_ex == 0:
            errors.append(f"empty_session:{s.session_code}")

        # Minimum structure expectations (soft-strict)
        if len(s.main) == 0:
            errors.append(f"missing_main_block:{s.session_code}")
        if len(s.warmup) == 0:
            errors.append(f"missing_warmup_block:{s.session_code}")
        if len(s.cooldown) == 0:
            errors.append(f"missing_cooldown_block:{s.session_code}")

    # --------------------
    # 5) Exercise-level checks
    # --------------------
    forbidden = set(c.hard.forbidden_exercise_tags)
    pool_map = _pool_index(exercise_pool) if exercise_pool is not None else {}

    def check_exercise(ex, where: str):
        # RPE bound
        if ex.rpe is not None and ex.rpe > plan.max_rpe:
            errors.append(f"exercise_rpe_too_high:{where}:{ex.name}")

        # Required volume/time fields
        has_strength_volume = (ex.sets is not None and ex.reps is not None)
        has_time = (ex.minutes is not None)

        if not (has_strength_volume or has_time):
            errors.append(f"exercise_missing_sets_reps_or_minutes:{where}:{ex.name}")

        # Check tags against forbidden
        if forbidden.intersection(set(ex.tags)):
            errors.append(f"forbidden_tag_used:{where}:{ex.name}")

        # Check exercise_id exists in pool (if pool provided)
        if pool_map:
            if ex.exercise_id not in pool_map:
                errors.append(f"exercise_id_not_in_pool:{where}:{ex.exercise_id}")
            else:
                # Check contraindications from pool entry too
                pool_ex = pool_map[ex.exercise_id]
                if forbidden.intersection(set(pool_ex.contraindication_tags)):
                    errors.append(f"pool_contraindication_violation:{where}:{ex.exercise_id}")

    for s in plan.sessions:
        for idx, ex in enumerate(s.warmup):
            check_exercise(ex, f"{s.session_code}.warmup[{idx}]")
        for idx, ex in enumerate(s.main):
            check_exercise(ex, f"{s.session_code}.main[{idx}]")
        for idx, ex in enumerate(s.cooldown):
            check_exercise(ex, f"{s.session_code}.cooldown[{idx}]")

    return (len(errors) == 0), errors