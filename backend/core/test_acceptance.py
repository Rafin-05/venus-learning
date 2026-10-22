import json
import re
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Certificate, Contest, ContestAttempt, EmailToken, Enrollment, Lesson,
    LessonProgress, LoginAttempt, Problem, Question, Quiz, QuizAttempt, Rating,
    Submission, SupportTicket, Unit, User,
)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AcceptanceBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.learner = self.user("learner@example.test", is_verified=True)
        self.unverified = self.user("unverified@example.test")
        self.blocked = self.user("blocked@example.test", is_verified=True, is_active=False)
        self.instructor = self.user("instructor@example.test", role="instructor", is_verified=True, instructor_approved=True)
        self.pending_instructor = self.user("pending-inst@example.test", role="instructor", is_verified=True)
        self.admin = self.user("admin@example.test", role="admin", is_verified=True, is_staff=True, is_superuser=True, instructor_approved=True)
        self.course = self.course_for(self.instructor, "Approved", "approved")
        self.pending = self.course_for(self.instructor, "Pending", "pending")
        self.unit = Unit.objects.create(course=self.course, title="Unit", position=1)
        self.video = Lesson.objects.create(unit=self.unit, title="Video", lesson_type="video", video_url="https://video.test/a", position=1)
        self.coding = Lesson.objects.create(unit=self.unit, title="Code", lesson_type="coding", coding_language="python", coding_expected_output="ok\n", position=2)
        self.enrollment = Enrollment.objects.create(learner=self.learner, course=self.course)
        self.quiz = Quiz.objects.create(course=self.course, owner=self.instructor, title="Quiz", pass_percentage=50)
        self.question = Question.objects.create(quiz=self.quiz, question="One?", option_a="yes", option_b="no", correct_answer="a")
        self.problem = Problem.objects.create(owner=self.instructor, title="Echo", statement="echo", test_cases=[{"input": "", "output": "ok\n"}])

    def user(self, email, password="SafePass123!", **kwargs):
        return User.objects.create_user(email, password, full_name=email.split("@")[0], **kwargs)

    def course_for(self, instructor, title, status="pending"):
        return __import__("core.models", fromlist=["Course"]).Course.objects.create(
            title=title, description="Description", instructor=instructor, status=status
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def post(self, url, data=None, user=None, **kwargs):
        if user is not None:
            self.auth(user)
        return self.client.post(url, data or {}, format="json", **kwargs)

    def patch(self, url, data=None, user=None):
        if user is not None:
            self.auth(user)
        return self.client.patch(url, data or {}, format="json")

    def assert_denied(self, response):
        self.assertIn(response.status_code, (401, 403, 404, 405))


class CatalogAndAuthorizationTests(AcceptanceBase):
    def test_public_catalog_only_approved_and_no_secret_fields(self):
        r = self.client.get("/api/courses/")
        self.assertEqual(r.status_code, 200)
        rows = r.data if isinstance(r.data, list) else r.data.get("results", [])
        self.assertTrue(all(x["id"] != self.pending.id for x in rows))
        self.assertNotIn("password", json.dumps(r.data).lower())
        detail = self.client.get(f"/api/courses/{self.course.id}/curriculum/")
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn("coding_expected_output", json.dumps(detail.data))

    def test_pending_owner_can_edit_but_other_users_cannot(self):
        r = self.patch(f"/api/courses/{self.pending.id}/", {"title": "Changed"}, user=self.instructor)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data.get("status"), "pending")
        self.assert_denied(self.patch(f"/api/courses/{self.pending.id}/", {"title": "No"}, user=self.learner))

    def test_unapproved_instructor_cannot_create_course(self):
        self.assert_denied(self.post("/api/courses/", {"title": "X", "description": "x"}, user=self.pending_instructor))

    def test_anonymous_and_learner_cannot_mutate_courses_units_lessons_quizzes_problems(self):
        cases = [
            ("/api/courses/", {"title": "x", "description": "x"}),
            ("/api/units/", {"course": self.course.id, "title": "x"}),
            ("/api/lessons/", {"unit": self.unit.id, "title": "x"}),
            ("/api/quizzes/", {"course": self.course.id, "title": "x", "questions": []}),
            ("/api/problems/", {"title": "x", "statement": "x"}),
        ]
        for url, body in cases:
            self.assert_denied(self.client.post(url, body, format="json"))
            self.assert_denied(self.post(url, body, user=self.learner))

    def test_instructor_ownership_is_enforced_for_nested_resources(self):
        other = self.user("other-inst@example.test", role="instructor", is_verified=True, instructor_approved=True)
        self.assert_denied(self.patch(f"/api/units/{self.unit.id}/", {"title": "x"}, user=other))
        self.assert_denied(self.patch(f"/api/lessons/{self.video.id}/", {"title": "x"}, user=other))
        self.assert_denied(self.patch(f"/api/quizzes/{self.quiz.id}/", {"title": "x"}, user=other))
        self.assert_denied(self.patch(f"/api/problems/{self.problem.id}/", {"title": "x"}, user=other))

    def test_enrollment_is_required_to_read_lesson_and_submit_quiz(self):
        outsider = self.user("outsider@example.test", is_verified=True)
        self.assert_denied(self.client.get(f"/api/lessons/{self.video.id}/", format="json"))
        self.assert_denied(self.post(f"/api/quizzes/{self.quiz.id}/submit/", {"answers": {str(self.question.id): "a"}}, user=outsider))

    def test_numeric_progress_range_and_coding_cannot_self_complete(self):
        self.assertEqual(self.patch(f"/api/lessons/{self.video.id}/progress/", {"progress": 101}, user=self.learner).status_code, 400)
        r = self.patch(f"/api/lessons/{self.coding.id}/progress/", {"progress": 100}, user=self.learner)
        self.assertNotEqual(r.status_code, 500)
        if r.status_code < 300:
            self.assertFalse(LessonProgress.objects.get(enrollment=self.enrollment, lesson=self.coding).completed_at)

    def test_enroll_is_idempotent_and_pending_course_is_not_publicly_enrollable(self):
        self.assertIn(self.post(f"/api/courses/{self.course.id}/enroll/", user=self.learner).status_code, (200, 201, 204, 409))
        self.assertIn(self.post(f"/api/courses/{self.pending.id}/enroll/", user=self.learner).status_code, (403, 404))


class QuizAndCertificateTests(AcceptanceBase):
    def test_learner_quiz_payload_hides_answer_key_but_owner_can_edit(self):
        self.auth(self.learner)
        data = self.client.get(f"/api/quizzes/{self.quiz.id}/").data
        self.assertNotIn("correct_answer", json.dumps(data))
        self.auth(self.instructor)
        r = self.client.get(f"/api/quizzes/{self.quiz.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("correct_answer", json.dumps(r.data))

    def test_nested_quiz_write_preserves_correct_answer_and_rejects_empty(self):
        r = self.patch(f"/api/quizzes/{self.quiz.id}/", {"title": "Updated", "questions": [{"id": self.question.id, "question": "Changed", "option_a": "yes", "option_b": "no", "correct_answer": "b"}]}, user=self.instructor)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.quiz.questions.order_by("id").first().correct_answer, "b")
        self.assertEqual(self.post("/api/quizzes/", {"course": self.course.id, "title": "Empty", "questions": []}, user=self.instructor).status_code, 400)

    def test_malformed_quiz_ids_and_answers_return_400_not_500(self):
        self.assertEqual(self.post(f"/api/quizzes/{self.quiz.id}/submit/", {"answers": {"not-an-id": "a"}}, user=self.learner).status_code, 400)
        self.assertEqual(self.post(f"/api/quizzes/{self.quiz.id}/submit/", {"answers": ["a"]}, user=self.learner).status_code, 400)
        self.assertIn(self.post("/api/quizzes/not-a-number/submit/", {"answers": {}}, user=self.learner).status_code, (400, 404))

    def test_quiz_submit_rejects_top_level_non_object_json_without_side_effects(self):
        self.auth(self.learner)
        attempt_count = QuizAttempt.objects.count()
        points = self.learner.points
        payloads = [[], [{"answers": {str(self.question.id): "a"}}], "not-an-object", 42, True, None]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.generic(
                    "POST",
                    f"/api/quizzes/{self.quiz.id}/submit/",
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {"detail": "Request body must be a JSON object."})
                self.assertEqual(QuizAttempt.objects.count(), attempt_count)
                self.learner.refresh_from_db()
                self.assertEqual(self.learner.points, points)

        valid = self.client.generic(
            "POST",
            f"/api/quizzes/{self.quiz.id}/submit/",
            data=json.dumps({"answers": {str(self.question.id): "a"}}),
            content_type="application/json",
        )
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(QuizAttempt.objects.count(), attempt_count + 1)

    def test_quiz_attempt_hides_answer_payload(self):
        self.post(f"/api/quizzes/{self.quiz.id}/submit/", {"answers": {str(self.question.id): "a"}}, user=self.learner)
        data = self.client.get("/api/quiz-attempts/").data
        self.assertNotIn("answers", json.dumps(data))

    def test_certificate_rejects_empty_and_incomplete_coding_and_missing_quiz_pass(self):
        empty = self.course_for(self.instructor, "Empty", "approved")
        Enrollment.objects.create(learner=self.learner, course=empty)
        self.assertIn(self.post(f"/api/courses/{empty.id}/certificate/", user=self.learner).status_code, (400, 409))
        self.assertEqual(self.post(f"/api/courses/{self.course.id}/certificate/", user=self.learner).status_code, 400)
        LessonProgress.objects.create(enrollment=self.enrollment, lesson=self.video, progress=100, completed_at=timezone.now())
        self.assertEqual(self.post(f"/api/courses/{self.course.id}/certificate/", user=self.learner).status_code, 400)

    def test_certificate_issues_once_after_all_requirements(self):
        LessonProgress.objects.create(enrollment=self.enrollment, lesson=self.video, progress=100, completed_at=timezone.now())
        LessonProgress.objects.create(enrollment=self.enrollment, lesson=self.coding, progress=100, completed_at=timezone.now())
        QuizAttempt.objects.create(learner=self.learner, quiz=self.quiz, score=1, total=1, percentage=100, passed=True)
        # Marking coding complete represents a successful server-side runner result.
        r = self.post(f"/api/courses/{self.course.id}/certificate/", user=self.learner)
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(self.post(f"/api/courses/{self.course.id}/certificate/", user=self.learner).status_code, 200)
        self.assertEqual(Certificate.objects.filter(learner=self.learner, course=self.course).count(), 1)


class CodingRatingAndStaffTests(AcceptanceBase):
    @override_settings(JUDGE0_URL="https://judge.test")
    @patch("core.views.urllib.request.urlopen")
    def test_judge0_compares_stdout_not_only_accepted_status(self, urlopen):
        urlopen.return_value = BytesIO(json.dumps({"status": {"id": 3, "description": "Accepted"}, "stdout": "wrong\n"}).encode())
        r = self.post(f"/api/problems/{self.problem.id}/submit/", {"code": "print('wrong')", "language_id": 71}, user=self.learner)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "failed")
        self.assertNotIn("expected_output", json.dumps(r.data))

    @patch("core.views.urllib.request.urlopen", side_effect=URLError("down"))
    def test_coding_runner_unavailable_is_503_and_private_expected_output_is_not_returned(self, _):
        with override_settings(JUDGE0_URL="https://judge.test"):
            r = self.post(f"/api/problems/{self.problem.id}/submit/", {"code": "print('ok')", "language_id": 71}, user=self.learner)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("expected_output", json.dumps(getattr(r, "data", {})))

    def test_rating_requires_enrollment_and_ownership(self):
        self.assertEqual(self.post("/api/ratings/", {"course": self.course.id, "rating": 5}, user=self.learner).status_code, 201)
        other = self.user("rating-other@example.test", is_verified=True)
        self.assert_denied(self.post("/api/ratings/", {"course": self.course.id, "rating": 1}, user=other))
        rating = Rating.objects.get(course=self.course, learner=self.learner)
        self.assert_denied(self.patch(f"/api/ratings/{rating.id}/", {"rating": 1}, user=other))

    def test_staff_user_patch_whitelist_cannot_escalate_role(self):
        r = self.patch(f"/api/staff/users/{self.learner.id}/", {"full_name": "Updated", "role": "admin", "is_staff": True, "is_superuser": True}, user=self.admin)
        self.assertIn(r.status_code, (200, 400))
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.role, "learner")
        self.assertFalse(self.learner.is_staff)

    def test_only_staff_can_issue_response_and_status_updates(self):
        ticket = SupportTicket.objects.create(user=self.learner, subject="Help", message="Question")
        self.assert_denied(self.patch(f"/api/staff/issues/{ticket.id}/", {"response": "No", "status": "closed"}, user=self.learner))
        r = self.patch(f"/api/staff/issues/{ticket.id}/", {"response": "Resolved", "status": "closed"}, user=self.admin)
        self.assertEqual(r.status_code, 200)
        ticket.refresh_from_db(); self.assertEqual(ticket.response, "Resolved"); self.assertEqual(ticket.status, "closed")


class ContestAndAuthTests(AcceptanceBase):
    def contest(self, starts=None, ends=None):
        starts = starts or timezone.now() - timedelta(hours=1)
        ends = ends or timezone.now() + timedelta(hours=1)
        return Contest.objects.create(owner=self.admin, title="Contest", starts_at=starts, ends_at=ends, prize="Prize", questions=[{"id": "q1", "question": "2+2?", "option_a": "4", "option_b": "5", "correct_answer": "a"}])

    def test_contest_answers_and_upcoming_questions_are_hidden(self):
        c = self.contest(starts=timezone.now() + timedelta(hours=1), ends=timezone.now() + timedelta(hours=2))
        self.auth(self.learner)
        data = self.client.get(f"/api/contests/{c.id}/").data
        self.assertNotIn("correct_answer", json.dumps(data))
        self.assertNotIn("q1", json.dumps(data))

    def test_ended_contest_leaderboard_remains_accessible_and_duplicate_submit_conflicts(self):
        self.auth(self.learner)
        c = self.contest(starts=timezone.now() - timedelta(hours=2), ends=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.client.get(f"/api/contests/{c.id}/leaderboard/").status_code, 200)
        c2 = self.contest()
        body = {"answers": {"q1": "a"}}
        first = self.post(f"/api/contests/{c2.id}/submit/", body, user=self.learner)
        second = self.post(f"/api/contests/{c2.id}/submit/", body, user=self.learner)
        self.assertIn(first.status_code, (200, 201)); self.assertEqual(second.status_code, 409)

    def test_contest_mutation_is_staff_only_and_malformed_answers_are_400(self):
        body = {"title": "C", "starts_at": (timezone.now() + timedelta(hours=1)).isoformat(), "ends_at": (timezone.now() + timedelta(hours=2)).isoformat(), "questions": []}
        self.assert_denied(self.post("/api/contests/", body, user=self.learner))
        c = self.contest()
        self.assertEqual(self.post(f"/api/contests/{c.id}/submit/", {"answers": []}, user=self.learner).status_code, 400)

    @override_settings(FRONTEND_URL="https://frontend.example")
    @patch("core.views.send_mail")
    def test_register_csrf_required_and_verification_link_is_absolute_one_use(self, send_mail):
        csrf_client = APIClient(enforce_csrf_checks=True)
        body = {"email": "new@example.test", "password": "SafePass123!", "full_name": "New", "role": "learner"}
        self.assertEqual(csrf_client.post("/api/auth/register/", body, format="json").status_code, 403)
        token = csrf_client.get("/api/auth/csrf/").cookies["csrftoken"].value
        r = csrf_client.post("/api/auth/register/", body, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 201)
        link = send_mail.call_args.args[1]
        self.assertRegex(link, r"https://frontend\.example/(?:verify/|verify-email\?token=)[0-9a-f-]+")
        t = EmailToken.objects.filter(user__email="new@example.test", kind="verify").latest("token")
        self.assertEqual(self.client.get(f"/api/auth/verify/{t.token}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/auth/verify/{t.token}/").status_code, 400)

    @patch("core.views.send_mail")
    def test_password_reset_absolute_link_expiration_and_reuse(self, send_mail):
        self.client.post("/api/auth/password-reset/", {"email": self.learner.email}, format="json")
        link = send_mail.call_args.args[1]
        self.assertRegex(link, r"https?://[^ ]+/reset(?:/|-password\?token=)[0-9a-f-]+")
        token = EmailToken.objects.create(user=self.learner, kind="reset", expires_at=timezone.now() + timedelta(hours=1))
        self.assertEqual(self.client.post(f"/api/auth/password-reset/confirm/{token.token}/", {"password": "NewSafePass123!"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/auth/password-reset/confirm/{token.token}/", {"password": "OtherSafePass123!"}, format="json").status_code, 400)
        expired = EmailToken.objects.create(user=self.learner, kind="reset", expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(f"/api/auth/password-reset/confirm/{expired.token}/", {"password": "NewSafePass123!"}, format="json").status_code, 400)

    def test_login_requires_csrf_and_account_lockout_survives_ip_changes_and_expires(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        body = {"email": self.learner.email, "password": "wrong"}
        self.assertEqual(csrf_client.post("/api/auth/login/", body, format="json").status_code, 403)
        token = csrf_client.get("/api/auth/csrf/").cookies["csrftoken"].value
        for _ in range(5): csrf_client.post("/api/auth/login/", body, format="json", HTTP_X_CSRFTOKEN=token, REMOTE_ADDR="10.0.0.1")
        self.assertEqual(csrf_client.post("/api/auth/login/", {"email": self.learner.email, "password": "SafePass123!"}, format="json", HTTP_X_CSRFTOKEN=token, REMOTE_ADDR="10.0.0.1").status_code, 429)
        self.assertEqual(csrf_client.post("/api/auth/login/", {"email": self.learner.email, "password": "SafePass123!"}, format="json", HTTP_X_CSRFTOKEN=token, REMOTE_ADDR="10.0.0.2").status_code, 429)
        attempt = LoginAttempt.objects.get(email=self.learner.email, ip="0.0.0.0")
        attempt.locked_until = timezone.now() - timedelta(seconds=1); attempt.save()
        self.assertEqual(csrf_client.post("/api/auth/login/", {"email": self.learner.email, "password": "SafePass123!"}, format="json", HTTP_X_CSRFTOKEN=token, REMOTE_ADDR="10.0.0.1").status_code, 200)

    def test_login_rejects_top_level_non_object_json_without_auth_or_attempts(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        token = csrf_client.get("/api/auth/csrf/").cookies["csrftoken"].value
        attempt_count = LoginAttempt.objects.count()
        payloads = [[], [{"email": self.learner.email, "password": "SafePass123!"}], "not-an-object", 42, True, None]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = csrf_client.generic(
                    "POST",
                    "/api/auth/login/",
                    data=json.dumps(payload),
                    content_type="application/json",
                    HTTP_X_CSRFTOKEN=token,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data, {"detail": "Request body must be a JSON object."})
                self.assertIsNone(csrf_client.session.get("_auth_user_id"))
                self.assertEqual(LoginAttempt.objects.count(), attempt_count)

    @override_settings(FRONTEND_URL="https://frontend.example")
    @patch("core.views.send_mail")
    def test_resend_verification_requires_csrf_and_sends_absolute_single_use_link(self, send_mail):
        csrf_client = APIClient(enforce_csrf_checks=True)
        body = {"email": self.unverified.email}
        self.assertEqual(csrf_client.post("/api/auth/resend-verification/", body, format="json").status_code, 403)
        csrf = csrf_client.get("/api/auth/csrf/").cookies["csrftoken"].value
        response = csrf_client.post("/api/auth/resend-verification/", body, format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(send_mail.call_count, 1)
        token = EmailToken.objects.get(user=self.unverified, kind="verify")
        self.assertRegex(send_mail.call_args.args[1], r"https://frontend\.example/verify/[0-9a-f-]+")
        self.assertEqual(self.client.get(f"/api/auth/verify/{token.token}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/auth/verify/{token.token}/").status_code, 400)

    def test_resend_verification_rejects_non_object_and_invalid_email(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf = csrf_client.get("/api/auth/csrf/").cookies["csrftoken"].value
        for payload in ([], "email@example.test", {"email": "not-an-email"}):
            response = csrf_client.generic("POST", "/api/auth/resend-verification/", data=json.dumps(payload), content_type="application/json", HTTP_X_CSRFTOKEN=csrf)
            self.assertEqual(response.status_code, 400)

    @patch("core.views.send_mail")
    def test_resend_verification_is_generic_and_cooldown_does_not_issue_again(self, send_mail):
        confirmations = []
        for email in ("unknown@example.test", self.learner.email, self.blocked.email):
            response = self.client.post("/api/auth/resend-verification/", {"email": email}, format="json")
            self.assertEqual(response.status_code, 200)
            confirmations.append(response.data)
        send_mail.assert_not_called()
        first = self.client.post("/api/auth/resend-verification/", {"email": self.unverified.email}, format="json")
        second = self.client.post("/api/auth/resend-verification/", {"email": self.unverified.email}, format="json")
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        for confirmation in confirmations + [second.data]:
            self.assertEqual(confirmation, first.data)
        self.assertEqual(send_mail.call_count, 1)
        self.assertEqual(EmailToken.objects.filter(user=self.unverified, kind="verify").count(), 1)

    @patch("core.views.send_mail", side_effect=RuntimeError("smtp unavailable"))
    def test_resend_verification_mail_failure_rolls_back_token_and_stays_generic(self, send_mail):
        old = EmailToken.objects.create(user=self.unverified, kind="verify", expires_at=timezone.now() + timedelta(hours=1))
        response = self.client.post("/api/auth/resend-verification/", {"email": self.unverified.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"detail": "If the account is eligible, a verification link was sent."})
        self.assertEqual(EmailToken.objects.filter(user=self.unverified, kind="verify").count(), 1)
        old.refresh_from_db()
        self.assertIsNone(old.used_at)
        self.assertFalse(LoginAttempt.objects.filter(email=f"resend-verification-{self.unverified.pk}@rate.invalid").exists())
        self.assertEqual(self.client.get(f"/api/auth/verify/{old.token}/").status_code, 200)

    @patch("core.views.send_mail")
    def test_resend_verification_replaces_live_links_and_recovers_after_cooldown(self, send_mail):
        old = EmailToken.objects.create(user=self.unverified, kind="verify", expires_at=timezone.now() + timedelta(hours=1))
        response = self.client.post("/api/auth/resend-verification/", {"email": self.unverified.email.upper()}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/auth/verify/{old.token}/").status_code, 400)
        fresh = EmailToken.objects.filter(user=self.unverified, kind="verify", used_at__isnull=True).get()
        self.assertGreater(fresh.expires_at, timezone.now() + timedelta(hours=47))
        LoginAttempt.objects.filter(email=f"resend-verification-{self.unverified.pk}@rate.invalid").update(updated_at=timezone.now() - timedelta(seconds=61))
        self.assertEqual(self.client.post("/api/auth/resend-verification/", {"email": self.unverified.email}, format="json").status_code, 200)
        self.assertEqual(send_mail.call_count, 2)
        self.assertEqual(self.client.get(f"/api/auth/verify/{fresh.token}/").status_code, 400)
        newest = EmailToken.objects.filter(user=self.unverified, kind="verify", used_at__isnull=True).get()
        self.assertEqual(self.client.get(f"/api/auth/verify/{newest.token}/").status_code, 200)

    @patch("core.views.send_mail")
    def test_resend_verification_expires_old_link_and_allows_recovery(self, send_mail):
        expired = EmailToken.objects.create(user=self.unverified, kind="verify", expires_at=timezone.now() - timedelta(seconds=1))
        response = self.client.post("/api/auth/resend-verification/", {"email": self.unverified.email}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/auth/verify/{expired.token}/").status_code, 400)
        fresh = EmailToken.objects.filter(user=self.unverified, kind="verify").exclude(pk=expired.pk).get()
        self.assertEqual(self.client.get(f"/api/auth/verify/{fresh.token}/").status_code, 200)

    def test_resend_verification_source_ip_cap_is_ten_per_fifteen_minutes(self):
        for index in range(10):
            self.assertEqual(self.client.post("/api/auth/resend-verification/", {"email": f"unknown-{index}@example.test"}, REMOTE_ADDR="10.10.10.10", format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/resend-verification/", {"email": "unknown-final@example.test"}, REMOTE_ADDR="10.10.10.10", format="json").status_code, 429)


class HardeningTests(AcceptanceBase):
    def test_invalid_email_and_privileged_registration_are_rejected(self):
        for email in ('not-an-email', 'a@', 'bad space@example.com'):
            response = self.post('/api/auth/register/', {'email': email, 'password': 'StrongUnique892!pass', 'full_name': 'New', 'role': 'learner'})
            self.assertEqual(response.status_code, 400)
        response = self.post('/api/auth/register/', {'email': 'evil@example.test', 'password': 'StrongUnique892!pass', 'full_name': 'New', 'role': 'admin'})
        self.assertEqual(response.status_code, 400)

    def test_sql_injection_search_remains_a_literal_parameter(self):
        response = self.client.get('/api/courses/', {'search': "' OR 1=1; DROP TABLE core_user; --"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)
        self.assertTrue(User.objects.filter(pk=self.learner.pk).exists())

    def test_public_course_detail_never_contains_private_lesson_data(self):
        self.video.content = 'private-lesson-sentinel'
        self.video.save()
        response = self.client.get(f'/api/courses/{self.course.id}/')
        serialized = json.dumps(response.data)
        self.assertNotIn('private-lesson-sentinel', serialized)
        self.assertNotIn('coding_expected_output', serialized)
        self.assertNotIn(self.instructor.email, serialized)

    def test_javascript_urls_and_profile_privilege_edits_are_rejected(self):
        response = self.patch('/api/profile/', {'profile_pic': 'javascript:alert(1)'}, user=self.learner)
        self.assertEqual(response.status_code, 400)
        response = self.patch('/api/profile/', {'role': 'admin', 'points': 99999}, user=self.learner)
        self.assertEqual(response.status_code, 400)
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.role, 'learner')
        self.assertEqual(self.learner.points, 0)

    def test_unverified_blocked_and_unapproved_sessions_are_denied(self):
        for user in (self.unverified, self.blocked, self.pending_instructor):
            self.auth(user)
            self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)

    def test_owner_can_retrieve_pending_full_curriculum(self):
        unit = Unit.objects.create(course=self.pending, title='Private unit')
        Lesson.objects.create(unit=unit, title='Private lesson', lesson_type='coding', coding_language='python', coding_expected_output='private-answer')
        self.auth(self.instructor)
        response = self.client.get(f'/api/courses/{self.pending.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['units'][0]['lessons'][0]['coding_expected_output'], 'private-answer')

    def test_invalid_numeric_progress_and_query_filter_do_not_crash(self):
        for value in ('abc', -1, 101, None):
            response = self.patch(f'/api/lessons/{self.video.id}/progress/', {'progress': value}, user=self.learner)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get('/api/lessons/?course=malformed').status_code, 400)

    @override_settings(JUDGE0_URL='https://judge.test')
    @patch('core.views.urllib.request.urlopen')
    def test_coding_lesson_success_persists_progress_without_exposing_expected(self, urlopen):
        urlopen.return_value = BytesIO(json.dumps({'status': {'id': 3, 'description': 'Accepted'}, 'stdout': 'ok\n'}).encode())
        response = self.post(f'/api/lessons/{self.coding.id}/run/', {'code': 'print("ok")', 'language_id': 71}, user=self.learner)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['passed'])
        self.assertNotIn('expected_output', response.data)
        self.assertEqual(LessonProgress.objects.get(enrollment=self.enrollment, lesson=self.coding).progress, 100)
        self.assertEqual(self.client.get(f'/api/lessons/{self.coding.id}/').data['progress'], 100)

    @override_settings(JUDGE0_URL='https://judge.test')
    @patch('core.views.urllib.request.urlopen')
    def test_problem_grades_every_case_not_only_the_first(self, urlopen):
        self.problem.test_cases = [{'input': '1', 'output': 'one'}, {'input': '2', 'output': 'two'}]
        self.problem.save()
        urlopen.side_effect = [BytesIO(json.dumps({'status': {'id': 3, 'description': 'Accepted'}, 'stdout': 'one'}).encode()), BytesIO(json.dumps({'status': {'id': 3, 'description': 'Accepted'}, 'stdout': 'WRONG'}).encode())]
        response = self.post(f'/api/problems/{self.problem.id}/submit/', {'code': 'print("one")', 'language_id': 71}, user=self.learner)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'failed')
        self.assertEqual(urlopen.call_count, 2)
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.points, 0)

    @override_settings(JUDGE0_URL='https://judge.test')
    @patch('core.views.urllib.request.urlopen')
    def test_successful_problem_awards_points_once(self, urlopen):
        urlopen.side_effect = lambda *args, **kwargs: BytesIO(json.dumps({'status': {'id': 3, 'description': 'Accepted'}, 'stdout': 'ok\n'}).encode())
        for _ in range(2):
            response = self.post(f'/api/problems/{self.problem.id}/submit/', {'code': 'print("ok")', 'language_id': 71}, user=self.learner)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['status'], 'accepted')
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.points, 10)

    def test_staff_can_actually_approve_instructor_block_user_and_publish_course(self):
        self.assertEqual(self.patch(f'/api/staff/users/{self.pending_instructor.id}/', {'instructor_approved': True}, user=self.admin).status_code, 200)
        self.pending_instructor.refresh_from_db()
        self.assertTrue(self.pending_instructor.instructor_approved)
        self.assertEqual(self.patch(f'/api/staff/users/{self.learner.id}/', {'is_active': False}, user=self.admin).status_code, 200)
        self.learner.refresh_from_db()
        self.assertFalse(self.learner.is_active)
        self.assertEqual(self.patch(f'/api/staff/courses/{self.pending.id}/', {'status': 'approved'}, user=self.admin).status_code, 200)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, 'approved')

    def test_submissions_attempts_and_tickets_are_user_scoped(self):
        other = self.user('other-person@example.test', is_verified=True)
        Submission.objects.create(problem=self.problem, learner=other, code='private-source', language='71')
        SupportTicket.objects.create(user=other, subject='private-ticket', message='private-message')
        self.auth(self.learner)
        self.assertNotIn('private-source', json.dumps(self.client.get('/api/submissions/').data))
        self.assertNotIn('private-ticket', json.dumps(self.client.get('/api/issues/').data))


class PublicationAndPrizeTests(AcceptanceBase):
    def test_instructor_revocation_hides_catalog_enrollment_and_private_content(self):
        for field in ('is_active', 'is_verified', 'instructor_approved'):
            with self.subTest(field=field):
                setattr(self.instructor, field, False)
                self.instructor.save(update_fields=[field])
                self.client.force_authenticate(None)
                self.assertEqual(self.client.get('/api/courses/').data['count'], 0)
                self.assertEqual(self.client.get(f'/api/courses/{self.course.id}/curriculum/').status_code, 404)
                self.auth(self.learner)
                for path in (f'/api/courses/{self.course.id}/enroll/', f'/api/units/{self.unit.id}/', f'/api/lessons/{self.video.id}/', f'/api/quizzes/{self.quiz.id}/'):
                    self.assertEqual(self.client.get(path).status_code, 404, path)
                setattr(self.instructor, field, True)
                self.instructor.save(update_fields=[field])

    def test_ranked_prize_positions_must_be_unique_numeric_and_sorted(self):
        contest = self.contest_for_prizes()
        for prizes in ([{'position':True,'prize_label':'Invalid'}], [{'position':1,'prize_label':'First'},{'position':1,'prize_label':'Duplicate'}], [{'position':0,'prize_label':'Invalid'}]):
            self.assertEqual(self.patch(f'/api/contests/{contest.id}/', {'prizes':prizes}, user=self.admin).status_code, 400)
        response = self.patch(f'/api/contests/{contest.id}/', {'prizes':[{'position':2,'prize_label':'Second'},{'position':1,'prize_label':'First'}]}, user=self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['prizes'][0]['position'], 1)

    def contest_for_prizes(self):
        return Contest.objects.create(owner=self.admin, title='Prizes', starts_at=timezone.now()+timedelta(hours=1), ends_at=timezone.now()+timedelta(hours=2), questions=[{'id':'q1','question':'One?','option_a':'Yes','option_b':'No','correct_answer':'a'}])
