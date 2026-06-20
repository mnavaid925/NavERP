"""Security tests for the accounts app."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestAuthBackend:
    """EmailOrUsernameModelBackend authenticates by email or username."""

    def test_auth_by_email(self, admin_user):
        from django.contrib.auth import authenticate
        user = authenticate(None, username=admin_user.email, password="TestPass123!")
        assert user is not None
        assert user.pk == admin_user.pk

    def test_auth_by_username(self, admin_user):
        from django.contrib.auth import authenticate
        user = authenticate(None, username=admin_user.username, password="TestPass123!")
        assert user is not None
        assert user.pk == admin_user.pk

    def test_auth_case_insensitive_email(self, admin_user):
        from django.contrib.auth import authenticate
        user = authenticate(None, username=admin_user.email.upper(), password="TestPass123!")
        assert user is not None

    def test_wrong_password_returns_none(self, admin_user):
        from django.contrib.auth import authenticate
        user = authenticate(None, username=admin_user.email, password="WrongPass!")
        assert user is None

    def test_nonexistent_email_returns_none(self):
        from django.contrib.auth import authenticate
        user = authenticate(None, username="ghost@test.com", password="TestPass123!")
        assert user is None


class TestTenantAdminRequired:
    """@tenant_admin_required blocks non-admin members with 403."""

    def test_member_blocked_user_list(self, member_client):
        resp = member_client.get(reverse("accounts:user_list"))
        assert resp.status_code == 403

    def test_member_blocked_role_list(self, member_client):
        resp = member_client.get(reverse("accounts:role_list"))
        assert resp.status_code == 403

    def test_member_blocked_invite_list(self, member_client):
        resp = member_client.get(reverse("accounts:invite_list"))
        assert resp.status_code == 403

    def test_admin_allowed_user_list(self, client_a):
        resp = client_a.get(reverse("accounts:user_list"))
        assert resp.status_code == 200

    def test_anon_redirected_user_list(self, client):
        resp = client.get(reverse("accounts:user_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCSRFOnAccountViews:
    """CSRF is enforced on POST endpoints."""

    def test_logout_requires_csrf(self, admin_user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("accounts:logout"))
        assert resp.status_code == 403

    def test_user_delete_requires_csrf(self, admin_user, tenant_a):
        from apps.accounts.models import User
        target = User.objects.create_user(
            email="csrf_target@acme.com",
            username="csrf_target",
            password="TestPass123!",
            tenant=tenant_a,
        )
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("accounts:user_delete", args=[target.pk]))
        assert resp.status_code == 403
        # Target must still exist
        assert User.objects.filter(pk=target.pk).exists()


class TestForgotPasswordDoesNotLeakEmailExistence:
    """Forgot password endpoint must always return the same response."""

    def test_no_leak_for_registered_email(self, client, admin_user):
        resp = client.post(reverse("accounts:forgot_password"), {"email": admin_user.email})
        assert resp.status_code == 302

    def test_no_leak_for_unregistered_email(self, client):
        resp = client.post(reverse("accounts:forgot_password"), {"email": "unknown@test.com"})
        assert resp.status_code == 302

    def test_same_redirect_location(self, client, admin_user):
        r1 = client.post(reverse("accounts:forgot_password"), {"email": admin_user.email})
        r2 = client.post(reverse("accounts:forgot_password"), {"email": "nobody@test.com"})
        assert r1["Location"] == r2["Location"]


class TestInviteCrossTenantIsolation:
    """Tenant A admin cannot revoke Tenant B invites."""

    def test_revoke_cross_tenant_invite_404(self, client_a, tenant_b, admin_b):
        from apps.accounts.models import UserInvite
        from django.utils import timezone
        inv_b = UserInvite.objects.create(
            tenant=tenant_b,
            email="b_invite@globex.com",
            invited_by=admin_b,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        resp = client_a.post(reverse("accounts:invite_revoke", args=[inv_b.pk]))
        assert resp.status_code == 404
