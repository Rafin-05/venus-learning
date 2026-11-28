"""Judge0 self-hosted: plain request to the internal service, no key/host.

With JUDGE0_URL pointing at the Compose service (http://judge0-server:2358)
and no JUDGE0_API_KEY / JUDGE0_API_HOST, execute_program must send a plain
request — no X-RapidAPI-Key, no X-RapidAPI-Host, no X-Auth-Token — because
the self-hosted Judge0 in compose.yaml runs with auth disabled (AUTHN_TOKEN
empty) and is only reachable inside the Compose network. Mocked urlopen, so
no real Judge0 or network is needed. The RapidAPI path is pinned separately
in test_judge0_rapidapi.py; this file pins the self-hosted path.
"""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from .views import RunnerUnavailable, execute_program

SELFHOSTED_URL = 'http://judge0-server:2358'


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
    JUDGE0_URL=SELFHOSTED_URL,
    JUDGE0_API_KEY='',
    JUDGE0_API_HOST='',
    CODING_RUNNER_URL='',
)
class SelfHostedNoAuthTests(SimpleTestCase):
    def test_plain_request_to_internal_service_no_auth_headers(self):
        fake = FakeUrlopen(payload=success_payload())
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            result = execute_program('print("ok")', 71, '', 'ok')
        self.assertTrue(result['passed'])
        request = fake.request
        self.assertTrue(request.full_url.startswith(SELFHOSTED_URL))
        self.assertTrue(request.full_url.endswith('/submissions?base64_encoded=false&wait=true'))
        self.assertIsNone(request.get_header('X-rapidapi-key'))
        self.assertIsNone(request.get_header('X-rapidapi-host'))
        self.assertIsNone(request.get_header('X-auth-token'))

    def test_self_hosted_500_raises_unavailable(self):
        error = urllib.error.HTTPError(
            SELFHOSTED_URL + '/submissions', 500, 'Server Error', {}, io.BytesIO(b'')
        )
        fake = FakeUrlopen(error=error)
        with patch('core.views.urllib.request.urlopen', side_effect=fake):
            with self.assertRaises(RunnerUnavailable):
                execute_program('print("ok")', 71, '', 'ok')


@override_settings(
    JUDGE0_URL='',
    JUDGE0_API_KEY='',
    JUDGE0_API_HOST='',
    CODING_RUNNER_URL='',
)
class SelfHostedDisabledTests(SimpleTestCase):
    def test_empty_url_raises_unavailable_without_calling_runner(self):
        with patch('core.views.urllib.request.urlopen') as urlopen:
            with self.assertRaises(RunnerUnavailable):
                execute_program('print("ok")', 71, '', 'ok')
        urlopen.assert_not_called()
