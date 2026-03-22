from fastapi import APIRouter, HTTPException

from app.schemas.models import DraftResponse, IterateRequest, FinalizeRequest, PlanDraft
from app.data.store import STORE  
from app.core.validator import validate_plan
from app.services.agent_service import generate_plan_draft_with_repair  

router = APIRouter()


@router.post("/draft", response_model=DraftResponse)
def draft(user_id: str):
    # 1) Debe existir intake context
    try:
        ctx = STORE.get_context(user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="No intake context found for user_id. Run POST /intake first.")

    # 2) Crear plan_id
    plan_id = STORE.new_plan_id()

    # 3) Generar plan con repair loop (ya incluye validación)
    plan, errors = generate_plan_draft_with_repair(
        plan_id=plan_id,
        version=1,
        user_profile=ctx.user_profile,
        constraints=ctx.constraints,
        blueprint=ctx.blueprint,
        exercise_pool=ctx.exercise_pool,
        max_attempts=3,
    )

    if errors:
        raise HTTPException(status_code=400, detail={"message": "Draft failed after repairs", "errors": errors})

    # 4) (Opcional) Re-validación final (consistente, con pool)
    ok, v_errors = validate_plan(plan, ctx.constraints, ctx.blueprint, ctx.exercise_pool)
    if not ok:
        raise HTTPException(status_code=400, detail={"message": "Draft failed final validation", "errors": v_errors})

    STORE.save_plan(plan_id, plan)
    return DraftResponse(plan=plan)


@router.post("/{plan_id}/iterate", response_model=DraftResponse)
def iterate(user_id: str, plan_id: str, req: IterateRequest):
    try:
        ctx = STORE.get_context(user_id)
        current: PlanDraft = STORE.get_plan(plan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Context or plan not found")

    new_version = current.version + 1

    # Nota: por ahora no estamos aplicando el user_message estructuradamente,
    # pero al menos lo incluimos en el prompt de reparación.
    # (Luego hacemos un parser a cambios soft.)
    plan, errors = generate_plan_draft_with_repair(
        plan_id=plan_id,
        version=new_version,
        user_profile=ctx.user_profile,
        constraints=ctx.constraints,
        blueprint=ctx.blueprint,
        exercise_pool=ctx.exercise_pool,
        max_attempts=3,
    )

    if errors:
        raise HTTPException(status_code=400, detail={"message": "Iteration failed after repairs", "errors": errors})

    ok, v_errors = validate_plan(plan, ctx.constraints, ctx.blueprint, ctx.exercise_pool)
    if not ok:
        raise HTTPException(status_code=400, detail={"message": "Iteration failed final validation", "errors": v_errors})

    STORE.save_plan(plan_id, plan)
    return DraftResponse(plan=plan)


@router.post("/{plan_id}/finalize", response_model=DraftResponse)
def finalize(user_id: str, plan_id: str, req: FinalizeRequest):
    if not req.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required to finalize")

    try:
        ctx = STORE.get_context(user_id)
        plan: PlanDraft = STORE.get_plan(plan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Context or plan not found")

    ok, errors = validate_plan(plan, ctx.constraints, ctx.blueprint, ctx.exercise_pool)
    if not ok:
        raise HTTPException(status_code=400, detail={"message": "Plan failed validation", "errors": errors})

    finalized = plan.model_copy(update={"status": "FINAL"})
    STORE.save_plan(plan_id, finalized)
    return DraftResponse(plan=finalized)


@router.get("/{plan_id}", response_model=DraftResponse)
def get_plan(plan_id: str):
    try:
        plan = STORE.get_plan(plan_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Plan not found")
    return DraftResponse(plan=plan)