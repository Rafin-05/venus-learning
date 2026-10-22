from django.contrib.auth.backends import ModelBackend
from django.conf import settings


class DemoAwareModelBackend(ModelBackend):
    """Prevent demo accounts from authenticating outside an explicitly enabled demo run."""

    @staticmethod
    def demo_accounts_enabled():
        return bool(settings.DEBUG and settings.ENABLE_DEMO_ACCOUNTS)

    @classmethod
    def allowed(cls, user):
        return bool(user and (not user.is_demo_account or cls.demo_accounts_enabled()))

    def authenticate(self, request, username=None, password=None, **kwargs):
        user = super().authenticate(request, username=username, password=password, **kwargs)
        return user if self.allowed(user) else None

    def get_user(self, user_id):
        user = super().get_user(user_id)
        return user if self.allowed(user) else None
