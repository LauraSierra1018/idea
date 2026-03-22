from fastapi import APIRouter
from app.schemas.models import UserProfileRaw, IntakeResponse
from app.core.policy_engine import normalize_profile, derive_constraints, build_blueprint, filter_exercises
from app.data.store import STORE, PlanningContext

router = APIRouter()

@router.post("/", response_model=IntakeResponse)
def intake(user_id: str, body: UserProfileRaw):
    normalized = normalize_profile(body)
    constraints = derive_constraints(normalized)
    blueprint = build_blueprint(normalized, constraints)
    pool = filter_exercises(normalized, constraints)

    STORE.set_context(
        user_id,
        PlanningContext(
            user_profile=normalized,
            constraints=constraints,
            blueprint=blueprint,
            exercise_pool=pool,
        ),
    )

    return IntakeResponse(
        user_profile=normalized,
        constraints=constraints,
        blueprint=blueprint,
        exercise_pool=pool,
    )