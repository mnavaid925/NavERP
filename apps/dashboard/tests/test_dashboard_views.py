"""Tests for the dashboard home view: tenant-scoped KPI aggregation.

``apps/dashboard`` owns no models and no forms of its own, so the four-lane convention
collapses to two here — a ``_models`` or ``_forms`` file would be empty. Everything
interesting about this app lives in ``views.home``, which is why the assertions below
are exact figures rather than smoke-level status codes.

The figures come from the fixtures in this package's ``conftest.py``, which builds on
the root baseline (``tenant_a`` = 2 active users and nothing else, ``tenant_b`` =
nothing at all).
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _home(client):
    return client.get(reverse("dashboard:home"))


# ------------------------------------------------------------------ Rendering and counters
class TestDashboardCounters:
    def test_home_renders_for_an_authenticated_tenant_user(self, client_a):
        resp = _home(client_a)
        assert resp.status_code == 200
        assert "dashboard/home.html" in [t.name for t in resp.templates]

    def test_user_counts_equal_the_seeded_figures(self, client_a, member_user):
        """2 users, both active.

        ``member_user`` is requested **deliberately**: pytest fixtures are lazy, so
        ``client_a`` alone leaves tenant_a with just its own ``admin_acme`` and the
        count would read 1. Naming the fixture here makes the premise visible instead
        of encoding a fixture-graph accident as an expected figure.
        """
        stats = _home(client_a).context["stats"]
        assert stats["users_count"] == 2
        assert stats["active_users"] == 2

    def test_party_count_is_tenant_scoped(self, client_a, dash_parties):
        # tenant_a has 3, tenant_b has 2 — a leaked filter would report 5.
        assert _home(client_a).context["stats"]["parties_count"] == 3

    def test_open_invoice_count_counts_only_open(self, client_a, dash_invoices):
        # tenant_a has 2 open + 1 paid; tenant_b's open one must not be counted either.
        assert _home(client_a).context["stats"]["open_invoices"] == 2

    def test_subscription_is_the_newest(self, client_a, dash_subscription):
        stats = _home(client_a).context["stats"]
        assert stats["subscription"] is not None
        assert stats["subscription"].pk == dash_subscription["newer"].pk


# ------------------------------------------------------------------ Grouped charts
class TestDashboardCharts:
    def test_role_chart_groups_and_orders_by_count_desc(self, client_a, dash_party_roles):
        resp = _home(client_a)
        # 2x customer, 1x supplier -> customer first under order_by("-c").
        # Labels are display strings from ROLE_CHOICES, not the raw db values.
        assert resp.context["chart_roles_labels"] == ["Customer", "Supplier"]
        assert resp.context["chart_roles_data"] == [2, 1]

    def test_activity_chart_groups_and_orders_by_status(self, client_a, dash_activities):
        resp = _home(client_a)
        # order_by("status") ascending: "done" before "open".
        assert resp.context["chart_activity_labels"] == ["Done", "Open"]
        assert resp.context["chart_activity_data"] == [1, 2]
        assert sum(resp.context["chart_activity_data"]) == 3

    def test_chart_label_and_data_lists_are_the_same_length(self, client_a, dash_party_roles, dash_activities):
        """The drift guard: a label list out of step with its data list breaks the chart silently."""
        resp = _home(client_a)
        assert len(resp.context["chart_roles_labels"]) == len(resp.context["chart_roles_data"])
        assert len(resp.context["chart_activity_labels"]) == len(resp.context["chart_activity_data"])

    def test_chart_label_falls_back_to_the_raw_value(self, client_a, tenant_a, dash_party_roles, dash_activities):
        """A value outside CHOICES must render as itself, never as ``None``.

        ``PartyRole.role`` and ``Activity.status`` are CharFields whose choices are not
        enforced on ``create()``, so an out-of-list value is reachable.
        """
        from apps.core.models import Activity, Party, PartyRole
        PartyRole.objects.create(
            tenant=tenant_a, party=Party.objects.create(tenant=tenant_a, name="Edge Case"), role="broker"
        )
        Activity.objects.create(tenant=tenant_a, subject="Edge Case", status="deferred")

        resp = _home(client_a)

        role_labels = resp.context["chart_roles_labels"]
        assert "broker" in role_labels
        assert None not in role_labels

        activity_labels = resp.context["chart_activity_labels"]
        assert "deferred" in activity_labels
        assert None not in activity_labels


# ------------------------------------------------------------------ Health metrics and audit feed
class TestDashboardHealthAndAudit:
    def test_latest_health_row_per_metric_wins_by_max_id(self, client_a, dash_health):
        """The ``Max("id")`` subquery must return the latest value per metric, not the first."""
        health = _home(client_a).context["health"]
        by_metric = {row.metric: row for row in health}
        assert len(health) == 2                      # storage_mb + users, one row each
        assert by_metric["users"].value == 99        # the later row, not 10
        assert by_metric["storage_mb"].value == 512

    def test_recent_audit_is_capped_at_eight_and_newest_first(self, client_a, dash_audit):
        recent = _home(client_a).context["recent_audit"]
        assert len(recent) == 8
        # tenant_a's 10 rows are the oldest-first slice [0..9]; the feed is [9..2].
        assert recent[0].pk == dash_audit["a"][9].pk
        assert recent[-1].pk == dash_audit["a"][2].pk
