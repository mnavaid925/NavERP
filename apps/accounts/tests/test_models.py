"""Tests for accounts models: User, Role, UserInvite."""
import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ User
class TestUser:
    def test_str(self, admin_user):
        assert str(admin_user) == "admin@acme.com"

    def test_get_full_name(self):
        from apps.accounts.models import User
        u = User.objects.create_user(
            email="full@test.com", username="fullname",
            password="TestPass123!", first_name="John", last_name="Doe"
        )
        assert u.get_full_name() == "John Doe"

    def test_get_full_name_fallback_to_username(self, admin_user):
        # admin_user has no first/last name set
        result = admin_user.get_full_name()
        assert result == admin_user.username

    def test_get_short_name_fallback(self, admin_user):
        result = admin_user.get_short_name()
        assert result == admin_user.username

    def test_initials_from_names(self):
        from apps.accounts.models import User
        u = User.objects.create_user(
            email="initials@test.com", username="initials_user",
            password="TestPass123!", first_name="Alice", last_name="Brown"
        )
        assert u.initials == "AB"

    def test_initials_fallback_to_email(self):
        from apps.accounts.models import User
        u = User.objects.create_user(
            email="zara@test.com", username="zara_user", password="TestPass123!"
        )
        # first_name empty, last_name empty → first char of email
        assert u.initials[0] == "Z"

    def test_default_status(self, admin_user):
        assert admin_user.status == "active"

    def test_is_tenant_admin_flag(self, admin_user, member_user):
        assert admin_user.is_tenant_admin is True
        assert member_user.is_tenant_admin is False

    def test_tenant_fk(self, admin_user, tenant_a):
        assert admin_user.tenant == tenant_a

    def test_status_choices(self):
        from apps.accounts.models import User
        statuses = [c[0] for c in User.STATUS_CHOICES]
        assert "active" in statuses
        assert "suspended" in statuses
        assert "archived" in statuses

    def test_create_superuser_no_tenant(self):
        from apps.accounts.models import User
        su = User.objects.create_superuser(
            email="su@test.com", username="superuser", password="TestPass123!"
        )
        assert su.is_superuser is True
        assert su.is_staff is True
        assert su.tenant is None

    def test_create_superuser_is_tenant_admin_false_by_default(self):
        from apps.accounts.models import User
        su = User.objects.create_superuser(
            email="su2@test.com", username="superuser2", password="TestPass123!"
        )
        assert su.is_tenant_admin is False

    def test_username_derived_from_email_if_absent(self, tenant_a):
        from apps.accounts.models import User
        u = User.objects.create_user(
            email="derive@test.com", password="TestPass123!", tenant=tenant_a
        )
        assert u.username == "derive"


# ------------------------------------------------------------------ Role
class TestRole:
    def test_str(self, role_a):
        assert str(role_a) == "Manager"

    def test_unique_together_tenant_name(self, tenant_a):
        from apps.accounts.models import Role
        from django.db import IntegrityError
        Role.objects.create(tenant=tenant_a, name="Duplicate")
        with pytest.raises(IntegrityError):
            Role.objects.create(tenant=tenant_a, name="Duplicate")

    def test_same_name_different_tenants_ok(self, tenant_a, tenant_b):
        from apps.accounts.models import Role
        r1 = Role.objects.create(tenant=tenant_a, name="Editor")
        r2 = Role.objects.create(tenant=tenant_b, name="Editor")
        assert r1.pk != r2.pk

    def test_is_system_default_false(self, tenant_a):
        from apps.accounts.models import Role
        role = Role.objects.create(tenant=tenant_a, name="Guest")
        assert role.is_system is False


# ------------------------------------------------------------------ UserInvite
class TestUserInvite:
    def test_token_auto_generated(self, pending_invite):
        assert pending_invite.token
        assert len(pending_invite.token) > 10

    def test_token_unique(self, tenant_a, admin_user):
        from apps.accounts.models import UserInvite
        inv1 = UserInvite.objects.create(
            tenant=tenant_a, email="a@test.com",
            invited_by=admin_user,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        inv2 = UserInvite.objects.create(
            tenant=tenant_a, email="b@test.com",
            invited_by=admin_user,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        assert inv1.token != inv2.token

    def test_expires_at_auto_set_when_not_given(self, tenant_a, admin_user):
        from apps.accounts.models import UserInvite
        # Pass expires_at explicitly because the model sets it in save() only if None
        # But let's test by not providing it (let it be set by the model)
        # Note: The fixture provides it; test the "not provided → auto-set" path via direct create
        # The model checks `if not self.expires_at:` in save()
        inv = UserInvite(
            tenant=tenant_a, email="auto@test.com", invited_by=admin_user
        )
        # expires_at is not set yet
        inv.save()
        assert inv.expires_at is not None
        # Should be roughly 7 days from now
        delta = inv.expires_at - timezone.now()
        assert 6 < delta.total_seconds() / 86400 < 8

    def test_is_expired_false_for_pending(self, pending_invite):
        assert pending_invite.is_expired() is False

    def test_is_expired_true_for_expired(self, expired_invite):
        assert expired_invite.is_expired() is True

    def test_str(self, pending_invite, tenant_a):
        assert "newuser@acme.com" in str(pending_invite)
        assert str(tenant_a) in str(pending_invite)

    def test_default_status(self, pending_invite):
        assert pending_invite.status == "pending"
