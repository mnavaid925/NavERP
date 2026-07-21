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


# ================================================================================================
# SCM 4.3 Inventory Management
# ================================================================================================

# ================================================================ Mass-assignment exclusions
class TestInventoryMassAssignmentExclusions:
    def test_item_form_excludes_average_cost_and_system_fields(self):
        from apps.scm.forms import ItemForm
        form = ItemForm(tenant=None)
        for field in ("average_cost", "tenant", "created_at", "updated_at"):
            assert field not in form.fields

    def test_uom_form_excludes_system_fields(self):
        from apps.scm.forms import UOMForm
        form = UOMForm(tenant=None)
        assert "tenant" not in form.fields

    def test_location_form_excludes_system_fields(self):
        from apps.scm.forms import LocationForm
        form = LocationForm(tenant=None)
        assert "tenant" not in form.fields

    def test_lotserial_form_excludes_tenant(self):
        from apps.scm.forms import LotSerialForm
        form = LotSerialForm(tenant=None)
        assert "tenant" not in form.fields

    def test_stocktransfer_form_excludes_status_number_and_completed_at(self):
        from apps.scm.forms import StockTransferForm
        form = StockTransferForm(tenant=None)
        for field in ("status", "number", "completed_at", "tenant"):
            assert field not in form.fields

    def test_stocktransferline_form_excludes_transfer_fk(self):
        from apps.scm.forms import StockTransferLineForm
        form = StockTransferLineForm(tenant=None)
        assert "transfer" not in form.fields

    def test_stockadjustment_form_excludes_status_number_and_posted_at(self):
        from apps.scm.forms import StockAdjustmentForm
        form = StockAdjustmentForm(tenant=None)
        for field in ("status", "number", "posted_at", "tenant"):
            assert field not in form.fields

    def test_stockadjustmentline_form_excludes_adjustment_fk(self):
        from apps.scm.forms import StockAdjustmentLineForm
        form = StockAdjustmentLineForm(tenant=None)
        assert "adjustment" not in form.fields

    def test_reorderrule_form_excludes_tenant(self):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(tenant=None)
        assert "tenant" not in form.fields

    def test_itemcategory_form_excludes_tenant(self):
        from apps.scm.forms import ItemCategoryForm
        form = ItemCategoryForm(tenant=None)
        assert "tenant" not in form.fields


# ================================================================================================
# Priority regression 2: TenantUniqueMixin must make a duplicate a FORM ERROR, not an IntegrityError
# ================================================================================================
class TestTenantUniqueMixinRegression:
    def test_duplicate_sku_is_a_form_error_not_an_integrity_error(self, tenant_a, item_a):
        from apps.scm.forms import ItemForm
        data = {
            "sku": item_a.sku, "name": "Another widget", "category": "", "uom": "",
            "item_type": "stock", "tracking": "none", "costing_method": "weighted_avg",
            "standard_cost": "0", "reorder_point": "0", "description": "", "is_active": "on",
        }
        form = ItemForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert form.non_field_errors() or "sku" in form.errors

    def test_genuinely_new_sku_still_validates(self, tenant_a, item_a):
        from apps.scm.forms import ItemForm
        data = {
            "sku": "WIDGET-2", "name": "A second widget", "category": "", "uom": "",
            "item_type": "stock", "tracking": "none", "costing_method": "weighted_avg",
            "standard_cost": "0", "reorder_point": "0", "description": "", "is_active": "on",
        }
        form = ItemForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_duplicate_uom_code_is_a_form_error(self, tenant_a, uom_each_a):
        from apps.scm.forms import UOMForm
        data = {"code": uom_each_a.code, "name": "Duplicate each", "factor": "1", "is_active": "on"}
        form = UOMForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert form.non_field_errors() or "code" in form.errors

    def test_genuinely_new_uom_code_still_validates(self, tenant_a, uom_each_a):
        from apps.scm.forms import UOMForm
        data = {"code": "BOX", "name": "Box of 12", "factor": "12", "is_active": "on"}
        form = UOMForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_duplicate_location_code_is_a_form_error(self, tenant_a, location_a):
        from apps.scm.forms import LocationForm
        data = {"code": location_a.code, "name": "Duplicate WH1", "location_type": "warehouse",
                "parent": "", "is_active": "on"}
        form = LocationForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert form.non_field_errors() or "code" in form.errors

    def test_genuinely_new_location_code_still_validates(self, tenant_a, location_a):
        from apps.scm.forms import LocationForm
        data = {"code": "WH9", "name": "New Warehouse", "location_type": "warehouse",
                "parent": "", "is_active": "on"}
        form = LocationForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_duplicate_lot_number_same_item_is_a_form_error(self, tenant_a, item_lot_a, lot_a):
        from apps.scm.forms import LotSerialForm
        data = {"item": str(item_lot_a.pk), "kind": "lot", "number": lot_a.number,
                "expiry_date": "", "status": "available", "notes": ""}
        form = LotSerialForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert form.non_field_errors() or "number" in form.errors

    def test_genuinely_new_lot_number_still_validates(self, tenant_a, item_lot_a, lot_a):
        from apps.scm.forms import LotSerialForm
        data = {"item": str(item_lot_a.pk), "kind": "lot", "number": "LOT-0002",
                "expiry_date": "", "status": "available", "notes": ""}
        form = LotSerialForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_editing_the_same_item_with_its_own_sku_still_validates(self, tenant_a, item_a):
        """Excluding the instance itself from the uniqueness check — editing a record must not
        trip over its OWN unchanged sku."""
        from apps.scm.forms import ItemForm
        data = {
            "sku": item_a.sku, "name": item_a.name, "category": "", "uom": "",
            "item_type": "stock", "tracking": "none", "costing_method": "weighted_avg",
            "standard_cost": "0", "reorder_point": "0", "description": "", "is_active": "on",
        }
        form = ItemForm(data=data, instance=item_a, tenant=tenant_a)
        assert form.is_valid() is True


# ================================================================ Self-parent exclusion
class TestInventorySelfParentExclusion:
    def test_itemcategory_form_excludes_itself_from_parent_choices(self, tenant_a, category_a):
        from apps.scm.forms import ItemCategoryForm
        form = ItemCategoryForm(instance=category_a, tenant=tenant_a)
        pks = set(form.fields["parent"].queryset.values_list("pk", flat=True))
        assert category_a.pk not in pks

    def test_location_form_excludes_itself_from_parent_choices(self, tenant_a, location_a):
        from apps.scm.forms import LocationForm
        form = LocationForm(instance=location_a, tenant=tenant_a)
        pks = set(form.fields["parent"].queryset.values_list("pk", flat=True))
        assert location_a.pk not in pks


# ================================================================ StockTransferForm validation
class TestStockTransferFormValidation:
    def test_same_source_and_destination_is_invalid(self, tenant_a, location_a):
        from apps.scm.forms import StockTransferForm
        data = {"from_location": str(location_a.pk), "to_location": str(location_a.pk),
                "transfer_date": "2026-01-15", "notes": ""}
        form = StockTransferForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "to_location" in form.errors

    def test_different_locations_is_valid(self, tenant_a, location_a, location_a2):
        from apps.scm.forms import StockTransferForm
        data = {"from_location": str(location_a.pk), "to_location": str(location_a2.pk),
                "transfer_date": "2026-01-15", "notes": ""}
        form = StockTransferForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True


# ================================================================ Line formsets — lot/item mismatch
class TestStockTransferLineFormLotItemMismatch:
    def test_lot_belonging_to_a_different_item_is_invalid(self, tenant_a, item_a, item_lot_a, lot_a):
        from apps.scm.forms import StockTransferLineForm
        data = {"item": str(item_a.pk), "lot_serial": str(lot_a.pk), "quantity": "1"}
        form = StockTransferLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "lot_serial" in form.errors

    def test_lot_belonging_to_its_own_item_is_valid(self, tenant_a, item_lot_a, lot_a):
        from apps.scm.forms import StockTransferLineForm
        data = {"item": str(item_lot_a.pk), "lot_serial": str(lot_a.pk), "quantity": "1"}
        form = StockTransferLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True


class TestStockAdjustmentLineFormValidation:
    def test_lot_belonging_to_a_different_item_is_invalid(self, tenant_a, item_a, item_lot_a, lot_a):
        from apps.scm.forms import StockAdjustmentLineForm
        data = {"item": str(item_a.pk), "lot_serial": str(lot_a.pk),
                "quantity_delta": "1", "unit_cost": "1.00"}
        form = StockAdjustmentLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "lot_serial" in form.errors

    def test_zero_quantity_delta_is_invalid(self, tenant_a, item_a):
        from apps.scm.forms import StockAdjustmentLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "quantity_delta": "0", "unit_cost": "1.00"}
        form = StockAdjustmentLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "quantity_delta" in form.errors

    def test_nonzero_quantity_delta_is_valid(self, tenant_a, item_a):
        from apps.scm.forms import StockAdjustmentLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "quantity_delta": "-3", "unit_cost": "1.00"}
        form = StockAdjustmentLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_unit_cost_over_the_cap_is_invalid(self, tenant_a, item_a):
        """MaxValueValidator(999999.9999) — defence-in-depth against an absurd cost riding a
        member-drafted line straight into a tenant-admin's bulk post."""
        from apps.scm.forms import StockAdjustmentLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "quantity_delta": "1", "unit_cost": "9999999.9999"}
        form = StockAdjustmentLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "unit_cost" in form.errors


# ================================================================ StockAdjustmentForm 'other' reason
class TestStockAdjustmentFormOtherReason:
    def test_other_reason_without_notes_is_invalid(self, tenant_a, location_a):
        from apps.scm.forms import StockAdjustmentForm
        data = {"location": str(location_a.pk), "reason": "other",
                "adjustment_date": "2026-01-15", "notes": ""}
        form = StockAdjustmentForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "notes" in form.errors

    def test_other_reason_with_notes_is_valid(self, tenant_a, location_a):
        from apps.scm.forms import StockAdjustmentForm
        data = {"location": str(location_a.pk), "reason": "other",
                "adjustment_date": "2026-01-15", "notes": "Explained clearly."}
        form = StockAdjustmentForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_cycle_count_reason_does_not_require_notes(self, tenant_a, location_a):
        from apps.scm.forms import StockAdjustmentForm
        data = {"location": str(location_a.pk), "reason": "cycle_count",
                "adjustment_date": "2026-01-15", "notes": ""}
        form = StockAdjustmentForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True


# ================================================================ Formset default prefixes
class TestInventoryFormsetDefaultPrefixes:
    def test_stocktransferline_formset_prefix_is_lines(self, tenant_a, stock_transfer_a):
        from apps.scm.forms import StockTransferLineFormSet
        formset = StockTransferLineFormSet(instance=stock_transfer_a, form_kwargs={"tenant": tenant_a})
        assert formset.get_default_prefix() == "lines"

    def test_stockadjustmentline_formset_prefix_is_lines(self, tenant_a, stock_adjustment_a):
        from apps.scm.forms import StockAdjustmentLineFormSet
        formset = StockAdjustmentLineFormSet(instance=stock_adjustment_a, form_kwargs={"tenant": tenant_a})
        assert formset.get_default_prefix() == "lines"


# ================================================================ Cross-tenant form scoping
class TestInventoryCrossTenantFormScoping:
    def test_item_form_category_and_uom_exclude_other_tenant(self, tenant_a, category_b, uom_each_b):
        from apps.scm.forms import ItemForm
        form = ItemForm(tenant=tenant_a)
        cat_pks = set(form.fields["category"].queryset.values_list("pk", flat=True))
        uom_pks = set(form.fields["uom"].queryset.values_list("pk", flat=True))
        assert category_b.pk not in cat_pks
        assert uom_each_b.pk not in uom_pks

    def test_location_form_parent_excludes_other_tenant(self, tenant_a, location_b):
        from apps.scm.forms import LocationForm
        form = LocationForm(tenant=tenant_a)
        pks = set(form.fields["parent"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in pks

    def test_lotserial_form_item_excludes_other_tenant(self, tenant_a, item_b):
        from apps.scm.forms import LotSerialForm
        form = LotSerialForm(tenant=tenant_a)
        pks = set(form.fields["item"].queryset.values_list("pk", flat=True))
        assert item_b.pk not in pks

    def test_reorderrule_form_item_and_location_exclude_other_tenant(self, tenant_a, item_b, location_b):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(tenant=tenant_a)
        item_pks = set(form.fields["item"].queryset.values_list("pk", flat=True))
        loc_pks = set(form.fields["location"].queryset.values_list("pk", flat=True))
        assert item_b.pk not in item_pks
        assert location_b.pk not in loc_pks

    def test_stocktransfer_form_locations_exclude_other_tenant(self, tenant_a, location_b):
        from apps.scm.forms import StockTransferForm
        form = StockTransferForm(tenant=tenant_a)
        from_pks = set(form.fields["from_location"].queryset.values_list("pk", flat=True))
        to_pks = set(form.fields["to_location"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in from_pks
        assert location_b.pk not in to_pks

    def test_stockadjustment_form_location_excludes_other_tenant(self, tenant_a, location_b):
        from apps.scm.forms import StockAdjustmentForm
        form = StockAdjustmentForm(tenant=tenant_a)
        pks = set(form.fields["location"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in pks

    def test_stocktransferline_form_item_excludes_other_tenant(self, tenant_a, item_b):
        from apps.scm.forms import StockTransferLineForm
        form = StockTransferLineForm(tenant=tenant_a)
        pks = set(form.fields["item"].queryset.values_list("pk", flat=True))
        assert item_b.pk not in pks


# ================================================================================================
# SCM 4.4 Warehouse Management
# ================================================================================================

# ================================================================ Mass-assignment exclusions
class TestWarehouseMassAssignmentExclusions:
    def test_putawaytask_form_excludes_status_and_completed_at(self):
        from apps.scm.forms import PutawayTaskForm
        form = PutawayTaskForm(tenant=None)
        for field in ("status", "number", "completed_at", "tenant"):
            assert field not in form.fields

    def test_picktask_form_excludes_status_and_timestamps(self):
        from apps.scm.forms import PickTaskForm
        form = PickTaskForm(tenant=None)
        for field in ("status", "number", "picked_at", "packed_at", "tenant"):
            assert field not in form.fields

    def test_picktaskline_form_excludes_pick_task_fk(self):
        from apps.scm.forms import PickTaskLineForm
        form = PickTaskLineForm(tenant=None)
        assert "pick_task" not in form.fields

    def test_cyclecounttask_form_excludes_status_timestamps_and_adjustment(self):
        from apps.scm.forms import CycleCountTaskForm
        form = CycleCountTaskForm(tenant=None)
        for field in ("status", "number", "started_at", "counted_at", "reconciled_at",
                      "adjustment", "tenant"):
            assert field not in form.fields

    def test_cyclecounttaskline_form_excludes_expected_quantity_and_cycle_count_fk(self):
        """L20/L22: expected_quantity is snapshotted server-side — exposing it on the form would
        let a counter see (or type over) the figure the count exists to check them against."""
        from apps.scm.forms import CycleCountTaskLineForm
        form = CycleCountTaskLineForm(tenant=None)
        assert "expected_quantity" not in form.fields
        assert "cycle_count" not in form.fields

    def test_yardvisit_form_excludes_status_and_timeline_stamps(self):
        from apps.scm.forms import YardVisitForm
        form = YardVisitForm(tenant=None)
        for field in ("status", "number", "arrived_at", "docked_at", "departed_at", "tenant"):
            assert field not in form.fields


# ================================================================ PickTaskLineForm validation
class TestPickTaskLineFormValidation:
    def test_over_pick_is_invalid(self, tenant_a, item_a, location_a):
        from apps.scm.forms import PickTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "from_location": str(location_a.pk),
                "quantity_requested": "5", "quantity_picked": "6", "notes": ""}
        form = PickTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "quantity_picked" in form.errors

    def test_short_pick_is_valid(self, tenant_a, item_a, location_a):
        from apps.scm.forms import PickTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "from_location": str(location_a.pk),
                "quantity_requested": "5", "quantity_picked": "3", "notes": ""}
        form = PickTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_picked_equal_to_requested_is_valid(self, tenant_a, item_a, location_a):
        from apps.scm.forms import PickTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "from_location": str(location_a.pk),
                "quantity_requested": "5", "quantity_picked": "5", "notes": ""}
        form = PickTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_lot_belonging_to_a_different_item_is_invalid(
        self, tenant_a, item_a, item_lot_a, lot_a, location_a,
    ):
        from apps.scm.forms import PickTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": str(lot_a.pk), "from_location": str(location_a.pk),
                "quantity_requested": "5", "quantity_picked": "0", "notes": ""}
        form = PickTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "lot_serial" in form.errors

    def test_lot_belonging_to_its_own_item_is_valid(self, tenant_a, item_lot_a, lot_a, location_a):
        from apps.scm.forms import PickTaskLineForm
        data = {"item": str(item_lot_a.pk), "lot_serial": str(lot_a.pk), "from_location": str(location_a.pk),
                "quantity_requested": "5", "quantity_picked": "0", "notes": ""}
        form = PickTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True


# ================================================================ PutawayTaskForm validation
class TestPutawayTaskFormValidation:
    def test_same_source_and_destination_is_invalid(self, tenant_a, location_a, item_a):
        from apps.scm.forms import PutawayTaskForm
        data = {"goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
                "from_location": str(location_a.pk), "to_location": str(location_a.pk),
                "quantity": "5", "strategy": "directed", "assigned_to": "", "notes": ""}
        form = PutawayTaskForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "to_location" in form.errors

    def test_different_locations_is_valid(self, tenant_a, location_a, location_a2, item_a):
        from apps.scm.forms import PutawayTaskForm
        data = {"goods_receipt": "", "item": str(item_a.pk), "lot_serial": "",
                "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
                "quantity": "5", "strategy": "directed", "assigned_to": "", "notes": ""}
        form = PutawayTaskForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_lot_belonging_to_a_different_item_is_invalid(
        self, tenant_a, item_a, item_lot_a, lot_a, location_a, location_a2,
    ):
        from apps.scm.forms import PutawayTaskForm
        data = {"goods_receipt": "", "item": str(item_a.pk), "lot_serial": str(lot_a.pk),
                "from_location": str(location_a.pk), "to_location": str(location_a2.pk),
                "quantity": "5", "strategy": "directed", "assigned_to": "", "notes": ""}
        form = PutawayTaskForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "lot_serial" in form.errors


# ================================================================ PickTaskPackForm validation
class TestPickTaskPackFormValidation:
    def test_package_weight_over_max_digits_is_invalid(self):
        from apps.scm.forms import PickTaskPackForm
        form = PickTaskPackForm(data={"package_count": "1", "package_weight": "9999999999.999",
                                      "tracking_ref": ""})
        assert form.is_valid() is False
        assert "package_weight" in form.errors

    def test_reasonable_package_weight_is_valid(self):
        from apps.scm.forms import PickTaskPackForm
        form = PickTaskPackForm(data={"package_count": "2", "package_weight": "3.500",
                                      "tracking_ref": "TRK1"})
        assert form.is_valid() is True

    def test_negative_package_weight_is_invalid(self):
        from apps.scm.forms import PickTaskPackForm
        form = PickTaskPackForm(data={"package_count": "1", "package_weight": "-1.000", "tracking_ref": ""})
        assert form.is_valid() is False
        assert "package_weight" in form.errors

    def test_everything_blank_is_valid_all_fields_optional(self):
        from apps.scm.forms import PickTaskPackForm
        form = PickTaskPackForm(data={"package_count": "", "package_weight": "", "tracking_ref": ""})
        assert form.is_valid() is True


# ================================================================ CycleCountTaskLineForm validation
class TestCycleCountTaskLineFormValidation:
    def test_lot_belonging_to_a_different_item_is_invalid(self, tenant_a, item_a, item_lot_a, lot_a):
        from apps.scm.forms import CycleCountTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": str(lot_a.pk), "counted_quantity": "5", "notes": ""}
        form = CycleCountTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is False
        assert "lot_serial" in form.errors

    def test_lot_belonging_to_its_own_item_is_valid(self, tenant_a, item_lot_a, lot_a):
        from apps.scm.forms import CycleCountTaskLineForm
        data = {"item": str(item_lot_a.pk), "lot_serial": str(lot_a.pk), "counted_quantity": "5", "notes": ""}
        form = CycleCountTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True

    def test_blank_counted_quantity_is_valid_and_cleans_to_none(self, tenant_a, item_a):
        """Uncounted must stay distinguishable from counted-zero all the way through cleaning."""
        from apps.scm.forms import CycleCountTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "counted_quantity": "", "notes": ""}
        form = CycleCountTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True
        assert form.cleaned_data["counted_quantity"] is None

    def test_counted_zero_is_valid_and_distinct_from_blank(self, tenant_a, item_a):
        from apps.scm.forms import CycleCountTaskLineForm
        data = {"item": str(item_a.pk), "lot_serial": "", "counted_quantity": "0", "notes": ""}
        form = CycleCountTaskLineForm(data=data, tenant=tenant_a)
        assert form.is_valid() is True
        assert form.cleaned_data["counted_quantity"] == Decimal("0")


# ================================================================================================
# Priority regression 1b — the started-count composition freeze
# ================================================================================================
class TestCycleCountTaskLineFormSetLockGuard:
    """BaseCycleCountTaskLineFormSet, exercised directly (see apps/scm/forms/WarehouseManagement/
    CycleCountTasks.py). Once a count has started, the sheet's item list must be frozen — the
    counter can still fill in counted_quantity/notes, but can't add a row or swap a line's item."""

    def test_lock_sheet_disables_item_and_lot_fields_on_every_form(self, tenant_a, cyclecounttask_a):
        from apps.scm.forms import CycleCountTaskLineFormSet
        formset = CycleCountTaskLineFormSet(instance=cyclecounttask_a, form_kwargs={"tenant": tenant_a},
                                            lock_sheet=True)
        assert formset.extra == 0
        for form in formset.forms:
            assert form.fields["item"].disabled is True
            assert form.fields["lot_serial"].disabled is True

    def test_unlocked_formset_leaves_item_and_lot_fields_enabled(self, tenant_a, cyclecounttask_a):
        from apps.scm.forms import CycleCountTaskLineFormSet
        formset = CycleCountTaskLineFormSet(instance=cyclecounttask_a, form_kwargs={"tenant": tenant_a},
                                            lock_sheet=False)
        for form in formset.forms:
            assert form.fields["item"].disabled is False

    def test_a_hand_rolled_extra_row_is_rejected_when_locked(self, tenant_a, cyclecounttask_a, item_lot_a):
        from apps.scm.forms import CycleCountTaskLineFormSet
        line = cyclecounttask_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item": str(line.item_id), "lot_serial": "", "counted_quantity": "5", "notes": ""},
            {"id": "", "item": str(item_lot_a.pk), "lot_serial": "", "counted_quantity": "3", "notes": ""},
        ], initial=1)
        formset = CycleCountTaskLineFormSet(data=data, instance=cyclecounttask_a,
                                            form_kwargs={"tenant": tenant_a}, lock_sheet=True)
        assert formset.is_valid() is False

    def test_the_same_extra_row_is_accepted_when_not_locked(self, tenant_a, cyclecounttask_a, item_lot_a):
        from apps.scm.forms import CycleCountTaskLineFormSet
        line = cyclecounttask_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item": str(line.item_id), "lot_serial": "", "counted_quantity": "", "notes": ""},
            {"id": "", "item": str(item_lot_a.pk), "lot_serial": "", "counted_quantity": "", "notes": ""},
        ], initial=1)
        formset = CycleCountTaskLineFormSet(data=data, instance=cyclecounttask_a,
                                            form_kwargs={"tenant": tenant_a}, lock_sheet=False)
        assert formset.is_valid() is True

    def test_item_swap_on_an_existing_row_is_silently_ignored_when_locked(
        self, tenant_a, cyclecounttask_a, item_lot_a,
    ):
        """The disabled field discards the POSTed value and keeps the instance's own — so the
        crafted swap fails, but the legitimate counted_quantity on the SAME row still saves."""
        from apps.scm.forms import CycleCountTaskLineFormSet
        line = cyclecounttask_a.lines.first()
        original_item_id = line.item_id
        data = formset_data("lines", [
            {"id": line.pk, "item": str(item_lot_a.pk), "lot_serial": "", "counted_quantity": "9", "notes": ""},
        ], initial=1)
        formset = CycleCountTaskLineFormSet(data=data, instance=cyclecounttask_a,
                                            form_kwargs={"tenant": tenant_a}, lock_sheet=True)
        assert formset.is_valid() is True
        formset.save()
        line.refresh_from_db()
        assert line.item_id == original_item_id  # swap ignored
        assert line.counted_quantity == Decimal("9")  # the count itself still saved


# ================================================================ Cross-tenant form scoping
class TestWarehouseCrossTenantFormScoping:
    def test_putawaytask_form_locations_and_item_exclude_other_tenant(
        self, tenant_a, location_b, item_b,
    ):
        from apps.scm.forms import PutawayTaskForm
        form = PutawayTaskForm(tenant=tenant_a)
        from_pks = set(form.fields["from_location"].queryset.values_list("pk", flat=True))
        to_pks = set(form.fields["to_location"].queryset.values_list("pk", flat=True))
        item_pks = set(form.fields["item"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in from_pks
        assert location_b.pk not in to_pks
        assert item_b.pk not in item_pks

    def test_picktaskline_form_item_and_location_exclude_other_tenant(self, tenant_a, item_b, location_b):
        from apps.scm.forms import PickTaskLineForm
        form = PickTaskLineForm(tenant=tenant_a)
        item_pks = set(form.fields["item"].queryset.values_list("pk", flat=True))
        loc_pks = set(form.fields["from_location"].queryset.values_list("pk", flat=True))
        assert item_b.pk not in item_pks
        assert location_b.pk not in loc_pks

    def test_cyclecounttask_form_location_excludes_other_tenant(self, tenant_a, location_b):
        from apps.scm.forms import CycleCountTaskForm
        form = CycleCountTaskForm(tenant=tenant_a)
        pks = set(form.fields["location"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in pks

    def test_yardvisit_form_dock_door_and_purchase_order_exclude_other_tenant(
        self, tenant_a, location_b, purchase_order_b,
    ):
        from apps.scm.forms import YardVisitForm
        form = YardVisitForm(tenant=tenant_a)
        door_pks = set(form.fields["dock_door"].queryset.values_list("pk", flat=True))
        po_pks = set(form.fields["purchase_order"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in door_pks
        assert purchase_order_b.pk not in po_pks


# ================================================================================================
# SCM 4.5 Order Management System
# ================================================================================================

# ================================================================ Mass-assignment exclusions (priority 6)
class TestSalesOrderMassAssignmentExclusions:
    def test_salesorder_form_excludes_workflow_and_system_fields(self):
        from apps.scm.forms import SalesOrderForm
        form = SalesOrderForm(tenant=None)
        for field in ("status", "number", "promised_date", "credit_hold", "fraud_flag", "hold_reason",
                     "confirmation_sent_at", "shipped_notification_at", "delivered_notification_at",
                     "invoice", "subtotal", "tax_total", "total", "source_quote", "tenant"):
            assert field not in form.fields

    def test_salesorderline_form_excludes_parent_fk(self):
        from apps.scm.forms import SalesOrderLineForm
        form = SalesOrderLineForm(tenant=None)
        assert "sales_order" not in form.fields

    def test_salesorderallocation_form_excludes_status_and_parent_fk(self):
        from apps.scm.forms import SalesOrderAllocationForm
        form = SalesOrderAllocationForm(tenant=None)
        assert "status" not in form.fields
        assert "sales_order_line" not in form.fields
        assert "tenant" not in form.fields
        assert "allocated_at" not in form.fields


# ================================================================================================
# Priority regression 1b — ship_to_address is actually usable on a NEW order
# ================================================================================================
class TestSalesOrderFormShipToAddressRegression:
    """`ship_to_address` used to be narrowed to the chosen customer's addresses, which made the
    field ALWAYS empty on create — no customer is chosen yet when a new-order form is first built.
    The guard is now `clean()`-based instead of queryset-based (frontend review)."""

    def test_a_new_order_offers_a_non_empty_ship_to_queryset(self, tenant_a, customer_a):
        from apps.core.models import Address
        from apps.scm.forms import SalesOrderForm
        Address.objects.create(tenant=tenant_a, party=customer_a, kind="shipping", line1="1 Main St",
                               city="Springfield")
        blank = SalesOrderForm(tenant=tenant_a)  # brand-new order, no instance, no customer chosen yet
        assert blank.fields["ship_to_address"].queryset.count() > 0

    def test_the_customers_own_address_validates(self, tenant_a, customer_a):
        from apps.core.models import Address
        from apps.scm.forms import SalesOrderForm
        addr = Address.objects.create(tenant=tenant_a, party=customer_a, kind="shipping", line1="1 Main St",
                                      city="Springfield")
        form = SalesOrderForm(
            {"customer": customer_a.pk, "ship_to_address": addr.pk, "source_channel": "manual",
             "order_date": "2026-01-05"}, tenant=tenant_a)
        assert form.is_valid() is True, form.errors

    def test_another_partys_address_is_rejected(self, tenant_a, customer_a):
        from apps.core.models import Address, Party, PartyRole
        from apps.scm.forms import SalesOrderForm
        other = Party.objects.create(tenant=tenant_a, name="Someone Else", kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=other, role="customer", status="active")
        other_addr = Address.objects.create(tenant=tenant_a, party=other, kind="shipping", line1="9 Wrong St",
                                            city="Shelbyville")
        form = SalesOrderForm(
            {"customer": customer_a.pk, "ship_to_address": other_addr.pk, "source_channel": "manual",
             "order_date": "2026-01-05"}, tenant=tenant_a)
        assert form.is_valid() is False
        assert "ship_to_address" in form.errors


# ================================================================ SalesOrderAllocationForm location scoping
class TestSalesOrderAllocationFormLocationScoping:
    def test_rejects_a_non_pickable_location(self, tenant_a, location_a):
        from apps.scm.forms import SalesOrderAllocationForm
        location_a.is_pickable = False
        location_a.save(update_fields=["is_pickable"])
        form = SalesOrderAllocationForm(data={"location": str(location_a.pk), "quantity": "1", "notes": ""},
                                        tenant=tenant_a)
        assert form.is_valid() is False
        assert "location" in form.errors

    def test_accepts_a_pickable_location(self, tenant_a, location_a):
        from apps.scm.forms import SalesOrderAllocationForm
        form = SalesOrderAllocationForm(data={"location": str(location_a.pk), "quantity": "1", "notes": ""},
                                        tenant=tenant_a)
        assert form.is_valid() is True


# ================================================================================================
# BaseSalesOrderLineFormSet — refuses to un-order what is already allocated (priority 6)
# ================================================================================================
class TestSalesOrderLineFormSetDeleteGuard:
    def test_deleting_a_line_with_an_active_allocation_is_a_validation_error(
        self, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.forms import SalesOrderLineFormSet
        from apps.scm.models import SalesOrderAllocation, SalesOrderLine
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("4"))
        data = formset_data("lines", [
            {"id": line.pk, "item": str(line.item_id), "description": "", "quantity_ordered": line.quantity_ordered,
             "unit_price": line.unit_price, "discount_pct": "0", "tax_pct": "0", "DELETE": "on"},
        ], initial=1)
        formset = SalesOrderLineFormSet(data=data, instance=sales_order_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is False
        assert any("cannot be removed" in e for e in formset.non_form_errors())
        assert SalesOrderLine.objects.filter(pk=line.pk).exists()

    def test_deleting_a_line_with_no_allocations_is_allowed(self, tenant_a, sales_order_a):
        from apps.scm.forms import SalesOrderLineFormSet
        line = sales_order_a.lines.first()
        data = formset_data("lines", [
            {"id": line.pk, "item": str(line.item_id), "description": "", "quantity_ordered": line.quantity_ordered,
             "unit_price": line.unit_price, "discount_pct": "0", "tax_pct": "0", "DELETE": "on"},
        ], initial=1)
        formset = SalesOrderLineFormSet(data=data, instance=sales_order_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True

    def test_shrinking_quantity_below_allocated_is_a_validation_error(
        self, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.forms import SalesOrderLineFormSet
        from apps.scm.models import SalesOrderAllocation
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("7"))  # ordered 10
        data = formset_data("lines", [
            {"id": line.pk, "item": str(line.item_id), "description": "", "quantity_ordered": "5",  # < 7 allocated
             "unit_price": line.unit_price, "discount_pct": "0", "tax_pct": "0"},
        ], initial=1)
        formset = SalesOrderLineFormSet(data=data, instance=sales_order_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is False
        assert any("less than is already allocated" in e for e in formset.non_form_errors())

    def test_reducing_quantity_to_exactly_the_allocated_amount_is_allowed(
        self, tenant_a, sales_order_a, location_a,
    ):
        from apps.scm.forms import SalesOrderLineFormSet
        from apps.scm.models import SalesOrderAllocation
        line = sales_order_a.lines.first()
        SalesOrderAllocation.objects.create(tenant=tenant_a, sales_order_line=line, location=location_a,
                                            quantity=Decimal("7"))
        data = formset_data("lines", [
            {"id": line.pk, "item": str(line.item_id), "description": "", "quantity_ordered": "7",
             "unit_price": line.unit_price, "discount_pct": "0", "tax_pct": "0"},
        ], initial=1)
        formset = SalesOrderLineFormSet(data=data, instance=sales_order_a, form_kwargs={"tenant": tenant_a})
        assert formset.is_valid() is True


# ================================================================ Cross-tenant form scoping
class TestSalesOrderCrossTenantFormScoping:
    def test_customer_field_excludes_other_tenant(self, tenant_a, customer_b):
        from apps.scm.forms import SalesOrderForm
        form = SalesOrderForm(tenant=tenant_a)
        pks = set(form.fields["customer"].queryset.values_list("pk", flat=True))
        assert customer_b.pk not in pks

    def test_ship_to_address_field_excludes_other_tenant(self, tenant_a, tenant_b, customer_b):
        from apps.core.models import Address
        from apps.scm.forms import SalesOrderForm
        addr_b = Address.objects.create(tenant=tenant_b, party=customer_b, kind="shipping", line1="1 Globex Way")
        form = SalesOrderForm(tenant=tenant_a)
        pks = set(form.fields["ship_to_address"].queryset.values_list("pk", flat=True))
        assert addr_b.pk not in pks

    def test_salesorderline_form_item_field_excludes_other_tenant(self, tenant_a, item_b):
        from apps.scm.forms import SalesOrderLineForm
        form = SalesOrderLineForm(tenant=tenant_a)
        pks = set(form.fields["item"].queryset.values_list("pk", flat=True))
        assert item_b.pk not in pks

    def test_salesorderallocation_form_location_field_excludes_other_tenant(self, tenant_a, location_b):
        from apps.scm.forms import SalesOrderAllocationForm
        form = SalesOrderAllocationForm(tenant=tenant_a)
        pks = set(form.fields["location"].queryset.values_list("pk", flat=True))
        assert location_b.pk not in pks


# ================================================================================================
# SCM 4.6 Transportation Management System
# ================================================================================================

# ================================================================ Mass-assignment exclusions
class TestTMSMassAssignmentExclusions:
    def test_carrier_form_excludes_number_and_derived_scorecard_fields(self):
        from apps.scm.forms import CarrierForm
        form = CarrierForm(tenant=None)
        for field in ("number", "on_time_delivery_pct", "performance_summary"):
            assert field not in form.fields

    def test_load_form_excludes_number_status_and_actual_timestamps(self):
        from apps.scm.forms import LoadForm
        form = LoadForm(tenant=None)
        for field in ("number", "status", "actual_departure", "actual_arrival"):
            assert field not in form.fields

    def test_shipment_form_excludes_number_status_and_tracking_derived_fields(self):
        from apps.scm.forms import ShipmentForm
        form = ShipmentForm(tenant=None)
        for field in ("number", "status", "actual_pickup_at", "actual_delivery_at",
                     "current_status_text", "last_known_location", "eta",
                     "pod_received", "pod_received_at"):
            assert field not in form.fields

    def test_trackingevent_form_excludes_shipment_and_recorded_by(self):
        from apps.scm.forms import TrackingEventForm
        form = TrackingEventForm(tenant=None)
        assert "shipment" not in form.fields
        assert "recorded_by" not in form.fields

    def test_freightinvoice_form_excludes_number_derived_amounts_and_approval_fields(self):
        from apps.scm.forms import FreightInvoiceForm
        form = FreightInvoiceForm(tenant=None)
        for field in ("number", "billed_amount", "contract_amount", "variance_amount", "variance_pct",
                     "match_status", "approval_status", "dispute_reason", "approved_by",
                     "approved_at", "bill"):
            assert field not in form.fields


# ================================================================ Carrier party scoping (_carrier_parties)
class TestCarrierPartyScoping:
    def test_carrier_parties_accepts_supplier_and_vendor_roles(self, tenant_a, supplier_a, vendor_a):
        from apps.scm.forms._common import _carrier_parties
        pks = set(_carrier_parties(tenant_a).values_list("pk", flat=True))
        assert supplier_a.pk in pks
        assert vendor_a.pk in pks

    def test_carrier_parties_excludes_a_customer_only_party(self, tenant_a, non_supplier_party_a):
        from apps.scm.forms._common import _carrier_parties
        pks = set(_carrier_parties(tenant_a).values_list("pk", flat=True))
        assert non_supplier_party_a.pk not in pks

    def test_carrier_parties_none_tenant_returns_empty(self):
        from apps.scm.forms._common import _carrier_parties
        assert _carrier_parties(None).count() == 0

    def test_carrierform_party_field_uses_carrier_parties_scoping(
        self, tenant_a, carrier_party_a, non_supplier_party_a,
    ):
        from apps.scm.forms import CarrierForm
        form = CarrierForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert carrier_party_a.pk in pks
        assert non_supplier_party_a.pk not in pks


# ================================================================ FreightInvoiceForm.clean() cross-check
class TestFreightInvoiceFormCarrierCrossCheck:
    """A freight invoice's linked load/shipment must have been executed by the SAME carrier being
    billed — a data-integrity guard added in the security review (an unassigned load/shipment is
    still allowed)."""

    def _base_data(self, carrier, **overrides):
        data = {
            "carrier": str(carrier.pk), "load": "", "shipment": "", "carrier_invoice_number": "",
            "invoice_date": "", "due_date": "", "currency": "", "match_tolerance_pct": "2.00",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_rejects_a_load_executed_by_a_different_carrier(self, tenant_a, carrier_a, carrier_party_a):
        from apps.core.models import Party, PartyRole
        from apps.scm.models import Carrier, Load
        other_party = Party.objects.create(tenant=tenant_a, name="Other Carrier Co", kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=other_party, role="vendor")
        other_carrier = Carrier.objects.create(tenant=tenant_a, party=other_party)
        load = Load.objects.create(tenant=tenant_a, carrier=other_carrier)

        from apps.scm.forms import FreightInvoiceForm
        form = FreightInvoiceForm(data=self._base_data(carrier_a, load=str(load.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "load" in form.errors

    def test_rejects_a_shipment_executed_by_a_different_carrier(self, tenant_a, carrier_a):
        from apps.core.models import Party, PartyRole
        from apps.scm.models import Carrier, Shipment
        other_party = Party.objects.create(tenant=tenant_a, name="Other Carrier Co 2", kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=other_party, role="vendor")
        other_carrier = Carrier.objects.create(tenant=tenant_a, party=other_party)
        shipment = Shipment.objects.create(tenant=tenant_a, carrier=other_carrier)

        from apps.scm.forms import FreightInvoiceForm
        form = FreightInvoiceForm(data=self._base_data(carrier_a, shipment=str(shipment.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "shipment" in form.errors

    def test_allows_a_load_with_no_carrier_assigned_yet(self, tenant_a, carrier_a):
        from apps.scm.models import Load
        load = Load.objects.create(tenant=tenant_a)  # unassigned
        from apps.scm.forms import FreightInvoiceForm
        form = FreightInvoiceForm(data=self._base_data(carrier_a, load=str(load.pk)), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_allows_a_load_executed_by_the_same_carrier(self, tenant_a, carrier_a, load_a):
        from apps.scm.forms import FreightInvoiceForm
        form = FreightInvoiceForm(data=self._base_data(carrier_a, load=str(load_a.pk)), tenant=tenant_a)
        assert form.is_valid(), form.errors


# ================================================================ Cross-tenant FORM binding
class TestTMSCrossTenantFormScoping:
    def test_carrierform_party_field_excludes_other_tenant(self, tenant_a, carrier_party_b):
        from apps.scm.forms import CarrierForm
        form = CarrierForm(tenant=tenant_a)
        pks = set(form.fields["party"].queryset.values_list("pk", flat=True))
        assert carrier_party_b.pk not in pks

    def test_loadform_carrier_field_excludes_other_tenant(self, tenant_a, carrier_b):
        from apps.scm.forms import LoadForm
        form = LoadForm(tenant=tenant_a)
        pks = set(form.fields["carrier"].queryset.values_list("pk", flat=True))
        assert carrier_b.pk not in pks

    def test_shipmentform_carrier_field_excludes_other_tenant(self, tenant_a, carrier_b):
        from apps.scm.forms import ShipmentForm
        form = ShipmentForm(tenant=tenant_a)
        pks = set(form.fields["carrier"].queryset.values_list("pk", flat=True))
        assert carrier_b.pk not in pks

    def test_freightinvoiceform_carrier_field_excludes_other_tenant(self, tenant_a, carrier_b):
        from apps.scm.forms import FreightInvoiceForm
        form = FreightInvoiceForm(tenant=tenant_a)
        pks = set(form.fields["carrier"].queryset.values_list("pk", flat=True))
        assert carrier_b.pk not in pks

    def test_crafted_carrier_post_with_other_tenant_party_is_rejected(self, tenant_a, carrier_party_b):
        from apps.scm.forms import CarrierForm
        form = CarrierForm(data={
            "party": str(carrier_party_b.pk), "carrier_type": "asset_based", "primary_mode": "truckload",
            "service_level": "standard", "status": "active",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "party" in form.errors
