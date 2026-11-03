"""Shared test contract fixtures for apps/bi."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bi.models import (
    CdcSyncConfig,
    DataSourceConnector,
    IngestionPipeline,
    IngestionRun,
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
