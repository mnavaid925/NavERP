"""Inventory 5.3 — form boundary for PO Management.

Two forms sit between a crafted POST and the approval/dispatch layer. ``PurchaseOrderApprovalRuleForm``
guards routing policy: tenant-stamped name uniqueness (a duplicate renders as an error instead of
500ing), the model's band sanity check surfacing through ``full_clean``, an org-unit dropdown that
only ever offers this workspace's departments, and the hard 1..10 tier ceiling. ``PurchaseOrderDispatchForm``
guards the transmission log: the order dropdown refuses anything not honestly dispatchable
(draft/pending/terminal orders), foreign pks die at choice-validation, and email-needs-recipient
renders as an error because the model's ``clean()`` fires during form validation on CREATE too —
the mixin's tenant stamp is what lets that ``clean()`` run without false-rejecting. Neither form
carries ``tenant`` or ``number``.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.inventory.forms import (
    PurchaseOrderApprovalRuleForm,
    PurchaseOrderDispatchForm,
)
from apps.inventory.models import PurchaseOrderApprovalRule, PurchaseOrderDispatch

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ local PO fixtures
#
# conftest.py's ``_make_po`` (behind po_pending_a / po_sent_a / po_dispatch_a) references
# ``datetime.date`` without importing ``datetime``, so requesting any of those fixtures dies
# with a NameError at setup. That file is frozen, so this module shadows the two fixtures it
# needs with byte-for-byte equivalent rows instead.


@pytest.fixture
def sent_po(db, tenant_a, admin_user, vendor_party_a):
    """An already-sent small order ($200) — dispatchable, nothing left to flip."""
    from apps.scm.models import PurchaseOrder, PurchaseOrderLine

    po = PurchaseOrder(
        tenant=tenant_a, vendor=vendor_party_a,
        order_date=datetime.date(2026, 8, 20), status="sent")
    po.save()
    PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Probe rig", sku_hint="PRB-1",
        quantity=Decimal("2"), unit_price=Decimal("100.00"))
    po.recalc_totals()
    return po


@pytest.fixture
def dispatch_row(db, tenant_a, sent_po):
    """One recorded email transmission of sent_po."""
    from django.utils import timezone

    return PurchaseOrderDispatch.objects.create(
        tenant=tenant_a, purchase_order=sent_po, channel="email",
        recipient="orders@acmesupplies.example.com", reference="MSG-PO-1",
        dispatched_at=timezone.now())


# ------------------------------------------------------------------ helpers

RULE_DATA = {
    "name": "Escalated band",
    "min_amount": "10000",
    "max_amount": "100000",
    "org_unit": "",
    "tier_count": "2",
    "is_active": "on",
}

DISPATCH_DATA = {
    "channel": "email",
    "recipient": "orders@acmesupplies.example.com",
    "reference": "",
    "dispatched_at": "2026-08-21T14:30",
    "note": "",
}


def rule_data(**overrides):
    data = dict(RULE_DATA)
    data.update(overrides)
    return data


def dispatch_data(purchase_order=None, **overrides):
    data = dict(DISPATCH_DATA)
    data.update(overrides)
    if purchase_order is not None:
        data["purchase_order"] = purchase_order.pk
    return data


def _make_status_po(tenant, vendor, status):
    """A bare spine purchase order in exactly ``status`` — no lines needed to exist."""
    from apps.scm.models import PurchaseOrder

    return PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor,
        order_date=datetime.date(2026, 8, 20), status=status)


# ------------------------------------------------------------------ PurchaseOrderApprovalRuleForm


class TestPurchaseOrderApprovalRuleForm:
    def test_po_valid_create_stamps_tenant(self, tenant_a):
        form = PurchaseOrderApprovalRuleForm(data=rule_data(), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.is_active is True

    def test_po_duplicate_name_rejected_within_tenant(self, tenant_a):
        """unique_together(tenant, name) must validate at the boundary: the first row saves,
        the same name again renders as an error instead of passing ``is_valid()`` and dying as
        an IntegrityError on save."""
        first = PurchaseOrderApprovalRuleForm(data=rule_data(name="Band A"), tenant=tenant_a)
        assert first.is_valid(), first.errors
        first.save()
        dup = PurchaseOrderApprovalRuleForm(data=rule_data(name="Band A"), tenant=tenant_a)
        assert not dup.is_valid()
        joined = " | ".join(msg for msgs in dup.errors.values() for msg in msgs)
        assert "already exist" in joined.lower() or "Band A" in joined
        assert PurchaseOrderApprovalRule.objects.filter(
            tenant=tenant_a, name="Band A").count() == 1

    def test_po_same_name_allowed_in_another_tenant(self, tenant_b, approval_rule_std_a):
        """The uniqueness scope is the workspace: tenant_b may define its own "Standard
        purchases" even though tenant_a already has one."""
        form = PurchaseOrderApprovalRuleForm(
            data=rule_data(name="Standard purchases", min_amount="0", max_amount="5000",
                           tier_count="1"),
            tenant=tenant_b)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_b.pk
        assert obj.name == approval_rule_std_a.name

    def test_po_max_below_min_is_field_error(self, tenant_a):
        """The band sanity check lives on the model's clean(), so it surfaces during form
        validation keyed on ``max_amount`` — same rule the admin obeys."""
        form = PurchaseOrderApprovalRuleForm(
            data=rule_data(min_amount="50000", max_amount="100"), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["max_amount"]

    def test_po_blank_max_amount_open_ended_valid(self, tenant_a):
        form = PurchaseOrderApprovalRuleForm(data=rule_data(max_amount=""), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.max_amount is None

    def test_po_org_unit_choices_scoped_to_tenant(self, tenant_a, tenant_b):
        """The department dropdown only offers this workspace's org units; a foreign pk dies
        at choice-validation ("Select a valid choice") — the narrowed <select> is UX, the
        queryset filter is the boundary."""
        from apps.core.models import OrgUnit
        own = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Ops")
        foreign = OrgUnit.objects.create(tenant=tenant_b, kind="branch", name="Globex Ops")

        queryset = PurchaseOrderApprovalRuleForm(tenant=tenant_a).fields["org_unit"].queryset
        assert own in queryset
        assert foreign not in queryset

        form = PurchaseOrderApprovalRuleForm(
            data=rule_data(org_unit=foreign.pk), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["org_unit"]
        assert form.instance.pk is None

    def test_po_tier_count_bounds_enforced(self, tenant_a):
        low = PurchaseOrderApprovalRuleForm(data=rule_data(tier_count="0"), tenant=tenant_a)
        high = PurchaseOrderApprovalRuleForm(data=rule_data(tier_count="11"), tenant=tenant_a)
        edge = PurchaseOrderApprovalRuleForm(data=rule_data(tier_count="10"), tenant=tenant_a)
        assert not low.is_valid()
        assert "tier_count" in low.errors
        assert not high.is_valid()
        assert "tier_count" in high.errors
        assert edge.is_valid(), edge.errors  # the ceiling itself is legal


# ------------------------------------------------------------------ PurchaseOrderDispatchForm


class TestPurchaseOrderDispatchForm:
    def test_po_dropdown_excludes_draft_pending_and_terminal_orders(
            self, tenant_a, vendor_party_a, sent_po):
        """A dispatch can honestly exist only from APPROVED onward: draft/pending orders have
        nothing sent yet, and cancelled/closed orders are terminal — re-sending them would lie."""
        from apps.inventory.forms.PurchaseOrderManagement.Dispatches import _dispatchable_orders

        draft = _make_status_po(tenant_a, vendor_party_a, "draft")
        pending = _make_status_po(tenant_a, vendor_party_a, "pending_approval")
        cancelled = _make_status_po(tenant_a, vendor_party_a, "cancelled")
        closed = _make_status_po(tenant_a, vendor_party_a, "closed")

        pks = set(_dispatchable_orders(tenant_a).values_list("pk", flat=True))
        assert sent_po.pk in pks
        assert {draft.pk, pending.pk, cancelled.pk, closed.pk}.isdisjoint(pks)

        # the form field serves exactly the helper's queryset
        form_qs = PurchaseOrderDispatchForm(tenant=tenant_a).fields["purchase_order"].queryset
        assert set(form_qs.values_list("pk", flat=True)) == pks

    def test_po_dropdown_includes_approved_through_received(
            self, tenant_a, vendor_party_a, sent_po):
        approved = _make_status_po(tenant_a, vendor_party_a, "approved")
        acknowledged = _make_status_po(tenant_a, vendor_party_a, "acknowledged")
        partial = _make_status_po(tenant_a, vendor_party_a, "partially_received")
        received = _make_status_po(tenant_a, vendor_party_a, "received")

        pks = set(PurchaseOrderDispatchForm(tenant=tenant_a)
                  .fields["purchase_order"].queryset.values_list("pk", flat=True))
        assert {approved.pk, sent_po.pk, acknowledged.pk, partial.pk, received.pk} <= pks

    def test_po_email_create_mints_number_and_reference_optional(self, tenant_a, sent_po):
        form = PurchaseOrderDispatchForm(data=dispatch_data(sent_po), tenant=tenant_a)
        assert form.is_valid(), form.errors  # reference left blank -> optional
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        import re
        assert re.fullmatch(r"PD-\d+", obj.number)
        assert obj.recipient == DISPATCH_DATA["recipient"]
        assert obj.reference == ""

    def test_po_email_blank_recipient_invalid(self, tenant_a, sent_po):
        """The channel/recipient rule is enforced on the MODEL, so it renders as a field error
        through full_clean() — on CREATE too, because TenantUniqueMixin stamped instance.tenant
        before validation rather than leaving it to post-is_valid() CRUD helpers."""
        form = PurchaseOrderDispatchForm(
            data=dispatch_data(sent_po, recipient=""), tenant=tenant_a)
        assert not form.is_valid()
        assert "recipient" in form.errors
        assert any("recipient" in msg.lower() for msg in form.errors["recipient"])
        assert form.instance.pk is None

    def test_po_print_channel_needs_no_recipient(self, tenant_a, sent_po):
        """Print/PDF is the one channel exempt from carrying an address: ``recipient`` is
        ``blank=True`` on the model, and only ``ADDRESSED_CHANNELS`` (email/edi) are policed
        by the model's ``clean()`` — so a print row with no recipient validates at BOTH the
        form boundary and ``full_clean()``. Email/EDI with a blank recipient still die with
        the model's own message (asserted in its sibling test)."""
        forced = PurchaseOrderDispatchForm(
            data=dispatch_data(sent_po, channel="print", recipient=""), tenant=tenant_a)
        assert forced.is_valid(), dict(forced.errors)
        obj = forced.save()
        assert obj.recipient == ""

        bare = PurchaseOrderDispatch(
            tenant=tenant_a, purchase_order=sent_po, channel="print", recipient="")
        bare.full_clean()  # print is exempt: no recipient demanded at the model layer either
        bare.save()
        assert PurchaseOrderDispatch.objects.get(pk=bare.pk).recipient == ""

    def test_po_rejects_foreign_purchase_order(self, tenant_a, tenant_b, vendor_party_b):
        """The dropdown is scoped to this workspace's orders, so a foreign pk fails choice-
        validation ("Select a valid choice"); _reject_foreign and the model's clean() sit
        beneath it as belt-and-braces. Either layer rejecting is a pass — assert invalid +
        error on the form's field + nothing saved."""
        from apps.inventory.forms.PurchaseOrderManagement.Dispatches import _dispatchable_orders
        foreign = _make_status_po(tenant_b, vendor_party_b, "sent")
        assert foreign not in _dispatchable_orders(tenant_a)

        before = PurchaseOrderDispatch.objects.count()
        form = PurchaseOrderDispatchForm(data=dispatch_data(foreign), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["purchase_order"]
        assert form.instance.pk is None
        assert PurchaseOrderDispatch.objects.count() == before

    def test_po_edit_preserves_recipient_without_retyping(
            self, tenant_a, sent_po, dispatch_row):
        """An untouched edit re-submits what the form rendered: the stored recipient comes back
        as initial, and posting it unchanged stays valid — nobody retypes an address to save
        an untouched row."""
        from django.utils import timezone

        blank = PurchaseOrderDispatchForm(instance=dispatch_row, tenant=tenant_a)
        assert blank.initial["recipient"] == dispatch_row.recipient
        data = {
            "purchase_order": sent_po.pk,
            "channel": dispatch_row.channel,
            "recipient": blank.initial["recipient"],
            "reference": dispatch_row.reference or "",
            "dispatched_at": timezone.localtime(
                dispatch_row.dispatched_at).strftime("%Y-%m-%dT%H:%M"),
            "note": "",
        }
        bound = PurchaseOrderDispatchForm(data=data, instance=dispatch_row, tenant=tenant_a)
        assert bound.is_valid(), bound.errors
        assert bound.cleaned_data["recipient"] == dispatch_row.recipient

    def test_po_datetime_local_format_accepted(self, tenant_a, sent_po):
        """The datetime-local widget's wire format ("%Y-%m-%dT%H:%M") round-trips."""
        form = PurchaseOrderDispatchForm(
            data=dispatch_data(sent_po, dispatched_at="2026-08-21T09:05"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.dispatched_at.strftime("%Y-%m-%dT%H:%M") == "2026-08-21T09:05"


# ------------------------------------------------------------------ excludes on both forms


class TestPoFormFieldExcludes:
    def test_po_forms_expose_no_tenant_or_number_fields(self, tenant_a):
        """``tenant`` is stamped by the mixin / crud helpers and never a POSTable field;
        ``number`` is minted by save() (editable=False) — or doesn't exist at all on the
        rule, which is TenantOwned, not numbered. A crafted POST can smuggle neither."""
        rule_form = PurchaseOrderApprovalRuleForm(tenant=tenant_a).fields
        dispatch_form = PurchaseOrderDispatchForm(tenant=tenant_a).fields
        for fields in (rule_form, dispatch_form):
            assert "tenant" not in fields
            assert "number" not in fields
