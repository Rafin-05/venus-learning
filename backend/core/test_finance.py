from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from .finance_models import TopUpRequest, WithdrawalRequest
from .mentor_models import Wallet, WalletTransaction
from .models import User


class FinanceTests(TestCase):
    def setUp(self):
        self.learner = User.objects.create_user('fin-learner@test.local', 'SafePass123!', full_name='Nusrat Jahan', is_verified=True)
        self.instructor = User.objects.create_user('fin-inst@test.local', 'SafePass123!', full_name='Tanvir Ahmed', role='instructor', is_verified=True, instructor_approved=True)
        self.admin = User.objects.create_user('fin-admin@test.local', 'SafePass123!', full_name='Admin', role='admin', is_staff=True, is_verified=True)

    def login(self, email):
        client = APIClient()
        self.assertEqual(client.post('/api/auth/login/', {'email': email, 'password': 'SafePass123!'}, format='json').status_code, 200)
        return client

    def top_up(self, amount='1500.00', method='bkash', transaction_id=None, account_number='01712345678'):
        return self.login('fin-learner@test.local').post('/api/finance/top-ups/', {
            'method': method, 'account_number': account_number,
            'transaction_id': transaction_id or f'TRX{uuid4().hex[:10]}', 'amount': amount,
        }, format='json')

    def withdraw(self, amount='500.00', method='nagad', account_number='01912345678'):
        return self.login('fin-inst@test.local').post('/api/finance/withdrawals/', {'method': method, 'account_number': account_number, 'amount': amount}, format='json')

    def balance(self, user):
        wallet = Wallet.objects.filter(user=user).first()
        return wallet.balance if wallet else Decimal('0.00')

    def credit_instructor(self, amount='2000.00'):
        Wallet.objects.update_or_create(user=self.instructor, defaults={'balance': Decimal(amount)})

    def test_summary_shows_balance_and_methods_for_learner(self):
        r = self.login('fin-learner@test.local').get('/api/finance/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(r.data['balance']), Decimal('0.00'))
        self.assertFalse(r.data['can_withdraw'])
        self.assertEqual([m['value'] for m in r.data['payment_methods']], ['bkash', 'nagad', 'rocket'])

    def test_summary_marks_instructors_as_withdrawable(self):
        r = self.login('fin-inst@test.local').get('/api/finance/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['can_withdraw'])

    def test_top_up_stays_pending_until_approved_then_credits_balance(self):
        r = self.top_up('1500.00', transaction_id='BKH8J2K9QW')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['status'], 'pending')
        self.assertEqual(self.balance(self.learner), Decimal('0.00'))

        r = self.login('fin-admin@test.local').post(f"/api/finance/top-ups/{r.data['id']}/approve/", {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'approved')
        self.assertEqual(self.balance(self.learner), Decimal('1500.00'))
        entry = WalletTransaction.objects.get(user=self.learner, kind='top_up')
        self.assertEqual(entry.amount, Decimal('1500.00'))
        self.assertIn('BKH8J2K9QW', entry.note)

        self.assertEqual(self.login('fin-admin@test.local').post(f"/api/finance/top-ups/{r.data['id']}/approve/", {}, format='json').status_code, 400)

    def test_rejected_top_up_does_not_credit_balance(self):
        r = self.top_up('900.00')
        r = self.login('fin-admin@test.local').post(f"/api/finance/top-ups/{r.data['id']}/reject/", {'note': 'Transaction not found.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'rejected')
        self.assertEqual(r.data['review_note'], 'Transaction not found.')
        self.assertEqual(self.balance(self.learner), Decimal('0.00'))
        self.assertFalse(WalletTransaction.objects.filter(user=self.learner).exists())

    def test_reused_transaction_id_is_rejected(self):
        self.assertEqual(self.top_up('500.00', 'bkash', 'DUPLICATE1').status_code, 201)
        r = self.top_up('500.00', 'bkash', 'DUPLICATE1')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.top_up('500.00', 'nagad', 'DUPLICATE1').status_code, 201)

    def test_top_up_validates_method_account_and_amount(self):
        self.assertEqual(self.top_up('500.00', method='paypal').status_code, 400)
        self.assertEqual(self.top_up('500.00', account_number='12345').status_code, 400)
        self.assertEqual(self.top_up('0.00').status_code, 400)

    def test_only_staff_can_review_requests(self):
        r = self.top_up('500.00')
        self.assertEqual(self.login('fin-learner@test.local').post(f"/api/finance/top-ups/{r.data['id']}/approve/", {}, format='json').status_code, 403)
        self.assertEqual(self.login('fin-inst@test.local').post(f"/api/finance/top-ups/{r.data['id']}/approve/", {}, format='json').status_code, 403)
        self.assertEqual(TopUpRequest.objects.get(pk=r.data['id']).status, 'pending')

    def test_learner_cannot_request_withdrawal(self):
        r = self.login('fin-learner@test.local').post('/api/finance/withdrawals/', {'method': 'bkash', 'account_number': '01712345678', 'amount': '100.00'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.login('fin-learner@test.local').get('/api/finance/withdrawals/').data, [])
        self.assertFalse(WithdrawalRequest.objects.exists())

    def test_instructor_withdrawal_pays_out_from_balance(self):
        self.credit_instructor('2000.00')
        r = self.withdraw('700.00')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['status'], 'pending')
        self.assertEqual(Decimal(Wallet.objects.get(user=self.instructor).balance), Decimal('2000.00'))

        r = self.login('fin-admin@test.local').post(f"/api/finance/withdrawals/{r.data['id']}/approve/", {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'paid')
        self.assertEqual(Decimal(Wallet.objects.get(user=self.instructor).balance), Decimal('1300.00'))
        entry = WalletTransaction.objects.get(user=self.instructor, kind='withdrawal')
        self.assertEqual(entry.amount, Decimal('-700.00'))
        self.assertEqual(entry.status, 'paid')

    def test_withdrawal_above_balance_is_rejected(self):
        self.credit_instructor('200.00')
        self.assertEqual(self.withdraw('500.00').status_code, 400)

    def test_withdrawal_is_rechecked_at_payout_time(self):
        self.credit_instructor('600.00')
        r = self.withdraw('500.00')
        wallet = Wallet.objects.get(user=self.instructor)
        wallet.balance = Decimal('100.00')
        wallet.save(update_fields=['balance'])
        r = self.login('fin-admin@test.local').post(f"/api/finance/withdrawals/{r.data['id']}/approve/", {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(WithdrawalRequest.objects.first().status, 'pending')
        self.assertEqual(Decimal(Wallet.objects.get(user=self.instructor).balance), Decimal('100.00'))

    def test_rejected_withdrawal_keeps_balance(self):
        self.credit_instructor('800.00')
        r = self.withdraw('300.00')
        r = self.login('fin-admin@test.local').post(f"/api/finance/withdrawals/{r.data['id']}/reject/", {'note': 'Number does not match.'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['status'], 'rejected')
        self.assertEqual(Decimal(Wallet.objects.get(user=self.instructor).balance), Decimal('800.00'))

    def test_staff_sees_all_withdrawal_requests_for_review(self):
        self.credit_instructor('800.00')
        self.withdraw('300.00')
        r = self.login('fin-admin@test.local').get('/api/finance/withdrawals/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['user_email'], 'fin-inst@test.local')
        self.assertEqual(r.data[0]['status'], 'pending')

        learner_view = self.login('fin-learner@test.local').get('/api/finance/withdrawals/')
        self.assertEqual(learner_view.status_code, 200)
        self.assertEqual(learner_view.data, [])

    def test_transactions_endpoint_lists_ledger(self):
        r = self.top_up('400.00')
        self.login('fin-admin@test.local').post(f"/api/finance/top-ups/{r.data['id']}/approve/", {}, format='json')
        r = self.login('fin-learner@test.local').get('/api/finance/transactions/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['kind'], 'top_up')
        self.assertEqual(Decimal(r.data[0]['amount']), Decimal('400.00'))

    def test_legacy_mentor_wallet_endpoint_is_gone(self):
        self.assertEqual(self.login('fin-learner@test.local').post('/api/mentor-hiring/wallet/top-up/', {'amount': '10.00'}, format='json').status_code, 404)
