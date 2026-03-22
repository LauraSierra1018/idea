from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

ActivityLevel = Literal["sedentary", "low", "medium", "high"]
ExperienceLevel = Literal["beginner", "intermediate"]
RiskLevel = Literal["low", "medium", "high"]
Environment = Literal["home", "gym", "mixed"]
PlanStatus = Literal["DRAFT", "FINAL"]

class UserProfileRaw(BaseModel):
    age: int = Field(..., ge=10, le=100)
    sex: Literal["female", "male", "other"]
    weight_kg: float = Field(..., ge=25, le=300)
    height_cm: float = Field(..., ge=120, le=230)

    activity_level_choice: ActivityLevel
    activity_history_text: Optional[str] = None

    injuries_text: Optional[str] = None
    medical_flags: List[str] = Field(default_factory=list)

    time_per_session_min: int = Field(..., ge=10, le=120)
    days_per_week_preferred: int = Field(..., ge=1, le=7)

    equipment_available: List[str] = Field(default_factory=list)
    goal_primary: Literal["fat_loss", "recomposition", "muscle_gain", "health", "mobility"]

class UserProfileNormalized(BaseModel):
    age: int
    sex: str
    weight_kg: float
    height_cm: float

    activity_level: ActivityLevel
    training_experience: ExperienceLevel
    injury_tags: List[str]
    medical_tags: List[str]

    time_per_session_min: int
    days_per_week_target_min: int
    days_per_week_target_max: int

    environment: Environment
    equipment_tags: List[str]
    goal_primary: str
    risk_level: RiskLevel

class ConstraintsHard(BaseModel):
    max_sessions_per_week: int
    max_intensity_rpe: int
    min_rest_days_per_week: int
    forbidden_exercise_tags: List[str] = Field(default_factory=list)
    required_components: List[str] = Field(default_factory=list)
    progression_caps: Dict[str, Any] = Field(default_factory=dict)

class ConstraintsSoft(BaseModel):
    preferred_session_types: List[str] = Field(default_factory=list)
    disliked_exercise_tags: List[str] = Field(default_factory=list)
    schedule_preferences: Dict[str, Any] = Field(default_factory=dict)

class Constraints(BaseModel):
    hard: ConstraintsHard
    soft: ConstraintsSoft

class SessionTemplate(BaseModel):
    code: str
    goal: str
    focus: Optional[str] = None

class Blueprint(BaseModel):
    weeks_horizon: int
    sessions_per_week: int
    session_duration_min: int
    intensity_target_rpe_min: int
    intensity_target_rpe_max: int
    session_templates: List[SessionTemplate]
    progression_plan_outline: Dict[str, Any] = Field(default_factory=dict)

class Exercise(BaseModel):
    id: str
    name: str
    modality: Literal["strength", "cardio", "mobility"]
    equipment_tags: List[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"]
    impact_level: Literal["low", "medium", "high"]
    contraindication_tags: List[str] = Field(default_factory=list)
    muscle_groups: List[str] = Field(default_factory=list)
    alternatives_ids: List[str] = Field(default_factory=list)

class PlanExercise(BaseModel):
    exercise_id: str
    name: str
    sets: Optional[int] = None
    reps: Optional[int] = None
    minutes: Optional[int] = None
    rpe: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class PlanSession(BaseModel):
    session_code: str
    day_label: str
    warmup: List[PlanExercise] = Field(default_factory=list)
    main: List[PlanExercise] = Field(default_factory=list)
    cooldown: List[PlanExercise] = Field(default_factory=list)
    estimated_minutes: int = Field(..., ge=5, le=180)

class PlanDraft(BaseModel):
    plan_id: str
    version: int
    status: PlanStatus
    sessions_per_week: int
    max_rpe: int
    rest_days_per_week: int
    weekly_schedule: List[str] = Field(default_factory=list)
    sessions: List[PlanSession]
    progression_notes: str
    rationale_summary: str
    questions_to_finalize: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    safety_flags: List[str] = Field(default_factory=list)

class IntakeResponse(BaseModel):
    user_profile: UserProfileNormalized
    constraints: Constraints
    blueprint: Blueprint
    exercise_pool: List[Exercise]

class DraftResponse(BaseModel):
    plan: PlanDraft

class IterateRequest(BaseModel):
    user_message: str

class FinalizeRequest(BaseModel):
    confirm: bool = False