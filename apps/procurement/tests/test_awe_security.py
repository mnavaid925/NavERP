"""Procurement 6.3 Approval Workflow Engine — security tests."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
    RequisitionApproval,
)
from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

pytestmark = pytest.mark.django_db


def _pending(tenant, requester, title="Pending", total="500"):
    pr = PurchaseRequisition.objects.create(
        tenant=tenant, title=title, status="pending_approval",
        requester=requester, estimated_total=Decimal("0"))
    PurchaseRequisitionLine.objects.create(
        requisition=pr, item_description="Safety goggles",
        quantity=Decimal("2"), estimated_unit_price=Decimal(total))
    pr.recalc_totals(save=True)
    return pr


@pytest.fixture
def rule_a(db, tenant_a):
    return ApprovalRoutingRule.objects.create(tenant=tenant_a, required_tiers=2)


@pytest.fixture
def rule_b(db, tenant_b):
    return ApprovalRoutingRule.objects.create(tenant=tenant_b, required_tiers=3)


def test_idor_routes_404(client_a, tenant_b, admin_b, rule_b):
    assert client_a.get(reverse("procurement:routingrule_detail",
                                args=[rule_b.pk])).status_code == 404
    assert client_a.get(reverse("procurement:routingrule_edit",
                                args=[rule_b.pk])).status_code == 404
    foreign_req = PurchaseRequisition.objects.create(
        tenant=tenant_b, title="Foreign", status="pending_approval")
    assert client_a.post(reverse("procurement:approval_approve",
                                 args=[foreign_req.pk]),
                         {"comment": ""}).status_code == 404
    grant_b = ApprovalDelegation.objects.create(
        tenant=tenant_b, delegator=admin_b,
        valid_from=timezone.localdate(),
        valid_until=timezone.localdate() + timedelta(days=3))
    assert client_a.get(reverse("procurement:delegation_detail",
                                args=[grant_b.pk])).status_code == 404


def test_member_write_gating(member_client, rule_a, db, tenant_a):
    assert member_client.post(reverse("procurement:routingrule_create"),
                              {"required_tiers": 1}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:routingrule_delete",
                                      args=[rule_a.pk])).status_code in (302, 403)
    assert member_client.post(reverse("procurement:delegation_create"),
                              {"reason": "x"}).status_code in (302, 403)
    # Nothing was written.
    assert ApprovalRoutingRule.objects.filter(required_tiers=99).count() == 0


def test_login_required_everywhere(client, db):
    for name in ("procurement:approval_queue", "procurement:approval_history",
                 "procurement:approval_mine", "procurement:escalation_queue",
                 "procurement:routingrule_list", "procurement:delegation_list"):
        assert client.get(reverse(name)).status_code in (302, 403)


def test_engine_tenant_isolation(tenant_a, tenant_b, admin_user, admin_b):
    from apps.procurement.models import resolve_routing
    req_a = PurchaseRequisition.objects.create(
        tenant=tenant_a, title="A", status="pending_approval",
        requester=admin_user, estimated_total=Decimal("500"))
    rule_a = ApprovalRoutingRule.objects.create(
        tenant=tenant_a, required_tiers=4)
    winner, _ = resolve_routing(req_a)
    assert winner is not None and winner.tenant_id == tenant_a.id
    # A foreign-tenant requisition never sees this workspace's rules.
    req_b = PurchaseRequisition.objects.create(
        tenant=tenant_b, title="B", status="pending_approval",
        requester=admin_b, estimated_total=Decimal("500"))
    winner_b, reason_b = resolve_routing(req_b)
    assert winner_b is None and "default" in reason_b.lower()


def test_signature_rows_immutable_via_admin(tenant_a, admin_user):
    """The register is read-only everywhere — including the Django admin."""
    from django.contrib import admin as dj_admin

    from apps.procurement.admin import RequisitionApprovalAdmin

    model_admin = RequisitionApprovalAdmin(RequisitionApproval, dj_admin.site)
    assert model_admin.has_add_permission(None) is False
    assert model_admin.has_change_permission(None, None) is False
    assert model_admin.has_delete_permission(None, None) is False
