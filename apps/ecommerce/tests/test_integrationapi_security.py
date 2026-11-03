"""Security, IDOR isolation, Authentication/Authorization gates, SSRF defenses,
Mass Assignment prevention, and Secret Exposure protection tests for
Module 9.19 Integration & API Ecosystem.

Covers:
1. Multi-Tenant IDOR:
   - Cross-tenant GET detail -> 404 (Acme accessing Globex and vice versa across all 4 models).
   - Cross-tenant GET edit form -> 404.
   - Cross-tenant POST edit mutation -> 404.
   - Cross-tenant POST delete -> 404.
   - Cross-tenant POST action (`test_connection`, `retry`, `ping`, `revoke`) -> 404.
   - List query tenant isolation across all 4 models.
2. Authentication Gates:
   - Unauthenticated requests to all 25 hub/connector/sync-job/webhook/credential routes redirect 302 to login.
3. Authorization Gates (`@tenant_admin_required`):
   - Non-admin member user (`member_client`) attempting create, edit, delete, test, ping, revoke
     on Connectors, Webhooks, and API Credentials receives 403 Forbidden.
   - Non-admin member user can read list and detail views.
   - Tenant Admin user (`client_a`) is permitted.
4. SSRF Protection:
   - Form clean methods reject loopback (127.0.0.1, localhost, ::1, 0.0.0.0), cloud metadata (169.254.169.254),
     private network IPs (10.0.0.1, 192.168.1.1, 172.16.0.1), and internal domains (*.internal, *.local).
   - View POST with SSRF target URLs returns 200 with form errors, persisting zero records to DB.
   - Legitimate public URLs (e.g. Stripe, Slack) are accepted without errors.
5. Mass Assignment & State Security:
   - Submitting POST payloads with tenant, number, health_status, status, client_secret_hash,
     client_id, created_by, consecutive_failures, etc. cannot overwrite model invariants.
   - Cross-tenant foreign connector injection on sync jobs is rejected via `reject_foreign`.
   - Attempting to un-revoke a revoked ApiCredential is rejected.
   - Attempting to elevate ApiCredential tier on edit is blocked / ignored.
6. Secret Exposure Prevention:
   - PasswordInput widgets enforce `render_value=False` for connector api_secret and webhook secret_key.
   - Edit HTML forms never expose raw secrets in input values.
   - ApiCredential raw secrets are never stored in DB plaintext (SHA-256 hash only).
   - One-time session secret is popped on first detail GET and absent thereafter.
7. HTTP Method Safety:
   - All 8 destructive / action endpoints require POST and reject GET with 405 Method Not Allowed.
8. Header Security:
   - Webhook custom headers reject CRLF injection, hop-by-hop overrides, and non-dict JSON.
"""
import hashlib
import pytest
from django import forms
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.ecommerce.forms.IntegrationApi.ApiCredentials import ApiCredentialForm
from apps.ecommerce.forms.IntegrationApi.EcommerceConnectors import EcommerceConnectorForm
from apps.ecommerce.forms.IntegrationApi.IntegrationSyncJobs import IntegrationSyncJobForm
from apps.ecommerce.forms.IntegrationApi.WebhookSubscriptions import WebhookSubscriptionForm
from apps.ecommerce.models import (
    EcommerceConnector,
    IntegrationSyncJob,
    WebhookSubscription,
    ApiCredential,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (Prefixed with _integrationapi_*)
# ==============================================================================

def _integrationapi_valid_connector_post_data(**overrides):
    """Return a valid POST payload for EcommerceConnector create/edit."""
    data = {
        "name": "Acme Production Gateway",
        "category": "payment",
        "provider": "stripe",
        "auth_type": "api_key",
        "status": "active",
        "base_url": "https://api.stripe.com/v1",
        "api_version": "v1",
        "api_key": "sk_live_valid_key_123",
        "api_secret": "sec_live_valid_secret_456",
        "account_id": "acct_live_789",
        "is_sandbox": False,
        "timeout_seconds": 30,
        "rate_limit_per_minute": 120,
        "description": "Production gateway connector.",
    }
    data.update(overrides)
    return data


def _integrationapi_valid_sync_job_post_data(connector, **overrides):
    """Return a valid POST payload for IntegrationSyncJob create/edit."""
    connector_id = connector.pk if hasattr(connector, "pk") else connector
    data = {
        "connector": connector_id,
        "sync_entity": "order_to_cash",
        "direction": "outbound",
        "trigger_type": "manual",
        "batch_id": "sec-sync-batch-001",
        "max_retries": 3,
        "payload_preview": '{"scope": "security_test"}',
        "error_summary": "",
    }
    data.update(overrides)
    return data


def _integrationapi_valid_webhook_post_data(**overrides):
    """Return a valid POST payload for WebhookSubscription create/edit."""
    data = {
        "name": "Acme OMS Webhook",
        "target_url": "https://api.example.com/webhooks/orders",
        "event_topic": "order.created",
        "status": "active",
        "secret_key": "whsec_valid_sec_test_secret_123",
        "payload_format": "json",
        "custom_headers": '{"X-Security-Test": "Passed"}',
        "max_consecutive_failures": 5,
        "is_verify_ssl": True,
        "description": "Valid external webhook subscription.",
    }
    data.update(overrides)
    return data


def _integrationapi_valid_credential_post_data(**overrides):
    """Return a valid POST payload for ApiCredential create/edit."""
    data = {
        "name": "Partner Integration Key",
        "tier": "partner_read",
        "status": "active",
        "scopes": "read_catalog,read_orders,write_orders",
        "allowed_origins": "https://partner.example.com",
        "allowed_ips": "198.51.100.25/32",
        "rate_limit_rpm": 120,
        "description": "Partner API integration credentials.",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Multi-Tenant IDOR Isolation Tests
# ==============================================================================

def test_integrationapi_security_idor_connector_get_detail_404(client_a, client_b, ecom_connector_a, ecom_connector_b):
    """Cross-tenant GET detail on EcommerceConnector returns 404."""
    # Tenant A accessing Tenant B's connector
    resp_a = client_a.get(reverse("ecommerce:ecommerceconnector_detail", args=[ecom_connector_b.pk]))
    assert resp_a.status_code == 404

    # Tenant B accessing Tenant A's connector
    resp_b = client_b.get(reverse("ecommerce:ecommerceconnector_detail", args=[ecom_connector_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_connector_get_edit_404(client_a, client_b, ecom_connector_a, ecom_connector_b):
    """Cross-tenant GET edit form on EcommerceConnector returns 404."""
    resp_a = client_a.get(reverse("ecommerce:ecommerceconnector_edit", args=[ecom_connector_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:ecommerceconnector_edit", args=[ecom_connector_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_connector_post_edit_404(client_a, ecom_connector_b):
    """Cross-tenant POST edit mutation on EcommerceConnector returns 404 and does not mutate record."""
    original_name = ecom_connector_b.name
    payload = _integrationapi_valid_connector_post_data(name="Maliciously Renamed Connector")

    resp = client_a.post(reverse("ecommerce:ecommerceconnector_edit", args=[ecom_connector_b.pk]), payload)
    assert resp.status_code == 404

    ecom_connector_b.refresh_from_db()
    assert ecom_connector_b.name == original_name


def test_integrationapi_security_idor_connector_post_delete_404(client_a, ecom_connector_b):
    """Cross-tenant POST delete on EcommerceConnector returns 404 and does not delete record."""
    resp = client_a.post(reverse("ecommerce:ecommerceconnector_delete", args=[ecom_connector_b.pk]))
    assert resp.status_code == 404

    assert EcommerceConnector.objects.filter(pk=ecom_connector_b.pk).exists()


def test_integrationapi_security_idor_connector_post_test_connection_404(client_a, ecom_connector_b):
    """Cross-tenant POST test_connection on EcommerceConnector returns 404."""
    resp = client_a.post(reverse("ecommerce:ecommerceconnector_test_connection", args=[ecom_connector_b.pk]))
    assert resp.status_code == 404


def test_integrationapi_security_idor_sync_job_get_detail_404(client_a, client_b, ecom_sync_job_a, ecom_sync_job_b):
    """Cross-tenant GET detail on IntegrationSyncJob returns 404."""
    resp_a = client_a.get(reverse("ecommerce:integrationsyncjob_detail", args=[ecom_sync_job_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:integrationsyncjob_detail", args=[ecom_sync_job_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_sync_job_get_edit_404(client_a, client_b, ecom_sync_job_a, ecom_sync_job_b):
    """Cross-tenant GET edit form on IntegrationSyncJob returns 404."""
    resp_a = client_a.get(reverse("ecommerce:integrationsyncjob_edit", args=[ecom_sync_job_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:integrationsyncjob_edit", args=[ecom_sync_job_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_sync_job_post_edit_404(client_a, ecom_sync_job_b):
    """Cross-tenant POST edit mutation on IntegrationSyncJob returns 404 and does not mutate record."""
    original_batch = ecom_sync_job_b.batch_id
    payload = _integrationapi_valid_sync_job_post_data(ecom_sync_job_b.connector, batch_id="malicious-batch-override")

    resp = client_a.post(reverse("ecommerce:integrationsyncjob_edit", args=[ecom_sync_job_b.pk]), payload)
    assert resp.status_code == 404

    ecom_sync_job_b.refresh_from_db()
    assert ecom_sync_job_b.batch_id == original_batch


def test_integrationapi_security_idor_sync_job_post_delete_404(client_a, ecom_sync_job_b):
    """Cross-tenant POST delete on IntegrationSyncJob returns 404 and does not delete record."""
    resp = client_a.post(reverse("ecommerce:integrationsyncjob_delete", args=[ecom_sync_job_b.pk]))
    assert resp.status_code == 404

    assert IntegrationSyncJob.objects.filter(pk=ecom_sync_job_b.pk).exists()


def test_integrationapi_security_idor_sync_job_post_retry_404(client_a, ecom_sync_job_b):
    """Cross-tenant POST retry on IntegrationSyncJob returns 404 and spawns no child jobs."""
    initial_count = IntegrationSyncJob.objects.filter(tenant=ecom_sync_job_b.tenant).count()

    resp = client_a.post(reverse("ecommerce:integrationsyncjob_retry", args=[ecom_sync_job_b.pk]))
    assert resp.status_code == 404

    assert IntegrationSyncJob.objects.filter(tenant=ecom_sync_job_b.tenant).count() == initial_count


def test_integrationapi_security_idor_webhook_get_detail_404(client_a, client_b, ecom_webhook_a, ecom_webhook_b):
    """Cross-tenant GET detail on WebhookSubscription returns 404."""
    resp_a = client_a.get(reverse("ecommerce:webhooksubscription_detail", args=[ecom_webhook_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:webhooksubscription_detail", args=[ecom_webhook_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_webhook_get_edit_404(client_a, client_b, ecom_webhook_a, ecom_webhook_b):
    """Cross-tenant GET edit form on WebhookSubscription returns 404."""
    resp_a = client_a.get(reverse("ecommerce:webhooksubscription_edit", args=[ecom_webhook_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:webhooksubscription_edit", args=[ecom_webhook_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_webhook_post_edit_404(client_a, ecom_webhook_b):
    """Cross-tenant POST edit mutation on WebhookSubscription returns 404 and does not mutate record."""
    original_name = ecom_webhook_b.name
    payload = _integrationapi_valid_webhook_post_data(name="Maliciously Hijacked Webhook")

    resp = client_a.post(reverse("ecommerce:webhooksubscription_edit", args=[ecom_webhook_b.pk]), payload)
    assert resp.status_code == 404

    ecom_webhook_b.refresh_from_db()
    assert ecom_webhook_b.name == original_name


def test_integrationapi_security_idor_webhook_post_delete_404(client_a, ecom_webhook_b):
    """Cross-tenant POST delete on WebhookSubscription returns 404 and does not delete record."""
    resp = client_a.post(reverse("ecommerce:webhooksubscription_delete", args=[ecom_webhook_b.pk]))
    assert resp.status_code == 404

    assert WebhookSubscription.objects.filter(pk=ecom_webhook_b.pk).exists()


def test_integrationapi_security_idor_webhook_post_ping_404(client_a, ecom_webhook_b):
    """Cross-tenant POST ping on WebhookSubscription returns 404 and does not mutate delivery counters."""
    initial_delivered = ecom_webhook_b.total_delivered_count

    resp = client_a.post(reverse("ecommerce:webhooksubscription_ping", args=[ecom_webhook_b.pk]))
    assert resp.status_code == 404

    ecom_webhook_b.refresh_from_db()
    assert ecom_webhook_b.total_delivered_count == initial_delivered


def test_integrationapi_security_idor_credential_get_detail_404(client_a, client_b, ecom_credential_a, ecom_credential_b):
    """Cross-tenant GET detail on ApiCredential returns 404."""
    resp_a = client_a.get(reverse("ecommerce:apicredential_detail", args=[ecom_credential_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:apicredential_detail", args=[ecom_credential_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_credential_get_edit_404(client_a, client_b, ecom_credential_a, ecom_credential_b):
    """Cross-tenant GET edit form on ApiCredential returns 404."""
    resp_a = client_a.get(reverse("ecommerce:apicredential_edit", args=[ecom_credential_b.pk]))
    assert resp_a.status_code == 404

    resp_b = client_b.get(reverse("ecommerce:apicredential_edit", args=[ecom_credential_a.pk]))
    assert resp_b.status_code == 404


def test_integrationapi_security_idor_credential_post_edit_404(client_a, ecom_credential_b):
    """Cross-tenant POST edit mutation on ApiCredential returns 404 and does not mutate record."""
    original_name = ecom_credential_b.name
    payload = _integrationapi_valid_credential_post_data(name="Maliciously Hijacked Key")

    resp = client_a.post(reverse("ecommerce:apicredential_edit", args=[ecom_credential_b.pk]), payload)
    assert resp.status_code == 404

    ecom_credential_b.refresh_from_db()
    assert ecom_credential_b.name == original_name


def test_integrationapi_security_idor_credential_post_delete_404(client_a, ecom_credential_b):
    """Cross-tenant POST delete on ApiCredential returns 404 and does not delete record."""
    resp = client_a.post(reverse("ecommerce:apicredential_delete", args=[ecom_credential_b.pk]))
    assert resp.status_code == 404

    assert ApiCredential.objects.filter(pk=ecom_credential_b.pk).exists()


def test_integrationapi_security_idor_credential_post_revoke_404(client_a, ecom_credential_b):
    """Cross-tenant POST revoke on ApiCredential returns 404 and does not alter status."""
    assert ecom_credential_b.status == "active"

    resp = client_a.post(reverse("ecommerce:apicredential_revoke", args=[ecom_credential_b.pk]))
    assert resp.status_code == 404

    ecom_credential_b.refresh_from_db()
    assert ecom_credential_b.status == "active"
    assert ecom_credential_b.revoked_at is None


def test_integrationapi_security_list_views_tenant_isolation(
    client_a, client_b,
    ecom_connector_a, ecom_connector_b,
    ecom_sync_job_a, ecom_sync_job_b,
    ecom_webhook_a, ecom_webhook_b,
    ecom_credential_a, ecom_credential_b,
):
    """Verify list views strictly isolate querysets between tenants across all 4 models."""
    # 1. Connectors
    resp = client_a.get(reverse("ecommerce:ecommerceconnector_list"))
    assert resp.status_code == 200
    conn_ids = [c.pk for c in resp.context["connectors"]]
    assert ecom_connector_a.pk in conn_ids
    assert ecom_connector_b.pk not in conn_ids

    # 2. Sync Jobs
    resp = client_a.get(reverse("ecommerce:integrationsyncjob_list"))
    assert resp.status_code == 200
    job_ids = [j.pk for j in resp.context["sync_jobs"]]
    assert ecom_sync_job_a.pk in job_ids
    assert ecom_sync_job_b.pk not in job_ids

    # 3. Webhooks
    resp = client_a.get(reverse("ecommerce:webhooksubscription_list"))
    assert resp.status_code == 200
    wh_ids = [w.pk for w in resp.context["webhooks"]]
    assert ecom_webhook_a.pk in wh_ids
    assert ecom_webhook_b.pk not in wh_ids

    # 4. API Credentials
    resp = client_a.get(reverse("ecommerce:apicredential_list"))
    assert resp.status_code == 200
    cred_ids = [c.pk for c in resp.context["credentials"]]
    assert ecom_credential_a.pk in cred_ids
    assert ecom_credential_b.pk not in cred_ids


# ==============================================================================
# 2. Authentication Gates Tests (Unauthenticated -> 302 Login Redirect)
# ==============================================================================

def test_integrationapi_security_anonymous_redirect_hub(client):
    """Anonymous access to integration hub redirects to login."""
    resp = client.get(reverse("ecommerce:integration_api_hub"))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


def test_integrationapi_security_anonymous_redirect_connectors(client, ecom_connector_a):
    """Anonymous access to connector routes redirects to login."""
    pk = ecom_connector_a.pk
    urls = [
        reverse("ecommerce:ecommerceconnector_list"),
        reverse("ecommerce:ecommerceconnector_create"),
        reverse("ecommerce:ecommerceconnector_detail", args=[pk]),
        reverse("ecommerce:ecommerceconnector_edit", args=[pk]),
        reverse("ecommerce:ecommerceconnector_delete", args=[pk]),
        reverse("ecommerce:ecommerceconnector_test_connection", args=[pk]),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for GET {url}"
        assert "login" in resp.url

        # POST attempts should also redirect to login
        resp_post = client.post(url, {})
        assert resp_post.status_code == 302, f"Expected 302 redirect for POST {url}"
        assert "login" in resp_post.url


def test_integrationapi_security_anonymous_redirect_sync_jobs(client, ecom_sync_job_a):
    """Anonymous access to sync job routes redirects to login."""
    pk = ecom_sync_job_a.pk
    urls = [
        reverse("ecommerce:integrationsyncjob_list"),
        reverse("ecommerce:integrationsyncjob_create"),
        reverse("ecommerce:integrationsyncjob_detail", args=[pk]),
        reverse("ecommerce:integrationsyncjob_edit", args=[pk]),
        reverse("ecommerce:integrationsyncjob_delete", args=[pk]),
        reverse("ecommerce:integrationsyncjob_retry", args=[pk]),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for GET {url}"
        assert "login" in resp.url

        resp_post = client.post(url, {})
        assert resp_post.status_code == 302, f"Expected 302 redirect for POST {url}"
        assert "login" in resp_post.url


def test_integrationapi_security_anonymous_redirect_webhooks(client, ecom_webhook_a):
    """Anonymous access to webhook routes redirects to login."""
    pk = ecom_webhook_a.pk
    urls = [
        reverse("ecommerce:webhooksubscription_list"),
        reverse("ecommerce:webhooksubscription_create"),
        reverse("ecommerce:webhooksubscription_detail", args=[pk]),
        reverse("ecommerce:webhooksubscription_edit", args=[pk]),
        reverse("ecommerce:webhooksubscription_delete", args=[pk]),
        reverse("ecommerce:webhooksubscription_ping", args=[pk]),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for GET {url}"
        assert "login" in resp.url

        resp_post = client.post(url, {})
        assert resp_post.status_code == 302, f"Expected 302 redirect for POST {url}"
        assert "login" in resp_post.url


def test_integrationapi_security_anonymous_redirect_credentials(client, ecom_credential_a):
    """Anonymous access to API credential routes redirects to login."""
    pk = ecom_credential_a.pk
    urls = [
        reverse("ecommerce:apicredential_list"),
        reverse("ecommerce:apicredential_create"),
        reverse("ecommerce:apicredential_detail", args=[pk]),
        reverse("ecommerce:apicredential_edit", args=[pk]),
        reverse("ecommerce:apicredential_delete", args=[pk]),
        reverse("ecommerce:apicredential_revoke", args=[pk]),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for GET {url}"
        assert "login" in resp.url

        resp_post = client.post(url, {})
        assert resp_post.status_code == 302, f"Expected 302 redirect for POST {url}"
        assert "login" in resp_post.url


# ==============================================================================
# 3. Authorization Gates Tests (@tenant_admin_required)
# ==============================================================================

def test_integrationapi_security_authorization_member_forbidden_connector_actions(member_client, ecom_connector_a):
    """Non-admin member user attempting create, edit, delete, or test on Connectors receives 403 Forbidden."""
    pk = ecom_connector_a.pk

    # 1. Create GET and POST
    assert member_client.get(reverse("ecommerce:ecommerceconnector_create")).status_code == 403
    assert member_client.post(reverse("ecommerce:ecommerceconnector_create"), _integrationapi_valid_connector_post_data()).status_code == 403

    # 2. Edit GET and POST
    assert member_client.get(reverse("ecommerce:ecommerceconnector_edit", args=[pk])).status_code == 403
    assert member_client.post(reverse("ecommerce:ecommerceconnector_edit", args=[pk]), _integrationapi_valid_connector_post_data()).status_code == 403

    # 3. Delete POST
    assert member_client.post(reverse("ecommerce:ecommerceconnector_delete", args=[pk])).status_code == 403

    # 4. Test connection POST
    assert member_client.post(reverse("ecommerce:ecommerceconnector_test_connection", args=[pk])).status_code == 403


def test_integrationapi_security_authorization_member_forbidden_webhook_actions(member_client, ecom_webhook_a):
    """Non-admin member user attempting create, edit, delete, or ping on Webhooks receives 403 Forbidden."""
    pk = ecom_webhook_a.pk

    # 1. Create GET and POST
    assert member_client.get(reverse("ecommerce:webhooksubscription_create")).status_code == 403
    assert member_client.post(reverse("ecommerce:webhooksubscription_create"), _integrationapi_valid_webhook_post_data()).status_code == 403

    # 2. Edit GET and POST
    assert member_client.get(reverse("ecommerce:webhooksubscription_edit", args=[pk])).status_code == 403
    assert member_client.post(reverse("ecommerce:webhooksubscription_edit", args=[pk]), _integrationapi_valid_webhook_post_data()).status_code == 403

    # 3. Delete POST
    assert member_client.post(reverse("ecommerce:webhooksubscription_delete", args=[pk])).status_code == 403

    # 4. Ping POST
    assert member_client.post(reverse("ecommerce:webhooksubscription_ping", args=[pk])).status_code == 403


def test_integrationapi_security_authorization_member_forbidden_credential_actions(member_client, ecom_credential_a):
    """Non-admin member user attempting create, edit, delete, or revoke on API Credentials receives 403 Forbidden."""
    pk = ecom_credential_a.pk

    # 1. Create GET and POST
    assert member_client.get(reverse("ecommerce:apicredential_create")).status_code == 403
    assert member_client.post(reverse("ecommerce:apicredential_create"), _integrationapi_valid_credential_post_data()).status_code == 403

    # 2. Edit GET and POST
    assert member_client.get(reverse("ecommerce:apicredential_edit", args=[pk])).status_code == 403
    assert member_client.post(reverse("ecommerce:apicredential_edit", args=[pk]), _integrationapi_valid_credential_post_data()).status_code == 403

    # 3. Delete POST
    assert member_client.post(reverse("ecommerce:apicredential_delete", args=[pk])).status_code == 403

    # 4. Revoke POST
    assert member_client.post(reverse("ecommerce:apicredential_revoke", args=[pk])).status_code == 403


def test_integrationapi_security_authorization_member_read_allowed(
    member_client,
    ecom_connector_a,
    ecom_sync_job_a,
    ecom_webhook_a,
    ecom_credential_a,
):
    """Non-admin member user is permitted read-only access (200) to hub, lists, and details."""
    read_urls = [
        reverse("ecommerce:integration_api_hub"),
        reverse("ecommerce:ecommerceconnector_list"),
        reverse("ecommerce:ecommerceconnector_detail", args=[ecom_connector_a.pk]),
        reverse("ecommerce:integrationsyncjob_list"),
        reverse("ecommerce:integrationsyncjob_detail", args=[ecom_sync_job_a.pk]),
        reverse("ecommerce:webhooksubscription_list"),
        reverse("ecommerce:webhooksubscription_detail", args=[ecom_webhook_a.pk]),
        reverse("ecommerce:apicredential_list"),
        reverse("ecommerce:apicredential_detail", args=[ecom_credential_a.pk]),
    ]
    for url in read_urls:
        resp = member_client.get(url)
        assert resp.status_code == 200, f"Expected 200 OK for member GET {url}"


def test_integrationapi_security_authorization_admin_permitted_all_actions(client_a, ecom_connector_a, ecom_webhook_a, ecom_credential_a):
    """Tenant admin user (client_a) is permitted to access privileged forms and actions."""
    # Create forms GET
    assert client_a.get(reverse("ecommerce:ecommerceconnector_create")).status_code == 200
    assert client_a.get(reverse("ecommerce:webhooksubscription_create")).status_code == 200
    assert client_a.get(reverse("ecommerce:apicredential_create")).status_code == 200

    # Edit forms GET
    assert client_a.get(reverse("ecommerce:ecommerceconnector_edit", args=[ecom_connector_a.pk])).status_code == 200
    assert client_a.get(reverse("ecommerce:webhooksubscription_edit", args=[ecom_webhook_a.pk])).status_code == 200
    assert client_a.get(reverse("ecommerce:apicredential_edit", args=[ecom_credential_a.pk])).status_code == 200


# ==============================================================================
# 4. SSRF Protection Tests
# ==============================================================================

def test_integrationapi_security_ssrf_webhook_form_rejections(tenant_a):
    """WebhookSubscriptionForm clean_target_url rejects loopback, metadata, and private IP ranges."""
    malicious_endpoints = [
        ("http://127.0.0.1/webhook", "Localhost and loopback"),
        ("https://localhost/webhook", "Localhost and loopback"),
        ("http://[::1]/webhook", "Localhost and loopback"),
        ("http://0.0.0.0/webhook", "Localhost and loopback"),
        ("http://169.254.169.254/latest/meta-data", "Private, loopback, or metadata"),
        ("http://instance-data/meta-data", "Internal and metadata"),
        ("http://10.0.0.1/webhook", "Private, loopback, or metadata"),
        ("http://192.168.1.1/webhook", "Private, loopback, or metadata"),
        ("http://172.16.0.1/webhook", "Private, loopback, or metadata"),
        ("http://internal.service.local/hook", "Internal and metadata"),
        ("http://cluster.internal/hook", "Internal and metadata"),
        ("ftp://example.com/hook", "must begin with https:// or http://"),
    ]
    for url, err_substr in malicious_endpoints:
        form_data = _integrationapi_valid_webhook_post_data(target_url=url)
        form = WebhookSubscriptionForm(data=form_data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected URL '{url}' to fail SSRF check."
        assert "target_url" in form.errors
        error_msg = " ".join(form.errors["target_url"])
        assert err_substr in error_msg, f"Expected '{err_substr}' in '{error_msg}'"


def test_integrationapi_security_ssrf_connector_form_rejections(tenant_a):
    """EcommerceConnectorForm clean_base_url rejects loopback, metadata, and private IP ranges."""
    malicious_endpoints = [
        ("http://127.0.0.1:8080", "Localhost and loopback"),
        ("https://localhost:9000", "Localhost and loopback"),
        ("http://[::1]:8000", "Localhost and loopback"),
        ("http://0.0.0.0:80", "Localhost and loopback"),
        ("http://169.254.169.254", "Private, loopback, or metadata"),
        ("http://instance-data", "Internal and metadata"),
        ("http://10.10.1.5", "Private, loopback, or metadata"),
        ("http://192.168.0.254", "Private, loopback, or metadata"),
        ("http://172.20.0.5", "Private, loopback, or metadata"),
        ("http://app.internal", "Internal and metadata"),
        ("http://app.local", "Internal and metadata"),
        ("gopher://example.com", "must begin with https:// or http://"),
    ]
    for url, err_substr in malicious_endpoints:
        form_data = _integrationapi_valid_connector_post_data(base_url=url)
        form = EcommerceConnectorForm(data=form_data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected base_url '{url}' to fail SSRF check."
        assert "base_url" in form.errors
        error_msg = " ".join(form.errors["base_url"])
        assert err_substr in error_msg, f"Expected '{err_substr}' in '{error_msg}'"


def test_integrationapi_security_ssrf_view_post_blocked(client_a, tenant_a):
    """Attempted SSRF payloads submitted via views return 200 with form errors and persist no records."""
    # 1. Webhook subscription create with AWS metadata endpoint
    wh_initial_count = WebhookSubscription.objects.filter(tenant=tenant_a).count()
    wh_payload = _integrationapi_valid_webhook_post_data(target_url="http://169.254.169.254/latest/meta-data/")
    resp_wh = client_a.post(reverse("ecommerce:webhooksubscription_create"), wh_payload)
    assert resp_wh.status_code == 200
    assert "target_url" in resp_wh.context["form"].errors
    assert WebhookSubscription.objects.filter(tenant=tenant_a).count() == wh_initial_count

    # 2. Connector create with loopback endpoint
    conn_initial_count = EcommerceConnector.objects.filter(tenant=tenant_a).count()
    conn_payload = _integrationapi_valid_connector_post_data(base_url="http://127.0.0.1:8000/api")
    resp_conn = client_a.post(reverse("ecommerce:ecommerceconnector_create"), conn_payload)
    assert resp_conn.status_code == 200
    assert "base_url" in resp_conn.context["form"].errors
    assert EcommerceConnector.objects.filter(tenant=tenant_a).count() == conn_initial_count


def test_integrationapi_security_ssrf_valid_public_urls_accepted(tenant_a):
    """Legitimate external public URLs are accepted without errors."""
    valid_urls = [
        "https://api.stripe.com/v1",
        "https://hooks.slack.com/services/T00/B00/X00",
        "https://api.sendgrid.com/v3/mail/send",
        "https://webhook.site/#!/view/12345",
    ]
    for url in valid_urls:
        form = WebhookSubscriptionForm(
            data=_integrationapi_valid_webhook_post_data(target_url=url),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"Expected valid URL '{url}' to pass. Errors: {form.errors}"


# ==============================================================================
# 5. Mass Assignment & State Security Tests
# ==============================================================================

def test_integrationapi_security_mass_assignment_connector_invariants_protected(client_a, tenant_a, tenant_b):
    """Attempted mass assignment of tenant, number, health_status on connector is ignored."""
    payload = _integrationapi_valid_connector_post_data(
        name="Security Invariant Connector",
        tenant=tenant_b.pk,
        number="ECON-MALICIOUS-9999",
        health_status="compromised",
    )
    resp = client_a.post(reverse("ecommerce:ecommerceconnector_create"), payload)
    assert resp.status_code == 302

    created = EcommerceConnector.objects.get(name="Security Invariant Connector")
    # Verify invariants
    assert created.tenant == tenant_a
    assert created.number.startswith("ECON-")
    assert created.number != "ECON-MALICIOUS-9999"
    assert created.health_status == "healthy"  # Not overridden to "compromised"


def test_integrationapi_security_mass_assignment_sync_job_invariants_protected(client_a, tenant_a, tenant_b, ecom_connector_a):
    """Attempted mass assignment of tenant, number, status on sync job is ignored."""
    payload = _integrationapi_valid_sync_job_post_data(
        ecom_connector_a,
        tenant=tenant_b.pk,
        number="ESYJ-MALICIOUS-9999",
        status="failed",
    )
    resp = client_a.post(reverse("ecommerce:integrationsyncjob_create"), payload)
    assert resp.status_code == 302

    created = IntegrationSyncJob.objects.filter(connector=ecom_connector_a).order_by("-created_at").first()
    assert created.tenant == tenant_a
    assert created.number.startswith("ESYJ-")
    assert created.number != "ESYJ-MALICIOUS-9999"
    assert created.status == "completed"  # Not overridden to "failed"


def test_integrationapi_security_mass_assignment_sync_job_foreign_connector_rejected(client_a, tenant_a, ecom_connector_b):
    """Attempting to inject a foreign tenant's connector into a sync job is rejected by reject_foreign."""
    payload = _integrationapi_valid_sync_job_post_data(ecom_connector_b)
    resp = client_a.post(reverse("ecommerce:integrationsyncjob_create"), payload)
    assert resp.status_code == 200
    assert "connector" in resp.context["form"].errors


def test_integrationapi_security_mass_assignment_webhook_invariants_protected(client_a, tenant_a, tenant_b):
    """Attempted mass assignment of tenant, number, consecutive_failures, total_delivered_count is ignored."""
    payload = _integrationapi_valid_webhook_post_data(
        name="Security Invariant Webhook",
        tenant=tenant_b.pk,
        number="EWBS-MALICIOUS-9999",
        consecutive_failures=999,
        total_delivered_count=9999,
        last_status_code=500,
    )
    resp = client_a.post(reverse("ecommerce:webhooksubscription_create"), payload)
    assert resp.status_code == 302

    created = WebhookSubscription.objects.get(name="Security Invariant Webhook")
    assert created.tenant == tenant_a
    assert created.number.startswith("EWBS-")
    assert created.number != "EWBS-MALICIOUS-9999"
    assert created.consecutive_failures == 0
    assert created.total_delivered_count == 0


def test_integrationapi_security_mass_assignment_credential_invariants_protected(client_a, tenant_a, tenant_b, admin_b):
    """Attempted mass assignment of tenant, number, client_secret_hash, client_id, created_by is ignored."""
    malicious_hash = hashlib.sha256(b"malicious_hash").hexdigest()
    payload = _integrationapi_valid_credential_post_data(
        name="Security Invariant Credential",
        tenant=tenant_b.pk,
        number="EAPC-MALICIOUS-9999",
        client_id="nep_hacked_id",
        client_secret_hash=malicious_hash,
        created_by=admin_b.pk,
        total_requests_count=500000,
    )
    resp = client_a.post(reverse("ecommerce:apicredential_create"), payload)
    assert resp.status_code == 302

    created = ApiCredential.objects.get(name="Security Invariant Credential")
    assert created.tenant == tenant_a
    assert created.number.startswith("EAPC-")
    assert created.number != "EAPC-MALICIOUS-9999"
    assert created.client_id.startswith("nep_")
    assert created.client_id != "nep_hacked_id"
    assert created.client_secret_hash != malicious_hash
    assert created.total_requests_count == 0


def test_integrationapi_security_state_credential_unrevoke_blocked(client_a, tenant_a, ecom_credential_a):
    """Attempting to un-revoke a revoked ApiCredential via edit form is rejected."""
    # Revoke the credential first
    ecom_credential_a.status = "revoked"
    ecom_credential_a.revoked_at = timezone.now()
    ecom_credential_a.save(update_fields=["status", "revoked_at"])

    # Attempt to reactivate via edit form
    edit_payload = _integrationapi_valid_credential_post_data(
        name=ecom_credential_a.name,
        status="active",
    )
    resp = client_a.post(reverse("ecommerce:apicredential_edit", args=[ecom_credential_a.pk]), edit_payload)
    assert resp.status_code == 200
    assert "status" in resp.context["form"].errors
    error_msg = " ".join(resp.context["form"].errors["status"])
    assert "Revoked API credentials cannot be reactivated" in error_msg

    ecom_credential_a.refresh_from_db()
    assert ecom_credential_a.status == "revoked"


def test_integrationapi_security_state_credential_tier_elevation_blocked(client_a, tenant_a, admin_user):
    """Attempting to elevate ApiCredential tier on edit is ignored; initial tier is preserved."""
    cred = ApiCredential.objects.create(
        tenant=tenant_a,
        name="Storefront Public Credential",
        tier="storefront_public",
        status="active",
        client_id="nep_pub_test_sec_tier",
        client_secret_hash=hashlib.sha256(b"sec_hash").hexdigest(),
        secret_prefix="nep_sec_test...",
        created_by=admin_user,
    )

    # Attempt to elevate to admin_server via edit POST
    edit_payload = _integrationapi_valid_credential_post_data(
        name="Elevated Privilege Request",
        tier="admin_server",
        status="active",
    )
    resp = client_a.post(reverse("ecommerce:apicredential_edit", args=[cred.pk]), edit_payload)
    assert resp.status_code == 302

    cred.refresh_from_db()
    assert cred.name == "Elevated Privilege Request"
    assert cred.tier == "storefront_public"  # Preserved, not elevated


# ==============================================================================
# 6. Secret Exposure Prevention Tests
# ==============================================================================

def test_integrationapi_security_secret_widgets_render_value_false():
    """Form widgets for sensitive secret fields enforce PasswordInput with render_value=False."""
    # 1. EcommerceConnectorForm
    connector_form = EcommerceConnectorForm()
    secret_widget = connector_form.fields["api_secret"].widget
    assert isinstance(secret_widget, forms.PasswordInput)
    assert secret_widget.render_value is False

    # 2. WebhookSubscriptionForm
    webhook_form = WebhookSubscriptionForm()
    wh_secret_widget = webhook_form.fields["secret_key"].widget
    assert isinstance(wh_secret_widget, forms.PasswordInput)
    assert wh_secret_widget.render_value is False


def test_integrationapi_security_secret_not_rendered_in_edit_html(client_a, ecom_connector_a, ecom_webhook_a):
    """Edit forms never expose secret keys in HTML markup."""
    # 1. Connector edit form
    ecom_connector_a.api_secret = "super_confidential_secret_value_xyz"
    ecom_connector_a.save(update_fields=["api_secret"])

    resp_conn = client_a.get(reverse("ecommerce:ecommerceconnector_edit", args=[ecom_connector_a.pk]))
    assert resp_conn.status_code == 200
    html_conn = resp_conn.content.decode("utf-8")
    assert "super_confidential_secret_value_xyz" not in html_conn

    # 2. Webhook edit form
    ecom_webhook_a.secret_key = "super_confidential_webhook_hmac_key_999"
    ecom_webhook_a.save(update_fields=["secret_key"])

    resp_wh = client_a.get(reverse("ecommerce:webhooksubscription_edit", args=[ecom_webhook_a.pk]))
    assert resp_wh.status_code == 200
    html_wh = resp_wh.content.decode("utf-8")
    assert "super_confidential_webhook_hmac_key_999" not in html_wh


def test_integrationapi_security_credential_raw_secret_never_stored_in_db(client_a, tenant_a):
    """ApiCredential raw secret is never stored in DB plaintext; only SHA-256 hash exists."""
    payload = _integrationapi_valid_credential_post_data(name="Secret Storage Test Key")
    resp = client_a.post(reverse("ecommerce:apicredential_create"), payload)
    assert resp.status_code == 302

    created = ApiCredential.objects.get(name="Secret Storage Test Key")
    # client_secret_hash must be a 64-char hex SHA-256 digest
    assert len(created.client_secret_hash) == 64
    int(created.client_secret_hash, 16)  # Verifies hex format

    # Ensure model has no plaintext secret field
    model_field_names = [f.name for f in ApiCredential._meta.get_fields()]
    assert "raw_secret" not in model_field_names
    assert "client_secret" not in model_field_names
    assert not hasattr(created, "raw_secret")


def test_integrationapi_security_credential_session_secret_single_use(client_a, tenant_a):
    """Raw secret is set in session on create, popped on first detail GET, and absent thereafter."""
    payload = _integrationapi_valid_credential_post_data(name="Single Use Flash Secret")
    resp_create = client_a.post(reverse("ecommerce:apicredential_create"), payload, follow=False)
    assert resp_create.status_code == 302

    created = ApiCredential.objects.get(name="Single Use Flash Secret")
    detail_url = reverse("ecommerce:apicredential_detail", args=[created.pk])

    # First detail GET: raw secret flashed in context and displayed
    resp_first = client_a.get(detail_url)
    assert resp_first.status_code == 200
    first_secret = resp_first.context.get("new_raw_secret")
    assert first_secret is not None
    assert first_secret.startswith("nep_sec_")
    assert first_secret in resp_first.content.decode("utf-8")

    # Second detail GET: session was popped; raw secret is None and absent from HTML
    resp_second = client_a.get(detail_url)
    assert resp_second.status_code == 200
    second_secret = resp_second.context.get("new_raw_secret")
    assert second_secret is None
    assert first_secret not in resp_second.content.decode("utf-8")


# ==============================================================================
# 7. HTTP Method Safety Tests (Require POST)
# ==============================================================================

def test_integrationapi_security_destructive_actions_require_post(
    client_a,
    ecom_connector_a,
    ecom_sync_job_a,
    ecom_webhook_a,
    ecom_credential_a,
):
    """Mutating and destructive action endpoints reject GET requests with 405 Method Not Allowed."""
    endpoints = [
        reverse("ecommerce:ecommerceconnector_delete", args=[ecom_connector_a.pk]),
        reverse("ecommerce:ecommerceconnector_test_connection", args=[ecom_connector_a.pk]),
        reverse("ecommerce:integrationsyncjob_delete", args=[ecom_sync_job_a.pk]),
        reverse("ecommerce:integrationsyncjob_retry", args=[ecom_sync_job_a.pk]),
        reverse("ecommerce:webhooksubscription_delete", args=[ecom_webhook_a.pk]),
        reverse("ecommerce:webhooksubscription_ping", args=[ecom_webhook_a.pk]),
        reverse("ecommerce:apicredential_delete", args=[ecom_credential_a.pk]),
        reverse("ecommerce:apicredential_revoke", args=[ecom_credential_a.pk]),
    ]
    for url in endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}"


# ==============================================================================
# 8. Webhook Custom Headers Security Tests (CRLF & Hop-by-Hop)
# ==============================================================================

def test_integrationapi_security_webhook_custom_headers_crlf_and_hop_by_hop(tenant_a):
    """WebhookSubscriptionForm rejects CRLF injection and restricted hop-by-hop headers."""
    # 1. CRLF injection attempt in header value
    crlf_data = _integrationapi_valid_webhook_post_data(
        custom_headers='{"X-Injected": "Value\\r\\nSet-Cookie: session=hacked"}'
    )
    form_crlf = WebhookSubscriptionForm(data=crlf_data, tenant=tenant_a)
    assert not form_crlf.is_valid()
    assert "custom_headers" in form_crlf.errors
    assert "CRLF" in " ".join(form_crlf.errors["custom_headers"])

    # 2. Hop-by-hop header override attempt (Host)
    host_data = _integrationapi_valid_webhook_post_data(
        custom_headers='{"Host": "internal.spoofed.com"}'
    )
    form_host = WebhookSubscriptionForm(data=host_data, tenant=tenant_a)
    assert not form_host.is_valid()
    assert "custom_headers" in form_host.errors
    assert "Hop-by-hop" in " ".join(form_host.errors["custom_headers"])

    # 3. Hop-by-hop header override attempt (Transfer-Encoding)
    te_data = _integrationapi_valid_webhook_post_data(
        custom_headers='{"Transfer-Encoding": "chunked"}'
    )
    form_te = WebhookSubscriptionForm(data=te_data, tenant=tenant_a)
    assert not form_te.is_valid()
    assert "custom_headers" in form_te.errors
    assert "Hop-by-hop" in " ".join(form_te.errors["custom_headers"])

    # 4. Non-JSON / Non-dictionary payload
    bad_json = _integrationapi_valid_webhook_post_data(
        custom_headers="This is not JSON"
    )
    form_bad = WebhookSubscriptionForm(data=bad_json, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "custom_headers" in form_bad.errors
