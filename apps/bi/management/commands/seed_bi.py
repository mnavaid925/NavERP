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
from apps.core.models import Tenant


class Command(BaseCommand):
    help = "Seed demo data for Business Intelligence (BI) Module 10 (10.1 Ingestion, 10.2 ETL/ELT Pipelines, & 10.3 Data Warehouse & Storage)."

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

        self.stdout.write(self.style.SUCCESS("Business Intelligence seeding finished."))
