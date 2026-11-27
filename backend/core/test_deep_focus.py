"""Deep Focus sessions: 30/60-minute benchmarks, badges, and the strict
tab-switch rule (a session interrupted before its benchmark earns nothing)."""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import FocusSession, User


class DeepFocusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.learner = User.objects.create_user(
            "focus-learner@test.local", "SafePass123!", full_name="Focus Learner", is_verified=True
        )
        self.other = User.objects.create_user(
            "focus-other@test.local", "SafePass123!", full_name="Other Learner", is_verified=True
        )
        self.instructor = User.objects.create_user(
            "focus-teacher@test.local", "SafePass123!", full_name="Focus Teacher",
            role="instructor", is_verified=True, instructor_approved=True,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def start(self, target=30, user=None):
        if user is not None:
            self.auth(user)
        return self.client.post("/api/focus-sessions/start/", {"target_minutes": target}, format="json")

    def test_start_accepts_30_and_60(self):
        for target in (30, 60):
            self.auth(self.learner)
            response = self.start(target)
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["target_minutes"], target)
            self.assertEqual(response.data["status"], "active")
            self.assertEqual(response.data["focused_seconds"], 0)
            # End it so the next target can start.
            self.assertEqual(self.client.post(f"/api/focus-sessions/{response.data['id']}/end/", {"reason": "interrupted"}, format="json").status_code, 200)

    def test_start_rejects_other_targets_and_missing_target(self):
        self.auth(self.learner)
        self.assertEqual(self.start(10).status_code, 400)
        self.assertEqual(self.start(45).status_code, 400)
        response = self.client.post("/api/focus-sessions/start/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_instructor_cannot_start(self):
        self.assertEqual(self.start(30, user=self.instructor).status_code, 403)

    def test_second_active_session_is_rejected(self):
        self.assertEqual(self.start(30, user=self.learner).status_code, 201)
        self.assertEqual(self.start(60).status_code, 400)

    def test_heartbeat_is_monotonic_and_capped(self):
        session = self.start(30, user=self.learner).data
        url = f"/api/focus-sessions/{session['id']}/heartbeat/"
        response = self.client.post(url, {"focused_seconds": 100}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["focused_seconds"], 100)
        self.assertEqual(response.data["status"], "active")
        # A lower value is ignored, not an error.
        response = self.client.post(url, {"focused_seconds": 50}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["focused_seconds"], 100)
        # Above the target it caps and completes.
        response = self.client.post(url, {"focused_seconds": 99999}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["focused_seconds"], 1800)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["badge"], {"target_minutes": 30, "count": 1})

    def test_reaching_target_returns_badge_with_count_1(self):
        session = self.start(60, user=self.learner).data
        response = self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 3600}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["badge"], {"target_minutes": 60, "count": 1})
        # A completed session accepts no further heartbeats.
        self.assertEqual(self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 3600}, format="json").status_code, 400)

    def test_second_completed_session_increments_only_its_own_count(self):
        for _ in range(2):
            session = self.start(30, user=self.learner).data
            response = self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 1800}, format="json")
            self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["badge"], {"target_minutes": 30, "count": 2})
        badges = self.client.get("/api/focus-sessions/badges/").data
        self.assertEqual(badges, [{"target_minutes": 30, "count": 2}])

    def test_interrupt_gives_no_badge_and_badges_stay_empty(self):
        session = self.start(30, user=self.learner).data
        self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 900}, format="json")
        response = self.client.post(f"/api/focus-sessions/{session['id']}/end/", {"reason": "interrupted"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "interrupted")
        self.assertNotIn("badge", response.data)
        self.assertEqual(self.client.get("/api/focus-sessions/badges/").data, [])
        # Ending an already-ended session is a 400.
        self.assertEqual(self.client.post(f"/api/focus-sessions/{session['id']}/end/", {"reason": "interrupted"}, format="json").status_code, 400)

    def test_end_completed_before_benchmark_is_rejected(self):
        session = self.start(30, user=self.learner).data
        self.assertEqual(self.client.post(f"/api/focus-sessions/{session['id']}/end/", {"reason": "completed"}, format="json").status_code, 400)

    def test_other_learner_cannot_touch_a_session(self):
        session = self.start(30, user=self.learner).data
        self.auth(self.other)
        self.assertEqual(self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 1800}, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"/api/focus-sessions/{session['id']}/end/", {"reason": "interrupted"}, format="json").status_code, 403)
        self.assertEqual(self.client.get(f"/api/focus-sessions/{session['id']}/").status_code, 403)
        # And the other learner's own badges are empty.
        self.assertEqual(self.client.get("/api/focus-sessions/badges/").data, [])

    def test_anonymous_is_denied(self):
        response = self.client.post("/api/focus-sessions/start/", {"target_minutes": 30}, format="json")
        self.assertIn(response.status_code, (401, 403))
        self.assertIn(self.client.get("/api/focus-sessions/badges/").status_code, (401, 403))

    def test_badges_endpoint_returns_only_own_counts(self):
        session = self.start(60, user=self.learner).data
        self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 3600}, format="json")
        self.auth(self.other)
        self.assertEqual(self.client.get("/api/focus-sessions/badges/").data, [])
        self.auth(self.learner)
        self.assertEqual(self.client.get("/api/focus-sessions/badges/").data, [{"target_minutes": 60, "count": 1}])

    def test_profile_summary_includes_focus_badges(self):
        session = self.start(30, user=self.learner).data
        self.client.post(f"/api/focus-sessions/{session['id']}/heartbeat/", {"focused_seconds": 1800}, format="json")
        response = self.client.get("/api/profile/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["focus_badges"], [{"target_minutes": 30, "count": 1}])
