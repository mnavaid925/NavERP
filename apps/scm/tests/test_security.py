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
