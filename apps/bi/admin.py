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
