import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    Certificate, Contest, ContestAttempt, Course, DailyActivity, Enrollment,
    Lesson, LessonProgress, LoginAttempt, Problem, ProblemCompletion, Submission,
    Unit, User,
)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ObjectBodyInputTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'body-input@example.test', 'SafePass123!', full_name='Original',
            is_verified=True,
        )
        self.owner = User.objects.create_user(
            'body-owner@example.test', 'SafePass123!', role='instructor',
            is_verified=True, instructor_approved=True,
        )
        self.course = Course.objects.create(
            title='Published', instructor=self.owner, status='approved',
        )
        unit = Unit.objects.create(course=self.course, title='Unit')
        self.lesson = Lesson.objects.create(unit=unit, title='Read', lesson_type='document')
        self.coding = Lesson.objects.create(
            unit=unit, title='Code', lesson_type='coding',
            coding_language='python', coding_expected_output='ok',
        )
        self.enrollment = Enrollment.objects.create(learner=self.user, course=self.course)
        self.problem = Problem.objects.create(
            owner=self.owner, title='Echo', statement='Echo',
            test_cases=[{'input': '', 'output': 'ok'}],
        )
        self.contest = Contest.objects.create(
            owner=self.owner, title='Active',
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1),
            questions=[{'id': 'q1', 'question': 'One?', 'option_a': 'Yes',
                        'option_b': 'No', 'correct_answer': 'a'}],
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.csrf = self.client.get('/api/auth/csrf/').cookies['csrftoken'].value
        self.routes = [
            ('PATCH', '/api/auth/me/'),
            ('PATCH', f'/api/lessons/{self.lesson.pk}/progress/'),
            ('POST', f'/api/contests/{self.contest.pk}/submit/'),
            ('POST', f'/api/lessons/{self.coding.pk}/run/'),
            ('POST', f'/api/problems/{self.problem.pk}/submit/'),
        ]

    def request_json(self, method, url, payload, csrf=True):
        headers = {'HTTP_X_CSRFTOKEN': self.csrf} if csrf else {}
        # Preserve false, null and empty arrays: APIClient convenience helpers
        # otherwise replace some falsy payloads with an empty object.
        return self.client.generic(
            method, url, data=json.dumps(payload),
            content_type='application/json', **headers,
        )

    def snapshot(self):
        models = (
            User, Enrollment, LessonProgress, ContestAttempt, Submission,
            ProblemCompletion, DailyActivity, Certificate, LoginAttempt,
        )
        return {model.__name__: list(model.objects.order_by('pk').values()) for model in models}

    @patch('core.views.execute_program')
    @patch('core.views.throttle_action')
    def assert_rejected(self, route, throttle, execute):
        before = self.snapshot()
        session_user = self.client.session.get('_auth_user_id')
        for payload in ([], [{'full_name': 'Changed'}], 'not-an-object', 42, 1.5, True, False, None):
            with self.subTest(route=route, payload=payload):
                response = self.request_json(*route, payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {'detail': 'Request body must be a JSON object.'})
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.client.session.get('_auth_user_id'), session_user)
                throttle.assert_not_called()
                execute.assert_not_called()

    def test_profile_rejects_non_objects(self):
        self.assert_rejected(self.routes[0])

    def test_progress_rejects_non_objects(self):
        self.assert_rejected(self.routes[1])

    def test_contest_submit_rejects_non_objects(self):
        self.assert_rejected(self.routes[2])

    def test_coding_lesson_run_rejects_non_objects(self):
        self.assert_rejected(self.routes[3])

    @override_settings(JUDGE0_URL='https://runner.example.test', CODING_RUNNER_URL='')
    def test_problem_submit_rejects_non_objects_with_runner_configured(self):
        self.assert_rejected(self.routes[4])

    @override_settings(JUDGE0_URL='', CODING_RUNNER_URL='')
    def test_problem_submit_validates_body_even_without_runner(self):
        self.assert_rejected(self.routes[4])
        response = self.request_json(*self.routes[4], {'code': 'print("ok")', 'language': 'python'})
        self.assertEqual(response.status_code, 503)

    def test_authentication_and_csrf_are_still_required(self):
        for route in self.routes:
            with self.subTest(route=route):
                self.assertEqual(self.request_json(*route, [], csrf=False).status_code, 403)
        self.client.logout()
        for route in self.routes:
            with self.subTest(route=route):
                self.assertEqual(self.request_json(*route, []).status_code, 403)

    @override_settings(JUDGE0_URL='https://runner.example.test', CODING_RUNNER_URL='')
    @patch('core.views.execute_program', return_value={'passed': True, 'status': 'Accepted', 'output': 'ok', 'stderr': ''})
    def test_valid_object_requests_keep_existing_workflows(self, execute):
        response = self.request_json(*self.routes[0], {'full_name': 'Updated'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, 'Updated')
        response = self.request_json(*self.routes[1], {'progress': 75})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LessonProgress.objects.get(lesson=self.lesson).progress, 75)
        response = self.request_json(*self.routes[2], {'answers': {'q1': 'a'}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContestAttempt.objects.get().score, 1)
        program = {'code': 'print("ok")', 'language': 'python'}
        self.assertEqual(self.request_json(*self.routes[3], program).status_code, 200)
        self.assertEqual(LessonProgress.objects.get(lesson=self.coding).progress, 100)
        self.assertEqual(self.request_json(*self.routes[4], program).status_code, 200)
        self.assertEqual(Submission.objects.get().status, 'accepted')
        self.assertEqual(ProblemCompletion.objects.count(), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.points, 11)
        self.assertEqual(execute.call_count, 2)
