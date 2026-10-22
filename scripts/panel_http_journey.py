#!/usr/bin/env python3
"""Exercise shared panel workflows against an isolated evaluation deployment.
Requires PANEL_{ADMIN,INSTRUCTOR,LEARNER}_{EMAIL,PASSWORD} environment variables.
Creates a uniquely titled test course, quiz, enrollment and support report. Do not run on production.
"""
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
import uuid

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8181').rstrip('/')


class Session:
    def __init__(self):
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, method='GET', data=None, expected=200):
        headers = {'Accept': 'application/json'}
        if method not in ('GET', 'HEAD', 'OPTIONS'):
            token = self.request('/auth/csrf/')['csrfToken']
            headers.update({'X-CSRFToken': token, 'Content-Type': 'application/json'})
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(BASE+'/api'+path, data=body, method=method, headers=headers)
        time.sleep(0.12)
        try:
            response = self.client.open(req, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read()
        payload = json.loads(raw) if raw else None
        statuses = (expected,) if isinstance(expected, int) else expected
        assert response.status in statuses, f'{method} {path}: expected {statuses}, received {response.status}'
        return payload


def rows(data):
    return data['results'] if isinstance(data, dict) else data


def check(label, condition):
    assert condition, label
    print('PASS:', label, flush=True)


def main():
    sessions = {}
    for role in ('ADMIN', 'INSTRUCTOR', 'LEARNER'):
        session = Session()
        email, password = os.environ[f'PANEL_{role}_EMAIL'], os.environ[f'PANEL_{role}_PASSWORD']
        user = session.request('/auth/login/', 'POST', {'email':email, 'password':password})
        # Login response is intentionally not assumed to equal the profile shape.
        user = session.request('/auth/me/')
        check(f'{role.lower()} session login and profile', user['role'] == role.lower())
        sessions[role] = (session, user)
    admin, _ = sessions['ADMIN']; instructor, instructor_user = sessions['INSTRUCTOR']; learner, learner_user = sessions['LEARNER']
    admin.request(f'/staff/users/{instructor_user["id"]}/', 'PATCH', {'instructor_approved':True})
    title = 'Panel integration '+uuid.uuid4().hex[:10]
    course = instructor.request('/courses/', 'POST', {'title':title,'description':'Shared API integration evaluation','category':'Development','level':'beginner'}, expected=201)
    cid = course['id']
    unit = instructor.request('/units/', 'POST', {'course':cid,'title':'Integration unit','position':1}, expected=201)
    lesson = instructor.request('/lessons/', 'POST', {'unit':unit['id'],'title':'Integration video','lesson_type':'video','video_url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ','position':1}, expected=201)
    quiz = instructor.request('/quizzes/', 'POST', {'course':cid,'title':'Integration quiz','pass_percentage':50,'questions':[{'question':'Which API is shared?','option_a':'Django REST','option_b':'Separate local state','option_c':'No API','option_d':'None','correct_answer':'a'}]}, expected=201)
    pending = rows(admin.request('/staff/courses/'))
    check('Instructor-authored course reaches administrator approval queue', any(x['id']==cid and x['status']=='pending' for x in pending))
    learner.request(f'/courses/{cid}/', expected=(403,404))
    admin.request(f'/staff/courses/{cid}/', 'PATCH', {'status':'approved'})
    check('Administrator approval publishes the same course to learner catalog', any(x['id']==cid for x in rows(learner.request('/courses/'))))
    learner.request(f'/courses/{cid}/enroll/', 'POST', {}, expected=(200,201))
    check('Learner enrollment appears in instructor student roster', any(x.get('learner',{}).get('id')==learner_user['id'] or x.get('learner_id')==learner_user['id'] or x.get('email')==learner_user['email'] or x.get('learner_email')==learner_user['email'] for x in rows(instructor.request(f'/courses/{cid}/students/'))))
    learner.request(f'/lessons/{lesson["id"]}/progress/', 'PATCH', {'progress':100})
    visible_quiz = learner.request(f'/quizzes/{quiz["id"]}/')
    check('Learner quiz response does not expose answer keys', 'correct_answer' not in json.dumps(visible_quiz))
    question_id = visible_quiz['questions'][0]['id']
    result = learner.request(f'/quizzes/{quiz["id"]}/submit/', 'POST', {'answers':{str(question_id):'a'}}, expected=(200,201))
    check('Shared API grades learner quiz', result['passed'] is True)
    certificate = learner.request(f'/courses/{cid}/certificate/', 'POST', {}, expected=(200,201))
    check('Learner certificate is issued from shared progress and quiz records', bool(certificate.get('id')))
    learner.request('/staff/dashboard/', expected=(401,403))
    learner.request(f'/staff/courses/{cid}/', 'PATCH', {'status':'approved'}, expected=(401,403,404))
    check('Learner cannot access administrator panel API or moderation actions', True)
    issue = learner.request('/issues/', 'POST', {'subject':title,'message':'Integration support message'}, expected=201)
    admin.request(f'/staff/issues/{issue["id"]}/', 'PATCH', {'status':'resolved','response':'Integrated response'})
    reports = rows(learner.request('/issues/'))
    check('Administrator support response reaches the learner panel', any(x['id']==issue['id'] and x.get('response')=='Integrated response' for x in reports))
    for label, (session, user) in sessions.items():
        for _ in range(4):
            check(f'{label.lower()} session remains valid across API replicas', session.request('/auth/me/')['id']==user['id'])
    print('Completed live cross-panel HTTP journey. Evaluation records remain only in the test database.', flush=True)


if __name__ == '__main__':
    main()
