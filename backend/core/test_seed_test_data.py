from django.contrib.auth import authenticate
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings

from .models import (User, Course, Enrollment, LessonProgress,
                     Certificate, FocusSession, Rating)


PASSWORD = 'TestPass-2026!'


@override_settings(DEBUG=True, ENABLE_DEMO_ACCOUNTS=True)
class SeedTestDataTests(TestCase):
    def seed(self, *args):
        call_command('seed_test_data', *args, verbosity=0)

    def test_seed_creates_expected_data_and_is_idempotent(self):
        self.seed()
        first_run = self.counts()
        self.seed()
        second_run = self.counts()
        self.assertEqual(first_run, second_run)

        self.assertEqual(User.objects.filter(is_demo_account=True).count(), 63)
        self.assertEqual(User.objects.filter(is_demo_account=True, role='learner').count(), 50)
        self.assertEqual(User.objects.filter(is_demo_account=True, role='instructor').count(), 10)
        self.assertEqual(User.objects.filter(is_demo_account=True, role='admin').count(), 3)

        instructors = User.objects.filter(is_demo_account=True, role='instructor')
        courses = Course.objects.filter(instructor__in=instructors)
        self.assertGreaterEqual(courses.count(), 10)
        self.assertLessEqual(courses.count(), 30)
        self.assertTrue(all(course.status == 'approved' for course in courses))

        learners = User.objects.filter(is_demo_account=True, role='learner')
        enrollments = Enrollment.objects.filter(learner__in=learners)
        self.assertGreater(enrollments.count(), 0)
        for learner in learners:
            count = enrollments.filter(learner=learner).count()
            self.assertGreaterEqual(count, 1)
            self.assertLessEqual(count, 4)

        self.assertEqual(Certificate.objects.filter(learner__in=learners).count(), 15)
        focus = FocusSession.objects.filter(learner__in=learners)
        self.assertEqual(focus.filter(target_minutes=30, status='completed').count(), 17)
        self.assertEqual(focus.filter(target_minutes=60, status='completed').count(), 10)
        self.assertEqual(focus.filter(status='interrupted').count(), 4)
        for session in focus.filter(status='completed'):
            self.assertEqual(session.focused_seconds, session.target_minutes * 60)
            self.assertIsNotNone(session.ended_at)

        for course in courses:
            ratings = Rating.objects.filter(course=course)
            self.assertGreaterEqual(ratings.count(), 2)
            self.assertLessEqual(ratings.count(), 4)

        for learner in learners:
            self.assertTrue(learner.bio)
            self.assertTrue(learner.profile_pic.startswith('https://api.dicebear.com/'))
            self.assertTrue(learner.check_password(PASSWORD))
        for instructor in instructors:
            self.assertTrue(instructor.title)
            self.assertTrue(instructor.expertise)
            self.assertTrue(instructor.bio)
            self.assertTrue(instructor.profile_pic.startswith('https://api.dicebear.com/'))
        admins = User.objects.filter(is_demo_account=True, role='admin')
        for admin in admins:
            self.assertTrue(admin.is_staff)
            self.assertTrue(admin.is_superuser)
            self.assertTrue(admin.bio)
            self.assertTrue(admin.profile_pic.startswith('https://api.dicebear.com/'))

        # Spot-check logins for one account of each role.
        for role in ('learner', 'instructor', 'admin'):
            user = User.objects.filter(is_demo_account=True, role=role).first()
            self.assertIsNotNone(authenticate(email=user.email, password=PASSWORD))

    def test_seed_requires_both_flags(self):
        with override_settings(DEBUG=True, ENABLE_DEMO_ACCOUNTS=False):
            with self.assertRaises(CommandError):
                self.seed()
        with override_settings(DEBUG=False, ENABLE_DEMO_ACCOUNTS=True):
            with self.assertRaises(CommandError):
                self.seed()
        self.assertEqual(User.objects.count(), 0)

    def test_collision_with_real_account_fails(self):
        User.objects.create_user('rahim.uddin@example.com', 'RealPassword-2026!', role='learner')
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(User.objects.count(), 1)

    def counts(self):
        learners = User.objects.filter(is_demo_account=True, role='learner')
        instructors = User.objects.filter(is_demo_account=True, role='instructor')
        courses = Course.objects.filter(instructor__in=instructors)
        return {
            'users': User.objects.filter(is_demo_account=True).count(),
            'courses': courses.count(),
            'enrollments': Enrollment.objects.filter(learner__in=learners).count(),
            'certificates': Certificate.objects.filter(learner__in=learners).count(),
            'focus': FocusSession.objects.filter(learner__in=learners).count(),
            'ratings': Rating.objects.filter(course__in=courses).count(),
        }
