"""Procurement 6.3 Approval Workflow Engine — view tests (queue/decisions/history)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.procurement.models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
    ProcurementAlert,
    RequisitionApproval,
)
from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine

pytestmark = pytest.mark.django_db


def _pending(tenant, requester, title="Pending", org=None, total="500",
             description="Safety goggles", created_at=None):
    pr = PurchaseRequisition.objects.create(
        tenant=tenant, title=title, status="pending_approval",
        requester=requester, org_unit=org, estimated_total=Decimal("0"))
    # qty MUST be 1: recalc_totals() sums qty*price, and a qty of 2 would double
    # every amount this suite reasons about (gotcha of record, 2026-08-25).
    PurchaseRequisitionLine.objects.create(
        requisition=pr, item_description=description,
        quantity=Decimal("1"), estimated_unit_price=Decimal(total))
    pr.recalc_totals(save=True)
    if created_at:
        PurchaseRequisition.objects.filter(pk=pr.pk).update(created_at=created_at)
    return pr


@pytest.fixture
def two_tier_rule(db, tenant_a):
    """Standard-amount commodity rule so a member may legally sign tier 1."""
    return ApprovalRoutingRule.objects.create(
        tenant=tenant_a, commodity="goggles", required_tiers=2)


def test_queue_lists_rows_and_stats(client_a, admin_user, requisition_pending_a):
    resp = client_a.get(reverse("procurement:approval_queue"))
    body = resp.content.decode()
    assert resp.status_code == 200 and requisition_pending_a.number in body
    assert "Pending chains" in body and "{#" not in body


def test_history_register_and_filter(client_a, tenant_a, admin_user,
                                     member_user, two_tier_rule):
    # Separation of duties (review F-01): the requester can never sign, so the
    # member raises the chain and the admin signs tier 1 of the two-tier rule.
    req = _pending(tenant_a, member_user)
    client_a.post(reverse("procurement:approval_approve", args=[req.pk]),
                  {"comment": "fine"})
    sig = RequisitionApproval.objects.get(requisition=req)
    resp = client_a.get(reverse("procurement:approval_history"))
    assert sig.comment in resp.content.decode()
    resp = client_a.get(reverse("procurement:approval_history") + "?decision=rejected")
    assert sig.number not in resp.content.decode()


def test_member_cannot_sign_own_or_final_tier(client_a, member_client, tenant_a,
                                              admin_user, member_user,
                                              two_tier_rule):
    own = _pending(tenant_a, member_user)  # single-tier: final AND own request
    resp = member_client.post(reverse("procurement:approval_approve",
                                      args=[own.pk]), {"comment": ""})
    assert resp.status_code in (302, 403)
    assert PurchaseRequisition.objects.get(pk=own.pk).status == "pending_approval"
    assert RequisitionApproval.objects.filter(requisition=own).count() == 0
    # The admin signs BOTH tiers of the two-tier commodity chain.
    resp = client_a.post(reverse("procurement:approval_approve", args=[own.pk]),
                         {"comment": "ok"})
    assert PurchaseRequisition.objects.get(pk=own.pk).status == "pending_approval"
    resp = client_a.post(reverse("procurement:approval_approve", args=[own.pk]),
                         {"comment": "final"})
    assert PurchaseRequisition.objects.get(pk=own.pk).status == "approved"


def test_two_tier_chain_with_delegation_credit(client_a, member_client, tenant_a,
                                               admin_user, member_user,
                                               two_tier_rule):
    req = _pending(tenant_a, admin_user)  # someone else's chain
    grant = ApprovalDelegation.objects.create(
        tenant=tenant_a, delegator=admin_user, delegate=member_user,
        valid_from=timezone.localdate(),
        valid_until=timezone.localdate() + timedelta(days=7))
    resp = member_client.post(reverse("procurement:approval_approve", args=[req.pk]),
                              {"comment": "covering"})
    assert resp.status_code in (302, 200)
    sig = RequisitionApproval.objects.get(requisition=req)
    assert sig.via_delegation_id == grant.pk and sig.tier == 1
    assert PurchaseRequisition.objects.get(pk=req.pk).status == "pending_approval"
    # The final tier is admin-only AND never the requester's (F-01/F-01b), so a
    # SECOND tenant admin performs the spine transition.
    final_admin = User.objects.create_user(
        email="admin2@acme.com", username="admin2_acme",
        password="TestPass123!", tenant=tenant_a, is_tenant_admin=True)
    final_client = Client()
    final_client.force_login(final_admin)
    final_client.post(reverse("procurement:approval_approve", args=[req.pk]),
                      {"comment": "final"})
    assert PurchaseRequisition.objects.get(pk=req.pk).status == "approved"
    # History shows both signatures; the closed chain refuses more.
    resp = member_client.post(reverse("procurement:approval_approve", args=[req.pk]),
                              {"comment": "again"}, follow=True)
    assert RequisitionApproval.objects.filter(requisition=req).count() == 2


def test_rejection_is_terminal_on_spine(client_a, tenant_a, admin_user, member_user,
                                        two_tier_rule):
    req = _pending(tenant_a, member_user)
    resp = client_a.post(reverse("procurement:approval_reject", args=[req.pk]),
                         {"comment": "no budget"})
    req.refresh_from_db()
    assert req.status == "rejected" and "no budget" in req.decision_note
    sig = RequisitionApproval.objects.get(requisition=req)
    assert sig.decision == "rejected"


def test_escalation_board_and_idempotent_run(client_a, member_client, tenant_a,
                                             admin_user, member_user):
    policy = EscalationPolicy.for_tenant(tenant_a)
    aged = _pending(tenant_a, member_user, title="Aged", total="20",
                    created_at=timezone.now() - timedelta(hours=policy.idle_hours + 5))
    assert client_a.get(reverse("procurement:escalation_queue")).status_code == 200
    resp = client_a.post(reverse("procurement:escalation_run"))
    assert resp.status_code in (302, 200)
    resp = client_a.post(reverse("procurement:escalation_run"))  # idempotent
    assert ProcurementAlert.objects.filter(
        tenant=tenant_a, kind="approval",
        link_url=f"/scm/requisitions/{aged.pk}/").count() == 1
    # Members cannot run escalations.
    assert member_client.post(reverse("procurement:escalation_run")
                              ).status_code in (302, 403)


def test_mine_surface_gates(client_a, member_client, tenant_a, admin_user,
                            member_user, two_tier_rule):
    own = _pending(tenant_a, member_user)          # own -> no buttons
    other = _pending(tenant_a, admin_user)         # intermediate tier -> buttons
    # A chain the commodity rule does NOT match resolves to the default ONE tier,
    # so its next signature IS the final one — the gate badge explains why a
    # member gets no button for it.
    final_other = _pending(tenant_a, admin_user, title="Final gate probe",
                           description="Lab consumables restock")
    body = member_client.get(reverse("procurement:approval_mine")).content.decode()
    assert own.title in body and other.title in body
    assert final_other.title in body
    assert "Final signature" in body  # gate badge explains why there is no button
