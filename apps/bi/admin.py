from django.contrib import admin

from apps.bi.models import (
    CdcSyncConfig,
    DataMart,
    DataSourceConnector,
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    IngestionPipeline,
    IngestionRun,
    LakehouseZone,
    TransformationStep,
    WarehouseStoragePolicy,
    WarehouseTable,
    SemanticModel,
    BusinessGlossaryTerm,
    CalculatedMeasure,
    DrillHierarchy,
    DataQualityProfile,
    DataQualityRule,
    DataQualityException,
    DataQualityScorecard,
    MdmGoldenRecord,
    MdmSurvivorshipRule,
    MdmHierarchyNode,
    MdmReferenceCode,
)


@admin.register(DataSourceConnector)
class DataSourceConnectorAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "connector_type", "status", "test_status", "tenant", "created_at")
    list_filter = ("status", "connector_type", "test_status", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("number", "created_at", "updated_at", "last_tested_at")


@admin.register(IngestionPipeline)
class IngestionPipelineAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "connector", "ingestion_mode", "target_staging_table", "status", "tenant")
    list_filter = ("status", "ingestion_mode", "schedule_cadence", "file_format", "tenant")
    search_fields = ("number", "name", "source_entity", "target_staging_table")
    readonly_fields = ("number", "webhook_token", "webhook_secret", "created_at", "updated_at", "last_run_at")


@admin.register(CdcSyncConfig)
class CdcSyncConfigAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "capture_method", "sync_mode", "cursor_field", "schema_drift_policy", "tenant")
    list_filter = ("capture_method", "sync_mode", "schema_drift_policy", "capture_deletes", "tenant")
    search_fields = ("number", "pipeline__name", "cursor_field", "primary_key_fields")
    readonly_fields = ("number", "created_at", "updated_at", "last_checkpoint_at")


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "status", "trigger_type", "records_read", "records_written", "started_at", "tenant")
    list_filter = ("status", "trigger_type", "tenant")
    search_fields = ("number", "pipeline__name", "error_message")
    readonly_fields = ("number", "created_at", "updated_at", "started_at", "completed_at")


@admin.register(EtlPipeline)
class EtlPipelineAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "pipeline_type", "status", "schedule_cadence", "tenant", "created_at")
    list_filter = ("status", "pipeline_type", "schedule_cadence", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("number", "created_at", "updated_at", "last_run_at")


@admin.register(TransformationStep)
class TransformationStepAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "pipeline", "step_type", "sequence_order", "is_enabled", "tenant")
    list_filter = ("step_type", "is_enabled", "tenant")
    search_fields = ("number", "name", "pipeline__name")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(EtlPipelineVersion)
class EtlPipelineVersionAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "version_number", "is_active", "tenant", "created_at")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "pipeline__name", "commit_message")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(EtlPipelineRun)
class EtlPipelineRunAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "status", "trigger_type", "records_processed", "duration_seconds", "tenant")
    list_filter = ("status", "trigger_type", "tenant")
    search_fields = ("number", "pipeline__name", "error_log")
    readonly_fields = ("number", "created_at", "updated_at", "started_at", "completed_at")


@admin.register(WarehouseStoragePolicy)
class WarehouseStoragePolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "tier", "compression_type", "retention_days", "archive_after_days", "is_default", "is_active", "tenant")
    list_filter = ("tier", "compression_type", "is_default", "is_active", "tenant")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(LakehouseZone)
class LakehouseZoneAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "zone_type", "storage_format", "file_format", "is_governed", "is_active", "tenant")
    list_filter = ("zone_type", "storage_format", "file_format", "is_governed", "is_active", "tenant")
    search_fields = ("number", "name", "code", "storage_location", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(DataMart)
class DataMartAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "subject_area", "refresh_cadence", "lead_steward", "org_unit", "is_active", "tenant")
    list_filter = ("subject_area", "refresh_cadence", "is_active", "tenant")
    search_fields = ("number", "name", "code", "target_schema", "description")
    readonly_fields = ("number", "tenant", "last_refreshed_at", "created_at", "updated_at")


@admin.register(WarehouseTable)
class WarehouseTableAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "table_name", "table_type", "lakehouse_zone", "data_mart", "storage_policy", "row_count_estimate", "size_bytes", "is_active", "tenant")
    list_filter = ("table_type", "partition_strategy", "is_materialized", "is_active", "tenant")
    search_fields = ("number", "name", "table_name", "schema_name", "description")
    readonly_fields = ("number", "tenant", "row_count_estimate", "size_bytes", "last_vacuumed_at", "last_analyzed_at", "created_at", "updated_at")


@admin.register(SemanticModel)
class SemanticModelAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "model_type", "lakehouse_zone", "data_mart", "warehouse_table", "certification_status", "is_active", "tenant")
    list_select_related = ("lakehouse_zone", "data_mart", "warehouse_table", "steward")
    list_filter = ("model_type", "certification_status", "is_active", "tenant")
    search_fields = ("number", "name", "code", "target_table_or_view", "description")
    readonly_fields = ("number", "tenant", "certified_at", "created_at", "updated_at")


@admin.register(BusinessGlossaryTerm)
class BusinessGlossaryTermAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "domain", "status", "sensitivity_classification", "steward", "semantic_model", "is_active", "tenant")
    list_select_related = ("steward", "semantic_model", "approved_by")
    list_filter = ("domain", "status", "sensitivity_classification", "is_active", "tenant")
    search_fields = ("number", "name", "code", "definition", "acronym", "synonyms_text")
    readonly_fields = ("number", "tenant", "approved_at", "created_at", "updated_at")


@admin.register(CalculatedMeasure)
class CalculatedMeasureAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "semantic_model", "aggregation_type", "time_intelligence", "format_string", "is_active", "tenant")
    list_select_related = ("semantic_model",)
    list_filter = ("aggregation_type", "time_intelligence", "format_string", "display_units", "is_active", "tenant")
    search_fields = ("number", "name", "code", "source_column", "formula_expression", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(DrillHierarchy)
class DrillHierarchyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "semantic_model", "hierarchy_type", "primary_drill_path", "is_active", "tenant")
    list_select_related = ("semantic_model",)
    list_filter = ("hierarchy_type", "primary_drill_path", "is_active", "tenant")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(DataQualityProfile)
class DataQualityProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "target_type", "status", "completeness_score", "uniqueness_score", "validity_score", "total_row_count", "is_active", "tenant")
    list_select_related = ("warehouse_table", "semantic_model", "profiled_by")
    list_filter = ("target_type", "status", "is_active", "tenant")
    search_fields = ("number", "name", "notes")
    readonly_fields = ("number", "tenant", "profiled_at", "duration_seconds", "created_at", "updated_at")


@admin.register(DataQualityRule)
class DataQualityRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "rule_category", "dimension", "target_type", "rule_type", "severity", "last_status", "pass_rate_pct", "is_active", "tenant")
    list_select_related = ("warehouse_table", "semantic_model", "steward")
    list_filter = ("rule_category", "dimension", "target_type", "rule_type", "severity", "last_status", "is_active", "tenant")
    search_fields = ("number", "name", "code", "target_column", "description")
    readonly_fields = ("number", "tenant", "last_run_at", "passed_records_count", "failed_records_count", "pass_rate_pct", "created_at", "updated_at")


@admin.register(DataQualityException)
class DataQualityExceptionAdmin(admin.ModelAdmin):
    list_display = ("number", "record_identifier", "target_column", "exception_type", "severity", "status", "remediation_action", "assigned_steward", "is_active", "tenant")
    list_select_related = ("rule", "profile", "warehouse_table", "semantic_model", "assigned_steward", "resolved_by")
    list_filter = ("exception_type", "severity", "status", "remediation_action", "is_active", "tenant")
    search_fields = ("number", "record_identifier", "target_column", "invalid_value", "expected_condition", "resolution_notes")
    readonly_fields = ("number", "tenant", "resolved_at", "created_at", "updated_at")


@admin.register(DataQualityScorecard)
class DataQualityScorecardAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "scope_type", "overall_quality_score", "grade", "health_status", "meets_sla", "total_rules_evaluated", "open_exceptions_count", "is_active", "tenant")
    list_select_related = ("warehouse_table", "semantic_model", "data_mart", "org_unit", "steward")
    list_filter = ("scope_type", "grade", "health_status", "meets_sla", "evaluation_period", "is_active", "tenant")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "tenant", "overall_quality_score", "completeness_score", "accuracy_score", "consistency_score", "timeliness_score", "uniqueness_score", "validity_score", "grade", "health_status", "meets_sla", "total_rules_evaluated", "rules_passed_count", "rules_failed_count", "open_exceptions_count", "critical_exceptions_count", "last_calculated_at", "created_at", "updated_at")


@admin.register(MdmGoldenRecord)
class MdmGoldenRecordAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "domain", "status", "trust_tier", "confidence_score", "source_record_count", "assigned_steward", "is_active", "tenant")
    list_select_related = ("party", "party_role", "item", "asset", "warehouse_table", "assigned_steward", "merged_into_record")
    list_filter = ("domain", "status", "trust_tier", "is_active", "tenant")
    search_fields = ("number", "name", "code", "tax_id", "primary_email", "primary_phone")
    readonly_fields = ("number", "tenant", "merged_into_record", "merged_at", "reviewed_by", "reviewed_at", "created_at", "updated_at")


@admin.register(MdmSurvivorshipRule)
class MdmSurvivorshipRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "domain", "target_field", "survivorship_strategy", "match_algorithm", "match_threshold_pct", "auto_merge_threshold_pct", "priority_order", "is_active", "tenant")
    list_select_related = ("steward",)
    list_filter = ("domain", "survivorship_strategy", "match_algorithm", "is_active", "tenant")
    search_fields = ("number", "name", "code", "target_field", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(MdmHierarchyNode)
class MdmHierarchyNodeAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "hierarchy_type", "parent", "level", "path", "golden_record", "sort_order", "is_active", "tenant")
    list_select_related = ("parent", "golden_record", "party", "org_unit", "item_category")
    list_filter = ("hierarchy_type", "level", "is_active", "tenant")
    search_fields = ("number", "name", "code", "path", "description")
    readonly_fields = ("number", "tenant", "level", "path", "created_at", "updated_at")


@admin.register(MdmReferenceCode)
class MdmReferenceCodeAdmin(admin.ModelAdmin):
    list_display = ("number", "code_set", "canonical_code", "canonical_name", "source_system", "source_code", "status", "is_active", "tenant")
    list_select_related = ("superseded_by",)
    list_filter = ("code_set", "status", "source_system", "is_active", "tenant")
    search_fields = ("number", "code_set", "canonical_code", "canonical_name", "source_code")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")
