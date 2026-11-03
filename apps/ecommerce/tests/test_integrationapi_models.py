"""Unit tests for Sub-module 9.19 Integration & API Ecosystem models.

Covers:
- EcommerceConnector: creation, prefix ECON-, __str__, choices, defaults, tenant isolation.
- IntegrationSyncJob: creation, prefix ESYJ-, __str__, choices, parent_job retries, FK cascade & set_null, tenant isolation.
- WebhookSubscription: creation, prefix EWBS-, __str__, event topics, defaults, secret key, tenant isolation.
- ApiCredential: creation, prefix EAPC-, __str__, client_id uniqueness, scopes_list property, tier choices, tenant isolation.
"""
from decimal import Decimal
import hashlib
import secrets
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.ecommerce.models import (
    EcommerceConnector,
    IntegrationSyncJob,
    WebhookSubscription,
    ApiCredential,
)

from apps.ecommerce.tests.conftest import INTEGRATIONAPI_MODEL_FIELDS

pytestmark = pytest.mark.django_db


# ==============================================================================
# Model Contract Fields Test
# ==============================================================================

def test_integrationapi_model_contract_fields():
    """Assert all 4 models contain the exact fields pinned in INTEGRATIONAPI_MODEL_FIELDS."""
    model_map = {
        "EcommerceConnector": EcommerceConnector,
        "IntegrationSyncJob": IntegrationSyncJob,
        "WebhookSubscription": WebhookSubscription,
        "ApiCredential": ApiCredential,
    }
    for model_name, expected_fields in INTEGRATIONAPI_MODEL_FIELDS.items():
        model_cls = model_map[model_name]
        actual_fields = {f.name for f in model_cls._meta.get_fields()}
        for field in expected_fields:
            assert field in actual_fields, f"Field '{field}' missing from {model_name}"


# ==============================================================================
# Module Helpers (Prefixed with _integrationapi_*)
# ==============================================================================

def _integrationapi_create_connector(tenant, **kwargs):
    """Create a helper EcommerceConnector with defaults."""
    params = {
        "tenant": tenant,
        "name": "Acme REST Connector",
        "category": "erp",
        "provider": "generic_rest",
        "auth_type": "api_key",
        "status": "active",
        "base_url": "https://api.acme-erp.internal/v1",
        "api_key": "acme_secret_key_123",
        "timeout_seconds": 45,
        "rate_limit_per_minute": 150,
    }
    params.update(kwargs)
    return EcommerceConnector.objects.create(**params)


def _integrationapi_create_sync_job(tenant, connector, **kwargs):
    """Create a helper IntegrationSyncJob with defaults."""
    params = {
        "tenant": tenant,
        "connector": connector,
        "sync_entity": "order_to_cash",
        "direction": "outbound",
        "status": "pending",
        "trigger_type": "manual",
        "records_total": 25,
    }
    params.update(kwargs)
    return IntegrationSyncJob.objects.create(**params)


def _integrationapi_create_webhook(tenant, **kwargs):
    """Create a helper WebhookSubscription with defaults."""
    params = {
        "tenant": tenant,
        "name": "Order Dispatch Listener",
        "target_url": f"https://dispatcher.external.io/events/{tenant.pk}/",
        "event_topic": "order.fulfilled",
        "status": "active",
        "secret_key": secrets.token_hex(20),
        "is_verify_ssl": True,
    }
    params.update(kwargs)
    return WebhookSubscription.objects.create(**params)


def _integrationapi_create_credential(tenant, **kwargs):
    """Create a helper ApiCredential with defaults."""
    client_id = kwargs.pop("client_id", f"nep_test_cid_{secrets.token_hex(8)}")
    params = {
        "tenant": tenant,
        "name": "Internal Microservice Key",
        "client_id": client_id,
        "client_secret_hash": hashlib.sha256(b"secret123").hexdigest(),
        "status": "active",
        "tier": "storefront_public",
        "scopes": "read_catalog,read_orders",
        "rate_limit_rpm": 90,
    }
    params.update(kwargs)
    return ApiCredential.objects.create(**params)


# ==============================================================================
# EcommerceConnector Unit Tests
# ==============================================================================

def test_integrationapi_connector_creation_and_numbering(tenant_a, ecom_connector_a):
    """Test EcommerceConnector creation, ECON- prefix numbering, defaults, and __str__."""
    assert ecom_connector_a.pk is not None
    assert ecom_connector_a.tenant == tenant_a
    assert ecom_connector_a.number.startswith("ECON-")
    assert str(ecom_connector_a) == f"{ecom_connector_a.number} - {ecom_connector_a.name} ({ecom_connector_a.get_provider_display()})"

    # Test explicit creation with default values
    conn = _integrationapi_create_connector(
        tenant_a,
        name="NetSuite ERP Production",
        category="erp",
        provider="netsuite",
    )
    assert conn.pk is not None
    assert conn.number.startswith("ECON-")
    assert conn.auth_type == "api_key"
    assert conn.status == "active"
    assert conn.health_status == "healthy"
    assert conn.is_sandbox is False
    assert conn.timeout_seconds == 45
    assert conn.rate_limit_per_minute == 150
    assert conn.api_version == "v1"
    assert str(conn) == f"{conn.number} - NetSuite ERP Production (Oracle NetSuite ERP)"


def test_integrationapi_connector_choices_validation(tenant_a):
    """Test EcommerceConnector choices for category, provider, auth_type, and status."""
    # Category choices
    valid_categories = ["erp", "payment", "shipping", "marketing", "custom"]
    for cat in valid_categories:
        conn = _integrationapi_create_connector(tenant_a, name=f"Conn {cat}", category=cat)
        assert conn.category == cat

    # Provider choices
    key_providers = ["stripe", "paypal", "fedex", "ups", "klaviyo", "generic_rest", "other"]
    for prov in key_providers:
        conn = _integrationapi_create_connector(tenant_a, name=f"Conn {prov}", provider=prov)
        assert conn.provider == prov
        assert conn.get_provider_display() != ""

    # Auth type choices
    valid_auth_types = ["api_key", "bearer_token", "oauth2", "basic_auth", "hmac_secret", "none"]
    for auth in valid_auth_types:
        conn = _integrationapi_create_connector(tenant_a, name=f"Conn {auth}", auth_type=auth)
        assert conn.auth_type == auth

    # Status choices
    valid_statuses = ["active", "inactive", "testing", "error", "maintenance"]
    for st in valid_statuses:
        conn = _integrationapi_create_connector(tenant_a, name=f"Conn {st}", status=st)
        assert conn.status == st


def test_integrationapi_connector_tenant_isolation(tenant_a, tenant_b, ecom_connector_a, ecom_connector_b):
    """Test EcommerceConnector tenant isolation and unique (tenant, number) constraint."""
    # Queryset isolation
    a_ids = list(EcommerceConnector.objects.filter(tenant=tenant_a).values_list("id", flat=True))
    b_ids = list(EcommerceConnector.objects.filter(tenant=tenant_b).values_list("id", flat=True))
    assert ecom_connector_a.id in a_ids
    assert ecom_connector_a.id not in b_ids
    assert ecom_connector_b.id in b_ids
    assert ecom_connector_b.id not in a_ids

    # Duplicate number in same tenant violates UniqueConstraint
    with pytest.raises(IntegrityError):
        EcommerceConnector.objects.create(
            tenant=tenant_a,
            number=ecom_connector_a.number,
            name="Conflicting Connector",
        )


# ==============================================================================
# IntegrationSyncJob Unit Tests
# ==============================================================================

def test_integrationapi_sync_job_creation_and_numbering(tenant_a, ecom_connector_a, ecom_sync_job_a):
    """Test IntegrationSyncJob creation, ESYJ- prefix numbering, defaults, and __str__."""
    assert ecom_sync_job_a.pk is not None
    assert ecom_sync_job_a.tenant == tenant_a
    assert ecom_sync_job_a.number.startswith("ESYJ-")
    assert str(ecom_sync_job_a) == f"{ecom_sync_job_a.number} - {ecom_sync_job_a.get_sync_entity_display()} ({ecom_sync_job_a.get_status_display()})"

    # Test explicit creation with defaults
    job = _integrationapi_create_sync_job(
        tenant_a,
        ecom_connector_a,
        sync_entity="inventory_levels",
        direction="inbound",
        status="running",
    )
    assert job.pk is not None
    assert job.number.startswith("ESYJ-")
    assert job.records_processed == 0
    assert job.records_succeeded == 0
    assert job.records_failed == 0
    assert job.duration_seconds == Decimal("0.00")
    assert job.retry_count == 0
    assert job.max_retries == 3
    assert job.batch_id == ""
    assert str(job) == f"{job.number} - Inventory Levels & Stock Availability (Running / In-Progress)"


def test_integrationapi_sync_job_choices_validation(tenant_a, ecom_connector_a):
    """Test IntegrationSyncJob choices for sync_entity, direction, status, and trigger_type."""
    # Sync entity choices
    entities = [
        "order_to_cash", "inventory_levels", "catalog_products",
        "customer_profiles", "shipment_tracking", "payment_settlement",
        "marketing_events", "custom_payload",
    ]
    for entity in entities:
        job = _integrationapi_create_sync_job(tenant_a, ecom_connector_a, sync_entity=entity)
        assert job.sync_entity == entity
        assert job.get_sync_entity_display() != ""

    # Direction choices
    for direction in ["inbound", "outbound", "bidirectional"]:
        job = _integrationapi_create_sync_job(tenant_a, ecom_connector_a, direction=direction)
        assert job.direction == direction

    # Status choices
    for st in ["pending", "running", "completed", "failed", "partial_success", "cancelled"]:
        job = _integrationapi_create_sync_job(tenant_a, ecom_connector_a, status=st)
        assert job.status == st

    # Trigger choices
    for trig in ["scheduled", "manual", "webhook", "event_driven"]:
        job = _integrationapi_create_sync_job(tenant_a, ecom_connector_a, trigger_type=trig)
        assert job.trigger_type == trig


def test_integrationapi_sync_job_parent_retry_relationship(tenant_a, ecom_connector_a):
    """Test self-referential parent_job / child_retries and on_delete=SET_NULL behavior."""
    parent = _integrationapi_create_sync_job(
        tenant_a,
        ecom_connector_a,
        status="failed",
        error_summary="HTTP 504 Gateway Timeout",
    )
    retry_1 = _integrationapi_create_sync_job(
        tenant_a,
        ecom_connector_a,
        parent_job=parent,
        retry_count=1,
        status="failed",
    )
    retry_2 = _integrationapi_create_sync_job(
        tenant_a,
        ecom_connector_a,
        parent_job=parent,
        retry_count=2,
        status="completed",
    )

    # Check child retries related manager
    children = list(parent.child_retries.all())
    assert retry_1 in children
    assert retry_2 in children
    assert len(children) == 2

    # Deleting parent job should set child parent_job to None (SET_NULL)
    parent_id = parent.id
    parent.delete()
    retry_1.refresh_from_db()
    assert retry_1.parent_job is None
    retry_2.refresh_from_db()
    assert retry_2.parent_job is None


def test_integrationapi_sync_job_foreign_key_behaviors(tenant_a):
    """Test connector on_delete=CASCADE and triggered_by on_delete=SET_NULL."""
    user_model = get_user_model()
    uid = secrets.token_hex(4)
    temp_user = user_model.objects.create_user(
        username=f"sync_worker_{uid}",
        email=f"sync_worker_{uid}@example.com",
        password="secretpassword",
    )
    temp_connector = _integrationapi_create_connector(tenant_a, name="Temporary Connector")
    job = _integrationapi_create_sync_job(
        tenant_a,
        temp_connector,
        triggered_by=temp_user,
    )

    # Deleting user should SET_NULL on triggered_by
    temp_user.delete()
    job.refresh_from_db()
    assert job.triggered_by is None

    # Deleting connector should CASCADE delete the sync job
    temp_connector.delete()
    assert not IntegrationSyncJob.objects.filter(id=job.id).exists()


def test_integrationapi_sync_job_tenant_isolation(tenant_a, tenant_b, ecom_sync_job_a, ecom_sync_job_b):
    """Test IntegrationSyncJob tenant isolation and unique (tenant, number) constraint."""
    # Queryset isolation
    a_ids = list(IntegrationSyncJob.objects.filter(tenant=tenant_a).values_list("id", flat=True))
    b_ids = list(IntegrationSyncJob.objects.filter(tenant=tenant_b).values_list("id", flat=True))
    assert ecom_sync_job_a.id in a_ids
    assert ecom_sync_job_a.id not in b_ids
    assert ecom_sync_job_b.id in b_ids
    assert ecom_sync_job_b.id not in a_ids

    # Duplicate number in same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        IntegrationSyncJob.objects.create(
            tenant=tenant_a,
            connector=ecom_sync_job_a.connector,
            number=ecom_sync_job_a.number,
        )


# ==============================================================================
# WebhookSubscription Unit Tests
# ==============================================================================

def test_integrationapi_webhook_subscription_creation_and_defaults(tenant_a, ecom_webhook_a):
    """Test WebhookSubscription creation, EWBS- prefix numbering, defaults, and __str__."""
    assert ecom_webhook_a.pk is not None
    assert ecom_webhook_a.tenant == tenant_a
    assert ecom_webhook_a.number.startswith("EWBS-")
    assert str(ecom_webhook_a) == f"{ecom_webhook_a.number} - {ecom_webhook_a.name} ({ecom_webhook_a.event_topic})"

    # Test explicit creation with defaults
    sub = _integrationapi_create_webhook(
        tenant_a,
        name="CRM Customer Sync Webhook",
        event_topic="customer.registered",
    )
    assert sub.pk is not None
    assert sub.number.startswith("EWBS-")
    assert sub.status == "active"
    assert sub.payload_format == "json"
    assert sub.is_verify_ssl is True
    assert sub.consecutive_failures == 0
    assert sub.max_consecutive_failures == 5
    assert sub.total_delivered_count == 0
    assert sub.total_failed_count == 0
    assert str(sub) == f"{sub.number} - CRM Customer Sync Webhook (customer.registered)"


def test_integrationapi_webhook_subscription_choices_validation(tenant_a):
    """Test WebhookSubscription choices for event_topic, status, and payload_format."""
    # Event topics
    topics = [
        "order.created", "order.paid", "order.fulfilled", "order.cancelled",
        "order.refunded", "inventory.low_stock", "inventory.updated",
        "product.created", "product.updated", "customer.registered",
        "dispute.opened", "all_events",
    ]
    for topic in topics:
        sub = _integrationapi_create_webhook(tenant_a, name=f"Hook {topic}", event_topic=topic)
        assert sub.event_topic == topic
        assert sub.get_event_topic_display() != ""

    # Status choices
    for st in ["active", "paused", "disabled", "circuit_broken"]:
        sub = _integrationapi_create_webhook(tenant_a, name=f"Hook {st}", status=st)
        assert sub.status == st

    # Payload format choices
    for fmt in ["json", "form_encoded"]:
        sub = _integrationapi_create_webhook(tenant_a, name=f"Hook {fmt}", payload_format=fmt)
        assert sub.payload_format == fmt


def test_integrationapi_webhook_subscription_secret_key_and_headers(tenant_a):
    """Test WebhookSubscription HMAC secret storage and custom headers JSON."""
    secret = "whsec_super_confidential_signing_key_4883"
    headers_json = '{"X-Custom-Client": "NavERP-Integration", "X-Trace-ID": "trace-8899"}'
    sub = _integrationapi_create_webhook(
        tenant_a,
        name="Secure Partner Hook",
        secret_key=secret,
        custom_headers=headers_json,
    )
    assert sub.secret_key == secret
    assert sub.custom_headers == headers_json


def test_integrationapi_webhook_subscription_tenant_isolation(tenant_a, tenant_b, ecom_webhook_a, ecom_webhook_b):
    """Test WebhookSubscription tenant isolation and unique (tenant, number) constraint."""
    # Queryset isolation
    a_ids = list(WebhookSubscription.objects.filter(tenant=tenant_a).values_list("id", flat=True))
    b_ids = list(WebhookSubscription.objects.filter(tenant=tenant_b).values_list("id", flat=True))
    assert ecom_webhook_a.id in a_ids
    assert ecom_webhook_a.id not in b_ids
    assert ecom_webhook_b.id in b_ids
    assert ecom_webhook_b.id not in a_ids

    # Duplicate number in same tenant violates UniqueConstraint
    with pytest.raises(IntegrityError):
        WebhookSubscription.objects.create(
            tenant=tenant_a,
            number=ecom_webhook_a.number,
            name="Conflicting Webhook",
            target_url="https://dup.target.com/hook",
        )


# ==============================================================================
# ApiCredential Unit Tests
# ==============================================================================

def test_integrationapi_api_credential_creation_and_numbering(tenant_a, admin_user, ecom_credential_a):
    """Test ApiCredential creation, EAPC- prefix numbering, defaults, and __str__."""
    assert ecom_credential_a.pk is not None
    assert ecom_credential_a.tenant == tenant_a
    assert ecom_credential_a.number.startswith("EAPC-")
    prefix = ecom_credential_a.client_id[:16]
    assert str(ecom_credential_a) == f"{ecom_credential_a.number} - {ecom_credential_a.name} ({prefix}...)"

    # Test explicit creation with defaults
    cred = _integrationapi_create_credential(
        tenant_a,
        name="Next.js Storefront Key",
        tier="storefront_public",
        created_by=admin_user,
    )
    assert cred.pk is not None
    assert cred.number.startswith("EAPC-")
    assert cred.status == "active"
    assert cred.allowed_origins == "*"
    assert cred.allowed_ips == ""
    assert cred.rate_limit_rpm == 90
    assert cred.total_requests_count == 0
    assert cred.created_by == admin_user


def test_integrationapi_api_credential_scopes_list_property(tenant_a):
    """Test ApiCredential.scopes_list property parses comma-delimited scopes."""
    cred = _integrationapi_create_credential(
        tenant_a,
        scopes="read_catalog, write_orders,  manage_inventory  ",
    )
    assert cred.scopes_list == ["read_catalog", "write_orders", "manage_inventory"]

    # Test empty or None scopes
    cred.scopes = ""
    cred.save()
    assert cred.scopes_list == []

    cred.scopes = "   "
    cred.save()
    assert cred.scopes_list == []


def test_integrationapi_api_credential_client_id_uniqueness(tenant_a, tenant_b):
    """Test that client_id is globally unique across all credentials and tenants."""
    shared_cid = f"nep_global_uniq_cid_{secrets.token_hex(6)}"
    _integrationapi_create_credential(tenant_a, client_id=shared_cid)

    # Reusing the exact client_id in tenant_b must raise IntegrityError
    with pytest.raises(IntegrityError):
        _integrationapi_create_credential(tenant_b, client_id=shared_cid)


def test_integrationapi_api_credential_tier_choices_and_foreign_key(tenant_a):
    """Test ApiCredential tier/status choices and created_by on_delete=SET_NULL."""
    user_model = get_user_model()
    aid = secrets.token_hex(4)
    temp_admin = user_model.objects.create_user(
        username=f"admin_creator_{aid}",
        email=f"admin_creator_{aid}@example.com",
        password="securepass123",
    )

    # Tier choices
    for tier in ["storefront_public", "admin_server", "partner_read", "webhook_receiver"]:
        cred = _integrationapi_create_credential(tenant_a, tier=tier, created_by=temp_admin)
        assert cred.tier == tier
        assert cred.get_tier_display() != ""

    # Status choices
    for st in ["active", "revoked", "expired", "rate_limited"]:
        cred = _integrationapi_create_credential(tenant_a, status=st)
        assert cred.status == st

    # Deleting temp_admin should SET_NULL on created_by
    target_cred = _integrationapi_create_credential(tenant_a, created_by=temp_admin)
    temp_admin.delete()
    target_cred.refresh_from_db()
    assert target_cred.created_by is None


def test_integrationapi_api_credential_tenant_isolation(tenant_a, tenant_b, ecom_credential_a, ecom_credential_b):
    """Test ApiCredential tenant isolation and unique (tenant, number) constraint."""
    # Queryset isolation
    a_ids = list(ApiCredential.objects.filter(tenant=tenant_a).values_list("id", flat=True))
    b_ids = list(ApiCredential.objects.filter(tenant=tenant_b).values_list("id", flat=True))
    assert ecom_credential_a.id in a_ids
    assert ecom_credential_a.id not in b_ids
    assert ecom_credential_b.id in b_ids
    assert ecom_credential_b.id not in a_ids

    # Duplicate number in same tenant violates UniqueConstraint
    with pytest.raises(IntegrityError):
        ApiCredential.objects.create(
            tenant=tenant_a,
            number=ecom_credential_a.number,
            name="Conflicting Credential",
            client_id=f"nep_different_cid_{secrets.token_hex(6)}",
        )
