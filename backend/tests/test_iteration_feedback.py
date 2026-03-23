import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.policy_engine import apply_iteration_feedback
from app.data.store import STORE, PlanningContext
from app.schemas.models import (
    Blueprint,
    Constraints,
    ConstraintsHard,
    ConstraintsSoft,
    Exercise,
    IterateRequest,
    PlanDraft,
    PlanExercise,
    PlanSession,
    SessionTemplate,
    UserProfileNormalized,
)
from app.schemas.plan_schema import get_plan_draft_schema


def build_context() -> PlanningContext:
    user_profile = UserProfileNormalized(
        age=35,
        sex="female",
        weight_kg=65,
        height_cm=168,
        activity_level="low",
        training_experience="beginner",
        injury_tags=[],
        medical_tags=[],
        time_per_session_min=30,
        days_per_week_target_min=2,
        days_per_week_target_max=4,
        environment="home",
        equipment_tags=["none"],
        goal_primary="health",
        risk_level="low",
    )
    constraints = Constraints(
        hard=ConstraintsHard(
            max_sessions_per_week=4,
            max_intensity_rpe=6,
            min_rest_days_per_week=4,
            forbidden_exercise_tags=[],
            required_components=["warmup", "cooldown"],
            progression_caps={},
        ),
        soft=ConstraintsSoft(preferred_session_types=["strength", "mobility", "cardio_zone2"]),
    )
    blueprint = Blueprint(
        weeks_horizon=2,
        sessions_per_week=3,
        session_duration_min=30,
        intensity_target_rpe_min=4,
        intensity_target_rpe_max=6,
        session_templates=[
            SessionTemplate(code="A", goal="strength_full_body"),
            SessionTemplate(code="B", goal="cardio_zone2_mobility"),
        ],
        progression_plan_outline={},
    )
    exercise_pool = [
        Exercise(
            id="ex_walk_zone2",
            name="Caminata (Zona 2)",
            modality="cardio",
            equipment_tags=["none"],
            difficulty="easy",
            impact_level="low",
            contraindication_tags=[],
            muscle_groups=[],
            alternatives_ids=[],
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
            alternatives_ids=[],
        ),
    ]
    return PlanningContext(
        user_profile=user_profile,
        constraints=constraints,
        blueprint=blueprint,
        exercise_pool=exercise_pool,
    )


def build_plan(plan_id: str, version: int, sessions_per_week: int, minutes: int) -> PlanDraft:
    session = PlanSession(
        session_code="A",
        day_label="Lunes",
        warmup=[PlanExercise(exercise_id="ex_mobility_hips", name="Movilidad de cadera", minutes=5, rpe=2)],
        main=[PlanExercise(exercise_id="ex_walk_zone2", name="Caminata (Zona 2)", minutes=20, rpe=4)],
        cooldown=[PlanExercise(exercise_id="ex_mobility_hips", name="Movilidad de cadera", minutes=5, rpe=2)],
        estimated_minutes=minutes,
    )
    sessions = []
    schedule = []
    valid_days = ["Lunes", "Miércoles", "Viernes", "Sábado"]
    for index in range(sessions_per_week):
        sessions.append(session.model_copy(update={"session_code": chr(65 + index), "day_label": valid_days[index]}))
        schedule.append(f"{valid_days[index]}:{chr(65 + index)}")
    return PlanDraft(
        plan_id=plan_id,
        version=version,
        status="DRAFT",
        sessions_per_week=sessions_per_week,
        max_rpe=6,
        rest_days_per_week=max(2, 7 - sessions_per_week),
        weekly_schedule=schedule,
        sessions=sessions,
        progression_notes="Mantener",
        rationale_summary="Plan de prueba",
        questions_to_finalize=[],
        assumptions=[],
        safety_flags=[],
    )


class IterationFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        STORE.user_ctx.clear()
        STORE.plans.clear()

    def test_apply_iteration_feedback_updates_blueprint_pool_and_preferences(self):
        ctx = build_context()

        updated_constraints, updated_blueprint, updated_pool, notes = apply_iteration_feedback(
            "Quiero 2 días, sesiones de 25 minutos, más cardio y sin caminata",
            ctx.constraints,
            ctx.blueprint,
            ctx.exercise_pool,
        )

        self.assertEqual(updated_blueprint.sessions_per_week, 2)
        self.assertEqual(updated_blueprint.session_duration_min, 25)
        self.assertEqual(updated_constraints.hard.min_rest_days_per_week, 5)
        self.assertEqual(updated_constraints.soft.preferred_session_types[0], "cardio_zone2")
        self.assertEqual(len(updated_pool), 1)
        self.assertTrue(any("sessions_per_week updated to 2" in note for note in notes))

    def test_plan_schema_matches_plan_draft(self):
        schema = get_plan_draft_schema()

        self.assertEqual(schema["title"], "PlanDraft")
        self.assertIn("properties", schema)
        self.assertIn("sessions", schema["properties"])

    @patch("app.api.routes.plan.generate_plan_draft_with_repair")
    def test_iterate_route_applies_feedback_before_generation(self, mock_generate):
        ctx = build_context()
        STORE.set_context("user-1", ctx)
        STORE.save_plan("plan-1", build_plan("plan-1", 1, 3, 30))

        mock_generate.return_value = (build_plan("plan-1", 2, 2, 25), [])
        client = TestClient(app)

        response = client.post(
            "/plan/plan-1/iterate",
            params={"user_id": "user-1"},
            json=IterateRequest(
                user_message="Solo 2 días, sesiones de 25 minutos y más cardio"
            ).model_dump(),
        )

        self.assertEqual(response.status_code, 200)
        kwargs = mock_generate.call_args.kwargs
        self.assertEqual(kwargs["blueprint"].sessions_per_week, 2)
        self.assertEqual(kwargs["blueprint"].session_duration_min, 25)
        self.assertEqual(kwargs["constraints"].soft.preferred_session_types[0], "cardio_zone2")
        self.assertIn("Solo 2 días", kwargs["iteration_feedback"])

        updated_ctx = STORE.get_context("user-1")
        self.assertEqual(updated_ctx.blueprint.sessions_per_week, 2)
        self.assertEqual(updated_ctx.blueprint.session_duration_min, 25)

    @patch("app.api.routes.plan.generate_plan_draft_with_repair")
    def test_finalize_uses_persisted_iteration_context(self, mock_generate):
        ctx = build_context()
        STORE.set_context("user-2", ctx)
        STORE.save_plan("plan-2", build_plan("plan-2", 1, 3, 30))
        mock_generate.return_value = (build_plan("plan-2", 2, 2, 25), [])

        client = TestClient(app)
        iterate_response = client.post(
            "/plan/plan-2/iterate",
            params={"user_id": "user-2"},
            json=IterateRequest(
                user_message="Quiero 2 días y sesiones de 25 minutos"
            ).model_dump(),
        )
        self.assertEqual(iterate_response.status_code, 200)

        finalize_response = client.post(
            "/plan/plan-2/finalize",
            params={"user_id": "user-2"},
            json={"confirm": True},
        )
        self.assertEqual(finalize_response.status_code, 200)
        self.assertEqual(finalize_response.json()["plan"]["status"], "FINAL")


if __name__ == "__main__":
    unittest.main()
