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
from apps.bi.models.MasterData.MdmGoldenRecords import MdmGoldenRecord
from apps.bi.models.MasterData.MdmHierarchyNodes import MdmHierarchyNode
from apps.bi.models.MasterData.MdmReferenceCodes import MdmReferenceCode
from apps.bi.models.MasterData.MdmSurvivorshipRules import MdmSurvivorshipRule
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataCatalog.CatalogLineageEdges import CatalogLineageEdge
from apps.bi.models.DataCatalog.DataGovernancePolicies import DataGovernancePolicy
from apps.bi.models.DataCatalog.CatalogTrustEndorsements import CatalogTrustEndorsement
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.Dashboards.BiDashboardBookmarks import BiDashboardBookmark
from apps.bi.models.Dashboards.BiDashboardFilters import BiDashboardFilter
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportDrillPaths import ReportDrillPath
from apps.bi.models.OperationalReporting.ReportExecutions import ReportExecution
from apps.bi.models.OperationalReporting.ReportParameters import ReportParameter
from apps.bi.models.SelfServiceAnalytics.AdHocCalculatedFields import AdHocCalculatedField
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.bi.models.SelfServiceAnalytics.DataBlendDefinitions import DataBlendDefinition
from apps.bi.models.SelfServiceAnalytics.SavedAnalysisViews import SavedAnalysisView
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PerformanceScorecards.PerformanceScorecards import PerformanceScorecard
from apps.bi.models.PerformanceScorecards.ScorecardKpiAssignments import ScorecardKpiAssignment
from apps.bi.models.PerformanceScorecards.StrategicObjectives import StrategicObjective
from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
from apps.bi.models.OlapAnalysis.PivotViews import PivotAnalysisView
from apps.bi.models.OlapAnalysis.WhatIfScenarios import WhatIfScenario
from apps.bi.models.OlapAnalysis.WritebackCells import ScenarioWritebackCell
from apps.accounting.models import Budget, FiscalPeriod, GLAccount
from apps.core.models import OrgUnit
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
                SavedAnalysisView.objects.all().delete()
                AdHocCalculatedField.objects.all().delete()
                AdHocQuery.objects.all().delete()
                DataBlendDefinition.objects.all().delete()
                ReportDrillPath.objects.all().delete()
                ReportExecution.objects.all().delete()
                ReportParameter.objects.all().delete()
                ReportDefinition.objects.all().delete()
                BiDashboardBookmark.objects.all().delete()
                BiDashboardFilter.objects.all().delete()
                BiDashboardWidget.objects.all().delete()
                BiDashboard.objects.all().delete()
                CatalogTrustEndorsement.objects.all().delete()
                CatalogLineageEdge.objects.all().delete()
                CatalogAsset.objects.all().delete()
                DataGovernancePolicy.objects.all().delete()
                MdmHierarchyNode.objects.all().delete()
                MdmGoldenRecord.objects.all().delete()
                MdmSurvivorshipRule.objects.all().delete()
                MdmReferenceCode.objects.all().delete()
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

            # =========================================================================
            # 10.6 Master Data Management (MDM) Seeding
            # =========================================================================
            if not MdmGoldenRecord.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"  Seeding BI Master Data Management for tenant: {tenant.name}...")
                with transaction.atomic():
                    from apps.core.models import Party, OrgUnit
                    from apps.scm.models.InventoryManagement.Items import Item, ItemCategory
                    from apps.scm.models.AssetManagement.Assets import Asset

                    demo_party = Party.objects.filter(tenant=tenant).first()
                    demo_item = Item.objects.filter(tenant=tenant).first()
                    demo_asset = Asset.objects.filter(tenant=tenant).first()
                    demo_org_unit = OrgUnit.objects.filter(tenant=tenant).first()
                    demo_item_category = ItemCategory.objects.filter(tenant=tenant).first()

                    # 1. MdmReferenceCode (Standard enterprise code sets)
                    ref_codes = [
                        ("country_codes", "USA", "United States of America", "iso_standard", "US", "Americas"),
                        ("country_codes", "GBR", "United Kingdom", "iso_standard", "GB", "Europe"),
                        ("country_codes", "DEU", "Germany", "iso_standard", "DE", "Europe"),
                        ("country_codes", "JPN", "Japan", "iso_standard", "JP", "Asia-Pacific"),
                        ("currency_codes", "USD", "US Dollar", "iso_standard", "USD", "Global"),
                        ("currency_codes", "EUR", "Euro", "iso_standard", "EUR", "Europe"),
                        ("currency_codes", "GBP", "British Pound", "iso_standard", "GBP", "Europe"),
                        ("currency_codes", "JPY", "Japanese Yen", "iso_standard", "JPY", "Asia"),
                        ("uom_codes", "KGM", "Kilogram", "iso_uom", "KG", "Mass"),
                        ("uom_codes", "EA", "Each / Unit", "iso_uom", "PC", "Quantity"),
                        ("uom_codes", "MTR", "Meter", "iso_uom", "M", "Length"),
                        ("payment_terms", "NET30", "Net 30 Days", "erp_core", "N30", "Commercial"),
                        ("payment_terms", "NET60", "Net 60 Days", "erp_core", "N60", "Commercial"),
                        ("payment_terms", "DUE_REC", "Due Upon Receipt", "erp_core", "COD", "Immediate"),
                    ]
                    for cset, ccode, cname, ssys, scode, cat in ref_codes:
                        MdmReferenceCode.objects.get_or_create(
                            tenant=tenant,
                            code_set=cset,
                            canonical_code=ccode,
                            source_system=ssys,
                            source_code=scode,
                            defaults={
                                "canonical_name": cname,
                                "category": cat,
                                "status": "active",
                                "attributes_json": {"standard_spec": "ISO-MDM", "scope": "enterprise"},
                                "is_active": True,
                            },
                        )

                    # 2. MdmSurvivorshipRule (Matching algorithms & precedence matrices)
                    MdmSurvivorshipRule.objects.get_or_create(
                        tenant=tenant,
                        code="legal_name_erp_precedence",
                        defaults={
                            "name": "Customer Legal Name ERP Precedence",
                            "domain": "customer",
                            "target_field": "name",
                            "survivorship_strategy": "source_priority",
                            "match_algorithm": "exact",
                            "match_threshold_pct": Decimal("85.00"),
                            "auto_merge_threshold_pct": Decimal("98.00"),
                            "source_priority_list_json": ["erp_core", "crm_sales", "billing_app", "web_portal"],
                            "priority_order": 10,
                            "steward": admin_user,
                            "description": "Enterprise legal entity name resolution prioritizing operational ERP records.",
                            "is_active": True,
                        },
                    )

                    MdmSurvivorshipRule.objects.get_or_create(
                        tenant=tenant,
                        code="primary_phone_most_recent",
                        defaults={
                            "name": "Primary Phone Most Recent Wins",
                            "domain": "all",
                            "target_field": "primary_phone",
                            "survivorship_strategy": "most_recent",
                            "match_algorithm": "exact",
                            "match_threshold_pct": Decimal("80.00"),
                            "auto_merge_threshold_pct": Decimal("95.00"),
                            "source_priority_list_json": ["crm_sales", "erp_core", "web_portal"],
                            "priority_order": 20,
                            "steward": admin_user,
                            "description": "Attribute survivorship rule selecting newest validated telephone contact.",
                            "is_active": True,
                        },
                    )

                    MdmSurvivorshipRule.objects.get_or_create(
                        tenant=tenant,
                        code="vendor_tax_id_exact_match",
                        defaults={
                            "name": "Vendor Tax ID Exact Deterministic Match",
                            "domain": "vendor",
                            "target_field": "tax_id",
                            "survivorship_strategy": "highest_completeness",
                            "match_algorithm": "exact",
                            "match_threshold_pct": Decimal("100.00"),
                            "auto_merge_threshold_pct": Decimal("100.00"),
                            "source_priority_list_json": ["scm_procurement", "erp_accounting", "legacy_db"],
                            "priority_order": 30,
                            "steward": admin_user,
                            "description": "Zero-tolerance exact tax and VAT ID reconciliation for supplier masters.",
                            "is_active": True,
                        },
                    )

                    MdmSurvivorshipRule.objects.get_or_create(
                        tenant=tenant,
                        code="product_fuzzy_matching_rule",
                        defaults={
                            "name": "Product SKU Fuzzy Jaro-Winkler Matching",
                            "domain": "product",
                            "target_field": "name",
                            "survivorship_strategy": "source_priority",
                            "match_algorithm": "fuzzy_jaro_winkler",
                            "match_threshold_pct": Decimal("82.00"),
                            "auto_merge_threshold_pct": Decimal("96.00"),
                            "source_priority_list_json": ["plm_engineering", "scm_inventory", "ecommerce_store"],
                            "priority_order": 40,
                            "steward": admin_user,
                            "description": "Fuzzy string clustering detecting cross-catalog duplicate material items.",
                            "is_active": True,
                        },
                    )

                    # 3. MdmGoldenRecord (Authoritative single sources of truth)
                    rec_acme, _ = MdmGoldenRecord.objects.get_or_create(
                        tenant=tenant,
                        domain="customer",
                        code="acme_global_industries",
                        defaults={
                            "name": "Acme Global Industries Inc.",
                            "status": "approved",
                            "trust_tier": "gold",
                            "confidence_score": Decimal("99.50"),
                            "tax_id": "US-123456789",
                            "primary_email": "contact@acmeglobal.example.com",
                            "primary_phone": "+1-555-0199",
                            "primary_address": "100 Innovation Way, Suite 400\nSan Jose, CA 95134",
                            "party": demo_party,
                            "source_record_count": 3,
                            "golden_attributes_json": {
                                "name": {"value": "Acme Global Industries Inc.", "source_system": "erp_core", "confidence": 100.0},
                                "tax_id": {"value": "US-123456789", "source_system": "erp_core", "confidence": 100.0},
                                "primary_phone": {"value": "+1-555-0199", "source_system": "crm_sales", "confidence": 98.5},
                                "primary_email": {"value": "contact@acmeglobal.example.com", "source_system": "crm_sales", "confidence": 99.0},
                            },
                            "source_crosswalks_json": [
                                {"source_system": "erp_core", "source_record_id": "CUST-1042", "match_confidence": 100.0, "ingested_at": "2026-11-01"},
                                {"source_system": "crm_sales", "source_record_id": "LEAD-9088", "match_confidence": 98.5, "ingested_at": "2026-11-02"},
                                {"source_system": "billing_app", "source_record_id": "ACC-4402", "match_confidence": 99.0, "ingested_at": "2026-11-03"},
                            ],
                            "assigned_steward": admin_user,
                            "reviewed_by": admin_user,
                            "reviewed_at": now,
                            "stewardship_notes": "Authoritative golden record verified across ERP, CRM, and billing feeds.",
                            "is_active": True,
                        },
                    )

                    rec_apex, _ = MdmGoldenRecord.objects.get_or_create(
                        tenant=tenant,
                        domain="vendor",
                        code="apex_industrial_supply",
                        defaults={
                            "name": "Apex Industrial Supply Corp",
                            "status": "approved",
                            "trust_tier": "gold",
                            "confidence_score": Decimal("98.80"),
                            "tax_id": "US-987654321",
                            "primary_email": "orders@apexsupply.example.com",
                            "primary_phone": "+1-555-0288",
                            "primary_address": "500 Logistics Blvd\nChicago, IL 60607",
                            "party": demo_party,
                            "source_record_count": 2,
                            "golden_attributes_json": {
                                "name": {"value": "Apex Industrial Supply Corp", "source_system": "scm_procurement", "confidence": 99.0},
                                "tax_id": {"value": "US-987654321", "source_system": "scm_procurement", "confidence": 100.0},
                            },
                            "source_crosswalks_json": [
                                {"source_system": "scm_procurement", "source_record_id": "VEND-804", "match_confidence": 100.0, "ingested_at": "2026-11-01"},
                                {"source_system": "legacy_accounting", "source_record_id": "AP-1109", "match_confidence": 97.6, "ingested_at": "2026-11-02"},
                            ],
                            "assigned_steward": admin_user,
                            "reviewed_by": admin_user,
                            "reviewed_at": now,
                            "stewardship_notes": "Consolidated supplier profile certified active.",
                            "is_active": True,
                        },
                    )

                    rec_drill, _ = MdmGoldenRecord.objects.get_or_create(
                        tenant=tenant,
                        domain="product",
                        code="titanium_drill_bit_v4",
                        defaults={
                            "name": "Precision Titanium Drill Bit #4",
                            "status": "approved",
                            "trust_tier": "silver",
                            "confidence_score": Decimal("94.20"),
                            "item": demo_item,
                            "source_record_count": 2,
                            "golden_attributes_json": {
                                "name": {"value": "Precision Titanium Drill Bit #4", "source_system": "plm_engineering", "confidence": 95.0},
                                "sku": {"value": "SKU-DRILL-T4", "source_system": "scm_inventory", "confidence": 93.4},
                            },
                            "source_crosswalks_json": [
                                {"source_system": "plm_engineering", "source_record_id": "PART-0044", "match_confidence": 95.0, "ingested_at": "2026-11-01"},
                                {"source_system": "scm_inventory", "source_record_id": "ITEM-8812", "match_confidence": 93.4, "ingested_at": "2026-11-03"},
                            ],
                            "assigned_steward": admin_user,
                            "is_active": True,
                        },
                    )

                    # Absorbed Duplicate Record
                    MdmGoldenRecord.objects.get_or_create(
                        tenant=tenant,
                        domain="customer",
                        code="acme_distribution_services",
                        defaults={
                            "name": "Acme Distribution Services LLC",
                            "status": "merged",
                            "trust_tier": "bronze",
                            "confidence_score": Decimal("86.50"),
                            "merged_into_record": rec_acme,
                            "merged_at": now,
                            "source_record_count": 1,
                            "assigned_steward": admin_user,
                            "stewardship_notes": f"[Merged into {rec_acme.number}]: Confirmed secondary regional branch subsidiary.",
                            "is_active": True,
                        },
                    )

                    # 4. MdmHierarchyNode (Multi-domain tree hierarchies)
                    root_holding, _ = MdmHierarchyNode.objects.get_or_create(
                        tenant=tenant,
                        hierarchy_type="corporate_legal",
                        code="apex_global_holding",
                        defaults={
                            "name": "Apex Global Holding Group",
                            "golden_record": rec_acme,
                            "party": demo_party,
                            "relationship_kind": "parent_holding_entity",
                            "sort_order": 1,
                            "level": 1,
                            "path": "/1/",
                            "description": "Global ultimate holding corporation for commercial entities.",
                            "is_active": True,
                        },
                    )

                    MdmHierarchyNode.objects.get_or_create(
                        tenant=tenant,
                        hierarchy_type="corporate_legal",
                        code="na_commercial_operations",
                        defaults={
                            "name": "North American Commercial Operations",
                            "parent": root_holding,
                            "party": demo_party,
                            "org_unit": demo_org_unit,
                            "relationship_kind": "operating_subsidiary",
                            "sort_order": 10,
                            "level": 2,
                            "path": f"{root_holding.path}{root_holding.pk}/",
                            "description": "Primary operating division across US and Canada.",
                            "is_active": True,
                        },
                    )

                    MdmHierarchyNode.objects.get_or_create(
                        tenant=tenant,
                        hierarchy_type="account_group",
                        code="tier1_strategic_accounts",
                        defaults={
                            "name": "Tier 1 Global Strategic Accounts",
                            "relationship_kind": "sales_account_tier",
                            "sort_order": 5,
                            "level": 1,
                            "description": "Enterprise accounts generating over $5M ARR.",
                            "is_active": True,
                        },
                    )

                    MdmHierarchyNode.objects.get_or_create(
                        tenant=tenant,
                        hierarchy_type="product_taxonomy",
                        code="industrial_tooling_taxonomy",
                        defaults={
                            "name": "Precision Industrial Tooling",
                            "item_category": demo_item_category,
                            "relationship_kind": "product_master_family",
                            "sort_order": 10,
                            "level": 1,
                            "description": "Top-level product taxonomy node for heavy tooling.",
                            "is_active": True,
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Master Data Management for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI Master Data Management already seeded for tenant: {tenant.name}")

            # --- 10.7 Data Catalog, Lineage & Governance ---
            if not CatalogAsset.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"  Seeding Data Catalog & Governance for tenant: {tenant.name}...")
                with transaction.atomic():
                    # Pick existing tenant entities
                    tenant_steward = get_user_model().objects.filter(tenant=tenant).first()
                    tbl_ref = WarehouseTable.objects.filter(tenant=tenant).first()
                    sem_ref = SemanticModel.objects.filter(tenant=tenant).first()
                    mdm_ref = MdmGoldenRecord.objects.filter(tenant=tenant).first()
                    term_ref = BusinessGlossaryTerm.objects.filter(tenant=tenant).first()
                    scorecard_ref = DataQualityScorecard.objects.filter(tenant=tenant).first()
                    etl_pipeline_ref = EtlPipeline.objects.filter(tenant=tenant).first()
                    etl_step_ref = TransformationStep.objects.filter(tenant=tenant).first()

                    today = timezone.now().date()

                    # 1. Governance Policies
                    pol_gdpr, _ = DataGovernancePolicy.objects.get_or_create(
                        tenant=tenant,
                        code="gdpr_pii_erasure_mandate",
                        defaults={
                            "name": "GDPR Customer PII Erasure & Redaction Mandate",
                            "policy_type": "regulatory_compliance",
                            "regulatory_framework": "gdpr_eu",
                            "enforcement_level": "strict_blocking",
                            "retention_period_days": 1095,
                            "masking_algorithm": "full_redaction",
                            "policy_owner": tenant_steward,
                            "effective_date": today,
                            "review_frequency_days": 365,
                            "compliance_notes": "GDPR Article 17 Right to Erasure & Article 32 Security of Processing.",
                            "description": "Enforces mandatory cryptographic masking on all customer personal identifying columns.",
                            "is_active": True,
                        },
                    )

                    pol_sox, _ = DataGovernancePolicy.objects.get_or_create(
                        tenant=tenant,
                        code="sox_7yr_financial_retention",
                        defaults={
                            "name": "SOX 7-Year Financial Audit Retention Schedule",
                            "policy_type": "retention_archival",
                            "regulatory_framework": "sox_financial",
                            "enforcement_level": "strict_blocking",
                            "retention_period_days": 2555,
                            "masking_algorithm": "none",
                            "policy_owner": tenant_steward,
                            "effective_date": today,
                            "review_frequency_days": 365,
                            "compliance_notes": "Sarbanes-Oxley Section 802 Criminal Penalties for Altering Documents.",
                            "description": "Mandates immutable retention of general ledger, billing marts, and journal line dimensions for 7 years.",
                            "is_active": True,
                        },
                    )

                    pol_pci, _ = DataGovernancePolicy.objects.get_or_create(
                        tenant=tenant,
                        code="pci_dss_payment_tokenization",
                        defaults={
                            "name": "PCI-DSS Cardholder Data Tokenization Standard",
                            "policy_type": "data_masking",
                            "regulatory_framework": "pci_dss",
                            "enforcement_level": "automated_masking",
                            "retention_period_days": 730,
                            "masking_algorithm": "hash_sha256",
                            "policy_owner": tenant_steward,
                            "effective_date": today,
                            "review_frequency_days": 180,
                            "compliance_notes": "PCI DSS Requirement 3: Protect Stored Cardholder Data.",
                            "description": "Requires SHA-256 cryptographic one-way hashing on all stored credit card primary account numbers.",
                            "is_active": True,
                        },
                    )

                    # 2. Catalog Assets
                    asset_cust, _ = CatalogAsset.objects.get_or_create(
                        tenant=tenant,
                        code="dim_customer_golden_master",
                        defaults={
                            "name": "Customer 360 Golden Dimension",
                            "domain": "customer",
                            "asset_type": "golden_record",
                            "golden_record": mdm_ref,
                            "warehouse_table": tbl_ref,
                            "business_glossary_term": term_ref,
                            "data_steward": tenant_steward,
                            "data_sensitivity": "restricted_pii",
                            "enterprise_tier": "tier_1_mission_critical",
                            "certification_status": "certified",
                            "average_rating": Decimal("4.85"),
                            "view_count": 142,
                            "quality_scorecard": scorecard_ref,
                            "schema_columns_json": [
                                {"name": "customer_key", "data_type": "varchar(64)", "is_nullable": False, "is_pii": True, "description": "Surrogate golden master key"},
                                {"name": "legal_company_name", "data_type": "varchar(255)", "is_nullable": False, "is_pii": False, "description": "Authoritative company legal entity"},
                                {"name": "tax_registration_id", "data_type": "varchar(40)", "is_nullable": True, "is_pii": True, "description": "Federal or state tax ID"},
                                {"name": "contact_email", "data_type": "varchar(120)", "is_nullable": True, "is_pii": True, "description": "Primary operational contact email"},
                            ],
                            "search_tags_json": ["customer", "golden_master", "mdm", "pii", "certified"],
                            "description": "Authoritative single-version-of-truth customer master record consolidating ERP and CRM entities.",
                            "is_active": True,
                        },
                    )

                    asset_sales, _ = CatalogAsset.objects.get_or_create(
                        tenant=tenant,
                        code="fct_sales_orders_mart",
                        defaults={
                            "name": "Enterprise Sales & Billing Ledger Mart",
                            "domain": "sales",
                            "asset_type": "warehouse_table",
                            "warehouse_table": tbl_ref,
                            "data_steward": tenant_steward,
                            "data_sensitivity": "internal",
                            "enterprise_tier": "tier_1_mission_critical",
                            "certification_status": "certified",
                            "average_rating": Decimal("4.90"),
                            "view_count": 215,
                            "quality_scorecard": scorecard_ref,
                            "schema_columns_json": [
                                {"name": "order_id", "data_type": "bigint", "is_nullable": False, "is_pii": False, "description": "Unique transaction identifier"},
                                {"name": "customer_key", "data_type": "varchar(64)", "is_nullable": False, "is_pii": True, "description": "Foreign key to dim_customer_master"},
                                {"name": "net_amount", "data_type": "decimal(18,2)", "is_nullable": False, "is_pii": False, "description": "Net billed sales amount"},
                                {"name": "transaction_date", "data_type": "date", "is_nullable": False, "is_pii": False, "description": "Accounting transaction date"},
                            ],
                            "search_tags_json": ["sales", "revenue", "orders", "sox", "tier1"],
                            "description": "Consolidated fact table containing customer orders and invoicing lines.",
                            "is_active": True,
                        },
                    )

                    asset_arr, _ = CatalogAsset.objects.get_or_create(
                        tenant=tenant,
                        code="sem_arr_performance_model",
                        defaults={
                            "name": "Annual Recurring Revenue (ARR) Analytics",
                            "domain": "finance",
                            "asset_type": "semantic_model",
                            "semantic_model": sem_ref,
                            "business_glossary_term": term_ref,
                            "data_steward": tenant_steward,
                            "data_sensitivity": "confidential",
                            "enterprise_tier": "tier_2_production_core",
                            "certification_status": "endorsed",
                            "average_rating": Decimal("4.70"),
                            "view_count": 94,
                            "search_tags_json": ["finance", "arr", "saas", "mrr", "kpi"],
                            "description": "Governed semantic layer model calculating normalized ARR, expansion revenue, and churn.",
                            "is_active": True,
                        },
                    )

                    asset_legacy, _ = CatalogAsset.objects.get_or_create(
                        tenant=tenant,
                        code="stg_legacy_crm_raw",
                        defaults={
                            "name": "Legacy CRM Ingestion Staging Dump",
                            "domain": "customer",
                            "asset_type": "source_dataset",
                            "data_steward": tenant_steward,
                            "data_sensitivity": "restricted_pii",
                            "enterprise_tier": "tier_4_sandbox",
                            "certification_status": "deprecated",
                            "deprecation_replacement": asset_cust,
                            "average_rating": Decimal("2.50"),
                            "view_count": 18,
                            "search_tags_json": ["deprecated", "raw", "staging", "legacy"],
                            "description": "Historical pre-MDM CRM dump table. Deprecated; migrate all analytics to Customer 360 Golden Dimension.",
                            "is_active": True,
                        },
                    )

                    # 3. Lineage Edges
                    CatalogLineageEdge.objects.get_or_create(
                        tenant=tenant,
                        upstream_asset=asset_legacy,
                        downstream_asset=asset_cust,
                        lineage_type="pipeline_transformation",
                        defaults={
                            "upstream_column": "client_raw_name",
                            "downstream_column": "legal_company_name",
                            "transformation_rule": "SELECT standardize_name(client_raw_name), dedupe_tax_id(raw_tax) FROM stg_legacy_crm_raw",
                            "etl_pipeline": etl_pipeline_ref,
                            "transformation_step": etl_step_ref,
                            "impact_criticality": "critical",
                            "is_automated_extraction": True,
                            "last_verified_at": timezone.now(),
                            "notes": "Automated ETL cleansing step converting raw staging strings into validated golden records.",
                            "is_active": True,
                        },
                    )

                    CatalogLineageEdge.objects.get_or_create(
                        tenant=tenant,
                        upstream_asset=asset_cust,
                        downstream_asset=asset_sales,
                        lineage_type="column_level",
                        defaults={
                            "upstream_column": "customer_key",
                            "downstream_column": "customer_key",
                            "transformation_rule": "JOIN dim_customer_golden_master ON fct_sales.customer_key = dim_customer.customer_key",
                            "impact_criticality": "high",
                            "is_automated_extraction": True,
                            "last_verified_at": timezone.now(),
                            "notes": "Dimensional foreign key constraint linking sales ledger to master customer record.",
                            "is_active": True,
                        },
                    )

                    CatalogLineageEdge.objects.get_or_create(
                        tenant=tenant,
                        upstream_asset=asset_sales,
                        downstream_asset=asset_arr,
                        lineage_type="semantic_abstraction",
                        defaults={
                            "upstream_column": "net_amount",
                            "downstream_column": "normalized_arr",
                            "transformation_rule": "SELECT SUM(net_amount * (12.0 / contract_months)) AS normalized_arr GROUP BY customer_key, fiscal_period",
                            "impact_criticality": "critical",
                            "is_automated_extraction": False,
                            "last_verified_at": timezone.now(),
                            "notes": "Governed calculation formula computing recurring revenue streams.",
                            "is_active": True,
                        },
                    )

                    # 4. Trust Endorsements
                    if tenant_steward:
                        CatalogTrustEndorsement.objects.get_or_create(
                            tenant=tenant,
                            asset=asset_cust,
                            endorsement_type="formal_certification",
                            defaults={
                                "verdict": "approved_certified",
                                "rating_value": 5,
                                "attested_by": tenant_steward,
                                "valid_until": today.replace(year=today.year + 1),
                                "criteria_checklist_json": {
                                    "schema_documented": True,
                                    "quality_sla_passed": True,
                                    "ownership_verified": True,
                                    "lineage_complete": True,
                                },
                                "review_comments": "Formal annual certification completed. 100% attribute provenance verified with full GDPR erasure compliance.",
                                "is_active": True,
                            },
                        )

                        CatalogTrustEndorsement.objects.get_or_create(
                            tenant=tenant,
                            asset=asset_sales,
                            endorsement_type="audit_clearance",
                            defaults={
                                "verdict": "approved_certified",
                                "rating_value": 5,
                                "attested_by": tenant_steward,
                                "valid_until": today.replace(year=today.year + 1),
                                "criteria_checklist_json": {
                                    "schema_documented": True,
                                    "quality_sla_passed": True,
                                    "ownership_verified": True,
                                    "lineage_complete": True,
                                },
                                "review_comments": "SOX Section 404 internal audit sign-off completed. Provenance and lineage fully audited.",
                                "is_active": True,
                            },
                        )

                        CatalogTrustEndorsement.objects.get_or_create(
                            tenant=tenant,
                            asset=asset_legacy,
                            endorsement_type="deprecation_notice",
                            defaults={
                                "verdict": "deprecated_scheduled_retirement",
                                "rating_value": 2,
                                "attested_by": tenant_steward,
                                "criteria_checklist_json": {
                                    "schema_documented": False,
                                    "quality_sla_passed": False,
                                    "ownership_verified": True,
                                    "lineage_complete": True,
                                },
                                "review_comments": "Superseded by Customer 360 Golden Dimension. Do not use for new reporting.",
                                "is_active": True,
                            },
                        )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Data Catalog & Governance for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI Data Catalog & Governance already seeded for tenant: {tenant.name}")

            # -------------------------------------------------------------
            # Sub-module 10.8: Dashboards & Visualization
            # -------------------------------------------------------------
            if not BiDashboard.objects.filter(tenant=tenant).exists():
                self.stdout.write(f"  Seeding BI Dashboards & Visualization for tenant: {tenant.name}...")
                with transaction.atomic():
                    tenant_admin = (
                        User.objects.filter(username__in=[f"admin_{tenant.slug}", "admin_acme", "admin_globex"]).first()
                        or User.objects.filter(is_superuser=True).first()
                    )

                    sem_ref = SemanticModel.objects.filter(tenant=tenant).first()
                    calc_ref = CalculatedMeasure.objects.filter(tenant=tenant).first()
                    wh_ref = WarehouseTable.objects.filter(tenant=tenant).first()

                    # 1. Dashboards
                    dsh_exec, _ = BiDashboard.objects.get_or_create(
                        tenant=tenant,
                        slug="executive-performance-command-center",
                        defaults={
                            "title": "Executive Performance Command Center",
                            "category": "executive",
                            "layout_type": "grid_12",
                            "theme": "slate_corporate",
                            "refresh_interval_seconds": 60,
                            "role_required": "all",
                            "is_published": True,
                            "is_template": False,
                            "is_default": True,
                            "is_kiosk_enabled": True,
                            "created_by": tenant_admin,
                            "description": "C-Suite consolidated KPI overview across net revenue, operating margins, customer growth, and departmental performance.",
                            "is_active": True,
                        },
                    )

                    dsh_ops, _ = BiDashboard.objects.get_or_create(
                        tenant=tenant,
                        slug="operational-monitoring-board",
                        defaults={
                            "title": "Plant & Supply Chain Operational Monitoring Board",
                            "category": "operations",
                            "layout_type": "operational_monitoring",
                            "theme": "amber_industrial",
                            "refresh_interval_seconds": 30,
                            "role_required": "operations",
                            "is_published": True,
                            "is_template": True,
                            "is_default": False,
                            "is_kiosk_enabled": True,
                            "created_by": tenant_admin,
                            "description": "High-frequency streaming telemetry board tracking line throughput, SLA fulfillment, and ingestion health.",
                            "is_active": True,
                        },
                    )

                    dsh_sales, _ = BiDashboard.objects.get_or_create(
                        tenant=tenant,
                        slug="sales-conversion-funnel-analytics",
                        defaults={
                            "title": "Sales Performance & Conversion Funnel",
                            "category": "sales_crm",
                            "layout_type": "executive_summary",
                            "theme": "emerald_growth",
                            "refresh_interval_seconds": 300,
                            "role_required": "all",
                            "is_published": True,
                            "is_template": False,
                            "is_default": False,
                            "is_kiosk_enabled": False,
                            "created_by": tenant_admin,
                            "description": "Deep-dive sales analytics mapping pipeline conversion ratios, deal velocity, and regional quotas.",
                            "is_active": True,
                        },
                    )

                    # 2. Widgets on Executive Dashboard
                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        title="Total Net Billed Revenue (YTD)",
                        defaults={
                            "subtitle": "Consolidated Financial Performance",
                            "widget_type": "kpi_card",
                            "semantic_model": sem_ref,
                            "calculated_measure": calc_ref,
                            "aggregation_type": "sum",
                            "pos_x": 0,
                            "pos_y": 0,
                            "width_cols": 4,
                            "height_rows": 3,
                            "refresh_interval_seconds": 60,
                            "drilldown_target_url": "/bi/dashboards/widgets/",
                            "sort_order": 10,
                            "is_active": True,
                        },
                    )

                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        title="Operating Margin %",
                        defaults={
                            "subtitle": "EBITDA Margin Efficiency",
                            "widget_type": "kpi_card",
                            "calculated_measure": calc_ref,
                            "aggregation_type": "avg",
                            "pos_x": 4,
                            "pos_y": 0,
                            "width_cols": 4,
                            "height_rows": 3,
                            "sort_order": 20,
                            "is_active": True,
                        },
                    )

                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        title="Customer Retention & ARR Expansion",
                        defaults={
                            "subtitle": "Net Retention Rate (112%)",
                            "widget_type": "kpi_card",
                            "aggregation_type": "avg",
                            "pos_x": 8,
                            "pos_y": 0,
                            "width_cols": 4,
                            "height_rows": 3,
                            "sort_order": 30,
                            "is_active": True,
                        },
                    )

                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        title="Quarterly Revenue Trajectory vs Target",
                        defaults={
                            "subtitle": "Quarterly Trend (Actual vs Budget)",
                            "widget_type": "line",
                            "semantic_model": sem_ref,
                            "aggregation_type": "sum",
                            "pos_x": 0,
                            "pos_y": 3,
                            "width_cols": 8,
                            "height_rows": 6,
                            "sort_order": 40,
                            "is_active": True,
                        },
                    )

                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        title="Revenue Distribution by Product Line",
                        defaults={
                            "subtitle": "Product Portfolio Composition",
                            "widget_type": "donut",
                            "warehouse_table": wh_ref,
                            "aggregation_type": "sum",
                            "pos_x": 8,
                            "pos_y": 3,
                            "width_cols": 4,
                            "height_rows": 6,
                            "sort_order": 50,
                            "is_active": True,
                        },
                    )

                    # 3. Widgets on Operational Monitoring Board
                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_ops,
                        title="Real-Time Data Ingestion Throughput",
                        defaults={
                            "subtitle": "Events Processed / Second",
                            "widget_type": "streaming_counter",
                            "aggregation_type": "last",
                            "pos_x": 0,
                            "pos_y": 0,
                            "width_cols": 4,
                            "height_rows": 4,
                            "refresh_interval_seconds": 10,
                            "sort_order": 10,
                            "is_active": True,
                        },
                    )

                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_ops,
                        title="Pipeline Processing Latency & Volume",
                        defaults={
                            "subtitle": "Hourly Ingestion Micro-Batches",
                            "widget_type": "area",
                            "aggregation_type": "sum",
                            "pos_x": 4,
                            "pos_y": 0,
                            "width_cols": 8,
                            "height_rows": 4,
                            "sort_order": 20,
                            "is_active": True,
                        },
                    )

                    # 4. Widgets on Sales Conversion Dashboard
                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_sales,
                        title="Enterprise Opportunity Conversion Funnel",
                        defaults={
                            "subtitle": "Lead -> Qualification -> Proposal -> Won",
                            "widget_type": "funnel",
                            "aggregation_type": "count",
                            "pos_x": 0,
                            "pos_y": 0,
                            "width_cols": 6,
                            "height_rows": 6,
                            "sort_order": 10,
                            "is_active": True,
                        },
                    )

                    BiDashboardWidget.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_sales,
                        title="Regional Opportunity Velocity",
                        defaults={
                            "subtitle": "Quarterly Win Rates by Territory",
                            "widget_type": "bar",
                            "aggregation_type": "avg",
                            "pos_x": 6,
                            "pos_y": 0,
                            "width_cols": 6,
                            "height_rows": 6,
                            "sort_order": 20,
                            "is_active": True,
                        },
                    )

                    # 5. Global Filter Controls on Executive Dashboard
                    BiDashboardFilter.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        filter_key="fiscal_period",
                        defaults={
                            "filter_label": "Fiscal Period",
                            "filter_type": "dropdown",
                            "target_field": "fiscal_period",
                            "default_value": "2026-Q4",
                            "options_source": "static_list",
                            "static_options_json": [
                                {"value": "2026-Q1", "label": "FY2026 Q1"},
                                {"value": "2026-Q2", "label": "FY2026 Q2"},
                                {"value": "2026-Q3", "label": "FY2026 Q3"},
                                {"value": "2026-Q4", "label": "FY2026 Q4"},
                            ],
                            "order": 10,
                            "is_required": False,
                            "is_active": True,
                        },
                    )

                    BiDashboardFilter.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        filter_key="region",
                        defaults={
                            "filter_label": "Market Region",
                            "filter_type": "dropdown",
                            "target_field": "market_region",
                            "default_value": "all",
                            "options_source": "static_list",
                            "static_options_json": [
                                {"value": "all", "label": "All Regions"},
                                {"value": "na", "label": "North America"},
                                {"value": "emea", "label": "Europe & Middle East"},
                                {"value": "apac", "label": "Asia-Pacific"},
                            ],
                            "order": 20,
                            "is_required": False,
                            "is_active": True,
                        },
                    )

                    BiDashboardFilter.objects.get_or_create(
                        tenant=tenant,
                        dashboard=dsh_exec,
                        filter_key="date_range",
                        defaults={
                            "filter_label": "Date Horizon",
                            "filter_type": "date_preset",
                            "target_field": "transaction_date",
                            "default_value": "ytd",
                            "options_source": "static_list",
                            "order": 30,
                            "is_required": False,
                            "is_active": True,
                        },
                    )

                    # 6. Saved Bookmarks
                    if tenant_admin:
                        BiDashboardBookmark.objects.get_or_create(
                            tenant=tenant,
                            dashboard=dsh_exec,
                            user=tenant_admin,
                            name="North America Q4 Executive Focus",
                            defaults={
                                "filter_state_json": {
                                    "fiscal_period": "2026-Q4",
                                    "region": "na",
                                    "date_range": "qtd",
                                },
                                "crossfilter_state_json": {},
                                "is_default": True,
                                "is_shared": True,
                                "description": "Default C-suite perspective filtered to North American operations for Q4.",
                                "is_active": True,
                            },
                        )

                        BiDashboardBookmark.objects.get_or_create(
                            tenant=tenant,
                            dashboard=dsh_exec,
                            user=tenant_admin,
                            name="Global Full Year Baseline",
                            defaults={
                                "filter_state_json": {
                                    "fiscal_period": "2026-Q4",
                                    "region": "all",
                                    "date_range": "ytd",
                                },
                                "crossfilter_state_json": {},
                                "is_default": False,
                                "is_shared": True,
                                "description": "Global enterprise-wide year-to-date performance view.",
                                "is_active": True,
                            },
                        )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded BI Dashboards & Visualization for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  BI Dashboards & Visualization already seeded for tenant: {tenant.name}")

            # --- 10.9 Standard & Operational Reporting Seeding ---
            if not ReportDefinition.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    tenant_admin = User.objects.filter(tenant=tenant, username__startswith=f"admin_{tenant.slug}").first()
                    if not tenant_admin:
                        tenant_admin = User.objects.filter(tenant=tenant).first()

                    sem_finance = SemanticModel.objects.filter(tenant=tenant, name__icontains="finance").first()
                    sem_sales = SemanticModel.objects.filter(tenant=tenant, name__icontains="sales").first()
                    wh_table = WarehouseTable.objects.filter(tenant=tenant).first()

                    # 1. Pre-Built Reports
                    rpt_pnl, _ = ReportDefinition.objects.get_or_create(
                        tenant=tenant,
                        slug="monthly-profit-loss-statement",
                        defaults={
                            "name": f"{tenant.name} Monthly Profit & Loss Statement",
                            "category": "finance",
                            "report_type": "pixel_perfect_document",
                            "paper_size": "a4",
                            "orientation": "portrait",
                            "margins_json": {"top": 15, "bottom": 15, "left": 15, "right": 15},
                            "bands_config_json": {
                                "title_band": {"height_mm": 25, "include_logo": True},
                                "page_header": {"height_mm": 12, "repeat": True},
                                "group_header": {"field": "account_type", "height_mm": 10},
                                "detail_band": {"height_mm": 8},
                                "group_footer": {"height_mm": 10, "show_subtotal": True},
                                "summary_band": {"height_mm": 15, "show_grand_total": True},
                                "page_footer": {"height_mm": 10, "show_page_number": True},
                            },
                            "columns_config_json": [
                                {"field": "row_id", "title": "#", "width": "8%", "align": "center"},
                                {"field": "item_code", "title": "GL Account Code", "width": "22%", "align": "left"},
                                {"field": "description", "title": "Account Title & Category", "width": "45%", "align": "left"},
                                {"field": "amount", "title": "Net Amount (USD)", "width": "25%", "align": "right", "format": "currency"},
                            ],
                            "watermark_text": "CONFIDENTIAL",
                            "semantic_model": sem_finance,
                            "warehouse_table": wh_table,
                            "created_by": tenant_admin,
                            "status": "published",
                            "is_prebuilt_template": True,
                            "description": "Standard audited income statement displaying gross margin, operating expenses, and net profit variance.",
                        },
                    )

                    rpt_sales, _ = ReportDefinition.objects.get_or_create(
                        tenant=tenant,
                        slug="sales-pipeline-customer-revenue",
                        defaults={
                            "name": f"{tenant.name} Sales Pipeline & Customer Revenue",
                            "category": "sales",
                            "report_type": "standard_tabular",
                            "paper_size": "letter",
                            "orientation": "landscape",
                            "margins_json": {"top": 12, "bottom": 12, "left": 15, "right": 15},
                            "columns_config_json": [
                                {"field": "row_id", "title": "#", "width": "5%", "align": "center"},
                                {"field": "item_code", "title": "Customer Ref", "width": "20%", "align": "left"},
                                {"field": "description", "title": "Account Name / Segment", "width": "45%", "align": "left"},
                                {"field": "amount", "title": "YTD Bookings ($)", "width": "30%", "align": "right", "format": "currency"},
                            ],
                            "semantic_model": sem_sales,
                            "created_by": tenant_admin,
                            "status": "published",
                            "is_prebuilt_template": True,
                            "description": "Comprehensive operational sales performance breakdown by client account and rep territory.",
                        },
                    )

                    rpt_inv, _ = ReportDefinition.objects.get_or_create(
                        tenant=tenant,
                        slug="inventory-valuation-aging-schedule",
                        defaults={
                            "name": f"{tenant.name} Inventory Valuation & Aging Schedule",
                            "category": "inventory",
                            "report_type": "standard_tabular",
                            "paper_size": "a4",
                            "orientation": "portrait",
                            "columns_config_json": [
                                {"field": "row_id", "title": "#", "width": "8%", "align": "center"},
                                {"field": "item_code", "title": "SKU / Part Number", "width": "22%", "align": "left"},
                                {"field": "description", "title": "Product Title / Category", "width": "45%", "align": "left"},
                                {"field": "amount", "title": "Inventory Value ($)", "width": "25%", "align": "right", "format": "currency"},
                            ],
                            "warehouse_table": wh_table,
                            "created_by": tenant_admin,
                            "status": "published",
                            "is_prebuilt_template": True,
                            "description": "Audited stock valuation schedule categorized by turnover velocity and warehouse storage bins.",
                        },
                    )

                    rpt_hr, _ = ReportDefinition.objects.get_or_create(
                        tenant=tenant,
                        slug="department-headcount-payroll-summary",
                        defaults={
                            "name": f"{tenant.name} Department Headcount & Payroll Register",
                            "category": "hr",
                            "report_type": "matrix_summary",
                            "paper_size": "letter",
                            "orientation": "landscape",
                            "columns_config_json": [
                                {"field": "row_id", "title": "#", "width": "8%", "align": "center"},
                                {"field": "item_code", "title": "Cost Center", "width": "22%", "align": "left"},
                                {"field": "description", "title": "Department & Role Level", "width": "45%", "align": "left"},
                                {"field": "amount", "title": "Monthly Base Payroll ($)", "width": "25%", "align": "right", "format": "currency"},
                            ],
                            "created_by": tenant_admin,
                            "status": "published",
                            "is_prebuilt_template": True,
                            "description": "Cross-tabulation of departmental staffing levels, overtime expenses, and benefit provisions.",
                        },
                    )

                    # 2. Prompt Parameters
                    ReportParameter.objects.get_or_create(
                        tenant=tenant,
                        report=rpt_pnl,
                        parameter_name="fiscal_year",
                        defaults={
                            "prompt_label": "Fiscal Year",
                            "parameter_type": "choice_single",
                            "default_value": "2026",
                            "choices_source": "static_list",
                            "choices_config_json": [
                                {"value": "2026", "label": "FY 2026 (Current)"},
                                {"value": "2025", "label": "FY 2025"},
                                {"value": "2024", "label": "FY 2024"},
                            ],
                            "prompt_order": 10,
                            "is_required": True,
                            "is_active": True,
                        },
                    )

                    ReportParameter.objects.get_or_create(
                        tenant=tenant,
                        report=rpt_pnl,
                        parameter_name="as_of_date",
                        defaults={
                            "prompt_label": "Period End Date",
                            "parameter_type": "date",
                            "default_value": "2026-10-31",
                            "choices_source": "static_list",
                            "prompt_order": 20,
                            "is_required": False,
                            "is_active": True,
                        },
                    )

                    ReportParameter.objects.get_or_create(
                        tenant=tenant,
                        report=rpt_sales,
                        parameter_name="sales_territory",
                        defaults={
                            "prompt_label": "Sales Territory",
                            "parameter_type": "choice_single",
                            "default_value": "all",
                            "choices_source": "static_list",
                            "choices_config_json": [
                                {"value": "all", "label": "All Territories"},
                                {"value": "na", "label": "North America"},
                                {"value": "emea", "label": "Europe & Middle East"},
                                {"value": "apac", "label": "Asia-Pacific"},
                            ],
                            "prompt_order": 10,
                            "is_required": False,
                            "is_active": True,
                        },
                    )

                    # 3. Drill-Through Paths
                    ReportDrillPath.objects.get_or_create(
                        tenant=tenant,
                        source_report=rpt_sales,
                        source_field="item_code",
                        defaults={
                            "drill_label": "Inspect Customer 360 Account",
                            "target_type": "erp_record_url",
                            "target_url_pattern": "/crm/accounts/{customer_code}/",
                            "parameter_mapping_json": {"item_code": "customer_code"},
                            "sort_order": 10,
                            "is_enabled": True,
                        },
                    )

                    ReportDrillPath.objects.get_or_create(
                        tenant=tenant,
                        source_report=rpt_pnl,
                        source_field="item_code",
                        defaults={
                            "drill_label": "Drill to Detailed Line Items",
                            "target_type": "operational_report",
                            "target_report": rpt_sales,
                            "parameter_mapping_json": {"item_code": "gl_account"},
                            "sort_order": 20,
                            "is_enabled": True,
                        },
                    )

                    # 4. Execution Logs
                    ReportExecution.objects.get_or_create(
                        tenant=tenant,
                        report=rpt_pnl,
                        output_format="pdf",
                        defaults={
                            "executed_by": tenant_admin,
                            "execution_mode": "export_pdf",
                            "execution_status": "completed",
                            "duration_ms": 240,
                            "row_count": 6,
                            "output_file_name": "monthly-profit-loss-statement_20261101.pdf",
                            "file_size_bytes": 148200,
                            "parameter_values_json": {"fiscal_year": "2026", "as_of_date": "2026-10-31"},
                        },
                    )

                    ReportExecution.objects.get_or_create(
                        tenant=tenant,
                        report=rpt_sales,
                        output_format="html",
                        defaults={
                            "executed_by": tenant_admin,
                            "execution_mode": "interactive_view",
                            "execution_status": "completed",
                            "duration_ms": 115,
                            "row_count": 6,
                            "parameter_values_json": {"sales_territory": "all"},
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded Standard & Operational Reporting for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  Standard & Operational Reporting already seeded for tenant: {tenant.name}")

            # =========================================================================
            # SUB-MODULE 10.10: Self-Service & Ad-Hoc Analytics
            # =========================================================================
            if not AdHocQuery.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    User = get_user_model()
                    tenant_admin = User.objects.filter(tenant=tenant, username__startswith=f"admin_{tenant.slug}").first() or User.objects.filter(tenant=tenant).first()

                    # Reference semantic models from 10.4 if available
                    smdl_sales = SemanticModel.objects.filter(tenant=tenant).first()
                    smdl_procure = SemanticModel.objects.filter(tenant=tenant).exclude(pk=smdl_sales.pk).first() if smdl_sales else smdl_sales
                    wtbl_fin = WarehouseTable.objects.filter(tenant=tenant, table_type="fact").first()

                    # 1. Data Blend Definition
                    blend_mashup, _ = DataBlendDefinition.objects.get_or_create(
                        tenant=tenant,
                        slug="sales-procurement-mashup",
                        defaults={
                            "name": "Sales Opportunities & SCM Procurement Mashup",
                            "description": "Cross-dataset blend linking sales demand with supply chain vendor procurement commitments.",
                            "primary_source_type": "semantic_model",
                            "primary_semantic_model": smdl_sales,
                            "secondary_source_type": "semantic_model",
                            "secondary_semantic_model": smdl_procure,
                            "join_type": "left_outer",
                            "cardinality": "many_to_one",
                            "join_keys_mapping_json": [
                                {"primary_field": "partner_id", "secondary_field": "vendor_partner_id"}
                            ],
                            "collision_resolution": "prefix_secondary",
                            "status": "active",
                            "created_by": tenant_admin,
                        },
                    )

                    # 2. Ad-Hoc Queries
                    q_revenue, _ = AdHocQuery.objects.get_or_create(
                        tenant=tenant,
                        slug="quarterly-revenue-profitability",
                        defaults={
                            "name": "Quarterly Revenue & Profitability Exploration",
                            "description": "Exploratory ad-hoc analysis evaluating quarterly revenue trends, gross profit, and order volumes across regions.",
                            "source_type": "semantic_model" if smdl_sales else "warehouse_table",
                            "semantic_model": smdl_sales,
                            "warehouse_table": wtbl_fin if not smdl_sales else None,
                            "fields_config_json": [
                                {"field": "fiscal_period", "label": "Fiscal Period", "type": "string", "agg": "none"},
                                {"field": "gross_revenue", "label": "Gross Revenue", "type": "currency", "agg": "sum"},
                                {"field": "cogs", "label": "Cost of Goods Sold", "type": "currency", "agg": "sum"},
                                {"field": "orders_count", "label": "Total Orders", "type": "integer", "agg": "count"},
                            ],
                            "filter_criteria_json": [
                                {"field": "fiscal_period", "operator": "starts_with", "value": "2026"}
                            ],
                            "sort_config_json": [
                                {"field": "fiscal_period", "direction": "asc"}
                            ],
                            "visualization_type": "bar_chart",
                            "chart_config_json": {"palette": "corporate_blue", "show_legend": True},
                            "row_limit": 500,
                            "status": "active",
                            "last_executed_at": timezone.now(),
                            "execution_duration_ms": 34,
                            "row_count": 4,
                            "created_by": tenant_admin,
                        },
                    )

                    q_blend, _ = AdHocQuery.objects.get_or_create(
                        tenant=tenant,
                        slug="customer-acquisition-order-volume",
                        defaults={
                            "name": "Customer Acquisition & Procurement Volume Mashup",
                            "description": "Blended exploratory dataset evaluating customer acquisition pipeline alongside vendor supplier fulfillments.",
                            "source_type": "blend",
                            "data_blend": blend_mashup,
                            "fields_config_json": [
                                {"field": "sales_region", "label": "Sales Region", "type": "string", "agg": "none"},
                                {"field": "customer_count", "label": "New Customers", "type": "integer", "agg": "count_distinct"},
                                {"field": "order_value", "label": "Order Value", "type": "currency", "agg": "sum"},
                            ],
                            "filter_criteria_json": [],
                            "sort_config_json": [
                                {"field": "order_value", "direction": "desc"}
                            ],
                            "visualization_type": "line_chart",
                            "chart_config_json": {"palette": "emerald_trend"},
                            "row_limit": 500,
                            "status": "active",
                            "last_executed_at": timezone.now(),
                            "execution_duration_ms": 48,
                            "row_count": 5,
                            "created_by": tenant_admin,
                        },
                    )

                    # 3. Custom Calculated Fields
                    AdHocCalculatedField.objects.get_or_create(
                        tenant=tenant,
                        query=q_revenue,
                        field_name="profit_margin_pct",
                        defaults={
                            "display_label": "Profit Margin Percentage",
                            "formula_expression": "(([gross_revenue] - [cogs]) / [gross_revenue]) * 100",
                            "return_type": "percentage",
                            "aggregation_mode": "post_agg",
                            "is_valid": True,
                            "created_by": tenant_admin,
                        },
                    )

                    AdHocCalculatedField.objects.get_or_create(
                        tenant=tenant,
                        query=q_revenue,
                        field_name="average_order_value",
                        defaults={
                            "display_label": "Average Order Value (AOV)",
                            "formula_expression": "[gross_revenue] / [orders_count]",
                            "return_type": "currency",
                            "aggregation_mode": "formula",
                            "is_valid": True,
                            "created_by": tenant_admin,
                        },
                    )

                    # 4. Saved Analysis Views
                    SavedAnalysisView.objects.get_or_create(
                        tenant=tenant,
                        slug="exec-2026-margin-explore",
                        defaults={
                            "name": "Executive 2026 Margin Exploration",
                            "description": "Standard exploratory view tracking Q1-Q4 quarterly revenue profitability and margin margins.",
                            "query": q_revenue,
                            "sharing_scope": "tenant_public",
                            "is_template": True,
                            "is_favorite": True,
                            "view_count": 18,
                            "last_viewed_at": timezone.now(),
                            "created_by": tenant_admin,
                        },
                    )

                    SavedAnalysisView.objects.get_or_create(
                        tenant=tenant,
                        slug="territory-sales-scm-view",
                        defaults={
                            "name": "Territory Sales vs SCM Blend Analysis",
                            "description": "Departmental exploration view showing cross-dataset pipeline against supplier orders.",
                            "query": q_blend,
                            "sharing_scope": "team",
                            "is_template": False,
                            "is_favorite": False,
                            "view_count": 9,
                            "last_viewed_at": timezone.now(),
                            "created_by": tenant_admin,
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded Self-Service & Ad-Hoc Analytics for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  Self-Service & Ad-Hoc Analytics already seeded for tenant: {tenant.name}")

            # ---------------------------------------------------------
            # 10.11 KPI & Performance Scorecards
            # ---------------------------------------------------------
            if not KpiDefinition.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    from apps.core.models.OrgUnit import OrgUnit
                    from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure

                    tenant_admin = get_user_model().objects.filter(tenant=tenant).first()
                    first_org = OrgUnit.objects.filter(tenant=tenant).first()
                    semantic_measure = CalculatedMeasure.objects.filter(tenant=tenant).first()

                    # 1. Seed Strategic Objectives (across 4 BSC perspectives)
                    obj_fin, _ = StrategicObjective.objects.get_or_create(
                        tenant=tenant,
                        code="STRAT-FIN-01",
                        defaults={
                            "name": "Accelerate High-Margin Recurring Revenue",
                            "slug": "accelerate-high-margin-recurring-revenue",
                            "perspective": "financial",
                            "statement_of_intent": "Drive sustainable operating profitability and maximize recurring EBITDA margins through enterprise expansion.",
                            "status": "active",
                            "rag_status": "green",
                            "alignment_score": Decimal("92.00"),
                            "owner": tenant_admin,
                            "org_unit": first_org,
                            "sort_order": 10,
                        },
                    )

                    obj_cust, _ = StrategicObjective.objects.get_or_create(
                        tenant=tenant,
                        code="STRAT-CUST-01",
                        defaults={
                            "name": "Maximize Customer Lifetime Value & Retention",
                            "slug": "maximize-customer-lifetime-value",
                            "perspective": "customer",
                            "statement_of_intent": "Deliver superior digital experiences to exceed industry benchmark NPS and reduce annualized client churn below 3%.",
                            "parent_objective": obj_fin,
                            "status": "active",
                            "rag_status": "green",
                            "alignment_score": Decimal("88.00"),
                            "owner": tenant_admin,
                            "org_unit": first_org,
                            "sort_order": 20,
                        },
                    )

                    obj_proc, _ = StrategicObjective.objects.get_or_create(
                        tenant=tenant,
                        code="STRAT-PROC-01",
                        defaults={
                            "name": "Streamline Order Fulfillment & Operational Efficiency",
                            "slug": "streamline-order-fulfillment",
                            "perspective": "internal_process",
                            "statement_of_intent": "Shorten manufacturing and procurement cycle times through automated ERP workflows and rigorous quality control.",
                            "parent_objective": obj_cust,
                            "status": "active",
                            "rag_status": "green",
                            "alignment_score": Decimal("85.00"),
                            "owner": tenant_admin,
                            "org_unit": first_org,
                            "sort_order": 30,
                        },
                    )

                    obj_lrn, _ = StrategicObjective.objects.get_or_create(
                        tenant=tenant,
                        code="STRAT-LRN-01",
                        defaults={
                            "name": "Cultivate Data-Driven Analytics Culture",
                            "slug": "cultivate-data-driven-analytics-culture",
                            "perspective": "learning_growth",
                            "statement_of_intent": "Certify 80% of management workforce on self-service BI analytics and strategy alignment tools.",
                            "parent_objective": obj_proc,
                            "status": "active",
                            "rag_status": "green",
                            "alignment_score": Decimal("90.00"),
                            "owner": tenant_admin,
                            "org_unit": first_org,
                            "sort_order": 40,
                        },
                    )

                    # 2. Seed Master KPI Definitions
                    kpi_om, _ = KpiDefinition.objects.get_or_create(
                        tenant=tenant,
                        code="KPI-FIN-01",
                        defaults={
                            "name": "Operating Profit Margin",
                            "slug": "operating-profit-margin",
                            "description": "Operating income divided by total gross net revenue.",
                            "category": "profitability",
                            "perspective": "financial",
                            "target_direction": "maximize",
                            "unit_of_measure": "percentage",
                            "tracking_frequency": "monthly",
                            "calculation_type": "semantic_measure" if semantic_measure else "formula_expression",
                            "semantic_measure": semantic_measure,
                            "formula_expression": "[operating_income] / [gross_revenue] * 100",
                            "target_value": Decimal("24.0000"),
                            "warning_threshold": Decimal("20.0000"),
                            "critical_threshold": Decimal("16.0000"),
                            "current_value": Decimal("25.4000"),
                            "previous_value": Decimal("23.8000"),
                            "industry_benchmark_value": Decimal("22.0000"),
                            "benchmark_source": "Gartner Peer Insights 2026",
                            "benchmark_percentile": 80,
                            "status": "active",
                            "is_active": True,
                            "owner": tenant_admin,
                            "department": first_org,
                        },
                    )

                    kpi_nps, _ = KpiDefinition.objects.get_or_create(
                        tenant=tenant,
                        code="KPI-CUST-01",
                        defaults={
                            "name": "Net Promoter Score (NPS)",
                            "slug": "net-promoter-score",
                            "description": "Customer advocacy index calculated from quarterly customer surveys.",
                            "category": "customer_experience",
                            "perspective": "customer",
                            "target_direction": "maximize",
                            "unit_of_measure": "score",
                            "tracking_frequency": "quarterly",
                            "calculation_type": "manual",
                            "target_value": Decimal("65.0000"),
                            "warning_threshold": Decimal("50.0000"),
                            "critical_threshold": Decimal("35.0000"),
                            "current_value": Decimal("68.0000"),
                            "previous_value": Decimal("62.0000"),
                            "industry_benchmark_value": Decimal("58.0000"),
                            "benchmark_source": "Satmetrix B2B SaaS Benchmark",
                            "benchmark_percentile": 75,
                            "status": "active",
                            "is_active": True,
                            "owner": tenant_admin,
                            "department": first_org,
                        },
                    )

                    kpi_cycle, _ = KpiDefinition.objects.get_or_create(
                        tenant=tenant,
                        code="KPI-PROC-01",
                        defaults={
                            "name": "Order Fulfillment Cycle Time",
                            "slug": "order-fulfillment-cycle-time",
                            "description": "Mean days elapsed between purchase order placement and customer delivery receipt.",
                            "category": "operations",
                            "perspective": "internal_process",
                            "target_direction": "minimize",
                            "unit_of_measure": "days",
                            "tracking_frequency": "weekly",
                            "calculation_type": "formula_expression",
                            "formula_expression": "[days_to_ship] + [days_in_transit]",
                            "target_value": Decimal("3.5000"),
                            "warning_threshold": Decimal("5.0000"),
                            "critical_threshold": Decimal("7.0000"),
                            "current_value": Decimal("3.2000"),
                            "previous_value": Decimal("3.8000"),
                            "industry_benchmark_value": Decimal("4.0000"),
                            "benchmark_source": "APQC Supply Chain Benchmark",
                            "benchmark_percentile": 85,
                            "status": "active",
                            "is_active": True,
                            "owner": tenant_admin,
                            "department": first_org,
                        },
                    )

                    kpi_cert, _ = KpiDefinition.objects.get_or_create(
                        tenant=tenant,
                        code="KPI-LRN-01",
                        defaults={
                            "name": "Employee BI Certification Rate",
                            "slug": "employee-bi-certification-rate",
                            "description": "Percentage of staff completing annual data literacy and analytics curriculum.",
                            "category": "human_capital",
                            "perspective": "learning_growth",
                            "target_direction": "maximize",
                            "unit_of_measure": "percentage",
                            "tracking_frequency": "quarterly",
                            "calculation_type": "manual",
                            "target_value": Decimal("80.0000"),
                            "warning_threshold": Decimal("65.0000"),
                            "critical_threshold": Decimal("50.0000"),
                            "current_value": Decimal("84.0000"),
                            "previous_value": Decimal("76.0000"),
                            "industry_benchmark_value": Decimal("70.0000"),
                            "benchmark_source": "HR Open Standards 2026",
                            "benchmark_percentile": 78,
                            "status": "active",
                            "is_active": True,
                            "owner": tenant_admin,
                            "department": first_org,
                        },
                    )

                    # 3. Seed Performance Scorecard
                    scorecard, _ = PerformanceScorecard.objects.get_or_create(
                        tenant=tenant,
                        slug="2026-corporate-balanced-scorecard",
                        defaults={
                            "name": "2026 Corporate Balanced Scorecard",
                            "description": "Enterprise-level executive scorecard tracking corporate strategy across Kaplan & Norton's four core perspectives.",
                            "scorecard_type": "balanced_scorecard",
                            "review_period": "quarterly",
                            "fiscal_year": 2026,
                            "financial_weight": Decimal("25.00"),
                            "customer_weight": Decimal("25.00"),
                            "internal_process_weight": Decimal("25.00"),
                            "learning_growth_weight": Decimal("25.00"),
                            "overall_score": Decimal("91.50"),
                            "overall_rag_status": "green",
                            "status": "active",
                            "is_default": True,
                            "is_published": True,
                            "owner": tenant_admin,
                            "org_unit": first_org,
                        },
                    )

                    # 4. Seed Scorecard KPI Assignments
                    ScorecardKpiAssignment.objects.get_or_create(
                        tenant=tenant,
                        scorecard=scorecard,
                        kpi=kpi_om,
                        defaults={
                            "objective": obj_fin,
                            "perspective": "financial",
                            "weight": Decimal("100.00"),
                            "target_value": Decimal("24.0000"),
                            "actual_value": Decimal("25.4000"),
                            "benchmark_overlay_value": Decimal("22.0000"),
                            "manager_notes": "Operating margins exceeded plan by 1.4% due to ERP procurement cost reductions and cloud optimization.",
                            "sort_order": 10,
                        },
                    )

                    ScorecardKpiAssignment.objects.get_or_create(
                        tenant=tenant,
                        scorecard=scorecard,
                        kpi=kpi_nps,
                        defaults={
                            "objective": obj_cust,
                            "perspective": "customer",
                            "weight": Decimal("100.00"),
                            "target_value": Decimal("65.0000"),
                            "actual_value": Decimal("68.0000"),
                            "benchmark_overlay_value": Decimal("58.0000"),
                            "manager_notes": "Customer NPS at all-time high of +68 following introduction of real-time shipment visibility portal.",
                            "sort_order": 20,
                        },
                    )

                    ScorecardKpiAssignment.objects.get_or_create(
                        tenant=tenant,
                        scorecard=scorecard,
                        kpi=kpi_cycle,
                        defaults={
                            "objective": obj_proc,
                            "perspective": "internal_process",
                            "weight": Decimal("100.00"),
                            "target_value": Decimal("3.5000"),
                            "actual_value": Decimal("3.2000"),
                            "benchmark_overlay_value": Decimal("4.0000"),
                            "manager_notes": "Average fulfillment cycle shortened to 3.2 days, well ahead of industry baseline of 4.0 days.",
                            "sort_order": 30,
                        },
                    )

                    ScorecardKpiAssignment.objects.get_or_create(
                        tenant=tenant,
                        scorecard=scorecard,
                        kpi=kpi_cert,
                        defaults={
                            "objective": obj_lrn,
                            "perspective": "learning_growth",
                            "weight": Decimal("100.00"),
                            "target_value": Decimal("80.0000"),
                            "actual_value": Decimal("84.0000"),
                            "benchmark_overlay_value": Decimal("70.0000"),
                            "manager_notes": "84% staff analytics certification reached following rollout of Module 10 self-service learning paths.",
                            "sort_order": 40,
                        },
                    )

                    scorecard.recalculate_performance()

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded KPI & Performance Scorecards for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  KPI & Performance Scorecards already seeded for tenant: {tenant.name}")

            # ---------------------------------------------------------
            # 10.12 OLAP & Multidimensional Analysis
            # ---------------------------------------------------------
            if not OlapCube.objects.filter(tenant=tenant).exists():
                with transaction.atomic():
                    from apps.accounting.models import Budget, FiscalPeriod, GLAccount
                    from apps.core.models import OrgUnit

                    tenant_admin = get_user_model().objects.filter(tenant=tenant).first()

                    # Reference spine masters
                    gl_rev = GLAccount.objects.filter(tenant=tenant, code__startswith="4").first() or GLAccount.objects.filter(tenant=tenant).first()
                    gl_exp = GLAccount.objects.filter(tenant=tenant, code__startswith="5").first() or GLAccount.objects.filter(tenant=tenant).last()
                    first_org = OrgUnit.objects.filter(tenant=tenant).first()
                    first_period = FiscalPeriod.objects.filter(tenant=tenant).first()
                    first_budget = Budget.objects.filter(tenant=tenant).first()
                    first_sem_model = SemanticModel.objects.filter(tenant=tenant).first()
                    first_wh_table = WarehouseTable.objects.filter(tenant=tenant).first()
                    first_hierarchy = DrillHierarchy.objects.filter(tenant=tenant).first()

                    # 1. OLAP Cubes
                    cube_fin, _ = OlapCube.objects.get_or_create(
                        tenant=tenant,
                        slug="exec-financial-cube",
                        defaults={
                            "name": "Executive Financial Performance Cube",
                            "description": "Pre-aggregated multidimensional cuboid space combining P&L accounts, org units, and fiscal periods.",
                            "storage_mode": "summary_rollup",
                            "semantic_model": first_sem_model,
                            "warehouse_table": first_wh_table,
                            "default_hierarchy": first_hierarchy,
                            "dimensions_config": [
                                {"name": "FiscalPeriod", "type": "time", "levels": ["Year", "Quarter", "Month"]},
                                {"name": "OrgUnit", "type": "organization", "levels": ["Company", "Division", "Department"]},
                                {"name": "GLAccount", "type": "financial", "levels": ["Class", "Group", "Account"]},
                            ],
                            "measures_config": [
                                {"name": "NetRevenue", "aggregation": "sum", "format": "$#,##0.00"},
                                {"name": "TotalExpenses", "aggregation": "sum", "format": "$#,##0.00"},
                                {"name": "OperatingMargin", "formula": "[NetRevenue] - [TotalExpenses]", "format": "$#,##0.00"},
                            ],
                            "aggregations_config": [
                                ["FiscalPeriod", "OrgUnit"],
                                ["FiscalPeriod", "GLAccount"],
                                ["OrgUnit", "GLAccount"],
                            ],
                            "time_intelligence_enabled": True,
                            "cache_ttl_minutes": 60,
                            "last_refreshed_at": timezone.now(),
                            "status": "active",
                            "created_by": tenant_admin,
                        },
                    )

                    cube_sales, _ = OlapCube.objects.get_or_create(
                        tenant=tenant,
                        slug="sales-margin-cube",
                        defaults={
                            "name": "Multidimensional Sales & Margin Cube",
                            "description": "Dynamic ROLAP cube for sales channel, territory, and product category slice-and-dice.",
                            "storage_mode": "rolap",
                            "semantic_model": first_sem_model,
                            "warehouse_table": first_wh_table,
                            "default_hierarchy": first_hierarchy,
                            "dimensions_config": [
                                {"name": "Territory", "type": "geography", "levels": ["Region", "Country", "Territory"]},
                                {"name": "Channel", "type": "distribution", "levels": ["Segment", "Channel"]},
                                {"name": "ProductCategory", "type": "catalog", "levels": ["Family", "Category"]},
                            ],
                            "measures_config": [
                                {"name": "SalesVolume", "aggregation": "sum", "format": "#,##0 units"},
                                {"name": "GrossRevenue", "aggregation": "sum", "format": "$#,##0.00"},
                                {"name": "GrossMarginPct", "formula": "([GrossRevenue] - [COGS]) / [GrossRevenue] * 100", "format": "0.0%"},
                            ],
                            "aggregations_config": [
                                ["Territory", "Channel"],
                            ],
                            "time_intelligence_enabled": True,
                            "cache_ttl_minutes": 120,
                            "last_refreshed_at": timezone.now(),
                            "status": "active",
                            "created_by": tenant_admin,
                        },
                    )

                    # 2. Pivot Analysis Views
                    pivot_pnl, _ = PivotAnalysisView.objects.get_or_create(
                        tenant=tenant,
                        slug="regional-pnl-cross-tab",
                        defaults={
                            "cube": cube_fin,
                            "name": "Regional P&L Cross-Tab Analysis",
                            "description": "Hierarchical row nesting of Org Units and General Ledger accounts across fiscal quarters.",
                            "row_dimensions": ["OrgUnit", "GLAccount"],
                            "column_dimensions": ["FiscalPeriod"],
                            "selected_measures": ["NetRevenue", "TotalExpenses", "OperatingMargin"],
                            "filters_json": [
                                {"field": "FiscalPeriod.Year", "operator": "eq", "value": "2026"}
                            ],
                            "show_row_subtotals": True,
                            "show_col_subtotals": True,
                            "show_grand_totals": True,
                            "total_position": "bottom_right",
                            "drill_through_enabled": True,
                            "drill_through_target": "accounting:journal_entry_list",
                            "status": "active",
                            "is_favorite": True,
                            "created_by": tenant_admin,
                        },
                    )

                    PivotAnalysisView.objects.get_or_create(
                        tenant=tenant,
                        slug="quarterly-territory-matrix",
                        defaults={
                            "cube": cube_sales,
                            "name": "Quarterly Territory Revenue Matrix",
                            "description": "Cross-tab view of regional distribution channels and margin attainment.",
                            "row_dimensions": ["Territory", "Channel"],
                            "column_dimensions": ["FiscalPeriod"],
                            "selected_measures": ["GrossRevenue", "GrossMarginPct"],
                            "filters_json": [],
                            "show_row_subtotals": True,
                            "show_col_subtotals": False,
                            "show_grand_totals": True,
                            "total_position": "bottom_right",
                            "drill_through_enabled": True,
                            "drill_through_target": "accounting:journal_entry_list",
                            "status": "active",
                            "is_favorite": False,
                            "created_by": tenant_admin,
                        },
                    )

                    # 3. What-If Scenarios
                    scenario_growth, _ = WhatIfScenario.objects.get_or_create(
                        tenant=tenant,
                        slug="fy2026-expansion-sim",
                        defaults={
                            "name": "FY2026 Expansion & Growth Simulation",
                            "description": "Scenario simulation factoring +12% revenue acceleration and 4.5% cost inflation.",
                            "cube": cube_fin,
                            "baseline_budget": first_budget,
                            "fiscal_period": first_period,
                            "driver_parameters": {
                                "revenue_growth_pct": 12.0,
                                "cost_inflation_pct": 4.5,
                                "headcount_expansion_rate": 1.08,
                            },
                            "default_disaggregation": "pro_rata",
                            "status": "simulated",
                            "total_baseline_amount": Decimal("1500000.00"),
                            "total_adjusted_amount": Decimal("1680000.00"),
                            "total_variance_amount": Decimal("180000.00"),
                            "created_by": tenant_admin,
                        },
                    )

                    WhatIfScenario.objects.get_or_create(
                        tenant=tenant,
                        slug="conservative-contingency-plan",
                        defaults={
                            "name": "Conservative Headwinds Contingency Plan",
                            "description": "Defensive contingency planning factoring supply tightening and non-essential spend freeze.",
                            "cube": cube_fin,
                            "baseline_budget": first_budget,
                            "fiscal_period": first_period,
                            "driver_parameters": {
                                "revenue_growth_pct": -2.5,
                                "discretionary_spend_cut_pct": 25.0,
                            },
                            "default_disaggregation": "delta",
                            "status": "draft",
                            "total_baseline_amount": Decimal("1500000.00"),
                            "total_adjusted_amount": Decimal("1470000.00"),
                            "total_variance_amount": Decimal("-30000.00"),
                            "created_by": tenant_admin,
                        },
                    )

                    # 4. Scenario Writeback Cells
                    ScenarioWritebackCell.objects.get_or_create(
                        tenant=tenant,
                        scenario=scenario_growth,
                        cell_coordinates={"period": "2026-Q1", "region": "North America"},
                        defaults={
                            "gl_account": gl_rev,
                            "org_unit": first_org,
                            "baseline_value": Decimal("450000.00"),
                            "adjusted_value": Decimal("504000.00"),
                            "variance_amount": Decimal("54000.00"),
                            "spread_method": "pro_rata",
                            "is_committed": False,
                            "commentary": "Top-down expansion driver applied to regional revenue target.",
                            "created_by": tenant_admin,
                        },
                    )

                    ScenarioWritebackCell.objects.get_or_create(
                        tenant=tenant,
                        scenario=scenario_growth,
                        cell_coordinates={"period": "2026-Q1", "cost_center": "R&D"},
                        defaults={
                            "gl_account": gl_exp,
                            "org_unit": first_org,
                            "baseline_value": Decimal("200000.00"),
                            "adjusted_value": Decimal("209000.00"),
                            "variance_amount": Decimal("9000.00"),
                            "spread_method": "delta",
                            "is_committed": False,
                            "commentary": "Calculated software infrastructure and engineering adjustments.",
                            "created_by": tenant_admin,
                        },
                    )

                self.stdout.write(self.style.SUCCESS(f"  Successfully seeded OLAP & Multidimensional Analysis for tenant: {tenant.name}"))
            else:
                self.stdout.write(f"  OLAP & Multidimensional Analysis already seeded for tenant: {tenant.name}")

        self.stdout.write(self.style.SUCCESS("Business Intelligence seeding finished."))
