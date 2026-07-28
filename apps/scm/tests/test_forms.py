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


# ================================================================================================
# SCM 4.7 Demand Planning & Forecasting
# ================================================================================================

# ================================================================ Mass-assignment exclusions
class TestDemandPlanningMassAssignmentExclusions:
    def test_demandforecast_form_excludes_every_system_field(self):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(tenant=None)
        for field in ("number", "status", "selected_method", "revision", "supersedes",
                      "generated_at", "approved_by", "approved_at", "tenant"):
            assert field not in form.fields, field

    def test_demandforecast_period_form_excludes_the_derived_columns(self):
        from apps.scm.forms import DemandForecastPeriodForm
        form = DemandForecastPeriodForm(tenant=None)
        for field in ("historical_quantity", "signal_adjustment_quantity", "consensus_quantity",
                      "forecast"):
            assert field not in form.fields, field

    def test_seasonalityprofile_form_excludes_number_and_the_derive_stamp(self):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(tenant=None)
        for field in ("number", "last_derived_at", "tenant"):
            assert field not in form.fields, field
        assert "derived_from_years" in form.fields  # an INPUT to derive, not a result of it

    def test_seasonalityindex_form_excludes_the_sample_size(self):
        from apps.scm.forms import SeasonalityIndexForm
        form = SeasonalityIndexForm(tenant=None)
        assert "sample_size" not in form.fields
        assert "profile" not in form.fields

    def test_demandsignal_form_excludes_the_triage_fields(self):
        from apps.scm.forms import DemandSignalForm
        form = DemandSignalForm(tenant=None)
        for field in ("number", "status", "applied_to_forecast", "reviewed_by", "reviewed_at",
                      "tenant"):
            assert field not in form.fields, field

    def test_forecastadjustment_form_excludes_the_review_gate_fields(self):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(tenant=None)
        for field in ("number", "status", "submitted_by", "resolved_quantity", "reviewed_by",
                      "reviewed_at", "review_note", "tenant"):
            assert field not in form.fields, field

    def test_reorderrule_form_excludes_the_seven_calculated_columns(self):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(tenant=None, is_tenant_admin=True)
        for field in ("avg_daily_demand", "demand_std_dev", "abc_class", "xyz_class",
                      "computed_safety_stock", "computed_reorder_point", "last_calculated_at"):
            assert field not in form.fields, field

    def test_reorderrule_form_still_offers_the_policy_inputs(self):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(tenant=None, is_tenant_admin=True)
        for field in ("safety_stock_method", "service_level_pct", "lead_time_days",
                      "lead_time_variability_days", "review_period_days", "seasonality_profile",
                      "demand_forecast"):
            assert field in form.fields, field


# ================================================================ DemandForecastForm.clean()
class TestDemandForecastFormValidation:
    def _payload(self, item, **overrides):
        from django.utils import timezone
        from apps.scm.tests._helpers import add_months, month_start
        start = month_start(timezone.localdate())
        data = {
            "name": "Widget plan", "item": str(item.pk), "location": "", "customer": "",
            "demand_source": "sales_orders", "bucket": "month",
            "horizon_start": start.isoformat(),
            "horizon_end": (add_months(start, 3) - datetime.timedelta(days=1)).isoformat(),
            "history_months": "24", "method": "moving_average", "method_parameter": "3",
            "seasonality_profile": "", "reference_item": "", "reference_scale_pct": "100",
            "exclude_outliers": "", "outlier_threshold_sigma": "3", "currency": "",
            "scenario": "baseline", "notes": "",
        }
        data.update(overrides)
        return data

    def test_a_valid_payload_is_accepted(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(self._payload(item_a), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_and_item_and_the_horizon_are_required(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm({}, tenant=tenant_a)
        assert not form.is_valid()
        for field in ("name", "item", "horizon_start", "horizon_end"):
            assert field in form.errors, field

    def test_a_horizon_that_ends_before_it_starts_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        from django.utils import timezone
        from apps.scm.tests._helpers import month_start
        start = month_start(timezone.localdate())
        form = DemandForecastForm(
            self._payload(item_a, horizon_start=start.isoformat(),
                          horizon_end=(start - datetime.timedelta(days=1)).isoformat()),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "horizon_end" in form.errors

    def test_a_horizon_beyond_the_period_cap_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        from apps.scm.models import DemandForecast
        form = DemandForecastForm(
            self._payload(item_a, bucket="day", horizon_start="2026-01-01",
                          horizon_end="2030-01-01"), tenant=tenant_a)
        assert not form.is_valid()
        assert str(DemandForecast.MAX_HORIZON_PERIODS) in str(form.errors["horizon_end"])

    def test_a_horizon_before_the_minimum_year_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(
            self._payload(item_a, horizon_start="1800-01-01", horizon_end="1800-06-30"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "horizon_start" in form.errors

    def test_a_like_item_forecast_without_a_reference_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(self._payload(item_a, method="like_item"), tenant=tenant_a)
        assert not form.is_valid()
        assert "reference_item" in form.errors

    def test_a_reference_item_pointing_at_itself_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(self._payload(item_a, reference_item=str(item_a.pk)),
                                  tenant=tenant_a)
        assert not form.is_valid()
        assert "reference_item" in form.errors

    def test_history_months_is_bounded(self, tenant_a, item_a):
        from apps.scm.forms import DemandForecastForm
        assert not DemandForecastForm(self._payload(item_a, history_months="0"),
                                      tenant=tenant_a).is_valid()
        assert not DemandForecastForm(self._payload(item_a, history_months="999"),
                                      tenant=tenant_a).is_valid()

    def test_the_customer_dropdown_only_offers_customer_parties(self, tenant_a, customer_a,
                                                                supplier_a):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(tenant=tenant_a)
        parties = list(form.fields["customer"].queryset)
        assert customer_a in parties
        assert supplier_a not in parties

    def test_the_currency_dropdown_only_offers_active_currencies(self, tenant_a, usd):
        from apps.accounting.models import Currency
        from apps.scm.forms import DemandForecastForm
        retired = Currency.objects.create(code="ZWD", name="Old Dollar", is_active=False)
        form = DemandForecastForm(tenant=tenant_a)
        currencies = list(form.fields["currency"].queryset)
        assert usd in currencies
        assert retired not in currencies

    def test_another_tenants_item_is_never_accepted(self, tenant_a, item_b):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(self._payload(item_b), tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_another_tenants_seasonality_profile_is_never_accepted(self, tenant_a, item_a,
                                                                    seasonality_profile_b):
        from apps.scm.forms import DemandForecastForm
        form = DemandForecastForm(
            self._payload(item_a, seasonality_profile=str(seasonality_profile_b.pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "seasonality_profile" in form.errors


# ================================================================ The period formset guard
class TestDemandForecastPeriodFormSetSequenceGuard:
    def test_reusing_an_existing_sequence_is_a_validation_error_not_an_integrityerror(
        self, forecast_with_periods_a,
    ):
        from apps.scm.forms import DemandForecastPeriodFormSet
        existing = forecast_with_periods_a.periods.first()
        data = formset_data("periods", [
            {"id": "", "sequence": str(existing.sequence),
             "period_start": existing.period_start.isoformat(),
             "period_end": existing.period_end.isoformat(), "period_label": "dupe",
             "baseline_quantity": "1", "seasonal_index_applied": "1",
             "event_uplift_quantity": "0", "final_quantity": "1", "unit_price": "0",
             "is_locked": ""},
        ])
        formset = DemandForecastPeriodFormSet(data, instance=forecast_with_periods_a,
                                              form_kwargs={"tenant": forecast_with_periods_a.tenant})
        assert not formset.is_valid()
        assert "sequence" in formset.forms[0].errors

    def test_editing_a_row_in_place_keeps_its_own_sequence(self, forecast_with_periods_a):
        from apps.scm.forms import DemandForecastPeriodFormSet
        existing = forecast_with_periods_a.periods.first()
        data = formset_data("periods", [
            {"id": str(existing.pk), "sequence": str(existing.sequence),
             "period_start": existing.period_start.isoformat(),
             "period_end": existing.period_end.isoformat(), "period_label": existing.period_label,
             "baseline_quantity": "111", "seasonal_index_applied": "1",
             "event_uplift_quantity": "0", "final_quantity": "111", "unit_price": "0",
             "is_locked": ""},
        ], initial=1)
        formset = DemandForecastPeriodFormSet(data, instance=forecast_with_periods_a,
                                              form_kwargs={"tenant": forecast_with_periods_a.tenant})
        assert formset.is_valid(), formset.errors

    def test_an_unsaved_parent_skips_the_cross_row_check(self, tenant_a):
        from apps.scm.forms import DemandForecastPeriodFormSet
        from apps.scm.models import DemandForecast
        formset = DemandForecastPeriodFormSet(formset_data("periods", []),
                                              instance=DemandForecast(),
                                              form_kwargs={"tenant": tenant_a})
        assert formset.is_valid()


# ================================================================ SeasonalityProfileForm.clean()
class TestSeasonalityProfileFormValidation:
    def _payload(self, **overrides):
        data = {
            "name": "Curve", "profile_type": "seasonal", "bucket": "month", "scope": "global",
            "item": "", "category": "", "location": "", "event_start": "", "event_end": "",
            "uplift_pct": "0", "cannibalization_pct": "0", "cannibalized_category": "",
            "promotion_mechanic": "", "derived_from_years": "2", "is_active": "on", "notes": "",
        }
        data.update(overrides)
        return data

    def test_a_valid_payload_is_accepted(self, tenant_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(self._payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_is_required(self, tenant_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(self._payload(name=""), tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_a_promotion_with_no_window_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(
            self._payload(profile_type="promotion", scope="item", item=str(item_a.pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "event_start" in form.errors

    def test_an_inverted_event_window_is_rejected(self, tenant_a, item_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(
            self._payload(profile_type="event", scope="item", item=str(item_a.pk),
                          event_start="2026-06-01", event_end="2026-05-01"), tenant=tenant_a)
        assert not form.is_valid()
        assert "event_end" in form.errors

    def test_an_item_scoped_profile_needs_an_item(self, tenant_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(self._payload(scope="item"), tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_a_category_scoped_profile_needs_a_category(self, tenant_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(self._payload(scope="category"), tenant=tenant_a)
        assert not form.is_valid()
        assert "category" in form.errors

    def test_a_location_scoped_profile_needs_a_location(self, tenant_a):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(self._payload(scope="location"), tenant=tenant_a)
        assert not form.is_valid()
        assert "location" in form.errors

    def test_derived_from_years_is_bounded(self, tenant_a):
        from apps.scm.forms import SeasonalityProfileForm
        assert not SeasonalityProfileForm(self._payload(derived_from_years="0"),
                                          tenant=tenant_a).is_valid()
        assert not SeasonalityProfileForm(self._payload(derived_from_years="50"),
                                          tenant=tenant_a).is_valid()

    def test_another_tenants_item_is_never_accepted(self, tenant_a, item_b):
        from apps.scm.forms import SeasonalityProfileForm
        form = SeasonalityProfileForm(self._payload(scope="item", item=str(item_b.pk)),
                                      tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_a_negative_index_factor_is_rejected(self, tenant_a):
        from apps.scm.forms import SeasonalityIndexForm
        form = SeasonalityIndexForm({"period_number": "1", "period_label": "",
                                     "index_factor": "-1"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "index_factor" in form.errors

    def test_an_out_of_range_period_number_is_rejected(self, tenant_a):
        from apps.scm.forms import SeasonalityIndexForm
        for value in ("0", "400"):
            form = SeasonalityIndexForm({"period_number": value, "period_label": "",
                                         "index_factor": "1"}, tenant=tenant_a)
            assert not form.is_valid(), value


# ================================================================ DemandSignalForm
class TestDemandSignalFormValidation:
    def _payload(self, **overrides):
        from django.utils import timezone
        data = {
            "signal_type": "order_surge", "source": "manual", "source_reference": "",
            "item": "", "category": "", "location": "", "customer": "",
            "observed_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "effective_from": "", "effective_to": "", "horizon_days": "28",
            "signal_value": "0", "baseline_value": "0", "impact_direction": "increase",
            "impact_pct": "0", "impact_quantity": "0", "confidence": "medium", "notes": "",
        }
        data.update(overrides)
        return data

    def test_a_valid_payload_is_accepted(self, tenant_a):
        from apps.scm.forms import DemandSignalForm
        form = DemandSignalForm(self._payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_observed_at_is_required(self, tenant_a):
        from apps.scm.forms import DemandSignalForm
        form = DemandSignalForm(self._payload(observed_at=""), tenant=tenant_a)
        assert not form.is_valid()
        assert "observed_at" in form.errors

    def test_an_inverted_effective_window_is_rejected(self, tenant_a):
        from apps.scm.forms import DemandSignalForm
        form = DemandSignalForm(self._payload(effective_from="2026-06-01",
                                              effective_to="2026-05-01"), tenant=tenant_a)
        assert not form.is_valid()
        assert "effective_to" in form.errors

    def test_horizon_days_is_bounded(self, tenant_a):
        from apps.scm.forms import DemandSignalForm
        assert not DemandSignalForm(self._payload(horizon_days="0"), tenant=tenant_a).is_valid()
        assert not DemandSignalForm(self._payload(horizon_days="999"), tenant=tenant_a).is_valid()

    def test_the_customer_dropdown_only_offers_customer_parties(self, tenant_a, customer_a,
                                                                supplier_a):
        from apps.scm.forms import DemandSignalForm
        parties = list(DemandSignalForm(tenant=tenant_a).fields["customer"].queryset)
        assert customer_a in parties and supplier_a not in parties

    def test_another_tenants_item_is_never_accepted(self, tenant_a, item_b):
        from apps.scm.forms import DemandSignalForm
        form = DemandSignalForm(self._payload(item=str(item_b.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors


# ================================================================ DemandSignalApplyForm scoping
class TestDemandSignalApplyFormScoping:
    def test_the_forecast_dropdown_is_scoped_to_the_adjustable_statuses(self, tenant_a,
                                                                        demand_signal_a,
                                                                        forecast_with_periods_a):
        from apps.scm.forms import DemandSignalApplyForm
        from apps.scm.models import DemandForecast
        draft = DemandForecast.objects.create(
            tenant=tenant_a, name="Still a draft", item=forecast_with_periods_a.item,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=forecast_with_periods_a.horizon_end)
        form = DemandSignalApplyForm(tenant=tenant_a, signal=demand_signal_a)
        offered = list(form.fields["forecast"].queryset)
        assert forecast_with_periods_a in offered  # statistical
        assert draft not in offered                # a draft has no grid to move

    def test_an_archived_forecast_is_not_offered(self, tenant_a, demand_signal_a,
                                                 forecast_with_periods_a):
        from apps.scm.forms import DemandSignalApplyForm
        forecast_with_periods_a.status = "archived"
        forecast_with_periods_a.save(update_fields=["status"])
        form = DemandSignalApplyForm(tenant=tenant_a, signal=demand_signal_a)
        assert forecast_with_periods_a not in list(form.fields["forecast"].queryset)

    def test_a_signal_naming_an_item_only_offers_that_items_forecasts(self, tenant_a, item_lot_a,
                                                                       demand_signal_a,
                                                                       forecast_with_periods_a):
        from apps.scm.forms import DemandSignalApplyForm
        from apps.scm.models import DemandForecast
        other = DemandForecast.objects.create(
            tenant=tenant_a, name="Other item", item=item_lot_a,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=forecast_with_periods_a.horizon_end, status="statistical")
        form = DemandSignalApplyForm(tenant=tenant_a, signal=demand_signal_a)
        offered = list(form.fields["forecast"].queryset)
        assert forecast_with_periods_a in offered
        assert other not in offered  # A's units must never be written into B's plan

    def test_a_network_wide_signal_is_deliberately_unnarrowed(self, tenant_a, item_lot_a,
                                                              forecast_with_periods_a):
        from django.utils import timezone
        from apps.scm.forms import DemandSignalApplyForm
        from apps.scm.models import DemandSignal
        signal = DemandSignal.objects.create(tenant=tenant_a, observed_at=timezone.now())
        form = DemandSignalApplyForm(tenant=tenant_a, signal=signal)
        assert forecast_with_periods_a in list(form.fields["forecast"].queryset)

    def test_another_tenants_forecast_is_never_offered_or_accepted(self, tenant_a, demand_signal_a,
                                                                    forecast_with_periods_b):
        from apps.scm.forms import DemandSignalApplyForm
        form = DemandSignalApplyForm({"forecast": str(forecast_with_periods_b.pk)},
                                     tenant=tenant_a, signal=demand_signal_a)
        assert not form.is_valid()
        assert "forecast" in form.errors

    def test_a_tenant_less_form_offers_nothing(self, demand_signal_a):
        from apps.scm.forms import DemandSignalApplyForm
        form = DemandSignalApplyForm(tenant=None, signal=demand_signal_a)
        assert list(form.fields["forecast"].queryset) == []

    def test_the_forecast_is_required(self, tenant_a, demand_signal_a):
        from apps.scm.forms import DemandSignalApplyForm
        form = DemandSignalApplyForm({}, tenant=tenant_a, signal=demand_signal_a)
        assert not form.is_valid()
        assert "forecast" in form.errors


# ================================================================ ForecastAdjustmentForm
class TestForecastAdjustmentFormValidation:
    def _payload(self, forecast, **overrides):
        data = {
            "forecast": str(forecast.pk), "period": "", "contributor_function": "sales",
            "org_unit": "", "adjustment_type": "absolute", "proposed_quantity": "140",
            "adjustment_pct": "0", "reason_code": "promotion",
            "rationale": "Spring campaign.", "confidence": "medium",
        }
        data.update(overrides)
        return data

    def test_a_valid_payload_is_accepted(self, tenant_a, forecast_with_periods_a):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(self._payload(forecast_with_periods_a), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_a_blank_rationale_is_rejected(self, tenant_a, forecast_with_periods_a):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(self._payload(forecast_with_periods_a, rationale="   "),
                                      tenant=tenant_a)
        assert not form.is_valid()
        assert "rationale" in form.errors

    def test_the_forecast_dropdown_is_scoped_to_the_adjustable_statuses(self, tenant_a,
                                                                        forecast_with_periods_a):
        from apps.scm.forms import ForecastAdjustmentForm
        from apps.scm.models import DemandForecast
        draft = DemandForecast.objects.create(
            tenant=tenant_a, name="Still a draft", item=forecast_with_periods_a.item,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=forecast_with_periods_a.horizon_end)
        offered = list(ForecastAdjustmentForm(tenant=tenant_a).fields["forecast"].queryset)
        assert forecast_with_periods_a in offered
        assert draft not in offered  # a draft has no grid for a delta to roll into

    def test_a_draft_forecast_is_refused_on_a_bound_form(self, tenant_a, demand_forecast_a):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(self._payload(demand_forecast_a), tenant=tenant_a)
        assert not form.is_valid()
        assert "forecast" in form.errors

    def test_the_period_dropdown_is_scoped_to_the_parent_forecast(self, tenant_a, item_a,
                                                                   forecast_with_periods_a):
        from apps.scm.forms import ForecastAdjustmentForm
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months
        other = DemandForecast.objects.create(
            tenant=tenant_a, name="Other", item=item_a,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=add_months(forecast_with_periods_a.horizon_start,
                                   3) - datetime.timedelta(days=1))
        other.generate_periods()
        form = ForecastAdjustmentForm(tenant=tenant_a, forecast=forecast_with_periods_a)
        offered = list(form.fields["period"].queryset)
        assert set(offered) == set(forecast_with_periods_a.periods.all())
        assert not any(row in offered for row in other.periods.all())

    def test_the_period_dropdown_is_empty_without_a_parent(self, tenant_a):
        from apps.scm.forms import ForecastAdjustmentForm
        assert list(ForecastAdjustmentForm(tenant=tenant_a).fields["period"].queryset) == []

    def test_a_bound_post_resolves_the_period_scope_from_its_own_forecast(
        self, tenant_a, forecast_with_periods_a, forecast_period_a,
    ):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(
            self._payload(forecast_with_periods_a, period=str(forecast_period_a.pk)),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["period"] == forecast_period_a

    def test_a_period_belonging_to_another_forecast_is_rejected(self, tenant_a, item_a,
                                                                forecast_with_periods_a):
        from apps.scm.forms import ForecastAdjustmentForm
        from apps.scm.models import DemandForecast
        from apps.scm.tests._helpers import add_months
        other = DemandForecast.objects.create(
            tenant=tenant_a, name="Other", item=item_a,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=add_months(forecast_with_periods_a.horizon_start,
                                   3) - datetime.timedelta(days=1))
        other.generate_periods()
        form = ForecastAdjustmentForm(
            self._payload(forecast_with_periods_a, period=str(other.periods.first().pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "period" in form.errors

    def test_another_tenants_forecast_is_never_accepted(self, tenant_a, forecast_with_periods_b):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(self._payload(forecast_with_periods_b), tenant=tenant_a)
        assert not form.is_valid()
        assert "forecast" in form.errors

    def test_another_tenants_period_is_never_accepted(self, tenant_a, forecast_with_periods_a,
                                                       forecast_with_periods_b):
        from apps.scm.forms import ForecastAdjustmentForm
        form = ForecastAdjustmentForm(
            self._payload(forecast_with_periods_a,
                          period=str(forecast_with_periods_b.periods.first().pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "period" in form.errors

    def test_a_tenant_less_form_offers_no_forecasts(self):
        from apps.scm.forms import ForecastAdjustmentForm
        assert list(ForecastAdjustmentForm(tenant=None).fields["forecast"].queryset) == []


# ================================================================================================
# ReorderRuleForm — the admin gate on the two columns that ARE the buying decision
# ================================================================================================
class TestReorderRuleFormAdminGate:
    def _payload(self, item, location, **overrides):
        data = {
            "item": str(item.pk), "location": str(location.pk), "reorder_point": "10",
            "safety_stock": "5", "reorder_quantity": "20", "is_active": "on",
            "safety_stock_method": "fixed", "service_level_pct": "95", "lead_time_days": "0",
            "lead_time_variability_days": "0", "review_period_days": "0",
            "seasonality_profile": "", "demand_forecast": "",
        }
        data.update(overrides)
        return data

    def test_a_non_admin_gets_the_two_live_columns_disabled(self, tenant_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(tenant=tenant_a, is_tenant_admin=False)
        for name in ReorderRuleForm.ADMIN_ONLY_FIELDS:
            assert form.fields[name].disabled is True, name

    def test_an_admin_keeps_them_editable(self, tenant_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(tenant=tenant_a, is_tenant_admin=True)
        for name in ReorderRuleForm.ADMIN_ONLY_FIELDS:
            assert form.fields[name].disabled is False, name

    def test_a_crafted_non_admin_post_cannot_write_the_live_columns(self, tenant_a,
                                                                     reorder_rule_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(
            self._payload(reorder_rule_a.item, reorder_rule_a.location,
                          safety_stock="99999", reorder_point="88888"),
            instance=reorder_rule_a, tenant=tenant_a, is_tenant_admin=False)
        assert form.is_valid(), form.errors
        rule = form.save()
        assert rule.safety_stock == Decimal("5.00")   # the instance's value stood
        assert rule.reorder_point == Decimal("10.00")

    def test_an_admin_post_does_write_them(self, tenant_a, reorder_rule_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(
            self._payload(reorder_rule_a.item, reorder_rule_a.location, safety_stock="42"),
            instance=reorder_rule_a, tenant=tenant_a, is_tenant_admin=True)
        assert form.is_valid(), form.errors
        assert form.save().safety_stock == Decimal("42")

    def test_a_non_admin_can_still_set_the_policy_inputs(self, tenant_a, reorder_rule_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(
            self._payload(reorder_rule_a.item, reorder_rule_a.location,
                          safety_stock_method="service_level", lead_time_days="14"),
            instance=reorder_rule_a, tenant=tenant_a, is_tenant_admin=False)
        assert form.is_valid(), form.errors
        rule = form.save()
        assert rule.safety_stock_method == "service_level"
        assert rule.lead_time_days == 14

    def test_the_demand_forecast_dropdown_is_narrowed_to_the_rules_own_item(
        self, tenant_a, item_lot_a, location_a, reorder_rule_a, forecast_with_periods_a,
    ):
        from apps.scm.forms import ReorderRuleForm
        from apps.scm.models import DemandForecast
        other = DemandForecast.objects.create(
            tenant=tenant_a, name="Other item plan", item=item_lot_a,
            horizon_start=forecast_with_periods_a.horizon_start,
            horizon_end=forecast_with_periods_a.horizon_end)
        form = ReorderRuleForm(instance=reorder_rule_a, tenant=tenant_a, is_tenant_admin=True)
        offered = list(form.fields["demand_forecast"].queryset)
        assert forecast_with_periods_a in offered  # same item as the rule
        assert other not in offered

    def test_another_tenants_forecast_is_never_accepted(self, tenant_a, reorder_rule_a,
                                                         forecast_with_periods_b):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(
            self._payload(reorder_rule_a.item, reorder_rule_a.location,
                          demand_forecast=str(forecast_with_periods_b.pk)),
            instance=reorder_rule_a, tenant=tenant_a, is_tenant_admin=True)
        assert not form.is_valid()
        assert "demand_forecast" in form.errors

    def test_another_tenants_seasonality_profile_is_never_accepted(self, tenant_a, reorder_rule_a,
                                                                    seasonality_profile_b):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(
            self._payload(reorder_rule_a.item, reorder_rule_a.location,
                          seasonality_profile=str(seasonality_profile_b.pk)),
            instance=reorder_rule_a, tenant=tenant_a, is_tenant_admin=True)
        assert not form.is_valid()
        assert "seasonality_profile" in form.errors

    def test_a_negative_service_level_is_rejected(self, tenant_a, item_a, location_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(self._payload(item_a, location_a, service_level_pct="-1"),
                               tenant=tenant_a, is_tenant_admin=True)
        assert not form.is_valid()
        assert "service_level_pct" in form.errors

    def test_a_service_level_above_100_is_rejected(self, tenant_a, item_a, location_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(self._payload(item_a, location_a, service_level_pct="150"),
                               tenant=tenant_a, is_tenant_admin=True)
        assert not form.is_valid()
        assert "service_level_pct" in form.errors

    def test_a_duplicate_item_location_pair_is_a_validation_error_not_a_500(self, tenant_a,
                                                                            reorder_rule_a):
        from apps.scm.forms import ReorderRuleForm
        form = ReorderRuleForm(self._payload(reorder_rule_a.item, reorder_rule_a.location),
                               tenant=tenant_a, is_tenant_admin=True)
        assert not form.is_valid()  # TenantUniqueMixin catches the unique_together


# ================================================================================================
# SCM 4.8 Manufacturing
# ================================================================================================

def _wo_payload(item, **overrides):
    data = {
        "item": str(item.pk), "uom": "", "bom": "", "quantity_planned": "5",
        "order_policy": "make_to_stock", "sales_order": "", "work_center": "",
        "priority": "normal", "planned_start": "", "planned_end": "",
        "schedule_direction": "forward", "due_date": "", "component_location": "",
        "output_location": "", "output_lot_serial": "", "notes": "",
    }
    data.update(overrides)
    return data


def _component_payload(item, **overrides):
    data = {
        "sequence": "10", "item": str(item.pk), "quantity_required": "4", "uom": "",
        "lot_serial": "", "issue_method": "manual", "unit_cost": "2.0000", "notes": "",
    }
    data.update(overrides)
    return data


def _work_centre_payload(**overrides):
    data = {
        "code": "WC-NEW", "name": "New Cell", "center_type": "machine", "location": "",
        "org_unit": "", "supervisor": "", "capacity_hours_per_day": "8", "efficiency_pct": "100",
        "setup_minutes": "0", "machine_cost_per_hour": "10", "labor_cost_per_hour": "20",
        "is_active": "on", "notes": "",
    }
    data.update(overrides)
    return data


def _time_log_payload(work_order, work_center, **overrides):
    from django.utils import timezone
    started = timezone.now() - datetime.timedelta(hours=2)
    data = {
        "work_order": str(work_order.pk), "work_center": str(work_center.pk),
        "operation": "Mill", "entry_type": "labor", "operator": "",
        "started_at": started.strftime("%Y-%m-%dT%H:%M"),
        "ended_at": (started + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "quantity_completed": "0", "quantity_scrapped": "0", "downtime_reason": "", "notes": "",
    }
    data.update(overrides)
    return data


# ================================================================ Mass-assignment exclusions
class TestManufacturingMassAssignmentExclusions:
    def test_workorder_form_excludes_every_single_writer_field(self):
        """status / quantity_produced / quantity_scrapped / produced_unit_cost / released_by are
        written ONLY by the lifecycle + posting actions. A form input for any of them would let a
        planner type a consumption or an output the stock ledger never saw."""
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(tenant=None)
        for field in ("number", "status", "actual_start", "actual_end", "quantity_produced",
                      "quantity_scrapped", "produced_unit_cost", "released_by", "tenant",
                      "created_at", "updated_at"):
            assert field not in form.fields, field

    def test_workorder_form_still_offers_the_planning_inputs(self):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(tenant=None)
        for field in ("item", "bom", "quantity_planned", "order_policy", "sales_order",
                      "work_center", "priority", "planned_start", "planned_end", "due_date",
                      "component_location", "output_location", "output_lot_serial"):
            assert field in form.fields, field

    def test_workordercomponent_form_excludes_the_issued_quantity(self):
        from apps.scm.forms import WorkOrderComponentForm
        form = WorkOrderComponentForm(tenant=None)
        assert "quantity_issued" not in form.fields
        assert "work_order" not in form.fields

    def test_productiontimelog_form_excludes_the_derived_duration(self):
        from apps.scm.forms import ProductionTimeLogForm
        form = ProductionTimeLogForm(tenant=None)
        for field in ("number", "duration_minutes", "tenant", "created_at", "updated_at"):
            assert field not in form.fields, field

    def test_workcenter_form_excludes_the_auto_number(self):
        from apps.scm.forms import WorkCenterForm
        form = WorkCenterForm(tenant=None)
        for field in ("number", "tenant", "created_at", "updated_at"):
            assert field not in form.fields, field

    def test_billofmaterials_form_excludes_the_auto_number_but_KEEPS_status(self):
        """A BOM's draft/active/obsolete progression is master-data curation, not a workflow that
        gates a stock posting — unlike WorkOrder.status it needs no transition actions."""
        from apps.scm.forms import BillOfMaterialsForm
        form = BillOfMaterialsForm(tenant=None)
        for field in ("number", "tenant", "created_at", "updated_at"):
            assert field not in form.fields, field
        assert "status" in form.fields
        assert "is_default" in form.fields

    def test_bomline_form_never_exposes_its_parent(self):
        from apps.scm.forms import BOMLineForm
        form = BOMLineForm(tenant=None)
        assert "bom" not in form.fields

    def test_a_crafted_status_in_the_post_body_cannot_move_a_run(self, tenant_a, work_order_a):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(work_order_a.item, status="completed",
                                         quantity_produced="99", produced_unit_cost="0.0001",
                                         released_by="1"),
                             instance=work_order_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.status == "draft"
        assert saved.quantity_produced == Decimal("0")
        assert saved.produced_unit_cost == Decimal("0")
        assert saved.released_by_id is None

    def test_a_crafted_quantity_issued_cannot_fake_a_consumption(self, tenant_a,
                                                                 stocked_work_order_a):
        from apps.scm.forms import WorkOrderComponentForm
        component = stocked_work_order_a.components.first()
        form = WorkOrderComponentForm(
            _component_payload(component.item, quantity_required="10", quantity_issued="10"),
            instance=component, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.save().quantity_issued == Decimal("0")

    def test_a_crafted_duration_cannot_inflate_the_booked_time(self, tenant_a, time_log_a,
                                                              released_work_order_a,
                                                              work_center_a):
        from apps.scm.forms import ProductionTimeLogForm
        form = ProductionTimeLogForm(
            _time_log_payload(released_work_order_a, work_center_a, duration_minutes="100000"),
            instance=time_log_a, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.save().duration_minutes == 60  # derived from the interval, not the POST


# ================================================================ Lot / item consistency
class TestManufacturingLotConsistency:
    def test_the_header_refuses_an_output_lot_belonging_to_another_item(self, tenant_a, item_a,
                                                                        lot_a, item_lot_a):
        """A crafted POST could pair item A with item B's lot, and report_production would write
        that into an APPEND-ONLY production move — permanently reporting A's units under B's lot."""
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_a, output_lot_serial=str(lot_a.pk)),
                             tenant=tenant_a)
        assert not form.is_valid()
        assert "output_lot_serial" in form.errors
        assert lot_a.number in str(form.errors["output_lot_serial"])

    def test_the_header_accepts_the_lot_that_belongs_to_its_own_item(self, tenant_a, item_lot_a,
                                                                     lot_a):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_lot_a, output_lot_serial=str(lot_a.pk)),
                             tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_a_component_line_refuses_a_lot_belonging_to_another_item(self, tenant_a,
                                                                      component_bolt_a, lot_a):
        from apps.scm.forms import WorkOrderComponentForm
        form = WorkOrderComponentForm(
            _component_payload(component_bolt_a, lot_serial=str(lot_a.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "lot_serial" in form.errors

    def test_a_component_line_accepts_its_own_items_lot(self, tenant_a, item_lot_a, lot_a):
        from apps.scm.forms import WorkOrderComponentForm
        form = WorkOrderComponentForm(
            _component_payload(item_lot_a, lot_serial=str(lot_a.pk)), tenant=tenant_a)
        assert form.is_valid(), form.errors


# ================================================================ WorkOrderForm dropdown scoping
class TestWorkOrderFormScoping:
    def test_the_bom_dropdown_is_narrowed_to_the_rows_own_item_on_edit(self, tenant_a,
                                                                       work_order_a, bom_a,
                                                                       bom_draft_a):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(instance=work_order_a, tenant=tenant_a)
        offered = set(form.fields["bom"].queryset)
        assert bom_a in offered
        assert bom_draft_a not in offered  # a different item's recipe

    def test_an_obsolete_bom_stays_selectable_on_the_row_that_already_uses_it(self, tenant_a,
                                                                              work_order_a,
                                                                              bom_a):
        """Otherwise the bound form fails validation on a field the user never touched."""
        from apps.scm.forms import WorkOrderForm
        bom_a.status = "obsolete"
        bom_a.save(update_fields=["status"])
        form = WorkOrderForm(instance=work_order_a, tenant=tenant_a)
        assert bom_a in set(form.fields["bom"].queryset)

    def test_the_create_form_offers_every_active_recipe(self, tenant_a, bom_a, bom_draft_a):
        """On create the item isn't known until the form binds, so WorkOrder.clean() is what
        actually refuses a BOM that produces a different item."""
        from apps.scm.forms import WorkOrderForm
        offered = set(WorkOrderForm(tenant=tenant_a).fields["bom"].queryset)
        assert bom_a in offered
        assert bom_draft_a not in offered  # draft, not active

    def test_the_clean_refuses_a_bom_that_makes_a_different_item(self, tenant_a, bom_a,
                                                                 item_lot_a):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_lot_a, bom=str(bom_a.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "bom" in form.errors

    def test_a_make_to_order_run_needs_its_sales_order(self, tenant_a, item_a):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_a, order_policy="make_to_order"), tenant=tenant_a)
        assert not form.is_valid()
        assert "sales_order" in form.errors


# ================================================================ WorkCenterForm
class TestWorkCenterFormValidation:
    def test_the_supervisor_dropdown_is_narrowed_to_employees(self, tenant_a, employee_party_a,
                                                              customer_a, supplier_a):
        from apps.scm.forms import WorkCenterForm
        offered = set(WorkCenterForm(tenant=tenant_a).fields["supervisor"].queryset)
        assert offered == {employee_party_a}

    def test_an_hourly_rate_over_the_ceiling_is_refused(self, tenant_a):
        """These rates flow into the unit_cost of a production StockMove, which rolls into the
        finished good's tenant-wide average_cost — an unbounded rate is a valuation-integrity
        hole, not a typo risk."""
        from apps.scm.forms import WorkCenterForm
        for field in ("machine_cost_per_hour", "labor_cost_per_hour"):
            form = WorkCenterForm(_work_centre_payload(**{field: "100001"}), tenant=tenant_a)
            assert not form.is_valid(), field
            assert field in form.errors, field

    def test_exactly_the_ceiling_is_accepted(self, tenant_a):
        from apps.scm.forms import WorkCenterForm
        form = WorkCenterForm(_work_centre_payload(machine_cost_per_hour="100000"),
                              tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_a_negative_rate_is_refused(self, tenant_a):
        from apps.scm.forms import WorkCenterForm
        form = WorkCenterForm(_work_centre_payload(labor_cost_per_hour="-1"), tenant=tenant_a)
        assert not form.is_valid()
        assert "labor_cost_per_hour" in form.errors

    def test_capacity_beyond_24_hours_a_day_is_refused(self, tenant_a):
        from apps.scm.forms import WorkCenterForm
        form = WorkCenterForm(_work_centre_payload(capacity_hours_per_day="25"), tenant=tenant_a)
        assert not form.is_valid()
        assert "capacity_hours_per_day" in form.errors

    def test_junk_and_over_max_digit_rates_are_rejected_not_500(self, tenant_a):
        from apps.scm.forms import WorkCenterForm
        for junk in ("NaN", "Infinity", "-Infinity", "not-a-number", "1e400", "9" * 20):
            form = WorkCenterForm(_work_centre_payload(machine_cost_per_hour=junk),
                                  tenant=tenant_a)
            assert not form.is_valid(), junk
            assert "machine_cost_per_hour" in form.errors, junk

    def test_a_duplicate_code_is_caught_on_the_form_not_as_an_integrityerror(self, tenant_a,
                                                                             work_center_a):
        from apps.scm.forms import WorkCenterForm
        form = WorkCenterForm(_work_centre_payload(code=work_center_a.code), tenant=tenant_a)
        assert not form.is_valid()


# ================================================================ ProductionTimeLogForm
class TestProductionTimeLogFormValidation:
    def test_the_work_order_dropdown_offers_only_open_runs(self, tenant_a, item_a,
                                                           released_work_order_a):
        """A log against a draft run has nothing to record, and one against a closed run is the
        freeze the model docstring describes."""
        from apps.scm.forms import ProductionTimeLogForm
        from apps.scm.models import WorkOrder
        draft = WorkOrder.objects.create(tenant=tenant_a, item=item_a,
                                         quantity_planned=Decimal("1"))
        closed = WorkOrder.objects.create(tenant=tenant_a, item=item_a,
                                          quantity_planned=Decimal("1"))
        WorkOrder.objects.filter(pk=closed.pk).update(status="closed")
        offered = set(ProductionTimeLogForm(tenant=tenant_a).fields["work_order"].queryset)
        assert released_work_order_a in offered
        assert draft not in offered
        assert closed not in offered

    def test_a_closed_runs_own_log_keeps_it_selectable_on_edit(self, tenant_a, time_log_a,
                                                               released_work_order_a):
        from apps.scm.forms import ProductionTimeLogForm
        released_work_order_a.status = "closed"
        released_work_order_a.save(update_fields=["status"])
        form = ProductionTimeLogForm(instance=time_log_a, tenant=tenant_a)
        assert released_work_order_a in set(form.fields["work_order"].queryset)

    def test_the_operator_dropdown_is_narrowed_to_employees(self, tenant_a, employee_party_a,
                                                            customer_a):
        from apps.scm.forms import ProductionTimeLogForm
        offered = set(ProductionTimeLogForm(tenant=tenant_a).fields["operator"].queryset)
        assert offered == {employee_party_a}

    def test_an_interval_over_31_days_is_refused_through_the_form(self, tenant_a,
                                                                  released_work_order_a,
                                                                  work_center_a):
        from django.utils import timezone
        from apps.scm.forms import ProductionTimeLogForm
        started = timezone.now()
        form = ProductionTimeLogForm(
            _time_log_payload(released_work_order_a, work_center_a,
                              started_at=started.strftime("%Y-%m-%dT%H:%M"),
                              ended_at=(started + datetime.timedelta(days=40)).strftime(
                                  "%Y-%m-%dT%H:%M")),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "ended_at" in form.errors

    def test_an_end_before_the_start_is_refused_through_the_form(self, tenant_a,
                                                                 released_work_order_a,
                                                                 work_center_a):
        from django.utils import timezone
        from apps.scm.forms import ProductionTimeLogForm
        started = timezone.now()
        form = ProductionTimeLogForm(
            _time_log_payload(released_work_order_a, work_center_a,
                              started_at=started.strftime("%Y-%m-%dT%H:%M"),
                              ended_at=(started - datetime.timedelta(hours=1)).strftime(
                                  "%Y-%m-%dT%H:%M")),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "ended_at" in form.errors

    def test_a_downtime_entry_without_a_reason_is_refused(self, tenant_a, released_work_order_a,
                                                          work_center_a):
        from apps.scm.forms import ProductionTimeLogForm
        form = ProductionTimeLogForm(
            _time_log_payload(released_work_order_a, work_center_a, entry_type="downtime"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "downtime_reason" in form.errors

    def test_a_negative_completed_quantity_is_refused(self, tenant_a, released_work_order_a,
                                                      work_center_a):
        from apps.scm.forms import ProductionTimeLogForm
        form = ProductionTimeLogForm(
            _time_log_payload(released_work_order_a, work_center_a, quantity_completed="-5"),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "quantity_completed" in form.errors


# ================================================================ WorkOrderScheduleForm bounds
class TestWorkOrderScheduleFormBounds:
    def test_a_year_9999_anchor_is_refused_rather_than_overflowing(self):
        """The view adds/subtracts a lead time from this — an unbounded 9999-12-31 raises an
        uncaught OverflowError, an ordinary POST turning into a 500."""
        from apps.scm.forms import WorkOrderScheduleForm
        form = WorkOrderScheduleForm({"direction": "forward", "anchor_date": "9999-12-31",
                                      "lead_time_days": "10"})
        assert not form.is_valid()
        assert "anchor_date" in form.errors

    def test_a_year_0001_anchor_is_refused_when_scheduling_backward(self):
        from apps.scm.forms import WorkOrderScheduleForm
        form = WorkOrderScheduleForm({"direction": "backward", "anchor_date": "0001-01-01",
                                      "lead_time_days": "10"})
        assert not form.is_valid()
        assert "anchor_date" in form.errors

    def test_an_in_range_anchor_is_accepted(self):
        from apps.scm.forms import WorkOrderScheduleForm
        form = WorkOrderScheduleForm({"direction": "forward", "anchor_date": "2026-05-01",
                                      "lead_time_days": "10"})
        assert form.is_valid(), form.errors

    def test_a_lead_time_beyond_ten_years_is_refused(self):
        from apps.scm.forms import WorkOrderScheduleForm
        form = WorkOrderScheduleForm({"direction": "forward", "anchor_date": "2026-05-01",
                                      "lead_time_days": "3651"})
        assert not form.is_valid()
        assert "lead_time_days" in form.errors

    def test_a_negative_lead_time_is_refused(self):
        from apps.scm.forms import WorkOrderScheduleForm
        form = WorkOrderScheduleForm({"direction": "forward", "anchor_date": "2026-05-01",
                                      "lead_time_days": "-1"})
        assert not form.is_valid()

    def test_a_junk_direction_is_refused(self):
        from apps.scm.forms import WorkOrderScheduleForm
        form = WorkOrderScheduleForm({"direction": "sideways", "anchor_date": "2026-05-01"})
        assert not form.is_valid()
        assert "direction" in form.errors


# ================================================================ WorkOrderReportForm
class TestWorkOrderReportFormValidation:
    def test_reporting_nothing_at_all_is_refused(self):
        from apps.scm.forms import WorkOrderReportForm
        form = WorkOrderReportForm({"quantity_good": "0", "quantity_scrapped": "0"})
        assert not form.is_valid()
        assert "Report a good quantity" in str(form.errors)

    def test_an_empty_post_is_refused(self):
        from apps.scm.forms import WorkOrderReportForm
        assert not WorkOrderReportForm({}).is_valid()

    def test_a_pure_scrap_report_is_allowed(self):
        from apps.scm.forms import WorkOrderReportForm
        form = WorkOrderReportForm({"quantity_good": "0", "quantity_scrapped": "2"})
        assert form.is_valid(), form.errors

    def test_negative_quantities_are_refused(self):
        from apps.scm.forms import WorkOrderReportForm
        form = WorkOrderReportForm({"quantity_good": "-3", "quantity_scrapped": "0"})
        assert not form.is_valid()
        assert "quantity_good" in form.errors

    def test_junk_and_over_max_digit_quantities_are_refused(self):
        from apps.scm.forms import WorkOrderReportForm
        for junk in ("NaN", "Infinity", "-Infinity", "abc", "1e400", "9" * 20):
            form = WorkOrderReportForm({"quantity_good": junk, "quantity_scrapped": "0"})
            assert not form.is_valid(), junk
            assert "quantity_good" in form.errors, junk

    def test_backflush_defaults_on_but_can_be_turned_off(self):
        from apps.scm.forms import WorkOrderReportForm
        assert WorkOrderReportForm().fields["backflush"].initial is True
        form = WorkOrderReportForm({"quantity_good": "1"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["backflush"] is False  # an unchecked box posts nothing


# ================================================================ BOM line formset guards
class TestBOMLineFormSetGuards:
    def _formset(self, tenant, instance, rows, initial=0):
        from apps.scm.forms import BOMLineFormSet
        return BOMLineFormSet(formset_data("lines", rows, initial=initial), instance=instance,
                              form_kwargs={"tenant": tenant})

    def test_a_recipe_that_consumes_its_own_output_is_refused(self, tenant_a, bom_draft_a,
                                                              item_lot_a):
        formset = self._formset(tenant_a, bom_draft_a, [
            {"id": "", "sequence": "10", "component": str(item_lot_a.pk), "quantity_per": "1",
             "uom": "", "scrap_pct": "0", "issue_method": "manual", "notes": ""},
        ])
        assert not formset.is_valid()
        assert "cannot consume itself" in str(formset.non_form_errors())

    def test_an_ordinary_component_line_is_accepted(self, tenant_a, bom_draft_a,
                                                    component_plate_a):
        formset = self._formset(tenant_a, bom_draft_a, [
            {"id": "", "sequence": "10", "component": str(component_plate_a.pk),
             "quantity_per": "1", "uom": "", "scrap_pct": "0", "issue_method": "manual",
             "notes": ""},
        ])
        assert formset.is_valid(), formset.errors

    def test_a_deleted_self_reference_is_not_re_flagged(self, tenant_a, bom_draft_a, item_lot_a):
        line = bom_draft_a.lines.first()
        formset = self._formset(tenant_a, bom_draft_a, [
            {"id": str(line.pk), "sequence": "10", "component": str(item_lot_a.pk),
             "quantity_per": "1", "uom": "", "scrap_pct": "0", "issue_method": "manual",
             "notes": "", "DELETE": "on"},
        ], initial=1)
        assert formset.is_valid(), formset.errors

    def test_more_than_200_lines_in_one_post_is_refused(self, tenant_a, bom_draft_a,
                                                        component_plate_a):
        """Without validate_max Django silently accepts up to absolute_max and ignores the
        overflow — and a recipe that wide feeds explode(), whose output is the PRODUCT of the
        branch factors."""
        from apps.scm.forms import BOMLineFormSet
        data = formset_data("lines", [
            {"id": "", "sequence": "10", "component": str(component_plate_a.pk),
             "quantity_per": "1", "uom": "", "scrap_pct": "0", "issue_method": "manual",
             "notes": ""},
        ])
        data["lines-TOTAL_FORMS"] = "201"
        formset = BOMLineFormSet(data, instance=bom_draft_a, form_kwargs={"tenant": tenant_a})
        assert not formset.is_valid()
        assert "at most 200" in str(formset.non_form_errors())

    def test_the_guard_no_ops_when_the_parent_has_no_item_yet(self, tenant_a, component_plate_a):
        """instance=None means item_id is None — the create VIEW is what has to attach the cleaned
        header before validating (see TestBillOfMaterialsCreateSelfReference in test_views)."""
        from apps.scm.forms import BOMLineFormSet
        formset = BOMLineFormSet(formset_data("lines", [
            {"id": "", "sequence": "10", "component": str(component_plate_a.pk),
             "quantity_per": "1", "uom": "", "scrap_pct": "0", "issue_method": "manual",
             "notes": ""},
        ]), form_kwargs={"tenant": tenant_a})
        assert formset.is_valid(), formset.errors


# ================================================================ Cross-tenant FORM binding
class TestManufacturingCrossTenantFormScoping:
    def test_the_work_order_form_refuses_another_tenants_item(self, tenant_a, item_b):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_b), tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_the_work_order_form_refuses_another_tenants_bom(self, tenant_a, item_a, bom_b):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_a, bom=str(bom_b.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "bom" in form.errors

    def test_the_work_order_form_refuses_another_tenants_work_centre(self, tenant_a, item_a,
                                                                     work_center_b):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_a, work_center=str(work_center_b.pk)),
                             tenant=tenant_a)
        assert not form.is_valid()
        assert "work_center" in form.errors

    def test_the_work_order_form_refuses_another_tenants_location(self, tenant_a, item_a,
                                                                  location_b):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_a, component_location=str(location_b.pk)),
                             tenant=tenant_a)
        assert not form.is_valid()
        assert "component_location" in form.errors

    def test_the_work_order_form_refuses_another_tenants_lot(self, tenant_a, item_a, lot_b):
        from apps.scm.forms import WorkOrderForm
        form = WorkOrderForm(_wo_payload(item_a, output_lot_serial=str(lot_b.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "output_lot_serial" in form.errors

    def test_the_component_form_refuses_another_tenants_item(self, tenant_a, item_b):
        from apps.scm.forms import WorkOrderComponentForm
        form = WorkOrderComponentForm(_component_payload(item_b), tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_the_bom_form_refuses_another_tenants_item(self, tenant_a, item_b):
        from apps.scm.forms import BillOfMaterialsForm
        form = BillOfMaterialsForm({"item": str(item_b.pk), "name": "Crafted", "version": "1",
                                    "bom_type": "manufacture", "output_quantity": "1", "uom": "",
                                    "lead_time_days": "0", "default_work_center": "",
                                    "status": "draft", "effective_from": "", "effective_to": "",
                                    "notes": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_the_bom_form_refuses_another_tenants_work_centre(self, tenant_a, item_a,
                                                              work_center_b):
        from apps.scm.forms import BillOfMaterialsForm
        form = BillOfMaterialsForm({"item": str(item_a.pk), "name": "Crafted", "version": "5",
                                    "bom_type": "manufacture", "output_quantity": "1", "uom": "",
                                    "lead_time_days": "0",
                                    "default_work_center": str(work_center_b.pk),
                                    "status": "draft", "effective_from": "", "effective_to": "",
                                    "notes": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "default_work_center" in form.errors

    def test_the_time_log_form_refuses_another_tenants_run(self, tenant_a, work_order_b,
                                                           work_center_a):
        from apps.scm.forms import ProductionTimeLogForm
        form = ProductionTimeLogForm(_time_log_payload(work_order_b, work_center_a),
                                     tenant=tenant_a)
        assert not form.is_valid()
        assert "work_order" in form.errors

    def test_the_time_log_form_refuses_another_tenants_work_centre(self, tenant_a,
                                                                   released_work_order_a,
                                                                   work_center_b):
        from apps.scm.forms import ProductionTimeLogForm
        form = ProductionTimeLogForm(_time_log_payload(released_work_order_a, work_center_b),
                                     tenant=tenant_a)
        assert not form.is_valid()
        assert "work_center" in form.errors

    def test_the_work_centre_form_refuses_another_tenants_location(self, tenant_a, location_b):
        from apps.scm.forms import WorkCenterForm
        form = WorkCenterForm(_work_centre_payload(location=str(location_b.pk)), tenant=tenant_a)
        assert not form.is_valid()
        assert "location" in form.errors
