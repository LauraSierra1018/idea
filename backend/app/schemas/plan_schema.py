from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, Field
from app.schemas.models import PlanDraft


def get_plan_draft_schema() -> dict:
    """
    Returns the JSON schema used to force the AI agent
    to generate a PlanDraft object.

    This ensures the model output matches exactly the
    PlanDraft structure defined in models.py.
    """
    return PlanDraft.model_json_schema()

class Session(BaseModel):
    day: Literal["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    type: Literal["fuerza", "cardio_zona2", "movilidad"]
    minutes: int = Field(ge=10, le=120)
    note: str
