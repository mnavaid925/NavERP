from django.contrib import admin

from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetAudit,
    AssetBusinessContinuityPlan,
    AssetCalibrationRecord,
    AssetCapitalization,
    AssetCategory,
    AssetComplianceAudit,
    AssetComplianceFramework,
    AssetComplianceIncident,
    AssetConditionAssessment,
    AssetCriticalityAssessment,
    AssetCustodyLog,
    AssetCyberSecurityProfile,
    AssetDepreciationSchedule,
    AssetDisposalRequest,
    AssetResaleListing,
    AssetScrapSalvage,
    AssetTradeIn,
    AssetDowntimeLog,
    AssetEnergyReading,
    AssetFailureMode,
    AssetIncidentReport,
    AssetInsuranceClaim,
    AssetInsurancePolicy,
    AssetLeaseBuyAnalysis,
    AssetLeaseContract,
    AssetLeaseModification,
    AssetLeaseSchedule,
    AssetMaintenanceLog,
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetModel,
    AssetMovementLog,
    AssetOeeRecord,
    AssetPerformanceScorecard,
    AssetPermitLicense,
    AssetRequisition,
    AssetRevaluation,
    AssetRiskMitigationAction,
    AssetRiskRegister,
    AssetServiceContract,
    AssetSpecificationTemplate,
    AssetTag,
    AssetTelemetryReading,
    AssetTransfer,
    AssetWarranty,
    AssetWarrantyClaim,
    CapitalizationPolicy,
    AssetGeofenceEvent,
    AssetScanLog,
    FieldWorkOrder,
    MobileAssetInspection,
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


@admin.register(AssetDowntimeLog)
class AssetDowntimeLogAdmin(admin.ModelAdmin):
    list_display = ("number", "started_at", "downtime_category", "impact_level", "duration_minutes", "total_downtime_cost", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "department", "logged_by")
    list_filter = ("status", "downtime_category", "impact_level", "is_mtbf_failure")
    search_fields = ("number", "root_cause_code", "failure_description")


@admin.register(AssetOeeRecord)
class AssetOeeRecordAdmin(admin.ModelAdmin):
    list_display = ("number", "record_date", "shift_name", "availability_percentage", "performance_percentage", "quality_percentage", "oee_percentage", "benchmark_tier", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "recorded_by")
    list_filter = ("status", "benchmark_tier")
    search_fields = ("number", "shift_name", "notes")


@admin.register(AssetEnergyReading)
class AssetEnergyReadingAdmin(admin.ModelAdmin):
    list_display = ("number", "reading_timestamp", "utility_type", "consumption_value", "unit_of_measure", "carbon_emissions_kg_co2e", "total_energy_cost", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "utility_provider", "recorded_by")
    list_filter = ("status", "utility_type", "ghg_scope")
    search_fields = ("number", "meter_serial_number", "notes")


@admin.register(AssetPerformanceScorecard)
class AssetPerformanceScorecardAdmin(admin.ModelAdmin):
    list_display = ("number", "period_type", "period_start", "period_end", "capacity_utilization_rate", "availability_rate", "mtbf_hours", "performance_index_score", "benchmark_grade", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "department", "evaluated_by")
    list_filter = ("status", "period_type", "benchmark_grade")
    search_fields = ("number", "executive_summary")


@admin.register(AssetConditionAssessment)
class AssetConditionAssessmentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "assessment_type", "condition_grade", "health_score", "operating_status", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "asset_category", "inspector", "external_inspector")
    list_filter = ("status", "condition_grade", "assessment_type", "operating_status")
    search_fields = ("number", "title", "findings")


@admin.register(AssetTelemetryReading)
class AssetTelemetryReadingAdmin(admin.ModelAdmin):
    list_display = ("number", "sensor_identifier", "metric_type", "reading_value", "metric_unit", "deviation_percentage", "threshold_status", "is_anomaly", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "recorded_by")
    list_filter = ("threshold_status", "metric_type", "source", "is_anomaly")
    search_fields = ("number", "sensor_identifier", "alert_notes")


@admin.register(AssetFailureMode)
class AssetFailureModeAdmin(admin.ModelAdmin):
    list_display = ("number", "component_subsystem", "failure_mode", "rpn", "risk_level", "rcm_strategy", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "asset_category", "linked_maintenance_schedule", "assessed_by")
    list_filter = ("status", "risk_level", "rcm_strategy")
    search_fields = ("number", "component_subsystem", "failure_mode", "failure_cause")


@admin.register(AssetCalibrationRecord)
class AssetCalibrationRecordAdmin(admin.ModelAdmin):
    list_display = ("number", "instrument_tag", "calibration_date", "next_due_date", "setpoint_nominal", "as_left_error", "calibration_result", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "calibrated_by", "service_vendor")
    list_filter = ("status", "calibration_result", "tolerance_unit")
    search_fields = ("number", "instrument_tag", "reference_standard_used", "certificate_number")


@admin.register(AssetWarranty)
class AssetWarrantyAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "warranty_type", "coverage_scope", "start_date", "end_date", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "asset_category", "warrantor_party", "currency")
    list_filter = ("status", "warranty_type", "coverage_scope")
    search_fields = ("number", "title", "warranty_certificate_number")


@admin.register(AssetWarrantyClaim)
class AssetWarrantyClaimAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "warranty", "incident_date", "claimed_amount", "approved_amount", "net_recovery_amount", "claim_status", "tenant")
    list_select_related = ("tenant", "warranty", "fixed_asset", "operational_asset", "currency")
    list_filter = ("claim_status", "resolution_type", "part_return_status")
    search_fields = ("number", "title", "warrantor_claim_reference", "rma_tracking_number")


@admin.register(AssetInsurancePolicy)
class AssetInsurancePolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "policy_number", "title", "policy_type", "effective_date", "expiration_date", "total_insured_value", "status", "tenant")
    list_select_related = ("tenant", "underwriter_party", "broker_party", "currency")
    list_filter = ("status", "policy_type", "valuation_basis")
    search_fields = ("number", "policy_number", "title")


@admin.register(AssetInsuranceClaim)
class AssetInsuranceClaimAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "policy", "peril_type", "incident_date", "claimed_loss_amount", "settlement_payout_amount", "claim_status", "tenant")
    list_select_related = ("tenant", "policy", "currency", "adjuster_party")
    list_filter = ("claim_status", "peril_type", "settlement_method")
    search_fields = ("number", "title", "carrier_claim_number", "incident_location")


@admin.register(AssetDisposalRequest)
class AssetDisposalRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "fixed_asset", "disposal_method", "retirement_reason", "net_book_value", "realized_gain_loss", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "operational_asset", "category")
    list_filter = ("status", "disposal_method", "retirement_reason")
    search_fields = ("number", "title", "justification_notes")


@admin.register(AssetResaleListing)
class AssetResaleListingAdmin(admin.ModelAdmin):
    list_display = ("number", "fixed_asset", "listing_channel", "asking_price", "highest_bid_amount", "gross_sale_proceeds", "status", "payment_status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "disposal_request", "buyer")
    list_filter = ("status", "listing_channel", "payment_status")
    search_fields = ("number", "listing_reference", "buyer_contact_name")


@admin.register(AssetTradeIn)
class AssetTradeInAdmin(admin.ModelAdmin):
    list_display = ("number", "retired_fixed_asset", "vendor", "trade_in_allowance", "net_credit_applied", "net_cash_outflow", "status", "tenant")
    list_select_related = ("tenant", "retired_fixed_asset", "vendor", "disposal_request")
    list_filter = ("status", "like_kind_exchange")
    search_fields = ("number", "agreement_number")


@admin.register(AssetScrapSalvage)
class AssetScrapSalvageAdmin(admin.ModelAdmin):
    list_display = ("number", "fixed_asset", "scrap_method", "recycler_partner", "total_scrap_weight_kg", "salvage_proceeds", "status", "tenant")
    list_select_related = ("tenant", "fixed_asset", "disposal_request", "recycler_partner")
    list_filter = ("status", "scrap_method", "has_hazardous_materials", "abatement_certified", "data_sanitized")
    search_fields = ("number", "cod_number", "epa_manifest_number", "carrier_name")


@admin.register(AssetComplianceFramework)
class AssetComplianceFrameworkAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "framework_type", "regulatory_agency", "applicable_category", "readiness_score", "status", "tenant")
    list_select_related = ("tenant", "regulatory_agency", "applicable_category")
    list_filter = ("status", "framework_type")
    search_fields = ("number", "code", "name", "regulatory_agency__name")


@admin.register(AssetComplianceAudit)
class AssetComplianceAuditAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "framework", "asset", "audit_type", "audit_date", "compliance_rating", "status", "tenant")
    list_select_related = ("tenant", "framework", "asset", "lead_auditor_user", "auditor_party")
    list_filter = ("status", "audit_type", "compliance_rating")
    search_fields = ("number", "title", "framework__code", "asset__name")


@admin.register(AssetPermitLicense)
class AssetPermitLicenseAdmin(admin.ModelAdmin):
    list_display = ("number", "permit_number", "permit_name", "permit_type", "asset", "issuing_authority", "expiration_date", "status", "tenant")
    list_select_related = ("tenant", "asset", "issuing_authority")
    list_filter = ("status", "permit_type")
    search_fields = ("number", "permit_number", "permit_name", "asset__code")


@admin.register(AssetComplianceIncident)
class AssetComplianceIncidentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "incident_type", "severity", "asset", "enforcement_agency", "fine_assessed", "fine_paid", "status", "tenant")
    list_select_related = ("tenant", "asset", "permit", "audit", "enforcement_agency", "assigned_investigator")
    list_filter = ("status", "severity", "incident_type", "root_cause")
    search_fields = ("number", "title", "citation_reference", "asset__code")


@admin.register(AssetLeaseContract)
class AssetLeaseContractAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "lessor", "classification", "payment_amount", "current_lease_liability", "status", "tenant")
    list_select_related = ("tenant", "lessor", "asset", "category", "fixed_asset")
    list_filter = ("status", "classification", "payment_frequency", "payment_timing")
    search_fields = ("number", "title", "master_lease_agreement_ref", "lessor__name")


@admin.register(AssetLeaseSchedule)
class AssetLeaseScheduleAdmin(admin.ModelAdmin):
    list_display = ("number", "lease_contract", "period_number", "due_date", "payment_amount", "interest_expense", "principal_reduction", "ending_liability", "status", "tenant")
    list_select_related = ("tenant", "lease_contract", "lease_contract__lessor")
    list_filter = ("status", "due_date")
    search_fields = ("number", "payment_reference", "lease_contract__number")


@admin.register(AssetLeaseModification)
class AssetLeaseModificationAdmin(admin.ModelAdmin):
    list_display = ("number", "lease_contract", "modification_type", "effective_date", "liability_adjustment", "status", "tenant")
    list_select_related = ("tenant", "lease_contract", "requested_by", "approved_by")
    list_filter = ("status", "modification_type")
    search_fields = ("number", "justification", "lease_contract__number")


@admin.register(AssetLeaseBuyAnalysis)
class AssetLeaseBuyAnalysisAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "target_asset_name", "category", "purchase_price", "monthly_lease_payment", "net_advantage_to_leasing", "recommendation", "status", "tenant")
    list_select_related = ("tenant", "category", "evaluated_by", "approved_by")
    list_filter = ("status", "recommendation")
    search_fields = ("number", "title", "target_asset_name")


@admin.register(MobileAssetInspection)
class MobileAssetInspectionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "asset", "inspection_type", "overall_result", "condition_rating", "inspector", "status", "tenant")
    list_select_related = ("tenant", "asset", "inspector")
    list_filter = ("status", "overall_result", "inspection_type")
    search_fields = ("number", "title", "asset__name", "asset__code")


@admin.register(FieldWorkOrder)
class FieldWorkOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "asset", "work_order_type", "priority", "assigned_technician", "labor_wrench_minutes", "status", "tenant")
    list_select_related = ("tenant", "asset", "assigned_technician")
    list_filter = ("status", "priority", "work_order_type")
    search_fields = ("number", "title", "asset__name", "asset__code")


@admin.register(AssetScanLog)
class AssetScanLogAdmin(admin.ModelAdmin):
    list_display = ("number", "raw_payload", "asset", "scan_method", "scan_context", "match_status", "scanned_by", "scanned_at", "tenant")
    list_select_related = ("tenant", "asset", "scanned_by")
    list_filter = ("match_status", "scan_method", "scan_context")
    search_fields = ("number", "raw_payload", "device_info")


@admin.register(AssetGeofenceEvent)
class AssetGeofenceEventAdmin(admin.ModelAdmin):
    list_display = ("number", "fence_name", "asset", "event_type", "severity", "distance_from_center_m", "status", "detected_at", "tenant")
    list_select_related = ("tenant", "asset", "acknowledged_by")
    list_filter = ("status", "event_type", "severity")
    search_fields = ("number", "fence_name", "resolution_notes")


@admin.register(AssetRiskRegister)
class AssetRiskRegisterAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "risk_category", "asset", "inherent_risk_score", "inherent_risk_level", "residual_risk_level", "status", "tenant")
    list_select_related = ("tenant", "asset", "category", "risk_owner")
    list_filter = ("status", "risk_category", "inherent_risk_level", "residual_risk_level")
    search_fields = ("number", "title", "failure_mode")


@admin.register(AssetBusinessContinuityPlan)
class AssetBusinessContinuityPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "primary_asset", "redundancy_type", "recovery_time_objective_hours", "disaster_scenario", "drill_result", "status", "tenant")
    list_select_related = ("tenant", "primary_asset", "backup_redundant_asset", "emergency_lead")
    list_filter = ("status", "redundancy_type", "disaster_scenario", "drill_result")
    search_fields = ("number", "title", "alternate_facility_site")


@admin.register(AssetCyberSecurityProfile)
class AssetCyberSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "asset", "device_type", "network_zone", "ip_address", "firmware_version", "cve_risk_score", "security_posture_status", "tenant")
    list_select_related = ("tenant", "asset")
    list_filter = ("security_posture_status", "firmware_update_status", "network_zone", "device_type")
    search_fields = ("number", "asset__name", "ip_address", "mac_address")


@admin.register(AssetRiskMitigationAction)
class AssetRiskMitigationActionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "risk", "action_type", "priority", "assigned_to", "target_completion_date", "status", "effectiveness_rating", "tenant")
    list_select_related = ("tenant", "risk", "assigned_to", "alternative_supplier")
    list_filter = ("status", "priority", "action_type", "effectiveness_rating")
    search_fields = ("number", "title", "risk__number")









