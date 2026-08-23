"""Inventory 5.3 — views.

The management layer around SCM 4.1's purchase-order spine, exercised end to end through
its four pages: routing RULES (admin-gated CRUD whose bands and decision trail render on
the detail page), the tiered approval QUEUE (progress replayed from decision rows, verbs
hidden from members), the DISPATCH log (proof of transmission; the first record of an
approved order sends it), and reorder DRAFTING (below-point rules become draft spine
orders grouped per vendor).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit, Party, PartyRole
from apps.inventory.models import (
    PurchaseOrderApproval,
    PurchaseOrderApprovalRule,
    PurchaseOrderDispatch,
)
from apps.scm.models import Item, Location, PurchaseOrder, PurchaseOrderLine, ReorderRule

pytestmark = pytest.mark.django_db


def _spine_po(tenant, vendor, *, status, quantity, unit_price):
    """An extra spine purchase order built directly through the ORM: one line, derived totals."""
    po = PurchaseOrder(
        tenant=tenant, vendor=vendor, order_date=datetime.date(2026, 8, 20), status=status)
    po.save()
    PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Probe rig", sku_hint="PRB-1",
        quantity=Decimal(quantity), unit_price=Decimal(unit_price))
    po.recalc_totals()
    return po


def _audit_actions(obj):
    """The changes['action'] values of every audit row about ``obj``, oldest first."""
    ct = ContentType.objects.get_for_model(type(obj))
    return [log.changes.get("action")
            for log in AuditLog.objects.filter(content_type=ct, object_id=str(obj.pk))]


def _flash(response):
    return [str(message) for message in response.context["messages"]]


# ---- 1. Approval-rule CRUD -------------------------------------------------------------------------


def test_po_rule_list_renders_seeded_rule_names(client_a, approval_rule_std_a,
                                                approval_rule_cap_a):
    response = client_a.get(reverse("inventory:approvalrule_list"))
    assert response.status_code == 200
    content = response.content
    assert b"PO Approval Rules" in content
    assert b"Standard purchases" in content
    assert b"Capital purchases" in content


def test_po_rule_list_search_and_state_filters(client_a, approval_rule_std_a,
                                               approval_rule_cap_a):
    retired = PurchaseOrderApprovalRule.objects.create(
        tenant=approval_rule_std_a.tenant, name="Retired band", is_active=False,
        min_amount=Decimal("0"), max_amount=Decimal("500"), tier_count=1)

    hit = client_a.get(reverse("inventory:approvalrule_list") + "?q=Capital")
    assert hit.status_code == 200
    assert [obj.name for obj in hit.context["object_list"]] == ["Capital purchases"]

    inactive = client_a.get(reverse("inventory:approvalrule_list") + "?active=False")
    assert inactive.status_code == 200
    # Both seeded rules are active — hiding actives leaves only the retired one.
    assert list(inactive.context["object_list"]) == [retired]


def test_po_rule_list_department_filter(client_a, approval_rule_std_a):
    unit = OrgUnit.objects.create(
        tenant=approval_rule_std_a.tenant, kind="department", name="Engineering")
    scoped = PurchaseOrderApprovalRule.objects.create(
        tenant=approval_rule_std_a.tenant, name="Engineering purchases",
        min_amount=Decimal("0"), max_amount=None, org_unit=unit, tier_count=2)
    hit = client_a.get(reverse("inventory:approvalrule_list") + f"?org_unit={unit.pk}")
    assert hit.status_code == 200
    assert list(hit.context["object_list"]) == [scoped]


def test_po_rule_detail_band_text_and_decisions_panel(client_a, admin_user, po_pending_a,
                                                      approval_rule_std_a,
                                                      approval_rule_cap_a, tier_decision_a):
    cap = client_a.get(reverse("inventory:approvalrule_detail",
                               args=[approval_rule_cap_a.pk]))
    assert cap.status_code == 200
    content = cap.content
    assert b"and above" in content                       # open-ended band text
    assert b"100000.00" in content
    assert b"3 sequential sign-offs" in content
    assert b"Recent Decisions Under This Rule" in content
    assert b"No decisions yet" not in content            # tier 1 was decided under this rule
    assert po_pending_a.number.encode() in content       # the decided order is linked
    assert admin_user.username.encode() in content       # ...with its signer

    std = client_a.get(reverse("inventory:approvalrule_detail",
                               args=[approval_rule_std_a.pk]))
    assert std.status_code == 200
    assert b"(exclusive)" in std.content                 # half-open upper bound rendered
    assert b"No decisions yet" in std.content


def test_po_rule_create_edit_delete_roundtrip(client_a, tenant_a):
    create_url = reverse("inventory:approvalrule_create")
    assert client_a.get(create_url).status_code == 200
    payload = {"name": "Services band", "min_amount": "5000", "max_amount": "20000",
               "org_unit": "", "tier_count": "2", "is_active": "on"}
    created = client_a.post(create_url, data=payload)
    assert created.status_code == 302
    assert created.url == reverse("inventory:approvalrule_list")
    listing = client_a.get(created.url)
    assert b"Services band" in listing.content
    rule = PurchaseOrderApprovalRule.objects.get(tenant=tenant_a, name="Services band")
    assert rule.tier_count == 2
    assert rule.is_active

    edit_url = reverse("inventory:approvalrule_edit", args=[rule.pk])
    assert client_a.get(edit_url).status_code == 200
    edited = client_a.post(edit_url, data={**payload, "tier_count": "3"})
    assert edited.status_code == 302
    rule.refresh_from_db()
    assert rule.tier_count == 3

    deleted = client_a.post(reverse("inventory:approvalrule_delete", args=[rule.pk]))
    assert deleted.status_code == 302
    assert not PurchaseOrderApprovalRule.objects.filter(pk=rule.pk).exists()


# ---- 2. Approval queue -----------------------------------------------------------------------------


def test_po_queue_renders_pending_order_with_routing_and_progress(
        client_a, po_pending_a, approval_rule_cap_a, tier_decision_a):
    response = client_a.get(reverse("inventory:approval_queue"))
    assert response.status_code == 200
    content = response.content
    assert b"PO Approval Workflows" in content
    assert po_pending_a.number.encode() in content
    assert b"250000.00" in content
    assert b"Capital purchases" in content               # routing rule resolved live
    assert b"1 of 3" in content                          # progress replayed from decisions
    assert b"Approve tier 2" in content                  # next-tier button for admins


def test_po_queue_member_sees_no_decision_buttons(member_client, po_pending_a,
                                                  tier_decision_a):
    response = member_client.get(reverse("inventory:approval_queue"))
    assert response.status_code == 200
    content = response.content
    assert po_pending_a.number.encode() in content       # members see the queue itself...
    assert b"Admin sign-off required" in content         # ...but never the verbs
    assert b"Approve tier 2" not in content
    verb_path = reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, 2])
    assert verb_path.encode() not in content             # no approve/reject action URLs at all
    assert b'name="note"' not in content


def test_po_queue_empty_tenant_renders_empty_state(client_b, po_pending_a):
    response = client_b.get(reverse("inventory:approval_queue"))
    assert response.status_code == 200
    content = response.content
    assert b"Nothing awaiting approval" in content
    assert b"No decisions recorded yet" in content
    assert po_pending_a.number.encode() not in content   # tenant_a's pending order never leaks


# ---- 3. Sequential workflow ------------------------------------------------------------------------


def test_po_approve_remaining_tiers_finalizes_order(client_a, admin_user, po_pending_a,
                                                    approval_rule_cap_a, tier_decision_a):
    second = client_a.post(
        reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, 2]),
        data={"note": "numbers check out"}, follow=True)
    assert second.status_code == 200
    assert any("Tier 2 of 3 recorded" in text for text in _flash(second))
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "pending_approval"     # mid-chain: not yet approved

    final = client_a.post(
        reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, 3]),
        data={}, follow=True)
    assert final.status_code == 200
    assert any("approved" in text for text in _flash(final))
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "approved"
    assert po_pending_a.approved_by_id == admin_user.pk
    assert po_pending_a.approved_at is not None
    rows = list(PurchaseOrderApproval.objects.filter(purchase_order=po_pending_a)
                .order_by("id"))
    assert [row.tier for row in rows] == [1, 2, 3]
    assert all(row.decision == "approved" for row in rows)


def test_po_out_of_sequence_tier_is_refused(client_a, po_pending_a, tier_decision_a):
    skipped = client_a.post(
        reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, 3]),
        data={}, follow=True)
    assert skipped.status_code == 200
    assert any("must be decided first" in text for text in _flash(skipped))
    assert (PurchaseOrderApproval.objects.filter(purchase_order=po_pending_a).count() == 1)
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "pending_approval"


def test_po_reject_returns_the_order_to_draft(client_a, po_pending_a, tier_decision_a):
    response = client_a.post(
        reverse("inventory:approval_tier_reject", args=[po_pending_a.pk, 2]),
        data={"note": "no budget line"}, follow=True)
    assert response.status_code == 200
    assert any("returned to draft" in text for text in _flash(response))
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "draft"
    rejection = PurchaseOrderApproval.objects.get(purchase_order=po_pending_a, tier=2)
    assert rejection.decision == "rejected"
    assert rejection.note == "no budget line"


def test_po_resubmitted_order_redecides_every_tier_with_fresh_rows(
        client_a, admin_user, po_pending_a, tier_decision_a):
    """THE C1 regression: run one's rows stay as history; run two writes its own rows."""
    rejected = client_a.post(
        reverse("inventory:approval_tier_reject", args=[po_pending_a.pk, 2]), data={})
    assert rejected.status_code == 302
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "draft"

    po_pending_a.status = "pending_approval"             # the buyer resubmits
    po_pending_a.save(update_fields=["status", "updated_at"])

    for tier in (1, 2, 3):                               # the whole chain runs again
        step = client_a.post(
            reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, tier]),
            data={})
        assert step.status_code == 302
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "approved"
    assert po_pending_a.approved_by_id == admin_user.pk

    rows = list(PurchaseOrderApproval.objects.filter(purchase_order=po_pending_a)
                .order_by("id"))
    assert [(row.tier, row.decision) for row in rows] == [
        (1, "approved"), (2, "rejected"),                # run one — kept, not overwritten
        (1, "approved"), (2, "approved"), (3, "approved")]  # run two — fresh rows per run


# ---- 4. Dispatch log -------------------------------------------------------------------------------


def test_po_dispatch_list_renders_number_recipient_and_reference(
        client_a, po_sent_a, po_dispatch_a):
    response = client_a.get(reverse("inventory:dispatch_list"))
    assert response.status_code == 200
    content = response.content
    assert b"PO Dispatch Log" in content
    assert po_dispatch_a.number.encode() in content
    assert po_sent_a.number.encode() in content
    assert b"orders@acmesupplies.example.com" in content
    assert b"MSG-PO-1" in content


def test_po_dispatch_list_channel_and_order_filters(client_a, po_pending_a, po_dispatch_a):
    base = reverse("inventory:dispatch_list")

    email = client_a.get(base + "?channel=email")
    assert email.status_code == 200
    assert po_dispatch_a in email.context["object_list"]

    edi = client_a.get(base + "?channel=edi")
    assert edi.status_code == 200
    assert len(edi.context["object_list"]) == 0

    other = client_a.get(base + f"?po={po_pending_a.pk}")
    assert other.status_code == 200
    assert len(other.context["object_list"]) == 0


def test_po_dispatch_detail_shows_reference_and_siblings_panel(
        client_a, po_sent_a, po_dispatch_a):
    sibling = PurchaseOrderDispatch.objects.create(
        tenant=po_sent_a.tenant, purchase_order=po_sent_a, channel="edi",
        recipient="EDI-PARTNER-7", reference="ICN-42", dispatched_at=timezone.now())
    response = client_a.get(reverse("inventory:dispatch_detail", args=[po_dispatch_a.pk]))
    assert response.status_code == 200
    content = response.content
    assert b"MSG-PO-1" in content
    section = content.split(b"Other Transmissions of")[1]
    assert f"po/dispatches/{sibling.pk}/".encode() in section
    assert f"po/dispatches/{po_dispatch_a.pk}/".encode() not in section  # self-excluded


def test_po_dispatch_create_on_approved_order_sends_it(client_a, tenant_a, vendor_party_a):
    approved = _spine_po(tenant_a, vendor_party_a, status="approved",
                         quantity="4", unit_price="50.00")
    response = client_a.post(reverse("inventory:dispatch_create"), data={
        "purchase_order": str(approved.pk), "channel": "email",
        "recipient": "orders@acme.example", "reference": "MSG-NEW-1",
        "dispatched_at": "2026-08-21T09:30", "note": ""})
    assert response.status_code == 302
    dispatch = PurchaseOrderDispatch.objects.get(reference="MSG-NEW-1")
    assert dispatch.number.startswith("PD-")
    assert response.url == reverse("inventory:dispatch_detail", args=[dispatch.pk])
    approved.refresh_from_db()
    assert approved.status == "sent"                     # the first dispatch sends the order


def test_po_dispatch_resend_of_sent_order_keeps_status(client_a, po_sent_a):
    before = PurchaseOrderDispatch.objects.count()
    response = client_a.post(reverse("inventory:dispatch_create"), data={
        "purchase_order": str(po_sent_a.pk), "channel": "email",
        "recipient": "orders@acme.example", "reference": "MSG-RESEND",
        "dispatched_at": "2026-08-22T08:00", "note": ""})
    assert response.status_code == 302
    assert PurchaseOrderDispatch.objects.count() == before + 1  # row recorded...
    po_sent_a.refresh_from_db()
    assert po_sent_a.status == "sent"                    # ...but the status never moves twice


def test_po_dispatch_print_channel_accepts_blank_recipient(client_a, po_sent_a):
    response = client_a.post(reverse("inventory:dispatch_create"), data={
        "purchase_order": str(po_sent_a.pk), "channel": "print", "recipient": "",
        "reference": "", "dispatched_at": "2026-08-22T08:00", "note": ""})
    assert response.status_code == 302                   # valid — print/PDF has no address
    row = PurchaseOrderDispatch.objects.get(channel="print")
    assert row.recipient == ""
    po_sent_a.refresh_from_db()
    assert po_sent_a.status == "sent"


def test_po_dispatch_delete_removes_the_row(client_a, po_dispatch_a):
    response = client_a.post(reverse("inventory:dispatch_delete", args=[po_dispatch_a.pk]))
    assert response.status_code == 302
    assert response.url == reverse("inventory:dispatch_list")
    assert not PurchaseOrderDispatch.objects.filter(pk=po_dispatch_a.pk).exists()


# ---- 5. Reorder drafting ---------------------------------------------------------------------------


def test_po_reorderdraft_lists_only_below_point_rules(
        client_a, tenant_a, item_a, location_a, reorder_below_a):
    dock_two = Location.objects.create(tenant=tenant_a, code="DOCK-2", name="Overflow dock")
    satisfied = ReorderRule.objects.create(          # point 0, on-hand 0: asks for nothing
        tenant=tenant_a, item=item_a, location=dock_two,
        reorder_point=Decimal("0"), safety_stock=Decimal("0"))

    response = client_a.get(reverse("inventory:reorderdraft"))
    assert response.status_code == 200
    suggestions = response.context["suggestions"]
    assert [row["rule"].pk for row in suggestions] == [reorder_below_a.pk]
    assert suggestions[0]["qty"] > 0
    content = response.content
    assert b"CAT-1" in content                           # the item sku renders on the row
    assert b"DOCK-2" not in content                      # the satisfied rule is absent


def test_po_reorderdraft_post_creates_one_draft_for_chosen_vendor(
        client_a, tenant_a, vendor_party_a, item_a, reorder_below_a):
    response = client_a.post(reverse("inventory:reorderdraft"), data={
        "select": str(reorder_below_a.pk),
        f"vendor_{reorder_below_a.pk}": str(vendor_party_a.pk)})
    assert response.status_code == 302
    order = PurchaseOrder.objects.get(tenant=tenant_a)
    assert order.vendor_id == vendor_party_a.pk
    assert order.status == "draft"                       # lands as a reviewable draft
    line = order.lines.get()
    assert line.quantity == Decimal("1000009.00")        # suggested_quantity recomputed live
    assert line.unit_price == item_a.standard_cost
    assert line.sku_hint == "CAT-1"
    assert response.url == reverse("scm:purchaseorder_detail", args=[order.pk])
    assert "auto_draft_reorder" in _audit_actions(order)


def test_po_reorderdraft_post_without_vendor_warns_and_drafts_zero(
        client_a, tenant_a, reorder_below_a):
    response = client_a.post(reverse("inventory:reorderdraft"),
                             data={"select": str(reorder_below_a.pk)}, follow=True)
    assert response.status_code == 200
    assert any("Nothing drafted" in text for text in _flash(response))
    assert not PurchaseOrder.objects.filter(tenant=tenant_a).exists()


def test_po_reorderdraft_post_without_selection_errors(client_a, tenant_a, reorder_below_a):
    response = client_a.post(reverse("inventory:reorderdraft"), data={}, follow=True)
    assert response.status_code == 200
    assert any("Tick at least one suggestion" in text for text in _flash(response))
    assert not PurchaseOrder.objects.filter(tenant=tenant_a).exists()


def test_po_reorderdraft_multi_vendor_creates_two_draft_orders(
        client_a, tenant_a, vendor_party_a, item_a, location_a, reorder_below_a):
    heavy = Item.objects.create(tenant=tenant_a, sku="CAT-9", name="Heavy Widget",
                                standard_cost=Decimal("4.00"))
    heavy_rule = ReorderRule.objects.create(
        tenant=tenant_a, item=heavy, location=location_a,
        reorder_point=Decimal("500"), safety_stock=Decimal("5"))
    other_vendor = Party.objects.create(
        tenant=tenant_a, name="Conrad Parts", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=other_vendor, role="vendor")

    response = client_a.post(reverse("inventory:reorderdraft"), data={
        "select": [str(reorder_below_a.pk), str(heavy_rule.pk)],
        f"vendor_{reorder_below_a.pk}": str(vendor_party_a.pk),
        f"vendor_{heavy_rule.pk}": str(other_vendor.pk)})
    assert response.status_code == 302
    assert response.url == reverse("scm:purchaseorder_list")   # multiple drafts -> the register
    orders = {order.vendor_id: order
              for order in PurchaseOrder.objects.filter(tenant=tenant_a)}
    assert len(orders) == 2                                    # one group per vendor
    acme, conrad = orders[vendor_party_a.pk], orders[other_vendor.pk]
    assert acme.status == "draft" and conrad.status == "draft"
    assert acme.lines.get().sku_hint == "CAT-1"
    assert conrad.lines.get().sku_hint == "CAT-9"


# ---- 6. Page hygiene -------------------------------------------------------------------------------


def test_po_pages_render_without_template_leak_markers(
        client_a, approval_rule_std_a, approval_rule_cap_a, po_dispatch_a, reorder_below_a):
    pages = [
        ("rule list", client_a.get(reverse("inventory:approvalrule_list"))),
        ("rule detail", client_a.get(reverse("inventory:approvalrule_detail",
                                             args=[approval_rule_std_a.pk]))),
        ("rule form", client_a.get(reverse("inventory:approvalrule_create"))),
        ("rule edit", client_a.get(reverse("inventory:approvalrule_edit",
                                           args=[approval_rule_std_a.pk]))),
        ("queue", client_a.get(reverse("inventory:approval_queue"))),
        ("dispatch list", client_a.get(reverse("inventory:dispatch_list"))),
        ("dispatch form", client_a.get(reverse("inventory:dispatch_create"))),
        ("dispatch detail", client_a.get(reverse("inventory:dispatch_detail",
                                                 args=[po_dispatch_a.pk]))),
        ("reorder draft", client_a.get(reverse("inventory:reorderdraft"))),
    ]
    for label, page in pages:
        assert page.status_code == 200, label
        assert b"{#" not in page.content, label          # no unrendered template comments
        assert b"{% comment" not in page.content, label
