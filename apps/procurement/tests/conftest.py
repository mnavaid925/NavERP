"""Procurement app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b, client_a,
client_b, member_user, member_client) and adds the 6.1 User Dashboard & Portal records:
ProcurementAlert rows across every lifecycle state plus the accounting masters the quick
requisition form scopes against.
"""
import datetime

import pytest

from django.utils import timezone


# ------------------------------------------------------------------ accounting masters
@pytest.fixture
def usd(db):
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(code="USD",
                                            defaults={"name": "US Dollar", "symbol": "$"})
    return obj


@pytest.fixture
def gl_expense_a(db, tenant_a):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="5000", name="Office Supplies Expense",
        account_type="expense")


@pytest.fixture
def gl_expense_b(db, tenant_b):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_b, code="5000", name="Globex Expense", account_type="expense")


@pytest.fixture
def org_unit_a(db, tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Acme Facilities", kind="department")


@pytest.fixture
def org_unit_b(db, tenant_b):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_b, name="Globex Facilities", kind="department")


# ------------------------------------------------------------------ alerts
def _alert(tenant, **overrides):
    from apps.procurement.models import ProcurementAlert
    fields = dict(
        tenant=tenant,
        kind="deadline", severity="critical", status="open",
        title="Printer paper reorder window closes",
        message="Submit before the supplier cut-off.",
        link_url="/procurement/quick-requisition/",
        due_at=timezone.now() + datetime.timedelta(days=2),
    )
    fields.update(overrides)
    return ProcurementAlert.objects.create(**fields)


@pytest.fixture
def alert_open(db, tenant_a, admin_user):
    return _alert(tenant_a, assigned_to=admin_user)


@pytest.fixture
def alert_acknowledged(db, tenant_a, admin_user):
    return _alert(tenant_a, assigned_to=admin_user, status="acknowledged",
                  severity="warning", kind="approval",
                  acknowledged_at=timezone.now())


@pytest.fixture
def alert_resolved(db, tenant_a):
    return _alert(tenant_a, status="resolved", severity="info", kind="task",
                  title="Quarterly stocktake closed out",
                  resolved_at=timezone.now(), resolution_note="Approved after quote arrived.")


@pytest.fixture
def alert_unassigned(db, tenant_a):
    """No assignee AND no due date - the 'team inbox' row that must not crowd dated ones."""
    return _alert(tenant_a, severity="info", kind="delivery", due_at=None)


@pytest.fixture
def alert_overdue(db, tenant_a, admin_user):
    return _alert(tenant_a, assigned_to=admin_user,
                  due_at=timezone.now() - datetime.timedelta(days=1))


@pytest.fixture
def alert_b(db, tenant_b, admin_b):
    return _alert(tenant_b, assigned_to=admin_b, title="Globex only alert")
