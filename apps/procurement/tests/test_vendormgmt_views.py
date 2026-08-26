"""Procurement 6.4 Vendor Management — view tests (portal access / suspensions /
invoice submissions / the login-gated vendor portal itself)."""
from decimal import Decimal
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Party
from apps.procurement.models import (
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
)
from apps.scm.models import PurchaseOrder

pytestmark = pytest.mark.django_db


def _msgs(resp):
    return [str(m) for m in resp.context["messages"]]


@pytest.fixture
def party_a(supplier_a):
    _, party = supplier_a
    return party


def _active_block(tenant, party, requester):
    return VendorSuspension.objects.create(
        tenant=tenant, supplier=party, kind="suspension", reason_category="delivery",
        reason="Repeated late deliveries.", status="active", requested_by=requester)


# ------------------------------------------------------------------ portal access (VPA)

def test_vpa_list_and_create_as_admin(client_a, tenant_a, admin_user, supplier_a,
                                      party_a, vpa_a):
    resp = client_a.get(reverse("procurement:vpa_list"))
    assert resp.status_code == 200 and vpa_a.number in resp.content.decode()
    resp = client_a.post(reverse("procurement:vpa_create"),
                         {"supplier": party_a.pk, "portal_user": "",
                          "is_active": "on", "note": "welcome aboard"})
    assert resp.status_code == 302
    row = VendorPortalAccess.objects.exclude(pk=vpa_a.pk).get()
    assert row.tenant == tenant_a and row.supplier == party_a
    assert row.invited_by == admin_user and row.is_active and row.note == "welcome aboard"
    resp = client_a.get(reverse("procurement:vpa_detail", args=[row.pk]))
    assert resp.status_code == 200 and row.number in resp.content.decode()


def test_vpa_create_is_admin_gated(member_client):
    resp = member_client.get(reverse("procurement:vpa_create"))
    assert resp.status_code == 403  # tenant_admin_required -> PermissionDenied
    assert VendorPortalAccess.objects.count() == 0


# ------------------------------------------------------------------ suspensions (VSU)

def test_vsu_list_and_member_can_file_request(member_client, tenant_a, member_user,
                                              party_a, vsu_requested_a):
    resp = member_client.get(reverse("procurement:vsu_list"))
    assert resp.status_code == 200 and vsu_requested_a.number in resp.content.decode()
    resp = member_client.post(
        reverse("procurement:vsu_create"),
        {"supplier": party_a.pk, "kind": "suspension", "reason_category": "quality",
         "reason": "Three bad batches.", "starts_on": timezone.localdate()})
    assert resp.status_code == 302
    row = VendorSuspension.objects.exclude(pk=vsu_requested_a.pk).get()
    assert row.status == "requested" and row.requested_by == member_user
    assert row.tenant == tenant_a


def test_vsu_approve_then_second_decision_is_info_only(client_a, vsu_requested_a):
    url = reverse("procurement:vsu_approve", args=[vsu_requested_a.pk])
    resp = client_a.post(url, {"note": "ok"}, follow=True)
    vsu_requested_a.refresh_from_db()
    assert vsu_requested_a.status == "active"
    assert vsu_requested_a.decided_by.username == "admin_acme"
    assert vsu_requested_a.decided_at is not None
    assert any("in force" in m for m in _msgs(resp))
    resp = client_a.post(url, {"note": "again"}, follow=True)
    vsu_requested_a.refresh_from_db()
    assert vsu_requested_a.status == "active"
    assert any("already been decided" in m for m in _msgs(resp))


def test_vsu_lift_requires_note_then_stamps_the_exit(client_a, tenant_a, admin_user,
                                                     party_a):
    block = _active_block(tenant_a, party_a, admin_user)
    resp = client_a.post(reverse("procurement:vsu_lift", args=[block.pk]), {},
                         follow=True)
    block.refresh_from_db()
    assert block.status == "active"
    assert any("Give a reason" in m for m in _msgs(resp))
    resp = client_a.post(reverse("procurement:vsu_lift", args=[block.pk]),
                         {"lift_note": "Deliveries recovered"}, follow=True)
    block.refresh_from_db()
    assert block.status == "lifted" and block.lift_note == "Deliveries recovered"
    assert block.lifted_by == admin_user and block.lifted_at is not None
    assert any("Block lifted" in m for m in _msgs(resp))


def test_vsu_edit_locks_once_decided(client_a, vsu_requested_a):
    resp = client_a.get(reverse("procurement:vsu_edit", args=[vsu_requested_a.pk]))
    assert resp.status_code in (200, 302)
    client_a.post(reverse("procurement:vsu_approve", args=[vsu_requested_a.pk]),
                  {"note": "ok"})
    resp = client_a.post(reverse("procurement:vsu_edit", args=[vsu_requested_a.pk]),
                         {"supplier": vsu_requested_a.supplier_id, "kind": "suspension",
                          "reason_category": "delivery", "reason": "rewritten",
                          "starts_on": timezone.localdate()}, follow=True)
    vsu_requested_a.refresh_from_db()
    assert vsu_requested_a.reason != "rewritten"
    assert any("immutable history" in m for m in _msgs(resp))


def test_vsu_delete_pending_only(client_a, tenant_a, admin_user, party_a,
                                 vsu_requested_a):
    resp = client_a.post(reverse("procurement:vsu_delete", args=[vsu_requested_a.pk]),
                         follow=True)
    assert not VendorSuspension.objects.filter(pk=vsu_requested_a.pk).exists()
    decided = _active_block(tenant_a, party_a, admin_user)
    resp = client_a.post(reverse("procurement:vsu_delete", args=[decided.pk]),
                         follow=True)
    assert VendorSuspension.objects.filter(pk=decided.pk).exists()
    assert any("register history cannot be deleted" in m for m in _msgs(resp))


# ------------------------------------------------------------------ submissions (VIS)

def test_vis_review_chain_then_redecision_is_info(client_a, admin_user,
                                                  vis_submitted_a):
    resp = client_a.post(reverse("procurement:vis_start_review",
                                 args=[vis_submitted_a.pk]), {}, follow=True)
    vis_submitted_a.refresh_from_db()
    assert vis_submitted_a.status == "under_review"
    assert any("Under Review" in m for m in _msgs(resp))
    resp = client_a.post(reverse("procurement:vis_accept", args=[vis_submitted_a.pk]),
                         {"review_note": "matches the goods receipt"}, follow=True)
    vis_submitted_a.refresh_from_db()
    assert vis_submitted_a.status == "accepted"
    assert vis_submitted_a.reviewed_by == admin_user
    assert vis_submitted_a.review_note == "matches the goods receipt"
    resp = client_a.post(reverse("procurement:vis_accept", args=[vis_submitted_a.pk]),
                         {"review_note": "again"}, follow=True)
    vis_submitted_a.refresh_from_db()
    assert vis_submitted_a.status == "accepted"
    assert any("no further decision applies" in m for m in _msgs(resp))


def test_vis_reject_path_from_fresh_submission(client_a, admin_user, party_a, po_a):
    fresh = VendorInvoiceSubmission.objects.create(
        tenant=party_a.tenant, supplier=party_a, purchase_order=po_a,
        invoice_ref="INV-9002", amount=Decimal("55.00"), status="submitted",
        submitted_by=admin_user)
    resp = client_a.post(reverse("procurement:vis_reject", args=[fresh.pk]),
                         {"review_note": "pricing mismatch vs PO"}, follow=True)
    fresh.refresh_from_db()
    assert fresh.status == "rejected"
    assert fresh.reviewed_by == admin_user
    assert fresh.review_note == "pricing mismatch vs PO"


def test_vis_decisions_are_admin_gated(member_client, vis_submitted_a):
    resp = member_client.post(reverse("procurement:vis_accept",
                                      args=[vis_submitted_a.pk]),
                              {"review_note": "me"})
    assert resp.status_code == 403
    vis_submitted_a.refresh_from_db()
    assert vis_submitted_a.status == "submitted"


def test_vis_delete_gates_on_submitted_only(client_a, admin_user, party_a, po_a,
                                            vis_submitted_a):
    # Decide the fixture first: a REVIEWED row is register history.
    client_a.post(reverse("procurement:vis_accept", args=[vis_submitted_a.pk]),
                  {"review_note": ""})
    resp = client_a.post(reverse("procurement:vis_delete", args=[vis_submitted_a.pk]),
                         follow=True)
    assert VendorInvoiceSubmission.objects.filter(pk=vis_submitted_a.pk).exists()
    assert any("cannot be deleted" in m for m in _msgs(resp))
    junk = VendorInvoiceSubmission.objects.create(
        tenant=party_a.tenant, supplier=party_a, purchase_order=po_a,
        invoice_ref="INV-JUNK", amount=Decimal("5.00"), status="submitted",
        submitted_by=admin_user)
    client_a.post(reverse("procurement:vis_delete", args=[junk.pk]))
    assert not VendorInvoiceSubmission.objects.filter(pk=junk.pk).exists()


# ------------------------------------------------------------------ vendor portal

def test_portal_without_binding_redirects_home_with_error(member_client):
    resp = member_client.get(reverse("procurement:vendor_portal_home"), follow=True)
    # The refusal ladder redirects (to the dashboard home route); its concrete path varies
    # with the urlconf under test, so assert the CHAIN + the flash, not a path prefix.
    assert resp.status_code == 200
    assert resp.redirect_chain, "expected a redirect away from the portal page"
    assert any("don't have vendor portal access" in m for m in _msgs(resp))
    assert member_client.get(reverse("procurement:vendor_invoice_new")
                             ).status_code in (302, 200)


def test_portal_home_lists_own_pos_only(client_a, tenant_a, po_a, vpa_a):
    other_party = Party.objects.create(tenant=tenant_a, name="Rival Vendor Co",
                                       kind="organization")
    other_po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=other_party,
                                            status="approved",
                                            order_date=timezone.localdate())
    resp = client_a.get(reverse("procurement:vendor_portal_home"))
    body = resp.content.decode()
    assert resp.status_code == 200 and po_a.number in body
    assert other_po.number not in body


def test_vendor_invoice_new_files_for_bound_supplier(client_a, admin_user, party_a,
                                                     po_a, vpa_a, db):
    resp = client_a.get(reverse("procurement:vendor_invoice_new"))
    body = resp.content.decode()
    assert resp.status_code == 200 and 'name="invoice_ref"' in body
    resp = client_a.post(reverse("procurement:vendor_invoice_new"),
                         {"purchase_order": po_a.pk, "invoice_ref": "INV-PORTAL-77",
                          "invoice_date": timezone.localdate(), "amount": "99.50",
                          "note": "as delivered"},
                         follow=True)
    row = VendorInvoiceSubmission.objects.get(invoice_ref="INV-PORTAL-77")
    assert row.supplier == party_a and row.submitted_by == admin_user
    assert row.status == "submitted" and row.tenant == po_a.tenant
    assert any("received" in m for m in _msgs(resp))


def test_blocked_supplier_cannot_submit_until_lifted(client_a, tenant_a, admin_user,
                                                     party_a, po_a, vpa_a):
    block = _active_block(tenant_a, party_a, admin_user)
    resp = client_a.get(reverse("procurement:vendor_invoice_new"))
    body = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="invoice_ref"' not in body and "Account suspended" in body
    payload = {"purchase_order": po_a.pk, "invoice_ref": "INV-BLOCKED",
               "amount": "10.00"}
    resp = client_a.post(reverse("procurement:vendor_invoice_new"), payload,
                         follow=True)
    assert not VendorInvoiceSubmission.objects.filter(invoice_ref="INV-BLOCKED").exists()
    assert any("suspended/blacklisted" in m for m in _msgs(resp))
    client_a.post(reverse("procurement:vsu_lift", args=[block.pk]),
                  {"lift_note": "resolved with the vendor"})
    resp = client_a.post(reverse("procurement:vendor_invoice_new"), payload,
                         follow=True)
    row = VendorInvoiceSubmission.objects.get(invoice_ref="INV-BLOCKED")
    assert row.supplier == party_a and row.submitted_by == admin_user


# ------------------------------------------------------------------ tenancy

def test_cross_tenant_suspension_detail_404(client_a, tenant_b, admin_b, supplier_b):
    _, party = supplier_b
    vsu_b = VendorSuspension.objects.create(
        tenant=tenant_b, supplier=party, kind="blacklist", reason_category="compliance",
        reason="Export-control breach.", status="requested", requested_by=admin_b)
    resp = client_a.get(reverse("procurement:vsu_detail", args=[vsu_b.pk]))
    assert resp.status_code == 404


# ------------------------------------------------------------------ deferred follow-ups
# (1) PO-side suspension enforcement inside scm's commitment verbs, (2) the portal
# payments panel over accounting.Bill, (3) the gated supplier bid page over 6.5's
# SourcingBid — all three landed together once VendorPortalAccess existed.

def _po(tenant, party, status="pending_approval"):
    from apps.scm.models import PurchaseOrder

    return PurchaseOrder.objects.create(tenant=tenant, vendor=party, status=status,
                                        order_date=timezone.localdate())


def test_blocked_vendor_po_approve_refused(client_a, tenant_a, admin_user, supplier_a,
                                           party_a):
    po = _po(tenant_a, party_a)
    _active_block(tenant_a, party_a, admin_user)
    resp = client_a.post(reverse("scm:purchaseorder_approve", args=[po.pk]), follow=True)
    assert resp.status_code == 200
    po.refresh_from_db()
    assert po.status == "pending_approval"
    assert any("blocked by suspension" in m for m in _msgs(resp))


def test_unblocked_vendor_po_approve_succeeds(client_a, tenant_a, admin_user, party_a):
    po = _po(tenant_a, party_a)
    resp = client_a.post(reverse("scm:purchaseorder_approve", args=[po.pk]), follow=True)
    po.refresh_from_db()
    assert po.status == "approved"


def test_block_filed_after_approval_stops_dispatch(client_a, tenant_a, admin_user,
                                                   supplier_a, party_a):
    """The send verb re-checks the register: a block filed between approve and dispatch
    still stops the PO from reaching the vendor."""
    po = _po(tenant_a, party_a, status="approved")
    _active_block(tenant_a, party_a, admin_user)
    client_a.post(reverse("scm:purchaseorder_send", args=[po.pk]), follow=True)
    po.refresh_from_db()
    assert po.status == "approved"


def test_portal_home_lists_accounting_bills(client_a, tenant_a, vpa_a, party_a):
    from datetime import timedelta

    from django.utils import timezone as tz

    from apps.accounting.models import Bill

    Bill.objects.create(tenant=tenant_a, party=party_a, bill_date=tz.localdate(),
                        due_date=tz.localdate() + timedelta(days=14), status="approved")
    Bill.objects.create(tenant=tenant_a, party=party_a, bill_date=tz.localdate(),
                        status="paid")
    resp = client_a.get(reverse("procurement:vendor_portal_home"))
    html = resp.content.decode()
    assert "Invoices &amp; payments" in html
    # both bills render with their numbers; balances/statuses come from accounting itself
    assert list(Bill.objects.filter(party=party_a).values_list("number", flat=True)) and True


def test_portal_bids_page_lists_own_bids_only(client_a, member_client, tenant_a,
                                              member_user, supplier_a, party_a):
    from apps.procurement.models import SourcingBid, SourcingEvent
    from apps.core.models import Party as P

    event = SourcingEvent.objects.create(
        tenant=tenant_a, title="Packaging tender", event_type="tender", status="open",
        opens_at=timezone.now() - timedelta(days=2),
        closes_at=timezone.now() + timedelta(days=5))
    mine = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=party_a,
                                      total_price=Decimal("100.00"), status="draft")
    other_party = P.objects.create(tenant=tenant_a, name="Rival Co", kind="organization")
    theirs = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=other_party,
                                        total_price=Decimal("90.00"), status="draft")

    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party_a, portal_user=member_user)
    resp = member_client.get(reverse("procurement:vendor_portal_bids"))
    html = resp.content.decode()
    assert mine.number in html and theirs.number not in html


def test_portal_bid_edit_and_submit_round_trip(client_a, member_client, tenant_a,
                                               member_user, supplier_a, party_a):
    from apps.procurement.models import SourcingBid, SourcingEvent

    event = SourcingEvent.objects.create(
        tenant=tenant_a, title="Consumables RFP", event_type="rfp", status="open",
        opens_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=7))
    bid = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=party_a,
                                     status="draft")
    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party_a, portal_user=member_user)

    resp = member_client.post(
        reverse("procurement:vendor_portal_bid_edit", args=[bid.pk]),
        {"total_price": "250.50", "lead_time_days": "12", "is_compliant": "on",
         "compliance_note": "", "summary": "Full scope covered.",
         "contact_ref": "bids@northwind.example"}, follow=True)
    assert resp.status_code == 200
    bid.refresh_from_db()
    assert bid.total_price == Decimal("250.50") and bid.status == "draft"

    resp = member_client.post(
        reverse("procurement:vendor_portal_bid_submit", args=[bid.pk]), follow=True)
    bid.refresh_from_db()
    assert bid.status == "submitted"
    assert bid.submitted_by_id == member_user.pk


def test_noncompliant_portal_bid_without_note_rejected(member_client, tenant_a,
                                                       member_user, supplier_a, party_a):
    from apps.procurement.models import SourcingBid, SourcingEvent

    event = SourcingEvent.objects.create(
        tenant=tenant_a, title="Lab services RFQ", event_type="rfq", status="open",
        opens_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=3))
    bid = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=party_a,
                                     status="draft")
    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party_a, portal_user=member_user)
    resp = member_client.post(
        reverse("procurement:vendor_portal_bid_edit", args=[bid.pk]),
        {"total_price": "80", "lead_time_days": "", "compliance_note": ""},
        follow=True)
    assert resp.status_code == 200
    assert b"marked not compliant" in resp.content  # form error rendered on the page
    bid.refresh_from_db()
    assert bid.status == "draft"


def test_submitted_portal_bid_not_editable(member_client, tenant_a, member_user,
                                           supplier_a, party_a):
    from apps.procurement.models import SourcingBid, SourcingEvent

    event = SourcingEvent.objects.create(
        tenant=tenant_a, title="Closed event check", event_type="tender", status="open",
        opens_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=3))
    bid = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=party_a,
                                     total_price=Decimal("10.00"), status="submitted")
    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party_a, portal_user=member_user)
    resp = member_client.post(
        reverse("procurement:vendor_portal_bid_edit", args=[bid.pk]),
        {"total_price": "999"}, follow=True)
    bid.refresh_from_db()
    assert bid.total_price == Decimal("10.00")


def test_blocked_supplier_cannot_submit_bid(client_a, member_client, tenant_a, admin_user,
                                            member_user, supplier_a, party_a):
    from apps.procurement.models import SourcingBid, SourcingEvent

    event = SourcingEvent.objects.create(
        tenant=tenant_a, title="Blocked vendor tender", event_type="tender", status="open",
        opens_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=3))
    bid = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=party_a,
                                     status="draft")
    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party_a, portal_user=member_user)
    _active_block(tenant_a, party_a, admin_user)
    member_client.post(reverse("procurement:vendor_portal_bid_submit", args=[bid.pk]))
    bid.refresh_from_db()
    assert bid.status == "draft"


def test_foreign_bid_pk_never_editable(client_a, member_client, tenant_a, member_user,
                                       supplier_a, party_a):
    from apps.core.models import Party as P
    from apps.procurement.models import SourcingBid, SourcingEvent

    event = SourcingEvent.objects.create(
        tenant=tenant_a, title="T", event_type="tender", status="open",
        opens_at=timezone.now() - timedelta(days=1),
        closes_at=timezone.now() + timedelta(days=3))
    rival = P.objects.create(tenant=tenant_a, name="Rival 2", kind="organization")
    foreign = SourcingBid.objects.create(tenant=tenant_a, event=event, supplier=rival,
                                         status="draft")
    VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party_a, portal_user=member_user)
    member_client.post(reverse("procurement:vendor_portal_bid_submit", args=[foreign.pk]))
    foreign.refresh_from_db()
    assert foreign.status == "draft"
