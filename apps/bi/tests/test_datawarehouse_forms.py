"""Unit tests for Sub-module 10.3 forms (DataMartForm, LakehouseZoneForm, WarehouseStoragePolicyForm, WarehouseTableForm)."""
import json
import pytest
from django.contrib.auth import get_user_model

from apps.bi.forms import (
    DataMartForm,
    LakehouseZoneForm,
    WarehouseStoragePolicyForm,
    WarehouseTableForm,
)
from apps.bi.models import (
    DataMart,
    LakehouseZone,
    WarehouseStoragePolicy,
    WarehouseTable,
)
from apps.core.models.OrgUnit import OrgUnit


User = get_user_model()


def _datawarehouse_create_user(tenant, username, is_active=True):
    """Helper to create a user with specified active status in a tenant."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_active=is_active,
    )


def _datawarehouse_create_org_unit(tenant, name="Finance Department"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _datawarehouse_base_datamart_data(**overrides):
    """Helper generating valid DataMart form payload."""
    data = {
        "name": "Finance General Ledger Mart",
        "code": "finance_gl_mart",
        "subject_area": "finance",
        "access_tier": "department",
        "certification_status": "certified",
        "refresh_cadence": "daily",
        "description": "General ledger and journal entries analytics mart.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _datawarehouse_base_lakehouse_zone_data(**overrides):
    """Helper generating valid LakehouseZone form payload."""
    data = {
        "name": "Silver Curated Zone",
        "code": "silver_curated",
        "zone_type": "silver",
        "storage_backend": "aws_s3",
        "default_format": "delta_lake",
        "base_uri_path": "s3://lakehouse-data/silver/",
        "is_read_only": False,
        "description": "Curated clean master zone.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _datawarehouse_base_storage_policy_data(**overrides):
    """Helper generating valid WarehouseStoragePolicy form payload."""
    data = {
        "name": "Standard Fact Retention Policy",
        "partition_strategy": "range_time",
        "partition_key": "posting_date",
        "partition_granularity": "month",
        "compression_codec": "zstd",
        "enable_zone_maps": True,
        "hot_tier_days": 90,
        "warm_tier_days": 365,
        "cold_tier_days": 2555,
        "time_travel_days": 14,
        "auto_purge_enabled": False,
        "vacuum_cadence": "weekly",
        "is_default": False,
        "description": "Standard storage lifecycle for financial tables.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _datawarehouse_base_warehouse_table_data(zone, policy=None, mart=None, **overrides):
    """Helper generating valid WarehouseTable form payload."""
    data = {
        "name": "Fact General Ledger Journal Entries",
        "table_name": "fact_gl_journal_entries",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": zone.pk,
        "primary_key_column": "entry_sk",
        "natural_key_column": "journal_number",
        "is_conformed_dimension": False,
        "description": "Transactional line item entries.",
        "is_active": True,
        "schema_definition_raw": json.dumps([
            {"name": "entry_sk", "type": "BIGINT", "nullable": False},
            {"name": "journal_number", "type": "VARCHAR(64)", "nullable": False},
            {"name": "posting_date", "type": "DATE", "nullable": False},
            {"name": "amount", "type": "NUMERIC(14,2)", "nullable": False},
        ]),
    }
    if policy:
        data["storage_policy"] = policy.pk
    if mart:
        data["data_mart"] = mart.pk
    data.update(overrides)
    return data


# ===========================================================================
# 1. DataMartForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_system_field_exclusions(tenant_a):
    """Verify DataMartForm excludes internal system fields from fields list."""
    form = DataMartForm(tenant=tenant_a)
    excluded = ["tenant", "number", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from DataMartForm"


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_valid_creation(tenant_a, admin_user):
    """Verify valid submission creates DataMart with tenant assigned and correct prefix."""
    ou = _datawarehouse_create_org_unit(tenant_a, "Financial Planning")
    data = _datawarehouse_base_datamart_data(
        name="FP&A Analytics Mart",
        code="fpa_analytics_mart",
        org_unit=ou.pk,
        owner=admin_user.pk,
        steward=admin_user.pk,
    )
    form = DataMartForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    mart = form.save()
    assert mart.tenant == tenant_a
    assert mart.name == "FP&A Analytics Mart"
    assert mart.code == "fpa_analytics_mart"
    assert mart.org_unit == ou
    assert mart.owner == admin_user
    assert mart.steward == admin_user
    assert mart.number.startswith("BDMT-")


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_required_fields(tenant_a):
    """Verify required field validation on name and code."""
    form = DataMartForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "code" in form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_scoped_querysets(tenant_a, tenant_b, admin_user, admin_user_b):
    """Verify org_unit, owner, and steward querysets are strictly tenant-isolated and active-only."""
    ou_a = _datawarehouse_create_org_unit(tenant_a, "Acme Finance")
    ou_b = _datawarehouse_create_org_unit(tenant_b, "Globex Finance")

    active_user_a = _datawarehouse_create_user(tenant_a, "active_analyst", is_active=True)
    inactive_user_a = _datawarehouse_create_user(tenant_a, "inactive_analyst", is_active=False)

    form = DataMartForm(tenant=tenant_a)
    ou_qs = form.fields["org_unit"].queryset
    assert ou_a in ou_qs
    assert ou_b not in ou_qs

    owner_qs = form.fields["owner"].queryset
    assert admin_user in owner_qs
    assert active_user_a in owner_qs
    assert inactive_user_a not in owner_qs
    assert admin_user_b not in owner_qs

    steward_qs = form.fields["steward"].queryset
    assert admin_user in steward_qs
    assert active_user_a in steward_qs
    assert inactive_user_a not in steward_qs
    assert admin_user_b not in steward_qs


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_scoped_querysets_bound_inactive_user(tenant_a):
    """Verify bound inactive owner and steward remain accessible in queryset during edits."""
    inactive_owner = _datawarehouse_create_user(tenant_a, "former_owner", is_active=False)
    inactive_steward = _datawarehouse_create_user(tenant_a, "former_steward", is_active=False)

    mart = DataMart.objects.create(
        tenant=tenant_a,
        name="Legacy Mart",
        code="legacy_mart",
        owner=inactive_owner,
        steward=inactive_steward,
    )

    form = DataMartForm(instance=mart, tenant=tenant_a)
    assert inactive_owner in form.fields["owner"].queryset
    assert inactive_steward in form.fields["steward"].queryset


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_unscoped_tenant_querysets():
    """Verify unscoped initialization (tenant=None) produces empty user querysets."""
    form = DataMartForm()
    assert form.fields["owner"].queryset.count() == 0
    assert form.fields["steward"].queryset.count() == 0


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_reject_foreign_org_unit(tenant_a, tenant_b):
    """Verify reject_foreign defense rejects foreign tenant org unit."""
    foreign_ou = _datawarehouse_create_org_unit(tenant_b, "Globex Org Unit")
    data = _datawarehouse_base_datamart_data(org_unit=foreign_ou.pk)

    # Scoped queryset rejects at field level
    form = DataMartForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors

    # reject_foreign defense validator rejects explicitly when queryset widened
    form_wide = DataMartForm(data=data, tenant=tenant_a)
    form_wide.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["org_unit"]


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_reject_foreign_owner_and_steward(tenant_a, tenant_b, admin_user_b):
    """Verify reject_foreign defense rejects foreign tenant owner and steward."""
    data = _datawarehouse_base_datamart_data(owner=admin_user_b.pk, steward=admin_user_b.pk)

    # Scoped queryset rejects at field level
    form = DataMartForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors
    assert "steward" in form.errors

    # reject_foreign defense validator rejects explicitly when querysets widened
    form_wide = DataMartForm(data=data, tenant=tenant_a)
    form_wide.fields["owner"].queryset = User.objects.all()
    form_wide.fields["steward"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["owner"]
    assert "That record belongs to another workspace." in form_wide.errors["steward"]


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_code_formatting_and_lowercasing(tenant_a):
    """Verify code is stripped and converted to lowercase."""
    data = _datawarehouse_base_datamart_data(code="  FINANCE_REPORTING_MART  ")
    form = DataMartForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    mart = form.save()
    assert mart.code == "finance_reporting_mart"


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_duplicate_code_validation_same_tenant(tenant_a, data_mart_a):
    """Verify duplicate slug code within the same tenant triggers validation error."""
    data = _datawarehouse_base_datamart_data(code=data_mart_a.code)
    form = DataMartForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "code" in form.errors
    assert "A data mart with this slug code already exists in your workspace." in form.errors["code"]


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_duplicate_code_allowed_cross_tenant(tenant_b, data_mart_a):
    """Verify identical slug code in different tenant is allowed."""
    data = _datawarehouse_base_datamart_data(code=data_mart_a.code)
    form = DataMartForm(data=data, tenant=tenant_b)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_edit_own_code_allowed(tenant_a, data_mart_a):
    """Verify updating existing mart retaining same code passes validation."""
    data = _datawarehouse_base_datamart_data(
        name="Updated Mart Name",
        code=data_mart_a.code,
    )
    form = DataMartForm(data=data, instance=data_mart_a, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_datamart_choices_validation(tenant_a):
    """Verify validation against invalid choice values."""
    data = _datawarehouse_base_datamart_data(
        subject_area="invalid_subject",
        access_tier="top_secret_invalid",
        certification_status="unapproved",
        refresh_cadence="every_second",
    )
    form = DataMartForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subject_area" in form.errors
    assert "access_tier" in form.errors
    assert "certification_status" in form.errors
    assert "refresh_cadence" in form.errors


# ===========================================================================
# 2. LakehouseZoneForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_system_field_exclusions(tenant_a):
    """Verify LakehouseZoneForm excludes internal system fields."""
    form = LakehouseZoneForm(tenant=tenant_a)
    excluded = ["tenant", "number", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from LakehouseZoneForm"


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_valid_creation(tenant_a):
    """Verify valid LakehouseZoneForm submission assigns tenant and generates BLHZ prefix."""
    data = _datawarehouse_base_lakehouse_zone_data(
        name="Bronze Ingestion Landing",
        code="bronze_ingestion_landing",
        zone_type="bronze",
        storage_backend="azure_blob",
        default_format="parquet",
        base_uri_path="abfss://lake@storage.dfs.core.windows.net/bronze/",
        is_read_only=True,
    )
    form = LakehouseZoneForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    zone = form.save()
    assert zone.tenant == tenant_a
    assert zone.name == "Bronze Ingestion Landing"
    assert zone.code == "bronze_ingestion_landing"
    assert zone.zone_type == "bronze"
    assert zone.storage_backend == "azure_blob"
    assert zone.default_format == "parquet"
    assert zone.is_read_only is True
    assert zone.number.startswith("BLHZ-")


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_code_lowercasing_and_trimming(tenant_a):
    """Verify code field is trimmed and converted to lowercase."""
    data = _datawarehouse_base_lakehouse_zone_data(code="  GOLD_AGGREGATES  ")
    form = LakehouseZoneForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    zone = form.save()
    assert zone.code == "gold_aggregates"


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_duplicate_code_same_tenant(tenant_a, lakehouse_zone_a):
    """Verify duplicate slug code within tenant raises validation error."""
    data = _datawarehouse_base_lakehouse_zone_data(code=lakehouse_zone_a.code)
    form = LakehouseZoneForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "code" in form.errors
    assert "A lakehouse zone with this slug code already exists in your workspace." in form.errors["code"]


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_duplicate_code_cross_tenant_allowed(tenant_b, lakehouse_zone_a):
    """Verify same slug code in another tenant passes validation."""
    data = _datawarehouse_base_lakehouse_zone_data(code=lakehouse_zone_a.code)
    form = LakehouseZoneForm(data=data, tenant=tenant_b)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_edit_own_code_allowed(tenant_a, lakehouse_zone_a):
    """Verify updating existing zone with its current code is valid."""
    data = _datawarehouse_base_lakehouse_zone_data(
        name="Renamed Gold Zone",
        code=lakehouse_zone_a.code,
    )
    form = LakehouseZoneForm(data=data, instance=lakehouse_zone_a, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_choices_validation(tenant_a):
    """Verify choices validation on zone_type, storage_backend, and default_format."""
    data = _datawarehouse_base_lakehouse_zone_data(
        zone_type="platinum_unknown",
        storage_backend="floppy_drive",
        default_format="binary_blob_unknown",
    )
    form = LakehouseZoneForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "zone_type" in form.errors
    assert "storage_backend" in form.errors
    assert "default_format" in form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_lakehouse_zone_base_uri_path_optional(tenant_a):
    """Verify base_uri_path is optional and can be left blank."""
    data = _datawarehouse_base_lakehouse_zone_data(base_uri_path="")
    form = LakehouseZoneForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    zone = form.save()
    assert zone.base_uri_path == ""


# ===========================================================================
# 3. WarehouseStoragePolicyForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_system_field_exclusions(tenant_a):
    """Verify WarehouseStoragePolicyForm excludes internal system fields."""
    form = WarehouseStoragePolicyForm(tenant=tenant_a)
    excluded = ["tenant", "number", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from WarehouseStoragePolicyForm"


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_valid_creation(tenant_a):
    """Verify valid storage policy submission assigns tenant and generates BWSP prefix."""
    data = _datawarehouse_base_storage_policy_data(
        name="Statutory 7-Year Cold Policy",
        partition_strategy="range_time",
        partition_key="posting_date",
        partition_granularity="month",
        compression_codec="zstd",
        enable_zone_maps=True,
        hot_tier_days=60,
        warm_tier_days=180,
        cold_tier_days=2555,
        time_travel_days=30,
        auto_purge_enabled=True,
        vacuum_cadence="monthly",
        is_default=True,
    )
    form = WarehouseStoragePolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    policy = form.save()
    assert policy.tenant == tenant_a
    assert policy.name == "Statutory 7-Year Cold Policy"
    assert policy.hot_tier_days == 60
    assert policy.warm_tier_days == 180
    assert policy.cold_tier_days == 2555
    assert policy.time_travel_days == 30
    assert policy.auto_purge_enabled is True
    assert policy.number.startswith("BWSP-")


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_time_travel_days_boundary_valid(tenant_a):
    """Verify time_travel_days boundary values 0 and 90 are both valid."""
    data_0 = _datawarehouse_base_storage_policy_data(time_travel_days=0)
    form_0 = WarehouseStoragePolicyForm(data=data_0, tenant=tenant_a)
    assert form_0.is_valid(), form_0.errors

    data_90 = _datawarehouse_base_storage_policy_data(time_travel_days=90)
    form_90 = WarehouseStoragePolicyForm(data=data_90, tenant=tenant_a)
    assert form_90.is_valid(), form_90.errors


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_time_travel_days_negative_rejected(tenant_a):
    """Verify time_travel_days < 0 triggers validation error."""
    data = _datawarehouse_base_storage_policy_data(time_travel_days=-1)
    form = WarehouseStoragePolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "time_travel_days" in form.errors

    # Verify clean() rule explicitly reports the custom error when negative value is checked
    form_clean = WarehouseStoragePolicyForm(tenant=tenant_a)
    form_clean.cleaned_data = {"time_travel_days": -10}
    form_clean.clean()
    assert "Time travel retention must be between 0 and 90 days." in form_clean.errors["time_travel_days"]


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_time_travel_days_exceeds_90_rejected(tenant_a):
    """Verify time_travel_days > 90 triggers validation error."""
    data = _datawarehouse_base_storage_policy_data(time_travel_days=91)
    form = WarehouseStoragePolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "time_travel_days" in form.errors
    assert "Time travel retention must be between 0 and 90 days." in form.errors["time_travel_days"]


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_tier_days_order_validation(tenant_a):
    """Verify hot <= warm <= cold order validation."""
    # hot > warm
    data_hot_warm = _datawarehouse_base_storage_policy_data(hot_tier_days=100, warm_tier_days=50)
    form_hw = WarehouseStoragePolicyForm(data=data_hot_warm, tenant=tenant_a)
    assert not form_hw.is_valid()
    assert "warm_tier_days" in form_hw.errors
    assert "Warm tier threshold must be greater than or equal to Hot tier days." in form_hw.errors["warm_tier_days"]

    # warm > cold
    data_warm_cold = _datawarehouse_base_storage_policy_data(
        hot_tier_days=30,
        warm_tier_days=400,
        cold_tier_days=300,
    )
    form_wc = WarehouseStoragePolicyForm(data=data_warm_cold, tenant=tenant_a)
    assert not form_wc.is_valid()
    assert "cold_tier_days" in form_wc.errors
    assert "Cold tier threshold must be greater than or equal to Warm tier days." in form_wc.errors["cold_tier_days"]


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_partition_key_required_if_partitioned(tenant_a):
    """Verify partition_key is required when partition_strategy is not 'none'."""
    data = _datawarehouse_base_storage_policy_data(
        partition_strategy="range_time",
        partition_key="",
    )
    form = WarehouseStoragePolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "partition_key" in form.errors
    assert "A partition key column must be specified when partition strategy is not None." in form.errors["partition_key"]

    # When strategy is none, partition_key can be empty
    data_none = _datawarehouse_base_storage_policy_data(
        partition_strategy="none",
        partition_key="",
    )
    form_none = WarehouseStoragePolicyForm(data=data_none, tenant=tenant_a)
    assert form_none.is_valid(), form_none.errors


@pytest.mark.django_db
def test_datawarehouse_forms_storage_policy_choices_validation(tenant_a):
    """Verify validation on partition_strategy, partition_granularity, compression_codec, and vacuum_cadence."""
    data = _datawarehouse_base_storage_policy_data(
        partition_strategy="invalid_strat",
        partition_granularity="millennium",
        compression_codec="rar_archive",
        vacuum_cadence="every_minute",
    )
    form = WarehouseStoragePolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "partition_strategy" in form.errors
    assert "partition_granularity" in form.errors
    assert "compression_codec" in form.errors
    assert "vacuum_cadence" in form.errors


# ===========================================================================
# 4. WarehouseTableForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_system_field_exclusions(tenant_a):
    """Verify WarehouseTableForm excludes internal system and analyzed metric fields."""
    form = WarehouseTableForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "row_count",
        "compressed_bytes",
        "compression_ratio",
        "last_analyzed_at",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from WarehouseTableForm"


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_valid_creation(
    tenant_a,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
):
    """Verify valid WarehouseTableForm submission parses schema JSON and saves instance."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        policy=storage_policy_a,
        mart=data_mart_a,
        name="Fact Sales Invoices",
        table_name="fact_sales_invoices",
        table_type="fact",
        schema_type="star",
        grain="transaction",
        primary_key_column="invoice_sk",
        natural_key_column="invoice_number",
        is_conformed_dimension=False,
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    table = form.save()
    assert table.tenant == tenant_a
    assert table.name == "Fact Sales Invoices"
    assert table.table_name == "fact_sales_invoices"
    assert table.lakehouse_zone == lakehouse_zone_a
    assert table.storage_policy == storage_policy_a
    assert table.data_mart == data_mart_a
    assert table.primary_key_column == "invoice_sk"
    assert len(table.schema_definition) == 4
    assert table.schema_definition[0]["name"] == "entry_sk"
    assert table.number.startswith("BDWT-")


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_scoped_querysets(
    tenant_a,
    tenant_b,
    lakehouse_zone_a,
    lakehouse_zone_b,
    storage_policy_a,
    storage_policy_b,
    data_mart_a,
    data_mart_b,
):
    """Verify lakehouse_zone, data_mart, and storage_policy querysets are tenant-scoped."""
    form = WarehouseTableForm(tenant=tenant_a)

    zone_qs = form.fields["lakehouse_zone"].queryset
    assert lakehouse_zone_a in zone_qs
    assert lakehouse_zone_b not in zone_qs

    mart_qs = form.fields["data_mart"].queryset
    assert data_mart_a in mart_qs
    assert data_mart_b not in mart_qs

    policy_qs = form.fields["storage_policy"].queryset
    assert storage_policy_a in policy_qs
    assert storage_policy_b not in policy_qs


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_permits_bound_inactive_fk_on_edit(
    tenant_a,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
):
    """Verify bound inactive foreign keys remain in choices during edits via Q(pk=...) filter."""
    # Deactivate the foreign keys
    lakehouse_zone_a.is_active = False
    lakehouse_zone_a.save(update_fields=["is_active"])

    storage_policy_a.is_active = False
    storage_policy_a.save(update_fields=["is_active"])

    data_mart_a.is_active = False
    data_mart_a.save(update_fields=["is_active"])

    # Create table bound to them
    table = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=storage_policy_a,
        data_mart=data_mart_a,
        name="Bound Inactive FK Table",
        table_name="fact_bound_inactive",
    )

    # In a fresh create form, inactive foreign keys must not appear
    fresh_form = WarehouseTableForm(tenant=tenant_a)
    assert lakehouse_zone_a not in fresh_form.fields["lakehouse_zone"].queryset
    assert storage_policy_a not in fresh_form.fields["storage_policy"].queryset
    assert data_mart_a not in fresh_form.fields["data_mart"].queryset

    # In the edit form of the bound instance, inactive foreign keys ARE included
    edit_form = WarehouseTableForm(instance=table, tenant=tenant_a)
    assert lakehouse_zone_a in edit_form.fields["lakehouse_zone"].queryset
    assert storage_policy_a in edit_form.fields["storage_policy"].queryset
    assert data_mart_a in edit_form.fields["data_mart"].queryset


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_sql_identifier_table_name_valid(tenant_a, lakehouse_zone_a):
    """Verify valid SQL identifiers for table_name."""
    valid_names = ["fact_orders", "_raw_staging_events", "dim_customer_2026", "a"]
    for valid_name in valid_names:
        data = _datawarehouse_base_warehouse_table_data(
            zone=lakehouse_zone_a,
            table_name=valid_name,
        )
        form = WarehouseTableForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected '{valid_name}' to be valid, got: {form.errors}"
        assert form.cleaned_data["table_name"] == valid_name.lower()


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_sql_identifier_table_name_invalid(tenant_a, lakehouse_zone_a):
    """Verify invalid SQL identifiers for table_name trigger validation errors."""
    invalid_names = [
        "123_starts_with_digit",
        "has-hyphens",
        "has.dots",
        "has spaces",
        "has$symbols",
        "a" * 64,  # exceeds 63 characters
    ]
    for invalid_name in invalid_names:
        data = _datawarehouse_base_warehouse_table_data(
            zone=lakehouse_zone_a,
            table_name=invalid_name,
        )
        form = WarehouseTableForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected '{invalid_name}' to be invalid"
        assert "table_name" in form.errors
        assert "Table name must be a valid SQL identifier" in form.errors["table_name"][0]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_sql_identifier_primary_key_column_valid_and_invalid(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify SQL identifier rules for primary_key_column."""
    # Valid
    for valid_col in ["id", "order_sk", "_pk", "pk1"]:
        data = _datawarehouse_base_warehouse_table_data(
            zone=lakehouse_zone_a,
            primary_key_column=valid_col,
        )
        form = WarehouseTableForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected valid pk '{valid_col}', got: {form.errors}"

    # Invalid
    for invalid_col in ["99_id", "col-with-hyphen", "col space", "a" * 64]:
        data = _datawarehouse_base_warehouse_table_data(
            zone=lakehouse_zone_a,
            primary_key_column=invalid_col,
        )
        form = WarehouseTableForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected invalid pk '{invalid_col}'"
        assert "primary_key_column" in form.errors
        assert "Primary key column must be a valid SQL identifier" in form.errors["primary_key_column"][0]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_duplicate_table_name_same_tenant(
    tenant_a,
    warehouse_table_a,
    lakehouse_zone_a,
):
    """Verify duplicate physical table_name within same tenant triggers error."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        table_name=warehouse_table_a.table_name,
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "table_name" in form.errors
    assert "A warehouse table with this physical table name already exists in your workspace." in form.errors["table_name"]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_duplicate_table_name_cross_tenant_allowed(
    tenant_b,
    warehouse_table_a,
    lakehouse_zone_b,
):
    """Verify duplicate physical table_name in different tenant passes validation."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_b,
        table_name=warehouse_table_a.table_name,
    )
    form = WarehouseTableForm(data=data, tenant=tenant_b)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_edit_own_table_name_allowed(tenant_a, warehouse_table_a):
    """Verify editing warehouse table retaining its current table_name is allowed."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=warehouse_table_a.lakehouse_zone,
        name="Renamed Fact Table Display",
        table_name=warehouse_table_a.table_name,
    )
    form = WarehouseTableForm(data=data, instance=warehouse_table_a, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_valid(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify comprehensive ANSI SQL types are recognized in schema definition."""
    valid_schema = [
        {"name": "sk", "type": "BIGINT", "nullable": False},
        {"name": "int_col", "type": "INTEGER", "nullable": True},
        {"name": "amount", "type": "NUMERIC(18, 4)", "nullable": False},
        {"name": "ratio", "type": "DOUBLE PRECISION", "nullable": True},
        {"name": "flag", "type": "BOOLEAN", "nullable": False},
        {"name": "code", "type": "VARCHAR(128)", "nullable": False},
        {"name": "memo", "type": "TEXT", "nullable": True},
        {"name": "txn_date", "type": "DATE", "nullable": False},
        {"name": "created_at", "type": "TIMESTAMP", "nullable": False},
        {"name": "payload", "type": "JSON", "nullable": True},
        {"name": "checksum", "type": "BYTES", "nullable": True},
    ]
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw=json.dumps(valid_schema),
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert len(form.cleaned_data["schema_definition_raw"]) == len(valid_schema)


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_empty(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify blank schema_definition_raw cleans to empty list."""
    for empty_val in ["", "   "]:
        data = _datawarehouse_base_warehouse_table_data(
            zone=lakehouse_zone_a,
            schema_definition_raw=empty_val,
        )
        form = WarehouseTableForm(data=data, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["schema_definition_raw"] == []


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_malformed_json(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify malformed JSON syntax in schema_definition_raw raises validation error."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw="[{bad_json: missing_quotes}",
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "schema_definition_raw" in form.errors
    assert "Invalid JSON format:" in form.errors["schema_definition_raw"][0]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_not_json_array(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify non-array JSON root (e.g. object) raises validation error."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw='{"name": "id", "type": "BIGINT"}',
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "schema_definition_raw" in form.errors
    assert "Schema definition must be a JSON array of column objects." in form.errors["schema_definition_raw"]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_item_missing_name_or_not_dict(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify array items that are not dicts or lack 'name' key trigger validation error."""
    # Non-dict item
    data_not_dict = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw='["column_name_as_string"]',
    )
    form_nd = WarehouseTableForm(data=data_not_dict, tenant=tenant_a)
    assert not form_nd.is_valid()
    assert "schema_definition_raw" in form_nd.errors
    assert "Each item in the schema definition must be a dictionary containing at least a 'name' key." in form_nd.errors["schema_definition_raw"]

    # Dict item missing 'name'
    data_no_name = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw='[{"type": "BIGINT"}]',
    )
    form_nn = WarehouseTableForm(data=data_no_name, tenant=tenant_a)
    assert not form_nn.is_valid()
    assert "schema_definition_raw" in form_nn.errors
    assert "Each item in the schema definition must be a dictionary containing at least a 'name' key." in form_nn.errors["schema_definition_raw"]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_invalid_column_name(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify column names must be valid SQL identifiers."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw='[{"name": "123_invalid_col", "type": "INTEGER"}]',
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "schema_definition_raw" in form.errors
    assert "Column name '123_invalid_col' must be a valid SQL identifier." in form.errors["schema_definition_raw"]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_clean_schema_definition_raw_unsupported_sql_type(
    tenant_a,
    lakehouse_zone_a,
):
    """Verify unsupported SQL data type raises validation error."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_a,
        schema_definition_raw='[{"name": "col_a", "type": "UNSUPPORTED_DATA_TYPE_XYZ"}]',
    )
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "schema_definition_raw" in form.errors
    assert "Unsupported or invalid SQL data type 'UNSUPPORTED_DATA_TYPE_XYZ'" in form.errors["schema_definition_raw"][0]


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_schema_definition_initial_display(
    tenant_a,
    warehouse_table_a,
):
    """Verify bound form populates schema_definition_raw initial value with pretty JSON."""
    form = WarehouseTableForm(instance=warehouse_table_a, tenant=tenant_a)
    initial_raw = form.fields["schema_definition_raw"].initial
    assert initial_raw is not None
    parsed = json.loads(initial_raw)
    assert parsed == warehouse_table_a.schema_definition


@pytest.mark.django_db
def test_datawarehouse_forms_warehouse_table_reject_foreign_fk_fields(
    tenant_a,
    tenant_b,
    lakehouse_zone_a,
    lakehouse_zone_b,
    storage_policy_b,
    data_mart_b,
):
    """Verify reject_foreign defense validator rejects foreign zone, mart, and policy."""
    data = _datawarehouse_base_warehouse_table_data(
        zone=lakehouse_zone_b,
        policy=storage_policy_b,
        mart=data_mart_b,
    )

    # Scoped queryset rejects at field level
    form = WarehouseTableForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lakehouse_zone" in form.errors
    assert "data_mart" in form.errors
    assert "storage_policy" in form.errors

    # reject_foreign defense validator rejects explicitly when querysets are widened
    form_wide = WarehouseTableForm(data=data, tenant=tenant_a)
    form_wide.fields["lakehouse_zone"].queryset = LakehouseZone.objects.all()
    form_wide.fields["data_mart"].queryset = DataMart.objects.all()
    form_wide.fields["storage_policy"].queryset = WarehouseStoragePolicy.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["lakehouse_zone"]
    assert "That record belongs to another workspace." in form_wide.errors["data_mart"]
    assert "That record belongs to another workspace." in form_wide.errors["storage_policy"]
