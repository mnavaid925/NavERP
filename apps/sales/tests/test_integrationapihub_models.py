"""Unit tests for Sales 8.18 Integration & API Hub models.

Subslug: integrationapihub
Prefix for test functions: test_integrationapihub_*
Prefix for helper functions: _integrationapihub_*

Covers:
1. SalesIntegrationConnector:
   - Auto-numbering prefix 'SIC-' and sequence per tenant.
   - Fernet credential encryption (set_credential), decryption (get_credential),
     masked property (credential_masked -> '••••••••'), and boolean helper (has_credential).
   - Tenant isolation & uniqueness constraint sales_sic_tenant_num_uniq.
   - String representation __str__.
   - Choice sets and default values.
2. SalesFieldMapping:
   - Unique constraint (tenant, connector, target_entity, local_field, remote_field).
   - Model-level clean() cross-tenant foreign key rejection (connector.tenant != mapping.tenant).
   - String representation __str__ (safe with connector or unassigned).
   - JSON value_map handling, validation, and default value.
   - Choice sets and unnumbered confirmation.
3. SalesSyncJob:
   - Auto-numbering prefix 'SSJ-' and sequence per tenant.
   - Unique constraint sales_ssj_tenant_num_uniq.
   - batch_size minimum value validator (MinValueValidator(1) rejects <= 0).
   - Model-level clean() cross-tenant foreign key rejection.
   - String representation __str__.
   - Choice sets and default values.
4. SalesSyncRun:
   - Auto-numbering prefix 'SSR-' and sequence per tenant.
   - Unique constraint sales_ssr_tenant_num_uniq.
   - Model-level clean() cross-tenant foreign key rejection (connector or job cross-tenant).
   - Simulated status default (status='simulated').
   - String representation __str__.
   - Nullable job reference with SET_NULL behavior.
"""
import re
import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.crypto import is_encrypted
from apps.sales.models import (
    AUTH_METHOD_CHOICES,
    CADENCE_CHOICES,
    CATEGORY_CHOICES,
    CONFLICT_POLICY_CHOICES,
    ENVIRONMENT_CHOICES,
    FIELD_DIRECTION_CHOICES,
    FIELD_TARGET_ENTITY_CHOICES,
    HEALTH_STATUS_CHOICES,
    JOB_DIRECTION_CHOICES,
    JOB_STATUS_CHOICES,
    PROVIDER_CHOICES,
    RUN_STATUS_CHOICES,
    RUN_TYPE_CHOICES,
    SalesFieldMapping,
    SalesIntegrationConnector,
    SalesSyncJob,
    SalesSyncRun,
    TRANSFORM_CHOICES,
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

def _integrationapihub_make_duplicate_num_connector(tenant, number):
    """Helper to bypass auto-numbering and attempt duplicate number insertion."""
    obj = SalesIntegrationConnector(
        tenant=tenant,
        name="Duplicate Number Test",
        category="erp",
        provider="sap",
    )
    obj.number = number
    return obj


def _integrationapihub_make_duplicate_num_job(tenant, connector, number):
    """Helper to bypass auto-numbering and attempt duplicate job number insertion."""
    obj = SalesSyncJob(
        tenant=tenant,
        connector=connector,
        name="Duplicate Job Number Test",
        entity_scope="order_to_cash",
    )
    obj.number = number
    return obj


def _integrationapihub_make_duplicate_num_run(tenant, connector, number):
    """Helper to bypass auto-numbering and attempt duplicate run number insertion."""
    obj = SalesSyncRun(
        tenant=tenant,
        connector=connector,
        run_type="manual",
    )
    obj.number = number
    return obj


# ==============================================================================
# 1. SalesIntegrationConnector Tests
# ==============================================================================

def test_integrationapihub_connector_number_prefix_and_sequence(tenant_a, tenant_b):
    """Auto-numbering starts with SIC- and sequence is isolated per tenant."""
    assert SalesIntegrationConnector.NUMBER_PREFIX == "SIC"

    conn_a1 = _integrationapihub_connector(tenant_a, name="Connector A1")
    conn_a2 = _integrationapihub_connector(tenant_a, name="Connector A2")
    conn_b1 = _integrationapihub_connector(tenant_b, name="Connector B1")

    assert re.match(r"^SIC-\d{5}$", conn_a1.number)
    assert re.match(r"^SIC-\d{5}$", conn_a2.number)
    assert re.match(r"^SIC-\d{5}$", conn_b1.number)

    # Tenant sequence starts at 1
    assert conn_a1.number == "SIC-00001"
    assert conn_a2.number == "SIC-00002"
    assert conn_b1.number == "SIC-00001"

    # Preserved on re-save
    original_number = conn_a1.number
    conn_a1.name = "Connector A1 Updated"
    conn_a1.save()
    conn_a1.refresh_from_db()
    assert conn_a1.number == original_number


def test_integrationapihub_connector_fernet_credential_encryption_and_decryption(tenant_a):
    """Fernet credential encryption stores encrypted text and decrypts cleanly."""
    conn = _integrationapihub_connector(tenant_a, name="SAP Financial Hub")
    raw_secret = "sap_prod_live_api_key_884920!"

    conn.set_credential(raw_secret)
    conn.save()
    conn.refresh_from_db()

    # Storage is encrypted with fernet prefix and differs from plaintext
    assert conn.credential_encrypted != raw_secret
    assert is_encrypted(conn.credential_encrypted)
    assert conn.credential_encrypted.startswith("fernet.v1:")

    # Decryption recovers exact secret
    assert conn.get_credential() == raw_secret

    # Stripping leading/trailing whitespace
    conn.set_credential("   secret_with_spaces   ")
    assert conn.get_credential() == "secret_with_spaces"

    # Clearing credential
    conn.set_credential("")
    assert conn.credential_encrypted == ""
    assert conn.get_credential() == ""

    # None clears as well
    conn.set_credential(None)
    assert conn.credential_encrypted == ""
    assert conn.get_credential() == ""


def test_integrationapihub_connector_credential_masked_and_has_credential_helper(tenant_a):
    """Masked property returns '••••••••' or 'None', has_credential returns boolean."""
    conn = _integrationapihub_connector(tenant_a, name="HubSpot Marketing Hub")

    # Initial state: no credentials
    assert conn.credential_encrypted == ""
    assert conn.has_credential() is False
    assert conn.credential_masked == "None"
    assert conn.masked_credential == "None"

    # Set credentials
    conn.set_credential("hs_private_app_secret_abc123")
    conn.save()

    assert conn.has_credential() is True
    assert conn.credential_masked == "••••••••"
    assert conn.masked_credential == "••••••••"


def test_integrationapihub_connector_tenant_isolation_and_uniqueness_constraint(tenant_a, tenant_b):
    """Unique constraint sales_sic_tenant_num_uniq prevents duplicate numbers within tenant."""
    conn_a1 = _integrationapihub_connector(tenant_a, name="Connector A1")
    assert conn_a1.number == "SIC-00001"

    # Duplicate on same tenant must fail
    dup = _integrationapihub_make_duplicate_num_connector(tenant_a, "SIC-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup.save()

    # Same number on different tenant must succeed
    conn_b1 = _integrationapihub_connector(tenant_b, name="Connector B1")
    assert conn_b1.number == "SIC-00001"

    # Queryset tenant isolation
    assert SalesIntegrationConnector.objects.filter(tenant=tenant_a).count() == 1
    assert SalesIntegrationConnector.objects.filter(tenant=tenant_b).count() == 1


def test_integrationapihub_connector_str_representation(tenant_a):
    """Connector __str__ formats number, name, and provider display."""
    conn = _integrationapihub_connector(
        tenant_a,
        name="Salesforce CRM Link",
        provider="hubspot",
    )
    expected = f"{conn.number} — Salesforce CRM Link (HubSpot CRM/Marketing)"
    assert str(conn) == expected


def test_integrationapihub_connector_choices_and_defaults(tenant_a):
    """Verify choice sets and default attribute values on SalesIntegrationConnector."""
    conn = SalesIntegrationConnector(tenant=tenant_a, name="Default Connector")
    assert conn.category == "erp"
    assert conn.provider == "sap"
    assert conn.environment == "production"
    assert conn.auth_method == "api_key"
    assert conn.health_status == "untested"
    assert conn.is_active is True
    assert conn.base_url == ""
    assert conn.remote_scope_ref == ""
    assert conn.credential_encrypted == ""
    assert conn.last_error_message == ""
    assert conn.notes == ""

    # Validate choices match constants
    assert len(CATEGORY_CHOICES) == 6
    assert len(PROVIDER_CHOICES) == 21
    assert len(ENVIRONMENT_CHOICES) == 3
    assert len(AUTH_METHOD_CHOICES) == 5
    assert len(HEALTH_STATUS_CHOICES) == 5


# ==============================================================================
# 2. SalesFieldMapping Tests
# ==============================================================================

def test_integrationapihub_field_mapping_unique_constraint(tenant_a, tenant_b, iah_connector_a, iah_connector_b):
    """Enforce sales_sfm_target_fields_uniq on (tenant, connector, target_entity, local_field, remote_field)."""
    mapping1 = _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="order",
        local_field="total_amount",
        remote_field="NETWR",
    )
    assert mapping1.pk is not None

    # Duplicate on same tenant, connector, target_entity, local_field, remote_field raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integrationapihub_field_mapping(
                tenant_a,
                connector=iah_connector_a,
                target_entity="order",
                local_field="total_amount",
                remote_field="NETWR",
            )

    # Different remote_field succeeds
    mapping_diff_remote = _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="order",
        local_field="total_amount",
        remote_field="BRTWR",
    )
    assert mapping_diff_remote.pk is not None

    # Same fields on different connector or tenant succeeds
    mapping_b = _integrationapihub_field_mapping(
        tenant_b,
        connector=iah_connector_b,
        target_entity="order",
        local_field="total_amount",
        remote_field="NETWR",
    )
    assert mapping_b.pk is not None


def test_integrationapihub_field_mapping_clean_cross_tenant_rejection(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
):
    """clean() rejects connector belonging to another tenant workspace."""
    # Cross-tenant: mapping on tenant_a with connector from tenant_b
    invalid_mapping = SalesFieldMapping(
        tenant=tenant_a,
        connector=iah_connector_b,
        target_entity="opportunity",
        local_field="probability",
        remote_field="PROB_PCT",
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_mapping.clean()
    assert "connector" in exc_info.value.message_dict
    assert "another tenant workspace" in exc_info.value.message_dict["connector"][0]

    # Matching tenant passes clean()
    valid_mapping = SalesFieldMapping(
        tenant=tenant_a,
        connector=iah_connector_a,
        target_entity="opportunity",
        local_field="probability",
        remote_field="PROB_PCT",
    )
    valid_mapping.clean()  # should not raise


def test_integrationapihub_field_mapping_str_representation(tenant_a, iah_connector_a):
    """__str__ formats connector name, target entity, and field arrow direction."""
    mapping = _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="quote",
        local_field="grand_total",
        remote_field="TOTAL_PRICE",
    )
    expected = f"{iah_connector_a.name} | CPQ Quote: grand_total → TOTAL_PRICE"
    assert str(mapping) == expected

    # Graceful fallback when connector is None / unassigned
    unattached = SalesFieldMapping(
        tenant=tenant_a,
        connector=None,
        target_entity="lead",
        local_field="email",
        remote_field="EMAIL_ADDR",
    )
    assert str(unattached) == "None | Sales Lead: email → EMAIL_ADDR"


def test_integrationapihub_field_mapping_json_value_map_and_default_value(tenant_a, iah_connector_a):
    """value_map stores JSON dictionary and clean() enforces dict type."""
    dict_map = {
        "draft": "D",
        "submitted": "S",
        "approved": "A",
        "rejected": "R",
    }
    mapping = _integrationapihub_field_mapping(
        tenant_a,
        connector=iah_connector_a,
        target_entity="order",
        local_field="status",
        remote_field="DOC_STATUS",
        transform_rule="value_map",
        value_map=dict_map,
        default_value="D",
    )
    mapping.refresh_from_db()
    assert mapping.value_map == dict_map
    assert mapping.default_value == "D"

    # Non-dictionary value_map rejected in clean()
    mapping.value_map = ["draft", "submitted"]
    with pytest.raises(ValidationError) as exc_info:
        mapping.clean()
    assert "value_map" in exc_info.value.message_dict
    assert "must be a dictionary" in exc_info.value.message_dict["value_map"][0]


def test_integrationapihub_field_mapping_is_unnumbered_and_choices(tenant_a, iah_connector_a):
    """SalesFieldMapping is TenantOwned (not TenantNumbered) and choice options match constants."""
    mapping = _integrationapihub_field_mapping(tenant_a, connector=iah_connector_a)

    assert not hasattr(mapping, "number")
    with pytest.raises(FieldDoesNotExist):
        SalesFieldMapping._meta.get_field("number")

    assert len(FIELD_TARGET_ENTITY_CHOICES) == 7
    assert len(FIELD_DIRECTION_CHOICES) == 3
    assert len(TRANSFORM_CHOICES) == 7


# ==============================================================================
# 3. SalesSyncJob Tests
# ==============================================================================

def test_integrationapihub_sync_job_number_prefix_and_sequence(tenant_a, tenant_b, iah_connector_a, iah_connector_b):
    """Auto-numbering starts with SSJ- and sequence is isolated per tenant."""
    assert SalesSyncJob.NUMBER_PREFIX == "SSJ"

    job_a1 = _integrationapihub_sync_job(tenant_a, connector=iah_connector_a, name="Job A1")
    job_a2 = _integrationapihub_sync_job(tenant_a, connector=iah_connector_a, name="Job A2")
    job_b1 = _integrationapihub_sync_job(tenant_b, connector=iah_connector_b, name="Job B1")

    assert re.match(r"^SSJ-\d{5}$", job_a1.number)
    assert re.match(r"^SSJ-\d{5}$", job_a2.number)
    assert re.match(r"^SSJ-\d{5}$", job_b1.number)

    assert job_a1.number == "SSJ-00001"
    assert job_a2.number == "SSJ-00002"
    assert job_b1.number == "SSJ-00001"

    # Number is preserved on re-save
    orig_num = job_a1.number
    job_a1.name = "Job A1 Renamed"
    job_a1.save()
    job_a1.refresh_from_db()
    assert job_a1.number == orig_num


def test_integrationapihub_sync_job_unique_constraint(tenant_a, tenant_b, iah_connector_a, iah_connector_b):
    """Unique constraint sales_ssj_tenant_num_uniq prevents duplicate numbers within tenant."""
    job_a1 = _integrationapihub_sync_job(tenant_a, connector=iah_connector_a, name="Job A1")
    assert job_a1.number == "SSJ-00001"

    dup = _integrationapihub_make_duplicate_num_job(tenant_a, iah_connector_a, "SSJ-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup.save()

    # Same number on different tenant succeeds
    job_b1 = _integrationapihub_sync_job(tenant_b, connector=iah_connector_b, name="Job B1")
    assert job_b1.number == "SSJ-00001"


def test_integrationapihub_sync_job_batch_size_min_value_validator(tenant_a, iah_connector_a):
    """batch_size MinValueValidator(1) rejects values <= 0 on full_clean()."""
    job = _integrationapihub_sync_job(tenant_a, connector=iah_connector_a, batch_size=50)
    job.full_clean()  # Valid

    job.batch_size = 0
    with pytest.raises(ValidationError) as exc_info:
        job.full_clean()
    assert "batch_size" in exc_info.value.message_dict

    job.batch_size = 1
    job.full_clean()  # 1 is valid minimum boundary


def test_integrationapihub_sync_job_clean_cross_tenant_rejection(tenant_a, tenant_b, iah_connector_b):
    """clean() rejects connector belonging to another tenant workspace."""
    invalid_job = SalesSyncJob(
        tenant=tenant_a,
        connector=iah_connector_b,
        name="Cross-Tenant Job",
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_job.clean()
    assert "connector" in exc_info.value.message_dict
    assert "another tenant workspace" in exc_info.value.message_dict["connector"][0]


def test_integrationapihub_sync_job_str_representation(tenant_a, iah_connector_a):
    """__str__ formats number, name, and entity scope display."""
    job = _integrationapihub_sync_job(
        tenant_a,
        connector=iah_connector_a,
        name="SAP Orders Hourly Push",
        entity_scope="order_to_cash",
    )
    expected = f"{job.number} — SAP Orders Hourly Push (Order-to-Cash (ERP))"
    assert str(job) == expected


def test_integrationapihub_sync_job_choices_and_defaults(tenant_a, iah_connector_a):
    """Verify default values and choices for SalesSyncJob."""
    job = SalesSyncJob(tenant=tenant_a, connector=iah_connector_a, name="Default Job")
    assert job.entity_scope == "order_to_cash"
    assert job.sync_direction == "outbound"
    assert job.conflict_policy == "last_updated_wins"
    assert job.cadence == "hourly"
    assert job.batch_size == 100
    assert job.status == "active"
    assert job.filter_expression == ""
    assert job.total_runs_count == 0
    assert job.total_records_synced == 0

    assert len(CADENCE_CHOICES) == 5
    assert len(CONFLICT_POLICY_CHOICES) == 4
    assert len(JOB_DIRECTION_CHOICES) == 3
    assert len(JOB_STATUS_CHOICES) == 3


# ==============================================================================
# 4. SalesSyncRun Tests
# ==============================================================================

def test_integrationapihub_sync_run_number_prefix_and_sequence(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
    iah_sync_job_a,
    iah_sync_job_b,
):
    """Auto-numbering starts with SSR- and sequence is isolated per tenant."""
    assert SalesSyncRun.NUMBER_PREFIX == "SSR"

    run_a1 = _integrationapihub_sync_run(tenant_a, connector=iah_connector_a, job=iah_sync_job_a)
    run_a2 = _integrationapihub_sync_run(tenant_a, connector=iah_connector_a, job=iah_sync_job_a)
    run_b1 = _integrationapihub_sync_run(tenant_b, connector=iah_connector_b, job=iah_sync_job_b)

    assert re.match(r"^SSR-\d{5}$", run_a1.number)
    assert re.match(r"^SSR-\d{5}$", run_a2.number)
    assert re.match(r"^SSR-\d{5}$", run_b1.number)

    assert run_a1.number == "SSR-00001"
    assert run_a2.number == "SSR-00002"
    assert run_b1.number == "SSR-00001"

    # Number is preserved on re-save
    orig_num = run_a1.number
    run_a1.records_read = 120
    run_a1.save()
    run_a1.refresh_from_db()
    assert run_a1.number == orig_num


def test_integrationapihub_sync_run_unique_constraint(tenant_a, tenant_b, iah_connector_a, iah_connector_b):
    """Unique constraint sales_ssr_tenant_num_uniq prevents duplicate numbers within tenant."""
    run_a1 = _integrationapihub_sync_run(tenant_a, connector=iah_connector_a)
    assert run_a1.number == "SSR-00001"

    dup = _integrationapihub_make_duplicate_num_run(tenant_a, iah_connector_a, "SSR-00001")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup.save()

    # Same number on different tenant succeeds
    run_b1 = _integrationapihub_sync_run(tenant_b, connector=iah_connector_b)
    assert run_b1.number == "SSR-00001"


def test_integrationapihub_sync_run_clean_cross_tenant_rejection(
    tenant_a,
    tenant_b,
    iah_connector_a,
    iah_connector_b,
    iah_sync_job_a,
    iah_sync_job_b,
):
    """clean() rejects cross-tenant connector or job."""
    # Cross-tenant connector
    invalid_run_conn = SalesSyncRun(
        tenant=tenant_a,
        connector=iah_connector_b,
        job=iah_sync_job_a,
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_run_conn.clean()
    assert "connector" in exc_info.value.message_dict
    assert "another tenant workspace" in exc_info.value.message_dict["connector"][0]

    # Cross-tenant job
    invalid_run_job = SalesSyncRun(
        tenant=tenant_a,
        connector=iah_connector_a,
        job=iah_sync_job_b,
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_run_job.clean()
    assert "job" in exc_info.value.message_dict
    assert "another tenant workspace" in exc_info.value.message_dict["job"][0]

    # Valid matching tenant
    valid_run = SalesSyncRun(
        tenant=tenant_a,
        connector=iah_connector_a,
        job=iah_sync_job_a,
    )
    valid_run.clean()  # should not raise


def test_integrationapihub_sync_run_simulated_status_default_and_choices(tenant_a, iah_connector_a):
    """SalesSyncRun defaults to status='simulated' (honest diagnostic) and manual run_type."""
    run = SalesSyncRun(tenant=tenant_a, connector=iah_connector_a)
    assert run.status == "simulated"
    assert run.run_type == "manual"
    assert run.records_read == 0
    assert run.records_written == 0
    assert run.records_failed == 0
    assert run.records_skipped == 0
    assert run.error_log == ""
    assert run.summary_payload == {}

    assert len(RUN_TYPE_CHOICES) == 4
    assert len(RUN_STATUS_CHOICES) == 4


def test_integrationapihub_sync_run_str_representation(tenant_a, iah_connector_a):
    """__str__ formats number, run type display, and status display."""
    run = _integrationapihub_sync_run(
        tenant_a,
        connector=iah_connector_a,
        run_type="test_ping",
        status="simulated",
    )
    expected = f"{run.number} — Health Ping / Test (Simulated (Honest Diagnostic))"
    assert str(run) == expected


def test_integrationapihub_sync_run_job_optional_and_set_null_on_delete(tenant_a, iah_connector_a, iah_sync_job_a):
    """job foreign key is optional; deleting the job sets run.job to NULL."""
    run = _integrationapihub_sync_run(
        tenant_a,
        connector=iah_connector_a,
        job=iah_sync_job_a,
    )
    assert run.job == iah_sync_job_a

    # Delete the job
    job_pk = iah_sync_job_a.pk
    iah_sync_job_a.delete()

    run.refresh_from_db()
    assert run.job is None
    assert not SalesSyncJob.objects.filter(pk=job_pk).exists()
    assert SalesSyncRun.objects.filter(pk=run.pk).exists()
