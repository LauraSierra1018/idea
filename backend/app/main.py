from fastapi import FastAPI
from app.api.routes.intake import router as intake_router
from app.api.routes.plan import router as plan_router

app = FastAPI(title="Backend Planner")

app.include_router(intake_router, prefix="/intake", tags=["intake"])
app.include_router(plan_router, prefix="/plan", tags=["plan"])

print(">>> LOADED app/main.py OK <<<")
print(">>> ROUTES:", [r.path for r in app.router.routes])