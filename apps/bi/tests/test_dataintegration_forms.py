import pytest

from apps.bi.forms import (
    CdcSyncConfigForm,
    DataSourceConnectorForm,
    IngestionPipelineForm,
    IngestionRunForm,
)
from apps.bi.models import (
    CdcSyncConfig,
    DataSourceConnector,
    IngestionPipeline,
    IngestionRun,
)


@pytest.mark.django_db
def test_dataintegration_connector_form_valid(tenant_a):
    data = {
        "name": "Warehouse Postgres Replica",
        "connector_type": "database_rdbms",
        "status": "active",
        "connection_config_raw": '{"host": "pg.internal", "port": 5432, "ssl": true}',
        "description": "Analytics read replica",
    }
    form = DataSourceConnectorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.connection_config == {"host": "pg.internal", "port": 5432, "ssl": True}


@pytest.mark.django_db
def test_dataintegration_connector_form_invalid_json(tenant_a):
    data = {
        "name": "Bad JSON Connector",
        "connector_type": "database_rdbms",
        "status": "active",
        "connection_config_raw": "{invalid_json: true}",
    }
    form = DataSourceConnectorForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "connection_config_raw" in form.errors


@pytest.mark.django_db
def test_dataintegration_connector_form_reject_foreign_credential(tenant_a, tenant_b):
    from apps.core.models.Integration import ApiCredential
    foreign_cred = ApiCredential.objects.create(
        tenant=tenant_b,
        label="Foreign Cred",
        prefix="nvr_for",
        key_hash="hash123",
    )
    data = {
        "name": "Connector with Foreign Cred",
        "connector_type": "rest_api",
        "status": "active",
        "credential": foreign_cred.pk,
    }
    form = DataSourceConnectorForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "credential" in form.errors


@pytest.mark.django_db
def test_dataintegration_pipeline_form_excludes_webhook_secret(tenant_a, bi_connector):
    form = IngestionPipelineForm(tenant=tenant_a)
    assert "webhook_secret" not in form.fields
    assert "webhook_token" not in form.fields
    assert "tenant" not in form.fields
    assert "number" not in form.fields


@pytest.mark.django_db
def test_dataintegration_pipeline_form_reject_foreign_connector(tenant_a, bi_connector_b):
    data = {
        "name": "Cross Tenant Pipeline",
        "connector": bi_connector_b.pk,
        "ingestion_mode": "batch_scheduled",
        "source_entity": "sales_order",
        "target_staging_table": "stg_orders",
        "schedule_cadence": "daily",
        "status": "active",
    }
    form = IngestionPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "connector" in form.errors


@pytest.mark.django_db
def test_dataintegration_cdc_form_excludes_already_configured_pipeline(tenant_a, bi_pipeline, bi_cdc_config):
    # bi_pipeline already has bi_cdc_config attached
    form = CdcSyncConfigForm(tenant=tenant_a)
    assert bi_pipeline not in form.fields["pipeline"].queryset
