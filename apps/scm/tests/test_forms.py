"""Form tests for the SCM 4.1 Procurement Management sub-module.

Covers:
- Mass-assignment guards: status / number / version / totals / secret-ish system fields
  are never ModelForm fields.
- Supplier scoping (_supplier_parties accepts BOTH the 'supplier' and 'vendor' PartyRole
  spellings; excludes parties with neither).
- The two formset DELETE guards that are this module's freshest regressions:
  BasePurchaseOrderLineFormSet (blocks deleting a received line) and BaseRFQLineFormSet
  (blocks deleting a quoted line).
- GoodsReceiptNoteForm's bill-vs-PO-vendor match guard.
"""
import datetime
from decimal import Decimal

import pytest

from apps.scm.tests._helpers import formset_data

pytestmark = pytest.mark.django_db


# ================================================================ Mass-assignment exclusions
class TestMassAssignmentExclusions:
    def test_requisition_form_excludes_system_fields(self):
        from apps.scm.forms import PurchaseRequisitionForm
        form = PurchaseRequisitionForm(tenant=None)
        for field in ("status", "requester", "estimated_total", "number", "approved_by",
                     "approved_at", "decision_note"):
            assert field not in form.fields

    def test_requisition_line_form_excludes_line_total(self):
        from apps.scm.forms import PurchaseRequisitionLineForm
        form = PurchaseRequisitionLineForm(tenant=None)
        assert "line_total" not in form.fields
        assert "requisition" not in form.fields

    def test_rfq_form_excludes_status(self):
        from apps.scm.forms import RFQForm
        form = RFQForm(tenant=None)
        assert "status" not in form.fields
        assert "number" not in form.fields

    def test_rfq_quote_form_excludes_status_and_total(self):
        from apps.scm.forms import RFQQuoteForm
        form = RFQQuoteForm(tenant=None)
        assert "status" not in form.fields
        assert "total" not in form.fields
        assert "number" not in form.fields
        assert "rfq" not in form.fields  # set by the view, not the form

    def test_purchaseorder_form_excludes_status_version_totals(self):
        from apps.scm.forms import PurchaseOrderForm
        form = PurchaseOrderForm(tenant=None)
        for field in ("status", "version", "amendment_reason", "subtotal", "tax_total", "total",
                     "number", "approved_by", "approved_at", "acknowledged_at",
                     "acknowledgement_note", "promised_ship_date", "cancelled_at",
                     "cancellation_reason"):
            assert field not in form.fields

    def test_purchaseorderline_form_excludes_line_total(self):
        from apps.scm.forms import PurchaseOrderLineForm
        form = PurchaseOrderLineForm(tenant=None)
        assert "line_total" not in form.fields
        assert "purchase_order" not in form.fields

    def test_goodsreceiptnote_form_excludes_status_and_match_fields(self):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(tenant=None)
        for field in ("status", "match_status", "match_notes", "received_by", "number"):
            assert field not in form.fields

    def test_goodsreceiptline_form_excludes_goods_receipt(self):
        from apps.scm.forms import GoodsReceiptLineForm
        form = GoodsReceiptLineForm(tenant=None)
        assert "goods_receipt" not in form.fields


# ================================================================ Supplier scoping
class TestSupplierScoping:
    def test_supplier_parties_accepts_both_supplier_and_vendor_roles(
        self, tenant_a, supplier_a, vendor_a,
    ):
        from apps.scm.forms._common import _supplier_parties
        pks = set(_supplier_parties(tenant_a).values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert vendor_a.pk in pks

    def test_supplier_parties_excludes_non_buy_from_parties(self, tenant_a, non_supplier_party_a):
        from apps.scm.forms._common import _supplier_parties
        pks = set(_supplier_parties(tenant_a).values_list("pk", flat=True))
        assert non_supplier_party_a.pk not in pks

    def test_supplier_parties_none_tenant_returns_empty(self):
        from apps.scm.forms._common import _supplier_parties
        assert _supplier_parties(None).count() == 0

    def test_purchaseorder_form_vendor_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import PurchaseOrderForm
        form = PurchaseOrderForm(tenant=tenant_a)
        pks = set(form.fields["vendor"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks

    def test_rfqvendor_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import RFQVendorForm
        form = RFQVendorForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks


# ================================================================ Formset DELETE guards (regressions)
class TestPurchaseOrderLineFormSetDeleteGuard:
    """BasePurchaseOrderLineFormSet must refuse — not 500 — deleting a line with receipts."""

    def test_deleting_received_line_is_a_validation_error_not_a_crash(
        self, tenant_a, purchase_order_a,
    ):
        from apps.scm.forms import PurchaseOrderLineFormSet
        from apps.scm.models import GoodsReceiptNote, GoodsReceiptLine, PurchaseOrderLine

        line = purchase_order_a.lines.first()
        grn = GoodsReceiptNote.objects.create(
            tenant=tenant_a, purchase_order=purchase_order_a,
            receipt_date=datetime.date(2026, 1, 10), status="received",
        )
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line, quantity_received=line.quantity)

        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "unit_price": line.unit_price,
             "tax_rate_pct": "0", "gl_account": "", "DELETE": "on"},
        ], initial=1)
        formset = PurchaseOrderLineFormSet(data=data, instance=purchase_order_a, form_kwargs={"tenant": tenant_a})

        assert formset.is_valid() is False  # NOT a 500/ProtectedError — a clean form error
        assert any("cannot be removed" in e for e in formset.non_form_errors())
        # The line survives — the guard never called .save()/.delete().
        assert PurchaseOrderLine.objects.filter(pk=line.pk).exists()

    def test_deleting_a_line_with_no_receipts_is_allowed(self, tenant_a, purchase_order_a):
        from apps.scm.forms import PurchaseOrderLineFormSet
        line = purchase_order_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "unit_price": line.unit_price,
             "tax_rate_pct": "0", "gl_account": "", "DELETE": "on"},
        ], initial=1)
        formset = PurchaseOrderLineFormSet(data=data, instance=purchase_order_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True


class TestRFQLineFormSetDeleteGuard:
    """BaseRFQLineFormSet must refuse to delete a line a supplier already quoted."""

    def test_deleting_quoted_line_is_a_validation_error(self, tenant_a, rfq_sent_a, quote_a):
        from apps.scm.forms import RFQLineFormSet
        from apps.scm.models import RFQQuoteLine

        line = rfq_sent_a.lines.first()
        quote_line = quote_a.lines.get(rfq_line=line)

        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "specification": "", "DELETE": "on"},
        ], initial=1)
        formset = RFQLineFormSet(data=data, instance=rfq_sent_a, form_kwargs={"tenant": tenant_a})

        assert formset.is_valid() is False
        assert any("cannot be removed" in e for e in formset.non_form_errors())
        # The supplier's quote line survives — never CASCADE-deleted by an invalid formset.
        assert RFQQuoteLine.objects.filter(pk=quote_line.pk).exists()

    def test_deleting_an_unquoted_line_is_allowed(self, tenant_a, rfq_a):
        from apps.scm.forms import RFQLineFormSet
        line = rfq_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item_description": line.item_description, "sku_hint": "",
             "uom_hint": "", "quantity": line.quantity, "specification": "", "DELETE": "on"},
        ], initial=1)
        formset = RFQLineFormSet(data=data, instance=rfq_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True


# ================================================================ GoodsReceiptNoteForm vendor/bill guard
class TestGoodsReceiptNoteFormVendorMatch:
    def test_bill_from_a_different_vendor_is_rejected(
        self, tenant_a, purchase_order_a, vendor_a, usd,
    ):
        from apps.accounting.models import Bill
        from apps.scm.forms import GoodsReceiptNoteForm

        other_bill = Bill.objects.create(
            tenant=tenant_a, party=vendor_a, bill_date=datetime.date(2026, 1, 12),
            status="approved", currency=usd,
        )
        form = GoodsReceiptNoteForm(
            data={
                "purchase_order": purchase_order_a.pk,
                "receipt_date": "2026-01-15",
                "delivery_note_ref": "",
                "bill": other_bill.pk,
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is False
        assert "bill" in form.errors

    def test_bill_from_the_same_vendor_is_accepted(self, tenant_a, purchase_order_a, bill_a):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(
            data={
                "purchase_order": purchase_order_a.pk,
                "receipt_date": "2026-01-15",
                "delivery_note_ref": "",
                "bill": bill_a.pk,
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True

    def test_no_bill_is_accepted(self, tenant_a, purchase_order_a):
        from apps.scm.forms import GoodsReceiptNoteForm
        form = GoodsReceiptNoteForm(
            data={
                "purchase_order": purchase_order_a.pk,
                "receipt_date": "2026-01-15",
                "delivery_note_ref": "",
                "bill": "",
                "notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True


# ================================================================================================
# SCM 4.2 Supplier Relationship Management
# ================================================================================================

# ================================================================ Mass-assignment exclusions
class TestSRMMassAssignmentExclusions:
    def test_supplierprofile_form_excludes_workflow_and_system_fields(self):
        from apps.scm.forms import SupplierProfileForm
        form = SupplierProfileForm(tenant=None)
        for field in ("onboarding_status", "approved_by", "approved_at", "decision_note"):
            assert field not in form.fields

    def test_scorecard_form_excludes_status_number_and_derived_fields(self):
        from apps.scm.forms import SupplierScorecardForm
        form = SupplierScorecardForm(tenant=None)
        for field in ("status", "number", "overall_score", "grade", "signal_summary"):
            assert field not in form.fields

    def test_contract_form_excludes_status_number_and_termination_fields(self):
        from apps.scm.forms import SupplierContractForm
        form = SupplierContractForm(tenant=None)
        for field in ("status", "number", "terminated_at", "termination_reason"):
            assert field not in form.fields

    def test_catalog_form_excludes_status_and_number(self):
        from apps.scm.forms import SupplierCatalogForm
        form = SupplierCatalogForm(tenant=None)
        assert "status" not in form.fields
        assert "number" not in form.fields

    def test_catalog_item_form_excludes_catalog_fk(self):
        from apps.scm.forms import SupplierCatalogItemForm
        form = SupplierCatalogItemForm(tenant=None)
        assert "catalog" not in form.fields

    def test_riskassessment_form_excludes_status_derived_and_assessor_fields(self):
        from apps.scm.forms import SupplierRiskAssessmentForm
        form = SupplierRiskAssessmentForm(tenant=None)
        for field in ("status", "number", "risk_level", "risk_index", "assessed_by"):
            assert field not in form.fields


# ================================================================ Scorecard score cap (priority regression)
class TestScorecardFormScoreCap:
    """Regression: MaxValueValidator(100) must reject a hand-entered score over 100 at the
    ModelForm layer, not just the raw model — this is the surface an edit form ships through."""

    def _base_data(self, supplier_a):
        return {
            "party": str(supplier_a.pk),
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "delivery_score": "", "quality_score": "", "price_score": "", "responsiveness_score": "",
            "manual_override": "",
            "notes": "",
        }

    def test_delivery_score_of_150_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierScorecardForm
        data = self._base_data(supplier_a)
        data["delivery_score"] = "150"
        form = SupplierScorecardForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "delivery_score" in form.errors

    def test_quality_score_negative_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierScorecardForm
        data = self._base_data(supplier_a)
        data["quality_score"] = "-10"
        form = SupplierScorecardForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "quality_score" in form.errors

    def test_score_of_100_is_valid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierScorecardForm
        data = self._base_data(supplier_a)
        data["delivery_score"] = "100"
        form = SupplierScorecardForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_period_end_before_start_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierScorecardForm
        data = self._base_data(supplier_a)
        data["period_start"] = "2026-02-01"
        data["period_end"] = "2026-01-01"
        form = SupplierScorecardForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "period_end" in form.errors


# ================================================================ SRM supplier scoping
class TestSRMSupplierScoping:
    def test_supplierprofile_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import SupplierProfileForm
        form = SupplierProfileForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks

    def test_scorecard_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import SupplierScorecardForm
        form = SupplierScorecardForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks

    def test_contract_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import SupplierContractForm
        form = SupplierContractForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks

    def test_catalog_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import SupplierCatalogForm
        form = SupplierCatalogForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks

    def test_riskassessment_form_party_field_excludes_non_supplier(
        self, tenant_a, supplier_a, non_supplier_party_a,
    ):
        from apps.scm.forms import SupplierRiskAssessmentForm
        form = SupplierRiskAssessmentForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert non_supplier_party_a.pk not in pks


# ================================================================ Cross-tenant form scoping
class TestSRMCrossTenantFormScoping:
    def test_supplierprofile_form_party_field_excludes_other_tenant(self, tenant_a, supplier_b):
        from apps.scm.forms import SupplierProfileForm
        form = SupplierProfileForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert supplier_b.pk not in pks

    def test_contract_form_currency_is_global_not_tenant_scoped(self, tenant_a, usd):
        """Currency has no tenant FK — every tenant legitimately shares the same active list."""
        from apps.scm.forms import SupplierContractForm
        form = SupplierContractForm(tenant=tenant_a)
        pks = set(form.fields["currency"].queryset.values_list("pk", flat=True))
        assert usd.pk in pks


# ================================================================ SupplierProfileForm validation
class TestSupplierProfileForm:
    def test_valid_minimal_submission(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierProfileForm
        data = {
            "party": str(supplier_a.pk), "tier": "transactional", "category": "Office Supplies",
            "legal_name": "", "tax_registration": "", "website": "",
            "primary_contact_name": "", "primary_contact_email": "", "primary_contact_phone": "",
            "country": "", "year_established": "",
            "dd_financials_verified": "", "dd_compliance_verified": "", "dd_insurance_verified": "",
            "dd_quality_cert_verified": "", "dd_references_checked": "", "notes": "",
        }
        form = SupplierProfileForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_missing_party_is_invalid(self, tenant_a):
        from apps.scm.forms import SupplierProfileForm
        data = {"party": "", "tier": "transactional"}
        form = SupplierProfileForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "party" in form.errors


# ================================================================ SupplierContractForm validation
class TestSupplierContractForm:
    def test_end_date_before_start_date_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierContractForm
        data = {
            "party": str(supplier_a.pk), "title": "Bad dates", "contract_type": "purchase",
            "start_date": "2026-06-01", "end_date": "2026-01-01", "contract_value": "0",
            "currency": "", "payment_terms": "", "auto_renew": "", "renewal_notice_days": "30",
            "terms_summary": "", "document": "", "notes": "",
        }
        form = SupplierContractForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "end_date" in form.errors

    def test_negative_contract_value_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierContractForm
        data = {
            "party": str(supplier_a.pk), "title": "Negative value", "contract_type": "purchase",
            "start_date": "", "end_date": "", "contract_value": "-1.00",
            "currency": "", "payment_terms": "", "auto_renew": "", "renewal_notice_days": "30",
            "terms_summary": "", "document": "", "notes": "",
        }
        form = SupplierContractForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "contract_value" in form.errors


# ================================================================ SupplierCatalogForm + item formset
class TestSupplierCatalogFormAndFormset:
    def test_valid_from_after_valid_until_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierCatalogForm
        data = {
            "party": str(supplier_a.pk), "name": "Bad dates", "currency": "",
            "valid_from": "2026-06-01", "valid_until": "2026-01-01", "notes": "",
        }
        form = SupplierCatalogForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "valid_until" in form.errors

    def test_item_formset_default_prefix_is_items(self, tenant_a, catalog_a):
        """SupplierCatalogItem.catalog has related_name='items' — the inline formset's
        default prefix must be 'items' (BaseInlineFormSet derives it from the accessor)."""
        from apps.scm.forms import SupplierCatalogItemFormSet
        formset = SupplierCatalogItemFormSet(instance=catalog_a, form_kwargs={"tenant": tenant_a})
        assert formset.get_default_prefix() == "items"

    def test_item_formset_saves_new_rows_on_the_catalog(self, tenant_a, catalog_a):
        from apps.scm.forms import SupplierCatalogItemFormSet
        data = formset_data("items", [
            {"id": "", "item_name": "Widget", "sku": "W-1", "uom": "ea",
             "unit_price": "9.99", "lead_time_days": "5", "min_order_qty": "1", "is_active": "on"},
            {"id": "", "item_name": "Gadget", "sku": "G-1", "uom": "ea",
             "unit_price": "19.99", "lead_time_days": "", "min_order_qty": "1", "is_active": "on"},
        ])
        formset = SupplierCatalogItemFormSet(data=data, instance=catalog_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True
        formset.save()
        assert catalog_a.items.count() == 2
        assert set(catalog_a.items.values_list("item_name", flat=True)) == {"Widget", "Gadget"}

    def test_item_formset_negative_unit_price_is_invalid(self, tenant_a, catalog_a):
        from apps.scm.forms import SupplierCatalogItemFormSet
        data = formset_data("items", [
            {"id": "", "item_name": "Bad price", "sku": "", "uom": "",
             "unit_price": "-5.00", "lead_time_days": "", "min_order_qty": "1", "is_active": "on"},
        ])
        formset = SupplierCatalogItemFormSet(data=data, instance=catalog_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is False


# ================================================================ SupplierRiskAssessmentForm validation
class TestSupplierRiskAssessmentForm:
    def test_valid_minimal_submission(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierRiskAssessmentForm
        data = {
            "party": str(supplier_a.pk), "assessment_date": "2026-01-01",
            "financial_score": "3", "geopolitical_score": "2", "compliance_score": "1",
            "operational_score": "4", "mitigation_plan": "", "next_review_date": "", "notes": "",
        }
        form = SupplierRiskAssessmentForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_score_out_of_1_to_5_range_is_invalid(self, tenant_a, supplier_a):
        from apps.scm.forms import SupplierRiskAssessmentForm
        data = {
            "party": str(supplier_a.pk), "assessment_date": "2026-01-01",
            "financial_score": "9", "geopolitical_score": "2", "compliance_score": "1",
            "operational_score": "4", "mitigation_plan": "", "next_review_date": "", "notes": "",
        }
        form = SupplierRiskAssessmentForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "financial_score" in form.errors
