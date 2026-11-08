"""Security, Multi-Tenancy, Authorization, and Tamper-Protection Test Suite for
Sub-module 10.19: Integration & API Hub (apps/bi).

Covers:
1. Cross-Tenant IDOR Defense:
   - Tenant A client accessing Tenant B objects returns 404 across detail, edit (GET/POST),
     delete (POST), and custom action (POST) for all 4 models:
     * IntegrationConnector (detail, edit, delete, ping)
     * WarehouseSyncEndpoint (detail, edit, delete, trigger)
     * BiWebhookSubscription (detail, edit, delete, ping)
     * BiExtensionPlugin (detail, edit, delete, toggle)
   - Reverse IDOR: Tenant B client accessing Tenant A objects returns 404 across all endpoints.
   - List querysets strictly isolate by tenant (zero cross-tenant data leakage).
   - Cross-tenant FK injection strictly rejected:
     * WarehouseSyncEndpointForm rejects foreign semantic_model & foreign data_mart.
     * View-level create and edit reject foreign semantic_model & foreign data_mart.
     * Defense-in-depth: widened queryset triggers reject_foreign validation error.

2. Secret Protection (Rule L20):
   - secret_token is excluded from BiWebhookSubscriptionForm.
   - Webhook secret_token cannot be overwritten via malicious POST payloads.
   - Webhook create auto-generates secure secret_token, ignoring POST injections.
   - Cleartext credentials are not prepopulated in IntegrationConnectorForm initial on edit.
   - Edit page HTML does not leak credentials in cleartext.
   - Webhook detail page masks secret token with bullet points and never renders the raw full secret.

3. Mass-Assignment Defenses:
   - Modifying tenant, number, health_status, total_messages_processed via malicious POST ignored on IntegrationConnector.
   - Modifying tenant, number, status, total_rows_synced, last_sync_duration_ms via malicious POST ignored on WarehouseSyncEndpoint.
   - Modifying tenant, number, secret_token, total_deliveries, consecutive_failures via malicious POST ignored on BiWebhookSubscription.
   - Modifying tenant, number, is_system_plugin, is_verified via malicious POST ignored on BiExtensionPlugin.
   - Elevation to system plugin or verified status blocked on plugin create.

4. Method Safety & CSRF / Unauthenticated Access:
   - Destructive and mutating endpoints enforce @require_POST and reject GET with 405 Method Not Allowed:
     * integration_connector_delete, integration_connector_ping
     * warehouse_sync_endpoint_delete, warehouse_sync_endpoint_trigger
     * bi_webhook_subscription_delete, bi_webhook_subscription_ping
     * bi_extension_plugin_delete, bi_extension_plugin_toggle
   - All 24 endpoints require authentication and redirect anonymous clients to login (302).

5. Audit Logging Verification:
   - AuditLog records verified for create, update, delete, ping, trigger, and toggle actions.
   - Verified that AuditLog records are tenant-scoped to Tenant A with actor set to admin_user.
   - Verified zero leakage of audit records to Tenant B.

6. System Plugin Tamper Protection:
   - Editing a system-bundled plugin via GET is blocked with 302 redirect and error message.
   - Editing a system-bundled plugin via POST is blocked with 302 redirect and changes discarded.
   - Deleting a system-bundled plugin via POST is blocked with 302 redirect and record preserved.
"""
import json
import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms.IntegrationHub.BiExtensionPlugins import BiExtensionPluginForm
from apps.bi.forms.IntegrationHub.BiWebhookSubscriptions import BiWebhookSubscriptionForm
from apps.bi.forms.IntegrationHub.IntegrationConnectors import IntegrationConnectorForm
from apps.bi.forms.IntegrationHub.WarehouseSyncEndpoints import WarehouseSyncEndpointForm
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
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _integrationhub_)
# ==============================================================================


def _integrationhub_sec_connector_data(**kwargs):
    """Return valid form data payload for IntegrationConnectorForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"Security Pipeline {ts}",
        "slug": f"sec-pipeline-{ts}",
        "description": "Integration connector for security testing.",
        "connector_type": "message_broker",
        "target_system": "kafka",
        "sync_direction": "outbound",
        "auth_type": "api_key",
        "message_format": "json",
        "sync_interval": "hourly",
        "status": "active",
        "is_enabled": True,
        "connection_config_raw": json.dumps(
            {"bootstrap_servers": "localhost:9092", "topic": "sec.events"}
        ),
        "auth_credentials_raw": json.dumps({"api_key": "sec_live_key_999"}),
    }
    data.update(kwargs)
    return data


def _integrationhub_sec_warehouse_sync_data(**kwargs):
    """Return valid form data payload for WarehouseSyncEndpointForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"Security Sync Endpoint {ts}",
        "slug": f"sec-sync-{ts}",
        "target_warehouse": "snowflake",
        "sync_mode": "incremental_merge",
        "destination_database": "ANALYTICS_TEST",
        "destination_schema": "TEST_SCHEMA",
        "destination_table": "TEST_TABLE",
        "auth_method": "service_account_key",
        "sync_schedule": "daily",
        "is_active": True,
        "connection_config_raw": json.dumps({"account": "sec_test_wh.us-east-1"}),
    }
    data.update(kwargs)
    return data


def _integrationhub_sec_webhook_data(**kwargs):
    """Return valid form data payload for BiWebhookSubscriptionForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"Security Incident Webhook {ts}",
        "endpoint_url": f"https://hooks.example.com/sec/{ts}",
        "payload_format": "slack_compatible",
        "max_retries": 3,
        "timeout_seconds": 10,
        "is_active": True,
        "event_types_raw": json.dumps(["kpi.threshold_breached"]),
        "custom_headers_raw": json.dumps({"Authorization": "Bearer sec_tok"}),
    }
    data.update(kwargs)
    return data


def _integrationhub_sec_plugin_data(**kwargs):
    """Return valid form data payload for BiExtensionPluginForm."""
    ts = int(timezone.now().timestamp() * 1000)
    data = {
        "name": f"Security Plugin Visual {ts}",
        "plugin_identifier": f"io.naverp.sec.{ts}",
        "version": "1.0.0",
        "plugin_type": "custom_visual",
        "category": "visualization",
        "description": "Custom visual extension plugin for security testing.",
        "author_name": "SecOps Team",
        "homepage_url": "https://sec.example.com/plugin",
        "repository_url": "https://github.com/sec/plugin",
        "license": "MIT",
        "status": "installed",
        "manifest_metadata_raw": json.dumps({"entrypoint_js": "/static/sec.js"}),
        "config_schema_raw": json.dumps({"type": "object"}),
        "current_config_raw": json.dumps({"theme": "dark"}),
        "permissions_required_raw": json.dumps(["read_semantic_layer"]),
    }
    data.update(kwargs)
    return data


def _integrationhub_sec_create_system_plugin(tenant, installed_by=None, name=None, **kwargs):
    """Create a tenant-scoped system plugin for tamper protection testing."""
    ts = int(timezone.now().timestamp() * 1000)
    defaults = {
        "tenant": tenant,
        "name": name or f"Core System Visualizer {ts}",
        "plugin_identifier": f"com.naverp.system.viz.{ts}",
        "version": "2.0.0",
        "plugin_type": "custom_visual",
        "category": "visualization",
        "description": "Protected system-bundled extension plugin.",
        "author_name": "NavERP Core Team",
        "status": "enabled",
        "is_system_plugin": True,
        "is_verified": True,
        "installed_by": installed_by,
    }
    defaults.update(kwargs)
    return BiExtensionPlugin.objects.create(**defaults)


# ==============================================================================
# 1. Cross-Tenant IDOR Defense Tests
# ==============================================================================


class TestIntegrationHubCrossTenantIDOR:
    """Verifies strict cross-tenant IDOR defense across all 4 Integration & API Hub models."""

    # --- IntegrationConnector ---

    def test_integrationhub_security_connector_idor_detail_404(
        self, client_a, client_b, integration_connector_a, integration_connector_b
    ):
        res_a = client_a.get(reverse("bi:integration_connector_detail", args=[integration_connector_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:integration_connector_detail", args=[integration_connector_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_connector_idor_edit_get_404(
        self, client_a, client_b, integration_connector_a, integration_connector_b
    ):
        res_a = client_a.get(reverse("bi:integration_connector_edit", args=[integration_connector_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:integration_connector_edit", args=[integration_connector_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_connector_idor_edit_post_404(
        self, client_a, client_b, integration_connector_a, integration_connector_b
    ):
        original_name_b = integration_connector_b.name
        payload_a = _integrationhub_sec_connector_data(name="Malicious Connector Overwrite")
        res_a = client_a.post(reverse("bi:integration_connector_edit", args=[integration_connector_b.pk]), payload_a)
        assert res_a.status_code == 404
        integration_connector_b.refresh_from_db()
        assert integration_connector_b.name == original_name_b

        original_name_a = integration_connector_a.name
        payload_b = _integrationhub_sec_connector_data(name="Reverse IDOR Overwrite")
        res_b = client_b.post(reverse("bi:integration_connector_edit", args=[integration_connector_a.pk]), payload_b)
        assert res_b.status_code == 404
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.name == original_name_a

    def test_integrationhub_security_connector_idor_delete_post_404(
        self, client_a, client_b, integration_connector_a, integration_connector_b
    ):
        res_a = client_a.post(reverse("bi:integration_connector_delete", args=[integration_connector_b.pk]))
        assert res_a.status_code == 404
        assert IntegrationConnector.objects.filter(pk=integration_connector_b.pk).exists()

        res_b = client_b.post(reverse("bi:integration_connector_delete", args=[integration_connector_a.pk]))
        assert res_b.status_code == 404
        assert IntegrationConnector.objects.filter(pk=integration_connector_a.pk).exists()

    def test_integrationhub_security_connector_idor_ping_post_404(
        self, client_a, client_b, integration_connector_a, integration_connector_b
    ):
        res_a = client_a.post(reverse("bi:integration_connector_ping", args=[integration_connector_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.post(reverse("bi:integration_connector_ping", args=[integration_connector_a.pk]))
        assert res_b.status_code == 404

    # --- WarehouseSyncEndpoint ---

    def test_integrationhub_security_warehouse_sync_idor_detail_404(
        self, client_a, client_b, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
    ):
        res_a = client_a.get(reverse("bi:warehouse_sync_endpoint_detail", args=[warehouse_sync_endpoint_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:warehouse_sync_endpoint_detail", args=[warehouse_sync_endpoint_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_warehouse_sync_idor_edit_get_404(
        self, client_a, client_b, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
    ):
        res_a = client_a.get(reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_warehouse_sync_idor_edit_post_404(
        self, client_a, client_b, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
    ):
        original_name_b = warehouse_sync_endpoint_b.name
        payload_a = _integrationhub_sec_warehouse_sync_data(name="Malicious Sync Overwrite")
        res_a = client_a.post(reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_b.pk]), payload_a)
        assert res_a.status_code == 404
        warehouse_sync_endpoint_b.refresh_from_db()
        assert warehouse_sync_endpoint_b.name == original_name_b

        original_name_a = warehouse_sync_endpoint_a.name
        payload_b = _integrationhub_sec_warehouse_sync_data(name="Reverse Sync Overwrite")
        res_b = client_b.post(reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_a.pk]), payload_b)
        assert res_b.status_code == 404
        warehouse_sync_endpoint_a.refresh_from_db()
        assert warehouse_sync_endpoint_a.name == original_name_a

    def test_integrationhub_security_warehouse_sync_idor_delete_post_404(
        self, client_a, client_b, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
    ):
        res_a = client_a.post(reverse("bi:warehouse_sync_endpoint_delete", args=[warehouse_sync_endpoint_b.pk]))
        assert res_a.status_code == 404
        assert WarehouseSyncEndpoint.objects.filter(pk=warehouse_sync_endpoint_b.pk).exists()

        res_b = client_b.post(reverse("bi:warehouse_sync_endpoint_delete", args=[warehouse_sync_endpoint_a.pk]))
        assert res_b.status_code == 404
        assert WarehouseSyncEndpoint.objects.filter(pk=warehouse_sync_endpoint_a.pk).exists()

    def test_integrationhub_security_warehouse_sync_idor_trigger_post_404(
        self, client_a, client_b, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
    ):
        res_a = client_a.post(reverse("bi:warehouse_sync_endpoint_trigger", args=[warehouse_sync_endpoint_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.post(reverse("bi:warehouse_sync_endpoint_trigger", args=[warehouse_sync_endpoint_a.pk]))
        assert res_b.status_code == 404

    # --- BiWebhookSubscription ---

    def test_integrationhub_security_webhook_idor_detail_404(
        self, client_a, client_b, bi_webhook_subscription_a, bi_webhook_subscription_b
    ):
        res_a = client_a.get(reverse("bi:bi_webhook_subscription_detail", args=[bi_webhook_subscription_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:bi_webhook_subscription_detail", args=[bi_webhook_subscription_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_webhook_idor_edit_get_404(
        self, client_a, client_b, bi_webhook_subscription_a, bi_webhook_subscription_b
    ):
        res_a = client_a.get(reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_webhook_idor_edit_post_404(
        self, client_a, client_b, bi_webhook_subscription_a, bi_webhook_subscription_b
    ):
        original_name_b = bi_webhook_subscription_b.name
        payload_a = _integrationhub_sec_webhook_data(name="Malicious Webhook Overwrite")
        res_a = client_a.post(reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_b.pk]), payload_a)
        assert res_a.status_code == 404
        bi_webhook_subscription_b.refresh_from_db()
        assert bi_webhook_subscription_b.name == original_name_b

        original_name_a = bi_webhook_subscription_a.name
        payload_b = _integrationhub_sec_webhook_data(name="Reverse Webhook Overwrite")
        res_b = client_b.post(reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_a.pk]), payload_b)
        assert res_b.status_code == 404
        bi_webhook_subscription_a.refresh_from_db()
        assert bi_webhook_subscription_a.name == original_name_a

    def test_integrationhub_security_webhook_idor_delete_post_404(
        self, client_a, client_b, bi_webhook_subscription_a, bi_webhook_subscription_b
    ):
        res_a = client_a.post(reverse("bi:bi_webhook_subscription_delete", args=[bi_webhook_subscription_b.pk]))
        assert res_a.status_code == 404
        assert BiWebhookSubscription.objects.filter(pk=bi_webhook_subscription_b.pk).exists()

        res_b = client_b.post(reverse("bi:bi_webhook_subscription_delete", args=[bi_webhook_subscription_a.pk]))
        assert res_b.status_code == 404
        assert BiWebhookSubscription.objects.filter(pk=bi_webhook_subscription_a.pk).exists()

    def test_integrationhub_security_webhook_idor_ping_post_404(
        self, client_a, client_b, bi_webhook_subscription_a, bi_webhook_subscription_b
    ):
        res_a = client_a.post(reverse("bi:bi_webhook_subscription_ping", args=[bi_webhook_subscription_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.post(reverse("bi:bi_webhook_subscription_ping", args=[bi_webhook_subscription_a.pk]))
        assert res_b.status_code == 404

    # --- BiExtensionPlugin ---

    def test_integrationhub_security_plugin_idor_detail_404(
        self, client_a, client_b, bi_extension_plugin_a, bi_extension_plugin_b
    ):
        res_a = client_a.get(reverse("bi:bi_extension_plugin_detail", args=[bi_extension_plugin_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:bi_extension_plugin_detail", args=[bi_extension_plugin_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_plugin_idor_edit_get_404(
        self, client_a, client_b, bi_extension_plugin_a, bi_extension_plugin_b
    ):
        res_a = client_a.get(reverse("bi:bi_extension_plugin_edit", args=[bi_extension_plugin_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.get(reverse("bi:bi_extension_plugin_edit", args=[bi_extension_plugin_a.pk]))
        assert res_b.status_code == 404

    def test_integrationhub_security_plugin_idor_edit_post_404(
        self, client_a, client_b, bi_extension_plugin_a, bi_extension_plugin_b
    ):
        original_name_b = bi_extension_plugin_b.name
        payload_a = _integrationhub_sec_plugin_data(name="Malicious Plugin Overwrite")
        res_a = client_a.post(reverse("bi:bi_extension_plugin_edit", args=[bi_extension_plugin_b.pk]), payload_a)
        assert res_a.status_code == 404
        bi_extension_plugin_b.refresh_from_db()
        assert bi_extension_plugin_b.name == original_name_b

        original_name_a = bi_extension_plugin_a.name
        payload_b = _integrationhub_sec_plugin_data(name="Reverse Plugin Overwrite")
        res_b = client_b.post(reverse("bi:bi_extension_plugin_edit", args=[bi_extension_plugin_a.pk]), payload_b)
        assert res_b.status_code == 404
        bi_extension_plugin_a.refresh_from_db()
        assert bi_extension_plugin_a.name == original_name_a

    def test_integrationhub_security_plugin_idor_delete_post_404(
        self, client_a, client_b, bi_extension_plugin_a, bi_extension_plugin_b
    ):
        res_a = client_a.post(reverse("bi:bi_extension_plugin_delete", args=[bi_extension_plugin_b.pk]))
        assert res_a.status_code == 404
        assert BiExtensionPlugin.objects.filter(pk=bi_extension_plugin_b.pk).exists()

        res_b = client_b.post(reverse("bi:bi_extension_plugin_delete", args=[bi_extension_plugin_a.pk]))
        assert res_b.status_code == 404
        assert BiExtensionPlugin.objects.filter(pk=bi_extension_plugin_a.pk).exists()

    def test_integrationhub_security_plugin_idor_toggle_post_404(
        self, client_a, client_b, bi_extension_plugin_a, bi_extension_plugin_b
    ):
        res_a = client_a.post(reverse("bi:bi_extension_plugin_toggle", args=[bi_extension_plugin_b.pk]))
        assert res_a.status_code == 404

        res_b = client_b.post(reverse("bi:bi_extension_plugin_toggle", args=[bi_extension_plugin_a.pk]))
        assert res_b.status_code == 404

    # --- List Queryset Zero Cross-Tenant Leakage ---

    def test_integrationhub_security_connector_list_no_cross_tenant_leakage(
        self, client_a, client_b, integration_connector_a, integration_connector_b
    ):
        res_a = client_a.get(reverse("bi:integration_connector_list"))
        assert res_a.status_code == 200
        connectors_a = list(res_a.context["connectors"])
        assert integration_connector_a in connectors_a
        assert integration_connector_b not in connectors_a

        res_b = client_b.get(reverse("bi:integration_connector_list"))
        assert res_b.status_code == 200
        connectors_b = list(res_b.context["connectors"])
        assert integration_connector_b in connectors_b
        assert integration_connector_a not in connectors_b

    def test_integrationhub_security_warehouse_sync_list_no_cross_tenant_leakage(
        self, client_a, client_b, warehouse_sync_endpoint_a, warehouse_sync_endpoint_b
    ):
        res_a = client_a.get(reverse("bi:warehouse_sync_endpoint_list"))
        assert res_a.status_code == 200
        endpoints_a = list(res_a.context["page_obj"])
        assert warehouse_sync_endpoint_a in endpoints_a
        assert warehouse_sync_endpoint_b not in endpoints_a

        res_b = client_b.get(reverse("bi:warehouse_sync_endpoint_list"))
        assert res_b.status_code == 200
        endpoints_b = list(res_b.context["page_obj"])
        assert warehouse_sync_endpoint_b in endpoints_b
        assert warehouse_sync_endpoint_a not in endpoints_b

    def test_integrationhub_security_webhook_list_no_cross_tenant_leakage(
        self, client_a, client_b, bi_webhook_subscription_a, bi_webhook_subscription_b
    ):
        res_a = client_a.get(reverse("bi:bi_webhook_subscription_list"))
        assert res_a.status_code == 200
        webhooks_a = list(res_a.context["page_obj"])
        assert bi_webhook_subscription_a in webhooks_a
        assert bi_webhook_subscription_b not in webhooks_a

        res_b = client_b.get(reverse("bi:bi_webhook_subscription_list"))
        assert res_b.status_code == 200
        webhooks_b = list(res_b.context["page_obj"])
        assert bi_webhook_subscription_b in webhooks_b
        assert bi_webhook_subscription_a not in webhooks_b

    def test_integrationhub_security_plugin_list_no_cross_tenant_leakage(
        self, client_a, client_b, bi_extension_plugin_a, bi_extension_plugin_b
    ):
        res_a = client_a.get(reverse("bi:bi_extension_plugin_list"))
        assert res_a.status_code == 200
        plugins_a = list(res_a.context["page_obj"])
        assert bi_extension_plugin_a in plugins_a
        assert bi_extension_plugin_b not in plugins_a

        res_b = client_b.get(reverse("bi:bi_extension_plugin_list"))
        assert res_b.status_code == 200
        plugins_b = list(res_b.context["page_obj"])
        assert bi_extension_plugin_b in plugins_b
        assert bi_extension_plugin_a not in plugins_b

    # --- Cross-Tenant FK Injection Defenses ---

    def test_integrationhub_security_warehouse_sync_rejects_foreign_semantic_model_in_form(
        self, tenant_a, semantic_model_b
    ):
        data = _integrationhub_sec_warehouse_sync_data(semantic_model=str(semantic_model_b.pk))
        form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "semantic_model" in form.errors

    def test_integrationhub_security_warehouse_sync_rejects_foreign_data_mart_in_form(
        self, tenant_a, data_mart_b
    ):
        data = _integrationhub_sec_warehouse_sync_data(data_mart=str(data_mart_b.pk))
        form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "data_mart" in form.errors

    def test_integrationhub_security_warehouse_sync_rejects_foreign_semantic_model_in_view_create(
        self, client_a, tenant_a, semantic_model_b
    ):
        data = _integrationhub_sec_warehouse_sync_data(
            name="Injected Semantic Sync",
            semantic_model=str(semantic_model_b.pk),
        )
        res = client_a.post(reverse("bi:warehouse_sync_endpoint_create"), data)
        assert res.status_code == 200
        assert not WarehouseSyncEndpoint.objects.filter(
            tenant=tenant_a,
            name="Injected Semantic Sync",
        ).exists()

    def test_integrationhub_security_warehouse_sync_rejects_foreign_data_mart_in_view_create(
        self, client_a, tenant_a, data_mart_b
    ):
        data = _integrationhub_sec_warehouse_sync_data(
            name="Injected Mart Sync",
            data_mart=str(data_mart_b.pk),
        )
        res = client_a.post(reverse("bi:warehouse_sync_endpoint_create"), data)
        assert res.status_code == 200
        assert not WarehouseSyncEndpoint.objects.filter(
            tenant=tenant_a,
            name="Injected Mart Sync",
        ).exists()

    def test_integrationhub_security_warehouse_sync_rejects_foreign_fk_in_view_edit(
        self, client_a, warehouse_sync_endpoint_a, semantic_model_b, data_mart_b
    ):
        data = _integrationhub_sec_warehouse_sync_data(
            name=warehouse_sync_endpoint_a.name,
            slug=warehouse_sync_endpoint_a.slug,
            semantic_model=str(semantic_model_b.pk),
            data_mart=str(data_mart_b.pk),
        )
        res = client_a.post(
            reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_a.pk]),
            data,
        )
        assert res.status_code == 200
        warehouse_sync_endpoint_a.refresh_from_db()
        assert warehouse_sync_endpoint_a.semantic_model != semantic_model_b
        assert warehouse_sync_endpoint_a.data_mart != data_mart_b

    def test_integrationhub_security_warehouse_sync_form_reject_foreign_defense_in_depth(
        self, tenant_a, semantic_model_b, data_mart_b
    ):
        """Defense-in-depth: if ModelChoiceField querysets are widened, reject_foreign catches foreign PKs."""
        data = _integrationhub_sec_warehouse_sync_data(
            semantic_model=str(semantic_model_b.pk),
            data_mart=str(data_mart_b.pk),
        )
        form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
        # Artificially widen querysets to include cross-tenant objects
        form.fields["semantic_model"].queryset = SemanticModel.objects.all()
        form.fields["data_mart"].queryset = DataMart.objects.all()

        assert not form.is_valid()
        assert "semantic_model" in form.errors
        assert "data_mart" in form.errors
        assert any("workspace" in str(err).lower() for err in form.errors["semantic_model"])
        assert any("workspace" in str(err).lower() for err in form.errors["data_mart"])


# ==============================================================================
# 2. Secret Protection Tests (Rule L20)
# ==============================================================================


class TestIntegrationHubSecretProtection:
    """Verifies that cleartext tokens, API keys, and secrets are strictly protected."""

    def test_integrationhub_security_webhook_form_excludes_secret_token(self):
        form = BiWebhookSubscriptionForm()
        assert "secret_token" not in form.fields
        assert "secret_token" not in BiWebhookSubscriptionForm.Meta.fields

    def test_integrationhub_security_webhook_secret_token_immutable_via_post(
        self, client_a, bi_webhook_subscription_a
    ):
        original_token = bi_webhook_subscription_a.secret_token
        assert original_token.startswith("whsec_")

        data = _integrationhub_sec_webhook_data(
            name="Attempted Token Override",
            secret_token="hacked_whsec_malicious_token",
        )
        res = client_a.post(
            reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_a.pk]),
            data,
        )
        assert res.status_code == 302
        bi_webhook_subscription_a.refresh_from_db()
        assert bi_webhook_subscription_a.name == "Attempted Token Override"
        assert bi_webhook_subscription_a.secret_token == original_token
        assert bi_webhook_subscription_a.secret_token != "hacked_whsec_malicious_token"

    def test_integrationhub_security_webhook_create_auto_generates_secret_token_ignoring_post(
        self, client_a, tenant_a
    ):
        data = _integrationhub_sec_webhook_data(
            name="New Safe Webhook Subscription",
            secret_token="injected_cleartext_secret",
        )
        res = client_a.post(reverse("bi:bi_webhook_subscription_create"), data)
        assert res.status_code == 302
        webhook = BiWebhookSubscription.objects.get(
            tenant=tenant_a,
            name="New Safe Webhook Subscription",
        )
        assert webhook.secret_token.startswith("whsec_")
        assert webhook.secret_token != "injected_cleartext_secret"
        assert len(webhook.secret_token) > 20

    def test_integrationhub_security_connector_form_initial_suppresses_credentials(
        self, tenant_a, integration_connector_a
    ):
        integration_connector_a.auth_credentials = {"api_key": "sec_test_key_123"}
        integration_connector_a.save()

        form = IntegrationConnectorForm(instance=integration_connector_a, tenant=tenant_a)
        assert "auth_credentials_raw" in form.fields
        # Secret credentials MUST NOT be prepopulated in form initial on edit
        assert not form.fields["auth_credentials_raw"].initial

    def test_integrationhub_security_connector_edit_view_masks_credentials_html(
        self, client_a, integration_connector_a
    ):
        integration_connector_a.auth_credentials = {"api_key": "sec_super_secret_payload_99"}
        integration_connector_a.save()

        res = client_a.get(reverse("bi:integration_connector_edit", args=[integration_connector_a.pk]))
        assert res.status_code == 200
        html = res.content.decode()
        assert "sec_super_secret_payload_99" not in html

    def test_integrationhub_security_webhook_detail_masks_secret_token(
        self, client_a, bi_webhook_subscription_a
    ):
        res = client_a.get(
            reverse("bi:bi_webhook_subscription_detail", args=[bi_webhook_subscription_a.pk])
        )
        assert res.status_code == 200
        html = res.content.decode()

        # The full secret token MUST NOT be exposed in cleartext
        assert bi_webhook_subscription_a.secret_token not in html
        # Detail template masks the secret with bullet indicators
        assert "••••••••••••••••••••••••" in html
        # First 10 prefix characters are displayed for verification
        assert bi_webhook_subscription_a.secret_token[:10] in html


# ==============================================================================
# 3. Mass-Assignment Defense Tests
# ==============================================================================


class TestIntegrationHubMassAssignmentDefenses:
    """Verifies that read-only, system, and tenant-identifying fields cannot be spoofed via POST."""

    def test_integrationhub_security_connector_mass_assignment_defense(
        self, client_a, tenant_a, tenant_b, integration_connector_a
    ):
        original_number = integration_connector_a.number
        data = _integrationhub_sec_connector_data(
            name="Renamed Safe Connector",
            tenant=tenant_b.pk,
            number="BINT-99999",
            health_status="unreachable",
            total_messages_processed=999999,
        )
        res = client_a.post(
            reverse("bi:integration_connector_edit", args=[integration_connector_a.pk]),
            data,
        )
        assert res.status_code == 302
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.name == "Renamed Safe Connector"
        assert integration_connector_a.tenant == tenant_a
        assert integration_connector_a.number == original_number
        assert integration_connector_a.total_messages_processed == 0

    def test_integrationhub_security_warehouse_sync_mass_assignment_defense(
        self, client_a, tenant_a, tenant_b, warehouse_sync_endpoint_a
    ):
        original_number = warehouse_sync_endpoint_a.number
        data = _integrationhub_sec_warehouse_sync_data(
            name="Renamed Safe Sync",
            tenant=tenant_b.pk,
            number="BSNC-99999",
            status="syncing",
            total_rows_synced=888888,
            last_rows_synced=77777,
            last_sync_duration_ms=123,
        )
        res = client_a.post(
            reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_a.pk]),
            data,
        )
        assert res.status_code == 302
        warehouse_sync_endpoint_a.refresh_from_db()
        assert warehouse_sync_endpoint_a.name == "Renamed Safe Sync"
        assert warehouse_sync_endpoint_a.tenant == tenant_a
        assert warehouse_sync_endpoint_a.number == original_number
        assert warehouse_sync_endpoint_a.status == "idle"
        assert warehouse_sync_endpoint_a.total_rows_synced == 0
        assert warehouse_sync_endpoint_a.last_rows_synced == 0
        assert warehouse_sync_endpoint_a.last_sync_duration_ms == 0

    def test_integrationhub_security_webhook_mass_assignment_defense(
        self, client_a, tenant_a, tenant_b, bi_webhook_subscription_a
    ):
        original_number = bi_webhook_subscription_a.number
        data = _integrationhub_sec_webhook_data(
            name="Renamed Safe Webhook",
            tenant=tenant_b.pk,
            number="BWHK-99999",
            secret_token="injected_secret_token",
            total_deliveries=999999,
            consecutive_failures=50,
            status="suspended",
        )
        res = client_a.post(
            reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_a.pk]),
            data,
        )
        assert res.status_code == 302
        bi_webhook_subscription_a.refresh_from_db()
        assert bi_webhook_subscription_a.name == "Renamed Safe Webhook"
        assert bi_webhook_subscription_a.tenant == tenant_a
        assert bi_webhook_subscription_a.number == original_number
        assert bi_webhook_subscription_a.status == "active"
        assert bi_webhook_subscription_a.total_deliveries == 0
        assert bi_webhook_subscription_a.consecutive_failures == 0

    def test_integrationhub_security_plugin_mass_assignment_defense(
        self, client_a, tenant_a, tenant_b, bi_extension_plugin_a
    ):
        original_number = bi_extension_plugin_a.number
        data = _integrationhub_sec_plugin_data(
            name="Renamed Safe Plugin",
            tenant=tenant_b.pk,
            number="BEXT-99999",
            is_system_plugin=True,
            is_verified=True,
        )
        res = client_a.post(
            reverse("bi:bi_extension_plugin_edit", args=[bi_extension_plugin_a.pk]),
            data,
        )
        assert res.status_code == 302
        bi_extension_plugin_a.refresh_from_db()
        assert bi_extension_plugin_a.name == "Renamed Safe Plugin"
        assert bi_extension_plugin_a.tenant == tenant_a
        assert bi_extension_plugin_a.number == original_number
        assert bi_extension_plugin_a.is_system_plugin is False

    def test_integrationhub_security_plugin_create_cannot_elevate_to_system_or_verified(
        self, client_a, tenant_a, tenant_b
    ):
        data = _integrationhub_sec_plugin_data(
            name="Unauthorized Privileged Plugin",
            tenant=tenant_b.pk,
            is_system_plugin=True,
            is_verified=True,
        )
        res = client_a.post(reverse("bi:bi_extension_plugin_create"), data)
        assert res.status_code == 302
        plugin = BiExtensionPlugin.objects.get(
            tenant=tenant_a,
            name="Unauthorized Privileged Plugin",
        )
        assert plugin.tenant == tenant_a
        assert plugin.is_system_plugin is False
        assert plugin.is_verified is False


# ==============================================================================
# 4. Method Safety & Unauthenticated Access Tests
# ==============================================================================


class TestIntegrationHubMethodSafetyAndAuth:
    """Verifies HTTP method safety (@require_POST) and authentication enforcement."""

    def test_integrationhub_security_destructive_actions_reject_get_405(
        self, client_a, integration_connector_a, warehouse_sync_endpoint_a, bi_webhook_subscription_a, bi_extension_plugin_a
    ):
        destructive_urls = [
            reverse("bi:integration_connector_delete", args=[integration_connector_a.pk]),
            reverse("bi:warehouse_sync_endpoint_delete", args=[warehouse_sync_endpoint_a.pk]),
            reverse("bi:bi_webhook_subscription_delete", args=[bi_webhook_subscription_a.pk]),
            reverse("bi:bi_extension_plugin_delete", args=[bi_extension_plugin_a.pk]),
        ]
        for url in destructive_urls:
            res = client_a.get(url)
            assert res.status_code == 405

    def test_integrationhub_security_mutating_actions_reject_get_405(
        self, client_a, integration_connector_a, warehouse_sync_endpoint_a, bi_webhook_subscription_a, bi_extension_plugin_a
    ):
        mutating_urls = [
            reverse("bi:integration_connector_ping", args=[integration_connector_a.pk]),
            reverse("bi:warehouse_sync_endpoint_trigger", args=[warehouse_sync_endpoint_a.pk]),
            reverse("bi:bi_webhook_subscription_ping", args=[bi_webhook_subscription_a.pk]),
            reverse("bi:bi_extension_plugin_toggle", args=[bi_extension_plugin_a.pk]),
        ]
        for url in mutating_urls:
            res = client_a.get(url)
            assert res.status_code == 405

    def test_integrationhub_security_anonymous_access_redirects_to_login(
        self, client, integration_connector_a, warehouse_sync_endpoint_a, bi_webhook_subscription_a, bi_extension_plugin_a
    ):
        all_routes = [
            # IntegrationConnector
            reverse("bi:integration_connector_list"),
            reverse("bi:integration_connector_create"),
            reverse("bi:integration_connector_detail", args=[integration_connector_a.pk]),
            reverse("bi:integration_connector_edit", args=[integration_connector_a.pk]),
            reverse("bi:integration_connector_delete", args=[integration_connector_a.pk]),
            reverse("bi:integration_connector_ping", args=[integration_connector_a.pk]),
            # WarehouseSyncEndpoint
            reverse("bi:warehouse_sync_endpoint_list"),
            reverse("bi:warehouse_sync_endpoint_create"),
            reverse("bi:warehouse_sync_endpoint_detail", args=[warehouse_sync_endpoint_a.pk]),
            reverse("bi:warehouse_sync_endpoint_edit", args=[warehouse_sync_endpoint_a.pk]),
            reverse("bi:warehouse_sync_endpoint_delete", args=[warehouse_sync_endpoint_a.pk]),
            reverse("bi:warehouse_sync_endpoint_trigger", args=[warehouse_sync_endpoint_a.pk]),
            # BiWebhookSubscription
            reverse("bi:bi_webhook_subscription_list"),
            reverse("bi:bi_webhook_subscription_create"),
            reverse("bi:bi_webhook_subscription_detail", args=[bi_webhook_subscription_a.pk]),
            reverse("bi:bi_webhook_subscription_edit", args=[bi_webhook_subscription_a.pk]),
            reverse("bi:bi_webhook_subscription_delete", args=[bi_webhook_subscription_a.pk]),
            reverse("bi:bi_webhook_subscription_ping", args=[bi_webhook_subscription_a.pk]),
            # BiExtensionPlugin
            reverse("bi:bi_extension_plugin_list"),
            reverse("bi:bi_extension_plugin_create"),
            reverse("bi:bi_extension_plugin_detail", args=[bi_extension_plugin_a.pk]),
            reverse("bi:bi_extension_plugin_edit", args=[bi_extension_plugin_a.pk]),
            reverse("bi:bi_extension_plugin_delete", args=[bi_extension_plugin_a.pk]),
            reverse("bi:bi_extension_plugin_toggle", args=[bi_extension_plugin_a.pk]),
        ]
        for url in all_routes:
            res_get = client.get(url)
            assert res_get.status_code == 302
            assert "/login/" in res_get["Location"]

            res_post = client.post(url, {})
            assert res_post.status_code == 302
            assert "/login/" in res_post["Location"]


# ==============================================================================
# 5. Audit Logging Verification Tests
# ==============================================================================


class TestIntegrationHubAuditLogging:
    """Verifies that AuditLog rows are recorded with tenant isolation for all CRUD and actions."""

    def test_integrationhub_security_connector_audit_logs(
        self, client_a, admin_user, tenant_a
    ):
        # 1. Create
        data = _integrationhub_sec_connector_data(name="Audit Test Connector")
        res_create = client_a.post(reverse("bi:integration_connector_create"), data)
        assert res_create.status_code == 302
        connector = IntegrationConnector.objects.get(tenant=tenant_a, name="Audit Test Connector")

        log_create = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="create",
            object_id=connector.pk,
        ).first()
        assert log_create is not None

        # 2. Update
        edit_data = _integrationhub_sec_connector_data(name="Audit Test Connector Updated")
        res_edit = client_a.post(reverse("bi:integration_connector_edit", args=[connector.pk]), edit_data)
        assert res_edit.status_code == 302

        log_update = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="update",
            object_id=connector.pk,
        ).first()
        assert log_update is not None

        # 3. Action (Ping)
        res_ping = client_a.post(reverse("bi:integration_connector_ping", args=[connector.pk]))
        assert res_ping.status_code == 302

        log_action = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="action",
            object_id=connector.pk,
        ).first()
        assert log_action is not None
        assert log_action.changes.get("health_status") == "healthy"

        # 4. Delete
        conn_pk = connector.pk
        res_del = client_a.post(reverse("bi:integration_connector_delete", args=[conn_pk]))
        assert res_del.status_code == 302

        log_del = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="delete",
            object_id=conn_pk,
        ).first()
        assert log_del is not None

    def test_integrationhub_security_warehouse_sync_audit_logs(
        self, client_a, admin_user, tenant_a
    ):
        # 1. Create
        data = _integrationhub_sec_warehouse_sync_data(name="Audit Warehouse Sync")
        res_create = client_a.post(reverse("bi:warehouse_sync_endpoint_create"), data)
        assert res_create.status_code == 302
        endpoint = WarehouseSyncEndpoint.objects.get(tenant=tenant_a, name="Audit Warehouse Sync")

        log_create = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="create",
            object_id=endpoint.pk,
        ).first()
        assert log_create is not None

        # 2. Update
        edit_data = _integrationhub_sec_warehouse_sync_data(name="Audit Warehouse Sync Updated")
        res_edit = client_a.post(reverse("bi:warehouse_sync_endpoint_edit", args=[endpoint.pk]), edit_data)
        assert res_edit.status_code == 302

        log_update = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="update",
            object_id=endpoint.pk,
        ).first()
        assert log_update is not None

        # 3. Action (Trigger)
        res_trigger = client_a.post(reverse("bi:warehouse_sync_endpoint_trigger", args=[endpoint.pk]))
        assert res_trigger.status_code == 302

        log_action = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="action",
            object_id=endpoint.pk,
        ).first()
        assert log_action is not None
        assert log_action.changes.get("status") == "success"

        # 4. Delete
        ep_pk = endpoint.pk
        res_del = client_a.post(reverse("bi:warehouse_sync_endpoint_delete", args=[ep_pk]))
        assert res_del.status_code == 302

        log_del = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="delete",
            object_id=ep_pk,
        ).first()
        assert log_del is not None

    def test_integrationhub_security_webhook_audit_logs(
        self, client_a, admin_user, tenant_a
    ):
        # 1. Create
        data = _integrationhub_sec_webhook_data(name="Audit Webhook")
        res_create = client_a.post(reverse("bi:bi_webhook_subscription_create"), data)
        assert res_create.status_code == 302
        webhook = BiWebhookSubscription.objects.get(tenant=tenant_a, name="Audit Webhook")

        log_create = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="create",
            object_id=webhook.pk,
        ).first()
        assert log_create is not None

        # 2. Update
        edit_data = _integrationhub_sec_webhook_data(name="Audit Webhook Updated")
        res_edit = client_a.post(reverse("bi:bi_webhook_subscription_edit", args=[webhook.pk]), edit_data)
        assert res_edit.status_code == 302

        log_update = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="update",
            object_id=webhook.pk,
        ).first()
        assert log_update is not None

        # 3. Action (Ping)
        res_ping = client_a.post(reverse("bi:bi_webhook_subscription_ping", args=[webhook.pk]))
        assert res_ping.status_code == 302

        log_action = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="action",
            object_id=webhook.pk,
        ).first()
        assert log_action is not None
        assert log_action.changes.get("response_code") == 200

        # 4. Delete
        wh_pk = webhook.pk
        res_del = client_a.post(reverse("bi:bi_webhook_subscription_delete", args=[wh_pk]))
        assert res_del.status_code == 302

        log_del = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="delete",
            object_id=wh_pk,
        ).first()
        assert log_del is not None

    def test_integrationhub_security_plugin_audit_logs(
        self, client_a, admin_user, tenant_a
    ):
        # 1. Create
        data = _integrationhub_sec_plugin_data(name="Audit Plugin")
        res_create = client_a.post(reverse("bi:bi_extension_plugin_create"), data)
        assert res_create.status_code == 302
        plugin = BiExtensionPlugin.objects.get(tenant=tenant_a, name="Audit Plugin")

        log_create = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="create",
            object_id=plugin.pk,
        ).first()
        assert log_create is not None

        # 2. Update
        edit_data = _integrationhub_sec_plugin_data(name="Audit Plugin Updated")
        res_edit = client_a.post(reverse("bi:bi_extension_plugin_edit", args=[plugin.pk]), edit_data)
        assert res_edit.status_code == 302

        log_update = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="update",
            object_id=plugin.pk,
        ).first()
        assert log_update is not None

        # 3. Action (Toggle)
        res_toggle = client_a.post(reverse("bi:bi_extension_plugin_toggle", args=[plugin.pk]))
        assert res_toggle.status_code == 302

        log_action = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="action",
            object_id=plugin.pk,
        ).first()
        assert log_action is not None
        assert "status" in log_action.changes

        # 4. Delete
        pl_pk = plugin.pk
        res_del = client_a.post(reverse("bi:bi_extension_plugin_delete", args=[pl_pk]))
        assert res_del.status_code == 302

        log_del = AuditLog.objects.filter(
            tenant=tenant_a,
            user=admin_user,
            action="delete",
            object_id=pl_pk,
        ).first()
        assert log_del is not None

    def test_integrationhub_security_audit_logs_zero_leakage_to_tenant_b(
        self, client_a, tenant_a, tenant_b, integration_connector_a
    ):
        initial_tenant_b_logs = AuditLog.objects.filter(tenant=tenant_b).count()

        # Perform mutations as Tenant A
        client_a.post(reverse("bi:integration_connector_ping", args=[integration_connector_a.pk]))
        client_a.post(
            reverse("bi:integration_connector_edit", args=[integration_connector_a.pk]),
            _integrationhub_sec_connector_data(name="Safe Edit Audit Check"),
        )

        # Confirm zero audit logs were created under Tenant B
        final_tenant_b_logs = AuditLog.objects.filter(tenant=tenant_b).count()
        assert final_tenant_b_logs == initial_tenant_b_logs


# ==============================================================================
# 6. System Plugin Tamper Protection Tests
# ==============================================================================


class TestIntegrationHubSystemPluginTamperProtection:
    """Verifies that system-bundled extension plugins cannot be modified or deleted."""

    def test_integrationhub_security_system_plugin_edit_blocked_get(
        self, client_a, tenant_a, admin_user
    ):
        system_plugin = _integrationhub_sec_create_system_plugin(tenant_a, installed_by=admin_user)
        url = reverse("bi:bi_extension_plugin_edit", args=[system_plugin.pk])

        res = client_a.get(url, follow=True)
        assert res.status_code == 200
        # Redirected to detail page
        assert res.resolver_match.url_name == "bi_extension_plugin_detail"
        # Error message rendered
        messages = list(res.context["messages"])
        assert any("System-bundled extension plugins cannot be modified" in m.message for m in messages)

    def test_integrationhub_security_system_plugin_edit_blocked_post(
        self, client_a, tenant_a, admin_user
    ):
        system_plugin = _integrationhub_sec_create_system_plugin(tenant_a, installed_by=admin_user)
        original_name = system_plugin.name
        url = reverse("bi:bi_extension_plugin_edit", args=[system_plugin.pk])

        tampered_data = _integrationhub_sec_plugin_data(name="Maliciously Tampered System Plugin")
        res = client_a.post(url, tampered_data, follow=True)
        assert res.status_code == 200
        assert res.resolver_match.url_name == "bi_extension_plugin_detail"

        messages = list(res.context["messages"])
        assert any("System-bundled extension plugins cannot be modified" in m.message for m in messages)

        # Confirm data in database was NOT modified
        system_plugin.refresh_from_db()
        assert system_plugin.name == original_name
        assert system_plugin.name != "Maliciously Tampered System Plugin"

    def test_integrationhub_security_system_plugin_delete_blocked_post(
        self, client_a, tenant_a, admin_user
    ):
        system_plugin = _integrationhub_sec_create_system_plugin(tenant_a, installed_by=admin_user)
        url = reverse("bi:bi_extension_plugin_delete", args=[system_plugin.pk])

        res = client_a.post(url, follow=True)
        assert res.status_code == 200
        assert res.resolver_match.url_name == "bi_extension_plugin_detail"

        messages = list(res.context["messages"])
        assert any("System-bundled extension plugins cannot be deleted" in m.message for m in messages)

        # Confirm system plugin remains intact in database
        assert BiExtensionPlugin.objects.filter(pk=system_plugin.pk).exists()
