from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.bi.models.DataIntegration.CdcSyncConfigs import CdcSyncConfig
from apps.bi.models.DataIntegration.DataSourceConnectors import DataSourceConnector
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.models.DataIntegration.IngestionRuns import IngestionRun
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.DataWarehouse.LakehouseZones import LakehouseZone
from apps.bi.models.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicy
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.EtlPipelines.EtlPipelineRuns import EtlPipelineRun
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.EtlPipelineVersions import EtlPipelineVersion
from apps.bi.models.EtlPipelines.TransformationSteps import TransformationStep
from apps.bi.models.DataQuality.DataQualityExceptions import DataQualityException
from apps.bi.models.DataQuality.DataQualityProfiles import DataQualityProfile
from apps.bi.models.DataQuality.DataQualityRules import DataQualityRule
from apps.bi.models.DataQuality.DataQualityScorecards import DataQualityScorecard
from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.bi.models.SemanticLayer.DrillHierarchies import DrillHierarchy
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Seed demo data for Business Intelligence (BI) Module 10 (10.1 Ingestion, 10.2 ETL/ELT Pipelines, 10.3 Data Warehouse & Storage, 10.4 Data Modeling & Semantic Layer, and 10.5 Data Quality & Cleansing)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing BI demo data before seeding.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Seeding Business Intelligence (BI) demo data...")
        flush = options.get("flush", False)
        if flush:
            self.stdout.write("Flushing existing BI data...")
            with transaction.atomic():
                DataQualityScorecard.objects.all().delete()
                DataQualityException.objects.all().delete()
                DataQualityRule.objects.all().delete()
                DataQualityProfile.objects.all().delete()
                DrillHierarchy.objects.all().delete()
                CalculatedMeasure.objects.all().delete()
                BusinessGlossaryTerm.objects.all().delete()
                SemanticModel.objects.all().delete()
                WarehouseTable.objects.all().delete()
                WarehouseStoragePolicy.objects.all().delete()
                LakehouseZone.objects.all().delete()
                DataMart.objects.all().delete()
                EtlPipelineRun.objects.all().delete()
                TransformationStep.objects.all().delete()
                EtlPipelineVersion.objects.all().delete()
                EtlPipeline.objects.all().delete()
                IngestionRun.objects.all().delete()
                CdcSyncConfig.objects.all().delete()
                IngestionPipeline.objects.all().delete()
                DataSourceConnector.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Existing BI data flushed successfully."))

        tenants = Tenant.objects.all()
        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No tenants found. Run seed_accounts / seed_core first."))
            return

        User = get_user_model()
        now = timezone.now()

        for tenant in tenants:
            admin_user = User.objects.filter(tenant=tenant).first()

            # --- 10.1 Data Integration & Ingestion Seeding ---
            if not DataSourceConnector.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    # 1. DataSourceConnectors
                    erp_connector, _ = DataSourceConnector.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} Internal ERP Master DB",
                        defaults={
                            "connector_type": "internal_erp",
                            "status": "active",
                            "connection_config": {"engine": "django.db.backends.mysql", "scope": "full_read_replica"},
                            "test_status": "success",
                            "test_message": "Internal ERP database connectivity verified (latency 1.2ms).",
                            "last_tested_at": now,
                            "description": "Primary internal NavERP operational database read replica for analytical ingestion.",
                            "created_by": admin_user,
                        },
                    )

                    pg_connector, _ = DataSourceConnector.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} Enterprise PostgreSQL Replica",
                        defaults={
                            "connector_type": "database_rdbms",
                            "status": "active",
                            "connection_config": {
                                "host": "postgres-read.analytics.internal",
                                "port": 5432,
                                "database": "enterprise_dw",
                                "ssl": True,
                            },
                            "test_status": "success",
                            "test_message": "PostgreSQL connection pool ready (pool_size=10, latency 4.8ms).",
                            "last_tested_at": now,
                            "description": "Enterprise transactional and CRM reporting replica.",
                            "created_by": admin_user,
                        },
                    )

                    s3_connector, _ = DataSourceConnector.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} S3 Analytics Drop Bucket",
                        defaults={
                            "connector_type": "cloud_storage",
                            "status": "active",
                            "connection_config": {
                                "provider": "aws_s3",
                                "bucket_name": f"{getattr(tenant, 'slug', tenant.name.lower().replace(' ', '-'))}-analytics-raw-ingress",
                                "region": "us-east-1",
                                "prefix": "incoming/",
                            },
                            "test_status": "success",
                            "test_message": "S3 bucket accessible with ListBucket and GetObject permissions.",
                            "last_tested_at": now,
                            "description": "Amazon S3 raw ingestion staging bucket for batch files and event streams.",
                            "created_by": admin_user,
                        },
                    )

                    webhook_connector, _ = DataSourceConnector.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} Streaming Event Webhook Gateway",
                        defaults={
                            "connector_type": "webhook_push",
                            "status": "active",
                            "connection_config": {"protocol": "https", "ingress_format": "application/json"},
                            "test_status": "success",
                            "test_message": "Inbound webhook gateway endpoint healthy and responsive.",
                            "last_tested_at": now,
                            "description": "Real-time streaming push endpoint for external commerce and payment events.",
                            "created_by": admin_user,
                        },
                    )

                    # 2. IngestionPipelines
                    pipe_invoices, _ = IngestionPipeline.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} Daily General Ledger Invoices",
                        defaults={
                            "connector": erp_connector,
                            "ingestion_mode": "batch_scheduled",
                            "source_entity": "accounting_invoice",
                            "target_staging_table": "stg_accounting_invoices",
                            "schedule_cadence": "daily",
                            "cron_expression": "0 2 * * *",
                            "file_format": "none",
                            "status": "active",
                            "last_run_at": now,
                        },
                    )

                    pipe_s3_clicks, _ = IngestionPipeline.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} S3 Clickstream Telemetry Load",
                        defaults={
                            "connector": s3_connector,
                            "ingestion_mode": "micro_batch",
                            "source_entity": "s3://raw-logs/clicks/*.ndjson",
                            "target_staging_table": "stg_clickstream_events",
                            "schedule_cadence": "every_15_min",
                            "cron_expression": "*/15 * * * *",
                            "file_format": "ndjson",
                            "file_parsing_options": {"has_header": False, "encoding": "utf-8"},
                            "status": "active",
                            "last_run_at": now,
                        },
                    )

                    pipe_orders_webhook, _ = IngestionPipeline.objects.get_or_create(
                        tenant=tenant,
                        name=f"{tenant.name} Streaming Order Events Ingress",
                        defaults={
                            "connector": webhook_connector,
                            "ingestion_mode": "real_time_webhook",
                            "source_entity": "/api/v1/orders/stream",
                            "target_staging_table": "stg_ecommerce_orders",
                            "schedule_cadence": "manual",
                            "file_format": "json",
                            "status": "active",
                            "last_run_at": now,
                        },
                    )

                    # 3. CdcSyncConfig
                    cdc_invoices, _ = CdcSyncConfig.objects.get_or_create(
                        tenant=tenant,
                        pipeline=pipe_invoices,
                        defaults={
                            "capture_method": "query_timestamp",
                            "sync_mode": "incremental_deduped",
                            "primary_key_fields": "id,tenant_id",
                            "cursor_field": "updated_at",
                            "last_cursor_value": now.isoformat(),
                            "last_checkpoint_at": now,
                            "schema_drift_policy": "detect_and_warn",
                            "capture_deletes": True,
                            "soft_delete_field": "is_deleted",
                        },
                    )

                    # 4. IngestionRuns
                    IngestionRun.objects.get_or_create(
                        tenant=tenant,
                        pipeline=pipe_invoices,
                        number="BIJR-00001",
                        defaults={
                            "trigger_type": "scheduled",
                            "status": "completed",
                            "started_at": now,
                            "ended_at": now,
                            "duration_seconds": Decimal("2.45"),
                            "records_extracted": 240,
                            "records_inserted": 238,
                            "records_updated": 0,
                            "records_rejected": 2,
                            "bytes_transferred": 78400,
                            "committed_cursor": now.isoformat(),
                            "log_summary": f"Scheduled nightly run completed. 238 rows committed to {pipe_invoices.target_staging_table}. 2 malformed lines rejected.",
                        },
                    )

                    IngestionRun.objects.get_or_create(
                        tenant=tenant,
                        pipeline=pipe_s3_clicks,
                        number="BIJR-00002",
                        defaults={
                            "trigger_type": "scheduled",
                            "status": "completed",
                            "started_at": now,
                            "ended_at": now,
                            "duration_seconds": Decimal("1.15"),
                            "records_extracted": 850,
                            "records_inserted": 850,
                            "records_updated": 0,
                            "records_rejected": 0,
                            "bytes_transferred": 192000,
                            "committed_cursor": "s3://raw-logs/clicks/part-004.ndjson",
                            "log_summary": f"Micro-batch ingestion complete. All 850 events loaded into {pipe_s3_clicks.target_staging_table}.",
                        },
                    )

                    IngestionRun.objects.get_or_create(
                        tenant=tenant,
                        pipeline=pipe_orders_webhook,
                        number="BIJR-00003",
                        defaults={
                            "trigger_type": "webhook",
                            "status": "completed",
                            "started_at": now,
                            "ended_at": now,
                            "duration_seconds": Decimal("0.35"),
                            "records_extracted": 15,
                            "records_inserted": 15,
                            "records_updated": 0,
                            "records_rejected": 0,
                            "bytes_transferred": 14200,
                            "committed_cursor": "webhook_event_ack_20261103",
                            "log_summary": "Streaming webhook batch processed successfully.",
                        },
                    )
                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Data Integration for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI data source connectors already seeded for tenant: {tenant.name}")

            # --- 10.2 ETL/ELT & Data Pipelines Seeding ---
            if not EtlPipeline.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    pipe_invoices = IngestionPipeline.objects.filter(tenant=tenant).first()
                pipe_s3_clicks = IngestionPipeline.objects.filter(tenant=tenant, ingestion_mode="micro_batch").first()

                # 1. EtlPipeline
                pipe_sales_mart, _ = EtlPipeline.objects.get_or_create(
                    tenant=tenant,
                    name=f"{tenant.name} Sales Mart Aggregation Pipeline",
                    defaults={
                        "source_ingestion_pipeline": pipe_invoices,
                        "source_staging_table": "stg_accounting_invoices",
                        "target_table": "fct_monthly_sales",
                        "target_layer": "data_mart",
                        "trigger_type": "scheduled_cron",
                        "cron_expression": "0 3 * * *",
                        "upstream_dependencies": ["BING-00001"],
                        "retry_policy": {"max_retries": 3, "retry_delay_seconds": 60, "backoff_factor": 2},
                        "sla_timeout_seconds": 3600,
                        "alert_on_sla_miss": True,
                        "status": "active",
                        "description": "Multi-step analytical transformation joining customer masters and calculating monthly margin metrics.",
                        "created_by": admin_user,
                        "last_run_at": now,
                    },
                )

                pipe_clickstream_summary, _ = EtlPipeline.objects.get_or_create(
                    tenant=tenant,
                    name=f"{tenant.name} Clickstream Session Engagement Aggregator",
                    defaults={
                        "source_ingestion_pipeline": pipe_s3_clicks,
                        "source_staging_table": "stg_clickstream_events",
                        "target_table": "fct_session_engagement",
                        "target_layer": "warehouse_fact",
                        "trigger_type": "event_on_ingest",
                        "upstream_dependencies": ["BING-00002"],
                        "retry_policy": {"max_retries": 2, "retry_delay_seconds": 30},
                        "sla_timeout_seconds": 1800,
                        "alert_on_sla_miss": True,
                        "status": "active",
                        "description": "Transforms raw JSON event stream into sessionized engagement metrics.",
                        "created_by": admin_user,
                        "last_run_at": now,
                    },
                )

                # 2. TransformationSteps for Sales Mart
                step1, _ = TransformationStep.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_sales_mart,
                    sequence=1,
                    defaults={
                        "name": "Join Customer Master & Accounting Period",
                        "step_type": "join",
                        "upstream_step_ids": [],
                        "step_config": {
                            "join_type": "inner",
                            "left_key": "customer_id",
                            "right_key": "id",
                            "right_table": "core_party",
                        },
                        "status": "active",
                        "is_blocking": True,
                        "canvas_x": 100,
                        "canvas_y": 150,
                        "description": "Enriches invoice records with customer master classifications.",
                    },
                )

                step2, _ = TransformationStep.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_sales_mart,
                    sequence=2,
                    defaults={
                        "name": "Calculate Net Margin & Apply Tax Rates",
                        "step_type": "derived_column",
                        "upstream_step_ids": [step1.number],
                        "step_config": {
                            "formula": "total_amount - tax_amount",
                            "output_column": "net_revenue",
                            "margin_rate": "(net_revenue - cogs) / net_revenue",
                        },
                        "status": "active",
                        "is_blocking": True,
                        "canvas_x": 350,
                        "canvas_y": 150,
                        "description": "Calculates revenue metrics, margins, and financial KPIs.",
                    },
                )

                step3, _ = TransformationStep.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_sales_mart,
                    sequence=3,
                    defaults={
                        "name": "Aggregate Revenue by Customer & Fiscal Period",
                        "step_type": "aggregate",
                        "upstream_step_ids": [step2.number],
                        "step_config": {
                            "group_by": ["customer_id", "fiscal_period"],
                            "metrics": ["sum(net_revenue)", "sum(tax_amount)", "count(invoice_id)"],
                        },
                        "status": "active",
                        "is_blocking": True,
                        "canvas_x": 600,
                        "canvas_y": 150,
                        "description": "Aggregates revenue totals into warehouse analytical fact mart.",
                    },
                )

                # TransformationStep for Clickstream Summary
                step_click, _ = TransformationStep.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_clickstream_summary,
                    sequence=1,
                    defaults={
                        "name": "Matrix Pivot Events by Session ID",
                        "step_type": "pivot",
                        "upstream_step_ids": [],
                        "step_config": {
                            "pivot_column": "event_type",
                            "value_column": "duration_ms",
                            "aggregation": "sum",
                        },
                        "status": "active",
                        "is_blocking": True,
                        "canvas_x": 150,
                        "canvas_y": 150,
                        "description": "Pivots raw event types into columnar session metrics.",
                    },
                )

                # 3. EtlPipelineVersion
                v1_sales, _ = EtlPipelineVersion.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_sales_mart,
                    version_number="v1.0.0",
                    defaults={
                        "environment": "production",
                        "status": "published",
                        "promoted_by": admin_user,
                        "promoted_at": now,
                        "changelog": "Initial production release of Sales Mart DAG with customer join and margin calculations.",
                        "dag_definition": {
                            "pipeline": pipe_sales_mart.name,
                            "steps_count": 3,
                            "target": pipe_sales_mart.target_table,
                        },
                    },
                )
                pipe_sales_mart.active_version = v1_sales
                pipe_sales_mart.save(update_fields=["active_version"])

                # 4. EtlPipelineRun
                EtlPipelineRun.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_sales_mart,
                    number="BEXR-00001",
                    defaults={
                        "version": v1_sales,
                        "trigger_type": "scheduled",
                        "status": "completed",
                        "started_at": now,
                        "ended_at": now,
                        "duration_seconds": Decimal("14.50"),
                        "records_in": 1200,
                        "records_transformed": 1195,
                        "records_out": 1195,
                        "records_rejected": 5,
                        "bytes_processed": 450000,
                        "sla_missed": False,
                        "step_progress": {"join": "success", "derived_column": "success", "aggregate": "success"},
                        "execution_log": f"[INFO] ETL Pipeline {pipe_sales_mart.number} completed successfully. 1195 rows written to {pipe_sales_mart.target_table}.",
                    },
                )

                EtlPipelineRun.objects.get_or_create(
                    tenant=tenant,
                    pipeline=pipe_sales_mart,
                    number="BEXR-00002",
                    defaults={
                        "version": v1_sales,
                        "trigger_type": "manual",
                        "status": "running",
                        "started_at": now,
                        "duration_seconds": Decimal("4.20"),
                        "records_in": 500,
                        "records_transformed": 490,
                        "records_out": 490,
                        "records_rejected": 10,
                        "bytes_processed": 180000,
                        "sla_missed": False,
                        "step_progress": {"join": "success", "derived_column": "in_progress"},
                        "execution_log": "[INFO] Worker actively executing Step #2 derived column transformation.",
                    },
                )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI ETL Pipelines for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI ETL pipelines already seeded for tenant: {tenant.name}")

            # --- 10.3 Data Warehouse & Storage Seeding ---
            if not DataMart.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    # 1. DataMarts
                    mart_finance, _ = DataMart.objects.get_or_create(
                        tenant=tenant,
                        code="finance",
                        defaults={
                            "name": "Finance & Accounting Mart",
                            "subject_area": "finance",
                            "owner": admin_user,
                            "steward": admin_user,
                            "access_tier": "department",
                            "certification_status": "certified",
                            "refresh_cadence": "daily",
                            "description": "General ledger, receivables, payables, and fiscal budget analytics.",
                            "is_active": True,
                        },
                    )

                    mart_sales, _ = DataMart.objects.get_or_create(
                        tenant=tenant,
                        code="sales",
                        defaults={
                            "name": "Sales & CRM Mart",
                            "subject_area": "sales",
                            "owner": admin_user,
                            "steward": admin_user,
                            "access_tier": "department",
                            "certification_status": "certified",
                            "refresh_cadence": "hourly",
                            "description": "Sales pipelines, opportunity conversion rates, and revenue attainment.",
                            "is_active": True,
                        },
                    )

                    mart_scm, _ = DataMart.objects.get_or_create(
                        tenant=tenant,
                        code="supply_chain",
                        defaults={
                            "name": "Supply Chain & Logistics Mart",
                            "subject_area": "supply_chain",
                            "owner": admin_user,
                            "steward": admin_user,
                            "access_tier": "department",
                            "certification_status": "in_review",
                            "refresh_cadence": "daily",
                            "description": "Inventory turnover, stock movement ledgers, and procurement spend.",
                            "is_active": True,
                        },
                    )

                    mart_hr, _ = DataMart.objects.get_or_create(
                        tenant=tenant,
                        code="hr",
                        defaults={
                            "name": "Human Resources & Workforce Mart",
                            "subject_area": "hr",
                            "owner": admin_user,
                            "steward": admin_user,
                            "access_tier": "restricted",
                            "certification_status": "draft",
                            "refresh_cadence": "weekly",
                            "description": "Headcount trends, employee retention, payroll allocations, and attendance.",
                            "is_active": True,
                        },
                    )

                    # 2. LakehouseZones
                    zone_bronze, _ = LakehouseZone.objects.get_or_create(
                        tenant=tenant,
                        code="bronze",
                        defaults={
                            "name": "Bronze Raw Ingestion Zone",
                            "zone_type": "bronze",
                            "storage_backend": "internal_db",
                            "default_format": "relational_table",
                            "base_uri_path": "internal://lake/bronze/",
                            "is_read_only": True,
                            "description": "Append-only immutable raw landing layer from operational extractors.",
                            "is_active": True,
                        },
                    )

                    zone_silver, _ = LakehouseZone.objects.get_or_create(
                        tenant=tenant,
                        code="silver",
                        defaults={
                            "name": "Silver Curated Master Zone",
                            "zone_type": "silver",
                            "storage_backend": "internal_db",
                            "default_format": "parquet",
                            "base_uri_path": "internal://lake/silver/",
                            "is_read_only": False,
                            "description": "Cleaned, sanitized, and conformed master dataset layer.",
                            "is_active": True,
                        },
                    )

                    zone_gold, _ = LakehouseZone.objects.get_or_create(
                        tenant=tenant,
                        code="gold",
                        defaults={
                            "name": "Gold Enterprise Analytics Zone",
                            "zone_type": "gold",
                            "storage_backend": "internal_db",
                            "default_format": "delta_lake",
                            "base_uri_path": "internal://lake/gold/",
                            "is_read_only": False,
                            "description": "Aggregated dimensional star schemas and certified business reporting layer.",
                            "is_active": True,
                        },
                    )

                    zone_sandbox, _ = LakehouseZone.objects.get_or_create(
                        tenant=tenant,
                        code="sandbox",
                        defaults={
                            "name": "Sandbox Exploration Zone",
                            "zone_type": "sandbox",
                            "storage_backend": "internal_db",
                            "default_format": "relational_table",
                            "base_uri_path": "internal://lake/sandbox/",
                            "is_read_only": False,
                            "description": "Ad-hoc experimentation and feature engineering workspace.",
                            "is_active": True,
                        },
                    )

                    # 3. WarehouseStoragePolicies
                    policy_fin, _ = WarehouseStoragePolicy.objects.get_or_create(
                        tenant=tenant,
                        name="Financial Statutory 7-Year Retention",
                        defaults={
                            "partition_strategy": "range_time",
                            "partition_key": "posting_date",
                            "partition_granularity": "month",
                            "compression_codec": "zstd",
                            "enable_zone_maps": True,
                            "hot_tier_days": 90,
                            "warm_tier_days": 365,
                            "cold_tier_days": 2555,
                            "time_travel_days": 14,
                            "auto_purge_enabled": False,
                            "vacuum_cadence": "weekly",
                            "is_default": False,
                            "description": "Statutory retention rule conforming to GAAP/IFRS 7-year audit requirements.",
                            "is_active": True,
                        },
                    )

                    policy_timeseries, _ = WarehouseStoragePolicy.objects.get_or_create(
                        tenant=tenant,
                        name="High-Throughput Timeseries Policy",
                        defaults={
                            "partition_strategy": "range_time",
                            "partition_key": "created_at",
                            "partition_granularity": "day",
                            "compression_codec": "snappy",
                            "enable_zone_maps": True,
                            "hot_tier_days": 30,
                            "warm_tier_days": 90,
                            "cold_tier_days": 365,
                            "time_travel_days": 7,
                            "auto_purge_enabled": True,
                            "vacuum_cadence": "daily",
                            "is_default": False,
                            "description": "Fast-ingestion policy for operational events and transactional ledgers.",
                            "is_active": True,
                        },
                    )

                    policy_dim, _ = WarehouseStoragePolicy.objects.get_or_create(
                        tenant=tenant,
                        name="Standard Dimensional Storage",
                        defaults={
                            "partition_strategy": "none",
                            "partition_key": "",
                            "partition_granularity": "month",
                            "compression_codec": "zstd",
                            "enable_zone_maps": True,
                            "hot_tier_days": 365,
                            "warm_tier_days": 730,
                            "cold_tier_days": 2555,
                            "time_travel_days": 7,
                            "auto_purge_enabled": False,
                            "vacuum_cadence": "monthly",
                            "is_default": True,
                            "description": "Default storage policy for dimensional lookup tables.",
                            "is_active": True,
                        },
                    )

                    # 4. WarehouseTables
                    WarehouseTable.objects.get_or_create(
                        tenant=tenant,
                        table_name="fact_gl_journal_entries",
                        defaults={
                            "name": "Fact GL Journal Entries",
                            "table_type": "fact",
                            "schema_type": "star",
                            "grain": "transaction",
                            "lakehouse_zone": zone_gold,
                            "data_mart": mart_finance,
                            "storage_policy": policy_fin,
                            "primary_key_column": "entry_sk",
                            "natural_key_column": "journal_number",
                            "is_conformed_dimension": False,
                            "schema_definition": [
                                {"name": "entry_sk", "type": "BIGINT", "nullable": False, "description": "Surrogate primary key"},
                                {"name": "posting_date", "type": "DATE", "nullable": False, "description": "Fiscal posting date"},
                                {"name": "account_sk", "type": "INTEGER", "nullable": False, "description": "FK to dim_accounts"},
                                {"name": "debit_amount", "type": "NUMERIC(18,2)", "nullable": False, "description": "Debit line total"},
                                {"name": "credit_amount", "type": "NUMERIC(18,2)", "nullable": False, "description": "Credit line total"},
                            ],
                            "row_count": 250000,
                            "compressed_bytes": 45000000,
                            "compression_ratio": Decimal("3.40"),
                            "last_analyzed_at": now,
                            "description": "Consolidated general ledger entries loaded from Module 2 Accounting.",
                            "is_active": True,
                        },
                    )

                    WarehouseTable.objects.get_or_create(
                        tenant=tenant,
                        table_name="fact_sales_orders",
                        defaults={
                            "name": "Fact Sales Orders",
                            "table_type": "fact",
                            "schema_type": "star",
                            "grain": "transaction",
                            "lakehouse_zone": zone_gold,
                            "data_mart": mart_sales,
                            "storage_policy": policy_timeseries,
                            "primary_key_column": "order_sk",
                            "natural_key_column": "order_number",
                            "is_conformed_dimension": False,
                            "schema_definition": [
                                {"name": "order_sk", "type": "BIGINT", "nullable": False, "description": "Surrogate primary key"},
                                {"name": "order_date", "type": "DATE", "nullable": False, "description": "Order placement date"},
                                {"name": "customer_sk", "type": "INTEGER", "nullable": False, "description": "FK to dim_customers"},
                                {"name": "net_amount", "type": "NUMERIC(18,2)", "nullable": False, "description": "Net sales amount"},
                                {"name": "tax_amount", "type": "NUMERIC(18,2)", "nullable": False, "description": "Tax charge"},
                            ],
                            "row_count": 180000,
                            "compressed_bytes": 32000000,
                            "compression_ratio": Decimal("3.20"),
                            "last_analyzed_at": now,
                            "description": "Order transactions syndicating sales pipeline attainments.",
                            "is_active": True,
                        },
                    )

                    WarehouseTable.objects.get_or_create(
                        tenant=tenant,
                        table_name="fact_inventory_movements",
                        defaults={
                            "name": "Fact Inventory Movements",
                            "table_type": "fact",
                            "schema_type": "star",
                            "grain": "transaction",
                            "lakehouse_zone": zone_silver,
                            "data_mart": mart_scm,
                            "storage_policy": policy_timeseries,
                            "primary_key_column": "movement_sk",
                            "natural_key_column": "movement_number",
                            "is_conformed_dimension": False,
                            "schema_definition": [
                                {"name": "movement_sk", "type": "BIGINT", "nullable": False, "description": "Surrogate primary key"},
                                {"name": "movement_date", "type": "DATE", "nullable": False, "description": "Movement date"},
                                {"name": "item_code", "type": "VARCHAR(50)", "nullable": False, "description": "Stock item code"},
                                {"name": "quantity", "type": "NUMERIC(12,4)", "nullable": False, "description": "Stock quantity"},
                            ],
                            "row_count": 420000,
                            "compressed_bytes": 78000000,
                            "compression_ratio": Decimal("3.50"),
                            "last_analyzed_at": now,
                            "description": "StockMove ledger lines tracking warehouse transactions.",
                            "is_active": True,
                        },
                    )

                    WarehouseTable.objects.get_or_create(
                        tenant=tenant,
                        table_name="dim_customers",
                        defaults={
                            "name": "Dim Customers",
                            "table_type": "dimension",
                            "schema_type": "star",
                            "grain": "entity_state",
                            "lakehouse_zone": zone_gold,
                            "data_mart": mart_sales,
                            "storage_policy": policy_dim,
                            "primary_key_column": "customer_sk",
                            "natural_key_column": "customer_code",
                            "is_conformed_dimension": True,
                            "schema_definition": [
                                {"name": "customer_sk", "type": "BIGINT", "nullable": False, "description": "Surrogate dimension key"},
                                {"name": "customer_code", "type": "VARCHAR(50)", "nullable": False, "description": "Natural customer code"},
                                {"name": "customer_name", "type": "VARCHAR(255)", "nullable": False, "description": "Account / customer name"},
                                {"name": "industry", "type": "VARCHAR(100)", "nullable": True, "description": "Market sector"},
                            ],
                            "row_count": 12500,
                            "compressed_bytes": 2500000,
                            "compression_ratio": Decimal("2.80"),
                            "last_analyzed_at": now,
                            "description": "Conformed customer dimension shared across sales and finance.",
                            "is_active": True,
                        },
                    )

                    WarehouseTable.objects.get_or_create(
                        tenant=tenant,
                        table_name="dim_accounts",
                        defaults={
                            "name": "Dim Accounts",
                            "table_type": "dimension",
                            "schema_type": "snowflake",
                            "grain": "entity_state",
                            "lakehouse_zone": zone_gold,
                            "data_mart": mart_finance,
                            "storage_policy": policy_dim,
                            "primary_key_column": "account_sk",
                            "natural_key_column": "account_code",
                            "is_conformed_dimension": True,
                            "schema_definition": [
                                {"name": "account_sk", "type": "BIGINT", "nullable": False, "description": "Surrogate key"},
                                {"name": "account_code", "type": "VARCHAR(50)", "nullable": False, "description": "GL account code"},
                                {"name": "account_name", "type": "VARCHAR(150)", "nullable": False, "description": "GL account title"},
                                {"name": "account_type", "type": "VARCHAR(50)", "nullable": False, "description": "Asset/Liability/Equity/Rev/Exp"},
                            ],
                            "row_count": 850,
                            "compressed_bytes": 400000,
                            "compression_ratio": Decimal("2.10"),
                            "last_analyzed_at": now,
                            "description": "Conformed chart of accounts dimension for financial statement reporting.",
                            "is_active": True,
                        },
                    )

                    WarehouseTable.objects.get_or_create(
                        tenant=tenant,
                        table_name="dim_dates",
                        defaults={
                            "name": "Dim Dates (Time Intelligence)",
                            "table_type": "dimension",
                            "schema_type": "star",
                            "grain": "entity_state",
                            "lakehouse_zone": zone_gold,
                            "data_mart": None,
                            "storage_policy": policy_dim,
                            "primary_key_column": "date_sk",
                            "natural_key_column": "calendar_date",
                            "is_conformed_dimension": True,
                            "schema_definition": [
                                {"name": "date_sk", "type": "INTEGER", "nullable": False, "description": "YYYYMMDD integer key"},
                                {"name": "calendar_date", "type": "DATE", "nullable": False, "description": "Calendar day"},
                                {"name": "fiscal_year", "type": "SMALLINT", "nullable": False, "description": "Fiscal year"},
                                {"name": "fiscal_quarter", "type": "SMALLINT", "nullable": False, "description": "Fiscal quarter 1-4"},
                                {"name": "month_name", "type": "VARCHAR(20)", "nullable": False, "description": "Month name"},
                            ],
                            "row_count": 3650,
                            "compressed_bytes": 800000,
                            "compression_ratio": Decimal("2.50"),
                            "last_analyzed_at": now,
                            "description": "Conformed enterprise calendar and fiscal date dimension.",
                            "is_active": True,
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Data Warehouse for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI Data Warehouse already seeded for tenant: {tenant.name}")

            # --- 10.4 Data Modeling & Semantic Layer Seeding ---
            if not SemanticModel.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    # Retrieve 10.3 warehouse tables and marts
                    tbl_sales = WarehouseTable.objects.filter(tenant=tenant, table_name="fact_sales_orders").first()
                    tbl_gl = WarehouseTable.objects.filter(tenant=tenant, table_name="fact_gl_journal_entries").first()
                    tbl_customers = WarehouseTable.objects.filter(tenant=tenant, table_name="dim_customers").first()
                    tbl_dates = WarehouseTable.objects.filter(tenant=tenant, table_name="dim_dates").first()

                    mart_finance = DataMart.objects.filter(tenant=tenant, code="finance_accounting").first()
                    mart_sales = DataMart.objects.filter(tenant=tenant, code="sales_commercial").first()

                    # 1. Semantic Models
                    sm_sales, _ = SemanticModel.objects.get_or_create(
                        tenant=tenant,
                        code="sales_performance_model",
                        defaults={
                            "name": "Sales Performance Model",
                            "model_type": "fact",
                            "warehouse_table": tbl_sales,
                            "data_mart": mart_sales,
                            "primary_key_column": "order_sk",
                            "natural_key_columns": "order_number",
                            "grain_description": "One row per confirmed customer sales order line item",
                            "is_conformed_dimension": False,
                            "scd_type": "type_1",
                            "access_tier": "department",
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "certification_notes": "Validated and approved by Sales Operations & Finance teams.",
                            "source_fingerprint": "a1b2c3d4e5f67890",
                            "last_introspected_at": now,
                            "owner": admin_user,
                            "description": "Governed sales fact model tracking customer orders, gross margins, and fulfillment volumes.",
                            "is_active": True,
                        },
                    )

                    sm_gl, _ = SemanticModel.objects.get_or_create(
                        tenant=tenant,
                        code="gl_financials_model",
                        defaults={
                            "name": "General Ledger Financial Model",
                            "model_type": "fact",
                            "warehouse_table": tbl_gl,
                            "data_mart": mart_finance,
                            "primary_key_column": "entry_sk",
                            "natural_key_columns": "journal_number, line_no",
                            "grain_description": "One row per posted double-entry GL transaction line",
                            "is_conformed_dimension": False,
                            "scd_type": "type_1",
                            "access_tier": "restricted",
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "certification_notes": "Statutory audit certified single source of financial truth.",
                            "source_fingerprint": "f6e5d4c3b2a10987",
                            "last_introspected_at": now,
                            "owner": admin_user,
                            "description": "Statutory balanced financial ledger entries for trial balance and P&L analysis.",
                            "is_active": True,
                        },
                    )

                    sm_customers, _ = SemanticModel.objects.get_or_create(
                        tenant=tenant,
                        code="customer_dimension_model",
                        defaults={
                            "name": "Customer Analytical Master",
                            "model_type": "dimension",
                            "warehouse_table": tbl_customers,
                            "data_mart": mart_sales,
                            "primary_key_column": "customer_sk",
                            "natural_key_columns": "customer_code",
                            "grain_description": "One row per commercial account entity state",
                            "is_conformed_dimension": True,
                            "scd_type": "type_2",
                            "access_tier": "public",
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "certification_notes": "Conformed customer master verified across CRM and Accounting.",
                            "source_fingerprint": "1234567890abcdef",
                            "last_introspected_at": now,
                            "owner": admin_user,
                            "description": "Conformed customer dimension supporting historical SCD Type 2 tracking.",
                            "is_active": True,
                        },
                    )

                    sm_dates, _ = SemanticModel.objects.get_or_create(
                        tenant=tenant,
                        code="fiscal_calendar_dimension",
                        defaults={
                            "name": "Fiscal Calendar & Time Dimension",
                            "model_type": "dimension",
                            "warehouse_table": tbl_dates,
                            "data_mart": None,
                            "primary_key_column": "date_sk",
                            "natural_key_columns": "calendar_date",
                            "grain_description": "One row per calendar day",
                            "is_conformed_dimension": True,
                            "scd_type": "type_0",
                            "access_tier": "public",
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "certification_notes": "Enterprise-wide corporate fiscal calendar standard.",
                            "source_fingerprint": "fedcba0987654321",
                            "last_introspected_at": now,
                            "owner": admin_user,
                            "description": "Universal calendar dimension governing fiscal periods, quarters, and time-intelligence rollups.",
                            "is_active": True,
                        },
                    )

                    sm_arr_view, _ = SemanticModel.objects.get_or_create(
                        tenant=tenant,
                        code="arr_executive_view",
                        defaults={
                            "name": "Executive ARR & Retention View",
                            "model_type": "virtual_view",
                            "warehouse_table": None,
                            "data_mart": mart_finance,
                            "primary_key_column": "customer_name",
                            "natural_key_columns": "customer_name",
                            "grain_description": "One row per customer annualized subscription cohort",
                            "is_conformed_dimension": False,
                            "scd_type": "type_1",
                            "is_virtual_view": True,
                            "sql_definition": "SELECT c.customer_name, SUM(s.net_amount) AS annualized_arr, COUNT(s.order_sk) AS total_orders FROM fact_sales_orders s JOIN dim_customers c ON s.customer_sk = c.customer_sk GROUP BY c.customer_name",
                            "access_tier": "restricted",
                            "certification_status": "in_review",
                            "certification_notes": "Under review by FP&A director.",
                            "owner": admin_user,
                            "description": "Virtual analytical SQL view computing annualized customer recurring revenue on the fly.",
                            "is_active": True,
                        },
                    )

                    # 2. Business Glossary Terms
                    term_nrr, _ = BusinessGlossaryTerm.objects.get_or_create(
                        tenant=tenant,
                        code="net_recurring_revenue",
                        defaults={
                            "name": "Net Recurring Revenue (NRR)",
                            "domain_category": "finance",
                            "short_definition": "Percentage of recurring revenue retained from existing customers over a period, factoring expansions, contractions, and churn.",
                            "full_definition": "Net Recurring Revenue (also known as Net Retention Rate) measures the net change in annualized recurring revenue from an existing cohort of customers over a 12-month period. A rate exceeding 100% indicates organic expansion without new customer acquisition.",
                            "calculation_rule": "(Starting ARR + Expansion ARR - Contraction ARR - Churn ARR) / Starting ARR * 100",
                            "synonyms": "NRR, Net Revenue Retention, Net Dollar Retention (NDR)",
                            "steward": admin_user,
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "certification_notes": "SaaS and contractual billing KPI standard.",
                            "is_active": True,
                        },
                    )

                    term_arr, _ = BusinessGlossaryTerm.objects.get_or_create(
                        tenant=tenant,
                        code="annual_recurring_revenue",
                        defaults={
                            "name": "Annual Recurring Revenue (ARR)",
                            "domain_category": "finance",
                            "short_definition": "The annualized monetary value of recurring subscription contracts active at the close of the reporting period.",
                            "full_definition": "Normalized annual value of active recurring software or subscription service commitments, excluding one-time professional services or non-recurring setup fees.",
                            "calculation_rule": "SUM(Monthly Recurring Revenue * 12)",
                            "synonyms": "ARR, Annual Contract Value",
                            "steward": admin_user,
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "is_active": True,
                        },
                    )

                    term_gp, _ = BusinessGlossaryTerm.objects.get_or_create(
                        tenant=tenant,
                        code="gross_profit_margin",
                        defaults={
                            "name": "Gross Profit Margin %",
                            "domain_category": "finance",
                            "short_definition": "Gross profit expressed as a percentage of total net revenue.",
                            "full_definition": "The proportion of money left over from commercial revenues after accounting for the direct cost of goods sold (COGS) and service fulfillment.",
                            "calculation_rule": "(Total Invoiced Revenue - COGS) / Total Invoiced Revenue * 100",
                            "synonyms": "GP %, Gross Margin",
                            "steward": admin_user,
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "is_active": True,
                        },
                    )

                    term_cust, _ = BusinessGlossaryTerm.objects.get_or_create(
                        tenant=tenant,
                        code="active_commercial_customer",
                        defaults={
                            "name": "Active Commercial Customer",
                            "domain_category": "sales",
                            "short_definition": "An enterprise account with at least one active order or paid invoice within the rolling 90-day window.",
                            "full_definition": "Accounts that have transacted or maintained an active contract agreement within the last 90 calendar days.",
                            "calculation_rule": "COUNT(DISTINCT customer_id) WHERE last_activity_date >= TODAY - 90 DAYS",
                            "synonyms": "Active Account, Transacting Client",
                            "steward": admin_user,
                            "certification_status": "certified",
                            "certified_by": admin_user,
                            "certified_at": now,
                            "is_active": True,
                        },
                    )

                    term_nrr.related_terms.add(term_arr)

                    # 3. Calculated Measures
                    CalculatedMeasure.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_sales,
                        code="total_sales_revenue",
                        defaults={
                            "name": "Total Sales Revenue",
                            "glossary_term": None,
                            "aggregation_type": "sum",
                            "source_column": "net_amount",
                            "time_intelligence": "none",
                            "format_string": "currency",
                            "display_units": "auto",
                            "target_value": Decimal("1000000.0000"),
                            "warning_threshold": Decimal("800000.0000"),
                            "critical_threshold": Decimal("600000.0000"),
                            "description": "Total net monetary value of all booked sales orders.",
                            "is_active": True,
                        },
                    )

                    CalculatedMeasure.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_sales,
                        code="sales_gross_margin_pct",
                        defaults={
                            "name": "Sales Gross Margin %",
                            "glossary_term": term_gp,
                            "aggregation_type": "formula",
                            "formula_expression": "([total_sales_revenue] - [cost_amount]) / [total_sales_revenue] * 100",
                            "time_intelligence": "none",
                            "format_string": "percentage",
                            "display_units": "none",
                            "target_value": Decimal("45.0000"),
                            "warning_threshold": Decimal("35.0000"),
                            "critical_threshold": Decimal("25.0000"),
                            "description": "Calculated percentage gross profit on booked sales.",
                            "is_active": True,
                        },
                    )

                    CalculatedMeasure.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_sales,
                        code="completed_order_count",
                        defaults={
                            "name": "Completed Orders Count",
                            "glossary_term": None,
                            "aggregation_type": "count",
                            "filter_expression": "order_status = 'completed'",
                            "time_intelligence": "none",
                            "format_string": "integer",
                            "display_units": "auto",
                            "description": "Count of successfully fulfilled and closed orders.",
                            "is_active": True,
                        },
                    )

                    CalculatedMeasure.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_sales,
                        code="revenue_yoy_growth",
                        defaults={
                            "name": "YoY Revenue Growth %",
                            "glossary_term": None,
                            "aggregation_type": "sum",
                            "source_column": "net_amount",
                            "time_intelligence": "yoy_growth",
                            "format_string": "percentage",
                            "display_units": "none",
                            "target_value": Decimal("15.0000"),
                            "warning_threshold": Decimal("5.0000"),
                            "critical_threshold": Decimal("0.0000"),
                            "description": "Year-over-Year revenue expansion rate compared to same prior fiscal period.",
                            "is_active": True,
                        },
                    )

                    CalculatedMeasure.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_gl,
                        code="net_ledger_balance",
                        defaults={
                            "name": "Net GL Ledger Balance",
                            "glossary_term": None,
                            "aggregation_type": "sum",
                            "source_column": "amount",
                            "time_intelligence": "none",
                            "format_string": "currency",
                            "display_units": "auto",
                            "description": "Sum of net posted debit and credit GL journal line amounts.",
                            "is_active": True,
                        },
                    )

                    # 4. Drill Hierarchies
                    DrillHierarchy.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_dates,
                        code="fiscal_calendar_drill_path",
                        defaults={
                            "name": "Fiscal Calendar Drill Path",
                            "hierarchy_type": "time",
                            "levels_json": [
                                {"level": 1, "name": "Fiscal Year", "column": "fiscal_year"},
                                {"level": 2, "name": "Fiscal Quarter", "column": "fiscal_quarter"},
                                {"level": 3, "name": "Fiscal Month", "column": "month_name"},
                                {"level": 4, "name": "Date", "column": "calendar_date"},
                            ],
                            "primary_drill_path": True,
                            "description": "Standard temporal drill path from fiscal year down to daily granularity.",
                            "is_active": True,
                        },
                    )

                    DrillHierarchy.objects.get_or_create(
                        tenant=tenant,
                        semantic_model=sm_sales,
                        code="sales_order_time_path",
                        defaults={
                            "name": "Sales Order Time Path",
                            "hierarchy_type": "time",
                            "levels_json": [
                                {"level": 1, "name": "Order Year", "column": "order_year"},
                                {"level": 2, "name": "Order Quarter", "column": "order_quarter"},
                                {"level": 3, "name": "Order Month", "column": "order_month"},
                            ],
                            "primary_drill_path": True,
                            "description": "Temporal drill path for sales order volume analysis.",
                            "is_active": True,
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Semantic Layer for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI Semantic Layer already seeded for tenant: {tenant.name}")

            # --- 10.5 Data Quality & Cleansing Seeding ---
            if not DataQualityProfile.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    tbl_sales = WarehouseTable.objects.filter(tenant=tenant, table_name="fact_sales_orders").first()
                    tbl_customers = WarehouseTable.objects.filter(tenant=tenant, table_name="dim_customers").first()
                    sm_sales = SemanticModel.objects.filter(tenant=tenant, code="sales_performance_model").first()

                    # 1. Data Quality Profiles
                    prof_sales, _ = DataQualityProfile.objects.get_or_create(
                        tenant=tenant,
                        name="Sales Fact Table Quality Profile",
                        defaults={
                            "target_type": "warehouse_table",
                            "warehouse_table": tbl_sales,
                            "semantic_model": None,
                            "status": "completed",
                            "total_row_count": 1250,
                            "total_column_count": 8,
                            "completeness_score": Decimal("99.80"),
                            "uniqueness_score": Decimal("100.00"),
                            "validity_score": Decimal("99.40"),
                            "column_profiles_json": [
                                {"column_name": "order_sk", "data_type": "BIGINT", "null_count": 0, "null_pct": "0.00%", "distinct_count": 1250, "distinct_pct": "100.00%", "min_value": "1", "max_value": "1250", "completeness_score": "100.00%"},
                                {"column_name": "order_number", "data_type": "VARCHAR(60)", "null_count": 0, "null_pct": "0.00%", "distinct_count": 1250, "distinct_pct": "100.00%", "min_value": "SO-0001", "max_value": "SO-1250", "completeness_score": "100.00%"},
                                {"column_name": "total_amount", "data_type": "DECIMAL(14,2)", "null_count": 0, "null_pct": "0.00%", "distinct_count": 890, "distinct_pct": "71.20%", "min_value": "15.00", "max_value": "45000.00", "completeness_score": "100.00%"},
                                {"column_name": "tax_amount", "data_type": "DECIMAL(14,2)", "null_count": 2, "null_pct": "0.16%", "distinct_count": 420, "distinct_pct": "33.60%", "min_value": "0.00", "max_value": "4500.00", "completeness_score": "99.84%"},
                            ],
                            "profiled_by": admin_user,
                            "profiled_at": now,
                            "duration_seconds": Decimal("1.42"),
                            "notes": "Automated profiling of commercial sales transactions.",
                            "is_active": True,
                        },
                    )

                    prof_cust, _ = DataQualityProfile.objects.get_or_create(
                        tenant=tenant,
                        name="Customer Analytical Master Quality Profile",
                        defaults={
                            "target_type": "semantic_model" if sm_sales else "warehouse_table",
                            "warehouse_table": tbl_customers,
                            "semantic_model": sm_sales,
                            "status": "completed",
                            "total_row_count": 450,
                            "total_column_count": 6,
                            "completeness_score": Decimal("98.90"),
                            "uniqueness_score": Decimal("100.00"),
                            "validity_score": Decimal("98.70"),
                            "column_profiles_json": [
                                {"column_name": "customer_sk", "data_type": "BIGINT", "null_count": 0, "null_pct": "0.00%", "distinct_count": 450, "distinct_pct": "100.00%", "min_value": "1", "max_value": "450", "completeness_score": "100.00%"},
                                {"column_name": "email", "data_type": "VARCHAR(255)", "null_count": 3, "null_pct": "0.67%", "distinct_count": 447, "distinct_pct": "99.33%", "min_value": "a@corp.com", "max_value": "z@corp.com", "completeness_score": "99.33%"},
                            ],
                            "profiled_by": admin_user,
                            "profiled_at": now,
                            "duration_seconds": Decimal("0.85"),
                            "notes": "Profiling customer master contact info and attributes.",
                            "is_active": True,
                        },
                    )

                    # 2. Data Quality Rules
                    rule_amount, _ = DataQualityRule.objects.get_or_create(
                        tenant=tenant,
                        code="sales_order_amount_gt_zero",
                        defaults={
                            "name": "Sales Order Amount Greater Than Zero",
                            "rule_category": "validation",
                            "dimension": "accuracy",
                            "target_type": "warehouse_table",
                            "warehouse_table": tbl_sales,
                            "target_column": "total_amount",
                            "rule_type": "range_between",
                            "parameters_json": {"min_value": 0.01, "max_value": 1000000.00},
                            "severity": "critical",
                            "failure_tolerance_pct": Decimal("0.00"),
                            "last_run_at": now,
                            "last_status": "passed",
                            "passed_records_count": 1250,
                            "failed_records_count": 0,
                            "pass_rate_pct": Decimal("100.00"),
                            "steward": admin_user,
                            "description": "Total amount on confirmed order lines must be strictly positive.",
                            "is_active": True,
                        },
                    )

                    rule_email, _ = DataQualityRule.objects.get_or_create(
                        tenant=tenant,
                        code="customer_email_syntax_check",
                        defaults={
                            "name": "Customer Email Syntax Validation",
                            "rule_category": "validation",
                            "dimension": "validity",
                            "target_type": "warehouse_table",
                            "warehouse_table": tbl_customers,
                            "target_column": "email",
                            "rule_type": "regex_pattern",
                            "parameters_json": {"regex": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"},
                            "severity": "warning",
                            "failure_tolerance_pct": Decimal("1.00"),
                            "last_run_at": now,
                            "last_status": "warning",
                            "passed_records_count": 447,
                            "failed_records_count": 3,
                            "pass_rate_pct": Decimal("99.33"),
                            "steward": admin_user,
                            "description": "Validate that customer email addresses conform to standard format.",
                            "is_active": True,
                        },
                    )

                    rule_freshness, _ = DataQualityRule.objects.get_or_create(
                        tenant=tenant,
                        code="sales_fact_freshness_sla",
                        defaults={
                            "name": "Sales Fact Table 24H Freshness SLA",
                            "rule_category": "consistency",
                            "dimension": "timeliness",
                            "target_type": "warehouse_table",
                            "warehouse_table": tbl_sales,
                            "target_column": "updated_at",
                            "rule_type": "date_freshness",
                            "parameters_json": {"max_age_hours": 24},
                            "severity": "critical",
                            "failure_tolerance_pct": Decimal("0.00"),
                            "last_run_at": now,
                            "last_status": "passed",
                            "passed_records_count": 1250,
                            "failed_records_count": 0,
                            "pass_rate_pct": Decimal("100.00"),
                            "steward": admin_user,
                            "description": "Fact table records must not be older than 24 hours.",
                            "is_active": True,
                        },
                    )

                    rule_dedup, _ = DataQualityRule.objects.get_or_create(
                        tenant=tenant,
                        code="customer_fuzzy_dedup_check",
                        defaults={
                            "name": "Customer Account Fuzzy Deduplication",
                            "rule_category": "uniqueness",
                            "dimension": "uniqueness",
                            "target_type": "warehouse_table",
                            "warehouse_table": tbl_customers,
                            "target_column": "name",
                            "rule_type": "duplicate_cluster",
                            "parameters_json": {"fuzzy_algorithm": "levenshtein", "match_threshold": 0.85},
                            "severity": "warning",
                            "failure_tolerance_pct": Decimal("0.50"),
                            "last_run_at": now,
                            "last_status": "warning",
                            "passed_records_count": 448,
                            "failed_records_count": 2,
                            "pass_rate_pct": Decimal("99.55"),
                            "steward": admin_user,
                            "description": "Flag potential duplicate customer records based on fuzzy string distance.",
                            "is_active": True,
                        },
                    )

                    # 3. Data Quality Exceptions
                    DataQualityException.objects.get_or_create(
                        tenant=tenant,
                        rule=rule_email,
                        record_identifier="CUST-00042",
                        defaults={
                            "profile": prof_cust,
                            "warehouse_table": tbl_customers,
                            "target_column": "email",
                            "invalid_value": "john.doe@invalid-domain-syntax",
                            "expected_condition": "Valid email conforming to regex pattern",
                            "exception_type": "format_invalid",
                            "severity": "warning",
                            "status": "open",
                            "remediation_action": "none",
                            "proposed_value": "john.doe@valid-domain.com",
                            "assigned_steward": admin_user,
                            "resolution_notes": "Outreach needed to customer to verify domain extension.",
                            "is_active": True,
                        },
                    )

                    DataQualityException.objects.get_or_create(
                        tenant=tenant,
                        rule=rule_dedup,
                        record_identifier="CUST-00108 / CUST-00214",
                        defaults={
                            "profile": prof_cust,
                            "warehouse_table": tbl_customers,
                            "target_column": "name",
                            "invalid_value": "Acme Corp Ltd vs Acme Corporation Limited",
                            "expected_condition": "Distinct non-duplicate commercial accounts",
                            "exception_type": "duplicate_candidate",
                            "severity": "warning",
                            "status": "investigating",
                            "remediation_action": "merge_duplicate",
                            "proposed_value": "Acme Corporation Ltd",
                            "assigned_steward": admin_user,
                            "resolution_notes": "Candidate match identified with 92% fuzzy similarity score.",
                            "is_active": True,
                        },
                    )

                    # 4. Data Quality Scorecards
                    DataQualityScorecard.objects.get_or_create(
                        tenant=tenant,
                        code="sales_commercial_dq_scorecard",
                        defaults={
                            "name": "Sales Commercial Data Quality Scorecard",
                            "scope_type": "warehouse_table",
                            "warehouse_table": tbl_sales,
                            "overall_quality_score": Decimal("99.50"),
                            "completeness_score": Decimal("99.80"),
                            "accuracy_score": Decimal("100.00"),
                            "consistency_score": Decimal("99.40"),
                            "timeliness_score": Decimal("100.00"),
                            "uniqueness_score": Decimal("100.00"),
                            "validity_score": Decimal("97.80"),
                            "grade": "A",
                            "health_status": "healthy",
                            "target_quality_score": Decimal("95.00"),
                            "meets_sla": True,
                            "total_rules_evaluated": 8,
                            "rules_passed_count": 8,
                            "rules_failed_count": 0,
                            "open_exceptions_count": 0,
                            "critical_exceptions_count": 0,
                            "evaluation_period": "daily",
                            "last_calculated_at": now,
                            "steward": admin_user,
                            "description": "Sales operations executive data trust and SLA scorecard.",
                            "is_active": True,
                        },
                    )

                    DataQualityScorecard.objects.get_or_create(
                        tenant=tenant,
                        code="enterprise_dti_scorecard",
                        defaults={
                            "name": "Enterprise Data Trust Index Scorecard",
                            "scope_type": "tenant_wide",
                            "overall_quality_score": Decimal("98.60"),
                            "completeness_score": Decimal("99.20"),
                            "accuracy_score": Decimal("98.50"),
                            "consistency_score": Decimal("97.80"),
                            "timeliness_score": Decimal("100.00"),
                            "uniqueness_score": Decimal("99.90"),
                            "validity_score": Decimal("96.20"),
                            "grade": "A",
                            "health_status": "healthy",
                            "target_quality_score": Decimal("95.00"),
                            "meets_sla": True,
                            "total_rules_evaluated": 24,
                            "rules_passed_count": 22,
                            "rules_failed_count": 2,
                            "open_exceptions_count": 2,
                            "critical_exceptions_count": 0,
                            "evaluation_period": "weekly",
                            "last_calculated_at": now,
                            "steward": admin_user,
                            "description": "Executive tenant-wide aggregate data quality index across all warehouse domains.",
                            "is_active": True,
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Data Quality for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI Data Quality already seeded for tenant: {tenant.name}")

        self.stdout.write(self.style.SUCCESS("Business Intelligence seeding finished."))
