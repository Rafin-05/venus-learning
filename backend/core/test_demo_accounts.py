from django.contrib.auth import authenticate
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .auth_backend import DemoAwareModelBackend
from .models import User


DEMO_PASSWORDS = {
    'learner': 'VenusDemo-Learner-2026!',
    'instructor': 'VenusDemo-Instructor-2026!',
    'admin': 'VenusDemo-Admin-2026!',
}
DEMO_EMAILS = {role: f'demo.{role}@example.com' for role in DEMO_PASSWORDS}


@override_settings(DEBUG=True, ENABLE_DEMO_ACCOUNTS=True)
class DemoAccountsTests(TestCase):
    def seed(self, *args):
        call_command('seed_demo', *args, verbosity=0)

    def test_all_demo_api_logins_and_role_boundaries(self):
        self.seed()
        client = APIClient()
        for role, email in DEMO_EMAILS.items():
            response = client.post('/api/auth/login/', {'email': email, 'password': DEMO_PASSWORDS[role]}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['role'], role)
            staff_response = client.get('/api/staff/dashboard/')
            self.assertEqual(staff_response.status_code, 200 if role == 'admin' else 403)
            client.post('/api/auth/logout/', format='json')

    def test_default_off_and_debug_false_block_auth_and_sessions(self):
        self.seed()
        user = User.objects.get(email=DEMO_EMAILS['admin'])
        backend = DemoAwareModelBackend()
        with override_settings(DEBUG=True, ENABLE_DEMO_ACCOUNTS=False):
            self.assertIsNone(authenticate(email=user.email, password=DEMO_PASSWORDS['admin']))
            self.assertIsNone(backend.get_user(user.pk))
        with override_settings(DEBUG=False, ENABLE_DEMO_ACCOUNTS=True):
            self.assertIsNone(authenticate(email=user.email, password=DEMO_PASSWORDS['admin']))
            self.assertIsNone(backend.get_user(user.pk))

    def test_existing_sessions_and_api_logins_are_blocked_when_disabled(self):
        self.seed()
        for debug, enabled in ((True, False), (False, True), (False, False)):
            for role, email in DEMO_EMAILS.items():
                client = APIClient()
                response = client.post('/api/auth/login/', {'email': email, 'password': DEMO_PASSWORDS[role]}, format='json')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(client.get('/api/auth/me/').status_code, 200)
                with override_settings(DEBUG=debug, ENABLE_DEMO_ACCOUNTS=enabled,
                                       SECURE_SSL_REDIRECT=False):
                    self.assertIn(client.get('/api/auth/me/').status_code, (401, 403))
                    response = APIClient().post('/api/auth/login/', {'email': email, 'password': DEMO_PASSWORDS[role]}, format='json')
                    self.assertIn(response.status_code, (400, 401, 403))

    def test_unexpected_demo_role_is_not_promoted_or_reset(self):
        user = User.objects.create_user(DEMO_EMAILS['admin'], 'KeepThisPassword-2026!',
                                        role='learner', is_demo_account=True)
        with self.assertRaises(CommandError):
            self.seed('--reset-passwords')
        user.refresh_from_db()
        self.assertEqual(user.role, 'learner')
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('KeepThisPassword-2026!'))
        self.assertEqual(User.objects.count(), 1)

    def test_real_accounts_are_unaffected(self):
        real = User.objects.create_user('real@example.com', 'RealPassword-2026!', role='learner', is_verified=True)
        with override_settings(DEBUG=False, ENABLE_DEMO_ACCOUNTS=False):
            self.assertIsNotNone(authenticate(email=real.email, password='RealPassword-2026!'))

    def test_collision_fails_atomically(self):
        User.objects.create_user(DEMO_EMAILS['learner'], 'RealPassword-2026!')
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(User.objects.filter(email=DEMO_EMAILS['admin']).exists())

    def test_idempotence_preserves_password_and_reset_restores_hash(self):
        self.seed()
        admin = User.objects.get(email=DEMO_EMAILS['admin'])
        admin.set_password('ChangedPassword-2026!')
        admin.save(update_fields=['password'])
        changed_hash = admin.password
        self.seed()
        admin.refresh_from_db()
        self.assertEqual(admin.password, changed_hash)
        self.assertTrue(admin.check_password('ChangedPassword-2026!'))
        self.seed('--reset-passwords')
        admin.refresh_from_db()
        self.assertTrue(admin.check_password(DEMO_PASSWORDS['admin']))
        self.assertNotEqual(admin.password, DEMO_PASSWORDS['admin'])

    def test_seed_requires_both_flags(self):
        with override_settings(DEBUG=True, ENABLE_DEMO_ACCOUNTS=False):
            with self.assertRaises(CommandError):
                self.seed()
        with override_settings(DEBUG=False, ENABLE_DEMO_ACCOUNTS=True):
            with self.assertRaises(CommandError):
                self.seed()
        self.assertEqual(User.objects.count(), 0)
