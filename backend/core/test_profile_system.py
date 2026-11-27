import uuid

from django.utils import timezone
from rest_framework.test import APIClient
from django.test import TestCase

from .mentor_models import MentorProfile, MentorSession
from .models import Certificate, Course, Enrollment, Rating, Unit, Lesson, User


class ProfileSystemTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.learner = User.objects.create_user(
            "learner@profile.test", "SafePass123!", full_name="Learner One", is_verified=True
        )
        self.instructor = User.objects.create_user(
            "teacher@profile.test", "SafePass123!", full_name="Teacher One",
            role="instructor", is_verified=True, instructor_approved=True,
        )
        self.unapproved = User.objects.create_user(
            "pending@profile.test", "SafePass123!", full_name="Pending Teacher",
            role="instructor", is_verified=True, instructor_approved=False,
        )
        self.course = Course.objects.create(
            title="Python Basics", description="Learn Python", instructor=self.instructor, status="approved"
        )
        self.unit = Unit.objects.create(course=self.course, title="Start", position=1)
        self.lesson = Lesson.objects.create(unit=self.unit, title="Hello", position=1)
        self.enrollment = Enrollment.objects.create(learner=self.learner, course=self.course)
        self.certificate_no = uuid.uuid4()
        Certificate.objects.create(learner=self.learner, course=self.course, certificate_no=self.certificate_no)
        Rating.objects.create(course=self.course, learner=self.learner, rating=5, review="Great")
        self.mentor_profile = MentorProfile.objects.create(
            user=self.instructor, qualifications="MSc Computer Science", topics="Python, ML", hourly_rate="1500.00"
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def test_title_can_be_edited_but_role_and_points_cannot(self):
        self.auth(self.instructor)
        response = self.client.patch("/api/profile/", {"title": "Senior Python Instructor"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Senior Python Instructor")
        response = self.client.patch("/api/profile/", {"role": "admin", "points": 999}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_learner_summary_has_enrollments_certificates_and_sessions(self):
        self.auth(self.learner)
        response = self.client.get("/api/profile/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["enrollments"]), 1)
        self.assertEqual(response.data["enrollments"][0]["course"]["title"], "Python Basics")
        self.assertEqual(len(response.data["certificates"]), 1)
        self.assertEqual(response.data["certificates"][0]["certificate_no"], str(self.certificate_no))
        self.assertEqual(response.data["upcoming_sessions"], [])

    def test_instructor_summary_has_courses_students_rating_and_mentor_profile(self):
        self.auth(self.instructor)
        response = self.client.get("/api/profile/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["courses"]), 1)
        self.assertEqual(response.data["students"], 1)
        self.assertEqual(float(response.data["average_rating"]), 5.0)
        self.assertEqual(response.data["reviews"], 1)
        self.assertEqual(response.data["mentor_profile"]["hourly_rate"], "1500.00")
        self.assertEqual(response.data["sessions_completed"], 0)

    def test_learner_upcoming_mentor_session_appears_in_summary(self):
        MentorSession.objects.create(
            student=self.learner, mentor=self.instructor, mentor_profile=self.mentor_profile,
            topic="Loops", duration_hours=1, hourly_rate="1500.00", total_fee="1500.00",
            scheduled_at=timezone.now() + timezone.timedelta(days=1), status="confirmed",
        )
        self.auth(self.learner)
        response = self.client.get("/api/profile/summary/")
        self.assertEqual(len(response.data["upcoming_sessions"]), 1)
        self.assertEqual(response.data["upcoming_sessions"][0]["topic"], "Loops")

    def test_public_instructor_profile_and_its_guards(self):
        self.auth(self.learner)
        response = self.client.get(f"/api/instructors/{self.instructor.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["full_name"], "Teacher One")
        self.assertEqual(response.data["students"], 1)
        self.assertEqual(float(response.data["average_rating"]), 5.0)
        self.assertEqual(response.data["mentor_profile"]["topics"], "Python, ML")
        self.assertEqual(len(response.data["courses"]), 1)
        # A learner has no public instructor profile.
        self.assertEqual(self.client.get(f"/api/instructors/{self.learner.id}/").status_code, 404)
        # An instructor needs no admin approval for a public profile.
        self.assertEqual(self.client.get(f"/api/instructors/{self.unapproved.id}/").status_code, 200)
