"""Shared test contract fixtures for apps/bi."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
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


@pytest.fixture
def admin_user_b(db, tenant_b):
    return User.objects.create_user(
        email="admin@globex.com",
        username="admin_globex",
        password="TestPass123!",
        tenant=tenant_b,
        is_tenant_admin=True,
    )


@pytest.fixture
def auth_client(client_a):
    return client_a


@pytest.fixture
def anon_client(client):
    return client


@pytest.fixture
def bi_connector(db, tenant_a, admin_user):
    return DataSourceConnector.objects.create(
        tenant=tenant_a,
        name="Acme Master ERP",
        connector_type="internal_erp",
        status="active",
        connection_config={"engine": "mysql", "host": "localhost"},
        test_status="success",
        test_message="Connection verified",
        created_by=admin_user,
    )


@pytest.fixture
def bi_pipeline(db, tenant_a, bi_connector):
    return IngestionPipeline.objects.create(
        tenant=tenant_a,
        connector=bi_connector,
        name="Acme Invoices Pipeline",
        ingestion_mode="batch_scheduled",
        source_entity="accounting_invoice",
        target_staging_table="stg_accounting_invoices",
        schedule_cadence="daily",
        cron_expression="0 2 * * *",
        file_format="none",
        status="active",
    )


@pytest.fixture
def bi_cdc_config(db, tenant_a, bi_pipeline):
    return CdcSyncConfig.objects.create(
        tenant=tenant_a,
        pipeline=bi_pipeline,
        capture_method="query_timestamp",
        sync_mode="incremental_deduped",
        primary_key_fields="id",
        cursor_field="updated_at",
        last_cursor_value="2026-11-03T12:00:00Z",
        schema_drift_policy="detect_and_warn",
        capture_deletes=True,
    )


@pytest.fixture
def bi_run(db, tenant_a, bi_pipeline):
    return IngestionRun.objects.create(
        tenant=tenant_a,
        pipeline=bi_pipeline,
        trigger_type="scheduled",
        status="completed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        duration_seconds=Decimal("1.45"),
        records_extracted=100,
        records_inserted=98,
        records_rejected=2,
        bytes_transferred=25600,
        committed_cursor="2026-11-03T12:00:00Z",
        log_summary="Test run finished successfully.",
    )


@pytest.fixture
def bi_connector_b(db, tenant_b, admin_user_b):
    return DataSourceConnector.objects.create(
        tenant=tenant_b,
        name="Globex Master ERP",
        connector_type="internal_erp",
        status="active",
        test_status="success",
        created_by=admin_user_b,
    )


@pytest.fixture
def bi_pipeline_b(db, tenant_b, bi_connector_b):
    return IngestionPipeline.objects.create(
        tenant=tenant_b,
        connector=bi_connector_b,
        name="Globex Invoices Pipeline",
        ingestion_mode="batch_scheduled",
        source_entity="accounting_invoice",
        target_staging_table="stg_accounting_invoices",
        status="active",
    )


@pytest.fixture
def bi_cdc_config_b(db, tenant_b, bi_pipeline_b):
    return CdcSyncConfig.objects.create(
        tenant=tenant_b,
        pipeline=bi_pipeline_b,
        capture_method="query_timestamp",
        sync_mode="incremental_deduped",
        primary_key_fields="id",
        cursor_field="updated_at",
    )


@pytest.fixture
def bi_run_b(db, tenant_b, bi_pipeline_b):
    return IngestionRun.objects.create(
        tenant=tenant_b,
        pipeline=bi_pipeline_b,
        trigger_type="manual",
        status="completed",
        records_extracted=50,
        records_inserted=50,
    )


# ---------------------------------------------------------------------------
# Sub-module 10.2 (ETL/ELT & Data Pipelines) Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def etl_pipeline_a(db, tenant_a, admin_user, bi_pipeline):
    return EtlPipeline.objects.create(
        tenant=tenant_a,
        name="Acme Invoices Daily Mart",
        description="Transforms raw staging invoices into fact_daily_sales mart",
        source_ingestion_pipeline=bi_pipeline,
        source_staging_table="stg_accounting_invoices",
        target_table="fact_daily_sales",
        target_layer="warehouse_fact",
        trigger_type="scheduled_cron",
        cron_expression="0 2 * * *",
        status="active",
        created_by=admin_user,
    )


@pytest.fixture
def etl_step_a(db, tenant_a, etl_pipeline_a):
    return TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        name="Join Customer Master",
        step_type="join",
        sequence=1,
        upstream_step_ids=[],
        step_config={"join_type": "inner", "left_key": "customer_id", "right_key": "id"},
        status="active",
        is_blocking=True,
    )


@pytest.fixture
def etl_version_a(db, tenant_a, admin_user, etl_pipeline_a):
    ver = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version_number="v1.0.0",
        environment="production",
        status="published",
        changelog="Initial production deployment",
        promoted_by=admin_user,
        promoted_at=timezone.now(),
    )
    etl_pipeline_a.active_version = ver
    etl_pipeline_a.save(update_fields=["active_version"])
    return ver


@pytest.fixture
def etl_run_a(db, tenant_a, etl_pipeline_a, etl_version_a):
    return EtlPipelineRun.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version=etl_version_a,
        trigger_type="scheduled",
        status="completed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        duration_seconds=Decimal("12.50"),
        records_in=1000,
        records_transformed=980,
        records_out=980,
        records_rejected=20,
        bytes_processed=1048576,
    )


@pytest.fixture
def etl_pipeline_b(db, tenant_b, admin_user_b, bi_pipeline_b):
    return EtlPipeline.objects.create(
        tenant=tenant_b,
        name="Globex Invoices Daily Mart",
        description="Globex transformation mart",
        source_ingestion_pipeline=bi_pipeline_b,
        source_staging_table="stg_accounting_invoices",
        target_table="fact_daily_sales",
        target_layer="warehouse_fact",
        trigger_type="scheduled_cron",
        cron_expression="0 3 * * *",
        status="active",
        created_by=admin_user_b,
    )


@pytest.fixture
def etl_step_b(db, tenant_b, etl_pipeline_b):
    return TransformationStep.objects.create(
        tenant=tenant_b,
        pipeline=etl_pipeline_b,
        name="Globex Customer Join",
        step_type="join",
        sequence=1,
        upstream_step_ids=[],
        step_config={"join_type": "left", "left_key": "cust_id", "right_key": "id"},
        status="active",
        is_blocking=True,
    )


@pytest.fixture
def etl_version_b(db, tenant_b, admin_user_b, etl_pipeline_b):
    ver = EtlPipelineVersion.objects.create(
        tenant=tenant_b,
        pipeline=etl_pipeline_b,
        version_number="v1.0.0",
        environment="production",
        status="published",
        changelog="Globex initial release",
        promoted_by=admin_user_b,
        promoted_at=timezone.now(),
    )
    etl_pipeline_b.active_version = ver
    etl_pipeline_b.save(update_fields=["active_version"])
    return ver


@pytest.fixture
def etl_run_b(db, tenant_b, etl_pipeline_b, etl_version_b):
    return EtlPipelineRun.objects.create(
        tenant=tenant_b,
        pipeline=etl_pipeline_b,
        version=etl_version_b,
        trigger_type="manual",
        status="completed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        duration_seconds=Decimal("5.20"),
        records_in=500,
        records_transformed=500,
        records_out=500,
        records_rejected=0,
        bytes_processed=524288,
    )


# ---------------------------------------------------------------------------
# Sub-module 10.3 (Data Warehouse & Storage) Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lakehouse_zone_a(db, tenant_a):
    return LakehouseZone.objects.create(
        tenant=tenant_a,
        name="Gold Marts Zone",
        code="gold-marts-zone",
        zone_type="gold",
        storage_backend="internal_db",
        base_uri_path="/warehouse/gold",
        default_format="relational_table",
        is_active=True,
    )


@pytest.fixture
def storage_policy_a(db, tenant_a):
    return WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="Daily Range Snappy Policy",
        partition_strategy="range_time",
        partition_granularity="day",
        compression_codec="snappy",
        vacuum_cadence="weekly",
        time_travel_days=30,
        enable_zone_maps=True,
        is_active=True,
    )


@pytest.fixture
def data_mart_a(db, tenant_a, admin_user):
    return DataMart.objects.create(
        tenant=tenant_a,
        name="Revenue Finance Mart",
        code="revenue-finance-mart",
        subject_area="finance",
        certification_status="certified",
        access_tier="department",
        refresh_cadence="daily",
        owner=admin_user,
        steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def warehouse_table_a(db, tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a):
    return WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=storage_policy_a,
        data_mart=data_mart_a,
        name="Daily Invoiced Revenue Fact",
        table_name="fact_daily_revenue",
        table_type="fact",
        schema_type="star",
        grain="transaction",
        primary_key_column="id",
        schema_definition=[
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "invoice_date", "type": "DATE", "nullable": False},
            {"name": "customer_id", "type": "INTEGER", "nullable": False},
            {"name": "amount", "type": "NUMERIC(14, 2)", "nullable": False},
        ],
        row_count=100000,
        compressed_bytes=10485760,
        compression_ratio=Decimal("2.80"),
        is_conformed_dimension=True,
        is_active=True,
    )


@pytest.fixture
def lakehouse_zone_b(db, tenant_b):
    return LakehouseZone.objects.create(
        tenant=tenant_b,
        name="Globex Bronze Ingestion Zone",
        code="globex-bronze-landing",
        zone_type="bronze",
        storage_backend="internal_db",
        base_uri_path="/warehouse/globex/bronze",
        default_format="relational_table",
        is_active=True,
    )


@pytest.fixture
def storage_policy_b(db, tenant_b):
    return WarehouseStoragePolicy.objects.create(
        tenant=tenant_b,
        name="Globex Monthly Policy",
        partition_strategy="range_time",
        partition_granularity="month",
        compression_codec="zstd",
        vacuum_cadence="monthly",
        time_travel_days=14,
        is_active=True,
    )


@pytest.fixture
def data_mart_b(db, tenant_b, admin_user_b):
    return DataMart.objects.create(
        tenant=tenant_b,
        name="Globex Sales Mart",
        code="globex-sales-mart",
        subject_area="sales",
        certification_status="certified",
        access_tier="department",
        owner=admin_user_b,
        steward=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def warehouse_table_b(db, tenant_b, lakehouse_zone_b, storage_policy_b, data_mart_b):
    return WarehouseTable.objects.create(
        tenant=tenant_b,
        lakehouse_zone=lakehouse_zone_b,
        storage_policy=storage_policy_b,
        data_mart=data_mart_b,
        name="Globex Orders Fact",
        table_name="fact_globex_orders",
        table_type="fact",
        schema_type="star",
        grain="transaction",
        primary_key_column="id",
        schema_definition=[
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "order_date", "type": "DATE", "nullable": False},
        ],
        row_count=50000,
        compressed_bytes=5242880,
        compression_ratio=Decimal("2.50"),
        is_active=True,
    )


