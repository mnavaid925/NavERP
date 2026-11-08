"""Unit tests for Sub-module 10.19 Integration & API Hub models.

Models covered:
- IntegrationConnector (BINT)
- WarehouseSyncEndpoint (BSNC)
- BiWebhookSubscription (BWHK)
- BiExtensionPlugin (BEXT)
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.bi.models import (
    BiExtensionPlugin,
    BiWebhookSubscription,
    DataMart,
    IntegrationConnector,
    SemanticModel,
    WarehouseSyncEndpoint,
)
from apps.core.models import Tenant

User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _integrationhub_)
# ---------------------------------------------------------------------------


def _integrationhub_choice_keys(choices):
    """Return list of valid key identifiers from Django model choices list."""
    return [key for key, _label in choices]


def _integrationhub_create_connector(tenant, name="Integration Stream Connector", **kwargs):
    """Helper to create an IntegrationConnector with sensible defaults."""
    defaults = {
        "name": name,
        "connector_type": "internal_erp",
        "target_system": "erp_accounting",
        "sync_direction": "outbound",
        "connection_config": {"port": 9092, "host": "kafka.internal"},
        "auth_type": "internal_session",
        "auth_credentials": {"token": "sample_token_123"},
        "message_format": "json",
        "sync_interval": "realtime_event",
        "status": "active",
        "health_status": "healthy",
        "is_enabled": True,
    }
    defaults.update(kwargs)
    return IntegrationConnector.objects.create(tenant=tenant, **defaults)


def _integrationhub_create_sync_endpoint(tenant, name="Cloud Warehouse Sync", destination_table="FCT_ANALYTICS", **kwargs):
    """Helper to create a WarehouseSyncEndpoint with sensible defaults."""
    defaults = {
        "name": name,
        "target_warehouse": "snowflake",
        "sync_mode": "incremental_merge",
        "destination_database": "ANALYTICS_DB",
        "destination_schema": "PUBLIC",
        "destination_table": destination_table,
        "connection_config": {"account": "xy12345", "warehouse": "COMPUTE_WH"},
        "auth_method": "service_account_key",
        "sync_schedule": "daily",
        "status": "idle",
        "is_active": True,
    }
    defaults.update(kwargs)
    return WarehouseSyncEndpoint.objects.create(tenant=tenant, **defaults)


def _integrationhub_create_webhook(tenant, name="Analytical Webhook Subscription", endpoint_url="https://api.example.com/webhook", **kwargs):
    """Helper to create a BiWebhookSubscription with sensible defaults."""
    defaults = {
        "name": name,
        "endpoint_url": endpoint_url,
        "event_types": ["alert.triggered", "sync.completed"],
        "payload_format": "standard_json",
        "custom_headers": {"X-Custom-Auth": "sec_header_val"},
        "max_retries": 3,
        "timeout_seconds": 10,
        "status": "active",
        "is_active": True,
    }
    defaults.update(kwargs)
    return BiWebhookSubscription.objects.create(tenant=tenant, **defaults)


def _integrationhub_create_plugin(tenant, name="Data Extension Plugin", plugin_identifier="org.example.bi.plugin", author_name="Data Team", **kwargs):
    """Helper to create a BiExtensionPlugin with sensible defaults."""
    defaults = {
        "name": name,
        "plugin_identifier": plugin_identifier,
        "version": "1.0.0",
        "plugin_type": "custom_visual",
        "category": "visualization",
        "author_name": author_name,
        "status": "installed",
        "is_verified": False,
        "is_system_plugin": False,
        "manifest_metadata": {"entrypoint": "main.js", "icon": "icon.svg"},
        "config_schema": {"type": "object", "properties": {"color": {"type": "string"}}},
        "current_config": {"color": "#3b82f6"},
        "permissions_required": ["read_semantic_layer"],
    }
    defaults.update(kwargs)
    return BiExtensionPlugin.objects.create(tenant=tenant, **defaults)


# ===========================================================================
# 1. IntegrationConnector Model Tests (BINT)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_models_connector_fixture_and_str(integration_connector_a):
    """Test IntegrationConnector fixture from conftest, prefix, and __str__ representation."""
    assert integration_connector_a.pk is not None
    assert integration_connector_a.number.startswith("BINT-")
    expected_str = f"{integration_connector_a.number} - {integration_connector_a.name} ({integration_connector_a.get_target_system_display()})"
    assert str(integration_connector_a) == expected_str


@pytest.mark.django_db
def test_integrationhub_models_connector_autonumbering(tenant_a):
    """Test auto-number sequence BINT-##### increments monotonically per tenant."""
    c1 = _integrationhub_create_connector(tenant_a, name="Connector Alpha")
    c2 = _integrationhub_create_connector(tenant_a, name="Connector Beta")

    assert c1.number.startswith("BINT-")
    assert c2.number.startswith("BINT-")
    num1 = int(c1.number.split("-")[1])
    num2 = int(c2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_integrationhub_models_connector_defaults(tenant_a):
    """Verify default field values on minimal IntegrationConnector."""
    c = IntegrationConnector.objects.create(tenant=tenant_a, name="Default Settings Connector")

    assert c.connector_type == "internal_erp"
    assert c.target_system == "erp_accounting"
    assert c.sync_direction == "outbound"
    assert c.connection_config == {}
    assert c.auth_type == "internal_session"
    assert c.auth_credentials == {}
    assert c.message_format == "json"
    assert c.sync_interval == "realtime_event"
    assert c.status == "active"
    assert c.health_status == "healthy"
    assert c.total_messages_processed == 0
    assert c.error_message == ""
    assert c.is_enabled is True
    assert c.slug == "default-settings-connector"


@pytest.mark.django_db
def test_integrationhub_models_connector_choices():
    """Verify choices lists exposed on IntegrationConnector."""
    type_keys = _integrationhub_choice_keys(IntegrationConnector.CONNECTOR_TYPE_CHOICES)
    assert "internal_erp" in type_keys
    assert "message_broker" in type_keys
    assert "saas_application" in type_keys
    assert "custom_api" in type_keys

    target_keys = _integrationhub_choice_keys(IntegrationConnector.TARGET_SYSTEM_CHOICES)
    assert "erp_accounting" in target_keys
    assert "erp_hrm" in target_keys
    assert "erp_scm" in target_keys
    assert "erp_crm" in target_keys
    assert "erp_inventory" in target_keys
    assert "kafka" in target_keys
    assert "rabbitmq" in target_keys
    assert "aws_eventbridge" in target_keys
    assert "redis_streams" in target_keys
    assert "generic_webhook" in target_keys

    sync_dir_keys = _integrationhub_choice_keys(IntegrationConnector.SYNC_DIRECTION_CHOICES)
    assert "inbound" in sync_dir_keys
    assert "outbound" in sync_dir_keys
    assert "bidirectional" in sync_dir_keys

    auth_keys = _integrationhub_choice_keys(IntegrationConnector.AUTH_TYPE_CHOICES)
    assert "internal_session" in auth_keys
    assert "api_key" in auth_keys
    assert "bearer_token" in auth_keys
    assert "basic_auth" in auth_keys
    assert "iam_role" in auth_keys
    assert "tls_certificate" in auth_keys

    msg_fmt_keys = _integrationhub_choice_keys(IntegrationConnector.MESSAGE_FORMAT_CHOICES)
    assert "json" in msg_fmt_keys
    assert "avro" in msg_fmt_keys
    assert "protobuf" in msg_fmt_keys
    assert "cloudevents" in msg_fmt_keys

    interval_keys = _integrationhub_choice_keys(IntegrationConnector.SYNC_INTERVAL_CHOICES)
    assert "realtime_event" in interval_keys
    assert "every_minute" in interval_keys
    assert "every_5_minutes" in interval_keys
    assert "hourly" in interval_keys
    assert "daily" in interval_keys
    assert "manual" in interval_keys

    status_keys = _integrationhub_choice_keys(IntegrationConnector.STATUS_CHOICES)
    assert "active" in status_keys
    assert "paused" in status_keys
    assert "error" in status_keys
    assert "maintenance" in status_keys

    health_keys = _integrationhub_choice_keys(IntegrationConnector.HEALTH_STATUS_CHOICES)
    assert "healthy" in health_keys
    assert "degraded" in health_keys
    assert "unreachable" in health_keys
    assert "untested" in health_keys


@pytest.mark.django_db
def test_integrationhub_models_connector_choice_validation_valid(tenant_a):
    """Verify valid choices pass full_clean validation."""
    c = _integrationhub_create_connector(
        tenant_a,
        name="Valid Choices Connector",
        connector_type="message_broker",
        target_system="kafka",
        sync_direction="bidirectional",
        auth_type="tls_certificate",
        message_format="avro",
        sync_interval="every_minute",
        status="active",
        health_status="untested",
    )
    c.full_clean()
    assert c.connector_type == "message_broker"
    assert c.health_status == "untested"


@pytest.mark.django_db
def test_integrationhub_models_connector_choice_validation_invalid(tenant_a):
    """Verify invalid choice values raise ValidationError on full_clean."""
    c = _integrationhub_create_connector(tenant_a, name="Invalid Connector")

    c.connector_type = "invalid_type"
    with pytest.raises(ValidationError):
        c.full_clean()

    c.connector_type = "internal_erp"
    c.target_system = "invalid_system"
    with pytest.raises(ValidationError):
        c.full_clean()

    c.target_system = "erp_accounting"
    c.health_status = "invalid_health"
    with pytest.raises(ValidationError):
        c.full_clean()

    c.health_status = "healthy"
    c.status = "invalid_status"
    with pytest.raises(ValidationError):
        c.full_clean()


@pytest.mark.django_db
def test_integrationhub_models_connector_slug_autogen_and_deduplication(tenant_a):
    """Verify slug generation and collision deduplication within same tenant."""
    c1 = _integrationhub_create_connector(tenant_a, name="Hub Kafka Bus")
    c2 = _integrationhub_create_connector(tenant_a, name="Hub Kafka Bus")
    c3 = _integrationhub_create_connector(tenant_a, name="Hub Kafka Bus")

    assert c1.slug == "hub-kafka-bus"
    assert c2.slug == "hub-kafka-bus-1"
    assert c3.slug == "hub-kafka-bus-2"


@pytest.mark.django_db
def test_integrationhub_models_connector_same_slug_different_tenants(tenant_a, tenant_b):
    """Verify connectors in different tenants can have the same slug."""
    c_a = _integrationhub_create_connector(tenant_a, name="Shared Slug Connector")
    c_b = _integrationhub_create_connector(tenant_b, name="Shared Slug Connector")

    assert c_a.slug == "shared-slug-connector"
    assert c_b.slug == "shared-slug-connector"
    assert c_a.tenant != c_b.tenant


@pytest.mark.django_db
def test_integrationhub_models_connector_unique_number(tenant_a):
    """Verify bi_bint_ten_num_uniq constraint prevents duplicate number in same tenant."""
    c1 = _integrationhub_create_connector(tenant_a, name="Original Connector")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_connector(tenant_a, name="Duplicate Number", number=c1.number)


@pytest.mark.django_db
def test_integrationhub_models_connector_unique_slug(tenant_a):
    """Verify bi_bint_ten_slug_uniq constraint prevents duplicate forced slug in same tenant."""
    _integrationhub_create_connector(tenant_a, name="First With Slug", slug="forced-unique-slug")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_connector(tenant_a, name="Second With Slug", slug="forced-unique-slug")


@pytest.mark.django_db
def test_integrationhub_models_connector_created_by_set_null(tenant_a):
    """Verify user deletion sets created_by to NULL via SET_NULL."""
    user = User.objects.create_user(
        email="connector_dev@example.com",
        username="connector_dev",
        password="testpassword",
        tenant=tenant_a,
    )
    c = _integrationhub_create_connector(tenant_a, name="User Owned Connector", created_by=user)
    assert c.created_by == user

    user.delete()
    c.refresh_from_db()
    assert c.created_by is None


@pytest.mark.django_db
def test_integrationhub_models_connector_json_fields(tenant_a):
    """Verify JSON fields store and retrieve config and credentials properly."""
    cfg = {"brokers": ["10.0.0.1:9092", "10.0.0.2:9092"], "timeout_ms": 5000, "ssl": True}
    creds = {"cert_path": "/var/certs/client.pem", "key_secret_ref": "vault://sec/kafka"}
    c = _integrationhub_create_connector(
        tenant_a,
        name="Kafka TLS Connector",
        connection_config=cfg,
        auth_credentials=creds,
    )
    c.refresh_from_db()
    assert c.connection_config == cfg
    assert c.auth_credentials == creds


@pytest.mark.django_db
def test_integrationhub_models_connector_health_and_status_variants(tenant_a):
    """Verify health status and status states can be updated and queried."""
    c = _integrationhub_create_connector(
        tenant_a,
        name="Degraded Stream",
        health_status="untested",
        status="paused",
        is_enabled=False,
    )
    assert c.health_status == "untested"
    assert c.status == "paused"
    assert c.is_enabled is False

    c.health_status = "degraded"
    c.error_message = "Consumer lag exceeded 50,000 messages"
    c.total_messages_processed = 1250000
    c.save()

    c.refresh_from_db()
    assert c.health_status == "degraded"
    assert c.error_message == "Consumer lag exceeded 50,000 messages"
    assert c.total_messages_processed == 1250000


# ===========================================================================
# 2. WarehouseSyncEndpoint Model Tests (BSNC)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_fixture_and_str(warehouse_sync_endpoint_a):
    """Test WarehouseSyncEndpoint fixture from conftest, prefix, and __str__ representation."""
    assert warehouse_sync_endpoint_a.pk is not None
    assert warehouse_sync_endpoint_a.number.startswith("BSNC-")
    expected_str = f"{warehouse_sync_endpoint_a.number} - {warehouse_sync_endpoint_a.name} -> {warehouse_sync_endpoint_a.get_target_warehouse_display()}"
    assert str(warehouse_sync_endpoint_a) == expected_str


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_autonumbering(tenant_a):
    """Test auto-number sequence BSNC-##### increments monotonically per tenant."""
    s1 = _integrationhub_create_sync_endpoint(tenant_a, name="Sync Alpha")
    s2 = _integrationhub_create_sync_endpoint(tenant_a, name="Sync Beta")

    assert s1.number.startswith("BSNC-")
    assert s2.number.startswith("BSNC-")
    num1 = int(s1.number.split("-")[1])
    num2 = int(s2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_defaults(tenant_a):
    """Verify default field values on minimal WarehouseSyncEndpoint."""
    s = WarehouseSyncEndpoint.objects.create(
        tenant=tenant_a,
        name="Default Sync Endpoint",
        destination_table="DIM_STORES",
    )

    assert s.target_warehouse == "snowflake"
    assert s.sync_mode == "incremental_merge"
    assert s.auth_method == "service_account_key"
    assert s.sync_schedule == "daily"
    assert s.status == "idle"
    assert s.last_sync_duration_ms == 0
    assert s.last_rows_synced == 0
    assert s.total_rows_synced == 0
    assert s.last_error_message == ""
    assert s.is_active is True
    assert s.connection_config == {}
    assert s.slug == "default-sync-endpoint"


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_choices():
    """Verify choices lists exposed on WarehouseSyncEndpoint."""
    wh_keys = _integrationhub_choice_keys(WarehouseSyncEndpoint.TARGET_WAREHOUSE_CHOICES)
    assert "snowflake" in wh_keys
    assert "google_bigquery" in wh_keys
    assert "aws_redshift" in wh_keys
    assert "databricks_unity" in wh_keys
    assert "power_bi_semantic_model" in wh_keys
    assert "tableau_hyper" in wh_keys
    assert "looker_lookml" in wh_keys

    mode_keys = _integrationhub_choice_keys(WarehouseSyncEndpoint.SYNC_MODE_CHOICES)
    assert "incremental_merge" in mode_keys
    assert "full_refresh" in mode_keys
    assert "append_only" in mode_keys
    assert "delta_sharing" in mode_keys
    assert "direct_query_federation" in mode_keys

    auth_keys = _integrationhub_choice_keys(WarehouseSyncEndpoint.AUTH_METHOD_CHOICES)
    assert "service_account_key" in auth_keys
    assert "snowflake_keypair" in auth_keys
    assert "oauth2_token" in auth_keys
    assert "iam_role_arn" in auth_keys
    assert "personal_access_token" in auth_keys

    sched_keys = _integrationhub_choice_keys(WarehouseSyncEndpoint.SYNC_SCHEDULE_CHOICES)
    assert "hourly" in sched_keys
    assert "every_4_hours" in sched_keys
    assert "daily" in sched_keys
    assert "weekly" in sched_keys
    assert "event_triggered" in sched_keys
    assert "manual" in sched_keys

    status_keys = _integrationhub_choice_keys(WarehouseSyncEndpoint.STATUS_CHOICES)
    assert "idle" in status_keys
    assert "syncing" in status_keys
    assert "success" in status_keys
    assert "error" in status_keys
    assert "disabled" in status_keys


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_choice_validation_valid(tenant_a):
    """Verify valid choices pass full_clean validation."""
    s = _integrationhub_create_sync_endpoint(
        tenant_a,
        name="Valid Choices Endpoint",
        target_warehouse="google_bigquery",
        sync_mode="full_refresh",
        auth_method="oauth2_token",
        sync_schedule="hourly",
        status="idle",
    )
    s.full_clean()
    assert s.target_warehouse == "google_bigquery"
    assert s.sync_mode == "full_refresh"


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_choice_validation_invalid(tenant_a):
    """Verify invalid choice values raise ValidationError on full_clean."""
    s = _integrationhub_create_sync_endpoint(tenant_a, name="Invalid Endpoint")

    s.target_warehouse = "unsupported_warehouse"
    with pytest.raises(ValidationError):
        s.full_clean()

    s.target_warehouse = "snowflake"
    s.sync_mode = "invalid_mode"
    with pytest.raises(ValidationError):
        s.full_clean()

    s.sync_mode = "incremental_merge"
    s.sync_schedule = "invalid_schedule"
    with pytest.raises(ValidationError):
        s.full_clean()

    s.sync_schedule = "daily"
    s.status = "invalid_status"
    with pytest.raises(ValidationError):
        s.full_clean()


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_slug_autogen_and_deduplication(tenant_a):
    """Verify slug generation and collision deduplication within same tenant."""
    s1 = _integrationhub_create_sync_endpoint(tenant_a, name="Warehouse Daily Sync")
    s2 = _integrationhub_create_sync_endpoint(tenant_a, name="Warehouse Daily Sync")
    s3 = _integrationhub_create_sync_endpoint(tenant_a, name="Warehouse Daily Sync")

    assert s1.slug == "warehouse-daily-sync"
    assert s2.slug == "warehouse-daily-sync-1"
    assert s3.slug == "warehouse-daily-sync-2"


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_same_slug_different_tenants(tenant_a, tenant_b):
    """Verify endpoints in different tenants can have the same slug."""
    s_a = _integrationhub_create_sync_endpoint(tenant_a, name="Global Redshift Mart")
    s_b = _integrationhub_create_sync_endpoint(tenant_b, name="Global Redshift Mart")

    assert s_a.slug == "global-redshift-mart"
    assert s_b.slug == "global-redshift-mart"
    assert s_a.tenant != s_b.tenant


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_unique_number(tenant_a):
    """Verify bi_bsnc_ten_num_uniq constraint prevents duplicate number in same tenant."""
    s1 = _integrationhub_create_sync_endpoint(tenant_a, name="Original Sync Endpoint")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_sync_endpoint(tenant_a, name="Duplicate Number Endpoint", number=s1.number)


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_unique_slug(tenant_a):
    """Verify bi_bsnc_ten_slug_uniq constraint prevents duplicate forced slug in same tenant."""
    _integrationhub_create_sync_endpoint(tenant_a, name="First Slug", slug="unique-sync-slug")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_sync_endpoint(tenant_a, name="Second Slug", slug="unique-sync-slug")


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_foreign_keys_set_null(tenant_a, data_mart_a, semantic_model_a, admin_user):
    """Verify data_mart, semantic_model, and owner FKs set to NULL on deletion."""
    s = _integrationhub_create_sync_endpoint(
        tenant_a,
        name="Governed Feed Sync",
        data_mart=data_mart_a,
        semantic_model=semantic_model_a,
        owner=admin_user,
    )
    assert s.data_mart == data_mart_a
    assert s.semantic_model == semantic_model_a
    assert s.owner == admin_user

    # Delete semantic_model
    semantic_model_a.delete()
    s.refresh_from_db()
    assert s.semantic_model is None
    assert s.data_mart == data_mart_a


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_owner_set_null(tenant_a):
    """Verify user deletion sets owner to NULL via SET_NULL."""
    user = User.objects.create_user(
        email="sync_owner@example.com",
        username="sync_owner",
        password="testpassword",
        tenant=tenant_a,
    )
    s = _integrationhub_create_sync_endpoint(tenant_a, name="Owner Bound Sync", owner=user)
    assert s.owner == user

    user.delete()
    s.refresh_from_db()
    assert s.owner is None


@pytest.mark.django_db
def test_integrationhub_models_warehouse_sync_sync_modes_and_schedules(tenant_a):
    """Verify diverse combinations of target warehouse, sync modes, and metrics."""
    s = _integrationhub_create_sync_endpoint(
        tenant_a,
        name="Databricks Delta Sharing Feed",
        target_warehouse="databricks_unity",
        sync_mode="delta_sharing",
        sync_schedule="event_triggered",
        destination_database="CATALOG_PROD",
        destination_schema="GOLD_ANALYTICS",
        destination_table="FACT_LEDGER_ENTRIES",
        status="success",
        last_sync_duration_ms=4520,
        last_rows_synced=82500,
        total_rows_synced=1420000,
    )
    s.refresh_from_db()
    assert s.target_warehouse == "databricks_unity"
    assert s.sync_mode == "delta_sharing"
    assert s.last_sync_duration_ms == 4520
    assert s.last_rows_synced == 82500
    assert s.total_rows_synced == 1420000


# ===========================================================================
# 3. BiWebhookSubscription Model Tests (BWHK)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_models_webhook_fixture_and_str(bi_webhook_subscription_a):
    """Test BiWebhookSubscription fixture from conftest, prefix, and __str__ representation."""
    assert bi_webhook_subscription_a.pk is not None
    assert bi_webhook_subscription_a.number.startswith("BWHK-")
    expected_str = f"{bi_webhook_subscription_a.number} - {bi_webhook_subscription_a.name} ({bi_webhook_subscription_a.endpoint_url[:40]})"
    assert str(bi_webhook_subscription_a) == expected_str


@pytest.mark.django_db
def test_integrationhub_models_webhook_autonumbering(tenant_a):
    """Test auto-number sequence BWHK-##### increments monotonically per tenant."""
    w1 = _integrationhub_create_webhook(tenant_a, name="Webhook Alpha")
    w2 = _integrationhub_create_webhook(tenant_a, name="Webhook Beta")

    assert w1.number.startswith("BWHK-")
    assert w2.number.startswith("BWHK-")
    num1 = int(w1.number.split("-")[1])
    num2 = int(w2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_integrationhub_models_webhook_defaults(tenant_a):
    """Verify default field values on minimal BiWebhookSubscription."""
    w = BiWebhookSubscription.objects.create(
        tenant=tenant_a,
        name="Default Webhook",
        endpoint_url="https://hooks.acme.corp/bi-events",
    )

    assert w.payload_format == "standard_json"
    assert w.max_retries == 3
    assert w.timeout_seconds == 10
    assert w.status == "active"
    assert w.consecutive_failures == 0
    assert w.last_response_time_ms == 0
    assert w.total_deliveries == 0
    assert w.is_active is True
    assert w.event_types == []
    assert w.custom_headers == {}
    assert w.secret_token.startswith("whsec_")


@pytest.mark.django_db
def test_integrationhub_models_webhook_secret_token_auto_generation(tenant_a):
    """Verify secret token is automatically generated with whsec_ prefix when omitted."""
    w = _integrationhub_create_webhook(tenant_a, name="Token Auto Webhook", secret_token="")
    assert w.secret_token.startswith("whsec_")
    assert len(w.secret_token) > 20


@pytest.mark.django_db
def test_integrationhub_models_webhook_secret_token_custom_preserved(tenant_a):
    """Verify custom secret token is preserved upon creation."""
    custom_secret = "whsec_custom_established_secret_abc123"
    w = _integrationhub_create_webhook(tenant_a, name="Custom Secret Webhook", secret_token=custom_secret)
    w.refresh_from_db()
    assert w.secret_token == custom_secret


@pytest.mark.django_db
def test_integrationhub_models_webhook_choices():
    """Verify choices lists exposed on BiWebhookSubscription."""
    format_keys = _integrationhub_choice_keys(BiWebhookSubscription.PAYLOAD_FORMAT_CHOICES)
    assert "standard_json" in format_keys
    assert "cloudevents_v1" in format_keys
    assert "slack_compatible" in format_keys
    assert "compact_minimal" in format_keys

    status_keys = _integrationhub_choice_keys(BiWebhookSubscription.STATUS_CHOICES)
    assert "active" in status_keys
    assert "suspended" in status_keys
    assert "failing" in status_keys
    assert "disabled" in status_keys


@pytest.mark.django_db
def test_integrationhub_models_webhook_choice_validation_valid(tenant_a):
    """Verify valid choices pass full_clean validation."""
    w = _integrationhub_create_webhook(
        tenant_a,
        name="CloudEvents Hook",
        payload_format="cloudevents_v1",
        status="suspended",
    )
    w.full_clean()
    assert w.payload_format == "cloudevents_v1"
    assert w.status == "suspended"


@pytest.mark.django_db
def test_integrationhub_models_webhook_choice_validation_invalid(tenant_a):
    """Verify invalid choice values raise ValidationError on full_clean."""
    w = _integrationhub_create_webhook(tenant_a, name="Invalid Webhook")

    w.payload_format = "invalid_format"
    with pytest.raises(ValidationError):
        w.full_clean()

    w.payload_format = "standard_json"
    w.status = "invalid_status"
    with pytest.raises(ValidationError):
        w.full_clean()


@pytest.mark.django_db
def test_integrationhub_models_webhook_unique_number(tenant_a):
    """Verify bi_bwhk_ten_num_uniq constraint prevents duplicate number in same tenant."""
    w1 = _integrationhub_create_webhook(tenant_a, name="Original Webhook")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_webhook(tenant_a, name="Duplicate Number Webhook", number=w1.number)


@pytest.mark.django_db
def test_integrationhub_models_webhook_created_by_set_null(tenant_a):
    """Verify user deletion sets created_by to NULL via SET_NULL."""
    user = User.objects.create_user(
        email="webhook_author@example.com",
        username="webhook_author",
        password="testpassword",
        tenant=tenant_a,
    )
    w = _integrationhub_create_webhook(tenant_a, name="Authored Webhook", created_by=user)
    assert w.created_by == user

    user.delete()
    w.refresh_from_db()
    assert w.created_by is None


@pytest.mark.django_db
def test_integrationhub_models_webhook_json_fields(tenant_a):
    """Verify event_types and custom_headers store and retrieve structured data."""
    events = ["kpi.breached", "etl.completed", "anomaly.detected"]
    headers = {"Authorization": "Bearer token123", "X-Service-Name": "NavERP-Dispatcher"}

    w = _integrationhub_create_webhook(
        tenant_a,
        name="Header & Event Hook",
        event_types=events,
        custom_headers=headers,
    )
    w.refresh_from_db()
    assert w.event_types == events
    assert w.custom_headers == headers


@pytest.mark.django_db
def test_integrationhub_models_webhook_status_variants(tenant_a):
    """Verify webhook operational metrics update and persist correctly."""
    w = _integrationhub_create_webhook(
        tenant_a,
        name="Incident Alert Hook",
        status="failing",
        consecutive_failures=5,
        last_response_code=504,
        last_response_time_ms=10050,
        last_error_log="Gateway Timeout: Target hook endpoint took > 10s to respond",
        total_deliveries=42,
    )
    w.refresh_from_db()
    assert w.status == "failing"
    assert w.consecutive_failures == 5
    assert w.last_response_code == 504
    assert w.last_response_time_ms == 10050
    assert "Gateway Timeout" in w.last_error_log
    assert w.total_deliveries == 42


# ===========================================================================
# 4. BiExtensionPlugin Model Tests (BEXT)
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_models_plugin_fixture_and_str(bi_extension_plugin_a):
    """Test BiExtensionPlugin fixture from conftest, prefix, and __str__ representation."""
    assert bi_extension_plugin_a.pk is not None
    assert bi_extension_plugin_a.number.startswith("BEXT-")
    expected_str = f"{bi_extension_plugin_a.number} - {bi_extension_plugin_a.name} v{bi_extension_plugin_a.version} ({bi_extension_plugin_a.plugin_identifier})"
    assert str(bi_extension_plugin_a) == expected_str


@pytest.mark.django_db
def test_integrationhub_models_plugin_autonumbering(tenant_a):
    """Test auto-number sequence BEXT-##### increments monotonically per tenant."""
    p1 = _integrationhub_create_plugin(tenant_a, name="Plugin Alpha", plugin_identifier="org.naverp.alpha")
    p2 = _integrationhub_create_plugin(tenant_a, name="Plugin Beta", plugin_identifier="org.naverp.beta")

    assert p1.number.startswith("BEXT-")
    assert p2.number.startswith("BEXT-")
    num1 = int(p1.number.split("-")[1])
    num2 = int(p2.number.split("-")[1])
    assert num2 == num1 + 1


@pytest.mark.django_db
def test_integrationhub_models_plugin_defaults(tenant_a):
    """Verify default field values on minimal BiExtensionPlugin."""
    p = BiExtensionPlugin.objects.create(
        tenant=tenant_a,
        name="Default Chord Diagram",
        plugin_identifier="io.naverp.visuals.chord",
        author_name="Visual Labs",
    )

    assert p.version == "1.0.0"
    assert p.plugin_type == "custom_visual"
    assert p.category == "visualization"
    assert p.license == "MIT"
    assert p.status == "installed"
    assert p.is_verified is False
    assert p.is_system_plugin is False
    assert p.manifest_metadata == {}
    assert p.config_schema == {}
    assert p.current_config == {}
    assert p.permissions_required == []


@pytest.mark.django_db
def test_integrationhub_models_plugin_choices():
    """Verify choices lists exposed on BiExtensionPlugin."""
    type_keys = _integrationhub_choice_keys(BiExtensionPlugin.PLUGIN_TYPE_CHOICES)
    assert "custom_visual" in type_keys
    assert "connector_plugin" in type_keys
    assert "transformation_script" in type_keys
    assert "dashboard_extension" in type_keys
    assert "metric_provider" in type_keys

    cat_keys = _integrationhub_choice_keys(BiExtensionPlugin.CATEGORY_CHOICES)
    assert "visualization" in cat_keys
    assert "data_integration" in cat_keys
    assert "governance" in cat_keys
    assert "advanced_analytics" in cat_keys
    assert "workflow_action" in cat_keys

    status_keys = _integrationhub_choice_keys(BiExtensionPlugin.STATUS_CHOICES)
    assert "installed" in status_keys
    assert "enabled" in status_keys
    assert "disabled" in status_keys
    assert "deprecated" in status_keys
    assert "quarantined" in status_keys


@pytest.mark.django_db
def test_integrationhub_models_plugin_choice_validation_valid(tenant_a):
    """Verify valid choices pass full_clean validation."""
    p = _integrationhub_create_plugin(
        tenant_a,
        name="Connector Plugin",
        plugin_identifier="org.naverp.plugins.sap_connector",
        plugin_type="connector_plugin",
        category="data_integration",
        status="enabled",
    )
    p.full_clean()
    assert p.plugin_type == "connector_plugin"
    assert p.category == "data_integration"
    assert p.status == "enabled"


@pytest.mark.django_db
def test_integrationhub_models_plugin_choice_validation_invalid(tenant_a):
    """Verify invalid choice values raise ValidationError on full_clean."""
    p = _integrationhub_create_plugin(tenant_a, name="Invalid Plugin", plugin_identifier="org.naverp.invalid")

    p.plugin_type = "invalid_plugin_type"
    with pytest.raises(ValidationError):
        p.full_clean()

    p.plugin_type = "custom_visual"
    p.category = "invalid_category"
    with pytest.raises(ValidationError):
        p.full_clean()

    p.category = "visualization"
    p.status = "invalid_status"
    with pytest.raises(ValidationError):
        p.full_clean()


@pytest.mark.django_db
def test_integrationhub_models_plugin_unique_number(tenant_a):
    """Verify bi_bext_ten_num_uniq constraint prevents duplicate number in same tenant."""
    p1 = _integrationhub_create_plugin(tenant_a, name="Original Plugin", plugin_identifier="org.naverp.orig")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_plugin(
                tenant_a,
                name="Duplicate Number Plugin",
                plugin_identifier="org.naverp.dupnum",
                number=p1.number,
            )


@pytest.mark.django_db
def test_integrationhub_models_plugin_unique_identifier(tenant_a):
    """Verify bi_bext_ten_ident_uniq constraint prevents duplicate identifier in same tenant."""
    shared_id = "org.naverp.visuals.waterfall"
    _integrationhub_create_plugin(tenant_a, name="Waterfall A", plugin_identifier=shared_id)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            _integrationhub_create_plugin(tenant_a, name="Waterfall B", plugin_identifier=shared_id)


@pytest.mark.django_db
def test_integrationhub_models_plugin_same_identifier_different_tenants(tenant_a, tenant_b):
    """Verify extension plugins in different tenants can have the same plugin_identifier."""
    shared_id = "com.marketplace.d3.sankey"
    p_a = _integrationhub_create_plugin(tenant_a, name="Sankey Tenant A", plugin_identifier=shared_id)
    p_b = _integrationhub_create_plugin(tenant_b, name="Sankey Tenant B", plugin_identifier=shared_id)

    assert p_a.plugin_identifier == shared_id
    assert p_b.plugin_identifier == shared_id
    assert p_a.tenant != p_b.tenant


@pytest.mark.django_db
def test_integrationhub_models_plugin_installed_by_set_null(tenant_a):
    """Verify user deletion sets installed_by to NULL via SET_NULL."""
    user = User.objects.create_user(
        email="plugin_admin@example.com",
        username="plugin_admin",
        password="testpassword",
        tenant=tenant_a,
    )
    p = _integrationhub_create_plugin(
        tenant_a,
        name="Admin Installed Plugin",
        plugin_identifier="org.naverp.admin.plugin",
        installed_by=user,
    )
    assert p.installed_by == user

    user.delete()
    p.refresh_from_db()
    assert p.installed_by is None


@pytest.mark.django_db
def test_integrationhub_models_plugin_json_fields(tenant_a):
    """Verify JSON fields store and retrieve manifest, schemas, and permissions."""
    manifest = {
        "entrypoint_js": "bundle.js",
        "entrypoint_css": "bundle.css",
        "min_bi_version": "5.1.0",
        "icon_svg": "<svg>...</svg>",
    }
    schema = {
        "type": "object",
        "properties": {
            "api_endpoint": {"type": "string"},
            "refresh_seconds": {"type": "integer", "default": 60},
        },
    }
    config = {"api_endpoint": "https://service.example.com", "refresh_seconds": 30}
    perms = ["read_semantic_layer", "export_raw_data"]

    p = _integrationhub_create_plugin(
        tenant_a,
        name="Rich JSON Plugin",
        plugin_identifier="io.naverp.plugins.rich",
        manifest_metadata=manifest,
        config_schema=schema,
        current_config=config,
        permissions_required=perms,
        is_verified=True,
        is_system_plugin=True,
    )
    p.refresh_from_db()
    assert p.manifest_metadata == manifest
    assert p.config_schema == schema
    assert p.current_config == config
    assert p.permissions_required == perms
    assert p.is_verified is True
    assert p.is_system_plugin is True


@pytest.mark.django_db
def test_integrationhub_models_plugin_types_and_categories(tenant_a):
    """Verify various plugin types and operational statuses."""
    p = _integrationhub_create_plugin(
        tenant_a,
        name="Transform Hook Extension",
        plugin_identifier="org.naverp.transform.pyclean",
        plugin_type="transformation_script",
        category="advanced_analytics",
        version="2.4.1",
        status="quarantined",
    )
    p.refresh_from_db()
    assert p.plugin_type == "transformation_script"
    assert p.category == "advanced_analytics"
    assert p.version == "2.4.1"
    assert p.status == "quarantined"


# ===========================================================================
# 5. Metadata, Cascade Deletion & Tenant Isolation Tests
# ===========================================================================


@pytest.mark.django_db
def test_integrationhub_models_meta_table_names_and_indexes():
    """Verify table names, composite indexes, and constraints on all 4 models."""
    # 1. IntegrationConnector
    assert IntegrationConnector._meta.db_table == "bi_integration_connector"
    c_indexes = [idx.name for idx in IntegrationConnector._meta.indexes]
    assert "idx_bint_ten_stat" in c_indexes
    assert "idx_bint_ten_type" in c_indexes
    assert "idx_bint_ten_target" in c_indexes
    assert "idx_bint_ten_intv" in c_indexes
    assert "idx_bint_ten_enb" in c_indexes
    assert "idx_bint_ten_created" in c_indexes
    c_constraints = [c.name for c in IntegrationConnector._meta.constraints]
    assert "bi_bint_ten_num_uniq" in c_constraints
    assert "bi_bint_ten_slug_uniq" in c_constraints

    # 2. WarehouseSyncEndpoint
    assert WarehouseSyncEndpoint._meta.db_table == "bi_warehouse_sync_endpoint"
    s_indexes = [idx.name for idx in WarehouseSyncEndpoint._meta.indexes]
    assert "idx_bsnc_ten_stat" in s_indexes
    assert "idx_bsnc_ten_wh" in s_indexes
    assert "idx_bsnc_ten_sem" in s_indexes
    assert "idx_bsnc_ten_mart" in s_indexes
    assert "idx_bsnc_ten_mode" in s_indexes
    assert "idx_bsnc_ten_sched" in s_indexes
    assert "idx_bsnc_ten_act" in s_indexes
    assert "idx_bsnc_ten_created" in s_indexes
    s_constraints = [c.name for c in WarehouseSyncEndpoint._meta.constraints]
    assert "bi_bsnc_ten_num_uniq" in s_constraints
    assert "bi_bsnc_ten_slug_uniq" in s_constraints

    # 3. BiWebhookSubscription
    assert BiWebhookSubscription._meta.db_table == "bi_webhook_subscription"
    w_indexes = [idx.name for idx in BiWebhookSubscription._meta.indexes]
    assert "idx_bwhk_ten_stat" in w_indexes
    assert "idx_bwhk_ten_act" in w_indexes
    assert "idx_bwhk_ten_fmt" in w_indexes
    assert "idx_bwhk_ten_created" in w_indexes
    w_constraints = [c.name for c in BiWebhookSubscription._meta.constraints]
    assert "bi_bwhk_ten_num_uniq" in w_constraints

    # 4. BiExtensionPlugin
    assert BiExtensionPlugin._meta.db_table == "bi_extension_plugin"
    p_indexes = [idx.name for idx in BiExtensionPlugin._meta.indexes]
    assert "idx_bext_ten_stat" in p_indexes
    assert "idx_bext_ten_type" in p_indexes
    assert "idx_bext_ten_cat" in p_indexes
    assert "idx_bext_ten_ver" in p_indexes
    assert "idx_bext_ten_created" in p_indexes
    p_constraints = [c.name for c in BiExtensionPlugin._meta.constraints]
    assert "bi_bext_ten_num_uniq" in p_constraints
    assert "bi_bext_ten_ident_uniq" in p_constraints


@pytest.mark.django_db
def test_integrationhub_models_tenant_cascade_delete():
    """Verify that deleting a tenant cascades and removes all associated records across all 4 models."""
    temp_tenant = Tenant.objects.create(
        name="IntegrationHub Ephemeral Tenant",
        slug="ihub-ephemeral-tenant",
    )

    connector = _integrationhub_create_connector(temp_tenant, name="Ephemeral Connector")
    sync_endpoint = _integrationhub_create_sync_endpoint(temp_tenant, name="Ephemeral Sync")
    webhook = _integrationhub_create_webhook(temp_tenant, name="Ephemeral Hook")
    plugin = _integrationhub_create_plugin(temp_tenant, name="Ephemeral Plugin", plugin_identifier="org.temp.plugin")

    c_id = connector.pk
    s_id = sync_endpoint.pk
    w_id = webhook.pk
    p_id = plugin.pk

    assert IntegrationConnector.objects.filter(pk=c_id).exists()
    assert WarehouseSyncEndpoint.objects.filter(pk=s_id).exists()
    assert BiWebhookSubscription.objects.filter(pk=w_id).exists()
    assert BiExtensionPlugin.objects.filter(pk=p_id).exists()

    temp_tenant.delete()

    assert not IntegrationConnector.objects.filter(pk=c_id).exists()
    assert not WarehouseSyncEndpoint.objects.filter(pk=s_id).exists()
    assert not BiWebhookSubscription.objects.filter(pk=w_id).exists()
    assert not BiExtensionPlugin.objects.filter(pk=p_id).exists()


@pytest.mark.django_db
def test_integrationhub_models_tenant_isolation_queries(
    tenant_a,
    tenant_b,
    integration_connector_a,
    integration_connector_b,
    warehouse_sync_endpoint_a,
    warehouse_sync_endpoint_b,
    bi_webhook_subscription_a,
    bi_webhook_subscription_b,
    bi_extension_plugin_a,
    bi_extension_plugin_b,
):
    """Verify tenant isolation filters accurately partition records between tenant_a and tenant_b."""
    # 1. IntegrationConnector
    qs_c_a = IntegrationConnector.objects.filter(tenant=tenant_a)
    assert integration_connector_a in qs_c_a
    assert integration_connector_b not in qs_c_a

    qs_c_b = IntegrationConnector.objects.filter(tenant=tenant_b)
    assert integration_connector_b in qs_c_b
    assert integration_connector_a not in qs_c_b

    # 2. WarehouseSyncEndpoint
    qs_s_a = WarehouseSyncEndpoint.objects.filter(tenant=tenant_a)
    assert warehouse_sync_endpoint_a in qs_s_a
    assert warehouse_sync_endpoint_b not in qs_s_a

    qs_s_b = WarehouseSyncEndpoint.objects.filter(tenant=tenant_b)
    assert warehouse_sync_endpoint_b in qs_s_b
    assert warehouse_sync_endpoint_a not in qs_s_b

    # 3. BiWebhookSubscription
    qs_w_a = BiWebhookSubscription.objects.filter(tenant=tenant_a)
    assert bi_webhook_subscription_a in qs_w_a
    assert bi_webhook_subscription_b not in qs_w_a

    qs_w_b = BiWebhookSubscription.objects.filter(tenant=tenant_b)
    assert bi_webhook_subscription_b in qs_w_b
    assert bi_webhook_subscription_a not in qs_w_b

    # 4. BiExtensionPlugin
    qs_p_a = BiExtensionPlugin.objects.filter(tenant=tenant_a)
    assert bi_extension_plugin_a in qs_p_a
    assert bi_extension_plugin_b not in qs_p_a

    qs_p_b = BiExtensionPlugin.objects.filter(tenant=tenant_b)
    assert bi_extension_plugin_b in qs_p_b
    assert bi_extension_plugin_a not in qs_p_b
