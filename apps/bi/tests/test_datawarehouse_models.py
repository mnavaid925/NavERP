"""Unit tests for Sub-module 10.3 models (DataMart, LakehouseZone, WarehouseStoragePolicy, WarehouseTable)."""
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from apps.bi.models import (
    DataMart,
    LakehouseZone,
    WarehouseStoragePolicy,
    WarehouseTable,
)


def _datawarehouse_extract_choice_keys(choices_list):
    """Helper to extract keys from Django choices tuple/list."""
    return [c[0] for c in choices_list]


# ---------------------------------------------------------------------------
# 1. DataMart Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datawarehouse_models_datamart_creation_and_prefix(tenant_a, admin_user):
    """Test DataMart creation, BDMT prefix, str format, and default values."""
    mart = DataMart.objects.create(
        tenant=tenant_a,
        name="Finance General Ledger Mart",
        code="finance-gl-mart",
        owner=admin_user,
    )
    assert mart.number.startswith("BDMT-")
    assert str(mart) == f"{mart.name} ({mart.number})"
    assert mart.subject_area == "finance"
    assert mart.access_tier == "department"
    assert mart.certification_status == "draft"
    assert mart.refresh_cadence == "daily"
    assert mart.is_active is True
    assert mart.description == ""
    assert mart.org_unit is None
    assert mart.steward is None
    assert mart.created_at is not None
    assert mart.updated_at is not None


@pytest.mark.django_db
def test_datawarehouse_models_datamart_choices_contract():
    """Verify DataMart choice constants match frozen specification."""
    subject_keys = _datawarehouse_extract_choice_keys(DataMart.SUBJECT_AREA_CHOICES)
    assert subject_keys == [
        "finance",
        "sales",
        "hr",
        "supply_chain",
        "procurement",
        "manufacturing",
        "executive",
    ]

    tier_keys = _datawarehouse_extract_choice_keys(DataMart.ACCESS_TIER_CHOICES)
    assert tier_keys == ["public", "department", "restricted"]

    cert_keys = _datawarehouse_extract_choice_keys(DataMart.CERTIFICATION_STATUS_CHOICES)
    assert cert_keys == ["draft", "in_review", "certified", "deprecated"]

    cadence_keys = _datawarehouse_extract_choice_keys(DataMart.REFRESH_CADENCE_CHOICES)
    assert cadence_keys == ["real_time", "hourly", "daily", "weekly", "on_demand"]


@pytest.mark.django_db
def test_datawarehouse_models_datamart_meta_indexes_and_constraints():
    """Verify DataMart meta table name, ordering, indexes, and constraints."""
    meta = DataMart._meta
    assert meta.db_table == "bi_data_mart"
    assert meta.ordering == ["name"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_bdmt_ten_name" in index_names
    assert "idx_bdmt_ten_subj" in index_names
    assert "idx_bdmt_ten_cert" in index_names
    assert "idx_bdmt_ten_active" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_bdmt_tenant_code_uniq" in constraint_names
    assert "bi_bdmt_tenant_num_uniq" in constraint_names


@pytest.mark.django_db
def test_datawarehouse_models_datamart_tenant_isolation_and_uniqueness(tenant_a, tenant_b):
    """Verify unique constraint on code per tenant, and tenant isolation."""
    mart1 = DataMart.objects.create(
        tenant=tenant_a,
        name="Sales Analytics",
        code="sales-analytics",
    )
    # Duplicate code within tenant_a must fail
    with pytest.raises(IntegrityError):
        DataMart.objects.create(
            tenant=tenant_a,
            name="Another Sales Analytics",
            code="sales-analytics",
        )

    # Same code in tenant_b must succeed
    mart_b = DataMart.objects.create(
        tenant=tenant_b,
        name="Globex Sales Analytics",
        code="sales-analytics",
    )
    assert mart_b.pk != mart1.pk
    assert mart_b.number.startswith("BDMT-")
    assert mart_b.tenant == tenant_b


# ---------------------------------------------------------------------------
# 2. LakehouseZone Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datawarehouse_models_lakehouse_zone_creation_and_prefix(tenant_a):
    """Test LakehouseZone creation, BLHZ prefix, str format, and defaults."""
    zone = LakehouseZone.objects.create(
        tenant=tenant_a,
        name="Silver Curated Zone",
        code="silver-curated",
        zone_type="silver",
        storage_backend="aws_s3",
        base_uri_path="s3://acme-lakehouse/silver/",
    )
    assert zone.number.startswith("BLHZ-")
    assert str(zone) == f"{zone.name} ({zone.number})"
    assert zone.zone_type == "silver"
    assert zone.storage_backend == "aws_s3"
    assert zone.default_format == "relational_table"
    assert zone.is_read_only is False
    assert zone.is_active is True
    assert zone.description == ""
    assert zone.created_at is not None
    assert zone.updated_at is not None


@pytest.mark.django_db
def test_datawarehouse_models_lakehouse_zone_choices_contract():
    """Verify LakehouseZone choice constants match frozen specification."""
    zone_keys = _datawarehouse_extract_choice_keys(LakehouseZone.ZONE_TYPE_CHOICES)
    assert zone_keys == ["bronze", "silver", "gold", "sandbox"]

    backend_keys = _datawarehouse_extract_choice_keys(LakehouseZone.STORAGE_BACKEND_CHOICES)
    assert backend_keys == ["internal_db", "aws_s3", "azure_blob", "gcs", "local_filesystem"]

    format_keys = _datawarehouse_extract_choice_keys(LakehouseZone.DEFAULT_FORMAT_CHOICES)
    assert format_keys == ["relational_table", "parquet", "delta_lake", "iceberg", "csv_compressed"]


@pytest.mark.django_db
def test_datawarehouse_models_lakehouse_zone_meta_indexes_and_constraints():
    """Verify LakehouseZone meta table name, ordering, indexes, and constraints."""
    meta = LakehouseZone._meta
    assert meta.db_table == "bi_lakehouse_zone"
    assert meta.ordering == ["zone_type", "name"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_blhz_ten_zone" in index_names
    assert "idx_blhz_ten_backend" in index_names
    assert "idx_blhz_ten_active" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_blhz_tenant_code_uniq" in constraint_names
    assert "bi_blhz_tenant_num_uniq" in constraint_names


@pytest.mark.django_db
def test_datawarehouse_models_lakehouse_zone_tenant_isolation_and_uniqueness(tenant_a, tenant_b):
    """Verify LakehouseZone unique constraints and tenant isolation."""
    z1 = LakehouseZone.objects.create(
        tenant=tenant_a,
        name="Bronze Ingestion Landing",
        code="bronze-landing",
        zone_type="bronze",
    )
    with pytest.raises(IntegrityError):
        LakehouseZone.objects.create(
            tenant=tenant_a,
            name="Another Bronze",
            code="bronze-landing",
            zone_type="bronze",
        )

    # Same code in tenant_b succeeds
    z_b = LakehouseZone.objects.create(
        tenant=tenant_b,
        name="Bronze Ingestion Landing",
        code="bronze-landing",
        zone_type="bronze",
    )
    assert z_b.pk != z1.pk
    assert z_b.tenant == tenant_b


# ---------------------------------------------------------------------------
# 3. WarehouseStoragePolicy Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datawarehouse_models_storage_policy_creation_and_prefix(tenant_a):
    """Test WarehouseStoragePolicy creation, BWSP prefix, str format, and defaults."""
    policy = WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="Quarterly Hash Compression Policy",
    )
    assert policy.number.startswith("BWSP-")
    assert str(policy) == f"{policy.name} ({policy.number})"
    assert policy.partition_strategy == "range_time"
    assert policy.partition_key == ""
    assert policy.partition_granularity == "month"
    assert policy.compression_codec == "zstd"
    assert policy.enable_zone_maps is True
    assert policy.hot_tier_days == 90
    assert policy.warm_tier_days == 365
    assert policy.cold_tier_days == 2555
    assert policy.time_travel_days == 7
    assert policy.auto_purge_enabled is False
    assert policy.vacuum_cadence == "weekly"
    assert policy.is_default is False
    assert policy.is_active is True
    assert policy.description == ""


@pytest.mark.django_db
def test_datawarehouse_models_storage_policy_choices_contract():
    """Verify WarehouseStoragePolicy choice constants match frozen specification."""
    strategy_keys = _datawarehouse_extract_choice_keys(WarehouseStoragePolicy.PARTITION_STRATEGY_CHOICES)
    assert strategy_keys == ["none", "range_time", "range_numeric", "hash", "list_category"]

    granularity_keys = _datawarehouse_extract_choice_keys(WarehouseStoragePolicy.PARTITION_GRANULARITY_CHOICES)
    assert granularity_keys == ["hour", "day", "month", "quarter", "year"]

    codec_keys = _datawarehouse_extract_choice_keys(WarehouseStoragePolicy.COMPRESSION_CODEC_CHOICES)
    assert codec_keys == ["none", "snappy", "zstd", "lz4", "gzip"]

    vacuum_keys = _datawarehouse_extract_choice_keys(WarehouseStoragePolicy.VACUUM_CADENCE_CHOICES)
    assert vacuum_keys == ["daily", "weekly", "monthly", "manual"]


@pytest.mark.django_db
def test_datawarehouse_models_storage_policy_meta_indexes_and_constraints():
    """Verify WarehouseStoragePolicy meta table name, ordering, indexes, and constraints."""
    meta = WarehouseStoragePolicy._meta
    assert meta.db_table == "bi_warehouse_storage_policy"
    assert meta.ordering == ["name"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_bwsp_ten_name" in index_names
    assert "idx_bwsp_ten_part" in index_names
    assert "idx_bwsp_ten_def" in index_names
    assert "idx_bwsp_ten_active" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_bwsp_tenant_num_uniq" in constraint_names


@pytest.mark.django_db
def test_datawarehouse_models_storage_policy_tenant_isolation(tenant_a, tenant_b):
    """Verify policy isolation across tenants and distinct generated numbers."""
    p_a = WarehouseStoragePolicy.objects.create(tenant=tenant_a, name="Policy A")
    p_b = WarehouseStoragePolicy.objects.create(tenant=tenant_b, name="Policy B")

    assert p_a.number.startswith("BWSP-")
    assert p_b.number.startswith("BWSP-")
    assert p_a.tenant != p_b.tenant
    assert WarehouseStoragePolicy.objects.filter(tenant=tenant_a).filter(pk=p_b.pk).exists() is False


# ---------------------------------------------------------------------------
# 4. WarehouseTable Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datawarehouse_models_warehouse_table_creation_and_prefix(
    tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a
):
    """Test WarehouseTable creation, BDWT prefix, str format, and defaults."""
    table = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=storage_policy_a,
        data_mart=data_mart_a,
        name="Monthly Cost Aggregates",
        table_name="agg_monthly_costs",
    )
    assert table.number.startswith("BDWT-")
    assert str(table) == f"{table.name} ({table.table_name})"
    assert table.table_type == "fact"
    assert table.schema_type == "star"
    assert table.grain == "transaction"
    assert table.primary_key_column == "id"
    assert table.natural_key_column == ""
    assert table.is_conformed_dimension is False
    assert table.schema_definition == []
    assert table.row_count == 0
    assert table.compressed_bytes == 0
    assert table.compression_ratio == Decimal("1.00")
    assert table.last_analyzed_at is None
    assert table.is_active is True
    assert table.description == ""


@pytest.mark.django_db
def test_datawarehouse_models_warehouse_table_choices_contract():
    """Verify WarehouseTable choice constants match frozen specification."""
    type_keys = _datawarehouse_extract_choice_keys(WarehouseTable.TABLE_TYPE_CHOICES)
    assert type_keys == ["fact", "dimension", "aggregate", "bridge", "staging"]

    schema_keys = _datawarehouse_extract_choice_keys(WarehouseTable.SCHEMA_TYPE_CHOICES)
    assert schema_keys == ["star", "snowflake", "flat", "medallion"]

    grain_keys = _datawarehouse_extract_choice_keys(WarehouseTable.GRAIN_CHOICES)
    assert grain_keys == [
        "transaction",
        "daily_snapshot",
        "monthly_snapshot",
        "accumulating_snapshot",
        "entity_state",
    ]


@pytest.mark.django_db
def test_datawarehouse_models_warehouse_table_meta_indexes_and_constraints():
    """Verify WarehouseTable meta table name, ordering, indexes, and constraints."""
    meta = WarehouseTable._meta
    assert meta.db_table == "bi_warehouse_table"
    assert meta.ordering == ["table_type", "table_name"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_bdwt_ten_type" in index_names
    assert "idx_bdwt_ten_zone" in index_names
    assert "idx_bdwt_ten_mart" in index_names
    assert "idx_bdwt_ten_policy" in index_names
    assert "idx_bdwt_ten_active" in index_names
    assert "idx_bdwt_ten_created" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_bdwt_tenant_tbl_uniq" in constraint_names
    assert "bi_bdwt_tenant_num_uniq" in constraint_names


@pytest.mark.django_db
def test_datawarehouse_models_warehouse_table_relationships_and_protect(
    tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a, warehouse_table_a
):
    """Verify FK relationships, reverse accessors, and PROTECT deletion integrity."""
    assert warehouse_table_a.lakehouse_zone == lakehouse_zone_a
    assert warehouse_table_a.storage_policy == storage_policy_a
    assert warehouse_table_a.data_mart == data_mart_a

    # Reverse relationships
    assert lakehouse_zone_a.tables.filter(pk=warehouse_table_a.pk).exists()
    assert storage_policy_a.tables.filter(pk=warehouse_table_a.pk).exists()
    assert data_mart_a.tables.filter(pk=warehouse_table_a.pk).exists()

    # LakehouseZone deletion must raise ProtectedError because on_delete=models.PROTECT
    with pytest.raises(ProtectedError):
        lakehouse_zone_a.delete()

    # DataMart deletion sets FK to null because on_delete=models.SET_NULL
    data_mart_a.delete()
    warehouse_table_a.refresh_from_db()
    assert warehouse_table_a.data_mart is None

    # WarehouseStoragePolicy deletion sets FK to null
    storage_policy_a.delete()
    warehouse_table_a.refresh_from_db()
    assert warehouse_table_a.storage_policy is None


@pytest.mark.django_db
def test_datawarehouse_models_warehouse_table_tenant_isolation_and_uniqueness(
    tenant_a, tenant_b, lakehouse_zone_a, lakehouse_zone_b
):
    """Verify table_name unique constraint per tenant and multi-tenant isolation."""
    tbl_a = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        name="GL Journals",
        table_name="fact_gl_journals",
    )

    # Duplicate table_name in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        WarehouseTable.objects.create(
            tenant=tenant_a,
            lakehouse_zone=lakehouse_zone_a,
            name="GL Journals Duplicate",
            table_name="fact_gl_journals",
        )

    # Same table_name in tenant_b must succeed
    tbl_b = WarehouseTable.objects.create(
        tenant=tenant_b,
        lakehouse_zone=lakehouse_zone_b,
        name="Globex GL Journals",
        table_name="fact_gl_journals",
    )
    assert tbl_b.pk != tbl_a.pk
    assert tbl_b.tenant == tenant_b


@pytest.mark.django_db
def test_datawarehouse_models_warehouse_table_ddl_generation_partition_strategies(tenant_a, lakehouse_zone_a):
    """Verify generate_ddl_sql() across partition strategies (RANGE, HASH, LIST, and unpartitioned)."""
    columns = [
        {"name": "id", "type": "BIGINT", "nullable": False},
        {"name": "event_date", "type": "DATE", "nullable": False},
        {"name": "customer_id", "type": "INTEGER", "nullable": False},
        {"name": "region_code", "type": "VARCHAR(10)", "nullable": True},
        {"name": "revenue_amount", "type": "NUMERIC(12, 2)", "nullable": False},
    ]

    # 1. RANGE partition strategy (time-based)
    policy_range = WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="Range Time Policy",
        partition_strategy="range_time",
        partition_key="event_date",
    )
    table_range = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=policy_range,
        name="Events Fact",
        table_name="fact_events_range",
        primary_key_column="id",
        schema_definition=columns,
    )
    ddl_range = table_range.generate_ddl_sql()
    assert "-- Table: fact_events_range" in ddl_range
    assert "CREATE TABLE IF NOT EXISTS fact_events_range (" in ddl_range
    assert "    id BIGINT PRIMARY KEY," in ddl_range
    assert "    event_date DATE NOT NULL," in ddl_range
    assert "    customer_id INTEGER NOT NULL," in ddl_range
    assert "    region_code VARCHAR(10)," in ddl_range
    assert "    revenue_amount NUMERIC(12, 2) NOT NULL" in ddl_range
    assert "PARTITION BY RANGE (event_date);" in ddl_range

    # 2. HASH partition strategy
    policy_hash = WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="Hash Policy",
        partition_strategy="hash",
        partition_key="customer_id",
    )
    table_hash = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=policy_hash,
        name="Events Hash Fact",
        table_name="fact_events_hash",
        primary_key_column="id",
        schema_definition=columns,
    )
    ddl_hash = table_hash.generate_ddl_sql()
    assert "PARTITION BY HASH (customer_id);" in ddl_hash

    # 3. LIST partition strategy (categorical)
    policy_list = WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="List Policy",
        partition_strategy="list_category",
        partition_key="region_code",
    )
    table_list = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=policy_list,
        name="Events List Fact",
        table_name="fact_events_list",
        primary_key_column="id",
        schema_definition=columns,
    )
    ddl_list = table_list.generate_ddl_sql()
    assert "PARTITION BY LIST (region_code);" in ddl_list

    # 4. Unpartitioned flat table (no storage policy, or partition_strategy == 'none')
    table_nopart = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=None,
        name="Events Flat Fact",
        table_name="fact_events_flat",
        primary_key_column="id",
        schema_definition=columns,
    )
    ddl_nopart = table_nopart.generate_ddl_sql()
    assert "PARTITION BY" not in ddl_nopart
    assert ddl_nopart.endswith(");")

    # 5. Fallback when schema_definition is empty
    table_empty = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        name="Empty Schema Table",
        table_name="fact_empty",
        primary_key_column="id",
        schema_definition=[],
    )
    ddl_empty = table_empty.generate_ddl_sql()
    assert "    id BIGINT PRIMARY KEY" in ddl_empty
    assert ddl_empty.endswith(");")
