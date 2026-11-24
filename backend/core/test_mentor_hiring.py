from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .mentor_models import MentorProfile, MentorSession, SessionRequest, Wallet, WalletTransaction
from .models import User


class MentorHiringTests(TestCase):
    def setUp(self):
        self.learner = User.objects.create_user('mentor-learner@test.local', 'SafePass123!', full_name='Learner', is_verified=True)
        self.mentor = User.objects.create_user('mentor-inst@test.local', 'SafePass123!', full_name='Mentor', role='instructor', is_verified=True, instructor_approved=True)
        self.profile = MentorProfile.objects.create(user=self.mentor, qualifications='BSc Computer Science', topics='Backtracking, Dynamic Programming', hourly_rate=Decimal('1500.00'))
        self.when = (timezone.now() + timedelta(days=1)).isoformat()

    def login(self, email):
        client = APIClient()
        self.assertEqual(client.post('/api/auth/login/', {'email': email, 'password': 'SafePass123!'}, format='json').status_code, 200)
        return client

    def completed_session(self, fee=Decimal('3000.00')):
        return MentorSession.objects.create(student=self.learner, mentor=self.mentor, mentor_profile=self.profile, topic='Backtracking', duration_hours=2, hourly_rate=Decimal('1500.00'), total_fee=fee, scheduled_at=timezone.now() - timedelta(hours=3), status='completed')

    def test_wallet_top_up_creates_ledger_entry(self):
        client = self.login('mentor-learner@test.local')
        r = client.post('/api/mentor-hiring/wallet/top-up/', {'amount': '3000.00'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(r.data['wallet']['balance']), Decimal('3000.00'))
        entries = WalletTransaction.objects.filter(user=self.learner, kind='top_up')
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().amount, Decimal('3000.00'))
        r = client.get('/api/mentor-hiring/wallet/transactions/')
        self.assertEqual(len(r.data), 1)

    def test_browse_booking_computes_total_from_rate_and_hours(self):
        client = self.login('mentor-learner@test.local')
        r = client.post('/api/mentor-hiring/bookings/', {'mentor': self.mentor.id, 'topic': 'Backtracking', 'duration_hours': 2, 'scheduled_at': self.when}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(r.data['total_fee']), Decimal('3000.00'))
        self.assertEqual(Decimal(r.data['hourly_rate']), Decimal('1500.00'))
        self.assertEqual(r.data['status'], 'pending')
        self.assertEqual(r.data['payment_status'], 'unpaid')

    def test_payment_math_deduction_and_mentor_credit(self):
        session = self.completed_session()
        client = self.login('mentor-learner@test.local')
        client.post('/api/mentor-hiring/wallet/top-up/', {'amount': '3000.00'}, format='json')
        r = client.post(f'/api/mentor-hiring/bookings/{session.id}/pay/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(r.data['platform_deduction']), Decimal('300.00'))
        self.assertEqual(Decimal(r.data['credited_to_mentor']), Decimal('2700.00'))
        self.assertEqual(Wallet.objects.get(user=self.learner).balance, Decimal('0.00'))
        self.assertEqual(Wallet.objects.get(user=self.mentor).balance, Decimal('2700.00'))
        deduction = WalletTransaction.objects.get(session=session, kind='platform_deduction')
        self.assertEqual(deduction.deduction_amount, Decimal('300.00'))
        payment = WalletTransaction.objects.get(session=session, kind='session_payment')
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.fee_amount, Decimal('3000.00'))
        credit = WalletTransaction.objects.get(session=session, kind='mentor_credit')
        self.assertEqual(credit.status, 'credited')
        self.assertEqual(credit.credited_amount, Decimal('2700.00'))
        session.refresh_from_db()
        self.assertEqual(session.payment_status, 'paid')

    def test_payment_with_insufficient_balance_is_rejected(self):
        session = self.completed_session()
        client = self.login('mentor-learner@test.local')
        client.post('/api/mentor-hiring/wallet/top-up/', {'amount': '100.00'}, format='json')
        r = client.post(f'/api/mentor-hiring/bookings/{session.id}/pay/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        session.refresh_from_db()
        self.assertEqual(session.payment_status, 'unpaid')
        self.assertEqual(Wallet.objects.get(user=self.learner).balance, Decimal('100.00'))
        self.assertFalse(WalletTransaction.objects.filter(session=session).exists())

    def test_offer_accept_creates_booking(self):
        learner_client = self.login('mentor-learner@test.local')
        r = learner_client.post('/api/mentor-hiring/requests/', {'topic': 'Backtracking', 'problem': 'I do not understand backtracking.', 'tried': 'I read the chapter and tried two problems.', 'preferred_duration_hours': 2, 'preferred_times': ['Saturday 10:00']}, format='json')
        self.assertEqual(r.status_code, 201)
        request_id = r.data['id']
        mentor_client = self.login('mentor-inst@test.local')
        r = mentor_client.post('/api/mentor-hiring/offers/', {'session_request': request_id, 'proposed_time': self.when, 'message': 'I can teach this.'}, format='json')
        self.assertEqual(r.status_code, 201)
        offer_id = r.data['id']
        self.assertEqual(Decimal(r.data['hourly_rate']), Decimal('1500.00'))
        r = learner_client.post(f'/api/mentor-hiring/offers/{offer_id}/accept/', {}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Decimal(r.data['total_fee']), Decimal('3000.00'))
        self.assertEqual(r.data['status'], 'confirmed')
        self.assertEqual(r.data['source'], 'request')
        self.assertEqual(SessionRequest.objects.get(id=request_id).status, 'booked')

    def test_rating_only_after_completion(self):
        session = MentorSession.objects.create(student=self.learner, mentor=self.mentor, mentor_profile=self.profile, topic='Backtracking', duration_hours=1, hourly_rate=Decimal('1500.00'), total_fee=Decimal('1500.00'), scheduled_at=timezone.now() + timedelta(days=1), status='confirmed')
        client = self.login('mentor-learner@test.local')
        r = client.post('/api/mentor-hiring/ratings/', {'session': session.id, 'rating': 5, 'comment': 'Great session.'}, format='json')
        self.assertEqual(r.status_code, 400)
        session.status = 'completed'
        session.save(update_fields=['status'])
        r = client.post('/api/mentor-hiring/ratings/', {'session': session.id, 'rating': 5, 'comment': 'Great session.'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['rating'], 5)
        self.assertEqual(r.data['mentor'], self.mentor.id)

    def test_refund_returns_fee_to_student(self):
        session = self.completed_session()
        client = self.login('mentor-learner@test.local')
        client.post('/api/mentor-hiring/wallet/top-up/', {'amount': '3000.00'}, format='json')
        client.post(f'/api/mentor-hiring/bookings/{session.id}/pay/', {}, format='json')
        r = client.post(f'/api/mentor-hiring/bookings/{session.id}/refund/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['payment_status'], 'refunded')
        self.assertEqual(Wallet.objects.get(user=self.learner).balance, Decimal('3000.00'))
        self.assertEqual(Wallet.objects.get(user=self.mentor).balance, Decimal('0.00'))
        self.assertTrue(WalletTransaction.objects.filter(session=session, kind='refund', status='refunded').exists())
