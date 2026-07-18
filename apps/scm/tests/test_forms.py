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
