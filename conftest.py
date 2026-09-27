"""Root conftest — shared fixtures for all NavERP test suites."""
import pytest
from django.db.backends.signals import connection_created
from django.dispatch import receiver
from django.test import Client


# ------------------------------------------------------------------ SQLite speed (test DB only)
@receiver(connection_created)
def _naverp_sqlite_fast_pragmas(sender, connection, **kwargs):
    """Make the TEST SQLite database skip durability work.

    Applying ~270 migrations commits thousands of times, and SQLite's default `synchronous=FULL`
    fsyncs on every one of them. On Windows that dominates the entire suite — the migration phase
    alone ran past 20 minutes of solid CPU. The database is thrown away after the run, so durability
    buys us nothing; what we actually want from a test database is *speed*.

    Guarded on the engine, so this can never touch a real database: it fires only for SQLite, and
    under `pytest` the only settings module in play is `config.settings_test`, which is SQLite-only
    by design (L19 — the suite must never reach the shared MySQL dev database).
    """
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA synchronous=OFF;")
        cursor.execute("PRAGMA journal_mode=MEMORY;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA cache_size=-64000;")  # 64 MB, negative == KiB not pages


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
