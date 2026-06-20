"""Accounts app test fixtures."""
import pytest
from django.utils import timezone


@pytest.fixture
def role_a(db, tenant_a):
    from apps.accounts.models import Role
    return Role.objects.create(tenant=tenant_a, name="Manager", description="Manager role")


@pytest.fixture
def pending_invite(db, tenant_a, admin_user):
    from apps.accounts.models import UserInvite
    return UserInvite.objects.create(
        tenant=tenant_a,
        email="newuser@acme.com",
        invited_by=admin_user,
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )


@pytest.fixture
def expired_invite(db, tenant_a, admin_user):
    from apps.accounts.models import UserInvite
    inv = UserInvite.objects.create(
        tenant=tenant_a,
        email="expired@acme.com",
        invited_by=admin_user,
        expires_at=timezone.now() - timezone.timedelta(days=1),
    )
    return inv
