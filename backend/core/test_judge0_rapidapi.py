"""Judge0 via RapidAPI: headers, rate-limit (429) and bad-key (401/403) handling.

The backend already spoke the Judge0 API; what was missing was the RapidAPI
wiring — RapidAPI takes the key in X-RapidAPI-Key plus X-RapidAPI-Host, while
a self-hosted Judge0 takes it in X-Auth-Token. These tests pin that down
with a mocked urlopen, so no real key or network is needed.
"""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .models import Course, Enrollment, Lesson, Problem, Unit, User
from .views import RunnerRateLimited, RunnerUnauthorized, RunnerUnavailable, execute_program

RAPIDAPI_URL = 'https://judge0-ce.p.rapidapi.com'
RAPIDAPI_HOST = 'judge0-ce.p.rapidapi.com'


def success_payload(stdout='ok'):
    return {
        'status': {'id': 3, 'description': 'Accepted'},
        'stdout': stdout,
        'stderr': '',
        'compile_output': '',
    }


class FakeUrlopen:
    """Capture the outgoing Judge0 request and answer with a canned payload."""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.request = None

    def __call__(self, request, timeout=10):
        self.request = request
        if self.error is not None:
            raise self.error
        response = MagicMock()
        response.read.return_value = json.dumps(self.payload).encode()
        return response


@override_settings(
    JUDGE0_URL=RAPIDAPI_URL,
    JUDGE0_API_KEY='test-key-123',
    JUDGE0_API_HOST=RAPIDAPI_HOST,
    CODING_RUNNER_URL='',
)
class RapidApiHeadersTests(SimpleTestCase):
    def test_rapidapi_key_and_host_headers_sent(self):
        fake = FakeUrlopen(payload=success_payload())
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            result = execute_program('print("ok")', 71, '', 'ok')
        self.assertTrue(result['passed'])
        request = fake.request
        self.assertTrue(request.full_url.endswith('/submissions?base64_encoded=false&wait=true'))
        self.assertEqual(request.get_header('X-rapidapi-key'), 'test-key-123')
        self.assertEqual(request.get_header('X-rapidapi-host'), RAPIDAPI_HOST)
        self.assertIsNone(request.get_header('X-auth-token'))

    def test_429_raises_rate_limited(self):
        error = urllib.error.HTTPError(
            RAPIDAPI_URL + '/submissions', 429, 'Too Many Requests', {}, io.BytesIO(b'')
        )
        fake = FakeUrlopen(error=error)
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            with self.assertRaises(RunnerRateLimited):
                execute_program('print("ok")', 71, '', 'ok')

    def test_401_raises_unauthorized(self):
        error = urllib.error.HTTPError(
            RAPIDAPI_URL + '/submissions', 401, 'Unauthorized', {}, io.BytesIO(b'')
        )
        fake = FakeUrlopen(error=error)
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            with self.assertRaises(RunnerUnauthorized):
                execute_program('print("ok")', 71, '', 'ok')

    def test_500_raises_unavailable(self):
        error = urllib.error.HTTPError(
            RAPIDAPI_URL + '/submissions', 500, 'Server Error', {}, io.BytesIO(b'')
        )
        fake = FakeUrlopen(error=error)
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            with self.assertRaises(RunnerUnavailable):
                execute_program('print("ok")', 71, '', 'ok')


@override_settings(
    JUDGE0_URL='http://localhost:2358',
    JUDGE0_API_KEY='selfhost-key',
    JUDGE0_API_HOST='',
    CODING_RUNNER_URL='',
)
class SelfHostedHeadersTests(SimpleTestCase):
    def test_self_hosted_uses_x_auth_token(self):
        fake = FakeUrlopen(payload=success_payload())
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            result = execute_program('print("ok")', 71, '', 'ok')
        self.assertTrue(result['passed'])
        self.assertEqual(fake.request.get_header('X-auth-token'), 'selfhost-key')
        self.assertIsNone(fake.request.get_header('X-rapidapi-key'))
        self.assertIsNone(fake.request.get_header('X-rapidapi-host'))


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    JUDGE0_URL=RAPIDAPI_URL,
    JUDGE0_API_KEY='test-key-123',
    JUDGE0_API_HOST=RAPIDAPI_HOST,
    CODING_RUNNER_URL='',
)
class RateLimitResponseTests(TestCase):
    def setUp(self):
        self.learner = User.objects.create_user(
            'judge0-learner@example.test', 'SafePass123!', is_verified=True,
        )
        self.owner = User.objects.create_user(
            'judge0-owner@example.test', 'SafePass123!', role='instructor',
            is_verified=True, instructor_approved=True,
        )
        self.course = Course.objects.create(
            title='Coding', instructor=self.owner, status='approved',
        )
        unit = Unit.objects.create(course=self.course, title='Unit')
        self.coding = Lesson.objects.create(
            unit=unit, title='Code', lesson_type='coding',
            coding_language='python', coding_expected_output='ok',
        )
        Enrollment.objects.create(learner=self.learner, course=self.course)
        self.problem = Problem.objects.create(
            owner=self.owner, title='Echo', statement='Echo',
            test_cases=[{'input': '', 'output': 'ok'}],
        )
        self.client = APIClient()
        self.client.force_login(self.learner)

    @patch('core.views.execute_program', side_effect=RunnerRateLimited())
    def test_problem_submit_returns_429_on_daily_limit(self, _execute):
        response = self.client.post(
            f'/api/problems/{self.problem.pk}/submit/',
            {'code': 'print("ok")', 'language': 'python'}, format='json',
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['detail'], 'Daily Judge0 limit reached. Try again tomorrow.')

    @patch('core.views.execute_program', side_effect=RunnerUnauthorized())
    def test_problem_submit_reports_bad_key(self, _execute):
        response = self.client.post(
            f'/api/problems/{self.problem.pk}/submit/',
            {'code': 'print("ok")', 'language': 'python'}, format='json',
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn('API key', response.json()['detail'])

    @patch('core.views.execute_program', side_effect=RunnerRateLimited())
    def test_lesson_run_returns_429_on_daily_limit(self, _execute):
        response = self.client.post(
            f'/api/lessons/{self.coding.pk}/run/',
            {'code': 'print("ok")'}, format='json',
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['detail'], 'Daily Judge0 limit reached. Try again tomorrow.')
