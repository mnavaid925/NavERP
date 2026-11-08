"""View test suite for Sub-module 10.19: Integration & API Hub (apps/bi).

Views covered (24 view routes across 4 entities):
1. IntegrationConnector views:
   - integration_connector_list: 200, context variables contract pinned, metrics aggregation,
     search q=, choices filter dropdowns (connector_type, target_system, status), pagination (15/page)
   - integration_connector_detail: 200, context variables contract pinned, detail rendering
   - integration_connector_create: GET 200, POST 302 redirects to detail, tenant/created_by assigned, audit log
   - integration_connector_edit: GET 200, POST 302 redirects to detail, updates persisted, audit log
   - integration_connector_delete: GET 405 (require_POST), POST 302 redirects to list, object deleted, audit log
   - integration_connector_ping: GET 405 (require_POST), POST 302 redirects to detail, heartbeat timestamp,
     health_status='healthy', status='active', error_message cleared, total_messages_processed incremented, audit log

2. WarehouseSyncEndpoint views:
   - warehouse_sync_endpoint_list: 200, context variables contract pinned, metrics aggregation,
     search q=, choices filter dropdowns (target_warehouse, sync_mode, status), pagination (15/page)
   - warehouse_sync_endpoint_detail: 200, context variables contract pinned, detail rendering
   - warehouse_sync_endpoint_create: GET 200, POST 302 redirects to detail, tenant/owner assigned, audit log
   - warehouse_sync_endpoint_edit: GET 200, POST 302 redirects to detail, updates persisted, audit log
   - warehouse_sync_endpoint_delete: GET 405 (require_POST), POST 302 redirects to list, object deleted, audit log
   - warehouse_sync_endpoint_trigger: GET 405 (require_POST), POST 302 redirects to detail, status='success',
     last_sync_at timestamp, last_sync_duration_ms, last_rows_synced, total_rows_synced incremented, audit log

3. BiWebhookSubscription views:
   - bi_webhook_subscription_list: 200, context variables contract pinned, metrics aggregation,
     search q=, choices filter dropdowns (payload_format, status), pagination (15/page)
   - bi_webhook_subscription_detail: 200, context variables contract pinned, detail rendering
   - bi_webhook_subscription_create: GET 200, POST 302 redirects to detail, tenant/created_by assigned, audit log
   - bi_webhook_subscription_edit: GET 200, POST 302 redirects to detail, updates persisted, audit log
   - bi_webhook_subscription_delete: GET 405 (require_POST), POST 302 redirects to list, object deleted, audit log
   - bi_webhook_subscription_ping: GET 405 (require_POST), POST 302 redirects to detail, status='active',
     last_triggered_at timestamp, last_response_code=200, last_response_time_ms=145, consecutive_failures=0,
     total_deliveries incremented, audit log

4. BiExtensionPlugin views:
   - bi_extension_plugin_list: 200, context variables contract pinned, metrics aggregation,
     search q=, choices filter dropdowns (plugin_type, category, status), pagination (15/page)
   - bi_extension_plugin_detail: 200, context variables contract pinned, detail rendering
   - bi_extension_plugin_create: GET 200, POST 302 redirects to detail, tenant/installed_by assigned, audit log
   - bi_extension_plugin_edit: GET 200, POST 302 redirects to detail, updates persisted, audit log;
     system plugin protected (GET/POST 302 redirect with error message, modifications blocked)
   - bi_extension_plugin_delete: GET 405 (require_POST), POST 302 redirects to list, user plugin deleted, audit log;
     system plugin protected (POST 302 redirect with error message, deletion blocked)
   - bi_extension_plugin_toggle: GET 405 (require_POST), POST 302 redirects to detail, flips status between
     'enabled' and 'disabled', audit log

5. Cross-Cutting:
   - Cross-tenant IDOR protection: tenant_b client accessing tenant_a objects returns 404
   - Unauthenticated access: anonymous client requests redirect (302) to login URL
"""
import json
import os

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    BiExtensionPlugin,
    BiWebhookSubscription,
    DataMart,
    IntegrationConnector,
    SemanticModel,
    WarehouseSyncEndpoint,
)
from apps.core.models import AuditLog

User = get_user_model()


# ==============================================================================
# Module Helpers (strictly prefixed with _integrationhub_)
# ==============================================================================


def _integrationhub_create_connector(tenant, created_by=None, name=None, **kwargs):
    """Create a tenant-scoped IntegrationConnector for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "name": name or f"Test Connector {ts}",
        "slug": f"connector-{ts}",
        "description": "Enterprise broker integration for BI streaming.",
        "connector_type": "message_broker",
        "target_system": "kafka",
        "sync_direction": "outbound",
        "auth_type": "api_key",
        "message_format": "json",
        "sync_interval": "hourly",
        "status": "active",
        "health_status": "healthy",
        "is_enabled": True,
        "connection_config": {"bootstrap_servers": "localhost:9092"},
        "auth_credentials": {"api_key": "sec_test_123"},
        "created_by": created_by,
    }
    defaults.update(kwargs)
    return IntegrationConnector.objects.create(**defaults)


def _integrationhub_connector_form_data(**kwargs):
    """Return valid form data payload for IntegrationConnectorForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"Finance GL Pipeline {ts}",
        "slug": f"finance-gl-pipeline-{ts}",
        "description": "Reverse ETL pipeline syncing ledger summaries to cloud message broker.",
        "connector_type": "message_broker",
        "target_system": "kafka",
        "sync_direction": "outbound",
        "auth_type": "api_key",
        "message_format": "json",
        "sync_interval": "hourly",
        "status": "active",
        "is_enabled": True,
        "connection_config_raw": json.dumps(
            {"bootstrap_servers": "kafka.internal:9092", "topic": "erp.gl.events"}
        ),
        "auth_credentials_raw": json.dumps(
            {"api_key": "sec_live_abcdef123456"}
        ),
    }
    data.update(kwargs)
    return data


def _integrationhub_create_warehouse_sync(
    tenant, owner=None, name=None, semantic_model=None, data_mart=None, **kwargs
):
    """Create a tenant-scoped WarehouseSyncEndpoint for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "name": name or f"Test Sync Endpoint {ts}",
        "slug": f"sync-endpoint-{ts}",
        "target_warehouse": "snowflake",
        "sync_mode": "incremental_merge",
        "destination_database": "ANALYTICS_PROD",
        "destination_schema": "NAVERP_EXPORTS",
        "destination_table": "DIM_CUSTOMERS",
        "auth_method": "service_account_key",
        "sync_schedule": "daily",
        "status": "idle",
        "is_active": True,
        "connection_config": {"account": "xy12345.us-east-1"},
        "semantic_model": semantic_model,
        "data_mart": data_mart,
        "owner": owner,
    }
    defaults.update(kwargs)
    return WarehouseSyncEndpoint.objects.create(**defaults)


def _integrationhub_warehouse_sync_form_data(semantic_model=None, data_mart=None, **kwargs):
    """Return valid form data payload for WarehouseSyncEndpointForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"Snowflake Customer Metrics Sync {ts}",
        "slug": f"snowflake-sync-{ts}",
        "target_warehouse": "snowflake",
        "sync_mode": "incremental_merge",
        "destination_database": "ANALYTICS_PROD",
        "destination_schema": "NAVERP_EXPORTS",
        "destination_table": "DIM_CUSTOMERS",
        "auth_method": "service_account_key",
        "sync_schedule": "daily",
        "is_active": True,
        "connection_config_raw": json.dumps(
            {"account": "xy12345.us-east-1", "warehouse": "COMPUTE_WH"}
        ),
    }
    if semantic_model:
        data["semantic_model"] = str(semantic_model.pk)
    if data_mart:
        data["data_mart"] = str(data_mart.pk)
    data.update(kwargs)
    return data


def _integrationhub_create_webhook(tenant, created_by=None, name=None, **kwargs):
    """Create a tenant-scoped BiWebhookSubscription for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "name": name or f"Test Webhook {ts}",
        "endpoint_url": f"https://hooks.example.com/bi/{ts}",
        "payload_format": "standard_json",
        "event_types": ["kpi.threshold_breached", "anomaly.detected"],
        "custom_headers": {"Authorization": "Bearer ext_tok_123"},
        "max_retries": 3,
        "timeout_seconds": 10,
        "is_active": True,
        "status": "active",
        "created_by": created_by,
    }
    defaults.update(kwargs)
    return BiWebhookSubscription.objects.create(**defaults)


def _integrationhub_webhook_form_data(**kwargs):
    """Return valid form data payload for BiWebhookSubscriptionForm."""
    ts = int(timezone.now().timestamp() * 1000)
    base_url = getattr(settings, "SLACK_WEBHOOK_URL", "") or os.getenv(
        "SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/mock/dummy/test-webhook"
    )
    data = {
        "name": f"Slack Incident Webhook {ts}",
        "endpoint_url": f"{base_url}/{ts}",
        "payload_format": "slack_compatible",
        "max_retries": 4,
        "timeout_seconds": 15,
        "is_active": True,
        "event_types_raw": json.dumps(["kpi.threshold_breached", "anomaly.detected"]),
        "custom_headers_raw": json.dumps(
            {"Authorization": "Bearer ext_token_test"}
        ),
    }
    data.update(kwargs)
    return data


def _integrationhub_create_plugin(
    tenant, installed_by=None, name=None, is_system_plugin=False, **kwargs
):
    """Create a tenant-scoped BiExtensionPlugin for testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "name": name or f"Test Plugin {ts}",
        "plugin_identifier": f"io.naverp.plugin.{ts}",
        "version": "1.0.0",
        "plugin_type": "custom_visual",
        "category": "visualization",
        "description": "Custom visual extension plugin.",
        "author_name": "Test Author",
        "homepage_url": "https://example.com/plugin",
        "repository_url": "https://github.com/example/plugin",
        "license": "MIT",
        "status": "enabled",
        "is_system_plugin": is_system_plugin,
        "is_verified": True,
        "manifest_metadata": {"entrypoint_js": "/static/test.js"},
        "config_schema": {"type": "object"},
        "current_config": {"theme": "light"},
        "permissions_required": ["read_semantic_layer"],
        "installed_by": installed_by,
    }
    defaults.update(kwargs)
    return BiExtensionPlugin.objects.create(**defaults)


def _integrationhub_plugin_form_data(**kwargs):
    """Return valid form data payload for BiExtensionPluginForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"ECharts Sankey Visualizer {ts}",
        "plugin_identifier": f"io.naverp.visuals.sankey.{ts}",
        "version": "1.2.0",
        "plugin_type": "custom_visual",
        "category": "visualization",
        "description": "Interactive flow diagram visualization component.",
        "author_name": "NavERP Visuals Team",
        "homepage_url": "https://naverp.example.com/plugins/sankey",
        "repository_url": "https://github.com/naverp/echarts-sankey",
        "license": "Apache-2.0",
        "status": "installed",
        "manifest_metadata_raw": json.dumps(
            {"entrypoint_js": "/static/bi/plugins/sankey.js"}
        ),
        "config_schema_raw": json.dumps(
            {"type": "object", "properties": {"theme": {"type": "string"}}}
        ),
        "current_config_raw": json.dumps(
            {"theme": "dark"}
        ),
        "permissions_required_raw": json.dumps(
            ["read_semantic_layer", "render_canvas_ui"]
        ),
    }
    data.update(kwargs)
    return data


# ==============================================================================
# 1. IntegrationConnector View Tests (6 views)
# ==============================================================================


@pytest.mark.django_db
def test_integrationhub_views_connector_list_status_context_and_tenant_isolation(
    client_a, integration_connector_a, integration_connector_b
):
    """Test integration_connector_list returns 200, context variables contract pinned, and tenant isolation."""
    url = reverse("bi:integration_connector_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "connectors" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "error_count" in resp.context
    assert "search_query" in resp.context
    assert "connector_type" in resp.context
    assert "target_system" in resp.context
    assert "status" in resp.context
    assert "type_choices" in resp.context
    assert "target_choices" in resp.context
    assert "status_choices" in resp.context

    # Verify tenant isolation: tenant_a sees connector_a, does NOT see connector_b
    item_pks = [c.pk for c in resp.context["connectors"]]
    assert integration_connector_a.pk in item_pks
    assert integration_connector_b.pk not in item_pks

    content = resp.content.decode("utf-8")
    assert integration_connector_a.name in content
    assert integration_connector_a.number in content
    assert integration_connector_b.name not in content


@pytest.mark.django_db
def test_integrationhub_views_connector_list_metrics_aggregation(
    client_a, tenant_a, admin_user
):
    """Test integration_connector_list aggregates total, active, and error connector metrics."""
    # Create active connector
    _integrationhub_create_connector(
        tenant_a, created_by=admin_user, status="active", health_status="healthy"
    )
    # Create error connector by status
    _integrationhub_create_connector(
        tenant_a, created_by=admin_user, status="error", health_status="healthy"
    )
    # Create error connector by health_status
    _integrationhub_create_connector(
        tenant_a, created_by=admin_user, status="paused", health_status="unreachable"
    )

    url = reverse("bi:integration_connector_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] >= 3
    assert resp.context["active_count"] >= 1
    assert resp.context["error_count"] >= 2


@pytest.mark.django_db
def test_integrationhub_views_connector_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching connectors by query matching name, number, slug, or description."""
    target = _integrationhub_create_connector(
        tenant_a,
        created_by=admin_user,
        name="UniqueBrokerTargetAlpha",
        slug="unique-broker-target-alpha",
        description="Special streaming pipeline description keyword",
    )
    url = reverse("bi:integration_connector_list")

    # Match by name
    resp_match = client_a.get(url, {"q": "BrokerTargetAlpha"})
    assert resp_match.status_code == 200
    pks = [c.pk for c in resp_match.context["connectors"]]
    assert target.pk in pks

    # Match by description
    resp_desc = client_a.get(url, {"q": "streaming pipeline description"})
    assert resp_desc.status_code == 200
    pks_desc = [c.pk for c in resp_desc.context["connectors"]]
    assert target.pk in pks_desc

    # Unmatched query
    resp_none = client_a.get(url, {"q": "NonExistentConnectorXYZ999"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["connectors"]) == 0


@pytest.mark.django_db
def test_integrationhub_views_connector_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering connectors by connector_type, target_system, and status."""
    c_kafka = _integrationhub_create_connector(
        tenant_a,
        created_by=admin_user,
        name="Kafka Stream Ingress",
        connector_type="message_broker",
        target_system="kafka",
        status="active",
    )
    c_crm = _integrationhub_create_connector(
        tenant_a,
        created_by=admin_user,
        name="CRM Operational Link",
        connector_type="internal_erp",
        target_system="erp_crm",
        status="paused",
    )
    url = reverse("bi:integration_connector_list")

    # Filter connector_type=message_broker
    resp_type = client_a.get(url, {"connector_type": "message_broker"})
    pks_type = [c.pk for c in resp_type.context["connectors"]]
    assert c_kafka.pk in pks_type
    assert c_crm.pk not in pks_type

    # Filter target_system=erp_crm
    resp_target = client_a.get(url, {"target_system": "erp_crm"})
    pks_target = [c.pk for c in resp_target.context["connectors"]]
    assert c_crm.pk in pks_target
    assert c_kafka.pk not in pks_target

    # Filter status=paused
    resp_status = client_a.get(url, {"status": "paused"})
    pks_status = [c.pk for c in resp_status.context["connectors"]]
    assert c_crm.pk in pks_status
    assert c_kafka.pk not in pks_status


@pytest.mark.django_db
def test_integrationhub_views_connector_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination of connectors with 15 items per page."""
    for i in range(16):
        _integrationhub_create_connector(
            tenant_a, created_by=admin_user, name=f"Paginated Connector {i:02d}"
        )

    url = reverse("bi:integration_connector_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["connectors"]) == 15
    assert resp_p1.context["connectors"].has_next() is True
    assert resp_p1.context["is_paginated"] is True

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["connectors"]) >= 1


@pytest.mark.django_db
def test_integrationhub_views_connector_detail(
    client_a, integration_connector_a
):
    """Test integration_connector_detail returns 200, pins context variable, and renders details."""
    url = reverse("bi:integration_connector_detail", kwargs={"pk": integration_connector_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "connector" in resp.context
    assert resp.context["connector"].pk == integration_connector_a.pk

    content = resp.content.decode("utf-8")
    assert integration_connector_a.name in content
    assert integration_connector_a.number in content
    assert integration_connector_a.slug in content


@pytest.mark.django_db
def test_integrationhub_views_connector_create_get_and_post_valid(
    client_a, tenant_a, admin_user
):
    """Test connector create view GET returns form and valid POST redirects to detail."""
    url = reverse("bi:integration_connector_create")

    # GET returns form
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_create"] is True

    # POST valid form
    data = _integrationhub_connector_form_data(name="Enterprise Kafka Producer Stream")
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = IntegrationConnector.objects.filter(
        tenant=tenant_a, name="Enterprise Kafka Producer Stream"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert resp_post.url == reverse("bi:integration_connector_detail", kwargs={"pk": created.pk})

    # Verify audit log recorded
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_connector_create_post_invalid(client_a):
    """Test connector create with invalid payload re-renders form with 200 and errors."""
    url = reverse("bi:integration_connector_create")
    resp = client_a.post(url, {"name": ""})  # Name is required

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_connector_edit_get_and_post_valid(
    client_a, tenant_a, integration_connector_a
):
    """Test connector edit view GET returns 200 and valid POST updates connector."""
    url = reverse("bi:integration_connector_edit", kwargs={"pk": integration_connector_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert "connector" in resp_get.context
    assert resp_get.context["is_create"] is False

    # POST valid update
    data = _integrationhub_connector_form_data(
        name="Enterprise Kafka Stream Updated",
        status="paused",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:integration_connector_detail", kwargs={"pk": integration_connector_a.pk}
    )

    integration_connector_a.refresh_from_db()
    assert integration_connector_a.name == "Enterprise Kafka Stream Updated"
    assert integration_connector_a.status == "paused"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=integration_connector_a.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_connector_edit_post_invalid(client_a, integration_connector_a):
    """Test connector edit with invalid payload re-renders form with 200."""
    url = reverse("bi:integration_connector_edit", kwargs={"pk": integration_connector_a.pk})
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_connector_delete(
    client_a, tenant_a, admin_user
):
    """Test connector delete requires POST (GET returns 405) and deletes object."""
    connector = _integrationhub_create_connector(
        tenant_a, created_by=admin_user, name="Connector To Delete"
    )
    url = reverse("bi:integration_connector_delete", kwargs={"pk": connector.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes object
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:integration_connector_list")
    assert not IntegrationConnector.objects.filter(pk=connector.pk).exists()

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=connector.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_connector_ping_action(
    client_a, tenant_a, integration_connector_a
):
    """Test connector ping action requires POST, updates health_status, and increments processed count."""
    integration_connector_a.health_status = "degraded"
    integration_connector_a.total_messages_processed = 10
    integration_connector_a.error_message = "Previous timeout"
    integration_connector_a.save()

    url = reverse("bi:integration_connector_ping", kwargs={"pk": integration_connector_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST dispatches ping
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:integration_connector_detail", kwargs={"pk": integration_connector_a.pk}
    )

    integration_connector_a.refresh_from_db()
    assert integration_connector_a.health_status == "healthy"
    assert integration_connector_a.status == "active"
    assert integration_connector_a.error_message == ""
    assert integration_connector_a.last_heartbeat_at is not None
    assert integration_connector_a.total_messages_processed == 11

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="action", object_id=integration_connector_a.pk
    ).exists()


# ==============================================================================
# 2. WarehouseSyncEndpoint View Tests (6 views)
# ==============================================================================


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_list_status_context_and_tenant_isolation(
    client_a, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
):
    """Test warehouse_sync_endpoint_list returns 200, context variables contract pinned, and tenant isolation."""
    url = reverse("bi:warehouse_sync_endpoint_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "sync_endpoints" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "total_count" in resp.context
    assert "success_count" in resp.context
    assert "error_count" in resp.context
    assert "search_query" in resp.context
    assert "target_warehouse" in resp.context
    assert "sync_mode" in resp.context
    assert "status" in resp.context
    assert "warehouse_choices" in resp.context
    assert "mode_choices" in resp.context
    assert "status_choices" in resp.context

    # Verify tenant isolation
    item_pks = [s.pk for s in resp.context["sync_endpoints"]]
    assert warehouse_sync_endpoint_a.pk in item_pks
    assert warehouse_sync_endpoint_b.pk not in item_pks

    content = resp.content.decode("utf-8")
    assert warehouse_sync_endpoint_a.name in content
    assert warehouse_sync_endpoint_a.number in content
    assert warehouse_sync_endpoint_b.name not in content


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_list_metrics_aggregation(
    client_a, tenant_a, admin_user
):
    """Test warehouse_sync_endpoint_list aggregates total, success, and error sync metrics."""
    _integrationhub_create_warehouse_sync(
        tenant_a, owner=admin_user, status="success"
    )
    _integrationhub_create_warehouse_sync(
        tenant_a, owner=admin_user, status="error"
    )

    url = reverse("bi:warehouse_sync_endpoint_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] >= 2
    assert resp.context["success_count"] >= 1
    assert resp.context["error_count"] >= 1


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching warehouse sync endpoints by name, number, slug, destination_table, destination_database."""
    target = _integrationhub_create_warehouse_sync(
        tenant_a,
        owner=admin_user,
        name="UniqueWarehouseSyncTarget",
        destination_database="PROD_DW_TARGET",
        destination_table="FCT_REVENUE_METRICS",
    )
    url = reverse("bi:warehouse_sync_endpoint_list")

    # Match by destination_table
    resp_match = client_a.get(url, {"q": "FCT_REVENUE_METRICS"})
    assert resp_match.status_code == 200
    pks = [s.pk for s in resp_match.context["sync_endpoints"]]
    assert target.pk in pks

    # Match by destination_database
    resp_db = client_a.get(url, {"q": "PROD_DW_TARGET"})
    assert resp_db.status_code == 200
    pks_db = [s.pk for s in resp_db.context["sync_endpoints"]]
    assert target.pk in pks_db

    # Unmatched query
    resp_none = client_a.get(url, {"q": "NonExistentSyncXYZ888"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["sync_endpoints"]) == 0


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering warehouse syncs by target_warehouse, sync_mode, and status."""
    s_snowflake = _integrationhub_create_warehouse_sync(
        tenant_a,
        owner=admin_user,
        name="Snowflake Nightly Sync",
        target_warehouse="snowflake",
        sync_mode="incremental_merge",
        status="idle",
    )
    s_bigquery = _integrationhub_create_warehouse_sync(
        tenant_a,
        owner=admin_user,
        name="BigQuery Hourly Sync",
        target_warehouse="google_bigquery",
        sync_mode="append_only",
        status="success",
    )
    url = reverse("bi:warehouse_sync_endpoint_list")

    # Filter target_warehouse=snowflake
    resp_wh = client_a.get(url, {"target_warehouse": "snowflake"})
    pks_wh = [s.pk for s in resp_wh.context["sync_endpoints"]]
    assert s_snowflake.pk in pks_wh
    assert s_bigquery.pk not in pks_wh

    # Filter sync_mode=append_only
    resp_mode = client_a.get(url, {"sync_mode": "append_only"})
    pks_mode = [s.pk for s in resp_mode.context["sync_endpoints"]]
    assert s_bigquery.pk in pks_mode
    assert s_snowflake.pk not in pks_mode

    # Filter status=success
    resp_stat = client_a.get(url, {"status": "success"})
    pks_stat = [s.pk for s in resp_stat.context["sync_endpoints"]]
    assert s_bigquery.pk in pks_stat
    assert s_snowflake.pk not in pks_stat


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination of warehouse sync endpoints with 15 items per page."""
    for i in range(16):
        _integrationhub_create_warehouse_sync(
            tenant_a, owner=admin_user, name=f"Paginated Sync {i:02d}"
        )

    url = reverse("bi:warehouse_sync_endpoint_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["sync_endpoints"]) == 15
    assert resp_p1.context["sync_endpoints"].has_next() is True
    assert resp_p1.context["is_paginated"] is True

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["sync_endpoints"]) >= 1


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_detail(
    client_a, warehouse_sync_endpoint_a
):
    """Test warehouse_sync_endpoint_detail returns 200, context variables contract pinned, and renders content."""
    url = reverse("bi:warehouse_sync_endpoint_detail", kwargs={"pk": warehouse_sync_endpoint_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "sync_endpoint" in resp.context
    assert resp.context["sync_endpoint"].pk == warehouse_sync_endpoint_a.pk

    content = resp.content.decode("utf-8")
    assert warehouse_sync_endpoint_a.name in content
    assert warehouse_sync_endpoint_a.number in content
    assert warehouse_sync_endpoint_a.destination_table in content


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_create_get_and_post_valid(
    client_a, tenant_a, admin_user
):
    """Test warehouse sync create view GET returns form and valid POST redirects to detail."""
    url = reverse("bi:warehouse_sync_endpoint_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_create"] is True

    # POST valid form
    data = _integrationhub_warehouse_sync_form_data(
        name="Google BigQuery Analytical Dataset Export"
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = WarehouseSyncEndpoint.objects.filter(
        tenant=tenant_a, name="Google BigQuery Analytical Dataset Export"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.owner == admin_user
    assert resp_post.url == reverse("bi:warehouse_sync_endpoint_detail", kwargs={"pk": created.pk})

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_create_post_invalid(client_a):
    """Test warehouse sync create with invalid payload re-renders form with 200."""
    url = reverse("bi:warehouse_sync_endpoint_create")
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_edit_get_and_post_valid(
    client_a, tenant_a, warehouse_sync_endpoint_a
):
    """Test warehouse sync edit view GET returns 200 and valid POST updates object."""
    url = reverse("bi:warehouse_sync_endpoint_edit", kwargs={"pk": warehouse_sync_endpoint_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert "sync_endpoint" in resp_get.context
    assert resp_get.context["is_create"] is False

    # POST valid update
    data = _integrationhub_warehouse_sync_form_data(
        name="Snowflake Nightly Sync Renovated",
        sync_schedule="hourly",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:warehouse_sync_endpoint_detail", kwargs={"pk": warehouse_sync_endpoint_a.pk}
    )

    warehouse_sync_endpoint_a.refresh_from_db()
    assert warehouse_sync_endpoint_a.name == "Snowflake Nightly Sync Renovated"
    assert warehouse_sync_endpoint_a.sync_schedule == "hourly"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=warehouse_sync_endpoint_a.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_edit_post_invalid(client_a, warehouse_sync_endpoint_a):
    """Test warehouse sync edit with invalid payload re-renders form with 200."""
    url = reverse("bi:warehouse_sync_endpoint_edit", kwargs={"pk": warehouse_sync_endpoint_a.pk})
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_delete(
    client_a, tenant_a, admin_user
):
    """Test warehouse sync delete requires POST (GET returns 405) and deletes object."""
    sync_endpoint = _integrationhub_create_warehouse_sync(
        tenant_a, owner=admin_user, name="Sync Endpoint To Delete"
    )
    url = reverse("bi:warehouse_sync_endpoint_delete", kwargs={"pk": sync_endpoint.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes object
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:warehouse_sync_endpoint_list")
    assert not WarehouseSyncEndpoint.objects.filter(pk=sync_endpoint.pk).exists()

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=sync_endpoint.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_warehouse_sync_trigger_action(
    client_a, tenant_a, warehouse_sync_endpoint_a
):
    """Test warehouse sync trigger action requires POST, updates status, and increments sync counter."""
    warehouse_sync_endpoint_a.status = "idle"
    warehouse_sync_endpoint_a.total_rows_synced = 5000
    warehouse_sync_endpoint_a.save()

    url = reverse("bi:warehouse_sync_endpoint_trigger", kwargs={"pk": warehouse_sync_endpoint_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST triggers sync
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:warehouse_sync_endpoint_detail", kwargs={"pk": warehouse_sync_endpoint_a.pk}
    )

    warehouse_sync_endpoint_a.refresh_from_db()
    assert warehouse_sync_endpoint_a.status == "success"
    assert warehouse_sync_endpoint_a.last_sync_at is not None
    assert warehouse_sync_endpoint_a.last_sync_duration_ms == 1420
    assert warehouse_sync_endpoint_a.last_rows_synced == 2500
    assert warehouse_sync_endpoint_a.total_rows_synced == 7500
    assert warehouse_sync_endpoint_a.last_error_message == ""

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="action", object_id=warehouse_sync_endpoint_a.pk
    ).exists()


# ==============================================================================
# 3. BiWebhookSubscription View Tests (6 views)
# ==============================================================================


@pytest.mark.django_db
def test_integrationhub_views_webhook_list_status_context_and_tenant_isolation(
    client_a, bi_webhook_subscription_a, bi_webhook_subscription_b
):
    """Test bi_webhook_subscription_list returns 200, context variables contract pinned, and tenant isolation."""
    url = reverse("bi:bi_webhook_subscription_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "webhooks" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "failing_count" in resp.context
    assert "search_query" in resp.context
    assert "payload_format" in resp.context
    assert "status" in resp.context
    assert "format_choices" in resp.context
    assert "status_choices" in resp.context

    # Verify tenant isolation
    item_pks = [w.pk for w in resp.context["webhooks"]]
    assert bi_webhook_subscription_a.pk in item_pks
    assert bi_webhook_subscription_b.pk not in item_pks

    content = resp.content.decode("utf-8")
    assert bi_webhook_subscription_a.name in content
    assert bi_webhook_subscription_a.number in content
    assert bi_webhook_subscription_b.name not in content


@pytest.mark.django_db
def test_integrationhub_views_webhook_list_metrics_aggregation(
    client_a, tenant_a, admin_user
):
    """Test bi_webhook_subscription_list aggregates total, active, and failing webhook metrics."""
    _integrationhub_create_webhook(
        tenant_a, created_by=admin_user, status="active"
    )
    _integrationhub_create_webhook(
        tenant_a, created_by=admin_user, status="failing"
    )
    _integrationhub_create_webhook(
        tenant_a, created_by=admin_user, status="suspended"
    )

    url = reverse("bi:bi_webhook_subscription_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] >= 3
    assert resp.context["active_count"] >= 1
    assert resp.context["failing_count"] >= 2


@pytest.mark.django_db
def test_integrationhub_views_webhook_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching webhooks by query matching name, number, or endpoint_url."""
    target = _integrationhub_create_webhook(
        tenant_a,
        created_by=admin_user,
        name="UniqueIncidentDispatcherWebhook",
        endpoint_url="https://hooks.example.com/unique-endpoint-target",
    )
    url = reverse("bi:bi_webhook_subscription_list")

    # Match by name
    resp_match = client_a.get(url, {"q": "IncidentDispatcher"})
    assert resp_match.status_code == 200
    pks = [w.pk for w in resp_match.context["webhooks"]]
    assert target.pk in pks

    # Match by endpoint_url
    resp_url = client_a.get(url, {"q": "unique-endpoint-target"})
    assert resp_url.status_code == 200
    pks_url = [w.pk for w in resp_url.context["webhooks"]]
    assert target.pk in pks_url

    # Unmatched query
    resp_none = client_a.get(url, {"q": "NonExistentWebhookXYZ777"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["webhooks"]) == 0


@pytest.mark.django_db
def test_integrationhub_views_webhook_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering webhooks by payload_format and status."""
    w_slack = _integrationhub_create_webhook(
        tenant_a,
        created_by=admin_user,
        name="Slack Alert Subscription",
        payload_format="slack_compatible",
        status="active",
    )
    w_cloud = _integrationhub_create_webhook(
        tenant_a,
        created_by=admin_user,
        name="CloudEvents Event Mesh Subscription",
        payload_format="cloudevents_v1",
        status="failing",
    )
    url = reverse("bi:bi_webhook_subscription_list")

    # Filter payload_format=slack_compatible
    resp_fmt = client_a.get(url, {"payload_format": "slack_compatible"})
    pks_fmt = [w.pk for w in resp_fmt.context["webhooks"]]
    assert w_slack.pk in pks_fmt
    assert w_cloud.pk not in pks_fmt

    # Filter status=failing
    resp_stat = client_a.get(url, {"status": "failing"})
    pks_stat = [w.pk for w in resp_stat.context["webhooks"]]
    assert w_cloud.pk in pks_stat
    assert w_slack.pk not in pks_stat


@pytest.mark.django_db
def test_integrationhub_views_webhook_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination of webhooks with 15 items per page."""
    for i in range(16):
        _integrationhub_create_webhook(
            tenant_a, created_by=admin_user, name=f"Paginated Webhook {i:02d}"
        )

    url = reverse("bi:bi_webhook_subscription_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["webhooks"]) == 15
    assert resp_p1.context["webhooks"].has_next() is True
    assert resp_p1.context["is_paginated"] is True

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["webhooks"]) >= 1


@pytest.mark.django_db
def test_integrationhub_views_webhook_detail(
    client_a, bi_webhook_subscription_a
):
    """Test bi_webhook_subscription_detail returns 200, context variables contract pinned, and renders details."""
    url = reverse("bi:bi_webhook_subscription_detail", kwargs={"pk": bi_webhook_subscription_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "webhook" in resp.context
    assert resp.context["webhook"].pk == bi_webhook_subscription_a.pk

    content = resp.content.decode("utf-8")
    assert bi_webhook_subscription_a.name in content
    assert bi_webhook_subscription_a.number in content
    assert bi_webhook_subscription_a.endpoint_url in content


@pytest.mark.django_db
def test_integrationhub_views_webhook_create_get_and_post_valid(
    client_a, tenant_a, admin_user
):
    """Test webhook create view GET returns form and valid POST redirects to detail."""
    url = reverse("bi:bi_webhook_subscription_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_create"] is True

    # POST valid form
    data = _integrationhub_webhook_form_data(name="Microsoft Teams Broadcast Webhook")
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = BiWebhookSubscription.objects.filter(
        tenant=tenant_a, name="Microsoft Teams Broadcast Webhook"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert resp_post.url == reverse("bi:bi_webhook_subscription_detail", kwargs={"pk": created.pk})

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_webhook_create_post_invalid(client_a):
    """Test webhook create with invalid payload re-renders form with 200."""
    url = reverse("bi:bi_webhook_subscription_create")
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_webhook_edit_get_and_post_valid(
    client_a, tenant_a, bi_webhook_subscription_a
):
    """Test webhook edit view GET returns 200 and valid POST updates webhook."""
    url = reverse("bi:bi_webhook_subscription_edit", kwargs={"pk": bi_webhook_subscription_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert "webhook" in resp_get.context
    assert resp_get.context["is_create"] is False

    # POST valid update
    data = _integrationhub_webhook_form_data(
        name="Alert Dispatch Webhook Renovated",
        endpoint_url="https://hooks.example.com/alerts/v2",
        max_retries=5,
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:bi_webhook_subscription_detail", kwargs={"pk": bi_webhook_subscription_a.pk}
    )

    bi_webhook_subscription_a.refresh_from_db()
    assert bi_webhook_subscription_a.name == "Alert Dispatch Webhook Renovated"
    assert bi_webhook_subscription_a.endpoint_url == "https://hooks.example.com/alerts/v2"
    assert bi_webhook_subscription_a.max_retries == 5

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=bi_webhook_subscription_a.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_webhook_edit_post_invalid(client_a, bi_webhook_subscription_a):
    """Test webhook edit with invalid payload re-renders form with 200."""
    url = reverse("bi:bi_webhook_subscription_edit", kwargs={"pk": bi_webhook_subscription_a.pk})
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_webhook_delete(
    client_a, tenant_a, admin_user
):
    """Test webhook delete requires POST (GET returns 405) and deletes object."""
    webhook = _integrationhub_create_webhook(
        tenant_a, created_by=admin_user, name="Webhook To Delete"
    )
    url = reverse("bi:bi_webhook_subscription_delete", kwargs={"pk": webhook.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes object
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_webhook_subscription_list")
    assert not BiWebhookSubscription.objects.filter(pk=webhook.pk).exists()

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=webhook.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_webhook_ping_action(
    client_a, tenant_a, bi_webhook_subscription_a
):
    """Test webhook ping action requires POST, records test dispatch, and increments delivery count."""
    bi_webhook_subscription_a.status = "failing"
    bi_webhook_subscription_a.consecutive_failures = 3
    bi_webhook_subscription_a.total_deliveries = 50
    bi_webhook_subscription_a.save()

    url = reverse("bi:bi_webhook_subscription_ping", kwargs={"pk": bi_webhook_subscription_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST dispatches test ping
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:bi_webhook_subscription_detail", kwargs={"pk": bi_webhook_subscription_a.pk}
    )

    bi_webhook_subscription_a.refresh_from_db()
    assert bi_webhook_subscription_a.status == "active"
    assert bi_webhook_subscription_a.consecutive_failures == 0
    assert bi_webhook_subscription_a.last_response_code == 200
    assert bi_webhook_subscription_a.last_response_time_ms == 145
    assert bi_webhook_subscription_a.last_triggered_at is not None
    assert bi_webhook_subscription_a.total_deliveries == 51

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="action", object_id=bi_webhook_subscription_a.pk
    ).exists()


# ==============================================================================
# 4. BiExtensionPlugin View Tests (6 views + protection)
# ==============================================================================


@pytest.mark.django_db
def test_integrationhub_views_plugin_list_status_context_and_tenant_isolation(
    client_a, bi_extension_plugin_a, bi_extension_plugin_b
):
    """Test bi_extension_plugin_list returns 200, context variables contract pinned, and tenant isolation."""
    url = reverse("bi:bi_extension_plugin_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "plugins" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "total_count" in resp.context
    assert "enabled_count" in resp.context
    assert "verified_count" in resp.context
    assert "search_query" in resp.context
    assert "plugin_type" in resp.context
    assert "category" in resp.context
    assert "status" in resp.context
    assert "type_choices" in resp.context
    assert "category_choices" in resp.context
    assert "status_choices" in resp.context

    # Verify tenant isolation
    item_pks = [p.pk for p in resp.context["plugins"]]
    assert bi_extension_plugin_a.pk in item_pks
    assert bi_extension_plugin_b.pk not in item_pks

    content = resp.content.decode("utf-8")
    assert bi_extension_plugin_a.name in content
    assert bi_extension_plugin_a.number in content
    assert bi_extension_plugin_b.name not in content


@pytest.mark.django_db
def test_integrationhub_views_plugin_list_metrics_aggregation(
    client_a, tenant_a, admin_user
):
    """Test bi_extension_plugin_list aggregates total, enabled, and verified metrics."""
    _integrationhub_create_plugin(
        tenant_a, installed_by=admin_user, status="enabled", is_verified=True
    )
    _integrationhub_create_plugin(
        tenant_a, installed_by=admin_user, status="disabled", is_verified=False
    )

    url = reverse("bi:bi_extension_plugin_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["total_count"] >= 2
    assert resp.context["enabled_count"] >= 1
    assert resp.context["verified_count"] >= 1


@pytest.mark.django_db
def test_integrationhub_views_plugin_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching plugins by name, plugin_identifier, author_name, or description."""
    target = _integrationhub_create_plugin(
        tenant_a,
        installed_by=admin_user,
        name="UniqueChordDiagramVisualizer",
        plugin_identifier="io.naverp.visuals.chord",
        author_name="VisualsLabExclusiveAuthor",
        description="Complex hierarchical circular flow chart.",
    )
    url = reverse("bi:bi_extension_plugin_list")

    # Match by plugin_identifier
    resp_ident = client_a.get(url, {"q": "visuals.chord"})
    assert resp_ident.status_code == 200
    pks = [p.pk for p in resp_ident.context["plugins"]]
    assert target.pk in pks

    # Match by author_name
    resp_author = client_a.get(url, {"q": "ExclusiveAuthor"})
    assert resp_author.status_code == 200
    pks_author = [p.pk for p in resp_author.context["plugins"]]
    assert target.pk in pks_author

    # Unmatched query
    resp_none = client_a.get(url, {"q": "NonExistentPluginXYZ666"})
    assert resp_none.status_code == 200
    assert len(resp_none.context["plugins"]) == 0


@pytest.mark.django_db
def test_integrationhub_views_plugin_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering plugins by plugin_type, category, and status."""
    p_visual = _integrationhub_create_plugin(
        tenant_a,
        installed_by=admin_user,
        name="Radar Chart Visualizer",
        plugin_type="custom_visual",
        category="visualization",
        status="enabled",
    )
    p_transform = _integrationhub_create_plugin(
        tenant_a,
        installed_by=admin_user,
        name="Data Cleansing Transform Hook",
        plugin_type="transformation_script",
        category="data_integration",
        status="disabled",
    )
    url = reverse("bi:bi_extension_plugin_list")

    # Filter plugin_type=custom_visual
    resp_type = client_a.get(url, {"plugin_type": "custom_visual"})
    pks_type = [p.pk for p in resp_type.context["plugins"]]
    assert p_visual.pk in pks_type
    assert p_transform.pk not in pks_type

    # Filter category=data_integration
    resp_cat = client_a.get(url, {"category": "data_integration"})
    pks_cat = [p.pk for p in resp_cat.context["plugins"]]
    assert p_transform.pk in pks_cat
    assert p_visual.pk not in pks_cat

    # Filter status=disabled
    resp_stat = client_a.get(url, {"status": "disabled"})
    pks_stat = [p.pk for p in resp_stat.context["plugins"]]
    assert p_transform.pk in pks_stat
    assert p_visual.pk not in pks_stat


@pytest.mark.django_db
def test_integrationhub_views_plugin_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test pagination of extension plugins with 15 items per page."""
    for i in range(16):
        _integrationhub_create_plugin(
            tenant_a, installed_by=admin_user, name=f"Paginated Plugin {i:02d}"
        )

    url = reverse("bi:bi_extension_plugin_list")

    # Page 1
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["plugins"]) == 15
    assert resp_p1.context["plugins"].has_next() is True
    assert resp_p1.context["is_paginated"] is True

    # Page 2
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["plugins"]) >= 1


@pytest.mark.django_db
def test_integrationhub_views_plugin_detail(
    client_a, bi_extension_plugin_a
):
    """Test bi_extension_plugin_detail returns 200, context variables contract pinned, and renders details."""
    url = reverse("bi:bi_extension_plugin_detail", kwargs={"pk": bi_extension_plugin_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "plugin" in resp.context
    assert resp.context["plugin"].pk == bi_extension_plugin_a.pk

    content = resp.content.decode("utf-8")
    assert bi_extension_plugin_a.name in content
    assert bi_extension_plugin_a.number in content
    assert bi_extension_plugin_a.plugin_identifier in content
    assert bi_extension_plugin_a.version in content


@pytest.mark.django_db
def test_integrationhub_views_plugin_create_get_and_post_valid(
    client_a, tenant_a, admin_user
):
    """Test plugin create view GET returns form and valid POST redirects to detail."""
    url = reverse("bi:bi_extension_plugin_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_create"] is True

    # POST valid form
    data = _integrationhub_plugin_form_data(name="Vega-Lite Interactive Visualizer")
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302

    created = BiExtensionPlugin.objects.filter(
        tenant=tenant_a, name="Vega-Lite Interactive Visualizer"
    ).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.installed_by == admin_user
    assert resp_post.url == reverse("bi:bi_extension_plugin_detail", kwargs={"pk": created.pk})

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="create", object_id=created.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_plugin_create_post_invalid(client_a):
    """Test plugin create with invalid payload re-renders form with 200."""
    url = reverse("bi:bi_extension_plugin_create")
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_plugin_edit_get_and_post_valid(
    client_a, tenant_a, bi_extension_plugin_a
):
    """Test plugin edit view GET returns 200 and valid POST updates plugin."""
    url = reverse("bi:bi_extension_plugin_edit", kwargs={"pk": bi_extension_plugin_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert "plugin" in resp_get.context
    assert resp_get.context["is_create"] is False

    # POST valid update
    data = _integrationhub_plugin_form_data(
        name="Sankey Visualizer Plugin Renovated",
        version="1.5.0",
        author_name="DataViz Lab Pro Team",
    )
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:bi_extension_plugin_detail", kwargs={"pk": bi_extension_plugin_a.pk}
    )

    bi_extension_plugin_a.refresh_from_db()
    assert bi_extension_plugin_a.name == "Sankey Visualizer Plugin Renovated"
    assert bi_extension_plugin_a.version == "1.5.0"
    assert bi_extension_plugin_a.author_name == "DataViz Lab Pro Team"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="update", object_id=bi_extension_plugin_a.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_plugin_edit_post_invalid(client_a, bi_extension_plugin_a):
    """Test plugin edit with invalid payload re-renders form with 200."""
    url = reverse("bi:bi_extension_plugin_edit", kwargs={"pk": bi_extension_plugin_a.pk})
    resp = client_a.post(url, {"name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_integrationhub_views_plugin_edit_system_plugin_protected(
    client_a, tenant_a, admin_user
):
    """Test system-bundled extension plugins cannot be edited via GET or POST."""
    system_plugin = _integrationhub_create_plugin(
        tenant_a,
        installed_by=admin_user,
        name="Protected Core System Visualizer",
        is_system_plugin=True,
    )
    url = reverse("bi:bi_extension_plugin_edit", kwargs={"pk": system_plugin.pk})

    # GET redirects to detail with error
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse(
        "bi:bi_extension_plugin_detail", kwargs={"pk": system_plugin.pk}
    )

    # POST redirects to detail and does not modify plugin
    data = _integrationhub_plugin_form_data(name="Attempted System Rename")
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:bi_extension_plugin_detail", kwargs={"pk": system_plugin.pk}
    )

    system_plugin.refresh_from_db()
    assert system_plugin.name == "Protected Core System Visualizer"


@pytest.mark.django_db
def test_integrationhub_views_plugin_delete_user_plugin(
    client_a, tenant_a, admin_user
):
    """Test user-installed plugin delete requires POST (GET returns 405) and deletes object."""
    plugin = _integrationhub_create_plugin(
        tenant_a, installed_by=admin_user, name="Plugin To Uninstall", is_system_plugin=False
    )
    url = reverse("bi:bi_extension_plugin_delete", kwargs={"pk": plugin.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes object
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:bi_extension_plugin_list")
    assert not BiExtensionPlugin.objects.filter(pk=plugin.pk).exists()

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="delete", object_id=plugin.pk
    ).exists()


@pytest.mark.django_db
def test_integrationhub_views_plugin_delete_system_plugin_protected(
    client_a, tenant_a, admin_user
):
    """Test system-bundled extension plugins cannot be deleted; POST redirects and preserves object."""
    system_plugin = _integrationhub_create_plugin(
        tenant_a, installed_by=admin_user, name="Critical Core System Plugin", is_system_plugin=True
    )
    url = reverse("bi:bi_extension_plugin_delete", kwargs={"pk": system_plugin.pk})

    # POST redirects with error and does NOT delete
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse(
        "bi:bi_extension_plugin_detail", kwargs={"pk": system_plugin.pk}
    )
    assert BiExtensionPlugin.objects.filter(pk=system_plugin.pk).exists()


@pytest.mark.django_db
def test_integrationhub_views_plugin_toggle_action(
    client_a, tenant_a, bi_extension_plugin_a
):
    """Test plugin toggle action requires POST, flips status between enabled and disabled."""
    bi_extension_plugin_a.status = "enabled"
    bi_extension_plugin_a.save()

    url = reverse("bi:bi_extension_plugin_toggle", kwargs={"pk": bi_extension_plugin_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # First POST: flips enabled -> disabled
    resp_toggle_1 = client_a.post(url)
    assert resp_toggle_1.status_code == 302
    assert resp_toggle_1.url == reverse(
        "bi:bi_extension_plugin_detail", kwargs={"pk": bi_extension_plugin_a.pk}
    )

    bi_extension_plugin_a.refresh_from_db()
    assert bi_extension_plugin_a.status == "disabled"

    # Second POST: flips disabled -> enabled
    resp_toggle_2 = client_a.post(url)
    assert resp_toggle_2.status_code == 302

    bi_extension_plugin_a.refresh_from_db()
    assert bi_extension_plugin_a.status == "enabled"

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a, action="action", object_id=bi_extension_plugin_a.pk
    ).exists()


# ==============================================================================
# 5. Cross-Tenant Isolation (IDOR) & Unauthenticated Access Tests
# ==============================================================================


@pytest.mark.django_db
def test_integrationhub_views_cross_tenant_idor_protection(
    client_b,
    integration_connector_a,
    warehouse_sync_endpoint_a,
    bi_webhook_subscription_a,
    bi_extension_plugin_a,
):
    """Test that a tenant B user receives 404 when attempting to access tenant A objects."""
    # 1. IntegrationConnector cross-tenant
    assert (
        client_b.get(
            reverse("bi:integration_connector_detail", kwargs={"pk": integration_connector_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.get(
            reverse("bi:integration_connector_edit", kwargs={"pk": integration_connector_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse("bi:integration_connector_delete", kwargs={"pk": integration_connector_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse("bi:integration_connector_ping", kwargs={"pk": integration_connector_a.pk})
        ).status_code
        == 404
    )

    # 2. WarehouseSyncEndpoint cross-tenant
    assert (
        client_b.get(
            reverse(
                "bi:warehouse_sync_endpoint_detail", kwargs={"pk": warehouse_sync_endpoint_a.pk}
            )
        ).status_code
        == 404
    )
    assert (
        client_b.get(
            reverse("bi:warehouse_sync_endpoint_edit", kwargs={"pk": warehouse_sync_endpoint_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse(
                "bi:warehouse_sync_endpoint_delete", kwargs={"pk": warehouse_sync_endpoint_a.pk}
            )
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse(
                "bi:warehouse_sync_endpoint_trigger", kwargs={"pk": warehouse_sync_endpoint_a.pk}
            )
        ).status_code
        == 404
    )

    # 3. BiWebhookSubscription cross-tenant
    assert (
        client_b.get(
            reverse(
                "bi:bi_webhook_subscription_detail", kwargs={"pk": bi_webhook_subscription_a.pk}
            )
        ).status_code
        == 404
    )
    assert (
        client_b.get(
            reverse("bi:bi_webhook_subscription_edit", kwargs={"pk": bi_webhook_subscription_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse(
                "bi:bi_webhook_subscription_delete", kwargs={"pk": bi_webhook_subscription_a.pk}
            )
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse(
                "bi:bi_webhook_subscription_ping", kwargs={"pk": bi_webhook_subscription_a.pk}
            )
        ).status_code
        == 404
    )

    # 4. BiExtensionPlugin cross-tenant
    assert (
        client_b.get(
            reverse("bi:bi_extension_plugin_detail", kwargs={"pk": bi_extension_plugin_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.get(
            reverse("bi:bi_extension_plugin_edit", kwargs={"pk": bi_extension_plugin_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse("bi:bi_extension_plugin_delete", kwargs={"pk": bi_extension_plugin_a.pk})
        ).status_code
        == 404
    )
    assert (
        client_b.post(
            reverse("bi:bi_extension_plugin_toggle", kwargs={"pk": bi_extension_plugin_a.pk})
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_integrationhub_views_unauthenticated_access_redirects_to_login(
    anon_client,
    integration_connector_a,
    warehouse_sync_endpoint_a,
    bi_webhook_subscription_a,
    bi_extension_plugin_a,
):
    """Test that unauthenticated requests to all 24 endpoints return 302 redirecting to login."""
    urls = [
        # 1. IntegrationConnector (6)
        reverse("bi:integration_connector_list"),
        reverse("bi:integration_connector_create"),
        reverse("bi:integration_connector_detail", kwargs={"pk": integration_connector_a.pk}),
        reverse("bi:integration_connector_edit", kwargs={"pk": integration_connector_a.pk}),
        reverse("bi:integration_connector_delete", kwargs={"pk": integration_connector_a.pk}),
        reverse("bi:integration_connector_ping", kwargs={"pk": integration_connector_a.pk}),
        # 2. WarehouseSyncEndpoint (6)
        reverse("bi:warehouse_sync_endpoint_list"),
        reverse("bi:warehouse_sync_endpoint_create"),
        reverse(
            "bi:warehouse_sync_endpoint_detail", kwargs={"pk": warehouse_sync_endpoint_a.pk}
        ),
        reverse("bi:warehouse_sync_endpoint_edit", kwargs={"pk": warehouse_sync_endpoint_a.pk}),
        reverse(
            "bi:warehouse_sync_endpoint_delete", kwargs={"pk": warehouse_sync_endpoint_a.pk}
        ),
        reverse(
            "bi:warehouse_sync_endpoint_trigger", kwargs={"pk": warehouse_sync_endpoint_a.pk}
        ),
        # 3. BiWebhookSubscription (6)
        reverse("bi:bi_webhook_subscription_list"),
        reverse("bi:bi_webhook_subscription_create"),
        reverse(
            "bi:bi_webhook_subscription_detail", kwargs={"pk": bi_webhook_subscription_a.pk}
        ),
        reverse("bi:bi_webhook_subscription_edit", kwargs={"pk": bi_webhook_subscription_a.pk}),
        reverse(
            "bi:bi_webhook_subscription_delete", kwargs={"pk": bi_webhook_subscription_a.pk}
        ),
        reverse(
            "bi:bi_webhook_subscription_ping", kwargs={"pk": bi_webhook_subscription_a.pk}
        ),
        # 4. BiExtensionPlugin (6)
        reverse("bi:bi_extension_plugin_list"),
        reverse("bi:bi_extension_plugin_create"),
        reverse("bi:bi_extension_plugin_detail", kwargs={"pk": bi_extension_plugin_a.pk}),
        reverse("bi:bi_extension_plugin_edit", kwargs={"pk": bi_extension_plugin_a.pk}),
        reverse("bi:bi_extension_plugin_delete", kwargs={"pk": bi_extension_plugin_a.pk}),
        reverse("bi:bi_extension_plugin_toggle", kwargs={"pk": bi_extension_plugin_a.pk}),
    ]

    for u in urls:
        resp = anon_client.get(u)
        assert resp.status_code == 302, (
            f"Expected 302 redirect to login for URL {u}, got {resp.status_code}"
        )
        assert "/accounts/login/" in resp.url or "login" in resp.url
