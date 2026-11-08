from django.contrib import admin

from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetAudit,
    AssetCapitalization,
    AssetCustodyLog,
    AssetIncidentReport,
    AssetMovementLog,
    AssetRequisition,
    AssetTag,
)


@admin.register(AssetRequisition)
class AssetRequisitionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "asset_category", "priority", "estimated_cost", "status", "tenant")
    list_select_related = ("tenant",)
    list_filter = ("status", "priority", "asset_category")
    search_fields = ("number", "title", "budget_code")


@admin.register(AssetAcquisitionReceipt)
class AssetAcquisitionReceiptAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "serial_number", "condition_on_arrival", "status", "tenant")
    list_select_related = ("tenant",)
    list_filter = ("status", "condition_on_arrival")
    search_fields = ("number", "title", "serial_number", "tracking_number")


@admin.register(AssetCapitalization)
class AssetCapitalizationAdmin(admin.ModelAdmin):
    list_display = ("number", "asset_name", "total_cost_basis", "depreciation_method", "status", "tenant")
    list_select_related = ("tenant",)
    list_filter = ("status", "depreciation_method")
    search_fields = ("number", "asset_name")


@admin.register(AssetTag)
class AssetTagAdmin(admin.ModelAdmin):
    list_display = ("tag_code", "number", "tag_format", "status", "is_verified", "tenant")
    list_select_related = ("tenant",)
    list_filter = ("status", "tag_format", "is_verified")
    search_fields = ("tag_code", "number", "physical_placement")


@admin.register(AssetAudit)
class AssetAuditAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "audit_type", "scheduled_date", "is_blind_count", "status", "tenant")
    list_select_related = ("tenant",)
    list_filter = ("status", "audit_type", "is_blind_count")
    search_fields = ("number", "title", "discrepancy_notes")


@admin.register(AssetMovementLog)
class AssetMovementLogAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "asset", "movement_type", "status", "dispatch_date", "received_date", "tenant")
    list_select_related = ("tenant", "asset")
    list_filter = ("status", "movement_type", "condition_on_receipt")
    search_fields = ("number", "title", "tracking_number", "carrier_name")


@admin.register(AssetCustodyLog)
class AssetCustodyLogAdmin(admin.ModelAdmin):
    list_display = ("number", "asset", "action_type", "borrower_name", "status", "checkout_date", "expected_return_date", "tenant")
    list_select_related = ("tenant", "asset")
    list_filter = ("status", "action_type", "checkout_condition")
    search_fields = ("number", "borrower_name", "work_order_reference", "purpose")


@admin.register(AssetIncidentReport)
class AssetIncidentReportAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "asset", "incident_type", "severity", "status", "incident_date", "estimated_loss_value", "tenant")
    list_select_related = ("tenant", "asset")
    list_filter = ("status", "incident_type", "severity", "police_report_filed", "insurance_claim_filed")
    search_fields = ("number", "title", "police_report_number", "insurance_claim_number")
