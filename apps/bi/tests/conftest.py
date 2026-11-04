"""Shared test contract fixtures for apps/bi."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bi.models import (
    BusinessGlossaryTerm,
    CalculatedMeasure,
    CdcSyncConfig,
    DataMart,
    DataQualityException,
    DataQualityProfile,
    DataQualityRule,
    DataQualityScorecard,
    DataSourceConnector,
    DrillHierarchy,
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    IngestionPipeline,
    IngestionRun,
    LakehouseZone,
    MdmGoldenRecord,
    MdmHierarchyNode,
    MdmReferenceCode,
    MdmSurvivorshipRule,
    SemanticModel,
    TransformationStep,
    WarehouseStoragePolicy,
    WarehouseTable,
)


@pytest.fixture
def admin_user_b(db, tenant_b):
    return User.objects.create_user(
        email="admin@globex.com",
        username="admin_globex",
        password="TestPass123!",
        tenant=tenant_b,
        is_tenant_admin=True,
    )


@pytest.fixture
def auth_client(client_a):
    return client_a


@pytest.fixture
def anon_client(client):
    return client


@pytest.fixture
def bi_connector(db, tenant_a, admin_user):
    return DataSourceConnector.objects.create(
        tenant=tenant_a,
        name="Acme Master ERP",
        connector_type="internal_erp",
        status="active",
        connection_config={"engine": "mysql", "host": "localhost"},
        test_status="success",
        test_message="Connection verified",
        created_by=admin_user,
    )


@pytest.fixture
def bi_pipeline(db, tenant_a, bi_connector):
    return IngestionPipeline.objects.create(
        tenant=tenant_a,
        connector=bi_connector,
        name="Acme Invoices Pipeline",
        ingestion_mode="batch_scheduled",
        source_entity="accounting_invoice",
        target_staging_table="stg_accounting_invoices",
        schedule_cadence="daily",
        cron_expression="0 2 * * *",
        file_format="none",
        status="active",
    )


@pytest.fixture
def bi_cdc_config(db, tenant_a, bi_pipeline):
    return CdcSyncConfig.objects.create(
        tenant=tenant_a,
        pipeline=bi_pipeline,
        capture_method="query_timestamp",
        sync_mode="incremental_deduped",
        primary_key_fields="id",
        cursor_field="updated_at",
        last_cursor_value="2026-11-03T12:00:00Z",
        schema_drift_policy="detect_and_warn",
        capture_deletes=True,
    )


@pytest.fixture
def bi_run(db, tenant_a, bi_pipeline):
    return IngestionRun.objects.create(
        tenant=tenant_a,
        pipeline=bi_pipeline,
        trigger_type="scheduled",
        status="completed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        duration_seconds=Decimal("1.45"),
        records_extracted=100,
        records_inserted=98,
        records_rejected=2,
        bytes_transferred=25600,
        committed_cursor="2026-11-03T12:00:00Z",
        log_summary="Test run finished successfully.",
    )


@pytest.fixture
def bi_connector_b(db, tenant_b, admin_user_b):
    return DataSourceConnector.objects.create(
        tenant=tenant_b,
        name="Globex Master ERP",
        connector_type="internal_erp",
        status="active",
        test_status="success",
        created_by=admin_user_b,
    )


@pytest.fixture
def bi_pipeline_b(db, tenant_b, bi_connector_b):
    return IngestionPipeline.objects.create(
        tenant=tenant_b,
        connector=bi_connector_b,
        name="Globex Invoices Pipeline",
        ingestion_mode="batch_scheduled",
        source_entity="accounting_invoice",
        target_staging_table="stg_accounting_invoices",
        status="active",
    )


@pytest.fixture
def bi_cdc_config_b(db, tenant_b, bi_pipeline_b):
    return CdcSyncConfig.objects.create(
        tenant=tenant_b,
        pipeline=bi_pipeline_b,
        capture_method="query_timestamp",
        sync_mode="incremental_deduped",
        primary_key_fields="id",
        cursor_field="updated_at",
    )


@pytest.fixture
def bi_run_b(db, tenant_b, bi_pipeline_b):
    return IngestionRun.objects.create(
        tenant=tenant_b,
        pipeline=bi_pipeline_b,
        trigger_type="manual",
        status="completed",
        records_extracted=50,
        records_inserted=50,
    )


# ---------------------------------------------------------------------------
# Sub-module 10.2 (ETL/ELT & Data Pipelines) Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def etl_pipeline_a(db, tenant_a, admin_user, bi_pipeline):
    return EtlPipeline.objects.create(
        tenant=tenant_a,
        name="Acme Invoices Daily Mart",
        description="Transforms raw staging invoices into fact_daily_sales mart",
        source_ingestion_pipeline=bi_pipeline,
        source_staging_table="stg_accounting_invoices",
        target_table="fact_daily_sales",
        target_layer="warehouse_fact",
        trigger_type="scheduled_cron",
        cron_expression="0 2 * * *",
        status="active",
        created_by=admin_user,
    )


@pytest.fixture
def etl_step_a(db, tenant_a, etl_pipeline_a):
    return TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        name="Join Customer Master",
        step_type="join",
        sequence=1,
        upstream_step_ids=[],
        step_config={"join_type": "inner", "left_key": "customer_id", "right_key": "id"},
        status="active",
        is_blocking=True,
    )


@pytest.fixture
def etl_version_a(db, tenant_a, admin_user, etl_pipeline_a):
    ver = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version_number="v1.0.0",
        environment="production",
        status="published",
        changelog="Initial production deployment",
        promoted_by=admin_user,
        promoted_at=timezone.now(),
    )
    etl_pipeline_a.active_version = ver
    etl_pipeline_a.save(update_fields=["active_version"])
    return ver


@pytest.fixture
def etl_run_a(db, tenant_a, etl_pipeline_a, etl_version_a):
    return EtlPipelineRun.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version=etl_version_a,
        trigger_type="scheduled",
        status="completed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        duration_seconds=Decimal("12.50"),
        records_in=1000,
        records_transformed=980,
        records_out=980,
        records_rejected=20,
        bytes_processed=1048576,
    )


@pytest.fixture
def etl_pipeline_b(db, tenant_b, admin_user_b, bi_pipeline_b):
    return EtlPipeline.objects.create(
        tenant=tenant_b,
        name="Globex Invoices Daily Mart",
        description="Globex transformation mart",
        source_ingestion_pipeline=bi_pipeline_b,
        source_staging_table="stg_accounting_invoices",
        target_table="fact_daily_sales",
        target_layer="warehouse_fact",
        trigger_type="scheduled_cron",
        cron_expression="0 3 * * *",
        status="active",
        created_by=admin_user_b,
    )


@pytest.fixture
def etl_step_b(db, tenant_b, etl_pipeline_b):
    return TransformationStep.objects.create(
        tenant=tenant_b,
        pipeline=etl_pipeline_b,
        name="Globex Customer Join",
        step_type="join",
        sequence=1,
        upstream_step_ids=[],
        step_config={"join_type": "left", "left_key": "cust_id", "right_key": "id"},
        status="active",
        is_blocking=True,
    )


@pytest.fixture
def etl_version_b(db, tenant_b, admin_user_b, etl_pipeline_b):
    ver = EtlPipelineVersion.objects.create(
        tenant=tenant_b,
        pipeline=etl_pipeline_b,
        version_number="v1.0.0",
        environment="production",
        status="published",
        changelog="Globex initial release",
        promoted_by=admin_user_b,
        promoted_at=timezone.now(),
    )
    etl_pipeline_b.active_version = ver
    etl_pipeline_b.save(update_fields=["active_version"])
    return ver


@pytest.fixture
def etl_run_b(db, tenant_b, etl_pipeline_b, etl_version_b):
    return EtlPipelineRun.objects.create(
        tenant=tenant_b,
        pipeline=etl_pipeline_b,
        version=etl_version_b,
        trigger_type="manual",
        status="completed",
        started_at=timezone.now(),
        ended_at=timezone.now(),
        duration_seconds=Decimal("5.20"),
        records_in=500,
        records_transformed=500,
        records_out=500,
        records_rejected=0,
        bytes_processed=524288,
    )


# ---------------------------------------------------------------------------
# Sub-module 10.3 (Data Warehouse & Storage) Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def lakehouse_zone_a(db, tenant_a):
    return LakehouseZone.objects.create(
        tenant=tenant_a,
        name="Gold Marts Zone",
        code="gold-marts-zone",
        zone_type="gold",
        storage_backend="internal_db",
        base_uri_path="/warehouse/gold",
        default_format="relational_table",
        is_active=True,
    )


@pytest.fixture
def storage_policy_a(db, tenant_a):
    return WarehouseStoragePolicy.objects.create(
        tenant=tenant_a,
        name="Daily Range Snappy Policy",
        partition_strategy="range_time",
        partition_granularity="day",
        compression_codec="snappy",
        vacuum_cadence="weekly",
        time_travel_days=30,
        enable_zone_maps=True,
        is_active=True,
    )


@pytest.fixture
def data_mart_a(db, tenant_a, admin_user):
    return DataMart.objects.create(
        tenant=tenant_a,
        name="Revenue Finance Mart",
        code="revenue-finance-mart",
        subject_area="finance",
        certification_status="certified",
        access_tier="department",
        refresh_cadence="daily",
        owner=admin_user,
        steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def warehouse_table_a(db, tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a):
    return WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        storage_policy=storage_policy_a,
        data_mart=data_mart_a,
        name="Daily Invoiced Revenue Fact",
        table_name="fact_daily_revenue",
        table_type="fact",
        schema_type="star",
        grain="transaction",
        primary_key_column="id",
        schema_definition=[
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "invoice_date", "type": "DATE", "nullable": False},
            {"name": "customer_id", "type": "INTEGER", "nullable": False},
            {"name": "amount", "type": "NUMERIC(14, 2)", "nullable": False},
        ],
        row_count=100000,
        compressed_bytes=10485760,
        compression_ratio=Decimal("2.80"),
        is_conformed_dimension=True,
        is_active=True,
    )


@pytest.fixture
def lakehouse_zone_b(db, tenant_b):
    return LakehouseZone.objects.create(
        tenant=tenant_b,
        name="Globex Bronze Ingestion Zone",
        code="globex-bronze-landing",
        zone_type="bronze",
        storage_backend="internal_db",
        base_uri_path="/warehouse/globex/bronze",
        default_format="relational_table",
        is_active=True,
    )


@pytest.fixture
def storage_policy_b(db, tenant_b):
    return WarehouseStoragePolicy.objects.create(
        tenant=tenant_b,
        name="Globex Monthly Policy",
        partition_strategy="range_time",
        partition_granularity="month",
        compression_codec="zstd",
        vacuum_cadence="monthly",
        time_travel_days=14,
        is_active=True,
    )


@pytest.fixture
def data_mart_b(db, tenant_b, admin_user_b):
    return DataMart.objects.create(
        tenant=tenant_b,
        name="Globex Sales Mart",
        code="globex-sales-mart",
        subject_area="sales",
        certification_status="certified",
        access_tier="department",
        owner=admin_user_b,
        steward=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def warehouse_table_b(db, tenant_b, lakehouse_zone_b, storage_policy_b, data_mart_b):
    return WarehouseTable.objects.create(
        tenant=tenant_b,
        lakehouse_zone=lakehouse_zone_b,
        storage_policy=storage_policy_b,
        data_mart=data_mart_b,
        name="Globex Orders Fact",
        table_name="fact_globex_orders",
        table_type="fact",
        schema_type="star",
        grain="transaction",
        primary_key_column="id",
        schema_definition=[
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "order_date", "type": "DATE", "nullable": False},
        ],
        row_count=50000,
        compressed_bytes=5242880,
        compression_ratio=Decimal("2.50"),
        is_active=True,
    )


# ---------------------------------------------------------------------------
# 10.4 Semantic Layer Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def semantic_model_a(db, tenant_a, warehouse_table, data_mart, admin_user):
    return SemanticModel.objects.create(
        tenant=tenant_a,
        warehouse_table=warehouse_table,
        data_mart=data_mart,
        name="Acme Sales Performance Analytics",
        code="acme_sales_perf",
        model_type="fact",
        primary_key_column="id",
        grain_description="One row per line item",
        access_tier="department",
        certification_status="certified",
        certified_by=admin_user,
        certified_at=timezone.now(),
        owner=admin_user,
        is_active=True,
    )


@pytest.fixture
def glossary_term_a(db, tenant_a, admin_user):
    return BusinessGlossaryTerm.objects.create(
        tenant=tenant_a,
        name="Net Recurring Revenue",
        code="net_recurring_revenue",
        domain_category="finance",
        short_definition="Standard corporate NRR calculation",
        full_definition="Percentage of recurring revenue retained from existing customers.",
        calculation_rule="(Ending ARR - Contraction - Churn + Expansion) / Starting ARR",
        steward=admin_user,
        certification_status="certified",
        certified_by=admin_user,
        certified_at=timezone.now(),
        is_active=True,
    )


@pytest.fixture
def calculated_measure_a(db, tenant_a, semantic_model_a, glossary_term_a):
    return CalculatedMeasure.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        glossary_term=glossary_term_a,
        name="Total Sales Revenue",
        code="total_sales_revenue",
        aggregation_type="sum",
        source_column="amount",
        time_intelligence="none",
        format_string="currency",
        display_units="auto",
        target_value=Decimal("1000000.00"),
        warning_threshold=Decimal("750000.00"),
        critical_threshold=Decimal("500000.00"),
        is_active=True,
    )


@pytest.fixture
def drill_hierarchy_a(db, tenant_a, semantic_model_a):
    return DrillHierarchy.objects.create(
        tenant=tenant_a,
        semantic_model=semantic_model_a,
        name="Fiscal Time Drill",
        code="fiscal_time_drill",
        hierarchy_type="time",
        levels_json=[
            {"level": 1, "name": "Fiscal Year", "column": "fiscal_year"},
            {"level": 2, "name": "Fiscal Quarter", "column": "fiscal_quarter"},
            {"level": 3, "name": "Fiscal Month", "column": "fiscal_month"},
        ],
        primary_drill_path=True,
        is_active=True,
    )


@pytest.fixture
def semantic_model_b(db, tenant_b, warehouse_table_b, data_mart_b, admin_user_b):
    return SemanticModel.objects.create(
        tenant=tenant_b,
        warehouse_table=warehouse_table_b,
        data_mart=data_mart_b,
        name="Globex Commercial Model",
        code="globex_commercial_model",
        model_type="fact",
        primary_key_column="id",
        access_tier="restricted",
        certification_status="draft",
        owner=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def glossary_term_b(db, tenant_b, admin_user_b):
    return BusinessGlossaryTerm.objects.create(
        tenant=tenant_b,
        name="Globex Customer Churn Rate",
        code="globex_customer_churn",
        domain_category="sales",
        short_definition="Globex Churn percentage formula",
        steward=admin_user_b,
        certification_status="draft",
        is_active=True,
    )


@pytest.fixture
def calculated_measure_b(db, tenant_b, semantic_model_b, glossary_term_b):
    return CalculatedMeasure.objects.create(
        tenant=tenant_b,
        semantic_model=semantic_model_b,
        glossary_term=glossary_term_b,
        name="Globex Order Total",
        code="globex_order_total",
        aggregation_type="sum",
        source_column="order_total",
        is_active=True,
    )


@pytest.fixture
def drill_hierarchy_b(db, tenant_b, semantic_model_b):
    return DrillHierarchy.objects.create(
        tenant=tenant_b,
        semantic_model=semantic_model_b,
        name="Globex Territory Hierarchy",
        code="globex_territory_hierarchy",
        hierarchy_type="geography",
        levels_json=[
            {"level": 1, "name": "Region", "column": "region"},
            {"level": 2, "name": "Country", "column": "country"},
        ],
        primary_drill_path=True,
        is_active=True,
    )


@pytest.fixture
def warehouse_table(warehouse_table_a):
    return warehouse_table_a


@pytest.fixture
def data_mart(data_mart_a):
    return data_mart_a


@pytest.fixture
def dq_profile_a(db, tenant_a, warehouse_table_a, admin_user):
    return DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Acme Invoice Profile",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        status="completed",
        total_row_count=1500,
        completeness_score=Decimal("99.40"),
        validity_score=Decimal("98.70"),
        uniqueness_score=Decimal("100.00"),
        profiled_by=admin_user,
        profiled_at=timezone.now(),
    )


@pytest.fixture
def dq_rule_a(db, tenant_a, warehouse_table_a, admin_user):
    return DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Invoice Amount Must Be Positive",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        target_column="total_amount",
        dimension="validity",
        rule_type="range_between",
        parameters_json={"min_val": 0.01},
        severity="critical",
        failure_tolerance_pct=Decimal("0.00"),
        last_status="passed",
        pass_rate_pct=Decimal("100.00"),
        steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def dq_exception_a(db, tenant_a, dq_profile_a, dq_rule_a, warehouse_table_a, admin_user):
    return DataQualityException.objects.create(
        tenant=tenant_a,
        profile=dq_profile_a,
        rule=dq_rule_a,
        warehouse_table=warehouse_table_a,
        target_column="total_amount",
        record_identifier="INV-2026-9999",
        exception_type="range_outlier",
        invalid_value="-45.00",
        expected_condition="amount > 0",
        severity="critical",
        status="open",
        remediation_action="manual_edit",
        assigned_steward=admin_user,
    )


@pytest.fixture
def dq_scorecard_a(db, tenant_a, warehouse_table_a, admin_user):
    return DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Core Financials Data Trust",
        code="core_fin_dti",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        evaluation_period="monthly",
        target_quality_score=Decimal("95.00"),
        overall_quality_score=Decimal("98.50"),
        grade="A",
        health_status="healthy",
        meets_sla=True,
        steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def dq_profile_b(db, tenant_b, warehouse_table_b, admin_user_b):
    return DataQualityProfile.objects.create(
        tenant=tenant_b,
        name="Globex Customer Profile",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_b,
        status="completed",
        total_row_count=500,
        completeness_score=Decimal("95.00"),
        validity_score=Decimal("92.00"),
        uniqueness_score=Decimal("90.00"),
        profiled_by=admin_user_b,
        profiled_at=timezone.now(),
    )


@pytest.fixture
def dq_rule_b(db, tenant_b, warehouse_table_b, admin_user_b):
    return DataQualityRule.objects.create(
        tenant=tenant_b,
        name="Globex Customer Email Not Null",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_b,
        target_column="email",
        dimension="completeness",
        rule_type="not_null",
        parameters_json={},
        severity="warning",
        failure_tolerance_pct=Decimal("5.00"),
        last_status="passed",
        pass_rate_pct=Decimal("98.00"),
        steward=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def dq_exception_b(db, tenant_b, dq_profile_b, dq_rule_b, warehouse_table_b, admin_user_b):
    return DataQualityException.objects.create(
        tenant=tenant_b,
        profile=dq_profile_b,
        rule=dq_rule_b,
        warehouse_table=warehouse_table_b,
        target_column="email",
        record_identifier="CUST-GLOBEX-101",
        exception_type="null_anomaly",
        invalid_value="NULL",
        expected_condition="email IS NOT NULL",
        severity="warning",
        status="open",
        remediation_action="impute_value",
        assigned_steward=admin_user_b,
    )


@pytest.fixture
def dq_scorecard_b(db, tenant_b, warehouse_table_b, admin_user_b):
    return DataQualityScorecard.objects.create(
        tenant=tenant_b,
        name="Globex Operations Scorecard",
        code="globex_ops_scorecard",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_b,
        evaluation_period="weekly",
        target_quality_score=Decimal("90.00"),
        overall_quality_score=Decimal("88.00"),
        grade="B",
        health_status="needs_attention",
        meets_sla=False,
        steward=admin_user_b,
        is_active=True,
    )

# ---------------------------------------------------------------------------
# 10.6 Master Data Management Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mdm_golden_record_a(db, tenant_a, admin_user):
    return MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-00001",
        name="Acme Prime Corp",
        domain="customer",
        trust_tier="gold",
        confidence_score=Decimal("98.50"),
        status="approved",
        assigned_steward=admin_user,
        source_record_count=1,
        source_crosswalks_json=[{"system": "CRM", "id": "101"}],
        golden_attributes_json={"tier": "VIP"},
    )


@pytest.fixture
def mdm_golden_record_secondary_a(db, tenant_a, admin_user):
    return MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-00002",
        name="Acme Subsidiary Corp",
        domain="customer",
        trust_tier="silver",
        confidence_score=Decimal("85.00"),
        status="pending_review",
        assigned_steward=admin_user,
        source_record_count=1,
        source_crosswalks_json=[{"system": "ERP", "id": "202"}],
        golden_attributes_json={"tier": "Standard"},
    )


@pytest.fixture
def mdm_golden_record_b(db, tenant_b, admin_user_b):
    return MdmGoldenRecord.objects.create(
        tenant=tenant_b,
        number="BMGR-00003",
        name="Globex Heavy Industries",
        domain="customer",
        trust_tier="silver",
        confidence_score=Decimal("89.00"),
        status="approved",
        assigned_steward=admin_user_b,
        source_record_count=1,
        source_crosswalks_json=[{"system": "CRM", "id": "GLB-101"}],
        golden_attributes_json={"industry": "Manufacturing"},
    )


@pytest.fixture
def mdm_survivorship_rule_a(db, tenant_a, admin_user):
    return MdmSurvivorshipRule.objects.create(
        tenant=tenant_a,
        number="BMSR-00001",
        name="Acme Customer Survivorship Rule",
        domain="customer",
        survivorship_strategy="source_priority",
        source_precedence_list=["CRM", "ERP", "BILLING"],
        match_algorithm="exact",
        match_threshold_pct=Decimal("80.00"),
        auto_merge_threshold_pct=Decimal("95.00"),
        steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def mdm_survivorship_rule_b(db, tenant_b, admin_user_b):
    return MdmSurvivorshipRule.objects.create(
        tenant=tenant_b,
        number="BMSR-00002",
        name="Globex Vendor Survivorship Rule",
        domain="vendor",
        survivorship_strategy="most_recent",
        source_precedence_list=["PROCUREMENT"],
        match_algorithm="fuzzy_token",
        match_threshold_pct=Decimal("85.00"),
        auto_merge_threshold_pct=Decimal("95.00"),
        steward=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def mdm_hierarchy_node_root_a(db, tenant_a):
    return MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        number="BMHR-00001",
        name="Acme Global Enterprise",
        code="acme_global",
        hierarchy_type="corporate_legal",
        node_type="holding_company",
        parent=None,
        level=0,
        sort_order=10,
        is_active=True,
    )


@pytest.fixture
def mdm_hierarchy_node_child_a(db, tenant_a, mdm_hierarchy_node_root_a, mdm_golden_record_a):
    return MdmHierarchyNode.objects.create(
        tenant=tenant_a,
        number="BMHR-00002",
        name="Acme North America LLC",
        code="acme_na",
        hierarchy_type="corporate_legal",
        node_type="subsidiary",
        parent=mdm_hierarchy_node_root_a,
        golden_record=mdm_golden_record_a,
        level=1,
        sort_order=20,
        is_active=True,
    )


@pytest.fixture
def mdm_hierarchy_node_b(db, tenant_b):
    return MdmHierarchyNode.objects.create(
        tenant=tenant_b,
        number="BMHR-00003",
        name="Globex International Corp",
        code="globex_intl",
        hierarchy_type="corporate_legal",
        node_type="holding_company",
        parent=None,
        level=0,
        sort_order=10,
        is_active=True,
    )


@pytest.fixture
def mdm_reference_code_a(db, tenant_a):
    return MdmReferenceCode.objects.create(
        tenant=tenant_a,
        number="BMRD-00001",
        code_set="ISO-4217-CURRENCY",
        source_system="SAP",
        source_code="USD",
        canonical_code="USD",
        canonical_name="United States Dollar",
        status="active",
        is_standard=True,
    )


@pytest.fixture
def mdm_reference_code_b(db, tenant_b):
    return MdmReferenceCode.objects.create(
        tenant=tenant_b,
        number="BMRD-00002",
        code_set="ISO-4217-CURRENCY",
        source_system="ORACLE",
        source_code="EUR",
        canonical_code="EUR",
        canonical_name="Euro",
        status="active",
        is_standard=True,
    )

