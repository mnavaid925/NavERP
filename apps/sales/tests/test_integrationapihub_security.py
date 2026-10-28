"""Sub-module 8.18 Integration & API Hub — Security & Multi-Tenancy Test Suite.

Subslug: integrationapihub
Prefix for test functions: test_integrationapihub_*
Prefix for helper functions: _integrationapihub_*

Covers:
1. Cross-Tenant IDOR:
   - Client authenticated as Tenant A requesting Tenant B objects (Connectors, Mappings, Jobs, Runs)
     across detail, edit, delete, test, and trigger views -> assert 404 Not Found.
   - Client authenticated as Tenant B requesting Tenant A objects -> assert 404 Not Found.
   - List views (connectors, mappings, jobs, runs) and Dashboard never leak Tenant B data into Tenant A's response.
2. Cross-Tenant FK Injection:
   - Tenant A client attempting to assign Tenant B's connector to a new field mapping or sync job -> rejected
     by form validation with clean error.
   - Tenant A client attempting to update existing field mapping or sync job to point to Tenant B's connector -> rejected.
3. AuthN & AuthZ:
   - All 26 routes reject unauthenticated access and redirect to login (302).
   - `@tenant_admin_required`: Non-admin member receives 403 PermissionDenied on all mutating endpoints
     (`sic_create`, `sic_edit`, `sic_delete`, `sic_test`, `sfm_create`, `sfm_edit`, `sfm_delete`,
      `ssj_create`, `ssj_edit`, `ssj_delete`, `ssj_trigger`, `ssr_delete`).
   - Non-admin member can safely read list and detail pages (200).
4. HTTP Method Enforcement:
   - Destructive and execution endpoints (`sic_delete`, `sic_test`, `sfm_delete`, `ssj_delete`,
     `ssj_trigger`, `ssr_delete`) reject GET with 405 Method Not Allowed (`@require_POST`).
5. CSRF Protection:
   - Enforce CSRF protection on POST endpoints (`Client(enforce_csrf_checks=True)` returns 403 without token).
6. Secret Protection & Cryptography (L20, L25):
   - Secret submitted via `credential_input` is stored encrypted at rest with Fernet (`fernet.v1:`).
   - Detail view displays `••••••••` masked credential and never leaks plaintext secret.
   - Plaintext secret is never flashed in Django `messages.success`.
   - Plaintext secret is never written to `AuditLog.changes`.
7. Zero Outbound Sockets / HTTP Requests:
   - Assert `sic_test` and `ssj_trigger` execute simulated runs (`status="simulated"`) without making
     outbound network socket connections.
"""
import socket
import urllib.request
import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from apps.core.crypto import decrypt, is_encrypted
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

def _integrationapihub_forbid_network(*args, **kwargs):
    """Network block guard to prove zero outbound socket or HTTP execution."""
    raise AssertionError("Outbound network access is strictly forbidden in simulation execution!")


def _integrationapihub_csrf_client(user):
    """Return a test client for user with strict CSRF check enforcement enabled."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


def _integrationapihub_all_routes(iah_connector_a, iah_field_mapping_a, iah_sync_job_a, iah_sync_run_a):
    """Return all 26 route names and required URL arguments for Integration & API Hub."""
    return [
        # Dashboard & Category Lens routes (6)
        ("sales:integration_hub", []),
        ("sales:sic_erp_list", []),
        ("sales:sic_marketing_list", []),
        ("sales:sic_communication_list", []),
        ("sales:sic_bi_list", []),
        ("sales:sic_esignature_list", []),
        # SalesIntegrationConnector routes (6)
        ("sales:sic_list", []),
        ("sales:sic_create", []),
        ("sales:sic_detail", [iah_connector_a.pk]),
        ("sales:sic_edit", [iah_connector_a.pk]),
        ("sales:sic_delete", [iah_connector_a.pk]),
        ("sales:sic_test", [iah_connector_a.pk]),
        # SalesFieldMapping routes (5)
        ("sales:sfm_list", []),
        ("sales:sfm_create", []),
        ("sales:sfm_detail", [iah_field_mapping_a.pk]),
        ("sales:sfm_edit", [iah_field_mapping_a.pk]),
        ("sales:sfm_delete", [iah_field_mapping_a.pk]),
        # SalesSyncJob routes (6)
        ("sales:ssj_list", []),
        ("sales:ssj_create", []),
        ("sales:ssj_detail", [iah_sync_job_a.pk]),
        ("sales:ssj_edit", [iah_sync_job_a.pk]),
        ("sales:ssj_delete", [iah_sync_job_a.pk]),
        ("sales:ssj_trigger", [iah_sync_job_a.pk]),
        # SalesSyncRun routes (3)
        ("sales:ssr_list", []),
        ("sales:ssr_detail", [iah_sync_run_a.pk]),
        ("sales:ssr_delete", [iah_sync_run_a.pk]),
    ]


def _integrationapihub_mutating_endpoints(iah_connector_a, iah_field_mapping_a, iah_sync_job_a, iah_sync_run_a):
    """Return mutating endpoints that require tenant admin privilege."""
    return [
        ("post", reverse("sales:sic_create")),
        ("get", reverse("sales:sic_create")),
        ("post", reverse("sales:sic_edit", args=[iah_connector_a.pk])),
        ("get", reverse("sales:sic_edit", args=[iah_connector_a.pk])),
        ("post", reverse("sales:sic_delete", args=[iah_connector_a.pk])),
        ("post", reverse("sales:sic_test", args=[iah_connector_a.pk])),
        ("post", reverse("sales:sfm_create")),
        ("get", reverse("sales:sfm_create")),
        ("post", reverse("sales:sfm_edit", args=[iah_field_mapping_a.pk])),
        ("get", reverse("sales:sfm_edit", args=[iah_field_mapping_a.pk])),
        ("post", reverse("sales:sfm_delete", args=[iah_field_mapping_a.pk])),
        ("post", reverse("sales:ssj_create")),
        ("get", reverse("sales:ssj_create")),
        ("post", reverse("sales:ssj_edit", args=[iah_sync_job_a.pk])),
        ("get", reverse("sales:ssj_edit", args=[iah_sync_job_a.pk])),
        ("post", reverse("sales:ssj_delete", args=[iah_sync_job_a.pk])),
        ("post", reverse("sales:ssj_trigger", args=[iah_sync_job_a.pk])),
        ("post", reverse("sales:ssr_delete", args=[iah_sync_run_a.pk])),
    ]


# ==============================================================================
# 1. Cross-Tenant IDOR Protection
# ==============================================================================

def test_integrationapihub_cross_tenant_idor_detail_views_return_404(
    client_a,
    iah_connector_b,
    iah_field_mapping_b,
    iah_sync_job_b,
    iah_sync_run_b,
):
    """Client authenticated as Tenant A accessing Tenant B detail views returns 404 Not Found."""
    targets = [
        ("sales:sic_detail", [iah_connector_b.pk]),
        ("sales:sfm_detail", [iah_field_mapping_b.pk]),
        ("sales:ssj_detail", [iah_sync_job_b.pk]),
        ("sales:ssr_detail", [iah_sync_run_b.pk]),
    ]
    for route_name, args in targets:
        url = reverse(route_name, args=args)
        resp = client_a.get(url)
        assert resp.status_code == 404, f"{route_name} for Tenant B object did not return 404"


def test_integrationapihub_cross_tenant_idor_edit_views_return_404(
    client_a,
    iah_connector_b,
    iah_field_mapping_b,
    iah_sync_job_b,
):
    """Client authenticated as Tenant A attempting to view or submit edit for Tenant B objects returns 404."""
    targets = [
        ("sales:sic_edit", [iah_connector_b.pk], {"name": "Hacked Connector"}),
        ("sales:sfm_edit", [iah_field_mapping_b.pk], {"local_field": "hacked"}),
        ("sales:ssj_edit", [iah_sync_job_b.pk], {"name": "Hacked Sync Job"}),
    ]
    for route_name, args, post_data in targets:
        url = reverse(route_name, args=args)
        get_resp = client_a.get(url)
        assert get_resp.status_code == 404, f"GET {route_name} for foreign object expected 404"

        post_resp = client_a.post(url, data=post_data)
        assert post_resp.status_code == 404, f"POST {route_name} for foreign object expected 404"


def test_integrationapihub_cross_tenant_idor_delete_views_return_404(
    client_a,
    iah_connector_b,
    iah_field_mapping_b,
    iah_sync_job_b,
    iah_sync_run_b,
):
    """Client authenticated as Tenant A attempting to POST delete foreign objects returns 404 and does not delete."""
    targets = [
        ("sales:sic_delete", [iah_connector_b.pk], SalesIntegrationConnector, iah_connector_b.pk),
        ("sales:sfm_delete", [iah_field_mapping_b.pk], SalesFieldMapping, iah_field_mapping_b.pk),
        ("sales:ssj_delete", [iah_sync_job_b.pk], SalesSyncJob, iah_sync_job_b.pk),
        ("sales:ssr_delete", [iah_sync_run_b.pk], SalesSyncRun, iah_sync_run_b.pk),
    ]
    for route_name, args, model_cls, pk in targets:
        url = reverse(route_name, args=args)
        resp = client_a.post(url)
        assert resp.status_code == 404, f"POST {route_name} for foreign object expected 404"
        assert model_cls.objects.filter(pk=pk).exists(), f"{model_cls.__name__} should not have been deleted"


def test_integrationapihub_cross_tenant_idor_execution_actions_return_404(
    client_a,
    iah_connector_b,
    iah_sync_job_b,
):
    """Client authenticated as Tenant A attempting to trigger test or sync job on Tenant B returns 404."""
    initial_health = iah_connector_b.health_status
    initial_runs = iah_sync_job_b.total_runs_count

    # Connector test ping
    test_url = reverse("sales:sic_test", args=[iah_connector_b.pk])
    resp_test = client_a.post(test_url)
    assert resp_test.status_code == 404
    iah_connector_b.refresh_from_db()
    assert iah_connector_b.health_status == initial_health

    # Sync job trigger
    trigger_url = reverse("sales:ssj_trigger", args=[iah_sync_job_b.pk])
    resp_trigger = client_a.post(trigger_url)
    assert resp_trigger.status_code == 404
    iah_sync_job_b.refresh_from_db()
    assert iah_sync_job_b.total_runs_count == initial_runs


def test_integrationapihub_cross_tenant_idor_reverse_b_cannot_access_a(
    client_b,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """Client authenticated as Tenant B accessing Tenant A objects returns 404 on all detail and action routes."""
    targets = [
        ("sales:sic_detail", [iah_connector_a.pk]),
        ("sales:sic_edit", [iah_connector_a.pk]),
        ("sales:sic_delete", [iah_connector_a.pk]),
        ("sales:sic_test", [iah_connector_a.pk]),
        ("sales:sfm_detail", [iah_field_mapping_a.pk]),
        ("sales:sfm_edit", [iah_field_mapping_a.pk]),
        ("sales:sfm_delete", [iah_field_mapping_a.pk]),
        ("sales:ssj_detail", [iah_sync_job_a.pk]),
        ("sales:ssj_edit", [iah_sync_job_a.pk]),
        ("sales:ssj_delete", [iah_sync_job_a.pk]),
        ("sales:ssj_trigger", [iah_sync_job_a.pk]),
        ("sales:ssr_detail", [iah_sync_run_a.pk]),
        ("sales:ssr_delete", [iah_sync_run_a.pk]),
    ]
    for route_name, args in targets:
        url = reverse(route_name, args=args)
        resp = client_b.get(url) if "delete" not in route_name and "trigger" not in route_name and "test" not in route_name else client_b.post(url)
        assert resp.status_code == 404, f"{route_name} by Tenant B for Tenant A object expected 404"


def test_integrationapihub_list_views_and_dashboard_never_leak_foreign_tenant_data(
    client_a,
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
    iah_field_mapping_a,
    iah_field_mapping_b,
    iah_sync_job_a,
    iah_sync_job_b,
    iah_sync_run_a,
    iah_sync_run_b,
):
    """List views and Dashboard never display, count, or leak Tenant B records into Tenant A's session."""
    # Ensure distinct names for content leak assertion
    iah_sync_job_b.name = "Globex Isolated Enterprise Sync"
    iah_sync_job_b.save(update_fields=["name"])
    # 1. Connectors list
    resp_conn = client_a.get(reverse("sales:sic_list"))
    assert resp_conn.status_code == 200
    connectors = list(resp_conn.context["connectors"])
    assert iah_connector_a in connectors
    assert iah_connector_b not in connectors
    conn_content = resp_conn.content.decode("utf-8")
    assert iah_connector_b.name not in conn_content

    # 2. Field mappings list
    resp_sfm = client_a.get(reverse("sales:sfm_list"))
    assert resp_sfm.status_code == 200
    mappings = list(resp_sfm.context["mappings"])
    assert iah_field_mapping_a in mappings
    assert iah_field_mapping_b not in mappings

    # 3. Sync jobs list
    resp_ssj = client_a.get(reverse("sales:ssj_list"))
    assert resp_ssj.status_code == 200
    jobs = list(resp_ssj.context["jobs"])
    assert iah_sync_job_a in jobs
    assert iah_sync_job_b not in jobs
    job_content = resp_ssj.content.decode("utf-8")
    assert iah_sync_job_b.name not in job_content

    # 4. Sync runs list
    resp_ssr = client_a.get(reverse("sales:ssr_list"))
    assert resp_ssr.status_code == 200
    runs = list(resp_ssr.context["runs"])
    assert iah_sync_run_a in runs
    assert iah_sync_run_b not in runs
    assert iah_sync_run_b.pk not in [r.pk for r in runs]

    # 5. Hub dashboard
    resp_dash = client_a.get(reverse("sales:integration_hub"))
    assert resp_dash.status_code == 200
    ctx = resp_dash.context
    assert ctx["connectors_count"] == SalesIntegrationConnector.objects.filter(tenant=tenant_a).count()
    assert ctx["jobs_count"] == SalesSyncJob.objects.filter(tenant=tenant_a).count()
    assert ctx["runs_count"] == SalesSyncRun.objects.filter(tenant=tenant_a).count()
    assert iah_connector_b not in ctx["erp_connectors"]
    assert iah_sync_run_b not in ctx["recent_runs"]

    dash_content = resp_dash.content.decode("utf-8")
    assert iah_connector_b.name not in dash_content
    assert iah_sync_job_b.name not in dash_content


# ==============================================================================
# 2. Cross-Tenant ForeignKey Injection Protection
# ==============================================================================

def test_integrationapihub_cross_tenant_fk_injection_field_mapping_rejected(
    client_a,
    tenant_a,
    iah_connector_b,
    iah_connector_a,
    iah_field_mapping_a,
):
    """Tenant A client attempting to assign Tenant B's connector to a field mapping is rejected with form error."""
    # Attempt FK injection on Create
    create_url = reverse("sales:sfm_create")
    malicious_create_data = {
        "connector": iah_connector_b.pk,
        "target_entity": "opportunity",
        "local_field": "injected_field",
        "remote_field": "foreign_remote_field",
        "direction": "outbound",
        "transform_rule": "direct",
        "is_active": True,
    }
    resp_create = client_a.post(create_url, malicious_create_data)
    assert resp_create.status_code == 200
    form = resp_create.context["form"]
    assert not form.is_valid()
    assert "connector" in form.errors
    assert not SalesFieldMapping.objects.filter(
        tenant=tenant_a,
        local_field="injected_field",
    ).exists()

    # Attempt FK injection on Edit
    edit_url = reverse("sales:sfm_edit", args=[iah_field_mapping_a.pk])
    malicious_edit_data = {
        "connector": iah_connector_b.pk,
        "target_entity": iah_field_mapping_a.target_entity,
        "local_field": iah_field_mapping_a.local_field,
        "remote_field": iah_field_mapping_a.remote_field,
        "direction": iah_field_mapping_a.direction,
        "transform_rule": iah_field_mapping_a.transform_rule,
        "is_active": True,
    }
    resp_edit = client_a.post(edit_url, malicious_edit_data)
    assert resp_edit.status_code == 200
    assert not resp_edit.context["form"].is_valid()
    assert "connector" in resp_edit.context["form"].errors
    iah_field_mapping_a.refresh_from_db()
    assert iah_field_mapping_a.connector == iah_connector_a


def test_integrationapihub_cross_tenant_fk_injection_sync_job_rejected(
    client_a,
    tenant_a,
    iah_connector_b,
    iah_connector_a,
    iah_sync_job_a,
):
    """Tenant A client attempting to assign Tenant B's connector to a sync job is rejected with form error."""
    # Attempt FK injection on Create
    create_url = reverse("sales:ssj_create")
    malicious_job_data = {
        "name": "Malicious Injected Sync Job",
        "connector": iah_connector_b.pk,
        "entity_scope": "orders",
        "sync_direction": "inbound",
        "conflict_policy": "source_wins",
        "cadence": "hourly",
        "batch_size": 100,
        "status": "active",
    }
    resp_create = client_a.post(create_url, malicious_job_data)
    assert resp_create.status_code == 200
    form = resp_create.context["form"]
    assert not form.is_valid()
    assert "connector" in form.errors
    assert not SalesSyncJob.objects.filter(
        tenant=tenant_a,
        name="Malicious Injected Sync Job",
    ).exists()

    # Attempt FK injection on Edit
    edit_url = reverse("sales:ssj_edit", args=[iah_sync_job_a.pk])
    malicious_job_edit = {
        "name": "Updated Malicious Sync Job",
        "connector": iah_connector_b.pk,
        "entity_scope": iah_sync_job_a.entity_scope,
        "sync_direction": iah_sync_job_a.sync_direction,
        "conflict_policy": iah_sync_job_a.conflict_policy,
        "cadence": iah_sync_job_a.cadence,
        "batch_size": 50,
        "status": "active",
    }
    resp_edit = client_a.post(edit_url, malicious_job_edit)
    assert resp_edit.status_code == 200
    assert not resp_edit.context["form"].is_valid()
    assert "connector" in resp_edit.context["form"].errors
    iah_sync_job_a.refresh_from_db()
    assert iah_sync_job_a.connector == iah_connector_a


# ==============================================================================
# 3. Authentication & Authorization (AuthN & AuthZ)
# ==============================================================================

def test_integrationapihub_unauthenticated_access_redirects_all_routes_to_login(
    client,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """Anonymous visitors accessing any of the 26 Integration & API Hub routes redirect to login (302)."""
    routes = _integrationapihub_all_routes(
        iah_connector_a,
        iah_field_mapping_a,
        iah_sync_job_a,
        iah_sync_run_a,
    )
    assert len(routes) == 26

    for route_name, args in routes:
        url = reverse(route_name, args=args)
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect to login for {route_name}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected /login/ in redirect URL for {route_name}, got {resp.url}"


def test_integrationapihub_tenant_admin_required_blocks_non_admin_member(
    member_client,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """Non-admin tenant member receives 403 PermissionDenied on all mutating endpoints."""
    mutations = _integrationapihub_mutating_endpoints(
        iah_connector_a,
        iah_field_mapping_a,
        iah_sync_job_a,
        iah_sync_run_a,
    )
    for method, url in mutations:
        client_fn = getattr(member_client, method)
        resp = client_fn(url)
        assert resp.status_code == 403, (
            f"{method.upper()} {url} by non-admin member expected 403 PermissionDenied, got {resp.status_code}"
        )


def test_integrationapihub_non_admin_member_can_safely_read_surfaces(
    member_client,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """Non-admin tenant member can safely access all read surfaces (list, detail, dashboard)."""
    read_surfaces = [
        ("sales:integration_hub", []),
        ("sales:sic_list", []),
        ("sales:sic_detail", [iah_connector_a.pk]),
        ("sales:sfm_list", []),
        ("sales:sfm_detail", [iah_field_mapping_a.pk]),
        ("sales:ssj_list", []),
        ("sales:ssj_detail", [iah_sync_job_a.pk]),
        ("sales:ssr_list", []),
        ("sales:ssr_detail", [iah_sync_run_a.pk]),
    ]
    for route_name, args in read_surfaces:
        url = reverse(route_name, args=args)
        resp = member_client.get(url)
        assert resp.status_code == 200, f"Member GET {route_name} expected 200 OK, got {resp.status_code}"


# ==============================================================================
# 4. HTTP Method Enforcement
# ==============================================================================

def test_integrationapihub_http_method_enforcement_rejects_get_on_destructive_endpoints(
    client_a,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """Destructive and execution endpoints (@require_POST) reject GET with 405 Method Not Allowed."""
    post_only_endpoints = [
        ("sales:sic_delete", [iah_connector_a.pk]),
        ("sales:sic_test", [iah_connector_a.pk]),
        ("sales:sfm_delete", [iah_field_mapping_a.pk]),
        ("sales:ssj_delete", [iah_sync_job_a.pk]),
        ("sales:ssj_trigger", [iah_sync_job_a.pk]),
        ("sales:ssr_delete", [iah_sync_run_a.pk]),
    ]
    for route_name, args in post_only_endpoints:
        url = reverse(route_name, args=args)
        resp = client_a.get(url)
        assert resp.status_code == 405, (
            f"GET {route_name} expected 405 Method Not Allowed, got {resp.status_code}"
        )


# ==============================================================================
# 5. CSRF Protection
# ==============================================================================

def test_integrationapihub_csrf_protection_enforced_on_mutating_endpoints(
    admin_user,
    iah_connector_a,
    iah_field_mapping_a,
    iah_sync_job_a,
    iah_sync_run_a,
):
    """POST to mutating endpoints with Client(enforce_csrf_checks=True) returns 403 Forbidden without CSRF token."""
    csrf_client = _integrationapihub_csrf_client(admin_user)

    mutating_posts = [
        reverse("sales:sic_create"),
        reverse("sales:sic_edit", args=[iah_connector_a.pk]),
        reverse("sales:sic_delete", args=[iah_connector_a.pk]),
        reverse("sales:sic_test", args=[iah_connector_a.pk]),
        reverse("sales:sfm_create"),
        reverse("sales:sfm_edit", args=[iah_field_mapping_a.pk]),
        reverse("sales:sfm_delete", args=[iah_field_mapping_a.pk]),
        reverse("sales:ssj_create"),
        reverse("sales:ssj_edit", args=[iah_sync_job_a.pk]),
        reverse("sales:ssj_delete", args=[iah_sync_job_a.pk]),
        reverse("sales:ssj_trigger", args=[iah_sync_job_a.pk]),
        reverse("sales:ssr_delete", args=[iah_sync_run_a.pk]),
    ]

    for url in mutating_posts:
        resp = csrf_client.post(url, {})
        assert resp.status_code == 403, (
            f"CSRF protection failed for POST {url}: expected 403, got {resp.status_code}"
        )


# ==============================================================================
# 6. Secret Protection & Cryptography (L20, L25)
# ==============================================================================

def test_integrationapihub_secret_protection_fernet_encrypted_at_rest(
    client_a,
    tenant_a,
):
    """Secret submitted via credential_input is stored encrypted at rest with Fernet (fernet.v1:)."""
    raw_secret = "ConfidentialApiKey_Prod_998877!@#$"
    create_url = reverse("sales:sic_create")
    post_data = {
        "name": "Stripe Payments Production Bridge",
        "category": "erp",
        "provider": "custom",
        "environment": "production",
        "base_url": "https://api.stripe.example.com",
        "auth_method": "api_key",
        "credential_input": raw_secret,
        "remote_scope_ref": "acct_prod_stripe_123",
        "health_status": "untested",
        "is_active": True,
        "notes": "Encrypted credentials test",
    }

    resp = client_a.post(create_url, post_data)
    assert resp.status_code == 302

    connector = SalesIntegrationConnector.objects.get(
        tenant=tenant_a,
        name="Stripe Payments Production Bridge",
    )

    # 1. Stored encrypted at rest
    assert connector.credential_encrypted != raw_secret
    assert is_encrypted(connector.credential_encrypted)
    assert connector.credential_encrypted.startswith("fernet.v1:")
    # Decrypt returns original plaintext
    assert connector.get_credential() == raw_secret


def test_integrationapihub_secret_protection_masked_in_detail_and_never_leaked(
    client_a,
    tenant_a,
):
    """Detail view displays •••••••• masked credential and never leaks plaintext secret."""
    raw_secret = "TopSecretBearerToken_XYZ_12345"
    connector = _integrationapihub_connector(
        tenant_a,
        name="Secure Vault Connector",
        auth_method="api_key",
    )
    connector.set_credential(raw_secret)
    connector.save()

    detail_url = reverse("sales:sic_detail", args=[connector.pk])
    resp = client_a.get(detail_url)
    assert resp.status_code == 200

    content = resp.content.decode("utf-8")
    assert "••••••••" in content
    assert raw_secret not in content


def test_integrationapihub_secret_protection_never_flashed_in_messages_or_audit_log(
    client_a,
    tenant_a,
):
    """Plaintext secret is never flashed in Django messages or saved in AuditLog changes."""
    raw_secret = "NeverLeakThisSuperSecretString#2026"
    create_url = reverse("sales:sic_create")
    post_data = {
        "name": "Audit Safe Connector",
        "category": "communication",
        "provider": "slack",
        "environment": "production",
        "base_url": "https://slack.example.com/api",
        "auth_method": "oauth2",
        "credential_input": raw_secret,
        "remote_scope_ref": "workspace_corp",
        "health_status": "connected",
        "is_active": True,
        "notes": "Audit safe test",
    }

    resp = client_a.post(create_url, post_data, follow=True)
    assert resp.status_code == 200

    # 1. Plaintext secret is never in messages
    messages_list = list(get_messages(resp.wsgi_request))
    assert len(messages_list) >= 1
    for msg in messages_list:
        assert raw_secret not in msg.message

    # 2. Plaintext secret is never in response HTML content
    assert raw_secret not in resp.content.decode("utf-8")

    # 3. Plaintext secret is never written to AuditLog.changes
    connector = SalesIntegrationConnector.objects.get(
        tenant=tenant_a,
        name="Audit Safe Connector",
    )
    audit_logs = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=str(connector.pk),
    )
    assert audit_logs.exists()
    for log in audit_logs:
        assert raw_secret not in str(log.changes)
        assert "credential_input" not in str(log.changes)


# ==============================================================================
# 7. Zero Outbound Sockets / HTTP Requests
# ==============================================================================

def test_integrationapihub_zero_outbound_sockets_on_connector_test(
    client_a,
    iah_connector_a,
    monkeypatch,
):
    """sic_test executes simulated health check without making any outbound network socket connection."""
    monkeypatch.setattr(socket, "create_connection", _integrationapihub_forbid_network)
    monkeypatch.setattr(socket.socket, "connect", _integrationapihub_forbid_network)
    monkeypatch.setattr(urllib.request, "urlopen", _integrationapihub_forbid_network)

    url = reverse("sales:sic_test", args=[iah_connector_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    # Assert test run was created and recorded as simulated
    latest_run = SalesSyncRun.objects.filter(
        connector=iah_connector_a,
        run_type="test_ping",
    ).latest("created_at")

    assert latest_run.status == "simulated"
    assert latest_run.records_read == 1
    assert latest_run.records_written == 1
    assert latest_run.summary_payload.get("result") == "simulated_healthy_response"

    iah_connector_a.refresh_from_db()
    assert iah_connector_a.health_status == "connected"


def test_integrationapihub_zero_outbound_sockets_on_sync_job_trigger(
    client_a,
    iah_sync_job_a,
    monkeypatch,
):
    """ssj_trigger executes simulated sync run without making any outbound network socket connection."""
    monkeypatch.setattr(socket, "create_connection", _integrationapihub_forbid_network)
    monkeypatch.setattr(socket.socket, "connect", _integrationapihub_forbid_network)
    monkeypatch.setattr(urllib.request, "urlopen", _integrationapihub_forbid_network)

    initial_runs = iah_sync_job_a.total_runs_count

    url = reverse("sales:ssj_trigger", args=[iah_sync_job_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    iah_sync_job_a.refresh_from_db()
    assert iah_sync_job_a.total_runs_count == initial_runs + 1

    # Assert sync run was recorded as simulated
    latest_run = SalesSyncRun.objects.filter(
        job=iah_sync_job_a,
        run_type="manual",
    ).latest("created_at")

    assert latest_run.status == "simulated"
    assert latest_run.records_read == 5
    assert latest_run.records_written == 5
    assert latest_run.summary_payload.get("simulated") is True
