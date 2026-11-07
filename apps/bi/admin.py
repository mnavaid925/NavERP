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
    CatalogAsset,
    CatalogLineageEdge,
    DataGovernancePolicy,
    CatalogTrustEndorsement,
    BiDashboard,
    BiDashboardWidget,
    BiDashboardBookmark,
    BiDashboardFilter,
    ReportDefinition,
    ReportParameter,
    ReportExecution,
    ReportDrillPath,
    AdHocQuery,
    AdHocCalculatedField,
    DataBlendDefinition,
    SavedAnalysisView,
    KpiDefinition,
    PerformanceScorecard,
    ScorecardKpiAssignment,
    StrategicObjective,
    OlapCube,
    PivotAnalysisView,
    WhatIfScenario,
    ScenarioWritebackCell,
    PredictiveModel,
    ForecastExecution,
    StatisticalAnomaly,
    OptimizationScenario,
    AugmentedInsight,
    SmartDataPrepSuggestion,
    TextSentimentAnalysis,
    AnalyticsRecommendation,
    NaturalLanguageQuery,
    BiConversationSession,
    NarrativeExplanation,
    SearchDiscoveryIndex,
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
    list_display = ("number", "pipeline", "trigger_type", "status", "duration_seconds", "records_extracted", "records_inserted", "records_rejected", "started_at")
    list_filter = ("status", "trigger_type", "tenant")
    search_fields = ("number", "pipeline__name", "error_message", "log_summary")
    readonly_fields = ("number", "started_at", "ended_at", "created_at", "updated_at")


@admin.register(EtlPipeline)
class EtlPipelineAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "target_table", "target_layer", "trigger_type", "status", "tenant", "created_at")
    list_filter = ("status", "target_layer", "trigger_type", "tenant")
    search_fields = ("number", "name", "source_staging_table", "target_table", "description")
    readonly_fields = ("number", "created_at", "updated_at", "last_run_at")


@admin.register(TransformationStep)
class TransformationStepAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "sequence", "name", "step_type", "status", "is_blocking", "tenant")
    list_select_related = ("pipeline",)
    list_filter = ("step_type", "status", "is_blocking", "tenant")
    search_fields = ("number", "name", "pipeline__name", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(EtlPipelineVersion)
class EtlPipelineVersionAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "version_number", "environment", "status", "promoted_by", "promoted_at", "tenant")
    list_select_related = ("pipeline", "promoted_by")
    list_filter = ("environment", "status", "tenant")
    search_fields = ("number", "version_number", "pipeline__name", "changelog")
    readonly_fields = ("number", "created_at", "updated_at", "promoted_at")


@admin.register(EtlPipelineRun)
class EtlPipelineRunAdmin(admin.ModelAdmin):
    list_display = ("number", "pipeline", "trigger_type", "status", "duration_seconds", "records_in", "records_out", "records_rejected", "sla_missed", "started_at")
    list_select_related = ("pipeline",)
    list_filter = ("status", "trigger_type", "sla_missed", "is_backfill", "tenant")
    search_fields = ("number", "pipeline__name", "error_message")
    readonly_fields = ("number", "started_at", "ended_at", "created_at")


@admin.register(DataMart)
class DataMartAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "subject_area", "access_tier", "certification_status", "refresh_cadence", "is_active", "tenant")
    list_select_related = ("org_unit", "owner", "steward")
    list_filter = ("subject_area", "certification_status", "access_tier", "refresh_cadence", "is_active", "tenant")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(LakehouseZone)
class LakehouseZoneAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "zone_type", "storage_backend", "default_format", "is_read_only", "is_active", "tenant")
    list_filter = ("zone_type", "storage_backend", "default_format", "is_read_only", "is_active", "tenant")
    search_fields = ("number", "name", "code", "base_uri_path", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(WarehouseStoragePolicy)
class WarehouseStoragePolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "partition_strategy", "partition_key", "compression_codec", "hot_tier_days", "warm_tier_days", "cold_tier_days", "is_default", "is_active", "tenant")
    list_filter = ("partition_strategy", "compression_codec", "vacuum_cadence", "is_default", "is_active", "tenant")
    search_fields = ("number", "name", "partition_key", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(WarehouseTable)
class WarehouseTableAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "table_name", "table_type", "schema_type", "grain", "lakehouse_zone", "data_mart", "row_count", "is_active", "tenant")
    list_select_related = ("lakehouse_zone", "data_mart", "storage_policy")
    list_filter = ("table_type", "schema_type", "grain", "is_conformed_dimension", "is_active", "tenant")
    search_fields = ("number", "name", "table_name", "primary_key_column", "natural_key_column")
    readonly_fields = ("number", "row_count", "compressed_bytes", "compression_ratio", "last_analyzed_at", "created_at", "updated_at")


@admin.register(SemanticModel)
class SemanticModelAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "model_type", "warehouse_table", "data_mart", "scd_type", "certification_status", "is_active", "tenant")
    list_select_related = ("warehouse_table", "data_mart", "owner", "certified_by")
    list_filter = ("model_type", "scd_type", "certification_status", "access_tier", "is_conformed_dimension", "is_virtual_view", "is_active", "tenant")
    search_fields = ("number", "name", "code", "primary_key_column", "natural_key_columns", "description")
    readonly_fields = ("number", "tenant", "source_fingerprint", "last_introspected_at", "certified_at", "created_at", "updated_at")


@admin.register(BusinessGlossaryTerm)
class BusinessGlossaryTermAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "domain_category", "steward", "org_unit", "certification_status", "is_active", "tenant")
    list_select_related = ("steward", "org_unit", "certified_by")
    list_filter = ("domain_category", "certification_status", "is_active", "tenant")
    search_fields = ("number", "name", "code", "short_definition", "synonyms")
    readonly_fields = ("number", "tenant", "certified_at", "created_at", "updated_at")


@admin.register(CalculatedMeasure)
class CalculatedMeasureAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "semantic_model", "glossary_term", "aggregation_type", "time_intelligence", "format_string", "is_active", "tenant")
    list_select_related = ("semantic_model", "glossary_term")
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


@admin.register(CatalogAsset)
class CatalogAssetAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "domain", "asset_type", "data_sensitivity", "enterprise_tier", "certification_status", "average_rating", "view_count", "data_steward", "is_active", "tenant")
    list_select_related = ("data_steward", "owning_org_unit", "warehouse_table", "semantic_model", "golden_record", "business_glossary_term", "quality_scorecard", "deprecation_replacement")
    list_filter = ("domain", "asset_type", "data_sensitivity", "enterprise_tier", "certification_status", "is_active", "tenant")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "tenant", "view_count", "average_rating", "created_at", "updated_at")


@admin.register(CatalogLineageEdge)
class CatalogLineageEdgeAdmin(admin.ModelAdmin):
    list_display = ("number", "upstream_asset", "downstream_asset", "lineage_type", "impact_criticality", "upstream_column", "downstream_column", "is_automated_extraction", "is_active", "tenant")
    list_select_related = ("upstream_asset", "downstream_asset", "etl_pipeline", "transformation_step")
    list_filter = ("lineage_type", "impact_criticality", "is_automated_extraction", "is_active", "tenant")
    search_fields = ("number", "upstream_asset__name", "downstream_asset__name", "upstream_column", "downstream_column", "transformation_rule")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(DataGovernancePolicy)
class DataGovernancePolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "policy_type", "regulatory_framework", "enforcement_level", "retention_period_days", "masking_algorithm", "policy_owner", "effective_date", "is_active", "tenant")
    list_select_related = ("policy_owner",)
    list_filter = ("policy_type", "regulatory_framework", "enforcement_level", "masking_algorithm", "is_active", "tenant")
    search_fields = ("number", "name", "code", "compliance_notes", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(CatalogTrustEndorsement)
class CatalogTrustEndorsementAdmin(admin.ModelAdmin):
    list_display = ("number", "asset", "endorsement_type", "verdict", "rating_value", "attested_by", "attested_at", "valid_until", "is_active", "tenant")
    list_select_related = ("asset", "attested_by")
    list_filter = ("endorsement_type", "verdict", "is_active", "tenant")
    search_fields = ("number", "asset__name", "review_comments")
    readonly_fields = ("number", "tenant", "attested_at", "created_at", "updated_at")


@admin.register(BiDashboard)
class BiDashboardAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "slug", "category", "layout_type", "theme", "is_published", "is_default", "view_count", "tenant")
    list_select_related = ("created_by", "org_unit")
    list_filter = ("category", "layout_type", "theme", "is_published", "is_default", "is_active", "tenant")
    search_fields = ("number", "title", "slug", "description")
    readonly_fields = ("number", "tenant", "view_count", "last_viewed_at", "created_at", "updated_at")


@admin.register(BiDashboardWidget)
class BiDashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "dashboard", "widget_type", "aggregation_type", "pos_x", "pos_y", "width_cols", "height_rows", "is_active", "tenant")
    list_select_related = ("dashboard", "semantic_model", "calculated_measure", "warehouse_table")
    list_filter = ("widget_type", "aggregation_type", "is_active", "tenant")
    search_fields = ("number", "title", "subtitle", "dashboard__title")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(BiDashboardBookmark)
class BiDashboardBookmarkAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "dashboard", "user", "is_default", "is_shared", "view_count", "tenant")
    list_select_related = ("dashboard", "user")
    list_filter = ("is_default", "is_shared", "is_active", "tenant")
    search_fields = ("number", "name", "dashboard__title", "description")
    readonly_fields = ("number", "tenant", "view_count", "last_viewed_at", "created_at", "updated_at")


@admin.register(BiDashboardFilter)
class BiDashboardFilterAdmin(admin.ModelAdmin):
    list_display = ("number", "filter_label", "filter_key", "dashboard", "filter_type", "target_field", "order", "is_required", "is_active", "tenant")
    list_select_related = ("dashboard",)
    list_filter = ("filter_type", "options_source", "is_required", "is_active", "tenant")
    search_fields = ("number", "filter_label", "filter_key", "target_field", "dashboard__title")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(ReportDefinition)
class ReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "category", "report_type", "paper_size", "orientation", "status", "is_prebuilt_template", "tenant")
    list_select_related = ("tenant", "semantic_model", "warehouse_table", "org_unit")
    list_filter = ("category", "report_type", "paper_size", "orientation", "status", "is_prebuilt_template", "is_active", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(ReportParameter)
class ReportParameterAdmin(admin.ModelAdmin):
    list_display = ("number", "prompt_label", "parameter_name", "report", "parameter_type", "choices_source", "prompt_order", "is_required", "is_active", "tenant")
    list_select_related = ("report", "tenant")
    list_filter = ("parameter_type", "choices_source", "is_required", "is_hidden", "is_active", "tenant")
    search_fields = ("number", "prompt_label", "parameter_name", "report__name")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = ("number", "report", "executed_by", "execution_mode", "output_format", "execution_status", "duration_ms", "row_count", "started_at", "tenant")
    list_select_related = ("report", "executed_by", "tenant")
    list_filter = ("execution_mode", "output_format", "execution_status", "is_cached", "tenant")
    search_fields = ("number", "report__name", "executed_by__username", "output_file_name")
    readonly_fields = ("number", "tenant", "started_at", "created_at", "updated_at")


@admin.register(ReportDrillPath)
class ReportDrillPathAdmin(admin.ModelAdmin):
    list_display = ("number", "drill_label", "source_report", "source_field", "target_type", "target_report", "sort_order", "is_enabled", "tenant")
    list_select_related = ("source_report", "target_report", "tenant")
    list_filter = ("target_type", "is_enabled", "tenant")
    search_fields = ("number", "drill_label", "source_field", "source_report__name", "target_report__name")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(AdHocQuery)
class AdHocQueryAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "source_type", "visualization_type", "row_limit", "status", "row_count", "tenant")
    list_select_related = ("tenant", "semantic_model", "warehouse_table", "data_blend", "created_by")
    list_filter = ("source_type", "visualization_type", "status", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "last_executed_at", "execution_duration_ms", "row_count", "created_at", "updated_at")


@admin.register(AdHocCalculatedField)
class AdHocCalculatedFieldAdmin(admin.ModelAdmin):
    list_display = ("number", "display_label", "field_name", "query", "return_type", "aggregation_mode", "is_valid", "tenant")
    list_select_related = ("tenant", "query")
    list_filter = ("return_type", "aggregation_mode", "is_valid", "tenant")
    search_fields = ("number", "display_label", "field_name", "formula_expression", "query__name")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(DataBlendDefinition)
class DataBlendDefinitionAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "join_type", "cardinality", "status", "tenant")
    list_select_related = ("tenant", "primary_semantic_model", "secondary_semantic_model", "primary_warehouse_table", "secondary_warehouse_table")
    list_filter = ("join_type", "cardinality", "status", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(SavedAnalysisView)
class SavedAnalysisViewAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "query", "sharing_scope", "org_unit", "is_template", "is_favorite", "view_count", "tenant")
    list_select_related = ("tenant", "query", "org_unit", "parent_view")
    list_filter = ("sharing_scope", "is_template", "is_favorite", "tenant")
    search_fields = ("number", "name", "slug", "description", "share_token")
    readonly_fields = ("number", "tenant", "share_token", "view_count", "last_viewed_at", "created_at", "updated_at")


@admin.register(OlapCube)
class OlapCubeAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "storage_mode", "status", "time_intelligence_enabled", "last_refreshed_at", "tenant")
    list_select_related = ("tenant", "semantic_model", "warehouse_table", "default_hierarchy", "created_by")
    list_filter = ("storage_mode", "status", "time_intelligence_enabled", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "last_refreshed_at", "created_at", "updated_at")


@admin.register(PivotAnalysisView)
class PivotAnalysisViewAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "cube", "total_position", "drill_through_enabled", "status", "is_favorite", "tenant")
    list_select_related = ("tenant", "cube", "created_by")
    list_filter = ("status", "is_favorite", "drill_through_enabled", "total_position", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(WhatIfScenario)
class WhatIfScenarioAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "cube", "fiscal_period", "default_disaggregation", "status", "total_variance_amount", "tenant")
    list_select_related = ("tenant", "cube", "baseline_budget", "fiscal_period", "created_by", "committed_by")
    list_filter = ("status", "default_disaggregation", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "total_baseline_amount", "total_adjusted_amount", "total_variance_amount", "committed_at", "committed_by", "created_at", "updated_at")


@admin.register(ScenarioWritebackCell)
class ScenarioWritebackCellAdmin(admin.ModelAdmin):
    list_display = ("number", "scenario", "gl_account", "org_unit", "baseline_value", "adjusted_value", "variance_amount", "is_committed", "tenant")
    list_select_related = ("tenant", "scenario", "gl_account", "org_unit", "committed_budget_line", "created_by")
    list_filter = ("spread_method", "is_committed", "tenant")
    search_fields = ("number", "scenario__name", "gl_account__name", "gl_account__code", "commentary")
    readonly_fields = ("number", "tenant", "variance_amount", "created_at", "updated_at")


@admin.register(KpiDefinition)
class KpiDefinitionAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "perspective", "target_direction", "tracking_frequency", "current_value", "target_value", "status", "tenant")
    list_select_related = ("tenant", "semantic_measure", "department", "owner")
    list_filter = ("perspective", "target_direction", "tracking_frequency", "calculation_type", "status", "is_active", "tenant")
    search_fields = ("number", "code", "name", "slug", "description", "category")
    readonly_fields = ("number", "tenant", "last_calculated_at", "created_at", "updated_at")


@admin.register(PerformanceScorecard)
class PerformanceScorecardAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "scorecard_type", "review_period", "fiscal_year", "overall_score", "overall_rag_status", "status", "tenant")
    list_select_related = ("tenant", "owner", "org_unit")
    list_filter = ("scorecard_type", "review_period", "fiscal_year", "overall_rag_status", "status", "is_default", "is_published", "tenant")
    search_fields = ("number", "name", "slug", "description")
    readonly_fields = ("number", "tenant", "overall_score", "overall_rag_status", "last_recalculated_at", "created_at", "updated_at")


@admin.register(ScorecardKpiAssignment)
class ScorecardKpiAssignmentAdmin(admin.ModelAdmin):
    list_display = ("number", "scorecard", "kpi", "perspective", "weight", "target_value", "actual_value", "variance", "rag_status", "trend_direction", "tenant")
    list_select_related = ("tenant", "scorecard", "kpi", "objective")
    list_filter = ("perspective", "rag_status", "trend_direction", "tenant")
    search_fields = ("number", "scorecard__name", "kpi__name", "kpi__code", "manager_notes")
    readonly_fields = ("number", "tenant", "variance", "variance_percentage", "rag_status", "trend_direction", "normalized_score", "benchmark_gap", "evaluated_at", "created_at", "updated_at")


@admin.register(StrategicObjective)
class StrategicObjectiveAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "perspective", "parent_objective", "alignment_score", "rag_status", "status", "tenant")
    list_select_related = ("tenant", "parent_objective", "owner", "org_unit")
    list_filter = ("perspective", "rag_status", "status", "tenant")
    search_fields = ("number", "code", "name", "slug", "statement_of_intent")
    readonly_fields = ("number", "tenant", "alignment_score", "rag_status", "created_at", "updated_at")


@admin.register(AugmentedInsight)
class AugmentedInsightAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "insight_type", "metric_name", "variance_percentage", "impact_direction", "severity", "status", "tenant")
    list_select_related = ("tenant", "semantic_model", "kpi_definition", "warehouse_table", "created_by")
    list_filter = ("insight_type", "impact_direction", "severity", "status", "tenant")
    search_fields = ("number", "title", "metric_name", "dimension_name", "dimension_value", "narrative_summary")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(SmartDataPrepSuggestion)
class SmartDataPrepSuggestionAdmin(admin.ModelAdmin):
    list_display = ("number", "suggestion_type", "target_table", "target_column", "related_table", "related_column", "confidence_score", "status", "tenant")
    list_select_related = ("tenant", "target_table", "related_table", "reviewed_by")
    list_filter = ("suggestion_type", "status", "tenant")
    search_fields = ("number", "target_column", "related_column", "rationale")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(TextSentimentAnalysis)
class TextSentimentAnalysisAdmin(admin.ModelAdmin):
    list_display = ("number", "source_reference", "source_type", "sentiment_category", "polarity_score", "subjectivity_score", "linked_party", "tenant")
    list_select_related = ("tenant", "linked_party", "linked_org_unit")
    list_filter = ("source_type", "sentiment_category", "tenant")
    search_fields = ("number", "source_reference", "text_content")
    readonly_fields = ("number", "tenant", "analyzed_at", "created_at", "updated_at")


@admin.register(AnalyticsRecommendation)
class AnalyticsRecommendationAdmin(admin.ModelAdmin):
    list_display = ("number", "target_title", "recommendation_type", "user", "reason", "affinity_score", "status", "tenant")
    list_select_related = ("tenant", "user", "dashboard", "report", "kpi", "semantic_model")
    list_filter = ("recommendation_type", "reason", "status", "tenant")
    search_fields = ("number", "target_title", "target_url", "rationale_text", "user__username")
    readonly_fields = ("number", "tenant", "created_at", "updated_at")


@admin.register(PredictiveModel)
class PredictiveModelAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'problem_type', 'algorithm', 'target_metric', 'accuracy_metric_name', 'accuracy_metric_value', 'status', 'tenant')
    list_select_related = ('tenant', 'semantic_model', 'warehouse_table', 'created_by')
    list_filter = ('problem_type', 'algorithm', 'status', 'is_active', 'tenant')
    search_fields = ('number', 'name', 'slug', 'target_metric', 'description')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at')


@admin.register(ForecastExecution)
class ForecastExecutionAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'model', 'cadence', 'horizon_periods', 'confidence_level', 'trend_direction', 'mape_score', 'status', 'tenant')
    list_select_related = ('tenant', 'model', 'semantic_model', 'kpi_definition', 'executed_by')
    list_filter = ('cadence', 'confidence_level', 'trend_direction', 'status', 'tenant')
    search_fields = ('number', 'name', 'notes')
    readonly_fields = ('number', 'tenant', 'executed_at')


@admin.register(StatisticalAnomaly)
class StatisticalAnomalyAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'metric_name', 'anomaly_type', 'detection_method', 'severity', 'observed_value', 'expected_value', 'triage_status', 'tenant')
    list_select_related = ('tenant', 'model', 'semantic_model', 'kpi_definition', 'assigned_to')
    list_filter = ('anomaly_type', 'detection_method', 'severity', 'triage_status', 'tenant')
    search_fields = ('number', 'title', 'metric_name', 'resolution_notes')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at')


@admin.register(OptimizationScenario)
class OptimizationScenarioAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'objective_type', 'target_metric_name', 'baseline_value', 'optimal_value', 'projected_lift_percentage', 'solver_status', 'tenant')
    list_select_related = ('tenant', 'kpi_definition', 'owner')
    list_filter = ('objective_type', 'solver_algorithm', 'solver_status', 'status', 'tenant')
    search_fields = ('number', 'name', 'slug', 'target_metric_name', 'description')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at')


@admin.register(NaturalLanguageQuery)
class NaturalLanguageQueryAdmin(admin.ModelAdmin):
    list_display = ('number', 'query_text', 'input_modality', 'intent_type', 'chart_type', 'confidence_score', 'execution_status', 'user_rating', 'tenant')
    list_select_related = ('tenant', 'semantic_model', 'warehouse_table', 'kpi_definition', 'conversation_session', 'user')
    list_filter = ('input_modality', 'intent_type', 'chart_type', 'execution_status', 'user_rating', 'tenant')
    search_fields = ('number', 'query_text', 'generated_sql', 'user_feedback_notes')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at')


@admin.register(BiConversationSession)
class BiConversationSessionAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'user', 'session_status', 'is_pinned', 'message_count', 'last_interaction_at', 'tenant')
    list_select_related = ('tenant', 'user', 'primary_semantic_model', 'primary_dashboard')
    list_filter = ('session_status', 'is_pinned', 'tenant')
    search_fields = ('number', 'title', 'user__username')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at', 'last_interaction_at')


@admin.register(NarrativeExplanation)
class NarrativeExplanationAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'headline', 'target_artifact_type', 'narrative_style', 'language', 'status', 'tenant')
    list_select_related = ('tenant', 'dashboard', 'report', 'kpi', 'query', 'insight', 'created_by')
    list_filter = ('target_artifact_type', 'narrative_style', 'status', 'tenant')
    search_fields = ('number', 'title', 'headline', 'narrative_body')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at')


@admin.register(SearchDiscoveryIndex)
class SearchDiscoveryIndexAdmin(admin.ModelAdmin):
    list_display = ('number', 'asset_name', 'asset_type', 'category', 'relevance_weight', 'search_hit_count', 'view_count', 'is_featured', 'is_verified', 'tenant')
    list_select_related = ('tenant', 'semantic_model', 'dashboard', 'report', 'kpi', 'warehouse_table', 'glossary_term')
    list_filter = ('asset_type', 'is_featured', 'is_verified', 'category', 'tenant')
    search_fields = ('number', 'asset_name', 'target_url', 'description', 'search_keywords')
    readonly_fields = ('number', 'tenant', 'created_at', 'updated_at')
