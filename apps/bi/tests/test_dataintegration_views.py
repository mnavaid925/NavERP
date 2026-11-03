import pytest
from django.urls import reverse

from apps.bi.models import (
    CdcSyncConfig,
    DataSourceConnector,
    IngestionPipeline,
    IngestionRun,
)


@pytest.mark.django_db
def test_dataintegration_views_render_200(auth_client, bi_connector, bi_pipeline, bi_cdc_config, bi_run):
    routes = [
        ("bi:data_integration_hub", {}),
        ("bi:data_source_connector_list", {}),
        ("bi:data_source_connector_create", {}),
        ("bi:data_source_connector_detail", {"pk": bi_connector.pk}),
        ("bi:data_source_connector_edit", {"pk": bi_connector.pk}),
        ("bi:ingestion_pipeline_list", {}),
        ("bi:ingestion_pipeline_create", {}),
        ("bi:ingestion_pipeline_detail", {"pk": bi_pipeline.pk}),
        ("bi:ingestion_pipeline_edit", {"pk": bi_pipeline.pk}),
        ("bi:cdc_sync_config_list", {}),
        ("bi:cdc_sync_config_create", {}),
        ("bi:cdc_sync_config_detail", {"pk": bi_cdc_config.pk}),
        ("bi:cdc_sync_config_edit", {"pk": bi_cdc_config.pk}),
        ("bi:ingestion_run_list", {}),
        ("bi:ingestion_run_detail", {"pk": bi_run.pk}),
    ]
    for name, kwargs in routes:
        resp = auth_client.get(reverse(name, kwargs=kwargs))
        assert resp.status_code == 200, f"Route {name} returned status {resp.status_code}"


@pytest.mark.django_db
def test_dataintegration_views_junk_params_resilience(auth_client):
    # Pipeline list with invalid non-int connector_id
    resp = auth_client.get(reverse("bi:ingestion_pipeline_list") + "?connector_id=notanint")
    assert resp.status_code == 200

    # Ingestion run list with invalid non-int pipeline_id
    resp = auth_client.get(reverse("bi:ingestion_run_list") + "?pipeline_id=junk")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_dataintegration_connector_delete_protected_error(auth_client, bi_connector, bi_pipeline):
    # bi_pipeline references bi_connector, so connector cannot be deleted
    resp = auth_client.post(reverse("bi:data_source_connector_delete", kwargs={"pk": bi_connector.pk}))
    assert resp.status_code == 302
    assert DataSourceConnector.objects.filter(pk=bi_connector.pk).exists()


@pytest.mark.django_db
def test_dataintegration_connector_test_action(auth_client, bi_connector):
    resp = auth_client.post(reverse("bi:data_source_connector_test", kwargs={"pk": bi_connector.pk}))
    assert resp.status_code == 302
    bi_connector.refresh_from_db()
    assert bi_connector.test_status == "success"
    assert "verified" in bi_connector.test_message.lower()


@pytest.mark.django_db
def test_dataintegration_pipeline_trigger_action(auth_client, bi_pipeline):
    initial_runs = bi_pipeline.runs.count()
    resp = auth_client.post(reverse("bi:ingestion_pipeline_trigger", kwargs={"pk": bi_pipeline.pk}))
    assert resp.status_code == 302
    assert bi_pipeline.runs.count() == initial_runs + 1
    bi_pipeline.refresh_from_db()
    assert bi_pipeline.last_run_at is not None


@pytest.mark.django_db
def test_dataintegration_run_retry_action(auth_client, bi_run):
    pipeline = bi_run.pipeline
    initial_runs = pipeline.runs.count()
    resp = auth_client.post(reverse("bi:ingestion_run_retry", kwargs={"pk": bi_run.pk}))
    assert resp.status_code == 302
    assert pipeline.runs.count() == initial_runs + 1
