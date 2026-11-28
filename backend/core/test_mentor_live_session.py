from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .mentor_models import MentorProfile, MentorSession
from .models import User


class MentorLiveSessionTests(TestCase):
    def setUp(self):
        self.learner = User.objects.create_user('live-learner@test.local', 'SafePass123!', full_name='Learner', is_verified=True)
        self.mentor = User.objects.create_user('live-inst@test.local', 'SafePass123!', full_name='Mentor', role='instructor', is_verified=True, instructor_approved=True)
        self.profile = MentorProfile.objects.create(user=self.mentor, qualifications='BSc Computer Science', topics='Backtracking', hourly_rate=Decimal('1500.00'))
        self.when = (timezone.now() + timedelta(days=1)).isoformat()

    def login(self, email):
        client = APIClient()
        self.assertEqual(client.post('/api/auth/login/', {'email': email, 'password': 'SafePass123!'}, format='json').status_code, 200)
        return client

    def confirmed_session(self, meet_link='https://meet.google.com/abc-defg-hij'):
        return MentorSession.objects.create(
            student=self.learner, mentor=self.mentor, mentor_profile=self.profile,
            topic='Backtracking', duration_hours=1, hourly_rate=Decimal('1500.00'),
            total_fee=Decimal('1500.00'), scheduled_at=timezone.now() + timedelta(days=1),
            status='confirmed', meet_link=meet_link)

    def make_request(self, learner_client):
        r = learner_client.post('/api/mentor-hiring/requests/', {'topic': 'Backtracking', 'problem': 'I do not understand backtracking.', 'tried': 'I read the chapter.', 'preferred_duration_hours': 2, 'preferred_times': ['Saturday 10:00']}, format='json')
        self.assertEqual(r.status_code, 201)
        return r.data['id']

    def test_start_requires_confirmed_status_and_meet_link(self):
        mentor_client = self.login('live-inst@test.local')
        no_link = self.confirmed_session(meet_link='')
        r = mentor_client.post(f'/api/mentor-hiring/bookings/{no_link.id}/start/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        pending = MentorSession.objects.create(
            student=self.learner, mentor=self.mentor, mentor_profile=self.profile,
            topic='Backtracking', duration_hours=1, hourly_rate=Decimal('1500.00'),
            total_fee=Decimal('1500.00'), scheduled_at=timezone.now() + timedelta(days=1),
            status='pending', meet_link='https://meet.google.com/abc-defg-hij')
        r = mentor_client.post(f'/api/mentor-hiring/bookings/{pending.id}/start/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        session = self.confirmed_session()
        r = mentor_client.post(f'/api/mentor-hiring/bookings/{session.id}/start/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'live')
        self.assertIsNotNone(r.data['started_at'])
        session.refresh_from_db()
        self.assertEqual(session.status, 'live')
        self.assertIsNotNone(session.started_at)

    def test_student_cannot_start_or_end(self):
        session = self.confirmed_session()
        learner_client = self.login('live-learner@test.local')
        r = learner_client.post(f'/api/mentor-hiring/bookings/{session.id}/start/', {}, format='json')
        self.assertEqual(r.status_code, 403)
        mentor_client = self.login('live-inst@test.local')
        mentor_client.post(f'/api/mentor-hiring/bookings/{session.id}/start/', {}, format='json')
        r = learner_client.post(f'/api/mentor-hiring/bookings/{session.id}/end/', {}, format='json')
        self.assertEqual(r.status_code, 403)
        session.refresh_from_db()
        self.assertEqual(session.status, 'live')

    def test_end_only_from_live_returns_fare_breakdown(self):
        session = self.confirmed_session()
        mentor_client = self.login('live-inst@test.local')
        r = mentor_client.post(f'/api/mentor-hiring/bookings/{session.id}/end/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        mentor_client.post(f'/api/mentor-hiring/bookings/{session.id}/start/', {}, format='json')
        r = mentor_client.post(f'/api/mentor-hiring/bookings/{session.id}/end/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['session']['status'], 'completed')
        self.assertIsNotNone(r.data['session']['ended_at'])
        self.assertGreaterEqual(r.data['elapsed_minutes'], 0)
        self.assertEqual(Decimal(r.data['total_fee']), Decimal('1500.00'))
        self.assertEqual(Decimal(r.data['platform_deduction']), Decimal('150.00'))
        self.assertEqual(Decimal(r.data['credited_to_mentor']), Decimal('1350.00'))
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        self.assertIsNotNone(session.ended_at)

    def test_fixed_price_offer_accept_creates_session_with_agreed_amount(self):
        learner_client = self.login('live-learner@test.local')
        request_id = self.make_request(learner_client)
        mentor_client = self.login('live-inst@test.local')
        r = mentor_client.post('/api/mentor-hiring/offers/', {'session_request': request_id, 'proposed_time': self.when, 'pricing_type': 'fixed', 'agreed_amount': '2500.00', 'message': 'Fixed price for the whole topic.'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['pricing_type'], 'fixed')
        self.assertEqual(Decimal(r.data['agreed_amount']), Decimal('2500.00'))
        r = learner_client.post(f"/api/mentor-hiring/offers/{r.data['id']}/accept/", {}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['pricing_type'], 'fixed')
        self.assertEqual(Decimal(r.data['total_fee']), Decimal('2500.00'))
        self.assertEqual(r.data['status'], 'confirmed')

    def test_hourly_offer_accept_unchanged(self):
        learner_client = self.login('live-learner@test.local')
        request_id = self.make_request(learner_client)
        mentor_client = self.login('live-inst@test.local')
        r = mentor_client.post('/api/mentor-hiring/offers/', {'session_request': request_id, 'proposed_time': self.when, 'message': 'I can teach this.'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['pricing_type'], 'hourly')
        r = learner_client.post(f"/api/mentor-hiring/offers/{r.data['id']}/accept/", {}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(r.data['total_fee']), Decimal('3000.00'))

    def test_fixed_offer_requires_agreed_amount(self):
        learner_client = self.login('live-learner@test.local')
        request_id = self.make_request(learner_client)
        mentor_client = self.login('live-inst@test.local')
        r = mentor_client.post('/api/mentor-hiring/offers/', {'session_request': request_id, 'proposed_time': self.when, 'pricing_type': 'fixed', 'message': 'No amount.'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = mentor_client.post('/api/mentor-hiring/offers/', {'session_request': request_id, 'proposed_time': self.when, 'pricing_type': 'fixed', 'agreed_amount': '0.00', 'message': 'Zero amount.'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_browse_booking_stays_hourly(self):
        client = self.login('live-learner@test.local')
        r = client.post('/api/mentor-hiring/bookings/', {'mentor': self.mentor.id, 'topic': 'Backtracking', 'duration_hours': 2, 'scheduled_at': self.when}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['pricing_type'], 'hourly')
        self.assertEqual(Decimal(r.data['total_fee']), Decimal('3000.00'))

    def test_serializer_exposes_live_fields(self):
        session = self.confirmed_session()
        mentor_client = self.login('live-inst@test.local')
        mentor_client.post(f'/api/mentor-hiring/bookings/{session.id}/start/', {}, format='json')
        r = mentor_client.get(f'/api/mentor-hiring/bookings/{session.id}/', format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'live')
        self.assertIsNotNone(r.data['started_at'])
        self.assertIsNone(r.data['ended_at'])
        self.assertIsNotNone(r.data['elapsed_minutes'])
