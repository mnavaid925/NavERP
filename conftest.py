"""Root conftest — shared fixtures for all NavERP test suites."""
import pytest
from django.test import Client


@pytest.fixture
def tenant_a(db):
    from apps.core.models import Tenant
    return Tenant.objects.create(name="Acme Corp", slug="acme")


@pytest.fixture
def tenant_b(db):
    from apps.core.models import Tenant
    return Tenant.objects.create(name="Globex Corp", slug="globex")


@pytest.fixture
def admin_user(db, tenant_a):
    from apps.accounts.models import User
    return User.objects.create_user(
        email="admin@acme.com",
        username="admin_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=True,
    )


@pytest.fixture
def member_user(db, tenant_a):
    from apps.accounts.models import User
    return User.objects.create_user(
        email="member@acme.com",
        username="member_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )


@pytest.fixture
def admin_b(db, tenant_b):
    from apps.accounts.models import User
    return User.objects.create_user(
        email="admin@globex.com",
        username="admin_globex",
        password="TestPass123!",
        tenant=tenant_b,
        is_tenant_admin=True,
    )


@pytest.fixture
def client_a(db, admin_user):
    c = Client()
    c.force_login(admin_user)
    return c


@pytest.fixture
def client_b(db, admin_b):
    c = Client()
    c.force_login(admin_b)
    return c


@pytest.fixture
def member_client(db, member_user):
    c = Client()
    c.force_login(member_user)
    return c
