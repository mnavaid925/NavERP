"""SCM admin registrations.

Stays a flat module at the app root (per the Backend Package Structure rule); the models import
works because apps/scm/models/__init__.py re-exports everything.
"""
from django.contrib import admin

from apps.scm.models import (
    GoodsReceiptLine,
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
    RFQ,
    RFQLine,
    RFQQuote,
    RFQQuoteLine,
    RFQVendor,
    SupplierCatalog,
    SupplierCatalogItem,
    SupplierContract,
    SupplierProfile,
    SupplierRiskAssessment,
    SupplierScorecard,
)


class PurchaseRequisitionLineInline(admin.TabularInline):
    model = PurchaseRequisitionLine
    extra = 0


@admin.register(PurchaseRequisition)
class PurchaseRequisitionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "tenant", "status", "estimated_total", "required_by")
    list_filter = ("tenant", "status")
    search_fields = ("number", "title")
    inlines = [PurchaseRequisitionLineInline]


class RFQLineInline(admin.TabularInline):
    model = RFQLine
    extra = 0


class RFQVendorInline(admin.TabularInline):
    model = RFQVendor
    extra = 0


@admin.register(RFQ)
class RFQAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "tenant", "status", "issue_date", "response_due")
    list_filter = ("tenant", "status")
    search_fields = ("number", "title")
    inlines = [RFQLineInline, RFQVendorInline]


class RFQQuoteLineInline(admin.TabularInline):
    model = RFQQuoteLine
    extra = 0


@admin.register(RFQQuote)
class RFQQuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "rfq", "party", "tenant", "status", "total", "lead_time_days")
    list_filter = ("tenant", "status")
    search_fields = ("number", "vendor_reference", "party__name")
    inlines = [RFQQuoteLineInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "vendor", "tenant", "status", "total", "order_date", "version")
    list_filter = ("tenant", "status")
    search_fields = ("number", "vendor__name")
    inlines = [PurchaseOrderLineInline]


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 0


@admin.register(GoodsReceiptNote)
class GoodsReceiptNoteAdmin(admin.ModelAdmin):
    list_display = ("number", "purchase_order", "tenant", "status", "match_status", "receipt_date")
    list_filter = ("tenant", "status", "match_status")
    search_fields = ("number", "delivery_note_ref", "purchase_order__number")
    inlines = [GoodsReceiptLineInline]


# ============================================================ 4.2 Supplier Relationship Management
@admin.register(SupplierProfile)
class SupplierProfileAdmin(admin.ModelAdmin):
    list_display = ("party", "tenant", "onboarding_status", "tier", "category")
    list_filter = ("tenant", "onboarding_status", "tier")
    search_fields = ("party__name", "legal_name", "category")


@admin.register(SupplierScorecard)
class SupplierScorecardAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "tenant", "status", "overall_score", "grade", "period_end")
    list_filter = ("tenant", "status")
    search_fields = ("number", "party__name")


@admin.register(SupplierContract)
class SupplierContractAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "party", "tenant", "status", "end_date")
    list_filter = ("tenant", "status", "contract_type")
    search_fields = ("number", "title", "party__name")


class SupplierCatalogItemInline(admin.TabularInline):
    model = SupplierCatalogItem
    extra = 0


@admin.register(SupplierCatalog)
class SupplierCatalogAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "party", "tenant", "status", "valid_until")
    list_filter = ("tenant", "status")
    search_fields = ("number", "name", "party__name")
    inlines = [SupplierCatalogItemInline]


@admin.register(SupplierRiskAssessment)
class SupplierRiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "tenant", "status", "risk_level", "assessment_date")
    list_filter = ("tenant", "status", "risk_level")
    search_fields = ("number", "party__name")
