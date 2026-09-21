"""Security tests for the dashboard home view: anonymous access and tenant isolation.

The landing page aggregates six tables from other apps. Two things must never happen:
an anonymous visitor must not reach it, and one workspace must never see another's
figures. The tenant-less case is tested explicitly because ``views.home`` carries an
``if tenant is not None:`` guard whose whole purpose is that path.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def tenantless_client(db):
    """A logged-in superuser with **no tenant** — the ``if tenant is not None:`` premise.

    Defined here rather than in ``conftest.py`` because it is this lane's premise: the
    seeded superuser ``admin`` has ``tenant=None`` by design, and
    ``UserManager.create_superuser`` defaults it to ``None``.
    """
    from django.contrib.auth import get_user_model
    from django.test import Client

    user = get_user_model().objects.create_superuser(
        email="rootless@example.com", password="pw-rootless"
    )
    assert user.tenant is None
    client = Client()
    client.force_login(user)
    return client


# ------------------------------------------------------------------ Access control
class TestDashboardAccessControl:
    def test_anonymous_is_redirected_to_login(self, client):
        resp = client.get(reverse("dashboard:home"))
        assert resp.status_code == 302
        assert "/login" in resp["Location"]


# ------------------------------------------------------------------ Tenant isolation
class TestDashboardTenantIsolation:
    def test_tenant_isolation_of_the_aggregates(
        self, client_a, tenant_a, dash_parties, dash_invoices, dash_audit
    ):
        """tenant_b's rows exist in every table and are *newer* — none may surface."""
        resp = client_a.get(reverse("dashboard:home"))
        stats = resp.context["stats"]

        assert stats["parties_count"] == 3          # tenant_a's 3, not 3 + tenant_b's 2
        assert stats["open_invoices"] == 2          # tenant_a's 2, not 2 + tenant_b's 1

        recent = resp.context["recent_audit"]
        assert len(recent) == 8                     # capped from tenant_a's 10
        assert {row.tenant_id for row in recent} == {tenant_a.pk}


# ------------------------------------------------------------------ No tenant
class TestDashboardWithoutTenant:
    """The ``if tenant is not None:`` guard — the superuser path must render, not raise."""

    def test_no_tenant_renders_zeroed_stats(self, tenantless_client):
        resp = tenantless_client.get(reverse("dashboard:home"))
        assert resp.status_code == 200

        stats = resp.context["stats"]
        assert stats["users_count"] == 0
        assert stats["active_users"] == 0
        assert stats["parties_count"] == 0
        assert stats["open_invoices"] == 0
        assert stats["subscription"] is None

    def test_no_tenant_returns_empty_charts(self, tenantless_client):
        resp = tenantless_client.get(reverse("dashboard:home"))
        assert resp.context["health"] == []
        assert resp.context["recent_audit"] == []
        assert resp.context["chart_roles_labels"] == []
        assert resp.context["chart_roles_data"] == []
        assert resp.context["chart_activity_labels"] == []
        assert resp.context["chart_activity_data"] == []
