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


# ------------------------------------------------------------------ 6.2 Requisition Management
from decimal import Decimal  # noqa: E402


def _pr(tenant, requester, status="draft", title="Test requisition", **overrides):
    from apps.scm.models import PurchaseRequisition

    fields = dict(
        tenant=tenant, title=title, requester=requester,
        required_by=datetime.date.today() + datetime.timedelta(days=10),
        status=status,
        justification="Needed for the smoke-free quarter.",
    )
    fields.update(overrides)
    return PurchaseRequisition.objects.create(**fields)


def _pr_line(pr, description="A4 printer paper", qty="4", price="22.50", **overrides):
    from apps.scm.models import PurchaseRequisitionLine

    fields = dict(
        requisition=pr, item_description=description,
        quantity=Decimal(qty), estimated_unit_price=Decimal(price),
    )
    fields.update(overrides)
    return PurchaseRequisitionLine.objects.create(**fields)


@pytest.fixture
def requisition_approved_a(db, tenant_a, admin_user, gl_expense_a):
    """An APPROVED spine requisition (amendable) with two lines."""
    pr = _pr(tenant_a, admin_user, status="approved",
             title="Quarterly office supplies")
    pr.approved_by = admin_user
    pr.save()
    _pr_line(pr, "A4 printer paper", "4", "22.50")
    _pr_line(pr, "Ballpoint pens blue", "2", "6.80")
    pr.recalc_totals()
    return pr


@pytest.fixture
def requisition_pending_a(db, tenant_a, admin_user):
    """A PENDING-approval spine requisition (also amendable) with one line."""
    pr = _pr(tenant_a, admin_user, status="pending_approval",
             title="Lab consumables restock")
    _pr_line(pr, "Nitrile gloves medium", "10", "8.40")
    pr.recalc_totals()
    return pr


@pytest.fixture
def template_with_lines_a(db, tenant_a, org_unit_a, gl_expense_a, admin_user):
    from apps.procurement.models import RequisitionTemplate, RequisitionTemplateLine

    template = RequisitionTemplate.objects.create(
        tenant=tenant_a, name="Monthly office supplies",
        description="Standing monthly order.", org_unit=org_unit_a,
        default_lead_days=7, justification="Recurring consumables.",
        created_by=admin_user,
    )
    RequisitionTemplateLine.objects.create(
        template=template, item_description="A4 printer paper",
        quantity=Decimal("4"), estimated_unit_price=Decimal("22.50"),
        gl_account=gl_expense_a)
    RequisitionTemplateLine.objects.create(
        template=template, item_description="Sticky notes assorted",
        quantity=Decimal("3"), estimated_unit_price=Decimal("4.20"))
    return template


@pytest.fixture
def amendment_pending_a(db, tenant_a, admin_user, requisition_approved_a):
    from apps.procurement.models import RequisitionAmendment

    return RequisitionAmendment.objects.create(
        tenant=tenant_a,
        requisition=requisition_approved_a,
        amendment_type="amend", status="pending",
        requested_by=admin_user,
        reason="Vendor moved the dispatch date.",
        new_required_by=datetime.date.today() + datetime.timedelta(days=17),
    )
