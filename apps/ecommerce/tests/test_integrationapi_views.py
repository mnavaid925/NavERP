"""Unit, route, context-contract, filter, and action tests for Module 9.19 Integration & API Ecosystem views.

Covers:
- Integration Hub (`ecommerce:integration_api_hub`):
  - Authenticated GET 200, stats dictionary metrics, recent collections, rendered page content.
  - Unauthenticated redirect 302 to login.
- EcommerceConnector:
  - List (`ecommerce:ecommerceconnector_list`): GET 200, filters (?category=, ?status=, ?provider=), search (?q=), pagination.
  - Create (`ecommerce:ecommerceconnector_create`): GET 200, POST valid (redirects 302 to detail, audit logged), POST invalid (200 with errors).
  - Detail (`ecommerce:ecommerceconnector_detail`): GET 200, displays ECON- number, context contract, recent sync jobs.
  - Edit (`ecommerce:ecommerceconnector_edit`): GET 200, POST valid (redirects 302 to detail, updates DB, audit logged).
  - Delete (`ecommerce:ecommerceconnector_delete`): POST 302 (deletes record, audit logged), GET 405 Method Not Allowed.
  - Test connection action (`ecommerce:ecommerceconnector_test_connection`): POST 302 (updates health_status, audit logged), GET 405.
- IntegrationSyncJob:
  - List (`ecommerce:integrationsyncjob_list`): GET 200, filters (?status=, ?entity=, ?direction=, ?trigger=, ?connector=), search (?q=), pagination.
  - Create (`ecommerce:integrationsyncjob_create`): GET 200 (with initial connector), POST valid (redirects 302 to detail, simulation execution, audit logged), POST invalid (200 with errors).
  - Detail (`ecommerce:integrationsyncjob_detail`): GET 200, displays ESYJ- number, child retries.
  - Edit (`ecommerce:integrationsyncjob_edit`): GET 200, POST valid (redirects 302 to detail, updates DB, audit logged).
  - Delete (`ecommerce:integrationsyncjob_delete`): POST 302 (deletes record, audit logged), GET 405.
  - Retry action (`ecommerce:integrationsyncjob_retry`): POST 302 (generates child retry job, increments retry_count, audit logged), GET 405.
- WebhookSubscription:
  - List (`ecommerce:webhooksubscription_list`): GET 200, filters (?topic=, ?status=), search (?q=), pagination.
  - Create (`ecommerce:webhooksubscription_create`): GET 200, POST valid (redirects 302 to detail, audit logged), POST invalid SSRF (200 with errors).
  - Detail (`ecommerce:webhooksubscription_detail`): GET 200, displays EWBS- number, context contract.
  - Edit (`ecommerce:webhooksubscription_edit`): GET 200, POST valid (redirects 302 to detail, updates DB, audit logged).
  - Delete (`ecommerce:webhooksubscription_delete`): POST 302 (deletes record, audit logged), GET 405.
  - Ping action (`ecommerce:webhooksubscription_ping`): POST 302 (resets circuit breaker, increments metrics, audit logged), GET 405.
- ApiCredential:
  - List (`ecommerce:apicredential_list`): GET 200, filters (?tier=, ?status=), search (?q=), pagination.
  - Create (`ecommerce:apicredential_create`): GET 200, POST valid (redirects 302 to detail, puts raw secret in session, audit logged), POST invalid (200 with errors).
  - Detail (`ecommerce:apicredential_detail`): GET 200, displays EAPC- number, displays scopes, one-time raw secret flashed & popped from session.
  - Edit (`ecommerce:apicredential_edit`): GET 200, POST valid (redirects 302 to detail, updates DB, audit logged).
  - Delete (`ecommerce:apicredential_delete`): POST 302 (deletes record, audit logged), GET 405.
  - Revoke action (`ecommerce:apicredential_revoke`): POST 302 (sets status='revoked', revoked_at set, audit logged), GET 405.
- Cross-tenant boundaries:
  - client_a accessing tenant_b's objects returns 404 for detail and actions.
"""
import json
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    EcommerceConnector,
    IntegrationSyncJob,
    WebhookSubscription,
    ApiCredential,
)
from apps.ecommerce.tests.conftest import (
    _integrationapi_connector,
    _integrationapi_sync_job,
    _integrationapi_webhook,
    _integrationapi_credential,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (Prefixed with _integrationapi_*)
# ==============================================================================

def _integrationapi_valid_connector_payload(**kwargs):
    """Return a valid POST payload for EcommerceConnector create/edit."""
    data = {
        "name": "Stripe Live Payments",
        "category": "payment",
        "provider": "stripe",
        "auth_type": "api_key",
        "status": "active",
        "base_url": "https://api.stripe.com/v1",
        "api_version": "v1",
        "api_key": "sk_live_valid_test_key_123",
        "api_secret": "sec_live_valid_secret_456",
        "account_id": "acct_live_789",
        "is_sandbox": False,
        "timeout_seconds": 30,
        "rate_limit_per_minute": 120,
        "description": "Production payment gateway connector.",
    }
    data.update(kwargs)
    return data


def _integrationapi_valid_sync_job_payload(connector, **kwargs):
    """Return a valid POST payload for IntegrationSyncJob create/edit."""
    connector_id = connector.pk if hasattr(connector, "pk") else connector
    data = {
        "connector": connector_id,
        "sync_entity": "order_to_cash",
        "direction": "outbound",
        "trigger_type": "manual",
        "batch_id": "batch-sync-2026-001",
        "max_retries": 4,
        "payload_preview": '{"scope": "hourly_orders"}',
        "error_summary": "",
    }
    data.update(kwargs)
    return data


def _integrationapi_valid_webhook_payload(**kwargs):
    """Return a valid POST payload for WebhookSubscription create/edit."""
    data = {
        "name": "Partner ERP Order Webhook",
        "target_url": "https://api.partner-system.com/webhooks/orders",
        "event_topic": "order.created",
        "status": "active",
        "secret_key": "whsec_custom_secret_key_12345",
        "payload_format": "json",
        "custom_headers": json.dumps({"X-Source": "NavERP-Integration"}),
        "max_consecutive_failures": 5,
        "is_verify_ssl": True,
        "description": "Dispatches order creation events to partner ERP.",
    }
    data.update(kwargs)
    return data


def _integrationapi_valid_credential_payload(**kwargs):
    """Return a valid POST payload for ApiCredential create/edit."""
    data = {
        "name": "Headless Mobile App Client",
        "tier": "storefront_public",
        "status": "active",
        "scopes": "read_catalog,write_orders",
        "allowed_origins": "https://m.apexoutdoors.com",
        "allowed_ips": "198.51.100.0/24",
        "rate_limit_rpm": 60,
        "description": "Public storefront API token for mobile shopping application.",
    }
    data.update(kwargs)
    return data


# ==============================================================================
# 1. Integration Hub View Tests
# ==============================================================================

def test_integrationapi_hub_view_authenticated(
    client_a,
    tenant_a,
    ecom_connector_a,
    ecom_sync_job_a,
    ecom_webhook_a,
    ecom_credential_a,
):
    """Test Hub cockpit returns 200 OK with aggregated KPI metrics and recent items."""
    url = reverse("ecommerce:integration_api_hub")
    response = client_a.get(url)
    assert response.status_code == 200

    # Context contract assertions
    assert "stats" in response.context
    stats = response.context["stats"]
    assert stats["total_connectors"] >= 1
    assert stats["active_connectors"] >= 1
    assert stats["total_jobs"] >= 1
    assert stats["total_webhooks"] >= 1
    assert stats["total_credentials"] >= 1
    assert "payment_connectors" in stats
    assert "running_jobs" in stats
    assert "failed_jobs" in stats
    assert "broken_webhooks" in stats

    assert "recent_jobs" in response.context
    assert "recent_connectors" in response.context
    assert "active_webhooks" in response.context
    assert "active_credentials" in response.context

    # Rendered content assertions
    content = response.content.decode("utf-8")
    assert "Integration &amp; API Ecosystem" in content or "Integration & API Ecosystem" in content
    assert "Connectors Configured" in content
    assert "Sync Jobs Run" in content
    assert "Webhook Subscriptions" in content


def test_integrationapi_hub_view_unauthenticated():
    """Test Hub requires authentication and redirects unauthenticated requests."""
    anonymous_client = Client()
    url = reverse("ecommerce:integration_api_hub")
    response = anonymous_client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url or "login" in response.url


# ==============================================================================
# 2. EcommerceConnector Views Tests
# ==============================================================================

def test_integrationapi_connector_list_view(client_a, ecom_connector_a):
    """Test EcommerceConnector list view returns 200 with scoped connectors and choices context."""
    url = reverse("ecommerce:ecommerceconnector_list")
    response = client_a.get(url)
    assert response.status_code == 200

    assert "connectors" in response.context
    assert "total_count" in response.context
    assert "active_count" in response.context
    assert "category_choices" in response.context
    assert "status_choices" in response.context
    assert "provider_choices" in response.context
    assert response.context["total_count"] >= 1
    assert ecom_connector_a in response.context["connectors"]


def test_integrationapi_connector_list_filters(client_a, tenant_a, ecom_connector_a):
    """Test EcommerceConnector list filtering by category, status, provider, and search query."""
    # Create distinct connector for tenant_a
    erp_conn = _integrationapi_connector(
        tenant_a,
        name="SAP S/4HANA ERP",
        category="erp",
        status="testing",
        provider="sap_s4hana",
    )

    url = reverse("ecommerce:ecommerceconnector_list")

    # Filter by category
    resp_pay = client_a.get(url, {"category": "payment"})
    assert resp_pay.status_code == 200
    connectors_pay = resp_pay.context["connectors"]
    assert ecom_connector_a in connectors_pay
    assert erp_conn not in connectors_pay

    resp_erp = client_a.get(url, {"category": "erp"})
    assert resp_erp.status_code == 200
    connectors_erp = resp_erp.context["connectors"]
    assert erp_conn in connectors_erp
    assert ecom_connector_a not in connectors_erp

    # Filter by status
    resp_active = client_a.get(url, {"status": "active"})
    assert resp_active.status_code == 200
    assert ecom_connector_a in resp_active.context["connectors"]
    assert erp_conn not in resp_active.context["connectors"]

    # Filter by provider
    resp_sap = client_a.get(url, {"provider": "sap_s4hana"})
    assert resp_sap.status_code == 200
    assert erp_conn in resp_sap.context["connectors"]

    # Search query
    resp_q = client_a.get(url, {"q": "SAP S/4HANA"})
    assert resp_q.status_code == 200
    assert erp_conn in resp_q.context["connectors"]
    assert ecom_connector_a not in resp_q.context["connectors"]


def test_integrationapi_connector_list_pagination(client_a, tenant_a):
    """Test EcommerceConnector list pagination with 16+ records."""
    for i in range(16):
        _integrationapi_connector(
            tenant_a,
            name=f"Paginated Connector {i:02d}",
            category="custom",
            provider="custom_rest",
        )

    url = reverse("ecommerce:ecommerceconnector_list")
    resp_p1 = client_a.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["connectors"]) == 15

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["connectors"]) >= 1


def test_integrationapi_connector_create_get(client_a):
    """Test EcommerceConnector create GET renders form with is_edit=False and initial category."""
    url = reverse("ecommerce:ecommerceconnector_create")
    response = client_a.get(url, {"category": "shipping"})
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["connector"] is None
    assert response.context["form"].initial.get("category") == "shipping"


def test_integrationapi_connector_create_post_valid(client_a, tenant_a, admin_user):
    """Test EcommerceConnector create POST creates instance, writes audit log, and redirects to detail."""
    url = reverse("ecommerce:ecommerceconnector_create")
    payload = _integrationapi_valid_connector_payload(
        name="FedEx Logistics Connector",
        category="shipping",
        provider="fedex",
        base_url="https://apis.fedex.com/track/v1",
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302

    created = EcommerceConnector.objects.get(tenant=tenant_a, name="FedEx Logistics Connector")
    assert response.url == reverse("ecommerce:ecommerceconnector_detail", kwargs={"pk": created.pk})
    assert created.category == "shipping"
    assert created.provider == "fedex"
    assert created.number.startswith("ECON-")

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_connector_create_post_invalid(client_a):
    """Test EcommerceConnector create POST with invalid data re-renders form with 200 and errors."""
    url = reverse("ecommerce:ecommerceconnector_create")
    # Empty payload missing required name and category
    response = client_a.post(url, data={})
    assert response.status_code == 200
    assert response.context["form"].is_valid() is False
    assert "name" in response.context["form"].errors


def test_integrationapi_connector_detail_view(client_a, ecom_connector_a, ecom_sync_job_a):
    """Test EcommerceConnector detail GET displays ECON- number, connector info, and recent sync jobs."""
    url = reverse("ecommerce:ecommerceconnector_detail", kwargs={"pk": ecom_connector_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["connector"] == ecom_connector_a
    assert ecom_sync_job_a in response.context["recent_jobs"]

    content = response.content.decode("utf-8")
    assert ecom_connector_a.number in content
    assert ecom_connector_a.number.startswith("ECON-")
    assert ecom_connector_a.name in content


def test_integrationapi_connector_edit_get(client_a, ecom_connector_a):
    """Test EcommerceConnector edit GET renders form with is_edit=True and populated instance."""
    url = reverse("ecommerce:ecommerceconnector_edit", kwargs={"pk": ecom_connector_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["connector"] == ecom_connector_a
    assert response.context["form"].instance == ecom_connector_a


def test_integrationapi_connector_edit_post_valid(client_a, tenant_a, ecom_connector_a):
    """Test EcommerceConnector edit POST updates instance, logs audit, and redirects to detail."""
    url = reverse("ecommerce:ecommerceconnector_edit", kwargs={"pk": ecom_connector_a.pk})
    payload = _integrationapi_valid_connector_payload(
        name="Acme Stripe Connector Renamed",
        status="maintenance",
        timeout_seconds=60,
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:ecommerceconnector_detail", kwargs={"pk": ecom_connector_a.pk})

    ecom_connector_a.refresh_from_db()
    assert ecom_connector_a.name == "Acme Stripe Connector Renamed"
    assert ecom_connector_a.status == "maintenance"
    assert ecom_connector_a.timeout_seconds == 60

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=ecom_connector_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_connector_delete_post(client_a, tenant_a):
    """Test EcommerceConnector delete POST removes instance, logs audit, and redirects to list."""
    conn = _integrationapi_connector(tenant_a, name="Disposable Connector")
    pk = conn.pk
    url = reverse("ecommerce:ecommerceconnector_delete", kwargs={"pk": pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:ecommerceconnector_list")

    assert not EcommerceConnector.objects.filter(pk=pk).exists()

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_connector_delete_get_not_allowed(client_a, ecom_connector_a):
    """Test EcommerceConnector delete rejects GET requests with 405 Method Not Allowed."""
    url = reverse("ecommerce:ecommerceconnector_delete", kwargs={"pk": ecom_connector_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


def test_integrationapi_connector_test_connection_action_post(client_a, tenant_a, ecom_connector_a):
    """Test test_connection action updates health_status, clears error, writes audit log, and redirects."""
    ecom_connector_a.health_status = "degraded"
    ecom_connector_a.last_error_message = "Previous connection timeout"
    ecom_connector_a.save()

    url = reverse("ecommerce:ecommerceconnector_test_connection", kwargs={"pk": ecom_connector_a.pk})
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:ecommerceconnector_detail", kwargs={"pk": ecom_connector_a.pk})

    ecom_connector_a.refresh_from_db()
    assert ecom_connector_a.health_status == "healthy"
    assert ecom_connector_a.last_error_message == ""
    assert ecom_connector_a.last_health_check_at is not None

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="test",
        object_id=ecom_connector_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_connector_test_connection_get_not_allowed(client_a, ecom_connector_a):
    """Test test_connection action rejects GET with 405."""
    url = reverse("ecommerce:ecommerceconnector_test_connection", kwargs={"pk": ecom_connector_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


# ==============================================================================
# 3. IntegrationSyncJob Views Tests
# ==============================================================================

def test_integrationapi_sync_job_list_view(client_a, ecom_sync_job_a, ecom_connector_a):
    """Test IntegrationSyncJob list view returns 200 with scoped jobs, counts, and choices context."""
    url = reverse("ecommerce:integrationsyncjob_list")
    response = client_a.get(url)
    assert response.status_code == 200

    assert "sync_jobs" in response.context
    assert "connectors" in response.context
    assert "total_count" in response.context
    assert "running_count" in response.context
    assert "failed_count" in response.context
    assert "completed_count" in response.context
    assert "status_choices" in response.context
    assert "entity_choices" in response.context
    assert "direction_choices" in response.context
    assert "trigger_choices" in response.context
    assert response.context["total_count"] >= 1
    assert ecom_sync_job_a in response.context["sync_jobs"]


def test_integrationapi_sync_job_list_filters(client_a, tenant_a, ecom_connector_a, admin_user):
    """Test IntegrationSyncJob list filtering by status, entity, direction, trigger, and connector."""
    job_failed = _integrationapi_sync_job(
        tenant_a,
        ecom_connector_a,
        status="failed",
        sync_entity="inventory_levels",
        direction="inbound",
        trigger_type="scheduled",
        batch_id="batch-failed-inv-99",
        triggered_by=admin_user,
    )

    url = reverse("ecommerce:integrationsyncjob_list")

    # Filter by status
    resp_failed = client_a.get(url, {"status": "failed"})
    assert resp_failed.status_code == 200
    assert job_failed in resp_failed.context["sync_jobs"]

    # Filter by sync_entity
    resp_inv = client_a.get(url, {"entity": "inventory_levels"})
    assert resp_inv.status_code == 200
    assert job_failed in resp_inv.context["sync_jobs"]

    # Filter by direction
    resp_in = client_a.get(url, {"direction": "inbound"})
    assert resp_in.status_code == 200
    assert job_failed in resp_in.context["sync_jobs"]

    # Filter by trigger_type
    resp_sch = client_a.get(url, {"trigger": "scheduled"})
    assert resp_sch.status_code == 200
    assert job_failed in resp_sch.context["sync_jobs"]

    # Filter by connector
    resp_conn = client_a.get(url, {"connector": ecom_connector_a.pk})
    assert resp_conn.status_code == 200
    assert job_failed in resp_conn.context["sync_jobs"]

    # Search by batch_id
    resp_q = client_a.get(url, {"q": "batch-failed-inv-99"})
    assert resp_q.status_code == 200
    assert job_failed in resp_q.context["sync_jobs"]


def test_integrationapi_sync_job_list_pagination(client_a, tenant_a, ecom_connector_a, admin_user):
    """Test IntegrationSyncJob list pagination with 16+ records."""
    for i in range(16):
        _integrationapi_sync_job(
            tenant_a,
            ecom_connector_a,
            sync_entity="catalog_products",
            batch_id=f"page-batch-{i:02d}",
            triggered_by=admin_user,
        )

    url = reverse("ecommerce:integrationsyncjob_list")
    resp_p1 = client_a.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["sync_jobs"]) == 15

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["sync_jobs"]) >= 1


def test_integrationapi_sync_job_create_get(client_a, ecom_connector_a):
    """Test IntegrationSyncJob create GET renders form with is_edit=False and connector query prefill."""
    url = reverse("ecommerce:integrationsyncjob_create")
    response = client_a.get(url, {"connector": ecom_connector_a.pk})
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["sync_job"] is None
    assert str(response.context["form"].initial.get("connector")) == str(ecom_connector_a.pk)


def test_integrationapi_sync_job_create_post_valid(client_a, tenant_a, ecom_connector_a, admin_user):
    """Test IntegrationSyncJob create POST auto-executes simulation, sets status='completed', writes audit log."""
    url = reverse("ecommerce:integrationsyncjob_create")
    payload = _integrationapi_valid_sync_job_payload(
        ecom_connector_a,
        sync_entity="order_to_cash",
        direction="outbound",
        batch_id="batch-manual-run-101",
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302

    created = IntegrationSyncJob.objects.get(tenant=tenant_a, batch_id="batch-manual-run-101")
    assert response.url == reverse("ecommerce:integrationsyncjob_detail", kwargs={"pk": created.pk})
    assert created.status == "completed"
    assert created.records_processed == 10
    assert created.records_succeeded == 10
    assert created.triggered_by == admin_user
    assert created.number.startswith("ESYJ-")

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_sync_job_create_post_invalid(client_a):
    """Test IntegrationSyncJob create POST with missing connector re-renders form with 200 and errors."""
    url = reverse("ecommerce:integrationsyncjob_create")
    response = client_a.post(url, data={})
    assert response.status_code == 200
    assert response.context["form"].is_valid() is False
    assert "connector" in response.context["form"].errors


def test_integrationapi_sync_job_detail_view(client_a, ecom_sync_job_a):
    """Test IntegrationSyncJob detail GET displays ESYJ- number and child retries."""
    url = reverse("ecommerce:integrationsyncjob_detail", kwargs={"pk": ecom_sync_job_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["sync_job"] == ecom_sync_job_a
    assert "child_retries" in response.context

    content = response.content.decode("utf-8")
    assert ecom_sync_job_a.number in content
    assert ecom_sync_job_a.number.startswith("ESYJ-")


def test_integrationapi_sync_job_edit_get(client_a, ecom_sync_job_a):
    """Test IntegrationSyncJob edit GET renders form with is_edit=True and populated instance."""
    url = reverse("ecommerce:integrationsyncjob_edit", kwargs={"pk": ecom_sync_job_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["sync_job"] == ecom_sync_job_a


def test_integrationapi_sync_job_edit_post_valid(client_a, tenant_a, ecom_sync_job_a, ecom_connector_a):
    """Test IntegrationSyncJob edit POST updates instance, logs audit, and redirects to detail."""
    url = reverse("ecommerce:integrationsyncjob_edit", kwargs={"pk": ecom_sync_job_a.pk})
    payload = _integrationapi_valid_sync_job_payload(
        ecom_connector_a,
        sync_entity="order_to_cash",
        error_summary="Updated error note during review.",
        max_retries=10,
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:integrationsyncjob_detail", kwargs={"pk": ecom_sync_job_a.pk})

    ecom_sync_job_a.refresh_from_db()
    assert ecom_sync_job_a.error_summary == "Updated error note during review."
    assert ecom_sync_job_a.max_retries == 10

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=ecom_sync_job_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_sync_job_delete_post(client_a, tenant_a, ecom_connector_a, admin_user):
    """Test IntegrationSyncJob delete POST removes instance, logs audit, and redirects to list."""
    job = _integrationapi_sync_job(tenant_a, ecom_connector_a, triggered_by=admin_user)
    pk = job.pk
    url = reverse("ecommerce:integrationsyncjob_delete", kwargs={"pk": pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:integrationsyncjob_list")

    assert not IntegrationSyncJob.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_sync_job_delete_get_not_allowed(client_a, ecom_sync_job_a):
    """Test IntegrationSyncJob delete rejects GET with 405."""
    url = reverse("ecommerce:integrationsyncjob_delete", kwargs={"pk": ecom_sync_job_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


def test_integrationapi_sync_job_retry_action_post(client_a, tenant_a, ecom_sync_job_a, admin_user):
    """Test retry action generates child retry job with parent reference, increments retry count, and logs audit."""
    ecom_sync_job_a.batch_id = "initial-sync-001"
    ecom_sync_job_a.retry_count = 0
    ecom_sync_job_a.records_total = 12
    ecom_sync_job_a.save()

    url = reverse("ecommerce:integrationsyncjob_retry", kwargs={"pk": ecom_sync_job_a.pk})
    response = client_a.post(url)
    assert response.status_code == 302

    # Find created retry job
    retry_job = IntegrationSyncJob.objects.filter(parent_job=ecom_sync_job_a).first()
    assert retry_job is not None
    assert response.url == reverse("ecommerce:integrationsyncjob_detail", kwargs={"pk": retry_job.pk})

    assert retry_job.retry_count == 1
    assert retry_job.batch_id == "retry-initial-sync-001"
    assert retry_job.status == "completed"
    assert retry_job.records_total == 12
    assert retry_job.triggered_by == admin_user

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="retry_sync",
        object_id=retry_job.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_sync_job_retry_get_not_allowed(client_a, ecom_sync_job_a):
    """Test retry action rejects GET with 405."""
    url = reverse("ecommerce:integrationsyncjob_retry", kwargs={"pk": ecom_sync_job_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


# ==============================================================================
# 4. WebhookSubscription Views Tests
# ==============================================================================

def test_integrationapi_webhook_list_view(client_a, ecom_webhook_a):
    """Test WebhookSubscription list view returns 200 with scoped webhooks, counts, and choices."""
    url = reverse("ecommerce:webhooksubscription_list")
    response = client_a.get(url)
    assert response.status_code == 200

    assert "webhooks" in response.context
    assert "total_count" in response.context
    assert "active_count" in response.context
    assert "broken_count" in response.context
    assert "topic_choices" in response.context
    assert "status_choices" in response.context
    assert response.context["total_count"] >= 1
    assert ecom_webhook_a in response.context["webhooks"]


def test_integrationapi_webhook_list_filters(client_a, tenant_a, ecom_webhook_a):
    """Test WebhookSubscription list filtering by topic, status, and search query."""
    hook_refund = _integrationapi_webhook(
        tenant_a,
        name="Refund Dispatched Webhook",
        event_topic="order.refunded",
        status="circuit_broken",
        target_url="https://api.partner-system.com/webhooks/refunds",
    )

    url = reverse("ecommerce:webhooksubscription_list")

    # Filter by topic
    resp_refund = client_a.get(url, {"topic": "order.refunded"})
    assert resp_refund.status_code == 200
    assert hook_refund in resp_refund.context["webhooks"]
    assert ecom_webhook_a not in resp_refund.context["webhooks"]

    # Filter by status
    resp_broken = client_a.get(url, {"status": "circuit_broken"})
    assert resp_broken.status_code == 200
    assert hook_refund in resp_broken.context["webhooks"]
    assert ecom_webhook_a not in resp_broken.context["webhooks"]

    # Search by name
    resp_q = client_a.get(url, {"q": "Refund Dispatched"})
    assert resp_q.status_code == 200
    assert hook_refund in resp_q.context["webhooks"]


def test_integrationapi_webhook_list_pagination(client_a, tenant_a):
    """Test WebhookSubscription list pagination with 16+ records."""
    for i in range(16):
        _integrationapi_webhook(
            tenant_a,
            name=f"Paginated Webhook {i:02d}",
            target_url=f"https://api.example.com/webhook/test/{i}",
            event_topic="order.created",
        )

    url = reverse("ecommerce:webhooksubscription_list")
    resp_p1 = client_a.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["webhooks"]) == 15

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["webhooks"]) >= 1


def test_integrationapi_webhook_create_get(client_a):
    """Test WebhookSubscription create GET renders form with is_edit=False."""
    url = reverse("ecommerce:webhooksubscription_create")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["webhook"] is None


def test_integrationapi_webhook_create_post_valid(client_a, tenant_a):
    """Test WebhookSubscription create POST creates instance, logs audit, and redirects to detail."""
    url = reverse("ecommerce:webhooksubscription_create")
    payload = _integrationapi_valid_webhook_payload(
        name="Inventory Level Alert Webhook",
        event_topic="inventory.low_stock",
        target_url="https://api.external-wms.com/webhooks/inventory",
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302

    created = WebhookSubscription.objects.get(tenant=tenant_a, name="Inventory Level Alert Webhook")
    assert response.url == reverse("ecommerce:webhooksubscription_detail", kwargs={"pk": created.pk})
    assert created.event_topic == "inventory.low_stock"
    assert created.number.startswith("EWBS-")

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_webhook_create_post_invalid_ssrf(client_a):
    """Test WebhookSubscription create POST blocks SSRF targets with 200 form errors."""
    url = reverse("ecommerce:webhooksubscription_create")
    payload = _integrationapi_valid_webhook_payload(
        target_url="http://169.254.169.254/latest/meta-data",
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert response.context["form"].is_valid() is False
    assert "target_url" in response.context["form"].errors


def test_integrationapi_webhook_detail_view(client_a, ecom_webhook_a):
    """Test WebhookSubscription detail GET displays EWBS- number and event topic."""
    url = reverse("ecommerce:webhooksubscription_detail", kwargs={"pk": ecom_webhook_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["webhook"] == ecom_webhook_a

    content = response.content.decode("utf-8")
    assert ecom_webhook_a.number in content
    assert ecom_webhook_a.number.startswith("EWBS-")
    assert ecom_webhook_a.event_topic in content


def test_integrationapi_webhook_edit_get(client_a, ecom_webhook_a):
    """Test WebhookSubscription edit GET renders form with is_edit=True and populated instance."""
    url = reverse("ecommerce:webhooksubscription_edit", kwargs={"pk": ecom_webhook_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["webhook"] == ecom_webhook_a


def test_integrationapi_webhook_edit_post_valid(client_a, tenant_a, ecom_webhook_a):
    """Test WebhookSubscription edit POST updates instance, logs audit, and redirects to detail."""
    url = reverse("ecommerce:webhooksubscription_edit", kwargs={"pk": ecom_webhook_a.pk})
    payload = _integrationapi_valid_webhook_payload(
        name="Order Created Webhook Updated",
        status="paused",
        max_consecutive_failures=10,
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:webhooksubscription_detail", kwargs={"pk": ecom_webhook_a.pk})

    ecom_webhook_a.refresh_from_db()
    assert ecom_webhook_a.name == "Order Created Webhook Updated"
    assert ecom_webhook_a.status == "paused"
    assert ecom_webhook_a.max_consecutive_failures == 10

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=ecom_webhook_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_webhook_delete_post(client_a, tenant_a):
    """Test WebhookSubscription delete POST removes record, logs audit, and redirects to list."""
    hook = _integrationapi_webhook(tenant_a, name="Disposable Webhook")
    pk = hook.pk
    url = reverse("ecommerce:webhooksubscription_delete", kwargs={"pk": pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:webhooksubscription_list")

    assert not WebhookSubscription.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_webhook_delete_get_not_allowed(client_a, ecom_webhook_a):
    """Test WebhookSubscription delete rejects GET with 405."""
    url = reverse("ecommerce:webhooksubscription_delete", kwargs={"pk": ecom_webhook_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


def test_integrationapi_webhook_ping_action_post(client_a, tenant_a, ecom_webhook_a):
    """Test ping action resets circuit-breaker, resets failures count, increments deliveries, and logs audit."""
    ecom_webhook_a.status = "circuit_broken"
    ecom_webhook_a.consecutive_failures = 7
    ecom_webhook_a.total_delivered_count = 5
    ecom_webhook_a.save()

    url = reverse("ecommerce:webhooksubscription_ping", kwargs={"pk": ecom_webhook_a.pk})
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:webhooksubscription_detail", kwargs={"pk": ecom_webhook_a.pk})

    ecom_webhook_a.refresh_from_db()
    assert ecom_webhook_a.status == "active"
    assert ecom_webhook_a.consecutive_failures == 0
    assert ecom_webhook_a.last_status_code == 200
    assert ecom_webhook_a.total_delivered_count == 6
    assert ecom_webhook_a.last_delivery_at is not None

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="test_ping",
        object_id=ecom_webhook_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_webhook_ping_get_not_allowed(client_a, ecom_webhook_a):
    """Test ping action rejects GET with 405."""
    url = reverse("ecommerce:webhooksubscription_ping", kwargs={"pk": ecom_webhook_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


# ==============================================================================
# 5. ApiCredential Views Tests
# ==============================================================================

def test_integrationapi_credential_list_view(client_a, ecom_credential_a):
    """Test ApiCredential list view returns 200 with scoped credentials, counts, and choices."""
    url = reverse("ecommerce:apicredential_list")
    response = client_a.get(url)
    assert response.status_code == 200

    assert "credentials" in response.context
    assert "total_count" in response.context
    assert "active_count" in response.context
    assert "revoked_count" in response.context
    assert "tier_choices" in response.context
    assert "status_choices" in response.context
    assert response.context["total_count"] >= 1
    assert ecom_credential_a in response.context["credentials"]


def test_integrationapi_credential_list_filters(client_a, tenant_a, admin_user, ecom_credential_a):
    """Test ApiCredential list filtering by tier, status, and search query."""
    cred_erp = _integrationapi_credential(
        tenant_a,
        admin_user,
        name="NetSuite ERP Sync Token",
        tier="admin_server",
        status="revoked",
        client_id="nep_live_netsuite_sync_999",
    )

    url = reverse("ecommerce:apicredential_list")

    # Filter by tier
    resp_erp = client_a.get(url, {"tier": "admin_server"})
    assert resp_erp.status_code == 200
    assert cred_erp in resp_erp.context["credentials"]
    assert ecom_credential_a not in resp_erp.context["credentials"]

    # Filter by status
    resp_revoked = client_a.get(url, {"status": "revoked"})
    assert resp_revoked.status_code == 200
    assert cred_erp in resp_revoked.context["credentials"]
    assert ecom_credential_a not in resp_revoked.context["credentials"]

    # Search query
    resp_q = client_a.get(url, {"q": "NetSuite"})
    assert resp_q.status_code == 200
    assert cred_erp in resp_q.context["credentials"]


def test_integrationapi_credential_list_pagination(client_a, tenant_a, admin_user):
    """Test ApiCredential list pagination with 16+ records."""
    for i in range(16):
        _integrationapi_credential(
            tenant_a,
            admin_user,
            name=f"Paginated Credential {i:02d}",
            client_id=f"nep_pub_paginated_{i:02d}_{tenant_a.pk}",
        )

    url = reverse("ecommerce:apicredential_list")
    resp_p1 = client_a.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert resp_p1.context["is_paginated"] is True
    assert len(resp_p1.context["credentials"]) == 15

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["credentials"]) >= 1


def test_integrationapi_credential_create_get(client_a):
    """Test ApiCredential create GET renders form with is_edit=False."""
    url = reverse("ecommerce:apicredential_create")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["credential"] is None


def test_integrationapi_credential_create_post_valid(client_a, tenant_a, admin_user):
    """Test ApiCredential create POST provisions client_id, stores raw secret in session, and writes audit log."""
    url = reverse("ecommerce:apicredential_create")
    payload = _integrationapi_valid_credential_payload(
        name="WMS Warehouse Gateway Token",
        tier="admin_server",
        scopes="read_catalog,read_orders,write_orders",
        rate_limit_rpm=180,
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302

    created = ApiCredential.objects.get(tenant=tenant_a, name="WMS Warehouse Gateway Token")
    assert response.url == reverse("ecommerce:apicredential_detail", kwargs={"pk": created.pk})
    assert created.client_id.startswith("nep_live_")
    assert created.secret_prefix.startswith("nep_sec_")
    assert created.created_by == admin_user
    assert created.number.startswith("EAPC-")

    # One-time raw secret was placed in session
    session_key = f"new_secret_{created.pk}"
    assert session_key in client_a.session
    assert client_a.session[session_key].startswith("nep_sec_")

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_credential_create_post_invalid(client_a):
    """Test ApiCredential create POST with invalid rate limit returns 200 with errors."""
    url = reverse("ecommerce:apicredential_create")
    payload = _integrationapi_valid_credential_payload(rate_limit_rpm=0)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert response.context["form"].is_valid() is False
    assert "rate_limit_rpm" in response.context["form"].errors


def test_integrationapi_credential_detail_view(client_a, ecom_credential_a):
    """Test ApiCredential detail GET displays EAPC- number and granted scopes."""
    url = reverse("ecommerce:apicredential_detail", kwargs={"pk": ecom_credential_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert response.context["credential"] == ecom_credential_a

    content = response.content.decode("utf-8")
    assert ecom_credential_a.number in content
    assert ecom_credential_a.number.startswith("EAPC-")
    assert "read_catalog" in content
    assert "write_orders" in content


def test_integrationapi_credential_detail_one_time_raw_secret_in_session(client_a, ecom_credential_a):
    """Test detail view renders the raw secret once from session and pops it on subsequent visits."""
    secret_val = "nep_sec_test_one_time_raw_value_987654321"
    session = client_a.session
    session[f"new_secret_{ecom_credential_a.pk}"] = secret_val
    session.save()

    url = reverse("ecommerce:apicredential_detail", kwargs={"pk": ecom_credential_a.pk})

    # 1. First GET: Raw secret displayed in alert card
    resp1 = client_a.get(url)
    assert resp1.status_code == 200
    assert resp1.context["new_raw_secret"] == secret_val
    content1 = resp1.content.decode("utf-8")
    assert secret_val in content1
    assert "Save Your API Secret Key Now" in content1

    # 2. Second GET: Raw secret has been popped from session and is no longer displayed
    resp2 = client_a.get(url)
    assert resp2.status_code == 200
    assert resp2.context["new_raw_secret"] is None
    content2 = resp2.content.decode("utf-8")
    assert secret_val not in content2
    assert "Save Your API Secret Key Now" not in content2


def test_integrationapi_credential_edit_get(client_a, ecom_credential_a):
    """Test ApiCredential edit GET renders form with is_edit=True and populated instance."""
    url = reverse("ecommerce:apicredential_edit", kwargs={"pk": ecom_credential_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["credential"] == ecom_credential_a


def test_integrationapi_credential_edit_post_valid(client_a, tenant_a, ecom_credential_a):
    """Test ApiCredential edit POST updates instance, logs audit, and redirects to detail."""
    url = reverse("ecommerce:apicredential_edit", kwargs={"pk": ecom_credential_a.pk})
    payload = _integrationapi_valid_credential_payload(
        name="Renamed Mobile SDK Client",
        scopes="read_catalog",
        rate_limit_rpm=90,
    )
    response = client_a.post(url, data=payload)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:apicredential_detail", kwargs={"pk": ecom_credential_a.pk})

    ecom_credential_a.refresh_from_db()
    assert ecom_credential_a.name == "Renamed Mobile SDK Client"
    assert ecom_credential_a.scopes == "read_catalog"
    assert ecom_credential_a.rate_limit_rpm == 90

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=ecom_credential_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_credential_delete_post(client_a, tenant_a, admin_user):
    """Test ApiCredential delete POST removes record, logs audit, and redirects to list."""
    cred = _integrationapi_credential(tenant_a, admin_user, name="Disposable Credential")
    pk = cred.pk
    url = reverse("ecommerce:apicredential_delete", kwargs={"pk": pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:apicredential_list")

    assert not ApiCredential.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_credential_delete_get_not_allowed(client_a, ecom_credential_a):
    """Test ApiCredential delete rejects GET with 405."""
    url = reverse("ecommerce:apicredential_delete", kwargs={"pk": ecom_credential_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


def test_integrationapi_credential_revoke_action_post(client_a, tenant_a, ecom_credential_a):
    """Test ApiCredential revoke action sets status='revoked', sets revoked_at, logs audit, and redirects."""
    assert ecom_credential_a.status == "active"
    assert ecom_credential_a.revoked_at is None

    url = reverse("ecommerce:apicredential_revoke", kwargs={"pk": ecom_credential_a.pk})
    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("ecommerce:apicredential_detail", kwargs={"pk": ecom_credential_a.pk})

    ecom_credential_a.refresh_from_db()
    assert ecom_credential_a.status == "revoked"
    assert ecom_credential_a.revoked_at is not None

    # Audit log check
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="revoke",
        object_id=ecom_credential_a.pk,
    ).exists()
    assert audit_exists is True


def test_integrationapi_credential_revoke_get_not_allowed(client_a, ecom_credential_a):
    """Test ApiCredential revoke action rejects GET with 405."""
    url = reverse("ecommerce:apicredential_revoke", kwargs={"pk": ecom_credential_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


# ==============================================================================
# 6. Cross-Tenant IDOR View Isolation Tests
# ==============================================================================

def test_integrationapi_cross_tenant_isolation_detail_views(
    client_a,
    ecom_connector_b,
    ecom_sync_job_b,
    ecom_webhook_b,
    ecom_credential_b,
):
    """Test client_a cannot view tenant_b's entities via detail routes (returns 404)."""
    # Connector
    resp = client_a.get(reverse("ecommerce:ecommerceconnector_detail", kwargs={"pk": ecom_connector_b.pk}))
    assert resp.status_code == 404

    # Sync Job
    resp = client_a.get(reverse("ecommerce:integrationsyncjob_detail", kwargs={"pk": ecom_sync_job_b.pk}))
    assert resp.status_code == 404

    # Webhook
    resp = client_a.get(reverse("ecommerce:webhooksubscription_detail", kwargs={"pk": ecom_webhook_b.pk}))
    assert resp.status_code == 404

    # Credential
    resp = client_a.get(reverse("ecommerce:apicredential_detail", kwargs={"pk": ecom_credential_b.pk}))
    assert resp.status_code == 404


def test_integrationapi_cross_tenant_isolation_action_views(
    client_a,
    ecom_connector_b,
    ecom_sync_job_b,
    ecom_webhook_b,
    ecom_credential_b,
):
    """Test client_a cannot invoke action endpoints on tenant_b's entities (returns 404)."""
    # Connector test connection
    resp = client_a.post(reverse("ecommerce:ecommerceconnector_test_connection", kwargs={"pk": ecom_connector_b.pk}))
    assert resp.status_code == 404

    # Sync Job retry
    resp = client_a.post(reverse("ecommerce:integrationsyncjob_retry", kwargs={"pk": ecom_sync_job_b.pk}))
    assert resp.status_code == 404

    # Webhook ping
    resp = client_a.post(reverse("ecommerce:webhooksubscription_ping", kwargs={"pk": ecom_webhook_b.pk}))
    assert resp.status_code == 404

    # Credential revoke
    resp = client_a.post(reverse("ecommerce:apicredential_revoke", kwargs={"pk": ecom_credential_b.pk}))
    assert resp.status_code == 404
