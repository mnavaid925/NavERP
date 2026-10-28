"""Unit tests for Sales 8.18 Integration & API Hub forms.

Subslug: integrationapihub
Prefix for test functions: test_integrationapihub_*
Prefix for helper functions: _integrationapihub_*

Covers:
1. SalesIntegrationConnectorForm:
   - Excluded fields: tenant, number, credential_encrypted, last_health_check_at, last_error_message.
   - Plaintext credential_input (PasswordInput, render_value=False) encryption on create.
   - Existing credential preservation on edit when credential_input is left empty.
   - Automatic clearance of credential_encrypted when auth_method == "none".
   - Required fields and validation rules.
2. SalesFieldMappingForm:
   - Excluded fields: tenant (and number is unnumbered).
   - TenantUniqueMixin uniqueness validation: submitting duplicate
     (connector, target_entity, local_field, remote_field) under the same tenant produces
     a clean form error instead of 500 IntegrityError.
   - Allows same composite mapping under a different tenant.
   - Cross-tenant connector rejection via _reject_foreign.
   - clean_value_map: defaults empty/None to {} and raises ValidationError for non-dict JSON
     (e.g. list, integer, string, boolean) and invalid JSON syntax.
   - Checkbox widget class is form-check.
3. SalesSyncJobForm:
   - Excluded fields: tenant, number, last_run_at, next_run_at, total_runs_count, total_records_synced.
   - Batch size validation (rejects <= 0, accepts >= 1).
   - Cross-tenant connector rejection via _reject_foreign.
4. SalesSyncRunForm:
   - Excluded fields: tenant, number, started_at, finished_at.
   - Cross-tenant rejection for connector and job.
"""
import pytest
from django import forms

from apps.sales.forms import (
    SalesFieldMappingForm,
    SalesIntegrationConnectorForm,
    SalesSyncJobForm,
    SalesSyncRunForm,
)
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

def _integrationapihub_widen(form, field_name, queryset):
    """Widens a form field queryset to allow cross-tenant test values past field validation."""
    form.fields[field_name].queryset = queryset


def _integrationapihub_connector_payload(**overrides):
    defaults = {
        "name": "Production ERP Connector",
        "category": "erp",
        "provider": "sap",
        "environment": "production",
        "base_url": "https://erp.example.com/api",
        "auth_method": "api_key",
        "credential_input": "sec_prod_live_key_9981",
        "remote_scope_ref": "client_100",
        "health_status": "connected",
        "is_active": True,
        "notes": "Main ERP connector.",
    }
    defaults.update(overrides)
    return defaults


def _integrationapihub_mapping_payload(connector, **overrides):
    defaults = {
        "connector": connector.pk if hasattr(connector, "pk") else connector,
        "target_entity": "order",
        "local_field": "total_amount",
        "remote_field": "NETWR",
        "direction": "bidirectional",
        "transform_rule": "currency_round",
        "value_map": "{}",
        "default_value": "0.00",
        "is_key": False,
        "is_required": True,
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def _integrationapihub_job_payload(connector, **overrides):
    defaults = {
        "name": "Daily Order Ingestion",
        "connector": connector.pk if hasattr(connector, "pk") else connector,
        "entity_scope": "order_to_cash",
        "sync_direction": "outbound",
        "conflict_policy": "last_updated_wins",
        "cadence": "daily",
        "filter_expression": "status='confirmed'",
        "batch_size": 100,
        "status": "active",
    }
    defaults.update(overrides)
    return defaults


def _integrationapihub_run_payload(connector, job=None, **overrides):
    defaults = {
        "connector": connector.pk if hasattr(connector, "pk") else connector,
        "job": (job.pk if hasattr(job, "pk") else job) if job else "",
        "run_type": "manual",
        "status": "simulated",
        "records_read": 100,
        "records_written": 98,
        "records_failed": 2,
        "records_skipped": 0,
        "error_log": "",
    }
    defaults.update(overrides)
    return defaults


# ==============================================================================
# 1. SalesIntegrationConnectorForm Tests
# ==============================================================================

def test_integrationapihub_connector_form_excluded_fields():
    """Verify sensitive, auto-generated, and diagnostic fields are excluded."""
    form = SalesIntegrationConnectorForm()
    excluded = {
        "tenant",
        "number",
        "credential_encrypted",
        "last_health_check_at",
        "last_error_message",
    }
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must be excluded from SalesIntegrationConnectorForm"

    expected_fields = {
        "name",
        "category",
        "provider",
        "environment",
        "base_url",
        "auth_method",
        "remote_scope_ref",
        "health_status",
        "is_active",
        "notes",
        "credential_input",
    }
    assert set(form.fields.keys()) == expected_fields


def test_integrationapihub_connector_form_credential_input_widget_attributes():
    """credential_input uses PasswordInput, render_value=False, and is optional."""
    form = SalesIntegrationConnectorForm()
    field = form.fields["credential_input"]

    assert isinstance(field, forms.CharField)
    assert not field.required
    assert isinstance(field.widget, forms.PasswordInput)
    assert field.widget.render_value is False
    assert field.widget.attrs.get("class") == "form-input"
    assert "placeholder" in field.widget.attrs


def test_integrationapihub_connector_form_create_encrypts_plaintext_credential(tenant_a):
    """Plaintext credential_input is encrypted with Fernet upon save."""
    secret = "live_sap_production_secret_token_12345!"
    payload = _integrationapihub_connector_payload(
        name="Encrypted SAP Connector",
        auth_method="api_key",
        credential_input=secret,
    )
    form = SalesIntegrationConnectorForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    connector = form.save(commit=False)
    connector.tenant = tenant_a
    connector.save()

    assert connector.pk is not None
    assert connector.has_credential() is True
    assert connector.get_credential() == secret
    assert connector.credential_encrypted.startswith("fernet.v1:")
    assert connector.credential_encrypted != secret
    assert connector.credential_masked == "••••••••"


def test_integrationapihub_connector_form_edit_preserves_existing_credential_when_blank(tenant_a):
    """Leaving credential_input blank on edit preserves the previously stored secret."""
    connector = _integrationapihub_connector(tenant_a, name="Existing Connector")
    connector.set_credential("preserved_master_token_777")
    connector.save()

    payload = _integrationapihub_connector_payload(
        name="Renamed Existing Connector",
        auth_method="api_key",
        credential_input="",  # Left blank to preserve
    )
    form = SalesIntegrationConnectorForm(data=payload, instance=connector, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.name == "Renamed Existing Connector"
    assert updated.has_credential() is True
    assert updated.get_credential() == "preserved_master_token_777"


def test_integrationapihub_connector_form_edit_updates_credential_when_provided(tenant_a):
    """Entering a new value in credential_input replaces the stored secret."""
    connector = _integrationapihub_connector(tenant_a, name="Rotated Connector")
    connector.set_credential("old_stale_token_111")
    connector.save()

    payload = _integrationapihub_connector_payload(
        name="Rotated Connector",
        auth_method="api_key",
        credential_input="freshly_rotated_token_999",
    )
    form = SalesIntegrationConnectorForm(data=payload, instance=connector, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.get_credential() == "freshly_rotated_token_999"


def test_integrationapihub_connector_form_clears_credential_when_auth_method_none(tenant_a):
    """Setting auth_method to 'none' clears credential_encrypted automatically."""
    connector = _integrationapihub_connector(tenant_a, name="Public Connector")
    connector.set_credential("temporary_token_to_clear")
    connector.save()
    assert connector.has_credential() is True

    payload = _integrationapihub_connector_payload(
        name="Public Connector",
        auth_method="none",
        credential_input="should_be_ignored_and_cleared",
    )
    form = SalesIntegrationConnectorForm(data=payload, instance=connector, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.auth_method == "none"
    assert updated.credential_encrypted == ""
    assert updated.get_credential() == ""
    assert updated.has_credential() is False


def test_integrationapihub_connector_form_required_fields_and_validation(tenant_a):
    """Verify name is required, base_url validates URL structure, and invalid choices fail."""
    # Missing name
    payload_no_name = _integrationapihub_connector_payload(name="")
    form_no_name = SalesIntegrationConnectorForm(data=payload_no_name, tenant=tenant_a)
    assert not form_no_name.is_valid()
    assert "name" in form_no_name.errors

    # Invalid URL format
    payload_bad_url = _integrationapihub_connector_payload(base_url="not-a-valid-url-format")
    form_bad_url = SalesIntegrationConnectorForm(data=payload_bad_url, tenant=tenant_a)
    assert not form_bad_url.is_valid()
    assert "base_url" in form_bad_url.errors

    # Invalid choice
    payload_bad_provider = _integrationapihub_connector_payload(provider="nonexistent_provider")
    form_bad_provider = SalesIntegrationConnectorForm(data=payload_bad_provider, tenant=tenant_a)
    assert not form_bad_provider.is_valid()
    assert "provider" in form_bad_provider.errors


# ==============================================================================
# 2. SalesFieldMappingForm Tests
# ==============================================================================

def test_integrationapihub_field_mapping_form_excluded_fields():
    """Verify tenant is excluded and field mapping has no number field."""
    form = SalesFieldMappingForm()
    assert "tenant" not in form.fields
    assert "number" not in form.fields

    expected_fields = {
        "connector",
        "target_entity",
        "local_field",
        "remote_field",
        "direction",
        "transform_rule",
        "value_map",
        "default_value",
        "is_key",
        "is_required",
        "is_active",
    }
    assert set(form.fields.keys()) == expected_fields


def test_integrationapihub_field_mapping_form_checkbox_widget_class():
    """Boolean fields use CheckboxInput widget with 'form-check' class."""
    form = SalesFieldMappingForm()
    checkbox_fields = ["is_key", "is_required", "is_active"]
    for field_name in checkbox_fields:
        field = form.fields[field_name]
        assert isinstance(field.widget, forms.CheckboxInput)
        assert field.widget.attrs.get("class") == "form-check"


def test_integrationapihub_field_mapping_form_tenant_scoped_queryset(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
):
    """connector dropdown queryset is strictly filtered to current tenant."""
    form = SalesFieldMappingForm(tenant=tenant_a)
    qs = form.fields["connector"].queryset
    assert iah_connector_a in qs
    assert iah_connector_b not in qs


def test_integrationapihub_field_mapping_form_tenant_unique_mixin_duplicate_validation(
    tenant_a,
    iah_connector_a,
):
    """Submitting duplicate (connector, target_entity, local_field, remote_field) triggers a clean form error."""
    _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="order",
        local_field="total_amount",
        remote_field="NETWR",
    )

    duplicate_payload = _integrationapihub_mapping_payload(
        iah_connector_a,
        target_entity="order",
        local_field="total_amount",
        remote_field="NETWR",
    )
    form = SalesFieldMappingForm(data=duplicate_payload, tenant=tenant_a)
    assert not form.is_valid()
    assert form.non_field_errors()
    error_message = str(form.non_field_errors())
    assert "already exists" in error_message.lower()


def test_integrationapihub_field_mapping_form_allows_same_composite_mapping_different_tenant(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
):
    """Same composite mapping under a different tenant succeeds cleanly."""
    _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="quote",
        local_field="grand_total",
        remote_field="TOTAL_PRICE",
    )

    payload_b = _integrationapihub_mapping_payload(
        iah_connector_b,
        target_entity="quote",
        local_field="grand_total",
        remote_field="TOTAL_PRICE",
    )
    form_b = SalesFieldMappingForm(data=payload_b, tenant=tenant_b)
    assert form_b.is_valid(), form_b.errors

    saved_b = form_b.save()
    assert saved_b.pk is not None
    assert saved_b.tenant == tenant_b
    assert saved_b.connector == iah_connector_b


def test_integrationapihub_field_mapping_form_allows_updating_existing_instance(
    tenant_a,
    iah_connector_a,
):
    """Editing an existing mapping does not collide with its own uniqueness constraint."""
    mapping = _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="lead",
        local_field="email",
        remote_field="EMAIL_ADDR",
        default_value="fallback@example.com",
    )

    update_payload = _integrationapihub_mapping_payload(
        iah_connector_a,
        target_entity="lead",
        local_field="email",
        remote_field="EMAIL_ADDR",
        default_value="updated_fallback@example.com",
    )
    form = SalesFieldMappingForm(data=update_payload, instance=mapping, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.default_value == "updated_fallback@example.com"


def test_integrationapihub_field_mapping_form_cross_tenant_connector_rejection(
    tenant_a,
    iah_connector_b,
):
    """_reject_foreign rejects connector belonging to another workspace."""
    payload = _integrationapihub_mapping_payload(
        iah_connector_b,
        target_entity="opportunity",
        local_field="amount",
        remote_field="EXP_REVENUE",
    )
    # Unwidened: rejected at choice validation
    form = SalesFieldMappingForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "connector" in form.errors

    # Widened: passes field clean, reaches clean() and triggers _reject_foreign
    form_widened = SalesFieldMappingForm(data=payload, tenant=tenant_a)
    _integrationapihub_widen(form_widened, "connector", SalesIntegrationConnector.objects.all())
    assert not form_widened.is_valid()
    assert "connector" in form_widened.errors
    assert "another workspace" in form_widened.errors["connector"][0].lower()


def test_integrationapihub_field_mapping_form_clean_value_map_empty_defaults_to_dict(
    tenant_a,
    iah_connector_a,
):
    """Empty or None value_map defaults to empty dict {}."""
    payload = _integrationapihub_mapping_payload(iah_connector_a, value_map="")
    form = SalesFieldMappingForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value_map"] == {}


def test_integrationapihub_field_mapping_form_clean_value_map_valid_dict(
    tenant_a,
    iah_connector_a,
):
    """Valid JSON dictionary string is successfully parsed and cleaned into dict."""
    dict_str = '{"draft": "D", "confirmed": "C", "closed": "X"}'
    payload = _integrationapihub_mapping_payload(iah_connector_a, value_map=dict_str)
    form = SalesFieldMappingForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value_map"] == {"draft": "D", "confirmed": "C", "closed": "X"}


def test_integrationapihub_field_mapping_form_clean_value_map_rejects_non_dict_json(
    tenant_a,
    iah_connector_a,
):
    """Non-dict JSON inputs (list, integer, string, boolean) raise ValidationError."""
    non_dict_inputs = [
        '["draft", "confirmed"]',  # JSON list
        "12345",                    # JSON integer
        '"just a string"',         # JSON string
        "true",                    # JSON boolean
    ]
    for non_dict_val in non_dict_inputs:
        payload = _integrationapihub_mapping_payload(iah_connector_a, value_map=non_dict_val)
        form = SalesFieldMappingForm(data=payload, tenant=tenant_a)
        assert not form.is_valid(), f"Expected invalid form for non-dict JSON: {non_dict_val}"
        assert "value_map" in form.errors
        assert "must be a valid JSON dictionary mapping" in form.errors["value_map"][0]


def test_integrationapihub_field_mapping_form_clean_value_map_rejects_invalid_json_syntax(
    tenant_a,
    iah_connector_a,
):
    """Malformed JSON syntax raises form error on value_map."""
    payload = _integrationapihub_mapping_payload(iah_connector_a, value_map="{bad_json: missing_quotes}")
    form = SalesFieldMappingForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "value_map" in form.errors


# ==============================================================================
# 3. SalesSyncJobForm Tests
# ==============================================================================

def test_integrationapihub_sync_job_form_excluded_fields():
    """Verify tenant, number, runtime statistics, and scheduler timestamps are excluded."""
    form = SalesSyncJobForm()
    excluded = {
        "tenant",
        "number",
        "last_run_at",
        "next_run_at",
        "total_runs_count",
        "total_records_synced",
    }
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must be excluded from SalesSyncJobForm"

    expected_fields = {
        "name",
        "connector",
        "entity_scope",
        "sync_direction",
        "conflict_policy",
        "cadence",
        "filter_expression",
        "batch_size",
        "status",
    }
    assert set(form.fields.keys()) == expected_fields


def test_integrationapihub_sync_job_form_tenant_scoped_queryset(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
):
    """connector dropdown queryset is strictly filtered to current tenant."""
    form = SalesSyncJobForm(tenant=tenant_a)
    qs = form.fields["connector"].queryset
    assert iah_connector_a in qs
    assert iah_connector_b not in qs


def test_integrationapihub_sync_job_form_batch_size_validation(
    tenant_a,
    iah_connector_a,
):
    """batch_size rejects values <= 0 and accepts valid positive values."""
    # Zero batch size
    payload_zero = _integrationapihub_job_payload(iah_connector_a, batch_size=0)
    form_zero = SalesSyncJobForm(data=payload_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "batch_size" in form_zero.errors

    # Negative batch size
    payload_neg = _integrationapihub_job_payload(iah_connector_a, batch_size=-50)
    form_neg = SalesSyncJobForm(data=payload_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "batch_size" in form_neg.errors

    # Boundary: 1 is valid
    payload_one = _integrationapihub_job_payload(iah_connector_a, batch_size=1)
    form_one = SalesSyncJobForm(data=payload_one, tenant=tenant_a)
    assert form_one.is_valid(), form_one.errors

    # Standard positive value
    payload_valid = _integrationapihub_job_payload(iah_connector_a, batch_size=250)
    form_valid = SalesSyncJobForm(data=payload_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_integrationapihub_sync_job_form_cross_tenant_connector_rejection(
    tenant_a,
    iah_connector_b,
):
    """_reject_foreign rejects connector belonging to another workspace."""
    payload = _integrationapihub_job_payload(iah_connector_b)
    # Unwidened
    form = SalesSyncJobForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "connector" in form.errors

    # Widened: triggers _reject_foreign
    form_widened = SalesSyncJobForm(data=payload, tenant=tenant_a)
    _integrationapihub_widen(form_widened, "connector", SalesIntegrationConnector.objects.all())
    assert not form_widened.is_valid()
    assert "connector" in form_widened.errors
    assert "another workspace" in form_widened.errors["connector"][0].lower()


def test_integrationapihub_sync_job_form_valid_save(tenant_a, iah_connector_a):
    """Valid submission saves SalesSyncJob with proper tenant isolation and auto-numbering."""
    payload = _integrationapihub_job_payload(
        iah_connector_a,
        name="Scheduled Order Pipeline",
        cadence="hourly",
        batch_size=200,
    )
    form = SalesSyncJobForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    job = form.save(commit=False)
    job.tenant = tenant_a
    job.save()

    assert job.pk is not None
    assert job.tenant == tenant_a
    assert job.number.startswith("SSJ-")
    assert job.name == "Scheduled Order Pipeline"
    assert job.batch_size == 200


# ==============================================================================
# 4. SalesSyncRunForm Tests
# ==============================================================================

def test_integrationapihub_sync_run_form_excluded_fields():
    """Verify tenant, number, started_at, and finished_at are excluded."""
    form = SalesSyncRunForm()
    excluded = {"tenant", "number", "started_at", "finished_at"}
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must be excluded from SalesSyncRunForm"

    expected_fields = {
        "connector",
        "job",
        "run_type",
        "status",
        "records_read",
        "records_written",
        "records_failed",
        "records_skipped",
        "error_log",
    }
    assert set(form.fields.keys()) == expected_fields


def test_integrationapihub_sync_run_form_tenant_scoped_querysets(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
    iah_sync_job_a,
    iah_sync_job_b,
):
    """connector and job querysets are strictly filtered to current tenant."""
    form = SalesSyncRunForm(tenant=tenant_a)
    assert iah_connector_a in form.fields["connector"].queryset
    assert iah_connector_b not in form.fields["connector"].queryset
    assert iah_sync_job_a in form.fields["job"].queryset
    assert iah_sync_job_b not in form.fields["job"].queryset


def test_integrationapihub_sync_run_form_cross_tenant_connector_rejection(
    tenant_a,
    iah_connector_b,
    iah_sync_job_a,
):
    """_reject_foreign rejects connector belonging to another workspace."""
    payload = _integrationapihub_run_payload(iah_connector_b, job=iah_sync_job_a)
    # Unwidened
    form = SalesSyncRunForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "connector" in form.errors

    # Widened: triggers _reject_foreign
    form_widened = SalesSyncRunForm(data=payload, tenant=tenant_a)
    _integrationapihub_widen(form_widened, "connector", SalesIntegrationConnector.objects.all())
    assert not form_widened.is_valid()
    assert "connector" in form_widened.errors
    assert "another workspace" in form_widened.errors["connector"][0].lower()


def test_integrationapihub_sync_run_form_cross_tenant_job_rejection(
    tenant_a,
    iah_connector_a,
    iah_sync_job_b,
):
    """_reject_foreign rejects job belonging to another workspace."""
    payload = _integrationapihub_run_payload(iah_connector_a, job=iah_sync_job_b)
    # Unwidened
    form = SalesSyncRunForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "job" in form.errors

    # Widened: triggers _reject_foreign
    form_widened = SalesSyncRunForm(data=payload, tenant=tenant_a)
    _integrationapihub_widen(form_widened, "job", SalesSyncJob.objects.all())
    assert not form_widened.is_valid()
    assert "job" in form_widened.errors
    assert "another workspace" in form_widened.errors["job"][0].lower()


def test_integrationapihub_sync_run_form_valid_save_with_and_without_job(
    tenant_a,
    iah_connector_a,
    iah_sync_job_a,
):
    """SalesSyncRunForm saves successfully both with an associated job and on-demand without a job."""
    # With job
    payload_with_job = _integrationapihub_run_payload(
        iah_connector_a,
        job=iah_sync_job_a,
        run_type="scheduled",
        status="completed",
        records_read=500,
        records_written=495,
        records_failed=5,
    )
    form_with_job = SalesSyncRunForm(data=payload_with_job, tenant=tenant_a)
    assert form_with_job.is_valid(), form_with_job.errors

    run1 = form_with_job.save(commit=False)
    run1.tenant = tenant_a
    run1.save()

    assert run1.pk is not None
    assert run1.tenant == tenant_a
    assert run1.number.startswith("SSR-")
    assert run1.job == iah_sync_job_a
    assert run1.records_read == 500

    # Without job (on-demand / test ping)
    payload_no_job = _integrationapihub_run_payload(
        iah_connector_a,
        job=None,
        run_type="test_ping",
        status="simulated",
    )
    form_no_job = SalesSyncRunForm(data=payload_no_job, tenant=tenant_a)
    assert form_no_job.is_valid(), form_no_job.errors

    run2 = form_no_job.save(commit=False)
    run2.tenant = tenant_a
    run2.save()

    assert run2.pk is not None
    assert run2.tenant == tenant_a
    assert run2.job is None
    assert run2.run_type == "test_ping"
    assert run2.status == "simulated"
