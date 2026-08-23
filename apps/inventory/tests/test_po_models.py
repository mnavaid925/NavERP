"""Inventory 5.3 — model invariants around SCM 4.1's purchase-order spine.

The management layer adds three entities AROUND the PO document: routing RULES whose bands
are half-open (``min <= total < max``) and resolved most-specific-wins, the per-tier
approval CHAIN whose count honestly resets after a rejection, and the DISPATCH log whose
addressed channels cannot go out without a recipient. Nothing here touches stock or GL.

Spine orders are built directly through the ORM below rather than via the shared conftest's
PO fixtures, whose ``_make_po`` helper currently raises ``NameError`` (missing datetime
import) — see the report note accompanying this suite.
"""
import datetime
import re
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    PurchaseOrderApproval,
    PurchaseOrderApprovalRule,
    PurchaseOrderDispatch,
)

pytestmark = pytest.mark.django_db


def _po(tenant, vendor):
    """A bare spine purchase order built directly through the ORM."""
    from apps.scm.models import PurchaseOrder
    return PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor, order_date=datetime.date(2026, 8, 20))


def _line_po(tenant, vendor, status, quantity, unit_price):
    """A spine PO carrying one line; totals derived via recalc_totals()."""
    from apps.scm.models import PurchaseOrderLine
    po = _po(tenant, vendor)
    po.status = status
    po.save(update_fields=["status", "updated_at"])
    PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Probe rig", sku_hint="PRB-1",
        quantity=Decimal(quantity), unit_price=Decimal(unit_price))
    po.recalc_totals()
    return po


def _approval(tenant, po, rule=None, tier=1, decision="approved", user=None):
    """One sequential sign-off written the way the decide action writes it."""
    from django.utils import timezone

    return PurchaseOrderApproval.objects.create(
        tenant=tenant, purchase_order=po, rule=rule, tier=tier,
        decision=decision, decided_by=user, decided_at=timezone.now())


def _dispatch(tenant, po, channel="email", recipient="buyer@acme.example"):
    """One recorded transmission of an order."""
    from django.utils import timezone

    return PurchaseOrderDispatch.objects.create(
        tenant=tenant, purchase_order=po, channel=channel, recipient=recipient,
        dispatched_at=timezone.now())


# ------------------------------------------------------------------ rule resolution


class TestPurchaseOrderApprovalRuleResolve:
    def test_min_inclusive_capital_edge_at_100k(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        found = PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("100000.00"))
        assert found.pk == approval_rule_cap_a.pk  # min bound is INCLUSIVE
        assert found.tier_count == 3

    def test_max_exclusive_10k_boundary_leaves_the_band(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        inside = PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("9999.99"))
        assert inside.pk == approval_rule_std_a.pk
        # The upper bound is EXCLUSIVE: exactly 10,000 matches NEITHER rule (the gap).
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("10000.00")) is None

    def test_gap_between_bands_answers_none(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("99999.99")) is None

    def test_org_scoped_rule_wins_only_for_matching_unit(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        from apps.core.models import OrgUnit
        engineering = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Engineering")
        sales = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Sales")
        scoped = PurchaseOrderApprovalRule.objects.create(
            tenant=tenant_a, name="Engineering purchases",
            min_amount=Decimal("5000"), max_amount=Decimal("20000"),
            org_unit=engineering, tier_count=2)
        # Matching unit: the scoped rule beats the overlapping generic one.
        assert PurchaseOrderApprovalRule.resolve(
            tenant_a, Decimal("8000"), org_unit_id=engineering.pk).pk == scoped.pk
        # Below the scoped band the generic rule answers again.
        assert PurchaseOrderApprovalRule.resolve(
            tenant_a, Decimal("2500"), org_unit_id=engineering.pk).pk == approval_rule_std_a.pk
        # Any other unit (or none): the scoped rule never hijacks the answer.
        assert PurchaseOrderApprovalRule.resolve(
            tenant_a, Decimal("8000"), org_unit_id=sales.pk).pk == approval_rule_std_a.pk
        assert PurchaseOrderApprovalRule.resolve(
            tenant_a, Decimal("8000")).pk == approval_rule_std_a.pk

    def test_narrowest_unscoped_band_wins(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        small = PurchaseOrderApprovalRule.objects.create(
            tenant=tenant_a, name="Small buys",
            min_amount=Decimal("0"), max_amount=Decimal("5000"), tier_count=1)
        # Both unscoped rules cover 2,500 — the narrower band takes it.
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("2500")).pk == small.pk
        # Outside the narrow band the wider standard rule covers again.
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("7000")).pk == approval_rule_std_a.pk

    def test_inactive_rules_are_ignored(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        approval_rule_std_a.is_active = False
        approval_rule_std_a.save()
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("2500")) is None
        # An inactive NARROWER rule cannot steal coverage back from an active one either.
        approval_rule_std_a.is_active = True
        approval_rule_std_a.save()
        PurchaseOrderApprovalRule.objects.create(
            tenant=tenant_a, name="Micro buys", is_active=False,
            min_amount=Decimal("0"), max_amount=Decimal("200"), tier_count=1)
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("100")).pk == approval_rule_std_a.pk


class TestPurchaseOrderApprovalRuleResolveFrom:
    def test_pre_fetched_list_agrees_with_querying_resolve(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        snapshot = list(PurchaseOrderApprovalRule.objects.filter(tenant=tenant_a, is_active=True))
        probes = [
            (Decimal("2500"), None),
            (Decimal("7000"), None),
            (Decimal("99999.99"), None),
            (Decimal("250000"), None),
        ]
        for total, unit_id in probes:
            from_list = PurchaseOrderApprovalRule.resolve_from(snapshot, total, unit_id)
            from_query = PurchaseOrderApprovalRule.resolve(tenant_a, total, unit_id)
            # Both sides may honestly answer None (a gap between bands).
            assert (from_list.pk if from_list else None) \
                == (from_query.pk if from_query else None)

    def test_snapshot_list_is_used_verbatim_without_querying(self, tenant_a, approval_rule_std_a, approval_rule_cap_a):
        """A list taken BEFORE a new matching row exists keeps answering the old way."""
        snapshot = list(PurchaseOrderApprovalRule.objects.filter(tenant=tenant_a, is_active=True))
        late = PurchaseOrderApprovalRule.objects.create(
            tenant=tenant_a, name="Late arrival",
            min_amount=Decimal("0"), max_amount=Decimal("900"), tier_count=1)
        # The stale iterable cannot see the new row...
        assert PurchaseOrderApprovalRule.resolve_from(snapshot, Decimal("500")).pk \
            == approval_rule_std_a.pk
        # ...while a live query resolves the narrower newcomer instead.
        assert PurchaseOrderApprovalRule.resolve(tenant_a, Decimal("500")).pk == late.pk


# ------------------------------------------------------------------ rule validation


class TestPurchaseOrderApprovalRuleClean:
    def test_upper_bound_must_exceed_lower_bound(self, tenant_a):
        for lo, hi in ((Decimal("10000"), Decimal("10000")), (Decimal("50"), Decimal("49"))):
            row = PurchaseOrderApprovalRule(
                tenant=tenant_a, name="Broken band", min_amount=lo, max_amount=hi)
            with pytest.raises(ValidationError) as err:
                row.full_clean()
            assert "max_amount" in err.value.message_dict


# ------------------------------------------------------------------ approval chain


class TestPurchaseOrderApprovalClearedTiers:
    def test_no_decisions_means_zero(self, tenant_a, vendor_party_a):
        po = _line_po(tenant_a, vendor_party_a, "pending_approval", "5", "50000.00")
        assert PurchaseOrderApproval.cleared_tier_count([]) == 0
        assert PurchaseOrderApproval.cleared_tier_count(
            po.inventory_approvals.all()) == 0

    def test_sequential_approvals_accumulate(self, tenant_a, vendor_party_a):
        po = _line_po(tenant_a, vendor_party_a, "pending_approval", "5", "50000.00")
        _approval(tenant_a, po, tier=1)
        assert PurchaseOrderApproval.cleared_tier_count(
            po.inventory_approvals.all()) == 1
        _approval(tenant_a, po, tier=2)
        assert PurchaseOrderApproval.cleared_tier_count(
            po.inventory_approvals.all()) == 2

    def test_rejection_resets_then_later_approvals_rebuild(self, tenant_a, vendor_party_a):
        po = _line_po(tenant_a, vendor_party_a, "pending_approval", "5", "50000.00")
        _approval(tenant_a, po, tier=1)
        _approval(tenant_a, po, tier=2, decision="rejected")
        # A fresh queryset each time — a cached one would replay a stale chain.
        assert PurchaseOrderApproval.cleared_tier_count(
            po.inventory_approvals.all()) == 0  # history kept, progress reset
        _approval(tenant_a, po, tier=3)
        _approval(tenant_a, po, tier=4)
        assert PurchaseOrderApproval.cleared_tier_count(
            po.inventory_approvals.all()) == 2

    def test_bare_decision_strings_are_accepted(self):
        count = PurchaseOrderApproval.cleared_tier_count
        assert count(["approved"]) == 1
        assert count(["approved", "approved"]) == 2
        assert count(["approved", "rejected"]) == 0
        assert count(["rejected", "approved"]) == 1


class TestPoNumbering:
    def test_pa_prefix_sequence_restarts_per_tenant(self, tenant_a, tenant_b, vendor_party_a, vendor_party_b):
        po_a1, po_b = _po(tenant_a, vendor_party_a), _po(tenant_b, vendor_party_b)
        first = _approval(tenant_a, po_a1, tier=1)
        second = _approval(tenant_a, po_a1, tier=2)
        theirs = _approval(tenant_b, po_b, tier=1)
        assert re.fullmatch(r"PA-\d{5}", first.number)
        assert second.number == "PA-00002"
        assert theirs.number == "PA-00001"  # workspaces never share a sequence

    def test_pd_prefix_sequence_restarts_per_tenant(self, tenant_a, tenant_b, vendor_party_a, vendor_party_b):
        sent_po = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        first = _dispatch(tenant_a, sent_po)
        second = _dispatch(tenant_a, sent_po, channel="print", recipient="")
        theirs = _dispatch(tenant_b, _po(tenant_b, vendor_party_b),
                           channel="edi", recipient="PARTNER-1")
        assert re.fullmatch(r"PD-\d{5}", first.number)
        assert second.number == "PD-00002"
        assert theirs.number == "PD-00001"


# ------------------------------------------------------------------ dispatch validation


class TestPurchaseOrderDispatchClean:
    def test_email_dispatch_demands_recipient(self, tenant_a, vendor_party_a):
        sent_po = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        row = PurchaseOrderDispatch(
            tenant=tenant_a, purchase_order=sent_po, channel="email", recipient="")
        with pytest.raises(ValidationError) as err:
            row.clean()
        assert "recipient" in err.value.message_dict

    def test_whitespace_recipient_fails_edi_too(self, tenant_a, vendor_party_a):
        sent_po = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        row = PurchaseOrderDispatch(
            tenant=tenant_a, purchase_order=sent_po, channel="edi", recipient="   ")
        with pytest.raises(ValidationError) as err:
            row.clean()
        assert "recipient" in err.value.message_dict

    def test_print_channel_may_have_blank_recipient(self, tenant_a, vendor_party_a):
        sent_po = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        row = PurchaseOrderDispatch(
            tenant=tenant_a, purchase_order=sent_po, channel="print", recipient="")
        row.clean()  # must not raise — print/PDF has no address to fill in
        row.save()
        row.refresh_from_db()
        assert row.recipient == ""

    def test_dispatch_of_another_workspaces_order_is_rejected(self, tenant_a, tenant_b, vendor_party_a, vendor_party_b):
        sent_po = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        row = _dispatch(tenant_a, sent_po)
        row.purchase_order = _po(tenant_b, vendor_party_b)  # foreign workspace's order
        with pytest.raises(ValidationError) as err:
            row.clean()
        assert "purchase_order" in err.value.message_dict


# ------------------------------------------------------------------ badge css maps


class TestPoBadgeCssMaps:
    def test_channel_css_colours_every_choice_and_mutes_unknown(self):
        expected = {"email": "badge-info", "edi": "badge-green", "print": "badge-slate"}
        for channel, colour in expected.items():
            assert PurchaseOrderDispatch(channel=channel).channel_css == colour
        assert PurchaseOrderDispatch(channel="carrier_pigeon").channel_css == "badge-muted"

    def test_decision_css_colours_every_choice_and_mutes_unknown(self):
        assert PurchaseOrderApproval(decision="approved").decision_css == "badge-green"
        assert PurchaseOrderApproval(decision="rejected").decision_css == "badge-red"
        assert PurchaseOrderApproval(decision="abstain").decision_css == "badge-muted"


# ------------------------------------------------------------------ fk lifecycle


class TestPoForeignKeysLifecycle:
    def test_deleting_the_spine_removes_decisions_and_dispatches(self, tenant_a, vendor_party_a):
        big = _line_po(tenant_a, vendor_party_a, "pending_approval", "5", "50000.00")
        decision = _approval(tenant_a, big, tier=1)
        small = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        transmission = _dispatch(tenant_a, small)
        decision_pk, dispatch_pk = decision.pk, transmission.pk
        big.delete()
        small.delete()
        with pytest.raises(PurchaseOrderApproval.DoesNotExist):
            decision.refresh_from_db()
        with pytest.raises(PurchaseOrderDispatch.DoesNotExist):
            transmission.refresh_from_db()
        assert not PurchaseOrderApproval.objects.filter(pk=decision_pk).exists()
        assert not PurchaseOrderDispatch.objects.filter(pk=dispatch_pk).exists()

    def test_deleting_the_rule_keeps_decisions_with_null_rule(
            self, tenant_a, vendor_party_a, approval_rule_cap_a):
        big = _line_po(tenant_a, vendor_party_a, "pending_approval", "5", "50000.00")
        decision = _approval(tenant_a, big, rule=approval_rule_cap_a, tier=1)
        approval_rule_cap_a.delete()
        decision.refresh_from_db()  # SET_NULL — the row survives
        assert decision.rule_id is None
        assert decision.tier == 1  # what actually governed is untouched


# ------------------------------------------------------------------ presentation


class TestPoStrSanity:
    def test_saved_rows_render_number_po_and_channel_or_tier(self, tenant_a, vendor_party_a, approval_rule_cap_a):
        big = _line_po(tenant_a, vendor_party_a, "pending_approval", "5", "50000.00")
        decision = _approval(tenant_a, big, rule=approval_rule_cap_a, tier=1)
        text = str(decision)
        assert decision.number in text
        assert decision.purchase_order.number in text
        assert "tier 1" in text and "Approved" in text
        small = _line_po(tenant_a, vendor_party_a, "sent", "2", "100.00")
        transmission = _dispatch(tenant_a, small)
        text = str(transmission)
        assert transmission.number in text
        assert transmission.purchase_order.number in text
        assert "Email" in text
        assert str(approval_rule_cap_a) == "Capital purchases"
