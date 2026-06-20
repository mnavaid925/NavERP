"""Tests for accounts views: login, logout, user/role CRUD, invites, permissions."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ Login view
class TestLoginView:
    def test_get_login_200(self, client):
        resp = client.get(reverse("accounts:login"))
        assert resp.status_code == 200

    def test_login_by_email_redirects_dashboard(self, client, admin_user):
        resp = client.post(reverse("accounts:login"), {
            "identifier": admin_user.email,
            "password": "TestPass123!",
        })
        assert resp.status_code == 302
        assert "dashboard" in resp["Location"] or "/" in resp["Location"]

    def test_login_by_username_redirects_dashboard(self, client, admin_user):
        resp = client.post(reverse("accounts:login"), {
            "identifier": admin_user.username,
            "password": "TestPass123!",
        })
        assert resp.status_code == 302

    def test_wrong_password_stays_on_login(self, client, admin_user):
        resp = client.post(reverse("accounts:login"), {
            "identifier": admin_user.email,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 200

    def test_wrong_password_shows_error(self, client, admin_user):
        resp = client.post(reverse("accounts:login"), {
            "identifier": admin_user.email,
            "password": "WrongPassword!",
        })
        messages = list(resp.context["messages"])
        assert any("Invalid" in str(m) for m in messages)

    def test_authenticated_user_redirected_from_login(self, client_a):
        resp = client_a.get(reverse("accounts:login"))
        assert resp.status_code == 302

    def test_next_param_respected(self, client, admin_user):
        resp = client.post(
            reverse("accounts:login") + "?next=/core/parties/",
            {"identifier": admin_user.email, "password": "TestPass123!"},
        )
        assert resp.status_code == 302
        assert "/core/parties/" in resp["Location"]


# ------------------------------------------------------------------ Logout view
class TestLogoutView:
    def test_logout_requires_post(self, client_a):
        resp = client_a.get(reverse("accounts:logout"))
        # GET on a @require_POST view returns 405
        assert resp.status_code == 405

    def test_logout_post_redirects(self, client_a):
        resp = client_a.post(reverse("accounts:logout"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_logout_anon_redirects_to_login(self, client):
        resp = client.post(reverse("accounts:logout"))
        assert resp.status_code == 302


# ------------------------------------------------------------------ Forgot password
class TestForgotPassword:
    def test_returns_success_for_existing_email(self, client, admin_user):
        resp = client.post(reverse("accounts:forgot_password"), {
            "email": admin_user.email,
        })
        assert resp.status_code == 302  # redirects to login

    def test_returns_same_response_for_nonexistent_email(self, client):
        """Must NOT reveal whether the email exists."""
        resp = client.post(reverse("accounts:forgot_password"), {
            "email": "nonexistent@test.com",
        })
        # Same redirect regardless
        assert resp.status_code == 302

    def test_same_redirect_target_for_both(self, client, admin_user):
        r1 = client.post(reverse("accounts:forgot_password"), {"email": admin_user.email})
        r2 = client.post(reverse("accounts:forgot_password"), {"email": "nobody@test.com"})
        assert r1["Location"] == r2["Location"]


# ------------------------------------------------------------------ Register view
class TestRegisterView:
    def test_get_register_200(self, client):
        resp = client.get(reverse("accounts:register"))
        assert resp.status_code == 200

    def test_register_creates_tenant_and_admin(self, client):
        from apps.accounts.models import User
        from apps.core.models import Tenant
        resp = client.post(reverse("accounts:register"), {
            "company_name": "TestCo",
            "first_name": "Bob",
            "last_name": "Jones",
            "email": "bob@testco.com",
            "password1": "SuperSecret123!",
            "password2": "SuperSecret123!",
        })
        assert resp.status_code == 302
        assert User.objects.filter(email="bob@testco.com", is_tenant_admin=True).exists()
        assert Tenant.objects.filter(name="TestCo").count() == 1


# ------------------------------------------------------------------ User management
class TestUserManagement:
    def test_user_list_admin_200(self, client_a):
        resp = client_a.get(reverse("accounts:user_list"))
        assert resp.status_code == 200

    def test_user_list_member_403(self, member_client):
        resp = member_client.get(reverse("accounts:user_list"))
        assert resp.status_code == 403

    def test_user_list_anon_redirects(self, client):
        resp = client.get(reverse("accounts:user_list"))
        assert resp.status_code == 302

    def test_user_detail_admin_200(self, client_a, admin_user):
        resp = client_a.get(reverse("accounts:user_detail", args=[admin_user.pk]))
        assert resp.status_code == 200

    def test_user_detail_cross_tenant_404(self, client_a, admin_b):
        """Tenant A admin cannot see Tenant B user."""
        resp = client_a.get(reverse("accounts:user_detail", args=[admin_b.pk]))
        assert resp.status_code == 404

    def test_user_create_admin_200(self, client_a):
        resp = client_a.get(reverse("accounts:user_create"))
        assert resp.status_code == 200

    def test_user_create_member_403(self, member_client):
        resp = member_client.get(reverse("accounts:user_create"))
        assert resp.status_code == 403

    def test_user_delete_self_not_allowed(self, client_a, admin_user):
        resp = client_a.post(reverse("accounts:user_delete", args=[admin_user.pk]))
        # Redirects but does not delete self
        assert resp.status_code == 302
        from apps.accounts.models import User
        assert User.objects.filter(pk=admin_user.pk).exists()

    def test_user_delete_other_user(self, client_a, tenant_a):
        from apps.accounts.models import User
        target = User.objects.create_user(
            email="delete_me@acme.com",
            username="delete_me",
            password="TestPass123!",
            tenant=tenant_a,
        )
        resp = client_a.post(reverse("accounts:user_delete", args=[target.pk]))
        assert resp.status_code == 302
        assert not User.objects.filter(pk=target.pk).exists()


# ------------------------------------------------------------------ Role management
class TestRoleManagement:
    def test_role_list_admin_200(self, client_a):
        resp = client_a.get(reverse("accounts:role_list"))
        assert resp.status_code == 200

    def test_role_list_member_403(self, member_client):
        resp = member_client.get(reverse("accounts:role_list"))
        assert resp.status_code == 403

    def test_role_create_post(self, client_a, tenant_a):
        from apps.accounts.models import Role
        resp = client_a.post(reverse("accounts:role_create"), {
            "name": "Auditor",
            "description": "Read-only",
            "permissions": [],
        })
        assert resp.status_code == 302
        assert Role.objects.filter(tenant=tenant_a, name="Auditor").exists()

    def test_role_detail_cross_tenant_404(self, client_a, tenant_b):
        from apps.accounts.models import Role
        role_b = Role.objects.create(tenant=tenant_b, name="B Role")
        resp = client_a.get(reverse("accounts:role_detail", args=[role_b.pk]))
        assert resp.status_code == 404

    def test_role_delete_system_role_not_deleted(self, client_a, tenant_a):
        from apps.accounts.models import Role
        sys_role = Role.objects.create(tenant=tenant_a, name="System", is_system=True)
        resp = client_a.post(reverse("accounts:role_delete", args=[sys_role.pk]))
        assert resp.status_code == 302
        assert Role.objects.filter(pk=sys_role.pk).exists()

    def test_role_delete_non_system(self, client_a, tenant_a):
        from apps.accounts.models import Role
        role = Role.objects.create(tenant=tenant_a, name="Deletable")
        resp = client_a.post(reverse("accounts:role_delete", args=[role.pk]))
        assert resp.status_code == 302
        assert not Role.objects.filter(pk=role.pk).exists()


# ------------------------------------------------------------------ Invite management
class TestInviteManagement:
    def test_invite_list_admin_200(self, client_a):
        resp = client_a.get(reverse("accounts:invite_list"))
        assert resp.status_code == 200

    def test_invite_list_member_403(self, member_client):
        resp = member_client.get(reverse("accounts:invite_list"))
        assert resp.status_code == 403

    def test_invite_create_sends_invite(self, client_a, tenant_a):
        from apps.accounts.models import UserInvite
        resp = client_a.post(reverse("accounts:invite_create"), {
            "email": "invited@acme.com",
            "role": "",
        })
        assert resp.status_code == 302
        assert UserInvite.objects.filter(tenant=tenant_a, email="invited@acme.com").exists()

    def test_invite_accept_expired_token_invalid(self, client, expired_invite):
        resp = client.get(reverse("accounts:invite_accept", args=[expired_invite.token]))
        assert resp.status_code == 200
        assert resp.context["valid"] is False

    def test_invite_accept_valid_token_creates_user(self, client, pending_invite):
        resp = client.post(
            reverse("accounts:invite_accept", args=[pending_invite.token]),
            {
                "first_name": "New",
                "last_name": "User",
                "username": "new_user_acme",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        assert resp.status_code == 302
        from apps.accounts.models import User
        assert User.objects.filter(email="newuser@acme.com").exists()
        # Invite status updated to accepted
        pending_invite.refresh_from_db()
        assert pending_invite.status == "accepted"

    def test_invite_accept_valid_token_creates_user_in_correct_tenant(
        self, client, pending_invite, tenant_a
    ):
        client.post(
            reverse("accounts:invite_accept", args=[pending_invite.token]),
            {
                "first_name": "New",
                "last_name": "User",
                "username": "new_user_acme2",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        from apps.accounts.models import User
        u = User.objects.get(email="newuser@acme.com")
        assert u.tenant == tenant_a

    def test_invite_revoke(self, client_a, pending_invite):
        resp = client_a.post(reverse("accounts:invite_revoke", args=[pending_invite.pk]))
        assert resp.status_code == 302
        pending_invite.refresh_from_db()
        assert pending_invite.status == "revoked"


# ------------------------------------------------------------------ Profile
class TestProfile:
    def test_profile_requires_login(self, client):
        resp = client.get(reverse("accounts:profile"))
        assert resp.status_code == 302

    def test_profile_get_200(self, client_a):
        resp = client_a.get(reverse("accounts:profile"))
        assert resp.status_code == 200

    def test_profile_update(self, client_a, admin_user):
        resp = client_a.post(reverse("accounts:profile"), {
            "first_name": "Updated",
            "last_name": "Name",
            "email": admin_user.email,
            "username": admin_user.username,
        })
        assert resp.status_code == 302
        admin_user.refresh_from_db()
        assert admin_user.first_name == "Updated"
