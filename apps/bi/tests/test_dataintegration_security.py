import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dataintegration_cross_tenant_idor_returns_404(
    auth_client,
    bi_connector_b,
    bi_pipeline_b,
    bi_cdc_config_b,
    bi_run_b,
):
    # auth_client is logged in as admin_acme (tenant_a)
    idor_routes = [
        ("bi:data_source_connector_detail", {"pk": bi_connector_b.pk}),
        ("bi:data_source_connector_edit", {"pk": bi_connector_b.pk}),
        ("bi:data_source_connector_delete", {"pk": bi_connector_b.pk}),
        ("bi:data_source_connector_test", {"pk": bi_connector_b.pk}),
        ("bi:ingestion_pipeline_detail", {"pk": bi_pipeline_b.pk}),
        ("bi:ingestion_pipeline_edit", {"pk": bi_pipeline_b.pk}),
        ("bi:ingestion_pipeline_delete", {"pk": bi_pipeline_b.pk}),
        ("bi:ingestion_pipeline_trigger", {"pk": bi_pipeline_b.pk}),
        ("bi:cdc_sync_config_detail", {"pk": bi_cdc_config_b.pk}),
        ("bi:cdc_sync_config_edit", {"pk": bi_cdc_config_b.pk}),
        ("bi:cdc_sync_config_delete", {"pk": bi_cdc_config_b.pk}),
        ("bi:cdc_sync_config_reset_cursor", {"pk": bi_cdc_config_b.pk}),
        ("bi:ingestion_run_detail", {"pk": bi_run_b.pk}),
        ("bi:ingestion_run_delete", {"pk": bi_run_b.pk}),
        ("bi:ingestion_run_retry", {"pk": bi_run_b.pk}),
    ]

    for name, kwargs in idor_routes:
        url = reverse(name, kwargs=kwargs)
        # Try both GET and POST
        resp_get = auth_client.get(url)
        assert resp_get.status_code in (404, 405), f"GET IDOR leaked on {name}: {resp_get.status_code}"
        resp_post = auth_client.post(url)
        assert resp_post.status_code == 404, f"POST IDOR leaked on {name}: {resp_post.status_code}"


@pytest.mark.django_db
def test_dataintegration_anonymous_user_redirects_login(anon_client, bi_connector):
    routes = [
        ("bi:data_integration_hub", {}),
        ("bi:data_source_connector_list", {}),
        ("bi:data_source_connector_detail", {"pk": bi_connector.pk}),
    ]
    for name, kwargs in routes:
        resp = anon_client.get(reverse(name, kwargs=kwargs))
        assert resp.status_code == 302
        assert "/accounts/login" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_dataintegration_delete_rejects_get_requests(auth_client, bi_connector):
    url = reverse("bi:data_source_connector_delete", kwargs={"pk": bi_connector.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 405
