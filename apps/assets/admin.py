from django.contrib import admin

from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetAudit,
    AssetCapitalization,
    AssetCategory,
    AssetCriticalityAssessment,
    AssetCustodyLog,
    AssetDepreciationSchedule,
    AssetIncidentReport,
    AssetMaintenanceLog,
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetModel,
    AssetMovementLog,
    AssetRequisition,
    AssetRevaluation,
    AssetServiceContract,
    AssetSpecificationTemplate,
    AssetTag,
    AssetTransfer,
    CapitalizationPolicy,
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


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category_type", "unspsc_code", "default_criticality", "is_active", "tenant")
    list_select_related = ("tenant", "parent")
    list_filter = ("category_type", "default_criticality", "is_active")
    search_fields = ("code", "name", "unspsc_code", "unspsc_title")


@admin.register(AssetModel)
class AssetModelAdmin(admin.ModelAdmin):
    list_display = ("model_number", "name", "category", "manufacturer", "standard_warranty_months", "model_status", "tenant")
    list_select_related = ("tenant", "category", "manufacturer")
    list_filter = ("model_status", "warranty_coverage_type", "is_active")
    search_fields = ("model_number", "name", "manufacturer_name_fallback")


@admin.register(AssetCriticalityAssessment)
class AssetCriticalityAssessmentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "asset", "composite_score", "abc_rating", "is_single_point_of_failure", "assessment_status", "tenant")
    list_select_related = ("tenant", "asset", "assessor")
    list_filter = ("abc_rating", "assessment_status", "is_single_point_of_failure")
    search_fields = ("number", "title", "findings_and_mitigation")


@admin.register(AssetSpecificationTemplate)
class AssetSpecificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("attribute_key", "display_name", "category", "model", "data_type", "unit_of_measure", "is_required", "tenant")
    list_select_related = ("tenant", "category", "model")
    list_filter = ("data_type", "is_required", "is_filterable")
    search_fields = ("attribute_key", "display_name", "unit_of_measure")


@admin.register(AssetDepreciationSchedule)
class AssetDepreciationScheduleAdmin(admin.ModelAdmin):
    list_display = ("number", "fixed_asset", "fiscal_year", "period_number", "depreciation_method", "depreciation_amount", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "fiscal_period")
    list_filter = ("status", "depreciation_method", "fiscal_year", "period_frequency")
    search_fields = ("number", "fixed_asset__name", "fixed_asset__number", "notes")


@admin.register(AssetRevaluation)
class AssetRevaluationAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "fixed_asset", "event_type", "valuation_date", "new_fair_market_value", "revaluation_adjustment", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "appraiser")
    list_filter = ("status", "event_type", "valuation_method")
    search_fields = ("number", "title", "fixed_asset__name", "fixed_asset__number")


@admin.register(AssetTransfer)
class AssetTransferAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "fixed_asset", "transfer_type", "source_department", "destination_department", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "source_department", "destination_department")
    list_filter = ("status", "transfer_type")
    search_fields = ("number", "title", "fixed_asset__name", "fixed_asset__number")


@admin.register(CapitalizationPolicy)
class CapitalizationPolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "policy_scope", "minimum_cost_threshold", "minimum_useful_life_months", "de_minimis_safe_harbor", "is_active", "tenant")
    list_select_related = ("tenant", "category")
    list_filter = ("policy_scope", "de_minimis_safe_harbor", "is_active")
    search_fields = ("number", "name", "applicable_gaap_standard")


@admin.register(AssetMaintenanceRequest)
class AssetMaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "request_type", "urgency", "is_breakdown", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "assigned_technician", "assigned_vendor")
    list_filter = ("status", "urgency", "request_type", "is_breakdown")
    search_fields = ("number", "title", "symptom_description")


@admin.register(AssetMaintenanceSchedule)
class AssetMaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "schedule_type", "frequency_interval", "frequency_unit", "next_due_date", "is_active", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "assigned_technician")
    list_filter = ("status", "schedule_type", "frequency_unit", "is_active", "is_mandatory")
    search_fields = ("number", "name", "service_checklist")


@admin.register(AssetServiceContract)
class AssetServiceContractAdmin(admin.ModelAdmin):
    list_display = ("number", "contract_number", "title", "vendor", "contract_type", "contract_value", "end_date", "status", "tenant")
    list_select_related = ("tenant", "vendor", "fixed_asset", "operational_asset")
    list_filter = ("status", "contract_type", "billing_frequency", "auto_renew")
    search_fields = ("number", "contract_number", "title", "vendor__name")


@admin.register(AssetMaintenanceLog)
class AssetMaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ("number", "service_date", "maintenance_type", "failure_code", "downtime_hours", "total_cost", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "lead_technician", "service_vendor")
    list_filter = ("status", "maintenance_type", "failure_code")
    search_fields = ("number", "parts_consumed_summary", "action_taken")

