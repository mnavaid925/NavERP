"""Security tests for the SCM 4.1 Procurement Management sub-module.

Covers:
- Anonymous -> redirect to login.
- @tenant_admin_required gates: requisition_approve/reject, quote_award,
  purchaseorder_approve/cancel/amend, goodsreceipt_cancel -> 403 for a non-admin member;
  admin succeeds. Plain @login_required actions work for a non-admin member.
- Cross-tenant IDOR: tenant-A admin against tenant-B objects -> 404, on every
  detail/edit route and every POST action route.
- Cross-tenant FORM/FORMSET binding: a tenant-A form/formset must never accept a
  tenant-B FK value (requisition/quote/bill/purchase_order on the headers; po_line/
  rfq_line on the child formsets via _scope_to_parent).
- POST-only action views: GET -> 405.
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.scm.tests._helpers import formset_data

pytestmark = pytest.mark.django_db


# ================================================================ Anonymous -> login redirect
class TestAnonymousRedirect:
    def test_overview_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:overview"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_requisition_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:requisition_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_rfq_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:rfq_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_purchaseorder_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:purchaseorder_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_goodsreceipt_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:goodsreceipt_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ @tenant_admin_required gates
class TestAdminRequiredGates:
    def test_requisition_approve_requires_admin(self, member_client, client_a, requisition_pending_a):
        url = reverse("scm:requisition_approve", args=[requisition_pending_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_requisition_reject_requires_admin(self, member_client, client_a, requisition_pending_a):
        url = reverse("scm:requisition_reject", args=[requisition_pending_a.pk])
        assert member_client.post(url).status_code == 403
        resp = client_a.post(url, {"decision_note": "Not needed"})
        assert resp.status_code != 403

    def test_quote_award_requires_admin(self, member_client, client_a, quote_a):
        url = reverse("scm:quote_award", args=[quote_a.pk])
        assert member_client.post(url).status_code == 403

    def test_purchaseorder_approve_requires_admin(self, member_client, client_a, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="pending_approval")
        url = reverse("scm:purchaseorder_approve", args=[po.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_purchaseorder_cancel_requires_admin(self, member_client, client_a, purchase_order_a):
        url = reverse("scm:purchaseorder_cancel", args=[purchase_order_a.pk])
        assert member_client.post(url).status_code == 403

    def test_purchaseorder_amend_requires_admin(self, member_client, purchase_order_a):
        url = reverse("scm:purchaseorder_amend", args=[purchase_order_a.pk])
        assert member_client.get(url).status_code == 403
        assert member_client.post(url).status_code == 403

    def test_goodsreceipt_cancel_requires_admin(self, member_client, client_a, goods_receipt_a):
        url = reverse("scm:goodsreceipt_cancel", args=[goods_receipt_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Plain @login_required actions work for a member
class TestOrdinaryActionsAllowNonAdmin:
    def test_member_can_submit_own_requisition(self, member_client, requisition_a):
        url = reverse("scm:requisition_submit", args=[requisition_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        requisition_a.refresh_from_db()
        assert requisition_a.status == "pending_approval"

    def test_member_can_send_rfq(self, member_client, rfq_a, supplier_a, tenant_a):
        from apps.scm.models import RFQVendor
        RFQVendor.objects.create(tenant=tenant_a, rfq=rfq_a, party=supplier_a)
        url = reverse("scm:rfq_send", args=[rfq_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        rfq_a.refresh_from_db()
        assert rfq_a.status == "sent"

    def test_member_can_submit_purchase_order(self, member_client, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder, PurchaseOrderLine
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="draft")
        PurchaseOrderLine.objects.create(purchase_order=po, item_description="x", quantity=1, unit_price=Decimal("1.00"))
        url = reverse("scm:purchaseorder_submit", args=[po.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        po.refresh_from_db()
        assert po.status == "pending_approval"

    def test_member_can_receive_goods_receipt(self, member_client, goods_receipt_a):
        url = reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        goods_receipt_a.refresh_from_db()
        assert goods_receipt_a.status == "received"

    def test_member_can_view_requisition_detail(self, member_client, requisition_a):
        url = reverse("scm:requisition_detail", args=[requisition_a.pk])
        assert member_client.get(url).status_code == 200


# ================================================================ Cross-tenant IDOR -> 404
class TestCrossTenantIDOR:
    def test_requisition_detail_cross_tenant_404(self, client_a, requisition_b):
        assert client_a.get(reverse("scm:requisition_detail", args=[requisition_b.pk])).status_code == 404

    def test_requisition_edit_cross_tenant_404(self, client_a, requisition_b):
        assert client_a.get(reverse("scm:requisition_edit", args=[requisition_b.pk])).status_code == 404

    def test_requisition_delete_cross_tenant_404(self, client_a, requisition_b):
        assert client_a.post(reverse("scm:requisition_delete", args=[requisition_b.pk])).status_code == 404

    def test_requisition_submit_cross_tenant_404(self, client_a, requisition_b):
        assert client_a.post(reverse("scm:requisition_submit", args=[requisition_b.pk])).status_code == 404

    def test_requisition_approve_cross_tenant_404(self, client_a, requisition_b):
        assert client_a.post(reverse("scm:requisition_approve", args=[requisition_b.pk])).status_code == 404

    def test_rfq_detail_cross_tenant_404(self, client_a, rfq_b):
        assert client_a.get(reverse("scm:rfq_detail", args=[rfq_b.pk])).status_code == 404

    def test_rfq_edit_cross_tenant_404(self, client_a, rfq_b):
        assert client_a.get(reverse("scm:rfq_edit", args=[rfq_b.pk])).status_code == 404

    def test_rfq_delete_cross_tenant_404(self, client_a, rfq_b):
        assert client_a.post(reverse("scm:rfq_delete", args=[rfq_b.pk])).status_code == 404

    def test_quote_edit_cross_tenant_404(self, client_a, quote_b):
        assert client_a.get(reverse("scm:quote_edit", args=[quote_b.pk])).status_code == 404

    def test_quote_award_cross_tenant_404(self, client_a, quote_b):
        assert client_a.post(reverse("scm:quote_award", args=[quote_b.pk])).status_code == 404

    def test_purchaseorder_detail_cross_tenant_404(self, client_a, purchase_order_b):
        assert client_a.get(reverse("scm:purchaseorder_detail", args=[purchase_order_b.pk])).status_code == 404

    def test_purchaseorder_edit_cross_tenant_404(self, client_a, purchase_order_b):
        # tenant filtering (get_object_or_404(..., tenant=request.tenant)) happens before the
        # is_editable check, so this 404s regardless of purchase_order_b's status.
        assert client_a.get(reverse("scm:purchaseorder_edit", args=[purchase_order_b.pk])).status_code == 404

    def test_purchaseorder_amend_cross_tenant_404(self, client_a, purchase_order_b):
        assert client_a.get(reverse("scm:purchaseorder_amend", args=[purchase_order_b.pk])).status_code == 404

    def test_purchaseorder_cancel_cross_tenant_404(self, client_a, purchase_order_b):
        assert client_a.post(reverse("scm:purchaseorder_cancel", args=[purchase_order_b.pk])).status_code == 404

    def test_goodsreceipt_detail_cross_tenant_404(self, client_a, goods_receipt_b):
        assert client_a.get(reverse("scm:goodsreceipt_detail", args=[goods_receipt_b.pk])).status_code == 404

    def test_goodsreceipt_edit_cross_tenant_404(self, client_a, goods_receipt_b):
        assert client_a.get(reverse("scm:goodsreceipt_edit", args=[goods_receipt_b.pk])).status_code == 404

    def test_goodsreceipt_receive_cross_tenant_404(self, client_a, goods_receipt_b):
        assert client_a.post(reverse("scm:goodsreceipt_receive", args=[goods_receipt_b.pk])).status_code == 404

    def test_goodsreceipt_cancel_cross_tenant_404(self, client_a, goods_receipt_b):
        assert client_a.post(reverse("scm:goodsreceipt_cancel", args=[goods_receipt_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM/FORMSET binding
class TestCrossTenantFormScoping:
    """TenantModelForm scopes header FKs; _scope_to_parent scopes child-table FKs. Both
    must exclude another tenant's rows, not just filter them out of the rendered <select>.
    """

    def test_rfq_form_requisition_field_excludes_other_tenant(self, tenant_a, requisition_b):
        from apps.scm.forms import RFQForm
        form = RFQForm(tenant=tenant_a)
        pks = set(form.fields["requisition"].queryset.values_list("pk", flat=True))
        assert requisition_b.pk not in pks

    def test_purchaseorder_form_requisition_and_quote_fields_exclude_other_tenant(
        self, tenant_a, requisition_b, quote_b,
    ):
        from apps.scm.forms import PurchaseOrderForm
        form = PurchaseOrderForm(tenant=tenant_a)
        req_pks = set(form.fields["requisition"].queryset.values_list("pk", flat=True))
        quote_pks = set(form.fields["quote"].queryset.values_list("pk", flat=True))
        assert requisition_b.pk not in req_pks
        assert quote_b.pk not in quote_pks

    def test_goodsreceiptnote_form_bill_and_po_fields_exclude_other_tenant(
        self, tenant_a, purchase_order_b, bill_b,
    ):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(tenant=tenant_a)
        po_pks = set(form.fields["purchase_order"].queryset.values_list("pk", flat=True))
        bill_pks = set(form.fields["bill"].queryset.values_list("pk", flat=True))
        assert purchase_order_b.pk not in po_pks
        assert bill_b.pk not in bill_pks

    def test_goodsreceiptline_formset_po_line_rejects_a_foreign_order_line(
        self, tenant_a, purchase_order_a, purchase_order_b,
    ):
        """_scope_to_parent: po_line choices come from the receipt's OWN order only — a
        line from a DIFFERENT (here, another tenant's) order must be rejected outright,
        not merely hidden from the rendered dropdown."""
        from apps.scm.forms import GoodsReceiptLineFormSet
        foreign_line = purchase_order_b.lines.first()
        data = formset_data("lines", [
            {"id": "", "po_line": foreign_line.pk, "quantity_received": "1",
             "quantity_rejected": "0", "rejection_reason": "", "notes": ""},
        ])
        formset = GoodsReceiptLineFormSet(
            data=data, instance=None, purchase_order=purchase_order_a, form_kwargs={"tenant": tenant_a},
        )
        assert formset.is_valid() is False
        assert "po_line" in formset.forms[0].errors

    def test_rfqquoteline_formset_rfq_line_rejects_a_foreign_rfq_line(
        self, tenant_a, rfq_sent_a, quote_a, rfq_b,
    ):
        """_scope_to_parent: rfq_line choices come from the quote's OWN rfq only."""
        from apps.scm.models import RFQLine
        from apps.scm.forms import RFQQuoteLineFormSet
        foreign_line = RFQLine.objects.create(rfq=rfq_b, item_description="Globex thing", quantity=Decimal("1"))
        data = formset_data("lines", [
            {"id": "", "rfq_line": foreign_line.pk, "quantity": "1", "unit_price": "10.00",
             "lead_time_days": "", "note": ""},
        ])
        formset = RFQQuoteLineFormSet(
            data=data, instance=quote_a, rfq=rfq_sent_a, form_kwargs={"tenant": tenant_a},
        )
        assert formset.is_valid() is False
        assert "rfq_line" in formset.forms[0].errors


# ================================================================ POST-only action views: GET -> 405
class TestPostOnlyActions:
    def test_get_requisition_delete_returns_405(self, client_a, requisition_a):
        assert client_a.get(reverse("scm:requisition_delete", args=[requisition_a.pk])).status_code == 405

    def test_get_requisition_approve_returns_405(self, client_a, requisition_pending_a):
        assert client_a.get(reverse("scm:requisition_approve", args=[requisition_pending_a.pk])).status_code == 405

    def test_get_purchaseorder_delete_returns_405(self, client_a, tenant_a, supplier_a):
        from apps.scm.models import PurchaseOrder
        po = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, status="draft")
        assert client_a.get(reverse("scm:purchaseorder_delete", args=[po.pk])).status_code == 405

    def test_get_purchaseorder_cancel_returns_405(self, client_a, purchase_order_a):
        assert client_a.get(reverse("scm:purchaseorder_cancel", args=[purchase_order_a.pk])).status_code == 405

    def test_get_goodsreceipt_receive_returns_405(self, client_a, goods_receipt_a):
        assert client_a.get(reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk])).status_code == 405

    def test_get_quote_award_returns_405(self, client_a, quote_a):
        assert client_a.get(reverse("scm:quote_award", args=[quote_a.pk])).status_code == 405
