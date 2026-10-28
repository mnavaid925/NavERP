"""Integration and unit tests for Sales 8.18 Integration & API Hub views.

Subslug: integrationapihub
Prefix for test functions: test_integrationapihub_*
Prefix for helper functions: _integrationapihub_*

Covers:
1. Hub Dashboard (`sales:integration_hub`):
   - Authenticated GET 200 rendering KPI cards, configured connectors, sync jobs, and recent runs.
   - Unauthenticated GET redirects to login.
2. Category Lens Routes:
   - `sales:sic_erp_list`, `sales:sic_marketing_list`, `sales:sic_communication_list`,
     `sales:sic_bi_list`, `sales:sic_esignature_list` all redirect (302) to `sales:sic_list`
     with their respective `?category=` filter.
3. `SalesIntegrationConnector` Views:
   - `sic_list`: GET 200, search `q`, filter `category`, `provider`, `health_status`,
     junk query params return 200 without crashing (L11).
   - `sic_create`: GET 200, POST 302 creates connector with encrypted credential, redirects to `sales:sic_detail`.
   - `sic_detail`: GET 200, displays masked credential `••••••••` and never leaks plaintext secret.
   - `sic_edit`: GET 200, POST 302 updates name/notes while preserving encrypted credential.
   - `sic_delete`: POST 302 deletes connector; rejects GET with 405.
   - `sic_test`: POST 302 executes simulated health check, creates `SalesSyncRun` with `status="simulated"`
     and `run_type="test_ping"`, updates `health_status="connected"` and `"updated_at"`.
     Also tests inactive connector sets `health_status="offline"`.
4. `SalesFieldMapping` Views:
   - `sfm_list`: GET 200, filters `connector`, `target_entity`, `direction`.
   - `sfm_list` huge integer parameter test: `?connector=999999999999999999999999999999` returns 200 gracefully (I2).
   - `sfm_create`: GET 200, POST 302 creates mapping.
   - `sfm_detail`: GET 200.
   - `sfm_edit`: GET 200, POST 302 updates mapping.
   - `sfm_delete`: POST 302 deletes mapping and honors `next` parameter or list redirect (M1); rejects GET with 405.
5. `SalesSyncJob` Views:
   - `ssj_list`: GET 200, filters `connector`, `entity_scope`, `status`.
   - `ssj_list` huge integer parameter test: `?connector=999999999999999999999999999999` returns 200 gracefully (I2).
   - `ssj_create`: GET 200, POST 302 creates sync job.
   - `ssj_detail`: GET 200.
   - `ssj_edit`: GET 200, POST 302 updates job.
   - `ssj_delete`: POST 302 deletes job; rejects GET with 405.
   - `ssj_trigger`: POST 302 executes simulated run, creates `SalesSyncRun` with `status="simulated"`,
     increments `total_runs_count`, updates `last_run_at` and `updated_at`; rejects GET with 405.
6. `SalesSyncRun` Views:
   - `ssr_list`: GET 200, filters `connector`, `job`, `run_type`, `status`.
   - `ssr_list` huge integer parameter tests: `?connector=...` and `?job=...` return 200 gracefully (I2).
   - `ssr_detail`: GET 200.
   - `ssr_delete`: POST 302 deletes run log; rejects GET with 405.
7. Pagination:
   - Tests pagination handling with invalid page params (`?page=invalid`, `?page=999999`, `?page=-1`).
8. Cross-Tenant Isolation:
   - IDOR prevention returning 404 for tenant B objects accessed by tenant A user.
9. Tenant Admin Privileges:
   - Verifies mutations require tenant admin rights (`@tenant_admin_required` raises 403 for non-admins).
"""
import pytest
from django.urls import reverse

from apps.core.crypto import is_encrypted
from apps.core.models import AuditLog
from apps.sales.models import (
    SalesFieldMapping,
    SalesIntegrationConnector,
    SalesSyncJob,
    SalesSyncRun,
)
from apps.sales.tests.conftest import (
    _integrationapihub_connector,
    _integrationapihub_field_mapping,
    _integrationapihub_sync_job,
    _integrationapihub_sync_run,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_integrationapihub_*)
# ==============================================================================

def _integrationapihub_create_test_connector(tenant, name="Integration Test Connector", **kwargs):
    """Create a helper connector instance with defaults."""
    return _integrationapihub_connector(tenant, name=name, **kwargs)


def _integrationapihub_create_test_field_mapping(tenant, connector=None, **kwargs):
    """Create a helper field mapping instance with defaults."""
    return _integrationapihub_field_mapping(tenant, connector=connector, **kwargs)


def _integrationapihub_create_test_sync_job(tenant, connector=None, **kwargs):
    """Create a helper sync job instance with defaults."""
    return _integrationapihub_sync_job(tenant, connector=connector, **kwargs)


def _integrationapihub_create_test_sync_run(tenant, connector=None, job=None, **kwargs):
    """Create a helper sync run log instance with defaults."""
    return _integrationapihub_sync_run(tenant, connector=connector, job=job, **kwargs)


# ==============================================================================
# 1. Hub Dashboard (`sales:integration_hub`)
# ==============================================================================

def test_integrationapihub_hub_dashboard_authenticated(
    client_a, tenant_a, iah_connector_a, iah_sync_job_a, iah_sync_run_a
):
    """Hub dashboard returns 200 and passes all KPI statistics, connectors, jobs, and runs."""
    url = reverse("sales:integration_hub")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/integrationapihub/hub_dashboard.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert ctx["connectors_count"] >= 1
    assert ctx["healthy_count"] >= 1
    assert ctx["jobs_count"] >= 1
    assert ctx["active_jobs_count"] >= 1
    assert ctx["runs_count"] >= 1

    assert iah_connector_a in ctx["erp_connectors"]
    assert iah_sync_run_a in ctx["recent_runs"]
    assert "category_counts" in ctx
    assert ctx["category_counts"].get("erp", 0) >= 1

    content = resp.content.decode("utf-8")
    assert iah_connector_a.name in content
    assert iah_sync_job_a.name in content
    assert iah_sync_run_a.number in content


def test_integrationapihub_hub_dashboard_unauthenticated(client):
    """Unauthenticated access to hub dashboard redirects to login."""
    url = reverse("sales:integration_hub")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login/" in resp.url


# ==============================================================================
# 2. Category Lens Routes
# ==============================================================================

def test_integrationapihub_category_lens_redirects(client_a):
    """Category lens routes redirect (302) to sic_list with appropriate ?category= query param."""
    base_sic_list = reverse("sales:sic_list")
    lenses = [
        ("sales:sic_erp_list", f"{base_sic_list}?category=erp"),
        ("sales:sic_marketing_list", f"{base_sic_list}?category=marketing"),
        ("sales:sic_communication_list", f"{base_sic_list}?category=communication"),
        ("sales:sic_bi_list", f"{base_sic_list}?category=bi_warehouse"),
        ("sales:sic_esignature_list", f"{base_sic_list}?category=esignature"),
    ]

    for route_name, expected_target in lenses:
        url = reverse(route_name)
        resp = client_a.get(url)
        assert resp.status_code == 302, f"Expected 302 for {route_name}"
        assert resp.url == expected_target, f"Expected redirect to {expected_target} for {route_name}"


def test_integrationapihub_category_lens_unauthenticated(client):
    """Unauthenticated access to category lenses redirects to login."""
    lenses = [
        "sales:sic_erp_list",
        "sales:sic_marketing_list",
        "sales:sic_communication_list",
        "sales:sic_bi_list",
        "sales:sic_esignature_list",
    ]
    for route_name in lenses:
        resp = client.get(reverse(route_name))
        assert resp.status_code == 302
        assert "/login/" in resp.url


# ==============================================================================
# 3. SalesIntegrationConnector Views
# ==============================================================================

def test_integrationapihub_connector_list_view_and_search(client_a, tenant_a):
    """sic_list returns 200, handles search filtering by name, number, notes."""
    conn1 = _integrationapihub_create_test_connector(
        tenant_a,
        name="Oracle NetSuite Enterprise Bridge",
        notes="Financial data sync",
    )
    conn2 = _integrationapihub_create_test_connector(
        tenant_a,
        name="HubSpot Inbound Marketing Hub",
        notes="Lead capture pipeline",
        category="marketing",
        provider="hubspot",
    )

    url = reverse("sales:sic_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    connectors = resp.context["connectors"]
    assert conn1 in connectors
    assert conn2 in connectors

    # Search by name substring
    search_resp = client_a.get(url, {"q": "Oracle NetSuite"})
    assert search_resp.status_code == 200
    assert conn1 in search_resp.context["connectors"]
    assert conn2 not in search_resp.context["connectors"]

    # Search by number
    search_num_resp = client_a.get(url, {"q": conn2.number})
    assert search_num_resp.status_code == 200
    assert conn2 in search_num_resp.context["connectors"]
    assert conn1 not in search_num_resp.context["connectors"]


def test_integrationapihub_connector_list_filters(client_a, tenant_a):
    """sic_list correctly filters by category, provider, and health_status."""
    erp_conn = _integrationapihub_create_test_connector(
        tenant_a,
        name="SAP S/4HANA",
        category="erp",
        provider="sap",
        health_status="connected",
    )
    marketing_conn = _integrationapihub_create_test_connector(
        tenant_a,
        name="ActiveCampaign Sync",
        category="marketing",
        provider="custom",
        health_status="untested",
    )

    url = reverse("sales:sic_list")

    # Filter by category
    resp_cat = client_a.get(url, {"category": "erp"})
    assert erp_conn in resp_cat.context["connectors"]
    assert marketing_conn not in resp_cat.context["connectors"]

    # Filter by provider
    resp_prov = client_a.get(url, {"provider": "custom"})
    assert marketing_conn in resp_prov.context["connectors"]
    assert erp_conn not in resp_prov.context["connectors"]

    # Filter by health status
    resp_health = client_a.get(url, {"health_status": "untested"})
    assert marketing_conn in resp_health.context["connectors"]
    assert erp_conn not in resp_health.context["connectors"]


def test_integrationapihub_connector_list_junk_params_resilience(client_a):
    """sic_list handles junk/invalid filter parameters gracefully without crashing (L11)."""
    url = reverse("sales:sic_list")
    resp = client_a.get(
        url,
        {
            "category": "non_existent_category",
            "provider": "unknown_provider",
            "health_status": "super_healthy_bogus",
            "q": "///$$$^^^",
            "page": "invalid_page_number",
        },
    )
    assert resp.status_code == 200
    assert "connectors" in resp.context


def test_integrationapihub_connector_create_view(client_a, tenant_a):
    """sic_create renders form on GET and creates connector with encrypted credential on POST."""
    create_url = reverse("sales:sic_create")
    get_resp = client_a.get(create_url)
    assert get_resp.status_code == 200
    assert get_resp.context["is_edit"] is False

    post_data = {
        "name": "NetSuite Revenue Hub",
        "category": "erp",
        "provider": "netsuite",
        "environment": "production",
        "base_url": "https://12345.restlets.api.netsuite.com/rest/endpoint",
        "auth_method": "oauth2",
        "remote_scope_ref": "tenant_netsuite_prod",
        "health_status": "untested",
        "is_active": True,
        "notes": "NetSuite ERP Financial connector.",
        "credential_input": "super-secret-netsuite-oauth-token-12345",
    }
    post_resp = client_a.post(create_url, data=post_data)
    assert post_resp.status_code == 302

    created = SalesIntegrationConnector.objects.get(tenant=tenant_a, name="NetSuite Revenue Hub")
    assert post_resp.url == reverse("sales:sic_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert is_encrypted(created.credential_encrypted)
    assert created.get_credential() == "super-secret-netsuite-oauth-token-12345"
    assert created.masked_credential == "••••••••"
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_integrationapihub_connector_detail_view_masked_credential(client_a, tenant_a):
    """sic_detail displays masked credential '••••••••' and never leaks plaintext secret."""
    raw_secret = "highly-sensitive-api-token-998877"
    connector = _integrationapihub_create_test_connector(tenant_a, name="Encrypted Detail Connector")
    connector.set_credential(raw_secret)
    connector.save()

    detail_url = reverse("sales:sic_detail", kwargs={"pk": connector.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["connector"] == connector

    html = resp.content.decode("utf-8")
    assert "••••••••" in html
    assert raw_secret not in html


def test_integrationapihub_connector_edit_view(client_a, tenant_a, iah_connector_a):
    """sic_edit updates connector attributes and preserves credentials when left blank."""
    iah_connector_a.set_credential("preserved-secret-token")
    iah_connector_a.save()

    edit_url = reverse("sales:sic_edit", kwargs={"pk": iah_connector_a.pk})
    get_resp = client_a.get(edit_url)
    assert get_resp.status_code == 200
    assert get_resp.context["is_edit"] is True
    assert get_resp.context["connector"] == iah_connector_a

    post_data = {
        "name": "Updated Acme SAP Connector",
        "category": iah_connector_a.category,
        "provider": iah_connector_a.provider,
        "environment": "sandbox",
        "base_url": iah_connector_a.base_url,
        "auth_method": iah_connector_a.auth_method,
        "remote_scope_ref": iah_connector_a.remote_scope_ref,
        "health_status": iah_connector_a.health_status,
        "is_active": True,
        "notes": "Updated operational configuration for sandbox testing.",
        "credential_input": "",  # Blank preserves existing
    }
    post_resp = client_a.post(edit_url, data=post_data)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:sic_detail", kwargs={"pk": iah_connector_a.pk})

    iah_connector_a.refresh_from_db()
    assert iah_connector_a.name == "Updated Acme SAP Connector"
    assert iah_connector_a.environment == "sandbox"
    assert iah_connector_a.notes == "Updated operational configuration for sandbox testing."
    assert iah_connector_a.get_credential() == "preserved-secret-token"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=iah_connector_a.pk).exists()


def test_integrationapihub_connector_delete_view(client_a, tenant_a):
    """sic_delete rejects GET (405) and deletes connector on POST (302)."""
    connector = _integrationapihub_create_test_connector(tenant_a, name="Connector To Delete")
    del_url = reverse("sales:sic_delete", kwargs={"pk": connector.pk})

    # GET is rejected with 405 Method Not Allowed
    get_resp = client_a.get(del_url)
    assert get_resp.status_code == 405

    # POST deletes
    post_resp = client_a.post(del_url)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:sic_list")
    assert not SalesIntegrationConnector.objects.filter(pk=connector.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=connector.pk).exists()


def test_integrationapihub_connector_test_ping_action_active(client_a, tenant_a):
    """sic_test executes simulated health check, updates health_status='connected', and logs run."""
    connector = _integrationapihub_create_test_connector(
        tenant_a,
        name="Live Health Ping Target",
        health_status="untested",
        is_active=True,
    )
    test_url = reverse("sales:sic_test", kwargs={"pk": connector.pk})

    # GET is rejected (require_POST)
    get_resp = client_a.get(test_url)
    assert get_resp.status_code == 405

    post_resp = client_a.post(test_url)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:sic_detail", kwargs={"pk": connector.pk})

    connector.refresh_from_db()
    assert connector.health_status == "connected"
    assert connector.last_health_check_at is not None
    assert connector.last_error_message == ""

    run = SalesSyncRun.objects.filter(tenant=tenant_a, connector=connector).latest("id")
    assert run.run_type == "test_ping"
    assert run.status == "simulated"
    assert run.records_read == 1
    assert run.records_written == 1
    assert run.summary_payload.get("result") == "simulated_healthy_response"
    assert AuditLog.objects.filter(tenant=tenant_a, action="test", object_id=connector.pk).exists()


def test_integrationapihub_connector_test_ping_action_inactive(client_a, tenant_a):
    """sic_test on inactive connector sets health_status='offline' and logs diagnostic message."""
    connector = _integrationapihub_create_test_connector(
        tenant_a,
        name="Paused Inactive Connector",
        health_status="untested",
        is_active=False,
    )
    test_url = reverse("sales:sic_test", kwargs={"pk": connector.pk})
    post_resp = client_a.post(test_url)
    assert post_resp.status_code == 302

    connector.refresh_from_db()
    assert connector.health_status == "offline"
    assert "Connector is currently inactive/paused." in connector.last_error_message


# ==============================================================================
# 4. SalesFieldMapping Views
# ==============================================================================

def test_integrationapihub_field_mapping_list_view_and_filters(client_a, tenant_a, iah_connector_a):
    """sfm_list returns 200 and filters by connector, target_entity, direction, and search query."""
    map1 = _integrationapihub_create_test_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="order",
        local_field="order_number",
        remote_field="SAP_VBELN",
        direction="outbound",
    )
    map2 = _integrationapihub_create_test_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="lead",
        local_field="email",
        remote_field="hs_email",
        direction="inbound",
    )

    url = reverse("sales:sfm_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    mappings = resp.context["mappings"]
    assert map1 in mappings
    assert map2 in mappings

    # Filter by connector
    resp_conn = client_a.get(url, {"connector": iah_connector_a.pk})
    assert map1 in resp_conn.context["mappings"]
    assert map2 in resp_conn.context["mappings"]

    # Filter by target_entity
    resp_ent = client_a.get(url, {"target_entity": "order"})
    assert map1 in resp_ent.context["mappings"]
    assert map2 not in resp_ent.context["mappings"]

    # Filter by direction
    resp_dir = client_a.get(url, {"direction": "inbound"})
    assert map2 in resp_dir.context["mappings"]
    assert map1 not in resp_dir.context["mappings"]

    # Search query
    resp_q = client_a.get(url, {"q": "SAP_VBELN"})
    assert map1 in resp_q.context["mappings"]
    assert map2 not in resp_q.context["mappings"]


def test_integrationapihub_field_mapping_list_huge_int_resilience(client_a):
    """sfm_list handles huge integer param safely without SQLite integer overflow error (I2)."""
    url = reverse("sales:sfm_list")
    huge_int = "999999999999999999999999999999"
    resp = client_a.get(url, {"connector": huge_int})
    assert resp.status_code == 200
    assert "mappings" in resp.context


def test_integrationapihub_field_mapping_create_view(client_a, tenant_a, iah_connector_a):
    """sfm_create renders form on GET and creates field mapping on POST."""
    create_url = reverse("sales:sfm_create")
    get_resp = client_a.get(create_url, {"connector": iah_connector_a.pk})
    assert get_resp.status_code == 200
    assert get_resp.context["is_edit"] is False

    post_data = {
        "connector": iah_connector_a.pk,
        "target_entity": "opportunity",
        "local_field": "win_probability",
        "remote_field": "PROB_PCT",
        "direction": "outbound",
        "transform_rule": "none",
        "value_map": "{}",
        "default_value": "50",
        "is_key": False,
        "is_required": True,
        "is_active": True,
    }
    post_resp = client_a.post(create_url, data=post_data)
    assert post_resp.status_code == 302

    created = SalesFieldMapping.objects.get(
        tenant=tenant_a,
        connector=iah_connector_a,
        local_field="win_probability",
        remote_field="PROB_PCT",
    )
    assert post_resp.url == reverse("sales:sfm_detail", kwargs={"pk": created.pk})
    assert created.target_entity == "opportunity"
    assert created.direction == "outbound"
    assert created.value_map == {}
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_integrationapihub_field_mapping_detail_view(client_a, iah_field_mapping_a):
    """sfm_detail returns 200 and passes mapping in context."""
    url = reverse("sales:sfm_detail", kwargs={"pk": iah_field_mapping_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["mapping"] == iah_field_mapping_a


def test_integrationapihub_field_mapping_edit_view(client_a, tenant_a, iah_field_mapping_a):
    """sfm_edit renders form on GET and updates field mapping on POST."""
    edit_url = reverse("sales:sfm_edit", kwargs={"pk": iah_field_mapping_a.pk})
    get_resp = client_a.get(edit_url)
    assert get_resp.status_code == 200
    assert get_resp.context["is_edit"] is True
    assert get_resp.context["mapping"] == iah_field_mapping_a

    post_data = {
        "connector": iah_field_mapping_a.connector.pk,
        "target_entity": iah_field_mapping_a.target_entity,
        "local_field": "net_amount",
        "remote_field": iah_field_mapping_a.remote_field,
        "direction": "outbound",
        "transform_rule": "currency_round",
        "value_map": "{}",
        "default_value": "10.00",
        "is_key": True,
        "is_required": False,
        "is_active": True,
    }
    post_resp = client_a.post(edit_url, data=post_data)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:sfm_detail", kwargs={"pk": iah_field_mapping_a.pk})

    iah_field_mapping_a.refresh_from_db()
    assert iah_field_mapping_a.local_field == "net_amount"
    assert iah_field_mapping_a.direction == "outbound"
    assert iah_field_mapping_a.default_value == "10.00"
    assert iah_field_mapping_a.is_key is True
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=iah_field_mapping_a.pk).exists()


def test_integrationapihub_field_mapping_delete_view_with_next_param(client_a, tenant_a, iah_connector_a):
    """sfm_delete honors 'next' param redirect (M1)."""
    mapping = _integrationapihub_create_test_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        local_field="temp_delete_1",
        remote_field="TEMP_1",
    )
    del_url = reverse("sales:sfm_delete", kwargs={"pk": mapping.pk})

    # GET is rejected (require_POST)
    assert client_a.get(del_url).status_code == 405

    # POST with next parameter
    target_next = reverse("sales:sfm_list")
    post_resp = client_a.post(del_url, data={"next": target_next})
    assert post_resp.status_code == 302
    assert post_resp.url == target_next
    assert not SalesFieldMapping.objects.filter(pk=mapping.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=mapping.pk).exists()


def test_integrationapihub_field_mapping_delete_view_default_and_referer_redirect(
    client_a, tenant_a, iah_connector_a
):
    """sfm_delete redirects to connector detail by default or sfm_list when HTTP_REFERER contains 'mappings'."""
    # 1. Default redirect without next or referer -> sic_detail
    map1 = _integrationapihub_create_test_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        local_field="default_redir_local",
        remote_field="DEFAULT_REDIR_REMOTE",
    )
    del1_url = reverse("sales:sfm_delete", kwargs={"pk": map1.pk})
    resp1 = client_a.post(del1_url)
    assert resp1.status_code == 302
    assert resp1.url == reverse("sales:sic_detail", kwargs={"pk": iah_connector_a.pk})

    # 2. Referer containing 'mappings' -> sfm_list
    map2 = _integrationapihub_create_test_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        local_field="referer_redir_local",
        remote_field="REFERER_REDIR_REMOTE",
    )
    del2_url = reverse("sales:sfm_delete", kwargs={"pk": map2.pk})
    resp2 = client_a.post(del2_url, HTTP_REFERER="https://testserver/sales/mappings/?page=1")
    assert resp2.status_code == 302
    assert resp2.url == reverse("sales:sfm_list")


# ==============================================================================
# 5. SalesSyncJob Views
# ==============================================================================

def test_integrationapihub_sync_job_list_view_and_filters(client_a, tenant_a, iah_connector_a):
    """ssj_list returns 200 and filters by connector, entity_scope, and status."""
    job1 = _integrationapihub_create_test_sync_job(
        tenant_a,
        connector=iah_connector_a,
        name="Contract Envelope Pipeline",
        entity_scope="contract_envelope_status",
        status="active",
    )
    job2 = _integrationapihub_create_test_sync_job(
        tenant_a,
        connector=iah_connector_a,
        name="BI Warehouse Daily Feed",
        entity_scope="bi_warehouse_feed",
        status="paused",
    )

    url = reverse("sales:ssj_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    jobs = resp.context["jobs"]
    assert job1 in jobs
    assert job2 in jobs

    # Filter by connector
    resp_conn = client_a.get(url, {"connector": iah_connector_a.pk})
    assert job1 in resp_conn.context["jobs"]
    assert job2 in resp_conn.context["jobs"]

    # Filter by entity_scope
    resp_scope = client_a.get(url, {"entity_scope": "contract_envelope_status"})
    assert job1 in resp_scope.context["jobs"]
    assert job2 not in resp_scope.context["jobs"]

    # Filter by status
    resp_status = client_a.get(url, {"status": "paused"})
    assert job2 in resp_status.context["jobs"]
    assert job1 not in resp_status.context["jobs"]

    # Search query
    resp_q = client_a.get(url, {"q": "Warehouse Daily"})
    assert job2 in resp_q.context["jobs"]
    assert job1 not in resp_q.context["jobs"]


def test_integrationapihub_sync_job_list_huge_int_resilience(client_a):
    """ssj_list handles huge integer param safely without SQLite integer overflow error (I2)."""
    url = reverse("sales:ssj_list")
    huge_int = "999999999999999999999999999999"
    resp = client_a.get(url, {"connector": huge_int})
    assert resp.status_code == 200
    assert "jobs" in resp.context


def test_integrationapihub_sync_job_create_view(client_a, tenant_a, iah_connector_a):
    """ssj_create renders form on GET and creates sync job on POST."""
    create_url = reverse("sales:ssj_create")
    get_resp = client_a.get(create_url, {"connector": iah_connector_a.pk})
    assert get_resp.status_code == 200
    assert get_resp.context["is_edit"] is False

    post_data = {
        "name": "Customer Accounts Master Sync",
        "connector": iah_connector_a.pk,
        "entity_scope": "lead_lifecycle",
        "sync_direction": "inbound",
        "conflict_policy": "remote_wins",
        "cadence": "hourly",
        "filter_expression": "status='qualified'",
        "batch_size": 200,
        "status": "active",
    }
    post_resp = client_a.post(create_url, data=post_data)
    assert post_resp.status_code == 302

    created = SalesSyncJob.objects.get(tenant=tenant_a, name="Customer Accounts Master Sync")
    assert post_resp.url == reverse("sales:ssj_detail", kwargs={"pk": created.pk})
    assert created.batch_size == 200
    assert created.total_runs_count == 0
    assert created.total_records_synced == 0
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_integrationapihub_sync_job_detail_view(client_a, iah_sync_job_a):
    """ssj_detail returns 200 and passes job and recent_runs in context."""
    url = reverse("sales:ssj_detail", kwargs={"pk": iah_sync_job_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["job"] == iah_sync_job_a
    assert "recent_runs" in resp.context


def test_integrationapihub_sync_job_edit_view(client_a, tenant_a, iah_sync_job_a):
    """ssj_edit renders form on GET and updates job on POST."""
    edit_url = reverse("sales:ssj_edit", kwargs={"pk": iah_sync_job_a.pk})
    get_resp = client_a.get(edit_url)
    assert get_resp.status_code == 200
    assert get_resp.context["is_edit"] is True
    assert get_resp.context["job"] == iah_sync_job_a

    post_data = {
        "name": "Updated Order Pipeline Sync",
        "connector": iah_sync_job_a.connector.pk,
        "entity_scope": iah_sync_job_a.entity_scope,
        "sync_direction": iah_sync_job_a.sync_direction,
        "conflict_policy": "local_wins",
        "cadence": "daily",
        "filter_expression": "status='posted'",
        "batch_size": 500,
        "status": "paused",
    }
    post_resp = client_a.post(edit_url, data=post_data)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:ssj_detail", kwargs={"pk": iah_sync_job_a.pk})

    iah_sync_job_a.refresh_from_db()
    assert iah_sync_job_a.name == "Updated Order Pipeline Sync"
    assert iah_sync_job_a.conflict_policy == "local_wins"
    assert iah_sync_job_a.cadence == "daily"
    assert iah_sync_job_a.batch_size == 500
    assert iah_sync_job_a.status == "paused"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=iah_sync_job_a.pk).exists()


def test_integrationapihub_sync_job_delete_view(client_a, tenant_a, iah_connector_a):
    """ssj_delete rejects GET (405) and deletes sync job on POST (302)."""
    job = _integrationapihub_create_test_sync_job(
        tenant_a,
        connector=iah_connector_a,
        name="Job To Delete",
    )
    del_url = reverse("sales:ssj_delete", kwargs={"pk": job.pk})

    # GET is rejected (require_POST)
    assert client_a.get(del_url).status_code == 405

    # POST deletes
    post_resp = client_a.post(del_url)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:ssj_list")
    assert not SalesSyncJob.objects.filter(pk=job.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=job.pk).exists()


def test_integrationapihub_sync_job_trigger_action(client_a, tenant_a, iah_sync_job_a):
    """ssj_trigger executes simulated run, increments total_runs_count, updates last_run_at, logs run."""
    trigger_url = reverse("sales:ssj_trigger", kwargs={"pk": iah_sync_job_a.pk})

    # GET is rejected (require_POST)
    assert client_a.get(trigger_url).status_code == 405

    initial_runs = iah_sync_job_a.total_runs_count
    initial_synced = iah_sync_job_a.total_records_synced

    post_resp = client_a.post(trigger_url)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:ssj_detail", kwargs={"pk": iah_sync_job_a.pk})

    iah_sync_job_a.refresh_from_db()
    assert iah_sync_job_a.total_runs_count == initial_runs + 1
    assert iah_sync_job_a.total_records_synced == initial_synced + 5
    assert iah_sync_job_a.last_run_at is not None

    run = SalesSyncRun.objects.filter(
        tenant=tenant_a,
        job=iah_sync_job_a,
        connector=iah_sync_job_a.connector,
    ).latest("id")
    assert run.run_type == "manual"
    assert run.status == "simulated"
    assert run.records_read == 5
    assert run.records_written == 5
    assert run.records_failed == 0
    assert run.summary_payload.get("simulated") is True
    assert AuditLog.objects.filter(tenant=tenant_a, action="run", object_id=iah_sync_job_a.pk).exists()


# ==============================================================================
# 6. SalesSyncRun Views
# ==============================================================================

def test_integrationapihub_sync_run_list_view_and_filters(
    client_a, tenant_a, iah_connector_a, iah_sync_job_a, admin_user
):
    """ssr_list returns 200 and filters by connector, job, run_type, status, and search query."""
    run1 = _integrationapihub_create_test_sync_run(
        tenant_a,
        connector=iah_connector_a,
        job=iah_sync_job_a,
        run_type="manual",
        status="simulated",
        triggered_by=admin_user,
    )
    run2 = _integrationapihub_create_test_sync_run(
        tenant_a,
        connector=iah_connector_a,
        job=None,
        run_type="test_ping",
        status="completed",
        triggered_by=admin_user,
    )

    url = reverse("sales:ssr_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    runs = resp.context["runs"]
    assert run1 in runs
    assert run2 in runs

    # Filter by connector
    resp_conn = client_a.get(url, {"connector": iah_connector_a.pk})
    assert run1 in resp_conn.context["runs"]
    assert run2 in resp_conn.context["runs"]

    # Filter by job
    resp_job = client_a.get(url, {"job": iah_sync_job_a.pk})
    assert run1 in resp_job.context["runs"]
    assert run2 not in resp_job.context["runs"]

    # Filter by run_type
    resp_type = client_a.get(url, {"run_type": "test_ping"})
    assert run2 in resp_type.context["runs"]
    assert run1 not in resp_type.context["runs"]

    # Filter by status
    resp_stat = client_a.get(url, {"status": "completed"})
    assert run2 in resp_stat.context["runs"]
    assert run1 not in resp_stat.context["runs"]

    # Search by run number
    resp_q = client_a.get(url, {"q": run1.number})
    assert run1 in resp_q.context["runs"]
    assert run2 not in resp_q.context["runs"]


def test_integrationapihub_sync_run_list_huge_int_resilience(client_a):
    """ssr_list handles huge integer param safely without SQLite integer overflow error (I2)."""
    url = reverse("sales:ssr_list")
    huge_int = "999999999999999999999999999999"
    resp = client_a.get(url, {"connector": huge_int, "job": huge_int})
    assert resp.status_code == 200
    assert "runs" in resp.context


def test_integrationapihub_sync_run_detail_view(client_a, iah_sync_run_a):
    """ssr_detail returns 200 and passes run in context."""
    url = reverse("sales:ssr_detail", kwargs={"pk": iah_sync_run_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["run"] == iah_sync_run_a


def test_integrationapihub_sync_run_delete_view(client_a, tenant_a, iah_connector_a):
    """ssr_delete rejects GET (405) and deletes run log on POST (302)."""
    run = _integrationapihub_create_test_sync_run(tenant_a, connector=iah_connector_a)
    del_url = reverse("sales:ssr_delete", kwargs={"pk": run.pk})

    # GET is rejected (require_POST)
    assert client_a.get(del_url).status_code == 405

    # POST deletes
    post_resp = client_a.post(del_url)
    assert post_resp.status_code == 302
    assert post_resp.url == reverse("sales:ssr_list")
    assert not SalesSyncRun.objects.filter(pk=run.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=run.pk).exists()


# ==============================================================================
# 7. Pagination Handling
# ==============================================================================

def test_integrationapihub_pagination_invalid_page(
    client_a, tenant_a, iah_connector_a, iah_field_mapping_a, iah_sync_job_a, iah_sync_run_a
):
    """All list views gracefully recover from invalid or out-of-range ?page= params."""
    list_urls = [
        reverse("sales:sic_list"),
        reverse("sales:sfm_list"),
        reverse("sales:ssj_list"),
        reverse("sales:ssr_list"),
    ]

    for url in list_urls:
        # String/invalid page returns page 1
        resp_invalid = client_a.get(url, {"page": "invalid_page"})
        assert resp_invalid.status_code == 200
        assert resp_invalid.context["page_obj"].number == 1

        # Negative page returns page 1 or handles cleanly
        resp_negative = client_a.get(url, {"page": "-5"})
        assert resp_negative.status_code == 200

        # Excessive page number returns last page
        resp_excessive = client_a.get(url, {"page": "999999"})
        assert resp_excessive.status_code == 200


# ==============================================================================
# 8. Cross-Tenant IDOR Protection
# ==============================================================================

def test_integrationapihub_cross_tenant_isolation_404(
    client_a,
    tenant_b,
    iah_connector_b,
    iah_field_mapping_b,
    iah_sync_job_b,
    iah_sync_run_b,
):
    """Client from tenant A attempting to read or mutate tenant B objects receives 404."""
    endpoints = [
        ("get", reverse("sales:sic_detail", kwargs={"pk": iah_connector_b.pk})),
        ("get", reverse("sales:sic_edit", kwargs={"pk": iah_connector_b.pk})),
        ("post", reverse("sales:sic_delete", kwargs={"pk": iah_connector_b.pk})),
        ("post", reverse("sales:sic_test", kwargs={"pk": iah_connector_b.pk})),
        ("get", reverse("sales:sfm_detail", kwargs={"pk": iah_field_mapping_b.pk})),
        ("get", reverse("sales:sfm_edit", kwargs={"pk": iah_field_mapping_b.pk})),
        ("post", reverse("sales:sfm_delete", kwargs={"pk": iah_field_mapping_b.pk})),
        ("get", reverse("sales:ssj_detail", kwargs={"pk": iah_sync_job_b.pk})),
        ("get", reverse("sales:ssj_edit", kwargs={"pk": iah_sync_job_b.pk})),
        ("post", reverse("sales:ssj_delete", kwargs={"pk": iah_sync_job_b.pk})),
        ("post", reverse("sales:ssj_trigger", kwargs={"pk": iah_sync_job_b.pk})),
        ("get", reverse("sales:ssr_detail", kwargs={"pk": iah_sync_run_b.pk})),
        ("post", reverse("sales:ssr_delete", kwargs={"pk": iah_sync_run_b.pk})),
    ]

    for method, url in endpoints:
        client_fn = getattr(client_a, method)
        resp = client_fn(url)
        assert resp.status_code == 404, f"{method.upper()} {url} across tenants expected 404 but got {resp.status_code}"


# ==============================================================================
# 9. Tenant Admin Role Guard
# ==============================================================================

def test_integrationapihub_tenant_admin_required_guard(
    member_client,
    tenant_a,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """Non-admin tenant member accessing admin-gated mutation endpoints receives 403 PermissionDenied."""
    mutations = [
        ("get", reverse("sales:sic_create")),
        ("post", reverse("sales:sic_create")),
        ("get", reverse("sales:sic_edit", kwargs={"pk": iah_connector_a.pk})),
        ("post", reverse("sales:sic_edit", kwargs={"pk": iah_connector_a.pk})),
        ("post", reverse("sales:sic_delete", kwargs={"pk": iah_connector_a.pk})),
        ("post", reverse("sales:sic_test", kwargs={"pk": iah_connector_a.pk})),
        ("get", reverse("sales:sfm_create")),
        ("post", reverse("sales:sfm_create")),
        ("get", reverse("sales:sfm_edit", kwargs={"pk": iah_field_mapping_a.pk})),
        ("post", reverse("sales:sfm_edit", kwargs={"pk": iah_field_mapping_a.pk})),
        ("post", reverse("sales:sfm_delete", kwargs={"pk": iah_field_mapping_a.pk})),
        ("get", reverse("sales:ssj_create")),
        ("post", reverse("sales:ssj_create")),
        ("get", reverse("sales:ssj_edit", kwargs={"pk": iah_sync_job_a.pk})),
        ("post", reverse("sales:ssj_edit", kwargs={"pk": iah_sync_job_a.pk})),
        ("post", reverse("sales:ssj_delete", kwargs={"pk": iah_sync_job_a.pk})),
        ("post", reverse("sales:ssj_trigger", kwargs={"pk": iah_sync_job_a.pk})),
        ("post", reverse("sales:ssr_delete", kwargs={"pk": iah_sync_run_a.pk})),
    ]

    for method, url in mutations:
        client_fn = getattr(member_client, method)
        resp = client_fn(url)
        assert resp.status_code == 403, f"{method.upper()} {url} by member expected 403 PermissionDenied"
