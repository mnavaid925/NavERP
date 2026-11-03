"""Unit tests for Sub-module 9.19 Integration & API Ecosystem forms.

Covers:
- EcommerceConnectorForm:
  - System field exclusion (security invariant: tenant, number, health_status,
    last_health_check_at, last_error_message, created_at, updated_at excluded).
  - Valid submission and instance creation.
  - clean_base_url SSRF validation: rejects loopback (127.0.0.1, localhost, ::1, 0.0.0.0),
    metadata (169.254.169.254, instance-data), private RFC1918 IPs (10.0.0.1, 172.16.0.1, 192.168.1.1),
    internal/local domains, invalid schemes, missing host.
  - clean_timeout_seconds bounds check (1 to 300).
  - clean_rate_limit_per_minute bounds check (>= 1).
  - clean_name required validation.
  - clean_api_secret: preserves existing secret on edit when left blank;
    PasswordInput widget uses render_value=False.
- IntegrationSyncJobForm:
  - System field exclusion (tenant, number, status, records_*, started_at, finished_at,
    duration_seconds, retry_count, parent_job, triggered_by, created_at, updated_at).
  - Scoped connector dropdown: only shows connectors for tenant_a, excludes tenant_b.
  - Cross-tenant connector validation (reject_foreign).
  - clean_max_retries bounds check (0 to 20).
  - Valid submission and save.
- WebhookSubscriptionForm:
  - System field exclusion (tenant, number, consecutive_failures, last_delivery_at,
    last_status_code, last_error_message, total_delivered_count, total_failed_count,
    created_at, updated_at).
  - clean_target_url SSRF validation: rejects loopback, metadata, and private IPs.
  - clean_secret_key: auto-generates whsec_... on create when blank; preserves existing secret on edit;
    PasswordInput widget uses render_value=False.
  - clean_custom_headers: accepts valid JSON dictionary, rejects malformed JSON, rejects non-dict JSON,
    rejects non-primitive values, rejects CRLF injection, blocks hop-by-hop headers.
- ApiCredentialForm:
  - System field exclusion (tenant, number, client_id, client_secret_hash, secret_prefix,
    total_requests_count, last_used_at, revoked_at, created_by, created_at, updated_at).
  - clean_name required check.
  - clean_status: blocks un-revoking a credential if existing instance is 'revoked';
    allows normal lifecycle transitions when not revoked.
  - tier immutability: disabled on edit and returns instance.tier even if tampered.
  - clean_rate_limit_rpm bounds check (> 0).
"""
import json
import pytest
from django import forms

from apps.ecommerce.forms.IntegrationApi import (
    EcommerceConnectorForm,
    IntegrationSyncJobForm,
    WebhookSubscriptionForm,
    ApiCredentialForm,
)
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

def _integrationapi_valid_connector_data(**kwargs):
    """Return valid form data dictionary for EcommerceConnectorForm."""
    data = {
        "name": "Stripe Payments Live",
        "category": "payment",
        "provider": "stripe",
        "auth_type": "api_key",
        "status": "active",
        "base_url": "https://api.stripe.com/v1",
        "api_version": "v1",
        "api_key": "sk_live_sample_key_12345",
        "api_secret": "sec_live_sample_secret_67890",
        "account_id": "acct_1234567890",
        "is_sandbox": False,
        "timeout_seconds": 45,
        "rate_limit_per_minute": 100,
        "description": "Primary payment gateway connector for checkout transactions.",
    }
    data.update(kwargs)
    return data


def _integrationapi_valid_sync_job_data(connector, **kwargs):
    """Return valid form data dictionary for IntegrationSyncJobForm."""
    connector_pk = connector.pk if hasattr(connector, "pk") else connector
    data = {
        "connector": connector_pk,
        "sync_entity": "order_to_cash",
        "direction": "outbound",
        "trigger_type": "manual",
        "batch_id": "batch-2026-11-03-001",
        "max_retries": 5,
        "payload_preview": '{"scope": "recent_orders"}',
        "error_summary": "",
    }
    data.update(kwargs)
    return data


def _integrationapi_valid_webhook_data(**kwargs):
    """Return valid form data dictionary for WebhookSubscriptionForm."""
    data = {
        "name": "ERP Order Sync Webhook",
        "target_url": "https://api.partner-erp.com/webhooks/orders",
        "event_topic": "order.created",
        "status": "active",
        "secret_key": "whsec_custom_secret_key_12345",
        "payload_format": "json",
        "custom_headers": json.dumps({"X-Source": "NavERP-Ecom", "X-Version": "1.0"}),
        "max_consecutive_failures": 5,
        "is_verify_ssl": True,
        "description": "Dispatches real-time order creation payloads to ERP.",
    }
    data.update(kwargs)
    return data


def _integrationapi_valid_credential_data(**kwargs):
    """Return valid form data dictionary for ApiCredentialForm."""
    data = {
        "name": "Mobile Storefront iOS App",
        "tier": "storefront_public",
        "status": "active",
        "scopes": "read_catalog,write_orders",
        "allowed_origins": "https://mobile.myshop.com",
        "allowed_ips": "198.51.100.0/24",
        "rate_limit_rpm": 120,
        "description": "API credential client for native iOS customer shopping application.",
    }
    data.update(kwargs)
    return data


# ==============================================================================
# 1. EcommerceConnectorForm Tests
# ==============================================================================

def test_integrationapi_connector_form_field_exclusion(tenant_a):
    """Assert security invariant: tenant, number, health_status, last_health_check_at,
    last_error_message, last_synced_at, created_at, updated_at are NOT exposed in form."""
    form = EcommerceConnectorForm(tenant=tenant_a)

    excluded_fields = {
        "tenant",
        "number",
        "health_status",
        "last_health_check_at",
        "last_error_message",
        "last_synced_at",
        "created_at",
        "updated_at",
    }
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from EcommerceConnectorForm"

    expected_present = {
        "name",
        "category",
        "provider",
        "auth_type",
        "status",
        "base_url",
        "api_version",
        "api_key",
        "api_secret",
        "account_id",
        "is_sandbox",
        "timeout_seconds",
        "rate_limit_per_minute",
        "description",
    }
    for field_name in expected_present:
        assert field_name in form.fields, f"Expected field '{field_name}' missing from EcommerceConnectorForm"

    # PasswordInput widget check
    secret_field = form.fields["api_secret"]
    assert isinstance(secret_field.widget, forms.PasswordInput)
    assert secret_field.widget.render_value is False


def test_integrationapi_connector_form_valid(tenant_a):
    """Test valid submission and saving of EcommerceConnectorForm."""
    data = _integrationapi_valid_connector_data()
    form = EcommerceConnectorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    connector = form.save(commit=False)
    connector.tenant = tenant_a
    connector.save()

    assert connector.pk is not None
    assert connector.name == data["name"]
    assert connector.category == data["category"]
    assert connector.provider == data["provider"]
    assert connector.auth_type == data["auth_type"]
    assert connector.status == data["status"]
    assert connector.base_url == data["base_url"]
    assert connector.api_key == data["api_key"]
    assert connector.api_secret == data["api_secret"]
    assert connector.timeout_seconds == data["timeout_seconds"]
    assert connector.rate_limit_per_minute == data["rate_limit_per_minute"]


def test_integrationapi_connector_form_empty_name_rejected(tenant_a):
    """Test that missing or whitespace-only connector name is rejected."""
    for bad_name in ["", "   ", "\t\n"]:
        data = _integrationapi_valid_connector_data(name=bad_name)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors


def test_integrationapi_connector_form_clean_base_url_valid(tenant_a):
    """Test valid public endpoints pass clean_base_url validation."""
    valid_urls = [
        "https://api.stripe.com/v1",
        "https://api.netsuite.com/rest/record/v1",
        "http://api.partner.example.com:8443/custom",
        "",  # blank URL is allowed as base_url is optional
    ]
    for url in valid_urls:
        data = _integrationapi_valid_connector_data(base_url=url)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid URL '{url}' unexpectedly rejected: {form.errors}"


def test_integrationapi_connector_form_clean_base_url_ssrf_protection(tenant_a):
    """Test clean_base_url rejects loopback, cloud metadata, RFC1918 private IPs,
    internal domain names, invalid schemes, and missing hosts."""
    ssrf_urls = [
        # Loopback
        "http://localhost/api",
        "https://127.0.0.1:8080/v1",
        "http://[::1]/v1",
        "http://0.0.0.0/api",
        # Cloud metadata / link-local
        "http://169.254.169.254/latest/meta-data",
        "http://instance-data/latest/meta-data",
        # RFC1918 Private IPs
        "http://10.0.0.1/api",
        "http://172.16.0.10/v1",
        "https://192.168.1.1/api",
        # Internal / local domains
        "https://internal-service.local/api",
        "https://backend.internal/v1",
        # Invalid schemes
        "ftp://api.example.com",
        "file:///etc/passwd",
        # Missing host
        "https://",
    ]
    for url in ssrf_urls:
        data = _integrationapi_valid_connector_data(base_url=url)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"SSRF URL '{url}' should have been rejected."
        assert "base_url" in form.errors, f"Expected 'base_url' error for '{url}', got: {form.errors}"


def test_integrationapi_connector_form_clean_timeout_bounds(tenant_a):
    """Test timeout_seconds validation enforces bounds between 1 and 300 seconds."""
    # Under minimum
    for bad_val in [0, -1, -50]:
        data = _integrationapi_valid_connector_data(timeout_seconds=bad_val)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "timeout_seconds" in form.errors

    # Over maximum (300)
    for bad_val in [301, 500, 1000]:
        data = _integrationapi_valid_connector_data(timeout_seconds=bad_val)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "timeout_seconds" in form.errors

    # Valid boundary values
    for good_val in [1, 30, 150, 300]:
        data = _integrationapi_valid_connector_data(timeout_seconds=good_val)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid timeout '{good_val}' rejected: {form.errors}"


def test_integrationapi_connector_form_clean_rate_limit_bounds(tenant_a):
    """Test rate_limit_per_minute enforces minimum of 1 request/minute."""
    for bad_val in [0, -1, -100]:
        data = _integrationapi_valid_connector_data(rate_limit_per_minute=bad_val)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "rate_limit_per_minute" in form.errors

    for good_val in [1, 60, 500]:
        data = _integrationapi_valid_connector_data(rate_limit_per_minute=good_val)
        form = EcommerceConnectorForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid rate limit '{good_val}' rejected: {form.errors}"


def test_integrationapi_connector_form_edit_preserves_api_secret_when_blank(tenant_a, ecom_connector_a):
    """Test that editing a connector leaving api_secret blank preserves existing secret."""
    ecom_connector_a.api_secret = "initial_unmasked_secret_key"
    ecom_connector_a.save()

    data = _integrationapi_valid_connector_data(
        name="Renamed Stripe Connector",
        api_secret="",  # Submitted blank on edit
    )
    form = EcommerceConnectorForm(data=data, instance=ecom_connector_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["api_secret"] == "initial_unmasked_secret_key"

    saved_obj = form.save()
    saved_obj.refresh_from_db()
    assert saved_obj.name == "Renamed Stripe Connector"
    assert saved_obj.api_secret == "initial_unmasked_secret_key"


def test_integrationapi_connector_form_edit_updates_api_secret_when_provided(tenant_a, ecom_connector_a):
    """Test that editing a connector with a new api_secret updates it properly."""
    ecom_connector_a.api_secret = "initial_secret"
    ecom_connector_a.save()

    data = _integrationapi_valid_connector_data(
        api_secret="brand_new_rotated_secret_999",
    )
    form = EcommerceConnectorForm(data=data, instance=ecom_connector_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["api_secret"] == "brand_new_rotated_secret_999"

    saved_obj = form.save()
    saved_obj.refresh_from_db()
    assert saved_obj.api_secret == "brand_new_rotated_secret_999"


# ==============================================================================
# 2. IntegrationSyncJobForm Tests
# ==============================================================================

def test_integrationapi_sync_job_form_field_exclusion(tenant_a):
    """Assert system execution fields are excluded from IntegrationSyncJobForm."""
    form = IntegrationSyncJobForm(tenant=tenant_a)

    excluded_fields = {
        "tenant",
        "number",
        "status",
        "records_total",
        "records_processed",
        "records_succeeded",
        "records_failed",
        "started_at",
        "finished_at",
        "duration_seconds",
        "retry_count",
        "parent_job",
        "triggered_by",
        "created_at",
        "updated_at",
    }
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from IntegrationSyncJobForm"

    expected_present = {
        "connector",
        "sync_entity",
        "direction",
        "trigger_type",
        "batch_id",
        "max_retries",
        "payload_preview",
        "error_summary",
    }
    for field_name in expected_present:
        assert field_name in form.fields, f"Expected field '{field_name}' missing from IntegrationSyncJobForm"


def test_integrationapi_sync_job_form_valid(tenant_a, ecom_connector_a):
    """Test valid submission and saving of IntegrationSyncJobForm."""
    data = _integrationapi_valid_sync_job_data(ecom_connector_a)
    form = IntegrationSyncJobForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    job = form.save(commit=False)
    job.tenant = tenant_a
    job.save()

    assert job.pk is not None
    assert job.connector == ecom_connector_a
    assert job.sync_entity == data["sync_entity"]
    assert job.direction == data["direction"]
    assert job.trigger_type == data["trigger_type"]
    assert job.batch_id == data["batch_id"]
    assert job.max_retries == data["max_retries"]


def test_integrationapi_sync_job_form_connector_scoping(tenant_a, tenant_b, ecom_connector_a, ecom_connector_b):
    """Test connector choice queryset is strictly scoped to tenant."""
    form_a = IntegrationSyncJobForm(tenant=tenant_a)
    qs_a = form_a.fields["connector"].queryset

    assert qs_a.filter(pk=ecom_connector_a.pk).exists()
    assert not qs_a.filter(pk=ecom_connector_b.pk).exists()

    form_b = IntegrationSyncJobForm(tenant=tenant_b)
    qs_b = form_b.fields["connector"].queryset

    assert qs_b.filter(pk=ecom_connector_b.pk).exists()
    assert not qs_b.filter(pk=ecom_connector_a.pk).exists()


def test_integrationapi_sync_job_form_cross_tenant_connector_rejection(tenant_a, tenant_b, ecom_connector_b):
    """Test submitting tenant_b's connector with tenant=tenant_a triggers validation error."""
    data = _integrationapi_valid_sync_job_data(ecom_connector_b)
    form = IntegrationSyncJobForm(data=data, tenant=tenant_a)

    assert not form.is_valid()
    assert "connector" in form.errors


def test_integrationapi_sync_job_form_clean_max_retries_bounds(tenant_a, ecom_connector_a):
    """Test max_retries validation enforces bounds between 0 and 20."""
    # Negative
    for bad_val in [-1, -5]:
        data = _integrationapi_valid_sync_job_data(ecom_connector_a, max_retries=bad_val)
        form = IntegrationSyncJobForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "max_retries" in form.errors

    # Exceeding 20
    for bad_val in [21, 50, 100]:
        data = _integrationapi_valid_sync_job_data(ecom_connector_a, max_retries=bad_val)
        form = IntegrationSyncJobForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "max_retries" in form.errors

    # Valid boundaries
    for good_val in [0, 1, 10, 20]:
        data = _integrationapi_valid_sync_job_data(ecom_connector_a, max_retries=good_val)
        form = IntegrationSyncJobForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid max_retries '{good_val}' rejected: {form.errors}"


# ==============================================================================
# 3. WebhookSubscriptionForm Tests
# ==============================================================================

def test_integrationapi_webhook_form_field_exclusion(tenant_a):
    """Assert execution metrics and delivery telemetry are excluded from WebhookSubscriptionForm."""
    form = WebhookSubscriptionForm(tenant=tenant_a)

    excluded_fields = {
        "tenant",
        "number",
        "consecutive_failures",
        "consecutive_failure_count",
        "last_delivery_at",
        "last_status_code",
        "last_error_message",
        "total_delivered_count",
        "total_failed_count",
        "created_at",
        "updated_at",
    }
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from WebhookSubscriptionForm"

    expected_present = {
        "name",
        "target_url",
        "event_topic",
        "status",
        "secret_key",
        "payload_format",
        "custom_headers",
        "max_consecutive_failures",
        "is_verify_ssl",
        "description",
    }
    for field_name in expected_present:
        assert field_name in form.fields, f"Expected field '{field_name}' missing from WebhookSubscriptionForm"

    # PasswordInput widget check
    secret_field = form.fields["secret_key"]
    assert isinstance(secret_field.widget, forms.PasswordInput)
    assert secret_field.widget.render_value is False


def test_integrationapi_webhook_form_valid(tenant_a):
    """Test valid submission and saving of WebhookSubscriptionForm."""
    data = _integrationapi_valid_webhook_data()
    form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    webhook = form.save(commit=False)
    webhook.tenant = tenant_a
    webhook.save()

    assert webhook.pk is not None
    assert webhook.name == data["name"]
    assert webhook.target_url == data["target_url"]
    assert webhook.event_topic == data["event_topic"]
    assert webhook.status == data["status"]
    assert webhook.secret_key == data["secret_key"]
    assert webhook.payload_format == data["payload_format"]
    assert webhook.is_verify_ssl is True


def test_integrationapi_webhook_form_clean_target_url_valid(tenant_a):
    """Test valid public webhook destinations pass clean_target_url validation."""
    valid_urls = [
        "https://api.external.com/webhooks/orders",
        "http://partner-gateway.com:8443/listener",
    ]
    for url in valid_urls:
        data = _integrationapi_valid_webhook_data(target_url=url)
        form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid target_url '{url}' rejected: {form.errors}"


def test_integrationapi_webhook_form_clean_target_url_ssrf_protection(tenant_a):
    """Test clean_target_url rejects loopback, metadata, RFC1918 private IPs,
    internal domain names, invalid schemes, and missing target."""
    ssrf_urls = [
        "",  # required
        "   ",
        # Loopback
        "http://localhost:9000/webhook",
        "https://127.0.0.1/webhook",
        "http://[::1]/webhook",
        "http://0.0.0.0/webhook",
        # Cloud metadata / link-local
        "http://169.254.169.254/latest/meta-data",
        "http://instance-data/webhook",
        # RFC1918 Private IPs
        "http://10.100.1.5/webhook",
        "http://172.20.0.1/webhook",
        "https://192.168.0.50/webhook",
        # Internal / local domains
        "https://webhook.internal/orders",
        "https://receiver.local/events",
        # Invalid schemes
        "ftp://example.com/webhook",
        "file:///etc/hosts",
        # Missing host
        "https://",
    ]
    for url in ssrf_urls:
        data = _integrationapi_valid_webhook_data(target_url=url)
        form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"SSRF URL '{url}' should have been rejected."
        assert "target_url" in form.errors, f"Expected 'target_url' error for '{url}', got: {form.errors}"


def test_integrationapi_webhook_form_secret_key_auto_generation_on_create(tenant_a):
    """Test that submitting a blank secret_key on create auto-generates a secure whsec_... key."""
    data = _integrationapi_valid_webhook_data(secret_key="")
    form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    secret = form.cleaned_data["secret_key"]
    assert secret.startswith("whsec_")
    assert len(secret) > 30


def test_integrationapi_webhook_form_secret_key_preservation_on_edit(tenant_a, ecom_webhook_a):
    """Test that editing a webhook subscription with a blank secret_key preserves the existing secret."""
    ecom_webhook_a.secret_key = "whsec_existing_precious_secret_12345"
    ecom_webhook_a.save()

    data = _integrationapi_valid_webhook_data(
        name="Renamed Webhook Subscription",
        secret_key="",  # Submitted blank on edit
    )
    form = WebhookSubscriptionForm(data=data, instance=ecom_webhook_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["secret_key"] == "whsec_existing_precious_secret_12345"

    saved_obj = form.save()
    saved_obj.refresh_from_db()
    assert saved_obj.name == "Renamed Webhook Subscription"
    assert saved_obj.secret_key == "whsec_existing_precious_secret_12345"


def test_integrationapi_webhook_form_secret_key_explicit_override(tenant_a):
    """Test providing an explicit secret_key uses the provided value."""
    data = _integrationapi_valid_webhook_data(secret_key="whsec_custom_provided_key_777")
    form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["secret_key"] == "whsec_custom_provided_key_777"


def test_integrationapi_webhook_form_clean_custom_headers_valid_json(tenant_a):
    """Test clean_custom_headers accepts valid JSON dictionary of string/primitive values."""
    valid_headers = [
        json.dumps({"X-Service-Name": "NavERP-Core", "X-Retry-Limit": 3, "X-Score": 99.5}),
        "",   # Blank defaults to "{}"
        "   ",
    ]
    for val in valid_headers:
        data = _integrationapi_valid_webhook_data(custom_headers=val)
        form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid headers '{val}' rejected: {form.errors}"
        if not val.strip():
            assert form.cleaned_data["custom_headers"] == "{}"


def test_integrationapi_webhook_form_clean_custom_headers_invalid_json(tenant_a):
    """Test clean_custom_headers rejects malformed JSON and non-dict structures."""
    invalid_headers = [
        "not json at all",
        "{malformed: json,",
        "[1, 2, 3]",                  # JSON list
        '"a string literal"',          # JSON string
        "12345",                       # JSON number
        json.dumps({"X-Bad": ["nested", "list"]}),       # Non-primitive value
        json.dumps({"X-Bad": {"nested": "dict"}}),       # Non-primitive value
    ]
    for val in invalid_headers:
        data = _integrationapi_valid_webhook_data(custom_headers=val)
        form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Invalid headers '{val}' should have been rejected."
        assert "custom_headers" in form.errors


def test_integrationapi_webhook_form_clean_custom_headers_crlf_injection(tenant_a):
    """Test clean_custom_headers rejects CRLF carriage returns and newlines in keys and values."""
    crlf_headers = [
        json.dumps({"X-Injected\r\nHeader": "valid_val"}),
        json.dumps({"X-Injected\nHeader": "valid_val"}),
        json.dumps({"X-Valid-Header": "value\r\nInjected-Header: evil"}),
        json.dumps({"X-Valid-Header": "value\nInjected-Header: evil"}),
    ]
    for val in crlf_headers:
        data = _integrationapi_valid_webhook_data(custom_headers=val)
        form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"CRLF headers '{val}' should have been rejected."
        assert "custom_headers" in form.errors
        assert "CRLF carriage returns and newlines are not permitted" in form.errors["custom_headers"][0]


def test_integrationapi_webhook_form_clean_custom_headers_hop_by_hop_blocked(tenant_a):
    """Test clean_custom_headers blocks hop-by-hop headers from being overridden."""
    hop_by_hop_names = [
        "connection",
        "Connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "Host",
        "content-length",
    ]
    for header_name in hop_by_hop_names:
        data = _integrationapi_valid_webhook_data(custom_headers=json.dumps({header_name: "test_val"}))
        form = WebhookSubscriptionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Hop-by-hop header '{header_name}' should have been rejected."
        assert "custom_headers" in form.errors
        assert "Hop-by-hop header" in form.errors["custom_headers"][0]


# ==============================================================================
# 4. ApiCredentialForm Tests
# ==============================================================================

def test_integrationapi_credential_form_field_exclusion(tenant_a):
    """Assert security-sensitive credentials and telemetry fields are excluded from ApiCredentialForm."""
    form = ApiCredentialForm(tenant=tenant_a)

    excluded_fields = {
        "tenant",
        "number",
        "client_id",
        "client_secret_hash",
        "secret_prefix",
        "total_requests_count",
        "created_by",
        "last_used_at",
        "revoked_at",
        "created_at",
        "updated_at",
    }
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"Field '{field_name}' must be excluded from ApiCredentialForm"

    expected_present = {
        "name",
        "tier",
        "status",
        "scopes",
        "allowed_origins",
        "allowed_ips",
        "rate_limit_rpm",
        "expires_at",
        "description",
    }
    for field_name in expected_present:
        assert field_name in form.fields, f"Expected field '{field_name}' missing from ApiCredentialForm"


def test_integrationapi_credential_form_valid(tenant_a):
    """Test valid submission of ApiCredentialForm."""
    data = _integrationapi_valid_credential_data()
    form = ApiCredentialForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # Verify save commit=False allows population of system fields
    credential = form.save(commit=False)
    credential.tenant = tenant_a
    credential.client_id = f"nep_test_pub_{tenant_a.pk}_99"
    credential.client_secret_hash = "mocked_sha256_hash_here"
    credential.save()

    assert credential.pk is not None
    assert credential.name == data["name"]
    assert credential.tier == data["tier"]
    assert credential.status == data["status"]
    assert credential.scopes == data["scopes"]
    assert credential.rate_limit_rpm == data["rate_limit_rpm"]


def test_integrationapi_credential_form_clean_name_required(tenant_a):
    """Test that missing or whitespace client name raises validation error."""
    for bad_name in ["", "   ", "\t"]:
        data = _integrationapi_valid_credential_data(name=bad_name)
        form = ApiCredentialForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors


def test_integrationapi_credential_form_tier_disabled_and_immutable_on_edit(tenant_a, ecom_credential_a):
    """Test that tier field is disabled on edit and returns instance.tier even if submitted."""
    assert ecom_credential_a.tier == "storefront_public"

    # Check unbound form has disabled tier
    edit_form = ApiCredentialForm(instance=ecom_credential_a, tenant=tenant_a)
    assert edit_form.fields["tier"].disabled is True

    # Check bound form with tampered tier returns original instance.tier
    data = _integrationapi_valid_credential_data(
        tier="admin_server",  # Attempting to escalate tier on edit
    )
    bound_form = ApiCredentialForm(data=data, instance=ecom_credential_a, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    assert bound_form.cleaned_data["tier"] == "storefront_public"

    saved_obj = bound_form.save()
    saved_obj.refresh_from_db()
    assert saved_obj.tier == "storefront_public"


def test_integrationapi_credential_form_clean_status_blocks_unrevoking(tenant_a, ecom_credential_a):
    """Test clean_status blocks reactivating a revoked API credential."""
    ecom_credential_a.status = "revoked"
    ecom_credential_a.save()

    # Attempting to reactivate to 'active'
    data = _integrationapi_valid_credential_data(status="active")
    form = ApiCredentialForm(data=data, instance=ecom_credential_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Revoked API credentials cannot be reactivated." in form.errors["status"][0]

    # Attempting to change to 'expired'
    data_expired = _integrationapi_valid_credential_data(status="expired")
    form_expired = ApiCredentialForm(data=data_expired, instance=ecom_credential_a, tenant=tenant_a)
    assert not form_expired.is_valid()
    assert "status" in form_expired.errors

    # Staying 'revoked' is allowed
    data_revoked = _integrationapi_valid_credential_data(status="revoked")
    form_revoked = ApiCredentialForm(data=data_revoked, instance=ecom_credential_a, tenant=tenant_a)
    assert form_revoked.is_valid(), form_revoked.errors


def test_integrationapi_credential_form_clean_status_allows_transition_when_not_revoked(tenant_a, ecom_credential_a):
    """Test clean_status allows lifecycle transitions when existing status is active."""
    for target_status in ["revoked", "rate_limited", "expired", "active"]:
        ecom_credential_a.status = "active"
        data = _integrationapi_valid_credential_data(status=target_status)
        form = ApiCredentialForm(data=data, instance=ecom_credential_a, tenant=tenant_a)
        assert form.is_valid(), f"Transition from active to '{target_status}' should be permitted: {form.errors}"


def test_integrationapi_credential_form_clean_rate_limit_bounds(tenant_a):
    """Test rate_limit_rpm enforces minimum of 1 request/minute."""
    for bad_rpm in [0, -1, -50]:
        data = _integrationapi_valid_credential_data(rate_limit_rpm=bad_rpm)
        form = ApiCredentialForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "rate_limit_rpm" in form.errors
        assert "Rate limit must be at least 1 request/minute." in form.errors["rate_limit_rpm"][0]

    for good_rpm in [1, 60, 1000]:
        data = _integrationapi_valid_credential_data(rate_limit_rpm=good_rpm)
        form = ApiCredentialForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Valid rate limit '{good_rpm}' rejected: {form.errors}"
