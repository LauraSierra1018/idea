from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
from uuid import uuid4

@dataclass
class PlanningContext:
    user_profile: Any
    constraints: Any
    blueprint: Any
    exercise_pool: Any

class InMemoryStore:
    def __init__(self) -> None:
        self.user_ctx: Dict[str, PlanningContext] = {}
        self.plans: Dict[str, Any] = {}

    def set_context(self, user_id: str, ctx: PlanningContext) -> None:
        self.user_ctx[user_id] = ctx

    def get_context(self, user_id: str) -> PlanningContext:
        return self.user_ctx[user_id]

    def new_plan_id(self) -> str:
        return str(uuid4())

    def save_plan(self, plan_id: str, plan_obj: Any) -> None:
        self.plans[plan_id] = plan_obj

    def get_plan(self, plan_id: str) -> Any:
        return self.plans[plan_id]

STORE = InMemoryStore()