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

    #: The five 4.7 safety-stock POLICY inputs. They carry model defaults but are NOT `blank=True`,
    #: so ReorderRuleForm renders them required — a POST that omits them is rejected. The browser
    #: form always posts them (the template renders every field with its initial), so this is the
    #: real wire format for this page since 4.7.
    POLICY_FIELDS = {"safety_stock_method": "fixed", "service_level_pct": "95",
                     "lead_time_days": "0", "lead_time_variability_days": "0",
                     "review_period_days": "0", "seasonality_profile": "", "demand_forecast": ""}

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, item_a, location_a2):
        from apps.scm.models import ReorderRule
        data = {"item": str(item_a.pk), "location": str(location_a2.pk), "reorder_point": "5",
                "safety_stock": "2", "reorder_quantity": "10", "is_active": "on",
                **self.POLICY_FIELDS}
        resp = client_a.post(reverse("scm:reorderrule_create"), data)
        assert resp.status_code == 302
        rule = ReorderRule.objects.get(item=item_a, location=location_a2)
        assert rule.tenant_id == tenant_a.pk
        assert rule.safety_stock_method == "fixed"  # 4.7 default reproduces pre-4.7 behaviour

    def test_edit_updates_fields(self, client_a, reorder_rule_a, item_a, location_a):
        data = {"item": str(item_a.pk), "location": str(location_a.pk), "reorder_point": "99",
                "safety_stock": "5", "reorder_quantity": "20", "is_active": "on",
                **self.POLICY_FIELDS}
        resp = client_a.post(reverse("scm:reorderrule_edit", args=[reorder_rule_a.pk]), data)
        assert resp.status_code == 302
        reorder_rule_a.refresh_from_db()
        assert reorder_rule_a.reorder_point == Decimal("99.00")

    def test_a_post_omitting_the_4_7_policy_fields_is_rejected_not_500ed(self, client_a, item_a,
                                                                         location_a2):
        """Regression guard for the stale-payload break above: the refusal must be a re-rendered
        form with field errors, never an exception."""
        from apps.scm.models import ReorderRule
        data = {"item": str(item_a.pk), "location": str(location_a2.pk), "reorder_point": "5",
                "safety_stock": "2", "reorder_quantity": "10", "is_active": "on"}
        resp = client_a.post(reverse("scm:reorderrule_create"), data)
        assert resp.status_code == 200
        assert "safety_stock_method" in resp.context["form"].errors
        assert not ReorderRule.objects.filter(item=item_a, location=location_a2).exists()

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


# ================================================================================================
# SCM 4.5 Order Management System
# ================================================================================================

# ================================================================ SalesOrder CRUD
class TestSalesOrderCRUD:
    def test_list_returns_200(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_list"))
        assert resp.status_code == 200
        assert sales_order_a in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_list"), {"status": "draft"})
        assert sales_order_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:salesorder_list"), {"status": "cancelled"})
        assert sales_order_a not in resp2.context["object_list"]

    def test_list_filter_by_customer(self, client_a, sales_order_a, customer_a):
        resp = client_a.get(reverse("scm:salesorder_list"), {"customer": str(customer_a.pk)})
        assert sales_order_a in resp.context["object_list"]

    def test_list_search_by_number(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_list"), {"q": sales_order_a.number})
        assert sales_order_a in resp.context["object_list"]

    def test_list_no_n_plus_one_query_blowup(
        self, client_a, tenant_a, customer_a, item_a, django_assert_max_num_queries,
    ):
        from apps.scm.models import SalesOrder, SalesOrderLine
        for i in range(8):
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=datetime.date(2026, 1, i + 1))
            SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                          unit_price=Decimal("1"))
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:salesorder_list"))
        assert resp.status_code == 200

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, customer_a, item_a):
        from apps.scm.models import SalesOrder
        data = {
            "customer": str(customer_a.pk), "ship_to_address": "", "source_channel": "manual",
            "order_date": "2026-01-05", "requested_date": "", "currency": "", "payment_terms": "",
            "notes": "",
            **formset_data("lines", [
                {"id": "", "item": str(item_a.pk), "description": "", "quantity_ordered": "4",
                 "unit_price": "25.00", "discount_pct": "0", "tax_pct": "0"},
            ]),
        }
        resp = client_a.post(reverse("scm:salesorder_create"), data)
        assert resp.status_code == 302
        order = SalesOrder.objects.get(customer=customer_a, order_date=datetime.date(2026, 1, 5))
        assert order.tenant_id == tenant_a.pk
        assert order.number == "SO-00001"
        assert order.total == Decimal("100.00")

    def test_edit_redirects_away_from_the_form_once_submitted(self, client_a, sales_order_a):
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.get(reverse("scm:salesorder_edit", args=[sales_order_a.pk]))
        assert resp.status_code == 302

    def test_edit_updates_notes_while_draft(self, client_a, sales_order_a, customer_a):
        line = sales_order_a.lines.first()
        data = {
            "customer": str(customer_a.pk), "ship_to_address": "", "source_channel": "manual",
            "order_date": "2026-01-05", "requested_date": "", "currency": "", "payment_terms": "",
            "notes": "edited",
            **formset_data("lines", [
                {"id": line.pk, "item": str(line.item_id), "description": "",
                 "quantity_ordered": line.quantity_ordered, "unit_price": line.unit_price,
                 "discount_pct": "0", "tax_pct": "0"},
            ], initial=1),
        }
        resp = client_a.post(reverse("scm:salesorder_edit", args=[sales_order_a.pk]), data)
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.notes == "edited"

    def test_delete_draft_removes_it(self, client_a, sales_order_a):
        from apps.scm.models import SalesOrder
        resp = client_a.post(reverse("scm:salesorder_delete", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        assert not SalesOrder.objects.filter(pk=sales_order_a.pk).exists()

    def test_delete_submitted_order_is_refused(self, client_a, sales_order_a):
        from apps.scm.models import SalesOrder
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_delete", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        assert SalesOrder.objects.filter(pk=sales_order_a.pk).exists()


class TestSalesOrderDetailContext:
    def test_detail_shows_rows_and_backorder(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_detail", args=[sales_order_a.pk]))
        assert resp.status_code == 200
        assert len(resp.context["rows"]) == 1
        row = resp.context["rows"][0]
        assert row["allocated"] == Decimal("0")
        assert row["backordered"] == sales_order_a.lines.first().quantity_ordered

    def test_linkable_invoices_only_offered_once_fulfilled(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_detail", args=[sales_order_a.pk]))
        assert resp.context["linkable_invoices"] == []

    def test_detail_groups_an_active_allocation_under_its_line(
        self, client_a, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("4"))
        resp = client_a.get(reverse("scm:salesorder_detail", args=[sales_order_a.pk]))
        assert resp.status_code == 200
        row = resp.context["rows"][0]
        assert row["allocated"] == Decimal("4")
        assert len(row["allocations"]) == 1
        assert resp.context["has_active_allocations"] is True

    def test_create_form_get_renders_200(self, client_a):
        resp = client_a.get(reverse("scm:salesorder_create"))
        assert resp.status_code == 200

    def test_edit_form_get_renders_200_while_draft(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_edit", args=[sales_order_a.pk]))
        assert resp.status_code == 200


# ================================================================ Mass-assignment (priority 6)
class TestSalesOrderMassAssignment:
    def test_create_ignores_workflow_and_system_fields(self, client_a, tenant_a, customer_a, item_a):
        from apps.scm.models import SalesOrder
        data = {
            "customer": str(customer_a.pk), "ship_to_address": "", "source_channel": "manual",
            "order_date": "2026-01-05", "requested_date": "", "currency": "", "payment_terms": "",
            "notes": "hack attempt",
            "status": "invoiced", "number": "SO-99999", "promised_date": "2026-01-01",
            "credit_hold": "on", "fraud_flag": "on", "hold_reason": "forged",
            "confirmation_sent_at": "2026-01-01T00:00", "subtotal": "1.00", "tax_total": "1.00",
            "total": "999999.00",
            **formset_data("lines", [
                {"id": "", "item": str(item_a.pk), "description": "", "quantity_ordered": "2",
                 "unit_price": "10.00", "discount_pct": "0", "tax_pct": "0"},
            ]),
        }
        resp = client_a.post(reverse("scm:salesorder_create"), data)
        assert resp.status_code == 302
        order = SalesOrder.objects.get(notes="hack attempt")
        assert order.status == "draft"
        assert order.number == "SO-00001"
        assert order.promised_date is None
        assert order.credit_hold is False
        assert order.fraud_flag is False
        assert order.hold_reason == ""
        assert order.confirmation_sent_at is None
        assert order.total == Decimal("20.00")


# ================================================================================================
# State machine (priority 2)
# ================================================================================================
class TestSalesOrderStateMachine:
    def test_submit_under_credit_limit_moves_to_submitted_and_stamps_confirmation(self, client_a, sales_order_a):
        resp = client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"
        assert sales_order_a.confirmation_sent_at is not None

    def test_submit_without_an_order_date_stamps_todays_date(self, client_a, tenant_a, customer_a, item_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a)  # no order_date
        SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                      unit_price=Decimal("1"))
        order.recalc_totals()
        client_a.post(reverse("scm:salesorder_submit", args=[order.pk]))
        order.refresh_from_db()
        assert order.status == "submitted"
        assert order.order_date == timezone.localdate()

    def test_submit_with_an_unmapped_line_is_refused(self, client_a, sales_order_a):
        from apps.scm.models import SalesOrderLine
        SalesOrderLine.objects.create(sales_order=sales_order_a, item=None, description="Unmapped",
                                      quantity_ordered=Decimal("1"), unit_price=Decimal("1"))
        resp = client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "draft"

    def test_submit_with_no_lines_is_refused(self, client_a, tenant_a, customer_a):
        from apps.scm.models import SalesOrder
        empty = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a)
        resp = client_a.post(reverse("scm:salesorder_submit", args=[empty.pk]))
        assert resp.status_code == 302
        empty.refresh_from_db()
        assert empty.status == "draft"

    def test_submit_twice_is_a_noop(self, client_a, sales_order_a):
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"

    def test_over_credit_limit_lands_on_hold_and_does_not_stamp_confirmation(
        self, client_a, tenant_a, sales_order_a, customer_a,
    ):
        from apps.accounting.models import CustomerProfile
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_limit=Decimal("50.00"))
        resp = client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "on_hold"
        assert sales_order_a.credit_hold is True
        assert "Credit limit exceeded" in sales_order_a.hold_reason
        assert sales_order_a.confirmation_sent_at is None

    def test_release_hold_without_reason_is_refused(self, client_a, tenant_a, sales_order_a, customer_a):
        from apps.accounting.models import CustomerProfile
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_limit=Decimal("50.00"))
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_release_hold", args=[sales_order_a.pk]),
                             {"release_note": ""})
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "on_hold"

    def test_release_hold_appends_to_hold_reason_and_returns_to_submitted(
        self, client_a, tenant_a, sales_order_a, customer_a,
    ):
        from apps.accounting.models import CustomerProfile
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_limit=Decimal("50.00"))
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        sales_order_a.refresh_from_db()
        original_reason = sales_order_a.hold_reason
        resp = client_a.post(reverse("scm:salesorder_release_hold", args=[sales_order_a.pk]),
                             {"release_note": "Prepaid by wire"})
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"
        assert original_reason in sales_order_a.hold_reason
        assert "Prepaid by wire" in sales_order_a.hold_reason
        assert sales_order_a.confirmation_sent_at is not None

    def test_release_hold_on_a_non_held_order_is_a_noop(self, client_a, sales_order_a):
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_release_hold", args=[sales_order_a.pk]),
                             {"release_note": "no hold to release"})
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"

    def test_fulfill_requires_allocated_or_partially_fulfilled(self, client_a, sales_order_a):
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"  # unchanged — not yet allocated

    def test_fulfill_allocated_order_stamps_shipped_notification(
        self, client_a, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        sales_order_a.refresh_from_db()  # pick up the status change made by the client POST above
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("10"))
        sales_order_a.recompute_allocation_status()
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "allocated"
        resp = client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "fulfilled"
        assert sales_order_a.shipped_notification_at is not None

    def test_mark_delivered_before_fulfilled_is_refused(self, client_a, sales_order_a):
        resp = client_a.post(reverse("scm:salesorder_mark_delivered", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.delivered_notification_at is None

    def test_mark_delivered_after_fulfilled_does_not_change_status(
        self, client_a, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        sales_order_a.refresh_from_db()  # pick up the status change made by the client POST above
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("10"))
        sales_order_a.recompute_allocation_status()
        client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_mark_delivered", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.delivered_notification_at is not None
        assert sales_order_a.status == "fulfilled"

    def test_close_requires_invoiced(self, client_a, sales_order_a):
        resp = client_a.post(reverse("scm:salesorder_close", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "draft"

    def test_cancel_refused_while_allocation_active_and_allowed_after_cancelling(
        self, client_a, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        line = sales_order_a.lines.first()
        alloc = SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                                     quantity=Decimal("4"))
        resp = client_a.post(reverse("scm:salesorder_cancel", args=[sales_order_a.pk]),
                             {"cancel_reason": "changed mind"})
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status != "cancelled"
        client_a.post(reverse("scm:salesorderallocation_cancel", args=[alloc.pk]))
        resp2 = client_a.post(reverse("scm:salesorder_cancel", args=[sales_order_a.pk]),
                              {"cancel_reason": "changed mind"})
        assert resp2.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "cancelled"

    def test_cancel_without_reason_is_refused(self, client_a, sales_order_a):
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_cancel", args=[sales_order_a.pk]))
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status != "cancelled"

    def test_cancel_fulfilled_order_is_refused(self, client_a, tenant_a, sales_order_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        sales_order_a.refresh_from_db()  # pick up the status change made by the client POST above
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("10"))
        sales_order_a.recompute_allocation_status()
        client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_a.pk]))
        resp = client_a.post(reverse("scm:salesorder_cancel", args=[sales_order_a.pk]),
                             {"cancel_reason": "too late"})
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "fulfilled"


# ================================================================================================
# Priority regression 1a — salesorder_mark_invoiced is reachable
# ================================================================================================
class TestSalesOrderMarkInvoicedRegression:
    """`invoice` used to be a draft-only form field while this action needs `fulfilled` — the two
    conditions could never both hold, so the AR hand-off was a dead end (code review)."""

    def _fulfilled_order(self, client_a, tenant_a, sales_order_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        sales_order_a.refresh_from_db()  # pick up the status change made by the client POST above
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("10"))
        sales_order_a.recompute_allocation_status()
        client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_a.pk]))
        sales_order_a.refresh_from_db()
        return sales_order_a

    def test_invoice_is_not_a_form_field(self):
        from apps.scm.forms import SalesOrderForm
        form = SalesOrderForm(tenant=None)
        assert "invoice" not in form.fields

    def test_mark_invoiced_refused_on_a_non_fulfilled_order(self, client_a, tenant_a, sales_order_a, customer_a):
        from apps.accounting.models import Invoice
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        inv = Invoice.objects.create(tenant=tenant_a, party=customer_a, issue_date=datetime.date(2026, 1, 20),
                                     due_date=datetime.date(2026, 2, 20), status="draft")
        resp = client_a.post(reverse("scm:salesorder_mark_invoiced", args=[sales_order_a.pk]), {"invoice": inv.pk})
        assert resp.status_code == 302
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"
        assert sales_order_a.invoice_id is None

    def test_mark_invoiced_without_an_invoice_pk_is_refused(self, client_a, tenant_a, sales_order_a, location_a):
        order = self._fulfilled_order(client_a, tenant_a, sales_order_a, location_a)
        resp = client_a.post(reverse("scm:salesorder_mark_invoiced", args=[order.pk]))
        assert resp.status_code == 302
        order.refresh_from_db()
        assert order.status == "fulfilled"
        assert order.invoice_id is None

    def test_linkable_invoices_offered_on_the_detail_page_once_fulfilled(
        self, client_a, tenant_a, sales_order_a, location_a, customer_a,
    ):
        from apps.accounting.models import Invoice
        order = self._fulfilled_order(client_a, tenant_a, sales_order_a, location_a)
        inv = Invoice.objects.create(tenant=tenant_a, party=customer_a, issue_date=datetime.date(2026, 1, 20),
                                     due_date=datetime.date(2026, 2, 20), status="draft")
        resp = client_a.get(reverse("scm:salesorder_detail", args=[order.pk]))
        assert resp.status_code == 200
        assert inv in resp.context["linkable_invoices"]

    def test_mark_invoiced_links_the_invoice_and_advances_the_order(
        self, client_a, tenant_a, sales_order_a, location_a, customer_a,
    ):
        from apps.accounting.models import Invoice
        order = self._fulfilled_order(client_a, tenant_a, sales_order_a, location_a)
        inv = Invoice.objects.create(tenant=tenant_a, party=customer_a, issue_date=datetime.date(2026, 1, 20),
                                     due_date=datetime.date(2026, 2, 20), status="draft")
        resp = client_a.post(reverse("scm:salesorder_mark_invoiced", args=[order.pk]), {"invoice": inv.pk})
        assert resp.status_code == 302
        order.refresh_from_db()
        assert order.status == "invoiced"
        assert order.invoice_id == inv.pk

    def test_and_the_order_can_then_be_closed(self, client_a, tenant_a, sales_order_a, location_a, customer_a):
        from apps.accounting.models import Invoice
        order = self._fulfilled_order(client_a, tenant_a, sales_order_a, location_a)
        inv = Invoice.objects.create(tenant=tenant_a, party=customer_a, issue_date=datetime.date(2026, 1, 20),
                                     due_date=datetime.date(2026, 2, 20), status="draft")
        client_a.post(reverse("scm:salesorder_mark_invoiced", args=[order.pk]), {"invoice": inv.pk})
        resp = client_a.post(reverse("scm:salesorder_close", args=[order.pk]))
        assert resp.status_code == 302
        order.refresh_from_db()
        assert order.status == "closed"

    def test_cross_tenant_invoice_pk_is_rejected(self, client_a, tenant_a, tenant_b, sales_order_a, location_a):
        from apps.accounting.models import Invoice
        from apps.core.models import Party
        order = self._fulfilled_order(client_a, tenant_a, sales_order_a, location_a)
        other_customer = Party.objects.create(tenant=tenant_b, name="Someone Else", kind="organization")
        foreign_inv = Invoice.objects.create(tenant=tenant_b, party=other_customer,
                                             issue_date=datetime.date(2026, 1, 20),
                                             due_date=datetime.date(2026, 2, 20), status="draft")
        resp = client_a.post(reverse("scm:salesorder_mark_invoiced", args=[order.pk]),
                             {"invoice": foreign_inv.pk})
        assert resp.status_code == 302
        order.refresh_from_db()
        assert order.status == "fulfilled"
        assert order.invoice_id is None


# ================================================================================================
# Credit / fraud hold (priority 4)
# ================================================================================================
class TestSalesOrderCreditFraudHold:
    def test_evaluate_hold_trips_on_credit_on_hold_flag(self, tenant_a, sales_order_a, customer_a):
        from apps.accounting.models import CustomerProfile
        from apps.scm.views.OrderManagement.SalesOrders import _evaluate_hold
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_on_hold=True)
        sales_order_a.recalc_totals()
        credit_hold, fraud_flag, reason = _evaluate_hold(sales_order_a)
        assert credit_hold is True
        assert "credit hold" in reason.lower()

    def test_evaluate_hold_trips_over_the_credit_limit(self, tenant_a, sales_order_a, customer_a):
        from apps.accounting.models import CustomerProfile
        from apps.scm.views.OrderManagement.SalesOrders import _evaluate_hold
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_limit=Decimal("50.00"))
        sales_order_a.recalc_totals()  # total = 150.00, over the 50.00 limit
        credit_hold, fraud_flag, reason = _evaluate_hold(sales_order_a)
        assert credit_hold is True
        assert "Credit limit exceeded" in reason

    def test_evaluate_hold_does_not_trip_under_the_credit_limit(self, tenant_a, sales_order_a, customer_a):
        from apps.accounting.models import CustomerProfile
        from apps.scm.views.OrderManagement.SalesOrders import _evaluate_hold
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_limit=Decimal("1000.00"))
        sales_order_a.recalc_totals()
        credit_hold, fraud_flag, reason = _evaluate_hold(sales_order_a)
        assert credit_hold is False

    def test_evaluate_hold_trips_new_customer_first_order_over_threshold(self, tenant_a, customer_a, item_a):
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.views.OrderManagement.SalesOrders import _evaluate_hold
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=datetime.date(2026, 1, 5))
        SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                      unit_price=Decimal("9000"))
        order.recalc_totals()
        credit_hold, fraud_flag, reason = _evaluate_hold(order)
        assert fraud_flag is True
        assert "New customer" in reason

    def test_evaluate_hold_does_not_trip_fraud_for_a_repeat_customer(self, tenant_a, customer_a, item_a):
        """A SECOND order for a customer who already has one on file is not a 'first order'."""
        from apps.scm.models import SalesOrder, SalesOrderLine
        from apps.scm.views.OrderManagement.SalesOrders import _evaluate_hold
        SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, order_date=datetime.date(2026, 1, 1))
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=datetime.date(2026, 1, 5))
        SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                      unit_price=Decimal("9000"))
        order.recalc_totals()
        credit_hold, fraud_flag, reason = _evaluate_hold(order)
        assert fraud_flag is False

    def test_first_order_rule_does_not_retrip_on_the_same_order_when_resubmitted(
        self, client_a, tenant_a, customer_a, item_a,
    ):
        """Regression: once released, the order sits at 'submitted' — `salesorder_submit` only
        evaluates credit/fraud from `draft`, so a normal re-submit attempt on the SAME order is a
        no-op that skips re-evaluation entirely and can never re-trip its own fraud flag."""
        from apps.scm.models import SalesOrder, SalesOrderLine
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=datetime.date(2026, 1, 5))
        SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                      unit_price=Decimal("9000"))
        order.recalc_totals()
        client_a.post(reverse("scm:salesorder_submit", args=[order.pk]))
        order.refresh_from_db()
        assert order.status == "on_hold" and order.fraud_flag is True
        client_a.post(reverse("scm:salesorder_release_hold", args=[order.pk]), {"release_note": "Verified"})
        order.refresh_from_db()
        assert order.status == "submitted" and order.fraud_flag is False
        resp = client_a.post(reverse("scm:salesorder_submit", args=[order.pk]))
        assert resp.status_code == 302
        order.refresh_from_db()
        assert order.status == "submitted"
        assert order.fraud_flag is False


# ================================================================================================
# SalesOrderAllocation CRUD + lifecycle (priority 3)
# ================================================================================================
class TestSalesOrderAllocationCRUD:
    def test_list_returns_200(self, client_a, allocation_a):
        resp = client_a.get(reverse("scm:salesorderallocation_list"))
        assert resp.status_code == 200
        assert allocation_a in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, allocation_a):
        resp = client_a.get(reverse("scm:salesorderallocation_list"), {"status": "reserved"})
        assert allocation_a in resp.context["object_list"]

    def test_detail_returns_200(self, client_a, allocation_a):
        resp = client_a.get(reverse("scm:salesorderallocation_detail", args=[allocation_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == allocation_a


class TestSalesOrderAllocationLifecycle:
    def _stock(self, tenant, item, location, qty):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant, item=item, location=location, quantity=Decimal(qty),
                         unit_cost=Decimal("10.00"), move_type="receipt")

    def test_allocation_posts_no_stockmove(self, client_a, tenant_a, sales_order_line_a, location_a, item_a):
        self._stock(tenant_a, item_a, location_a, "10")
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "5", "notes": ""})
        assert resp.status_code == 302
        assert item_a.on_hand(location=location_a) == Decimal("10")  # unchanged — soft reservation

    def test_cannot_allocate_more_than_the_line_ordered(
        self, client_a, tenant_a, sales_order_line_a, location_a, item_a,
    ):
        self._stock(tenant_a, item_a, location_a, "20")
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "11", "notes": ""})  # ordered 10
        assert resp.status_code == 200  # re-rendered with an error
        assert sales_order_line_a.allocations.count() == 0

    def test_atp_guard_blocks_promising_stock_another_order_reserved(
        self, client_a, tenant_a, customer_a, item_a, location_a,
    ):
        from apps.scm.models import SalesOrder, SalesOrderLine
        self._stock(tenant_a, item_a, location_a, "10")
        order1 = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                           order_date=datetime.date(2026, 1, 5))
        line1 = SalesOrderLine.objects.create(sales_order=order1, item=item_a, quantity_ordered=Decimal("8"),
                                              unit_price=Decimal("1"))
        order1.recalc_totals()
        client_a.post(reverse("scm:salesorder_submit", args=[order1.pk]))
        client_a.post(reverse("scm:salesorderallocation_create", args=[line1.pk]),
                      {"location": location_a.pk, "quantity": "5", "notes": ""})

        order2 = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                           order_date=datetime.date(2026, 1, 5))
        line2 = SalesOrderLine.objects.create(sales_order=order2, item=item_a, quantity_ordered=Decimal("8"),
                                              unit_price=Decimal("1"))
        order2.recalc_totals()
        client_a.post(reverse("scm:salesorder_submit", args=[order2.pk]))
        alloc2_url = reverse("scm:salesorderallocation_create", args=[line2.pk])
        client_a.post(alloc2_url, {"location": location_a.pk, "quantity": "8", "notes": ""})  # only 5 left
        assert line2.quantity_allocated() == Decimal("0")
        client_a.post(alloc2_url, {"location": location_a.pk, "quantity": "5", "notes": ""})
        assert line2.quantity_allocated() == Decimal("5")

    def test_cancelling_an_allocation_frees_atp_for_re_reservation(
        self, client_a, tenant_a, sales_order_line_a, location_a, item_a,
    ):
        self._stock(tenant_a, item_a, location_a, "10")
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(url, {"location": location_a.pk, "quantity": "10", "notes": ""})
        assert sales_order_line_a.quantity_allocated() == Decimal("10")
        alloc = sales_order_line_a.allocations.first()
        client_a.post(reverse("scm:salesorderallocation_cancel", args=[alloc.pk]))
        assert sales_order_line_a.quantity_allocated() == Decimal("0")
        client_a.post(url, {"location": location_a.pk, "quantity": "10", "notes": ""})
        assert sales_order_line_a.quantity_allocated() == Decimal("10")

    def test_release_still_counts_as_allocated_and_posts_no_stockmove(
        self, client_a, tenant_a, sales_order_line_a, location_a, item_a,
    ):
        self._stock(tenant_a, item_a, location_a, "10")
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(url, {"location": location_a.pk, "quantity": "5", "notes": ""})
        alloc = sales_order_line_a.allocations.first()
        resp = client_a.post(reverse("scm:salesorderallocation_release", args=[alloc.pk]))
        assert resp.status_code == 302
        alloc.refresh_from_db()
        assert alloc.status == "released"
        assert sales_order_line_a.quantity_allocated() == Decimal("5")
        assert item_a.on_hand(location=location_a) == Decimal("10")

    def test_delete_refused_once_released(self, client_a, tenant_a, sales_order_line_a, location_a, item_a):
        self._stock(tenant_a, item_a, location_a, "10")
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(url, {"location": location_a.pk, "quantity": "5", "notes": ""})
        alloc = sales_order_line_a.allocations.first()
        client_a.post(reverse("scm:salesorderallocation_release", args=[alloc.pk]))
        resp = client_a.post(reverse("scm:salesorderallocation_delete", args=[alloc.pk]))
        assert resp.status_code == 302
        alloc.refresh_from_db()
        assert alloc.status == "released"  # unchanged — delete refused for a released row

    def test_delete_reserved_allocation_succeeds(self, client_a, tenant_a, sales_order_line_a, location_a, item_a):
        from apps.scm.models import SalesOrderAllocation
        self._stock(tenant_a, item_a, location_a, "10")
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(url, {"location": location_a.pk, "quantity": "5", "notes": ""})
        alloc = sales_order_line_a.allocations.first()
        resp = client_a.post(reverse("scm:salesorderallocation_delete", args=[alloc.pk]))
        assert resp.status_code == 302
        assert not SalesOrderAllocation.objects.filter(pk=alloc.pk).exists()

    def test_edit_success_updates_quantity_and_recomputes_order_status(
        self, client_a, tenant_a, sales_order_line_a, location_a, item_a,
    ):
        self._stock(tenant_a, item_a, location_a, "10")
        create_url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(create_url, {"location": location_a.pk, "quantity": "4", "notes": ""})
        alloc = sales_order_line_a.allocations.first()
        edit_url = reverse("scm:salesorderallocation_edit", args=[alloc.pk])
        assert client_a.get(edit_url).status_code == 200
        resp = client_a.post(edit_url, {"location": location_a.pk, "quantity": "10", "notes": "topped up"})
        assert resp.status_code == 302
        alloc.refresh_from_db()
        assert alloc.quantity == Decimal("10")
        assert alloc.notes == "topped up"
        sales_order_line_a.sales_order.refresh_from_db()
        assert sales_order_line_a.sales_order.status == "allocated"  # fully covered now

    def test_edit_re_saving_the_same_quantity_does_not_double_count_itself(
        self, client_a, tenant_a, sales_order_line_a, location_a, item_a,
    ):
        """exclude_pk in the edit path's ATP check — without it, re-saving a row unchanged would
        count its own existing reservation twice and wrongly reject itself."""
        self._stock(tenant_a, item_a, location_a, "10")
        create_url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(create_url, {"location": location_a.pk, "quantity": "10", "notes": ""})
        alloc = sales_order_line_a.allocations.first()
        edit_url = reverse("scm:salesorderallocation_edit", args=[alloc.pk])
        resp = client_a.post(edit_url, {"location": location_a.pk, "quantity": "10", "notes": "unchanged"})
        assert resp.status_code == 302
        alloc.refresh_from_db()
        assert alloc.quantity == Decimal("10")

    def test_edit_refused_once_released(self, client_a, tenant_a, sales_order_line_a, location_a, item_a):
        self._stock(tenant_a, item_a, location_a, "10")
        create_url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(create_url, {"location": location_a.pk, "quantity": "5", "notes": ""})
        alloc = sales_order_line_a.allocations.first()
        client_a.post(reverse("scm:salesorderallocation_release", args=[alloc.pk]))
        edit_url = reverse("scm:salesorderallocation_edit", args=[alloc.pk])
        resp = client_a.get(edit_url)
        assert resp.status_code == 302  # redirected to detail, not the form

    def test_release_an_already_released_allocation_is_a_noop(self, allocation_a, client_a):
        client_a.post(reverse("scm:salesorderallocation_release", args=[allocation_a.pk]))
        resp = client_a.post(reverse("scm:salesorderallocation_release", args=[allocation_a.pk]))
        assert resp.status_code == 302
        allocation_a.refresh_from_db()
        assert allocation_a.status == "released"

    def test_cancel_an_already_cancelled_allocation_is_a_noop(self, allocation_a, client_a):
        client_a.post(reverse("scm:salesorderallocation_cancel", args=[allocation_a.pk]))
        resp = client_a.post(reverse("scm:salesorderallocation_cancel", args=[allocation_a.pk]))
        assert resp.status_code == 302
        allocation_a.refresh_from_db()
        assert allocation_a.status == "cancelled"

    def test_create_refused_when_the_order_is_not_allocatable(self, client_a, tenant_a, sales_order_a, item_a):
        """sales_order_a is still `draft` — allocation is only offered from submitted onward."""
        line = sales_order_a.lines.first()
        resp = client_a.get(reverse("scm:salesorderallocation_create", args=[line.pk]))
        assert resp.status_code == 302

    def test_create_refused_when_the_line_item_is_unmapped(self, client_a, tenant_a, sales_order_submitted_a):
        from apps.scm.models import SalesOrderLine
        line = SalesOrderLine.objects.create(sales_order=sales_order_submitted_a, item=None,
                                             description="Unmapped", quantity_ordered=Decimal("1"))
        resp = client_a.get(reverse("scm:salesorderallocation_create", args=[line.pk]))
        assert resp.status_code == 302

    def test_create_redirects_when_the_user_has_no_tenant_workspace(self, db, sales_order_line_a):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(email="orphan-alloc@example.com", username="orphan_alloc",
                                        password="x", tenant=None, is_superuser=True)
        c = Client()
        c.force_login(user)
        resp = c.get(reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk]))
        assert resp.status_code == 302

    def test_edit_atp_guard_blocks_growing_into_stock_another_order_holds(
        self, client_a, tenant_a, customer_a, item_a, location_a, sales_order_line_a,
    ):
        from apps.scm.models import SalesOrder, SalesOrderLine
        self._stock(tenant_a, item_a, location_a, "10")
        create_url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        client_a.post(create_url, {"location": location_a.pk, "quantity": "4", "notes": ""})
        alloc = sales_order_line_a.allocations.first()

        other_order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                                 order_date=datetime.date(2026, 1, 5))
        other_line = SalesOrderLine.objects.create(sales_order=other_order, item=item_a,
                                                    quantity_ordered=Decimal("5"), unit_price=Decimal("1"))
        other_order.recalc_totals()
        client_a.post(reverse("scm:salesorder_submit", args=[other_order.pk]))
        client_a.post(reverse("scm:salesorderallocation_create", args=[other_line.pk]),
                      {"location": location_a.pk, "quantity": "5", "notes": ""})  # 4 + 5 = 9 of 10 reserved

        edit_url = reverse("scm:salesorderallocation_edit", args=[alloc.pk])
        resp = client_a.post(edit_url, {"location": location_a.pk, "quantity": "8", "notes": ""})  # only 5 free
        assert resp.status_code == 200  # re-rendered with an error, not saved
        alloc.refresh_from_db()
        assert alloc.quantity == Decimal("4")  # unchanged


class TestAvailableToPromiseAndAtpRowsHelpers:
    def test_available_to_promise_is_zero_without_an_item_or_location(self, location_a, item_a):
        from apps.scm.views.OrderManagement.SalesOrderAllocations import _available_to_promise
        assert _available_to_promise(None, location_a) == Decimal("0")
        assert _available_to_promise(item_a, None) == Decimal("0")

    def test_atp_rows_is_empty_without_an_item(self, tenant_a):
        from apps.scm.views.OrderManagement.SalesOrderAllocations import _atp_rows
        assert _atp_rows(tenant_a, None) == []

    def test_atp_rows_is_empty_with_no_pickable_locations(self, tenant_a, item_a):
        from apps.scm.models import Location
        from apps.scm.views.OrderManagement.SalesOrderAllocations import _atp_rows
        Location.objects.filter(tenant=tenant_a).update(is_pickable=False)
        assert _atp_rows(tenant_a, item_a) == []


# ================================================================ Negative-input hardening
class TestSalesOrderNegativeInputHardening:
    def test_junk_customer_filter_returns_200_not_500(self, client_a):
        resp = client_a.get(reverse("scm:salesorder_list"), {"customer": "abc"})
        assert resp.status_code == 200

    def test_junk_status_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:salesorder_list"), {"status": "not-a-status"})
        assert resp.status_code == 200

    def test_page_past_the_end_returns_200(self, client_a, sales_order_a):
        resp = client_a.get(reverse("scm:salesorder_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_page_2_when_rows_exceed_page_size(self, client_a, tenant_a, customer_a, item_a):
        from apps.scm.models import SalesOrder, SalesOrderLine
        for i in range(20):
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=datetime.date(2026, 1, (i % 28) + 1))
            SalesOrderLine.objects.create(sales_order=order, item=item_a, quantity_ordered=Decimal("1"),
                                          unit_price=Decimal("1"))
        resp = client_a.get(reverse("scm:salesorder_list"), {"page": "2"})
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) > 0


class TestSalesOrderAllocationNegativeInputHardening:
    def test_quantity_nan_is_rejected_not_500(self, client_a, sales_order_line_a, location_a):
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "NaN", "notes": ""})
        assert resp.status_code == 200
        assert sales_order_line_a.allocations.count() == 0

    def test_quantity_infinity_is_rejected_not_500(self, client_a, sales_order_line_a, location_a):
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "Infinity", "notes": ""})
        assert resp.status_code == 200
        assert sales_order_line_a.allocations.count() == 0

    def test_quantity_garbage_is_rejected_not_500(self, client_a, sales_order_line_a, location_a):
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "abc", "notes": ""})
        assert resp.status_code == 200
        assert sales_order_line_a.allocations.count() == 0

    def test_quantity_negative_is_rejected_not_500(self, client_a, sales_order_line_a, location_a):
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "-5", "notes": ""})
        assert resp.status_code == 200
        assert sales_order_line_a.allocations.count() == 0

    def test_quantity_over_max_digits_is_rejected_not_500(self, client_a, sales_order_line_a, location_a):
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        resp = client_a.post(url, {"location": location_a.pk, "quantity": "99999999999999.9999", "notes": ""})
        assert resp.status_code == 200
        assert sales_order_line_a.allocations.count() == 0

    def test_junk_status_filter_on_allocation_list_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:salesorderallocation_list"), {"status": "bogus"})
        assert resp.status_code == 200

    def test_junk_location_filter_on_allocation_list_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:salesorderallocation_list"), {"location": "abc"})
        assert resp.status_code == 200


# ================================================================================================
# Quote conversion (priority 8)
# ================================================================================================
class TestSalesOrderCreateFromQuote:
    def _accepted_quote(self, tenant, account):
        from apps.crm.models import Quote, QuoteLine
        quote = Quote.objects.create(tenant=tenant, name="Q1", account=account, status="accepted",
                                     currency_code="USD")
        QuoteLine.objects.create(tenant=tenant, quote=quote, description="Widget", quantity=Decimal("3"),
                                 unit_price=Decimal("25.00"), discount_pct=Decimal("5"), tax_pct=Decimal("8"))
        return quote

    def test_copies_lines_with_item_none_and_the_quotes_description(self, client_a, tenant_a, customer_a):
        from apps.scm.models import SalesOrder
        quote = self._accepted_quote(tenant_a, customer_a)
        resp = client_a.post(reverse("scm:salesorder_create_from_quote", args=[quote.pk]))
        assert resp.status_code == 302
        order = SalesOrder.objects.get(tenant=tenant_a, source_quote=quote)
        line = order.lines.first()
        assert line.item_id is None
        assert line.description == "Widget"
        assert order.customer_id == customer_a.pk

    def test_refuses_a_non_accepted_quote(self, client_a, tenant_a, customer_a):
        from apps.crm.models import Quote
        from apps.scm.models import SalesOrder
        quote = Quote.objects.create(tenant=tenant_a, name="Draft Q", account=customer_a, status="draft")
        resp = client_a.post(reverse("scm:salesorder_create_from_quote", args=[quote.pk]))
        assert resp.status_code == 302
        assert not SalesOrder.objects.filter(tenant=tenant_a, source_quote=quote).exists()

    def test_refuses_when_the_account_lacks_the_customer_role(self, client_a, tenant_a):
        from apps.core.models import Party
        from apps.crm.models import Quote
        from apps.scm.models import SalesOrder
        non_customer = Party.objects.create(tenant=tenant_a, name="Lead Only", kind="organization")
        quote = Quote.objects.create(tenant=tenant_a, name="Q2", account=non_customer, status="accepted")
        resp = client_a.post(reverse("scm:salesorder_create_from_quote", args=[quote.pk]))
        assert resp.status_code == 302
        assert not SalesOrder.objects.filter(tenant=tenant_a, source_quote=quote).exists()

    def test_idempotent_second_conversion_redirects_to_the_existing_order(self, client_a, tenant_a, customer_a):
        from apps.scm.models import SalesOrder
        quote = self._accepted_quote(tenant_a, customer_a)
        client_a.post(reverse("scm:salesorder_create_from_quote", args=[quote.pk]))
        order = SalesOrder.objects.get(tenant=tenant_a, source_quote=quote)
        resp = client_a.post(reverse("scm:salesorder_create_from_quote", args=[quote.pk]))
        assert resp.status_code == 302
        assert reverse("scm:salesorder_detail", args=[order.pk]) in resp["Location"]
        assert SalesOrder.objects.filter(tenant=tenant_a, source_quote=quote).count() == 1

    def test_cross_tenant_quote_pk_404s(self, client_a, tenant_b, customer_b):
        quote = self._accepted_quote(tenant_b, customer_b)
        resp = client_a.post(reverse("scm:salesorder_create_from_quote", args=[quote.pk]))
        assert resp.status_code == 404


# ================================================================ Create guarded when the user has no tenant
class TestSalesOrderCreateWithoutTenantWorkspace:
    def test_salesorder_create_redirects(self, db):
        from django.test import Client
        from apps.accounts.models import User
        from apps.scm.models import SalesOrder
        user = User.objects.create_user(email="orphan-oms@example.com", username="orphan_oms", password="x",
                                        tenant=None)
        c = Client()
        c.force_login(user)
        resp = c.get(reverse("scm:salesorder_create"))
        assert resp.status_code == 302
        assert SalesOrder.objects.count() == 0


# ================================================================================================
# SCM 4.6 Transportation Management System
# ================================================================================================

# ================================================================ Carrier CRUD
class TestCarrierCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, carrier_a):
        resp = client_a.get(reverse("scm:carrier_list"))
        assert resp.status_code == 200
        assert carrier_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, carrier_a, carrier_b):
        resp = client_a.get(reverse("scm:carrier_list"))
        assert carrier_b not in resp.context["object_list"]

    def test_list_search_by_scac_code(self, client_a, carrier_a):
        carrier_a.scac_code = "ACME"
        carrier_a.save(update_fields=["scac_code"])
        resp = client_a.get(reverse("scm:carrier_list"), {"q": "ACME"})
        assert carrier_a in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, carrier_a):
        resp = client_a.get(reverse("scm:carrier_list"), {"status": "active"})
        assert carrier_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:carrier_list"), {"status": "suspended"})
        assert carrier_a not in resp2.context["object_list"]

    def test_list_filter_by_primary_mode(self, client_a, carrier_a):
        resp = client_a.get(reverse("scm:carrier_list"), {"primary_mode": "truckload"})
        assert carrier_a in resp.context["object_list"]

    def _valid_data(self, party, **overrides):
        data = {
            "party": str(party.pk), "carrier_type": "asset_based", "primary_mode": "truckload",
            "service_level": "standard", "scac_code": "", "mc_number": "", "dot_number": "",
            "insurance_certificate_expiry": "", "primary_contact_name": "", "primary_contact_email": "",
            "primary_contact_phone": "", "is_preferred": "", "status": "active", "notes": "",
            **formset_data("rate_cards", []),
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, carrier_party_a):
        from apps.scm.models import Carrier
        resp = client_a.post(reverse("scm:carrier_create"), self._valid_data(carrier_party_a))
        assert resp.status_code == 302
        carrier = Carrier.objects.get(tenant=tenant_a, party=carrier_party_a)
        assert carrier.number == "CAR-00001"

    def test_edit_updates_fields(self, client_a, carrier_a, carrier_party_a):
        resp = client_a.post(reverse("scm:carrier_edit", args=[carrier_a.pk]),
                             self._valid_data(carrier_party_a, notes="edited", is_preferred="on"))
        assert resp.status_code == 302
        carrier_a.refresh_from_db()
        assert carrier_a.notes == "edited"
        assert carrier_a.is_preferred is True

    def test_delete_removes_a_carrier_with_no_freight_invoices(self, client_a, carrier_a):
        from apps.scm.models import Carrier
        resp = client_a.post(reverse("scm:carrier_delete", args=[carrier_a.pk]))
        assert resp.status_code == 302
        assert not Carrier.objects.filter(pk=carrier_a.pk).exists()

    def test_delete_blocked_when_the_carrier_has_freight_invoices(self, client_a, tenant_a, carrier_a):
        from apps.scm.models import Carrier, FreightInvoice
        FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)
        resp = client_a.post(reverse("scm:carrier_delete", args=[carrier_a.pk]))
        assert resp.status_code == 302
        assert Carrier.objects.filter(pk=carrier_a.pk).exists()

    def test_get_create_form_renders_200(self, client_a):
        assert client_a.get(reverse("scm:carrier_create")).status_code == 200

    def test_get_edit_form_renders_200(self, client_a, carrier_a):
        assert client_a.get(reverse("scm:carrier_edit", args=[carrier_a.pk])).status_code == 200


class TestCarrierScorecard:
    def test_recompute_scorecard_action_updates_the_pct(self, client_a, tenant_a, carrier_a):
        from django.utils import timezone
        from apps.scm.models import Shipment
        Shipment.objects.create(
            tenant=tenant_a, carrier=carrier_a, status="delivered",
            planned_delivery_date=datetime.date(2026, 1, 10),
            actual_delivery_at=timezone.make_aware(datetime.datetime(2026, 1, 9, 12, 0)),
        )
        resp = client_a.post(reverse("scm:carrier_recompute_scorecard", args=[carrier_a.pk]))
        assert resp.status_code == 302
        carrier_a.refresh_from_db()
        assert carrier_a.on_time_delivery_pct == Decimal("100.00")

    def test_detail_shows_rate_cards_and_recent_shipments(self, client_a, carrier_a, shipment_a):
        from apps.scm.models import CarrierRateCard
        CarrierRateCard.objects.create(carrier=carrier_a, lane_name="Chicago → Dallas")
        resp = client_a.get(reverse("scm:carrier_detail", args=[carrier_a.pk]))
        assert resp.status_code == 200
        assert len(resp.context["rate_cards"]) == 1
        assert shipment_a in resp.context["recent_shipments"]


# ================================================================ Load CRUD
class TestLoadCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, load_a):
        resp = client_a.get(reverse("scm:load_list"))
        assert resp.status_code == 200
        assert load_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, load_a, load_b):
        resp = client_a.get(reverse("scm:load_list"))
        assert load_b not in resp.context["object_list"]

    def test_list_search_by_number(self, client_a, load_a):
        resp = client_a.get(reverse("scm:load_list"), {"q": load_a.number})
        assert load_a in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, load_a):
        resp = client_a.get(reverse("scm:load_list"), {"status": "planning"})
        assert load_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:load_list"), {"status": "delivered"})
        assert load_a not in resp2.context["object_list"]

    def test_list_filter_by_carrier(self, client_a, load_a, carrier_a):
        resp = client_a.get(reverse("scm:load_list"), {"carrier": str(carrier_a.pk)})
        assert load_a in resp.context["object_list"]

    def _valid_data(self, carrier=None, **overrides):
        data = {
            "carrier": str(carrier.pk) if carrier else "", "mode": "truckload", "equipment_type": "dry_van",
            "origin_text": "", "destination_text": "", "planned_departure": "", "planned_arrival": "",
            "distance_km": "", "estimated_fuel_cost": "", "freight_cost_estimate": "",
            "equipment_capacity_weight_kg": "", "equipment_capacity_volume_cbm": "",
            "driver_name": "", "vehicle_ref": "", "notes": "",
            **formset_data("stops", []),
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, carrier_a):
        from apps.scm.models import Load
        resp = client_a.post(reverse("scm:load_create"), self._valid_data(carrier_a, origin_text="Chicago"))
        assert resp.status_code == 302
        load = Load.objects.get(tenant=tenant_a, origin_text="Chicago")
        assert load.number == "LD-00001"
        assert load.status == "planning"

    def test_edit_updates_notes_while_planning(self, client_a, load_a, carrier_a):
        resp = client_a.post(reverse("scm:load_edit", args=[load_a.pk]),
                             self._valid_data(carrier_a, notes="edited"))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.notes == "edited"

    def test_edit_blocked_once_booked(self, client_a, load_a):
        client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        resp = client_a.get(reverse("scm:load_edit", args=[load_a.pk]))
        assert resp.status_code == 302

    def test_delete_while_planning_removes_it(self, client_a, load_a):
        from apps.scm.models import Load
        resp = client_a.post(reverse("scm:load_delete", args=[load_a.pk]))
        assert resp.status_code == 302
        assert not Load.objects.filter(pk=load_a.pk).exists()

    def test_delete_blocked_once_booked(self, client_a, load_a):
        from apps.scm.models import Load
        client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        resp = client_a.post(reverse("scm:load_delete", args=[load_a.pk]))
        assert resp.status_code == 302
        assert Load.objects.filter(pk=load_a.pk).exists()

    def test_detail_shows_utilization_context(self, client_a, load_a):
        resp = client_a.get(reverse("scm:load_detail", args=[load_a.pk]))
        assert resp.status_code == 200
        assert resp.context["weight_util"] is None  # no equipment capacity set on the fixture
        assert resp.context["planned_weight"] == Decimal("0")


class TestLoadLifecycle:
    def test_tender_requires_a_carrier(self, client_a, tenant_a):
        from apps.scm.models import Load
        load = Load.objects.create(tenant=tenant_a)
        resp = client_a.post(reverse("scm:load_tender", args=[load.pk]))
        assert resp.status_code == 302
        load.refresh_from_db()
        assert load.status == "planning"

    def test_tender_with_a_carrier_moves_to_tendered(self, client_a, load_a):
        resp = client_a.post(reverse("scm:load_tender", args=[load_a.pk]))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.status == "tendered"

    def test_book_from_planning_moves_to_booked(self, client_a, load_a):
        resp = client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.status == "booked"

    def test_book_without_a_carrier_is_refused(self, client_a, tenant_a):
        from apps.scm.models import Load
        load = Load.objects.create(tenant=tenant_a)
        resp = client_a.post(reverse("scm:load_book", args=[load.pk]))
        load.refresh_from_db()
        assert load.status == "planning"

    def test_dispatch_from_booked_moves_to_in_transit_and_stamps_departure(self, client_a, load_a):
        client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        resp = client_a.post(reverse("scm:load_dispatch", args=[load_a.pk]))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.status == "in_transit"
        assert load_a.actual_departure is not None

    def test_deliver_from_in_transit_moves_to_delivered_and_stamps_arrival(self, client_a, load_a):
        client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        client_a.post(reverse("scm:load_dispatch", args=[load_a.pk]))
        resp = client_a.post(reverse("scm:load_deliver", args=[load_a.pk]))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.status == "delivered"
        assert load_a.actual_arrival is not None

    def test_illegal_transition_is_refused_gracefully(self, client_a, load_a):
        resp = client_a.post(reverse("scm:load_deliver", args=[load_a.pk]))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.status == "planning"

    def test_cancel_from_planning_moves_to_cancelled(self, client_a, load_a):
        resp = client_a.post(reverse("scm:load_cancel", args=[load_a.pk]))
        assert resp.status_code == 302
        load_a.refresh_from_db()
        assert load_a.status == "cancelled"

    def test_cancel_already_closed_load_is_refused(self, client_a, load_a):
        client_a.post(reverse("scm:load_cancel", args=[load_a.pk]))
        resp = client_a.post(reverse("scm:load_cancel", args=[load_a.pk]))
        assert resp.status_code == 302


# ================================================================ Shipment CRUD
class TestShipmentCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, shipment_a):
        resp = client_a.get(reverse("scm:shipment_list"))
        assert resp.status_code == 200
        assert shipment_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, shipment_a, shipment_b):
        resp = client_a.get(reverse("scm:shipment_list"))
        assert shipment_b not in resp.context["object_list"]

    def test_list_search_by_number(self, client_a, shipment_a):
        resp = client_a.get(reverse("scm:shipment_list"), {"q": shipment_a.number})
        assert shipment_a in resp.context["object_list"]

    def test_list_filter_by_direction(self, client_a, shipment_a):
        resp = client_a.get(reverse("scm:shipment_list"), {"direction": "outbound"})
        assert shipment_a in resp.context["object_list"]
        resp2 = client_a.get(reverse("scm:shipment_list"), {"direction": "inbound"})
        assert shipment_a not in resp2.context["object_list"]

    def test_list_filter_by_carrier(self, client_a, shipment_a, carrier_a):
        resp = client_a.get(reverse("scm:shipment_list"), {"carrier": str(carrier_a.pk)})
        assert shipment_a in resp.context["object_list"]

    def _valid_data(self, carrier=None, **overrides):
        data = {
            "direction": "outbound", "carrier": str(carrier.pk) if carrier else "", "load": "",
            "sales_order": "", "purchase_order": "", "ship_from_address": "", "ship_to_address": "",
            "origin_text": "", "destination_text": "", "mode": "truckload",
            "planned_pickup_date": "", "planned_delivery_date": "", "weight_kg": "", "volume_cbm": "",
            "package_count": "", "carrier_tracking_number": "", "freight_cost_estimate": "", "notes": "",
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant(self, client_a, tenant_a, carrier_a):
        from apps.scm.models import Shipment
        resp = client_a.post(reverse("scm:shipment_create"),
                             self._valid_data(carrier_a, origin_text="Chicago"))
        assert resp.status_code == 302
        shipment = Shipment.objects.get(tenant=tenant_a, origin_text="Chicago")
        assert shipment.number == "SHP-00001"
        assert shipment.status == "planned"

    def test_edit_updates_notes_while_planned(self, client_a, shipment_a, carrier_a):
        resp = client_a.post(reverse("scm:shipment_edit", args=[shipment_a.pk]),
                             self._valid_data(carrier_a, notes="edited"))
        assert resp.status_code == 302
        shipment_a.refresh_from_db()
        assert shipment_a.notes == "edited"

    def test_edit_blocked_once_in_transit(self, client_a, shipment_a):
        client_a.post(reverse("scm:shipment_book", args=[shipment_a.pk]))
        from apps.scm.models import TrackingEvent
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="pickup")
        shipment_a.apply_tracking_event(event)
        resp = client_a.get(reverse("scm:shipment_edit", args=[shipment_a.pk]))
        assert resp.status_code == 302

    def test_delete_while_planned_removes_it(self, client_a, shipment_a):
        from apps.scm.models import Shipment
        resp = client_a.post(reverse("scm:shipment_delete", args=[shipment_a.pk]))
        assert resp.status_code == 302
        assert not Shipment.objects.filter(pk=shipment_a.pk).exists()

    def test_delete_blocked_once_in_transit(self, client_a, shipment_a):
        from apps.scm.models import Shipment, TrackingEvent
        client_a.post(reverse("scm:shipment_book", args=[shipment_a.pk]))
        event = TrackingEvent.objects.create(shipment=shipment_a, event_type="pickup")
        shipment_a.apply_tracking_event(event)
        resp = client_a.post(reverse("scm:shipment_delete", args=[shipment_a.pk]))
        assert resp.status_code == 302
        assert Shipment.objects.filter(pk=shipment_a.pk).exists()

    def test_detail_shows_events_and_the_event_form(self, client_a, shipment_a):
        resp = client_a.get(reverse("scm:shipment_detail", args=[shipment_a.pk]))
        assert resp.status_code == 200
        assert resp.context["events"] == []
        assert resp.context["event_form"] is not None


class TestShipmentLifecycle:
    def test_book_requires_a_carrier(self, client_a, tenant_a):
        from apps.scm.models import Shipment
        shipment = Shipment.objects.create(tenant=tenant_a)
        resp = client_a.post(reverse("scm:shipment_book", args=[shipment.pk]))
        shipment.refresh_from_db()
        assert shipment.status == "planned"

    def test_book_with_a_carrier_moves_to_booked(self, client_a, shipment_a):
        resp = client_a.post(reverse("scm:shipment_book", args=[shipment_a.pk]))
        assert resp.status_code == 302
        shipment_a.refresh_from_db()
        assert shipment_a.status == "booked"

    def test_add_pickup_event_moves_booked_shipment_to_in_transit(self, client_a, shipment_a):
        client_a.post(reverse("scm:shipment_book", args=[shipment_a.pk]))
        resp = client_a.post(reverse("scm:shipment_add_event", args=[shipment_a.pk]), {
            "event_type": "pickup", "event_at": "2026-01-05T09:00", "location_text": "Chicago DC",
            "latitude": "", "longitude": "", "source": "manual", "notes": "",
        })
        assert resp.status_code == 302
        shipment_a.refresh_from_db()
        assert shipment_a.status == "in_transit"
        assert shipment_a.actual_pickup_at is not None

    def test_add_delivered_event_closes_shipment_and_recomputes_carrier_scorecard(
        self, client_a, shipment_a, carrier_a,
    ):
        shipment_a.planned_delivery_date = datetime.date(2026, 1, 10)
        shipment_a.save(update_fields=["planned_delivery_date"])
        resp = client_a.post(reverse("scm:shipment_add_event", args=[shipment_a.pk]), {
            "event_type": "delivered", "event_at": "2026-01-09T14:00", "location_text": "Dallas DC",
            "latitude": "", "longitude": "", "source": "manual", "notes": "",
        })
        assert resp.status_code == 302
        shipment_a.refresh_from_db()
        assert shipment_a.status == "delivered"
        assert shipment_a.actual_delivery_at is not None
        carrier_a.refresh_from_db()
        assert carrier_a.on_time_delivery_pct == Decimal("100.00")

    def test_add_event_blocked_once_shipment_is_closed(self, client_a, shipment_a):
        from apps.scm.models import TrackingEvent
        shipment_a.status = "delivered"
        shipment_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:shipment_add_event", args=[shipment_a.pk]), {
            "event_type": "exception", "event_at": "2026-01-05T09:00", "location_text": "",
            "latitude": "", "longitude": "", "source": "manual", "notes": "",
        })
        assert resp.status_code == 302
        assert not TrackingEvent.objects.filter(shipment=shipment_a).exists()

    def test_add_event_with_invalid_data_does_not_500(self, client_a, shipment_a):
        resp = client_a.post(reverse("scm:shipment_add_event", args=[shipment_a.pk]), {
            "event_type": "not-a-real-type", "event_at": "", "location_text": "",
            "latitude": "", "longitude": "", "source": "manual", "notes": "",
        })
        assert resp.status_code == 302

    def test_cancel_with_a_reason_appends_it_to_notes(self, client_a, shipment_a):
        resp = client_a.post(reverse("scm:shipment_cancel", args=[shipment_a.pk]),
                             {"cancel_reason": "customer request"})
        assert resp.status_code == 302
        shipment_a.refresh_from_db()
        assert shipment_a.status == "cancelled"
        assert "customer request" in shipment_a.notes

    def test_cancel_already_closed_shipment_is_refused(self, client_a, shipment_a):
        client_a.post(reverse("scm:shipment_cancel", args=[shipment_a.pk]))
        resp = client_a.post(reverse("scm:shipment_cancel", args=[shipment_a.pk]))
        assert resp.status_code == 302


# ================================================================ FreightInvoice CRUD
class TestFreightInvoiceCRUD:
    def test_list_returns_200_and_contains_own_tenant_row(self, client_a, freight_invoice_a):
        resp = client_a.get(reverse("scm:freightinvoice_list"))
        assert resp.status_code == 200
        assert freight_invoice_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, freight_invoice_a, freight_invoice_b):
        resp = client_a.get(reverse("scm:freightinvoice_list"))
        assert freight_invoice_b not in resp.context["object_list"]

    def test_list_search_by_carrier_invoice_number(self, client_a, freight_invoice_a):
        freight_invoice_a.carrier_invoice_number = "CARR-42"
        freight_invoice_a.save(update_fields=["carrier_invoice_number"])
        resp = client_a.get(reverse("scm:freightinvoice_list"), {"q": "CARR-42"})
        assert freight_invoice_a in resp.context["object_list"]

    def test_list_filter_by_match_status(self, client_a, freight_invoice_a):
        resp = client_a.get(reverse("scm:freightinvoice_list"), {"match_status": "not_matched"})
        assert freight_invoice_a in resp.context["object_list"]

    def test_list_filter_by_carrier(self, client_a, freight_invoice_a, carrier_a):
        resp = client_a.get(reverse("scm:freightinvoice_list"), {"carrier": str(carrier_a.pk)})
        assert freight_invoice_a in resp.context["object_list"]

    def _valid_data(self, carrier, **overrides):
        data = {
            "carrier": str(carrier.pk), "load": "", "shipment": "", "carrier_invoice_number": "",
            "invoice_date": "", "due_date": "", "currency": "", "match_tolerance_pct": "2.00", "notes": "",
            **formset_data("lines", []),
        }
        data.update(overrides)
        return data

    def test_create_saves_with_request_tenant_and_runs_the_audit(self, client_a, tenant_a, carrier_a):
        from apps.scm.models import FreightInvoice
        data = self._valid_data(carrier_a, notes="fresh invoice",
                                **formset_data("lines", [
                                    {"id": "", "charge_type": "linehaul", "description": "",
                                     "billed_amount": "500.00", "contract_amount": "500.00"},
                                ]))
        resp = client_a.post(reverse("scm:freightinvoice_create"), data)
        assert resp.status_code == 302
        inv = FreightInvoice.objects.get(tenant=tenant_a, notes="fresh invoice")
        assert inv.number == "FRT-00001"
        assert inv.billed_amount == Decimal("500.00")
        assert inv.match_status == "matched"

    def test_edit_blocked_once_approved(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        resp = client_a.get(reverse("scm:freightinvoice_edit", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302

    def test_delete_removes_a_pending_invoice(self, client_a, freight_invoice_a):
        from apps.scm.models import FreightInvoice
        resp = client_a.post(reverse("scm:freightinvoice_delete", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        assert not FreightInvoice.objects.filter(pk=freight_invoice_a.pk).exists()

    def test_delete_blocked_once_approved(self, client_a, freight_invoice_a):
        from apps.scm.models import FreightInvoice
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        resp = client_a.post(reverse("scm:freightinvoice_delete", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        assert FreightInvoice.objects.filter(pk=freight_invoice_a.pk).exists()

    def test_detail_shows_lines(self, client_a, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a, billed_amount=Decimal("100"),
                                          contract_amount=Decimal("100"))
        resp = client_a.get(reverse("scm:freightinvoice_detail", args=[freight_invoice_a.pk]))
        assert resp.status_code == 200
        assert len(resp.context["lines"]) == 1


class TestFreightInvoiceLifecycleActions:
    def test_run_audit_action_recomputes_match_status(self, client_a, freight_invoice_a):
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a,
                                          billed_amount=Decimal("600"), contract_amount=Decimal("500"))
        resp = client_a.post(reverse("scm:freightinvoice_run_audit", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.match_status == "price_variance"

    def test_run_audit_is_frozen_once_approved(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        resp = client_a.post(reverse("scm:freightinvoice_run_audit", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302

    def test_dispute_requires_a_reason(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_dispute", args=[freight_invoice_a.pk]), {"dispute_reason": ""})
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.match_status != "disputed"

    def test_dispute_with_a_reason_sets_disputed(self, client_a, freight_invoice_a):
        resp = client_a.post(reverse("scm:freightinvoice_dispute", args=[freight_invoice_a.pk]),
                             {"dispute_reason": "carrier overcharged"})
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.match_status == "disputed"
        assert freight_invoice_a.dispute_reason == "carrier overcharged"

    def test_dispute_blocked_once_approved(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        client_a.post(reverse("scm:freightinvoice_dispute", args=[freight_invoice_a.pk]),
                      {"dispute_reason": "too late"})
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.match_status != "disputed"

    def test_approve_blocked_while_disputed(self, client_a, freight_invoice_a):
        freight_invoice_a.match_status = "disputed"
        freight_invoice_a.save(update_fields=["match_status"])
        resp = client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "pending"


# ================================================================================================
# FreightInvoice approve/reject state machine — the code-review regression: a crafted POST must
# never overturn an already-decided invoice.
# ================================================================================================
class TestFreightInvoiceApprovalStateMachine:
    def test_reject_on_an_approved_invoice_is_blocked(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "approved"

        resp = client_a.post(reverse("scm:freightinvoice_reject", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "approved"  # unchanged

    def test_approve_on_a_rejected_invoice_is_blocked(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_reject", args=[freight_invoice_a.pk]))
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "rejected"

        resp = client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "rejected"  # unchanged

    def test_reject_already_handed_off_invoice_is_blocked(self, client_a, freight_invoice_a):
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        client_a.post(reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk]))
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.bill_id is not None

        resp = client_a.post(reverse("scm:freightinvoice_reject", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "approved"


# ================================================================================================
# FreightInvoice.handoff — drafts an accounting.Bill, never posts a journal entry, and is idempotent.
# ================================================================================================
class TestFreightInvoiceHandoff:
    def test_handoff_creates_exactly_one_draft_bill_for_the_carrier_party(
        self, client_a, tenant_a, freight_invoice_a, carrier_a,
    ):
        from apps.accounting.models import Bill
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a, billed_amount=Decimal("500.00"),
                                          contract_amount=Decimal("500.00"))
        freight_invoice_a.run_audit()
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))

        resp = client_a.post(reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.bill_id is not None
        bill = freight_invoice_a.bill
        assert bill.party_id == carrier_a.party_id
        assert bill.status == "draft"
        assert bill.journal_entry_id is None
        assert Bill.objects.filter(tenant=tenant_a).count() == 1

    def test_second_handoff_is_a_no_op_and_does_not_duplicate_the_bill(
        self, client_a, tenant_a, freight_invoice_a,
    ):
        from apps.accounting.models import Bill
        from apps.scm.models import FreightInvoiceLine
        FreightInvoiceLine.objects.create(freight_invoice=freight_invoice_a, billed_amount=Decimal("500.00"),
                                          contract_amount=Decimal("500.00"))
        freight_invoice_a.run_audit()
        client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        client_a.post(reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk]))
        first_bill_id = freight_invoice_a.__class__.objects.get(pk=freight_invoice_a.pk).bill_id

        client_a.post(reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk]))
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.bill_id == first_bill_id
        assert Bill.objects.filter(tenant=tenant_a).count() == 1

    def test_handoff_requires_approval_first(self, client_a, freight_invoice_a):
        resp = client_a.post(reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk]))
        assert resp.status_code == 302
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.bill_id is None


# ================================================================================================
# Negative-input hardening (L11/L9) — junk FK/status filters and out-of-range pages must 200, not 500.
# ================================================================================================
class TestTMSNegativeInputHardening:
    def test_carrier_list_junk_carrier_type_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:carrier_list"), {"carrier_type": "not-a-real-type"})
        assert resp.status_code == 200

    def test_carrier_list_junk_status_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:carrier_list"), {"status": "nonsense"})
        assert resp.status_code == 200

    def test_carrier_list_page_past_the_end_returns_200(self, client_a, carrier_a):
        resp = client_a.get(reverse("scm:carrier_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_load_list_junk_carrier_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:load_list"), {"carrier": "abc"})
        assert resp.status_code == 200

    def test_load_list_junk_status_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:load_list"), {"status": "nonsense"})
        assert resp.status_code == 200

    def test_load_list_page_2_returns_200_when_rows_exceed_page_size(self, client_a, tenant_a, carrier_a):
        from apps.scm.models import Load
        for _ in range(20):
            Load.objects.create(tenant=tenant_a, carrier=carrier_a)
        resp = client_a.get(reverse("scm:load_list"), {"page": "2"})
        assert resp.status_code == 200

    def test_shipment_list_junk_carrier_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:shipment_list"), {"carrier": "abc"})
        assert resp.status_code == 200

    def test_shipment_list_junk_status_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:shipment_list"), {"status": "nonsense"})
        assert resp.status_code == 200

    def test_shipment_list_page_past_the_end_returns_200(self, client_a, shipment_a):
        resp = client_a.get(reverse("scm:shipment_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_freightinvoice_list_junk_carrier_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:freightinvoice_list"), {"carrier": "abc"})
        assert resp.status_code == 200

    def test_freightinvoice_list_junk_match_status_filter_returns_200(self, client_a):
        resp = client_a.get(reverse("scm:freightinvoice_list"), {"match_status": "nonsense"})
        assert resp.status_code == 200

    def test_freightinvoice_list_page_past_the_end_returns_200(self, client_a, freight_invoice_a):
        resp = client_a.get(reverse("scm:freightinvoice_list"), {"page": "999"})
        assert resp.status_code == 200


# ================================================================================================
# List-view N+1 guards (locks in the select_related as rows grow)
# ================================================================================================
class TestTMSListQueryCounts:
    def test_carrier_list_no_n_plus_one_query_blowup(self, client_a, tenant_a, django_assert_max_num_queries):
        from apps.core.models import Party, PartyRole
        from apps.scm.models import Carrier
        for i in range(8):
            party = Party.objects.create(tenant=tenant_a, name=f"Carrier {i}", kind="organization")
            PartyRole.objects.create(tenant=tenant_a, party=party, role="vendor")
            Carrier.objects.create(tenant=tenant_a, party=party)
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:carrier_list"))
        assert resp.status_code == 200

    def test_load_list_no_n_plus_one_query_blowup(
        self, client_a, tenant_a, carrier_a, django_assert_max_num_queries,
    ):
        from apps.scm.models import Load
        for _ in range(8):
            Load.objects.create(tenant=tenant_a, carrier=carrier_a)
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:load_list"))
        assert resp.status_code == 200

    def test_shipment_list_no_n_plus_one_query_blowup(
        self, client_a, tenant_a, carrier_a, django_assert_max_num_queries,
    ):
        from apps.scm.models import Shipment
        for _ in range(8):
            Shipment.objects.create(tenant=tenant_a, carrier=carrier_a)
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:shipment_list"))
        assert resp.status_code == 200

    def test_freightinvoice_list_no_n_plus_one_query_blowup(
        self, client_a, tenant_a, carrier_a, django_assert_max_num_queries,
    ):
        from apps.scm.models import FreightInvoice
        for _ in range(8):
            FreightInvoice.objects.create(tenant=tenant_a, carrier=carrier_a)
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("scm:freightinvoice_list"))
        assert resp.status_code == 200


# ================================================================ Create guarded when the user has no tenant
class TestTMSCreateWithoutTenantWorkspace:
    def test_carrier_create_redirects(self, db):
        from django.test import Client
        from apps.accounts.models import User
        from apps.scm.models import Carrier
        user = User.objects.create_user(email="orphan-tms@example.com", username="orphan_tms", password="x",
                                        tenant=None)
        c = Client()
        c.force_login(user)
        resp = c.get(reverse("scm:carrier_create"))
        assert resp.status_code == 302
        assert Carrier.objects.count() == 0

    def test_load_create_redirects(self, db):
        from django.test import Client
        from apps.accounts.models import User
        from apps.scm.models import Load
        user = User.objects.create_user(email="orphan-tms2@example.com", username="orphan_tms2", password="x",
                                        tenant=None)
        c = Client()
        c.force_login(user)
        resp = c.get(reverse("scm:load_create"))
        assert resp.status_code == 302
        assert Load.objects.count() == 0

    def test_freightinvoice_create_redirects(self, db):
        from django.test import Client
        from apps.accounts.models import User
        from apps.scm.models import FreightInvoice
        user = User.objects.create_user(email="orphan-tms3@example.com", username="orphan_tms3", password="x",
                                        tenant=None)
        c = Client()
        c.force_login(user)
        resp = c.get(reverse("scm:freightinvoice_create"))
        assert resp.status_code == 302
        assert FreightInvoice.objects.count() == 0


# ================================================================================================
# SCM 4.7 Demand Planning & Forecasting
# ================================================================================================

def _forecast_payload(item, start, end, **overrides):
    data = {
        "name": "New widget plan", "item": str(item.pk), "location": "", "customer": "",
        "demand_source": "sales_orders", "bucket": "month", "horizon_start": start.isoformat(),
        "horizon_end": end.isoformat(), "history_months": "24", "method": "moving_average",
        "method_parameter": "3", "seasonality_profile": "", "reference_item": "",
        "reference_scale_pct": "100", "exclude_outliers": "", "outlier_threshold_sigma": "3",
        "currency": "", "scenario": "baseline", "notes": "",
        **formset_data("periods", []),
    }
    data.update(overrides)
    return data


def _profile_payload(**overrides):
    data = {
        "name": "New curve", "profile_type": "seasonal", "bucket": "month", "scope": "global",
        "item": "", "category": "", "location": "", "event_start": "", "event_end": "",
        "uplift_pct": "0", "cannibalization_pct": "0", "cannibalized_category": "",
        "promotion_mechanic": "", "derived_from_years": "2", "is_active": "on", "notes": "",
        **formset_data("indices", []),
    }
    data.update(overrides)
    return data


def _signal_payload(**overrides):
    from django.utils import timezone
    data = {
        "signal_type": "pos_sell_through", "source": "retailer_pos", "source_reference": "",
        "item": "", "category": "", "location": "", "customer": "",
        "observed_at": timezone.now().strftime("%Y-%m-%dT%H:%M"), "effective_from": "",
        "effective_to": "", "horizon_days": "28", "signal_value": "0", "baseline_value": "0",
        "impact_direction": "increase", "impact_pct": "0", "impact_quantity": "0",
        "confidence": "medium", "notes": "",
    }
    data.update(overrides)
    return data


def _adjustment_payload(forecast, **overrides):
    data = {
        "forecast": str(forecast.pk), "period": "", "contributor_function": "sales",
        "org_unit": "", "adjustment_type": "absolute", "proposed_quantity": "140",
        "adjustment_pct": "0", "reason_code": "promotion", "rationale": "Spring campaign.",
        "confidence": "medium",
    }
    data.update(overrides)
    return data


# ================================================================ SeasonalityProfile CRUD
class TestSeasonalityProfileCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, seasonality_profile_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_list"))
        assert resp.status_code == 200
        assert seasonality_profile_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, seasonality_profile_a,
                                             seasonality_profile_b):
        resp = client_a.get(reverse("scm:seasonalityprofile_list"))
        assert seasonality_profile_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, seasonality_profile_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_list"))
        assert "scm/demandplanning/seasonalityprofile/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "type_choices", "scope_choices",
                    "bucket_choices", "items", "categories", "locations"):
            assert key in resp.context, key

    def test_list_search_by_name(self, client_a, seasonality_profile_a):
        found = client_a.get(reverse("scm:seasonalityprofile_list"), {"q": "Widget seasonality"})
        missed = client_a.get(reverse("scm:seasonalityprofile_list"), {"q": "no such curve"})
        assert seasonality_profile_a in found.context["object_list"]
        assert seasonality_profile_a not in missed.context["object_list"]

    def test_list_filter_by_profile_type(self, client_a, seasonality_profile_a,
                                         promotion_profile_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_list"), {"profile_type": "promotion"})
        rows = list(resp.context["object_list"])
        assert promotion_profile_a in rows
        assert seasonality_profile_a not in rows

    def test_list_filter_by_item(self, client_a, seasonality_profile_a, item_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_list"), {"item": str(item_a.pk)})
        assert seasonality_profile_a in resp.context["object_list"]

    def test_create_saves_with_the_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import SeasonalityProfile
        resp = client_a.post(reverse("scm:seasonalityprofile_create"), _profile_payload())
        assert resp.status_code == 302
        profile = SeasonalityProfile.objects.get(name="New curve")
        assert profile.tenant_id == tenant_a.pk
        assert profile.number == "SEA-00001"

    def test_create_saves_the_index_rows_in_the_same_transaction(self, client_a, tenant_a):
        from apps.scm.models import SeasonalityProfile
        data = _profile_payload(**formset_data("indices", [
            {"id": "", "period_number": "1", "period_label": "Jan", "index_factor": "0.8"},
            {"id": "", "period_number": "2", "period_label": "Feb", "index_factor": "1.2"},
        ]))
        client_a.post(reverse("scm:seasonalityprofile_create"), data)
        profile = SeasonalityProfile.objects.get(name="New curve")
        assert profile.indices.count() == 2

    def test_create_rejects_an_invalid_payload_without_saving(self, client_a, tenant_a):
        from apps.scm.models import SeasonalityProfile
        resp = client_a.post(reverse("scm:seasonalityprofile_create"),
                             _profile_payload(profile_type="promotion", scope="global"))
        assert resp.status_code == 200
        assert not SeasonalityProfile.objects.filter(tenant=tenant_a).exists()

    def test_detail_returns_200_with_the_index_rows(self, client_a, seasonality_profile_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_detail",
                                    args=[seasonality_profile_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == seasonality_profile_a
        assert len(resp.context["indices"]) == 12
        assert resp.context["peak_factor"] == Decimal("1.5000")

    def test_detail_peak_factor_never_divides_by_zero(self, client_a, category_profile_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_detail", args=[category_profile_a.pk]))
        assert resp.status_code == 200
        assert resp.context["peak_factor"] == Decimal("1")

    def test_edit_updates_the_row(self, client_a, seasonality_profile_a):
        resp = client_a.post(reverse("scm:seasonalityprofile_edit", args=[seasonality_profile_a.pk]),
                             _profile_payload(name="Renamed curve", scope="item",
                                              item=str(seasonality_profile_a.item_id)))
        assert resp.status_code == 302
        seasonality_profile_a.refresh_from_db()
        assert seasonality_profile_a.name == "Renamed curve"

    def test_delete_is_post_only(self, client_a, seasonality_profile_a):
        from apps.scm.models import SeasonalityProfile
        assert client_a.get(reverse("scm:seasonalityprofile_delete",
                                    args=[seasonality_profile_a.pk])).status_code == 405
        assert SeasonalityProfile.objects.filter(pk=seasonality_profile_a.pk).exists()

    def test_delete_removes_the_row_and_its_indices(self, client_a, seasonality_profile_a):
        from apps.scm.models import SeasonalityIndex, SeasonalityProfile
        resp = client_a.post(reverse("scm:seasonalityprofile_delete",
                                     args=[seasonality_profile_a.pk]))
        assert resp.status_code == 302
        assert not SeasonalityProfile.objects.filter(pk=seasonality_profile_a.pk).exists()
        assert not SeasonalityIndex.objects.filter(profile_id=seasonality_profile_a.pk).exists()


class TestSeasonalityProfileDerive:
    def test_derive_fills_the_index_rows_from_history(self, client_a, category_profile_a,
                                                      demand_history_a):
        resp = client_a.post(reverse("scm:seasonalityprofile_derive",
                                     args=[category_profile_a.pk]))
        assert resp.status_code == 302
        category_profile_a.refresh_from_db()
        assert category_profile_a.indices.exists()
        assert category_profile_a.last_derived_at is not None

    def test_a_flat_history_derives_a_neutral_curve(self, client_a, tenant_a, category_a,
                                                    customer_a, category_profile_a):
        """Each factor is the period's mean / the overall mean, so a flat history MUST give 1.0000.

        The history has to cover the whole derive window (derived_from_years x 365 days back to
        today) — a partly-filled window is a genuinely uneven curve, not a flat one.
        """
        from django.utils import timezone
        from apps.scm.models import Item, SalesOrder, SalesOrderLine
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        item = Item.objects.create(tenant=tenant_a, sku="FLAT-1", name="Flat seller",
                                   category=category_a)
        for back in range(25, -1, -1):
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=add_months(this_month, -back),
                                              status="submitted")
            SalesOrderLine.objects.create(sales_order=order, item=item,
                                          quantity_ordered=Decimal("100"),
                                          unit_price=Decimal("1"))
        client_a.post(reverse("scm:seasonalityprofile_derive", args=[category_profile_a.pk]))
        factors = {row.index_factor for row in category_profile_a.indices.all()}
        assert factors == {Decimal("1.0000")}

    def test_a_seasonal_history_derives_a_peak_above_neutral(self, client_a, tenant_a, category_a,
                                                             customer_a, category_profile_a):
        from django.utils import timezone
        from apps.scm.models import Item, SalesOrder, SalesOrderLine
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        item = Item.objects.create(tenant=tenant_a, sku="PEAKY-1", name="Peaky seller",
                                   category=category_a)
        peak_month = add_months(this_month, -3).month
        for back in range(25, -1, -1):
            when = add_months(this_month, -back)
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=when, status="submitted")
            SalesOrderLine.objects.create(
                sales_order=order, item=item,
                quantity_ordered=Decimal("300") if when.month == peak_month else Decimal("100"),
                unit_price=Decimal("1"))
        client_a.post(reverse("scm:seasonalityprofile_derive", args=[category_profile_a.pk]))
        peak = category_profile_a.indices.get(period_number=peak_month)
        trough = category_profile_a.indices.exclude(period_number=peak_month).first()
        assert peak.index_factor > Decimal("1")
        assert trough.index_factor < peak.index_factor

    def test_derive_records_the_sample_size(self, client_a, category_profile_a, demand_history_a):
        client_a.post(reverse("scm:seasonalityprofile_derive", args=[category_profile_a.pk]))
        assert all(row.sample_size >= 1 for row in category_profile_a.indices.all())

    def test_derive_is_idempotent_and_updates_in_place(self, client_a, category_profile_a,
                                                       demand_history_a):
        client_a.post(reverse("scm:seasonalityprofile_derive", args=[category_profile_a.pk]))
        first = set(category_profile_a.indices.values_list("pk", flat=True))
        client_a.post(reverse("scm:seasonalityprofile_derive", args=[category_profile_a.pk]))
        assert set(category_profile_a.indices.values_list("pk", flat=True)) == first

    def test_derive_refuses_an_item_with_no_orders_at_all(self, client_a, seasonality_profile_a):
        """The item-scoped series is DENSE, so an item that never sold yields zero-filled buckets
        rather than an empty list — the zero-total guard is what refuses here."""
        resp = client_a.post(reverse("scm:seasonalityprofile_derive",
                                     args=[seasonality_profile_a.pk]), follow=True)
        assert resp.status_code == 200
        assert any("No sales history" in str(m) for m in resp.context["messages"])
        assert not seasonality_profile_a.indices.filter(sample_size__gt=0).exists()

    def test_derive_refuses_on_a_location_scoped_profile(self, client_a, tenant_a, location_a,
                                                         demand_history_a):
        from apps.scm.models import SeasonalityProfile
        profile = SeasonalityProfile.objects.create(tenant=tenant_a, name="Site curve",
                                                    scope="location", location=location_a)
        resp = client_a.post(reverse("scm:seasonalityprofile_derive", args=[profile.pk]),
                             follow=True)
        assert not profile.indices.exists()
        assert any("Nothing to derive from" in str(m) for m in resp.context["messages"])

    def test_derive_refuses_when_the_history_totals_zero(self, client_a, tenant_a, category_a,
                                                        item_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine, SeasonalityProfile
        from apps.scm.tests._helpers import add_months, month_start
        order = SalesOrder.objects.create(
            tenant=tenant_a, customer=customer_a, status="submitted",
            order_date=add_months(month_start(timezone.localdate()), -2))
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("0"), unit_price=Decimal("1"))
        profile = SeasonalityProfile.objects.create(tenant=tenant_a, name="Zero curve",
                                                    scope="category", category=category_a)
        resp = client_a.post(reverse("scm:seasonalityprofile_derive", args=[profile.pk]),
                             follow=True)
        assert any("No sales history" in str(m) for m in resp.context["messages"])

    def test_derive_is_post_only(self, client_a, category_profile_a):
        assert client_a.get(reverse("scm:seasonalityprofile_derive",
                                    args=[category_profile_a.pk])).status_code == 405


# ================================================================ DemandForecast CRUD
class TestDemandForecastCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, demand_forecast_a):
        resp = client_a.get(reverse("scm:demandforecast_list"))
        assert resp.status_code == 200
        assert demand_forecast_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, demand_forecast_a, demand_forecast_b):
        resp = client_a.get(reverse("scm:demandforecast_list"))
        assert demand_forecast_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, demand_forecast_a):
        resp = client_a.get(reverse("scm:demandforecast_list"))
        assert "scm/demandplanning/demandforecast/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "status_choices", "method_choices",
                    "bucket_choices", "scenario_choices", "items", "locations"):
            assert key in resp.context, key

    def test_list_search_by_number(self, client_a, demand_forecast_a):
        resp = client_a.get(reverse("scm:demandforecast_list"), {"q": demand_forecast_a.number})
        assert demand_forecast_a in resp.context["object_list"]

    def test_list_filter_by_status(self, client_a, tenant_a, forecast_with_periods_a):
        from apps.scm.models import DemandForecast
        draft = DemandForecast.objects.create(
            tenant=tenant_a, name="Still a draft", item=forecast_with_periods_a.item,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=forecast_with_periods_a.horizon_end)
        resp = client_a.get(reverse("scm:demandforecast_list"), {"status": "statistical"})
        rows = list(resp.context["object_list"])
        assert forecast_with_periods_a in rows
        assert draft not in rows

    def test_list_filter_by_item(self, client_a, demand_forecast_a, item_a):
        resp = client_a.get(reverse("scm:demandforecast_list"), {"item": str(item_a.pk)})
        assert demand_forecast_a in resp.context["object_list"]

    def test_create_saves_with_the_request_tenant(self, client_a, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        end = add_months(start, 3) - datetime.timedelta(days=1)
        resp = client_a.post(reverse("scm:demandforecast_create"),
                             _forecast_payload(item_a, start, end))
        assert resp.status_code == 302
        forecast = DemandForecast.objects.get(name="New widget plan")
        assert forecast.tenant_id == tenant_a.pk
        assert forecast.number == "DF-00001"
        assert forecast.status == "draft"  # the grid is built by Generate, not by Save

    def test_create_ignores_a_status_posted_in_the_body(self, client_a, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        end = add_months(start, 3) - datetime.timedelta(days=1)
        client_a.post(reverse("scm:demandforecast_create"),
                      _forecast_payload(item_a, start, end, status="approved",
                                        number="DF-99999", selected_method="holt_winters",
                                        revision="9"))
        forecast = DemandForecast.objects.get(name="New widget plan")
        assert forecast.status == "draft"
        assert forecast.number == "DF-00001"
        assert forecast.selected_method == ""
        assert forecast.revision == 1

    def test_create_rejects_an_over_long_horizon(self, client_a, tenant_a, item_a):
        from apps.scm.models import DemandForecast
        resp = client_a.post(reverse("scm:demandforecast_create"),
                             _forecast_payload(item_a, datetime.date(2026, 1, 1),
                                               datetime.date(2030, 1, 1), bucket="day"))
        assert resp.status_code == 200
        assert not DemandForecast.objects.filter(tenant=tenant_a).exists()

    def test_detail_returns_200_with_the_waterfall_context(self, client_a, forecast_with_periods_a):
        resp = client_a.get(reverse("scm:demandforecast_detail",
                                    args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 200
        assert "scm/demandplanning/demandforecast/detail.html" in [t.name for t in resp.templates]
        for key in ("obj", "rows", "accuracy", "total_quantity", "total_value", "generate_form",
                    "signals", "adjustments"):
            assert key in resp.context, key
        assert len(resp.context["rows"]) == 3
        assert resp.context["total_quantity"] == Decimal("300.0000")

    def test_edit_updates_an_open_forecast(self, client_a, demand_forecast_a):
        from django.utils import timezone
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        end = add_months(start, 3) - datetime.timedelta(days=1)
        resp = client_a.post(reverse("scm:demandforecast_edit", args=[demand_forecast_a.pk]),
                             _forecast_payload(demand_forecast_a.item, start, end,
                                               name="Renamed plan"))
        assert resp.status_code == 302
        demand_forecast_a.refresh_from_db()
        assert demand_forecast_a.name == "Renamed plan"

    def test_edit_is_refused_once_approved(self, client_a, approved_forecast_a):
        resp = client_a.get(reverse("scm:demandforecast_edit", args=[approved_forecast_a.pk]),
                            follow=True)
        assert any("revise it" in str(m) for m in resp.context["messages"])

    def test_edit_is_refused_once_archived(self, client_a, forecast_with_periods_a):
        forecast_with_periods_a.status = "archived"
        forecast_with_periods_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:demandforecast_edit", args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 302

    def test_delete_is_post_only(self, client_a, demand_forecast_a):
        from apps.scm.models import DemandForecast
        assert client_a.get(reverse("scm:demandforecast_delete",
                                    args=[demand_forecast_a.pk])).status_code == 405
        assert DemandForecast.objects.filter(pk=demand_forecast_a.pk).exists()

    def test_delete_removes_an_open_forecast(self, client_a, demand_forecast_a):
        from apps.scm.models import DemandForecast
        resp = client_a.post(reverse("scm:demandforecast_delete", args=[demand_forecast_a.pk]))
        assert resp.status_code == 302
        assert not DemandForecast.objects.filter(pk=demand_forecast_a.pk).exists()

    def test_delete_is_refused_once_approved(self, client_a, approved_forecast_a):
        from apps.scm.models import DemandForecast
        resp = client_a.post(reverse("scm:demandforecast_delete", args=[approved_forecast_a.pk]),
                             follow=True)
        assert DemandForecast.objects.filter(pk=approved_forecast_a.pk).exists()
        assert any("archive it" in str(m) for m in resp.context["messages"])


class TestDemandForecastGenerateAction:
    def test_generate_builds_the_grid(self, client_a, demand_forecast_a, demand_history_a):
        resp = client_a.post(reverse("scm:demandforecast_generate", args=[demand_forecast_a.pk]))
        assert resp.status_code == 302
        demand_forecast_a.refresh_from_db()
        assert demand_forecast_a.periods.count() == 3
        assert demand_forecast_a.status == "statistical"

    def test_generate_leaves_locked_periods_alone_by_default(self, client_a,
                                                             forecast_with_periods_a,
                                                             forecast_period_a, demand_history_a):
        forecast_period_a.is_locked, forecast_period_a.baseline_quantity = True, Decimal("999")
        forecast_period_a.save(update_fields=["is_locked", "baseline_quantity"])
        client_a.post(reverse("scm:demandforecast_generate", args=[forecast_with_periods_a.pk]))
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.baseline_quantity == Decimal("999.0000")

    def test_generate_can_be_asked_to_overwrite_locked_periods(self, client_a,
                                                               forecast_with_periods_a,
                                                               forecast_period_a,
                                                               demand_history_a):
        forecast_period_a.is_locked, forecast_period_a.baseline_quantity = True, Decimal("999")
        forecast_period_a.save(update_fields=["is_locked", "baseline_quantity"])
        client_a.post(reverse("scm:demandforecast_generate", args=[forecast_with_periods_a.pk]),
                      {"regenerate_locked": "on"})
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.baseline_quantity == Decimal("100.0000")

    def test_generate_is_refused_on_an_approved_plan(self, client_a, approved_forecast_a):
        resp = client_a.post(reverse("scm:demandforecast_generate",
                                     args=[approved_forecast_a.pk]), follow=True)
        assert any("revise an approved plan" in str(m) for m in resp.context["messages"])

    def test_generate_reports_an_empty_horizon_rather_than_500ing(self, client_a,
                                                                   demand_forecast_a):
        demand_forecast_a.horizon_end = demand_forecast_a.horizon_start - datetime.timedelta(days=1)
        demand_forecast_a.save(update_fields=["horizon_end"])
        resp = client_a.post(reverse("scm:demandforecast_generate", args=[demand_forecast_a.pk]),
                             follow=True)
        assert resp.status_code == 200
        assert any("Nothing to generate" in str(m) for m in resp.context["messages"])

    def test_generate_is_post_only(self, client_a, demand_forecast_a):
        assert client_a.get(reverse("scm:demandforecast_generate",
                                    args=[demand_forecast_a.pk])).status_code == 405


class TestDemandForecastLifecycle:
    def test_submit_for_review_moves_a_statistical_plan(self, client_a, forecast_with_periods_a):
        resp = client_a.post(reverse("scm:demandforecast_submit_review",
                                     args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 302
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "in_review"

    def test_submit_for_review_is_refused_from_approved(self, client_a, approved_forecast_a):
        client_a.post(reverse("scm:demandforecast_submit_review", args=[approved_forecast_a.pk]))
        approved_forecast_a.refresh_from_db()
        assert approved_forecast_a.status == "approved"

    def test_approve_stamps_the_approver(self, client_a, admin_user, forecast_with_periods_a):
        client_a.post(reverse("scm:demandforecast_approve", args=[forecast_with_periods_a.pk]))
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "approved"
        assert forecast_with_periods_a.approved_by_id == admin_user.pk
        assert forecast_with_periods_a.approved_at is not None

    def test_approve_is_refused_from_draft(self, client_a, demand_forecast_a):
        client_a.post(reverse("scm:demandforecast_approve", args=[demand_forecast_a.pk]))
        demand_forecast_a.refresh_from_db()
        assert demand_forecast_a.status == "draft"

    def test_archive_retires_the_plan(self, client_a, approved_forecast_a):
        client_a.post(reverse("scm:demandforecast_archive", args=[approved_forecast_a.pk]))
        approved_forecast_a.refresh_from_db()
        assert approved_forecast_a.status == "archived"

    def test_archive_is_refused_on_an_already_archived_plan(self, client_a,
                                                            forecast_with_periods_a):
        forecast_with_periods_a.status = "archived"
        forecast_with_periods_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:demandforecast_archive",
                                     args=[forecast_with_periods_a.pk]), follow=True)
        assert any("can't be archived" in str(m) for m in resp.context["messages"])

    def test_revise_clones_the_plan_and_archives_the_original(self, client_a,
                                                              approved_forecast_a):
        from apps.scm.models import DemandForecast
        resp = client_a.post(reverse("scm:demandforecast_revise", args=[approved_forecast_a.pk]))
        assert resp.status_code == 302
        approved_forecast_a.refresh_from_db()
        assert approved_forecast_a.status == "archived"
        revision = DemandForecast.objects.get(supersedes=approved_forecast_a)
        assert revision.revision == 2
        assert revision.status == "statistical"
        assert revision.approved_by_id is None
        assert revision.number != approved_forecast_a.number

    def test_revise_copies_the_period_grid(self, client_a, approved_forecast_a):
        from apps.scm.models import DemandForecast
        client_a.post(reverse("scm:demandforecast_revise", args=[approved_forecast_a.pk]))
        revision = DemandForecast.objects.get(supersedes=approved_forecast_a)
        assert revision.periods.count() == approved_forecast_a.periods.count()
        assert revision.periods.first().final_quantity == Decimal("100.0000")

    def test_revise_is_refused_on_an_archived_plan(self, client_a, forecast_with_periods_a):
        from apps.scm.models import DemandForecast
        forecast_with_periods_a.status = "archived"
        forecast_with_periods_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:demandforecast_revise",
                                     args=[forecast_with_periods_a.pk]), follow=True)
        assert any("already archived" in str(m) for m in resp.context["messages"])
        assert not DemandForecast.objects.filter(supersedes=forecast_with_periods_a).exists()

    def test_the_lifecycle_actions_are_post_only(self, client_a, forecast_with_periods_a):
        for name in ("demandforecast_submit_review", "demandforecast_approve",
                     "demandforecast_archive", "demandforecast_revise"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[forecast_with_periods_a.pk])).status_code == 405, name


# ================================================================ DemandSignal CRUD + triage
class TestDemandSignalCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, demand_signal_a):
        resp = client_a.get(reverse("scm:demandsignal_list"))
        assert resp.status_code == 200
        assert demand_signal_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, demand_signal_a, demand_signal_b):
        resp = client_a.get(reverse("scm:demandsignal_list"))
        assert demand_signal_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, demand_signal_a):
        resp = client_a.get(reverse("scm:demandsignal_list"))
        assert "scm/demandplanning/demandsignal/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "status_choices", "type_choices",
                    "source_choices", "direction_choices", "items", "locations"):
            assert key in resp.context, key

    def test_list_filter_by_signal_type(self, client_a, tenant_a, demand_signal_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        weather = DemandSignal.objects.create(tenant=tenant_a, signal_type="weather",
                                              observed_at=timezone.now())
        resp = client_a.get(reverse("scm:demandsignal_list"), {"signal_type": "weather"})
        rows = list(resp.context["object_list"])
        assert weather in rows
        assert demand_signal_a not in rows

    def test_list_search_by_source_reference(self, client_a, demand_signal_a):
        demand_signal_a.source_reference = "POS-FEED-42"
        demand_signal_a.save(update_fields=["source_reference"])
        resp = client_a.get(reverse("scm:demandsignal_list"), {"q": "POS-FEED-42"})
        assert demand_signal_a in resp.context["object_list"]

    def test_create_saves_with_the_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import DemandSignal
        resp = client_a.post(reverse("scm:demandsignal_create"),
                             _signal_payload(source_reference="POS-1"))
        assert resp.status_code == 302
        signal = DemandSignal.objects.get(source_reference="POS-1")
        assert signal.tenant_id == tenant_a.pk
        assert signal.status == "new"

    def test_create_ignores_a_status_posted_in_the_body(self, client_a, tenant_a):
        from apps.scm.models import DemandSignal
        client_a.post(reverse("scm:demandsignal_create"),
                      _signal_payload(source_reference="POS-2", status="applied",
                                      number="DS-99999"))
        signal = DemandSignal.objects.get(source_reference="POS-2")
        assert signal.status == "new"
        assert signal.number == "DS-00001"

    def test_detail_returns_200_with_the_window_and_action_forms(self, client_a, demand_signal_a):
        resp = client_a.get(reverse("scm:demandsignal_detail", args=[demand_signal_a.pk]))
        assert resp.status_code == 200
        assert "scm/demandplanning/demandsignal/detail.html" in [t.name for t in resp.templates]
        for key in ("obj", "window_from", "window_to", "apply_form", "dismiss_form"):
            assert key in resp.context, key

    def test_edit_updates_an_open_signal(self, client_a, demand_signal_a):
        resp = client_a.post(reverse("scm:demandsignal_edit", args=[demand_signal_a.pk]),
                             _signal_payload(item=str(demand_signal_a.item_id),
                                             source_reference="edited",
                                             effective_from=demand_signal_a.effective_from.isoformat(),
                                             effective_to=demand_signal_a.effective_to.isoformat()))
        assert resp.status_code == 302
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.source_reference == "edited"

    def test_edit_is_refused_once_the_signal_is_closed(self, client_a, demand_signal_a):
        from apps.scm.models import DemandSignal
        DemandSignal.objects.filter(pk=demand_signal_a.pk).update(status="dismissed")
        resp = client_a.get(reverse("scm:demandsignal_edit", args=[demand_signal_a.pk]),
                            follow=True)
        assert any("closed observation" in str(m) for m in resp.context["messages"])

    def test_delete_is_post_only(self, client_a, demand_signal_a):
        from apps.scm.models import DemandSignal
        assert client_a.get(reverse("scm:demandsignal_delete",
                                    args=[demand_signal_a.pk])).status_code == 405
        assert DemandSignal.objects.filter(pk=demand_signal_a.pk).exists()

    def test_delete_removes_an_open_signal(self, client_a, demand_signal_a):
        from apps.scm.models import DemandSignal
        client_a.post(reverse("scm:demandsignal_delete", args=[demand_signal_a.pk]))
        assert not DemandSignal.objects.filter(pk=demand_signal_a.pk).exists()

    def test_delete_is_refused_on_an_applied_signal(self, client_a, demand_signal_a,
                                                    forecast_with_periods_a):
        from apps.scm.models import DemandSignal
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        resp = client_a.post(reverse("scm:demandsignal_delete", args=[demand_signal_a.pk]),
                             follow=True)
        assert DemandSignal.objects.filter(pk=demand_signal_a.pk).exists()
        assert any("part of the record" in str(m) for m in resp.context["messages"])


class TestDemandSignalTriageActions:
    def test_review_moves_a_new_signal_under_review(self, client_a, admin_user, demand_signal_a):
        resp = client_a.post(reverse("scm:demandsignal_review", args=[demand_signal_a.pk]))
        assert resp.status_code == 302
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "under_review"
        assert demand_signal_a.reviewed_by_id == admin_user.pk

    def test_review_is_refused_twice(self, client_a, demand_signal_a):
        client_a.post(reverse("scm:demandsignal_review", args=[demand_signal_a.pk]))
        resp = client_a.post(reverse("scm:demandsignal_review", args=[demand_signal_a.pk]),
                             follow=True)
        assert any("Only a new signal" in str(m) for m in resp.context["messages"])

    def test_apply_moves_the_forecast_periods(self, client_a, demand_signal_a,
                                              forecast_with_periods_a):
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": str(forecast_with_periods_a.pk), "impact_quantity": ""})
        assert resp.status_code == 302
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "applied"
        assert forecast_with_periods_a.periods.first().final_quantity == Decimal("130.0000")

    def test_apply_honours_an_explicit_quantity(self, client_a, demand_signal_a,
                                                forecast_with_periods_a):
        client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                      {"forecast": str(forecast_with_periods_a.pk), "impact_quantity": "-20"})
        assert forecast_with_periods_a.periods.first().final_quantity == Decimal("80.0000")

    def test_re_applying_is_refused(self, client_a, demand_signal_a, forecast_with_periods_a):
        client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                      {"forecast": str(forecast_with_periods_a.pk)})
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": str(forecast_with_periods_a.pk)}, follow=True)
        assert any("already been applied" in str(m) for m in resp.context["messages"])
        # The impact must not be double-counted into signal_adjustment_quantity.
        assert forecast_with_periods_a.periods.first().signal_adjustment_quantity == Decimal("30.0000")

    def test_apply_without_a_forecast_is_a_friendly_error(self, client_a, demand_signal_a):
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]), {},
                             follow=True)
        assert resp.status_code == 200
        assert any("Pick a forecast" in str(m) for m in resp.context["messages"])

    def test_apply_with_a_junk_forecast_id_is_a_friendly_error(self, client_a, demand_signal_a):
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": "not-a-pk"}, follow=True)
        assert resp.status_code == 200
        assert any("Pick a forecast" in str(m) for m in resp.context["messages"])

    def test_apply_reports_a_forecast_with_no_overlapping_periods(self, client_a, tenant_a,
                                                                   item_a, demand_signal_a):
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months
        far = DemandForecast.objects.create(
            tenant=tenant_a, name="Next year", item=item_a, status="statistical",
            horizon_start=add_months(demand_signal_a.effective_from, 12),
            horizon_end=add_months(demand_signal_a.effective_from, 15) - datetime.timedelta(days=1))
        far.generate_periods()
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": str(far.pk)}, follow=True)
        assert any("no periods inside" in str(m) for m in resp.context["messages"])
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "new"

    def test_dismiss_closes_the_signal_and_appends_the_note(self, client_a, demand_signal_a):
        demand_signal_a.notes = "Observer note."
        demand_signal_a.save(update_fields=["notes"])
        client_a.post(reverse("scm:demandsignal_dismiss", args=[demand_signal_a.pk]),
                      {"notes": "Known one-off."})
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "dismissed"
        assert "Observer note." in demand_signal_a.notes
        assert "Known one-off." in demand_signal_a.notes

    def test_dismiss_is_refused_after_apply(self, client_a, demand_signal_a,
                                            forecast_with_periods_a):
        demand_signal_a.apply_to_forecast(forecast_with_periods_a)
        resp = client_a.post(reverse("scm:demandsignal_dismiss", args=[demand_signal_a.pk]),
                             follow=True)
        assert any("already been applied" in str(m) for m in resp.context["messages"])

    def test_detect_runs_the_internal_detector(self, client_a, tenant_a, approved_forecast_a):
        from apps.scm.models import DemandSignal
        resp = client_a.post(reverse("scm:demandsignal_detect"), follow=True)
        assert resp.status_code == 200
        assert DemandSignal.objects.filter(tenant=tenant_a, source="internal_orders").count() == 1

    def test_detect_reports_nothing_found_rather_than_failing(self, client_a, tenant_a):
        resp = client_a.post(reverse("scm:demandsignal_detect"), follow=True)
        assert resp.status_code == 200
        assert any("No order-pattern deviations" in str(m) for m in resp.context["messages"])

    def test_detect_also_expires_stale_open_signals(self, client_a, tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        stale = DemandSignal.objects.create(
            tenant=tenant_a, item=item_a, observed_at=timezone.now(),
            effective_to=timezone.localdate() - datetime.timedelta(days=1))
        client_a.post(reverse("scm:demandsignal_detect"))
        stale.refresh_from_db()
        assert stale.status == "expired"

    def test_the_triage_actions_are_post_only(self, client_a, demand_signal_a):
        for name in ("demandsignal_review", "demandsignal_apply", "demandsignal_dismiss"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[demand_signal_a.pk])).status_code == 405, name
        assert client_a.get(reverse("scm:demandsignal_detect")).status_code == 405


# ================================================================ ForecastAdjustment CRUD + review
class TestForecastAdjustmentCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, forecast_adjustment_a):
        resp = client_a.get(reverse("scm:forecastadjustment_list"))
        assert resp.status_code == 200
        assert forecast_adjustment_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, forecast_adjustment_a,
                                             forecast_adjustment_b):
        resp = client_a.get(reverse("scm:forecastadjustment_list"))
        assert forecast_adjustment_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, forecast_adjustment_a):
        resp = client_a.get(reverse("scm:forecastadjustment_list"))
        assert "scm/demandplanning/forecastadjustment/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "status_choices", "function_choices",
                    "reason_choices", "type_choices", "forecasts", "proposed_count"):
            assert key in resp.context, key
        assert resp.context["proposed_count"] == 1

    def test_list_filter_by_status_is_the_review_queue(self, client_a, tenant_a,
                                                       forecast_adjustment_a):
        from apps.scm.models import ForecastAdjustment
        ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).update(status="accepted")
        resp = client_a.get(reverse("scm:forecastadjustment_list"), {"status": "proposed"})
        assert forecast_adjustment_a not in resp.context["object_list"]

    def test_list_search_by_rationale(self, client_a, forecast_adjustment_a):
        resp = client_a.get(reverse("scm:forecastadjustment_list"), {"q": "Spring campaign"})
        assert forecast_adjustment_a in resp.context["object_list"]

    def test_create_stamps_the_submitter_from_the_session(self, client_a, admin_user, tenant_a,
                                                          forecast_with_periods_a):
        from apps.scm.models import ForecastAdjustment
        resp = client_a.post(reverse("scm:forecastadjustment_create"),
                             _adjustment_payload(forecast_with_periods_a))
        assert resp.status_code == 302
        adjustment = ForecastAdjustment.objects.get(rationale="Spring campaign.")
        assert adjustment.tenant_id == tenant_a.pk
        assert adjustment.submitted_by_id == admin_user.pk
        assert adjustment.status == "proposed"

    def test_create_ignores_a_submitter_and_status_posted_in_the_body(self, client_a, admin_user,
                                                                      admin_b,
                                                                      forecast_with_periods_a):
        from apps.scm.models import ForecastAdjustment
        client_a.post(reverse("scm:forecastadjustment_create"),
                      _adjustment_payload(forecast_with_periods_a, submitted_by=str(admin_b.pk),
                                          status="accepted", resolved_quantity="9999"))
        adjustment = ForecastAdjustment.objects.get(rationale="Spring campaign.")
        assert adjustment.submitted_by_id == admin_user.pk
        assert adjustment.status == "proposed"
        # Derived in save() from the live base, never taken from the POST: the payload names no
        # period, so "absolute 140" is measured against the whole 300-unit horizon.
        assert adjustment.resolved_quantity == Decimal("-160.0000")

    def test_create_prefills_from_a_forecast_query_param(self, client_a, forecast_with_periods_a):
        resp = client_a.get(reverse("scm:forecastadjustment_create"),
                            {"forecast": str(forecast_with_periods_a.pk)})
        assert resp.status_code == 200
        periods = list(resp.context["form"].fields["period"].queryset)
        assert set(periods) == set(forecast_with_periods_a.periods.all())

    def test_a_junk_forecast_query_param_is_ignored(self, client_a):
        resp = client_a.get(reverse("scm:forecastadjustment_create"), {"forecast": "abc"})
        assert resp.status_code == 200
        assert list(resp.context["form"].fields["period"].queryset) == []

    def test_another_tenants_forecast_query_param_is_ignored(self, client_a,
                                                             forecast_with_periods_b):
        resp = client_a.get(reverse("scm:forecastadjustment_create"),
                            {"forecast": str(forecast_with_periods_b.pk)})
        assert resp.status_code == 200
        assert list(resp.context["form"].fields["period"].queryset) == []

    def test_detail_returns_200_with_the_resolved_base(self, client_a, forecast_adjustment_a):
        resp = client_a.get(reverse("scm:forecastadjustment_detail",
                                    args=[forecast_adjustment_a.pk]))
        assert resp.status_code == 200
        assert "scm/demandplanning/forecastadjustment/detail.html" in [t.name for t in resp.templates]
        assert resp.context["base_quantity"] == Decimal("100.0000")
        assert "review_form" in resp.context

    def test_edit_updates_a_proposal(self, client_a, forecast_adjustment_a,
                                     forecast_with_periods_a):
        resp = client_a.post(reverse("scm:forecastadjustment_edit",
                                     args=[forecast_adjustment_a.pk]),
                             _adjustment_payload(forecast_with_periods_a,
                                                 rationale="Revised rationale."))
        assert resp.status_code == 302
        forecast_adjustment_a.refresh_from_db()
        assert forecast_adjustment_a.rationale == "Revised rationale."

    def test_edit_is_refused_once_reviewed(self, client_a, forecast_adjustment_a):
        from apps.scm.models import ForecastAdjustment
        ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).update(status="accepted")
        resp = client_a.get(reverse("scm:forecastadjustment_edit",
                                    args=[forecast_adjustment_a.pk]), follow=True)
        assert any("consensus record" in str(m) for m in resp.context["messages"])

    def test_delete_is_post_only(self, client_a, forecast_adjustment_a):
        from apps.scm.models import ForecastAdjustment
        assert client_a.get(reverse("scm:forecastadjustment_delete",
                                    args=[forecast_adjustment_a.pk])).status_code == 405
        assert ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).exists()

    def test_delete_removes_an_unreviewed_proposal(self, client_a, forecast_adjustment_a):
        from apps.scm.models import ForecastAdjustment
        client_a.post(reverse("scm:forecastadjustment_delete", args=[forecast_adjustment_a.pk]))
        assert not ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).exists()

    def test_delete_is_refused_on_a_reviewed_adjustment(self, client_a, forecast_adjustment_a):
        from apps.scm.models import ForecastAdjustment
        ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).update(status="accepted")
        resp = client_a.post(reverse("scm:forecastadjustment_delete",
                                     args=[forecast_adjustment_a.pk]), follow=True)
        assert ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).exists()
        assert any("reversing adjustment" in str(m) for m in resp.context["messages"])


class TestForecastAdjustmentReview:
    def test_accept_rolls_the_delta_into_the_consensus_column(self, client_a, admin_user,
                                                              forecast_adjustment_a,
                                                              forecast_period_a):
        resp = client_a.post(reverse("scm:forecastadjustment_accept",
                                     args=[forecast_adjustment_a.pk]),
                             {"review_note": "Agreed with sales."})
        assert resp.status_code == 302
        forecast_adjustment_a.refresh_from_db()
        forecast_period_a.refresh_from_db()
        assert forecast_adjustment_a.status == "accepted"
        assert forecast_adjustment_a.reviewed_by_id == admin_user.pk
        assert forecast_adjustment_a.review_note == "Agreed with sales."
        assert forecast_period_a.consensus_quantity == Decimal("40.0000")
        assert forecast_period_a.final_quantity == Decimal("140.0000")

    def test_a_second_accept_is_refused(self, client_a, forecast_adjustment_a,
                                        forecast_period_a):
        client_a.post(reverse("scm:forecastadjustment_accept", args=[forecast_adjustment_a.pk]))
        resp = client_a.post(reverse("scm:forecastadjustment_accept",
                                     args=[forecast_adjustment_a.pk]), follow=True)
        assert any("already been reviewed" in str(m) for m in resp.context["messages"])
        forecast_period_a.refresh_from_db()
        assert forecast_period_a.final_quantity == Decimal("140.0000")  # not double-counted

    def test_reject_after_accept_is_refused_so_the_rollup_stays_honest(self, client_a,
                                                                       forecast_adjustment_a):
        client_a.post(reverse("scm:forecastadjustment_accept", args=[forecast_adjustment_a.pk]))
        client_a.post(reverse("scm:forecastadjustment_reject", args=[forecast_adjustment_a.pk]))
        forecast_adjustment_a.refresh_from_db()
        assert forecast_adjustment_a.status == "accepted"

    def test_reject_leaves_the_plan_where_it_was(self, client_a, forecast_adjustment_a,
                                                 forecast_period_a):
        client_a.post(reverse("scm:forecastadjustment_reject", args=[forecast_adjustment_a.pk]),
                      {"review_note": "Not supported by the pipeline."})
        forecast_adjustment_a.refresh_from_db()
        forecast_period_a.refresh_from_db()
        assert forecast_adjustment_a.status == "rejected"
        assert forecast_period_a.final_quantity == Decimal("100.0000")

    def test_accepting_against_an_archived_forecast_is_refused(self, client_a,
                                                               forecast_adjustment_a,
                                                               forecast_with_periods_a):
        from apps.scm.models import DemandForecast
        DemandForecast.objects.filter(pk=forecast_with_periods_a.pk).update(status="archived")
        resp = client_a.post(reverse("scm:forecastadjustment_accept",
                                     args=[forecast_adjustment_a.pk]), follow=True)
        assert any("no longer open to consensus" in str(m) for m in resp.context["messages"])
        forecast_adjustment_a.refresh_from_db()
        assert forecast_adjustment_a.status == "proposed"

    def test_accepting_against_a_draft_forecast_is_refused(self, client_a, forecast_adjustment_a,
                                                           forecast_with_periods_a):
        from apps.scm.models import DemandForecast
        DemandForecast.objects.filter(pk=forecast_with_periods_a.pk).update(status="draft")
        resp = client_a.post(reverse("scm:forecastadjustment_accept",
                                     args=[forecast_adjustment_a.pk]), follow=True)
        assert any("still a draft" in str(m) for m in resp.context["messages"])
        forecast_adjustment_a.refresh_from_db()
        assert forecast_adjustment_a.status == "proposed"

    def test_the_review_actions_are_post_only(self, client_a, forecast_adjustment_a):
        for name in ("forecastadjustment_accept", "forecastadjustment_reject"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[forecast_adjustment_a.pk])).status_code == 405, name


# ================================================================ Safety-stock + accuracy reports
class TestSafetyStockReport:
    def test_report_returns_200_with_the_documented_context(self, client_a,
                                                            reorder_rule_service_level_a):
        resp = client_a.get(reverse("scm:safety_stock_report"))
        assert resp.status_code == 200
        assert "scm/demandplanning/safety_stock_report.html" in [t.name for t in resp.templates]
        for key in ("rows", "page_obj", "total_rules", "method_choices", "items", "locations",
                    "q", "uncalculated"):
            assert key in resp.context, key
        assert resp.context["total_rules"] == 1
        assert resp.context["uncalculated"] == 1

    def test_report_only_lists_active_rules(self, client_a, reorder_rule_a):
        reorder_rule_a.is_active = False
        reorder_rule_a.save(update_fields=["is_active"])
        resp = client_a.get(reverse("scm:safety_stock_report"))
        assert resp.context["total_rules"] == 0

    def test_report_never_lists_another_tenants_rules(self, client_a, reorder_rule_a,
                                                      reorder_rule_b):
        resp = client_a.get(reverse("scm:safety_stock_report"))
        assert [row["rule"] for row in resp.context["rows"]] == [reorder_rule_a]

    def test_report_filters_by_method(self, client_a, reorder_rule_a,
                                      reorder_rule_service_level_a):
        resp = client_a.get(reverse("scm:safety_stock_report"),
                            {"safety_stock_method": "service_level"})
        assert [row["rule"] for row in resp.context["rows"]] == [reorder_rule_service_level_a]

    def test_report_search_matches_the_item_sku(self, client_a, reorder_rule_a):
        found = client_a.get(reverse("scm:safety_stock_report"), {"q": "WIDGET-1"})
        missed = client_a.get(reverse("scm:safety_stock_report"), {"q": "nothing-here"})
        assert found.context["total_rules"] == 1
        assert missed.context["total_rules"] == 0

    def test_recalculate_writes_only_the_computed_columns(self, client_a,
                                                          reorder_rule_service_level_a,
                                                          demand_history_a):
        resp = client_a.post(reverse("scm:safety_stock_recalculate"))
        assert resp.status_code == 302
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_service_level_a.last_calculated_at is not None
        assert reorder_rule_service_level_a.computed_safety_stock > Decimal("0")
        assert reorder_rule_service_level_a.safety_stock == Decimal("5.00")   # untouched
        assert reorder_rule_service_level_a.reorder_point == Decimal("10.00")  # untouched

    def test_recalculate_reports_an_empty_rule_set(self, client_a, tenant_a):
        resp = client_a.post(reverse("scm:safety_stock_recalculate"), follow=True)
        assert any("No active reorder rules" in str(m) for m in resp.context["messages"])

    def test_recalculate_carries_the_filters_into_the_redirect(self, client_a,
                                                               reorder_rule_service_level_a):
        resp = client_a.post(reverse("scm:safety_stock_recalculate"),
                             {"safety_stock_method": "service_level", "q": "WIDGET"})
        assert "safety_stock_method=service_level" in resp["Location"]
        assert "csrf" not in resp["Location"].lower()

    def test_recalculate_only_touches_the_filtered_rules(self, client_a, reorder_rule_a,
                                                         reorder_rule_service_level_a):
        client_a.post(reverse("scm:safety_stock_recalculate"),
                      {"safety_stock_method": "service_level"})
        reorder_rule_a.refresh_from_db()
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_a.last_calculated_at is None
        assert reorder_rule_service_level_a.last_calculated_at is not None

    def test_recalculate_ranks_abc_over_every_active_rule_not_just_the_filtered_ones(
        self, client_a, tenant_a, location_a, customer_a, reorder_rule_a,
    ):
        """A Pareto class computed against a one-item filter would call that item 'A' by definition."""
        from apps.scm.models import Item, ReorderRule, SalesOrder, SalesOrderLine
        big = Item.objects.create(tenant=tenant_a, sku="BIG", name="Big earner")
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                          order_date=datetime.date(2026, 1, 5), status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=big, quantity_ordered=Decimal("1"),
                                      unit_price=Decimal("100000"))
        ReorderRule.objects.create(tenant=tenant_a, item=big, location=location_a)
        client_a.post(reverse("scm:safety_stock_recalculate"), {"q": "WIDGET-1"})
        reorder_rule_a.refresh_from_db()
        assert reorder_rule_a.abc_class == "C"  # ranked against BIG, not against itself alone

    def test_recalculate_is_post_only(self, client_a):
        assert client_a.get(reverse("scm:safety_stock_recalculate")).status_code == 405

    def test_apply_promotes_the_calculated_policy(self, client_a, reorder_rule_service_level_a,
                                                  demand_history_a):
        client_a.post(reverse("scm:safety_stock_recalculate"))
        reorder_rule_service_level_a.refresh_from_db()
        computed = reorder_rule_service_level_a.computed_safety_stock
        resp = client_a.post(reverse("scm:safety_stock_apply",
                                     args=[reorder_rule_service_level_a.pk]))
        assert resp.status_code == 302
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_service_level_a.safety_stock == computed

    def test_apply_is_refused_before_a_recalculation(self, client_a,
                                                     reorder_rule_service_level_a):
        resp = client_a.post(reverse("scm:safety_stock_apply",
                                     args=[reorder_rule_service_level_a.pk]), follow=True)
        assert any("Recalculate this rule" in str(m) for m in resp.context["messages"])
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_service_level_a.safety_stock == Decimal("5.00")

    def test_apply_is_post_only(self, client_a, reorder_rule_a):
        assert client_a.get(reverse("scm:safety_stock_apply",
                                    args=[reorder_rule_a.pk])).status_code == 405


class TestForecastAccuracyReport:
    def test_report_returns_200_with_the_documented_context(self, client_a,
                                                            forecast_with_periods_a):
        resp = client_a.get(reverse("scm:forecast_accuracy_report"))
        assert resp.status_code == 200
        assert "scm/demandplanning/forecast_accuracy_report.html" in [t.name for t in resp.templates]
        for key in ("rows", "scored", "exceptions", "bias_threshold", "signal_threshold"):
            assert key in resp.context, key

    def test_draft_forecasts_are_excluded(self, client_a, demand_forecast_a):
        resp = client_a.get(reverse("scm:forecast_accuracy_report"))
        assert resp.context["rows"] == []

    def test_another_tenants_forecast_never_appears(self, client_a, forecast_with_periods_a,
                                                    forecast_with_periods_b):
        resp = client_a.get(reverse("scm:forecast_accuracy_report"))
        assert [row["forecast"] for row in resp.context["rows"]] == [forecast_with_periods_a]

    def test_an_elapsed_plan_that_ran_high_is_flagged_as_an_exception(self, client_a, tenant_a,
                                                                       item_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast, SalesOrder, SalesOrderLine
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        start = add_months(this_month, -3)
        forecast = DemandForecast.objects.create(
            tenant=tenant_a, name="Over-forecast", item=item_a, status="approved",
            horizon_start=start, horizon_end=this_month - datetime.timedelta(days=1))
        forecast.generate_periods()
        forecast.periods.update(baseline_quantity=Decimal("100"), final_quantity=Decimal("100"))
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a, order_date=start,
                                          status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_a,
                                      quantity_ordered=Decimal("10"), unit_price=Decimal("1"))
        resp = client_a.get(reverse("scm:forecast_accuracy_report"))
        row = next(r for r in resp.context["rows"] if r["forecast"].pk == forecast.pk)
        assert row["metrics"]["points"] == 3
        assert row["is_exception"] is True
        assert resp.context["exceptions"] == 1

    def test_a_customer_scoped_forecast_is_graded_on_its_own_channel(self, client_a, tenant_a,
                                                                      item_a, customer_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        start = add_months(this_month, -3)
        forecast = DemandForecast.objects.create(
            tenant=tenant_a, name="Channel plan", item=item_a, customer=customer_a,
            status="approved", horizon_start=start,
            horizon_end=this_month - datetime.timedelta(days=1))
        forecast.generate_periods()
        resp = client_a.get(reverse("scm:forecast_accuracy_report"))
        assert resp.status_code == 200
        assert any(r["forecast"].pk == forecast.pk for r in resp.context["rows"])


# ================================================================================================
# Negative-input hardening (L11 junk FK filters / L9 pagination) — 200, never a 500.
# ================================================================================================
class TestDemandPlanningNegativeInputHardening:
    LIST_ROUTES = ("scm:seasonalityprofile_list", "scm:demandforecast_list",
                   "scm:demandsignal_list", "scm:forecastadjustment_list")

    def test_every_list_survives_a_junk_item_filter(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"item": "abc"}).status_code == 200, name

    def test_every_list_survives_a_junk_status_filter(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"status": "nonsense"}).status_code == 200, name

    def test_every_list_survives_a_page_past_the_end(self, client_a, demand_forecast_a,
                                                     demand_signal_a, seasonality_profile_a,
                                                     forecast_adjustment_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"page": "999"}).status_code == 200, name

    def test_every_list_survives_a_non_numeric_page(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"page": "abc"}).status_code == 200, name

    def test_forecast_list_survives_a_junk_location_filter(self, client_a):
        assert client_a.get(reverse("scm:demandforecast_list"),
                            {"location": "-1"}).status_code == 200

    def test_seasonality_list_survives_a_junk_is_active_filter(self, client_a):
        assert client_a.get(reverse("scm:seasonalityprofile_list"),
                            {"is_active": "abc"}).status_code == 200

    def test_seasonality_list_survives_a_junk_category_filter(self, client_a):
        assert client_a.get(reverse("scm:seasonalityprofile_list"),
                            {"category": "not-a-pk"}).status_code == 200

    def test_adjustment_list_survives_a_junk_forecast_filter(self, client_a):
        assert client_a.get(reverse("scm:forecastadjustment_list"),
                            {"forecast": "abc"}).status_code == 200

    def test_forecast_list_page_2_returns_200_when_rows_exceed_the_page_size(self, client_a,
                                                                             tenant_a, item_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        for i in range(20):
            DemandForecast.objects.create(
                tenant=tenant_a, name=f"Plan {i}", item=item_a, horizon_start=start,
                horizon_end=add_months(start, 3) - datetime.timedelta(days=1))
        resp = client_a.get(reverse("scm:demandforecast_list"), {"page": "2"})
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) == 5

    def test_signal_list_page_2_returns_200_when_rows_exceed_the_page_size(self, client_a,
                                                                           tenant_a):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        for _ in range(20):
            DemandSignal.objects.create(tenant=tenant_a, observed_at=timezone.now())
        resp = client_a.get(reverse("scm:demandsignal_list"), {"page": "2"})
        assert resp.status_code == 200

    def test_safety_stock_report_survives_junk_filters(self, client_a, reorder_rule_a):
        for params in ({"item": "abc"}, {"location": "-1"}, {"safety_stock_method": "nonsense"},
                       {"page": "999"}, {"page": "abc"}):
            assert client_a.get(reverse("scm:safety_stock_report"),
                                params).status_code == 200, params

    def test_safety_stock_report_page_2_returns_200_beyond_the_page_size(self, client_a, tenant_a,
                                                                         location_a):
        from apps.scm.models import Item, ReorderRule
        for i in range(35):
            item = Item.objects.create(tenant=tenant_a, sku=f"BULK-{i}", name=f"Bulk {i}")
            ReorderRule.objects.create(tenant=tenant_a, item=item, location=location_a)
        resp = client_a.get(reverse("scm:safety_stock_report"), {"page": "2"})
        assert resp.status_code == 200
        assert resp.context["page_obj"].number == 2

    def test_safety_stock_recalculate_survives_junk_post_filters(self, client_a,
                                                                  reorder_rule_a):
        resp = client_a.post(reverse("scm:safety_stock_recalculate"),
                             {"item": "abc", "location": "NaN", "safety_stock_method": "junk"})
        assert resp.status_code == 302

    def test_the_apply_signal_form_rejects_nan_and_infinity_quantities(self, client_a,
                                                                        demand_signal_a,
                                                                        forecast_with_periods_a):
        for junk in ("NaN", "Infinity", "-Infinity", "not-a-number", "1e400"):
            resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                                 {"forecast": str(forecast_with_periods_a.pk),
                                  "impact_quantity": junk}, follow=True)
            assert resp.status_code == 200, junk
            assert any("Pick a forecast" in str(m) for m in resp.context["messages"]), junk
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "new"  # nothing was applied

    def test_the_apply_signal_form_rejects_an_over_max_digits_quantity(self, client_a,
                                                                        demand_signal_a,
                                                                        forecast_with_periods_a):
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": str(forecast_with_periods_a.pk),
                              "impact_quantity": "9" * 20}, follow=True)
        assert resp.status_code == 200
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "new"

    def test_a_negative_apply_quantity_is_accepted_as_a_signed_override(self, client_a,
                                                                         demand_signal_a,
                                                                         forecast_with_periods_a):
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": str(forecast_with_periods_a.pk),
                              "impact_quantity": "-10"})
        assert resp.status_code == 302
        assert forecast_with_periods_a.periods.first().final_quantity == Decimal("90.0000")

    def test_the_forecast_form_rejects_junk_decimals_without_500ing(self, client_a, tenant_a,
                                                                     item_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        end = add_months(start, 3) - datetime.timedelta(days=1)
        for junk in ("NaN", "Infinity", "abc", "9" * 20):
            resp = client_a.post(reverse("scm:demandforecast_create"),
                                 _forecast_payload(item_a, start, end, method_parameter=junk))
            assert resp.status_code == 200, junk
        assert not DemandForecast.objects.filter(tenant=tenant_a).exists()

    def test_the_forecast_form_rejects_a_negative_reference_scale(self, client_a, tenant_a,
                                                                   item_a):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        resp = client_a.post(
            reverse("scm:demandforecast_create"),
            _forecast_payload(item_a, start, add_months(start, 3) - datetime.timedelta(days=1),
                              reference_scale_pct="-5"))
        assert resp.status_code == 200
        assert not DemandForecast.objects.filter(tenant=tenant_a).exists()

    def test_the_adjustment_form_rejects_junk_quantities(self, client_a, tenant_a,
                                                         forecast_with_periods_a):
        from apps.scm.models import ForecastAdjustment
        for junk in ("NaN", "Infinity", "abc", "9" * 20):
            resp = client_a.post(reverse("scm:forecastadjustment_create"),
                                 _adjustment_payload(forecast_with_periods_a,
                                                     proposed_quantity=junk))
            assert resp.status_code == 200, junk
        assert not ForecastAdjustment.objects.filter(tenant=tenant_a).exists()

    def test_the_signal_form_rejects_junk_impact_values(self, client_a, tenant_a):
        from apps.scm.models import DemandSignal
        for junk in ("NaN", "Infinity", "abc", "9" * 20):
            resp = client_a.post(reverse("scm:demandsignal_create"),
                                 _signal_payload(source_reference="junk", impact_quantity=junk))
            assert resp.status_code == 200, junk
        assert not DemandSignal.objects.filter(tenant=tenant_a).exists()

    def test_the_seasonality_index_formset_rejects_a_junk_factor(self, client_a, tenant_a):
        from apps.scm.models import SeasonalityProfile
        data = _profile_payload(**formset_data("indices", [
            {"id": "", "period_number": "1", "period_label": "", "index_factor": "NaN"},
        ]))
        resp = client_a.post(reverse("scm:seasonalityprofile_create"), data)
        assert resp.status_code == 200
        assert not SeasonalityProfile.objects.filter(tenant=tenant_a).exists()


# ================================================================================================
# Query-count regression guards (locks in the batching the performance review added)
# ================================================================================================
class TestDemandPlanningQueryCounts:
    def test_seasonality_list_has_no_n_plus_one(self, client_a, tenant_a, item_a, category_a,
                                                location_a, django_assert_max_num_queries):
        from apps.scm.models import SeasonalityProfile
        for i in range(8):
            SeasonalityProfile.objects.create(tenant=tenant_a, name=f"Curve {i}", scope="item",
                                              item=item_a, category=category_a,
                                              location=location_a)
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:seasonalityprofile_list")).status_code == 200

    def test_forecast_list_has_no_n_plus_one(self, client_a, tenant_a, item_a, location_a,
                                             customer_a, seasonality_profile_a,
                                             django_assert_max_num_queries):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        for i in range(8):
            DemandForecast.objects.create(
                tenant=tenant_a, name=f"Plan {i}", item=item_a, location=location_a,
                customer=customer_a, seasonality_profile=seasonality_profile_a,
                horizon_start=start,
                horizon_end=add_months(start, 3) - datetime.timedelta(days=1))
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:demandforecast_list")).status_code == 200

    def test_signal_list_has_no_n_plus_one(self, client_a, tenant_a, item_a, category_a,
                                           location_a, customer_a,
                                           django_assert_max_num_queries):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        for _ in range(8):
            DemandSignal.objects.create(tenant=tenant_a, item=item_a, category=category_a,
                                        location=location_a, customer=customer_a,
                                        observed_at=timezone.now())
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:demandsignal_list")).status_code == 200

    def test_adjustment_list_has_no_n_plus_one(self, client_a, tenant_a, org_unit_a, admin_user,
                                               forecast_with_periods_a, forecast_period_a,
                                               django_assert_max_num_queries):
        from apps.scm.models import ForecastAdjustment
        for _ in range(8):
            ForecastAdjustment.objects.create(
                tenant=tenant_a, forecast=forecast_with_periods_a, period=forecast_period_a,
                submitted_by=admin_user, org_unit=org_unit_a, rationale="bulk")
        with django_assert_max_num_queries(16):
            assert client_a.get(reverse("scm:forecastadjustment_list")).status_code == 200

    def test_item_detail_stays_flat_with_the_4_7_forecast_panel(self, client_a, tenant_a, item_a,
                                                                location_a,
                                                                django_assert_max_num_queries):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        for i in range(6):
            DemandForecast.objects.create(
                tenant=tenant_a, name=f"Item plan {i}", item=item_a, location=location_a,
                horizon_start=start,
                horizon_end=add_months(start, 3) - datetime.timedelta(days=1))
        with django_assert_max_num_queries(20):
            assert client_a.get(reverse("scm:item_detail", args=[item_a.pk])).status_code == 200

    def test_safety_stock_report_stays_flat_as_rules_grow(self, client_a, tenant_a, location_a,
                                                          django_assert_max_num_queries):
        from apps.scm.models import Item, ReorderRule
        for i in range(10):
            item = Item.objects.create(tenant=tenant_a, sku=f"RPT-{i}", name=f"Reported {i}")
            ReorderRule.objects.create(tenant=tenant_a, item=item, location=location_a)
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:safety_stock_report")).status_code == 200

    def test_safety_stock_recalculate_stays_flat_with_ten_profiled_rules(
        self, client_a, tenant_a, item_a, location_a, customer_a, demand_history_a,
        django_assert_max_num_queries,
    ):
        """10 rules, 5 of them sized from a forecast's error, all sharing 2 forecasts and a profile.

        The batching that has to hold: ONE grouped history query, ONE ABC ranking query, ONE WMAPE
        pass per DISTINCT forecast (not per rule) and ONE bulk_update.
        """
        from django.utils import timezone
        from apps.scm.models import DemandForecast, Item, ReorderRule
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        profile = _flat_profile_view(tenant_a, item_a)
        forecasts = [
            DemandForecast.objects.create(
                tenant=tenant_a, name=f"Shared plan {i}", item=item_a, horizon_start=start,
                horizon_end=add_months(start, 3) - datetime.timedelta(days=1))
            for i in range(2)]
        for forecast in forecasts:
            forecast.generate_periods()
        for i in range(10):
            item = Item.objects.create(tenant=tenant_a, sku=f"CALC-{i}", name=f"Calc {i}")
            ReorderRule.objects.create(
                tenant=tenant_a, item=item, location=location_a, lead_time_days=10,
                lead_time_variability_days=Decimal("2"), seasonality_profile=profile,
                safety_stock_method="forecast_error" if i < 5 else "service_level",
                demand_forecast=forecasts[i % 2] if i < 5 else None)
        with django_assert_max_num_queries(30):
            resp = client_a.post(reverse("scm:safety_stock_recalculate"))
        assert resp.status_code == 302

    def test_demandsignal_detect_stays_flat_with_five_approved_forecasts(
        self, client_a, tenant_a, location_a, customer_a, django_assert_max_num_queries,
    ):
        from django.utils import timezone
        from apps.scm.models import DemandForecast, Item
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        for i in range(5):
            item = Item.objects.create(tenant=tenant_a, sku=f"DET-{i}", name=f"Detected {i}")
            forecast = DemandForecast.objects.create(
                tenant=tenant_a, name=f"Approved {i}", item=item, location=location_a,
                customer=customer_a, horizon_start=start,
                horizon_end=add_months(start, 3) - datetime.timedelta(days=1))
            forecast.generate_periods()
            forecast.periods.update(baseline_quantity=Decimal("100"),
                                    final_quantity=Decimal("100"))
            DemandForecast.objects.filter(pk=forecast.pk).update(status="approved")
        with django_assert_max_num_queries(40):
            resp = client_a.post(reverse("scm:demandsignal_detect"))
        assert resp.status_code == 302

    def test_seasonalityprofile_derive_stays_flat_on_a_ten_item_category(
        self, client_a, tenant_a, category_a, customer_a, category_profile_a,
        django_assert_max_num_queries,
    ):
        """A 300-SKU category must not become 300 aggregates inside one synchronous POST."""
        from django.utils import timezone
        from apps.scm.models import Item, SalesOrder, SalesOrderLine
        from apps.scm.tests._helpers import add_months, month_start
        this_month = month_start(timezone.localdate())
        for i in range(10):
            item = Item.objects.create(tenant=tenant_a, sku=f"CAT-{i}", name=f"Cat {i}",
                                       category=category_a)
            order = SalesOrder.objects.create(tenant=tenant_a, customer=customer_a,
                                              order_date=add_months(this_month, -(i % 12) - 1),
                                              status="submitted")
            SalesOrderLine.objects.create(sales_order=order, item=item,
                                          quantity_ordered=Decimal("50"), unit_price=Decimal("1"))
        with django_assert_max_num_queries(25):
            resp = client_a.post(reverse("scm:seasonalityprofile_derive",
                                         args=[category_profile_a.pk]))
        assert resp.status_code == 302

    def test_forecast_detail_derives_its_history_once(self, client_a, forecast_with_periods_a,
                                                      demand_history_a,
                                                      django_assert_max_num_queries):
        with django_assert_max_num_queries(20):
            assert client_a.get(reverse("scm:demandforecast_detail",
                                        args=[forecast_with_periods_a.pk])).status_code == 200


def _flat_profile_view(tenant, item, factor="1.2000"):
    from apps.scm.models import SeasonalityIndex, SeasonalityProfile
    profile = SeasonalityProfile.objects.create(tenant=tenant, name="View curve", scope="item",
                                                item=item)
    for month in range(1, 13):
        SeasonalityIndex.objects.create(profile=profile, period_number=month,
                                        index_factor=Decimal(factor))
    return profile


# ================================================================ Create guarded when the user has no tenant
class TestDemandPlanningCreateWithoutTenantWorkspace:
    def _orphan_client(self, suffix):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(email=f"orphan-dp{suffix}@example.com",
                                        username=f"orphan_dp{suffix}", password="x", tenant=None)
        client = Client()
        client.force_login(user)
        return client

    def test_forecast_create_redirects(self, db):
        from apps.scm.models import DemandForecast
        resp = self._orphan_client("1").get(reverse("scm:demandforecast_create"))
        assert resp.status_code == 302
        assert DemandForecast.objects.count() == 0

    def test_seasonality_create_redirects(self, db):
        from apps.scm.models import SeasonalityProfile
        resp = self._orphan_client("2").get(reverse("scm:seasonalityprofile_create"))
        assert resp.status_code == 302
        assert SeasonalityProfile.objects.count() == 0

    def test_signal_create_redirects(self, db):
        from apps.scm.models import DemandSignal
        resp = self._orphan_client("3").get(reverse("scm:demandsignal_create"))
        assert resp.status_code == 302
        assert DemandSignal.objects.count() == 0

    def test_adjustment_create_redirects(self, db):
        from apps.scm.models import ForecastAdjustment
        resp = self._orphan_client("4").get(reverse("scm:forecastadjustment_create"))
        assert resp.status_code == 302
        assert ForecastAdjustment.objects.count() == 0

    def test_signal_detect_redirects(self, db):
        from apps.scm.models import DemandSignal
        resp = self._orphan_client("5").post(reverse("scm:demandsignal_detect"))
        assert resp.status_code == 302
        assert DemandSignal.objects.count() == 0

    def test_safety_stock_recalculate_redirects(self, db):
        resp = self._orphan_client("6").post(reverse("scm:safety_stock_recalculate"))
        assert resp.status_code == 302


# ================================================================ The form PAGES themselves (GET)
class TestDemandPlanningFormPagesRender:
    def test_forecast_create_page_renders_the_form_and_empty_grid(self, client_a):
        resp = client_a.get(reverse("scm:demandforecast_create"))
        assert resp.status_code == 200
        assert "scm/demandplanning/demandforecast/form.html" in [t.name for t in resp.templates]
        assert resp.context["is_edit"] is False
        assert resp.context["obj"] is None
        assert resp.context["formset"].total_form_count() == 0  # extra=0: Generate builds the grid

    def test_forecast_edit_page_renders_the_existing_periods(self, client_a,
                                                              forecast_with_periods_a):
        resp = client_a.get(reverse("scm:demandforecast_edit",
                                    args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["obj"] == forecast_with_periods_a
        assert resp.context["formset"].total_form_count() == 3

    def test_seasonality_create_page_renders_the_index_formset(self, client_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_create"))
        assert resp.status_code == 200
        assert "scm/demandplanning/seasonalityprofile/form.html" in [t.name for t in resp.templates]
        assert resp.context["is_edit"] is False
        assert resp.context["formset"].total_form_count() == 3  # extra=3 blank index rows

    def test_seasonality_edit_page_renders_the_existing_indices(self, client_a,
                                                                seasonality_profile_a):
        resp = client_a.get(reverse("scm:seasonalityprofile_edit",
                                    args=[seasonality_profile_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["formset"].total_form_count() == 15  # 12 saved + 3 extra

    def test_signal_create_page_renders(self, client_a):
        resp = client_a.get(reverse("scm:demandsignal_create"))
        assert resp.status_code == 200
        assert "scm/demandplanning/demandsignal/form.html" in [t.name for t in resp.templates]
        assert resp.context["is_edit"] is False

    def test_signal_edit_page_renders(self, client_a, demand_signal_a):
        resp = client_a.get(reverse("scm:demandsignal_edit", args=[demand_signal_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"] == demand_signal_a

    def test_adjustment_create_page_renders(self, client_a):
        resp = client_a.get(reverse("scm:forecastadjustment_create"))
        assert resp.status_code == 200
        assert "scm/demandplanning/forecastadjustment/form.html" in [t.name for t in resp.templates]
        assert resp.context["is_edit"] is False

    def test_adjustment_edit_page_renders(self, client_a, forecast_adjustment_a):
        resp = client_a.get(reverse("scm:forecastadjustment_edit",
                                    args=[forecast_adjustment_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["obj"] == forecast_adjustment_a


# ================================================================ Report FK filters (the int guard's happy path)
class TestSafetyStockReportFkFilters:
    def test_filter_by_item_pk(self, client_a, tenant_a, location_a, reorder_rule_a, item_a):
        from apps.scm.models import Item, ReorderRule
        other = Item.objects.create(tenant=tenant_a, sku="OTHER-1", name="Other")
        ReorderRule.objects.create(tenant=tenant_a, item=other, location=location_a)
        resp = client_a.get(reverse("scm:safety_stock_report"), {"item": str(item_a.pk)})
        assert [row["rule"] for row in resp.context["rows"]] == [reorder_rule_a]

    def test_filter_by_location_pk(self, client_a, reorder_rule_a, location_a,
                                   reorder_rule_service_level_a):
        resp = client_a.get(reverse("scm:safety_stock_report"), {"location": str(location_a.pk)})
        assert [row["rule"] for row in resp.context["rows"]] == [reorder_rule_a]


# ================================================================================================
# SCM 4.8 Manufacturing
# ================================================================================================

def _wo_view_payload(item, **overrides):
    data = {
        "item": str(item.pk), "uom": "", "bom": "", "quantity_planned": "5",
        "order_policy": "make_to_stock", "sales_order": "", "work_center": "",
        "priority": "normal", "planned_start": "", "planned_end": "",
        "schedule_direction": "forward", "due_date": "", "component_location": "",
        "output_location": "", "output_lot_serial": "", "notes": "",
        **formset_data("components", []),
    }
    data.update(overrides)
    return data


def _bom_view_payload(item, lines=(), **overrides):
    data = {
        "item": str(item.pk), "name": "New recipe", "version": "1", "bom_type": "manufacture",
        "output_quantity": "1", "uom": "", "lead_time_days": "0", "default_work_center": "",
        "status": "draft", "effective_from": "", "effective_to": "", "notes": "",
        **formset_data("lines", list(lines)),
    }
    data.update(overrides)
    return data


def _bom_line_row(component, **overrides):
    row = {"id": "", "sequence": "10", "component": str(component.pk), "quantity_per": "1",
           "uom": "", "scrap_pct": "0", "issue_method": "manual", "notes": ""}
    row.update(overrides)
    return row


def _wc_view_payload(**overrides):
    data = {
        "code": "WC-NEW", "name": "New Cell", "center_type": "machine", "location": "",
        "org_unit": "", "supervisor": "", "capacity_hours_per_day": "8", "efficiency_pct": "100",
        "setup_minutes": "0", "machine_cost_per_hour": "10", "labor_cost_per_hour": "20",
        "is_active": "on", "notes": "",
    }
    data.update(overrides)
    return data


def _log_view_payload(work_order, work_center, **overrides):
    from django.utils import timezone
    started = timezone.now() - datetime.timedelta(hours=3)
    data = {
        "work_order": str(work_order.pk), "work_center": str(work_center.pk),
        "operation": "Mill", "entry_type": "labor", "operator": "",
        "started_at": started.strftime("%Y-%m-%dT%H:%M"),
        "ended_at": (started + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "quantity_completed": "0", "quantity_scrapped": "0", "downtime_reason": "", "notes": "",
    }
    data.update(overrides)
    return data


def _release(client, order):
    """Drive the real release route, so its three guards are exercised every time."""
    return client.post(reverse("scm:workorder_release", args=[order.pk]))


def _issue(client, order):
    return client.post(reverse("scm:workorder_issue_components", args=[order.pk]))


def _report(client, order, good="0", scrapped="0", backflush=True):
    data = {"quantity_good": good, "quantity_scrapped": scrapped}
    if backflush:
        data["backflush"] = "on"
    return client.post(reverse("scm:workorder_report_production", args=[order.pk]), data)


def _book_hours(order, work_center, entry_type, hours, minutes_ago=0):
    from django.utils import timezone
    from apps.scm.models import ProductionTimeLog
    started = timezone.now() - datetime.timedelta(minutes=minutes_ago or 0) \
        - datetime.timedelta(hours=hours)
    return ProductionTimeLog.objects.create(
        tenant=order.tenant, work_order=order, work_center=work_center, entry_type=entry_type,
        started_at=started, ended_at=started + datetime.timedelta(hours=hours))


def _moves(order, move_type=None):
    from apps.scm.models import StockMove
    qs = StockMove.objects.filter(tenant=order.tenant, reference=order.number)
    return qs.filter(move_type=move_type) if move_type else qs


# ================================================================ WorkCenter CRUD
class TestWorkCenterCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, work_center_a):
        resp = client_a.get(reverse("scm:workcenter_list"))
        assert resp.status_code == 200
        assert work_center_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, work_center_a, work_center_b):
        resp = client_a.get(reverse("scm:workcenter_list"))
        assert work_center_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, work_center_a):
        resp = client_a.get(reverse("scm:workcenter_list"))
        assert "scm/manufacturing/workcenter/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "type_choices", "locations"):
            assert key in resp.context, key

    def test_list_search_by_code(self, client_a, work_center_a):
        found = client_a.get(reverse("scm:workcenter_list"), {"q": "WC-CNC"})
        missed = client_a.get(reverse("scm:workcenter_list"), {"q": "no such centre"})
        assert work_center_a in found.context["object_list"]
        assert work_center_a not in missed.context["object_list"]

    def test_list_filter_by_centre_type(self, client_a, work_center_a, work_center_a2):
        resp = client_a.get(reverse("scm:workcenter_list"), {"center_type": "assembly"})
        rows = list(resp.context["object_list"])
        assert work_center_a2 in rows
        assert work_center_a not in rows

    def test_list_filter_by_location(self, client_a, work_center_a, work_center_a2, location_a):
        resp = client_a.get(reverse("scm:workcenter_list"), {"location": str(location_a.pk)})
        rows = list(resp.context["object_list"])
        assert work_center_a in rows
        assert work_center_a2 not in rows

    def test_create_saves_with_the_request_tenant(self, client_a, tenant_a):
        from apps.scm.models import WorkCenter
        resp = client_a.post(reverse("scm:workcenter_create"), _wc_view_payload())
        assert resp.status_code == 302
        centre = WorkCenter.objects.get(tenant=tenant_a, code="WC-NEW")
        assert centre.number.startswith("WC-")
        assert centre.machine_cost_per_hour == Decimal("10.0000")

    def test_edit_updates_the_row(self, client_a, work_center_a):
        resp = client_a.post(reverse("scm:workcenter_edit", args=[work_center_a.pk]),
                             _wc_view_payload(code=work_center_a.code, name="Renamed Cell"))
        assert resp.status_code == 302
        work_center_a.refresh_from_db()
        assert work_center_a.name == "Renamed Cell"

    def test_detail_renders_the_load_and_oee_chips(self, client_a, work_center_a, time_log_a):
        resp = client_a.get(reverse("scm:workcenter_detail", args=[work_center_a.pk]))
        assert resp.status_code == 200
        assert "scm/manufacturing/workcenter/detail.html" in [t.name for t in resp.templates]
        for key in ("obj", "open_orders", "can_delete", "window_days", "scheduled_hours",
                    "actual_hours", "capacity_hours", "utilization_pct", "oee"):
            assert key in resp.context, key
        assert resp.context["actual_hours"] == Decimal("1.00")
        assert resp.context["can_delete"] is False  # it has both a run and a log

    def test_delete_is_post_only_and_a_get_never_deletes(self, client_a, work_center_a2):
        from apps.scm.models import WorkCenter
        assert client_a.get(reverse("scm:workcenter_delete",
                                    args=[work_center_a2.pk])).status_code == 405
        assert WorkCenter.objects.filter(pk=work_center_a2.pk).exists()

    def test_delete_removes_an_unused_centre(self, client_a, work_center_a2):
        from apps.scm.models import WorkCenter
        resp = client_a.post(reverse("scm:workcenter_delete", args=[work_center_a2.pk]))
        assert resp.status_code == 302
        assert not WorkCenter.objects.filter(pk=work_center_a2.pk).exists()

    def test_delete_is_refused_for_a_centre_with_work_orders(self, client_a, work_center_a,
                                                             work_order_a):
        from apps.scm.models import WorkCenter
        resp = client_a.post(reverse("scm:workcenter_delete", args=[work_center_a.pk]),
                             follow=True)
        assert resp.status_code == 200
        assert any("has work orders" in str(m) for m in resp.context["messages"])
        assert WorkCenter.objects.filter(pk=work_center_a.pk).exists()

    def test_delete_is_refused_for_a_centre_with_time_logs(self, client_a, tenant_a,
                                                           work_center_a2, released_work_order_a):
        from apps.scm.models import ProductionTimeLog, WorkCenter
        from django.utils import timezone
        ProductionTimeLog.objects.create(tenant=tenant_a, work_order=released_work_order_a,
                                         work_center=work_center_a2, started_at=timezone.now())
        resp = client_a.post(reverse("scm:workcenter_delete", args=[work_center_a2.pk]),
                             follow=True)
        assert any("production time logs" in str(m) for m in resp.context["messages"])
        assert WorkCenter.objects.filter(pk=work_center_a2.pk).exists()


# ================================================================ BillOfMaterials CRUD
class TestBillOfMaterialsCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, bom_a):
        resp = client_a.get(reverse("scm:billofmaterials_list"))
        assert resp.status_code == 200
        assert bom_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, bom_a, bom_b):
        resp = client_a.get(reverse("scm:billofmaterials_list"))
        assert bom_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, bom_a):
        resp = client_a.get(reverse("scm:billofmaterials_list"))
        assert "scm/manufacturing/billofmaterials/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "status_choices", "type_choices", "items",
                    "work_centers"):
            assert key in resp.context, key

    def test_list_annotates_the_line_count_without_a_per_row_query(self, client_a, bom_a):
        resp = client_a.get(reverse("scm:billofmaterials_list"))
        row = next(r for r in resp.context["object_list"] if r.pk == bom_a.pk)
        assert row.line_count == 2

    def test_list_search_and_status_filter(self, client_a, bom_a, bom_draft_a):
        found = client_a.get(reverse("scm:billofmaterials_list"), {"q": "Widget recipe"})
        assert bom_a in found.context["object_list"]
        active = client_a.get(reverse("scm:billofmaterials_list"), {"status": "active"})
        rows = list(active.context["object_list"])
        assert bom_a in rows and bom_draft_a not in rows

    def test_create_saves_the_header_and_its_lines_in_one_go(self, client_a, tenant_a, item_a,
                                                             component_bolt_a):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_create"),
                             _bom_view_payload(item_a, [_bom_line_row(component_bolt_a,
                                                                      quantity_per="3")],
                                               version="7"))
        assert resp.status_code == 302
        bom = BillOfMaterials.objects.get(tenant=tenant_a, version="7")
        assert bom.number.startswith("BOM-")
        assert [line.quantity_per for line in bom.lines.all()] == [Decimal("3.0000")]

    def test_edit_updates_the_header(self, client_a, bom_draft_a, item_lot_a, component_bolt_a):
        line = bom_draft_a.lines.first()
        resp = client_a.post(
            reverse("scm:billofmaterials_edit", args=[bom_draft_a.pk]),
            _bom_view_payload(item_lot_a, [
                dict(_bom_line_row(component_bolt_a), id=str(line.pk), quantity_per="9"),
            ], name="Renamed recipe", status="active", **{"lines-INITIAL_FORMS": "1"}))
        assert resp.status_code == 302
        bom_draft_a.refresh_from_db()
        assert bom_draft_a.name == "Renamed recipe"
        assert bom_draft_a.lines.first().quantity_per == Decimal("9.0000")

    def test_detail_renders_the_flattened_explosion(self, client_a, bom_a):
        resp = client_a.get(reverse("scm:billofmaterials_detail", args=[bom_a.pk]))
        assert resp.status_code == 200
        assert "scm/manufacturing/billofmaterials/detail.html" in [t.name for t in resp.templates]
        for key in ("obj", "lines", "exploded", "is_multi_level", "estimated_unit_cost",
                    "is_effective_now", "work_order_count"):
            assert key in resp.context, key
        assert resp.context["estimated_unit_cost"] == Decimal("9.0000")
        assert resp.context["is_multi_level"] is False
        assert resp.context["is_effective_now"] is True

    def test_detail_flags_a_multi_level_recipe(self, client_a, tenant_a, bom_a, component_bolt_a,
                                                component_plate_a):
        from apps.scm.models import BillOfMaterials, BOMLine
        sub = BillOfMaterials.objects.create(tenant=tenant_a, item=component_bolt_a,
                                             name="Bolt recipe", version="1", status="active")
        BOMLine.objects.create(bom=sub, component=component_plate_a, quantity_per=Decimal("1"))
        resp = client_a.get(reverse("scm:billofmaterials_detail", args=[bom_a.pk]))
        assert resp.context["is_multi_level"] is True

    def test_delete_is_post_only(self, client_a, bom_draft_a):
        from apps.scm.models import BillOfMaterials
        assert client_a.get(reverse("scm:billofmaterials_delete",
                                    args=[bom_draft_a.pk])).status_code == 405
        assert BillOfMaterials.objects.filter(pk=bom_draft_a.pk).exists()

    def test_delete_removes_an_unused_recipe(self, client_a, bom_draft_a):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_delete", args=[bom_draft_a.pk]))
        assert resp.status_code == 302
        assert not BillOfMaterials.objects.filter(pk=bom_draft_a.pk).exists()

    def test_delete_is_refused_once_a_work_order_has_used_it(self, client_a, bom_a, work_order_a):
        """WorkOrder.bom is SET_NULL, so deleting would silently orphan the link on historical
        runs rather than error — the run's provenance is worth more than the tidy-up."""
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_delete", args=[bom_a.pk]), follow=True)
        assert any("mark it obsolete instead" in str(m) for m in resp.context["messages"])
        assert BillOfMaterials.objects.filter(pk=bom_a.pk).exists()


# ================================================================ The self-reference create bug
class TestBillOfMaterialsCreateSelfReference:
    """The formset guard compares each line's component against the PARENT's item. On create the
    view passed instance=None, so BaseInlineFormSet substituted an empty BillOfMaterials() whose
    item_id was None — and the guard silently no-opped on exactly the path it exists for."""

    def test_a_recipe_that_consumes_its_own_output_is_refused_on_CREATE(self, client_a, tenant_a,
                                                                        item_a):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_create"),
                             _bom_view_payload(item_a, [_bom_line_row(item_a)], version="9"))
        assert resp.status_code == 200  # re-rendered, not saved
        assert "cannot consume itself" in resp.content.decode()
        assert not BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()

    def test_the_same_guard_holds_on_EDIT(self, client_a, bom_draft_a, item_lot_a):
        resp = client_a.post(reverse("scm:billofmaterials_edit", args=[bom_draft_a.pk]),
                             _bom_view_payload(item_lot_a, [_bom_line_row(item_lot_a)]))
        assert resp.status_code == 200
        assert "cannot consume itself" in resp.content.decode()

    def test_a_legitimate_component_still_saves_on_create(self, client_a, tenant_a, item_a,
                                                          component_plate_a):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_create"),
                             _bom_view_payload(item_a, [_bom_line_row(component_plate_a)],
                                               version="9"))
        assert resp.status_code == 302
        assert BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()


# ================================================================ WorkOrder CRUD
class TestWorkOrderCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, work_order_a):
        resp = client_a.get(reverse("scm:workorder_list"))
        assert resp.status_code == 200
        assert work_order_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, work_order_a, work_order_b):
        resp = client_a.get(reverse("scm:workorder_list"))
        assert work_order_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, work_order_a):
        resp = client_a.get(reverse("scm:workorder_list"))
        assert "scm/manufacturing/workorder/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "status_choices", "priority_choices",
                    "policy_choices", "items", "work_centers"):
            assert key in resp.context, key

    def test_list_search_by_number(self, client_a, work_order_a):
        found = client_a.get(reverse("scm:workorder_list"), {"q": work_order_a.number})
        missed = client_a.get(reverse("scm:workorder_list"), {"q": "WO-99999"})
        assert work_order_a in found.context["object_list"]
        assert work_order_a not in missed.context["object_list"]

    def test_list_filter_by_status_and_item(self, client_a, work_order_a, item_a):
        by_status = client_a.get(reverse("scm:workorder_list"), {"status": "draft"})
        assert work_order_a in by_status.context["object_list"]
        by_other = client_a.get(reverse("scm:workorder_list"), {"status": "closed"})
        assert work_order_a not in by_other.context["object_list"]
        by_item = client_a.get(reverse("scm:workorder_list"), {"item": str(item_a.pk)})
        assert work_order_a in by_item.context["object_list"]

    def test_create_saves_with_the_request_tenant_and_explodes_the_bom(self, client_a, tenant_a,
                                                                        item_a, bom_a,
                                                                        component_bolt_a):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_create"),
                             _wo_view_payload(item_a, bom=str(bom_a.pk), quantity_planned="4"))
        assert resp.status_code == 302
        order = WorkOrder.objects.get(tenant=tenant_a, quantity_planned=Decimal("4"))
        assert order.number.startswith("WO-")
        assert order.status == "draft"
        assert order.components.count() == 2
        bolt = order.components.get(item=component_bolt_a)
        assert bolt.quantity_required == Decimal("8.0000")

    def test_create_with_hand_entered_components_and_no_bom(self, client_a, tenant_a, item_a,
                                                            component_plate_a):
        from apps.scm.models import WorkOrder
        data = _wo_view_payload(item_a, quantity_planned="2")
        data.update(formset_data("components", [
            {"id": "", "sequence": "10", "item": str(component_plate_a.pk),
             "quantity_required": "6", "uom": "", "lot_serial": "", "issue_method": "manual",
             "unit_cost": "5", "notes": ""},
        ]))
        resp = client_a.post(reverse("scm:workorder_create"), data)
        assert resp.status_code == 302
        order = WorkOrder.objects.get(tenant=tenant_a, quantity_planned=Decimal("2"))
        assert [c.quantity_required for c in order.components.all()] == [Decimal("6.0000")]

    def test_a_mis_picked_bom_is_refused_at_the_view(self, client_a, tenant_a, bom_a,
                                                     item_lot_a):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_create"),
                             _wo_view_payload(item_lot_a, bom=str(bom_a.pk)))
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a, item=item_lot_a).exists()

    def test_edit_updates_a_draft_run(self, client_a, work_order_a, item_a):
        resp = client_a.post(reverse("scm:workorder_edit", args=[work_order_a.pk]),
                             _wo_view_payload(item_a, quantity_planned="7", priority="urgent"))
        assert resp.status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.quantity_planned == Decimal("7.0000")
        assert work_order_a.priority == "urgent"

    def test_edit_is_refused_once_the_run_is_released(self, client_a, released_work_order_a):
        resp = client_a.get(reverse("scm:workorder_edit", args=[released_work_order_a.pk]),
                            follow=True)
        assert any("can no longer be edited" in str(m) for m in resp.context["messages"])

    def test_detail_resolves_every_cost_pool_once(self, client_a, released_work_order_a,
                                                   time_log_a):
        resp = client_a.get(reverse("scm:workorder_detail", args=[released_work_order_a.pk]))
        assert resp.status_code == 200
        assert "scm/manufacturing/workorder/detail.html" in [t.name for t in resp.templates]
        for key in ("obj", "components", "shortfalls", "time_logs", "moves", "material_cost",
                    "labor_cost", "machine_cost", "wip_value", "actual_hours",
                    "duration_variance_hours", "schedule_form", "report_form"):
            assert key in resp.context, key
        assert resp.context["machine_cost"] == Decimal("10.0000")
        assert resp.context["wip_value"] == Decimal("10.0000")

    def test_delete_is_post_only_and_a_get_never_deletes(self, client_a, work_order_a):
        from apps.scm.models import WorkOrder
        assert client_a.get(reverse("scm:workorder_delete",
                                    args=[work_order_a.pk])).status_code == 405
        assert WorkOrder.objects.filter(pk=work_order_a.pk).exists()

    def test_delete_removes_a_draft_run(self, client_a, work_order_a):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_delete", args=[work_order_a.pk]))
        assert resp.status_code == 302
        assert not WorkOrder.objects.filter(pk=work_order_a.pk).exists()

    def test_delete_is_refused_once_the_run_is_live(self, client_a, released_work_order_a):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_delete", args=[released_work_order_a.pk]),
                             follow=True)
        assert any("cancel it instead" in str(m) for m in resp.context["messages"])
        assert WorkOrder.objects.filter(pk=released_work_order_a.pk).exists()


# ================================================================ Lifecycle (no stock effect)
class TestWorkOrderLifecycle:
    def test_plan_moves_a_draft_run_forward(self, client_a, work_order_a):
        assert client_a.post(reverse("scm:workorder_plan",
                                     args=[work_order_a.pk])).status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.status == "planned"

    def test_plan_is_refused_from_any_other_status(self, client_a, released_work_order_a):
        resp = client_a.post(reverse("scm:workorder_plan", args=[released_work_order_a.pk]),
                             follow=True)
        assert any("can't be planned" in str(m) for m in resp.context["messages"])
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "released"

    def test_release_stamps_the_releasing_user(self, client_a, admin_user, stocked_work_order_a):
        assert _release(client_a, stocked_work_order_a).status_code == 302
        stocked_work_order_a.refresh_from_db()
        assert stocked_work_order_a.status == "released"
        assert stocked_work_order_a.released_by_id == admin_user.pk

    def test_release_is_refused_without_components(self, client_a, work_order_a):
        resp = _release(client_a, work_order_a)
        assert resp.status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.status == "draft"

    def test_release_is_refused_without_both_locations(self, client_a, stocked_work_order_a):
        stocked_work_order_a.output_location = None
        stocked_work_order_a.save(update_fields=["output_location"])
        resp = _release(client_a, stocked_work_order_a)
        assert resp.status_code == 302
        stocked_work_order_a.refresh_from_db()
        assert stocked_work_order_a.status == "draft"

    def test_release_is_refused_from_a_completed_run(self, client_a, stocked_work_order_a):
        from apps.scm.models import WorkOrder
        WorkOrder.objects.filter(pk=stocked_work_order_a.pk).update(status="completed")
        resp = _release(client_a, stocked_work_order_a)
        assert resp.status_code == 302
        stocked_work_order_a.refresh_from_db()
        assert stocked_work_order_a.status == "completed"

    def test_close_is_only_legal_from_completed(self, client_a, released_work_order_a):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_close", args=[released_work_order_a.pk]),
                             follow=True)
        assert any("can't be closed" in str(m) for m in resp.context["messages"])
        WorkOrder.objects.filter(pk=released_work_order_a.pk).update(status="completed")
        assert client_a.post(reverse("scm:workorder_close",
                                     args=[released_work_order_a.pk])).status_code == 302
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "closed"

    def test_cancel_works_on_a_run_that_moved_no_stock(self, client_a, released_work_order_a):
        assert client_a.post(reverse("scm:workorder_cancel",
                                     args=[released_work_order_a.pk])).status_code == 302
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "cancelled"

    def test_cancel_is_refused_once_stock_has_moved(self, client_a, released_work_order_a):
        """The components are gone from stock — cancelling would leave that cost attached to a
        document claiming nothing happened."""
        _issue(client_a, released_work_order_a)
        resp = client_a.post(reverse("scm:workorder_cancel", args=[released_work_order_a.pk]),
                             follow=True)
        assert any("posted stock movements" in str(m) for m in resp.context["messages"])
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "in_progress"

    def test_cancelling_twice_is_a_friendly_no_op(self, client_a, released_work_order_a):
        client_a.post(reverse("scm:workorder_cancel", args=[released_work_order_a.pk]))
        resp = client_a.post(reverse("scm:workorder_cancel", args=[released_work_order_a.pk]),
                             follow=True)
        assert any("already closed or cancelled" in str(m) for m in resp.context["messages"])


# ================================================================ Scheduling (date arithmetic)
class TestWorkOrderSchedule:
    def test_scheduling_forward_fills_the_window_from_the_start(self, client_a, work_order_a):
        resp = client_a.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                             {"direction": "forward", "anchor_date": "2026-05-01",
                              "lead_time_days": "4"})
        assert resp.status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.planned_start.date() == datetime.date(2026, 5, 1)
        assert work_order_a.planned_end.date() == datetime.date(2026, 5, 5)
        assert work_order_a.schedule_direction == "forward"

    def test_scheduling_backward_fills_the_window_from_the_due_date(self, client_a,
                                                                    work_order_a):
        resp = client_a.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                             {"direction": "backward", "anchor_date": "2026-05-10",
                              "lead_time_days": "3"})
        assert resp.status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.planned_start.date() == datetime.date(2026, 5, 7)
        assert work_order_a.planned_end.date() == datetime.date(2026, 5, 10)

    def test_a_blank_lead_time_falls_back_to_the_boms(self, client_a, work_order_a, bom_a):
        resp = client_a.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                             {"direction": "forward", "anchor_date": "2026-05-01",
                              "lead_time_days": ""})
        assert resp.status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.planned_end.date() == datetime.date(2026, 5, 4)  # bom lead time 3

    def test_a_year_9999_anchor_does_not_500(self, client_a, work_order_a):
        resp = client_a.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                             {"direction": "forward", "anchor_date": "9999-12-31",
                              "lead_time_days": "10"}, follow=True)
        assert resp.status_code == 200
        work_order_a.refresh_from_db()
        assert work_order_a.planned_start is None

    def test_a_junk_anchor_does_not_500(self, client_a, work_order_a):
        for junk in ("not-a-date", "0001-01-01", "2026-13-45", ""):
            resp = client_a.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                                 {"direction": "forward", "anchor_date": junk}, follow=True)
            assert resp.status_code == 200, junk
        work_order_a.refresh_from_db()
        assert work_order_a.planned_start is None

    def test_scheduling_a_released_run_is_refused(self, client_a, released_work_order_a):
        resp = client_a.post(reverse("scm:workorder_schedule",
                                     args=[released_work_order_a.pk]),
                             {"direction": "forward", "anchor_date": "2026-05-01"}, follow=True)
        assert any("can be rescheduled" in str(m) for m in resp.context["messages"])
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.planned_start is None


# ================================================================ Component issue (posts stock)
class TestWorkOrderIssueComponents:
    def test_issuing_draws_one_consumption_move_per_component(self, client_a,
                                                              released_work_order_a,
                                                              component_bolt_a,
                                                              component_plate_a):
        assert _issue(client_a, released_work_order_a).status_code == 302
        moves = {m.item_id: m for m in _moves(released_work_order_a, "consumption")}
        assert set(moves) == {component_bolt_a.pk, component_plate_a.pk}
        assert moves[component_bolt_a.pk].quantity == Decimal("-10.0000")
        assert moves[component_plate_a.pk].quantity == Decimal("-5.0000")
        assert all(m.reference == released_work_order_a.number for m in moves.values())

    def test_issuing_moves_a_released_run_into_progress(self, client_a, released_work_order_a):
        _issue(client_a, released_work_order_a)
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "in_progress"
        assert released_work_order_a.actual_start is not None

    def test_a_SECOND_issue_post_posts_nothing_more(self, client_a, released_work_order_a):
        """The double-click / retry / replay guard: the status is re-read inside the transaction
        behind a row lock, and every line is already fully issued."""
        _issue(client_a, released_work_order_a)
        resp = _issue(client_a, released_work_order_a)
        assert resp.status_code == 302
        assert _moves(released_work_order_a, "consumption").count() == 2
        for component in released_work_order_a.components.all():
            assert component.quantity_issued == component.quantity_required

    def test_the_second_post_says_why_nothing_happened(self, client_a, released_work_order_a):
        _issue(client_a, released_work_order_a)
        resp = client_a.post(
            reverse("scm:workorder_issue_components", args=[released_work_order_a.pk]),
            follow=True)
        assert any("already fully issued" in str(m) for m in resp.context["messages"])

    def test_issuing_before_release_is_refused(self, client_a, stocked_work_order_a):
        resp = _issue(client_a, stocked_work_order_a)
        assert resp.status_code == 302
        assert _moves(stocked_work_order_a).count() == 0

    def test_issuing_without_a_component_location_is_refused(self, client_a,
                                                             released_work_order_a):
        from apps.scm.models import WorkOrder
        WorkOrder.objects.filter(pk=released_work_order_a.pk).update(component_location=None)
        resp = _issue(client_a, released_work_order_a)
        assert resp.status_code == 302
        assert _moves(released_work_order_a).count() == 0

    def test_insufficient_stock_is_a_message_not_a_500_and_rolls_the_whole_draw_back(
        self, client_a, released_work_order_a, component_plate_a,
    ):
        component = released_work_order_a.components.get(item=component_plate_a)
        component.quantity_required = Decimal("500")
        component.save(update_fields=["quantity_required"])
        resp = _issue(client_a, released_work_order_a)
        assert resp.status_code == 302
        assert _moves(released_work_order_a).count() == 0   # the bolt line rolled back too
        for row in released_work_order_a.components.all():
            assert row.quantity_issued == Decimal("0")

    def test_the_snapshot_cost_rolls_as_a_weighted_average_across_partial_issues(
        self, client_a, released_work_order_a, component_bolt_a, location_a,
    ):
        """Overwriting it would re-value the earlier issue at today's rate, so issued_value would
        disagree with the ledger rows it summarises."""
        from apps.scm.tests._helpers import seed_stock
        component = released_work_order_a.components.get(item=component_bolt_a)
        component.quantity_required = Decimal("4")
        component.save(update_fields=["quantity_required"])
        _issue(client_a, released_work_order_a)          # 4 @ 2.0000
        seed_stock(released_work_order_a.tenant, component_bolt_a, location_a, "100", "6.0000")
        component.refresh_from_db()
        component.quantity_required = Decimal("8")
        component.save(update_fields=["quantity_required"])
        _issue(client_a, released_work_order_a)          # 4 more, at the NEW average
        component.refresh_from_db()
        assert component.quantity_issued == Decimal("8.0000")
        assert Decimal("2.0000") < component.unit_cost < Decimal("6.0000")


# ================================================================ Report production (posts stock)
class TestWorkOrderReportProduction:
    def test_reporting_posts_one_positive_production_move(self, client_a, released_work_order_a,
                                                          item_a):
        _issue(client_a, released_work_order_a)
        assert _report(client_a, released_work_order_a, good="3").status_code == 302
        moves = list(_moves(released_work_order_a, "production"))
        assert len(moves) == 1
        assert moves[0].item_id == item_a.pk
        assert moves[0].quantity == Decimal("3.0000")
        assert moves[0].reference == released_work_order_a.number
        assert moves[0].location_id == released_work_order_a.output_location_id

    def test_the_run_completes_when_nothing_remains(self, client_a, released_work_order_a):
        _issue(client_a, released_work_order_a)
        _report(client_a, released_work_order_a, good="5")
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("5.0000")
        assert released_work_order_a.status == "completed"
        assert released_work_order_a.actual_end is not None

    def test_scrap_is_recorded_but_posts_NO_move(self, client_a, released_work_order_a):
        """Scrapped units never entered stock, so there is nothing to take out."""
        _issue(client_a, released_work_order_a)
        _report(client_a, released_work_order_a, good="0", scrapped="2")
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_scrapped == Decimal("2.0000")
        assert _moves(released_work_order_a, "production").count() == 0
        assert released_work_order_a.produced_unit_cost == Decimal("0")

    def test_reporting_beyond_the_remaining_quantity_is_REFUSED(self, client_a,
                                                                released_work_order_a):
        _issue(client_a, released_work_order_a)
        resp = _report(client_a, released_work_order_a, good="99", scrapped="0")
        assert resp.status_code == 302
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("0")
        assert _moves(released_work_order_a, "production").count() == 0

    def test_the_over_report_message_names_the_remaining_quantity(self, client_a,
                                                                  released_work_order_a):
        resp = client_a.post(
            reverse("scm:workorder_report_production", args=[released_work_order_a.pk]),
            {"quantity_good": "9", "quantity_scrapped": "0"}, follow=True)
        assert any("remaining on" in str(m) for m in resp.context["messages"])

    def test_an_over_report_leaves_NO_partial_backflush_consumption(self, client_a,
                                                                    released_work_order_a):
        """The remaining-quantity guard runs BEFORE the backflush draw, so an over-report cannot
        consume material against output it was never allowed to book."""
        released_work_order_a.components.update(issue_method="backflush")
        resp = _report(client_a, released_work_order_a, good="99")
        assert resp.status_code == 302
        assert _moves(released_work_order_a).count() == 0
        for row in released_work_order_a.components.all():
            assert row.quantity_issued == Decimal("0")

    def test_a_failing_backflush_rolls_the_WHOLE_report_back(self, client_a,
                                                             released_work_order_a,
                                                             component_plate_a):
        """The first component posts, the second finds no stock and raises — the atomic block must
        take the first one back with it rather than leaving a half-consumed run."""
        released_work_order_a.components.update(issue_method="backflush")
        plate = released_work_order_a.components.get(item=component_plate_a)
        plate.quantity_required = Decimal("500")
        plate.save(update_fields=["quantity_required"])
        resp = _report(client_a, released_work_order_a, good="2")
        assert resp.status_code == 302
        assert _moves(released_work_order_a).count() == 0
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("0")
        for row in released_work_order_a.components.all():
            assert row.quantity_issued == Decimal("0")

    def test_reporting_before_release_is_refused(self, client_a, stocked_work_order_a):
        resp = _report(client_a, stocked_work_order_a, good="1")
        assert resp.status_code == 302
        assert _moves(stocked_work_order_a).count() == 0

    def test_reporting_without_an_output_location_is_refused(self, client_a,
                                                             released_work_order_a):
        from apps.scm.models import WorkOrder
        WorkOrder.objects.filter(pk=released_work_order_a.pk).update(output_location=None)
        resp = _report(client_a, released_work_order_a, good="1")
        assert resp.status_code == 302
        assert _moves(released_work_order_a, "production").count() == 0

    def test_an_empty_report_is_refused_by_the_form(self, client_a, released_work_order_a):
        resp = client_a.post(
            reverse("scm:workorder_report_production", args=[released_work_order_a.pk]),
            {"quantity_good": "0", "quantity_scrapped": "0"}, follow=True)
        assert any("Report a good quantity" in str(m) for m in resp.context["messages"])
        assert _moves(released_work_order_a).count() == 0

    def test_junk_report_quantities_never_500(self, client_a, released_work_order_a):
        for junk in ("NaN", "Infinity", "-Infinity", "abc", "-4", "1e400", "9" * 20):
            resp = client_a.post(
                reverse("scm:workorder_report_production", args=[released_work_order_a.pk]),
                {"quantity_good": junk, "quantity_scrapped": "0"}, follow=True)
            assert resp.status_code == 200, junk
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("0")
        assert _moves(released_work_order_a).count() == 0


# ================================================================ Backflush vs manual issue
class TestWorkOrderBackflush:
    def test_a_backflush_line_is_NOT_drawn_by_the_issue_action(self, client_a,
                                                               released_work_order_a,
                                                               component_bolt_a,
                                                               component_plate_a):
        """Issuing it here would pre-consume it and make the issue-method distinction inert."""
        plate = released_work_order_a.components.get(item=component_plate_a)
        plate.issue_method = "backflush"
        plate.save(update_fields=["issue_method"])
        _issue(client_a, released_work_order_a)
        assert _moves(released_work_order_a, "consumption").count() == 1
        plate.refresh_from_db()
        assert plate.quantity_issued == Decimal("0")
        bolt = released_work_order_a.components.get(item=component_bolt_a)
        assert bolt.quantity_issued == Decimal("10.0000")

    def test_a_backflush_line_IS_consumed_in_proportion_to_the_output(self, client_a,
                                                                      released_work_order_a,
                                                                      component_plate_a):
        plate = released_work_order_a.components.get(item=component_plate_a)
        plate.issue_method = "backflush"
        plate.save(update_fields=["issue_method"])
        _issue(client_a, released_work_order_a)
        _report(client_a, released_work_order_a, good="2")   # 2 of 5 planned -> 2 of 5 plates
        plate.refresh_from_db()
        assert plate.quantity_issued == Decimal("2.0000")
        drawn = _moves(released_work_order_a, "consumption").filter(item=component_plate_a)
        assert [m.quantity for m in drawn] == [Decimal("-2.0000")]

    def test_scrap_pulls_backflush_material_too(self, client_a, released_work_order_a,
                                                component_plate_a):
        plate = released_work_order_a.components.get(item=component_plate_a)
        plate.issue_method = "backflush"
        plate.save(update_fields=["issue_method"])
        _report(client_a, released_work_order_a, good="1", scrapped="1")
        plate.refresh_from_db()
        assert plate.quantity_issued == Decimal("2.0000")  # (1 good + 1 scrapped) of 5 planned

    def test_turning_backflush_OFF_on_the_report_leaves_the_line_alone(self, client_a,
                                                                       released_work_order_a,
                                                                       component_plate_a):
        plate = released_work_order_a.components.get(item=component_plate_a)
        plate.issue_method = "backflush"
        plate.save(update_fields=["issue_method"])
        _report(client_a, released_work_order_a, good="2", backflush=False)
        plate.refresh_from_db()
        assert plate.quantity_issued == Decimal("0")

    def test_a_backflush_draw_never_exceeds_what_is_outstanding(self, client_a,
                                                                released_work_order_a,
                                                                component_plate_a):
        plate = released_work_order_a.components.get(item=component_plate_a)
        plate.issue_method = "backflush"
        plate.save(update_fields=["issue_method"])
        _report(client_a, released_work_order_a, good="5")
        plate.refresh_from_db()
        assert plate.quantity_issued == plate.quantity_required


# ================================================================ Costing end to end (the big one)
class TestWorkOrderCostingEndToEnd:
    """Release 5, issue, report 3 then 2 — the layered posting the old formula got wrong.

    Pool: 45.0000 material + 20.0000 machine (2 h) + 20.0000 labour (1 h) = 85.0000.
    The replaced formula divided the WHOLE pool by the CUMULATIVE good quantity, banking
    3 x (85/3) + 2 x (85/5) = 119.00 of stock value against 85.00 of real cost — 140 %, and a
    wip_value driven negative, which is the proof the two disagreed. The ledger is append-only, so
    an over-valued layer can never be corrected in place.
    """

    def _run(self, client, order, work_center):
        _issue(client, order)
        _book_hours(order, work_center, "machine", 2)
        _book_hours(order, work_center, "labor", 1)
        _report(client, order, good="3")
        _report(client, order, good="2")
        order.refresh_from_db()
        return order

    def _produced_value(self, order):
        return sum((m.quantity * m.unit_cost for m in _moves(order, "production")), Decimal("0"))

    def test_the_posted_stock_value_never_exceeds_the_cost_actually_incurred(
        self, client_a, released_work_order_a, work_center_a,
    ):
        order = self._run(client_a, released_work_order_a, work_center_a)
        labor, machine = order._time_costs()
        incurred = order.material_cost + labor + machine
        assert incurred == Decimal("85.0000")
        produced = self._produced_value(order)
        assert produced <= incurred
        # One 0.0001 quantum per unit posted is the irreducible rounding residual.
        assert incurred - produced <= Decimal("0.0005")

    def test_wip_lands_at_zero_once_the_run_is_complete(self, client_a, released_work_order_a,
                                                        work_center_a):
        order = self._run(client_a, released_work_order_a, work_center_a)
        assert abs(order.wip_value) <= Decimal("0.0005")
        assert order.wip_value >= Decimal("0")  # never NEGATIVE — that was the tell

    def test_the_run_finishes_with_everything_produced(self, client_a, released_work_order_a,
                                                       work_center_a):
        order = self._run(client_a, released_work_order_a, work_center_a)
        assert order.quantity_produced == Decimal("5.0000")
        assert order.quantity_remaining == Decimal("0.0000")
        assert order.status == "completed"

    def test_the_first_layer_carries_the_whole_pool_and_the_second_almost_nothing(
        self, client_a, released_work_order_a, work_center_a,
    ):
        _issue(client_a, released_work_order_a)
        _book_hours(released_work_order_a, work_center_a, "machine", 2)
        _book_hours(released_work_order_a, work_center_a, "labor", 1)
        _report(client_a, released_work_order_a, good="3")
        first = _moves(released_work_order_a, "production").order_by("id").first()
        assert first.unit_cost == Decimal("28.3333")        # 85 / 3, NOT 85 / 5
        _report(client_a, released_work_order_a, good="2")
        second = _moves(released_work_order_a, "production").order_by("id").last()
        assert second.unit_cost == Decimal("0.0000")        # the pool was already absorbed

    def test_cost_booked_BETWEEN_two_layers_lands_on_the_second_only(self, client_a,
                                                                     released_work_order_a,
                                                                     work_center_a):
        _issue(client_a, released_work_order_a)
        _book_hours(released_work_order_a, work_center_a, "machine", 2)
        _book_hours(released_work_order_a, work_center_a, "labor", 1)
        _report(client_a, released_work_order_a, good="3")
        _book_hours(released_work_order_a, work_center_a, "labor", 1)   # +20.00 after layer 1
        _report(client_a, released_work_order_a, good="2")
        second = _moves(released_work_order_a, "production").order_by("id").last()
        assert second.unit_cost == Decimal("10.0000")       # 20.0001 / 2
        released_work_order_a.refresh_from_db()
        labor, machine = released_work_order_a._time_costs()
        incurred = released_work_order_a.material_cost + labor + machine
        assert self._produced_value(released_work_order_a) <= incurred

    def test_a_scrappy_run_reports_a_higher_unit_cost_rather_than_hiding_the_loss(
        self, client_a, released_work_order_a,
    ):
        _issue(client_a, released_work_order_a)
        _report(client_a, released_work_order_a, good="4", scrapped="1")
        released_work_order_a.refresh_from_db()
        # 45.00 of material absorbed by the 4 units that survived, not by all 5.
        assert released_work_order_a.produced_unit_cost == Decimal("11.2500")


# ================================================================ Move types vs 4.7 demand planning
class TestManufacturingMoveTypesAreNotCustomerDemand:
    """Reusing ``issue`` for a component draw would inflate every forecast built on the
    stock-issues source — the entire reason the two 4.8 move types exist."""

    def _window(self):
        from django.utils import timezone
        from apps.scm.tests._helpers import add_months, month_start
        today = timezone.localdate()
        return add_months(month_start(today), -1), today

    def test_component_draws_post_as_consumption_never_as_issue(self, client_a,
                                                                released_work_order_a):
        from apps.scm.models import StockMove
        _issue(client_a, released_work_order_a)
        assert _moves(released_work_order_a, "consumption").count() == 2
        assert not StockMove.objects.filter(tenant=released_work_order_a.tenant,
                                            reference=released_work_order_a.number,
                                            move_type="issue").exists()

    def test_output_posts_as_production_never_as_receipt(self, client_a,
                                                         released_work_order_a):
        from apps.scm.models import StockMove
        _issue(client_a, released_work_order_a)
        _report(client_a, released_work_order_a, good="2")
        assert _moves(released_work_order_a, "production").count() == 1
        assert not StockMove.objects.filter(tenant=released_work_order_a.tenant,
                                            reference=released_work_order_a.number,
                                            move_type="receipt").exists()

    def test_a_work_order_draw_is_NOT_counted_as_customer_demand(self, client_a, tenant_a,
                                                                 released_work_order_a,
                                                                 component_bolt_a):
        from apps.scm.models.DemandPlanning._history import demand_series
        _issue(client_a, released_work_order_a)
        start, end = self._window()
        rows = demand_series(tenant_a.pk, item=component_bolt_a, source="stock_issues",
                             start=start, end=end, bucket="month")
        assert sum(qty for _, qty in rows) == Decimal("0")

    def test_a_REAL_customer_issue_of_the_same_item_still_counts(self, client_a, tenant_a,
                                                                 released_work_order_a,
                                                                 component_bolt_a, location_a):
        """The control: proves the assertion above is measuring the move TYPE, not an empty query."""
        from django.utils import timezone
        from apps.scm.models import StockMove
        from apps.scm.models.DemandPlanning._history import demand_series
        _issue(client_a, released_work_order_a)
        StockMove.objects.create(tenant=tenant_a, item=component_bolt_a, location=location_a,
                                 quantity=Decimal("-7"), move_type="issue",
                                 moved_at=timezone.now())
        start, end = self._window()
        rows = demand_series(tenant_a.pk, item=component_bolt_a, source="stock_issues",
                             start=start, end=end, bucket="month")
        assert sum(qty for _, qty in rows) == Decimal("7")

    def test_finished_output_is_not_read_as_demand_either(self, client_a, tenant_a,
                                                          released_work_order_a, item_a):
        from apps.scm.models.DemandPlanning._history import demand_series
        _issue(client_a, released_work_order_a)
        _report(client_a, released_work_order_a, good="3")
        start, end = self._window()
        rows = demand_series(tenant_a.pk, item=item_a, source="stock_issues", start=start,
                             end=end, bucket="month")
        assert sum(qty for _, qty in rows) == Decimal("0")


# ================================================================ ProductionTimeLog CRUD
class TestProductionTimeLogCRUD:
    def test_list_returns_200_with_its_own_rows(self, client_a, time_log_a):
        resp = client_a.get(reverse("scm:productiontimelog_list"))
        assert resp.status_code == 200
        assert time_log_a in resp.context["object_list"]

    def test_list_excludes_other_tenant_rows(self, client_a, time_log_a, time_log_b):
        resp = client_a.get(reverse("scm:productiontimelog_list"))
        assert time_log_b not in resp.context["object_list"]

    def test_list_uses_the_documented_template_and_context(self, client_a, time_log_a):
        resp = client_a.get(reverse("scm:productiontimelog_list"))
        assert "scm/manufacturing/productiontimelog/list.html" in [t.name for t in resp.templates]
        for key in ("object_list", "page_obj", "q", "type_choices", "reason_choices",
                    "work_centers", "work_orders"):
            assert key in resp.context, key

    def test_the_filter_dropdown_offers_CLOSED_runs_too(self, client_a, time_log_a,
                                                        released_work_order_a):
        """A closed run's logs are exactly the rows this page is careful to still show — an
        open-only list made the deep link from a finished run silently reset to 'All'."""
        released_work_order_a.status = "closed"
        released_work_order_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:productiontimelog_list"))
        assert released_work_order_a in set(resp.context["work_orders"])

    def test_list_filter_by_entry_type_and_work_order(self, client_a, time_log_a,
                                                      released_work_order_a):
        by_type = client_a.get(reverse("scm:productiontimelog_list"), {"entry_type": "machine"})
        assert time_log_a in by_type.context["object_list"]
        by_other = client_a.get(reverse("scm:productiontimelog_list"), {"entry_type": "setup"})
        assert time_log_a not in by_other.context["object_list"]
        by_run = client_a.get(reverse("scm:productiontimelog_list"),
                              {"work_order": str(released_work_order_a.pk)})
        assert time_log_a in by_run.context["object_list"]

    def test_create_saves_with_the_request_tenant(self, client_a, tenant_a,
                                                  released_work_order_a, work_center_a):
        from apps.scm.models import ProductionTimeLog
        resp = client_a.post(reverse("scm:productiontimelog_create"),
                             _log_view_payload(released_work_order_a, work_center_a,
                                               operation="Deburr"))
        assert resp.status_code == 302
        log = ProductionTimeLog.objects.get(tenant=tenant_a, operation="Deburr")
        assert log.number.startswith("PRD-")
        assert log.duration_minutes == 60

    def test_edit_updates_a_live_runs_log(self, client_a, time_log_a, released_work_order_a,
                                          work_center_a):
        resp = client_a.post(reverse("scm:productiontimelog_edit", args=[time_log_a.pk]),
                             _log_view_payload(released_work_order_a, work_center_a,
                                               operation="Re-milled"))
        assert resp.status_code == 302
        time_log_a.refresh_from_db()
        assert time_log_a.operation == "Re-milled"

    def test_detail_renders_with_the_frozen_flag(self, client_a, time_log_a):
        resp = client_a.get(reverse("scm:productiontimelog_detail", args=[time_log_a.pk]))
        assert resp.status_code == 200
        assert "scm/manufacturing/productiontimelog/detail.html" in [t.name for t in resp.templates]
        assert resp.context["is_frozen"] is False

    def test_delete_is_post_only(self, client_a, time_log_a):
        from apps.scm.models import ProductionTimeLog
        assert client_a.get(reverse("scm:productiontimelog_delete",
                                    args=[time_log_a.pk])).status_code == 405
        assert ProductionTimeLog.objects.filter(pk=time_log_a.pk).exists()

    def test_delete_removes_a_live_runs_log(self, client_a, time_log_a):
        from apps.scm.models import ProductionTimeLog
        resp = client_a.post(reverse("scm:productiontimelog_delete", args=[time_log_a.pk]))
        assert resp.status_code == 302
        assert not ProductionTimeLog.objects.filter(pk=time_log_a.pk).exists()

    def test_an_over_long_interval_is_refused_through_the_view(self, client_a, tenant_a,
                                                               released_work_order_a,
                                                               work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        started = timezone.now()
        resp = client_a.post(reverse("scm:productiontimelog_create"), _log_view_payload(
            released_work_order_a, work_center_a, operation="Geological era",
            started_at=started.strftime("%Y-%m-%dT%H:%M"),
            ended_at=(started + datetime.timedelta(days=40)).strftime("%Y-%m-%dT%H:%M")))
        assert resp.status_code == 200
        assert not ProductionTimeLog.objects.filter(tenant=tenant_a,
                                                    operation="Geological era").exists()


# ================================================================ Frozen logs
class TestProductionTimeLogFreeze:
    def test_editing_a_closed_runs_log_is_refused(self, client_a, time_log_a,
                                                  released_work_order_a):
        released_work_order_a.status = "closed"
        released_work_order_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:productiontimelog_edit", args=[time_log_a.pk]),
                            follow=True)
        assert any("log is frozen" in str(m) for m in resp.context["messages"])

    def test_a_closed_runs_log_cannot_be_edited_by_POST_either(self, client_a, time_log_a,
                                                               released_work_order_a,
                                                               work_center_a):
        released_work_order_a.status = "closed"
        released_work_order_a.save(update_fields=["status"])
        client_a.post(reverse("scm:productiontimelog_edit", args=[time_log_a.pk]),
                      _log_view_payload(released_work_order_a, work_center_a,
                                        operation="Snuck in"))
        time_log_a.refresh_from_db()
        assert time_log_a.operation == "Mill"

    def test_deleting_a_closed_runs_log_is_refused(self, client_a, time_log_a,
                                                   released_work_order_a):
        from apps.scm.models import ProductionTimeLog
        released_work_order_a.status = "closed"
        released_work_order_a.save(update_fields=["status"])
        resp = client_a.post(reverse("scm:productiontimelog_delete", args=[time_log_a.pk]),
                             follow=True)
        assert any("log is frozen" in str(m) for m in resp.context["messages"])
        assert ProductionTimeLog.objects.filter(pk=time_log_a.pk).exists()

    def test_a_cancelled_run_freezes_its_logs_too(self, client_a, time_log_a,
                                                  released_work_order_a):
        from apps.scm.models import ProductionTimeLog
        released_work_order_a.status = "cancelled"
        released_work_order_a.save(update_fields=["status"])
        assert client_a.get(reverse("scm:productiontimelog_edit",
                                    args=[time_log_a.pk])).status_code == 302
        client_a.post(reverse("scm:productiontimelog_delete", args=[time_log_a.pk]))
        assert ProductionTimeLog.objects.filter(pk=time_log_a.pk).exists()

    def test_a_completed_run_freezes_its_logs(self, client_a, time_log_a,
                                              released_work_order_a):
        released_work_order_a.status = "completed"
        released_work_order_a.save(update_fields=["status"])
        resp = client_a.get(reverse("scm:productiontimelog_detail", args=[time_log_a.pk]))
        assert resp.context["is_frozen"] is True


# ================================================================ MRP (compute, never write)
def _mrp_demand(tenant, customer, item, quantity="10", status="submitted"):
    from django.utils import timezone
    from apps.scm.models import SalesOrder, SalesOrderLine
    order = SalesOrder.objects.create(tenant=tenant, customer=customer,
                                      order_date=timezone.localdate(), status=status)
    SalesOrderLine.objects.create(sales_order=order, item=item,
                                  quantity_ordered=Decimal(quantity), unit_price=Decimal("20"))
    return order


def _mrp_rows(resp):
    return {row["item"].pk: row for row in resp.context["rows"]}


class TestMRPReport:
    def test_it_renders_with_the_documented_template_and_context(self, client_a):
        resp = client_a.get(reverse("scm:mrp_report"))
        assert resp.status_code == 200
        assert "scm/manufacturing/mrp_report.html" in [t.name for t in resp.templates]
        for key in ("rows", "page_obj", "horizon_days", "until", "locations", "make_count",
                    "buy_count", "total_rows"):
            assert key in resp.context, key
        assert resp.context["horizon_days"] == 90

    def test_open_demand_for_a_manufactured_item_explodes_to_its_raw_components(
        self, client_a, tenant_a, customer_a, item_a, bom_a, component_bolt_a,
        component_plate_a,
    ):
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        rows = _mrp_rows(client_a.get(reverse("scm:mrp_report")))
        assert rows[item_a.pk]["action"] == "make"
        assert rows[item_a.pk]["shortfall"] == Decimal("10.0000")
        assert rows[component_bolt_a.pk]["action"] == "buy"
        assert rows[component_bolt_a.pk]["shortfall"] == Decimal("20.0000")
        assert rows[component_plate_a.pk]["shortfall"] == Decimal("10.0000")

    def test_the_make_buy_split_is_counted(self, client_a, tenant_a, customer_a, item_a, bom_a):
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        resp = client_a.get(reverse("scm:mrp_report"))
        assert resp.context["make_count"] == 1
        assert resp.context["buy_count"] == 2
        assert resp.context["total_rows"] == 3

    def test_the_sources_column_names_where_each_requirement_came_from(self, client_a, tenant_a,
                                                                       customer_a, item_a, bom_a,
                                                                       component_bolt_a):
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        rows = _mrp_rows(client_a.get(reverse("scm:mrp_report")))
        assert rows[item_a.pk]["sources"] == "Sales orders"
        assert rows[component_bolt_a.pk]["sources"] == f"BOM {bom_a.number}"

    def test_on_hand_nets_the_shortfall_away(self, client_a, tenant_a, customer_a, item_a, bom_a,
                                             location_a):
        """A parent with stock needs nothing built, so pushing raw material down its BOM would
        invent a component shortage that does not exist."""
        from apps.scm.tests._helpers import seed_stock
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        seed_stock(tenant_a, item_a, location_a, "10", "9.0000")
        resp = client_a.get(reverse("scm:mrp_report"))
        assert resp.context["total_rows"] == 0

    def test_safety_stock_raises_the_requirement(self, client_a, tenant_a, customer_a, item_a,
                                                 bom_a, location_a, reorder_rule_a):
        from apps.scm.tests._helpers import seed_stock
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        seed_stock(tenant_a, item_a, location_a, "10", "9.0000")
        rows = _mrp_rows(client_a.get(reverse("scm:mrp_report")))
        assert rows[item_a.pk]["safety_stock"] == Decimal("5.0000")
        assert rows[item_a.pk]["shortfall"] == Decimal("5.0000")

    def test_draft_and_cancelled_orders_are_not_demand(self, client_a, tenant_a, customer_a,
                                                       item_a, bom_a):
        for status in ("draft", "cancelled", "closed", "fulfilled", "invoiced"):
            _mrp_demand(tenant_a, customer_a, item_a, "10", status=status)
        assert client_a.get(reverse("scm:mrp_report")).context["total_rows"] == 0

    def test_a_live_runs_outstanding_components_are_dependent_demand(self, client_a, tenant_a,
                                                                     released_work_order_a,
                                                                     component_bolt_a):
        rows = _mrp_rows(client_a.get(reverse("scm:mrp_report")))
        # 10 bolts required, 100 on hand -> covered; the requirement is still SEEN.
        assert component_bolt_a.pk not in rows
        released_work_order_a.components.filter(item=component_bolt_a).update(
            quantity_required=Decimal("500"))
        rows = _mrp_rows(client_a.get(reverse("scm:mrp_report")))
        assert rows[component_bolt_a.pk]["sources"] == "Work orders"
        assert rows[component_bolt_a.pk]["shortfall"] == Decimal("400.0000")

    def test_another_tenants_demand_never_appears(self, client_a, tenant_b, customer_b, item_b,
                                                  bom_b):
        _mrp_demand(tenant_b, customer_b, item_b, "10")
        assert client_a.get(reverse("scm:mrp_report")).context["total_rows"] == 0

    def test_the_horizon_is_clamped_and_junk_falls_back_to_90(self, client_a):
        for value, expected in (("30", 30), ("0", 1), ("9999", 365), ("abc", 90), ("", 90),
                                ("-5", 1), ("NaN", 90), ("Infinity", 90)):
            resp = client_a.get(reverse("scm:mrp_report"), {"horizon": value})
            assert resp.status_code == 200, value
            assert resp.context["horizon_days"] == expected, value

    def test_the_location_filter_narrows_on_hand(self, client_a, tenant_a, customer_a, item_a,
                                                 bom_a, location_a, location_a2):
        from apps.scm.tests._helpers import seed_stock
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        seed_stock(tenant_a, item_a, location_a, "10", "9.0000")
        everywhere = client_a.get(reverse("scm:mrp_report"))
        elsewhere = client_a.get(reverse("scm:mrp_report"), {"location": str(location_a2.pk)})
        assert everywhere.context["total_rows"] == 0
        assert elsewhere.context["total_rows"] == 3   # WH2 holds none of it

    def test_a_junk_location_filter_is_ignored_rather_than_500ing(self, client_a):
        for junk in ("abc", "-1", "NaN", "1.5"):
            assert client_a.get(reverse("scm:mrp_report"),
                                {"location": junk}).status_code == 200, junk

    def test_it_writes_nothing(self, client_a, tenant_a, customer_a, item_a, bom_a):
        """Compute-then-convert: a silent auto-PO is a business decision the planner never made."""
        from apps.scm.models import PurchaseRequisition, WorkOrder
        _mrp_demand(tenant_a, customer_a, item_a, "10")
        before = (WorkOrder.objects.count(), PurchaseRequisition.objects.count())
        client_a.get(reverse("scm:mrp_report"))
        assert (WorkOrder.objects.count(), PurchaseRequisition.objects.count()) == before


# ================================================================ Production schedule (load board)
class TestProductionSchedule:
    def test_it_renders_with_the_documented_template_and_context(self, client_a, work_center_a):
        resp = client_a.get(reverse("scm:production_schedule"))
        assert resp.status_code == 200
        assert "scm/manufacturing/production_schedule.html" in [t.name for t in resp.templates]
        for key in ("rows", "orders", "unscheduled", "unscheduled_count", "days", "start", "end",
                    "overloaded_count"):
            assert key in resp.context, key
        assert resp.context["days"] == 14

    def test_every_active_centre_gets_a_row(self, client_a, work_center_a, work_center_a2):
        rows = client_a.get(reverse("scm:production_schedule")).context["rows"]
        assert {row["centre"].pk for row in rows} == {work_center_a.pk, work_center_a2.pk}

    def test_an_inactive_centre_is_off_the_board(self, client_a, work_center_a, work_center_a2):
        work_center_a2.is_active = False
        work_center_a2.save(update_fields=["is_active"])
        rows = client_a.get(reverse("scm:production_schedule")).context["rows"]
        assert {row["centre"].pk for row in rows} == {work_center_a.pk}

    def test_a_run_longer_than_the_window_marks_the_centre_overloaded(self, client_a, tenant_a,
                                                                       item_a, work_center_a):
        from django.utils import timezone
        from apps.scm.models import WorkOrder
        now = timezone.now()
        order = WorkOrder.objects.create(
            tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
            work_center=work_center_a, planned_start=now,
            planned_end=now + datetime.timedelta(days=10))
        WorkOrder.objects.filter(pk=order.pk).update(status="planned")
        resp = client_a.get(reverse("scm:production_schedule"))
        row = next(r for r in resp.context["rows"] if r["centre"].pk == work_center_a.pk)
        assert row["scheduled_hours"] == Decimal("240.00")
        assert row["capacity_hours"] == Decimal("112.00")   # 8 h x 100 % x 14 days
        assert row["is_overloaded"] is True
        assert resp.context["overloaded_count"] == 1

    def test_a_run_with_no_planned_window_lands_in_the_unscheduled_list(self, client_a,
                                                                        work_order_a):
        from apps.scm.models import WorkOrder
        WorkOrder.objects.filter(pk=work_order_a.pk).update(status="planned")
        resp = client_a.get(reverse("scm:production_schedule"))
        assert work_order_a in list(resp.context["unscheduled"])
        assert resp.context["unscheduled_count"] == 1

    def test_a_draft_run_is_not_on_the_board_at_all(self, client_a, work_order_a):
        resp = client_a.get(reverse("scm:production_schedule"))
        assert work_order_a not in list(resp.context["orders"])
        assert resp.context["unscheduled_count"] == 0

    def test_another_tenants_centres_never_appear(self, client_a, work_center_a, work_center_b):
        rows = client_a.get(reverse("scm:production_schedule")).context["rows"]
        assert work_center_b.pk not in {row["centre"].pk for row in rows}

    def test_the_days_window_is_clamped_and_junk_falls_back_to_14(self, client_a):
        for value, expected in (("7", 7), ("0", 1), ("999", 90), ("notanumber", 14), ("", 14),
                                ("-3", 1), ("NaN", 14)):
            resp = client_a.get(reverse("scm:production_schedule"), {"days": value})
            assert resp.status_code == 200, value
            assert resp.context["days"] == expected, value

    def test_a_zero_capacity_centre_does_not_divide_by_zero(self, client_a, tenant_a, item_a,
                                                            work_center_a):
        from django.utils import timezone
        from apps.scm.models import WorkOrder
        work_center_a.capacity_hours_per_day = Decimal("0")
        work_center_a.save(update_fields=["capacity_hours_per_day"])
        now = timezone.now()
        order = WorkOrder.objects.create(
            tenant=tenant_a, item=item_a, quantity_planned=Decimal("1"),
            work_center=work_center_a, planned_start=now,
            planned_end=now + datetime.timedelta(hours=4))
        WorkOrder.objects.filter(pk=order.pk).update(status="planned")
        resp = client_a.get(reverse("scm:production_schedule"))
        row = next(r for r in resp.context["rows"] if r["centre"].pk == work_center_a.pk)
        assert resp.status_code == 200
        assert row["load_pct"] == Decimal("0")
        assert row["is_overloaded"] is False


# ================================================================ location_delete PROTECT guard
class TestLocationDeleteWithAWorkOrderReference:
    def test_a_location_a_work_order_points_at_cannot_be_deleted_and_does_not_500(
        self, client_a, work_order_a, location_a2,
    ):
        """WorkOrder.component_location / output_location are PROTECT — the miss showed up as an
        uncaught ProtectedError, i.e. a 500 on an ordinary delete."""
        from apps.scm.models import Location
        resp = client_a.post(reverse("scm:location_delete", args=[location_a2.pk]), follow=True)
        assert resp.status_code == 200
        assert any("cannot be deleted" in str(m) for m in resp.context["messages"])
        assert Location.objects.filter(pk=location_a2.pk).exists()

    def test_the_message_names_the_blocking_model(self, client_a, work_order_a, location_a2):
        resp = client_a.post(reverse("scm:location_delete", args=[location_a2.pk]), follow=True)
        assert any("work order" in str(m).lower() for m in resp.context["messages"])

    def test_a_location_a_work_CENTRE_points_at_is_SET_NULL_and_still_deletes(self, client_a,
                                                                              work_center_a,
                                                                              location_a):
        from apps.scm.models import Location
        resp = client_a.post(reverse("scm:location_delete", args=[location_a.pk]))
        assert resp.status_code == 302
        assert not Location.objects.filter(pk=location_a.pk).exists()
        work_center_a.refresh_from_db()
        assert work_center_a.location_id is None

    def test_an_unreferenced_location_still_deletes(self, client_a, location_a2):
        from apps.scm.models import Location
        client_a.post(reverse("scm:location_delete", args=[location_a2.pk]))
        assert not Location.objects.filter(pk=location_a2.pk).exists()


# ================================================================================================
# Negative-input hardening (L11 junk FK filters / L9 pagination) — 200, never a 500.
# ================================================================================================
class TestManufacturingNegativeInputHardening:
    LIST_ROUTES = ("scm:workcenter_list", "scm:billofmaterials_list", "scm:workorder_list",
                   "scm:productiontimelog_list")
    REPORT_ROUTES = ("scm:mrp_report", "scm:production_schedule")

    def test_every_list_survives_a_junk_item_filter(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"item": "abc"}).status_code == 200, name

    def test_every_list_survives_a_junk_status_filter(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"status": "nope"}).status_code == 200, name

    def test_every_list_survives_a_junk_work_centre_filter(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name),
                                {"work_center": "not-a-pk"}).status_code == 200, name

    def test_every_list_survives_a_page_past_the_end(self, client_a, work_center_a, bom_a,
                                                     work_order_a, time_log_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"page": "9999"}).status_code == 200, name

    def test_every_list_survives_a_non_numeric_page(self, client_a):
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), {"page": "abc"}).status_code == 200, name

    def test_every_list_survives_the_whole_junk_query_string_at_once(self, client_a):
        params = {"status": "nope", "item": "abc", "page": "9999", "work_center": "-1",
                  "location": "NaN", "is_active": "abc", "entry_type": "junk",
                  "downtime_reason": "junk", "bom_type": "junk", "is_default": "abc",
                  "center_type": "junk", "priority": "junk", "order_policy": "junk",
                  "work_order": "abc", "default_work_center": "1.5", "q": "'; DROP TABLE --"}
        for name in self.LIST_ROUTES:
            assert client_a.get(reverse(name), params).status_code == 200, name

    def test_both_reports_survive_the_junk_query_string(self, client_a):
        params = {"horizon": "abc", "days": "notanumber", "location": "-1", "page": "9999"}
        for name in self.REPORT_ROUTES:
            assert client_a.get(reverse(name), params).status_code == 200, name

    def test_the_workcenter_list_page_2_returns_200_beyond_the_page_size(self, client_a,
                                                                         tenant_a):
        from apps.scm.models import WorkCenter
        for i in range(20):
            WorkCenter.objects.create(tenant=tenant_a, code=f"BULK-{i}", name=f"Bulk {i}")
        resp = client_a.get(reverse("scm:workcenter_list"), {"page": "2"})
        assert resp.status_code == 200
        assert resp.context["page_obj"].number == 2
        assert len(resp.context["object_list"]) == 5

    def test_the_bom_list_page_2_returns_200_beyond_the_page_size(self, client_a, tenant_a,
                                                                  item_a):
        from apps.scm.models import BillOfMaterials
        for i in range(20):
            BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name=f"Bulk {i}",
                                           version=f"v{i}")
        resp = client_a.get(reverse("scm:billofmaterials_list"), {"page": "2"})
        assert resp.status_code == 200
        assert resp.context["page_obj"].number == 2

    def test_the_workorder_list_page_2_returns_200_beyond_the_page_size(self, client_a, tenant_a,
                                                                        item_a):
        from apps.scm.models import WorkOrder
        for _ in range(20):
            WorkOrder.objects.create(tenant=tenant_a, item=item_a,
                                     quantity_planned=Decimal("1"))
        resp = client_a.get(reverse("scm:workorder_list"), {"page": "2"})
        assert resp.status_code == 200
        assert len(resp.context["object_list"]) == 5

    def test_the_time_log_list_page_2_returns_200_beyond_the_page_size(self, client_a, tenant_a,
                                                                       released_work_order_a,
                                                                       work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        for _ in range(20):
            ProductionTimeLog.objects.create(tenant=tenant_a, work_order=released_work_order_a,
                                             work_center=work_center_a,
                                             started_at=timezone.now())
        resp = client_a.get(reverse("scm:productiontimelog_list"), {"page": "2"})
        assert resp.status_code == 200
        assert resp.context["page_obj"].number == 2

    def test_the_mrp_report_page_2_returns_200_beyond_the_page_size(self, client_a, tenant_a,
                                                                     customer_a):
        from apps.scm.models import Item
        for i in range(35):
            item = Item.objects.create(tenant=tenant_a, sku=f"MRPP-{i}", name=f"Mrp {i}")
            _mrp_demand(tenant_a, customer_a, item, "5")
        resp = client_a.get(reverse("scm:mrp_report"), {"page": "2"})
        assert resp.status_code == 200
        assert resp.context["page_obj"].number == 2

    def test_the_workcenter_form_rejects_junk_rates_without_500ing(self, client_a, tenant_a):
        from apps.scm.models import WorkCenter
        for junk in ("NaN", "Infinity", "-Infinity", "abc", "-1", "100001", "9" * 20):
            resp = client_a.post(reverse("scm:workcenter_create"),
                                 _wc_view_payload(machine_cost_per_hour=junk))
            assert resp.status_code == 200, junk
        assert not WorkCenter.objects.filter(tenant=tenant_a, code="WC-NEW").exists()

    def test_the_workorder_form_rejects_junk_quantities_without_500ing(self, client_a, tenant_a,
                                                                        item_a):
        from apps.scm.models import WorkOrder
        for junk in ("NaN", "Infinity", "abc", "0", "-5", "9" * 20):
            resp = client_a.post(reverse("scm:workorder_create"),
                                 _wo_view_payload(item_a, quantity_planned=junk))
            assert resp.status_code == 200, junk
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_the_bom_form_rejects_a_junk_output_quantity(self, client_a, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        for junk in ("NaN", "Infinity", "abc", "0", "-1", "9" * 20):
            resp = client_a.post(reverse("scm:billofmaterials_create"),
                                 _bom_view_payload(item_a, version="9", output_quantity=junk))
            assert resp.status_code == 200, junk
        assert not BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()

    def test_the_bom_line_formset_rejects_a_junk_quantity(self, client_a, tenant_a, item_a,
                                                          component_bolt_a):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_create"), _bom_view_payload(
            item_a, [_bom_line_row(component_bolt_a, quantity_per="NaN")], version="9"))
        assert resp.status_code == 200
        assert not BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()

    def test_the_component_formset_rejects_a_junk_quantity(self, client_a, tenant_a, item_a,
                                                           component_bolt_a):
        from apps.scm.models import WorkOrder
        data = _wo_view_payload(item_a)
        data.update(formset_data("components", [
            {"id": "", "sequence": "10", "item": str(component_bolt_a.pk),
             "quantity_required": "Infinity", "uom": "", "lot_serial": "",
             "issue_method": "manual", "unit_cost": "2", "notes": ""},
        ]))
        resp = client_a.post(reverse("scm:workorder_create"), data)
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_a_junk_pk_in_the_url_is_a_404_not_a_500(self, client_a):
        for name in ("scm:workorder_detail", "scm:billofmaterials_detail",
                     "scm:workcenter_detail", "scm:productiontimelog_detail"):
            assert client_a.get(reverse(name, args=[999999])).status_code == 404, name


# ================================================================================================
# Query-count regression guards (locks in the batching the performance review added)
# ================================================================================================
def _query_count(client, url, params=None):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(url, params or {})
    assert resp.status_code == 200
    return len(ctx.captured_queries)


def _seed_mrp_fixture(tenant, customer, start, count):
    """``count`` demanded parents, each with its own 1-line active BOM. Explodes to 2x rows."""
    from apps.scm.models import BillOfMaterials, BOMLine, Item
    for i in range(start, start + count):
        parent = Item.objects.create(tenant=tenant, sku=f"MRPX-P-{i}", name=f"Parent {i}",
                                     standard_cost=Decimal("10"))
        child = Item.objects.create(tenant=tenant, sku=f"MRPX-C-{i}", name=f"Child {i}",
                                    standard_cost=Decimal("2"))
        bom = BillOfMaterials.objects.create(tenant=tenant, item=parent, name=f"Recipe {i}",
                                             version="1", status="active")
        BOMLine.objects.create(bom=bom, component=child, quantity_per=Decimal("2"))
        _mrp_demand(tenant, customer, parent, "10")


def _seed_schedule_fixture(tenant, item, start, count):
    from django.utils import timezone
    from apps.scm.models import WorkCenter, WorkOrder
    now = timezone.now()
    for i in range(start, start + count):
        centre = WorkCenter.objects.create(tenant=tenant, code=f"SCHX-{i}", name=f"Cell {i}")
        order = WorkOrder.objects.create(
            tenant=tenant, item=item, quantity_planned=Decimal("1"), work_center=centre,
            planned_start=now, planned_end=now + datetime.timedelta(hours=6))
        WorkOrder.objects.filter(pk=order.pk).update(status="planned")


class TestManufacturingQueryCounts:
    def test_workcenter_list_has_no_n_plus_one(self, client_a, tenant_a, location_a,
                                               employee_party_a, org_unit_a,
                                               django_assert_max_num_queries):
        from apps.scm.models import WorkCenter
        for i in range(10):
            WorkCenter.objects.create(tenant=tenant_a, code=f"NP-{i}", name=f"Cell {i}",
                                      location=location_a, org_unit=org_unit_a,
                                      supervisor=employee_party_a)
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:workcenter_list")).status_code == 200

    def test_billofmaterials_list_has_no_n_plus_one(self, client_a, tenant_a, item_a, uom_each_a,
                                                    work_center_a, component_bolt_a,
                                                    django_assert_max_num_queries):
        from apps.scm.models import BillOfMaterials, BOMLine
        for i in range(10):
            bom = BillOfMaterials.objects.create(tenant=tenant_a, item=item_a, name=f"R{i}",
                                                 version=f"v{i}", uom=uom_each_a,
                                                 default_work_center=work_center_a)
            BOMLine.objects.create(bom=bom, component=component_bolt_a,
                                   quantity_per=Decimal("1"))
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:billofmaterials_list")).status_code == 200

    def test_workorder_list_has_no_n_plus_one(self, client_a, tenant_a, item_a, bom_a,
                                              work_center_a, location_a, location_a2,
                                              sales_order_a, django_assert_max_num_queries):
        from apps.scm.models import WorkOrder
        for _ in range(10):
            WorkOrder.objects.create(tenant=tenant_a, item=item_a, bom=bom_a,
                                     quantity_planned=Decimal("1"), work_center=work_center_a,
                                     sales_order=sales_order_a, component_location=location_a,
                                     output_location=location_a2)
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:workorder_list")).status_code == 200

    def test_productiontimelog_list_has_no_n_plus_one(self, client_a, tenant_a,
                                                      released_work_order_a, work_center_a,
                                                      employee_party_a,
                                                      django_assert_max_num_queries):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog
        for _ in range(10):
            ProductionTimeLog.objects.create(tenant=tenant_a, work_order=released_work_order_a,
                                             work_center=work_center_a,
                                             operator=employee_party_a,
                                             started_at=timezone.now())
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:productiontimelog_list")).status_code == 200

    def test_workorder_detail_resolves_each_pool_once(self, client_a, released_work_order_a,
                                                      time_log_a, django_assert_max_num_queries):
        _issue(client_a, released_work_order_a)
        with django_assert_max_num_queries(15):
            assert client_a.get(reverse("scm:workorder_detail",
                                        args=[released_work_order_a.pk])).status_code == 200

    def test_workcenter_detail_aggregates_the_time_logs_once(self, client_a, work_center_a,
                                                             time_log_a,
                                                             django_assert_max_num_queries):
        with django_assert_max_num_queries(12):
            assert client_a.get(reverse("scm:workcenter_detail",
                                        args=[work_center_a.pk])).status_code == 200

    def test_billofmaterials_detail_explodes_once(self, client_a, tenant_a, bom_a,
                                                  component_bolt_a, component_plate_a,
                                                  django_assert_max_num_queries):
        from apps.scm.models import BillOfMaterials, BOMLine
        sub = BillOfMaterials.objects.create(tenant=tenant_a, item=component_bolt_a,
                                             name="Bolt recipe", version="1", status="active")
        BOMLine.objects.create(bom=sub, component=component_plate_a, quantity_per=Decimal("1"))
        with django_assert_max_num_queries(18):
            assert client_a.get(reverse("scm:billofmaterials_detail",
                                        args=[bom_a.pk])).status_code == 200

    def test_workorder_create_page_does_not_query_per_option(self, client_a, tenant_a, item_a,
                                                             bom_a, work_center_a, location_a,
                                                             lot_a, sales_order_a,
                                                             django_assert_max_num_queries):
        with django_assert_max_num_queries(30):
            assert client_a.get(reverse("scm:workorder_create")).status_code == 200

    def test_mrp_report_stays_flat_as_demand_grows(self, client_a, tenant_a, customer_a,
                                                   django_assert_max_num_queries):
        _seed_mrp_fixture(tenant_a, customer_a, 0, 10)
        with django_assert_max_num_queries(20):
            assert client_a.get(reverse("scm:mrp_report")).status_code == 200

    def test_production_schedule_stays_flat_as_the_board_grows(self, client_a, tenant_a, item_a,
                                                               django_assert_max_num_queries):
        _seed_schedule_fixture(tenant_a, item_a, 0, 10)
        with django_assert_max_num_queries(14):
            assert client_a.get(reverse("scm:production_schedule")).status_code == 200

    def test_mrp_report_is_SCALE_INVARIANT(self, client_a, tenant_a, customer_a):
        """The one that matters: the explosion shares ONE index across every item it explodes.
        Before that, MRP asked active_for() per BOM line per level — ~2,300 queries for one page.
        """
        url = reverse("scm:mrp_report")
        _seed_mrp_fixture(tenant_a, customer_a, 0, 5)
        client_a.get(url)                      # warm any process-level caches
        before = _query_count(client_a, url)
        _seed_mrp_fixture(tenant_a, customer_a, 100, 5)   # double the fixture
        after = _query_count(client_a, url)
        assert after == before, f"{before} -> {after} queries when the fixture doubled"

    def test_production_schedule_is_SCALE_INVARIANT(self, client_a, tenant_a, item_a):
        """One grouped scheduled_hours_map for the whole board, not one aggregate per centre."""
        url = reverse("scm:production_schedule")
        _seed_schedule_fixture(tenant_a, item_a, 0, 5)
        client_a.get(url)
        before = _query_count(client_a, url)
        _seed_schedule_fixture(tenant_a, item_a, 100, 5)
        after = _query_count(client_a, url)
        assert after == before, f"{before} -> {after} queries when the fixture doubled"

    def test_workcenter_detail_is_scale_invariant_in_its_time_logs(self, client_a, tenant_a,
                                                                    released_work_order_a,
                                                                    work_center_a):
        from django.utils import timezone
        from apps.scm.models import ProductionTimeLog

        def _book(n):
            for _ in range(n):
                ProductionTimeLog.objects.create(
                    tenant=tenant_a, work_order=released_work_order_a,
                    work_center=work_center_a, started_at=timezone.now(),
                    ended_at=timezone.now() + datetime.timedelta(minutes=30))

        url = reverse("scm:workcenter_detail", args=[work_center_a.pk])
        _book(5)
        client_a.get(url)
        before = _query_count(client_a, url)
        _book(5)
        assert _query_count(client_a, url) == before


# ================================================================ Create guarded without a tenant
class TestManufacturingCreateWithoutTenantWorkspace:
    def _orphan_client(self, suffix):
        from django.test import Client
        from apps.accounts.models import User
        user = User.objects.create_user(email=f"orphan-mfg{suffix}@example.com",
                                        username=f"orphan_mfg{suffix}", password="x", tenant=None)
        client = Client()
        client.force_login(user)
        return client

    def test_workorder_create_redirects(self, db):
        from apps.scm.models import WorkOrder
        assert self._orphan_client("1").get(
            reverse("scm:workorder_create")).status_code == 302
        assert WorkOrder.objects.count() == 0

    def test_billofmaterials_create_redirects(self, db):
        from apps.scm.models import BillOfMaterials
        assert self._orphan_client("2").get(
            reverse("scm:billofmaterials_create")).status_code == 302
        assert BillOfMaterials.objects.count() == 0

    def test_workcenter_create_redirects(self, db):
        from apps.scm.models import WorkCenter
        assert self._orphan_client("3").get(
            reverse("scm:workcenter_create")).status_code == 302
        assert WorkCenter.objects.count() == 0

    def test_productiontimelog_create_redirects(self, db):
        from apps.scm.models import ProductionTimeLog
        assert self._orphan_client("4").get(
            reverse("scm:productiontimelog_create")).status_code == 302
        assert ProductionTimeLog.objects.count() == 0

    def test_the_reports_still_render_empty_for_a_tenant_less_user(self, db):
        client = self._orphan_client("5")
        for name in ("scm:mrp_report", "scm:production_schedule"):
            resp = client.get(reverse(name))
            assert resp.status_code == 200, name


# ================================================================ The form PAGES themselves (GET)
class TestManufacturingFormPagesRender:
    def test_workorder_create_page_renders_three_blank_component_rows(self, client_a):
        resp = client_a.get(reverse("scm:workorder_create"))
        assert resp.status_code == 200
        assert "scm/manufacturing/workorder/form.html" in [t.name for t in resp.templates]
        assert resp.context["is_edit"] is False
        assert resp.context["obj"] is None
        assert resp.context["formset"].total_form_count() == 3

    def test_workorder_edit_page_renders_the_saved_components(self, client_a,
                                                              stocked_work_order_a):
        resp = client_a.get(reverse("scm:workorder_edit", args=[stocked_work_order_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["obj"] == stocked_work_order_a
        assert resp.context["formset"].total_form_count() == 5   # 2 saved + 3 extra

    def test_billofmaterials_create_page_renders(self, client_a):
        resp = client_a.get(reverse("scm:billofmaterials_create"))
        assert resp.status_code == 200
        assert "scm/manufacturing/billofmaterials/form.html" in [t.name for t in resp.templates]
        assert resp.context["is_edit"] is False
        assert resp.context["formset"].total_form_count() == 3

    def test_billofmaterials_edit_page_renders_the_saved_lines(self, client_a, bom_a):
        resp = client_a.get(reverse("scm:billofmaterials_edit", args=[bom_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["formset"].total_form_count() == 5   # 2 saved + 3 extra

    def test_workcenter_create_and_edit_pages_render(self, client_a, work_center_a):
        create = client_a.get(reverse("scm:workcenter_create"))
        assert create.status_code == 200
        assert "scm/manufacturing/workcenter/form.html" in [t.name for t in create.templates]
        assert create.context["is_edit"] is False
        edit = client_a.get(reverse("scm:workcenter_edit", args=[work_center_a.pk]))
        assert edit.context["is_edit"] is True
        assert edit.context["obj"] == work_center_a

    def test_productiontimelog_create_and_edit_pages_render(self, client_a, time_log_a):
        create = client_a.get(reverse("scm:productiontimelog_create"))
        assert create.status_code == 200
        assert "scm/manufacturing/productiontimelog/form.html" in [
            t.name for t in create.templates]
        edit = client_a.get(reverse("scm:productiontimelog_edit", args=[time_log_a.pk]))
        assert edit.status_code == 200
        assert edit.context["obj"] == time_log_a


class TestMRPZeroQuantityDemand:
    def test_a_zero_quantity_order_line_adds_no_requirement(self, client_a, tenant_a, customer_a,
                                                            item_a, bom_a):
        _mrp_demand(tenant_a, customer_a, item_a, "0")
        assert client_a.get(reverse("scm:mrp_report")).context["total_rows"] == 0
