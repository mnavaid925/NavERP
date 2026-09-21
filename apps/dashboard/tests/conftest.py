"""Dashboard app test fixtures.

``apps/dashboard`` owns no models and no forms — its single view, ``home``, is a
tenant-scoped aggregation over six tables owned by ``core`` and ``tenants``. So this
file creates no dashboard records; it seeds rows in *other* apps' tables, in **both**
tenants, so the isolation tests have something real to exclude.

It builds on the root ``conftest.py`` baseline (probed 2026-09-21 with
``temp/probe_dashboard_baseline.py``): ``tenant_a`` ships with **2 active users and
nothing else**; ``tenant_b`` ships with nothing at all. Every figure the lanes assert
is therefore a number this file created — which is why the expected values are exact
rather than "greater than zero".

Determinism note — two of the six aggregates order by a column Django fills in for us
(``Subscription.created_at`` and ``AuditLog.at``, both ``auto_now_add``). Two rows
created inside one test can carry the same timestamp, which would make
``order_by("-created_at").first()`` non-deterministic. ``.update()`` bypasses an auto
field, so the fixtures below pin those timestamps explicitly rather than hoping the
clock ticks between two ``create()`` calls.
"""
import datetime

import pytest
from django.utils import timezone


def _pin(model, pk, when):
    """Force ``created_at`` on an ``auto_now_add`` column — ``.update()`` bypasses it."""
    model.objects.filter(pk=pk).update(created_at=when)


# ------------------------------------------------------------------ Parties
@pytest.fixture
def dash_parties(db, tenant_a, tenant_b):
    """3 parties for tenant_a, 2 for tenant_b — ``parties_count`` must be 3, never 5."""
    from apps.core.models import Party
    return {
        "a": [Party.objects.create(tenant=tenant_a, name=f"Acme Party {i}") for i in (1, 2, 3)],
        "b": [Party.objects.create(tenant=tenant_b, name=f"Globex Party {i}") for i in (1, 2)],
    }


# ------------------------------------------------------------------ Party roles
@pytest.fixture
def dash_party_roles(db, tenant_a, tenant_b, dash_parties):
    """tenant_a: 2x customer, 1x supplier. tenant_b: 1x customer.

    ``PartyRole`` is unique on ``(party, role)``, so each role goes on its own party.
    The grouped chart therefore has two rows with counts 2 and 1 — a genuine ordering
    rather than a tie.
    """
    from apps.core.models import PartyRole
    a1, a2, a3 = dash_parties["a"]
    return [
        PartyRole.objects.create(tenant=tenant_a, party=a1, role="customer"),
        PartyRole.objects.create(tenant=tenant_a, party=a2, role="customer"),
        PartyRole.objects.create(tenant=tenant_a, party=a3, role="supplier"),
        PartyRole.objects.create(tenant=tenant_b, party=dash_parties["b"][0], role="customer"),
    ]


# ------------------------------------------------------------------ Activities
@pytest.fixture
def dash_activities(db, tenant_a, tenant_b):
    """tenant_a: 2x open, 1x done. tenant_b: 1x open — the activity chart sums to 3."""
    from apps.core.models import Activity
    return {
        "a": [
            Activity.objects.create(tenant=tenant_a, subject="Acme open 1", status="open"),
            Activity.objects.create(tenant=tenant_a, subject="Acme open 2", status="open"),
            Activity.objects.create(tenant=tenant_a, subject="Acme done 1", status="done"),
        ],
        "b": [Activity.objects.create(tenant=tenant_b, subject="Globex open 1", status="open")],
    }


# ------------------------------------------------------------------ Health metrics
@pytest.fixture
def dash_health(db, tenant_a, tenant_b):
    """tenant_a: metric ``users`` twice (10 then 99) plus ``storage_mb`` once.

    This is the ``Max("id")`` subquery's entire purpose: the view must show the
    **latest** value per metric, so 99 must win over 10. Ids are autoincrement, so
    ``newer`` is guaranteed a higher pk than ``older``.
    """
    from apps.tenants.models import HealthMetric
    older = HealthMetric.objects.create(tenant=tenant_a, metric="users", value=10)
    newer = HealthMetric.objects.create(tenant=tenant_a, metric="users", value=99)
    storage = HealthMetric.objects.create(tenant=tenant_a, metric="storage_mb", value=512)
    return {
        "a": [older, newer, storage],
        "b": [HealthMetric.objects.create(tenant=tenant_b, metric="users", value=7)],
        "older": older,
        "newer": newer,
        "storage": storage,
    }


# ------------------------------------------------------------------ Audit log
@pytest.fixture
def dash_audit(db, tenant_a, tenant_b):
    """tenant_a: 10 rows. tenant_b: 3 rows, **all newer** than tenant_a's.

    ``recent_audit`` is capped at 8. Making tenant_b's rows the newest ones means a
    leaked ``tenant`` filter would change both the length and ``[0]`` — the isolation
    test can actually see the defect instead of passing by coincidence.
    """
    from apps.core.models import AuditLog
    a_base = timezone.now() - datetime.timedelta(hours=2)
    b_base = timezone.now() - datetime.timedelta(hours=1)

    def _make(tenant, prefix, base, count):
        rows = []
        for i in range(count):
            row = AuditLog.objects.create(tenant=tenant, action="create", target=f"{prefix}-{i}")
            AuditLog.objects.filter(pk=row.pk).update(at=base + datetime.timedelta(minutes=i))
            row.refresh_from_db()
            rows.append(row)
        return rows

    return {
        "a": _make(tenant_a, "acme", a_base, 10),
        "b": _make(tenant_b, "globex", b_base, 3),
    }


# ------------------------------------------------------------------ Subscriptions
@pytest.fixture
def dash_subscription(db, tenant_a, tenant_b):
    """tenant_a: two subscriptions with pinned, distinct ``created_at`` values.

    ``stats["subscription"]`` must be the **newest** — the older one is pinned 30 days
    back so the assertion cannot depend on clock resolution.
    """
    from apps.tenants.models import Subscription
    older = Subscription.objects.create(tenant=tenant_a, plan="starter", status="trialing")
    _pin(Subscription, older.pk, timezone.now() - datetime.timedelta(days=30))
    older.refresh_from_db()

    newer = Subscription.objects.create(tenant=tenant_a, plan="pro", status="active")
    _pin(Subscription, newer.pk, timezone.now() - datetime.timedelta(days=1))
    newer.refresh_from_db()

    return {
        "a": [older, newer],
        "b": Subscription.objects.create(tenant=tenant_b, plan="starter", status="active"),
        "older": older,
        "newer": newer,
    }


# ------------------------------------------------------------------ Subscription invoices
@pytest.fixture
def dash_invoices(db, tenant_a, tenant_b, dash_subscription):
    """tenant_a: 2 open + 1 paid. tenant_b: 1 open — ``open_invoices`` must be 2."""
    from apps.tenants.models import SubscriptionInvoice
    return {
        "a": [
            SubscriptionInvoice.objects.create(
                tenant=tenant_a, subscription=dash_subscription["newer"], status="open", amount="29.99"
            ),
            SubscriptionInvoice.objects.create(
                tenant=tenant_a, subscription=dash_subscription["newer"], status="open", amount="29.99"
            ),
            SubscriptionInvoice.objects.create(
                tenant=tenant_a, subscription=dash_subscription["older"], status="paid", amount="29.99"
            ),
        ],
        "b": [
            SubscriptionInvoice.objects.create(
                tenant=tenant_b, subscription=dash_subscription["b"], status="open", amount="9.99"
            )
        ],
    }
