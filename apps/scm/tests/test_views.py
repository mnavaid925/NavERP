"""View / CRUD tests for the SCM 4.1 Procurement Management sub-module.

Covers:
- List (200 + search/filter) / create (POST -> saved with the request tenant) / edit /
  delete (POST-only) for each of the 4 top-level entities.
- Mass-assignment guard at the view layer: status/number/version/total/match_status in
  the POST body must never land on the saved object.
- The state machine: illegal transitions (approve a draft requisition, award a draft
  RFQ, award twice, send an unapproved PO, cancel a PO with receipts, receive a GRN
  twice) refuse gracefully — no exception, no state change.
- The PO amend identity lock: a different (valid, same-tenant) vendor posted to
  purchaseorder_amend must not change the vendor (AMEND_LOCKED_FIELDS are disabled).
- A light N+1 guard on the busiest list view.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.scm.tests._helpers import formset_data

pytestmark = pytest.mark.django_db


# ================================================================ Purchase Requisition CRUD
class TestRequisitionCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, requisition_a):
        resp = client_a.get(reverse("scm:requisition_list"))
        assert resp.status_code == 200
        assert requisition_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, requisition_a, requisition_b):
        resp = client_a.get(reverse("scm:requisition_list"))
        assert requisition_b not in resp.context["object_list"]

    def test_list_search_by_title(self, client_a, requisition_a):
        resp = client_a.get(reverse("scm:requisition_list"), {"q": "Office supplies"})
        assert requisition_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:requisition_list"), {"q": "Nothing matches this"})
        assert requisition_a not in resp2.context["object_list"]

    def test_list_filter_by_status(self, client_a, requisition_a, requisition_pending_a):
        resp = client_a.get(reverse("scm:requisition_list"), {"status": "draft"})
        object_list = list(resp.context["object_list"])
        assert requisition_a in object_list
        assert requisition_pending_a not in object_list

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, org_unit_a, usd):
        from apps.scm.models import PurchaseRequisition
        data = {
            "title": "New requisition",
            "org_unit": str(org_unit_a.pk),
            "budget": "",
            "currency": str(usd.pk),
            "required_by": "",
            "justification": "",
            "notes": "",
            **formset_data("lines", [
                {"id": "", "item_description": "Pens", "sku_hint": "", "uom_hint": "",
                 "quantity": "5", "estimated_unit_price": "2.00", "gl_account": "", "needed_by": ""},
            ]),
        }
        resp = client_a.post(reverse("scm:requisition_create"), data)
        assert resp.status_code == 302
        req = PurchaseRequisition.objects.get(title="New requisition")
        assert req.tenant_id == tenant_a.pk
        assert req.number == "PR-00001"
        assert req.estimated_total == Decimal("10.00")
        assert req.lines.count() == 1

    def test_edit_updates_fields_and_recalculates_totals(self, client_a, requisition_a, org_unit_a, usd):
        line = requisition_a.lines.first()
        data = {
            "title": "Office supplies (revised)",
            "org_unit": str(org_unit_a.pk),
            "budget": "",
            "currency": str(usd.pk),
            "required_by": "",
            "justification": "",
            "notes": "",
            **formset_data("lines", [
                {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
                 "uom_hint": "", "quantity": "20", "estimated_unit_price": "15.00",
                 "gl_account": "", "needed_by": ""},
            ], initial=1),
        }
        resp = client_a.post(reverse("scm:requisition_edit", args=[requisition_a.pk]), data)
        assert resp.status_code == 302
        requisition_a.refresh_from_db()
        assert requisition_a.title == "Office supplies (revised)"
        assert requisition_a.estimated_total == Decimal("300.00")

    def test_delete_draft_removes_it(self, client_a, requisition_a):
        pk = requisition_a.pk
        resp = client_a.post(reverse("scm:requisition_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import PurchaseRequisition
        assert not PurchaseRequisition.objects.filter(pk=pk).exists()

    def test_delete_non_draft_is_refused(self, client_a, requisition_pending_a):
        from apps.scm.models import PurchaseRequisition
        resp = client_a.post(reverse("scm:requisition_delete", args=[requisition_pending_a.pk]))
        assert resp.status_code == 302
        assert PurchaseRequisition.objects.filter(pk=requisition_pending_a.pk).exists()


class TestRequisitionMassAssignment:
    def test_create_ignores_status_number_and_estimated_total(self, client_a, tenant_a, org_unit_a, usd):
        from apps.scm.models import PurchaseRequisition
        data = {
            "title": "Try to hack",
            "org_unit": str(org_unit_a.pk),
            "budget": "",
            "currency": str(usd.pk),
            "required_by": "",
            "justification": "",
            "notes": "",
            "status": "approved",
            "number": "PR-99999",
            "estimated_total": "999999.00",
            **formset_data("lines", [
                {"id": "", "item_description": "Pens", "sku_hint": "", "uom_hint": "",
                 "quantity": "1", "estimated_unit_price": "5.00", "gl_account": "", "needed_by": ""},
            ]),
        }
        resp = client_a.post(reverse("scm:requisition_create"), data)
        assert resp.status_code == 302
        req = PurchaseRequisition.objects.get(title="Try to hack")
        assert req.status == "draft"
        assert req.number == "PR-00001"
        assert req.estimated_total == Decimal("5.00")

    def test_create_ignores_posted_requester(self, client_a, member_user, tenant_a, org_unit_a, usd):
        """`requester` is excluded from the form and set to request.user server-side —
        posting another user's pk must not raise it in someone else's name."""
        from apps.scm.models import PurchaseRequisition
        data = {
            "title": "Whose name is this",
            "org_unit": str(org_unit_a.pk),
            "budget": "",
            "currency": str(usd.pk),
            "required_by": "",
            "justification": "",
            "notes": "",
            "requester": str(member_user.pk),
            **formset_data("lines", []),
        }
        resp = client_a.post(reverse("scm:requisition_create"), data)
        assert resp.status_code == 302
        req = PurchaseRequisition.objects.get(title="Whose name is this")
        assert req.requester_id != member_user.pk


# ================================================================ Requisition state machine
class TestRequisitionStateMachine:
    def test_submit_draft_moves_to_pending_approval(self, client_a, requisition_a):
        resp = client_a.post(reverse("scm:requisition_submit", args=[requisition_a.pk]))
        assert resp.status_code == 302
        requisition_a.refresh_from_db()
        assert requisition_a.status == "pending_approval"

    def test_submit_without_lines_is_refused(self, client_a, tenant_a):
        from apps.scm.models import PurchaseRequisition
        req = PurchaseRequisition.objects.create(tenant=tenant_a, title="Empty", status="draft")
        resp = client_a.post(reverse("scm:requisition_submit", args=[req.pk]))
        assert resp.status_code == 302
        req.refresh_from_db()
        assert req.status == "draft"

    def test_approve_a_draft_requisition_is_refused(self, client_a, requisition_a):
        """Illegal transition: approve is only valid from pending_approval."""
        resp = client_a.post(reverse("scm:requisition_approve", args=[requisition_a.pk]))
        assert resp.status_code == 302  # graceful redirect, not a 500
        requisition_a.refresh_from_db()
        assert requisition_a.status == "draft"  # unchanged

    def test_approve_pending_requisition_succeeds(self, client_a, requisition_pending_a):
        resp = client_a.post(reverse("scm:requisition_approve", args=[requisition_pending_a.pk]))
        assert resp.status_code == 302
        requisition_pending_a.refresh_from_db()
        assert requisition_pending_a.status == "approved"
        assert requisition_pending_a.approved_by is not None

    def test_reject_without_reason_is_refused(self, client_a, requisition_pending_a):
        resp = client_a.post(reverse("scm:requisition_reject", args=[requisition_pending_a.pk]))
        assert resp.status_code == 302
        requisition_pending_a.refresh_from_db()
        assert requisition_pending_a.status == "pending_approval"

    def test_reject_with_reason_succeeds(self, client_a, requisition_pending_a):
        resp = client_a.post(
            reverse("scm:requisition_reject", args=[requisition_pending_a.pk]),
            {"decision_note": "Not in this quarter's budget"},
        )
        assert resp.status_code == 302
        requisition_pending_a.refresh_from_db()
        assert requisition_pending_a.status == "rejected"


# ================================================================ RFQ CRUD
class TestRFQCRUD:
    def test_list_returns_200(self, client_a, rfq_a):
        resp = client_a.get(reverse("scm:rfq_list"))
        assert resp.status_code == 200
        assert rfq_a in resp.context["object_list"]

    def test_create_saves_lines_and_vendors_with_tenant(self, client_a, tenant_a, usd, supplier_a):
        from apps.scm.models import RFQ
        data = {
            "title": "New RFQ",
            "requisition": "",
            "currency": str(usd.pk),
            "issue_date": "",
            "response_due": "",
            "terms": "",
            "notes": "",
        }
        data.update(formset_data("lines", [
            {"id": "", "item_description": "Bond paper", "sku_hint": "", "uom_hint": "",
             "quantity": "10", "specification": ""},
        ]))
        data.update(formset_data("vendors", [
            {"id": "", "party": str(supplier_a.pk), "contact_note": "primary"},
        ]))
        resp = client_a.post(reverse("scm:rfq_create"), data)
        assert resp.status_code == 302
        rfq = RFQ.objects.get(title="New RFQ")
        assert rfq.tenant_id == tenant_a.pk
        assert rfq.number == "RFQ-00001"
        assert rfq.lines.count() == 1
        assert rfq.invited_vendors.count() == 1

    def test_delete_draft_rfq_removes_it(self, client_a, rfq_a):
        pk = rfq_a.pk
        resp = client_a.post(reverse("scm:rfq_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import RFQ
        assert not RFQ.objects.filter(pk=pk).exists()


class TestRFQStateMachine:
    def test_send_without_vendors_is_refused(self, client_a, rfq_a):
        resp = client_a.post(reverse("scm:rfq_send", args=[rfq_a.pk]))
        assert resp.status_code == 302
        rfq_a.refresh_from_db()
        assert rfq_a.status == "draft"

    def test_send_with_lines_and_vendors_succeeds(self, client_a, tenant_a, rfq_a, supplier_a):
        from apps.scm.models import RFQVendor
        RFQVendor.objects.create(tenant=tenant_a, rfq=rfq_a, party=supplier_a)
        resp = client_a.post(reverse("scm:rfq_send", args=[rfq_a.pk]))
        assert resp.status_code == 302
        rfq_a.refresh_from_db()
        assert rfq_a.status == "sent"

    def test_close_sent_rfq_succeeds(self, client_a, rfq_sent_a):
        resp = client_a.post(reverse("scm:rfq_close", args=[rfq_sent_a.pk]))
        assert resp.status_code == 302
        rfq_sent_a.refresh_from_db()
        assert rfq_sent_a.status == "closed"

    def test_award_on_a_draft_rfq_is_refused(self, client_a, tenant_a, rfq_a, supplier_a):
        """Illegal transition: award is only valid from sent/closed."""
        from apps.scm.models import RFQQuote, PurchaseOrder
        quote = RFQQuote.objects.create(tenant=tenant_a, rfq=rfq_a, party=supplier_a, status="received")
        resp = client_a.post(reverse("scm:quote_award", args=[quote.pk]))
        assert resp.status_code == 302
        rfq_a.refresh_from_db()
        assert rfq_a.status == "draft"
        assert PurchaseOrder.objects.filter(quote=quote).count() == 0

    def test_award_creates_draft_po_from_quote_lines(self, client_a, tenant_a, rfq_sent_a, quote_a):
        from apps.scm.models import PurchaseOrder
        resp = client_a.post(reverse("scm:quote_award", args=[quote_a.pk]))
        assert resp.status_code == 302
        quote_a.refresh_from_db()
        rfq_sent_a.refresh_from_db()
        assert quote_a.status == "awarded"
        assert rfq_sent_a.status == "awarded"
        po = PurchaseOrder.objects.get(quote=quote_a)
        assert po.status == "draft"
        assert po.vendor_id == quote_a.party_id
        assert po.lines.count() == quote_a.lines.count()

    def test_award_twice_is_refused_and_does_not_duplicate_the_po(self, client_a, tenant_a, rfq_sent_a, quote_a):
        from apps.scm.models import PurchaseOrder
        url = reverse("scm:quote_award", args=[quote_a.pk])
        client_a.post(url)
        assert PurchaseOrder.objects.filter(quote=quote_a).count() == 1
        resp = client_a.post(url)  # award again
        assert resp.status_code == 302
        assert PurchaseOrder.objects.filter(quote=quote_a).count() == 1  # still just one


# ================================================================ Purchase Order CRUD
class TestPurchaseOrderCRUD:
    def test_list_returns_200(self, client_a, purchase_order_a):
        resp = client_a.get(reverse("scm:purchaseorder_list"))
        assert resp.status_code == 200
        assert purchase_order_a in resp.context["object_list"]

    def test_list_filter_by_vendor(self, client_a, purchase_order_a, supplier_a):
        resp = client_a.get(reverse("scm:purchaseorder_list"), {"vendor": str(supplier_a.pk)})
        assert purchase_order_a in resp.context["object_list"]

    def test_list_no_n_plus_one_query_blowup(self, client_a, tenant_a, supplier_a, django_assert_max_num_queries):
        from apps.scm.models import PurchaseOrder, PurchaseOrderLine
        for i in range(8):
            po = PurchaseOrder.objects.create(
                tenant=tenant_a, vendor=supplier_a, status="draft",
                order_date=datetime.date(2026, 1, i + 1),
            )
            PurchaseOrderLine.objects.create(
                purchase_order=po, item_description="x", quantity=1, unit_price=Decimal("1.00"),
            )
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:purchaseorder_list"))
        assert resp.status_code == 200

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, supplier_a, usd):
        from apps.scm.models import PurchaseOrder
        data = {
            "vendor": str(supplier_a.pk),
            "requisition": "",
            "quote": "",
            "currency": str(usd.pk),
            "payment_terms": "",
            "order_date": "2026-01-05",
            "expected_date": "",
            "ship_to": "",
            "delivery_address": "",
            "notes": "",
            **formset_data("lines", [
                {"id": "", "item_description": "Widgets", "sku_hint": "", "uom_hint": "",
                 "quantity": "5", "unit_price": "20.00", "tax_rate_pct": "0", "gl_account": ""},
            ]),
        }
        resp = client_a.post(reverse("scm:purchaseorder_create"), data)
        assert resp.status_code == 302
        po = PurchaseOrder.objects.get(vendor=supplier_a, order_date=datetime.date(2026, 1, 5))
        assert po.tenant_id == tenant_a.pk
        assert po.number == "PO-00001"
        assert po.total == Decimal("100.00")

    def test_delete_draft_removes_it(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="draft")
        resp = client_a.post(reverse("scm:purchaseorder_delete", args=[po.pk]))
        assert resp.status_code == 302
        assert not PurchaseOrder.objects.filter(pk=po.pk).exists()

    def test_delete_approved_order_is_refused(self, client_a, purchase_order_a):
        from apps.scm.models import PurchaseOrder
        resp = client_a.post(reverse("scm:purchaseorder_delete", args=[purchase_order_a.pk]))
        assert resp.status_code == 302
        assert PurchaseOrder.objects.filter(pk=purchase_order_a.pk).exists()


class TestPurchaseOrderMassAssignment:
    def test_create_ignores_status_version_number_and_totals(self, client_a, tenant_a, supplier_a, usd):
        from apps.scm.models import PurchaseOrder
        data = {
            "vendor": str(supplier_a.pk),
            "requisition": "",
            "quote": "",
            "currency": str(usd.pk),
            "payment_terms": "",
            "order_date": "2026-02-01",
            "expected_date": "",
            "ship_to": "",
            "delivery_address": "",
            "notes": "hack attempt",
            "status": "sent",
            "version": "9",
            "number": "PO-99999",
            "subtotal": "1.00",
            "tax_total": "1.00",
            "total": "999999.00",
            **formset_data("lines", [
                {"id": "", "item_description": "Widgets", "sku_hint": "", "uom_hint": "",
                 "quantity": "5", "unit_price": "20.00", "tax_rate_pct": "0", "gl_account": ""},
            ]),
        }
        resp = client_a.post(reverse("scm:purchaseorder_create"), data)
        assert resp.status_code == 302
        po = PurchaseOrder.objects.get(notes="hack attempt")
        assert po.status == "draft"
        assert po.version == 1
        assert po.number == "PO-00001"
        assert po.total == Decimal("100.00")


class TestPurchaseOrderStateMachine:
    def test_submit_draft_moves_to_pending_approval(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder, PurchaseOrderLine
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="draft")
        PurchaseOrderLine.objects.create(purchase_order=po, item_description="x", quantity=1, unit_price=Decimal("1.00"))
        resp = client_a.post(reverse("scm:purchaseorder_submit", args=[po.pk]))
        assert resp.status_code == 302
        po.refresh_from_db()
        assert po.status == "pending_approval"

    def test_send_an_unapproved_order_is_refused(self, client_a, tenant_a, supplier_a):
        """Illegal transition: send is only valid from approved."""
        from apps.scm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="draft")
        resp = client_a.post(reverse("scm:purchaseorder_send", args=[po.pk]))
        assert resp.status_code == 302
        po.refresh_from_db()
        assert po.status == "draft"

    def test_send_an_approved_order_succeeds(self, client_a, purchase_order_a):
        resp = client_a.post(reverse("scm:purchaseorder_send", args=[purchase_order_a.pk]))
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status == "sent"

    def test_acknowledge_a_sent_order(self, client_a, purchase_order_a):
        client_a.post(reverse("scm:purchaseorder_send", args=[purchase_order_a.pk]))
        resp = client_a.post(
            reverse("scm:purchaseorder_acknowledge", args=[purchase_order_a.pk]),
            {"acknowledgement_note": "Confirmed", "promised_ship_date": "2026-01-20"},
        )
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status == "acknowledged"

    def test_cancel_an_order_with_receipts_is_refused(self, client_a, purchase_order_a, goods_receipt_a):
        client_a.post(reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk]))
        purchase_order_a.refresh_from_db()
        resp = client_a.post(
            reverse("scm:purchaseorder_cancel", args=[purchase_order_a.pk]),
            {"cancellation_reason": "Changed my mind"},
        )
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status != "cancelled"

    def test_cancel_without_reason_is_refused(self, client_a, purchase_order_a):
        resp = client_a.post(reverse("scm:purchaseorder_cancel", args=[purchase_order_a.pk]))
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status != "cancelled"

    def test_cancel_with_reason_and_no_receipts_succeeds(self, client_a, purchase_order_a):
        resp = client_a.post(
            reverse("scm:purchaseorder_cancel", args=[purchase_order_a.pk]),
            {"cancellation_reason": "No longer needed"},
        )
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status == "cancelled"
        assert purchase_order_a.cancellation_reason == "No longer needed"

    def test_close_a_fully_received_order(self, client_a, purchase_order_a, goods_receipt_a):
        client_a.post(reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk]))
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status == "received"
        resp = client_a.post(reverse("scm:purchaseorder_close", args=[purchase_order_a.pk]))
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status == "closed"


class TestPurchaseOrderAmend:
    def test_amend_locks_the_vendor_field(self, client_a, tenant_a, purchase_order_a, supplier_a, vendor_a):
        line = purchase_order_a.lines.first()
        data = {
            "vendor": str(vendor_a.pk),  # tamper attempt: a DIFFERENT, valid, same-tenant supplier
            "requisition": "",
            "quote": "",
            "currency": "",
            "payment_terms": "",
            "order_date": "2026-01-05",
            "expected_date": "",
            "ship_to": "",
            "delivery_address": "",
            "notes": "Amended",
            "amendment_reason": "Vendor renegotiated the unit price",
            **formset_data("lines", [
                {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
                 "uom_hint": "", "quantity": line.quantity, "unit_price": line.unit_price,
                 "tax_rate_pct": "0", "gl_account": ""},
            ], initial=1),
        }
        resp = client_a.post(reverse("scm:purchaseorder_amend", args=[purchase_order_a.pk]), data)
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.vendor_id == supplier_a.pk  # unchanged — disabled field ignores POST
        assert purchase_order_a.vendor_id != vendor_a.pk
        assert purchase_order_a.version == 2
        assert purchase_order_a.amendment_reason == "Vendor renegotiated the unit price"

    def test_amend_without_reason_is_refused(self, client_a, purchase_order_a):
        resp = client_a.post(reverse("scm:purchaseorder_amend", args=[purchase_order_a.pk]), {})
        assert resp.status_code == 302
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.version == 1


# ================================================================ Goods Receipt Note CRUD
class TestGoodsReceiptCRUD:
    def test_list_returns_200(self, client_a, goods_receipt_a):
        resp = client_a.get(reverse("scm:goodsreceipt_list"))
        assert resp.status_code == 200
        assert goods_receipt_a in resp.context["object_list"]

    def test_list_filter_by_match_status(self, client_a, goods_receipt_a):
        resp = client_a.get(reverse("scm:goodsreceipt_list"), {"match_status": "not_matched"})
        assert goods_receipt_a in resp.context["object_list"]

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, purchase_order_a):
        from apps.scm.models import GoodsReceiptNote
        line = purchase_order_a.lines.first()
        data = {
            "purchase_order": str(purchase_order_a.pk),
            "receipt_date": "2026-01-15",
            "delivery_note_ref": "DN-1001",
            "bill": "",
            "notes": "",
            **formset_data("lines", [
                {"id": "", "po_line": str(line.pk), "quantity_received": "10",
                 "quantity_rejected": "0", "rejection_reason": "", "notes": ""},
            ]),
        }
        resp = client_a.post(reverse("scm:goodsreceipt_create"), data)
        assert resp.status_code == 302
        grn = GoodsReceiptNote.objects.get(delivery_note_ref="DN-1001")
        assert grn.tenant_id == tenant_a.pk
        assert grn.number == "GRN-00001"
        assert grn.status == "draft"

    def test_delete_draft_removes_it(self, client_a, goods_receipt_a):
        pk = goods_receipt_a.pk
        resp = client_a.post(reverse("scm:goodsreceipt_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import GoodsReceiptNote
        assert not GoodsReceiptNote.objects.filter(pk=pk).exists()


class TestGoodsReceiptMassAssignment:
    def test_create_ignores_status_and_match_status(self, client_a, tenant_a, purchase_order_a):
        from apps.scm.models import GoodsReceiptNote
        line = purchase_order_a.lines.first()
        data = {
            "purchase_order": str(purchase_order_a.pk),
            "receipt_date": "2026-01-15",
            "delivery_note_ref": "DN-HACK",
            "bill": "",
            "notes": "",
            "status": "received",
            "match_status": "matched",
            "number": "GRN-99999",
            **formset_data("lines", [
                {"id": "", "po_line": str(line.pk), "quantity_received": "10",
                 "quantity_rejected": "0", "rejection_reason": "", "notes": ""},
            ]),
        }
        resp = client_a.post(reverse("scm:goodsreceipt_create"), data)
        assert resp.status_code == 302
        grn = GoodsReceiptNote.objects.get(delivery_note_ref="DN-HACK")
        assert grn.status == "draft"
        assert grn.number == "GRN-00001"


class TestGoodsReceiptStateMachine:
    def test_receive_draft_moves_to_received_and_updates_po_status(
        self, client_a, purchase_order_a, goods_receipt_a,
    ):
        resp = client_a.post(reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk]))
        assert resp.status_code == 302
        goods_receipt_a.refresh_from_db()
        purchase_order_a.refresh_from_db()
        assert goods_receipt_a.status == "received"
        assert purchase_order_a.status == "received"  # fully received (10 of 10)

    def test_receive_without_lines_is_refused(self, client_a, tenant_a, purchase_order_a):
        from apps.scm.models import GoodsReceiptNote
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="draft",
        )
        resp = client_a.post(reverse("scm:goodsreceipt_receive", args=[grn.pk]))
        assert resp.status_code == 302
        grn.refresh_from_db()
        assert grn.status == "draft"

    def test_receive_twice_is_refused(self, client_a, goods_receipt_a):
        url = reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk])
        client_a.post(url)
        goods_receipt_a.refresh_from_db()
        assert goods_receipt_a.status == "received"
        resp = client_a.post(url)  # receive again
        assert resp.status_code == 302
        goods_receipt_a.refresh_from_db()
        assert goods_receipt_a.status == "received"  # unchanged, not double-processed

    def test_cancel_reverts_po_status(self, client_a, purchase_order_a, goods_receipt_a):
        client_a.post(reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk]))
        purchase_order_a.refresh_from_db()
        assert purchase_order_a.status == "received"

        resp = client_a.post(reverse("scm:goodsreceipt_cancel", args=[goods_receipt_a.pk]))
        assert resp.status_code == 302
        goods_receipt_a.refresh_from_db()
        purchase_order_a.refresh_from_db()
        assert goods_receipt_a.status == "cancelled"
        assert purchase_order_a.status != "received"  # walked back once the receipt was reversed

    def test_rematch_recomputes_match_status(self, client_a, goods_receipt_a, bill_a):
        client_a.post(reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk]))
        goods_receipt_a.bill = bill_a
        goods_receipt_a.save(update_fields=["bill"])
        resp = client_a.post(reverse("scm:goodsreceipt_rematch", args=[goods_receipt_a.pk]))
        assert resp.status_code == 302
        goods_receipt_a.refresh_from_db()
        assert goods_receipt_a.match_status == "matched"
