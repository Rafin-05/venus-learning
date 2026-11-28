"""Tests for exam monitoring (AI proctoring v1).

Covers: consent is mandatory, enrolled learners can start a session,
event ingest updates the deterministic risk score (including a
LOOKING_AWAY event adding 5), invalid events are
rejected, learners cannot see each other's sessions, instructors can
list and review their own courses' sessions, and a high-risk session
is flagged (not failed) when it ends.

NOTE: verified locally 2026-11-28 against the real codebase with SQLite
(Django 5.2.18 + DRF 3.18.3): all 9 tests pass, and `makemigrations
--check --dry-run` reports no changes (migration 0013 only updates the
LOOKING_AWAY choice label to match the new behaviour; no schema change
beyond that). Still run once in Docker before merge, since production runs
MySQL: docker compose exec api python manage.py test core.test_proctoring
"""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Course, Enrollment, Question, Quiz, User
from .proctor_models import ProctoredExamSession


class ProctoringTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            'proc-inst@test.local', 'SafePass123!', full_name='Tanvir Ahmed',
            role='instructor', is_verified=True, instructor_approved=True)
        self.learner = User.objects.create_user(
            'proc-learner@test.local', 'SafePass123!', full_name='Nusrat Jahan',
            is_verified=True)
        self.other_learner = User.objects.create_user(
            'proc-other@test.local', 'SafePass123!', full_name='Rafi Chowdhury',
            is_verified=True)
        self.admin = User.objects.create_user(
            'proc-admin@test.local', 'SafePass123!', full_name='Admin',
            role='admin', is_staff=True, is_verified=True)
        self.course = Course.objects.create(
            title='Intro to Python', description='Basics', instructor=self.instructor,
            status='approved')
        Enrollment.objects.create(learner=self.learner, course=self.course)
        self.quiz = Quiz.objects.create(
            course=self.course, title='Midterm', owner=self.instructor)
        Question.objects.create(
            quiz=self.quiz, question='What is 2 + 2?', option_a='3', option_b='4',
            option_c='5', option_d='6', correct_answer='b')

    def login(self, email):
        client = APIClient()
        self.assertEqual(
            client.post('/api/auth/login/', {'email': email, 'password': 'SafePass123!'},
                        format='json').status_code, 200)
        return client

    def start(self, email='proc-learner@test.local', consent=True):
        return self.login(email).post('/api/proctoring/', {
            'quiz': self.quiz.id, 'consent_given': consent}, format='json')

    def test_start_requires_consent(self):
        r = self.start(consent=False)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ProctoredExamSession.objects.exists())

    def test_enrolled_learner_can_start_session(self):
        r = self.start()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['status'], 'active')
        self.assertEqual(r.data['risk_score'], 0)
        self.assertEqual(r.data['risk_band'], 'low')
        self.assertTrue(r.data['consent_given'])

    def test_non_enrolled_learner_cannot_start(self):
        r = self.start(email='proc-other@test.local')
        self.assertEqual(r.status_code, 403)

    def test_events_update_risk_score(self):
        session_id = self.start().data['id']
        client = self.login('proc-learner@test.local')
        r = client.post(f'/api/proctoring/{session_id}/events/', {
            'events': [
                {'event_type': 'TAB_SWITCH', 'detail': {'reason': 'tab-hidden'}},
                {'event_type': 'TAB_SWITCH', 'detail': {'reason': 'tab-hidden'}},
            ]}, format='json')
        self.assertEqual(r.status_code, 201)
        # TAB_SWITCH weighs 10, twice = 20 (still Low).
        self.assertEqual(r.data['risk_score'], 20)
        self.assertEqual(r.data['risk_band'], 'low')
        self.assertEqual(r.data['event_count'], 2)

    def test_looking_away_event_adds_five_to_risk_score(self):
        session_id = self.start().data['id']
        client = self.login('proc-learner@test.local')
        r = client.post(f'/api/proctoring/{session_id}/events/', {
            'events': [{'event_type': 'LOOKING_AWAY', 'detail': {
                'reason': 'gaze-down', 'sustained_ms': 5000}}]}, format='json')
        self.assertEqual(r.status_code, 201)
        # LOOKING_AWAY weighs 5 (still Low).
        self.assertEqual(r.data['risk_score'], 5)
        self.assertEqual(r.data['risk_band'], 'low')
        self.assertEqual(r.data['event_count'], 1)
        self.assertEqual(r.data['events'][0]['event_type'], 'LOOKING_AWAY')
        self.assertEqual(r.data['events'][0]['severity'], 'low')

    def test_invalid_event_type_is_rejected(self):
        session_id = self.start().data['id']
        r = self.login('proc-learner@test.local').post(
            f'/api/proctoring/{session_id}/events/',
            {'events': [{'event_type': 'MADE_UP', 'detail': {}}]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_learner_cannot_see_another_learners_session(self):
        session_id = self.start().data['id']
        other = self.login('proc-other@test.local')
        self.assertEqual(other.get(f'/api/proctoring/{session_id}/').status_code, 404)
        self.assertEqual(other.post(
            f'/api/proctoring/{session_id}/events/',
            {'events': [{'event_type': 'TAB_SWITCH'}]}, format='json').status_code, 404)

    def test_instructor_can_list_and_review(self):
        session_id = self.start().data['id']
        instructor = self.login('proc-inst@test.local')
        r = instructor.get('/api/proctoring/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([s['id'] for s in r.data['results']], [session_id])
        self.assertEqual(
            self.login('proc-learner@test.local').post(
                f'/api/proctoring/{session_id}/end/', {}, format='json').status_code, 200)
        r = instructor.post(f'/api/proctoring/{session_id}/review/',
                            {'review_note': 'Checked the timeline.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'reviewed')
        self.assertEqual(r.data['review_note'], 'Checked the timeline.')

    def test_high_risk_session_is_flagged_not_failed_on_end(self):
        session_id = self.start().data['id']
        client = self.login('proc-learner@test.local')
        # MULTIPLE_FACES 20 + NO_FACE 15 + CAMERA_BLOCKED 15 + TAB_SWITCH 10 = 60.
        r = client.post(f'/api/proctoring/{session_id}/events/', {'events': [
            {'event_type': 'MULTIPLE_FACES'},
            {'event_type': 'NO_FACE'},
            {'event_type': 'CAMERA_BLOCKED'},
            {'event_type': 'TAB_SWITCH'},
        ]}, format='json')
        self.assertEqual(r.data['risk_score'], 60)
        self.assertEqual(r.data['risk_band'], 'high')
        r = client.post(f'/api/proctoring/{session_id}/end/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'flagged')
