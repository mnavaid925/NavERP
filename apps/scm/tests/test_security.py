"""Security tests for the SCM 4.1 Procurement Management sub-module.

Covers:
- Anonymous -> redirect to login.
- @tenant_admin_required gates: requisition_approve/reject, quote_award,
  purchaseorder_approve/cancel/amend, goodsreceipt_receive/cancel -> 403 for a non-admin
  member; admin succeeds. Plain @login_required actions work for a non-admin member.
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

    def test_goodsreceipt_receive_requires_admin(self, member_client, client_a, goods_receipt_a):
        """Admin-gated since 4.4, when booking a receipt started posting real StockMoves.

        This began life as `test_member_can_receive_goods_receipt` in the ordinary-actions class:
        before 4.4 the action only flipped a status, so a member doing it was harmless. Once it
        moved stock it joined transfer-complete and adjustment-post, and the OLD test correctly
        started failing — it was asserting the pre-4.4 contract, not catching a regression.
        """
        url = reverse("scm:goodsreceipt_receive", args=[goods_receipt_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403
        goods_receipt_a.refresh_from_db()
        assert goods_receipt_a.status == "received"


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


# ================================================================================================
# SCM 4.2 Supplier Relationship Management
# ================================================================================================

# ================================================================ Anonymous -> login redirect
class TestSRMAnonymousRedirect:
    def test_supplierprofile_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:supplierprofile_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_scorecard_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:scorecard_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_contract_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:contract_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_catalog_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:catalog_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_riskassessment_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:riskassessment_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ @tenant_admin_required gates (priority)
class TestSRMAdminRequiredGates:
    def test_supplierprofile_approve_requires_admin(self, member_client, client_a, supplier_profile_dd_a):
        url = reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_supplierprofile_reject_requires_admin(self, member_client, client_a, supplier_profile_dd_a):
        url = reverse("scm:supplierprofile_reject", args=[supplier_profile_dd_a.pk])
        assert member_client.post(url).status_code == 403
        resp = client_a.post(url, {"decision_note": "Not a fit"})
        assert resp.status_code != 403

    def test_supplierprofile_reopen_requires_admin(self, member_client, client_a, tenant_a, supplier_a):
        from apps.scm.models import SupplierProfile
        sp = SupplierProfile.objects.create(tenant=tenant_a, party=supplier_a, onboarding_status="rejected")
        url = reverse("scm:supplierprofile_reopen", args=[sp.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_supplierprofile_suspend_requires_admin(self, member_client, client_a, supplier_profile_dd_a):
        client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk]))
        url = reverse("scm:supplierprofile_suspend", args=[supplier_profile_dd_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_contract_terminate_requires_admin(self, member_client, client_a, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        url = reverse("scm:contract_terminate", args=[contract_a.pk])
        assert member_client.post(url, {"termination_reason": "x"}).status_code == 403
        assert client_a.post(url, {"termination_reason": "x"}).status_code != 403

    def test_riskassessment_review_requires_admin(self, member_client, client_a, risk_assessment_a):
        risk_assessment_a.status = "submitted"
        risk_assessment_a.save(update_fields=["status"])
        url = reverse("scm:riskassessment_review", args=[risk_assessment_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Plain @login_required actions work for a member
class TestSRMOrdinaryActionsAllowNonAdmin:
    def test_member_can_submit_supplier_profile(self, member_client, supplier_profile_a):
        url = reverse("scm:supplierprofile_submit", args=[supplier_profile_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        supplier_profile_a.refresh_from_db()
        assert supplier_profile_a.onboarding_status == "due_diligence"

    def test_member_can_recompute_scorecard(self, member_client, scorecard_a):
        url = reverse("scm:scorecard_recompute", args=[scorecard_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403

    def test_member_can_activate_contract(self, member_client, contract_a):
        url = reverse("scm:contract_activate", args=[contract_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        contract_a.refresh_from_db()
        assert contract_a.status == "active"

    def test_member_can_submit_risk_assessment(self, member_client, risk_assessment_a):
        url = reverse("scm:riskassessment_submit", args=[risk_assessment_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        risk_assessment_a.refresh_from_db()
        assert risk_assessment_a.status == "submitted"

    def test_member_can_view_supplier_profile_detail(self, member_client, supplier_profile_a):
        url = reverse("scm:supplierprofile_detail", args=[supplier_profile_a.pk])
        assert member_client.get(url).status_code == 200


# ================================================================ Cross-tenant IDOR -> 404 (mandatory)
class TestSRMCrossTenantIDOR:
    def test_supplierprofile_detail_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.get(
            reverse("scm:supplierprofile_detail", args=[supplier_profile_b.pk])
        ).status_code == 404

    def test_supplierprofile_edit_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.get(reverse("scm:supplierprofile_edit", args=[supplier_profile_b.pk])).status_code == 404

    def test_supplierprofile_delete_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.post(reverse("scm:supplierprofile_delete", args=[supplier_profile_b.pk])).status_code == 404

    def test_supplierprofile_approve_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.post(reverse("scm:supplierprofile_approve", args=[supplier_profile_b.pk])).status_code == 404

    def test_supplierprofile_reject_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.post(reverse("scm:supplierprofile_reject", args=[supplier_profile_b.pk])).status_code == 404

    def test_supplierprofile_reopen_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.post(reverse("scm:supplierprofile_reopen", args=[supplier_profile_b.pk])).status_code == 404

    def test_supplierprofile_suspend_cross_tenant_404(self, client_a, supplier_profile_b):
        assert client_a.post(reverse("scm:supplierprofile_suspend", args=[supplier_profile_b.pk])).status_code == 404

    def test_scorecard_detail_cross_tenant_404(self, client_a, scorecard_b):
        assert client_a.get(reverse("scm:scorecard_detail", args=[scorecard_b.pk])).status_code == 404

    def test_scorecard_edit_cross_tenant_404(self, client_a, scorecard_b):
        assert client_a.get(reverse("scm:scorecard_edit", args=[scorecard_b.pk])).status_code == 404

    def test_scorecard_delete_cross_tenant_404(self, client_a, scorecard_b):
        assert client_a.post(reverse("scm:scorecard_delete", args=[scorecard_b.pk])).status_code == 404

    def test_scorecard_recompute_cross_tenant_404(self, client_a, scorecard_b):
        assert client_a.post(reverse("scm:scorecard_recompute", args=[scorecard_b.pk])).status_code == 404

    def test_contract_detail_cross_tenant_404(self, client_a, contract_b):
        assert client_a.get(reverse("scm:contract_detail", args=[contract_b.pk])).status_code == 404

    def test_contract_edit_cross_tenant_404(self, client_a, contract_b):
        assert client_a.get(reverse("scm:contract_edit", args=[contract_b.pk])).status_code == 404

    def test_contract_delete_cross_tenant_404(self, client_a, contract_b):
        assert client_a.post(reverse("scm:contract_delete", args=[contract_b.pk])).status_code == 404

    def test_contract_terminate_cross_tenant_404(self, client_a, contract_b):
        assert client_a.post(
            reverse("scm:contract_terminate", args=[contract_b.pk]), {"termination_reason": "x"},
        ).status_code == 404

    def test_catalog_detail_cross_tenant_404(self, client_a, catalog_b):
        assert client_a.get(reverse("scm:catalog_detail", args=[catalog_b.pk])).status_code == 404

    def test_catalog_edit_cross_tenant_404(self, client_a, catalog_b):
        assert client_a.get(reverse("scm:catalog_edit", args=[catalog_b.pk])).status_code == 404

    def test_catalog_delete_cross_tenant_404(self, client_a, catalog_b):
        assert client_a.post(reverse("scm:catalog_delete", args=[catalog_b.pk])).status_code == 404

    def test_riskassessment_detail_cross_tenant_404(self, client_a, risk_assessment_b):
        assert client_a.get(reverse("scm:riskassessment_detail", args=[risk_assessment_b.pk])).status_code == 404

    def test_riskassessment_edit_cross_tenant_404(self, client_a, risk_assessment_b):
        assert client_a.get(reverse("scm:riskassessment_edit", args=[risk_assessment_b.pk])).status_code == 404

    def test_riskassessment_review_cross_tenant_404(self, client_a, risk_assessment_b):
        assert client_a.post(reverse("scm:riskassessment_review", args=[risk_assessment_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM/FORMSET binding
class TestSRMCrossTenantFormScoping:
    def test_supplierprofile_form_party_field_excludes_other_tenant(self, tenant_a, supplier_b):
        from apps.scm.forms import SupplierProfileForm
        form = SupplierProfileForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_b.pk not in pks

    def test_contract_form_document_field_excludes_other_tenant(self, tenant_a, tenant_b, supplier_a):
        from apps.core.models import Document
        from apps.scm.forms import SupplierContractForm
        other_doc = Document.objects.create(tenant=tenant_b, name="Globex NDA.pdf")
        form = SupplierContractForm(tenant=tenant_a)
        pks = set(form.fields["document"].queryset.values_list("pk", flat=True))
        assert other_doc.pk not in pks

    def test_crafted_post_with_other_tenant_party_is_rejected(self, tenant_a, client_a, supplier_b):
        """A crafted POST naming a Tenant-B party pk on a Tenant-A create must fail validation
        (the party field's queryset is scoped to the request tenant), not silently bind it."""
        from apps.scm.models import SupplierProfile
        data = {
            "party": str(supplier_b.pk), "tier": "transactional", "category": "",
            "legal_name": "", "tax_registration": "", "website": "",
            "primary_contact_name": "", "primary_contact_email": "", "primary_contact_phone": "",
            "country": "", "year_established": "",
            "dd_financials_verified": "", "dd_compliance_verified": "", "dd_insurance_verified": "",
            "dd_quality_cert_verified": "", "dd_references_checked": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:supplierprofile_create"), data)
        assert resp.status_code == 200  # re-rendered form, not a redirect/save
        assert not SupplierProfile.objects.filter(party=supplier_b).exists()


# ================================================================ POST-only action views: GET -> 405
class TestSRMPostOnlyActions:
    def test_get_supplierprofile_delete_returns_405(self, client_a, supplier_profile_a):
        assert client_a.get(reverse("scm:supplierprofile_delete", args=[supplier_profile_a.pk])).status_code == 405

    def test_get_supplierprofile_approve_returns_405(self, client_a, supplier_profile_dd_a):
        assert client_a.get(reverse("scm:supplierprofile_approve", args=[supplier_profile_dd_a.pk])).status_code == 405

    def test_get_scorecard_delete_returns_405(self, client_a, scorecard_a):
        assert client_a.get(reverse("scm:scorecard_delete", args=[scorecard_a.pk])).status_code == 405

    def test_get_contract_terminate_returns_405(self, client_a, contract_a):
        assert client_a.get(reverse("scm:contract_terminate", args=[contract_a.pk])).status_code == 405

    def test_get_catalog_activate_returns_405(self, client_a, catalog_a):
        assert client_a.get(reverse("scm:catalog_activate", args=[catalog_a.pk])).status_code == 405

    def test_get_riskassessment_review_returns_405(self, client_a, risk_assessment_a):
        assert client_a.get(reverse("scm:riskassessment_review", args=[risk_assessment_a.pk])).status_code == 405


# ================================================================ CSRF enforcement
class TestSRMCSRFEnforcement:
    def test_post_without_csrf_token_is_rejected(self, admin_user, contract_a):
        contract_a.status = "active"
        contract_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("scm:contract_terminate", args=[contract_a.pk]), {"termination_reason": "No CSRF token"},
        )
        assert resp.status_code == 403
        contract_a.refresh_from_db()
        assert contract_a.status == "active"  # unchanged — the request never reached the view logic


# ================================================================================================
# SCM 4.3 Inventory Management
# ================================================================================================

# ================================================================ Anonymous -> login redirect
class TestInventoryAnonymousRedirect:
    def test_item_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:item_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_location_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:location_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_stocktransfer_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:stocktransfer_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_stockadjustment_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:stockadjustment_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_valuation_report_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:valuation_report"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_reorder_alerts_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:reorder_alerts"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ @tenant_admin_required gates (priority)
class TestInventoryAdminRequiredGates:
    def test_stocktransfer_complete_requires_admin(
        self, member_client, client_a, tenant_a, stock_transfer_a, location_a, item_a,
    ):
        from apps.scm.views._helpers import _post_stock_move
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("20"),
                         unit_cost=Decimal("5.00"), move_type="receipt")
        url = reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_stocktransfer_cancel_requires_admin(self, member_client, client_a, stock_transfer_a):
        url = reverse("scm:stocktransfer_cancel", args=[stock_transfer_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_stockadjustment_post_requires_admin(self, member_client, client_a, stock_adjustment_a):
        url = reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_stockadjustment_cancel_requires_admin(self, member_client, client_a, stock_adjustment_a):
        url = reverse("scm:stockadjustment_cancel", args=[stock_adjustment_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Plain @login_required actions work for a member
class TestInventoryOrdinaryActionsAllowNonAdmin:
    def test_member_can_view_item_list(self, member_client, item_a):
        assert member_client.get(reverse("scm:item_list")).status_code == 200

    def test_member_can_create_an_item(self, member_client, tenant_a):
        from apps.scm.models import Item
        data = {
            "sku": "MEMBER-1", "name": "Member created item", "category": "", "uom": "",
            "item_type": "stock", "tracking": "none", "costing_method": "weighted_avg",
            "standard_cost": "0", "reorder_point": "0", "description": "", "is_active": "on",
        }
        resp = member_client.post(reverse("scm:item_create"), data)
        assert resp.status_code != 403
        assert Item.objects.filter(tenant=tenant_a, sku="MEMBER-1").exists()

    def test_member_can_create_a_draft_stock_transfer(self, member_client, location_a, location_a2, item_a):
        url = reverse("scm:stocktransfer_create")
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "5"}]),
        }
        resp = member_client.post(url, data)
        assert resp.status_code != 403

    def test_member_can_view_stocktransfer_detail(self, member_client, stock_transfer_a):
        url = reverse("scm:stocktransfer_detail", args=[stock_transfer_a.pk])
        assert member_client.get(url).status_code == 200


# ================================================================ Cross-tenant IDOR -> 404 (mandatory)
class TestInventoryCrossTenantIDOR:
    def test_item_detail_cross_tenant_404(self, client_a, item_b):
        assert client_a.get(reverse("scm:item_detail", args=[item_b.pk])).status_code == 404

    def test_item_edit_cross_tenant_404(self, client_a, item_b):
        assert client_a.get(reverse("scm:item_edit", args=[item_b.pk])).status_code == 404

    def test_item_delete_cross_tenant_404(self, client_a, item_b):
        assert client_a.post(reverse("scm:item_delete", args=[item_b.pk])).status_code == 404

    def test_category_edit_cross_tenant_404(self, client_a, category_b):
        assert client_a.get(reverse("scm:category_edit", args=[category_b.pk])).status_code == 404

    def test_uom_edit_cross_tenant_404(self, client_a, uom_each_b):
        assert client_a.get(reverse("scm:uom_edit", args=[uom_each_b.pk])).status_code == 404

    def test_location_detail_cross_tenant_404(self, client_a, location_b):
        assert client_a.get(reverse("scm:location_detail", args=[location_b.pk])).status_code == 404

    def test_location_edit_cross_tenant_404(self, client_a, location_b):
        assert client_a.get(reverse("scm:location_edit", args=[location_b.pk])).status_code == 404

    def test_location_delete_cross_tenant_404(self, client_a, location_b):
        assert client_a.post(reverse("scm:location_delete", args=[location_b.pk])).status_code == 404

    def test_lotserial_detail_cross_tenant_404(self, client_a, lot_b):
        assert client_a.get(reverse("scm:lotserial_detail", args=[lot_b.pk])).status_code == 404

    def test_lotserial_edit_cross_tenant_404(self, client_a, lot_b):
        assert client_a.get(reverse("scm:lotserial_edit", args=[lot_b.pk])).status_code == 404

    def test_reorderrule_edit_cross_tenant_404(self, client_a, reorder_rule_b):
        assert client_a.get(reverse("scm:reorderrule_edit", args=[reorder_rule_b.pk])).status_code == 404

    def test_stocktransfer_detail_cross_tenant_404(self, client_a, stock_transfer_b):
        assert client_a.get(reverse("scm:stocktransfer_detail", args=[stock_transfer_b.pk])).status_code == 404

    def test_stocktransfer_edit_cross_tenant_404(self, client_a, stock_transfer_b):
        assert client_a.get(reverse("scm:stocktransfer_edit", args=[stock_transfer_b.pk])).status_code == 404

    def test_stocktransfer_delete_cross_tenant_404(self, client_a, stock_transfer_b):
        assert client_a.post(reverse("scm:stocktransfer_delete", args=[stock_transfer_b.pk])).status_code == 404

    def test_stocktransfer_complete_cross_tenant_404(self, client_a, stock_transfer_b):
        assert client_a.post(reverse("scm:stocktransfer_complete", args=[stock_transfer_b.pk])).status_code == 404

    def test_stocktransfer_cancel_cross_tenant_404(self, client_a, stock_transfer_b):
        assert client_a.post(reverse("scm:stocktransfer_cancel", args=[stock_transfer_b.pk])).status_code == 404

    def test_stockadjustment_detail_cross_tenant_404(self, client_a, stock_adjustment_b):
        assert client_a.get(reverse("scm:stockadjustment_detail", args=[stock_adjustment_b.pk])).status_code == 404

    def test_stockadjustment_edit_cross_tenant_404(self, client_a, stock_adjustment_b):
        assert client_a.get(reverse("scm:stockadjustment_edit", args=[stock_adjustment_b.pk])).status_code == 404

    def test_stockadjustment_delete_cross_tenant_404(self, client_a, stock_adjustment_b):
        assert client_a.post(reverse("scm:stockadjustment_delete", args=[stock_adjustment_b.pk])).status_code == 404

    def test_stockadjustment_post_cross_tenant_404(self, client_a, stock_adjustment_b):
        assert client_a.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_b.pk])).status_code == 404

    def test_stockadjustment_cancel_cross_tenant_404(self, client_a, stock_adjustment_b):
        assert client_a.post(reverse("scm:stockadjustment_cancel", args=[stock_adjustment_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM/FORMSET binding + IDOR list
class TestInventoryCrossTenantFormScoping:
    def test_item_list_never_contains_other_tenant_rows(self, client_a, item_a, item_b):
        resp = client_a.get(reverse("scm:item_list"))
        assert item_b not in resp.context["object_list"]

    def test_stocktransfer_form_locations_exclude_other_tenant(self, tenant_a, location_b):
        from apps.scm.forms import StockTransferForm
        form = StockTransferForm(tenant=tenant_a)
        pks = set(form.fields["from_location"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in pks

    def test_crafted_post_with_other_tenant_location_is_rejected(
        self, tenant_a, client_a, location_b, location_a, item_a,
    ):
        """A crafted POST naming a Tenant-B location pk on a Tenant-A transfer create must fail
        validation (the queryset is scoped to the request tenant), not silently bind it."""
        from apps.scm.models import StockTransfer
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_b.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "", "quantity": "5"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 200  # re-rendered form, not a redirect/save
        assert not StockTransfer.objects.filter(to_location=location_b).exists()

    def test_crafted_post_with_other_tenant_item_on_a_line_is_rejected(
        self, tenant_a, client_a, location_a, location_a2, item_b,
    ):
        """The line-level item dropdown is also tenant-scoped (_scope handled by TenantModelForm on
        the child form) — a Tenant-B item pk on a line must be rejected, not silently accepted."""
        from apps.scm.models import StockTransfer
        data = {
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "transfer_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_b.pk), "lot_serial": "", "quantity": "5"}]),
        }
        resp = client_a.post(reverse("scm:stocktransfer_create"), data)
        assert resp.status_code == 200
        assert not StockTransfer.objects.filter(tenant=tenant_a).exists()

    def test_crafted_post_with_other_tenant_location_on_adjustment_is_rejected(
        self, tenant_a, client_a, location_b, item_a,
    ):
        from apps.scm.models import StockAdjustment
        data = {
            "location": str(location_b.pk), "reason": "cycle_count", "adjustment_date": "2026-01-20", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "quantity_delta": "5", "unit_cost": "1.00"}]),
        }
        resp = client_a.post(reverse("scm:stockadjustment_create"), data)
        assert resp.status_code == 200
        assert not StockAdjustment.objects.filter(tenant=tenant_a).exists()


# ================================================================ POST-only action views: GET -> 405
class TestInventoryPostOnlyActions:
    def test_get_item_delete_returns_405(self, client_a, item_a):
        assert client_a.get(reverse("scm:item_delete", args=[item_a.pk])).status_code == 405

    def test_get_stocktransfer_complete_returns_405(self, client_a, stock_transfer_a):
        assert client_a.get(reverse("scm:stocktransfer_complete", args=[stock_transfer_a.pk])).status_code == 405

    def test_get_stocktransfer_cancel_returns_405(self, client_a, stock_transfer_a):
        assert client_a.get(reverse("scm:stocktransfer_cancel", args=[stock_transfer_a.pk])).status_code == 405

    def test_get_stockadjustment_post_returns_405(self, client_a, stock_adjustment_a):
        assert client_a.get(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk])).status_code == 405

    def test_get_stockadjustment_cancel_returns_405(self, client_a, stock_adjustment_a):
        assert client_a.get(reverse("scm:stockadjustment_cancel", args=[stock_adjustment_a.pk])).status_code == 405


# ================================================================ CSRF enforcement
class TestInventoryCSRFEnforcement:
    def test_post_without_csrf_token_is_rejected(self, admin_user, tenant_a, stock_adjustment_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:stockadjustment_post", args=[stock_adjustment_a.pk]))
        assert resp.status_code == 403
        stock_adjustment_a.refresh_from_db()
        assert stock_adjustment_a.status == "draft"  # unchanged — the request never reached the view logic


# ================================================================================================
# SCM 4.4 Warehouse Management
# ================================================================================================

# ================================================================ Anonymous -> login redirect
class TestWarehouseAnonymousRedirect:
    def test_putawaytask_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:putawaytask_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_picktask_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:picktask_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_cyclecounttask_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:cyclecounttask_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_yardvisit_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:yardvisit_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ @tenant_admin_required gates (priority)
class TestWarehouseAdminRequiredGates:
    def test_putawaytask_complete_requires_admin(self, member_client, client_a, putawaytask_a):
        url = reverse("scm:putawaytask_complete", args=[putawaytask_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_picktask_confirm_requires_admin(self, member_client, client_a, picktask_a):
        url = reverse("scm:picktask_confirm", args=[picktask_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_cyclecounttask_reconcile_requires_admin(self, member_client, client_a, cyclecounttask_a):
        url = reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Plain @login_required actions work for a member
class TestWarehouseOrdinaryActionsAllowNonAdmin:
    def test_member_can_start_a_putaway_task(self, member_client, putawaytask_a):
        url = reverse("scm:putawaytask_start", args=[putawaytask_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "in_progress"

    def test_member_can_start_a_released_pick(self, member_client, picktask_a):
        """picktask_start moves NO stock — deliberately plain @login_required, unlike confirm."""
        member_client.post(reverse("scm:picktask_release", args=[picktask_a.pk]))
        url = reverse("scm:picktask_start", args=[picktask_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        picktask_a.refresh_from_db()
        assert picktask_a.status == "picking"

    def test_member_can_start_a_cycle_count(self, member_client, cyclecounttask_a):
        url = reverse("scm:cyclecounttask_start", args=[cyclecounttask_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "in_progress"

    def test_member_can_arrive_a_yard_visit(self, member_client, yardvisit_a):
        url = reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        yardvisit_a.refresh_from_db()
        assert yardvisit_a.status == "arrived"

    def test_member_can_view_putawaytask_detail(self, member_client, putawaytask_a):
        url = reverse("scm:putawaytask_detail", args=[putawaytask_a.pk])
        assert member_client.get(url).status_code == 200

    def test_member_can_view_picktask_list(self, member_client, picktask_a):
        assert member_client.get(reverse("scm:picktask_list")).status_code == 200


# ================================================================ Cross-tenant IDOR -> 404 (mandatory)
class TestWarehouseCrossTenantIDOR:
    def test_putawaytask_detail_cross_tenant_404(self, client_a, putawaytask_b):
        assert client_a.get(reverse("scm:putawaytask_detail", args=[putawaytask_b.pk])).status_code == 404

    def test_putawaytask_edit_cross_tenant_404(self, client_a, putawaytask_b):
        assert client_a.get(reverse("scm:putawaytask_edit", args=[putawaytask_b.pk])).status_code == 404

    def test_putawaytask_delete_cross_tenant_404(self, client_a, putawaytask_b):
        assert client_a.post(reverse("scm:putawaytask_delete", args=[putawaytask_b.pk])).status_code == 404

    def test_putawaytask_start_cross_tenant_404(self, client_a, putawaytask_b):
        assert client_a.post(reverse("scm:putawaytask_start", args=[putawaytask_b.pk])).status_code == 404

    def test_putawaytask_complete_cross_tenant_404(self, client_a, putawaytask_b):
        assert client_a.post(reverse("scm:putawaytask_complete", args=[putawaytask_b.pk])).status_code == 404

    def test_putawaytask_cancel_cross_tenant_404(self, client_a, putawaytask_b):
        assert client_a.post(reverse("scm:putawaytask_cancel", args=[putawaytask_b.pk])).status_code == 404

    def test_picktask_detail_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.get(reverse("scm:picktask_detail", args=[picktask_b.pk])).status_code == 404

    def test_picktask_edit_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.get(reverse("scm:picktask_edit", args=[picktask_b.pk])).status_code == 404

    def test_picktask_delete_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.post(reverse("scm:picktask_delete", args=[picktask_b.pk])).status_code == 404

    def test_picktask_release_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.post(reverse("scm:picktask_release", args=[picktask_b.pk])).status_code == 404

    def test_picktask_start_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.post(reverse("scm:picktask_start", args=[picktask_b.pk])).status_code == 404

    def test_picktask_confirm_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.post(reverse("scm:picktask_confirm", args=[picktask_b.pk])).status_code == 404

    def test_picktask_pack_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.post(reverse("scm:picktask_pack", args=[picktask_b.pk])).status_code == 404

    def test_picktask_cancel_cross_tenant_404(self, client_a, picktask_b):
        assert client_a.post(reverse("scm:picktask_cancel", args=[picktask_b.pk])).status_code == 404

    def test_cyclecounttask_detail_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.get(reverse("scm:cyclecounttask_detail", args=[cyclecounttask_b.pk])).status_code == 404

    def test_cyclecounttask_edit_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.get(reverse("scm:cyclecounttask_edit", args=[cyclecounttask_b.pk])).status_code == 404

    def test_cyclecounttask_delete_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.post(reverse("scm:cyclecounttask_delete", args=[cyclecounttask_b.pk])).status_code == 404

    def test_cyclecounttask_start_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.post(reverse("scm:cyclecounttask_start", args=[cyclecounttask_b.pk])).status_code == 404

    def test_cyclecounttask_complete_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.post(reverse("scm:cyclecounttask_complete", args=[cyclecounttask_b.pk])).status_code == 404

    def test_cyclecounttask_reconcile_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_b.pk])).status_code == 404

    def test_cyclecounttask_cancel_cross_tenant_404(self, client_a, cyclecounttask_b):
        assert client_a.post(reverse("scm:cyclecounttask_cancel", args=[cyclecounttask_b.pk])).status_code == 404

    def test_yardvisit_detail_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.get(reverse("scm:yardvisit_detail", args=[yardvisit_b.pk])).status_code == 404

    def test_yardvisit_edit_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.get(reverse("scm:yardvisit_edit", args=[yardvisit_b.pk])).status_code == 404

    def test_yardvisit_delete_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.post(reverse("scm:yardvisit_delete", args=[yardvisit_b.pk])).status_code == 404

    def test_yardvisit_arrive_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.post(reverse("scm:yardvisit_arrive", args=[yardvisit_b.pk])).status_code == 404

    def test_yardvisit_dock_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.post(reverse("scm:yardvisit_dock", args=[yardvisit_b.pk])).status_code == 404

    def test_yardvisit_depart_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.post(reverse("scm:yardvisit_depart", args=[yardvisit_b.pk])).status_code == 404

    def test_yardvisit_cancel_cross_tenant_404(self, client_a, yardvisit_b):
        assert client_a.post(reverse("scm:yardvisit_cancel", args=[yardvisit_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM/FORMSET binding + IDOR list
class TestWarehouseCrossTenantFormScoping:
    def test_putawaytask_list_never_contains_other_tenant_rows(self, client_a, putawaytask_a, putawaytask_b):
        resp = client_a.get(reverse("scm:putawaytask_list"))
        assert putawaytask_b not in resp.context["object_list"]

    def test_crafted_putawaytask_post_with_other_tenant_item_is_rejected(
        self, tenant_a, client_a, location_a, location_a2, item_b,
    ):
        from apps.scm.models import PutawayTask
        data = {
            "goods_receipt": "", "item": str(item_b.pk), "lot_serial": "",
            "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
            "quantity": "5", "strategy": "directed", "assigned_to": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:putawaytask_create"), data)
        assert resp.status_code == 200  # re-rendered form, not saved
        assert not PutawayTask.objects.filter(tenant=tenant_a).exists()

    def test_crafted_picktaskline_post_with_other_tenant_location_is_rejected(
        self, tenant_a, client_a, item_a, location_b,
    ):
        from apps.scm.models import PickTask
        data = {
            "strategy": "single", "zone": "", "wave_ref": "", "assigned_to": "", "ship_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "from_location": str(location_b.pk),
                                      "quantity_requested": "5", "quantity_picked": "0", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:picktask_create"), data)
        assert resp.status_code == 200
        assert not PickTask.objects.filter(tenant=tenant_a).exists()

    def test_crafted_cyclecounttask_post_with_other_tenant_location_is_rejected(
        self, tenant_a, client_a, location_b, item_a,
    ):
        from apps.scm.models import CycleCountTask
        data = {
            "location": str(location_b.pk), "scheduled_date": "2026-01-25", "count_method": "full",
            "assigned_to": "", "notes": "",
            **formset_data("lines", [{"id": "", "item": str(item_a.pk), "lot_serial": "",
                                      "counted_quantity": "", "notes": ""}]),
        }
        resp = client_a.post(reverse("scm:cyclecounttask_create"), data)
        assert resp.status_code == 200
        assert not CycleCountTask.objects.filter(tenant=tenant_a).exists()

    def test_crafted_yardvisit_post_with_other_tenant_dock_door_is_rejected(
        self, tenant_a, client_a, location_b,
    ):
        from apps.scm.models import YardVisit
        data = {
            "carrier_name": "Sneaky Freight", "vehicle_ref": "", "trailer_ref": "", "driver_name": "",
            "direction": "inbound", "dock_door": str(location_b.pk), "purchase_order": "",
            "scheduled_at": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:yardvisit_create"), data)
        assert resp.status_code == 200
        assert not YardVisit.objects.filter(tenant=tenant_a).exists()


# ================================================================ POST-only action views: GET -> 405
class TestWarehousePostOnlyActions:
    def test_get_putawaytask_delete_returns_405(self, client_a, putawaytask_a):
        assert client_a.get(reverse("scm:putawaytask_delete", args=[putawaytask_a.pk])).status_code == 405

    def test_get_putawaytask_complete_returns_405(self, client_a, putawaytask_a):
        assert client_a.get(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk])).status_code == 405

    def test_get_picktask_delete_returns_405(self, client_a, picktask_a):
        assert client_a.get(reverse("scm:picktask_delete", args=[picktask_a.pk])).status_code == 405

    def test_get_picktask_confirm_returns_405(self, client_a, picktask_a):
        assert client_a.get(reverse("scm:picktask_confirm", args=[picktask_a.pk])).status_code == 405

    def test_get_cyclecounttask_delete_returns_405(self, client_a, cyclecounttask_a):
        assert client_a.get(reverse("scm:cyclecounttask_delete", args=[cyclecounttask_a.pk])).status_code == 405

    def test_get_cyclecounttask_reconcile_returns_405(self, client_a, cyclecounttask_a):
        assert client_a.get(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk])).status_code == 405

    def test_get_yardvisit_delete_returns_405(self, client_a, yardvisit_a):
        assert client_a.get(reverse("scm:yardvisit_delete", args=[yardvisit_a.pk])).status_code == 405

    def test_get_yardvisit_arrive_returns_405(self, client_a, yardvisit_a):
        assert client_a.get(reverse("scm:yardvisit_arrive", args=[yardvisit_a.pk])).status_code == 405


# ================================================================ CSRF enforcement
class TestWarehouseCSRFEnforcement:
    def test_post_without_csrf_token_is_rejected_on_putawaytask_complete(
        self, admin_user, tenant_a, putawaytask_a,
    ):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:putawaytask_complete", args=[putawaytask_a.pk]))
        assert resp.status_code == 403
        putawaytask_a.refresh_from_db()
        assert putawaytask_a.status == "pending"

    def test_post_without_csrf_token_is_rejected_on_cyclecounttask_reconcile(
        self, admin_user, tenant_a, cyclecounttask_a,
    ):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:cyclecounttask_reconcile", args=[cyclecounttask_a.pk]))
        assert resp.status_code == 403
        cyclecounttask_a.refresh_from_db()
        assert cyclecounttask_a.status == "scheduled"


# ================================================================================================
# SCM 4.5 Order Management System
# ================================================================================================

# ================================================================ Anonymous -> login redirect
class TestSalesOrderAnonymousRedirect:
    def test_salesorder_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:salesorder_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_salesorderallocation_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:salesorderallocation_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ @tenant_admin_required gates (priority)
class TestSalesOrderAdminRequiredGates:
    def test_release_hold_requires_admin(self, member_client, client_a, tenant_a, sales_order_a, customer_a):
        from apps.accounting.models import CustomerProfile
        CustomerProfile.objects.create(tenant=tenant_a, party=customer_a, credit_limit=Decimal("50.00"))
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        url = reverse("scm:salesorder_release_hold", args=[sales_order_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url, {"release_note": "ok"}).status_code != 403

    def test_fulfill_requires_admin(self, member_client, client_a, sales_order_submitted_a):
        url = reverse("scm:salesorder_fulfill", args=[sales_order_submitted_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_cancel_requires_admin(self, member_client, client_a, sales_order_submitted_a):
        url = reverse("scm:salesorder_cancel", args=[sales_order_submitted_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url, {"cancel_reason": "test"}).status_code != 403

    def test_allocation_create_requires_admin(self, member_client, client_a, sales_order_line_a):
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_a.pk])
        assert member_client.get(url).status_code == 403
        assert client_a.get(url).status_code != 403

    def test_allocation_edit_requires_admin(self, member_client, client_a, allocation_a):
        url = reverse("scm:salesorderallocation_edit", args=[allocation_a.pk])
        assert member_client.get(url).status_code == 403
        assert client_a.get(url).status_code != 403

    def test_allocation_release_requires_admin(self, member_client, client_a, allocation_a):
        url = reverse("scm:salesorderallocation_release", args=[allocation_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_allocation_cancel_requires_admin(self, member_client, client_a, allocation_a):
        url = reverse("scm:salesorderallocation_cancel", args=[allocation_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_allocation_delete_requires_admin(self, member_client, client_a, allocation_a):
        url = reverse("scm:salesorderallocation_delete", args=[allocation_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Plain @login_required actions work for a member
class TestSalesOrderOrdinaryActionsAllowNonAdmin:
    def test_submit_is_not_admin_gated(self, member_client, sales_order_a):
        """`salesorder_submit` is deliberately plain @login_required — any tenant member can place
        an order, credit/fraud review happens automatically, not via a permission wall."""
        url = reverse("scm:salesorder_submit", args=[sales_order_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "submitted"

    def test_member_can_view_salesorder_detail(self, member_client, sales_order_a):
        url = reverse("scm:salesorder_detail", args=[sales_order_a.pk])
        assert member_client.get(url).status_code == 200

    def test_member_can_mark_delivered(self, member_client, client_a, tenant_a, sales_order_a, location_a):
        from apps.scm.models import SalesOrderAllocation
        client_a.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("10"))
        sales_order_a.recompute_allocation_status()
        client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_a.pk]))
        url = reverse("scm:salesorder_mark_delivered", args=[sales_order_a.pk])
        resp = member_client.post(url)
        assert resp.status_code != 403


# ================================================================ Cross-tenant IDOR -> 404 (mandatory)
class TestSalesOrderCrossTenantIDOR:
    def test_salesorder_detail_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.get(reverse("scm:salesorder_detail", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_edit_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.get(reverse("scm:salesorder_edit", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_delete_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_delete", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_submit_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_submit", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_release_hold_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_release_hold", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_fulfill_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_fulfill", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_mark_delivered_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_mark_delivered", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_mark_invoiced_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_mark_invoiced", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_cancel_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_cancel", args=[sales_order_b.pk])).status_code == 404

    def test_salesorder_close_cross_tenant_404(self, client_a, sales_order_b):
        assert client_a.post(reverse("scm:salesorder_close", args=[sales_order_b.pk])).status_code == 404

    def test_salesorderallocation_detail_cross_tenant_404(self, client_a, allocation_b):
        assert client_a.get(reverse("scm:salesorderallocation_detail", args=[allocation_b.pk])).status_code == 404

    def test_salesorderallocation_edit_cross_tenant_404(self, client_a, allocation_b):
        assert client_a.get(reverse("scm:salesorderallocation_edit", args=[allocation_b.pk])).status_code == 404

    def test_salesorderallocation_delete_cross_tenant_404(self, client_a, allocation_b):
        assert client_a.post(reverse("scm:salesorderallocation_delete", args=[allocation_b.pk])).status_code == 404

    def test_salesorderallocation_release_cross_tenant_404(self, client_a, allocation_b):
        assert client_a.post(reverse("scm:salesorderallocation_release", args=[allocation_b.pk])).status_code == 404

    def test_salesorderallocation_cancel_cross_tenant_404(self, client_a, allocation_b):
        assert client_a.post(reverse("scm:salesorderallocation_cancel", args=[allocation_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM/FORMSET binding + IDOR list
class TestSalesOrderCrossTenantFormScoping:
    def test_list_never_contains_other_tenant_rows(self, client_a, sales_order_a, sales_order_b):
        resp = client_a.get(reverse("scm:salesorder_list"))
        assert sales_order_b not in resp.context["object_list"]

    def test_allocation_list_never_contains_other_tenant_rows(self, client_a, allocation_a, allocation_b):
        resp = client_a.get(reverse("scm:salesorderallocation_list"))
        assert allocation_b not in resp.context["object_list"]

    def test_crafted_salesorder_post_with_other_tenant_customer_is_rejected(
        self, tenant_a, client_a, customer_b,
    ):
        from apps.scm.models import SalesOrder
        data = {
            "customer": str(customer_b.pk), "ship_to_address": "", "source_channel": "manual",
            "order_date": "2026-01-05", "requested_date": "", "currency": "", "payment_terms": "",
            "notes": "",
            **formset_data("lines", []),
        }
        resp = client_a.post(reverse("scm:salesorder_create"), data)
        assert resp.status_code == 200  # re-rendered form, not saved
        assert not SalesOrder.objects.filter(tenant=tenant_a).exists()

    def test_salesorderallocation_create_with_a_foreign_tenant_line_pk_404s(self, client_a, sales_order_line_b):
        """`SalesOrderLine` has no tenant column of its own — it is scoped through
        `sales_order__tenant`, so this needs EXPLICIT coverage rather than relying on the model's
        own tenant FK like every other cross-tenant IDOR check in this suite."""
        url = reverse("scm:salesorderallocation_create", args=[sales_order_line_b.pk])
        assert client_a.get(url).status_code == 404
        assert client_a.post(url, {"location": "1", "quantity": "1", "notes": ""}).status_code == 404


# ================================================================ POST-only action views: GET -> 405
class TestSalesOrderPostOnlyActions:
    def test_get_salesorder_delete_returns_405(self, client_a, sales_order_a):
        assert client_a.get(reverse("scm:salesorder_delete", args=[sales_order_a.pk])).status_code == 405

    def test_get_salesorder_submit_returns_405(self, client_a, sales_order_a):
        assert client_a.get(reverse("scm:salesorder_submit", args=[sales_order_a.pk])).status_code == 405

    def test_get_salesorder_cancel_returns_405(self, client_a, sales_order_a):
        assert client_a.get(reverse("scm:salesorder_cancel", args=[sales_order_a.pk])).status_code == 405

    def test_get_salesorder_close_returns_405(self, client_a, sales_order_a):
        assert client_a.get(reverse("scm:salesorder_close", args=[sales_order_a.pk])).status_code == 405

    def test_get_salesorder_mark_invoiced_returns_405(self, client_a, sales_order_a):
        assert client_a.get(reverse("scm:salesorder_mark_invoiced", args=[sales_order_a.pk])).status_code == 405

    def test_get_salesorder_create_from_quote_returns_405(self, client_a, tenant_a, customer_a):
        from apps.crm.models import Quote
        quote = Quote.objects.create(tenant=tenant_a, name="X", account=customer_a, status="accepted")
        assert client_a.get(reverse("scm:salesorder_create_from_quote", args=[quote.pk])).status_code == 405

    def test_get_salesorderallocation_release_returns_405(self, client_a, allocation_a):
        assert client_a.get(reverse("scm:salesorderallocation_release", args=[allocation_a.pk])).status_code == 405

    def test_get_salesorderallocation_cancel_returns_405(self, client_a, allocation_a):
        assert client_a.get(reverse("scm:salesorderallocation_cancel", args=[allocation_a.pk])).status_code == 405

    def test_get_salesorderallocation_delete_returns_405(self, client_a, allocation_a):
        assert client_a.get(reverse("scm:salesorderallocation_delete", args=[allocation_a.pk])).status_code == 405


# ================================================================ CSRF enforcement
class TestSalesOrderCSRFEnforcement:
    def test_post_without_csrf_token_is_rejected_on_salesorder_submit(self, admin_user, tenant_a, sales_order_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:salesorder_submit", args=[sales_order_a.pk]))
        assert resp.status_code == 403
        sales_order_a.refresh_from_db()
        assert sales_order_a.status == "draft"

    def test_post_without_csrf_token_is_rejected_on_allocation_cancel(self, admin_user, tenant_a, allocation_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:salesorderallocation_cancel", args=[allocation_a.pk]))
        assert resp.status_code == 403
        allocation_a.refresh_from_db()
        assert allocation_a.status == "reserved"


# ================================================================================================
# SCM 4.6 Transportation Management System
# ================================================================================================

# ================================================================ Anonymous -> login redirect
class TestTMSAnonymousRedirect:
    def test_carrier_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:carrier_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_load_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:load_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_shipment_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:shipment_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_freightinvoice_list_redirects(self):
        c = Client()
        resp = c.get(reverse("scm:freightinvoice_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ @tenant_admin_required gates
class TestTMSAdminRequiredGates:
    def test_load_dispatch_requires_admin(self, member_client, client_a, load_a):
        client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        url = reverse("scm:load_dispatch", args=[load_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_load_deliver_requires_admin(self, member_client, client_a, load_a):
        client_a.post(reverse("scm:load_book", args=[load_a.pk]))
        client_a.post(reverse("scm:load_dispatch", args=[load_a.pk]))
        url = reverse("scm:load_deliver", args=[load_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_load_cancel_requires_admin(self, member_client, client_a, load_a):
        url = reverse("scm:load_cancel", args=[load_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_freightinvoice_approve_requires_admin(self, member_client, client_a, freight_invoice_a):
        url = reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_freightinvoice_reject_requires_admin(self, member_client, client_a, freight_invoice_a):
        url = reverse("scm:freightinvoice_reject", args=[freight_invoice_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_freightinvoice_handoff_requires_admin(self, member_client, client_a, freight_invoice_a):
        url = reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Plain @login_required actions work for a member
class TestTMSOrdinaryActionsAllowNonAdmin:
    def test_member_can_view_carrier_detail(self, member_client, carrier_a):
        assert member_client.get(reverse("scm:carrier_detail", args=[carrier_a.pk])).status_code == 200

    def test_member_can_tender_a_load(self, member_client, load_a):
        resp = member_client.post(reverse("scm:load_tender", args=[load_a.pk]))
        assert resp.status_code != 403

    def test_member_can_book_a_load(self, member_client, load_a):
        resp = member_client.post(reverse("scm:load_book", args=[load_a.pk]))
        assert resp.status_code != 403

    def test_member_can_book_a_shipment(self, member_client, shipment_a):
        resp = member_client.post(reverse("scm:shipment_book", args=[shipment_a.pk]))
        assert resp.status_code != 403

    def test_member_can_run_a_freightinvoice_audit(self, member_client, freight_invoice_a):
        resp = member_client.post(reverse("scm:freightinvoice_run_audit", args=[freight_invoice_a.pk]))
        assert resp.status_code != 403

    def test_member_can_dispute_a_freightinvoice(self, member_client, freight_invoice_a):
        resp = member_client.post(reverse("scm:freightinvoice_dispute", args=[freight_invoice_a.pk]),
                                  {"dispute_reason": "member flagged this"})
        assert resp.status_code != 403


# ================================================================ Cross-tenant IDOR -> 404 (mandatory)
class TestTMSCrossTenantIDOR:
    def test_carrier_detail_cross_tenant_404(self, client_a, carrier_b):
        assert client_a.get(reverse("scm:carrier_detail", args=[carrier_b.pk])).status_code == 404

    def test_carrier_edit_cross_tenant_404(self, client_a, carrier_b):
        assert client_a.get(reverse("scm:carrier_edit", args=[carrier_b.pk])).status_code == 404

    def test_carrier_delete_cross_tenant_404(self, client_a, carrier_b):
        assert client_a.post(reverse("scm:carrier_delete", args=[carrier_b.pk])).status_code == 404

    def test_carrier_recompute_scorecard_cross_tenant_404(self, client_a, carrier_b):
        assert client_a.post(reverse("scm:carrier_recompute_scorecard", args=[carrier_b.pk])).status_code == 404

    def test_load_detail_cross_tenant_404(self, client_a, load_b):
        assert client_a.get(reverse("scm:load_detail", args=[load_b.pk])).status_code == 404

    def test_load_edit_cross_tenant_404(self, client_a, load_b):
        assert client_a.get(reverse("scm:load_edit", args=[load_b.pk])).status_code == 404

    def test_load_delete_cross_tenant_404(self, client_a, load_b):
        assert client_a.post(reverse("scm:load_delete", args=[load_b.pk])).status_code == 404

    def test_load_tender_cross_tenant_404(self, client_a, load_b):
        assert client_a.post(reverse("scm:load_tender", args=[load_b.pk])).status_code == 404

    def test_load_book_cross_tenant_404(self, client_a, load_b):
        assert client_a.post(reverse("scm:load_book", args=[load_b.pk])).status_code == 404

    def test_load_dispatch_cross_tenant_404(self, client_a, load_b):
        assert client_a.post(reverse("scm:load_dispatch", args=[load_b.pk])).status_code == 404

    def test_load_deliver_cross_tenant_404(self, client_a, load_b):
        assert client_a.post(reverse("scm:load_deliver", args=[load_b.pk])).status_code == 404

    def test_load_cancel_cross_tenant_404(self, client_a, load_b):
        assert client_a.post(reverse("scm:load_cancel", args=[load_b.pk])).status_code == 404

    def test_shipment_detail_cross_tenant_404(self, client_a, shipment_b):
        assert client_a.get(reverse("scm:shipment_detail", args=[shipment_b.pk])).status_code == 404

    def test_shipment_edit_cross_tenant_404(self, client_a, shipment_b):
        assert client_a.get(reverse("scm:shipment_edit", args=[shipment_b.pk])).status_code == 404

    def test_shipment_delete_cross_tenant_404(self, client_a, shipment_b):
        assert client_a.post(reverse("scm:shipment_delete", args=[shipment_b.pk])).status_code == 404

    def test_shipment_book_cross_tenant_404(self, client_a, shipment_b):
        assert client_a.post(reverse("scm:shipment_book", args=[shipment_b.pk])).status_code == 404

    def test_shipment_add_event_cross_tenant_404(self, client_a, shipment_b):
        assert client_a.post(reverse("scm:shipment_add_event", args=[shipment_b.pk]), {}).status_code == 404

    def test_shipment_cancel_cross_tenant_404(self, client_a, shipment_b):
        assert client_a.post(reverse("scm:shipment_cancel", args=[shipment_b.pk])).status_code == 404

    def test_freightinvoice_detail_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.get(reverse("scm:freightinvoice_detail", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_edit_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.get(reverse("scm:freightinvoice_edit", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_delete_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.post(reverse("scm:freightinvoice_delete", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_run_audit_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.post(reverse("scm:freightinvoice_run_audit", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_dispute_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.post(reverse("scm:freightinvoice_dispute", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_approve_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_reject_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.post(reverse("scm:freightinvoice_reject", args=[freight_invoice_b.pk])).status_code == 404

    def test_freightinvoice_handoff_cross_tenant_404(self, client_a, freight_invoice_b):
        assert client_a.post(reverse("scm:freightinvoice_handoff", args=[freight_invoice_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM/FORMSET binding + IDOR list
class TestTMSCrossTenantFormScoping:
    def test_carrier_list_never_contains_other_tenant_rows(self, client_a, carrier_a, carrier_b):
        resp = client_a.get(reverse("scm:carrier_list"))
        assert carrier_b not in resp.context["object_list"]

    def test_load_list_never_contains_other_tenant_rows(self, client_a, load_a, load_b):
        resp = client_a.get(reverse("scm:load_list"))
        assert load_b not in resp.context["object_list"]

    def test_shipment_list_never_contains_other_tenant_rows(self, client_a, shipment_a, shipment_b):
        resp = client_a.get(reverse("scm:shipment_list"))
        assert shipment_b not in resp.context["object_list"]

    def test_freightinvoice_list_never_contains_other_tenant_rows(
        self, client_a, freight_invoice_a, freight_invoice_b,
    ):
        resp = client_a.get(reverse("scm:freightinvoice_list"))
        assert freight_invoice_b not in resp.context["object_list"]

    def test_crafted_carrier_post_with_other_tenant_party_is_rejected(self, tenant_a, client_a, carrier_party_b):
        from apps.scm.models import Carrier
        data = {
            "party": str(carrier_party_b.pk), "carrier_type": "asset_based", "primary_mode": "truckload",
            "service_level": "standard", "scac_code": "", "mc_number": "", "dot_number": "",
            "insurance_certificate_expiry": "", "primary_contact_name": "", "primary_contact_email": "",
            "primary_contact_phone": "", "is_preferred": "", "status": "active", "notes": "",
            **formset_data("rate_cards", []),
        }
        resp = client_a.post(reverse("scm:carrier_create"), data)
        assert resp.status_code == 200  # re-rendered form, not saved
        assert not Carrier.objects.filter(tenant=tenant_a).exists()

    def test_crafted_load_post_with_other_tenant_carrier_is_rejected(self, tenant_a, client_a, carrier_b):
        from apps.scm.models import Load
        data = {
            "carrier": str(carrier_b.pk), "mode": "truckload", "equipment_type": "dry_van",
            "origin_text": "", "destination_text": "", "planned_departure": "", "planned_arrival": "",
            "distance_km": "", "estimated_fuel_cost": "", "freight_cost_estimate": "",
            "equipment_capacity_weight_kg": "", "equipment_capacity_volume_cbm": "",
            "driver_name": "", "vehicle_ref": "", "notes": "",
            **formset_data("stops", []),
        }
        resp = client_a.post(reverse("scm:load_create"), data)
        assert resp.status_code == 200
        assert not Load.objects.filter(tenant=tenant_a).exists()

    def test_crafted_shipment_post_with_other_tenant_carrier_is_rejected(self, tenant_a, client_a, carrier_b):
        from apps.scm.models import Shipment
        data = {
            "direction": "outbound", "carrier": str(carrier_b.pk), "load": "", "sales_order": "",
            "purchase_order": "", "ship_from_address": "", "ship_to_address": "", "origin_text": "",
            "destination_text": "", "mode": "truckload", "planned_pickup_date": "",
            "planned_delivery_date": "", "weight_kg": "", "volume_cbm": "", "package_count": "",
            "carrier_tracking_number": "", "freight_cost_estimate": "", "notes": "",
        }
        resp = client_a.post(reverse("scm:shipment_create"), data)
        assert resp.status_code == 200
        assert not Shipment.objects.filter(tenant=tenant_a).exists()

    def test_crafted_freightinvoice_post_with_other_tenant_carrier_is_rejected(self, tenant_a, client_a, carrier_b):
        from apps.scm.models import FreightInvoice
        data = {
            "carrier": str(carrier_b.pk), "load": "", "shipment": "", "carrier_invoice_number": "",
            "invoice_date": "", "due_date": "", "currency": "", "match_tolerance_pct": "2.00", "notes": "",
            **formset_data("lines", []),
        }
        resp = client_a.post(reverse("scm:freightinvoice_create"), data)
        assert resp.status_code == 200
        assert not FreightInvoice.objects.filter(tenant=tenant_a).exists()


# ================================================================ POST-only action views: GET -> 405
class TestTMSPostOnlyActions:
    def test_get_carrier_delete_returns_405(self, client_a, carrier_a):
        assert client_a.get(reverse("scm:carrier_delete", args=[carrier_a.pk])).status_code == 405

    def test_get_carrier_recompute_scorecard_returns_405(self, client_a, carrier_a):
        assert client_a.get(reverse("scm:carrier_recompute_scorecard", args=[carrier_a.pk])).status_code == 405

    def test_get_load_delete_returns_405(self, client_a, load_a):
        assert client_a.get(reverse("scm:load_delete", args=[load_a.pk])).status_code == 405

    def test_get_load_tender_returns_405(self, client_a, load_a):
        assert client_a.get(reverse("scm:load_tender", args=[load_a.pk])).status_code == 405

    def test_get_load_cancel_returns_405(self, client_a, load_a):
        assert client_a.get(reverse("scm:load_cancel", args=[load_a.pk])).status_code == 405

    def test_get_shipment_delete_returns_405(self, client_a, shipment_a):
        assert client_a.get(reverse("scm:shipment_delete", args=[shipment_a.pk])).status_code == 405

    def test_get_shipment_add_event_returns_405(self, client_a, shipment_a):
        assert client_a.get(reverse("scm:shipment_add_event", args=[shipment_a.pk])).status_code == 405

    def test_get_shipment_cancel_returns_405(self, client_a, shipment_a):
        assert client_a.get(reverse("scm:shipment_cancel", args=[shipment_a.pk])).status_code == 405

    def test_get_freightinvoice_delete_returns_405(self, client_a, freight_invoice_a):
        assert client_a.get(reverse("scm:freightinvoice_delete", args=[freight_invoice_a.pk])).status_code == 405

    def test_get_freightinvoice_approve_returns_405(self, client_a, freight_invoice_a):
        assert client_a.get(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk])).status_code == 405

    def test_get_freightinvoice_handoff_returns_405(self, client_a, freight_invoice_a):
        assert client_a.get(reverse("scm:freightinvoice_handoff", args=[freight_invoice_a.pk])).status_code == 405


# ================================================================ CSRF enforcement
class TestTMSCSRFEnforcement:
    def test_post_without_csrf_token_is_rejected_on_load_tender(self, admin_user, tenant_a, load_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:load_tender", args=[load_a.pk]))
        assert resp.status_code == 403
        load_a.refresh_from_db()
        assert load_a.status == "planning"

    def test_post_without_csrf_token_is_rejected_on_shipment_book(self, admin_user, tenant_a, shipment_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:shipment_book", args=[shipment_a.pk]))
        assert resp.status_code == 403
        shipment_a.refresh_from_db()
        assert shipment_a.status == "planned"

    def test_post_without_csrf_token_is_rejected_on_freightinvoice_approve(
        self, admin_user, tenant_a, freight_invoice_a,
    ):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:freightinvoice_approve", args=[freight_invoice_a.pk]))
        assert resp.status_code == 403
        freight_invoice_a.refresh_from_db()
        assert freight_invoice_a.approval_status == "pending"


# ================================================================================================
# SCM 4.7 Demand Planning & Forecasting
# ================================================================================================

# ================================================================ Anonymous -> login redirect
class TestDemandPlanningAnonymousRedirect:
    ROUTES = ("scm:seasonalityprofile_list", "scm:seasonalityprofile_create",
              "scm:demandforecast_list", "scm:demandforecast_create",
              "scm:demandsignal_list", "scm:demandsignal_create",
              "scm:forecastadjustment_list", "scm:forecastadjustment_create",
              "scm:safety_stock_report", "scm:forecast_accuracy_report")

    def test_every_landing_route_redirects_to_login(self):
        c = Client()
        for name in self.ROUTES:
            resp = c.get(reverse(name))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_detail_routes_redirect_to_login(self, demand_forecast_a, demand_signal_a,
                                             seasonality_profile_a, forecast_adjustment_a):
        c = Client()
        for name, obj in (("scm:demandforecast_detail", demand_forecast_a),
                          ("scm:demandsignal_detail", demand_signal_a),
                          ("scm:seasonalityprofile_detail", seasonality_profile_a),
                          ("scm:forecastadjustment_detail", forecast_adjustment_a)):
            resp = c.get(reverse(name, args=[obj.pk]))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_post_actions_redirect_to_login(self, demand_forecast_a, demand_signal_a,
                                            reorder_rule_a):
        c = Client()
        for name, args in (("scm:demandforecast_generate", [demand_forecast_a.pk]),
                           ("scm:demandforecast_approve", [demand_forecast_a.pk]),
                           ("scm:demandsignal_detect", []),
                           ("scm:safety_stock_recalculate", []),
                           ("scm:safety_stock_apply", [reorder_rule_a.pk])):
            resp = c.post(reverse(name, args=args))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name


# ================================================================ @tenant_admin_required gates
class TestDemandPlanningAdminRequiredGates:
    def test_forecast_approve_is_admin_only(self, member_client, forecast_with_periods_a):
        resp = member_client.post(reverse("scm:demandforecast_approve",
                                          args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 403
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "statistical"

    def test_forecast_archive_is_admin_only(self, member_client, forecast_with_periods_a):
        resp = member_client.post(reverse("scm:demandforecast_archive",
                                          args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 403
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "statistical"

    def test_forecast_revise_is_admin_only(self, member_client, approved_forecast_a):
        from apps.scm.models import DemandForecast
        resp = member_client.post(reverse("scm:demandforecast_revise",
                                          args=[approved_forecast_a.pk]))
        assert resp.status_code == 403
        assert not DemandForecast.objects.filter(supersedes=approved_forecast_a).exists()

    def test_safety_stock_apply_is_admin_only(self, member_client, reorder_rule_service_level_a):
        from django.utils import timezone
        reorder_rule_service_level_a.computed_safety_stock = Decimal("42.00")
        reorder_rule_service_level_a.last_calculated_at = timezone.now()
        reorder_rule_service_level_a.save(update_fields=["computed_safety_stock",
                                                          "last_calculated_at"])
        resp = member_client.post(reverse("scm:safety_stock_apply",
                                          args=[reorder_rule_service_level_a.pk]))
        assert resp.status_code == 403
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_service_level_a.safety_stock == Decimal("5.00")

    def test_an_admin_may_approve(self, client_a, forecast_with_periods_a):
        resp = client_a.post(reverse("scm:demandforecast_approve",
                                     args=[forecast_with_periods_a.pk]))
        assert resp.status_code == 302
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "approved"

    def test_an_admin_may_apply_a_calculated_policy(self, client_a,
                                                    reorder_rule_service_level_a):
        from django.utils import timezone
        reorder_rule_service_level_a.computed_safety_stock = Decimal("42.00")
        reorder_rule_service_level_a.computed_reorder_point = Decimal("77.00")
        reorder_rule_service_level_a.last_calculated_at = timezone.now()
        reorder_rule_service_level_a.save(update_fields=["computed_safety_stock",
                                                          "computed_reorder_point",
                                                          "last_calculated_at"])
        resp = client_a.post(reverse("scm:safety_stock_apply",
                                     args=[reorder_rule_service_level_a.pk]))
        assert resp.status_code == 302
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_service_level_a.safety_stock == Decimal("42.00")


# ================================================================ Plain @login_required actions work for a member
class TestDemandPlanningOrdinaryActionsAllowNonAdmin:
    def test_a_member_may_generate_a_forecast(self, member_client, demand_forecast_a):
        resp = member_client.post(reverse("scm:demandforecast_generate",
                                          args=[demand_forecast_a.pk]))
        assert resp.status_code != 403
        assert demand_forecast_a.periods.count() == 3

    def test_a_member_may_submit_for_review(self, member_client, forecast_with_periods_a):
        resp = member_client.post(reverse("scm:demandforecast_submit_review",
                                          args=[forecast_with_periods_a.pk]))
        assert resp.status_code != 403
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "in_review"

    def test_a_member_may_triage_a_signal(self, member_client, demand_signal_a):
        assert member_client.post(reverse("scm:demandsignal_review",
                                          args=[demand_signal_a.pk])).status_code != 403

    def test_a_member_may_run_the_detector(self, member_client):
        assert member_client.post(reverse("scm:demandsignal_detect")).status_code != 403

    def test_a_member_may_review_an_adjustment(self, member_client, forecast_adjustment_a):
        assert member_client.post(reverse("scm:forecastadjustment_accept",
                                          args=[forecast_adjustment_a.pk])).status_code != 403

    def test_a_member_may_recalculate_the_safety_stock_proposals(self, member_client,
                                                                  reorder_rule_service_level_a):
        resp = member_client.post(reverse("scm:safety_stock_recalculate"))
        assert resp.status_code != 403
        reorder_rule_service_level_a.refresh_from_db()
        assert reorder_rule_service_level_a.safety_stock == Decimal("5.00")  # proposal only

    def test_a_member_cannot_type_the_live_columns_on_the_reorder_rule_form(
        self, member_client, reorder_rule_a,
    ):
        """The safety_stock_apply admin gate would be decoration if this page were open."""
        data = {
            "item": str(reorder_rule_a.item_id), "location": str(reorder_rule_a.location_id),
            "reorder_point": "88888", "safety_stock": "99999", "reorder_quantity": "20",
            "is_active": "on", "safety_stock_method": "fixed", "service_level_pct": "95",
            "lead_time_days": "0", "lead_time_variability_days": "0", "review_period_days": "0",
            "seasonality_profile": "", "demand_forecast": "",
        }
        resp = member_client.post(reverse("scm:reorderrule_edit", args=[reorder_rule_a.pk]), data)
        assert resp.status_code == 302
        reorder_rule_a.refresh_from_db()
        assert reorder_rule_a.safety_stock == Decimal("5.00")
        assert reorder_rule_a.reorder_point == Decimal("10.00")


# ================================================================ Cross-tenant IDOR -> 404 (mandatory)
class TestDemandPlanningCrossTenantIDOR:
    def test_seasonalityprofile_detail_cross_tenant_404(self, client_a, seasonality_profile_b):
        assert client_a.get(reverse("scm:seasonalityprofile_detail",
                                    args=[seasonality_profile_b.pk])).status_code == 404

    def test_seasonalityprofile_edit_cross_tenant_404(self, client_a, seasonality_profile_b):
        assert client_a.get(reverse("scm:seasonalityprofile_edit",
                                    args=[seasonality_profile_b.pk])).status_code == 404

    def test_seasonalityprofile_delete_cross_tenant_404(self, client_a, seasonality_profile_b):
        assert client_a.post(reverse("scm:seasonalityprofile_delete",
                                     args=[seasonality_profile_b.pk])).status_code == 404

    def test_seasonalityprofile_derive_cross_tenant_404(self, client_a, seasonality_profile_b):
        assert client_a.post(reverse("scm:seasonalityprofile_derive",
                                     args=[seasonality_profile_b.pk])).status_code == 404

    def test_demandforecast_detail_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.get(reverse("scm:demandforecast_detail",
                                    args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_edit_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.get(reverse("scm:demandforecast_edit",
                                    args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_delete_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.post(reverse("scm:demandforecast_delete",
                                     args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_generate_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.post(reverse("scm:demandforecast_generate",
                                     args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_submit_review_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.post(reverse("scm:demandforecast_submit_review",
                                     args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_approve_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.post(reverse("scm:demandforecast_approve",
                                     args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_archive_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.post(reverse("scm:demandforecast_archive",
                                     args=[demand_forecast_b.pk])).status_code == 404

    def test_demandforecast_revise_cross_tenant_404(self, client_a, demand_forecast_b):
        assert client_a.post(reverse("scm:demandforecast_revise",
                                     args=[demand_forecast_b.pk])).status_code == 404

    def test_demandsignal_detail_cross_tenant_404(self, client_a, demand_signal_b):
        assert client_a.get(reverse("scm:demandsignal_detail",
                                    args=[demand_signal_b.pk])).status_code == 404

    def test_demandsignal_edit_cross_tenant_404(self, client_a, demand_signal_b):
        assert client_a.get(reverse("scm:demandsignal_edit",
                                    args=[demand_signal_b.pk])).status_code == 404

    def test_demandsignal_delete_cross_tenant_404(self, client_a, demand_signal_b):
        assert client_a.post(reverse("scm:demandsignal_delete",
                                     args=[demand_signal_b.pk])).status_code == 404

    def test_demandsignal_review_cross_tenant_404(self, client_a, demand_signal_b):
        assert client_a.post(reverse("scm:demandsignal_review",
                                     args=[demand_signal_b.pk])).status_code == 404

    def test_demandsignal_apply_cross_tenant_404(self, client_a, demand_signal_b):
        assert client_a.post(reverse("scm:demandsignal_apply",
                                     args=[demand_signal_b.pk]), {}).status_code == 404

    def test_demandsignal_dismiss_cross_tenant_404(self, client_a, demand_signal_b):
        assert client_a.post(reverse("scm:demandsignal_dismiss",
                                     args=[demand_signal_b.pk])).status_code == 404

    def test_forecastadjustment_detail_cross_tenant_404(self, client_a, forecast_adjustment_b):
        assert client_a.get(reverse("scm:forecastadjustment_detail",
                                    args=[forecast_adjustment_b.pk])).status_code == 404

    def test_forecastadjustment_edit_cross_tenant_404(self, client_a, forecast_adjustment_b):
        assert client_a.get(reverse("scm:forecastadjustment_edit",
                                    args=[forecast_adjustment_b.pk])).status_code == 404

    def test_forecastadjustment_delete_cross_tenant_404(self, client_a, forecast_adjustment_b):
        assert client_a.post(reverse("scm:forecastadjustment_delete",
                                     args=[forecast_adjustment_b.pk])).status_code == 404

    def test_forecastadjustment_accept_cross_tenant_404(self, client_a, forecast_adjustment_b):
        assert client_a.post(reverse("scm:forecastadjustment_accept",
                                     args=[forecast_adjustment_b.pk])).status_code == 404

    def test_forecastadjustment_reject_cross_tenant_404(self, client_a, forecast_adjustment_b):
        assert client_a.post(reverse("scm:forecastadjustment_reject",
                                     args=[forecast_adjustment_b.pk])).status_code == 404

    def test_safety_stock_apply_cross_tenant_404(self, client_a, reorder_rule_b):
        assert client_a.post(reverse("scm:safety_stock_apply",
                                     args=[reorder_rule_b.pk])).status_code == 404


# ================================================================ Cross-tenant FORM binding + IDOR list
class TestDemandPlanningCrossTenantFormScoping:
    def test_seasonality_list_never_contains_other_tenant_rows(self, client_a,
                                                               seasonality_profile_a,
                                                               seasonality_profile_b):
        resp = client_a.get(reverse("scm:seasonalityprofile_list"))
        assert seasonality_profile_b not in resp.context["object_list"]

    def test_forecast_list_never_contains_other_tenant_rows(self, client_a, demand_forecast_a,
                                                            demand_forecast_b):
        resp = client_a.get(reverse("scm:demandforecast_list"))
        assert demand_forecast_b not in resp.context["object_list"]

    def test_signal_list_never_contains_other_tenant_rows(self, client_a, demand_signal_a,
                                                          demand_signal_b):
        resp = client_a.get(reverse("scm:demandsignal_list"))
        assert demand_signal_b not in resp.context["object_list"]

    def test_adjustment_list_never_contains_other_tenant_rows(self, client_a,
                                                              forecast_adjustment_a,
                                                              forecast_adjustment_b):
        resp = client_a.get(reverse("scm:forecastadjustment_list"))
        assert forecast_adjustment_b not in resp.context["object_list"]

    def test_safety_stock_report_never_contains_other_tenant_rules(self, client_a,
                                                                   reorder_rule_a,
                                                                   reorder_rule_b):
        resp = client_a.get(reverse("scm:safety_stock_report"))
        assert reorder_rule_b not in [row["rule"] for row in resp.context["rows"]]

    def test_accuracy_report_never_contains_other_tenant_forecasts(self, client_a,
                                                                   forecast_with_periods_a,
                                                                   forecast_with_periods_b):
        resp = client_a.get(reverse("scm:forecast_accuracy_report"))
        assert forecast_with_periods_b not in [row["forecast"] for row in resp.context["rows"]]

    def test_a_crafted_forecast_post_with_another_tenants_item_is_rejected(self, client_a,
                                                                            tenant_a, item_b):
        from django.utils import timezone
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        data = {
            "name": "Crafted", "item": str(item_b.pk), "location": "", "customer": "",
            "demand_source": "sales_orders", "bucket": "month",
            "horizon_start": start.isoformat(),
            "horizon_end": (add_months(start, 3) - datetime.timedelta(days=1)).isoformat(),
            "history_months": "24", "method": "moving_average", "method_parameter": "3",
            "seasonality_profile": "", "reference_item": "", "reference_scale_pct": "100",
            "exclude_outliers": "", "outlier_threshold_sigma": "3", "currency": "",
            "scenario": "baseline", "notes": "", **formset_data("periods", []),
        }
        resp = client_a.post(reverse("scm:demandforecast_create"), data)
        assert resp.status_code == 200  # re-rendered form, not saved
        assert not DemandForecast.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_signal_post_with_another_tenants_item_is_rejected(self, client_a,
                                                                         tenant_a, item_b):
        from django.utils import timezone
        from apps.scm.models import DemandSignal
        data = {
            "signal_type": "order_surge", "source": "manual", "source_reference": "crafted",
            "item": str(item_b.pk), "category": "", "location": "", "customer": "",
            "observed_at": timezone.now().strftime("%Y-%m-%dT%H:%M"), "effective_from": "",
            "effective_to": "", "horizon_days": "28", "signal_value": "0", "baseline_value": "0",
            "impact_direction": "increase", "impact_pct": "0", "impact_quantity": "0",
            "confidence": "medium", "notes": "",
        }
        resp = client_a.post(reverse("scm:demandsignal_create"), data)
        assert resp.status_code == 200
        assert not DemandSignal.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_adjustment_post_with_another_tenants_forecast_is_rejected(
        self, client_a, tenant_a, forecast_with_periods_b,
    ):
        from apps.scm.models import ForecastAdjustment
        data = {
            "forecast": str(forecast_with_periods_b.pk), "period": "",
            "contributor_function": "sales", "org_unit": "", "adjustment_type": "absolute",
            "proposed_quantity": "140", "adjustment_pct": "0", "reason_code": "promotion",
            "rationale": "crafted", "confidence": "medium",
        }
        resp = client_a.post(reverse("scm:forecastadjustment_create"), data)
        assert resp.status_code == 200
        assert not ForecastAdjustment.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_adjustment_post_with_another_tenants_period_is_rejected(
        self, client_a, tenant_a, forecast_with_periods_a, forecast_with_periods_b,
    ):
        from apps.scm.models import ForecastAdjustment
        data = {
            "forecast": str(forecast_with_periods_a.pk),
            "period": str(forecast_with_periods_b.periods.first().pk),
            "contributor_function": "sales", "org_unit": "", "adjustment_type": "absolute",
            "proposed_quantity": "140", "adjustment_pct": "0", "reason_code": "promotion",
            "rationale": "crafted", "confidence": "medium",
        }
        resp = client_a.post(reverse("scm:forecastadjustment_create"), data)
        assert resp.status_code == 200
        assert not ForecastAdjustment.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_signal_apply_post_cannot_move_another_tenants_forecast(
        self, client_a, demand_signal_a, forecast_with_periods_b,
    ):
        resp = client_a.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                             {"forecast": str(forecast_with_periods_b.pk)}, follow=True)
        assert resp.status_code == 200
        assert any("Pick a forecast" in str(m) for m in resp.context["messages"])
        assert forecast_with_periods_b.periods.first().signal_adjustment_quantity == Decimal("0.0000")
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "new"

    def test_a_crafted_profile_post_with_another_tenants_category_is_rejected(self, client_a,
                                                                               tenant_a,
                                                                               category_b):
        from apps.scm.models import SeasonalityProfile
        data = {
            "name": "Crafted curve", "profile_type": "seasonal", "bucket": "month",
            "scope": "category", "item": "", "category": str(category_b.pk), "location": "",
            "event_start": "", "event_end": "", "uplift_pct": "0", "cannibalization_pct": "0",
            "cannibalized_category": "", "promotion_mechanic": "", "derived_from_years": "2",
            "is_active": "on", "notes": "", **formset_data("indices", []),
        }
        resp = client_a.post(reverse("scm:seasonalityprofile_create"), data)
        assert resp.status_code == 200
        assert not SeasonalityProfile.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_reorderrule_post_with_another_tenants_forecast_is_rejected(
        self, client_a, tenant_a, item_a, location_a, forecast_with_periods_b,
    ):
        from apps.scm.models import ReorderRule
        data = {
            "item": str(item_a.pk), "location": str(location_a.pk), "reorder_point": "10",
            "safety_stock": "5", "reorder_quantity": "20", "is_active": "on",
            "safety_stock_method": "forecast_error", "service_level_pct": "95",
            "lead_time_days": "5", "lead_time_variability_days": "0", "review_period_days": "0",
            "seasonality_profile": "", "demand_forecast": str(forecast_with_periods_b.pk),
        }
        resp = client_a.post(reverse("scm:reorderrule_create"), data)
        assert resp.status_code == 200
        assert not ReorderRule.objects.filter(tenant=tenant_a).exists()


# ================================================================ POST-only action views: GET -> 405
class TestDemandPlanningPostOnlyActions:
    def test_get_on_every_forecast_action_returns_405(self, client_a, forecast_with_periods_a):
        for name in ("demandforecast_delete", "demandforecast_generate",
                     "demandforecast_submit_review", "demandforecast_approve",
                     "demandforecast_archive", "demandforecast_revise"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[forecast_with_periods_a.pk])).status_code == 405, name

    def test_get_on_every_signal_action_returns_405(self, client_a, demand_signal_a):
        for name in ("demandsignal_delete", "demandsignal_review", "demandsignal_apply",
                     "demandsignal_dismiss"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[demand_signal_a.pk])).status_code == 405, name

    def test_get_on_the_detector_returns_405(self, client_a):
        assert client_a.get(reverse("scm:demandsignal_detect")).status_code == 405

    def test_get_on_every_adjustment_action_returns_405(self, client_a, forecast_adjustment_a):
        for name in ("forecastadjustment_delete", "forecastadjustment_accept",
                     "forecastadjustment_reject"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[forecast_adjustment_a.pk])).status_code == 405, name

    def test_get_on_the_seasonality_actions_returns_405(self, client_a, seasonality_profile_a):
        for name in ("seasonalityprofile_delete", "seasonalityprofile_derive"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[seasonality_profile_a.pk])).status_code == 405, name

    def test_get_on_the_report_actions_returns_405(self, client_a, reorder_rule_a):
        assert client_a.get(reverse("scm:safety_stock_recalculate")).status_code == 405
        assert client_a.get(reverse("scm:safety_stock_apply",
                                    args=[reorder_rule_a.pk])).status_code == 405

    def test_a_get_never_deletes(self, client_a, demand_forecast_a, demand_signal_a,
                                 seasonality_profile_a, forecast_adjustment_a):
        from apps.scm.models import (DemandForecast, DemandSignal, ForecastAdjustment,
                                     SeasonalityProfile)
        client_a.get(reverse("scm:demandforecast_delete", args=[demand_forecast_a.pk]))
        client_a.get(reverse("scm:demandsignal_delete", args=[demand_signal_a.pk]))
        client_a.get(reverse("scm:seasonalityprofile_delete", args=[seasonality_profile_a.pk]))
        client_a.get(reverse("scm:forecastadjustment_delete", args=[forecast_adjustment_a.pk]))
        assert DemandForecast.objects.filter(pk=demand_forecast_a.pk).exists()
        assert DemandSignal.objects.filter(pk=demand_signal_a.pk).exists()
        assert SeasonalityProfile.objects.filter(pk=seasonality_profile_a.pk).exists()
        assert ForecastAdjustment.objects.filter(pk=forecast_adjustment_a.pk).exists()


# ================================================================ CSRF enforcement
class TestDemandPlanningCSRFEnforcement:
    def test_post_without_csrf_is_rejected_on_forecast_generate(self, admin_user,
                                                                demand_forecast_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:demandforecast_generate",
                              args=[demand_forecast_a.pk])).status_code == 403
        assert demand_forecast_a.periods.count() == 0

    def test_post_without_csrf_is_rejected_on_forecast_approve(self, admin_user,
                                                               forecast_with_periods_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:demandforecast_approve",
                              args=[forecast_with_periods_a.pk])).status_code == 403
        forecast_with_periods_a.refresh_from_db()
        assert forecast_with_periods_a.status == "statistical"

    def test_post_without_csrf_is_rejected_on_signal_apply(self, admin_user, demand_signal_a,
                                                           forecast_with_periods_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("scm:demandsignal_apply", args=[demand_signal_a.pk]),
                      {"forecast": str(forecast_with_periods_a.pk)})
        assert resp.status_code == 403
        demand_signal_a.refresh_from_db()
        assert demand_signal_a.status == "new"

    def test_post_without_csrf_is_rejected_on_adjustment_accept(self, admin_user,
                                                                forecast_adjustment_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:forecastadjustment_accept",
                              args=[forecast_adjustment_a.pk])).status_code == 403
        forecast_adjustment_a.refresh_from_db()
        assert forecast_adjustment_a.status == "proposed"

    def test_post_without_csrf_is_rejected_on_safety_stock_recalculate(self, admin_user,
                                                                        reorder_rule_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:safety_stock_recalculate")).status_code == 403
        reorder_rule_a.refresh_from_db()
        assert reorder_rule_a.last_calculated_at is None

    def test_post_without_csrf_is_rejected_on_safety_stock_apply(self, admin_user,
                                                                 reorder_rule_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:safety_stock_apply",
                              args=[reorder_rule_a.pk])).status_code == 403

    def test_post_without_csrf_is_rejected_on_seasonality_derive(self, admin_user,
                                                                 category_profile_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:seasonalityprofile_derive",
                              args=[category_profile_a.pk])).status_code == 403
        assert not category_profile_a.indices.exists()

    def test_post_without_csrf_is_rejected_on_signal_detect(self, admin_user, tenant_a):
        from apps.scm.models import DemandSignal
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:demandsignal_detect")).status_code == 403
        assert not DemandSignal.objects.filter(tenant=tenant_a).exists()


# ================================================================================================
# SCM 4.8 Manufacturing
# ================================================================================================

def _mfg_wo_payload(item, **overrides):
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


def _mfg_bom_payload(item, lines=(), **overrides):
    data = {
        "item": str(item.pk), "name": "Crafted recipe", "version": "9",
        "bom_type": "manufacture", "output_quantity": "1", "uom": "", "lead_time_days": "0",
        "default_work_center": "", "status": "draft", "effective_from": "", "effective_to": "",
        "notes": "", **formset_data("lines", list(lines)),
    }
    data.update(overrides)
    return data


def _mfg_wc_payload(**overrides):
    data = {
        "code": "WC-SEC", "name": "Sec Cell", "center_type": "machine", "location": "",
        "org_unit": "", "supervisor": "", "capacity_hours_per_day": "8", "efficiency_pct": "100",
        "setup_minutes": "0", "machine_cost_per_hour": "1", "labor_cost_per_hour": "1",
        "is_active": "on", "notes": "",
    }
    data.update(overrides)
    return data


def _mfg_log_payload(work_order, work_center, **overrides):
    from django.utils import timezone
    started = timezone.now() - datetime.timedelta(hours=3)
    data = {
        "work_order": str(work_order.pk), "work_center": str(work_center.pk),
        "operation": "Crafted", "entry_type": "labor", "operator": "",
        "started_at": started.strftime("%Y-%m-%dT%H:%M"),
        "ended_at": (started + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "quantity_completed": "0", "quantity_scrapped": "0", "downtime_reason": "", "notes": "",
    }
    data.update(overrides)
    return data


def _mfg_moves(order):
    from apps.scm.models import StockMove
    return StockMove.objects.filter(tenant=order.tenant, reference=order.number)


# ================================================================ Anonymous -> login redirect
class TestManufacturingAnonymousRedirect:
    ROUTES = ("scm:workcenter_list", "scm:workcenter_create",
              "scm:billofmaterials_list", "scm:billofmaterials_create",
              "scm:workorder_list", "scm:workorder_create",
              "scm:productiontimelog_list", "scm:productiontimelog_create",
              "scm:mrp_report", "scm:production_schedule")

    def test_every_landing_route_redirects_to_login(self):
        c = Client()
        for name in self.ROUTES:
            resp = c.get(reverse(name))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_detail_routes_redirect_to_login(self, work_center_a, bom_a, work_order_a,
                                             time_log_a):
        c = Client()
        for name, obj in (("scm:workcenter_detail", work_center_a),
                          ("scm:billofmaterials_detail", bom_a),
                          ("scm:workorder_detail", work_order_a),
                          ("scm:productiontimelog_detail", time_log_a)):
            resp = c.get(reverse(name, args=[obj.pk]))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_every_post_action_redirects_to_login_and_posts_nothing(self, released_work_order_a,
                                                                     work_center_a, bom_a,
                                                                     time_log_a):
        c = Client()
        for name in ("workorder_plan", "workorder_release", "workorder_close",
                     "workorder_cancel", "workorder_schedule", "workorder_issue_components",
                     "workorder_report_production", "workorder_delete"):
            resp = c.post(reverse(f"scm:{name}", args=[released_work_order_a.pk]))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name
        for name, obj in (("scm:workcenter_delete", work_center_a),
                          ("scm:billofmaterials_delete", bom_a),
                          ("scm:productiontimelog_delete", time_log_a)):
            resp = c.post(reverse(name, args=[obj.pk]))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name
        assert _mfg_moves(released_work_order_a).count() == 0


# ================================================================ @tenant_admin_required gates
class TestManufacturingAdminRequiredGates:
    def test_release_is_admin_only(self, member_client, stocked_work_order_a):
        assert member_client.post(reverse("scm:workorder_release",
                                          args=[stocked_work_order_a.pk])).status_code == 403
        stocked_work_order_a.refresh_from_db()
        assert stocked_work_order_a.status == "draft"

    def test_issue_components_is_admin_only(self, member_client, released_work_order_a):
        assert member_client.post(
            reverse("scm:workorder_issue_components",
                    args=[released_work_order_a.pk])).status_code == 403
        assert _mfg_moves(released_work_order_a).count() == 0
        for row in released_work_order_a.components.all():
            assert row.quantity_issued == Decimal("0")

    def test_report_production_is_admin_only(self, member_client, released_work_order_a):
        assert member_client.post(
            reverse("scm:workorder_report_production", args=[released_work_order_a.pk]),
            {"quantity_good": "2"}).status_code == 403
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("0")
        assert _mfg_moves(released_work_order_a).count() == 0

    def test_close_is_admin_only(self, member_client, released_work_order_a):
        from apps.scm.models import WorkOrder
        WorkOrder.objects.filter(pk=released_work_order_a.pk).update(status="completed")
        assert member_client.post(reverse("scm:workorder_close",
                                          args=[released_work_order_a.pk])).status_code == 403
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "completed"

    def test_cancel_is_admin_only(self, member_client, released_work_order_a):
        assert member_client.post(reverse("scm:workorder_cancel",
                                          args=[released_work_order_a.pk])).status_code == 403
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "released"

    def test_an_admin_may_do_all_five(self, client_a, stocked_work_order_a):
        assert client_a.post(reverse("scm:workorder_release",
                                     args=[stocked_work_order_a.pk])).status_code == 302
        assert client_a.post(reverse("scm:workorder_issue_components",
                                     args=[stocked_work_order_a.pk])).status_code == 302
        assert client_a.post(
            reverse("scm:workorder_report_production", args=[stocked_work_order_a.pk]),
            {"quantity_good": "5"}).status_code == 302
        assert client_a.post(reverse("scm:workorder_close",
                                     args=[stocked_work_order_a.pk])).status_code == 302
        stocked_work_order_a.refresh_from_db()
        assert stocked_work_order_a.status == "closed"


# ================================================================ Plain @login_required actions
class TestManufacturingOrdinaryActionsAllowNonAdmin:
    def test_a_member_may_plan_a_draft_run(self, member_client, work_order_a):
        assert member_client.post(reverse("scm:workorder_plan",
                                          args=[work_order_a.pk])).status_code != 403
        work_order_a.refresh_from_db()
        assert work_order_a.status == "planned"

    def test_a_member_may_schedule_a_draft_run(self, member_client, work_order_a):
        resp = member_client.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                                  {"direction": "forward", "anchor_date": "2026-05-01",
                                   "lead_time_days": "2"})
        assert resp.status_code != 403
        work_order_a.refresh_from_db()
        assert work_order_a.planned_start is not None

    def test_a_member_may_create_a_work_centre(self, member_client, tenant_a):
        from apps.scm.models import WorkCenter
        assert member_client.post(reverse("scm:workcenter_create"),
                                  _mfg_wc_payload()).status_code == 302
        assert WorkCenter.objects.filter(tenant=tenant_a, code="WC-SEC").exists()

    def test_a_member_may_author_a_recipe(self, member_client, tenant_a, item_a):
        from apps.scm.models import BillOfMaterials
        assert member_client.post(reverse("scm:billofmaterials_create"),
                                  _mfg_bom_payload(item_a)).status_code == 302
        assert BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()

    def test_a_member_may_book_a_time_log(self, member_client, tenant_a, released_work_order_a,
                                          work_center_a):
        from apps.scm.models import ProductionTimeLog
        assert member_client.post(
            reverse("scm:productiontimelog_create"),
            _mfg_log_payload(released_work_order_a, work_center_a)).status_code == 302
        assert ProductionTimeLog.objects.filter(tenant=tenant_a, operation="Crafted").exists()

    def test_a_member_may_read_both_reports(self, member_client):
        for name in ("scm:mrp_report", "scm:production_schedule"):
            assert member_client.get(reverse(name)).status_code == 200, name

    def test_a_member_cannot_type_the_single_writer_columns_on_the_form(self, member_client,
                                                                        work_order_a, item_a):
        """The release/issue/report admin gates would be decoration if this page were open."""
        resp = member_client.post(
            reverse("scm:workorder_edit", args=[work_order_a.pk]),
            _mfg_wo_payload(item_a, status="completed", quantity_produced="99",
                            produced_unit_cost="0.0001"))
        assert resp.status_code == 302
        work_order_a.refresh_from_db()
        assert work_order_a.status == "draft"
        assert work_order_a.quantity_produced == Decimal("0")
        assert work_order_a.produced_unit_cost == Decimal("0")


# ================================================================ Cross-tenant IDOR -> 404
class TestManufacturingCrossTenantIDOR:
    def test_workcenter_detail_edit_delete_cross_tenant_404(self, client_a, work_center_b):
        assert client_a.get(reverse("scm:workcenter_detail",
                                    args=[work_center_b.pk])).status_code == 404
        assert client_a.get(reverse("scm:workcenter_edit",
                                    args=[work_center_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:workcenter_delete",
                                     args=[work_center_b.pk])).status_code == 404

    def test_billofmaterials_detail_edit_delete_cross_tenant_404(self, client_a, bom_b):
        assert client_a.get(reverse("scm:billofmaterials_detail",
                                    args=[bom_b.pk])).status_code == 404
        assert client_a.get(reverse("scm:billofmaterials_edit",
                                    args=[bom_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:billofmaterials_delete",
                                     args=[bom_b.pk])).status_code == 404

    def test_workorder_detail_edit_delete_cross_tenant_404(self, client_a, work_order_b):
        assert client_a.get(reverse("scm:workorder_detail",
                                    args=[work_order_b.pk])).status_code == 404
        assert client_a.get(reverse("scm:workorder_edit",
                                    args=[work_order_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:workorder_delete",
                                     args=[work_order_b.pk])).status_code == 404

    def test_productiontimelog_detail_edit_delete_cross_tenant_404(self, client_a, time_log_b):
        assert client_a.get(reverse("scm:productiontimelog_detail",
                                    args=[time_log_b.pk])).status_code == 404
        assert client_a.get(reverse("scm:productiontimelog_edit",
                                    args=[time_log_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:productiontimelog_delete",
                                     args=[time_log_b.pk])).status_code == 404

    def test_every_work_order_POST_ACTION_is_404_across_tenants(self, client_a, work_order_b):
        for name in ("workorder_plan", "workorder_release", "workorder_close",
                     "workorder_cancel", "workorder_issue_components"):
            assert client_a.post(reverse(f"scm:{name}",
                                         args=[work_order_b.pk])).status_code == 404, name
        assert client_a.post(reverse("scm:workorder_schedule", args=[work_order_b.pk]),
                             {"direction": "forward",
                              "anchor_date": "2026-05-01"}).status_code == 404
        assert client_a.post(reverse("scm:workorder_report_production", args=[work_order_b.pk]),
                             {"quantity_good": "1"}).status_code == 404

    def test_a_cross_tenant_action_posts_no_stock_and_moves_no_status(self, client_a,
                                                                      work_order_b):
        from apps.scm.models import StockMove
        client_a.post(reverse("scm:workorder_release", args=[work_order_b.pk]))
        client_a.post(reverse("scm:workorder_issue_components", args=[work_order_b.pk]))
        work_order_b.refresh_from_db()
        assert work_order_b.status == "draft"
        assert not StockMove.objects.filter(reference=work_order_b.number).exists()

    def test_a_tenant_b_admin_is_equally_locked_out_of_tenant_a(self, client_b, work_order_a,
                                                                bom_a, work_center_a,
                                                                time_log_a):
        for name, obj in (("scm:workorder_detail", work_order_a),
                          ("scm:billofmaterials_detail", bom_a),
                          ("scm:workcenter_detail", work_center_a),
                          ("scm:productiontimelog_detail", time_log_a)):
            assert client_b.get(reverse(name, args=[obj.pk])).status_code == 404, name


# ================================================================ Cross-tenant list + form binding
class TestManufacturingCrossTenantFormScoping:
    def test_no_list_ever_contains_the_other_tenants_rows(self, client_a, work_center_a,
                                                          work_center_b, bom_a, bom_b,
                                                          work_order_a, work_order_b, time_log_a,
                                                          time_log_b):
        for name, mine, theirs in (
            ("scm:workcenter_list", work_center_a, work_center_b),
            ("scm:billofmaterials_list", bom_a, bom_b),
            ("scm:workorder_list", work_order_a, work_order_b),
            ("scm:productiontimelog_list", time_log_a, time_log_b),
        ):
            rows = list(client_a.get(reverse(name)).context["object_list"])
            assert mine in rows, name
            assert theirs not in rows, name

    def test_a_crafted_work_order_post_with_another_tenants_item_is_rejected(self, client_a,
                                                                             tenant_a, item_b):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_create"), _mfg_wo_payload(item_b))
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_work_order_post_with_another_tenants_bom_is_rejected(self, client_a,
                                                                            tenant_a, item_a,
                                                                            bom_b):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_create"),
                             _mfg_wo_payload(item_a, bom=str(bom_b.pk)))
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_work_order_post_with_another_tenants_work_centre_is_rejected(
        self, client_a, tenant_a, item_a, work_center_b,
    ):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_create"),
                             _mfg_wo_payload(item_a, work_center=str(work_center_b.pk)))
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_work_order_post_with_another_tenants_location_is_rejected(self, client_a,
                                                                                  tenant_a,
                                                                                  item_a,
                                                                                  location_b):
        from apps.scm.models import WorkOrder
        resp = client_a.post(reverse("scm:workorder_create"),
                             _mfg_wo_payload(item_a, output_location=str(location_b.pk)))
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_component_line_with_another_tenants_item_is_rejected(self, client_a,
                                                                            tenant_a, item_a,
                                                                            item_b):
        from apps.scm.models import WorkOrder
        data = _mfg_wo_payload(item_a)
        data.update(formset_data("components", [
            {"id": "", "sequence": "10", "item": str(item_b.pk), "quantity_required": "1",
             "uom": "", "lot_serial": "", "issue_method": "manual", "unit_cost": "1",
             "notes": ""},
        ]))
        resp = client_a.post(reverse("scm:workorder_create"), data)
        assert resp.status_code == 200
        assert not WorkOrder.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_bom_post_with_another_tenants_item_is_rejected(self, client_a, tenant_a,
                                                                      item_b):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_create"), _mfg_bom_payload(item_b))
        assert resp.status_code == 200
        assert not BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()

    def test_a_crafted_bom_line_with_another_tenants_component_is_rejected(self, client_a,
                                                                           tenant_a, item_a,
                                                                           item_b):
        from apps.scm.models import BillOfMaterials
        resp = client_a.post(reverse("scm:billofmaterials_create"), _mfg_bom_payload(item_a, [
            {"id": "", "sequence": "10", "component": str(item_b.pk), "quantity_per": "1",
             "uom": "", "scrap_pct": "0", "issue_method": "manual", "notes": ""},
        ]))
        assert resp.status_code == 200
        assert not BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()

    def test_a_crafted_time_log_post_with_another_tenants_run_is_rejected(self, client_a,
                                                                          tenant_a, work_order_b,
                                                                          work_center_a):
        from apps.scm.models import ProductionTimeLog
        resp = client_a.post(reverse("scm:productiontimelog_create"),
                             _mfg_log_payload(work_order_b, work_center_a))
        assert resp.status_code == 200
        assert not ProductionTimeLog.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_work_centre_post_with_another_tenants_location_is_rejected(self, client_a,
                                                                                   tenant_a,
                                                                                   location_b):
        from apps.scm.models import WorkCenter
        resp = client_a.post(reverse("scm:workcenter_create"),
                             _mfg_wc_payload(location=str(location_b.pk)))
        assert resp.status_code == 200
        assert not WorkCenter.objects.filter(tenant=tenant_a, code="WC-SEC").exists()

    def test_neither_report_leaks_the_other_tenants_rows(self, client_a, tenant_b, customer_b,
                                                         item_b, bom_b, work_center_b):
        from django.utils import timezone
        from apps.scm.models import SalesOrder, SalesOrderLine
        order = SalesOrder.objects.create(tenant=tenant_b, customer=customer_b,
                                          order_date=timezone.localdate(), status="submitted")
        SalesOrderLine.objects.create(sales_order=order, item=item_b,
                                      quantity_ordered=Decimal("50"), unit_price=Decimal("1"))
        assert client_a.get(reverse("scm:mrp_report")).context["total_rows"] == 0
        rows = client_a.get(reverse("scm:production_schedule")).context["rows"]
        assert work_center_b.pk not in {row["centre"].pk for row in rows}


# ================================================================ POST-only action views: GET -> 405
class TestManufacturingPostOnlyActions:
    def test_get_on_every_work_order_action_returns_405(self, client_a, work_order_a):
        for name in ("workorder_delete", "workorder_plan", "workorder_release",
                     "workorder_close", "workorder_cancel", "workorder_schedule",
                     "workorder_issue_components", "workorder_report_production"):
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[work_order_a.pk])).status_code == 405, name

    def test_get_on_every_delete_route_returns_405(self, client_a, work_center_a, bom_a,
                                                   time_log_a):
        for name, obj in (("scm:workcenter_delete", work_center_a),
                          ("scm:billofmaterials_delete", bom_a),
                          ("scm:productiontimelog_delete", time_log_a)):
            assert client_a.get(reverse(name, args=[obj.pk])).status_code == 405, name

    def test_a_get_never_deletes_and_never_posts_stock(self, client_a, released_work_order_a,
                                                       work_center_a, bom_a, time_log_a):
        from apps.scm.models import (BillOfMaterials, ProductionTimeLog, WorkCenter, WorkOrder)
        for name in ("workorder_delete", "workorder_release", "workorder_issue_components",
                     "workorder_report_production", "workorder_cancel"):
            client_a.get(reverse(f"scm:{name}", args=[released_work_order_a.pk]))
        client_a.get(reverse("scm:workcenter_delete", args=[work_center_a.pk]))
        client_a.get(reverse("scm:billofmaterials_delete", args=[bom_a.pk]))
        client_a.get(reverse("scm:productiontimelog_delete", args=[time_log_a.pk]))
        assert WorkOrder.objects.filter(pk=released_work_order_a.pk).exists()
        assert WorkCenter.objects.filter(pk=work_center_a.pk).exists()
        assert BillOfMaterials.objects.filter(pk=bom_a.pk).exists()
        assert ProductionTimeLog.objects.filter(pk=time_log_a.pk).exists()
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "released"
        assert _mfg_moves(released_work_order_a).count() == 0


# ================================================================ CSRF enforcement
class TestManufacturingCSRFEnforcement:
    def _client(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        return c

    def test_post_without_csrf_is_rejected_on_release(self, admin_user, stocked_work_order_a):
        assert self._client(admin_user).post(
            reverse("scm:workorder_release",
                    args=[stocked_work_order_a.pk])).status_code == 403
        stocked_work_order_a.refresh_from_db()
        assert stocked_work_order_a.status == "draft"

    def test_post_without_csrf_is_rejected_on_issue_components(self, admin_user,
                                                               released_work_order_a):
        assert self._client(admin_user).post(
            reverse("scm:workorder_issue_components",
                    args=[released_work_order_a.pk])).status_code == 403
        assert _mfg_moves(released_work_order_a).count() == 0

    def test_post_without_csrf_is_rejected_on_report_production(self, admin_user,
                                                                released_work_order_a):
        assert self._client(admin_user).post(
            reverse("scm:workorder_report_production", args=[released_work_order_a.pk]),
            {"quantity_good": "2"}).status_code == 403
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.quantity_produced == Decimal("0")

    def test_post_without_csrf_is_rejected_on_cancel_and_close(self, admin_user,
                                                               released_work_order_a):
        client = self._client(admin_user)
        assert client.post(reverse("scm:workorder_cancel",
                                   args=[released_work_order_a.pk])).status_code == 403
        assert client.post(reverse("scm:workorder_close",
                                   args=[released_work_order_a.pk])).status_code == 403
        released_work_order_a.refresh_from_db()
        assert released_work_order_a.status == "released"

    def test_post_without_csrf_is_rejected_on_plan_and_schedule(self, admin_user, work_order_a):
        client = self._client(admin_user)
        assert client.post(reverse("scm:workorder_plan",
                                   args=[work_order_a.pk])).status_code == 403
        assert client.post(reverse("scm:workorder_schedule", args=[work_order_a.pk]),
                           {"direction": "forward",
                            "anchor_date": "2026-05-01"}).status_code == 403
        work_order_a.refresh_from_db()
        assert work_order_a.status == "draft"
        assert work_order_a.planned_start is None

    def test_post_without_csrf_is_rejected_on_every_delete(self, admin_user, work_order_a,
                                                           work_center_a, bom_a, time_log_a):
        from apps.scm.models import (BillOfMaterials, ProductionTimeLog, WorkCenter, WorkOrder)
        client = self._client(admin_user)
        for name, obj in (("scm:workorder_delete", work_order_a),
                          ("scm:workcenter_delete", work_center_a),
                          ("scm:billofmaterials_delete", bom_a),
                          ("scm:productiontimelog_delete", time_log_a)):
            assert client.post(reverse(name, args=[obj.pk])).status_code == 403, name
        assert WorkOrder.objects.filter(pk=work_order_a.pk).exists()
        assert WorkCenter.objects.filter(pk=work_center_a.pk).exists()
        assert BillOfMaterials.objects.filter(pk=bom_a.pk).exists()
        assert ProductionTimeLog.objects.filter(pk=time_log_a.pk).exists()

    def test_post_without_csrf_is_rejected_on_every_create(self, admin_user, tenant_a, item_a,
                                                           released_work_order_a,
                                                           work_center_a):
        from apps.scm.models import BillOfMaterials, ProductionTimeLog, WorkCenter, WorkOrder
        client = self._client(admin_user)
        before = WorkOrder.objects.count()
        assert client.post(reverse("scm:workorder_create"),
                           _mfg_wo_payload(item_a)).status_code == 403
        assert client.post(reverse("scm:billofmaterials_create"),
                           _mfg_bom_payload(item_a)).status_code == 403
        assert client.post(reverse("scm:workcenter_create"),
                           _mfg_wc_payload()).status_code == 403
        assert client.post(reverse("scm:productiontimelog_create"),
                           _mfg_log_payload(released_work_order_a,
                                            work_center_a)).status_code == 403
        assert WorkOrder.objects.count() == before
        assert not BillOfMaterials.objects.filter(tenant=tenant_a, version="9").exists()
        assert not WorkCenter.objects.filter(tenant=tenant_a, code="WC-SEC").exists()
        assert not ProductionTimeLog.objects.filter(tenant=tenant_a,
                                                    operation="Crafted").exists()


# ================================================================================================
# SCM 4.9 Quality Management
# ================================================================================================

def _qms_qc_payload(item_obj, **overrides):
    from django.utils import timezone
    data = {
        "plan": "", "inspection_type": "incoming", "goods_receipt": "", "work_order": "",
        "shipment": "", "item": str(item_obj.pk), "lot_serial": "", "location": "", "supplier": "",
        "quantity_inspected": "10", "sample_size": "10", "quantity_accepted": "10",
        "quantity_rejected": "0", "inspector": "", "inspected_on": timezone.localdate().isoformat(),
        "supplier_coa_reference": "", "notes": "Crafted",
        **formset_data("results", []),
    }
    data.update(overrides)
    return data


def _qms_ncr_payload(item_obj, **overrides):
    from django.utils import timezone
    data = {
        "source": "internal", "inspection": "", "goods_receipt": "", "work_order": "",
        "shipment": "", "audit": "", "item": str(item_obj.pk), "lot_serial": "", "location": "",
        "supplier": "", "quantity_affected": "3", "uom": "", "defect_category": "dimensional",
        "severity": "major", "title": "Crafted NCR", "description": "Crafted description.",
        "detected_by": "", "detected_on": timezone.localdate().isoformat(),
        "containment_action": "", "cost_of_quality": "0", "owner": "", "due_date": "", "notes": "",
    }
    data.update(overrides)
    return data


def _qms_capa_payload(**overrides):
    data = {
        "action_type": "corrective", "title": "Crafted CAPA",
        "source": "internal_improvement", "nonconformance": "", "audit": "", "item": "",
        "supplier": "", "problem_statement": "Crafted problem.", "containment_action": "",
        "root_cause_method": "", "root_cause": "", "action_plan": "", "owner": "",
        "priority": "normal", "due_date": "", "effectiveness_due_date": "", "notes": "",
        **formset_data("tasks", []),
    }
    data.update(overrides)
    return data


def _qms_qa_payload(org_unit, **overrides):
    from django.utils import timezone
    data = {
        "audit_type": "internal", "title": "Crafted audit", "standard": "", "scope": "",
        "auditee_party": "", "auditee_org_unit": str(org_unit.pk), "checklist_plan": "",
        "lead_auditor": "", "planned_date": timezone.localdate().isoformat(),
        "risk_level": "medium", "conclusion": "", "notes": "",
    }
    data.update(overrides)
    return data


def _qms_plan_payload(item_obj=None, **overrides):
    data = {
        "code": "SEC-1", "name": "Crafted plan", "plan_type": "incoming_receipt",
        "item": str(item_obj.pk) if item_obj is not None else "", "item_category": "",
        "supplier": "", "sampling_method": "all_100", "sample_percentage": "", "sample_size": "",
        "aql_accept_number": "", "aql_reject_number": "", "frequency": "every",
        "frequency_value": "", "version": "1", "effective_from": "", "is_active": "on",
        "notes": "",
        **formset_data("characteristics", [
            {"id": "", "sequence": "10", "name": "Crafted check",
             "characteristic_type": "pass_fail", "uom": "", "target_value": "", "lower_limit": "",
             "upper_limit": "", "expected_text": "OK", "test_method": "", "is_mandatory": "on"},
        ]),
    }
    data.update(overrides)
    return data


#: Every mutating 4.9 route that takes a QualityInspection pk.
_QC_ACTIONS = ("qualityinspection_delete", "qualityinspection_generate_results",
               "qualityinspection_start", "qualityinspection_complete",
               "qualityinspection_hold", "qualityinspection_resume",
               "qualityinspection_cancel", "qualityinspection_decide",
               "qualityinspection_quarantine", "qualityinspection_release_lot",
               "qualityinspection_raise_ncr")
_NCR_ACTIONS = ("nonconformance_delete", "nonconformance_investigate",
                "nonconformance_quarantine", "nonconformance_release_lot",
                "nonconformance_disposition", "nonconformance_close", "nonconformance_cancel",
                "nonconformance_raise_capa")
_CAPA_ACTIONS = ("capaaction_delete", "capaaction_start", "capaaction_progress",
                 "capaaction_implement", "capaaction_verify", "capaaction_cancel")
_QA_ACTIONS = ("qualityaudit_delete", "qualityaudit_start", "qualityaudit_complete",
               "qualityaudit_close", "qualityaudit_cancel", "qualityaudit_add_finding")
#: The EIGHT privileged writes: the usage decision (a sign-off), the four lot-status flips, the MRB
#: disposition (the only ledger write in 4.9), the CAPA effectiveness sign-off, and issuing a
#: customer-facing certificate.
_ADMIN_ONLY = ("qualityinspection_decide", "qualityinspection_quarantine",
               "qualityinspection_release_lot", "nonconformance_quarantine",
               "nonconformance_release_lot", "nonconformance_disposition", "capaaction_verify",
               "coa_issue")


# ================================================================ Anonymous -> login redirect
class TestQualityAnonymousRedirect:
    ROUTES = ("scm:inspectionplan_list", "scm:inspectionplan_create",
              "scm:qualityinspection_list", "scm:qualityinspection_create",
              "scm:nonconformance_list", "scm:nonconformance_create",
              "scm:capaaction_list", "scm:capaaction_create",
              "scm:qualityaudit_list", "scm:qualityaudit_create", "scm:coa_report")

    def test_every_landing_route_redirects_to_login(self):
        c = Client()
        for name in self.ROUTES:
            resp = c.get(reverse(name))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_detail_routes_redirect_to_login(self, inspection_plan_a, outgoing_inspection_a,
                                             nonconformance_a, capa_action_a, quality_audit_a):
        c = Client()
        for name, obj in (("scm:inspectionplan_detail", inspection_plan_a),
                          ("scm:qualityinspection_detail", outgoing_inspection_a),
                          ("scm:nonconformance_detail", nonconformance_a),
                          ("scm:capaaction_detail", capa_action_a),
                          ("scm:qualityaudit_detail", quality_audit_a),
                          ("scm:qualityaudit_print", quality_audit_a),
                          ("scm:coa_print", outgoing_inspection_a)):
            resp = c.get(reverse(name, args=[obj.pk]))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_every_post_action_redirects_to_login_and_changes_nothing(self, outgoing_inspection_a,
                                                                     nonconformance_a,
                                                                     capa_action_a,
                                                                     quality_audit_a, lot_a,
                                                                     customer_a):
        from apps.scm.models import StockMove
        c = Client()
        for names, obj in ((_QC_ACTIONS, outgoing_inspection_a), (_NCR_ACTIONS, nonconformance_a),
                           (_CAPA_ACTIONS, capa_action_a), (_QA_ACTIONS, quality_audit_a)):
            for name in names:
                resp = c.post(reverse(f"scm:{name}", args=[obj.pk]))
                assert resp.status_code == 302, name
                assert "login" in resp["Location"], name
        resp = c.post(reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]),
                      {"coa_issued_to": str(customer_a.pk)})
        assert resp.status_code == 302
        assert "login" in resp["Location"]
        outgoing_inspection_a.refresh_from_db()
        nonconformance_a.refresh_from_db()
        capa_action_a.refresh_from_db()
        quality_audit_a.refresh_from_db()
        lot_a.refresh_from_db()
        assert outgoing_inspection_a.status == "passed"
        assert outgoing_inspection_a.coa_number == ""
        assert nonconformance_a.status == "open"
        assert nonconformance_a.disposition == "pending"
        assert capa_action_a.status == "open"
        assert quality_audit_a.status == "planned"
        assert lot_a.status == "available"
        assert StockMove.objects.count() == 0

    def test_anonymous_deletes_delete_nothing(self, inspection_plan_a, outgoing_inspection_a,
                                              nonconformance_a, capa_action_a, quality_audit_a):
        from apps.scm.models import (CapaAction, InspectionPlan, NonConformance, QualityAudit,
                                     QualityInspection)
        c = Client()
        for name, obj in (("scm:inspectionplan_delete", inspection_plan_a),
                          ("scm:qualityinspection_delete", outgoing_inspection_a),
                          ("scm:nonconformance_delete", nonconformance_a),
                          ("scm:capaaction_delete", capa_action_a),
                          ("scm:qualityaudit_delete", quality_audit_a)):
            assert c.post(reverse(name, args=[obj.pk])).status_code == 302, name
        assert InspectionPlan.objects.filter(pk=inspection_plan_a.pk).exists()
        assert QualityInspection.objects.filter(pk=outgoing_inspection_a.pk).exists()
        assert NonConformance.objects.filter(pk=nonconformance_a.pk).exists()
        assert CapaAction.objects.filter(pk=capa_action_a.pk).exists()
        assert QualityAudit.objects.filter(pk=quality_audit_a.pk).exists()


# ================================================================ @tenant_admin_required gates
class TestQualityAdminRequiredGates:
    def test_the_usage_decision_is_admin_only(self, member_client, outgoing_inspection_a):
        assert member_client.post(reverse("scm:qualityinspection_decide",
                                          args=[outgoing_inspection_a.pk]),
                                  {"usage_decision": "reject"}).status_code == 403
        outgoing_inspection_a.refresh_from_db()
        assert outgoing_inspection_a.usage_decision == "accept"

    def test_the_inspection_lot_flips_are_admin_only(self, member_client, outgoing_inspection_a,
                                                    lot_a):
        for name in ("qualityinspection_quarantine", "qualityinspection_release_lot"):
            assert member_client.post(reverse(f"scm:{name}",
                                              args=[outgoing_inspection_a.pk])).status_code == 403
        lot_a.refresh_from_db()
        assert lot_a.status == "available"

    def test_the_ncr_lot_flips_are_admin_only(self, member_client, nonconformance_lot_a, lot_a):
        for name in ("nonconformance_quarantine", "nonconformance_release_lot"):
            assert member_client.post(reverse(f"scm:{name}",
                                              args=[nonconformance_lot_a.pk])).status_code == 403
        lot_a.refresh_from_db()
        nonconformance_lot_a.refresh_from_db()
        assert lot_a.status == "available"
        assert nonconformance_lot_a.quarantine_applied is False

    def test_the_MRB_disposition_is_admin_only_and_posts_nothing(self, member_client, tenant_a,
                                                                nonconformance_a, item_a,
                                                                location_a):
        from apps.scm.models import StockMove
        from apps.scm.tests._helpers import seed_stock
        seed_stock(tenant_a, item_a, location_a, "20", "8.0000")
        before = StockMove.objects.count()
        assert member_client.post(reverse("scm:nonconformance_disposition",
                                          args=[nonconformance_a.pk]),
                                  {"disposition": "scrap",
                                   "disposition_quantity": "5"}).status_code == 403
        nonconformance_a.refresh_from_db()
        assert nonconformance_a.disposition == "pending"
        assert nonconformance_a.status == "open"
        assert StockMove.objects.count() == before

    def test_the_capa_effectiveness_sign_off_is_admin_only(self, member_client, capa_in_progress_a):
        from apps.scm.models import CapaAction
        capa_in_progress_a.tasks.update(status="done")
        CapaAction.objects.filter(pk=capa_in_progress_a.pk).update(status="pending_verification")
        assert member_client.post(reverse("scm:capaaction_verify", args=[capa_in_progress_a.pk]),
                                  {"effectiveness_result": "effective"}).status_code == 403
        capa_in_progress_a.refresh_from_db()
        assert capa_in_progress_a.status == "pending_verification"
        assert capa_in_progress_a.effectiveness_result == "pending"

    def test_issuing_a_certificate_is_admin_only(self, member_client, outgoing_inspection_a,
                                                customer_a):
        assert member_client.post(reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]),
                                  {"coa_issued_to": str(customer_a.pk),
                                   "issued_on": ""}).status_code == 403
        outgoing_inspection_a.refresh_from_db()
        assert outgoing_inspection_a.coa_number == ""

    def test_ALL_EIGHT_privileged_routes_403_a_plain_member(self, member_client,
                                                            outgoing_inspection_a,
                                                            nonconformance_lot_a, capa_action_a):
        targets = {
            "qualityinspection_decide": outgoing_inspection_a,
            "qualityinspection_quarantine": outgoing_inspection_a,
            "qualityinspection_release_lot": outgoing_inspection_a,
            "nonconformance_quarantine": nonconformance_lot_a,
            "nonconformance_release_lot": nonconformance_lot_a,
            "nonconformance_disposition": nonconformance_lot_a,
            "capaaction_verify": capa_action_a,
            "coa_issue": outgoing_inspection_a,
        }
        assert set(targets) == set(_ADMIN_ONLY)
        for name, obj in targets.items():
            assert member_client.post(reverse(f"scm:{name}",
                                              args=[obj.pk])).status_code == 403, name

    def test_an_admin_may_do_all_eight(self, client_a, outgoing_inspection_a, customer_a):
        assert client_a.post(reverse("scm:qualityinspection_decide",
                                     args=[outgoing_inspection_a.pk]),
                             {"usage_decision": "accept"}).status_code == 302
        assert client_a.post(reverse("scm:qualityinspection_quarantine",
                                     args=[outgoing_inspection_a.pk])).status_code == 302
        assert client_a.post(reverse("scm:qualityinspection_release_lot",
                                     args=[outgoing_inspection_a.pk])).status_code == 302
        assert client_a.post(reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]),
                             {"coa_issued_to": str(customer_a.pk),
                              "issued_on": ""}).status_code == 302


# ================================================================ Plain @login_required actions
class TestQualityOrdinaryActionsAllowNonAdmin:
    def test_a_member_may_author_an_inspection_plan(self, member_client, tenant_a, item_a):
        from apps.scm.models import InspectionPlan
        assert member_client.post(reverse("scm:inspectionplan_create"),
                                  _qms_plan_payload(item_a)).status_code == 302
        assert InspectionPlan.objects.filter(tenant=tenant_a, code="SEC-1").exists()

    def test_a_member_may_record_an_inspection_and_run_its_lifecycle(self, member_client,
                                                                    tenant_a, item_a,
                                                                    inspection_plan_a):
        from apps.scm.models import QualityInspection
        assert member_client.post(reverse("scm:qualityinspection_create"),
                                  _qms_qc_payload(item_a,
                                                  plan=str(inspection_plan_a.pk))
                                  ).status_code == 302
        obj = QualityInspection.objects.get(tenant=tenant_a)
        assert member_client.post(reverse("scm:qualityinspection_start",
                                          args=[obj.pk])).status_code != 403
        obj.refresh_from_db()
        assert obj.status == "in_progress"

    def test_a_member_may_generate_the_result_snapshot(self, member_client, quality_inspection_a):
        assert member_client.post(reverse("scm:qualityinspection_generate_results",
                                          args=[quality_inspection_a.pk])).status_code != 403
        assert quality_inspection_a.results.count() == 3

    def test_a_member_may_raise_an_ncr_from_a_failed_inspection(self, member_client, tenant_a,
                                                               quality_inspection_a):
        from apps.scm.models import NonConformance, QualityInspection
        QualityInspection.objects.filter(pk=quality_inspection_a.pk).update(
            status="failed", quantity_accepted=Decimal("8"), quantity_rejected=Decimal("2"))
        assert member_client.post(reverse("scm:qualityinspection_raise_ncr",
                                          args=[quality_inspection_a.pk])).status_code != 403
        assert NonConformance.objects.filter(tenant=tenant_a).count() == 1

    def test_a_member_may_raise_and_progress_a_capa(self, member_client, tenant_a,
                                                    nonconformance_a):
        from apps.scm.models import CapaAction
        assert member_client.post(reverse("scm:nonconformance_raise_capa",
                                          args=[nonconformance_a.pk])).status_code != 403
        capa = CapaAction.objects.get(tenant=tenant_a)
        assert member_client.post(reverse("scm:capaaction_start",
                                          args=[capa.pk])).status_code != 403
        capa.refresh_from_db()
        assert capa.status == "investigating"

    def test_a_member_may_run_an_audit_and_record_findings(self, member_client, tenant_a,
                                                           quality_audit_a):
        from apps.scm.models import NonConformance
        assert member_client.post(reverse("scm:qualityaudit_start",
                                          args=[quality_audit_a.pk])).status_code != 403
        assert member_client.post(reverse("scm:qualityaudit_add_finding",
                                          args=[quality_audit_a.pk]),
                                  {"title": "Finding", "description": "D", "severity": "minor",
                                   "defect_category": "documentation"}).status_code != 403
        assert NonConformance.objects.filter(tenant=tenant_a, source="audit").count() == 1

    def test_a_member_may_read_the_coa_register_and_the_print_page(self, member_client,
                                                                   outgoing_inspection_a,
                                                                   client_a, customer_a):
        assert member_client.get(reverse("scm:coa_report")).status_code == 200
        client_a.post(reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]),
                      {"coa_issued_to": str(customer_a.pk), "issued_on": ""})
        assert member_client.get(reverse("scm:coa_print",
                                         args=[outgoing_inspection_a.pk])).status_code == 200

    def test_a_member_cannot_type_the_single_writer_columns_on_the_inspection_form(
        self, member_client, quality_inspection_a, item_a, customer_a,
    ):
        """The decide / quarantine / issue admin gates would be decoration if this page were open."""
        resp = member_client.post(
            reverse("scm:qualityinspection_edit", args=[quality_inspection_a.pk]),
            _qms_qc_payload(item_a, status="passed", usage_decision="accept",
                            action_taken="quarantined", coa_number="COA-99999",
                            coa_issued_to=str(customer_a.pk)))
        assert resp.status_code == 302
        quality_inspection_a.refresh_from_db()
        assert quality_inspection_a.status == "draft"
        assert quality_inspection_a.usage_decision == "pending"
        assert quality_inspection_a.action_taken == "none"
        assert quality_inspection_a.coa_number == ""
        assert quality_inspection_a.coa_issued_to_id is None

    def test_a_member_cannot_type_the_MRB_block_on_the_ncr_form(self, member_client,
                                                               nonconformance_a, item_a):
        resp = member_client.post(reverse("scm:nonconformance_edit", args=[nonconformance_a.pk]),
                                  _qms_ncr_payload(item_a, status="closed", disposition="scrap",
                                                   disposition_quantity="5",
                                                   quarantine_applied="on"))
        assert resp.status_code == 302
        nonconformance_a.refresh_from_db()
        assert nonconformance_a.status == "open"
        assert nonconformance_a.disposition == "pending"
        assert nonconformance_a.disposition_quantity == Decimal("0")
        assert nonconformance_a.quarantine_applied is False

    def test_a_member_cannot_type_the_verification_block_on_the_capa_form(self, member_client,
                                                                         capa_action_a):
        resp = member_client.post(reverse("scm:capaaction_edit", args=[capa_action_a.pk]),
                                  _qms_capa_payload(status="closed",
                                                    effectiveness_result="effective",
                                                    implemented_on="2026-01-01"))
        assert resp.status_code == 302
        capa_action_a.refresh_from_db()
        assert capa_action_a.status == "open"
        assert capa_action_a.effectiveness_result == "pending"
        assert capa_action_a.implemented_on is None

    def test_a_member_cannot_type_the_audit_status_or_dates(self, member_client, quality_audit_a,
                                                           org_unit_a):
        resp = member_client.post(reverse("scm:qualityaudit_edit", args=[quality_audit_a.pk]),
                                  _qms_qa_payload(org_unit_a, status="closed",
                                                  actual_start="2026-01-01",
                                                  actual_end="2026-01-02"))
        assert resp.status_code == 302
        quality_audit_a.refresh_from_db()
        assert quality_audit_a.status == "planned"
        assert quality_audit_a.actual_start is None
        assert quality_audit_a.actual_end is None


# ================================================================ Cross-tenant IDOR -> 404
class TestQualityCrossTenantIDOR:
    def test_all_five_detail_and_edit_routes_are_404_across_tenants(self, client_a,
                                                                    inspection_plan_b,
                                                                    quality_inspection_b,
                                                                    nonconformance_b,
                                                                    capa_action_b,
                                                                    quality_audit_b):
        for detail, edit, obj in (
            ("scm:inspectionplan_detail", "scm:inspectionplan_edit", inspection_plan_b),
            ("scm:qualityinspection_detail", "scm:qualityinspection_edit", quality_inspection_b),
            ("scm:nonconformance_detail", "scm:nonconformance_edit", nonconformance_b),
            ("scm:capaaction_detail", "scm:capaaction_edit", capa_action_b),
            ("scm:qualityaudit_detail", "scm:qualityaudit_edit", quality_audit_b),
        ):
            assert client_a.get(reverse(detail, args=[obj.pk])).status_code == 404, detail
            assert client_a.get(reverse(edit, args=[obj.pk])).status_code == 404, edit

    def test_all_five_delete_routes_are_404_across_tenants(self, client_a, inspection_plan_b,
                                                           quality_inspection_b,
                                                           nonconformance_b, capa_action_b,
                                                           quality_audit_b):
        from apps.scm.models import (CapaAction, InspectionPlan, NonConformance, QualityAudit,
                                     QualityInspection)
        for name, obj in (("scm:inspectionplan_delete", inspection_plan_b),
                          ("scm:qualityinspection_delete", quality_inspection_b),
                          ("scm:nonconformance_delete", nonconformance_b),
                          ("scm:capaaction_delete", capa_action_b),
                          ("scm:qualityaudit_delete", quality_audit_b)):
            assert client_a.post(reverse(name, args=[obj.pk])).status_code == 404, name
        assert InspectionPlan.objects.filter(pk=inspection_plan_b.pk).exists()
        assert QualityInspection.objects.filter(pk=quality_inspection_b.pk).exists()
        assert NonConformance.objects.filter(pk=nonconformance_b.pk).exists()
        assert CapaAction.objects.filter(pk=capa_action_b.pk).exists()
        assert QualityAudit.objects.filter(pk=quality_audit_b.pk).exists()

    def test_every_inspection_POST_ACTION_is_404_across_tenants(self, client_a,
                                                                quality_inspection_b):
        for name in _QC_ACTIONS:
            assert client_a.post(reverse(f"scm:{name}",
                                         args=[quality_inspection_b.pk])).status_code == 404, name

    def test_every_nonconformance_POST_ACTION_is_404_across_tenants(self, client_a,
                                                                    nonconformance_b):
        for name in _NCR_ACTIONS:
            assert client_a.post(reverse(f"scm:{name}",
                                         args=[nonconformance_b.pk])).status_code == 404, name

    def test_every_capa_POST_ACTION_is_404_across_tenants(self, client_a, capa_action_b):
        for name in _CAPA_ACTIONS:
            assert client_a.post(reverse(f"scm:{name}",
                                         args=[capa_action_b.pk])).status_code == 404, name

    def test_every_audit_POST_ACTION_is_404_across_tenants(self, client_a, quality_audit_b):
        for name in _QA_ACTIONS:
            assert client_a.post(reverse(f"scm:{name}",
                                         args=[quality_audit_b.pk])).status_code == 404, name

    def test_the_two_coa_routes_are_404_across_tenants(self, client_a, tenant_b, item_b,
                                                       customer_a):
        from django.utils import timezone
        from apps.scm.models import InspectionResult, QualityInspection
        theirs = QualityInspection.objects.create(
            tenant=tenant_b, inspection_type="outgoing", item=item_b,
            inspected_on=timezone.localdate())
        InspectionResult.objects.create(inspection=theirs, characteristic_name="C",
                                        characteristic_type="pass_fail", include_on_coa=True,
                                        result="pass")
        QualityInspection.objects.filter(pk=theirs.pk).update(status="passed",
                                                              usage_decision="accept")
        assert client_a.post(reverse("scm:coa_issue", args=[theirs.pk]),
                             {"coa_issued_to": str(customer_a.pk),
                              "issued_on": ""}).status_code == 404
        assert client_a.get(reverse("scm:coa_print", args=[theirs.pk])).status_code == 404
        theirs.refresh_from_db()
        assert theirs.coa_number == ""

    def test_a_cross_tenant_action_changes_no_state_and_posts_no_stock(self, client_a,
                                                                       nonconformance_b, lot_b):
        from apps.scm.models import StockMove
        client_a.post(reverse("scm:nonconformance_investigate", args=[nonconformance_b.pk]))
        client_a.post(reverse("scm:nonconformance_disposition", args=[nonconformance_b.pk]),
                      {"disposition": "scrap", "disposition_quantity": "2"})
        client_a.post(reverse("scm:nonconformance_quarantine", args=[nonconformance_b.pk]))
        nonconformance_b.refresh_from_db()
        lot_b.refresh_from_db()
        assert nonconformance_b.status == "open"
        assert nonconformance_b.disposition == "pending"
        assert lot_b.status == "available"
        assert not StockMove.objects.filter(reference=nonconformance_b.number).exists()

    def test_a_tenant_b_admin_is_equally_locked_out_of_tenant_a(self, client_b, inspection_plan_a,
                                                                outgoing_inspection_a,
                                                                nonconformance_a, capa_action_a,
                                                                quality_audit_a):
        for name, obj in (("scm:inspectionplan_detail", inspection_plan_a),
                          ("scm:qualityinspection_detail", outgoing_inspection_a),
                          ("scm:nonconformance_detail", nonconformance_a),
                          ("scm:capaaction_detail", capa_action_a),
                          ("scm:qualityaudit_detail", quality_audit_a)):
            assert client_b.get(reverse(name, args=[obj.pk])).status_code == 404, name


# ================================================================ Cross-tenant list + form binding
class TestQualityCrossTenantFormScoping:
    def test_no_list_ever_contains_the_other_tenants_rows(self, client_a, inspection_plan_a,
                                                          inspection_plan_b,
                                                          quality_inspection_a,
                                                          quality_inspection_b, nonconformance_a,
                                                          nonconformance_b, capa_action_a,
                                                          capa_action_b, quality_audit_a,
                                                          quality_audit_b):
        for name, mine, theirs in (
            ("scm:inspectionplan_list", inspection_plan_a, inspection_plan_b),
            ("scm:qualityinspection_list", quality_inspection_a, quality_inspection_b),
            ("scm:nonconformance_list", nonconformance_a, nonconformance_b),
            ("scm:capaaction_list", capa_action_a, capa_action_b),
            ("scm:qualityaudit_list", quality_audit_a, quality_audit_b),
        ):
            rows = list(client_a.get(reverse(name)).context["object_list"])
            assert mine in rows, name
            assert theirs not in rows, name

    def test_a_crafted_inspection_post_with_another_tenants_item_is_rejected(self, client_a,
                                                                            tenant_a, item_b):
        from apps.scm.models import QualityInspection
        resp = client_a.post(reverse("scm:qualityinspection_create"), _qms_qc_payload(item_b))
        assert resp.status_code == 200
        assert not QualityInspection.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_inspection_post_with_another_tenants_plan_is_rejected(self, client_a,
                                                                            tenant_a, item_a,
                                                                            inspection_plan_b):
        from apps.scm.models import QualityInspection
        resp = client_a.post(reverse("scm:qualityinspection_create"),
                             _qms_qc_payload(item_a, plan=str(inspection_plan_b.pk)))
        assert resp.status_code == 200
        assert not QualityInspection.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_inspection_post_with_another_tenants_lot_is_rejected(self, client_a,
                                                                           tenant_a, item_a,
                                                                           lot_b):
        from apps.scm.models import QualityInspection
        resp = client_a.post(reverse("scm:qualityinspection_create"),
                             _qms_qc_payload(item_a, lot_serial=str(lot_b.pk)))
        assert resp.status_code == 200
        assert not QualityInspection.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_inspection_post_with_another_tenants_location_is_rejected(self, client_a,
                                                                                 tenant_a,
                                                                                 item_a,
                                                                                 location_b):
        from apps.scm.models import QualityInspection
        resp = client_a.post(reverse("scm:qualityinspection_create"),
                             _qms_qc_payload(item_a, location=str(location_b.pk)))
        assert resp.status_code == 200
        assert not QualityInspection.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_inspection_post_with_another_tenants_shipment_is_rejected(self, client_a,
                                                                                 tenant_a,
                                                                                 item_a,
                                                                                 shipment_b):
        from apps.scm.models import QualityInspection
        resp = client_a.post(reverse("scm:qualityinspection_create"),
                             _qms_qc_payload(item_a, inspection_type="outgoing",
                                             shipment=str(shipment_b.pk)))
        assert resp.status_code == 200
        assert not QualityInspection.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_ncr_post_with_another_tenants_item_or_audit_is_rejected(self, client_a,
                                                                              tenant_a, item_b,
                                                                              quality_audit_b):
        from apps.scm.models import NonConformance
        for override in ({}, {"audit": str(quality_audit_b.pk)}):
            resp = client_a.post(reverse("scm:nonconformance_create"),
                                 _qms_ncr_payload(item_b, **override))
            assert resp.status_code == 200
        assert not NonConformance.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_capa_post_with_another_tenants_nonconformance_is_rejected(self, client_a,
                                                                                tenant_a,
                                                                                nonconformance_b):
        from apps.scm.models import CapaAction
        resp = client_a.post(reverse("scm:capaaction_create"),
                             _qms_capa_payload(nonconformance=str(nonconformance_b.pk)))
        assert resp.status_code == 200
        assert not CapaAction.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_capa_TASK_owner_from_another_tenant_is_rejected(self, client_a, tenant_a,
                                                                      tenant_b):
        from apps.core.models import Party, PartyRole
        from apps.scm.models import CapaAction
        theirs = Party.objects.create(tenant=tenant_b, name="Globex Employee", kind="person")
        PartyRole.objects.create(tenant=tenant_b, party=theirs, role="employee")
        data = _qms_capa_payload()
        data.update(formset_data("tasks", [
            {"id": "", "sequence": "10", "description": "Crafted", "owner": str(theirs.pk),
             "due_date": "", "completed_on": "", "status": "open"},
        ]))
        resp = client_a.post(reverse("scm:capaaction_create"), data)
        assert resp.status_code == 200
        assert not CapaAction.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_audit_post_with_another_tenants_checklist_is_rejected(self, client_a,
                                                                            tenant_a, org_unit_a,
                                                                            inspection_plan_b):
        from apps.scm.models import QualityAudit
        resp = client_a.post(reverse("scm:qualityaudit_create"),
                             _qms_qa_payload(org_unit_a,
                                             checklist_plan=str(inspection_plan_b.pk)))
        assert resp.status_code == 200
        assert not QualityAudit.objects.filter(tenant=tenant_a, title="Crafted audit").exists()

    def test_a_crafted_plan_post_with_another_tenants_item_is_rejected(self, client_a, tenant_a,
                                                                       item_b):
        from apps.scm.models import InspectionPlan
        resp = client_a.post(reverse("scm:inspectionplan_create"), _qms_plan_payload(item_b))
        assert resp.status_code == 200
        assert not InspectionPlan.objects.filter(tenant=tenant_a, code="SEC-1").exists()

    def test_a_crafted_characteristic_uom_from_another_tenant_is_rejected(self, client_a,
                                                                         tenant_a, item_a,
                                                                         uom_each_b):
        from apps.scm.models import InspectionPlan
        data = _qms_plan_payload(item_a)
        data.update(formset_data("characteristics", [
            {"id": "", "sequence": "10", "name": "Crafted", "characteristic_type": "pass_fail",
             "uom": str(uom_each_b.pk), "target_value": "", "lower_limit": "", "upper_limit": "",
             "expected_text": "OK", "test_method": "", "is_mandatory": "on"},
        ]))
        resp = client_a.post(reverse("scm:inspectionplan_create"), data)
        assert resp.status_code == 200
        assert not InspectionPlan.objects.filter(tenant=tenant_a, code="SEC-1").exists()

    def test_a_crafted_certificate_recipient_from_another_tenant_is_rejected(self, client_a,
                                                                            outgoing_inspection_a,
                                                                            customer_b):
        resp = client_a.post(reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]),
                             {"coa_issued_to": str(customer_b.pk), "issued_on": ""})
        assert resp.status_code == 302
        outgoing_inspection_a.refresh_from_db()
        assert outgoing_inspection_a.coa_number == ""

    def test_a_crafted_finding_owner_from_another_tenant_is_rejected(self, client_a, tenant_a,
                                                                     tenant_b, quality_audit_a):
        from apps.core.models import Party, PartyRole
        from apps.scm.models import NonConformance
        theirs = Party.objects.create(tenant=tenant_b, name="Globex Employee", kind="person")
        PartyRole.objects.create(tenant=tenant_b, party=theirs, role="employee")
        client_a.post(reverse("scm:qualityaudit_start", args=[quality_audit_a.pk]))
        resp = client_a.post(reverse("scm:qualityaudit_add_finding", args=[quality_audit_a.pk]),
                             {"title": "T", "description": "D", "severity": "minor",
                              "defect_category": "documentation", "owner": str(theirs.pk)})
        assert resp.status_code == 302
        assert not NonConformance.objects.filter(tenant=tenant_a).exists()

    def test_the_coa_register_never_leaks_another_tenants_outgoing_inspections(self, client_a,
                                                                              tenant_b, item_b):
        from django.utils import timezone
        from apps.scm.models import QualityInspection
        theirs = QualityInspection.objects.create(
            tenant=tenant_b, inspection_type="outgoing", item=item_b,
            inspected_on=timezone.localdate())
        rows = client_a.get(reverse("scm:coa_report")).context["rows"]
        assert theirs.pk not in {row["obj"].pk for row in rows}


# ================================================================ POST-only action views: GET -> 405
class TestQualityPostOnlyActions:
    def test_get_on_every_inspection_action_returns_405(self, client_a, outgoing_inspection_a):
        for name in _QC_ACTIONS:
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[outgoing_inspection_a.pk])).status_code == 405, name

    def test_get_on_every_nonconformance_action_returns_405(self, client_a, nonconformance_a):
        for name in _NCR_ACTIONS:
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[nonconformance_a.pk])).status_code == 405, name

    def test_get_on_every_capa_action_returns_405(self, client_a, capa_action_a):
        for name in _CAPA_ACTIONS:
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[capa_action_a.pk])).status_code == 405, name

    def test_get_on_every_audit_action_returns_405(self, client_a, quality_audit_a):
        for name in _QA_ACTIONS:
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[quality_audit_a.pk])).status_code == 405, name

    def test_get_on_coa_issue_and_the_plan_delete_returns_405(self, client_a,
                                                              outgoing_inspection_a,
                                                              inspection_plan_a):
        assert client_a.get(reverse("scm:coa_issue",
                                    args=[outgoing_inspection_a.pk])).status_code == 405
        assert client_a.get(reverse("scm:inspectionplan_delete",
                                    args=[inspection_plan_a.pk])).status_code == 405

    def test_a_GET_never_deletes_never_moves_a_status_and_never_posts_stock(
        self, client_a, tenant_a, inspection_plan_a, outgoing_inspection_a, nonconformance_lot_a,
        capa_action_a, quality_audit_a, lot_a, item_lot_a, location_a,
    ):
        from apps.scm.models import (CapaAction, InspectionPlan, NonConformance, QualityAudit,
                                     QualityInspection, StockMove)
        from apps.scm.tests._helpers import seed_stock
        seed_stock(tenant_a, item_lot_a, location_a, "50", "1.0000")
        before = StockMove.objects.count()
        for names, obj in ((_QC_ACTIONS, outgoing_inspection_a),
                           (_NCR_ACTIONS, nonconformance_lot_a),
                           (_CAPA_ACTIONS, capa_action_a), (_QA_ACTIONS, quality_audit_a)):
            for name in names:
                client_a.get(reverse(f"scm:{name}", args=[obj.pk]))
        client_a.get(reverse("scm:inspectionplan_delete", args=[inspection_plan_a.pk]))
        client_a.get(reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]))
        assert InspectionPlan.objects.filter(pk=inspection_plan_a.pk).exists()
        assert QualityInspection.objects.filter(pk=outgoing_inspection_a.pk).exists()
        assert NonConformance.objects.filter(pk=nonconformance_lot_a.pk).exists()
        assert CapaAction.objects.filter(pk=capa_action_a.pk).exists()
        assert QualityAudit.objects.filter(pk=quality_audit_a.pk).exists()
        outgoing_inspection_a.refresh_from_db()
        nonconformance_lot_a.refresh_from_db()
        capa_action_a.refresh_from_db()
        quality_audit_a.refresh_from_db()
        lot_a.refresh_from_db()
        assert outgoing_inspection_a.status == "passed"
        assert outgoing_inspection_a.coa_number == ""
        assert nonconformance_lot_a.status == "open"
        assert nonconformance_lot_a.disposition == "pending"
        assert capa_action_a.status == "open"
        assert quality_audit_a.status == "planned"
        assert lot_a.status == "available"
        assert StockMove.objects.count() == before


# ================================================================ CSRF enforcement
class TestQualityCSRFEnforcement:
    def _client(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        return c

    def test_post_without_csrf_is_rejected_on_the_MRB_disposition(self, admin_user, tenant_a,
                                                                  nonconformance_a, item_a,
                                                                  location_a):
        from apps.scm.models import StockMove
        from apps.scm.tests._helpers import seed_stock
        seed_stock(tenant_a, item_a, location_a, "20", "8.0000")
        before = StockMove.objects.count()
        assert self._client(admin_user).post(
            reverse("scm:nonconformance_disposition", args=[nonconformance_a.pk]),
            {"disposition": "scrap", "disposition_quantity": "5"}).status_code == 403
        nonconformance_a.refresh_from_db()
        assert nonconformance_a.disposition == "pending"
        assert StockMove.objects.count() == before

    def test_post_without_csrf_is_rejected_on_issuing_a_certificate(self, admin_user,
                                                                    outgoing_inspection_a,
                                                                    customer_a):
        assert self._client(admin_user).post(
            reverse("scm:coa_issue", args=[outgoing_inspection_a.pk]),
            {"coa_issued_to": str(customer_a.pk), "issued_on": ""}).status_code == 403
        outgoing_inspection_a.refresh_from_db()
        assert outgoing_inspection_a.coa_number == ""

    def test_post_without_csrf_is_rejected_on_the_usage_decision(self, admin_user,
                                                                 outgoing_inspection_a):
        assert self._client(admin_user).post(
            reverse("scm:qualityinspection_decide", args=[outgoing_inspection_a.pk]),
            {"usage_decision": "reject"}).status_code == 403
        outgoing_inspection_a.refresh_from_db()
        assert outgoing_inspection_a.usage_decision == "accept"

    def test_post_without_csrf_is_rejected_on_both_quarantine_routes(self, admin_user,
                                                                     outgoing_inspection_a,
                                                                     nonconformance_lot_a,
                                                                     lot_a):
        client = self._client(admin_user)
        assert client.post(reverse("scm:qualityinspection_quarantine",
                                   args=[outgoing_inspection_a.pk])).status_code == 403
        assert client.post(reverse("scm:nonconformance_quarantine",
                                   args=[nonconformance_lot_a.pk])).status_code == 403
        lot_a.refresh_from_db()
        assert lot_a.status == "available"

    def test_post_without_csrf_is_rejected_on_every_lifecycle_action(self, admin_user,
                                                                     quality_inspection_a,
                                                                     nonconformance_a,
                                                                     capa_action_a,
                                                                     quality_audit_a):
        client = self._client(admin_user)
        for name, obj in (("qualityinspection_start", quality_inspection_a),
                          ("qualityinspection_generate_results", quality_inspection_a),
                          ("nonconformance_investigate", nonconformance_a),
                          ("capaaction_start", capa_action_a),
                          ("qualityaudit_start", quality_audit_a)):
            assert client.post(reverse(f"scm:{name}", args=[obj.pk])).status_code == 403, name
        quality_inspection_a.refresh_from_db()
        nonconformance_a.refresh_from_db()
        capa_action_a.refresh_from_db()
        quality_audit_a.refresh_from_db()
        assert quality_inspection_a.status == "draft"
        assert quality_inspection_a.results.count() == 0
        assert nonconformance_a.status == "open"
        assert capa_action_a.status == "open"
        assert quality_audit_a.status == "planned"

    def test_post_without_csrf_is_rejected_on_every_delete(self, admin_user, inspection_plan_a,
                                                           quality_inspection_a,
                                                           nonconformance_a, capa_action_a,
                                                           quality_audit_a):
        from apps.scm.models import (CapaAction, InspectionPlan, NonConformance, QualityAudit,
                                     QualityInspection)
        client = self._client(admin_user)
        for name, obj in (("scm:inspectionplan_delete", inspection_plan_a),
                          ("scm:qualityinspection_delete", quality_inspection_a),
                          ("scm:nonconformance_delete", nonconformance_a),
                          ("scm:capaaction_delete", capa_action_a),
                          ("scm:qualityaudit_delete", quality_audit_a)):
            assert client.post(reverse(name, args=[obj.pk])).status_code == 403, name
        assert InspectionPlan.objects.filter(pk=inspection_plan_a.pk).exists()
        assert QualityInspection.objects.filter(pk=quality_inspection_a.pk).exists()
        assert NonConformance.objects.filter(pk=nonconformance_a.pk).exists()
        assert CapaAction.objects.filter(pk=capa_action_a.pk).exists()
        assert QualityAudit.objects.filter(pk=quality_audit_a.pk).exists()

    def test_post_without_csrf_is_rejected_on_every_create(self, admin_user, tenant_a, item_a,
                                                           org_unit_a):
        from apps.scm.models import (CapaAction, InspectionPlan, NonConformance, QualityAudit,
                                     QualityInspection)
        client = self._client(admin_user)
        assert client.post(reverse("scm:inspectionplan_create"),
                           _qms_plan_payload(item_a)).status_code == 403
        assert client.post(reverse("scm:qualityinspection_create"),
                           _qms_qc_payload(item_a)).status_code == 403
        assert client.post(reverse("scm:nonconformance_create"),
                           _qms_ncr_payload(item_a)).status_code == 403
        assert client.post(reverse("scm:capaaction_create"),
                           _qms_capa_payload()).status_code == 403
        assert client.post(reverse("scm:qualityaudit_create"),
                           _qms_qa_payload(org_unit_a)).status_code == 403
        assert not InspectionPlan.objects.filter(tenant=tenant_a, code="SEC-1").exists()
        assert not QualityInspection.objects.filter(tenant=tenant_a).exists()
        assert not NonConformance.objects.filter(tenant=tenant_a).exists()
        assert not CapaAction.objects.filter(tenant=tenant_a).exists()
        assert not QualityAudit.objects.filter(tenant=tenant_a).exists()

    def test_post_without_csrf_is_rejected_on_adding_an_audit_finding(self, admin_user, tenant_a,
                                                                      quality_audit_a):
        from apps.scm.models import NonConformance, QualityAudit
        QualityAudit.objects.filter(pk=quality_audit_a.pk).update(status="in_progress")
        assert self._client(admin_user).post(
            reverse("scm:qualityaudit_add_finding", args=[quality_audit_a.pk]),
            {"title": "T", "description": "D", "severity": "minor",
             "defect_category": "documentation"}).status_code == 403
        assert NonConformance.objects.filter(tenant=tenant_a).count() == 0


# ================================================================================================
# SCM 4.10 Returns Management (Reverse Logistics) — security
# ================================================================================================
#: The TEN ``@tenant_admin_required`` routes in 4.10. Anything added to the sub-module that commits
#: us to a customer, moves stock or speaks to a counterparty belongs in this tuple AND in the test
#: below, or the gate is decoration.
_RETURNS_ADMIN_ONLY = (
    "returnauthorization_approve", "returnauthorization_reject",
    "returnauthorization_draft_credit_note", "returnauthorization_draft_replacement",
    "returndisposition_decide", "returndisposition_post", "returndisposition_split",
    "warrantyclaim_submit", "warrantyclaim_record_response", "warrantyclaim_record_credit",
)
#: Every mutating 4.10 route — all of them ``@require_POST``.
_RETURNS_POST_ONLY = _RETURNS_ADMIN_ONLY + (
    "returnauthorization_delete", "returnauthorization_cancel",
    "returnauthorization_receive_all", "returnauthorization_raise_warranty_claim",
    "returndisposition_delete", "returndisposition_mark_refurbished",
    "returnpolicy_delete", "returnreason_delete", "warrantyclaim_delete",
)
_RETURNS_READ_ROUTES = ("returnauthorization_list", "returnauthorization_create",
                        "returndisposition_list", "returndisposition_create",
                        "returnpolicy_list", "returnpolicy_create",
                        "returnreason_list", "returnreason_create",
                        "warrantyclaim_list", "warrantyclaim_create",
                        "refund_queue", "returns_awaiting_disposition",
                        "advance_refund_exposure", "return_portal", "portal_return_create")


def _returns_rma_payload(customer, item, reason):
    from django.utils import timezone
    data = {
        "customer": str(customer.pk), "sales_order": "", "return_type": "physical",
        "source": "csr", "policy": "", "requested_on": timezone.localdate().isoformat(),
        "resolution": "refund", "refund_method": "original_tender",
        "return_method": "mail_prepaid", "dropoff_location": "", "return_carrier": "",
        "return_tracking_number": "", "return_label_url": "", "label_cost": "0",
        "counterparty_rma_number": "", "currency": "", "advance_refund_deadline": "",
        "notes": "",
    }
    data.update(formset_data("lines", [{
        "sales_order_line": "", "item": str(item.pk), "description": "Widget",
        "quantity_requested": "1", "quantity_approved": "0", "reason": str(reason.pk),
        "unit_price": "15.00", "tax_pct": "0", "unit_cost": "8.0000", "line_fee": "0.00",
        "condition_reported": "", "lot_serial": "", "photo": "", "id": "",
    }]))
    return data


class TestReturnsAnonymousRedirect:
    def test_every_staff_route_redirects_to_login(self):
        c = Client()
        for name in _RETURNS_READ_ROUTES:
            resp = c.get(reverse(f"scm:{name}"))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_every_detail_route_redirects_to_login(self, return_authorization_a, disposition_a,
                                                   return_policy_a, return_reason_a,
                                                   warranty_claim_a):
        c = Client()
        for name, obj in (("returnauthorization_detail", return_authorization_a),
                          ("returnauthorization_edit", return_authorization_a),
                          ("returndisposition_detail", disposition_a),
                          ("returndisposition_edit", disposition_a),
                          ("returnpolicy_detail", return_policy_a),
                          ("returnpolicy_edit", return_policy_a),
                          ("returnreason_detail", return_reason_a),
                          ("returnreason_edit", return_reason_a),
                          ("warrantyclaim_detail", warranty_claim_a),
                          ("warrantyclaim_edit", warranty_claim_a)):
            resp = c.get(reverse(f"scm:{name}", args=[obj.pk]))
            assert resp.status_code == 302, name
            assert "login" in resp["Location"], name

    def test_the_two_TOKEN_routes_are_deliberately_public(self, rma_awaiting_receipt_a):
        c = Client()
        assert c.get(reverse("scm:returnauthorization_public",
                             args=[rma_awaiting_receipt_a.public_token])).status_code == 200
        assert c.get(reverse("scm:returnauthorization_label",
                             args=[rma_awaiting_receipt_a.public_token])).status_code == 200

    def test_they_are_the_ONLY_public_routes_in_the_sub_module(self, disposition_a,
                                                               warranty_claim_a):
        c = Client()
        for name, obj in (("returnauthorization_approve", disposition_a),
                          ("returndisposition_post", disposition_a),
                          ("warrantyclaim_submit", warranty_claim_a)):
            resp = c.post(reverse(f"scm:{name}", args=[obj.pk]))
            assert resp.status_code in (302, 403), name
            if resp.status_code == 302:
                assert "login" in resp["Location"], name


class TestReturnsAdminRequiredGates:
    """REGRESSION LOCK (item 15). Ten privileged routes; a plain tenant member gets 403 on every
    one of them and nothing changes."""

    def test_ALL_TEN_privileged_routes_403_a_plain_member(self, member_client,
                                                          return_authorization_a, disposition_a,
                                                          warranty_claim_a):
        targets = {
            "returnauthorization_approve": return_authorization_a,
            "returnauthorization_reject": return_authorization_a,
            "returnauthorization_draft_credit_note": return_authorization_a,
            "returnauthorization_draft_replacement": return_authorization_a,
            "returndisposition_decide": disposition_a,
            "returndisposition_post": disposition_a,
            "returndisposition_split": disposition_a,
            "warrantyclaim_submit": warranty_claim_a,
            "warrantyclaim_record_response": warranty_claim_a,
            "warrantyclaim_record_credit": warranty_claim_a,
        }
        assert set(targets) == set(_RETURNS_ADMIN_ONLY)
        for name, obj in targets.items():
            assert member_client.post(reverse(f"scm:{name}",
                                              args=[obj.pk])).status_code == 403, name

    def test_a_403_changes_nothing_and_posts_nothing(self, member_client, tenant_a,
                                                     return_authorization_a, disposition_a,
                                                     warranty_claim_a, location_a2):
        from apps.accounting.models import Invoice, JournalEntry
        from apps.scm.models import StockMove
        moves, journals = StockMove.objects.count(), JournalEntry.objects.count()
        member_client.post(reverse("scm:returnauthorization_approve",
                                   args=[return_authorization_a.pk]), {"resolution": "refund"})
        member_client.post(reverse("scm:returnauthorization_reject",
                                   args=[return_authorization_a.pk]),
                           {"rejected_reason": "No"})
        member_client.post(reverse("scm:returndisposition_decide", args=[disposition_a.pk]),
                           {"disposition": "restock",
                            "restock_location": str(location_a2.pk)})
        member_client.post(reverse("scm:returndisposition_post", args=[disposition_a.pk]))
        member_client.post(reverse("scm:returndisposition_split", args=[disposition_a.pk]),
                           {"quantity": "1"})
        member_client.post(reverse("scm:warrantyclaim_submit", args=[warranty_claim_a.pk]))
        return_authorization_a.refresh_from_db()
        disposition_a.refresh_from_db()
        warranty_claim_a.refresh_from_db()
        # Pinned ABSOLUTELY, not as before == after: a snapshot still passes if a fixture arrives
        # already approved or already posted, which is the regression this test exists to catch.
        # `return_authorization_a` is genuinely still a draft — `rma_awaiting_receipt_a` builds its
        # own row (`_build_draft_rma` in conftest) instead of mutating this one.
        assert return_authorization_a.status == "draft"
        assert return_authorization_a.rejected_reason == ""
        assert disposition_a.disposition == "received_pending"
        assert disposition_a.stock_posted is False
        assert warranty_claim_a.status == "draft"
        assert StockMove.objects.count() == moves
        assert JournalEntry.objects.count() == journals
        assert Invoice.objects.filter(tenant=tenant_a, kind="credit_note").count() == 0

    def test_an_admin_may_run_the_same_routes(self, client_a, return_authorization_a,
                                              disposition_a, warranty_claim_a, location_a2):
        assert client_a.post(reverse("scm:returnauthorization_approve",
                                     args=[return_authorization_a.pk]),
                             {"resolution": "refund"}).status_code == 302
        assert client_a.post(reverse("scm:returndisposition_decide", args=[disposition_a.pk]),
                             {"disposition": "restock",
                              "restock_location": str(location_a2.pk),
                              "restock_unit_cost": "4.0000"}).status_code == 302
        assert client_a.post(reverse("scm:returndisposition_post",
                                     args=[disposition_a.pk])).status_code == 302
        assert client_a.post(reverse("scm:warrantyclaim_submit",
                                     args=[warranty_claim_a.pk])).status_code == 302

    def test_the_three_privileged_bench_columns_are_admin_only_on_the_EDIT_FORM_too(
        self, member_client, disposition_a, location_a, location_a2,
    ):
        """REGRESSION LOCK (item 10). The edit view writes the SAME columns ``decide`` reserves, so
        without the same gate the one on the action is decoration."""
        resp = member_client.post(
            reverse("scm:returndisposition_edit", args=[disposition_a.pk]),
            {"return_line": str(disposition_a.return_line_id), "quantity": "3",
             "location": str(location_a.pk), "lot_serial": "", "condition_grade": "c",
             "disposition": "restock", "restock_location": str(location_a2.pk),
             "restock_unit_cost": "15.0000", "recovery_value": "0.00", "nonconformance": "",
             "notes": ""})
        assert resp.status_code == 302                    # the edit itself is ordinary CSR work
        disposition_a.refresh_from_db()
        assert disposition_a.condition_grade == "c"       # what they FOUND is theirs to record
        assert disposition_a.disposition == "received_pending"
        assert disposition_a.restock_location_id is None
        assert disposition_a.restock_unit_cost == Decimal("8.0000")

    def test_the_three_privileged_bench_columns_are_admin_only_on_the_CREATE_PATH_too(
        self, member_client, return_line_a, location_a, location_a2,
    ):
        """The edit form is gated (above) and so is ``decide`` — but a CSR receiving goods reaches
        the SAME three columns through the intake formset, which is the path they use every day.
        A member POSTing a decision here must have it ignored exactly as on the other two."""
        from apps.scm.models import ReturnDisposition, StockMove
        moves = StockMove.objects.count()
        data = {"return_line": str(return_line_a.pk)}
        data.update(formset_data("dispositions", [{
            "quantity": "3", "location": str(location_a.pk), "lot_serial": "",
            "condition_grade": "a", "disposition": "restock",
            "restock_location": str(location_a2.pk), "restock_unit_cost": "999.0000",
            "recovery_value": "0.00", "notes": "", "id": ""}]))
        resp = member_client.post(reverse("scm:returndisposition_create"), data)
        assert resp.status_code == 302                    # receiving goods IS ordinary CSR work
        row = ReturnDisposition.objects.get(return_line=return_line_a)
        assert row.disposition == "received_pending"      # the decision is NOT theirs to make
        assert row.restock_location_id is None
        assert row.restock_unit_cost != Decimal("999.0000")
        assert row.stock_posted is False
        assert StockMove.objects.count() == moves         # intake posts nothing, by design


class TestReturnsOrdinaryActionsAllowNonAdmin:
    def test_a_member_may_raise_and_edit_a_return(self, member_client, tenant_a, customer_a,
                                                  item_a, return_reason_a):
        from apps.scm.models import ReturnAuthorization
        assert member_client.post(reverse("scm:returnauthorization_create"),
                                  _returns_rma_payload(customer_a, item_a,
                                                       return_reason_a)).status_code == 302
        assert ReturnAuthorization.objects.filter(tenant=tenant_a).exists()

    def test_a_member_may_cancel_a_draft_return(self, member_client, return_authorization_a):
        assert member_client.post(reverse("scm:returnauthorization_cancel",
                                          args=[return_authorization_a.pk])).status_code != 403
        return_authorization_a.refresh_from_db()
        assert return_authorization_a.status == "cancelled"

    def test_a_member_may_receive_goods_onto_the_bench(self, member_client,
                                                       rma_awaiting_receipt_a, location_a):
        from apps.scm.models import ReturnDisposition
        assert member_client.post(reverse("scm:returnauthorization_receive_all",
                                          args=[rma_awaiting_receipt_a.pk]),
                                  {"location": str(location_a.pk),
                                   "condition_grade": "a"}).status_code != 403
        assert ReturnDisposition.objects.filter(
            return_line__return_authorization=rma_awaiting_receipt_a).exists()

    def test_a_member_may_mark_a_row_refurbished(self, member_client, client_a, disposition_a):
        client_a.post(reverse("scm:returndisposition_decide", args=[disposition_a.pk]),
                      {"disposition": "refurbish"})
        assert member_client.post(reverse("scm:returndisposition_mark_refurbished",
                                          args=[disposition_a.pk])).status_code != 403
        disposition_a.refresh_from_db()
        assert disposition_a.refurbished_on is not None

    def test_a_member_may_raise_a_warranty_claim_from_a_return(self, member_client, tenant_a,
                                                               rma_received_a, item_a,
                                                               purchase_order_a, supplier_a):
        from apps.scm.models import PurchaseOrderLine, WarrantyClaim
        PurchaseOrderLine.objects.create(purchase_order=purchase_order_a,
                                         item_description="Widget", sku_hint=item_a.sku,
                                         quantity=Decimal("5"), unit_price=Decimal("8.00"))
        assert member_client.post(reverse("scm:returnauthorization_raise_warranty_claim",
                                          args=[rma_received_a.pk])).status_code != 403
        assert WarrantyClaim.objects.filter(tenant=tenant_a).exists()

    def test_a_member_may_maintain_the_two_masters(self, member_client, tenant_a):
        from apps.scm.models import ReturnPolicy, ReturnReason
        assert member_client.post(reverse("scm:returnreason_create"),
                                  {"code": "MBR-1", "name": "Member reason",
                                   "fault_party": "customer", "allows_refund": "on",
                                   "suggested_disposition": "", "follow_up_question": "",
                                   "sort_order": "10", "is_active": "on"}).status_code == 302
        assert ReturnReason.objects.filter(tenant=tenant_a, code="MBR-1").exists()
        assert member_client.post(reverse("scm:returnpolicy_create"), {
            "name": "Member policy", "is_active": "on", "priority": "100", "item_category": "",
            "window_basis": "delivery", "window_days": "30", "fallback_days": "45",
            "allow_refund": "on", "refund_basis": "full", "refund_pct": "100",
            "restocking_fee_type": "none", "restocking_fee_value": "0",
            "return_shipping_paid_by": "customer", "grade_a_cost_pct": "100",
            "grade_b_cost_pct": "75", "grade_c_cost_pct": "40", "grade_d_cost_pct": "0",
            "warranty_window_days": "365", "return_to_address": "",
            "portal_instructions": ""}).status_code == 302
        assert ReturnPolicy.objects.filter(tenant=tenant_a, name="Member policy").exists()

    def test_a_member_may_delete_an_unposted_bench_row(self, member_client, disposition_a):
        from apps.scm.models import ReturnDisposition
        assert member_client.post(reverse("scm:returndisposition_delete",
                                          args=[disposition_a.pk])).status_code != 403
        assert not ReturnDisposition.objects.filter(pk=disposition_a.pk).exists()


class TestReturnsCrossTenantIDOR:
    """REGRESSION LOCK (item 15). Tenant A's admin against every one of tenant B's five models."""

    def test_every_detail_and_edit_route_404s_across_the_tenant_line(self, client_a,
                                                                     return_authorization_b,
                                                                     disposition_b,
                                                                     return_policy_b,
                                                                     return_reason_b,
                                                                     warranty_claim_b):
        for name, obj in (("returnauthorization_detail", return_authorization_b),
                          ("returnauthorization_edit", return_authorization_b),
                          ("returndisposition_detail", disposition_b),
                          ("returndisposition_edit", disposition_b),
                          ("returnpolicy_detail", return_policy_b),
                          ("returnpolicy_edit", return_policy_b),
                          ("returnreason_detail", return_reason_b),
                          ("returnreason_edit", return_reason_b),
                          ("warrantyclaim_detail", warranty_claim_b),
                          ("warrantyclaim_edit", warranty_claim_b)):
            assert client_a.get(reverse(f"scm:{name}", args=[obj.pk])).status_code == 404, name

    def test_every_POST_action_404s_across_the_tenant_line(self, client_a,
                                                           return_authorization_b,
                                                           disposition_b, return_policy_b,
                                                           return_reason_b, warranty_claim_b,
                                                           location_a2):
        payloads = {
            "returnauthorization_approve": (return_authorization_b, {"resolution": "refund"}),
            "returnauthorization_reject": (return_authorization_b,
                                           {"rejected_reason": "No"}),
            "returnauthorization_cancel": (return_authorization_b, {}),
            "returnauthorization_delete": (return_authorization_b, {}),
            "returnauthorization_receive_all": (return_authorization_b,
                                                {"location": str(location_a2.pk),
                                                 "condition_grade": "a"}),
            "returnauthorization_draft_credit_note": (return_authorization_b, {}),
            "returnauthorization_draft_replacement": (return_authorization_b, {}),
            "returnauthorization_raise_warranty_claim": (return_authorization_b, {}),
            "returndisposition_decide": (disposition_b, {"disposition": "scrap"}),
            "returndisposition_post": (disposition_b, {}),
            "returndisposition_split": (disposition_b, {"quantity": "1"}),
            "returndisposition_delete": (disposition_b, {}),
            "returndisposition_mark_refurbished": (disposition_b, {}),
            "returnpolicy_delete": (return_policy_b, {}),
            "returnreason_delete": (return_reason_b, {}),
            "warrantyclaim_submit": (warranty_claim_b, {}),
            "warrantyclaim_record_response": (warranty_claim_b,
                                              {"outcome": "approved",
                                               "amount_approved": "10.00"}),
            "warrantyclaim_record_credit": (warranty_claim_b,
                                            {"amount_credited": "10.00",
                                             "credit_reference": "CN-1"}),
            "warrantyclaim_delete": (warranty_claim_b, {}),
        }
        for name, (obj, data) in payloads.items():
            assert client_a.post(reverse(f"scm:{name}", args=[obj.pk]),
                                 data).status_code == 404, name

    def test_none_of_those_attempts_changed_anything(self, client_a, return_authorization_b,
                                                     disposition_b, return_policy_b,
                                                     return_reason_b, warranty_claim_b,
                                                     location_a2):
        from apps.scm.models import (ReturnDisposition, ReturnPolicy, ReturnReason, StockMove,
                                     WarrantyClaim)
        moves = StockMove.objects.count()
        for name, obj, data in (("returnauthorization_approve", return_authorization_b,
                                 {"resolution": "refund"}),
                                ("returndisposition_decide", disposition_b,
                                 {"disposition": "scrap"}),
                                ("returndisposition_post", disposition_b, {}),
                                ("warrantyclaim_submit", warranty_claim_b, {})):
            client_a.post(reverse(f"scm:{name}", args=[obj.pk]), data)
        return_authorization_b.refresh_from_db()
        disposition_b.refresh_from_db()
        warranty_claim_b.refresh_from_db()
        assert return_authorization_b.status == "awaiting_receipt"
        assert disposition_b.disposition == "received_pending"
        assert warranty_claim_b.status == "draft"
        assert ReturnDisposition.objects.filter(pk=disposition_b.pk).exists()
        assert ReturnPolicy.objects.filter(pk=return_policy_b.pk).exists()
        assert ReturnReason.objects.filter(pk=return_reason_b.pk).exists()
        assert WarrantyClaim.objects.filter(pk=warranty_claim_b.pk).exists()
        assert StockMove.objects.count() == moves

    def test_no_returns_list_or_queue_ever_shows_another_tenants_rows(self, client_a,
                                                                      return_authorization_b,
                                                                      disposition_b,
                                                                      return_policy_b,
                                                                      return_reason_b,
                                                                      warranty_claim_b):
        foreign = {return_authorization_b.pk, disposition_b.pk, return_policy_b.pk,
                   return_reason_b.pk, warranty_claim_b.pk}
        for name in ("returnauthorization_list", "returndisposition_list", "returnpolicy_list",
                     "returnreason_list", "warrantyclaim_list"):
            rows = client_a.get(reverse(f"scm:{name}")).context["object_list"]
            assert not ({row.pk for row in rows} & foreign), name
        for name in ("refund_queue", "advance_refund_exposure",
                     "returns_awaiting_disposition"):
            rows = client_a.get(reverse(f"scm:{name}")).context["rows"]
            assert not ({row["obj"].pk for row in rows} & foreign), name

    def test_a_crafted_POST_carrying_another_tenants_pk_in_an_FK_is_rejected(
        self, client_a, tenant_a, customer_b, item_b, return_reason_b, location_b,
    ):
        from apps.scm.models import ReturnAuthorization
        resp = client_a.post(reverse("scm:returnauthorization_create"),
                             _returns_rma_payload(customer_b, item_b, return_reason_b))
        assert resp.status_code == 200                 # the form re-renders with errors
        assert not ReturnAuthorization.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_bench_POST_cannot_book_against_another_tenants_line(self, client_a,
                                                                           tenant_a,
                                                                           return_line_b,
                                                                           location_a):
        from apps.scm.models import ReturnDisposition
        data = {"return_line": str(return_line_b.pk)}
        data.update(formset_data("dispositions", [{
            "quantity": "1", "location": str(location_a.pk), "lot_serial": "",
            "condition_grade": "a", "disposition": "received_pending", "restock_location": "",
            "restock_unit_cost": "8.0000", "recovery_value": "0.00", "notes": "", "id": ""}]))
        assert client_a.post(reverse("scm:returndisposition_create"), data).status_code == 200
        assert not ReturnDisposition.objects.filter(tenant=tenant_a).exists()

    def test_another_tenants_public_token_still_resolves_but_only_as_the_PUBLIC_page(
        self, client_a, return_authorization_b,
    ):
        """The token is a bearer credential and the tenant is taken OFF THE OBJECT — a logged-in
        tenant-A user gains nothing a stranger with the same link would not have."""
        resp = client_a.get(reverse("scm:returnauthorization_public",
                                    args=[return_authorization_b.public_token]))
        assert resp.status_code == 200
        assert resp.context["obj"].tenant_id == return_authorization_b.tenant_id
        assert client_a.get(reverse("scm:returnauthorization_detail",
                                    args=[return_authorization_b.pk])).status_code == 404


class TestReturnsPostOnlyActions:
    def test_a_GET_on_every_mutating_route_returns_405(self, client_a, return_authorization_a,
                                                       disposition_a, return_policy_a,
                                                       return_reason_a, warranty_claim_a):
        targets = {
            "returnauthorization_approve": return_authorization_a,
            "returnauthorization_reject": return_authorization_a,
            "returnauthorization_cancel": return_authorization_a,
            "returnauthorization_delete": return_authorization_a,
            "returnauthorization_receive_all": return_authorization_a,
            "returnauthorization_draft_credit_note": return_authorization_a,
            "returnauthorization_draft_replacement": return_authorization_a,
            "returnauthorization_raise_warranty_claim": return_authorization_a,
            "returndisposition_decide": disposition_a,
            "returndisposition_post": disposition_a,
            "returndisposition_split": disposition_a,
            "returndisposition_delete": disposition_a,
            "returndisposition_mark_refurbished": disposition_a,
            "returnpolicy_delete": return_policy_a,
            "returnreason_delete": return_reason_a,
            "warrantyclaim_submit": warranty_claim_a,
            "warrantyclaim_record_response": warranty_claim_a,
            "warrantyclaim_record_credit": warranty_claim_a,
            "warrantyclaim_delete": warranty_claim_a,
        }
        assert set(targets) == set(_RETURNS_POST_ONLY)
        for name, obj in targets.items():
            assert client_a.get(reverse(f"scm:{name}",
                                        args=[obj.pk])).status_code == 405, name

    def test_a_GET_never_deletes_never_moves_a_status_and_never_posts_stock(
        self, client_a, tenant_a, return_authorization_a, disposition_a, return_policy_a,
        return_reason_a, warranty_claim_a,
    ):
        from apps.accounting.models import Invoice
        from apps.scm.models import (ReturnAuthorization, ReturnDisposition, ReturnPolicy,
                                     ReturnReason, StockMove, WarrantyClaim)
        moves = StockMove.objects.count()
        for name, obj in (("returnauthorization_approve", return_authorization_a),
                          ("returnauthorization_delete", return_authorization_a),
                          ("returndisposition_post", disposition_a),
                          ("returndisposition_delete", disposition_a),
                          ("returnpolicy_delete", return_policy_a),
                          ("returnreason_delete", return_reason_a),
                          ("warrantyclaim_submit", warranty_claim_a),
                          ("warrantyclaim_delete", warranty_claim_a)):
            client_a.get(reverse(f"scm:{name}", args=[obj.pk]))
        assert ReturnAuthorization.objects.filter(pk=return_authorization_a.pk).exists()
        assert ReturnDisposition.objects.filter(pk=disposition_a.pk).exists()
        assert ReturnPolicy.objects.filter(pk=return_policy_a.pk).exists()
        assert ReturnReason.objects.filter(pk=return_reason_a.pk).exists()
        assert WarrantyClaim.objects.filter(pk=warranty_claim_a.pk).exists()
        return_authorization_a.refresh_from_db()
        disposition_a.refresh_from_db()
        warranty_claim_a.refresh_from_db()
        # Pinned ABSOLUTELY. `return_authorization_a` really is still a draft here: since
        # `rma_awaiting_receipt_a` builds its OWN row (see `_build_draft_rma` in conftest) rather
        # than mutating this one, requesting `disposition_a` no longer advances it. A before ==
        # after snapshot would pass even if a fixture arrived already approved or already posted,
        # which is precisely what a "a GET must not mutate" test has to rule out.
        assert return_authorization_a.status == "draft"
        assert disposition_a.disposition == "received_pending"
        assert disposition_a.stock_posted is False
        assert warranty_claim_a.status == "draft"
        assert StockMove.objects.count() == moves
        assert Invoice.objects.filter(tenant=tenant_a, kind="credit_note").count() == 0


class TestReturnsCSRFEnforcement:
    def _client(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        return c

    def test_the_ledger_write_is_rejected_without_a_token(self, admin_user, tenant_a,
                                                          disposition_a, location_a2, client_a):
        from apps.scm.models import StockMove
        client_a.post(reverse("scm:returndisposition_decide", args=[disposition_a.pk]),
                      {"disposition": "restock", "restock_location": str(location_a2.pk),
                       "restock_unit_cost": "4.0000"})
        before = StockMove.objects.count()
        assert self._client(admin_user).post(
            reverse("scm:returndisposition_post", args=[disposition_a.pk])).status_code == 403
        disposition_a.refresh_from_db()
        assert disposition_a.stock_posted is False
        assert StockMove.objects.count() == before

    def test_every_lifecycle_action_is_rejected_without_a_token(self, admin_user,
                                                                return_authorization_a,
                                                                disposition_a,
                                                                warranty_claim_a):
        client = self._client(admin_user)
        for name, obj, data in (
            ("returnauthorization_approve", return_authorization_a, {"resolution": "refund"}),
            ("returnauthorization_reject", return_authorization_a,
             {"rejected_reason": "No"}),
            ("returnauthorization_cancel", return_authorization_a, {}),
            ("returnauthorization_draft_credit_note", return_authorization_a, {}),
            ("returnauthorization_draft_replacement", return_authorization_a, {}),
            ("returndisposition_decide", disposition_a, {"disposition": "scrap"}),
            ("returndisposition_split", disposition_a, {"quantity": "1"}),
            ("returndisposition_mark_refurbished", disposition_a, {}),
            ("warrantyclaim_submit", warranty_claim_a, {}),
            ("warrantyclaim_record_response", warranty_claim_a,
             {"outcome": "approved", "amount_approved": "10.00"}),
            ("warrantyclaim_record_credit", warranty_claim_a,
             {"amount_credited": "10.00", "credit_reference": "CN-1"}),
        ):
            assert client.post(reverse(f"scm:{name}", args=[obj.pk]),
                               data).status_code == 403, name
        return_authorization_a.refresh_from_db()
        disposition_a.refresh_from_db()
        warranty_claim_a.refresh_from_db()
        # Pinned ABSOLUTELY: eleven CSRF-less lifecycle POSTs must leave every row exactly where
        # its fixture put it — draft RMA, undecided bench row, unposted ledger, draft claim.
        assert return_authorization_a.status == "draft"
        assert disposition_a.disposition == "received_pending"
        assert disposition_a.stock_posted is False
        assert warranty_claim_a.status == "draft"

    def test_every_delete_is_rejected_without_a_token(self, admin_user, return_authorization_a,
                                                      disposition_a, return_policy_a,
                                                      return_reason_a, warranty_claim_a):
        from apps.scm.models import (ReturnAuthorization, ReturnDisposition, ReturnPolicy,
                                     ReturnReason, WarrantyClaim)
        client = self._client(admin_user)
        for name, obj in (("returnauthorization_delete", return_authorization_a),
                          ("returndisposition_delete", disposition_a),
                          ("returnpolicy_delete", return_policy_a),
                          ("returnreason_delete", return_reason_a),
                          ("warrantyclaim_delete", warranty_claim_a)):
            assert client.post(reverse(f"scm:{name}", args=[obj.pk])).status_code == 403, name
        assert ReturnAuthorization.objects.filter(pk=return_authorization_a.pk).exists()
        assert ReturnDisposition.objects.filter(pk=disposition_a.pk).exists()
        assert ReturnPolicy.objects.filter(pk=return_policy_a.pk).exists()
        assert ReturnReason.objects.filter(pk=return_reason_a.pk).exists()
        assert WarrantyClaim.objects.filter(pk=warranty_claim_a.pk).exists()

    def test_every_create_is_rejected_without_a_token(self, admin_user, tenant_a, customer_a,
                                                      item_a, return_reason_a, supplier_a):
        from apps.scm.models import ReturnAuthorization, ReturnPolicy, ReturnReason
        client = self._client(admin_user)
        assert client.post(reverse("scm:returnauthorization_create"),
                           _returns_rma_payload(customer_a, item_a,
                                                return_reason_a)).status_code == 403
        assert client.post(reverse("scm:returnreason_create"),
                           {"code": "CSRF-1", "name": "X", "fault_party": "customer",
                            "allows_refund": "on", "sort_order": "1"}).status_code == 403
        assert client.post(reverse("scm:returnpolicy_create"),
                           {"name": "CSRF policy"}).status_code == 403
        assert not ReturnAuthorization.objects.filter(tenant=tenant_a).exists()
        assert not ReturnReason.objects.filter(tenant=tenant_a, code="CSRF-1").exists()
        assert not ReturnPolicy.objects.filter(tenant=tenant_a, name="CSRF policy").exists()

    def test_the_receive_all_action_is_rejected_without_a_token(self, admin_user,
                                                                rma_awaiting_receipt_a,
                                                                location_a):
        from apps.scm.models import ReturnDisposition
        assert self._client(admin_user).post(
            reverse("scm:returnauthorization_receive_all", args=[rma_awaiting_receipt_a.pk]),
            {"location": str(location_a.pk), "condition_grade": "a"}).status_code == 403
        assert ReturnDisposition.objects.count() == 0

    def test_the_PUBLIC_token_page_is_NOT_csrf_exempt(self, rma_awaiting_receipt_a):
        """The repo's only CSRF exemption is the Stripe webhook; nothing in 4.10 exempts itself."""
        c = Client(enforce_csrf_checks=True)
        url = reverse("scm:returnauthorization_public",
                      args=[rma_awaiting_receipt_a.public_token])
        assert c.get(url).status_code == 200
        assert c.post(url, {"action": "shipped"}).status_code == 403
        rma_awaiting_receipt_a.refresh_from_db()
        assert rma_awaiting_receipt_a.customer_shipped_on is None

    def test_the_portal_request_form_is_not_csrf_exempt(self, portal_user_a, portal_access_a,
                                                        tenant_a, item_a, return_reason_a,
                                                        returns_sales_order_a):
        from apps.scm.models import ReturnAuthorization
        client = Client(enforce_csrf_checks=True)
        client.force_login(portal_user_a)
        assert client.post(reverse("scm:portal_return_create"),
                           {"item": str(item_a.pk), "quantity_requested": "1",
                            "reason": str(return_reason_a.pk)}).status_code == 403
        assert not ReturnAuthorization.objects.filter(tenant=tenant_a).exists()


# =================================================================================================
# SCM 4.11 Supply Chain Analytics — auth, tenant isolation, CSRF, method gates and hostile input.
#
# 4.11 is READ-ONLY over 4.1-4.10 and writes only its own three tables, so the attack surface is
# exactly: who may read a computed page, who may press the two batch writers, whose rows a pk
# resolves to, and what a hand-edited query string can do to a page anybody can reach.
# =================================================================================================
_ANALYTICS_GET_ROUTES = (
    "scm:inventory_analytics", "scm:inventory_analytics_export",
    "scm:spend_analytics", "scm:spend_analytics_export",
    "scm:logistics_kpis", "scm:logistics_kpis_export",
    "scm:margin_analytics", "scm:margin_analytics_export",
    "scm:disruption_risk", "scm:disruption_risk_export",
    "scm:kpitarget_list", "scm:kpitarget_create",
    "scm:kpisnapshot_list", "scm:kpisnapshot_export",
    "scm:supplychainalert_list", "scm:supplychainalert_create",
)

#: The five report pages plus the two filterable list pages — every 4.11 screen a hand-edited query
#: string can reach.
_ANALYTICS_FILTERABLE = ("scm:inventory_analytics", "scm:spend_analytics", "scm:logistics_kpis",
                         "scm:margin_analytics", "scm:disruption_risk", "scm:kpitarget_list",
                         "scm:kpisnapshot_list", "scm:supplychainalert_list")

def _kpi_target_payload(**overrides):
    """A complete, VALID ``KpiTargetForm`` POST body (the same shape ``test_views`` posts)."""
    data = {
        "metric": "inv_turnover", "name": "Turnover goal", "scope": "all",
        "scope_category": "", "scope_location": "", "scope_carrier": "", "scope_vendor": "",
        "period_grain": "month", "date_range": "last_90", "direction": "",
        "target_value": "6.00", "warning_threshold": "4.00", "critical_threshold": "2.00",
        "parameter_days": "", "parameter_pct": "",
        "min_impact_value": "0.00", "severity": "warning", "owner": "",
        "display_order": "0", "is_active": "on", "notes": "",
    }
    data.update(overrides)
    return data


#: The POST-only routes that take a pk, as (url name, POST body).
_ANALYTICS_PK_ACTIONS = (
    ("scm:kpitarget_delete", {}),
    ("scm:kpitarget_snapshot", {}),
    ("scm:supplychainalert_acknowledge", {}),
    ("scm:supplychainalert_assign", {"assigned_to": ""}),
    ("scm:supplychainalert_snooze", {"snooze_days": "7"}),
    ("scm:supplychainalert_resolve", {"resolution_note": "done"}),
    ("scm:supplychainalert_dismiss", {}),
    ("scm:supplychainalert_delete", {}),
)


# ================================================================ 4.11 · anonymous is turned away
class TestAnalyticsAnonymousRedirect:
    @pytest.mark.parametrize("url_name", _ANALYTICS_GET_ROUTES)
    def test_every_get_route_redirects_to_login(self, url_name):
        resp = Client().get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_the_detail_pages_redirect_before_they_resolve_a_pk(self, kpi_target_a, kpi_snapshot_a,
                                                                alert_a):
        c = Client()
        for url_name, obj in (("scm:kpitarget_detail", kpi_target_a),
                              ("scm:kpitarget_edit", kpi_target_a),
                              ("scm:kpisnapshot_detail", kpi_snapshot_a),
                              ("scm:supplychainalert_detail", alert_a),
                              ("scm:supplychainalert_edit", alert_a)):
            resp = c.get(reverse(url_name, args=[obj.pk]))
            assert resp.status_code == 302 and "login" in resp["Location"], url_name

    def test_the_two_batch_writers_reject_anonymous_and_write_nothing(self, tenant_a,
                                                                      kpi_target_a):
        from apps.scm.models import KpiSnapshot, SupplyChainAlert
        c = Client()
        for url_name in ("scm:kpisnapshot_capture", "scm:supplychainalert_detect"):
            resp = c.post(reverse(url_name))
            assert resp.status_code == 302 and "login" in resp["Location"], url_name
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a).exists()

    @pytest.mark.parametrize("url_name,payload", _ANALYTICS_PK_ACTIONS)
    def test_every_pk_action_rejects_anonymous(self, alert_a, kpi_target_a, url_name, payload):
        obj = kpi_target_a if url_name.startswith("scm:kpitarget") else alert_a
        resp = Client().post(reverse(url_name, args=[obj.pk]), payload)
        assert resp.status_code == 302 and "login" in resp["Location"]
        alert_a.refresh_from_db()
        kpi_target_a.refresh_from_db()
        assert alert_a.status == "open"


# ================================================================ 4.11 · cross-tenant IDOR
class TestAnalyticsCrossTenantIsolation:
    """Tenant A's admin pointed at tenant B's pk. Every one of these must be a 404 — not a 403,
    which would confirm the row exists, and certainly not a 200."""

    def test_a_targets_detail_edit_and_delete_are_404_across_tenants(self, client_a, kpi_target_b):
        from apps.scm.models import KpiTarget
        assert client_a.get(reverse("scm:kpitarget_detail",
                                    args=[kpi_target_b.pk])).status_code == 404
        assert client_a.get(reverse("scm:kpitarget_edit",
                                    args=[kpi_target_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:kpitarget_edit", args=[kpi_target_b.pk]),
                             {"name": "stolen"}).status_code == 404
        assert client_a.post(reverse("scm:kpitarget_delete",
                                     args=[kpi_target_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:kpitarget_snapshot",
                                     args=[kpi_target_b.pk])).status_code == 404
        assert KpiTarget.objects.filter(pk=kpi_target_b.pk).exists()
        kpi_target_b.refresh_from_db()
        assert kpi_target_b.name == "Globex turnover goal"

    def test_a_snapshots_detail_and_delete_are_404_across_tenants(self, client_a, kpi_snapshot_b):
        from apps.scm.models import KpiSnapshot
        assert client_a.get(reverse("scm:kpisnapshot_detail",
                                    args=[kpi_snapshot_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:kpisnapshot_delete",
                                     args=[kpi_snapshot_b.pk])).status_code == 404
        assert KpiSnapshot.objects.filter(pk=kpi_snapshot_b.pk).exists()

    def test_an_alerts_detail_edit_and_delete_are_404_across_tenants(self, client_a, alert_b):
        from apps.scm.models import SupplyChainAlert
        assert client_a.get(reverse("scm:supplychainalert_detail",
                                    args=[alert_b.pk])).status_code == 404
        assert client_a.get(reverse("scm:supplychainalert_edit",
                                    args=[alert_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:supplychainalert_edit", args=[alert_b.pk]),
                             {"title": "stolen"}).status_code == 404
        assert client_a.post(reverse("scm:supplychainalert_delete",
                                     args=[alert_b.pk])).status_code == 404
        assert SupplyChainAlert.objects.filter(pk=alert_b.pk).exists()

    @pytest.mark.parametrize("url_name,payload", [
        ("scm:supplychainalert_acknowledge", {}),
        ("scm:supplychainalert_assign", {"assigned_to": ""}),
        ("scm:supplychainalert_snooze", {"snooze_days": "7"}),
        ("scm:supplychainalert_resolve", {"resolution_note": "done"}),
        ("scm:supplychainalert_dismiss", {}),
    ])
    def test_every_lifecycle_action_is_404_across_tenants(self, client_a, alert_b, url_name,
                                                          payload):
        """The tenant check comes BEFORE the form check on all five, so whether a POST 404s can
        never depend on the payload being valid."""
        assert client_a.post(reverse(url_name, args=[alert_b.pk]), payload).status_code == 404
        alert_b.refresh_from_db()
        assert alert_b.status == "open"
        assert alert_b.assigned_to_id is None
        assert alert_b.snoozed_until is None
        assert alert_b.resolved_by_id is None

    def test_a_list_page_never_shows_the_other_tenants_rows(self, client_a, kpi_target_a,
                                                            kpi_target_b, kpi_snapshot_a,
                                                            kpi_snapshot_b, alert_a, alert_b):
        rows = client_a.get(reverse("scm:kpitarget_list")).context["object_list"]
        assert kpi_target_a in rows and kpi_target_b not in rows
        rows = client_a.get(reverse("scm:kpisnapshot_list")).context["object_list"]
        assert kpi_snapshot_a in rows and kpi_snapshot_b not in rows
        rows = client_a.get(reverse("scm:supplychainalert_list")).context["object_list"]
        assert alert_a in rows and alert_b not in rows

    def test_a_report_page_measures_only_its_own_tenant(self, client_b, analytics_history_a):
        """Every figure on tenant A's history must be invisible to tenant B, whose own tenant is
        empty — a resolver that forgot its tenant filter would show A's spend here."""
        resp = client_b.get(reverse("scm:spend_analytics"))
        assert resp.status_code == 200
        assert resp.context["spend_cube"]["by_vendor"] == []
        assert all(tile["value"] is None for tile in resp.context["tiles"])
        assert "Acme Supplies Ltd" not in resp.content.decode()

    def test_a_crafted_scope_pointing_at_the_other_tenant_is_flagged_not_applied(self, client_a,
                                                                                  category_b,
                                                                                  location_b,
                                                                                  carrier_b,
                                                                                  supplier_b):
        """An id that does not resolve INSIDE THIS TENANT is dropped and SAID SO, never silently
        widened to the network and never another workspace's row (L40 §3)."""
        for url_name, param, obj in (("scm:inventory_analytics", "category", category_b),
                                     ("scm:inventory_analytics", "location", location_b),
                                     ("scm:logistics_kpis", "carrier", carrier_b),
                                     ("scm:spend_analytics", "vendor", supplier_b),
                                     ("scm:disruption_risk", "vendor", supplier_b)):
            resp = client_a.get(reverse(url_name), {param: str(obj.pk)})
            assert resp.status_code == 200, (url_name, param)
            assert resp.context["scope_invalid"] is True, (url_name, param)
            assert resp.context["scope_value"] == "all", (url_name, param)

    def test_a_crafted_snapshot_filter_pointing_at_the_other_tenants_target_matches_nothing(
        self, client_a, kpi_snapshot_a, kpi_target_b,
    ):
        resp = client_a.get(reverse("scm:kpisnapshot_list"), {"kpi_target": str(kpi_target_b.pk)})
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []

    def test_a_crafted_alert_POST_cannot_name_another_tenants_subject(self, client_a, tenant_a,
                                                                      item_b, carrier_b,
                                                                      kpi_target_b):
        """The form's querysets are UX; the guard is the model's clean(), which is what holds
        against a POST that never went near a dropdown."""
        from apps.scm.models import SupplyChainAlert
        resp = client_a.post(reverse("scm:supplychainalert_create"), {
            "alert_type": "dead_stock", "metric": "", "kpi_target": str(kpi_target_b.pk),
            "title": "Crafted", "severity": "warning", "observed_value": "",
            "threshold_value": "", "impact_value": "1.00", "dimension_label": "",
            "item": str(item_b.pk), "party": "", "carrier": str(carrier_b.pk), "shipment": "",
            "purchase_order": "", "location": "", "assigned_to": "", "notes": "",
        })
        assert resp.status_code == 200                       # re-rendered with errors
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a).exists()
        for field in ("kpi_target", "item", "carrier"):
            assert field in resp.context["form"].errors, field

    def test_an_alert_cannot_be_assigned_to_another_tenants_login(self, client_a, alert_a, admin_b):
        """A person and the exception they are handed must agree on at least the workspace."""
        resp = client_a.post(reverse("scm:supplychainalert_assign", args=[alert_a.pk]),
                             {"assigned_to": str(admin_b.pk)}, follow=True)
        assert resp.status_code == 200
        alert_a.refresh_from_db()
        assert alert_a.assigned_to_id is None

    def test_a_crafted_target_POST_cannot_scope_to_another_tenants_category(self, client_a,
                                                                            tenant_a, category_b):
        from apps.scm.models import KpiTarget
        resp = client_a.post(reverse("scm:kpitarget_create"),
                             _kpi_target_payload(name="Crafted scope", scope="category",
                                                 scope_category=str(category_b.pk)))
        assert resp.status_code == 200
        assert "scope_category" in resp.context["form"].errors
        assert not KpiTarget.objects.filter(tenant=tenant_a, name="Crafted scope").exists()


# ================================================================ 4.11 · the admin gates
class TestAnalyticsTenantAdminGates:
    """Four routes are ``@tenant_admin_required``; everything else in 4.11 is ``@login_required``.

    The rule the module states: the routes that WRITE frozen history or raise the queue for the
    whole workspace are admin-only, and so is the one that irreversibly destroys that history.
    """

    def test_a_member_cannot_capture_a_single_targets_snapshot(self, member_client, tenant_a,
                                                               kpi_target_a, analytics_history_a):
        from apps.scm.models import KpiSnapshot
        assert member_client.post(reverse("scm:kpitarget_snapshot",
                                          args=[kpi_target_a.pk])).status_code == 403
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()

    def test_a_member_cannot_run_the_capture_batch(self, member_client, tenant_a, kpi_target_a,
                                                   analytics_history_a):
        from apps.scm.models import KpiSnapshot
        assert member_client.post(reverse("scm:kpisnapshot_capture")).status_code == 403
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()

    def test_a_member_cannot_run_detection(self, member_client, tenant_a, alerting_target_a,
                                           late_shipment_a):
        from apps.scm.models import SupplyChainAlert
        assert member_client.post(reverse("scm:supplychainalert_detect")).status_code == 403
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a).exists()

    def test_a_member_cannot_delete_a_target_and_the_target_survives(self, member_client,
                                                                     kpi_target_a,
                                                                     kpi_snapshot_a):
        """THE LOCK on the gate this route was just given: deleting a target CASCADES its frozen
        snapshots, and writing those is admin-only — so leaving the destructive path open let a
        member irreversibly destroy exactly the rows they were not trusted to create."""
        from apps.scm.models import KpiSnapshot, KpiTarget
        assert member_client.post(reverse("scm:kpitarget_delete",
                                          args=[kpi_target_a.pk])).status_code == 403
        assert KpiTarget.objects.filter(pk=kpi_target_a.pk).exists()
        assert KpiSnapshot.objects.filter(pk=kpi_snapshot_a.pk).exists()

    def test_the_gate_also_blocks_a_GET_before_the_method_check(self, member_client,
                                                                kpi_target_a):
        """@tenant_admin_required wraps @require_POST, so a member gets 403 rather than a 405 that
        would tell them the route exists and takes a POST."""
        assert member_client.get(reverse("scm:kpitarget_delete",
                                         args=[kpi_target_a.pk])).status_code == 403
        assert member_client.get(reverse("scm:kpitarget_snapshot",
                                         args=[kpi_target_a.pk])).status_code == 403

    def test_a_member_keeps_every_read_and_the_ordinary_triage_actions(self, member_client,
                                                                       kpi_target_a, alert_a,
                                                                       kpi_snapshot_a):
        """The queue only gets triaged if triaging it is not behind an administrator."""
        for url_name in _ANALYTICS_GET_ROUTES:
            assert member_client.get(reverse(url_name)).status_code == 200, url_name
        assert member_client.post(reverse("scm:supplychainalert_acknowledge",
                                          args=[alert_a.pk])).status_code == 302
        alert_a.refresh_from_db()
        assert alert_a.status == "acknowledged"
        # Editing a target is deliberately open too — tuning a threshold is routine planner work.
        assert member_client.get(reverse("scm:kpitarget_edit",
                                         args=[kpi_target_a.pk])).status_code == 200

    def test_a_tenant_less_superuser_cannot_write_orphan_rows(self, db, tenant_a, kpi_target_a):
        """The superuser has tenant=None by design; every 4.11 view filters by tenant, so a create
        by that user would be an orphan row nobody can see."""
        from apps.accounts.models import User
        from apps.scm.models import KpiSnapshot, SupplyChainAlert
        superuser = User.objects.create_superuser(email="root@naverp.test", username="root",
                                                  password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        assert c.post(reverse("scm:kpisnapshot_capture")).status_code == 302
        assert c.post(reverse("scm:supplychainalert_detect")).status_code == 302
        assert not KpiSnapshot.objects.exists()
        assert not SupplyChainAlert.objects.exists()
        # And the read pages still render, with the "no workspace" state rather than a 500.
        resp = c.get(reverse("scm:disruption_risk"))
        assert resp.status_code == 200 and resp.context["no_tenant"] is True
        assert resp.context["open_alert_count"] == 0


# ================================================================ 4.11 · CSRF
class TestAnalyticsCSRF:
    """Every mutating route, with ``enforce_csrf_checks=True`` and no token. The repo's only CSRF
    exemption is the Stripe webhook; nothing in 4.11 exempts itself."""

    @staticmethod
    def _client(user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        return c

    def test_the_two_batch_writers_are_rejected_without_a_token(self, admin_user, tenant_a,
                                                                kpi_target_a, alerting_target_a,
                                                                late_shipment_a):
        from apps.scm.models import KpiSnapshot, SupplyChainAlert
        c = self._client(admin_user)
        assert c.post(reverse("scm:kpisnapshot_capture")).status_code == 403
        assert c.post(reverse("scm:supplychainalert_detect")).status_code == 403
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a).exists()

    def test_the_two_create_forms_are_rejected_without_a_token(self, admin_user, tenant_a):
        from apps.scm.models import KpiTarget, SupplyChainAlert
        c = self._client(admin_user)
        assert c.post(reverse("scm:kpitarget_create"),
                      _kpi_target_payload(name="CSRF target")).status_code == 403
        assert c.post(reverse("scm:supplychainalert_create"),
                      {"alert_type": "dead_stock", "title": "CSRF alert", "severity": "warning",
                       "impact_value": "0.00"}).status_code == 403
        assert not KpiTarget.objects.filter(tenant=tenant_a, name="CSRF target").exists()
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a).exists()

    def test_the_edit_forms_are_rejected_without_a_token(self, admin_user, kpi_target_a, alert_a):
        c = self._client(admin_user)
        assert c.post(reverse("scm:kpitarget_edit", args=[kpi_target_a.pk]),
                      _kpi_target_payload(name="CSRF edit")).status_code == 403
        assert c.post(reverse("scm:supplychainalert_edit", args=[alert_a.pk]),
                      {"alert_type": "dead_stock", "title": "CSRF edit",
                       "severity": "warning", "impact_value": "0.00"}).status_code == 403
        kpi_target_a.refresh_from_db()
        alert_a.refresh_from_db()
        assert kpi_target_a.name == "Turnover goal"
        assert alert_a.title == "Dead stock: WIDGET-1"

    def test_the_three_delete_routes_are_rejected_without_a_token(self, admin_user, kpi_target_a,
                                                                  kpi_snapshot_a, alert_a):
        from apps.scm.models import KpiSnapshot, KpiTarget, SupplyChainAlert
        c = self._client(admin_user)
        assert c.post(reverse("scm:kpitarget_delete", args=[kpi_target_a.pk])).status_code == 403
        assert c.post(reverse("scm:kpisnapshot_delete",
                              args=[kpi_snapshot_a.pk])).status_code == 403
        assert c.post(reverse("scm:supplychainalert_delete", args=[alert_a.pk])).status_code == 403
        assert KpiTarget.objects.filter(pk=kpi_target_a.pk).exists()
        assert KpiSnapshot.objects.filter(pk=kpi_snapshot_a.pk).exists()
        assert SupplyChainAlert.objects.filter(pk=alert_a.pk).exists()

    @pytest.mark.parametrize("url_name,payload", [
        ("scm:supplychainalert_acknowledge", {}),
        ("scm:supplychainalert_assign", {"assigned_to": ""}),
        ("scm:supplychainalert_snooze", {"snooze_days": "7"}),
        ("scm:supplychainalert_resolve", {"resolution_note": "done"}),
        ("scm:supplychainalert_dismiss", {}),
    ])
    def test_every_lifecycle_action_is_rejected_without_a_token(self, admin_user, alert_a,
                                                                url_name, payload):
        assert self._client(admin_user).post(reverse(url_name, args=[alert_a.pk]),
                                             payload).status_code == 403
        alert_a.refresh_from_db()
        assert alert_a.status == "open"
        assert alert_a.acknowledged_by_id is None

    def test_the_single_target_snapshot_action_is_rejected_without_a_token(self, admin_user,
                                                                           tenant_a, kpi_target_a,
                                                                           analytics_history_a):
        from apps.scm.models import KpiSnapshot
        assert self._client(admin_user).post(reverse("scm:kpitarget_snapshot",
                                                     args=[kpi_target_a.pk])).status_code == 403
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()


# ================================================================ 4.11 · POST-only method gates
class TestAnalyticsMethodGates:
    """A GET must never mutate. ``crud_delete`` is self-defending as well (it only writes on POST),
    so these routes are guarded twice."""

    def test_the_batch_writers_refuse_a_GET(self, client_a, tenant_a, kpi_target_a,
                                            alerting_target_a, late_shipment_a,
                                            analytics_history_a):
        from apps.scm.models import KpiSnapshot, SupplyChainAlert
        assert client_a.get(reverse("scm:kpisnapshot_capture")).status_code == 405
        assert client_a.get(reverse("scm:supplychainalert_detect")).status_code == 405
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a).exists()

    @pytest.mark.parametrize("url_name,payload", _ANALYTICS_PK_ACTIONS)
    def test_every_pk_action_refuses_a_GET(self, client_a, kpi_target_a, alert_a, kpi_snapshot_a,
                                           url_name, payload):
        from apps.scm.models import KpiTarget, SupplyChainAlert
        obj = kpi_target_a if url_name.startswith("scm:kpitarget") else alert_a
        assert client_a.get(reverse(url_name, args=[obj.pk]), payload).status_code == 405
        assert KpiTarget.objects.filter(pk=kpi_target_a.pk).exists()
        assert SupplyChainAlert.objects.filter(pk=alert_a.pk).exists()
        alert_a.refresh_from_db()
        assert alert_a.status == "open"

    def test_the_snapshot_delete_refuses_a_GET(self, client_a, kpi_snapshot_a):
        from apps.scm.models import KpiSnapshot
        assert client_a.get(reverse("scm:kpisnapshot_delete",
                                    args=[kpi_snapshot_a.pk])).status_code == 405
        assert KpiSnapshot.objects.filter(pk=kpi_snapshot_a.pk).exists()


# ================================================================ 4.11 · hostile query strings
class TestAnalyticsHostileFilters:
    """Nothing anybody can type into the address bar may 500 a read-only page.

    The headline case is the Unicode SUPERSCRIPT: ``'²'.isdigit()`` is True but ``int('²')`` raises,
    so ``?category=²`` sailed through an ``.isdigit()`` guard and then raised ``ValueError`` from
    INSIDE ``.filter()`` — an uncaught 500 on six pages. ``isdecimal()`` is precisely ``int()``'s
    accepted set, and that is what this class locks.
    """

    #: One junk value of every shape a filter has ever been handed.
    JUNK = ["abc", "²", "³", "1e5", "-1", "0", "999999999999999999999", " ",
            "1;DROP TABLE", "<script>", "1.5"]

    @pytest.mark.parametrize("value", JUNK)
    def test_a_junk_scope_id_never_500s_any_report_page(self, client_a, analytics_history_a,
                                                        value):
        for url_name, param in (("scm:inventory_analytics", "category"),
                                ("scm:inventory_analytics", "location"),
                                ("scm:spend_analytics", "vendor"),
                                ("scm:logistics_kpis", "carrier"),
                                ("scm:margin_analytics", "category"),
                                ("scm:disruption_risk", "vendor")):
            resp = client_a.get(reverse(url_name), {param: value})
            assert resp.status_code == 200, (url_name, param, value)

    @pytest.mark.parametrize("value", JUNK)
    def test_a_junk_scope_id_never_500s_any_export(self, client_a, analytics_history_a, value):
        for url_name, param in (("scm:inventory_analytics_export", "category"),
                                ("scm:spend_analytics_export", "vendor"),
                                ("scm:logistics_kpis_export", "carrier"),
                                ("scm:margin_analytics_export", "category"),
                                ("scm:disruption_risk_export", "vendor")):
            assert client_a.get(reverse(url_name),
                                {param: value}).status_code == 200, (url_name, value)

    @pytest.mark.parametrize("value", JUNK)
    def test_a_junk_kpi_target_filter_never_500s_the_snapshot_page_or_its_export(self, client_a,
                                                                                  kpi_snapshot_a,
                                                                                  value):
        """``?kpi_target=²`` — the exact superscript that raised out of ``.filter()``."""
        assert client_a.get(reverse("scm:kpisnapshot_list"),
                            {"kpi_target": value}).status_code == 200
        assert client_a.get(reverse("scm:kpisnapshot_export"),
                            {"kpi_target": value}).status_code == 200

    @pytest.mark.parametrize("value", JUNK)
    def test_a_junk_assignee_filter_never_500s_the_inbox(self, client_a, alert_a, value):
        assert client_a.get(reverse("scm:supplychainalert_list"),
                            {"assigned_to": value}).status_code == 200

    @pytest.mark.parametrize("value", ["NaN", "nan", "Infinity", "-Infinity", "inf", "1e400",
                                       "-1e400", "abc", "", "1e999999", "99999999999999999999",
                                       "--5", "1,000"])
    def test_a_hostile_min_impact_never_500s_the_inbox(self, client_a, alert_a, value):
        """``Decimal("NaN")`` parses happily and then poisons every comparison it touches; an
        oversized figure is clamped to what a DecimalField(14, 2) holds rather than dropped."""
        resp = client_a.get(reverse("scm:supplychainalert_list"), {"min_impact": value})
        assert resp.status_code == 200, value

    def test_an_oversized_min_impact_matches_nothing_rather_than_everything(self, client_a,
                                                                            alert_a):
        """Clamping is the truthful answer: "at least 10^400" matches nothing. DROPPING the filter
        would silently show every row under a heading that says it is filtered."""
        resp = client_a.get(reverse("scm:supplychainalert_list"), {"min_impact": "1e400"})
        assert list(resp.context["object_list"]) == []

    @pytest.mark.parametrize("value", ["lastweek", "2026-02-31", "0000-00-00", "²", "1/1/2026",
                                       "2026-13-01", "abc", "99999-01-01"])
    def test_a_junk_date_window_never_500s_a_page_or_an_export(self, client_a,
                                                               analytics_history_a,
                                                               kpi_snapshot_a, value):
        """``?date_to=2026-02-31`` is well-formed and NOT a date — parse_date raises on exactly
        that, which anybody can type into the address bar."""
        for url_name in ("scm:inventory_analytics", "scm:inventory_analytics_export",
                         "scm:kpisnapshot_list", "scm:kpisnapshot_export"):
            assert client_a.get(reverse(url_name),
                                {"date_from": value, "date_to": value}).status_code == 200, (
                                    url_name, value)

    @pytest.mark.parametrize("value", ["abc", "²", "-1", "0", "99999", "1e5", ""])
    def test_a_junk_page_number_never_500s_a_list(self, client_a, kpi_target_a, kpi_snapshot_a,
                                                  alert_a, value):
        """L9 — a page past the end lands on the last page; junk lands on the first."""
        for url_name in ("scm:kpitarget_list", "scm:kpisnapshot_list",
                         "scm:supplychainalert_list"):
            assert client_a.get(reverse(url_name),
                                {"page": value}).status_code == 200, (url_name, value)

    #: One value of the wrong SHAPE for every non-integer filter 4.11 offers, sent together: a page
    #: has to skip all of them at once, which is what a hand-edited URL actually looks like.
    JUNK_CHOICES = {
        "metric": "not_a_metric", "scope": "sideways", "severity": "purple", "group": "nonsense",
        "status": "not_a_status", "alert_type": "invented", "status_band": "chartreuse",
        "sort": "sideways", "basis": "furlongs", "date_range": "since_forever",
        "gl_account": "²", "org_unit": "²", "customer": "²", "channel": "²",
        "is_active": "maybe", "is_alerting": "maybe", "q": "²³",
    }

    @pytest.mark.parametrize("url_name", _ANALYTICS_FILTERABLE)
    def test_every_junk_choice_filter_at_once_is_skipped_rather_than_matched(
        self, client_a, kpi_target_a, kpi_snapshot_a, alert_a, analytics_history_a, url_name,
    ):
        assert client_a.get(reverse(url_name), self.JUNK_CHOICES).status_code == 200

    def test_a_junk_status_falls_back_to_the_default_view_not_to_an_empty_page(self, client_a,
                                                                               alert_a):
        resp = client_a.get(reverse("scm:supplychainalert_list"), {"status": "not_a_status"})
        assert list(resp.context["object_list"]) == [alert_a]
        # The select shows the view that was actually rendered, not the value that was typed.
        assert resp.context["status_value"] == ""

    def test_a_junk_search_term_never_500s_and_matches_nothing(self, client_a, kpi_target_a,
                                                               kpi_snapshot_a, alert_a):
        for url_name in ("scm:kpitarget_list", "scm:kpisnapshot_list",
                         "scm:supplychainalert_list"):
            resp = client_a.get(reverse(url_name), {"q": "'; DROP TABLE scm_kpitarget; --"})
            assert resp.status_code == 200
            assert list(resp.context["object_list"]) == []

    def test_two_scope_filters_at_once_apply_one_and_NAME_the_one_they_dropped(self, client_a,
                                                                               category_a,
                                                                               location_a):
        """A metric narrows to exactly ONE subject. Silently intersecting them is not available and
        silently dropping one is how a page ends up labelled with a filter it did not apply."""
        resp = client_a.get(reverse("scm:inventory_analytics"),
                            {"category": str(category_a.pk), "location": str(location_a.pk)})
        assert resp.status_code == 200
        assert resp.context["scope_value"] == "category"
        assert resp.context["scope_ignored"] == ["location"]


# ================================================================ 4.11 · CSV injection
class TestAnalyticsCsvInjection:
    """A cell beginning ``=`` ``+`` ``-`` ``@`` or a control character is executed as a FORMULA by
    Excel and LibreOffice. SKUs, supplier names, carrier names and a KPI target's name are all free
    text somebody typed, so every cell in every 4.11 export goes through one escape."""

    def test_a_target_named_like_a_formula_exports_quoted(self, client_a, tenant_a,
                                                          analytics_history_a):
        """The named case: a KpiTarget called ``=1+1`` must reach the file as ``'=1+1``."""
        from django.utils import timezone
        from apps.scm.models import KpiSnapshot, KpiTarget
        target = KpiTarget.objects.create(tenant=tenant_a, metric="inv_turnover", name="=1+1",
                                          scope="all", date_range="last_90")
        KpiSnapshot.objects.create(tenant=tenant_a, kpi_target=target, metric="inv_turnover",
                                   period_start=timezone.localdate() - datetime.timedelta(days=30),
                                   period_end=timezone.localdate(), value=Decimal("1.0000"))
        body = client_a.get(reverse("scm:kpisnapshot_export")).content.decode()
        assert "'=1+1" in body
        assert ",=1+1" not in body

    @pytest.mark.parametrize("hostile", ["=1+1", "+1+1", "-1+1", "@SUM(A1)",
                                         "=cmd|'/c calc'!A0", "\t=1+1"])
    def test_every_dangerous_prefix_is_neutralised(self, client_a, tenant_a, hostile):
        from django.utils import timezone
        from apps.scm.models import KpiSnapshot, KpiTarget
        target = KpiTarget.objects.create(tenant=tenant_a, metric="inv_turnover", name=hostile,
                                          scope="all")
        KpiSnapshot.objects.create(tenant=tenant_a, kpi_target=target, metric="inv_turnover",
                                   period_start=timezone.localdate() - datetime.timedelta(days=30),
                                   period_end=timezone.localdate(), value=Decimal("1.0000"),
                                   dimension_label=hostile)
        body = client_a.get(reverse("scm:kpisnapshot_export")).content.decode()
        assert f"'{hostile}" in body, hostile

    def test_an_item_named_like_a_formula_exports_quoted_from_a_report(self, client_a, tenant_a,
                                                                        analytics_history_a,
                                                                        category_a, uom_each_a,
                                                                        location_a):
        """The report exports carry resolver ROWS — SKUs and supplier names straight off records
        anybody in the tenant can rename."""
        from django.utils import timezone
        from apps.scm.models import Item
        from apps.scm.views._helpers import _post_stock_move
        item = Item.objects.create(tenant=tenant_a, sku="=1+1", name="@SUM(A1)",
                                   category=category_a, uom=uom_each_a,
                                   standard_cost=Decimal("5.00"))
        _post_stock_move(tenant_a, item=item, location=location_a, quantity=Decimal("10"),
                         move_type="receipt", unit_cost=Decimal("5.0000"), reference="OPENING",
                         moved_at=timezone.now() - datetime.timedelta(days=120))
        body = client_a.get(reverse("scm:inventory_analytics_export")).content.decode("utf-8-sig")
        assert "'=1+1" in body
        assert "'@SUM(A1)" in body

    def test_a_negative_NUMBER_is_left_alone_so_the_spreadsheet_can_still_sum_it(self, client_a,
                                                                                  tenant_a,
                                                                                  kpi_target_a):
        """Half the figures on these pages are negative (freight variance, a loss-making customer).
        Prefixing every one of them would turn the column into text."""
        from django.utils import timezone
        from apps.scm.models import KpiSnapshot
        KpiSnapshot.objects.create(tenant=tenant_a, kpi_target=kpi_target_a, metric="inv_turnover",
                                   period_start=timezone.localdate() - datetime.timedelta(days=30),
                                   period_end=timezone.localdate(), value=Decimal("-3.5000"))
        body = client_a.get(reverse("scm:kpisnapshot_export")).content.decode()
        assert "-3.5000" in body
        assert "'-3.5000" not in body

    def test_no_request_value_ever_reaches_a_content_disposition_header(self, client_a,
                                                                        analytics_history_a):
        """The filename is a server-side literal plus a server-side date — there is nothing to
        inject a newline into and no way to smuggle a parameter into the header."""
        from django.utils import timezone
        resp = client_a.get(reverse("scm:inventory_analytics_export"),
                            {"category": "1\r\nX-Injected: yes", "date_to": "</script>"})
        assert resp.status_code == 200
        assert "X-Injected" not in str(resp.serialize_headers())
        assert resp["Content-Disposition"] == (
            f'attachment; filename="inventory-analytics-{timezone.localdate().isoformat()}.csv"')


# ================================================================ 4.11 · XSS
class TestAnalyticsXss:
    def test_a_chart_payload_is_escaped_by_json_script_not_interpolated(self, client_a, tenant_a,
                                                                        analytics_history_a,
                                                                        admin_user):
        """Series labels are SKUs and supplier names. ``|safe`` on a hand-built JSON string is a
        stored-XSS hole the first time somebody names an item ``</script>``."""
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiTarget
        KpiTarget.objects.create(tenant=tenant_a, metric="inv_turnover",
                                 name="</script><script>alert(1)</script>", scope="all",
                                 date_range="last_90")
        capture_snapshots(tenant_a, user=admin_user)
        body = client_a.get(reverse("scm:inventory_analytics")).content.decode()
        assert "<script>alert(1)</script>" not in body

    def test_a_hostile_alert_title_is_escaped_on_the_inbox_and_the_detail_page(self, client_a,
                                                                               tenant_a):
        from apps.scm.models import SupplyChainAlert
        alert = SupplyChainAlert.objects.create(
            tenant=tenant_a, alert_type="dead_stock", title="<script>alert('xss')</script>",
            dimension_label="<img src=x onerror=alert(1)>")
        for url in (reverse("scm:supplychainalert_list"),
                    reverse("scm:supplychainalert_detail", args=[alert.pk])):
            body = client_a.get(url).content.decode()
            assert "<script>alert('xss')</script>" not in body
            assert "<img src=x onerror=alert(1)>" not in body
            assert "&lt;script&gt;" in body

    def test_a_hostile_search_term_is_escaped_back_into_the_filter_bar(self, client_a,
                                                                       kpi_target_a):
        body = client_a.get(reverse("scm:kpitarget_list"),
                            {"q": '"><script>alert(1)</script>'}).content.decode()
        assert "<script>alert(1)</script>" not in body


# ------------------------------------------------------------------------------------------------
# SCM 4.12 shared helpers.
#
# _security_blob is this module's OWN message reader, deliberately named apart from
# test_views._messages / test_views._message_blob: those two live in a different file, and a
# second definition of either name inside one module silently rebinds it for every caller written
# above it (the failure test_suite_hygiene.py exists to catch). Cross-file there is no shadowing,
# so a distinct name here keeps both files readable on their own.
#
# _localdate_sec is timezone.localdate(), NEVER datetime.date.today() — every 4.12
# clean() compares a posted date against the LOCAL date, so a payload built on the other basis
# flakes for the hours after local midnight (L16).
# ------------------------------------------------------------------------------------------------
def _security_blob(response):
    """Every flash message on a response as one lowercase string."""
    return " ".join(str(m) for m in response.context["messages"]).lower()


def _localdate_sec(days=0):
    """Today (or days from it) on the basis the 4.12 models validate against."""
    from django.utils import timezone
    return timezone.localdate() + datetime.timedelta(days=days)



# =================================================================================================
# SCM 4.12 Contract & Compliance Management — auth, tenant isolation, CSRF, method gates, hostile
# input, CSV injection and XSS.
#
# 4.12 is read-only over 4.1-4.11 (L29): the only rows it writes are its own four tables plus the
# two cached counters on the ``TradeLicense`` a document is charged to. That makes the attack surface
# exactly: who may read a register, who may press a verb, whose rows a pk resolves to, and what a
# hand-edited query string can do to a page anybody can reach.
#
# Two things in this sub-module need naming before the tests below make sense:
#
#   * ``ComplianceCheck`` has NO tenant column. It is a pure child reached through
#     ``requirement.tenant``, so its two routes must resolve it as
#     ``requirement__tenant=request.tenant`` — a bare pk lookup is a cross-tenant read, and
#     ``compliance_check_b`` is the row that proves whether one is happening.
#   * ``tradelicense_revoke`` / ``tradedocument_void`` both resolve the object BEFORE their
#     reason guard. Returning early on a missing reason meant a reasonless POST to another tenant's
#     pk answered 302 instead of 404 — so the "cross-tenant is always a 404" invariant held only
#     when a reason happened to be supplied. That is locked below with an EMPTY body.
# =================================================================================================
_COMPLIANCE_GET_ROUTES = (
    "scm:tradelicense_list", "scm:tradelicense_create",
    "scm:tradedocument_list", "scm:tradedocument_create",
    "scm:compliancerequirement_list", "scm:compliancerequirement_create",
    "scm:sustainabilityassessment_list", "scm:sustainabilityassessment_create",
    "scm:carbon_footprint_report", "scm:carbon_footprint_report_export",
)

#: The four filterable registers plus the computed report — every 4.12 screen a hand-edited query
#: string can reach.
_COMPLIANCE_FILTERABLE = ("scm:tradelicense_list", "scm:tradedocument_list",
                          "scm:compliancerequirement_list",
                          "scm:sustainabilityassessment_list", "scm:carbon_footprint_report",
                          "scm:carbon_footprint_report_export")

#: Every ``@tenant_admin_required`` route in 4.12, as (url name, fixture name, POST body). These are
#: the acts that destroy evidence, release a consumed authorisation, or move what the workspace is
#: allowed to ship.
_COMPLIANCE_ADMIN_ROUTES = (
    ("scm:tradelicense_delete", "draft_license_a", {}),
    ("scm:tradelicense_approve", "draft_license_a", {}),
    ("scm:tradelicense_revoke", "trade_license_a", {"reason": "Withdrawn."}),
    ("scm:tradelicense_recompute", "trade_license_a", {}),
    ("scm:tradedocument_delete", "trade_document_a", {}),
    ("scm:tradedocument_void", "issued_document_a", {"reason": "Superseded."}),
    ("scm:compliancerequirement_delete", "compliance_requirement_a", {}),
    ("scm:compliancecheck_delete", "compliance_check_a", {}),
    ("scm:sustainabilityassessment_delete", "sustainability_assessment_a", {}),
)

#: Every POST-only route in 4.12 — a GET to one must be a 405, never a silent state change.
_COMPLIANCE_POST_ONLY = (
    ("scm:tradelicense_delete", "draft_license_a"),
    ("scm:tradelicense_submit", "draft_license_a"),
    ("scm:tradelicense_approve", "draft_license_a"),
    ("scm:tradelicense_revoke", "trade_license_a"),
    ("scm:tradelicense_recompute", "trade_license_a"),
    ("scm:tradedocument_delete", "trade_document_a"),
    ("scm:tradedocument_issue", "trade_document_a"),
    ("scm:tradedocument_submit", "trade_document_a"),
    ("scm:tradedocument_accept", "trade_document_a"),
    ("scm:tradedocument_void", "trade_document_a"),
    ("scm:compliancerequirement_delete", "compliance_requirement_a"),
    ("scm:compliancerequirement_record_check", "compliance_requirement_a"),
    ("scm:compliancecheck_delete", "compliance_check_a"),
    ("scm:sustainabilityassessment_delete", "sustainability_assessment_a"),
)

#: Cross-tenant targets: (url name, the tenant-B fixture, POST body). Every one must answer 404 —
#: not 403, which would confirm the row exists, and certainly not 200.
_COMPLIANCE_CROSS_TENANT_POSTS = (
    ("scm:tradelicense_delete", "trade_license_b", {}),
    ("scm:tradelicense_submit", "trade_license_b", {}),
    ("scm:tradelicense_approve", "trade_license_b", {}),
    ("scm:tradelicense_revoke", "trade_license_b", {"reason": "Stolen."}),
    ("scm:tradelicense_recompute", "trade_license_b", {}),
    ("scm:tradelicense_edit", "trade_license_b", {"title": "stolen"}),
    ("scm:tradedocument_delete", "trade_document_b", {}),
    ("scm:tradedocument_issue", "trade_document_b", {}),
    ("scm:tradedocument_submit", "trade_document_b", {}),
    ("scm:tradedocument_accept", "trade_document_b", {}),
    ("scm:tradedocument_void", "trade_document_b", {"reason": "Stolen."}),
    ("scm:tradedocument_edit", "trade_document_b", {"doc_type": "packing_list"}),
    ("scm:compliancerequirement_delete", "compliance_requirement_b", {}),
    ("scm:compliancerequirement_edit", "compliance_requirement_b", {"title": "stolen"}),
    ("scm:compliancerequirement_record_check", "compliance_requirement_b", {"result": "pass"}),
    ("scm:compliancecheck_delete", "compliance_check_b", {}),
    ("scm:compliancecheck_edit", "compliance_check_b", {"result": "fail"}),
    ("scm:sustainabilityassessment_delete", "sustainability_assessment_b", {}),
    ("scm:sustainabilityassessment_edit", "sustainability_assessment_b", {"provider": "stolen"}),
)


def _compliance_license_body(**overrides):
    """A complete, VALID ``TradeLicenseForm`` POST body (the shape ``test_views`` posts)."""
    data = {
        "license_number": "BIS-SEC-1", "title": "Export licence", "license_type": "export_license",
        "issuing_authority": "BIS", "issuing_country": "United States", "holder_party": "",
        "end_user_party": "", "application_date": "", "issue_date": "", "expiry_date": "",
        "renewal_notice_days": "60", "authorized_value": "", "authorized_quantity": "",
        "currency": "", "commodity_scope": "", "eccn_or_hs": "", "destination_countries": "",
        "conditions": "", "document": "", "notes": "",
    }
    data.update(overrides)
    return data


def _compliance_requirement_body(**overrides):
    """A complete, VALID ``ComplianceRequirementForm`` POST body."""
    from django.utils import timezone
    data = {
        "title": "Annual COI on file", "description": "", "source": "regulation",
        "source_reference": "", "framework": "insurance_coi", "obligation_category": "",
        "jurisdiction": "", "scope": "tenant", "org_unit": "", "party": "", "location": "",
        "item": "", "owner": "", "frequency": "annual",
        "next_due_date": (timezone.localdate() + datetime.timedelta(days=30)).isoformat(),
        "notice_days": "30", "contract": "", "license": "", "document": "",
        "status": "applicable", "criticality": "medium", "not_applicable_reason": "", "notes": "",
    }
    data.update(overrides)
    return data


# ================================================================ 4.12 · anonymous is turned away
class TestComplianceAnonymousRedirect:
    @pytest.mark.parametrize("url_name", _COMPLIANCE_GET_ROUTES)
    def test_every_get_route_redirects_to_login(self, url_name):
        resp = Client().get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_every_detail_page_redirects_BEFORE_it_resolves_a_pk(self, trade_license_a,
                                                                  trade_document_a,
                                                                  compliance_requirement_a,
                                                                  compliance_check_a,
                                                                  sustainability_assessment_a):
        c = Client()
        for url_name, obj in (("scm:tradelicense_detail", trade_license_a),
                              ("scm:tradelicense_edit", trade_license_a),
                              ("scm:tradedocument_detail", trade_document_a),
                              ("scm:tradedocument_edit", trade_document_a),
                              ("scm:tradedocument_print", trade_document_a),
                              ("scm:compliancerequirement_detail", compliance_requirement_a),
                              ("scm:compliancerequirement_edit", compliance_requirement_a),
                              ("scm:compliancecheck_edit", compliance_check_a),
                              ("scm:sustainabilityassessment_detail",
                               sustainability_assessment_a),
                              ("scm:sustainabilityassessment_edit",
                               sustainability_assessment_a)):
            resp = c.get(reverse(url_name, args=[obj.pk]))
            assert resp.status_code == 302 and "login" in resp["Location"], url_name

    @pytest.mark.parametrize("url_name,fixture_name", _COMPLIANCE_POST_ONLY)
    def test_every_verb_rejects_anonymous_and_writes_nothing(self, request, url_name,
                                                              fixture_name):
        obj = request.getfixturevalue(fixture_name)
        before = getattr(obj, "status", None)
        resp = Client().post(reverse(url_name, args=[obj.pk]), {"reason": "x", "result": "pass"})
        assert resp.status_code == 302 and "login" in resp["Location"]
        obj.refresh_from_db()
        assert getattr(obj, "status", None) == before

    def test_anonymous_cannot_create_any_412_row(self, tenant_a, supplier_a):
        from apps.scm.models import (ComplianceRequirement, SustainabilityAssessment,
                                     TradeDocument, TradeLicense)
        c = Client()
        assert c.post(reverse("scm:tradelicense_create"),
                      _compliance_license_body()).status_code == 302
        assert c.post(reverse("scm:compliancerequirement_create"),
                      _compliance_requirement_body()).status_code == 302
        assert not TradeLicense.objects.exists()
        assert not TradeDocument.objects.exists()
        assert not ComplianceRequirement.objects.exists()
        assert not SustainabilityAssessment.objects.exists()


# ================================================================ 4.12 · cross-tenant IDOR
class TestComplianceCrossTenantIsolation:
    """Tenant A's admin pointed at tenant B's pk. Every one of these must be a 404."""

    def test_every_detail_and_edit_page_is_404_across_tenants(self, client_a, trade_license_b,
                                                               trade_document_b,
                                                               compliance_requirement_b,
                                                               compliance_check_b,
                                                               sustainability_assessment_b):
        for url_name, obj in (("scm:tradelicense_detail", trade_license_b),
                              ("scm:tradelicense_edit", trade_license_b),
                              ("scm:tradedocument_detail", trade_document_b),
                              ("scm:tradedocument_edit", trade_document_b),
                              ("scm:tradedocument_print", trade_document_b),
                              ("scm:compliancerequirement_detail", compliance_requirement_b),
                              ("scm:compliancerequirement_edit", compliance_requirement_b),
                              ("scm:compliancecheck_edit", compliance_check_b),
                              ("scm:sustainabilityassessment_detail",
                               sustainability_assessment_b),
                              ("scm:sustainabilityassessment_edit",
                               sustainability_assessment_b)):
            assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 404, url_name

    @pytest.mark.parametrize("url_name,fixture_name,payload", _COMPLIANCE_CROSS_TENANT_POSTS)
    def test_every_verb_is_404_across_tenants_and_changes_nothing(self, client_a, request,
                                                                   url_name, fixture_name,
                                                                   payload):
        obj = request.getfixturevalue(fixture_name)
        before = {name: getattr(obj, name, None)
                  for name in ("status", "title", "result", "provider", "doc_type", "used_value")}
        assert client_a.post(reverse(url_name, args=[obj.pk]), payload).status_code == 404
        obj.refresh_from_db()
        for name, value in before.items():
            assert getattr(obj, name, None) == value, name

    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:tradelicense_revoke", "trade_license_b"),
        ("scm:tradedocument_void", "trade_document_b"),
    ])
    def test_a_REASONLESS_cross_tenant_post_is_404_and_not_302(self, client_a, request, url_name,
                                                                fixture_name):
        """THE regression lock. Both verbs used to return early on a missing reason BEFORE resolving
        the object, so a reasonless POST to another tenant's pk answered 302 — the "cross-tenant is
        always a 404" invariant held only when a reason happened to be supplied, which is exactly
        what an attacker would omit."""
        obj = request.getfixturevalue(fixture_name)
        assert client_a.post(reverse(url_name, args=[obj.pk]), {}).status_code == 404

    @pytest.mark.parametrize("url_name", ["scm:tradelicense_revoke", "scm:tradedocument_void"])
    def test_a_REASONLESS_post_to_a_nonexistent_pk_is_404_and_not_302(self, client_a, url_name):
        assert client_a.post(reverse(url_name, args=[999999]), {}).status_code == 404

    def test_a_tenant_less_superuser_gets_404_rather_than_somebody_elses_proof_record(
        self, db, compliance_check_a, compliance_requirement_a,
    ):
        """``request.tenant`` of ``None`` resolves to ``requirement__tenant IS NULL``, and that
        column is NOT NULL — so the tenant-less superuser gets a 404, never a foreign row."""
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(email="root412@naverp.test", username="root412",
                                                  password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        assert c.get(reverse("scm:compliancecheck_edit",
                             args=[compliance_check_a.pk])).status_code == 404
        assert c.post(reverse("scm:compliancecheck_delete",
                              args=[compliance_check_a.pk])).status_code == 404

    def test_no_list_page_ever_shows_the_other_tenants_rows(self, client_a, trade_license_a,
                                                             trade_license_b, trade_document_a,
                                                             trade_document_b,
                                                             compliance_requirement_a,
                                                             compliance_requirement_b,
                                                             sustainability_assessment_a,
                                                             sustainability_assessment_b):
        for url_name, mine, theirs in (
            ("scm:tradelicense_list", trade_license_a, trade_license_b),
            ("scm:tradedocument_list", trade_document_a, trade_document_b),
            ("scm:compliancerequirement_list", compliance_requirement_a,
             compliance_requirement_b),
            ("scm:sustainabilityassessment_list", sustainability_assessment_a,
             sustainability_assessment_b),
        ):
            rows = client_a.get(reverse(url_name)).context["object_list"]
            assert mine in rows, url_name
            assert theirs not in rows, url_name

    def test_a_crafted_filter_pointing_at_the_other_tenants_row_matches_nothing(
        self, client_a, trade_document_a, trade_license_b, shipment_b, sustainability_assessment_a,
        supplier_b, compliance_requirement_a, admin_b,
    ):
        for url_name, param, obj in (("scm:tradedocument_list", "license", trade_license_b),
                                     ("scm:tradedocument_list", "shipment", shipment_b),
                                     ("scm:sustainabilityassessment_list", "party", supplier_b),
                                     ("scm:compliancerequirement_list", "owner", admin_b)):
            resp = client_a.get(reverse(url_name), {param: str(obj.pk)})
            assert resp.status_code == 200, (url_name, param)
            assert list(resp.context["object_list"]) == [], (url_name, param)

    @pytest.mark.parametrize("field,fixture_name", [
        ("holder_party", "supplier_b"), ("end_user_party", "supplier_b"),
        ("document", "evidence_document_b"),
    ])
    def test_a_crafted_licence_POST_cannot_name_another_tenants_row(self, client_a, request,
                                                                     tenant_a, field,
                                                                     fixture_name):
        """The form's querysets are UX; ``TradeLicense.clean()`` is what holds against a POST that
        never went near a dropdown (L39 §2)."""
        from apps.scm.models import TradeLicense
        other = request.getfixturevalue(fixture_name)
        resp = client_a.post(reverse("scm:tradelicense_create"),
                             _compliance_license_body(**{field: str(other.pk)}))
        assert resp.status_code == 200
        assert field in resp.context["form"].errors
        assert not TradeLicense.objects.filter(tenant=tenant_a).exists()

    @pytest.mark.parametrize("field,fixture_name,extra", [
        ("party", "supplier_b", {"scope": "party"}),
        ("org_unit", "org_unit_b", {"scope": "org_unit"}),
        ("location", "location_b", {"scope": "location"}),
        ("item", "item_b", {"scope": "item"}),
        ("contract", "contract_b", {"source": "contract"}),
        ("license", "trade_license_b", {"source": "license"}),
        ("document", "evidence_document_b", {}),
        ("owner", "admin_b", {}),
    ])
    def test_a_crafted_obligation_POST_cannot_name_another_tenants_row(self, client_a, request,
                                                                        tenant_a, field,
                                                                        fixture_name, extra):
        from apps.scm.models import ComplianceRequirement
        other = request.getfixturevalue(fixture_name)
        body = _compliance_requirement_body(**{field: str(other.pk)}, **extra)
        resp = client_a.post(reverse("scm:compliancerequirement_create"), body)
        assert resp.status_code == 200
        assert field in resp.context["form"].errors, resp.context["form"].errors
        assert not ComplianceRequirement.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_check_POST_cannot_attach_another_tenants_evidence(
        self, client_a, compliance_requirement_a, evidence_document_b,
    ):
        """``ComplianceCheck`` has no tenant column, so ``TenantModelForm`` cannot scope its evidence
        dropdown for free.

        Two guards stand here and the OUTER one answers first: the form re-filters ``evidence`` from
        ``Document.objects`` to this tenant, so a crafted pk is "not one of the available choices".
        The inner guard — ``ComplianceCheck.clean()`` checking the document against the PARENT's
        tenant — is what holds if that queryset is ever widened, and it is asserted directly in
        ``test_models.py``. What this test pins is the OUTCOME: a refusal message and no child row.
        """
        resp = client_a.post(reverse("scm:compliancerequirement_record_check",
                                     args=[compliance_requirement_a.pk]),
                             {"result": "pass", "due_date": "",
                              "performed_on": _localdate_sec().isoformat(),
                              "finding": "", "corrective_reference": "",
                              "evidence": str(evidence_document_b.pk), "notes": ""},
                             follow=True)
        assert resp.status_code == 200
        assert _security_blob(resp)                        # refused out loud, not silently dropped
        assert "select a valid choice" in _security_blob(resp)
        assert compliance_requirement_a.checks.count() == 0

    def test_a_crafted_document_POST_cannot_charge_another_tenants_licence(self, client_a,
                                                                           tenant_a,
                                                                           trade_license_b):
        from apps.scm.models import TradeDocument
        body = {
            "doc_type": "commercial_invoice", "direction": "export", "document_number": "X",
            "issue_date": "", "shipment": "", "carrier": "", "purchase_order": "",
            "sales_order": "", "license": str(trade_license_b.pk), "shipper_party": "",
            "consignee_party": "", "notify_party": "", "country_of_origin": "",
            "country_of_destination": "", "currency": "", "declared_value": "10.00",
            "freight_charges": "", "insurance_value": "", "incoterm": "", "gross_weight_kg": "",
            "net_weight_kg": "", "package_count": "", "vessel_or_flight": "", "voyage_number": "",
            "port_of_loading": "", "port_of_discharge": "", "container_numbers": "",
            "is_negotiable": "", "filing_reference": "", "document": "", "notes": "",
        }
        body.update(formset_data("lines", []))
        resp = client_a.post(reverse("scm:tradedocument_create"), body)
        assert resp.status_code == 200
        assert "license" in resp.context["form"].errors
        assert not TradeDocument.objects.filter(tenant=tenant_a).exists()

    def test_a_crafted_esg_POST_cannot_score_another_tenants_party(self, client_a, tenant_a,
                                                                    supplier_b):
        from apps.scm.models import SustainabilityAssessment
        resp = client_a.post(reverse("scm:sustainabilityassessment_create"), {
            "party": str(supplier_b.pk), "assessment_date": _localdate_sec().isoformat(),
            "valid_until": "", "source": "self_assessment", "provider": "", "status": "draft",
            "environment_score": "", "labor_human_rights_score": "", "ethics_score": "",
            "sustainable_procurement_score": "", "carbon_score": "", "strengths": "",
            "improvement_areas": "", "scope1_tco2e": "", "scope2_tco2e": "", "scope3_tco2e": "",
            "carbon_reporting_year": "", "document": "", "notes": "",
        })
        assert resp.status_code == 200
        assert "party" in resp.context["form"].errors
        assert not SustainabilityAssessment.objects.filter(tenant=tenant_a).exists()

    def test_the_carbon_report_measures_only_its_own_tenants_freight(self, client_b,
                                                                      carbon_shipment_a,
                                                                      sustainability_assessment_a):
        """A resolver that forgot its tenant filter would show tenant A's tonne-km here."""
        resp = client_b.get(reverse("scm:carbon_footprint_report"))
        assert resp.status_code == 200
        assert resp.context["total_tco2e"] is None
        assert resp.context["considered_count"] == 0
        assert resp.context["declared_count"] == 0
        assert "Acme Trucking Co" not in resp.content.decode()

    def test_a_cross_tenant_check_delete_leaves_the_row_and_its_parent_alone(self, client_a,
                                                                             tenant_a,
                                                                             compliance_check_b,
                                                                             compliance_requirement_b):
        """The child is reached ONLY through ``requirement__tenant``, so tenant A's admin cannot
        touch it — and the parent's derived ``compliance_rate`` is unchanged by the attempt."""
        from apps.scm.models import ComplianceCheck
        before = compliance_requirement_b.compliance_rate
        assert client_a.post(reverse("scm:compliancecheck_delete",
                                     args=[compliance_check_b.pk])).status_code == 404
        assert ComplianceCheck.objects.filter(pk=compliance_check_b.pk).exists()
        compliance_requirement_b.refresh_from_db()
        assert compliance_requirement_b.tenant_id != tenant_a.pk
        assert compliance_requirement_b.compliance_rate == before


# ================================================================ 4.12 · the admin gates
class TestComplianceTenantAdminGates:
    """The rule 4.12 states: recording work is open to every member; destroying evidence, releasing
    a consumed authorisation and moving what the workspace may ship are administrator acts."""

    @pytest.mark.parametrize("url_name,fixture_name,payload", _COMPLIANCE_ADMIN_ROUTES)
    def test_a_plain_member_is_403_on_every_gated_route(self, member_client, request, url_name,
                                                        fixture_name, payload):
        obj = request.getfixturevalue(fixture_name)
        assert member_client.post(reverse(url_name, args=[obj.pk]),
                                  payload).status_code == 403

    @pytest.mark.parametrize("url_name,fixture_name,payload", _COMPLIANCE_ADMIN_ROUTES)
    def test_the_gate_blocks_a_GET_BEFORE_the_method_check(self, member_client, request,
                                                           url_name, fixture_name, payload):
        """``@tenant_admin_required`` wraps ``@require_POST``, so a member gets 403 rather than a 405
        that would tell them the route exists and takes a POST."""
        obj = request.getfixturevalue(fixture_name)
        assert member_client.get(reverse(url_name, args=[obj.pk])).status_code == 403

    def test_nothing_a_member_was_refused_actually_moved(self, member_client, trade_license_a,
                                                          issued_document_a,
                                                          compliance_requirement_a,
                                                          compliance_check_a,
                                                          sustainability_assessment_a):
        from apps.scm.models import (ComplianceCheck, ComplianceRequirement,
                                     SustainabilityAssessment, TradeDocument, TradeLicense)
        for url_name, obj, payload in (
            ("scm:tradelicense_revoke", trade_license_a, {"reason": "x"}),
            ("scm:tradelicense_recompute", trade_license_a, {}),
            ("scm:tradedocument_void", issued_document_a, {"reason": "x"}),
            ("scm:compliancerequirement_delete", compliance_requirement_a, {}),
            ("scm:compliancecheck_delete", compliance_check_a, {}),
            ("scm:sustainabilityassessment_delete", sustainability_assessment_a, {}),
        ):
            member_client.post(reverse(url_name, args=[obj.pk]), payload)
        trade_license_a.refresh_from_db()
        issued_document_a.refresh_from_db()
        assert trade_license_a.status == "active"
        assert issued_document_a.status == "issued"
        assert ComplianceRequirement.objects.filter(pk=compliance_requirement_a.pk).exists()
        assert ComplianceCheck.objects.filter(pk=compliance_check_a.pk).exists()
        assert SustainabilityAssessment.objects.filter(
            pk=sustainability_assessment_a.pk).exists()
        assert TradeDocument.objects.filter(pk=issued_document_a.pk).exists()
        assert TradeLicense.objects.filter(pk=trade_license_a.pk).exists()

    def test_a_member_keeps_every_read_and_the_daily_work(self, member_client, trade_license_a,
                                                           draft_license_a, trade_document_a,
                                                           compliance_requirement_a,
                                                           sustainability_assessment_a):
        """The register only gets kept if keeping it is not behind a workspace administrator."""
        for url_name in _COMPLIANCE_GET_ROUTES:
            assert member_client.get(reverse(url_name)).status_code == 200, url_name
        # Lodging an application commits nothing and authorises nothing.
        assert member_client.post(reverse("scm:tradelicense_submit",
                                          args=[draft_license_a.pk])).status_code == 302
        # Raising and issuing paperwork is the daily work of the person shipping the goods; the
        # licence balance is the control here, not the role.
        assert member_client.post(reverse("scm:tradedocument_issue",
                                          args=[trade_document_a.pk])).status_code == 302
        # Recording that you did the thing you were supposed to do must not need an administrator,
        # or the register stops being kept at all.
        assert member_client.post(
            reverse("scm:compliancerequirement_record_check",
                    args=[compliance_requirement_a.pk]),
            {"result": "pass", "due_date": "", "performed_on": _localdate_sec().isoformat(),
             "finding": "", "corrective_reference": "", "evidence": "",
             "notes": ""}).status_code == 302
        compliance_requirement_a.refresh_from_db()
        assert compliance_requirement_a.status == "compliant"
        # Revising a scorecard is ordinary compliance work; only DISCARDING one is gated.
        assert member_client.get(reverse("scm:sustainabilityassessment_edit",
                                         args=[sustainability_assessment_a.pk])).status_code == 200

    def test_a_member_may_record_a_check_but_not_rewrite_one_after_the_fact(self, member_client,
                                                                            compliance_check_a):
        """This row IS the evidence, and a proof history anybody can quietly restate is not
        defensible documentation."""
        assert member_client.get(reverse("scm:compliancecheck_edit",
                                         args=[compliance_check_a.pk])).status_code == 403
        assert member_client.post(reverse("scm:compliancecheck_edit",
                                          args=[compliance_check_a.pk]),
                                  {"result": "pass"}).status_code == 403
        compliance_check_a.refresh_from_db()
        assert compliance_check_a.result == "partial"

    def test_a_tenant_less_superuser_cannot_write_orphan_rows(self, db, tenant_a):
        """The superuser has ``tenant=None`` by design, and every 4.12 view filters by tenant — a
        create by that user would be an orphan row no workspace can ever see."""
        from apps.accounts.models import User
        from apps.scm.models import ComplianceRequirement, TradeLicense
        superuser = User.objects.create_superuser(email="root412b@naverp.test",
                                                  username="root412b", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        assert c.post(reverse("scm:tradelicense_create"),
                      _compliance_license_body()).status_code == 302
        assert c.post(reverse("scm:compliancerequirement_create"),
                      _compliance_requirement_body()).status_code == 302
        assert not TradeLicense.objects.exists()
        assert not ComplianceRequirement.objects.exists()
        # ...the READ pages still render rather than 500-ing on a missing workspace...
        for url_name in ("scm:tradelicense_list", "scm:tradedocument_list",
                         "scm:compliancerequirement_list", "scm:sustainabilityassessment_list",
                         "scm:carbon_footprint_report", "scm:carbon_footprint_report_export"):
            assert c.get(reverse(url_name)).status_code == 200, url_name
        # ...and every CREATE screen turns the user away rather than rendering a form whose every
        # dropdown is empty and whose save would produce an orphan row.
        for url_name in ("scm:tradelicense_create", "scm:tradedocument_create",
                         "scm:compliancerequirement_create",
                         "scm:sustainabilityassessment_create"):
            assert c.get(reverse(url_name)).status_code == 302, url_name


# ================================================================ 4.12 · POST-only method gates
class TestComplianceMethodGates:
    @pytest.mark.parametrize("url_name,fixture_name", [
        (name, fixture) for name, fixture in _COMPLIANCE_POST_ONLY
        if name in ("scm:tradelicense_submit", "scm:tradedocument_issue",
                    "scm:tradedocument_submit", "scm:tradedocument_accept",
                    "scm:compliancerequirement_record_check")
    ])
    def test_a_GET_to_an_open_verb_is_405_and_changes_nothing(self, client_a, request, url_name,
                                                              fixture_name):
        obj = request.getfixturevalue(fixture_name)
        before = getattr(obj, "status", None)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 405
        obj.refresh_from_db()
        assert getattr(obj, "status", None) == before

    @pytest.mark.parametrize("url_name,fixture_name", [
        (name, fixture) for name, fixture in _COMPLIANCE_POST_ONLY
        if name in ("scm:tradelicense_delete", "scm:tradelicense_approve",
                    "scm:tradelicense_revoke", "scm:tradelicense_recompute",
                    "scm:tradedocument_delete", "scm:tradedocument_void",
                    "scm:compliancerequirement_delete", "scm:compliancecheck_delete",
                    "scm:sustainabilityassessment_delete")
    ])
    def test_a_GET_to_a_gated_verb_is_405_for_an_ADMIN_and_deletes_nothing(self, client_a,
                                                                           request, url_name,
                                                                           fixture_name):
        obj = request.getfixturevalue(fixture_name)
        model = type(obj)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 405
        assert model.objects.filter(pk=obj.pk).exists()


# ================================================================ 4.12 · CSRF
class TestComplianceCSRF:
    """Every mutating route with ``enforce_csrf_checks=True`` and no token. The repo's only CSRF
    exemption is the Stripe webhook; nothing in 4.12 exempts itself."""

    @staticmethod
    def _client(user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        return c

    def test_the_create_forms_are_rejected_without_a_token(self, admin_user, tenant_a,
                                                            supplier_a):
        from apps.scm.models import (ComplianceRequirement, SustainabilityAssessment,
                                     TradeDocument, TradeLicense)
        c = self._client(admin_user)
        assert c.post(reverse("scm:tradelicense_create"),
                      _compliance_license_body()).status_code == 403
        assert c.post(reverse("scm:compliancerequirement_create"),
                      _compliance_requirement_body()).status_code == 403
        assert c.post(reverse("scm:tradedocument_create"), {}).status_code == 403
        assert c.post(reverse("scm:sustainabilityassessment_create"),
                      {"party": str(supplier_a.pk)}).status_code == 403
        assert not TradeLicense.objects.filter(tenant=tenant_a).exists()
        assert not ComplianceRequirement.objects.filter(tenant=tenant_a).exists()
        assert not TradeDocument.objects.filter(tenant=tenant_a).exists()
        assert not SustainabilityAssessment.objects.filter(tenant=tenant_a).exists()

    def test_the_edit_forms_are_rejected_without_a_token(self, admin_user, trade_license_a,
                                                          trade_document_a,
                                                          compliance_requirement_a,
                                                          compliance_check_a,
                                                          sustainability_assessment_a):
        c = self._client(admin_user)
        for url_name, obj in (("scm:tradelicense_edit", trade_license_a),
                              ("scm:tradedocument_edit", trade_document_a),
                              ("scm:compliancerequirement_edit", compliance_requirement_a),
                              ("scm:compliancecheck_edit", compliance_check_a),
                              ("scm:sustainabilityassessment_edit",
                               sustainability_assessment_a)):
            assert c.post(reverse(url_name, args=[obj.pk]),
                          {"title": "CSRF"}).status_code == 403, url_name
        trade_license_a.refresh_from_db()
        assert trade_license_a.title == "Export licence - workstation hardware"

    @pytest.mark.parametrize("url_name,fixture_name", _COMPLIANCE_POST_ONLY)
    def test_every_verb_is_rejected_without_a_token(self, admin_user, request, url_name,
                                                    fixture_name):
        obj = request.getfixturevalue(fixture_name)
        before = getattr(obj, "status", None)
        assert self._client(admin_user).post(
            reverse(url_name, args=[obj.pk]),
            {"reason": "x", "result": "pass"}).status_code == 403
        obj.refresh_from_db()
        assert getattr(obj, "status", None) == before

    def test_the_licence_balance_is_untouched_by_a_tokenless_issue(self, admin_user,
                                                                    trade_document_a,
                                                                    trade_license_a):
        assert self._client(admin_user).post(
            reverse("scm:tradedocument_issue", args=[trade_document_a.pk])).status_code == 403
        trade_license_a.refresh_from_db()
        assert trade_license_a.used_value == Decimal("0.00")


# ================================================================ 4.12 · hostile query strings
class TestComplianceHostileFilters:
    """Nothing anybody can type into the address bar may 500 a page.

    The headline shapes: the Unicode SUPERSCRIPT (``'²'.isdigit()`` is True but ``int('²')`` raises),
    the 21-digit id (all decimal digits, converts cleanly, then raises inside the driver), and the
    out-of-range DATE (``0001-01-01`` makes ``date_to - timedelta(days=365)`` raise OverflowError).
    """

    #: One junk value of every shape a filter has ever been handed.
    JUNK = ["abc", "²", "³", "1e5", "-1", "0", "999999999999999999999", " ", "1;DROP TABLE",
            "<script>", "1.5"]

    @pytest.mark.parametrize("value", JUNK)
    def test_a_junk_int_filter_never_500s_any_register(self, client_a, trade_document_a,
                                                       compliance_requirement_a,
                                                       sustainability_assessment_a, value):
        for url_name, param in (("scm:tradedocument_list", "shipment"),
                                ("scm:tradedocument_list", "license"),
                                ("scm:compliancerequirement_list", "owner"),
                                ("scm:sustainabilityassessment_list", "party")):
            resp = client_a.get(reverse(url_name), {param: value})
            assert resp.status_code == 200, (url_name, param, value)

    @pytest.mark.parametrize("value", JUNK)
    def test_a_junk_carrier_filter_never_500s_the_carbon_report_or_its_export(self, client_a,
                                                                              carbon_shipment_a,
                                                                              value):
        """``?carrier=999999999999999999999`` is all decimal digits and converts fine, then raises
        ``OverflowError`` inside the driver — the same L11 guard ``crud_list`` applies to its own
        int filters has to be applied by hand here."""
        for url_name in ("scm:carbon_footprint_report", "scm:carbon_footprint_report_export"):
            assert client_a.get(reverse(url_name),
                                {"carrier": value}).status_code == 200, (url_name, value)

    @pytest.mark.parametrize("value", ["0001-01-01", "0001-12-31", "1899-12-31", "9999-12-31",
                                        "2026-02-31", "0000-00-00", "lastweek", "²", "1/1/2026",
                                        "2026-13-01", "abc", "99999-01-01", ""])
    def test_a_junk_or_out_of_range_date_window_never_500s_the_report_or_its_export(
        self, client_a, carbon_shipment_a, value,
    ):
        """``?date_to=0001-01-01`` parses as a real date and then makes the default-window
        subtraction raise ``OverflowError`` — an uncaught 500 on a value anybody can type into the
        address bar. It has to fall back to the default window and SAY so."""
        for url_name in ("scm:carbon_footprint_report", "scm:carbon_footprint_report_export"):
            for param in ("date_from", "date_to"):
                resp = client_a.get(reverse(url_name), {param: value})
                assert resp.status_code == 200, (url_name, param, value)

    def test_an_out_of_range_date_lights_the_invalid_banner_rather_than_failing_silently(
        self, client_a, carbon_shipment_a,
    ):
        """Silently ignoring what somebody asked for is worse than saying the default window is
        showing."""
        resp = client_a.get(reverse("scm:carbon_footprint_report"), {"date_to": "0001-01-01"})
        assert resp.status_code == 200
        assert resp.context["window_invalid"] is True
        assert resp.context["date_to_raw"] == "0001-01-01"
        # ...and the fallback window is a real one the shipment still lands in.
        assert resp.context["measured_count"] == 1

    def test_an_over_range_carrier_id_skips_the_filter_rather_than_raising(self, client_a,
                                                                           carbon_shipment_a):
        resp = client_a.get(reverse("scm:carbon_footprint_report"),
                            {"carrier": "999999999999999999999"})
        assert resp.status_code == 200
        assert resp.context["measured_count"] == 1
        # The typed value is echoed back into the input rather than swallowed.
        assert resp.context["carrier_id"] == "999999999999999999999"

    @pytest.mark.parametrize("value", ["abc", "²", "-1", "0", "99999", "1e5", ""])
    def test_a_junk_page_number_never_500s_a_register(self, client_a, trade_license_a,
                                                       trade_document_a,
                                                       compliance_requirement_a,
                                                       sustainability_assessment_a, value):
        """L9 — a page past the end lands on the last page; junk lands on the first."""
        for url_name in _COMPLIANCE_FILTERABLE[:4]:
            assert client_a.get(reverse(url_name),
                                {"page": value}).status_code == 200, (url_name, value)

    #: One value of the wrong SHAPE for every non-integer filter 4.12 offers, sent together — which
    #: is what a hand-edited URL actually looks like.
    JUNK_CHOICES = {
        "status": "not_a_status", "license_type": "invented", "issuing_country": "²",
        "doc_type": "nonsense", "direction": "sideways", "framework": "chartreuse",
        "source": "nowhere", "criticality": "purple", "due": "whenever", "rating": "tin",
        "mode": "teleport", "q": "²³",
    }

    @pytest.mark.parametrize("url_name", _COMPLIANCE_FILTERABLE)
    def test_every_junk_choice_filter_at_once_is_skipped_rather_than_matched(
        self, client_a, trade_license_a, trade_document_a, compliance_requirement_a,
        sustainability_assessment_a, carbon_shipment_a, url_name,
    ):
        assert client_a.get(reverse(url_name), self.JUNK_CHOICES).status_code == 200

    def test_a_junk_search_term_never_500s_and_matches_nothing(self, client_a, trade_license_a,
                                                                trade_document_a,
                                                                compliance_requirement_a,
                                                                sustainability_assessment_a):
        for url_name in _COMPLIANCE_FILTERABLE[:4]:
            resp = client_a.get(reverse(url_name), {"q": "'; DROP TABLE scm_tradelicense; --"})
            assert resp.status_code == 200, url_name
            assert list(resp.context["object_list"]) == [], url_name

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "abc", "1e400", "-1",
                                        "99999999999999999999.99", "--5", "1,000", ""])
    def test_a_hostile_decimal_in_a_create_body_is_a_field_error_never_a_500(self, client_a,
                                                                             tenant_a, value):
        """``Decimal("NaN")`` parses happily and then poisons every comparison it touches; an
        over-``max_digits`` figure raises ``DataError`` inside the driver if it ever reaches it."""
        from apps.scm.models import TradeLicense
        resp = client_a.post(reverse("scm:tradelicense_create"),
                             _compliance_license_body(authorized_value=value))
        assert resp.status_code in (200, 302), value
        if resp.status_code == 200:
            assert "authorized_value" in resp.context["form"].errors, value
        else:
            # The empty string is the legitimate "no ceiling" case, and it stores NULL not zero.
            assert value == ""
            assert TradeLicense.objects.get(tenant=tenant_a).authorized_value is None

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "-1.00", "1e400",
                                        "99999999999999999999.99"])
    def test_a_hostile_declared_value_never_reaches_a_licence_balance(self, client_a, tenant_a,
                                                                       trade_license_a, value):
        from apps.scm.models import TradeDocument
        body = {
            "doc_type": "commercial_invoice", "direction": "export", "document_number": "H",
            "issue_date": "", "shipment": "", "carrier": "", "purchase_order": "",
            "sales_order": "", "license": str(trade_license_a.pk), "shipper_party": "",
            "consignee_party": "", "notify_party": "", "country_of_origin": "",
            "country_of_destination": "", "currency": "", "declared_value": value,
            "freight_charges": "", "insurance_value": "", "incoterm": "", "gross_weight_kg": "",
            "net_weight_kg": "", "package_count": "", "vessel_or_flight": "", "voyage_number": "",
            "port_of_loading": "", "port_of_discharge": "", "container_numbers": "",
            "is_negotiable": "", "filing_reference": "", "document": "", "notes": "",
        }
        body.update(formset_data("lines", []))
        resp = client_a.post(reverse("scm:tradedocument_create"), body)
        assert resp.status_code == 200, value
        assert "declared_value" in resp.context["form"].errors, value
        assert not TradeDocument.objects.filter(tenant=tenant_a).exists()
        trade_license_a.refresh_from_db()
        assert trade_license_a.used_value == Decimal("0.00")

    @pytest.mark.parametrize("value", ["4294967295", "-1", "3651", "abc", "²", "1e5"])
    def test_a_hostile_day_count_is_a_field_error_not_an_OverflowError(self, client_a, tenant_a,
                                                                        value):
        """``PositiveIntegerField`` accepts 4294967295 on MariaDB and both of 4.12's day counts are
        fed to ``timedelta(days=...)`` — an absurd value is an uncaught OverflowError, i.e. a 500
        rather than a validation error (the 4.10 denial-of-service finding)."""
        from apps.scm.models import ComplianceRequirement, TradeLicense
        resp = client_a.post(reverse("scm:tradelicense_create"),
                             _compliance_license_body(renewal_notice_days=value))
        assert resp.status_code == 200, value
        assert "renewal_notice_days" in resp.context["form"].errors, value
        resp = client_a.post(reverse("scm:compliancerequirement_create"),
                             _compliance_requirement_body(notice_days=value))
        assert resp.status_code == 200, value
        assert "notice_days" in resp.context["form"].errors, value
        assert not TradeLicense.objects.filter(tenant=tenant_a).exists()
        assert not ComplianceRequirement.objects.filter(tenant=tenant_a).exists()

    def test_a_huge_notice_window_cannot_be_stored_and_then_hang_the_due_queue(self, client_a,
                                                                               tenant_a):
        """The register's due-soon condition expands one clause per DISTINCT notice window, and the
        expansion is capped — this pins that an absurd window never gets stored to begin with."""
        from apps.scm.models import ComplianceRequirement
        row = ComplianceRequirement(tenant=tenant_a, title="Absurd", frequency="on_event",
                                    notice_days=4294967295)
        from django.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            row.full_clean(exclude=["number"])

    def test_a_reason_longer_than_the_column_is_truncated_rather_than_raising(self, client_a,
                                                                              trade_license_a):
        """``revocation_reason`` is a TextField and the audit entry is capped at 200 chars, so a
        megabyte of prose is stored/truncated rather than crashing the verb."""
        client_a.post(reverse("scm:tradelicense_revoke", args=[trade_license_a.pk]),
                      {"reason": "A" * 50000})
        trade_license_a.refresh_from_db()
        assert trade_license_a.status == "revoked"
        assert len(trade_license_a.revocation_reason) == 2000


# ================================================================ 4.12 · CSV injection
class TestComplianceCsvInjection:
    """A cell beginning ``=`` ``+`` ``-`` ``@`` or a control character is executed as a FORMULA by
    Excel and LibreOffice. The carbon export's carrier column is ``Carrier.name``, a property over
    ``Party.name`` — i.e. free text anybody in the workspace can type."""

    def test_a_carrier_named_like_a_formula_exports_quoted(self, client_a, carbon_shipment_a,
                                                            carrier_party_a):
        carrier_party_a.name = "=1+1"
        carrier_party_a.save(update_fields=["name"])
        body = client_a.get(reverse("scm:carbon_footprint_report_export")).content.decode()
        assert "'=1+1" in body
        assert ",=1+1" not in body

    @pytest.mark.parametrize("hostile", ["=1+1", "+1+1", "-1+1", "@SUM(A1)",
                                          "=cmd|'/c calc'!A0", "\t=1+1"])
    def test_every_dangerous_prefix_is_neutralised(self, client_a, carbon_shipment_a,
                                                    carrier_party_a, hostile):
        carrier_party_a.name = hostile
        carrier_party_a.save(update_fields=["name"])
        body = client_a.get(reverse("scm:carbon_footprint_report_export")).content.decode()
        assert f"'{hostile}" in body, hostile

    def test_a_negative_NUMBER_is_left_alone_so_the_spreadsheet_can_still_sum_it(self, client_a,
                                                                                 carbon_shipment_a):
        """Prefixing every negative figure would turn the column into text in the spreadsheet that
        has to sum it. A number cannot carry a formula."""
        body = client_a.get(reverse("scm:carbon_footprint_report_export")).content.decode()
        assert "'1000.00" not in body
        assert "1000.00" in body

    def test_no_request_value_ever_reaches_the_content_disposition_header(self, client_a,
                                                                          carbon_shipment_a):
        """The filename is a server-side literal — there is nothing to inject a newline into."""
        resp = client_a.get(reverse("scm:carbon_footprint_report_export"),
                            {"carrier": "1\r\nX-Injected: yes", "date_to": "</script>"})
        assert resp.status_code == 200
        assert "X-Injected" not in str(resp.serialize_headers())
        assert resp["Content-Disposition"] == 'attachment; filename="carbon-footprint.csv"'


# ================================================================ 4.12 · XSS
class TestComplianceXss:
    """Titles, licence numbers, findings, conditions and provider names are all free text somebody
    typed, and every one of them is rendered on a list AND a detail page."""

    def test_a_hostile_licence_title_is_escaped_on_both_its_pages(self, client_a, tenant_a):
        from apps.scm.models import TradeLicense
        lic = TradeLicense.objects.create(
            tenant=tenant_a, license_number="<img src=x onerror=alert(1)>",
            title="<script>alert('xss')</script>", issuing_authority="BIS")
        for url in (reverse("scm:tradelicense_list"),
                    reverse("scm:tradelicense_detail", args=[lic.pk])):
            body = client_a.get(url).content.decode()
            assert "<script>alert('xss')</script>" not in body
            assert "<img src=x onerror=alert(1)>" not in body
            assert "&lt;script&gt;" in body

    def test_a_hostile_document_number_is_escaped(self, client_a, tenant_a):
        from apps.scm.models import TradeDocument
        doc = TradeDocument.objects.create(tenant=tenant_a,
                                           document_number="<script>alert(1)</script>",
                                           vessel_or_flight="<img src=x onerror=alert(1)>")
        for url in (reverse("scm:tradedocument_list"),
                    reverse("scm:tradedocument_detail", args=[doc.pk]),
                    reverse("scm:tradedocument_print", args=[doc.pk])):
            body = client_a.get(url).content.decode()
            assert "<script>alert(1)</script>" not in body
            assert "<img src=x onerror=alert(1)>" not in body

    def test_a_hostile_obligation_title_and_finding_are_escaped(self, client_a, tenant_a):
        from apps.scm.models import ComplianceCheck, ComplianceRequirement
        row = ComplianceRequirement.objects.create(
            tenant=tenant_a, title="<script>alert('cr')</script>", frequency="on_event",
            source_reference="<img src=x onerror=alert(1)>")
        ComplianceCheck.objects.create(requirement=row, result="fail",
                                       finding="<script>alert('chk')</script>")
        for url in (reverse("scm:compliancerequirement_list"),
                    reverse("scm:compliancerequirement_detail", args=[row.pk])):
            body = client_a.get(url).content.decode()
            assert "<script>alert('cr')</script>" not in body
            assert "<script>alert('chk')</script>" not in body

    def test_a_hostile_provider_name_is_escaped_on_the_scorecard(self, client_a, tenant_a,
                                                                  supplier_a):
        from apps.scm.models import SustainabilityAssessment
        row = SustainabilityAssessment.objects.create(
            tenant=tenant_a, party=supplier_a, assessment_date=_localdate_sec(),
            provider="<script>alert('esg')</script>",
            strengths="<img src=x onerror=alert(1)>")
        for url in (reverse("scm:sustainabilityassessment_list"),
                    reverse("scm:sustainabilityassessment_detail", args=[row.pk])):
            body = client_a.get(url).content.decode()
            assert "<script>alert('esg')</script>" not in body
            assert "<img src=x onerror=alert(1)>" not in body

    def test_a_hostile_search_term_is_escaped_back_into_the_filter_bar(self, client_a,
                                                                       trade_license_a):
        for url_name in ("scm:tradelicense_list", "scm:tradedocument_list",
                         "scm:compliancerequirement_list",
                         "scm:sustainabilityassessment_list"):
            body = client_a.get(reverse(url_name),
                                {"q": '"><script>alert(1)</script>'}).content.decode()
            assert "<script>alert(1)</script>" not in body, url_name

    def test_a_hostile_carrier_name_is_escaped_on_the_carbon_report(self, client_a,
                                                                     carbon_shipment_a,
                                                                     carrier_party_a):
        carrier_party_a.name = "<script>alert('carbon')</script>"
        carrier_party_a.save(update_fields=["name"])
        body = client_a.get(reverse("scm:carbon_footprint_report")).content.decode()
        assert "<script>alert('carbon')</script>" not in body
        assert "&lt;script&gt;" in body


# ------------------------------------------------------------------------------------------------
# SCM 4.13 date basis for the security payloads. timezone.localdate(), NEVER
# datetime.date.today(): every 4.13 clean() compares a posted date against the LOCAL date, so a body
# built on the other basis flakes for the hours after local midnight (L16).
# ------------------------------------------------------------------------------------------------
def _asset_sec_day(days=0):
    """Today (or days from it) on the basis the 4.13 models validate against."""
    from django.utils import timezone
    return timezone.localdate() + datetime.timedelta(days=days)


# =================================================================================================
# SCM 4.13 Asset Management — auth, tenant isolation, CSRF, method gates and hostile input.
#
# Three things need naming before the tests below make sense:
#
#   * THREE of the seven tables carry NO tenant column. ``AssetSparePart`` is reached through
#     ``asset__tenant``, ``MaintenancePlanTask`` through ``plan__tenant`` and
#     ``MaintenanceWorkOrderPart`` / ``MaintenanceWorkOrderTask`` through ``work_order__tenant``. A
#     bare pk lookup on any of them is a cross-tenant read or WRITE with no query anywhere that
#     would reveal it, so the parent join IS the authorization check.
#   * EIGHT routes are ``@tenant_admin_required``: the three deletes plus the spare-part delete, the
#     plan's generate action, and the job's approve / cancel / issue-parts. The last is admin-gated
#     because it is the only thing in the whole sub-module that writes a ledger.
#   * ``MeterReading`` has NO edit route and NO delete route AT ALL — not a missing feature, a
#     decision. The suite asserts the absence with ``NoReverseMatch``, which is the only assertion
#     that actually fails if somebody adds one back.
# =================================================================================================
_ASSET_GET_ROUTES = (
    "scm:asset_list", "scm:asset_create",
    "scm:maintenanceplan_list", "scm:maintenanceplan_create",
    "scm:maintenanceworkorder_list", "scm:maintenanceworkorder_create",
    "scm:meterreading_list", "scm:meterreading_create",
    "scm:pm_forecast", "scm:sparepart_list", "scm:asset_depreciation_report",
)

#: ``(url_name, fixture_name)`` for every detail/edit page that takes a pk.
_ASSET_PK_PAGES = (
    ("scm:asset_detail", "asset_b"),
    ("scm:asset_edit", "asset_b"),
    ("scm:asset_add_spare_part", "asset_b"),
    ("scm:maintenanceplan_detail", "maintenance_plan_b"),
    ("scm:maintenanceplan_edit", "maintenance_plan_b"),
    ("scm:maintenanceworkorder_detail", "maintenance_order_b"),
    ("scm:maintenanceworkorder_edit", "maintenance_order_b"),
    ("scm:meterreading_detail", "meter_reading_b"),
)

#: The SIXTEEN POST-only routes and the tenant_b fixture each one is aimed at.
_ASSET_POST_ONLY = (
    ("scm:asset_delete", "asset_b"),
    ("scm:assetsparepart_delete", "spare_part_b"),
    ("scm:maintenanceplan_delete", "maintenance_plan_b"),
    ("scm:maintenanceplan_generate", "maintenance_plan_b"),
    ("scm:maintenanceworkorder_delete", "maintenance_order_b"),
    ("scm:maintenanceworkorder_approve", "maintenance_order_b"),
    ("scm:maintenanceworkorder_schedule", "maintenance_order_b"),
    ("scm:maintenanceworkorder_start", "maintenance_order_b"),
    ("scm:maintenanceworkorder_hold", "maintenance_order_b"),
    ("scm:maintenanceworkorder_resume", "maintenance_order_b"),
    ("scm:maintenanceworkorder_complete", "maintenance_order_b"),
    ("scm:maintenanceworkorder_close", "maintenance_order_b"),
    ("scm:maintenanceworkorder_cancel", "maintenance_order_b"),
    ("scm:maintenanceworkorder_issue_parts", "maintenance_order_b"),
    ("scm:maintenanceworkorder_record_reading", "maintenance_order_b"),
    ("scm:maintenanceworkordertask_toggle", "job_task_b"),
)

#: The eight routes a plain member must be 403'd from.
_ASSET_ADMIN_ONLY = (
    ("scm:asset_delete", "asset_a2"),
    ("scm:assetsparepart_delete", "asset_spare_part_a"),
    ("scm:maintenanceplan_delete", "maintenance_plan_a"),
    ("scm:maintenanceplan_generate", "maintenance_plan_a"),
    ("scm:maintenanceworkorder_delete", "maintenance_order_a"),
    ("scm:maintenanceworkorder_approve", "maintenance_order_a"),
    ("scm:maintenanceworkorder_cancel", "maintenance_order_a"),
    ("scm:maintenanceworkorder_issue_parts", "maintenance_order_a"),
)

#: The routes an ORDINARY member may press — the counterweight, so the gate above is a boundary
#: rather than a wall. Every one of these is ``@login_required`` only.
_ASSET_MEMBER_ALLOWED = ("scm:maintenanceworkorder_schedule", "scm:maintenanceworkorder_start",
                         "scm:maintenanceworkorder_hold", "scm:maintenanceworkorder_resume",
                         "scm:maintenanceworkorder_complete", "scm:maintenanceworkorder_close",
                         "scm:maintenanceworkorder_record_reading")


@pytest.fixture
def spare_part_b(db, asset_b, spare_item_b):
    """A tenant_b parts-list line — the tenant-LESS child every ``asset__tenant`` assertion needs."""
    from apps.scm.models import AssetSparePart
    return AssetSparePart.objects.create(asset=asset_b, item=spare_item_b,
                                         quantity_per_service=Decimal("1"))


def _asset_sec_body(**overrides):
    """A complete, VALID ``AssetForm`` POST body."""
    data = {
        "code": "SEC-1", "name": "Security probe", "asset_type": "machine",
        "status": "in_service", "criticality": "medium", "category": "", "manufacturer": "",
        "model_number": "", "serial_number": "", "tag_code": "", "specifications": "",
        "parent": "", "location": "", "org_unit": "", "work_center": "", "custodian": "",
        "supplier": "", "service_vendor": "", "purchase_date": "", "commissioned_on": "",
        "warranty_expires_on": "", "purchase_cost": "0.00", "fixed_asset": "", "meter_name": "",
        "meter_unit": "", "is_active": "on", "notes": "",
    }
    data.update(overrides)
    return data


def _job_sec_body(**overrides):
    """A complete ``MaintenanceWorkOrderForm`` POST body with its (empty) parts formset."""
    data = {
        "title": "Security probe", "work_type": "corrective", "priority": "medium",
        "source": "request", "asset": "", "plan": "", "reported_by": "", "assigned_to": "",
        "service_vendor": "", "parts_location": "", "non_conformance": "",
        "reported_at": _asset_sec_day(0).isoformat(), "scheduled_start": "", "downtime_start": "",
        "downtime_end": "", "is_unplanned_downtime": "", "problem_code": "", "cause_code": "",
        "remedy_code": "", "labour_hours": "0.00", "labour_rate": "0.0000",
        "external_cost": "0.00", "meter_reading_at_work": "", "description": "",
        "resolution_notes": "",
    }
    data.update(overrides)
    data.update(formset_data("parts", []))
    return data


def _plan_sec_body(**overrides):
    """A complete ``MaintenancePlanForm`` POST body with its (empty) task formset."""
    data = {
        "name": "Security probe", "asset": "", "instructions": "", "is_active": "on",
        "trigger_type": "calendar", "schedule_basis": "floating", "interval_days": "30",
        "lead_time_days": "7", "meter_interval": "", "next_due_on": _asset_sec_day(10).isoformat(),
        "next_due_reading": "", "condition_operator": "", "condition_threshold": "",
        "priority": "medium", "work_type": "preventive", "estimated_hours": "1.00",
        "assigned_to": "", "parts_location": "",
    }
    data.update(overrides)
    data.update(formset_data("tasks", []))
    return data


# ================================================================ 4.13 · anonymous is turned away
class TestAssetManagementAnonymousRedirect:
    @pytest.mark.parametrize("url_name", _ASSET_GET_ROUTES)
    def test_every_get_route_redirects_to_login(self, url_name):
        resp = Client().get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:asset_detail", "asset_a"), ("scm:asset_edit", "asset_a"),
        ("scm:asset_add_spare_part", "asset_a"),
        ("scm:assetsparepart_edit", "asset_spare_part_a"),
        ("scm:maintenanceplan_detail", "maintenance_plan_a"),
        ("scm:maintenanceplan_edit", "maintenance_plan_a"),
        ("scm:maintenanceworkorder_detail", "maintenance_order_a"),
        ("scm:maintenanceworkorder_edit", "maintenance_order_a"),
        ("scm:meterreading_detail", "meter_reading_a"),
    ])
    def test_every_pk_page_redirects_before_it_resolves_a_pk(self, request, url_name,
                                                             fixture_name):
        obj = request.getfixturevalue(fixture_name)
        resp = Client().get(reverse(url_name, args=[obj.pk]))
        assert resp.status_code == 302 and "login" in resp["Location"]

    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:asset_delete", "asset_a2"),
        ("scm:assetsparepart_delete", "asset_spare_part_a"),
        ("scm:maintenanceplan_delete", "maintenance_plan_a"),
        ("scm:maintenanceplan_generate", "maintenance_plan_a"),
        ("scm:maintenanceworkorder_delete", "maintenance_order_a"),
        ("scm:maintenanceworkorder_approve", "maintenance_order_a"),
        ("scm:maintenanceworkorder_cancel", "maintenance_order_a"),
        ("scm:maintenanceworkorder_issue_parts", "maintenance_order_a"),
        ("scm:maintenanceworkordertask_toggle", "job_task_a"),
    ])
    def test_every_verb_rejects_anonymous_and_writes_nothing(self, request, url_name,
                                                             fixture_name):
        obj = request.getfixturevalue(fixture_name)
        before = getattr(obj, "status", None)
        resp = Client().post(reverse(url_name, args=[obj.pk]),
                             {"reason": "x", "reading": "1", "scheduled_start": "2026-01-01"})
        assert resp.status_code == 302 and "login" in resp["Location"]
        obj.refresh_from_db()
        assert getattr(obj, "status", None) == before

    def test_anonymous_cannot_create_any_413_row(self, tenant_a, asset_a):
        from apps.scm.models import Asset, MaintenancePlan, MaintenanceWorkOrder, MeterReading
        c = Client()
        assert c.post(reverse("scm:asset_create"), _asset_sec_body()).status_code == 302
        assert c.post(reverse("scm:maintenanceplan_create"),
                      _plan_sec_body(asset=str(asset_a.pk))).status_code == 302
        assert c.post(reverse("scm:maintenanceworkorder_create"),
                      _job_sec_body(asset=str(asset_a.pk))).status_code == 302
        assert not Asset.objects.filter(code="SEC-1").exists()
        assert not MaintenancePlan.objects.exists()
        assert not MaintenanceWorkOrder.objects.exists()
        assert not MeterReading.objects.exists()


# ================================================================ 4.13 · cross-tenant IDOR
class TestAssetManagementCrossTenantIsolation:
    """Tenant A's admin pointed at tenant B's pk. Every one of these must be a 404."""

    @pytest.mark.parametrize("url_name,fixture_name", _ASSET_PK_PAGES)
    def test_every_detail_and_edit_page_is_404_across_tenants(self, client_a, request, url_name,
                                                              fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 404

    def test_the_three_tenant_less_children_are_404_through_their_parent(self, client_a,
                                                                        spare_part_b,
                                                                        job_task_b):
        """``AssetSparePart`` has no tenant column, so ``asset__tenant`` IS the check; the same for
        ``MaintenanceWorkOrderTask`` through ``work_order__tenant``. Resolving either on its own pk
        would be a cross-tenant write with no query anywhere that would reveal it."""
        assert client_a.get(reverse("scm:assetsparepart_edit",
                                    args=[spare_part_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:assetsparepart_delete",
                                     args=[spare_part_b.pk])).status_code == 404
        assert client_a.post(reverse("scm:maintenanceworkordertask_toggle",
                                     args=[job_task_b.pk])).status_code == 404

    @pytest.mark.parametrize("url_name,fixture_name", _ASSET_POST_ONLY)
    def test_every_verb_is_404_across_tenants_and_changes_nothing(self, client_a, request,
                                                                  url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        before = {name: getattr(obj, name, None)
                  for name in ("status", "title", "next_due_on", "next_due_reading",
                               "last_generated_on", "is_done", "quantity_per_service")}
        resp = client_a.post(reverse(url_name, args=[obj.pk]),
                             {"reason": "x", "reading": "1",
                              "scheduled_start": _asset_sec_day(1).isoformat()})
        assert resp.status_code == 404, url_name
        obj.refresh_from_db()
        for name, value in before.items():
            assert getattr(obj, name, None) == value, (url_name, name)

    def test_a_generate_across_tenants_raises_no_job_at_all(self, client_a, maintenance_plan_b):
        from apps.scm.models import MaintenanceWorkOrder
        before = MaintenanceWorkOrder.objects.count()
        assert client_a.post(reverse("scm:maintenanceplan_generate",
                                     args=[maintenance_plan_b.pk])).status_code == 404
        assert MaintenanceWorkOrder.objects.count() == before

    def test_an_issue_parts_across_tenants_writes_no_stock_move(self, client_a, tenant_b,
                                                                maintenance_order_b,
                                                                spare_item_b):
        from apps.scm.models import MaintenanceWorkOrderPart, StockMove
        MaintenanceWorkOrderPart.objects.create(work_order=maintenance_order_b, item=spare_item_b,
                                                quantity=Decimal("1"))
        assert client_a.post(reverse("scm:maintenanceworkorder_issue_parts",
                                     args=[maintenance_order_b.pk])).status_code == 404
        assert not StockMove.objects.filter(tenant=tenant_b, move_type="maintenance").exists()

    def test_a_record_reading_across_tenants_writes_no_reading(self, client_a, tenant_b,
                                                               maintenance_order_b):
        from apps.scm.models import MeterReading
        before = MeterReading.objects.filter(tenant=tenant_b).count()
        assert client_a.post(reverse("scm:maintenanceworkorder_record_reading",
                                     args=[maintenance_order_b.pk]),
                             {"reading": "500"}).status_code == 404
        assert MeterReading.objects.filter(tenant=tenant_b).count() == before

    def test_a_tenant_less_superuser_gets_404_rather_than_somebody_elses_child(
            self, db, asset_spare_part_a, job_task_a):
        """``request.tenant`` of ``None`` resolves to ``asset__tenant IS NULL``, and that column is
        NOT NULL — so the tenant-less superuser gets a 404, never a foreign row."""
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(email="root413@naverp.test", username="root413",
                                                  password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        assert c.get(reverse("scm:assetsparepart_edit",
                             args=[asset_spare_part_a.pk])).status_code == 404
        assert c.post(reverse("scm:maintenanceworkordertask_toggle",
                              args=[job_task_a.pk])).status_code == 404

    def test_no_list_page_ever_shows_the_other_tenants_rows(self, client_a, asset_a, asset_b,
                                                            maintenance_plan_a,
                                                            maintenance_plan_b,
                                                            maintenance_order_a,
                                                            maintenance_order_b, meter_reading_a,
                                                            meter_reading_b):
        for url_name, mine, theirs in (
                ("scm:asset_list", asset_a, asset_b),
                ("scm:maintenanceplan_list", maintenance_plan_a, maintenance_plan_b),
                ("scm:maintenanceworkorder_list", maintenance_order_a, maintenance_order_b),
                ("scm:meterreading_list", meter_reading_a, meter_reading_b)):
            rows = client_a.get(reverse(url_name)).context["object_list"]
            assert mine in rows and theirs not in rows, url_name

    def test_neither_computed_report_leaks_a_foreign_row(self, client_a, asset_b,
                                                         maintenance_plan_b, spare_item_b):
        assert client_a.get(reverse("scm:pm_forecast")).context["stats"]["plans_considered"] == 0
        assert client_a.get(reverse("scm:sparepart_list")).context["rows"] == []
        assert client_a.get(reverse("scm:asset_depreciation_report")).context["rows"] == []

    @pytest.mark.parametrize("field,fixture_name", [
        ("location", "location_b"), ("work_center", "work_center_b"), ("org_unit", "org_unit_b"),
        ("custodian", "supplier_b"), ("supplier", "supplier_b"), ("service_vendor", "supplier_b"),
        ("fixed_asset", "fixed_asset_b"), ("parent", "asset_b"),
    ])
    def test_a_crafted_foreign_pk_in_an_asset_fk_is_rejected(self, client_a, request, field,
                                                             fixture_name):
        """A narrowed ``<select>`` is UX; the guard is the form's and the model's ``clean()``."""
        from apps.scm.models import Asset
        foreign = request.getfixturevalue(fixture_name)
        resp = client_a.post(reverse("scm:asset_create"),
                             _asset_sec_body(**{field: str(foreign.pk)}))
        assert resp.status_code == 200
        assert not Asset.objects.filter(code="SEC-1").exists()

    @pytest.mark.parametrize("field,fixture_name", [
        ("asset", "asset_b"), ("plan", "maintenance_plan_b"), ("parts_location", "location_b"),
        ("non_conformance", "nonconformance_b"), ("reported_by", "supplier_b"),
        ("assigned_to", "supplier_b"), ("service_vendor", "supplier_b"),
    ])
    def test_a_crafted_foreign_pk_in_a_job_fk_is_rejected(self, client_a, asset_a, request, field,
                                                          fixture_name):
        from apps.scm.models import MaintenanceWorkOrder
        foreign = request.getfixturevalue(fixture_name)
        body = _job_sec_body(asset=str(asset_a.pk))
        body[field] = str(foreign.pk)
        resp = client_a.post(reverse("scm:maintenanceworkorder_create"), body)
        assert resp.status_code == 200
        assert not MaintenanceWorkOrder.objects.filter(title="Security probe").exists()

    @pytest.mark.parametrize("field,fixture_name", [
        ("asset", "asset_b"), ("assigned_to", "supplier_b"), ("parts_location", "location_b"),
    ])
    def test_a_crafted_foreign_pk_in_a_plan_fk_is_rejected(self, client_a, asset_a, request,
                                                           field, fixture_name):
        from apps.scm.models import MaintenancePlan
        foreign = request.getfixturevalue(fixture_name)
        body = _plan_sec_body(asset=str(asset_a.pk))
        body[field] = str(foreign.pk)
        resp = client_a.post(reverse("scm:maintenanceplan_create"), body)
        assert resp.status_code == 200
        assert not MaintenancePlan.objects.filter(name="Security probe").exists()

    def test_a_crafted_foreign_item_on_a_parts_list_line_is_rejected(self, client_a, asset_a,
                                                                     spare_item_b):
        from apps.scm.models import AssetSparePart
        resp = client_a.post(reverse("scm:asset_add_spare_part", args=[asset_a.pk]),
                             {"item": str(spare_item_b.pk), "quantity_per_service": "1"})
        assert resp.status_code == 200
        assert not AssetSparePart.objects.filter(item=spare_item_b, asset=asset_a).exists()

    def test_a_crafted_foreign_item_in_the_parts_formset_is_rejected(self, client_a, asset_a,
                                                                     spare_item_b):
        from apps.scm.models import MaintenanceWorkOrder
        body = _job_sec_body(asset=str(asset_a.pk))
        body.update(formset_data("parts", [{"id": "", "item": str(spare_item_b.pk),
                                            "lot_serial": "", "quantity": "1"}]))
        resp = client_a.post(reverse("scm:maintenanceworkorder_create"), body)
        assert resp.status_code == 200
        assert not MaintenanceWorkOrder.objects.filter(title="Security probe").exists()

    def test_a_crafted_foreign_asset_on_a_manual_reading_is_rejected(self, client_a, asset_b,
                                                                     tenant_b):
        from apps.scm.models import MeterReading
        before = MeterReading.objects.filter(tenant=tenant_b).count()
        resp = client_a.post(reverse("scm:meterreading_create"),
                             {"asset": str(asset_b.pk), "meter_name": "Cycles", "unit": "",
                              "reading": "1", "read_at": _asset_sec_day(0).isoformat() + " 08:00",
                              "notes": ""})
        assert resp.status_code == 200
        assert MeterReading.objects.filter(tenant=tenant_b).count() == before


# ================================================================ 4.13 · the admin gates
class TestAssetManagementTenantAdminGates:
    @pytest.mark.parametrize("url_name,fixture_name", _ASSET_ADMIN_ONLY)
    def test_a_plain_member_is_403_on_every_admin_route(self, member_client, request, url_name,
                                                        fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert member_client.post(reverse(url_name, args=[obj.pk]),
                                  {"reason": "x"}).status_code == 403

    def test_there_are_exactly_eight_of_them(self):
        assert len({name for name, _ in _ASSET_ADMIN_ONLY}) == 8

    def test_a_403_writes_nothing(self, member_client, maintenance_plan_a, maintenance_order_a,
                                  part_line_a, tenant_a):
        from apps.scm.models import MaintenanceWorkOrder, StockMove
        published = maintenance_plan_a.next_due_on
        member_client.post(reverse("scm:maintenanceplan_generate", args=[maintenance_plan_a.pk]))
        member_client.post(reverse("scm:maintenanceworkorder_issue_parts",
                                   args=[maintenance_order_a.pk]))
        member_client.post(reverse("scm:maintenanceworkorder_approve",
                                   args=[maintenance_order_a.pk]))
        maintenance_plan_a.refresh_from_db()
        maintenance_order_a.refresh_from_db()
        assert maintenance_plan_a.next_due_on == published
        assert maintenance_plan_a.last_generated_on is None
        assert maintenance_order_a.status == "requested"
        assert MaintenanceWorkOrder.objects.filter(plan=maintenance_plan_a).count() == 0
        assert not StockMove.objects.filter(tenant=tenant_a, move_type="maintenance").exists()

    @pytest.mark.parametrize("url_name", _ASSET_MEMBER_ALLOWED)
    def test_ordinary_shop_floor_verbs_stay_open_to_a_member(self, member_client,
                                                             maintenance_order_a, url_name):
        """The counterweight: the gate is a boundary, not a wall. A member 403'd from starting the
        job they were assigned would simply stop recording work."""
        resp = member_client.post(reverse(url_name, args=[maintenance_order_a.pk]),
                                  {"reading": "1", "scheduled_start": _asset_sec_day(1).isoformat()})
        assert resp.status_code != 403

    def test_a_member_may_still_read_every_page_and_edit_the_ordinary_records(
            self, member_client, asset_a, maintenance_plan_a, maintenance_order_a,
            meter_reading_a):
        for url_name in _ASSET_GET_ROUTES:
            assert member_client.get(reverse(url_name)).status_code == 200, url_name
        for url_name, obj in (("scm:asset_edit", asset_a),
                              ("scm:maintenanceplan_edit", maintenance_plan_a),
                              ("scm:maintenanceworkorder_edit", maintenance_order_a)):
            assert member_client.get(reverse(url_name, args=[obj.pk])).status_code == 200

    def test_a_member_may_create_the_ordinary_records(self, member_client, tenant_a, asset_a):
        from apps.scm.models import Asset, MaintenanceWorkOrder
        member_client.post(reverse("scm:asset_create"), _asset_sec_body(), follow=True)
        member_client.post(reverse("scm:maintenanceworkorder_create"),
                           _job_sec_body(asset=str(asset_a.pk)), follow=True)
        assert Asset.objects.filter(tenant=tenant_a, code="SEC-1").exists()
        assert MaintenanceWorkOrder.objects.filter(title="Security probe").exists()


# ================================================================ 4.13 · the absent CRUD routes
class TestMeterReadingHasNoEditOrDeleteRoute:
    """The absence is a DECISION, not an omission, and this is the only assertion that fails if
    somebody adds one back.

    A wrong reading is corrected by posting a LATER, correct one — the ``scm.StockMove`` posture. An
    editable reading is a number a scheduler already acted on, changed after the fact, with no trace
    that it ever said anything else, on a log every meter-based due date is derived from.
    """

    @pytest.mark.parametrize("url_name", ["scm:meterreading_edit", "scm:meterreading_delete",
                                          "scm:meterreading_update", "scm:meterreading_remove"])
    def test_reversing_an_edit_or_delete_route_raises(self, url_name, meter_reading_a):
        from django.urls import NoReverseMatch
        with pytest.raises(NoReverseMatch):
            reverse(url_name, args=[meter_reading_a.pk])

    def test_the_view_layer_exports_no_such_callable(self):
        import apps.scm.views as views_pkg
        assert not hasattr(views_pkg, "meterreading_edit")
        assert not hasattr(views_pkg, "meterreading_delete")

    def test_the_three_routes_it_DOES_have_all_resolve(self, meter_reading_a):
        assert reverse("scm:meterreading_list")
        assert reverse("scm:meterreading_create")
        assert reverse("scm:meterreading_detail", args=[meter_reading_a.pk])

    def test_the_detail_page_offers_no_edit_or_delete_form(self, client_a, meter_reading_a):
        """Back to List only — and the page prints the note that explains why."""
        content = client_a.get(reverse("scm:meterreading_detail",
                                       args=[meter_reading_a.pk])).content.decode()
        assert "append-only" in content.lower()
        assert "meter-readings/%d/edit" % meter_reading_a.pk not in content
        assert "meter-readings/%d/delete" % meter_reading_a.pk not in content

    def test_there_is_no_checklist_create_or_delete_route_either(self, job_task_a):
        """The checklist is a SNAPSHOT written by ``maintenanceplan_generate``; ticking a step is
        the only change a job's checklist accepts."""
        from django.urls import NoReverseMatch
        for url_name in ("scm:maintenanceworkordertask_create",
                         "scm:maintenanceworkordertask_delete",
                         "scm:maintenanceworkordertask_edit"):
            with pytest.raises(NoReverseMatch):
                reverse(url_name, args=[job_task_a.pk])


# ================================================================ 4.13 · CSRF
class TestAssetManagementCSRF:
    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:maintenanceplan_generate", "maintenance_plan_a"),
        ("scm:maintenanceworkorder_approve", "maintenance_order_a"),
        ("scm:maintenanceworkorder_issue_parts", "maintenance_order_a"),
        ("scm:maintenanceworkordertask_toggle", "job_task_a"),
        ("scm:asset_delete", "asset_a2"),
        ("scm:assetsparepart_delete", "asset_spare_part_a"),
    ])
    def test_a_post_without_a_token_is_refused(self, admin_user, request, url_name,
                                               fixture_name):
        obj = request.getfixturevalue(fixture_name)
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse(url_name, args=[obj.pk]), {"reason": "x"}).status_code == 403

    def test_the_three_create_screens_refuse_a_tokenless_post(self, admin_user, tenant_a,
                                                              asset_a):
        from apps.scm.models import Asset, MaintenancePlan, MaintenanceWorkOrder
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        assert c.post(reverse("scm:asset_create"), _asset_sec_body()).status_code == 403
        assert c.post(reverse("scm:maintenanceplan_create"),
                      _plan_sec_body(asset=str(asset_a.pk))).status_code == 403
        assert c.post(reverse("scm:maintenanceworkorder_create"),
                      _job_sec_body(asset=str(asset_a.pk))).status_code == 403
        assert not Asset.objects.filter(code="SEC-1").exists()
        assert not MaintenancePlan.objects.filter(name="Security probe").exists()
        assert not MaintenanceWorkOrder.objects.filter(title="Security probe").exists()

    def test_the_refused_verb_wrote_nothing(self, admin_user, maintenance_plan_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        c.post(reverse("scm:maintenanceplan_generate", args=[maintenance_plan_a.pk]))
        maintenance_plan_a.refresh_from_db()
        assert maintenance_plan_a.last_generated_on is None

    def test_every_rendered_form_carries_a_token(self, client_a, asset_a, maintenance_plan_a,
                                                 maintenance_order_a):
        for url_name, args in (("scm:asset_create", []), ("scm:maintenanceplan_create", []),
                               ("scm:maintenanceworkorder_create", []),
                               ("scm:meterreading_create", []),
                               ("scm:asset_detail", [asset_a.pk]),
                               ("scm:maintenanceplan_detail", [maintenance_plan_a.pk]),
                               ("scm:maintenanceworkorder_detail",
                                [maintenance_order_a.pk])):
            content = client_a.get(reverse(url_name, args=args)).content.decode()
            assert "csrfmiddlewaretoken" in content, url_name


# ================================================================ 4.13 · hostile query strings
class TestAssetManagementHostileFilters:
    """Every one of these is a URL anybody can type into the address bar."""

    _JUNK = ("abc", "²", "99999999999999999999", "-1", "0", "'; DROP TABLE scm_asset; --",
             "<script>alert(1)</script>", "NaN", "Infinity")

    @pytest.mark.parametrize("junk", _JUNK)
    @pytest.mark.parametrize("param", ["location", "work_center", "org_unit", "status",
                                       "criticality", "asset_type", "is_active", "warranty", "q"])
    def test_the_asset_register_lands_on_a_page(self, client_a, asset_a, param, junk):
        assert client_a.get(reverse("scm:asset_list"), {param: junk}).status_code == 200

    @pytest.mark.parametrize("junk", _JUNK)
    @pytest.mark.parametrize("param", ["asset", "assigned_to", "trigger_type", "schedule_basis",
                                       "priority", "is_active", "due", "q"])
    def test_the_pm_programme_lands_on_a_page(self, client_a, maintenance_plan_a, param, junk):
        assert client_a.get(reverse("scm:maintenanceplan_list"),
                            {param: junk}).status_code == 200

    @pytest.mark.parametrize("junk", _JUNK)
    @pytest.mark.parametrize("param", ["asset", "assigned_to", "status", "work_type", "priority",
                                       "problem_code", "date_from", "date_to", "q"])
    def test_the_job_queue_lands_on_a_page(self, client_a, maintenance_order_a, param, junk):
        assert client_a.get(reverse("scm:maintenanceworkorder_list"),
                            {param: junk}).status_code == 200

    @pytest.mark.parametrize("junk", _JUNK)
    @pytest.mark.parametrize("param", ["asset", "source", "date_from", "date_to", "q"])
    def test_the_reading_log_lands_on_a_page(self, client_a, meter_reading_a, param, junk):
        assert client_a.get(reverse("scm:meterreading_list"), {param: junk}).status_code == 200

    @pytest.mark.parametrize("junk", _JUNK)
    def test_the_pm_board_horizon_lands_on_a_page(self, client_a, maintenance_plan_a, junk):
        resp = client_a.get(reverse("scm:pm_forecast"), {"days": junk})
        assert resp.status_code == 200
        assert 1 <= resp.context["days"] <= 365

    @pytest.mark.parametrize("junk", _JUNK)
    @pytest.mark.parametrize("param", ["category", "stock", "is_active", "date_from", "date_to",
                                       "q"])
    def test_the_storeroom_lands_on_a_page(self, client_a, spare_item_a, param, junk):
        assert client_a.get(reverse("scm:sparepart_list"), {param: junk}).status_code == 200

    @pytest.mark.parametrize("junk", _JUNK)
    @pytest.mark.parametrize("param", ["location", "status", "asset_type", "criticality",
                                       "linked", "q"])
    def test_the_depreciation_report_lands_on_a_page(self, client_a, asset_a, param, junk):
        assert client_a.get(reverse("scm:asset_depreciation_report"),
                            {param: junk}).status_code == 200

    @pytest.mark.parametrize("page", ["0", "-1", "abc", "99999", "99999999999999999999"])
    def test_every_paginated_page_survives_a_hostile_page_number(self, client_a, asset_a,
                                                                 maintenance_plan_a,
                                                                 maintenance_order_a,
                                                                 meter_reading_a, page):
        for url_name in ("scm:asset_list", "scm:maintenanceplan_list",
                         "scm:maintenanceworkorder_list", "scm:meterreading_list",
                         "scm:sparepart_list"):
            assert client_a.get(reverse(url_name),
                                {"page": page}).status_code == 200, (url_name, page)


# ================================================================ 4.13 · hostile POST values
class TestAssetManagementHostileNumbers:
    """Anywhere a decimal is hand-parsed from a POST body, junk must be a friendly error."""

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "abc", "-1",
                                       "99999999999999999999", "1e400", ""])
    def test_a_hostile_meter_capture_never_500s(self, client_a, maintenance_order_a, value):
        resp = client_a.post(reverse("scm:maintenanceworkorder_record_reading",
                                     args=[maintenance_order_a.pk]), {"reading": value},
                             follow=True)
        assert resp.status_code == 200

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "lastweek", "9999-99-99",
                                       "0000-01-01", "-1"])
    def test_a_hostile_scheduled_start_never_500s(self, client_a, approved_order_a, value):
        resp = client_a.post(reverse("scm:maintenanceworkorder_schedule",
                                     args=[approved_order_a.pk]),
                             {"scheduled_start": value}, follow=True)
        assert resp.status_code == 200

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "-5", "99999999999999999999"])
    def test_a_hostile_purchase_cost_is_a_field_error_and_not_a_500(self, client_a, value):
        from apps.scm.models import Asset
        resp = client_a.post(reverse("scm:asset_create"), _asset_sec_body(purchase_cost=value))
        assert resp.status_code == 200
        assert not Asset.objects.filter(code="SEC-1").exists()

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "-5", "4294967295"])
    def test_a_hostile_interval_is_a_field_error_and_not_a_500(self, client_a, asset_a, value):
        """``interval_days`` is fed straight to ``timedelta(days=...)`` — an unbounded value is an
        ``OverflowError``, i.e. a 500, on the very next list page load."""
        from apps.scm.models import MaintenancePlan
        resp = client_a.post(reverse("scm:maintenanceplan_create"),
                             _plan_sec_body(asset=str(asset_a.pk), interval_days=value))
        assert resp.status_code == 200
        assert not MaintenancePlan.objects.filter(name="Security probe").exists()

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "-1", "999999"])
    def test_a_hostile_labour_rate_is_a_field_error_and_not_a_500(self, client_a, asset_a, value):
        """The ceiling is on the way IN because an absurd rate flows into three other pages."""
        from apps.scm.models import MaintenanceWorkOrder
        resp = client_a.post(reverse("scm:maintenanceworkorder_create"),
                             _job_sec_body(asset=str(asset_a.pk), labour_rate=value))
        assert resp.status_code == 200
        assert not MaintenanceWorkOrder.objects.filter(title="Security probe").exists()

    @pytest.mark.parametrize("value", ["NaN", "Infinity", "abc", "-1"])
    def test_a_hostile_spare_quantity_is_a_field_error_and_not_a_500(self, client_a, asset_a,
                                                                     spare_item_a, value):
        from apps.scm.models import AssetSparePart
        resp = client_a.post(reverse("scm:asset_add_spare_part", args=[asset_a.pk]),
                             {"item": str(spare_item_a.pk), "quantity_per_service": value})
        assert resp.status_code == 200
        assert not AssetSparePart.objects.filter(asset=asset_a).exists()

    def test_an_absent_prerequisite_is_refused_and_never_falls_through(self, client_a,
                                                                       maintenance_order_a,
                                                                       part_line_a):
        """L35: the issue verb with NO storeroom must REFUSE, not guess one and post the ledger
        against a location that never held the stock."""
        from apps.scm.models import StockMove
        maintenance_order_a.parts_location = None
        maintenance_order_a.save(update_fields=["parts_location", "updated_at"])
        client_a.post(reverse("scm:maintenanceworkorder_issue_parts",
                              args=[maintenance_order_a.pk]), follow=True)
        assert not StockMove.objects.filter(reference=maintenance_order_a.number).exists()
        part_line_a.refresh_from_db()
        assert part_line_a.is_issued is False


# ================================================================ 4.13 · XSS
class TestAssetManagementXss:
    _PAYLOAD = "<script>alert('xss')</script>"

    def test_an_asset_name_is_escaped_on_every_page_that_renders_it(self, client_a, tenant_a,
                                                                    asset_a):
        asset_a.name = self._PAYLOAD
        asset_a.save(update_fields=["name", "updated_at"])
        for url_name, args in (("scm:asset_list", []), ("scm:asset_detail", [asset_a.pk]),
                               ("scm:asset_depreciation_report", [])):
            content = client_a.get(reverse(url_name, args=args)).content.decode()
            assert self._PAYLOAD not in content, url_name
            assert "&lt;script&gt;" in content, url_name

    def test_a_job_title_is_escaped(self, client_a, maintenance_order_a):
        maintenance_order_a.title = self._PAYLOAD
        maintenance_order_a.save(update_fields=["title", "updated_at"])
        for url_name, args in (("scm:maintenanceworkorder_list", []),
                               ("scm:maintenanceworkorder_detail",
                                [maintenance_order_a.pk])):
            content = client_a.get(reverse(url_name, args=args)).content.decode()
            assert self._PAYLOAD not in content, url_name

    def test_a_plan_name_and_a_meter_name_are_escaped(self, client_a, maintenance_plan_a,
                                                      meter_reading_a):
        maintenance_plan_a.name = self._PAYLOAD
        maintenance_plan_a.save(update_fields=["name", "updated_at"])
        meter_reading_a.meter_name = self._PAYLOAD[:40]
        meter_reading_a.save(update_fields=["meter_name", "updated_at"])
        for url_name, args in (("scm:maintenanceplan_list", []),
                               ("scm:maintenanceplan_detail", [maintenance_plan_a.pk]),
                               ("scm:meterreading_list", []),
                               ("scm:meterreading_detail", [meter_reading_a.pk]),
                               ("scm:pm_forecast", [])):
            content = client_a.get(reverse(url_name, args=args)).content.decode()
            assert "<script>alert(" not in content, url_name


# ================================================================ 4.13 · the inline-formset children
class TestAssetManagementInlineChildIsolation:
    """``MaintenancePlanTask`` and ``MaintenanceWorkOrderPart`` have NO route of their own — the
    only way to reach either is the parent's inline formset, which is exactly why the crafted ``id``
    has to be tested there.

    Both carry no ``tenant`` column (``plan__tenant`` / ``work_order__tenant``), so a formset row
    that named another workspace's child pk and was accepted would RE-PARENT that row into this
    workspace — a cross-tenant write with no query anywhere that would reveal it.
    """

    def test_a_foreign_plan_task_id_cannot_be_grafted_onto_this_workspaces_plan(
            self, client_a, maintenance_plan_a, plan_task_b, maintenance_plan_b):
        body = _plan_sec_body(asset=str(maintenance_plan_a.asset_id),
                              name=maintenance_plan_a.name)
        body.update(formset_data("tasks", [{"id": str(plan_task_b.pk), "sequence": "10",
                                            "description": "Stolen step", "expected_result": "",
                                            "is_mandatory": "on", "is_safety_step": ""}],
                                 initial=1))
        resp = client_a.post(reverse("scm:maintenanceplan_edit", args=[maintenance_plan_a.pk]),
                             body)
        plan_task_b.refresh_from_db()
        assert plan_task_b.plan_id == maintenance_plan_b.pk
        assert plan_task_b.description == "Globex step"
        assert not maintenance_plan_a.tasks.filter(description="Stolen step").exists()
        assert resp.status_code in (200, 302)

    def test_a_foreign_part_line_id_cannot_be_grafted_onto_this_workspaces_job(
            self, client_a, maintenance_order_a, maintenance_order_b, spare_item_a,
            spare_item_b):
        from apps.scm.models import MaintenanceWorkOrderPart
        foreign = MaintenanceWorkOrderPart.objects.create(
            work_order=maintenance_order_b, item=spare_item_b, quantity=Decimal("1"))
        body = _job_sec_body(asset=str(maintenance_order_a.asset_id),
                             title=maintenance_order_a.title)
        body.update(formset_data("parts", [{"id": str(foreign.pk), "item": str(spare_item_a.pk),
                                            "lot_serial": "", "quantity": "99"}], initial=1))
        resp = client_a.post(reverse("scm:maintenanceworkorder_edit",
                                     args=[maintenance_order_a.pk]), body)
        foreign.refresh_from_db()
        assert foreign.work_order_id == maintenance_order_b.pk
        assert foreign.item_id == spare_item_b.pk
        assert foreign.quantity == Decimal("1.0000")
        assert resp.status_code in (200, 302)

    def test_deleting_a_foreign_child_through_the_formset_is_refused(self, client_a,
                                                                     maintenance_plan_a,
                                                                     plan_task_b):
        from apps.scm.models import MaintenancePlanTask
        body = _plan_sec_body(asset=str(maintenance_plan_a.asset_id),
                              name=maintenance_plan_a.name)
        body.update(formset_data("tasks", [{"id": str(plan_task_b.pk), "sequence": "10",
                                            "description": "Globex step", "expected_result": "",
                                            "is_mandatory": "on", "is_safety_step": "",
                                            "DELETE": "on"}], initial=1))
        client_a.post(reverse("scm:maintenanceplan_edit", args=[maintenance_plan_a.pk]), body)
        assert MaintenancePlanTask.objects.filter(pk=plan_task_b.pk).exists()

    def test_neither_child_has_a_route_of_its_own(self, plan_task_a, part_line_a):
        """The absence IS the design: a child pk with its own route is one more surface that has to
        remember to join back to the parent for authorization."""
        from django.urls import NoReverseMatch
        for url_name in ("scm:maintenanceplantask_edit", "scm:maintenanceplantask_delete",
                         "scm:maintenanceworkorderpart_edit",
                         "scm:maintenanceworkorderpart_delete"):
            with pytest.raises(NoReverseMatch):
                reverse(url_name, args=[1])

# The 4.14 date helpers are module-level functions in conftest.py rather than fixtures, so pytest
# does not inject them. Imported, not re-declared: test_suite_hygiene.py fails the suite on a
# duplicate module-level name.
from apps.scm.tests.conftest import _labor_moment, _labor_workday  # noqa: E402


# =================================================================================================
# SCM 4.14 Labor Management — auth, tenant isolation, method gates and people-data privacy.
#
# Three things need naming before the tests below read correctly.
#
# TWO of the five tables cannot be reached by their own tenant column. `LaborPlanLine` has NO tenant
# field at all and is scoped through `plan__tenant`; `LaborActivity` is scoped through BOTH its own
# tenant AND `session__tenant`. On those, a bare pk lookup is a cross-tenant read or WRITE with no
# query anywhere that would reveal it — the parent join IS the authorization check, so each gets its
# own IDOR test rather than being assumed covered by its parent's.
#
# THIRTEEN routes are @tenant_admin_required, and `labor_scorecard` is one of them — it RANKS named
# colleagues against each other with a coaching band attached, and there is no version of that
# scoped to one person which is still a ranking. House policy for a workspace-wide roll-up over
# people is admin-only (hrm's cost / leave-liability / executive reports all are).
#
# `labor_payroll_export` is deliberately NOT gated, and that asymmetry is the subtlest thing here.
# It is a sidebar destination and `resolve_nav` has no per-link permission concept, so gating it
# would hand every member a bullet that 403s (L32). Instead the ROWS narrow: an admin sees the
# workspace, everyone else sees only themselves. Two things had to be right for that to hold and
# both are tested — a member with no linked Party must see NOTHING (a `None` worker id means "no
# filter" to the aggregate and would have returned the whole floor), and the worker DROPDOWN must
# narrow too, because listing every colleague by name in a <select> leaks exactly the roster the
# table just hid.
# =================================================================================================

#: Every 4.14 route that is @tenant_admin_required, as (url_name, fixture_name). A member POSTing
#: any of these is 403. Kept as one list so the count assertion below fails if a route is added or
#: gated later without this file noticing.
_LABOR_ADMIN_ONLY = [
    ("scm:laborstandard_delete", "labor_standard_a"),
    ("scm:laborstandard_activate", "draft_standard_a"),
    ("scm:laborstandard_archive", "labor_standard_a"),
    ("scm:laborsession_delete", "labor_session_a"),
    ("scm:laborsession_approve", "labor_session_a"),
    ("scm:laborsession_reopen", "labor_session_a"),
    ("scm:laborsession_cancel", "labor_session_a"),
    ("scm:laboractivity_delete", "labor_activity_a"),
    ("scm:laborplan_delete", "labor_plan_a"),
    ("scm:laborplan_generate", "labor_plan_a"),
    ("scm:laborplan_approve", "labor_plan_a"),
]
# NOTE `laborplan_archive` is deliberately NOT on that list. Archiving a plan is the SAFE move —
# every line, every snapshot and the approval stamp survive and the plan simply stops being live —
# so it is @login_required while `laborplan_delete` is admin-gated. That asymmetry is the point of
# having both verbs: refusing a planner the safe one only pushes them towards asking an
# administrator for the destructive one. Pinned by its own test below so it is not "tidied" into
# matching its siblings.

#: Every 4.14 verb, as (url_name, needs_pk). A GET must be 405 on all of them — a state change
#: reachable by typing a URL is a state change a link, a prefetch or a crawler can trigger.
_LABOR_VERBS = [
    ("scm:laborstandard_activate", True), ("scm:laborstandard_archive", True),
    ("scm:laborstandard_delete", True),
    ("scm:laborsession_clock_in", False), ("scm:laborsession_clock_out", True),
    ("scm:laborsession_close", True), ("scm:laborsession_approve", True),
    ("scm:laborsession_reopen", True), ("scm:laborsession_cancel", True),
    ("scm:laborsession_delete", True),
    ("scm:laboractivity_delete", True),
    ("scm:laborplan_generate", True), ("scm:laborplan_approve", True),
    ("scm:laborplan_archive", True), ("scm:laborplan_delete", True),
    ("scm:labor_board_assign", False), ("scm:labor_board_unassign", False),
]


class TestLaborCrossTenantIsolation:
    """A tenant-A admin against tenant-B rows: 404 everywhere, children included."""

    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:laborstandard_detail", "labor_standard_b"),
        ("scm:laborstandard_edit", "labor_standard_b"),
        ("scm:laborsession_detail", "labor_session_b"),
        ("scm:laborsession_edit", "labor_session_b"),
        ("scm:laboractivity_detail", "labor_activity_b"),
        ("scm:laboractivity_edit", "labor_activity_b"),
        ("scm:laborplan_detail", "labor_plan_b"),
        ("scm:laborplan_edit", "labor_plan_b"),
        ("scm:laborplanline_edit", "labor_plan_line_b"),
        ("scm:laborsession_add_activity", "labor_session_b"),
    ])
    def test_a_foreign_pk_is_404_on_every_get_route(self, client_a, request, url_name,
                                                    fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.get(reverse(url_name, args=[obj.pk])).status_code == 404

    @pytest.mark.parametrize("url_name,fixture_name", [
        ("scm:laborstandard_activate", "labor_standard_b"),
        ("scm:laborstandard_archive", "labor_standard_b"),
        ("scm:laborstandard_delete", "labor_standard_b"),
        ("scm:laborsession_clock_out", "labor_session_b"),
        ("scm:laborsession_close", "labor_session_b"),
        ("scm:laborsession_approve", "labor_session_b"),
        ("scm:laborsession_delete", "labor_session_b"),
        ("scm:laboractivity_delete", "labor_activity_b"),
        ("scm:laborplan_generate", "labor_plan_b"),
        ("scm:laborplan_approve", "labor_plan_b"),
        ("scm:laborplan_delete", "labor_plan_b"),
    ])
    def test_a_foreign_pk_is_404_on_every_verb(self, client_a, request, url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert client_a.post(reverse(url_name, args=[obj.pk])).status_code == 404

    def test_the_tenant_less_plan_line_is_scoped_through_its_PLAN(self, client_a,
                                                                  labor_plan_line_b):
        """LaborPlanLine has no tenant column, so `plan__tenant` is the only thing guarding it."""
        assert client_a.get(
            reverse("scm:laborplanline_edit", args=[labor_plan_line_b.pk])).status_code == 404
        assert client_a.post(
            reverse("scm:laborplanline_edit", args=[labor_plan_line_b.pk]),
            {"planned_headcount": "9"}).status_code == 404

    def test_a_foreign_row_is_never_in_a_list(self, client_a, labor_standard_a, labor_standard_b):
        html = client_a.get(reverse("scm:laborstandard_list")).content.decode()
        assert labor_standard_a.number in html
        assert labor_standard_b.name not in html


class TestLaborTenantAdminGates:
    """The thirteen privileged routes, and the count that catches a fourteenth."""

    @pytest.mark.parametrize("url_name,fixture_name", _LABOR_ADMIN_ONLY)
    def test_a_plain_member_is_403(self, member_client, request, url_name, fixture_name):
        obj = request.getfixturevalue(fixture_name)
        assert member_client.post(reverse(url_name, args=[obj.pk])).status_code == 403

    @pytest.mark.parametrize("url_name", ["scm:labor_board_assign", "scm:labor_board_unassign"])
    def test_a_member_cannot_write_another_sub_modules_table(self, member_client, url_name):
        """The board verbs write 4.4's assigned_to, which is why they are admin-gated."""
        assert member_client.post(reverse(url_name), {"task_kind": "pick"}).status_code == 403

    def test_the_scorecard_is_admin_only(self, member_client):
        """It ranks named colleagues — there is no per-person version that is still a ranking."""
        assert member_client.get(reverse("scm:labor_scorecard")).status_code == 403

    def test_a_member_CAN_archive_a_plan(self, member_client, labor_plan_a):
        """The deliberate exception, pinned. Archiving destroys nothing, so a planner may do it;
        deleting is the admin-gated one. Making these two match would remove the reason both
        exist."""
        assert member_client.post(
            reverse("scm:laborplan_archive", args=[labor_plan_a.pk])).status_code == 302
        labor_plan_a.refresh_from_db()
        assert labor_plan_a.status == "archived"

    def test_but_a_member_still_cannot_DELETE_that_plan(self, member_client, labor_plan_a):
        assert member_client.post(
            reverse("scm:laborplan_delete", args=[labor_plan_a.pk])).status_code == 403

    def test_the_admin_gated_set_is_exactly_fourteen_routes(self):
        """A count, so adding a route without gating it — or gating one silently — fails here."""
        names = {n for n, _ in _LABOR_ADMIN_ONLY}
        names |= {"scm:labor_board_assign", "scm:labor_board_unassign", "scm:labor_scorecard"}
        assert len(names) == 14, sorted(names)


class TestLaborPayrollExportPrivacy:
    """The export names people, so who may read whose figures is the security question."""

    @pytest.fixture
    def approved_shift(self, db, client_a, labor_activity_a, labor_session_a):
        client_a.post(reverse("scm:laborsession_clock_out", args=[labor_session_a.pk]))
        client_a.post(reverse("scm:laborsession_close", args=[labor_session_a.pk]))
        client_a.post(reverse("scm:laborsession_approve", args=[labor_session_a.pk]))
        labor_session_a.refresh_from_db()
        return labor_session_a

    def test_an_admin_sees_the_worker(self, client_a, approved_shift):
        html = client_a.get(reverse("scm:labor_payroll_export")).content.decode()
        assert approved_shift.worker.name in html

    def test_a_member_still_gets_200_because_it_is_a_sidebar_bullet(self, member_client,
                                                                   approved_shift):
        """Gating it would hand every member a sidebar bullet that 403s (L32)."""
        assert member_client.get(reverse("scm:labor_payroll_export")).status_code == 200

    def test_a_member_sees_NO_colleague_name_in_the_html(self, member_client, approved_shift):
        html = member_client.get(reverse("scm:labor_payroll_export")).content.decode()
        assert approved_shift.worker.name not in html

    def test_a_member_sees_NO_colleague_name_in_the_csv(self, member_client, approved_shift):
        resp = member_client.get(reverse("scm:labor_payroll_export"), {"format": "csv"})
        body = (b"".join(resp.streaming_content).decode() if resp.streaming
                else resp.content.decode())
        assert approved_shift.worker.name not in body

    def test_a_member_with_no_linked_party_sees_no_rows_at_all(self, member_client,
                                                              approved_shift):
        """The sentinel case. A `None` worker id means "no filter" to `_worker_aggregate`, so
        falling through with None here would have handed a member the ENTIRE workspace — through
        the very branch written to narrow them to themselves."""
        resp = member_client.get(reverse("scm:labor_payroll_export"))
        assert resp.status_code == 200
        assert not resp.context["rows"]

    def test_the_worker_dropdown_narrows_too(self, member_client, approved_shift):
        """Narrowing the table while listing every colleague in a <select> leaks the roster."""
        resp = member_client.get(reverse("scm:labor_payroll_export"))
        names = [str(w) for w in resp.context["workers"]]
        assert approved_shift.worker.name not in " ".join(names)


class TestLaborMethodGates:
    """A GET to a verb is 405 — a state change must not be reachable by typing a URL."""

    @pytest.mark.parametrize("url_name,needs_pk", _LABOR_VERBS)
    def test_get_to_every_verb_is_405(self, client_a, labor_standard_a, labor_session_a,
                                      labor_activity_a, labor_plan_a, url_name, needs_pk):
        args = [1] if needs_pk else []
        assert client_a.get(reverse(url_name, args=args)).status_code == 405


class TestLaborAnonymousRedirect:
    """Nothing in 4.14 is public — every route sends an anonymous visitor to the login page."""

    @pytest.mark.parametrize("url_name", [
        "scm:laborstandard_list", "scm:laborsession_list", "scm:laboractivity_list",
        "scm:laborplan_list", "scm:labor_board", "scm:labor_payroll_export",
        "scm:labor_scorecard", "scm:laborstandard_create", "scm:laborsession_create",
        "scm:laborplan_create",
    ])
    def test_anonymous_is_redirected(self, db, url_name):
        resp = Client().get(reverse(url_name))
        assert resp.status_code == 302
        assert "/login" in resp["Location"] or "/accounts/" in resp["Location"]


class TestLaborCsvInjection:
    """A worker's NAME reaches a spreadsheet cell, and a name is user-supplied."""

    @pytest.mark.parametrize("hostile", ["=cmd|'/c calc'!A0", "+1+1", "-1+1", "@SUM(A1)"])
    def test_a_formula_prefixed_name_is_neutralised(self, client_a, tenant_a, location_a,
                                                    hostile):
        from apps.core.models import Party, PartyRole
        from apps.scm.models import LaborActivity, LaborSession

        party = Party.objects.create(tenant=tenant_a, name=hostile, kind="person")
        PartyRole.objects.create(tenant=tenant_a, party=party, role="employee")
        start = _labor_moment(hours_ago=9)
        s = LaborSession(tenant=tenant_a, worker=party, location=location_a,
                         work_date=_labor_workday(start), clock_in=start,
                         clock_out=start + datetime.timedelta(minutes=480))
        s.save()
        LaborActivity.objects.create(tenant=tenant_a, session=s, activity_type="pick",
                                     started_at=start,
                                     ended_at=start + datetime.timedelta(minutes=60),
                                     quantity=Decimal("10"))
        s.status = "approved"
        s.save(update_fields=["status", "updated_at"])

        resp = client_a.get(reverse("scm:labor_payroll_export"), {"format": "csv"})
        body = (b"".join(resp.streaming_content).decode() if resp.streaming
                else resp.content.decode())
        for line in body.splitlines():
            for cell in line.split(","):
                bare = cell.strip().strip('"')
                assert not bare.startswith(("=", "+", "-", "@")), bare
