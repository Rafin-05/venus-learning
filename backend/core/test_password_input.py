import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import EmailToken, LoginAttempt, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PasswordBodyValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "password-input@example.test", "SafePass123!",
            full_name="Password Input", is_verified=True,
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/auth/csrf/").cookies["csrftoken"].value
        self.token = EmailToken.objects.create(
            user=self.user, kind="reset",
            expires_at=timezone.now() + timedelta(hours=1),
        )

    def post_json(self, url, payload):
        # generic preserves [], false and null rather than replacing them with {}.
        return self.client.generic(
            "POST", url, data=json.dumps(payload),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )

    @patch("core.views.send_mail")
    def assert_non_object_bodies_rejected(self, url, send_mail):
        original_password = User.objects.get(pk=self.user.pk).password
        original_tokens = list(EmailToken.objects.values())
        original_attempts = list(LoginAttempt.objects.values())
        original_session_user = self.client.session.get("_auth_user_id")
        payloads = [
            [],
            [{"email": self.user.email, "current_password": "SafePass123!",
              "new_password": "NewSafePass123!", "password": "NewSafePass123!"}],
            "not-an-object", 42, True, None,
        ]
        for payload in payloads:
            with self.subTest(url=url, payload=payload):
                response = self.post_json(url, payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {
                    "detail": "Request body must be a JSON object.",
                })
                self.user.refresh_from_db()
                self.assertEqual(self.user.password, original_password)
                self.assertEqual(list(EmailToken.objects.values()), original_tokens)
                self.assertEqual(list(LoginAttempt.objects.values()), original_attempts)
                self.assertEqual(self.client.session.get("_auth_user_id"), original_session_user)
                send_mail.assert_not_called()

    def test_change_password_rejects_non_objects_without_side_effects(self):
        # Use a real session and valid CSRF, not force_authenticate.
        self.client.force_login(self.user)
        self.assert_non_object_bodies_rejected("/api/auth/change-password/")

    def test_reset_request_rejects_non_objects_without_side_effects(self):
        self.assert_non_object_bodies_rejected("/api/auth/password-reset/")

    def test_reset_confirmation_rejects_non_objects_without_consuming_token(self):
        self.assert_non_object_bodies_rejected(
            f"/api/auth/password-reset/confirm/{self.token.token}/",
        )
        response = self.post_json(
            f"/api/auth/password-reset/confirm/{self.token.token}/",
            {"password": "NewSafePass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.token.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSafePass123!"))
        self.assertIsNotNone(self.token.used_at)

    def test_valid_change_password_still_updates_password_and_logs_out(self):
        self.client.force_login(self.user)
        response = self.post_json("/api/auth/change-password/", {
            "current_password": "SafePass123!", "new_password": "NewSafePass123!",
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSafePass123!"))
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_malformed_bodies_do_not_bypass_authentication_or_csrf(self):
        self.assertEqual(self.post_json("/api/auth/change-password/", []).status_code, 403)
        self.client.force_login(self.user)
        for url in (
            "/api/auth/change-password/", "/api/auth/password-reset/",
            f"/api/auth/password-reset/confirm/{self.token.token}/",
        ):
            with self.subTest(url=url):
                response = self.client.post(url, [], format="json")
                self.assertEqual(response.status_code, 403)
