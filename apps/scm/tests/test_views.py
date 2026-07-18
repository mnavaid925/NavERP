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


# ================================================================================================
# SCM 4.2 Supplier Relationship Management
# ================================================================================================

# ================================================================ SupplierProfile CRUD
class TestSupplierProfileCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, supplier_profile_a):
        resp = client_a.get(reverse("scm:supplierprofile_list"))
        assert resp.status_code == 200
        assert supplier_profile_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, supplier_profile_a, supplier_profile_b):
        resp = client_a.get(reverse("scm:supplierprofile_list"))
        assert supplier_profile_b not in resp.context["object_list"]

    def test_list_search_by_category(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        sp = SupplierProfile.objects.create(tenant=tenant_a, party=supplier_a, category="Packaging")
        resp = client_a.get(reverse("scm:supplierprofile_list"), {"q": "Packaging"})
        assert sp in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:supplierprofile_list"), {"q": "Nothing matches this"})
        assert sp not in resp2.context["object_list"]

    def test_list_filter_by_onboarding_status(self, client_a, tenant_a, supplier_profile_a, vendor_a):
        from apps.scm.models import SupplierProfile
        other = SupplierProfile.objects.create(
            tenant=tenant_a, party=vendor_a, onboarding_status="due_diligence",
        )
        resp = client_a.get(reverse("scm:supplierprofile_list"), {"onboarding_status": "draft"})
        object_list = list(resp.context["object_list"])
        assert supplier_profile_a in object_list
        assert other not in object_list

    def test_list_junk_status_filter_returns_200_not_500(self, client_a, supplier_profile_a):
        resp = client_a.get(reverse("scm:supplierprofile_list"), {"onboarding_status": "not-a-real-status"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, supplier_profile_a):
        resp = client_a.get(reverse("scm:supplierprofile_list"), {"page": "999"})
        assert resp.status_code == 200

    def _valid_data(self, supplier_a, **overrides):
        data = {
            "party": str(supplier_a.pk), "tier": "transactional", "category": "",
            "legal_name": "", "tax_registration": "", "website": "",
            "primary_contact_name": "", "primary_contact_email": "", "primary_contact_phone": "",
            "country": "", "year_established": "",
            "dd_financials_verified": "", "dd_compliance_verified": "", "dd_insurance_verified": "",
            "dd_quality_cert_verified": "", "dd_references_checked": "", "notes": "",
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        data = self._valid_data(supplier_a, tier="preferred", category="Packaging materials")
        resp = client_a.post(reverse("scm:supplierprofile_create"), data)
        assert resp.status_code == 302
        sp = SupplierProfile.objects.get(party=supplier_a)
        assert sp.tenant_id == tenant_a.pk
        assert sp.tier == "preferred"

    def test_create_ignores_posted_onboarding_status_and_decision_fields(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        data = self._valid_data(supplier_a, onboarding_status="approved", decision_note="hacked in")
        resp = client_a.post(reverse("scm:supplierprofile_create"), data)
        assert resp.status_code == 302
        sp = SupplierProfile.objects.get(party=supplier_a)
        assert sp.onboarding_status == "draft"
        assert sp.decision_note == ""

    def test_edit_updates_fields(self, client_a, supplier_profile_a, supplier_a):
        data = self._valid_data(supplier_a, tier="strategic", category="Updated category")
        resp = client_a.post(reverse("scm:supplierprofile_edit", args=[supplier_profile_a.pk]), data)
        assert resp.status_code == 302
        supplier_profile_a.refresh_from_db()
        assert supplier_profile_a.tier == "strategic"
        assert supplier_profile_a.category == "Updated category"

    def test_edit_blocked_once_approved(self, client_a, supplier_profile_dd_a):
        client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk]))
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "approved"
        resp = client_a.get(reverse("scm:supplierprofile_edit", args=[supplier_profile_dd_a.pk]))
        assert resp.status_code == 302  # redirected to detail, not the form

    def test_detail_returns_200(self, client_a, supplier_profile_a):
        resp = client_a.get(reverse("scm:supplierprofile_detail", args=[supplier_profile_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == supplier_profile_a

    def test_delete_draft_removes_it(self, client_a, supplier_profile_a):
        pk = supplier_profile_a.pk
        resp = client_a.post(reverse("scm:supplierprofile_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import SupplierProfile
        assert not SupplierProfile.objects.filter(pk=pk).exists()

    def test_delete_non_draft_is_refused(self, client_a, supplier_profile_dd_a):
        from apps.scm.models import SupplierProfile
        resp = client_a.post(reverse("scm:supplierprofile_delete", args=[supplier_profile_dd_a.pk]))
        assert resp.status_code == 302
        assert SupplierProfile.objects.filter(pk=supplier_profile_dd_a.pk).exists()

    def test_get_delete_returns_405_and_does_not_delete(self, client_a, supplier_profile_a):
        resp = client_a.get(reverse("scm:supplierprofile_delete", args=[supplier_profile_a.pk]))
        assert resp.status_code == 405
        from apps.scm.models import SupplierProfile
        assert SupplierProfile.objects.filter(pk=supplier_profile_a.pk).exists()


# ================================================================ SupplierProfile onboarding lifecycle (priority)
class TestSupplierProfileLifecycle:
    def test_submit_draft_moves_to_due_diligence(self, client_a, supplier_profile_a):
        resp = client_a.post(reverse("scm:supplierprofile_submit", args=[supplier_profile_a.pk]))
        assert resp.status_code == 302
        supplier_profile_a.refresh_from_db()
        assert supplier_profile_a.onboarding_status == "due_diligence"

    def test_submit_already_decided_is_a_no_op(self, client_a, supplier_profile_dd_a):
        client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk]))
        supplier_profile_dd_a.refresh_from_db()
        resp = client_a.post(reverse("scm:supplierprofile_submit", args=[supplier_profile_dd_a.pk]))
        assert resp.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "approved"  # unchanged

    # ---- Regression: approve source-state guard — draft is NOT a legal source state ----
    def test_approve_from_draft_is_refused_even_with_complete_dd(self, client_a, supplier_profile_a):
        supplier_profile_a.dd_financials_verified = True
        supplier_profile_a.dd_compliance_verified = True
        supplier_profile_a.dd_insurance_verified = True
        supplier_profile_a.dd_quality_cert_verified = True
        supplier_profile_a.dd_references_checked = True
        supplier_profile_a.save()
        resp = client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_a.pk]))
        assert resp.status_code == 302
        supplier_profile_a.refresh_from_db()
        assert supplier_profile_a.onboarding_status == "draft"  # NOT approved

    def test_approve_from_due_diligence_incomplete_is_refused(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        sp = SupplierProfile.objects.create(tenant=tenant_a, party=supplier_a, onboarding_status="due_diligence")
        resp = client_a.post(reverse("scm:supplierprofile_approve", args=[sp.pk]))
        assert resp.status_code == 302
        sp.refresh_from_db()
        assert sp.onboarding_status == "due_diligence"

    def test_approve_from_due_diligence_complete_succeeds(self, client_a, supplier_profile_dd_a):
        resp = client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk]))
        assert resp.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "approved"
        assert supplier_profile_dd_a.approved_by is not None
        assert supplier_profile_dd_a.approved_at is not None

    # ---- Regression: reject is for onboarding only, not an already-approved supplier ----
    def test_reject_on_approved_profile_is_refused(self, client_a, supplier_profile_dd_a):
        client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk]))
        supplier_profile_dd_a.refresh_from_db()
        resp = client_a.post(
            reverse("scm:supplierprofile_reject", args=[supplier_profile_dd_a.pk]),
            {"decision_note": "Changed my mind"},
        )
        assert resp.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "approved"  # unchanged

    def test_reject_without_reason_is_refused(self, client_a, supplier_profile_dd_a):
        resp = client_a.post(reverse("scm:supplierprofile_reject", args=[supplier_profile_dd_a.pk]))
        assert resp.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "due_diligence"

    def test_reject_with_reason_succeeds(self, client_a, supplier_profile_dd_a):
        resp = client_a.post(
            reverse("scm:supplierprofile_reject", args=[supplier_profile_dd_a.pk]),
            {"decision_note": "Failed a background check"},
        )
        assert resp.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "rejected"

    def test_reopen_rejected_profile_sends_to_draft(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        sp = SupplierProfile.objects.create(tenant=tenant_a, party=supplier_a, onboarding_status="rejected")
        resp = client_a.post(reverse("scm:supplierprofile_reopen", args=[sp.pk]))
        assert resp.status_code == 302
        sp.refresh_from_db()
        assert sp.onboarding_status == "draft"

    def test_reopen_non_rejected_is_a_no_op(self, client_a, supplier_profile_a):
        resp = client_a.post(reverse("scm:supplierprofile_reopen", args=[supplier_profile_a.pk]))
        assert resp.status_code == 302
        supplier_profile_a.refresh_from_db()
        assert supplier_profile_a.onboarding_status == "draft"

    def test_suspend_approved_profile_then_reinstate(self, client_a, supplier_profile_dd_a):
        client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk]))
        resp = client_a.post(reverse("scm:supplierprofile_suspend", args=[supplier_profile_dd_a.pk]))
        assert resp.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "suspended"

        resp2 = client_a.post(reverse("scm:supplierprofile_suspend", args=[supplier_profile_dd_a.pk]))
        assert resp2.status_code == 302
        supplier_profile_dd_a.refresh_from_db()
        assert supplier_profile_dd_a.onboarding_status == "approved"  # toggled back

    def test_suspend_a_draft_is_a_no_op(self, client_a, supplier_profile_a):
        resp = client_a.post(reverse("scm:supplierprofile_suspend", args=[supplier_profile_a.pk]))
        assert resp.status_code == 302
        supplier_profile_a.refresh_from_db()
        assert supplier_profile_a.onboarding_status == "draft"


# ================================================================ SupplierScorecard CRUD
class TestScorecardCRUD:
    def test_list_returns_200(self, client_a, scorecard_a):
        resp = client_a.get(reverse("scm:scorecard_list"))
        assert resp.status_code == 200
        assert scorecard_a in resp.context["object_list"]

    def test_list_filter_by_party(self, client_a, scorecard_a, supplier_a):
        resp = client_a.get(reverse("scm:scorecard_list"), {"party": str(supplier_a.pk)})
        assert scorecard_a in resp.context["object_list"]

    def test_list_junk_party_filter_returns_200_not_500(self, client_a, scorecard_a):
        resp = client_a.get(reverse("scm:scorecard_list"), {"party": "abc"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, scorecard_a):
        resp = client_a.get(reverse("scm:scorecard_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_page_2_when_rows_exceed_page_size(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierScorecard
        for i in range(20):
            SupplierScorecard.objects.create(
                tenant=tenant_a, party=supplier_a,
                period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 1, 31),
            )
        resp = client_a.get(reverse("scm:scorecard_list"), {"page": "2"})
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) > 0

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierScorecard
        data = {
            "party": str(supplier_a.pk), "period_start": "2026-01-01", "period_end": "2026-01-31",
            "delivery_score": "", "quality_score": "", "price_score": "", "responsiveness_score": "",
            "manual_override": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:scorecard_create"), data)
        assert resp.status_code == 302
        sc = SupplierScorecard.objects.get(party=supplier_a)
        assert sc.tenant_id == tenant_a.pk
        assert sc.number == "SCR-00001"

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierScorecard
        data = {
            "party": str(supplier_a.pk), "period_start": "2026-01-01", "period_end": "2026-01-31",
            "delivery_score": "", "quality_score": "", "price_score": "", "responsiveness_score": "",
            "manual_override": "", "notes": "",
            "status": "published", "number": "SCR-99999", "overall_score": "99.99",
        }
        resp = client_a.post(reverse("scm:scorecard_create"), data)
        assert resp.status_code == 302
        sc = SupplierScorecard.objects.get(party=supplier_a)
        assert sc.status == "draft"
        assert sc.number == "SCR-00001"

    def test_edit_blocked_once_archived(self, client_a, scorecard_a):
        scorecard_a.status = "archived"
        scorecard_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:scorecard_edit", args=[scorecard_a.pk]))
        assert resp.status_code == 302

    def test_detail_recomputes_overall(self, client_a, scorecard_a):
        scorecard_a.delivery_score = Decimal("80.00")
        scorecard_a.save(update_fields=["delivery_score"])
        resp = client_a.get(reverse("scm:scorecard_detail", args=[scorecard_a.pk]))
        assert resp.status_code == 200
        scorecard_a.refresh_from_db()
        assert scorecard_a.overall_score == Decimal("80.00")

    def test_delete_draft_removes_it(self, client_a, scorecard_a):
        pk = scorecard_a.pk
        resp = client_a.post(reverse("scm:scorecard_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import SupplierScorecard
        assert not SupplierScorecard.objects.filter(pk=pk).exists()

    def test_delete_non_draft_is_refused(self, client_a, scorecard_a):
        scorecard_a.status = "published"
        scorecard_a.save(update_fields=["status"])
        from apps.scm.models import SupplierScorecard
        resp = client_a.post(reverse("scm:scorecard_delete", args=[scorecard_a.pk]))
        assert resp.status_code == 302
        assert SupplierScorecard.objects.filter(pk=scorecard_a.pk).exists()


class TestScorecardActions:
    def test_recompute_updates_scores_from_signals(self, client_a, tenant_a, supplier_a, usd, scorecard_a):
        from apps.scm.models import PurchaseOrder, PurchaseOrderLine, GoodsReceiptNote, GoodsReceiptLine
        po = PurchaseOrder.objects.create(
            tenant=tenant_a, vendor=supplier_a, currency=usd, status="approved",
            order_date=datetime.date(2026, 1, 1), expected_date=datetime.date(2026, 1, 20),
        )
        line = PurchaseOrderLine.objects.create(
            purchase_order=po, item_description="Widget", quantity=Decimal("10"), unit_price=Decimal("5.00"),
        )
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=po, receipt_date=datetime.date(2026, 1, 15), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=Decimal("10"))

        resp = client_a.post(reverse("scm:scorecard_recompute", args=[scorecard_a.pk]))
        assert resp.status_code == 302
        scorecard_a.refresh_from_db()
        assert scorecard_a.delivery_score == Decimal("100.00")

    def test_recompute_blocked_on_manual_override(self, client_a, scorecard_a):
        scorecard_a.manual_override = True
        scorecard_a.delivery_score = Decimal("55.00")
        scorecard_a.save(update_fields=["manual_override", "delivery_score"])
        resp = client_a.post(reverse("scm:scorecard_recompute", args=[scorecard_a.pk]))
        assert resp.status_code == 302
        scorecard_a.refresh_from_db()
        assert scorecard_a.delivery_score == Decimal("55.00")

    def test_recompute_blocked_when_archived(self, client_a, scorecard_a):
        scorecard_a.status = "archived"
        scorecard_a.delivery_score = Decimal("55.00")
        scorecard_a.save(update_fields=["status", "delivery_score"])
        resp = client_a.post(reverse("scm:scorecard_recompute", args=[scorecard_a.pk]))
        assert resp.status_code == 302
        scorecard_a.refresh_from_db()
        assert scorecard_a.delivery_score == Decimal("55.00")

    def test_publish_draft_succeeds(self, client_a, scorecard_a):
        resp = client_a.post(reverse("scm:scorecard_publish", args=[scorecard_a.pk]))
        assert resp.status_code == 302
        scorecard_a.refresh_from_db()
        assert scorecard_a.status == "published"

    def test_publish_non_draft_is_a_no_op(self, client_a, scorecard_a):
        scorecard_a.status = "published"
        scorecard_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:scorecard_publish", args=[scorecard_a.pk]))
        assert resp.status_code == 302
        scorecard_a.refresh_from_db()
        assert scorecard_a.status == "published"


# ================================================================ SupplierContract CRUD
class TestContractCRUD:
    def test_list_returns_200(self, client_a, contract_a):
        resp = client_a.get(reverse("scm:contract_list"))
        assert resp.status_code == 200
        assert contract_a in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, contract_a):
        resp = client_a.get(reverse("scm:contract_list"), {"status": "draft"})
        assert contract_a in resp.context["object_list"]

    def test_list_junk_type_filter_returns_200_not_500(self, client_a, contract_a):
        resp = client_a.get(reverse("scm:contract_list"), {"contract_type": "not-a-type"})
        assert resp.status_code == 200

    def test_list_no_n_plus_one_query_blowup(self, client_a, tenant_a, supplier_a, django_assert_max_num_queries):
        from apps.scm.models import SupplierContract
        for i in range(8):
            SupplierContract.objects.create(tenant=tenant_a, party=supplier_a, title=f"Contract {i}")
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:contract_list"))
        assert resp.status_code == 200

    def _valid_data(self, supplier_a, **overrides):
        data = {
            "party": str(supplier_a.pk), "title": "New Deal", "contract_type": "purchase",
            "start_date": "2026-01-01", "end_date": "2026-12-31", "contract_value": "5000.00",
            "currency": "", "payment_terms": "", "auto_renew": "", "renewal_notice_days": "30",
            "terms_summary": "", "document": "", "notes": "",
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierContract
        resp = client_a.post(reverse("scm:contract_create"), self._valid_data(supplier_a))
        assert resp.status_code == 302
        c = SupplierContract.objects.get(title="New Deal")
        assert c.tenant_id == tenant_a.pk
        assert c.number == "SC-00001"
        assert c.status == "draft"

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierContract
        data = self._valid_data(
            supplier_a, title="Hack attempt", start_date="", end_date="", contract_value="0",
            status="active", number="SC-99999",
        )
        resp = client_a.post(reverse("scm:contract_create"), data)
        assert resp.status_code == 302
        c = SupplierContract.objects.get(title="Hack attempt")
        assert c.status == "draft"
        assert c.number == "SC-00001"

    # ---- Regression: renewed/terminated/expired contracts can't be edited ----
    @pytest.mark.parametrize("locked_status", ["renewed", "terminated", "expired"])
    def test_edit_blocked_for_locked_statuses(self, client_a, tenant_a, supplier_a, locked_status):
        from apps.scm.models import SupplierContract
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="Locked", status=locked_status,
        )
        resp = client_a.post(
            reverse("scm:contract_edit", args=[c.pk]),
            self._valid_data(supplier_a, title="Tampered title", start_date="", end_date="", contract_value="0"),
        )
        assert resp.status_code == 302
        c.refresh_from_db()
        assert c.title == "Locked"  # unchanged

    def test_delete_draft_removes_it(self, client_a, contract_a):
        pk = contract_a.pk
        resp = client_a.post(reverse("scm:contract_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import SupplierContract
        assert not SupplierContract.objects.filter(pk=pk).exists()

    def test_delete_active_contract_is_refused(self, client_a, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        from apps.scm.models import SupplierContract
        resp = client_a.post(reverse("scm:contract_delete", args=[contract_a.pk]))
        assert resp.status_code == 302
        assert SupplierContract.objects.filter(pk=contract_a.pk).exists()


class TestContractActions:
    def test_activate_draft_contract(self, client_a, contract_a):
        resp = client_a.post(reverse("scm:contract_activate", args=[contract_a.pk]))
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.status == "active"

    def test_activate_non_draft_is_a_no_op(self, client_a, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:contract_activate", args=[contract_a.pk]))
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.status == "active"

    def test_renew_creates_draft_and_marks_original_renewed(self, client_a, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:contract_renew", args=[contract_a.pk]))
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.status == "renewed"
        from apps.scm.models import SupplierContract
        new = SupplierContract.objects.exclude(pk=contract_a.pk).get(party=contract_a.party)
        assert new.status == "draft"
        assert new.number != contract_a.number

    def test_renew_draft_contract_is_refused(self, client_a, contract_a):
        resp = client_a.post(reverse("scm:contract_renew", args=[contract_a.pk]))
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.status == "draft"  # renew is only valid from active/expiring/expired

    def test_terminate_requires_reason(self, client_a, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:contract_terminate", args=[contract_a.pk]))
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.status == "active"  # unchanged

    def test_terminate_with_reason_succeeds(self, client_a, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        resp = client_a.post(
            reverse("scm:contract_terminate", args=[contract_a.pk]),
            {"termination_reason": "Vendor breach"},
        )
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.status == "terminated"
        assert contract_a.termination_reason == "Vendor breach"


# ================================================================ SupplierCatalog CRUD + item formset
class TestCatalogCRUD:
    def test_list_returns_200(self, client_a, catalog_a):
        resp = client_a.get(reverse("scm:catalog_list"))
        assert resp.status_code == 200
        assert catalog_a in resp.context["object_list"]

    def test_list_filter_by_party(self, client_a, catalog_a, supplier_a):
        resp = client_a.get(reverse("scm:catalog_list"), {"party": str(supplier_a.pk)})
        assert catalog_a in resp.context["object_list"]

    def test_list_junk_party_filter_returns_200_not_500(self, client_a, catalog_a):
        resp = client_a.get(reverse("scm:catalog_list"), {"party": "xyz"})
        assert resp.status_code == 200

    def test_create_saves_catalog_and_items_with_tenant(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierCatalog
        data = {
            "party": str(supplier_a.pk), "name": "2027 Price List", "currency": "",
            "valid_from": "", "valid_until": "", "notes": "",
            **formset_data("items", [
                {"id": "", "item_name": "Bond paper", "sku": "BP-1", "uom": "ream",
                 "unit_price": "6.50", "lead_time_days": "3", "min_order_qty": "1", "is_active": "on"},
            ]),
        }
        resp = client_a.post(reverse("scm:catalog_create"), data)
        assert resp.status_code == 302
        cat = SupplierCatalog.objects.get(name="2027 Price List")
        assert cat.tenant_id == tenant_a.pk
        assert cat.number == "CAT-00001"
        assert cat.items.count() == 1

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierCatalog
        data = {
            "party": str(supplier_a.pk), "name": "Hack list", "currency": "",
            "valid_from": "", "valid_until": "", "notes": "",
            "status": "active", "number": "CAT-99999",
            **formset_data("items", []),
        }
        resp = client_a.post(reverse("scm:catalog_create"), data)
        assert resp.status_code == 302
        cat = SupplierCatalog.objects.get(name="Hack list")
        assert cat.status == "draft"
        assert cat.number == "CAT-00001"

    def test_edit_blocked_once_archived(self, client_a, catalog_a):
        catalog_a.status = "archived"
        catalog_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:catalog_edit", args=[catalog_a.pk]))
        assert resp.status_code == 302

    def test_detail_returns_200(self, client_a, catalog_a):
        resp = client_a.get(reverse("scm:catalog_detail", args=[catalog_a.pk]))
        assert resp.status_code == 200

    def test_delete_draft_removes_it(self, client_a, catalog_a):
        pk = catalog_a.pk
        resp = client_a.post(reverse("scm:catalog_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import SupplierCatalog
        assert not SupplierCatalog.objects.filter(pk=pk).exists()

    def test_delete_active_catalog_is_refused(self, client_a, catalog_a):
        catalog_a.status = "active"
        catalog_a.save(update_fields=["status"])
        from apps.scm.models import SupplierCatalog
        resp = client_a.post(reverse("scm:catalog_delete", args=[catalog_a.pk]))
        assert resp.status_code == 302
        assert SupplierCatalog.objects.filter(pk=catalog_a.pk).exists()


class TestCatalogActivate:
    def test_activate_without_items_is_refused(self, client_a, catalog_a):
        resp = client_a.post(reverse("scm:catalog_activate", args=[catalog_a.pk]))
        assert resp.status_code == 302
        catalog_a.refresh_from_db()
        assert catalog_a.status == "draft"

    def test_activate_with_items_succeeds(self, client_a, catalog_a):
        from apps.scm.models import SupplierCatalogItem
        SupplierCatalogItem.objects.create(catalog=catalog_a, item_name="Widget", unit_price=Decimal("5.00"))
        resp = client_a.post(reverse("scm:catalog_activate", args=[catalog_a.pk]))
        assert resp.status_code == 302
        catalog_a.refresh_from_db()
        assert catalog_a.status == "active"


# ================================================================ SupplierRiskAssessment CRUD
class TestRiskAssessmentCRUD:
    def test_list_returns_200(self, client_a, risk_assessment_a):
        resp = client_a.get(reverse("scm:riskassessment_list"))
        assert resp.status_code == 200
        assert risk_assessment_a in resp.context["object_list"]

    def test_list_filter_by_risk_level(self, client_a, risk_assessment_a):
        resp = client_a.get(reverse("scm:riskassessment_list"), {"risk_level": "low"})
        assert risk_assessment_a in resp.context["object_list"]

    def test_list_junk_risk_level_filter_returns_200_not_500(self, client_a, risk_assessment_a):
        resp = client_a.get(reverse("scm:riskassessment_list"), {"risk_level": "nonsense"})
        assert resp.status_code == 200

    def test_create_derives_risk_level_from_factors(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        data = {
            "party": str(supplier_a.pk), "assessment_date": "2026-01-01",
            "financial_score": "5", "geopolitical_score": "1", "compliance_score": "1",
            "operational_score": "1", "mitigation_plan": "", "next_review_date": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:riskassessment_create"), data)
        assert resp.status_code == 302
        ra = SupplierRiskAssessment.objects.get(party=supplier_a)
        assert ra.tenant_id == tenant_a.pk
        assert ra.number == "SRA-00001"
        assert ra.risk_level == "high"  # single critical factor floors at High, not Medium
        assert ra.assessed_by is not None

    def test_create_ignores_posted_status_and_risk_level(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        data = {
            "party": str(supplier_a.pk), "assessment_date": "2026-01-01",
            "financial_score": "1", "geopolitical_score": "1", "compliance_score": "1",
            "operational_score": "1", "mitigation_plan": "", "next_review_date": "", "notes": "",
            "status": "reviewed", "risk_level": "critical", "risk_index": "9.99",
        }
        resp = client_a.post(reverse("scm:riskassessment_create"), data)
        assert resp.status_code == 302
        ra = SupplierRiskAssessment.objects.get(party=supplier_a)
        assert ra.status == "draft"
        assert ra.risk_level == "low"  # derived from the (all-1) factor scores, not the posted value

    def test_edit_blocked_once_reviewed(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierRiskAssessment
        ra = SupplierRiskAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=datetime.date(2026, 1, 1), status="reviewed",
        )
        resp = client_a.get(reverse("scm:riskassessment_edit", args=[ra.pk]))
        assert resp.status_code == 302

    def test_delete_draft_removes_it(self, client_a, risk_assessment_a):
        pk = risk_assessment_a.pk
        resp = client_a.post(reverse("scm:riskassessment_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import SupplierRiskAssessment
        assert not SupplierRiskAssessment.objects.filter(pk=pk).exists()

    def test_delete_non_draft_is_refused(self, client_a, risk_assessment_a):
        risk_assessment_a.status = "submitted"
        risk_assessment_a.save(update_fields=["status"])
        from apps.scm.models import SupplierRiskAssessment
        resp = client_a.post(reverse("scm:riskassessment_delete", args=[risk_assessment_a.pk]))
        assert resp.status_code == 302
        assert SupplierRiskAssessment.objects.filter(pk=risk_assessment_a.pk).exists()


class TestRiskAssessmentActions:
    def test_submit_draft_moves_to_submitted(self, client_a, risk_assessment_a):
        resp = client_a.post(reverse("scm:riskassessment_submit", args=[risk_assessment_a.pk]))
        assert resp.status_code == 302
        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.status == "submitted"

    def test_submit_already_submitted_is_a_no_op(self, client_a, risk_assessment_a):
        risk_assessment_a.status = "submitted"
        risk_assessment_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:riskassessment_submit", args=[risk_assessment_a.pk]))
        assert resp.status_code == 302
        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.status == "submitted"

    def test_review_submitted_assessment_succeeds(self, client_a, risk_assessment_a):
        risk_assessment_a.status = "submitted"
        risk_assessment_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:riskassessment_review", args=[risk_assessment_a.pk]))
        assert resp.status_code == 302
        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.status == "reviewed"

    def test_review_draft_assessment_is_a_no_op(self, client_a, risk_assessment_a):
        resp = client_a.post(reverse("scm:riskassessment_review", args=[risk_assessment_a.pk]))
        assert resp.status_code == 302
        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.status == "draft"


# ================================================================ Positive GET/edit paths (coverage completeness)
class TestCatalogEditAndCreateForm:
    def test_edit_get_renders_form_for_editable_catalog(self, client_a, catalog_a):
        resp = client_a.get(reverse("scm:catalog_edit", args=[catalog_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_create_get_renders_empty_form(self, client_a):
        resp = client_a.get(reverse("scm:catalog_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False


class TestContractEditAndDetail:
    def test_edit_updates_fields(self, client_a, contract_a, supplier_a):
        data = {
            "party": str(supplier_a.pk), "title": "Renegotiated Deal", "contract_type": "service",
            "start_date": "2026-01-01", "end_date": "2026-12-31", "contract_value": "7500.00",
            "currency": "", "payment_terms": "", "auto_renew": "", "renewal_notice_days": "45",
            "terms_summary": "", "document": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:contract_edit", args=[contract_a.pk]), data)
        assert resp.status_code == 302
        contract_a.refresh_from_db()
        assert contract_a.title == "Renegotiated Deal"
        assert contract_a.contract_value == Decimal("7500.00")

    def test_detail_returns_200(self, client_a, contract_a):
        resp = client_a.get(reverse("scm:contract_detail", args=[contract_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == contract_a


class TestContractListRollsStatuses:
    def test_list_transitions_an_active_contract_past_its_end_date_to_expired(
        self, client_a, tenant_a, supplier_a,
    ):
        from apps.scm.models import SupplierContract
        from django.utils import timezone
        past = timezone.now().date() - datetime.timedelta(days=5)
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="Lapsed", status="active", end_date=past,
        )
        resp = client_a.get(reverse("scm:contract_list"))
        assert resp.status_code == 200
        c.refresh_from_db()
        assert c.status == "expired"


class TestContractTerminateAlreadyClosed:
    def test_terminate_an_already_terminated_contract_is_a_no_op(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierContract
        c = SupplierContract.objects.create(
            tenant=tenant_a, party=supplier_a, title="Already done", status="terminated",
        )
        resp = client_a.post(
            reverse("scm:contract_terminate", args=[c.pk]), {"termination_reason": "Redundant"},
        )
        assert resp.status_code == 302
        c.refresh_from_db()
        assert c.status == "terminated"
        assert c.termination_reason == ""  # untouched — the guard fired before the reason was recorded


class TestRiskAssessmentEditAndDetail:
    def test_edit_get_renders_form_for_editable_assessment(self, client_a, risk_assessment_a):
        resp = client_a.get(reverse("scm:riskassessment_edit", args=[risk_assessment_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_create_get_renders_empty_form(self, client_a):
        resp = client_a.get(reverse("scm:riskassessment_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_detail_returns_200(self, client_a, risk_assessment_a):
        resp = client_a.get(reverse("scm:riskassessment_detail", args=[risk_assessment_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == risk_assessment_a


class TestScorecardEdit:
    def test_edit_updates_fields(self, client_a, scorecard_a, supplier_a):
        data = {
            "party": str(supplier_a.pk), "period_start": "2026-02-01", "period_end": "2026-02-28",
            "delivery_score": "90", "quality_score": "", "price_score": "", "responsiveness_score": "",
            "manual_override": "", "notes": "Revised period",
        }
        resp = client_a.post(reverse("scm:scorecard_edit", args=[scorecard_a.pk]), data)
        assert resp.status_code == 302
        scorecard_a.refresh_from_db()
        assert scorecard_a.notes == "Revised period"
        assert scorecard_a.delivery_score == Decimal("90.00")


class TestCatalogActivateAlreadyActive:
    def test_activate_an_already_active_catalog_is_a_no_op(self, client_a, catalog_a):
        catalog_a.status = "active"
        catalog_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:catalog_activate", args=[catalog_a.pk]))
        assert resp.status_code == 302
        catalog_a.refresh_from_db()
        assert catalog_a.status == "active"


# ================================================================ Create guarded when the user has no tenant
class TestSRMCreateWithoutTenantWorkspace:
    """`_need_tenant` — a logged-in user with no tenant workspace (e.g. the bare superuser)
    must be redirected away from every SRM create view, never allowed to save an orphan row."""

    def _tenantless_client(self, db):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(email="orphan@example.com", username="orphan", password="x", tenant=None)
        c = Client()
        c.force_login(user)
        return c

    def test_supplierprofile_create_redirects(self, db):
        from apps.scm.models import SupplierProfile
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:supplierprofile_create"))
        assert resp.status_code == 302
        assert SupplierProfile.objects.count() == 0

    def test_scorecard_create_redirects(self, db):
        from apps.scm.models import SupplierScorecard
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:scorecard_create"))
        assert resp.status_code == 302
        assert SupplierScorecard.objects.count() == 0

    def test_contract_create_redirects(self, db):
        from apps.scm.models import SupplierContract
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:contract_create"))
        assert resp.status_code == 302
        assert SupplierContract.objects.count() == 0

    def test_catalog_create_redirects(self, db):
        from apps.scm.models import SupplierCatalog
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:catalog_create"))
        assert resp.status_code == 302
        assert SupplierCatalog.objects.count() == 0

    def test_riskassessment_create_redirects(self, db):
        from apps.scm.models import SupplierRiskAssessment
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:riskassessment_create"))
        assert resp.status_code == 302
        assert SupplierRiskAssessment.objects.count() == 0


# ================================================================================================
# SCM 4.3 Inventory Management
# ================================================================================================

# ================================================================ Item CRUD
class TestItemCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, item_a):
        resp = client_a.get(reverse("scm:item_list"))
        assert resp.status_code == 200
        assert item_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, item_a, item_b):
        resp = client_a.get(reverse("scm:item_list"))
        assert item_b not in resp.context["object_list"]

    def test_list_search_by_sku(self, client_a, item_a):
        resp = client_a.get(reverse("scm:item_list"), {"q": "WIDGET-1"})
        assert item_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:item_list"), {"q": "Nothing matches this"})
        assert item_a not in resp2.context["object_list"]

    def test_list_filter_by_item_type(self, client_a, tenant_a, item_a):
        from apps.scm.models import Item
        service_item = Item.objects.create(tenant=tenant_a, sku="SVC-1", name="Consulting", item_type="service")
        resp = client_a.get(reverse("scm:item_list"), {"item_type": "service"})
        object_list = list(resp.context["object_list"])
        assert service_item in object_list
        assert item_a not in object_list

    def test_list_junk_category_filter_returns_200_not_500(self, client_a, item_a):
        resp = client_a.get(reverse("scm:item_list"), {"category": "not-an-id"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, item_a):
        resp = client_a.get(reverse("scm:item_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_page_2_when_rows_exceed_page_size(self, client_a, tenant_a):
        from apps.scm.models import Item
        for i in range(20):
            Item.objects.create(tenant=tenant_a, sku=f"SKU-{i:03d}", name=f"Item {i}")
        resp1 = client_a.get(reverse("scm:item_list"))
        resp2 = client_a.get(reverse("scm:item_list"), {"page": "2"})
        assert resp1.status_code == 200 and resp2.status_code == 200
        assert set(o.pk for o in resp1.context["object_list"]) != set(o.pk for o in resp2.context["object_list"])

    def _valid_data(self, **overrides):
        data = {
            "sku": "NEW-ITEM", "name": "New Item", "category": "", "uom": "",
            "item_type": "stock", "tracking": "none", "costing_method": "weighted_avg",
            "standard_cost": "5.00", "reorder_point": "0", "description": "", "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import Item
        resp = client_a.post(reverse("scm:item_create"), self._valid_data())
        assert resp.status_code == 302
        item = Item.objects.get(sku="NEW-ITEM")
        assert item.tenant_id == tenant_a.pk

    def test_create_ignores_posted_average_cost(self, client_a):
        from apps.scm.models import Item
        resp = client_a.post(reverse("scm:item_create"), self._valid_data(average_cost="999999.0000"))
        assert resp.status_code == 302
        item = Item.objects.get(sku="NEW-ITEM")
        assert item.average_cost == Decimal("0")

    def test_edit_updates_fields(self, client_a, item_a):
        resp = client_a.post(reverse("scm:item_edit", args=[item_a.pk]),
                             self._valid_data(sku=item_a.sku, name="Renamed Widget"))
        assert resp.status_code == 302
        item_a.refresh_from_db()
        assert item_a.name == "Renamed Widget"

    def test_detail_returns_200_with_context(self, client_a, item_a):
        resp = client_a.get(reverse("scm:item_detail", args=[item_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == item_a
        assert resp.context["on_hand"] == Decimal("0")

    def test_delete_with_no_stock_moves_removes_it(self, client_a, item_a):
        pk = item_a.pk
        resp = client_a.post(reverse("scm:item_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import Item
        assert not Item.objects.filter(pk=pk).exists()

    def test_delete_with_stock_moves_is_refused(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        from apps.scm.models import Item
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("1"),
                         unit_cost=Decimal("1.00"), move_type="receipt")
        resp = client_a.post(reverse("scm:item_delete", args=[item_a.pk]))
        assert resp.status_code == 302
        assert Item.objects.filter(pk=item_a.pk).exists()

    def test_get_delete_returns_405_and_does_not_delete(self, client_a, item_a):
        resp = client_a.get(reverse("scm:item_delete", args=[item_a.pk]))
        assert resp.status_code == 405
        from apps.scm.models import Item
        assert Item.objects.filter(pk=item_a.pk).exists()


# ================================================================ ItemCategory CRUD
class TestItemCategoryCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, category_a):
        resp = client_a.get(reverse("scm:category_list"))
        assert resp.status_code == 200
        assert category_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, category_a, category_b):
        resp = client_a.get(reverse("scm:category_list"))
        assert category_b not in resp.context["object_list"]

    def test_create_saves_with_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import ItemCategory
        data = {"name": "Gadgets", "parent": "", "description": "", "is_active": "on"}
        resp = client_a.post(reverse("scm:category_create"), data)
        assert resp.status_code == 302
        cat = ItemCategory.objects.get(name="Gadgets")
        assert cat.tenant_id == tenant_a.pk

    def test_edit_updates_fields(self, client_a, category_a):
        data = {"name": "Renamed", "parent": "", "description": "", "is_active": "on"}
        resp = client_a.post(reverse("scm:category_edit", args=[category_a.pk]), data)
        assert resp.status_code == 302
        category_a.refresh_from_db()
        assert category_a.name == "Renamed"

    def test_delete_removes_it(self, client_a, category_a):
        pk = category_a.pk
        resp = client_a.post(reverse("scm:category_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import ItemCategory
        assert not ItemCategory.objects.filter(pk=pk).exists()

    def test_get_delete_returns_405(self, client_a, category_a):
        assert client_a.get(reverse("scm:category_delete", args=[category_a.pk])).status_code == 405


# ================================================================ UOM CRUD
class TestUOMCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, uom_each_a):
        resp = client_a.get(reverse("scm:uom_list"))
        assert resp.status_code == 200
        assert uom_each_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, uom_each_a, uom_each_b):
        resp = client_a.get(reverse("scm:uom_list"))
        assert uom_each_b not in resp.context["object_list"]

    def test_list_search_by_code(self, client_a, uom_each_a):
        resp = client_a.get(reverse("scm:uom_list"), {"q": "EA"})
        assert uom_each_a in resp.context["object_list"]

    def test_create_saves_with_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import UOM
        data = {"code": "KG", "name": "Kilogram", "factor": "1", "is_active": "on"}
        resp = client_a.post(reverse("scm:uom_create"), data)
        assert resp.status_code == 302
        uom = UOM.objects.get(code="KG")
        assert uom.tenant_id == tenant_a.pk

    def test_edit_updates_fields(self, client_a, uom_each_a):
        data = {"code": uom_each_a.code, "name": "Renamed each", "factor": "1", "is_active": "on"}
        resp = client_a.post(reverse("scm:uom_edit", args=[uom_each_a.pk]), data)
        assert resp.status_code == 302
        uom_each_a.refresh_from_db()
        assert uom_each_a.name == "Renamed each"

    def test_delete_removes_it(self, client_a, uom_each_a):
        pk = uom_each_a.pk
        resp = client_a.post(reverse("scm:uom_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import UOM
        assert not UOM.objects.filter(pk=pk).exists()

    def test_get_delete_returns_405(self, client_a, uom_each_a):
        assert client_a.get(reverse("scm:uom_delete", args=[uom_each_a.pk])).status_code == 405


# ================================================================ Location CRUD
class TestLocationCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, location_a):
        resp = client_a.get(reverse("scm:location_list"))
        assert resp.status_code == 200
        assert location_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, location_a, location_b):
        resp = client_a.get(reverse("scm:location_list"))
        assert location_b not in resp.context["object_list"]

    def test_list_filter_by_location_type(self, client_a, tenant_a, location_a):
        from apps.scm.models import Location
        bin_ = Location.objects.create(tenant=tenant_a, code="BIN-9", name="Bin 9", location_type="bin")
        resp = client_a.get(reverse("scm:location_list"), {"location_type": "bin"})
        object_list = list(resp.context["object_list"])
        assert bin_ in object_list
        assert location_a not in object_list

    def test_create_saves_with_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import Location
        data = {"code": "WH3", "name": "Third Warehouse", "location_type": "warehouse",
                "parent": "", "is_active": "on"}
        resp = client_a.post(reverse("scm:location_create"), data)
        assert resp.status_code == 302
        loc = Location.objects.get(code="WH3")
        assert loc.tenant_id == tenant_a.pk

    def test_edit_updates_fields(self, client_a, location_a):
        data = {"code": location_a.code, "name": "Renamed WH", "location_type": "warehouse",
                "parent": "", "is_active": "on"}
        resp = client_a.post(reverse("scm:location_edit", args=[location_a.pk]), data)
        assert resp.status_code == 302
        location_a.refresh_from_db()
        assert location_a.name == "Renamed WH"

    def test_detail_returns_200_with_context(self, client_a, location_a):
        resp = client_a.get(reverse("scm:location_detail", args=[location_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == location_a
        assert resp.context["on_hand_value"] == Decimal("0.00")

    def test_delete_with_no_stock_moves_removes_it(self, client_a, location_a):
        pk = location_a.pk
        resp = client_a.post(reverse("scm:location_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import Location
        assert not Location.objects.filter(pk=pk).exists()

    def test_delete_with_stock_moves_is_refused(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        from apps.scm.models import Location
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("1"),
                         unit_cost=Decimal("1.00"), move_type="receipt")
        resp = client_a.post(reverse("scm:location_delete", args=[location_a.pk]))
        assert resp.status_code == 302
        assert Location.objects.filter(pk=location_a.pk).exists()

    def test_get_delete_returns_405(self, client_a, location_a):
        assert client_a.get(reverse("scm:location_delete", args=[location_a.pk])).status_code == 405


# ================================================================ LotSerial CRUD
class TestLotSerialCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, lot_a):
        resp = client_a.get(reverse("scm:lotserial_list"))
        assert resp.status_code == 200
        assert lot_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, lot_a, lot_b):
        resp = client_a.get(reverse("scm:lotserial_list"))
        assert lot_b not in resp.context["object_list"]

    def test_list_junk_item_filter_returns_200_not_500(self, client_a, lot_a):
        resp = client_a.get(reverse("scm:lotserial_list"), {"item": "not-an-id"})
        assert resp.status_code == 200

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, item_lot_a):
        from apps.scm.models import LotSerial
        data = {"item": str(item_lot_a.pk), "kind": "lot", "number": "LOT-NEW",
                "expiry_date": "", "status": "available", "notes": ""}
        resp = client_a.post(reverse("scm:lotserial_create"), data)
        assert resp.status_code == 302
        lot = LotSerial.objects.get(number="LOT-NEW")
        assert lot.tenant_id == tenant_a.pk

    def test_edit_updates_fields(self, client_a, lot_a, item_lot_a):
        data = {"item": str(item_lot_a.pk), "kind": "lot", "number": lot_a.number,
                "expiry_date": "", "status": "quarantine", "notes": "Hold for QA"}
        resp = client_a.post(reverse("scm:lotserial_edit", args=[lot_a.pk]), data)
        assert resp.status_code == 302
        lot_a.refresh_from_db()
        assert lot_a.status == "quarantine"

    def test_detail_returns_200_with_context(self, client_a, lot_a):
        resp = client_a.get(reverse("scm:lotserial_detail", args=[lot_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == lot_a
        assert resp.context["on_hand"] == Decimal("0")

    def test_delete_with_stock_moves_is_refused(self, client_a, tenant_a, item_lot_a, location_a, lot_a):
        from apps.scm.models import LotSerial
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_lot_a, location=location_a, quantity=Decimal("1"),
                         unit_cost=Decimal("1.00"), move_type="receipt", lot_serial=lot_a)
        resp = client_a.post(reverse("scm:lotserial_delete", args=[lot_a.pk]))
        assert resp.status_code == 302
        assert LotSerial.objects.filter(pk=lot_a.pk).exists()

    def test_delete_with_no_stock_moves_removes_it(self, client_a, lot_a):
        pk = lot_a.pk
        resp = client_a.post(reverse("scm:lotserial_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import LotSerial
        assert not LotSerial.objects.filter(pk=pk).exists()

    def test_get_delete_returns_405(self, client_a, lot_a):
        assert client_a.get(reverse("scm:lotserial_delete", args=[lot_a.pk])).status_code == 405


# ================================================================ ReorderRule CRUD
class TestReorderRuleCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, reorder_rule_a):
        resp = client_a.get(reverse("scm:reorderrule_list"))
        assert resp.status_code == 200
        assert reorder_rule_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, reorder_rule_a, reorder_rule_b):
        resp = client_a.get(reverse("scm:reorderrule_list"))
        assert reorder_rule_b not in resp.context["object_list"]

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, item_a, location_a2):
        from apps.scm.models import ReorderRule
        data = {"item": str(item_a.pk), "location": str(location_a2.pk), "reorder_point": "5",
                "safety_stock": "2", "reorder_quantity": "10", "is_active": "on"}
        resp = client_a.post(reverse("scm:reorderrule_create"), data)
        assert resp.status_code == 302
        rule = ReorderRule.objects.get(item=item_a, location=location_a2)
        assert rule.tenant_id == tenant_a.pk

    def test_edit_updates_fields(self, client_a, reorder_rule_a, item_a, location_a):
        data = {"item": str(item_a.pk), "location": str(location_a.pk), "reorder_point": "99",
                "safety_stock": "5", "reorder_quantity": "20", "is_active": "on"}
        resp = client_a.post(reverse("scm:reorderrule_edit", args=[reorder_rule_a.pk]), data)
        assert resp.status_code == 302
        reorder_rule_a.refresh_from_db()
        assert reorder_rule_a.reorder_point == Decimal("99.00")

    def test_delete_removes_it(self, client_a, reorder_rule_a):
        pk = reorder_rule_a.pk
        resp = client_a.post(reverse("scm:reorderrule_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import ReorderRule
        assert not ReorderRule.objects.filter(pk=pk).exists()

    def test_get_delete_returns_405(self, client_a, reorder_rule_a):
        assert client_a.get(reverse("scm:reorderrule_delete", args=[reorder_rule_a.pk])).status_code == 405


# ================================================================ StockTransfer CRUD
class TestStockTransferCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, stock_transfer_a):
        resp = client_a.get(reverse("scm:stocktransfer_list"))
        assert resp.status_code == 200
        assert stock_transfer_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, stock_transfer_a, stock_transfer_b):
        resp = client_a.get(reverse("scm:stocktransfer_list"))
        assert stock_transfer_b not in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, stock_transfer_a):
        resp = client_a.get(reverse("scm:stocktransfer_list"), {"status": "draft"})
        assert stock_transfer_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:stocktransfer_list"), {"status": "completed"})
        assert stock_transfer_a not in resp2.context["object_list"]

    def test_create_get_renders_an_empty_form(self, client_a):
        resp = client_a.get(reverse("scm:stocktransfer_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, location_a, location_a2, item_a):
        from apps.scm.models import StockTransfer
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "5"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 302
        transfer = StockTransfer.objects.get(tenant=tenant_a)
        assert transfer.number == "TRF-00001"
        assert transfer.lines.count() == 1

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, location_a, location_a2, item_a):
        from apps.scm.models import StockTransfer
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "", "status": "completed", "number": "TRF-99999",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "5"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 302
        transfer = StockTransfer.objects.get(tenant=tenant_a)
        assert transfer.status == "draft"
        assert transfer.number == "TRF-00001"

    def test_edit_updates_fields(self, client_a, stock_transfer_a, location_a, location_a2, item_a):
        line = stock_transfer_a.lines.first()
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-25", "notes": "Updated",
            **formset_data("lines", [{"id": line.pk, "item": str(item_a.pk), "lot_serial": "", "quantity": "8"}],
                           initial=1),
        }
        resp = client_a.post(reverse("scm:stocktransfer_edit", args=[stock_transfer_a.pk]), data)
        assert resp.status_code == 302
        stock_transfer_a.refresh_from_db()
        assert stock_transfer_a.notes == "Updated"
        assert stock_transfer_a.lines.first().quantity == Decimal("8")

    def test_edit_blocked_once_completed(self, client_a, tenant_a, stock_transfer_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        resp = client_a.get(reverse("scm:stocktransfer_edit", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302  # redirected to detail, not the form

    def test_detail_returns_200_with_context(self, client_a, stock_transfer_a):
        resp = client_a.get(reverse("scm:stocktransfer_detail", args=[stock_transfer_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == stock_transfer_a

    def test_delete_draft_removes_it(self, client_a, stock_transfer_a):
        pk = stock_transfer_a.pk
        resp = client_a.post(reverse("scm:stocktransfer_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import StockTransfer
        assert not StockTransfer.objects.filter(pk=pk).exists()

    def test_delete_non_draft_is_refused(self, client_a, tenant_a, stock_transfer_a, location_a, item_a):
        from apps.scm.models import StockTransfer
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        resp = client_a.post(reverse("scm:stocktransfer_delete", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        assert StockTransfer.objects.filter(pk=stock_transfer_a.pk).exists()

    def test_get_delete_returns_405(self, client_a, stock_transfer_a):
        assert client_a.get(reverse("scm:stocktransfer_delete", args=[stock_transfer_a.pk])).status_code == 405


# ================================================================ StockTransfer posting (state machine)
class TestStockTransferPosting:
    def test_complete_posts_paired_moves(self, client_a, tenant_a, stock_transfer_a, location_a, location_a2, item_a):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        stock_transfer_a.refresh_from_db()
        assert stock_transfer_a.status == "completed"
        assert stock_transfer_a.completed_at is not None
        assert item_a.on_hand(location=location_a) == Decimal("15")
        assert item_a.on_hand(location=location_a2) == Decimal("5")
        assert StockMove.objects.filter(tenant=tenant_a, reference=stock_transfer_a.number).count() == 2

    def test_complete_refused_when_no_lines(self, client_a, tenant_a, location_a, location_a2):
        from apps.scm.models import StockTransfer
        empty = StockTransfer.objects.create(tenant=tenant_a, from_location=location_a, to_location=location_a2,
                                             transfer_date=datetime.date(2026, 1, 20))
        resp = client_a.post(reverse("scm:stocktransfer_complete", args=[empty.pk]))
        assert resp.status_code == 302
        empty.refresh_from_db()
        assert empty.status == "draft"

    def test_complete_already_completed_is_a_noop(self, client_a, tenant_a, stock_transfer_a, location_a, item_a):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        resp = client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        # Still exactly 2 moves (double-post guard) — not 4.
        assert StockMove.objects.filter(tenant=tenant_a, reference=stock_transfer_a.number).count() == 2

    def test_complete_refused_when_never_received_anywhere(self, client_a, stock_transfer_a, location_a, item_a):
        """Absent-prerequisite (L35): the source has NEVER held this item — zero on-hand, not
        merely insufficient — completion must be refused, not silently treated as unlimited."""
        resp = client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        stock_transfer_a.refresh_from_db()
        assert stock_transfer_a.status == "draft"
        assert item_a.on_hand(location=location_a) == Decimal("0")

    def test_complete_over_transfer_rolls_back_atomically(
        self, client_a, tenant_a, stock_transfer_a, location_a, location_a2, item_a,
    ):
        """The line asks for 5 but the source only has 3 -> refused, draft, on-hand unchanged,
        and NOTHING partial gets committed (the atomic rollback regression)."""
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("3"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        stock_transfer_a.refresh_from_db()
        assert stock_transfer_a.status == "draft"
        assert item_a.on_hand(location=location_a) == Decimal("3")
        assert item_a.on_hand(location=location_a2) == Decimal("0")
        assert not StockMove.objects.filter(tenant=tenant_a, reference=stock_transfer_a.number).exists()

    def test_complete_refuses_lot_from_a_location_that_never_held_it(
        self, client_a, tenant_a, item_lot_a, location_a, location_a2, lot_a,
    ):
        """Priority regression 1, end-to-end: the lot's stock sits at location_a; a transfer
        drawing that SAME lot FROM location_a2 must be refused even though the lot's tenant-wide
        total would cover it — and location_a2 must never go negative."""
        from apps.scm.models import StockMove, StockTransfer, StockTransferLine
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_lot_a, location=location_a, quantity=Decimal("50"),
                         unit_cost=Decimal("10.00"), move_type="receipt", lot_serial=lot_a)
        transfer = StockTransfer.objects.create(
            tenant=tenant_a, from_location=location_a2, to_location=location_a,
            transfer_date=datetime.date(2026, 1, 20),
        )
        StockTransferLine.objects.create(transfer=transfer, item=item_lot_a, lot_serial=lot_a, quantity=Decimal("10"))
        resp = client_a.post(reverse("scm:stocktransfer_complete", args=[transfer.pk]))
        assert resp.status_code == 302
        transfer.refresh_from_db()
        assert transfer.status == "draft"
        assert item_lot_a.on_hand(location=location_a2) == Decimal("0")
        assert not StockMove.objects.filter(tenant=tenant_a, reference=transfer.number).exists()

    def test_cancel_draft_becomes_cancelled(self, client_a, stock_transfer_a):
        resp = client_a.post(reverse("scm:stocktransfer_cancel", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        stock_transfer_a.refresh_from_db()
        assert stock_transfer_a.status == "cancelled"

    def test_cancel_completed_is_refused(self, client_a, tenant_a, stock_transfer_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk]))
        resp = client_a.post(reverse("scm:stocktransfer_cancel", args=[stock_transfer_a.pk]))
        assert resp.status_code == 302
        stock_transfer_a.refresh_from_db()
        assert stock_transfer_a.status == "completed"  # unchanged

    def test_get_complete_returns_405(self, client_a, stock_transfer_a):
        assert client_a.get(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk])).status_code == 405


# ================================================================ StockAdjustment CRUD
class TestStockAdjustmentCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, stock_adjustment_a):
        resp = client_a.get(reverse("scm:stockadjustment_list"))
        assert resp.status_code == 200
        assert stock_adjustment_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, stock_adjustment_a, stock_adjustment_b):
        resp = client_a.get(reverse("scm:stockadjustment_list"))
        assert stock_adjustment_b not in resp.context["object_list"]

    def test_list_filter_by_reason(self, client_a, stock_adjustment_a):
        resp = client_a.get(reverse("scm:stockadjustment_list"), {"reason": "cycle_count"})
        assert stock_adjustment_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:stockadjustment_list"), {"reason": "damage"})
        assert stock_adjustment_a not in resp2.context["object_list"]

    def test_create_get_renders_an_empty_form(self, client_a):
        resp = client_a.get(reverse("scm:stockadjustment_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, location_a, item_a):
        from apps.scm.models import StockAdjustment
        data = {
            "location": str(location_a.pk), "reason": "cycle_count", "adjustment_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "quantity_delta": "10", "unit_cost": "5.00"}]),
        }
        resp = client_a.post(reverse("scm:stockadjustment_create"), data)
        assert resp.status_code == 302
        adj = StockAdjustment.objects.get(tenant=tenant_a)
        assert adj.number == "ADJ-00001"
        assert adj.lines.count() == 1

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, location_a, item_a):
        from apps.scm.models import StockAdjustment
        data = {
            "location": str(location_a.pk), "reason": "cycle_count", "adjustment_date": "2026-01-20",
            "notes": "", "status": "posted", "number": "ADJ-99999",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "quantity_delta": "10", "unit_cost": "5.00"}]),
        }
        resp = client_a.post(reverse("scm:stockadjustment_create"), data)
        assert resp.status_code == 302
        adj = StockAdjustment.objects.get(tenant=tenant_a)
        assert adj.status == "draft"
        assert adj.number == "ADJ-00001"

    def test_edit_updates_fields(self, client_a, stock_adjustment_a, location_a, item_a):
        line = stock_adjustment_a.lines.first()
        data = {
            "location": str(location_a.pk), "reason": "found", "adjustment_date": "2026-01-25",
            "notes": "Updated",
            **formset_data("lines", [{"id": line.pk, "item": str(item_a.pk), "lot_serial": "",
                                      "quantity_delta": "15", "unit_cost": "5.00"}], initial=1),
        }
        resp = client_a.post(reverse("scm:stockadjustment_edit", args=[stock_adjustment_a.pk]), data)
        assert resp.status_code == 302
        stock_adjustment_a.refresh_from_db()
        assert stock_adjustment_a.reason == "found"
        assert stock_adjustment_a.lines.first().quantity_delta == Decimal("15")

    def test_edit_blocked_once_posted(self, client_a, stock_adjustment_a):
        client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        resp = client_a.get(reverse("scm:stockadjustment_edit", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 302  # redirected to detail, not the form

    def test_detail_returns_200_with_context(self, client_a, stock_adjustment_a):
        resp = client_a.get(reverse("scm:stockadjustment_detail", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == stock_adjustment_a
        assert resp.context["value_impact"] == Decimal("80.00")

    def test_delete_draft_removes_it(self, client_a, stock_adjustment_a):
        pk = stock_adjustment_a.pk
        resp = client_a.post(reverse("scm:stockadjustment_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import StockAdjustment
        assert not StockAdjustment.objects.filter(pk=pk).exists()

    def test_delete_non_draft_is_refused(self, client_a, stock_adjustment_a):
        from apps.scm.models import StockAdjustment
        client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        resp = client_a.post(reverse("scm:stockadjustment_delete", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 302
        assert StockAdjustment.objects.filter(pk=stock_adjustment_a.pk).exists()

    def test_get_delete_returns_405(self, client_a, stock_adjustment_a):
        assert client_a.get(reverse("scm:stockadjustment_delete", args=[stock_adjustment_a.pk])).status_code == 405


# ================================================================ StockAdjustment posting (state machine)
class TestStockAdjustmentPosting:
    def test_post_writes_a_signed_move_and_posts(self, client_a, tenant_a, stock_adjustment_a, item_a, location_a):
        from apps.scm.models import StockMove
        resp = client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 302
        stock_adjustment_a.refresh_from_db()
        assert stock_adjustment_a.status == "posted"
        assert stock_adjustment_a.posted_at is not None
        assert item_a.on_hand(location=location_a) == Decimal("10")
        assert StockMove.objects.filter(tenant=tenant_a, reference=stock_adjustment_a.number).count() == 1

    def test_post_refused_when_no_lines(self, client_a, tenant_a, location_a):
        from apps.scm.models import StockAdjustment
        empty = StockAdjustment.objects.create(tenant=tenant_a, location=location_a,
                                               adjustment_date=datetime.date(2026, 1, 20))
        resp = client_a.post(reverse("scm:stockadjustment_post", args=[empty.pk]))
        assert resp.status_code == 302
        empty.refresh_from_db()
        assert empty.status == "draft"

    def test_post_already_posted_is_a_noop(self, client_a, tenant_a, stock_adjustment_a):
        from apps.scm.models import StockMove
        client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        resp = client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 302
        assert StockMove.objects.filter(tenant=tenant_a, reference=stock_adjustment_a.number).count() == 1

    def test_post_refuses_a_write_off_that_would_go_negative(self, client_a, tenant_a, location_a, item_a):
        """Absent-prerequisite (L35): no receipt at all has ever been posted for this item at this
        location — a write-off must be REJECTED outright, never fall through to a posted adjustment."""
        from apps.scm.models import StockAdjustment, StockAdjustmentLine, StockMove
        adj = StockAdjustment.objects.create(tenant=tenant_a, location=location_a, reason="write_off",
                                             adjustment_date=datetime.date(2026, 1, 20))
        StockAdjustmentLine.objects.create(adjustment=adj, item=item_a, quantity_delta=Decimal("-5"),
                                           unit_cost=Decimal("5.00"))
        resp = client_a.post(reverse("scm:stockadjustment_post", args=[adj.pk]))
        assert resp.status_code == 302
        adj.refresh_from_db()
        assert adj.status == "draft"
        assert item_a.on_hand(location=location_a) == Decimal("0")
        assert not StockMove.objects.filter(tenant=tenant_a, reference=adj.number).exists()

    def test_post_cumulative_weighted_average_end_to_end(self, client_a, tenant_a, item_a, location_a):
        """Priority regression 3, full view flow: two lines for the SAME item at different unit
        costs in one adjustment must blend cumulatively (11.3636), not from a stale pre-post read
        (10.9091)."""
        from apps.scm.models import StockAdjustment
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("100"),
                         unit_cost=Decimal("10.00"), move_type="receipt")
        data = {
            "location": str(location_a.pk), "reason": "found", "adjustment_date": "2026-01-20", "notes": "",
            **formset_data("lines", [
                {"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity_delta": "5", "unit_cost": "20.00"},
                {"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity_delta": "5", "unit_cost": "30.00"},
            ]),
        }
        resp = client_a.post(reverse("scm:stockadjustment_create"), data)
        assert resp.status_code == 302
        adj = StockAdjustment.objects.get(tenant=tenant_a)
        assert adj.lines.count() == 2
        resp2 = client_a.post(reverse("scm:stockadjustment_post", args=[adj.pk]))
        assert resp2.status_code == 302
        item_a.refresh_from_db()
        assert item_a.average_cost == Decimal("11.3636")
        assert item_a.on_hand() == Decimal("110")

    def test_cancel_draft_becomes_cancelled(self, client_a, stock_adjustment_a):
        resp = client_a.post(reverse("scm:stockadjustment_cancel", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 302
        stock_adjustment_a.refresh_from_db()
        assert stock_adjustment_a.status == "cancelled"

    def test_cancel_posted_is_refused(self, client_a, stock_adjustment_a):
        client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        resp = client_a.post(reverse("scm:stockadjustment_cancel", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 302
        stock_adjustment_a.refresh_from_db()
        assert stock_adjustment_a.status == "posted"  # unchanged

    def test_get_post_returns_405(self, client_a, stock_adjustment_a):
        assert client_a.get(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk])).status_code == 405


# ================================================================ Reports
class TestValuationReport:
    def test_returns_200_and_includes_weighted_average_item(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.get(reverse("scm:valuation_report"))
        assert resp.status_code == 200
        rows = {r["item"].pk: r for r in resp.context["rows"]}
        assert rows[item_a.pk]["on_hand"] == Decimal("10")
        assert rows[item_a.pk]["value"] == Decimal("50.00")

    def test_fifo_valuation_excludes_transfers(
        self, client_a, tenant_a, item_fifo_a, location_a, location_a2,
    ):
        """Priority regression 4: layers 40@290 + 15@330, then a transfer of 5 between locations —
        the transfer must NOT consume a FIFO layer. Value stays 16550.00, on_hand stays 55."""
        from apps.scm.models import StockTransfer, StockTransferLine
        from apps.scm.views._helpers import _post_stock_move, _post_transfer

        _post_stock_move(tenant_a, item=item_fifo_a, location=location_a, quantity=Decimal("40"),
                         unit_cost=Decimal("290"), move_type="receipt")
        _post_stock_move(tenant_a, item=item_fifo_a, location=location_a, quantity=Decimal("15"),
                         unit_cost=Decimal("330"), move_type="receipt")
        transfer = StockTransfer.objects.create(
            tenant=tenant_a, from_location=location_a, to_location=location_a2,
            transfer_date=datetime.date(2026, 1, 20),
        )
        StockTransferLine.objects.create(transfer=transfer, item=item_fifo_a, quantity=Decimal("5"))
        _post_transfer(transfer, user=None)

        resp = client_a.get(reverse("scm:valuation_report"))
        assert resp.status_code == 200
        rows = {r["item"].pk: r for r in resp.context["rows"]}
        assert rows[item_fifo_a.pk]["on_hand"] == Decimal("55")
        assert rows[item_fifo_a.pk]["value"] == Decimal("16550.00")

    def test_lifo_valuation_consumes_the_newest_layer_first(self, client_a, tenant_a, location_a):
        """LIFO: layers 10@100 (older) + 10@200 (newer); an issue of 5 consumes from the NEWEST
        layer — remaining value = 10*100 + 5*200 = 2000.00, not 10*100 + 5*100."""
        from django.utils import timezone
        from apps.scm.models import Item
        from apps.scm.views._helpers import _post_stock_move
        item = Item.objects.create(tenant=tenant_a, sku="LIFO-1", name="LIFO Widget", costing_method="lifo")
        _post_stock_move(tenant_a, item=item, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("100"), move_type="receipt")
        _post_stock_move(tenant_a, item=item, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("200"), move_type="receipt")
        _post_stock_move(tenant_a, item=item, location=location_a, quantity=Decimal("-5"),
                         unit_cost=Decimal("200"), move_type="issue", moved_at=timezone.now())
        resp = client_a.get(reverse("scm:valuation_report"))
        rows = {r["item"].pk: r for r in resp.context["rows"]}
        assert rows[item.pk]["on_hand"] == Decimal("15")
        assert rows[item.pk]["value"] == Decimal("2000.00")

    def test_zero_stock_item_excluded_from_rows(self, client_a, tenant_a, item_a):
        """An item with no stock movements at all (on_hand <= 0) must be skipped, not listed at
        zero value."""
        resp = client_a.get(reverse("scm:valuation_report"))
        rows = {r["item"].pk: r for r in resp.context["rows"]}
        assert item_a.pk not in rows


class TestReorderAlerts:
    def test_returns_200_and_flags_a_low_stock_rule(self, client_a, tenant_a, reorder_rule_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("2"),
                         unit_cost=Decimal("5.00"), move_type="receipt")  # below reorder_point=10
        resp = client_a.get(reverse("scm:reorder_alerts"))
        assert resp.status_code == 200
        alert_rule_pks = {a["rule"].pk for a in resp.context["alerts"]}
        assert reorder_rule_a.pk in alert_rule_pks

    def test_excludes_a_rule_above_its_reorder_point(self, client_a, tenant_a, reorder_rule_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("50"),
                         unit_cost=Decimal("5.00"), move_type="receipt")  # above reorder_point=10
        resp = client_a.get(reverse("scm:reorder_alerts"))
        alert_rule_pks = {a["rule"].pk for a in resp.context["alerts"]}
        assert reorder_rule_a.pk not in alert_rule_pks

    def test_query_count_does_not_scale_with_rule_count(self, client_a, tenant_a, django_assert_max_num_queries):
        from apps.scm.models import Item, Location, ReorderRule
        for i in range(20):
            item = Item.objects.create(tenant=tenant_a, sku=f"RR-{i:03d}", name=f"Reorder item {i}")
            loc = Location.objects.create(tenant=tenant_a, code=f"RRW-{i:03d}", name=f"Reorder WH {i}")
            ReorderRule.objects.create(tenant=tenant_a, item=item, location=loc, reorder_point=Decimal("10"))
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:reorder_alerts"))
        assert resp.status_code == 200


class TestStockLedger:
    def test_returns_200_with_moves(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt", reference="TEST-REF")
        resp = client_a.get(reverse("scm:stock_ledger"))
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) == 1

    def test_filter_by_move_type(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.get(reverse("scm:stock_ledger"), {"move_type": "issue"})
        assert len(resp.context["object_list"]) == 0

    def test_junk_item_and_location_filters_return_200_not_500(self, client_a):
        resp = client_a.get(reverse("scm:stock_ledger"), {"item": "abc", "location": "xyz"})
        assert resp.status_code == 200

    def test_search_by_reference(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt", reference="FIND-ME")
        resp = client_a.get(reverse("scm:stock_ledger"), {"q": "FIND-ME"})
        assert len(resp.context["object_list"]) == 1
        resp2 = client_a.get(reverse("scm:stock_ledger"), {"q": "no-such-reference"})
        assert len(resp2.context["object_list"]) == 0


class TestOnHandByLocation:
    def test_returns_200_and_groups_by_location(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.get(reverse("scm:on_hand_by_location"))
        assert resp.status_code == 200
        assert location_a.code in resp.context["grouped"]

    def test_zero_net_moves_are_excluded(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("-10"),
                         unit_cost=Decimal("5.00"), move_type="issue")
        resp = client_a.get(reverse("scm:on_hand_by_location"))
        assert resp.status_code == 200
        assert location_a.code not in resp.context["grouped"]


class TestOverviewQueryCount:
    """scm:overview must not scale with the number of reorder rules (on_hand_map perf regression)."""

    def test_query_count_does_not_scale_with_rule_count(self, client_a, tenant_a, django_assert_max_num_queries):
        from apps.scm.models import Item, Location, ReorderRule
        for i in range(20):
            item = Item.objects.create(tenant=tenant_a, sku=f"OV-{i:03d}", name=f"Overview item {i}")
            loc = Location.objects.create(tenant=tenant_a, code=f"OVW-{i:03d}", name=f"Overview WH {i}")
            ReorderRule.objects.create(tenant=tenant_a, item=item, location=loc, reorder_point=Decimal("10"))
        with django_assert_max_num_queries(25):
            resp = client_a.get(reverse("scm:overview"))
        assert resp.status_code == 200


# ================================================================ Negative-input hardening
class TestInventoryNegativeInputHardening:
    def test_stocktransferline_quantity_nan_is_rejected_not_500(self, client_a, location_a, location_a2, item_a):
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "NaN"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 200  # re-rendered form with an error, not a 500
        from apps.scm.models import StockTransfer
        assert not StockTransfer.objects.exists()

    def test_stocktransferline_quantity_infinity_is_rejected_not_500(self, client_a, location_a, location_a2, item_a):
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "Infinity"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import StockTransfer
        assert not StockTransfer.objects.exists()

    def test_stocktransferline_quantity_negative_is_rejected_not_500(self, client_a, location_a, location_a2, item_a):
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "-5"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import StockTransfer
        assert not StockTransfer.objects.exists()

    def test_stockadjustmentline_unit_cost_garbage_is_rejected_not_500(self, client_a, location_a, item_a):
        data = {
            "location": str(location_a.pk), "reason": "cycle_count", "adjustment_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "quantity_delta": "5", "unit_cost": "not-a-number"}]),
        }
        resp = client_a.post(reverse("scm:stockadjustment_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import StockAdjustment
        assert not StockAdjustment.objects.exists()

    def test_stockadjustmentline_unit_cost_over_max_digits_is_rejected_not_500(self, client_a, location_a, item_a):
        data = {
            "location": str(location_a.pk), "reason": "cycle_count", "adjustment_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "quantity_delta": "5", "unit_cost": "9999999.9999"}]),
        }
        resp = client_a.post(reverse("scm:stockadjustment_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import StockAdjustment
        assert not StockAdjustment.objects.exists()

    def test_item_standard_cost_nan_is_rejected_not_500(self, client_a):
        data = {
            "sku": "BAD-COST", "name": "Bad cost item", "category": "", "uom": "",
            "item_type": "stock", "tracking": "none", "costing_method": "weighted_avg",
            "standard_cost": "NaN", "reorder_point": "0", "description": "", "is_active": "on",
        }
        resp = client_a.post(reverse("scm:item_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import Item
        assert not Item.objects.filter(sku="BAD-COST").exists()

    def test_uom_factor_infinity_is_rejected_not_500(self, client_a):
        data = {"code": "BAD", "name": "Bad UOM", "factor": "Infinity", "is_active": "on"}
        resp = client_a.post(reverse("scm:uom_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import UOM
        assert not UOM.objects.filter(code="BAD").exists()


# ================================================================ Create guarded when the user has no tenant
class TestInventoryCreateWithoutTenantWorkspace:
    def _tenantless_client(self, db):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(email="orphan2@example.com", username="orphan2", password="x", tenant=None)
        c = Client()
        c.force_login(user)
        return c

    def test_item_create_redirects(self, db):
        from apps.scm.models import Item
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:item_create"))
        assert resp.status_code == 302
        assert Item.objects.count() == 0

    def test_location_create_redirects(self, db):
        from apps.scm.models import Location
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:location_create"))
        assert resp.status_code == 302
        assert Location.objects.count() == 0

    def test_stocktransfer_create_redirects(self, db):
        from apps.scm.models import StockTransfer
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:stocktransfer_create"))
        assert resp.status_code == 302
        assert StockTransfer.objects.count() == 0

    def test_stockadjustment_create_redirects(self, db):
        from apps.scm.models import StockAdjustment
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:stockadjustment_create"))
        assert resp.status_code == 302
        assert StockAdjustment.objects.count() == 0


# ================================================================================================
# SCM 4.4 Warehouse Management
# ================================================================================================

# ================================================================ PutawayTask CRUD
class TestPutawayTaskCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, putawaytask_a):
        resp = client_a.get(reverse("scm:putawaytask_list"))
        assert resp.status_code == 200
        assert putawaytask_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, putawaytask_a, putawaytask_b):
        resp = client_a.get(reverse("scm:putawaytask_list"))
        assert putawaytask_b not in resp.context["object_list"]

    def test_list_search_by_item_sku(self, client_a, putawaytask_a, item_a):
        resp = client_a.get(reverse("scm:putawaytask_list"), {"q": item_a.sku})
        assert putawaytask_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:putawaytask_list"), {"q": "no-match-at-all"})
        assert putawaytask_a not in resp2.context["object_list"]

    def test_list_filter_by_status(self, client_a, putawaytask_a):
        resp = client_a.get(reverse("scm:putawaytask_list"), {"status": "pending"})
        assert putawaytask_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:putawaytask_list"), {"status": "completed"})
        assert putawaytask_a not in resp2.context["object_list"]

    def test_list_junk_to_location_filter_returns_200_not_500(self, client_a, putawaytask_a):
        resp = client_a.get(reverse("scm:putawaytask_list"), {"to_location": "not-an-id"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, putawaytask_a):
        resp = client_a.get(reverse("scm:putawaytask_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_page_2_when_rows_exceed_page_size(self, client_a, tenant_a, item_a, location_a, location_a2):
        from apps.scm.models import PutawayTask
        for i in range(20):
            PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                       to_location=location_a2, quantity=Decimal("1"))
        resp1 = client_a.get(reverse("scm:putawaytask_list"))
        resp2 = client_a.get(reverse("scm:putawaytask_list"), {"page": "2"})
        assert resp1.status_code == 200 and resp2.status_code == 200
        assert set(o.pk for o in resp1.context["object_list"]) != set(o.pk for o in resp2.context["object_list"])

    def test_create_get_renders_an_empty_form(self, client_a):
        resp = client_a.get(reverse("scm:putawaytask_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, item_a, location_a, location_a2):
        from apps.scm.models import PutawayTask
        data = {
            "goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "5", "strategy": "directed", "assigned_to": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:putawaytask_create"), data)
        assert resp.status_code == 302
        task = PutawayTask.objects.get(tenant=tenant_a)
        assert task.number == "PUT-00001"
        assert task.status == "pending"

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, item_a, location_a, location_a2):
        from apps.scm.models import PutawayTask
        data = {
            "goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "5", "strategy": "directed", "assigned_to": "", "notes": "",
            "status": "completed", "number": "PUT-99999",
        }
        resp = client_a.post(reverse("scm:putawaytask_create"), data)
        assert resp.status_code == 302
        task = PutawayTask.objects.get(tenant=tenant_a)
        assert task.status == "pending"
        assert task.number == "PUT-00001"

    def test_edit_updates_fields(self, client_a, putawaytask_a, item_a, location_a, location_a2):
        data = {
            "goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "9", "strategy": "fixed", "assigned_to": "", "notes": "Updated",
        }
        resp = client_a.post(reverse("scm:putawaytask_edit", args=[putawaytask_a.pk]), data)
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.quantity == Decimal("9")
        assert putawaytask_a.strategy == "fixed"
        assert putawaytask_a.notes == "Updated"

    def test_edit_blocked_once_completed(self, client_a, tenant_a, putawaytask_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        resp = client_a.get(reverse("scm:putawaytask_edit", args=[putawaytask_a.pk]))
        assert resp.status_code == 302

    def test_detail_returns_200_with_context(self, client_a, putawaytask_a):
        resp = client_a.get(reverse("scm:putawaytask_detail", args=[putawaytask_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == putawaytask_a
        assert resp.context["available"] == Decimal("0")

    def test_delete_pending_removes_it(self, client_a, putawaytask_a):
        pk = putawaytask_a.pk
        resp = client_a.post(reverse("scm:putawaytask_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import PutawayTask
        assert not PutawayTask.objects.filter(pk=pk).exists()

    def test_get_delete_returns_405(self, client_a, putawaytask_a):
        assert client_a.get(reverse("scm:putawaytask_delete", args=[putawaytask_a.pk])).status_code == 405


# ================================================================ PutawayTask lifecycle
class TestPutawayTaskLifecycle:
    def test_start_pending_to_in_progress_claims_assignee(self, client_a, putawaytask_a, admin_user):
        resp = client_a.post(reverse("scm:putawaytask_start", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "in_progress"
        assert putawaytask_a.assigned_to_id == admin_user.pk

    def test_start_twice_is_a_noop(self, client_a, putawaytask_a):
        client_a.post(reverse("scm:putawaytask_start", args=[putawaytask_a.pk]))
        resp = client_a.post(reverse("scm:putawaytask_start", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "in_progress"

    def test_complete_posts_paired_moves_and_closes(
        self, client_a, tenant_a, putawaytask_a, location_a, location_a2, item_a,
    ):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "completed"
        assert putawaytask_a.completed_at is not None
        assert item_a.on_hand(location=location_a) == Decimal("5")
        assert item_a.on_hand(location=location_a2) == Decimal("5")
        assert StockMove.objects.filter(tenant=tenant_a, reference=putawaytask_a.number).count() == 2

    def test_complete_refused_when_source_never_held_stock(self, client_a, putawaytask_a, location_a, item_a):
        """Absent-prerequisite (L35): the staging location has never held this item — refused."""
        resp = client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "pending"
        assert item_a.on_hand(location=location_a) == Decimal("0")

    def test_complete_already_completed_is_a_noop(
        self, client_a, tenant_a, putawaytask_a, location_a, item_a,
    ):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        resp = client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        assert StockMove.objects.filter(tenant=tenant_a, reference=putawaytask_a.number).count() == 2

    def test_cancel_open_task_becomes_cancelled(self, client_a, putawaytask_a):
        resp = client_a.post(reverse("scm:putawaytask_cancel", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "cancelled"

    def test_cancel_completed_is_refused(self, client_a, tenant_a, putawaytask_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        resp = client_a.post(reverse("scm:putawaytask_cancel", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "completed"  # unchanged

    def test_delete_completed_is_refused(self, client_a, tenant_a, putawaytask_a, location_a, item_a):
        from apps.scm.models import PutawayTask
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        resp = client_a.post(reverse("scm:putawaytask_delete", args=[putawaytask_a.pk]))
        assert resp.status_code == 302
        assert PutawayTask.objects.filter(pk=putawaytask_a.pk).exists()

    def test_get_complete_returns_405(self, client_a, putawaytask_a):
        assert client_a.get(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk])).status_code == 405


# ================================================================ PickTask CRUD
class TestPickTaskCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, picktask_a):
        resp = client_a.get(reverse("scm:picktask_list"))
        assert resp.status_code == 200
        assert picktask_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, picktask_a, picktask_b):
        resp = client_a.get(reverse("scm:picktask_list"))
        assert picktask_b not in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, picktask_a):
        resp = client_a.get(reverse("scm:picktask_list"), {"status": "pending"})
        assert picktask_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:picktask_list"), {"status": "packed"})
        assert picktask_a not in resp2.context["object_list"]

    def test_list_junk_zone_filter_returns_200_not_500(self, client_a, picktask_a):
        resp = client_a.get(reverse("scm:picktask_list"), {"zone": "not-an-id"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, picktask_a):
        resp = client_a.get(reverse("scm:picktask_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_create_get_renders_an_empty_form_and_formset(self, client_a):
        resp = client_a.get(reverse("scm:picktask_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, location_a, item_a):
        from apps.scm.models import PickTask
        data = {
            "strategy": "single", "zone": "", "wave_ref": "", "assigned_to": "",
            "ship_to": "Acme HQ", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "from_location": str(location_a.pk),
                                      "quantity_requested": "5", "quantity_picked": "0", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:picktask_create"), data)
        assert resp.status_code == 302
        task = PickTask.objects.get(tenant=tenant_a)
        assert task.number == "PIK-00001"
        assert task.lines.count() == 1

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, location_a, item_a):
        from apps.scm.models import PickTask
        data = {
            "strategy": "single", "zone": "", "wave_ref": "", "assigned_to": "",
            "ship_to": "", "notes": "", "status": "picked", "number": "PIK-99999",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "from_location": str(location_a.pk),
                                      "quantity_requested": "5", "quantity_picked": "0", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:picktask_create"), data)
        assert resp.status_code == 302
        task = PickTask.objects.get(tenant=tenant_a)
        assert task.status == "pending"
        assert task.number == "PIK-00001"

    def test_edit_updates_fields(self, client_a, picktask_a, location_a, item_a):
        line = picktask_a.lines.first()
        data = {
            "strategy": "wave", "zone": "", "wave_ref": "WAVE-1", "assigned_to": "",
            "ship_to": "Updated dest", "notes": "",
            **formset_data("lines", [{"id": line.pk, "item": str(item_a.pk), "lot_serial": "",
                                      "from_location": str(location_a.pk),
                                      "quantity_requested": "5", "quantity_picked": "0", "notes": ""}],
                           initial=1),
        }
        resp = client_a.post(reverse("scm:picktask_edit", args=[picktask_a.pk]), data)
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.wave_ref == "WAVE-1"
        assert picktask_a.ship_to == "Updated dest"

    def test_edit_blocked_once_picking(self, client_a, picktask_a):
        picktask_a.status = "picking"
        picktask_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:picktask_edit", args=[picktask_a.pk]))
        assert resp.status_code == 302

    def test_detail_returns_200_with_context(self, client_a, picktask_a):
        resp = client_a.get(reverse("scm:picktask_detail", args=[picktask_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == picktask_a
        assert len(resp.context["line_rows"]) == 1

    def test_delete_pending_removes_it(self, client_a, picktask_a):
        pk = picktask_a.pk
        resp = client_a.post(reverse("scm:picktask_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import PickTask
        assert not PickTask.objects.filter(pk=pk).exists()

    def test_delete_released_is_refused(self, client_a, picktask_a):
        from apps.scm.models import PickTask
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_delete", args=[picktask_a.pk]))
        assert resp.status_code == 302
        assert PickTask.objects.filter(pk=picktask_a.pk).exists()

    def test_get_delete_returns_405(self, client_a, picktask_a):
        assert client_a.get(reverse("scm:picktask_delete", args=[picktask_a.pk])).status_code == 405


# ================================================================ PickTask lifecycle (pick + pack)
class TestPickTaskLifecycle:
    def test_release_requires_at_least_one_line(self, client_a, tenant_a):
        from apps.scm.models import PickTask
        empty = PickTask.objects.create(tenant=tenant_a)
        resp = client_a.post(reverse("scm:picktask_release", args=[empty.pk]))
        assert resp.status_code == 302
        empty.refresh_from_db()
        assert empty.status == "pending"

    def test_release_pending_to_released(self, client_a, picktask_a):
        resp = client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "released"

    def test_release_twice_is_a_noop(self, client_a, picktask_a):
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "released"

    def test_start_released_to_picking(self, client_a, picktask_a):
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_start", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "picking"

    def test_start_before_release_is_refused(self, client_a, picktask_a):
        resp = client_a.post(reverse("scm:picktask_start", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "pending"

    def test_confirm_from_picking_posts_the_full_pick(
        self, client_a, tenant_a, picktask_a, location_a, item_a,
    ):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        client_a.post(reverse("scm:picktask_start", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "picked"
        assert picktask_a.picked_at is not None
        assert item_a.on_hand(location=location_a) == Decimal("5")
        assert StockMove.objects.filter(tenant=tenant_a, reference=picktask_a.number).count() == 1

    def test_confirm_directly_from_released_also_works(
        self, client_a, tenant_a, picktask_a, location_a, item_a,
    ):
        """PICKABLE_STATUSES includes 'released' — a picker may confirm without a separate start."""
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "picked"

    def test_short_pick_sets_is_short_and_warns(self, client_a, tenant_a, picktask_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = Decimal("2")  # requested 5
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]), follow=True)
        picktask_a.refresh_from_db()
        assert picktask_a.status == "picked"
        assert picktask_a.is_short() is True
        msgs = [str(m) for m in resp.context["messages"]]
        assert any("short" in m.lower() for m in msgs)

    def test_confirm_with_nothing_picked_is_refused(self, client_a, picktask_a):
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "released"  # refused — nothing to confirm

    def test_confirm_over_available_bin_stock_is_refused(
        self, client_a, tenant_a, picktask_a, location_a, item_a,
    ):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("2"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = Decimal("5")
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "released"  # refused
        assert item_a.on_hand(location=location_a) == Decimal("2")  # unchanged

    def test_confirm_twice_does_not_double_post(self, client_a, tenant_a, picktask_a, location_a, item_a):
        from apps.scm.models import StockMove
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        assert resp.status_code == 302
        assert StockMove.objects.filter(tenant=tenant_a, reference=picktask_a.number).count() == 1

    def test_pack_after_picked_captures_details(self, client_a, tenant_a, picktask_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_pack", args=[picktask_a.pk]),
                             {"package_count": "2", "package_weight": "3.500", "tracking_ref": "TRK123"})
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "packed"
        assert picktask_a.package_count == 2
        assert picktask_a.package_weight == Decimal("3.500")
        assert picktask_a.tracking_ref == "TRK123"
        assert picktask_a.packed_at is not None

    def test_pack_before_picked_is_refused(self, client_a, picktask_a):
        resp = client_a.post(reverse("scm:picktask_pack", args=[picktask_a.pk]), {"package_count": "1"})
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "pending"
        assert picktask_a.package_count is None

    def test_cancel_pending_becomes_cancelled(self, client_a, picktask_a):
        resp = client_a.post(reverse("scm:picktask_cancel", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "cancelled"

    def test_cancel_picked_task_is_refused(self, client_a, tenant_a, picktask_a, location_a, item_a):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("10"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        line = picktask_a.lines.first()
        line.quantity_picked = line.quantity_requested
        line.save(update_fields=["quantity_picked"])
        client_a.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        client_a.post(reverse("scm:picktask_confirm", args=[picktask_a.pk]))
        resp = client_a.post(reverse("scm:picktask_cancel", args=[picktask_a.pk]))
        assert resp.status_code == 302
        picktask_a.refresh_from_db()
        assert picktask_a.status == "picked"  # unchanged — stock already moved

    def test_get_confirm_returns_405(self, client_a, picktask_a):
        assert client_a.get(reverse("scm:picktask_confirm", args=[picktask_a.pk])).status_code == 405


# ================================================================ CycleCountTask CRUD
class TestCycleCountTaskCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, cyclecounttask_a):
        resp = client_a.get(reverse("scm:cyclecounttask_list"))
        assert resp.status_code == 200
        assert cyclecounttask_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, cyclecounttask_a, cyclecounttask_b):
        resp = client_a.get(reverse("scm:cyclecounttask_list"))
        assert cyclecounttask_b not in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, cyclecounttask_a):
        resp = client_a.get(reverse("scm:cyclecounttask_list"), {"status": "scheduled"})
        assert cyclecounttask_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:cyclecounttask_list"), {"status": "reconciled"})
        assert cyclecounttask_a not in resp2.context["object_list"]

    def test_list_junk_location_filter_returns_200_not_500(self, client_a, cyclecounttask_a):
        resp = client_a.get(reverse("scm:cyclecounttask_list"), {"location": "not-an-id"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, cyclecounttask_a):
        resp = client_a.get(reverse("scm:cyclecounttask_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, location_a, item_a):
        from apps.scm.models import CycleCountTask
        data = {
            "location": str(location_a.pk), "scheduled_date": "2026-01-25", "count_method": "full",
            "assigned_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "counted_quantity": "", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_create"), data)
        assert resp.status_code == 302
        task = CycleCountTask.objects.get(tenant=tenant_a)
        assert task.number == "CC-00001"
        assert task.lines.count() == 1

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a, location_a, item_a):
        from apps.scm.models import CycleCountTask
        data = {
            "location": str(location_a.pk), "scheduled_date": "2026-01-25", "count_method": "full",
            "assigned_to": "", "notes": "", "status": "reconciled", "number": "CC-99999",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "counted_quantity": "", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_create"), data)
        assert resp.status_code == 302
        task = CycleCountTask.objects.get(tenant=tenant_a)
        assert task.status == "scheduled"
        assert task.number == "CC-00001"

    def test_edit_updates_fields(self, client_a, cyclecounttask_a, item_a):
        line = cyclecounttask_a.lines.first()
        data = {
            "location": str(cyclecounttask_a.location_id), "scheduled_date": "2026-01-30",
            "count_method": "abc", "assigned_to": "", "notes": "Updated",
            **formset_data("lines", [{"id": line.pk, "item": str(item_a.pk), "lot_serial": "",
                                      "counted_quantity": "", "notes": ""}], initial=1),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_a.pk]), data)
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.count_method == "abc"
        assert cyclecounttask_a.notes == "Updated"

    def test_edit_blocked_once_counted(self, client_a, cyclecounttask_a):
        cyclecounttask_a.status = "counted"
        cyclecounttask_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302

    def test_detail_returns_200_with_context(self, client_a, cyclecounttask_a):
        resp = client_a.get(reverse("scm:cyclecounttask_detail", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == cyclecounttask_a
        assert resp.context["variance_count"] == 0
        assert resp.context["net_variance"] == Decimal("0")

    def test_delete_scheduled_removes_it(self, client_a, cyclecounttask_a):
        pk = cyclecounttask_a.pk
        resp = client_a.post(reverse("scm:cyclecounttask_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import CycleCountTask
        assert not CycleCountTask.objects.filter(pk=pk).exists()

    def test_get_delete_returns_405(self, client_a, cyclecounttask_a):
        assert client_a.get(reverse("scm:cyclecounttask_delete", args=[cyclecounttask_a.pk])).status_code == 405


# ================================================================ CycleCountTask lifecycle
class TestCycleCountTaskLifecycle:
    def test_start_snapshots_expected_quantity_from_the_ledger(
        self, client_a, tenant_a, cyclecounttask_a, location_a, item_a,
    ):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("12"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        resp = client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "in_progress"
        assert cyclecounttask_a.started_at is not None
        line = cyclecounttask_a.lines.first()
        assert line.expected_quantity == Decimal("12")
        assert line.counted_quantity is None  # still distinguishable from counted-zero

    def test_start_without_lines_is_refused(self, client_a, tenant_a, location_a):
        from apps.scm.models import CycleCountTask
        empty = CycleCountTask.objects.create(tenant=tenant_a, location=location_a,
                                              scheduled_date=datetime.date(2026, 1, 20))
        resp = client_a.post(reverse("scm:cyclecounttask_start", args=[empty.pk]))
        assert resp.status_code == 302
        empty.refresh_from_db()
        assert empty.status == "scheduled"

    def test_start_twice_is_a_noop(self, client_a, cyclecounttask_a):
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "in_progress"

    def test_complete_requires_every_line_counted(self, client_a, cyclecounttask_a):
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "in_progress"  # refused, still uncounted

    def test_complete_with_all_lines_counted_moves_to_counted(self, client_a, cyclecounttask_a):
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        line.counted_quantity = Decimal("0")  # counted ZERO — distinct from uncounted (None)
        line.save(update_fields=["counted_quantity"])
        resp = client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "counted"
        assert cyclecounttask_a.counted_at is not None

    def test_reconcile_creates_exactly_one_stock_adjustment(
        self, client_a, tenant_a, cyclecounttask_a, item_a, location_a,
    ):
        from apps.scm.models import StockAdjustment
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        line.counted_quantity = Decimal("8")  # expected 0 -> variance +8
        line.save(update_fields=["counted_quantity"])
        client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "reconciled"
        assert cyclecounttask_a.reconciled_at is not None
        assert cyclecounttask_a.adjustment is not None
        assert StockAdjustment.objects.filter(tenant=tenant_a, cycle_counts=cyclecounttask_a).count() == 1
        assert item_a.on_hand(location=location_a) == Decimal("8")

    def test_reconcile_twice_does_not_double_apply(
        self, client_a, tenant_a, cyclecounttask_a, item_a, location_a,
    ):
        from apps.scm.models import StockMove
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        line.counted_quantity = Decimal("8")
        line.save(update_fields=["counted_quantity"])
        client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        cyclecounttask_a.refresh_from_db()
        adjustment_number = cyclecounttask_a.adjustment.number
        resp = client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.adjustment.number == adjustment_number  # no second adjustment
        assert item_a.on_hand(location=location_a) == Decimal("8")  # not doubled to 16
        assert StockMove.objects.filter(tenant=tenant_a, reference=adjustment_number).count() == 1

    def test_reconcile_with_no_variance_creates_no_adjustment(self, client_a, tenant_a, cyclecounttask_a):
        from apps.scm.models import StockAdjustment
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        line.counted_quantity = Decimal("0")  # matches expected (0) exactly
        line.save(update_fields=["counted_quantity"])
        client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "reconciled"
        assert cyclecounttask_a.adjustment is None
        assert not StockAdjustment.objects.filter(tenant=tenant_a).exists()

    def test_cancel_scheduled_becomes_cancelled(self, client_a, cyclecounttask_a):
        resp = client_a.post(reverse("scm:cyclecounttask_cancel", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "cancelled"

    def test_cancel_reconciled_is_refused(self, client_a, tenant_a, cyclecounttask_a):
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        line.counted_quantity = Decimal("0")
        line.save(update_fields=["counted_quantity"])
        client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_cancel", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "reconciled"  # unchanged

    def test_delete_reconciled_is_refused(self, client_a, tenant_a, cyclecounttask_a):
        from apps.scm.models import CycleCountTask
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        line.counted_quantity = Decimal("0")
        line.save(update_fields=["counted_quantity"])
        client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_delete", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        assert CycleCountTask.objects.filter(pk=cyclecounttask_a.pk).exists()

    def test_get_reconcile_returns_405(self, client_a, cyclecounttask_a):
        assert client_a.get(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk])).status_code == 405


# ================================================================================================
# Priority regression 1b — the started-count composition freeze (end-to-end via the real view)
# ================================================================================================
class TestCycleCountTaskLockRegression:
    """A CycleCountTask past 'scheduled' must not accept new formset rows or an item swap on an
    existing line — see BaseCycleCountTaskLineFormSet. The lock must not break ordinary counting."""

    def test_still_scheduled_count_accepts_a_new_line(self, client_a, cyclecounttask_a, item_lot_a):
        line = cyclecounttask_a.lines.first()
        data = {
            "location": str(cyclecounttask_a.location_id), "scheduled_date": "2026-01-20",
            "count_method": "full", "assigned_to": "", "notes": "",
            **formset_data("lines", [
                {"id": line.pk, "item": str(line.item_id), "lot_serial": "",
                 "counted_quantity": "", "notes": ""},
                {"id": "", "item": str(item_lot_a.pk), "lot_serial": "",
                 "counted_quantity": "", "notes": ""},
            ], initial=1),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_a.pk]), data)
        assert resp.status_code == 302
        assert cyclecounttask_a.lines.count() == 2

    def test_extra_row_after_start_is_rejected_line_count_unchanged(
        self, client_a, cyclecounttask_a, item_lot_a,
    ):
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "in_progress"
        line = cyclecounttask_a.lines.first()
        data = {
            "location": str(cyclecounttask_a.location_id), "scheduled_date": "2026-01-20",
            "count_method": "full", "assigned_to": "", "notes": "",
            **formset_data("lines", [
                {"id": line.pk, "item": str(line.item_id), "lot_serial": "",
                 "counted_quantity": "7", "notes": ""},
                {"id": "", "item": str(item_lot_a.pk), "lot_serial": "",
                 "counted_quantity": "3", "notes": ""},
            ], initial=1),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_a.pk]), data)
        assert resp.status_code == 200  # re-rendered with an error, not saved
        assert cyclecounttask_a.lines.count() == 1
        line.refresh_from_db()
        assert line.counted_quantity is None  # the whole POST was rejected, nothing saved

    def test_item_swap_on_existing_line_is_ignored_but_counted_quantity_still_saves(
        self, client_a, cyclecounttask_a, item_lot_a,
    ):
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        cyclecounttask_a.refresh_from_db()
        line = cyclecounttask_a.lines.first()
        original_item_id = line.item_id
        data = {
            "location": str(cyclecounttask_a.location_id), "scheduled_date": "2026-01-20",
            "count_method": "full", "assigned_to": "", "notes": "",
            **formset_data("lines", [
                {"id": line.pk, "item": str(item_lot_a.pk), "lot_serial": "",
                 "counted_quantity": "9", "notes": ""},
            ], initial=1),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_a.pk]), data)
        assert resp.status_code == 302  # saved — the disabled item field silently kept its original value
        assert cyclecounttask_a.lines.count() == 1
        line.refresh_from_db()
        assert line.item_id == original_item_id  # swap ignored
        assert line.counted_quantity == Decimal("9")  # the actual job — the count itself — still saved

    def test_reconcile_after_a_rejected_injection_does_not_fabricate_stock_for_the_other_item(
        self, client_a, tenant_a, cyclecounttask_a, item_lot_a,
    ):
        from apps.scm.models import StockAdjustmentLine
        client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        line = cyclecounttask_a.lines.first()
        # Attempted injection of a second, un-snapshotted item — rejected by the lock (test above).
        data = {
            "location": str(cyclecounttask_a.location_id), "scheduled_date": "2026-01-20",
            "count_method": "full", "assigned_to": "", "notes": "",
            **formset_data("lines", [
                {"id": line.pk, "item": str(line.item_id), "lot_serial": "",
                 "counted_quantity": "7", "notes": ""},
                {"id": "", "item": str(item_lot_a.pk), "lot_serial": "",
                 "counted_quantity": "3", "notes": ""},
            ], initial=1),
        }
        client_a.post(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_a.pk]), data)
        # Count the only real line properly, then complete + reconcile.
        line.counted_quantity = Decimal("7")
        line.save(update_fields=["counted_quantity"])
        client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_a.pk]))
        resp = client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302
        assert not StockAdjustmentLine.objects.filter(item=item_lot_a).exists()
        assert item_lot_a.on_hand() == Decimal("0")


# ================================================================================================
# Priority regression 1a — GRN cancel must refuse once its stock has already been put away
# ================================================================================================
class TestGoodsReceiptPutawayCancelRegression:
    """goodsreceipt_cancel must refuse once the received stock has already moved on to a bin via
    putaway — status stays 'received' and staging never goes negative. A receipt still sitting in
    staging must still cancel normally and return its stock (the guard must not be over-broad)."""

    def _receive_po_and_grn(self, tenant_a, location_a, item_a, supplier_a, qty=Decimal("10")):
        from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote, PurchaseOrder, PurchaseOrderLine
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a,
                                          order_date=datetime.date(2026, 1, 5), status="approved")
        line = PurchaseOrderLine.objects.create(purchase_order=po, item_description=item_a.name,
                                                sku_hint=item_a.sku, quantity=qty, unit_price=Decimal("5.00"))
        po.recalc_totals()
        grn = GoodsReceiptNote.objects.create(tenant=tenant_a, purchase_order=po, location=location_a,
                                              receipt_date=datetime.date(2026, 1, 10), status="draft")
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=qty)
        return po, grn

    def test_cancel_refused_after_putaway_moved_the_stock_on(
        self, client_a, tenant_a, location_a, location_a2, item_a, supplier_a,
    ):
        from apps.scm.models import PutawayTask
        _, grn = self._receive_po_and_grn(tenant_a, location_a, item_a, supplier_a)
        resp = client_a.post(reverse("scm:goodsreceipt_receive", args=[grn.pk]))
        assert resp.status_code == 302
        grn.refresh_from_db()
        assert grn.status == "received"
        assert item_a.on_hand(location=location_a) == Decimal("10")

        task = PutawayTask.objects.create(tenant=tenant_a, item=item_a, from_location=location_a,
                                          to_location=location_a2, quantity=Decimal("10"))
        resp = client_a.post(reverse("scm:putawaytask_complete", args=[task.pk]))
        assert resp.status_code == 302
        task.refresh_from_db()
        assert task.status == "completed"
        assert item_a.on_hand(location=location_a) == Decimal("0")
        assert item_a.on_hand(location=location_a2) == Decimal("10")

        resp = client_a.post(reverse("scm:goodsreceipt_cancel", args=[grn.pk]))
        assert resp.status_code == 302  # redirected with an error message, never a 500
        grn.refresh_from_db()
        assert grn.status == "received"  # refused — NOT cancelled
        assert item_a.on_hand(location=location_a) == Decimal("0")  # staging never went negative
        assert item_a.on_hand(location=location_a2) == Decimal("10")  # bin keeps its stock

    def test_cancel_still_works_when_the_stock_is_still_in_staging(
        self, client_a, tenant_a, location_a, item_a, supplier_a,
    ):
        _, grn = self._receive_po_and_grn(tenant_a, location_a, item_a, supplier_a)
        client_a.post(reverse("scm:goodsreceipt_receive", args=[grn.pk]))
        grn.refresh_from_db()
        assert item_a.on_hand(location=location_a) == Decimal("10")

        resp = client_a.post(reverse("scm:goodsreceipt_cancel", args=[grn.pk]))
        assert resp.status_code == 302
        grn.refresh_from_db()
        assert grn.status == "cancelled"
        assert item_a.on_hand(location=location_a) == Decimal("0")  # stock fully returned


# ================================================================ YardVisit CRUD
class TestYardVisitCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, yardvisit_a):
        resp = client_a.get(reverse("scm:yardvisit_list"))
        assert resp.status_code == 200
        assert yardvisit_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, yardvisit_a, yardvisit_b):
        resp = client_a.get(reverse("scm:yardvisit_list"))
        assert yardvisit_b not in resp.context["object_list"]

    def test_list_search_by_carrier_name(self, client_a, yardvisit_a):
        resp = client_a.get(reverse("scm:yardvisit_list"), {"q": "Acme Haulage"})
        assert yardvisit_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:yardvisit_list"), {"q": "No match here"})
        assert yardvisit_a not in resp2.context["object_list"]

    def test_list_filter_by_direction(self, client_a, yardvisit_a):
        resp = client_a.get(reverse("scm:yardvisit_list"), {"direction": "inbound"})
        assert yardvisit_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:yardvisit_list"), {"direction": "outbound"})
        assert yardvisit_a not in resp2.context["object_list"]

    def test_list_junk_dock_door_filter_returns_200_not_500(self, client_a, yardvisit_a):
        resp = client_a.get(reverse("scm:yardvisit_list"), {"dock_door": "not-an-id"})
        assert resp.status_code == 200

    def test_list_page_past_the_end_returns_200(self, client_a, yardvisit_a):
        resp = client_a.get(reverse("scm:yardvisit_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_create_saves_with_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import YardVisit
        data = {
            "carrier_name": "Speedy Freight", "vehicle_ref": "TRK-9", "trailer_ref": "",
            "driver_name": "Sam", "direction": "inbound", "dock_door": "", "purchase_order": "",
            "scheduled_at": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:yardvisit_create"), data)
        assert resp.status_code == 302
        visit = YardVisit.objects.get(tenant=tenant_a, carrier_name="Speedy Freight")
        assert visit.number == "YRD-00001"
        assert visit.status == "scheduled"

    def test_create_ignores_posted_status_and_number(self, client_a, tenant_a):
        from apps.scm.models import YardVisit
        data = {
            "carrier_name": "Hacker Freight", "vehicle_ref": "", "trailer_ref": "", "driver_name": "",
            "direction": "inbound", "dock_door": "", "purchase_order": "", "scheduled_at": "", "notes": "",
            "status": "departed", "number": "YRD-99999",
        }
        resp = client_a.post(reverse("scm:yardvisit_create"), data)
        assert resp.status_code == 302
        visit = YardVisit.objects.get(tenant=tenant_a, carrier_name="Hacker Freight")
        assert visit.status == "scheduled"
        assert visit.number == "YRD-00001"

    def test_edit_updates_fields(self, client_a, yardvisit_a):
        data = {
            "carrier_name": "Renamed Haulage", "vehicle_ref": "TRK-2", "trailer_ref": "",
            "driver_name": "", "direction": "inbound", "dock_door": "", "purchase_order": "",
            "scheduled_at": "", "notes": "Updated",
        }
        resp = client_a.post(reverse("scm:yardvisit_edit", args=[yardvisit_a.pk]), data)
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.carrier_name == "Renamed Haulage"
        assert yardvisit_a.notes == "Updated"

    def test_edit_blocked_once_departed(self, client_a, yardvisit_a):
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        client_a.post(reverse("scm:yardvisit_depart", args=[yardvisit_a.pk]))
        resp = client_a.get(reverse("scm:yardvisit_edit", args=[yardvisit_a.pk]))
        assert resp.status_code == 302

    def test_detail_returns_200_with_context(self, client_a, yardvisit_a):
        resp = client_a.get(reverse("scm:yardvisit_detail", args=[yardvisit_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == yardvisit_a
        assert resp.context["dwell"] is None  # not yet arrived

    def test_get_delete_returns_405(self, client_a, yardvisit_a):
        assert client_a.get(reverse("scm:yardvisit_delete", args=[yardvisit_a.pk])).status_code == 405


# ================================================================ YardVisit lifecycle
class TestYardVisitLifecycle:
    def test_arrive_scheduled_to_arrived_stamps_time(self, client_a, yardvisit_a):
        resp = client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "arrived"
        assert yardvisit_a.arrived_at is not None

    def test_arrive_twice_is_a_noop(self, client_a, yardvisit_a):
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        resp = client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "arrived"

    def test_dock_requires_a_dock_door_assigned(self, client_a, yardvisit_a):
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        resp = client_a.post(reverse("scm:yardvisit_dock", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "arrived"  # refused — no dock door

    def test_dock_with_door_assigned_succeeds(self, client_a, yardvisit_a, location_a):
        yardvisit_a.dock_door = location_a
        yardvisit_a.save(update_fields=["dock_door"])
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        resp = client_a.post(reverse("scm:yardvisit_dock", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "at_dock"
        assert yardvisit_a.docked_at is not None

    def test_depart_from_arrived_stops_the_clock(self, client_a, yardvisit_a):
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        resp = client_a.post(reverse("scm:yardvisit_depart", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "departed"
        assert yardvisit_a.departed_at is not None
        assert yardvisit_a.dwell_minutes() is not None

    def test_depart_before_arrival_is_refused(self, client_a, yardvisit_a):
        resp = client_a.post(reverse("scm:yardvisit_depart", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "scheduled"

    def test_cancel_scheduled_becomes_cancelled(self, client_a, yardvisit_a):
        resp = client_a.post(reverse("scm:yardvisit_cancel", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "cancelled"

    def test_cancel_departed_is_a_noop(self, client_a, yardvisit_a):
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        client_a.post(reverse("scm:yardvisit_depart", args=[yardvisit_a.pk]))
        resp = client_a.post(reverse("scm:yardvisit_cancel", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "departed"  # unchanged

    def test_delete_scheduled_removes_it(self, client_a, yardvisit_a):
        pk = yardvisit_a.pk
        resp = client_a.post(reverse("scm:yardvisit_delete", args=[pk]))
        assert resp.status_code == 302
        from apps.scm.models import YardVisit
        assert not YardVisit.objects.filter(pk=pk).exists()

    def test_delete_arrived_is_refused(self, client_a, yardvisit_a):
        from apps.scm.models import YardVisit
        client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk]))
        resp = client_a.post(reverse("scm:yardvisit_delete", args=[yardvisit_a.pk]))
        assert resp.status_code == 302
        assert YardVisit.objects.filter(pk=yardvisit_a.pk).exists()

    def test_get_arrive_returns_405(self, client_a, yardvisit_a):
        assert client_a.get(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk])).status_code == 405


# ================================================================ Negative-input hardening
class TestWarehouseNegativeInputHardening:
    def test_putawaytask_quantity_nan_is_rejected_not_500(self, client_a, item_a, location_a, location_a2):
        data = {
            "goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "NaN", "strategy": "directed", "assigned_to": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:putawaytask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import PutawayTask
        assert not PutawayTask.objects.exists()

    def test_putawaytask_quantity_infinity_is_rejected_not_500(
        self, client_a, item_a, location_a, location_a2,
    ):
        data = {
            "goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "Infinity", "strategy": "directed", "assigned_to": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:putawaytask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import PutawayTask
        assert not PutawayTask.objects.exists()

    def test_putawaytask_quantity_negative_is_rejected_not_500(
        self, client_a, item_a, location_a, location_a2,
    ):
        data = {
            "goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "-5", "strategy": "directed", "assigned_to": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:putawaytask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import PutawayTask
        assert not PutawayTask.objects.exists()

    def test_picktaskline_quantity_requested_garbage_is_rejected_not_500(self, client_a, item_a, location_a):
        data = {
            "strategy": "single", "zone": "", "wave_ref": "", "assigned_to": "", "ship_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "from_location": str(location_a.pk),
                                      "quantity_requested": "not-a-number", "quantity_picked": "0",
                                      "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:picktask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import PickTask
        assert not PickTask.objects.exists()

    def test_picktaskline_quantity_picked_infinity_is_rejected_not_500(self, client_a, item_a, location_a):
        data = {
            "strategy": "single", "zone": "", "wave_ref": "", "assigned_to": "", "ship_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "from_location": str(location_a.pk),
                                      "quantity_requested": "5", "quantity_picked": "Infinity",
                                      "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:picktask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import PickTask
        assert not PickTask.objects.exists()

    def test_cyclecounttaskline_counted_quantity_nan_is_rejected_not_500(self, client_a, location_a, item_a):
        data = {
            "location": str(location_a.pk), "scheduled_date": "2026-01-25", "count_method": "full",
            "assigned_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "counted_quantity": "NaN", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import CycleCountTask
        assert not CycleCountTask.objects.exists()

    def test_cyclecounttaskline_counted_quantity_negative_is_rejected_not_500(
        self, client_a, location_a, item_a,
    ):
        data = {
            "location": str(location_a.pk), "scheduled_date": "2026-01-25", "count_method": "full",
            "assigned_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "counted_quantity": "-3", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_create"), data)
        assert resp.status_code == 200
        from apps.scm.models import CycleCountTask
        assert not CycleCountTask.objects.exists()

    def test_pack_form_package_weight_nan_is_rejected_not_500(self, client_a, tenant_a, item_a, location_a):
        from apps.scm.models import PickTask, PickTaskLine
        task = PickTask.objects.create(tenant=tenant_a, status="picked")
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("5"), quantity_picked=Decimal("5"))
        resp = client_a.post(reverse("scm:picktask_pack", args=[task.pk]),
                             {"package_count": "1", "package_weight": "NaN", "tracking_ref": ""})
        assert resp.status_code == 302  # invalid pack form -> redirected with an error, never a 500
        task.refresh_from_db()
        assert task.status == "picked"  # unchanged — rejected
        assert task.package_count is None

    def test_pack_form_package_weight_over_max_digits_is_rejected_not_500(
        self, client_a, tenant_a, item_a, location_a,
    ):
        from apps.scm.models import PickTask, PickTaskLine
        task = PickTask.objects.create(tenant=tenant_a, status="picked")
        PickTaskLine.objects.create(pick_task=task, item=item_a, from_location=location_a,
                                    quantity_requested=Decimal("5"), quantity_picked=Decimal("5"))
        resp = client_a.post(reverse("scm:picktask_pack", args=[task.pk]),
                             {"package_count": "1", "package_weight": "9999999999.999", "tracking_ref": ""})
        assert resp.status_code == 302
        task.refresh_from_db()
        assert task.status == "picked"
        assert task.package_weight is None


# ================================================================ Query-count locks
class TestWarehouseQueryCounts:
    def test_cyclecounttask_detail_is_flat_regardless_of_line_count(
        self, client_a, tenant_a, cyclecounttask_a, django_assert_max_num_queries,
    ):
        from apps.scm.models import CycleCountTaskLine, Item
        for i in range(20):
            extra_item = Item.objects.create(tenant=tenant_a, sku=f"CCQ-{i:03d}", name=f"CC item {i}")
            CycleCountTaskLine.objects.create(cycle_count=cyclecounttask_a, item=extra_item)
        with django_assert_max_num_queries(10):
            resp = client_a.get(reverse("scm:cyclecounttask_detail", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 200

    def test_cyclecounttask_start_bulk_updates_rather_than_o_of_lines_writes(
        self, client_a, tenant_a, cyclecounttask_a, django_assert_max_num_queries,
    ):
        from apps.scm.models import CycleCountTaskLine, Item
        for i in range(20):
            extra_item = Item.objects.create(tenant=tenant_a, sku=f"CCS-{i:03d}", name=f"CCS item {i}")
            CycleCountTaskLine.objects.create(cycle_count=cyclecounttask_a, item=extra_item)
        # A single bulk_update() for the whole sheet, not one UPDATE per line — 20 lines would blow
        # this cap if the snapshot ever regressed to a per-line save() loop.
        with django_assert_max_num_queries(18):
            resp = client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 302


# ================================================================ Create guarded when the user has no tenant
class TestWarehouseCreateWithoutTenantWorkspace:
    def _tenantless_client(self, db):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(email="orphan-wms@example.com", username="orphan_wms",
                                        password="x", tenant=None)
        c = Client()
        c.force_login(user)
        return c

    def test_putawaytask_create_redirects(self, db):
        from apps.scm.models import PutawayTask
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:putawaytask_create"))
        assert resp.status_code == 302
        assert PutawayTask.objects.count() == 0

    def test_picktask_create_redirects(self, db):
        from apps.scm.models import PickTask
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:picktask_create"))
        assert resp.status_code == 302
        assert PickTask.objects.count() == 0

    def test_cyclecounttask_create_redirects(self, db):
        from apps.scm.models import CycleCountTask
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:cyclecounttask_create"))
        assert resp.status_code == 302
        assert CycleCountTask.objects.count() == 0

    def test_yardvisit_create_redirects(self, db):
        from apps.scm.models import YardVisit
        c = self._tenantless_client(db)
        resp = c.get(reverse("scm:yardvisit_create"))
        assert resp.status_code == 302
        assert YardVisit.objects.count() == 0
