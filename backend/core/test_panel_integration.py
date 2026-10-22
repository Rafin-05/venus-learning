from django.test import TestCase
from rest_framework.test import APIClient

from .models import Course, Enrollment, Lesson, Unit, User


class PanelIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.learner = User.objects.create_user(
            "learner@panel.test", "SafePass123!", full_name="Learner", is_verified=True
        )
        self.instructor = User.objects.create_user(
            "instructor@panel.test",
            "SafePass123!",
            full_name="Instructor",
            role="instructor",
            is_verified=True,
            instructor_approved=True,
        )
        self.other_instructor = User.objects.create_user(
            "other@panel.test",
            "SafePass123!",
            full_name="Other Instructor",
            role="instructor",
            is_verified=True,
            instructor_approved=True,
        )
        self.admin = User.objects.create_superuser(
            "admin@panel.test", "SafePass123!", full_name="Admin"
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def test_course_approval_enrollment_and_progress_use_shared_ids(self):
        self.auth(self.instructor)
        response = self.client.post(
            "/api/courses/",
            {"title": "Integrated Python", "description": "Learn safely", "category": "code"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        course_id = response.data["id"]
        self.assertEqual(response.data["status"], "pending")

        self.auth(self.admin)
        response = self.client.patch(
            f"/api/staff/courses/{course_id}/", {"status": "approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")

        self.auth(self.instructor)
        response = self.client.post(
            "/api/units/", {"course": course_id, "title": "Basics", "position": 1}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        unit_id = response.data["id"]
        response = self.client.post(
            "/api/lessons/",
            {"unit": unit_id, "title": "First lesson", "content": "Read this", "lesson_type": "document"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        lesson_id = response.data["id"]
        # Content edits correctly return an approved course to moderation.
        self.assertEqual(Course.objects.get(pk=course_id).status, "pending")

        self.auth(self.admin)
        self.assertEqual(
            self.client.patch(f"/api/staff/courses/{course_id}/", {"status": "approved"}, format="json").status_code,
            200,
        )
        self.auth(self.learner)
        response = self.client.post(f"/api/courses/{course_id}/enroll/", format="json")
        self.assertEqual(response.status_code, 201)
        enrollment_id = response.data["id"]
        self.assertEqual(Enrollment.objects.get(pk=enrollment_id).course_id, course_id)

        response = self.client.patch(
            f"/api/lessons/{lesson_id}/progress/", {"progress": 100}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["progress"], 100)
        response = self.client.get(f"/api/enrollments/{enrollment_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["progress_percent"], 100)

    def test_roles_cannot_read_or_change_other_users_course_resources(self):
        foreign_course = Course.objects.create(
            title="Private pending", description="draft", instructor=self.other_instructor
        )
        unit = Unit.objects.create(course=foreign_course, title="Draft unit")
        lesson = Lesson.objects.create(unit=unit, title="Draft lesson")

        self.auth(self.instructor)
        self.assertEqual(self.client.get(f"/api/courses/{foreign_course.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/units/{unit.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/lessons/{lesson.id}/").status_code, 404)
        self.assertEqual(
            self.client.patch(f"/api/lessons/{lesson.id}/", {"title": "tampered"}, format="json").status_code,
            404,
        )

        self.auth(self.learner)
        self.assertEqual(self.client.get("/api/staff/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/staff/courses/").status_code, 403)
        self.assertEqual(self.client.get("/api/staff/issues/").status_code, 403)
        self.assertEqual(self.client.get("/api/staff/dashboard/").status_code, 403)

        self.auth(self.admin)
        response = self.client.get("/api/staff/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("pending_courses", response.data)

    def test_instructor_cannot_approve_or_edit_another_instructors_course(self):
        course = Course.objects.create(
            title="Review me", description="draft", instructor=self.other_instructor
        )
        self.auth(self.instructor)
        self.assertEqual(
            self.client.patch(f"/api/staff/courses/{course.id}/", {"status": "approved"}, format="json").status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(f"/api/courses/{course.id}/", {"title": "changed"}, format="json").status_code,
            404,
        )
