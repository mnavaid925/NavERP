import pytest
from django.db import IntegrityError

from apps.bi.models import (
    CdcSyncConfig,
    DataSourceConnector,
    IngestionPipeline,
    IngestionRun,
)


@pytest.mark.django_db
def test_dataintegration_connector_creation_and_prefix(tenant_a, admin_user):
    connector = DataSourceConnector.objects.create(
        tenant=tenant_a,
        name="Production MySQL Replica",
        connector_type="internal_erp",
        created_by=admin_user,
    )
    assert connector.number.startswith("BDSC-")
    assert str(connector) == f"{connector.number} — Production MySQL Replica (NavERP Internal Module)"
    assert connector.test_status == "untested"
    assert connector.status == "active"


@pytest.mark.django_db
def test_dataintegration_pipeline_creation_and_token(tenant_a, bi_connector):
    pipeline = IngestionPipeline.objects.create(
        tenant=tenant_a,
        connector=bi_connector,
        name="Webhook Event Ingress",
        ingestion_mode="real_time_webhook",
        source_entity="/api/v1/stream",
        target_staging_table="stg_events",
    )
    assert pipeline.number.startswith("BING-")
    assert pipeline.webhook_token is not None
    assert len(pipeline.webhook_token) == 48  # 24 bytes hex
    assert pipeline.webhook_secret is not None
    assert str(pipeline) == f"{pipeline.number} — Webhook Event Ingress -> stg_events"


@pytest.mark.django_db
def test_dataintegration_cdc_config_creation(tenant_a, bi_pipeline):
    cdc = CdcSyncConfig.objects.create(
        tenant=tenant_a,
        pipeline=bi_pipeline,
        capture_method="query_timestamp",
        sync_mode="incremental_deduped",
        cursor_field="updated_at",
        primary_key_fields="id",
    )
    assert cdc.number.startswith("BCDC-")
    assert "Incremental Deduped" in str(cdc)
    assert cdc.schema_drift_policy == "detect_and_warn"


@pytest.mark.django_db
def test_dataintegration_ingestion_run_creation(tenant_a, bi_pipeline):
    run = IngestionRun.objects.create(
        tenant=tenant_a,
        pipeline=bi_pipeline,
        trigger_type="scheduled",
        status="completed",
        records_extracted=150,
        records_inserted=150,
    )
    assert run.number.startswith("BIJR-")
    assert "Completed Successfully" in str(run)
    assert run.records_rejected == 0


@pytest.mark.django_db
def test_dataintegration_unique_tenant_numbers(tenant_a):
    c1 = DataSourceConnector.objects.create(tenant=tenant_a, name="C1")
    c2 = DataSourceConnector.objects.create(tenant=tenant_a, name="C2")
    assert c1.number != c2.number
