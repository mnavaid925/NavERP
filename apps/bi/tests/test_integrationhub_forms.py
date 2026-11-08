"""Unit tests for Sub-module 10.19 Integration & API Hub forms.

Forms covered:
- IntegrationConnectorForm (IntegrationConnector)
- WarehouseSyncEndpointForm (WarehouseSyncEndpoint)
- BiWebhookSubscriptionForm (BiWebhookSubscription)
- BiExtensionPluginForm (BiExtensionPlugin)
"""
import json
import os

import pytest
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.bi.forms import (
    BiExtensionPluginForm,
    BiWebhookSubscriptionForm,
    IntegrationConnectorForm,
    WarehouseSyncEndpointForm,
)
from apps.bi.models import (
    BiExtensionPlugin,
    BiWebhookSubscription,
    DataMart,
    IntegrationConnector,
    SemanticModel,
    WarehouseSyncEndpoint,
)


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _integrationhub_)
# ---------------------------------------------------------------------------


def _integrationhub_valid_connector_data(**kwargs):
    """Helper returning a valid data dictionary for IntegrationConnectorForm."""
    data = {
        "name": "Finance GL Reverse ETL Pipeline",
        "slug": "finance-gl-reverse-etl",
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
            {"bootstrap_servers": "kafka.internal:9092", "topic": "erp.gl.events", "batch_size": 250}
        ),
        "auth_credentials_raw": json.dumps(
            {"api_key": "sec_live_abcdef123456", "header_name": "X-API-Key"}
        ),
    }
    data.update(kwargs)
    return data


def _integrationhub_valid_warehouse_sync_data(semantic_model=None, data_mart=None, **kwargs):
    """Helper returning a valid data dictionary for WarehouseSyncEndpointForm."""
    data = {
        "name": "Snowflake Executive Metrics Sync",
        "slug": "snowflake-exec-metrics-sync",
        "target_warehouse": "snowflake",
        "sync_mode": "incremental_merge",
        "destination_database": "ANALYTICS_PROD",
        "destination_schema": "NAVERP_EXPORTS",
        "destination_table": "DIM_CUSTOMERS",
        "auth_method": "service_account_key",
        "sync_schedule": "daily",
        "is_active": True,
        "connection_config_raw": json.dumps(
            {"account": "xy12345.us-east-1", "warehouse": "COMPUTE_WH", "role": "DATA_ANALYST"}
        ),
    }
    if semantic_model:
        data["semantic_model"] = semantic_model.pk
    if data_mart:
        data["data_mart"] = data_mart.pk
    data.update(kwargs)
    return data


def _integrationhub_valid_webhook_data(**kwargs):
    """Helper returning a valid data dictionary for BiWebhookSubscriptionForm."""
    data = {
        "name": "Slack Critical Incident Webhook",
        "endpoint_url": getattr(
            settings, "SLACK_WEBHOOK_URL", ""
        )
        or os.getenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/mock/dummy/test-webhook"),
        "payload_format": "slack_compatible",
        "max_retries": 4,
        "timeout_seconds": 15,
        "is_active": True,
        "event_types_raw": json.dumps(["kpi.threshold_breached", "anomaly.detected"]),
        "custom_headers_raw": json.dumps(
            {"Authorization": "Bearer ext_token_test", "X-Service-Name": "NavERP-BI"}
        ),
    }
    data.update(kwargs)
    return data


def _integrationhub_valid_plugin_data(**kwargs):
    """Helper returning a valid data dictionary for BiExtensionPluginForm."""
    data = {
        "name": "ECharts Sankey Visualizer Extension",
        "plugin_identifier": "io.naverp.visuals.echarts-sankey",
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
            {"entrypoint_js": "/static/bi/plugins/sankey.js", "min_naverp_version": "1.0.0"}
        ),
        "config_schema_raw": json.dumps(
            {"type": "object", "properties": {"theme": {"type": "string"}}}
        ),
        "current_config_raw": json.dumps(
            {"theme": "dark", "node_width": 24}
        ),
        "permissions_required_raw": json.dumps(
            ["read_semantic_layer", "render_canvas_ui"]
        ),
    }
    data.update(kwargs)
    return data


# ===========================================================================
# 1. System Field Exclusions Tests (L20 / Security Standards)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_connector_system_field_exclusions():
    """Verify system-managed and sensitive fields are excluded from IntegrationConnectorForm."""
    form = IntegrationConnectorForm()
    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "last_sync_at",
        "last_heartbeat_at",
        "total_messages_processed",
        "error_message",
        "created_by",
        "auth_credentials",
        "connection_config",
    ]
    for field in excluded_fields:
        assert field not in form.fields, (
            f"Security violation: field '{field}' must not be exposed in IntegrationConnectorForm"
        )


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_system_field_exclusions():
    """Verify system-managed and execution metric fields are excluded from WarehouseSyncEndpointForm."""
    form = WarehouseSyncEndpointForm()
    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "last_sync_at",
        "total_rows_synced",
        "last_sync_duration_ms",
        "last_rows_synced",
        "last_error_message",
        "status",
        "owner",
        "connection_config",
    ]
    for field in excluded_fields:
        assert field not in form.fields, (
            f"Security violation: field '{field}' must not be exposed in WarehouseSyncEndpointForm"
        )


@pytest.mark.django_db
def test_integrationhub_forms_webhook_system_field_exclusions():
    """Verify secret tokens and runtime delivery counters are excluded from BiWebhookSubscriptionForm."""
    form = BiWebhookSubscriptionForm()
    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "secret_token",
        "total_deliveries",
        "consecutive_failures",
        "status",
        "last_triggered_at",
        "last_response_code",
        "last_response_time_ms",
        "last_error_log",
        "created_by",
        "event_types",
        "custom_headers",
    ]
    for field in excluded_fields:
        assert field not in form.fields, (
            f"Security violation: field '{field}' must not be exposed in BiWebhookSubscriptionForm"
        )


@pytest.mark.django_db
def test_integrationhub_forms_plugin_system_field_exclusions():
    """Verify system verification badges and administrative flags are excluded from BiExtensionPluginForm."""
    form = BiExtensionPluginForm()
    excluded_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "is_verified",
        "is_system_plugin",
        "installed_at",
        "installed_by",
        "manifest_metadata",
        "config_schema",
        "current_config",
        "permissions_required",
    ]
    for field in excluded_fields:
        assert field not in form.fields, (
            f"Security violation: field '{field}' must not be exposed in BiExtensionPluginForm"
        )


@pytest.mark.django_db
def test_integrationhub_forms_comprehensive_system_field_exclusions_contract():
    """Verify the exact required system exclusions list across all four Integration Hub forms."""
    req_exclusions = {
        "tenant": [IntegrationConnectorForm, WarehouseSyncEndpointForm, BiWebhookSubscriptionForm, BiExtensionPluginForm],
        "number": [IntegrationConnectorForm, WarehouseSyncEndpointForm, BiWebhookSubscriptionForm, BiExtensionPluginForm],
        "created_at": [IntegrationConnectorForm, WarehouseSyncEndpointForm, BiWebhookSubscriptionForm, BiExtensionPluginForm],
        "updated_at": [IntegrationConnectorForm, WarehouseSyncEndpointForm, BiWebhookSubscriptionForm, BiExtensionPluginForm],
        "total_messages_processed": [IntegrationConnectorForm],
        "total_rows_synced": [WarehouseSyncEndpointForm],
        "total_deliveries": [BiWebhookSubscriptionForm],
        "secret_token": [BiWebhookSubscriptionForm],
        "is_verified": [BiExtensionPluginForm],
    }
    for field_name, form_classes in req_exclusions.items():
        for form_cls in form_classes:
            f = form_cls()
            assert field_name not in f.fields, (
                f"Field '{field_name}' must be excluded from {form_cls.__name__}"
            )


# ===========================================================================
# 2. Clean Methods & JSON Validation Tests
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_connector_json_config_valid(tenant_a):
    """Verify valid JSON dictionary parses cleanly in connection_config_raw."""
    data = _integrationhub_valid_connector_data(
        connection_config_raw='{"bootstrap_servers": "kafka.internal:9092", "topic": "gl.events"}'
    )
    form = IntegrationConnectorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data["connection_config_raw"] == {
        "bootstrap_servers": "kafka.internal:9092",
        "topic": "gl.events",
    }


@pytest.mark.django_db
def test_integrationhub_forms_connector_json_config_invalid_syntax(tenant_a):
    """Verify invalid JSON syntax triggers ValidationError on connection_config_raw."""
    data = _integrationhub_valid_connector_data(
        connection_config_raw='{"bootstrap_servers": "kafka.internal:9092", invalid_json}'
    )
    form = IntegrationConnectorForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "connection_config_raw" in form.errors
    assert "Invalid JSON syntax" in form.errors["connection_config_raw"][0]


@pytest.mark.django_db
def test_integrationhub_forms_connector_json_config_not_a_dict(tenant_a):
    """Verify JSON array or scalar triggers ValidationError requiring a JSON dictionary."""
    for invalid_payload in ['["server1", "server2"]', '"just_a_string"', '12345']:
        data = _integrationhub_valid_connector_data(connection_config_raw=invalid_payload)
        form = IntegrationConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "connection_config_raw" in form.errors
        assert "must be a JSON object (dictionary)" in form.errors["connection_config_raw"][0]


@pytest.mark.django_db
def test_integrationhub_forms_connector_json_config_empty(tenant_a):
    """Verify empty or whitespace connection_config_raw returns empty dictionary."""
    for empty_val in ["", "   ", None]:
        data = _integrationhub_valid_connector_data(connection_config_raw=empty_val)
        form = IntegrationConnectorForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Form errors: {form.errors}"
        assert form.cleaned_data["connection_config_raw"] == {}


@pytest.mark.django_db
def test_integrationhub_forms_connector_auth_creds_valid(tenant_a):
    """Verify valid JSON dictionary parses cleanly in auth_credentials_raw."""
    data = _integrationhub_valid_connector_data(
        auth_credentials_raw='{"api_key": "test_sec_key", "secret": "shh"}'
    )
    form = IntegrationConnectorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data["auth_credentials_raw"] == {
        "api_key": "test_sec_key",
        "secret": "shh",
    }


@pytest.mark.django_db
def test_integrationhub_forms_connector_auth_creds_invalid_syntax(tenant_a):
    """Verify invalid JSON syntax triggers ValidationError on auth_credentials_raw."""
    data = _integrationhub_valid_connector_data(
        auth_credentials_raw='{"api_key": "test_key", broken_syntax}'
    )
    form = IntegrationConnectorForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "auth_credentials_raw" in form.errors
    assert "Invalid JSON syntax in credentials" in form.errors["auth_credentials_raw"][0]


@pytest.mark.django_db
def test_integrationhub_forms_connector_auth_creds_not_a_dict(tenant_a):
    """Verify JSON array or scalar triggers ValidationError requiring a credentials dictionary."""
    for invalid_payload in ['["sec1", "sec2"]', '"plain_key"', '999']:
        data = _integrationhub_valid_connector_data(auth_credentials_raw=invalid_payload)
        form = IntegrationConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "auth_credentials_raw" in form.errors
        assert "must be a JSON object (dictionary)" in form.errors["auth_credentials_raw"][0]


@pytest.mark.django_db
def test_integrationhub_forms_connector_auth_creds_empty(tenant_a):
    """Verify empty or whitespace auth_credentials_raw returns None (to preserve existing)."""
    for empty_val in ["", "   ", None]:
        data = _integrationhub_valid_connector_data(auth_credentials_raw=empty_val)
        form = IntegrationConnectorForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Form errors: {form.errors}"
        assert form.cleaned_data["auth_credentials_raw"] is None


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_json_config_validation(tenant_a):
    """Verify WarehouseSyncEndpointForm connection_config_raw JSON validation."""
    # 1. Valid JSON dict
    valid_data = _integrationhub_valid_warehouse_sync_data(
        connection_config_raw='{"account": "xy12345", "warehouse": "COMPUTE_WH"}'
    )
    form = WarehouseSyncEndpointForm(data=valid_data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["connection_config_raw"] == {
        "account": "xy12345",
        "warehouse": "COMPUTE_WH",
    }

    # 2. Invalid syntax
    bad_syntax_data = _integrationhub_valid_warehouse_sync_data(
        connection_config_raw='{"account": "broken_json'
    )
    form = WarehouseSyncEndpointForm(data=bad_syntax_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "connection_config_raw" in form.errors
    assert "Invalid JSON syntax" in form.errors["connection_config_raw"][0]

    # 3. Not a dictionary
    non_dict_data = _integrationhub_valid_warehouse_sync_data(
        connection_config_raw='["account1", "account2"]'
    )
    form = WarehouseSyncEndpointForm(data=non_dict_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "connection_config_raw" in form.errors
    assert "must be a JSON object (dictionary)" in form.errors["connection_config_raw"][0]

    # 4. Blank string returns empty dict
    blank_data = _integrationhub_valid_warehouse_sync_data(connection_config_raw="")
    form = WarehouseSyncEndpointForm(data=blank_data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["connection_config_raw"] == {}


@pytest.mark.django_db
def test_integrationhub_forms_webhook_json_fields_validation(tenant_a):
    """Verify BiWebhookSubscriptionForm event_types_raw and custom_headers_raw validation."""
    # 1. Valid event_types_raw and custom_headers_raw
    data = _integrationhub_valid_webhook_data(
        event_types_raw='["kpi.breached", "report.ready", "sync.done"]',
        custom_headers_raw='{"X-Token": "secret_abc", "X-Env": "prod"}',
    )
    form = BiWebhookSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["event_types_raw"] == ["kpi.breached", "report.ready", "sync.done"]
    assert form.cleaned_data["custom_headers_raw"] == {"X-Token": "secret_abc", "X-Env": "prod"}

    # 2. Invalid JSON syntax in event_types_raw
    bad_event_data = _integrationhub_valid_webhook_data(event_types_raw='["kpi.breached", unclosed')
    form = BiWebhookSubscriptionForm(data=bad_event_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "event_types_raw" in form.errors
    assert "Invalid JSON syntax in event types" in form.errors["event_types_raw"][0]

    # 3. Non-array event_types_raw
    non_array_data = _integrationhub_valid_webhook_data(event_types_raw='{"event": "kpi.breached"}')
    form = BiWebhookSubscriptionForm(data=non_array_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "event_types_raw" in form.errors
    assert "must be a JSON array of strings" in form.errors["event_types_raw"][0]

    # 4. Empty event_types_raw defaults to kpi.threshold_breached
    empty_event_data = _integrationhub_valid_webhook_data(event_types_raw="")
    form = BiWebhookSubscriptionForm(data=empty_event_data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["event_types_raw"] == ["kpi.threshold_breached"]

    # 5. Invalid syntax in custom_headers_raw
    bad_header_data = _integrationhub_valid_webhook_data(custom_headers_raw='{"X-Token": }')
    form = BiWebhookSubscriptionForm(data=bad_header_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_headers_raw" in form.errors
    assert "Invalid JSON syntax in custom headers" in form.errors["custom_headers_raw"][0]

    # 6. Non-dict custom_headers_raw
    non_dict_header = _integrationhub_valid_webhook_data(custom_headers_raw='["X-Token: 123"]')
    form = BiWebhookSubscriptionForm(data=non_dict_header, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_headers_raw" in form.errors
    assert "must be a JSON object (dictionary)" in form.errors["custom_headers_raw"][0]

    # 7. Empty custom_headers_raw returns empty dict
    empty_header_data = _integrationhub_valid_webhook_data(custom_headers_raw="")
    form = BiWebhookSubscriptionForm(data=empty_header_data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["custom_headers_raw"] == {}


@pytest.mark.django_db
def test_integrationhub_forms_plugin_json_fields_validation(tenant_a):
    """Verify BiExtensionPluginForm JSON clean methods across all raw JSON fields."""
    # 1. Valid raw fields
    data = _integrationhub_valid_plugin_data(
        manifest_metadata_raw='{"entrypoint_js": "/app.js"}',
        config_schema_raw='{"type": "object"}',
        current_config_raw='{"theme": "light"}',
        permissions_required_raw='["read_data", "export_data"]',
    )
    form = BiExtensionPluginForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["manifest_metadata_raw"] == {"entrypoint_js": "/app.js"}
    assert form.cleaned_data["config_schema_raw"] == {"type": "object"}
    assert form.cleaned_data["current_config_raw"] == {"theme": "light"}
    assert form.cleaned_data["permissions_required_raw"] == ["read_data", "export_data"]

    # 2. Syntax errors
    bad_manifest = _integrationhub_valid_plugin_data(manifest_metadata_raw="{broken")
    f_man = BiExtensionPluginForm(data=bad_manifest, tenant=tenant_a)
    assert not f_man.is_valid()
    assert "manifest_metadata_raw" in f_man.errors
    assert "Invalid JSON in manifest metadata" in f_man.errors["manifest_metadata_raw"][0]

    bad_schema = _integrationhub_valid_plugin_data(config_schema_raw="{bad_schema")
    f_sch = BiExtensionPluginForm(data=bad_schema, tenant=tenant_a)
    assert not f_sch.is_valid()
    assert "config_schema_raw" in f_sch.errors

    bad_cfg = _integrationhub_valid_plugin_data(current_config_raw="{bad_config")
    f_cfg = BiExtensionPluginForm(data=bad_cfg, tenant=tenant_a)
    assert not f_cfg.is_valid()
    assert "current_config_raw" in f_cfg.errors

    bad_perms = _integrationhub_valid_plugin_data(permissions_required_raw="[bad_perms")
    f_perm = BiExtensionPluginForm(data=bad_perms, tenant=tenant_a)
    assert not f_perm.is_valid()
    assert "permissions_required_raw" in f_perm.errors

    # 3. Non-dictionary / Non-array errors
    non_dict_manifest = _integrationhub_valid_plugin_data(manifest_metadata_raw='["entry.js"]')
    f_ndm = BiExtensionPluginForm(data=non_dict_manifest, tenant=tenant_a)
    assert not f_ndm.is_valid()
    assert "manifest_metadata_raw" in f_ndm.errors
    assert "must be a JSON object (dictionary)" in f_ndm.errors["manifest_metadata_raw"][0]

    non_list_perms = _integrationhub_valid_plugin_data(permissions_required_raw='{"perm": "read"}')
    f_nlp = BiExtensionPluginForm(data=non_list_perms, tenant=tenant_a)
    assert not f_nlp.is_valid()
    assert "permissions_required_raw" in f_nlp.errors
    assert "must be a JSON array of strings" in f_nlp.errors["permissions_required_raw"][0]

    # 4. Empty fields default cleanly
    empty_plugin_data = _integrationhub_valid_plugin_data(
        manifest_metadata_raw="",
        config_schema_raw="",
        current_config_raw="",
        permissions_required_raw="",
    )
    f_empty = BiExtensionPluginForm(data=empty_plugin_data, tenant=tenant_a)
    assert f_empty.is_valid(), f"Errors: {f_empty.errors}"
    assert f_empty.cleaned_data["manifest_metadata_raw"] == {}
    assert f_empty.cleaned_data["config_schema_raw"] == {}
    assert f_empty.cleaned_data["current_config_raw"] == {}
    assert f_empty.cleaned_data["permissions_required_raw"] == []


# ===========================================================================
# 3. Tenant-Scoped FK Queryset Tests
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_tenant_scoped_fk_querysets(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    data_mart_a,
    data_mart_b,
):
    """Verify WarehouseSyncEndpointForm strictly scopes semantic_model and data_mart choices to tenant."""
    # When initialized for Tenant A
    form_a = WarehouseSyncEndpointForm(tenant=tenant_a)
    sm_qs_a = form_a.fields["semantic_model"].queryset
    dm_qs_a = form_a.fields["data_mart"].queryset

    assert sm_qs_a.filter(pk=semantic_model_a.pk).exists()
    assert not sm_qs_a.filter(pk=semantic_model_b.pk).exists()
    for model in sm_qs_a:
        assert model.tenant == tenant_a

    assert dm_qs_a.filter(pk=data_mart_a.pk).exists()
    assert not dm_qs_a.filter(pk=data_mart_b.pk).exists()
    for mart in dm_qs_a:
        assert mart.tenant == tenant_a

    # When initialized for Tenant B
    form_b = WarehouseSyncEndpointForm(tenant=tenant_b)
    sm_qs_b = form_b.fields["semantic_model"].queryset
    dm_qs_b = form_b.fields["data_mart"].queryset

    assert sm_qs_b.filter(pk=semantic_model_b.pk).exists()
    assert not sm_qs_b.filter(pk=semantic_model_a.pk).exists()
    for model in sm_qs_b:
        assert model.tenant == tenant_b

    assert dm_qs_b.filter(pk=data_mart_b.pk).exists()
    assert not dm_qs_b.filter(pk=data_mart_a.pk).exists()
    for mart in dm_qs_b:
        assert mart.tenant == tenant_b


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_no_tenant_empty_querysets():
    """Verify WarehouseSyncEndpointForm querysets are empty (.none()) when tenant is not provided."""
    form = WarehouseSyncEndpointForm(tenant=None)
    assert form.fields["semantic_model"].queryset.count() == 0
    assert form.fields["data_mart"].queryset.count() == 0


# ===========================================================================
# 4. Defense-in-Depth Cross-Tenant Rejection Tests (reject_foreign)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_rejects_cross_tenant_semantic_model(
    tenant_a,
    semantic_model_b,
    data_mart_a,
):
    """Verify reject_foreign rejects a cross-tenant semantic_model belonging to another tenant."""
    data = _integrationhub_valid_warehouse_sync_data(
        semantic_model=semantic_model_b,
        data_mart=data_mart_a,
    )
    form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    error_msg = str(form.errors["semantic_model"])
    assert (
        "That record belongs to another workspace" in error_msg
        or "Select a valid choice" in error_msg
    )


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_rejects_cross_tenant_data_mart(
    tenant_a,
    semantic_model_a,
    data_mart_b,
):
    """Verify reject_foreign rejects a cross-tenant data_mart belonging to another tenant."""
    data = _integrationhub_valid_warehouse_sync_data(
        semantic_model=semantic_model_a,
        data_mart=data_mart_b,
    )
    form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "data_mart" in form.errors
    error_msg = str(form.errors["data_mart"])
    assert (
        "That record belongs to another workspace" in error_msg
        or "Select a valid choice" in error_msg
    )


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_rejects_both_cross_tenant_fks(
    tenant_a,
    semantic_model_b,
    data_mart_b,
):
    """Verify reject_foreign flags both foreign keys when cross-tenant values are injected."""
    data = _integrationhub_valid_warehouse_sync_data(
        semantic_model=semantic_model_b,
        data_mart=data_mart_b,
    )
    form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "data_mart" in form.errors


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_accepts_same_tenant_fks(
    tenant_a,
    semantic_model_a,
    data_mart_a,
):
    """Verify WarehouseSyncEndpointForm successfully accepts foreign keys belonging to the same tenant."""
    data = _integrationhub_valid_warehouse_sync_data(
        semantic_model=semantic_model_a,
        data_mart=data_mart_a,
    )
    form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    sync_ep = form.save()
    assert sync_ep.semantic_model == semantic_model_a
    assert sync_ep.data_mart == data_mart_a
    assert sync_ep.tenant == tenant_a


# ===========================================================================
# 5. Edit Mode Credential Behavior Tests (Rule L20 / Masking)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_connector_edit_does_not_populate_cleartext_credentials(
    tenant_a,
    integration_connector_a,
):
    """Verify edit form does NOT populate auth_credentials_raw in cleartext (Rule L20)."""
    assert integration_connector_a.auth_credentials == {"api_key": "sec_test_key_123"}
    form = IntegrationConnectorForm(instance=integration_connector_a, tenant=tenant_a)

    # auth_credentials_raw must NOT be populated with cleartext secrets
    assert not form.fields["auth_credentials_raw"].initial

    # connection_config_raw SHOULD be populated with existing JSON configuration
    assert form.fields["connection_config_raw"].initial is not None
    loaded_config = json.loads(form.fields["connection_config_raw"].initial)
    assert loaded_config == {"timeout": 30, "base_url": "https://api.kafka.example.com"}


@pytest.mark.django_db
def test_integrationhub_forms_connector_edit_preserves_existing_credentials_when_blank(
    tenant_a,
    integration_connector_a,
):
    """Verify submitting blank auth_credentials_raw on edit preserves existing credentials intact."""
    data = _integrationhub_valid_connector_data(
        name="Updated Stream Connector",
        slug="enterprise-kafka-stream",
        auth_credentials_raw="",  # Leave blank on edit
    )
    form = IntegrationConnectorForm(
        data=data,
        instance=integration_connector_a,
        tenant=tenant_a,
    )
    assert form.is_valid(), f"Form errors: {form.errors}"
    saved_connector = form.save()

    assert saved_connector.pk == integration_connector_a.pk
    assert saved_connector.name == "Updated Stream Connector"
    # Preserves original credential dictionary
    assert saved_connector.auth_credentials == {"api_key": "sec_test_key_123"}


@pytest.mark.django_db
def test_integrationhub_forms_connector_edit_overwrites_credentials_when_provided(
    tenant_a,
    integration_connector_a,
):
    """Verify submitting new credentials JSON on edit updates auth_credentials."""
    data = _integrationhub_valid_connector_data(
        name="Rotated Stream Connector",
        slug="enterprise-kafka-stream",
        auth_credentials_raw=json.dumps({"api_key": "sec_rotated_9999", "tier": "gold"}),
    )
    form = IntegrationConnectorForm(
        data=data,
        instance=integration_connector_a,
        tenant=tenant_a,
    )
    assert form.is_valid(), f"Form errors: {form.errors}"
    saved_connector = form.save()

    assert saved_connector.pk == integration_connector_a.pk
    assert saved_connector.auth_credentials == {"api_key": "sec_rotated_9999", "tier": "gold"}


@pytest.mark.django_db
def test_integrationhub_forms_connector_create_blank_credentials_defaults_to_dict(tenant_a):
    """Verify creating a new connector with blank credentials sets auth_credentials to empty dict."""
    data = _integrationhub_valid_connector_data(
        name="New Anonymous Ingress Connector",
        slug="new-anon-ingress",
        auth_credentials_raw="",
    )
    form = IntegrationConnectorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    connector = form.save()

    assert connector.pk is not None
    assert connector.auth_credentials == {}


# ===========================================================================
# 6. URL Validation Tests
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_webhook_endpoint_url_valid_schemes(tenant_a):
    """Verify standard HTTP and HTTPS schemes pass validation on endpoint_url."""
    valid_urls = [
        "https://hooks.slack.com/services/T123/B456/789",
        "https://api.external.com/webhooks/v1/deliveries",
        "http://localhost:8000/api/bi/webhook-listener",
        "http://127.0.0.1:9000/alerts",
    ]
    for url in valid_urls:
        data = _integrationhub_valid_webhook_data(endpoint_url=url)
        form = BiWebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected valid URL '{url}', got errors: {form.errors}"
        assert form.cleaned_data["endpoint_url"] == url


@pytest.mark.django_db
def test_integrationhub_forms_webhook_endpoint_url_invalid_schemes(tenant_a):
    """Verify malformed or disallowed schemes fail validation on endpoint_url."""
    invalid_urls = [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "not-a-valid-url",
        "htp:/missing-slash.com",
        "mailto:test@example.com",
    ]
    for url in invalid_urls:
        data = _integrationhub_valid_webhook_data(endpoint_url=url)
        form = BiWebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"URL '{url}' should be rejected as invalid"
        assert "endpoint_url" in form.errors


@pytest.mark.django_db
def test_integrationhub_forms_plugin_urls_validation(tenant_a):
    """Verify homepage_url and repository_url standard HTTP/HTTPS validation on BiExtensionPluginForm."""
    # Valid HTTP/HTTPS
    data = _integrationhub_valid_plugin_data(
        homepage_url="https://plugins.example.com/sankey",
        repository_url="https://github.com/org/repo-sankey",
    )
    form = BiExtensionPluginForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assert form.cleaned_data["homepage_url"] == "https://plugins.example.com/sankey"
    assert form.cleaned_data["repository_url"] == "https://github.com/org/repo-sankey"

    # Invalid homepage_url
    bad_hp = _integrationhub_valid_plugin_data(homepage_url="invalid_url")
    form_hp = BiExtensionPluginForm(data=bad_hp, tenant=tenant_a)
    assert not form_hp.is_valid()
    assert "homepage_url" in form_hp.errors

    # Invalid repository_url
    bad_repo = _integrationhub_valid_plugin_data(repository_url="javascript:alert('xss')")
    form_repo = BiExtensionPluginForm(data=bad_repo, tenant=tenant_a)
    assert not form_repo.is_valid()
    assert "repository_url" in form_repo.errors

    # Blank URLs are allowed (blank=True on model)
    blank_urls = _integrationhub_valid_plugin_data(homepage_url="", repository_url="")
    form_blank = BiExtensionPluginForm(data=blank_urls, tenant=tenant_a)
    assert form_blank.is_valid(), f"Errors: {form_blank.errors}"
    assert form_blank.cleaned_data["homepage_url"] == ""
    assert form_blank.cleaned_data["repository_url"] == ""


# ===========================================================================
# 7. Form Save, Instance Persistence & Initial Population Tests
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_connector_valid_create_and_save(tenant_a):
    """Verify creating a new IntegrationConnector via form correctly persists all attributes."""
    data = _integrationhub_valid_connector_data(
        name="Warehouse CDC Streaming Connector",
        slug="warehouse-cdc-streaming",
        connector_type="saas_application",
        target_system="generic_webhook",
        sync_direction="bidirectional",
        auth_type="bearer_token",
        message_format="cloudevents",
        sync_interval="every_5_minutes",
        status="active",
        is_enabled=True,
    )
    form = IntegrationConnectorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    connector = form.save()

    assert connector.pk is not None
    assert connector.tenant == tenant_a
    assert connector.name == "Warehouse CDC Streaming Connector"
    assert connector.slug == "warehouse-cdc-streaming"
    assert connector.connector_type == "saas_application"
    assert connector.target_system == "generic_webhook"
    assert connector.sync_direction == "bidirectional"
    assert connector.auth_type == "bearer_token"
    assert connector.message_format == "cloudevents"
    assert connector.sync_interval == "every_5_minutes"
    assert connector.status == "active"
    assert connector.is_enabled is True
    assert connector.connection_config == {
        "bootstrap_servers": "kafka.internal:9092",
        "topic": "erp.gl.events",
        "batch_size": 250,
    }
    assert connector.auth_credentials == {
        "api_key": "sec_live_abcdef123456",
        "header_name": "X-API-Key",
    }


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_valid_create_and_save(tenant_a):
    """Verify creating a new WarehouseSyncEndpoint via form correctly persists attributes."""
    data = _integrationhub_valid_warehouse_sync_data(
        name="Google BigQuery Direct Federation",
        slug="gbq-direct-fed",
        target_warehouse="google_bigquery",
        sync_mode="direct_query_federation",
        destination_database="bigquery-public-data",
        destination_schema="analytics",
        destination_table="fct_sales_gl",
        auth_method="service_account_key",
        sync_schedule="hourly",
        is_active=True,
    )
    form = WarehouseSyncEndpointForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    endpoint = form.save()

    assert endpoint.pk is not None
    assert endpoint.tenant == tenant_a
    assert endpoint.name == "Google BigQuery Direct Federation"
    assert endpoint.slug == "gbq-direct-fed"
    assert endpoint.target_warehouse == "google_bigquery"
    assert endpoint.sync_mode == "direct_query_federation"
    assert endpoint.destination_database == "bigquery-public-data"
    assert endpoint.destination_schema == "analytics"
    assert endpoint.destination_table == "fct_sales_gl"
    assert endpoint.auth_method == "service_account_key"
    assert endpoint.sync_schedule == "hourly"
    assert endpoint.is_active is True
    assert endpoint.connection_config == {
        "account": "xy12345.us-east-1",
        "warehouse": "COMPUTE_WH",
        "role": "DATA_ANALYST",
    }


@pytest.mark.django_db
def test_integrationhub_forms_webhook_valid_create_and_save(tenant_a):
    """Verify creating a new BiWebhookSubscription via form generates secret_token and saves."""
    data = _integrationhub_valid_webhook_data(
        name="PagerDuty Operational Alarm Feed",
        endpoint_url="https://events.pagerduty.com/v2/enqueue",
        payload_format="standard_json",
        max_retries=5,
        timeout_seconds=20,
        is_active=True,
        event_types_raw=json.dumps(["kpi.threshold_breached", "anomaly.detected"]),
        custom_headers_raw=json.dumps({"X-Routing-Key": "pd_sec_key_123"}),
    )
    form = BiWebhookSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    webhook = form.save()

    assert webhook.pk is not None
    assert webhook.tenant == tenant_a
    assert webhook.name == "PagerDuty Operational Alarm Feed"
    assert webhook.endpoint_url == "https://events.pagerduty.com/v2/enqueue"
    assert webhook.payload_format == "standard_json"
    assert webhook.max_retries == 5
    assert webhook.timeout_seconds == 20
    assert webhook.is_active is True
    assert webhook.event_types == ["kpi.threshold_breached", "anomaly.detected"]
    assert webhook.custom_headers == {"X-Routing-Key": "pd_sec_key_123"}
    # Secret token auto-generated on model save
    assert webhook.secret_token.startswith("whsec_")


@pytest.mark.django_db
def test_integrationhub_forms_plugin_valid_create_and_save(tenant_a):
    """Verify creating a new BiExtensionPlugin via form parses and saves all JSON fields."""
    data = _integrationhub_valid_plugin_data(
        name="Custom D3 Treemap Matrix",
        plugin_identifier="io.naverp.visuals.d3-treemap",
        version="2.0.0",
        plugin_type="custom_visual",
        category="visualization",
        author_name="Analytics Lab",
        license="MIT",
        status="enabled",
    )
    form = BiExtensionPluginForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    plugin = form.save()

    assert plugin.pk is not None
    assert plugin.tenant == tenant_a
    assert plugin.name == "Custom D3 Treemap Matrix"
    assert plugin.plugin_identifier == "io.naverp.visuals.d3-treemap"
    assert plugin.version == "2.0.0"
    assert plugin.plugin_type == "custom_visual"
    assert plugin.category == "visualization"
    assert plugin.author_name == "Analytics Lab"
    assert plugin.license == "MIT"
    assert plugin.status == "enabled"
    assert plugin.manifest_metadata == {
        "entrypoint_js": "/static/bi/plugins/sankey.js",
        "min_naverp_version": "1.0.0",
    }
    assert plugin.config_schema == {"type": "object", "properties": {"theme": {"type": "string"}}}
    assert plugin.current_config == {"theme": "dark", "node_width": 24}
    assert plugin.permissions_required == ["read_semantic_layer", "render_canvas_ui"]


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_edit_populates_initial(
    tenant_a,
    warehouse_sync_endpoint_a,
):
    """Verify WarehouseSyncEndpointForm populates initial connection_config_raw when editing."""
    warehouse_sync_endpoint_a.connection_config = {"account": "test_acc", "warehouse": "DEV_WH"}
    warehouse_sync_endpoint_a.save()

    form = WarehouseSyncEndpointForm(instance=warehouse_sync_endpoint_a, tenant=tenant_a)
    initial_raw = form.fields["connection_config_raw"].initial
    assert initial_raw is not None
    assert json.loads(initial_raw) == {"account": "test_acc", "warehouse": "DEV_WH"}


@pytest.mark.django_db
def test_integrationhub_forms_webhook_edit_populates_initial(
    tenant_a,
    bi_webhook_subscription_a,
):
    """Verify BiWebhookSubscriptionForm populates initial event_types_raw and custom_headers_raw."""
    bi_webhook_subscription_a.event_types = ["alert.triggered", "sync.completed"]
    bi_webhook_subscription_a.custom_headers = {"X-Custom": "val123"}
    bi_webhook_subscription_a.save()

    form = BiWebhookSubscriptionForm(instance=bi_webhook_subscription_a, tenant=tenant_a)
    ev_initial = form.fields["event_types_raw"].initial
    hd_initial = form.fields["custom_headers_raw"].initial

    assert ev_initial is not None
    assert json.loads(ev_initial) == ["alert.triggered", "sync.completed"]
    assert hd_initial is not None
    assert json.loads(hd_initial) == {"X-Custom": "val123"}


@pytest.mark.django_db
def test_integrationhub_forms_plugin_edit_populates_initial(
    tenant_a,
    bi_extension_plugin_a,
):
    """Verify BiExtensionPluginForm populates all 4 initial raw JSON fields on edit."""
    bi_extension_plugin_a.manifest_metadata = {"main": "index.js"}
    bi_extension_plugin_a.config_schema = {"type": "object"}
    bi_extension_plugin_a.current_config = {"color": "blue"}
    bi_extension_plugin_a.permissions_required = ["perm_a", "perm_b"]
    bi_extension_plugin_a.save()

    form = BiExtensionPluginForm(instance=bi_extension_plugin_a, tenant=tenant_a)
    assert json.loads(form.fields["manifest_metadata_raw"].initial) == {"main": "index.js"}
    assert json.loads(form.fields["config_schema_raw"].initial) == {"type": "object"}
    assert json.loads(form.fields["current_config_raw"].initial) == {"color": "blue"}
    assert json.loads(form.fields["permissions_required_raw"].initial) == ["perm_a", "perm_b"]


# ===========================================================================
# 8. Required Fields & Widgets Validation Tests
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_forms_connector_required_fields(tenant_a):
    """Verify required field validation on IntegrationConnectorForm."""
    form = IntegrationConnectorForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_integrationhub_forms_warehouse_sync_required_fields(tenant_a):
    """Verify required field validation on WarehouseSyncEndpointForm."""
    form = WarehouseSyncEndpointForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "destination_table" in form.errors


@pytest.mark.django_db
def test_integrationhub_forms_webhook_required_fields(tenant_a):
    """Verify required field validation on BiWebhookSubscriptionForm."""
    form = BiWebhookSubscriptionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "endpoint_url" in form.errors


@pytest.mark.django_db
def test_integrationhub_forms_plugin_required_fields(tenant_a):
    """Verify required field validation on BiExtensionPluginForm."""
    form = BiExtensionPluginForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "plugin_identifier" in form.errors
    assert "author_name" in form.errors


@pytest.mark.django_db
def test_integrationhub_forms_widgets_css_classes():
    """Verify form widgets apply standard NavERP Tailwind design system classes."""
    # IntegrationConnectorForm
    conn_form = IntegrationConnectorForm()
    assert "form-input" in conn_form.fields["name"].widget.attrs.get("class", "")
    assert "form-select" in conn_form.fields["connector_type"].widget.attrs.get("class", "")
    assert "form-textarea" in conn_form.fields["connection_config_raw"].widget.attrs.get("class", "")

    # WarehouseSyncEndpointForm
    wh_form = WarehouseSyncEndpointForm()
    assert "form-input" in wh_form.fields["name"].widget.attrs.get("class", "")
    assert "form-select" in wh_form.fields["target_warehouse"].widget.attrs.get("class", "")

    # BiWebhookSubscriptionForm
    whk_form = BiWebhookSubscriptionForm()
    assert "form-input" in whk_form.fields["name"].widget.attrs.get("class", "")
    assert "form-input" in whk_form.fields["endpoint_url"].widget.attrs.get("class", "")

    # BiExtensionPluginForm
    plug_form = BiExtensionPluginForm()
    assert "form-input" in plug_form.fields["name"].widget.attrs.get("class", "")
    assert "form-select" in plug_form.fields["plugin_type"].widget.attrs.get("class", "")
    assert "form-textarea" in plug_form.fields["manifest_metadata_raw"].widget.attrs.get("class", "")
