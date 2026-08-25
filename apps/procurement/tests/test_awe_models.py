"""Procurement 6.3 Approval Workflow Engine — model tests."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.procurement.models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
    RequisitionApproval,
    escalation_candidates,
    resolve_routing,
    run_escalations,
)
from apps.scm.models import PurchaseRequisition

pytestmark = pytest.mark.django_db


def _rule(tenant, **overrides):
    fields = dict(tenant=tenant, required_tiers=1)
    fields.update(overrides)
    return ApprovalRoutingRule.objects.create(**fields)


def _pending(tenant, requester, title="Pending", org=None, total="500"):
    from apps.scm.models import PurchaseRequisitionLine

    pr = PurchaseRequisition.objects.create(
        tenant=tenant, title=title, status="pending_approval",
        requester=requester, org_unit=org, estimated_total=Decimal("0"))
    PurchaseRequisitionLine.objects.create(
        requisition=pr, item_description="Safety goggles",
        quantity=Decimal("2"), estimated_unit_price=Decimal(total))
    pr.recalc_totals(save=True)
    return pr


def test_rule_str_specificity_and_band_label(tenant_a, org_unit_a):
    rule = _rule(tenant_a, org_unit=org_unit_a, commodity="safety",
                 min_total=Decimal("100"), max_total=Decimal("1000"))
    assert rule.specificity == 3
    assert rule.band_label == "[100 – 1,000)"
    assert "safety" in str(rule)


def test_resolve_ladder_most_specific_wins(tenant_a, admin_user, org_unit_a):
    req = _pending(tenant_a, admin_user, org=org_unit_a, total="20000")
    catch_all = _rule(tenant_a, max_total=Decimal("100000"))
    dept_rule = _rule(tenant_a, org_unit=org_unit_a,
                      min_total=Decimal("10000"), required_tiers=2)
    commodity = _rule(tenant_a, commodity="goggles", required_tiers=3)
    # Department pin (2) beats commodity keyword (1) beats catch-all (0).
    winner, reason = resolve_routing(req)
    assert winner.pk == dept_rule.pk and winner.required_tiers == 2
    assert "fires" in reason
    # Among EQUAL specificity the narrower band wins.
    narrow = _rule(tenant_a, org_unit=org_unit_a,
                   min_total=Decimal("15000"), max_total=Decimal("25000"),
                   required_tiers=4)
    winner, _ = resolve_routing(req)
    assert winner.pk == narrow.pk
    # The commodity rule answers when nothing more specific matches.
    commodity = ApprovalRoutingRule.objects.get(pk=commodity.pk)
    commodity.org_unit = None
    commodity.min_total = None
    commodity.max_total = None
    commodity.save()
    plain = _pending(tenant_a, admin_user, title="Other", total="50")
    winner2, _ = resolve_routing(plain)
    assert winner2.pk == commodity.pk


def test_band_edges_half_open(tenant_a, admin_user):
    req = _pending(tenant_a, admin_user, title="Edge", total="1000")
    lo = _rule(tenant_a, min_total=Decimal("1000"), max_total=Decimal("2000"))
    hi_excl = _rule(tenant_a, min_total=Decimal("500"), max_total=Decimal("1000"))
    winner, _ = resolve_routing(req)
    assert winner.pk == lo.pk  # floor inclusive; ceiling exclusive


def test_no_match_means_one_default_tier(tenant_a, admin_user):
    req = _pending(tenant_a, admin_user, title="Unmatched", total="999999")
    _rule(tenant_a, max_total=Decimal("100"))
    rule, reason = resolve_routing(req)
    assert rule is None and "default" in reason.lower()


def test_signature_record_and_uniqueness(tenant_a, admin_user):
    req = _pending(tenant_a, admin_user)
    sig = RequisitionApproval.record(
        tenant_a, req, tier=1, tier_count=2, decision="approved",
        approver=admin_user, comment="ok")
    assert sig.number.startswith("RQA-") and not sig.is_final_tier
    with pytest.raises(Exception):
        RequisitionApproval.objects.create(
            tenant=tenant_a, requisition=req, tier=1, tier_count=2,
            decision="approved")


def test_delegation_clean_rules(tenant_a, member_user, admin_user):
    ok_fields = dict(tenant=tenant_a, delegator=admin_user, delegate=member_user,
                     valid_from=timezone.localdate(),
                     valid_until=timezone.localdate() + timedelta(days=7))
    with pytest.raises(ValidationError):
        ApprovalDelegation(**{**ok_fields, "delegate": admin_user}).full_clean()
    with pytest.raises(ValidationError):
        ApprovalDelegation(**{
            **ok_fields,
            "valid_until": timezone.localdate() - timedelta(days=1)}).full_clean()
    grant = ApprovalDelegation(**ok_fields)
    grant.full_clean()
    grant.save()
    assert grant.is_current


def test_active_for_is_delegate_directed_and_scoped(tenant_a, member_user,
                                                    admin_user, org_unit_a, org_unit_b):
    scoped = ApprovalDelegation.objects.create(
        tenant=tenant_a, delegator=admin_user, delegate=member_user,
        scope_org_unit=org_unit_a, valid_from=timezone.localdate(),
        valid_until=timezone.localdate() + timedelta(days=7))
    unscoped = ApprovalDelegation.objects.create(
        tenant=tenant_a, delegator=admin_user, delegate=member_user,
        valid_from=timezone.localdate(),
        valid_until=timezone.localdate() + timedelta(days=7))
    # Exact-scope beats unscoped inside the department...
    hit = ApprovalDelegation.active_for(tenant_a, member_user, org_unit_id=org_unit_a.pk)
    assert hit.pk == scoped.pk
    # ...the unscoped one answers elsewhere...
    hit = ApprovalDelegation.active_for(tenant_a, member_user, org_unit_id=org_unit_b.pk)
    assert hit.pk == unscoped.pk
    # ...and authority flows TO the delegate, never FROM them.
    assert ApprovalDelegation.active_for(tenant_a, admin_user) is None


def test_policy_singleton_and_escalation_engine(tenant_a, admin_user, member_user):
    policy = EscalationPolicy.for_tenant(tenant_a)
    assert EscalationPolicy.for_tenant(tenant_a).pk == policy.pk

    aged = _pending(tenant_a, member_user, title="Aged", total="20")
    fresh = _pending(tenant_a, member_user, title="Fresh", total="20")
    past = timezone.now() - timedelta(hours=policy.idle_hours + 5)
    PurchaseRequisition.objects.filter(pk=aged.pk).update(created_at=past)

    rows = {r["requisition"].pk: r for r in escalation_candidates(tenant_a, policy)}
    assert rows[aged.pk]["is_idle"] and not rows[fresh.pk]["is_idle"]
    assert not rows[aged.pk]["escalated"]

    summary = run_escalations(tenant_a, admin_user, policy)
    assert summary["raised"] == 1
    again = run_escalations(tenant_a, admin_user, policy)
    assert again["raised"] == 0 and again["skipped_open"] >= 1


def test_zero_hours_rule_escalates_immediately(tenant_a, admin_user, member_user):
    policy = EscalationPolicy.for_tenant(tenant_a)
    req = _pending(tenant_a, member_user, title="Zero window", total="20")
    _rule(tenant_a, commodity="goggles", escalation_hours=0)
    rows = escalation_candidates(tenant_a, policy)
    row = next(r for r in rows if r["requisition"].pk == req.pk)
    assert row["idle_hours_effective"] == 0 and row["is_idle"]
