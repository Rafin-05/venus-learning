#!/usr/bin/env python3
"""Read-only checks plus an optional login to an operator-supplied test account."""
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

BASE = os.getenv('BASE_URL', 'http://localhost:8080').rstrip('/')
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
checks = []


def request(path, method='GET', data=None, csrf=None):
    headers = {'Accept': 'application/json, text/html'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    if csrf:
        headers['X-CSRFToken'] = csrf
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE+path, data=body, headers=headers, method=method)
    try:
        response = client.open(req, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    return response.status, response.headers, response.read().decode('utf-8', errors='replace')


def check(label, condition):
    if not condition:
        raise RuntimeError(label)
    checks.append(label)
    print('PASS:', label)


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nonces = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            data = dict(attrs)
            if data.get('type') not in ('application/json', 'application/ld+json'):
                self.nonces.append(data.get('nonce'))


def main():
    status, headers, body = request('/api/health/')
    check('API health reaches MySQL', status == 200 and json.loads(body).get('database') == 'ok')
    status, headers, body = request('/')
    check('Next.js homepage and Venus branding', status == 200 and 'Venus Learning' in body and 'venus-wordmark.png' in body)
    policy = headers.get('Content-Security-Policy', '')
    script_policy = next((part for part in policy.split(';') if part.strip().startswith('script-src ')), '')
    match = re.search(r"'nonce-([^']+)'", script_policy)
    check('Nonce-based production script CSP', bool(match) and "'unsafe-inline'" not in script_policy and "'unsafe-eval'" not in script_policy)
    parser = Scripts(); parser.feed(body)
    check('Rendered framework scripts carry the CSP nonce', bool(parser.nonces) and all(nonce == match.group(1) for nonce in parser.nonces))
    status2, headers2, _ = request('/')
    check('Nonce changes for each document response', status2 == 200 and headers2.get('Content-Security-Policy') != policy)
    check('Anti-framing and MIME-sniffing headers', headers.get('X-Frame-Options') == 'DENY' and headers.get('X-Content-Type-Options') == 'nosniff')
    status, _, body = request('/api/courses/')
    payload = json.loads(body)
    rows = payload.get('results', []) if isinstance(payload, dict) else payload
    check('Public approved catalog', status == 200 and all(course.get('status') == 'approved' for course in rows))
    status, _, _ = request('/api/auth/me/')
    check('Anonymous account access is denied', status in (401, 403))
    status, _, _ = request('/api/auth/login/', 'POST', {'email': 'invalid@example.invalid', 'password': 'wrong'})
    check('Anonymous login requires CSRF', status == 403)
    status, _, body = request('/api/auth/csrf/')
    token = json.loads(body)['csrfToken']
    status, _, _ = request('/api/auth/register/', 'POST', {'email': 'not-an-email', 'password': 'DemoValidationOnly739!', 'full_name': 'Validation probe', 'role': 'learner'}, token)
    check('Malformed email is rejected server-side', status == 400)
    status, _, _ = request('/media/not-public.pdf')
    check('Raw media directory is not publicly served', status == 404)
    status, _, _ = request('/.env')
    check('Dotfiles are blocked', status in (403, 404))
    email, password = os.getenv('SMOKE_EMAIL'), os.getenv('SMOKE_PASSWORD')
    if email and password:
        _, _, body = request('/api/auth/csrf/')
        token = json.loads(body)['csrfToken']
        status, _, body = request('/api/auth/login/', 'POST', {'email': email, 'password': password}, token)
        check('Operator-supplied test account can sign in', status == 200)
        for _ in range(12):
            status, _, body = request('/api/auth/me/')
            if status != 200 or json.loads(body).get('email') != email.strip().lower():
                raise RuntimeError('Session did not survive repeated load-balanced requests')
        check('Session survives repeated load-balanced API requests', True)
    elif email or password:
        raise RuntimeError('Set both SMOKE_EMAIL and SMOKE_PASSWORD, or neither.')
    print(f'Completed {len(checks)} smoke checks. No account credentials or session tokens were displayed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
