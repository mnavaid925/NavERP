"""Shared test contract fixtures for apps/bi."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.bi.models import (
    AdHocCalculatedField,
    AdHocQuery,
    BiDashboard,
    BiDashboardBookmark,
    BiDashboardFilter,
    BiDashboardWidget,
    BusinessGlossaryTerm,
    CalculatedMeasure,
    CatalogAsset,
    CatalogLineageEdge,
    CatalogTrustEndorsement,
    CdcSyncConfig,
    DataGovernancePolicy,
    DataMart,
    DataQualityException,
    DataQualityProfile,
    DataQualityRule,
    DataQualityScorecard,
    DataSourceConnector,
    DataBlendDefinition,
    DrillHierarchy,
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    IngestionPipeline,
    IngestionRun,
    KpiDefinition,
    LakehouseZone,
    MdmGoldenRecord,
    MdmHierarchyNode,
    MdmReferenceCode,
    MdmSurvivorshipRule,
    OlapCube,
    PerformanceScorecard,
    PivotAnalysisView,
    ReportDefinition,
    ReportDrillPath,
    ReportExecution,
    ReportParameter,
    SavedAnalysisView,
    ScenarioWritebackCell,
    ScorecardKpiAssignment,
    SemanticModel,
    StrategicObjective,
    TransformationStep,
    WarehouseStoragePolicy,
    WarehouseTable,
    ForecastExecution,
    OptimizationScenario,
    PredictiveModel,
    StatisticalAnomaly,
    WhatIfScenario,
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


# --------------------------------------------------------------------------
# 10.7 Data Catalog, Lineage & Governance Fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def data_governance_policy_a(db, tenant_a, admin_user):
    return DataGovernancePolicy.objects.create(
        tenant=tenant_a,
        number="BGOV-00001",
        name="Acme Enterprise Data Retention Policy",
        code="acme_retention_policy",
        policy_type="data_retention",
        regulatory_framework="gdpr_eu",
        enforcement_level="strict_blocking",
        retention_period_days=1095,
        policy_owner=admin_user,
        effective_date="2026-01-01",
        is_active=True,
    )


@pytest.fixture
def data_governance_policy_b(db, tenant_b, admin_user_b):
    return DataGovernancePolicy.objects.create(
        tenant=tenant_b,
        number="BGOV-00002",
        name="Globex Financial Audit Policy",
        code="globex_audit_policy",
        policy_type="regulatory_compliance",
        regulatory_framework="sox",
        enforcement_level="strict_blocking",
        retention_period_days=2555,
        policy_owner=admin_user_b,
        effective_date="2026-01-01",
        is_active=True,
    )


@pytest.fixture
def catalog_asset_src_a(db, tenant_a, admin_user):
    return CatalogAsset.objects.create(
        tenant=tenant_a,
        number="BCAT-00001",
        name="Acme Ingestion Source Ledger",
        code="acme_src_ledger",
        domain="finance",
        asset_type="source_dataset",
        data_sensitivity="restricted_pii",
        enterprise_tier="tier_1_mission_critical",
        certification_status="certified",
        data_steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def catalog_asset_tgt_a(db, tenant_a, admin_user):
    return CatalogAsset.objects.create(
        tenant=tenant_a,
        number="BCAT-00002",
        name="Acme Sales Analytics Mart",
        code="acme_sales_mart",
        domain="sales",
        asset_type="warehouse_table",
        data_sensitivity="internal",
        enterprise_tier="tier_1_mission_critical",
        certification_status="certified",
        data_steward=admin_user,
        is_active=True,
    )


@pytest.fixture
def catalog_asset_b(db, tenant_b, admin_user_b):
    return CatalogAsset.objects.create(
        tenant=tenant_b,
        number="BCAT-00003",
        name="Globex Confidential Customer DB",
        code="globex_confidential_db",
        domain="customer",
        asset_type="source_dataset",
        data_sensitivity="highly_sensitive_pci_phi",
        enterprise_tier="tier_1_mission_critical",
        certification_status="certified",
        data_steward=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def catalog_lineage_edge_a(db, tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    return CatalogLineageEdge.objects.create(
        tenant=tenant_a,
        number="BLIN-00001",
        upstream_asset=catalog_asset_src_a,
        downstream_asset=catalog_asset_tgt_a,
        lineage_type="table_level",
        impact_criticality="critical",
        is_active=True,
    )


@pytest.fixture
def catalog_lineage_edge_b(db, tenant_b, catalog_asset_b):
    target_b = CatalogAsset.objects.create(
        tenant=tenant_b,
        number="BCAT-00004",
        name="Globex Target Vault",
        code="globex_target_vault",
        domain="customer",
        asset_type="warehouse_table",
        data_sensitivity="internal",
        is_active=True,
    )
    return CatalogLineageEdge.objects.create(
        tenant=tenant_b,
        number="BLIN-00002",
        upstream_asset=catalog_asset_b,
        downstream_asset=target_b,
        lineage_type="table_level",
        impact_criticality="critical",
        is_active=True,
    )


@pytest.fixture
def catalog_trust_endorsement_a(db, tenant_a, catalog_asset_tgt_a, admin_user):
    return CatalogTrustEndorsement.objects.create(
        tenant=tenant_a,
        number="BTRU-00001",
        asset=catalog_asset_tgt_a,
        endorsement_type="formal_certification",
        verdict="approved_certified",
        rating_value=5,
        attested_by=admin_user,
        is_active=True,
    )


@pytest.fixture
def catalog_trust_endorsement_b(db, tenant_b, catalog_asset_b, admin_user_b):
    return CatalogTrustEndorsement.objects.create(
        tenant=tenant_b,
        number="BTRU-00002",
        asset=catalog_asset_b,
        endorsement_type="peer_review",
        verdict="approved_certified",
        rating_value=4,
        attested_by=admin_user_b,
        is_active=True,
    )


@pytest.fixture
def bi_dashboard_a(db, tenant_a, admin_user):
    return BiDashboard.objects.create(
        tenant=tenant_a,
        number="BDSH-00001",
        title="Executive Performance Overview",
        slug="executive-performance-overview",
        description="Core metrics for executive leadership",
        category="executive",
        theme="slate_corporate",
        layout_type="grid_12",
        refresh_interval_seconds=0,
        is_published=True,
        is_kiosk_enabled=True,
        created_by=admin_user,
    )


@pytest.fixture
def bi_dashboard_b(db, tenant_b, admin_user_b):
    return BiDashboard.objects.create(
        tenant=tenant_b,
        number="BDSH-00002",
        title="Globex Revenue Operations",
        slug="globex-revenue-operations",
        description="Globex revenue KPIs",
        category="finance",
        theme="indigo_modern",
        layout_type="grid_12",
        refresh_interval_seconds=0,
        is_published=True,
        is_kiosk_enabled=True,
        created_by=admin_user_b,
    )


@pytest.fixture
def bi_dashboard_draft_a(db, tenant_a, admin_user):
    return BiDashboard.objects.create(
        tenant=tenant_a,
        number="BDSH-00003",
        title="Draft Strategy Dashboard",
        slug="draft-strategy-dashboard",
        description="Work in progress dashboard",
        category="executive",
        theme="dark_observability",
        layout_type="grid_12",
        refresh_interval_seconds=0,
        is_published=False,
        is_kiosk_enabled=False,
        created_by=admin_user,
    )


@pytest.fixture
def bi_widget_a(db, tenant_a, bi_dashboard_a):
    return BiDashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        number="BDWG-00001",
        title="Monthly Recurring Revenue",
        widget_type="kpi_card",
        pos_x=0,
        pos_y=0,
        width_cols=4,
        height_rows=2,
        chart_config_json={"value": "125000", "trend": "+12%"},
    )


@pytest.fixture
def bi_widget_b(db, tenant_b, bi_dashboard_b):
    return BiDashboardWidget.objects.create(
        tenant=tenant_b,
        dashboard=bi_dashboard_b,
        number="BDWG-00002",
        title="Globex Margin Rate",
        widget_type="kpi_card",
        pos_x=0,
        pos_y=0,
        width_cols=6,
        height_rows=2,
        chart_config_json={"value": "34.5%"},
    )


@pytest.fixture
def bi_bookmark_a(db, tenant_a, bi_dashboard_a, admin_user):
    return BiDashboardBookmark.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        number="BDBM-00001",
        name="Q3 Fiscal View",
        filter_state_json={"region": "EMEA", "currency": "USD"},
        crossfilter_state_json={"active_slice": "Enterprise"},
        is_default=False,
        is_shared=True,
    )


@pytest.fixture
def bi_bookmark_b(db, tenant_b, bi_dashboard_b, admin_user_b):
    return BiDashboardBookmark.objects.create(
        tenant=tenant_b,
        dashboard=bi_dashboard_b,
        user=admin_user_b,
        number="BDBM-00002",
        name="Globex Default View",
        filter_state_json={"region": "APAC"},
        crossfilter_state_json={},
        is_default=True,
        is_shared=False,
    )


@pytest.fixture
def bi_filter_a(db, tenant_a, bi_dashboard_a):
    return BiDashboardFilter.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        number="BDFL-00001",
        filter_label="Operating Region",
        filter_key="region",
        filter_type="dropdown",
        default_value="ALL",
        options_source="static_list",
        static_options_json=[{"value": "ALL", "label": "All Regions"}, {"value": "EMEA", "label": "EMEA"}],
        order=1,
    )


@pytest.fixture
def bi_filter_b(db, tenant_b, bi_dashboard_b):
    return BiDashboardFilter.objects.create(
        tenant=tenant_b,
        dashboard=bi_dashboard_b,
        number="BDFL-00002",
        filter_label="Product Segment",
        filter_key="segment",
        filter_type="dropdown",
        default_value="ALL",
        options_source="static_list",
        static_options_json=[{"value": "ALL", "label": "All Segments"}],
        order=1,
    )


# ---------------------------------------------------------------------------
# Sub-module 10.9: Standard & Operational Reporting Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def report_definition_a(db, tenant_a, admin_user_a, semantic_model_a):
    return ReportDefinition.objects.create(
        tenant=tenant_a,
        created_by=admin_user_a,
        name="Acme Monthly Revenue & Margin Report",
        slug="acme-monthly-revenue-margin-report",
        category="sales",
        report_type="tabular",
        status="published",
        semantic_model=semantic_model_a,
        page_orientation="portrait",
        page_size="A4",
        is_prebuilt=False,
        columns_config_json=[
            {"field": "row_id", "title": "#", "width": "40px", "align": "center"},
            {"field": "item_code", "title": "SKU / Code", "width": "120px", "align": "left"},
            {"field": "description", "title": "Product Title", "width": "220px", "align": "left"},
            {"field": "amount", "title": "Net Total (USD)", "width": "110px", "align": "right"},
        ],
    )


@pytest.fixture
def report_definition_b(db, tenant_b, admin_user_b, semantic_model_b):
    return ReportDefinition.objects.create(
        tenant=tenant_b,
        created_by=admin_user_b,
        name="Globex Monthly Revenue & Margin Report",
        slug="globex-monthly-revenue-margin-report",
        category="sales",
        report_type="tabular",
        status="published",
        semantic_model=semantic_model_b,
        page_orientation="portrait",
        page_size="A4",
        is_prebuilt=False,
        columns_config_json=[
            {"field": "row_id", "title": "#", "width": "40px", "align": "center"},
            {"field": "item_code", "title": "SKU / Code", "width": "120px", "align": "left"},
            {"field": "description", "title": "Product Title", "width": "220px", "align": "left"},
            {"field": "amount", "title": "Net Total (USD)", "width": "110px", "align": "right"},
        ],
    )


@pytest.fixture
def report_parameter_a(db, tenant_a, report_definition_a):
    return ReportParameter.objects.create(
        tenant=tenant_a,
        report=report_definition_a,
        parameter_name="fiscal_year",
        prompt_label="Fiscal Year",
        parameter_type="string",
        default_value="2026",
        is_required=True,
        prompt_order=1,
    )


@pytest.fixture
def report_parameter_b(db, tenant_b, report_definition_b):
    return ReportParameter.objects.create(
        tenant=tenant_b,
        report=report_definition_b,
        parameter_name="fiscal_year",
        prompt_label="Fiscal Year",
        parameter_type="string",
        default_value="2026",
        is_required=True,
        prompt_order=1,
    )


@pytest.fixture
def report_execution_a(db, tenant_a, report_definition_a, admin_user_a):
    return ReportExecution.objects.create(
        tenant=tenant_a,
        report=report_definition_a,
        executed_by=admin_user_a,
        execution_mode="interactive_view",
        execution_status="completed",
        output_format="html",
        row_count=12,
        duration_ms=45,
    )


@pytest.fixture
def report_execution_b(db, tenant_b, report_definition_b, admin_user_b):
    return ReportExecution.objects.create(
        tenant=tenant_b,
        report=report_definition_b,
        executed_by=admin_user_b,
        execution_mode="interactive_view",
        execution_status="completed",
        output_format="html",
        row_count=8,
        duration_ms=30,
    )


@pytest.fixture
def report_drill_path_a(db, tenant_a, report_definition_a):
    return ReportDrillPath.objects.create(
        tenant=tenant_a,
        source_report=report_definition_a,
        source_field="item_code",
        drill_label="Inspect Item Detail",
        target_type="operational_report",
        target_report=report_definition_a,
        sort_order=1,
    )


@pytest.fixture
def report_drill_path_b(db, tenant_b, report_definition_b):
    return ReportDrillPath.objects.create(
        tenant=tenant_b,
        source_report=report_definition_b,
        source_field="item_code",
        drill_label="Inspect Item Detail",
        target_type="operational_report",
        target_report=report_definition_b,
        sort_order=1,
    )


# ---------------------------------------------------------------------------
# 10.10 Self-Service & Ad-Hoc Analytics Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adhoc_query_a(db, tenant_a, admin_user):
    return AdHocQuery.objects.create(
        tenant=tenant_a,
        name="Acme Monthly Revenue",
        slug="acme-monthly-revenue",
        source_type="semantic_model",
        fields_config_json=[{"field": "period", "label": "Period", "type": "string"}, {"field": "revenue", "label": "Revenue", "type": "currency"}],
        filter_criteria_json=[{"field": "status", "operator": "equals", "value": "completed"}],
        row_limit=100,
        status="active",
        created_by=admin_user,
    )


@pytest.fixture
def adhoc_query_b(db, tenant_b, admin_user_b):
    return AdHocQuery.objects.create(
        tenant=tenant_b,
        name="Globex Monthly Revenue",
        slug="globex-monthly-revenue",
        source_type="semantic_model",
        fields_config_json=[{"field": "period", "label": "Period", "type": "string"}, {"field": "revenue", "label": "Revenue", "type": "currency"}],
        filter_criteria_json=[{"field": "status", "operator": "equals", "value": "completed"}],
        row_limit=100,
        status="active",
        created_by=admin_user_b,
    )


@pytest.fixture
def adhoc_calculated_field_a(db, tenant_a, adhoc_query_a):
    return AdHocCalculatedField.objects.create(
        tenant=tenant_a,
        query=adhoc_query_a,
        field_name="profit_margin",
        display_label="Profit Margin",
        formula_expression="[revenue] - [cost]",
        return_type="currency",
        aggregation_mode="sum",
        is_valid=True,
    )


@pytest.fixture
def adhoc_calculated_field_b(db, tenant_b, adhoc_query_b):
    return AdHocCalculatedField.objects.create(
        tenant=tenant_b,
        query=adhoc_query_b,
        field_name="globex_margin",
        display_label="Globex Margin",
        formula_expression="[revenue] - [cost]",
        return_type="currency",
        aggregation_mode="sum",
        is_valid=True,
    )


@pytest.fixture
def data_blend_definition_a(db, tenant_a, admin_user):
    return DataBlendDefinition.objects.create(
        tenant=tenant_a,
        name="Acme Sales & Inventory Blend",
        slug="acme-sales-inventory-blend",
        primary_source_type="semantic_model",
        secondary_source_type="warehouse_table",
        join_type="left_outer",
        cardinality="many_to_one",
        join_keys_mapping_json=[{"left": "item_id", "right": "id"}],
        status="active",
        created_by=admin_user,
    )


@pytest.fixture
def data_blend_definition_b(db, tenant_b, admin_user_b):
    return DataBlendDefinition.objects.create(
        tenant=tenant_b,
        name="Globex Sales & Inventory Blend",
        slug="globex-sales-inventory-blend",
        primary_source_type="semantic_model",
        secondary_source_type="warehouse_table",
        join_type="left_outer",
        cardinality="many_to_one",
        join_keys_mapping_json=[{"left": "item_id", "right": "id"}],
        status="active",
        created_by=admin_user_b,
    )


@pytest.fixture
def saved_analysis_view_a(db, tenant_a, adhoc_query_a, admin_user):
    return SavedAnalysisView.objects.create(
        tenant=tenant_a,
        query=adhoc_query_a,
        name="Acme Executive View",
        slug="acme-executive-view",
        description="Executive sales performance overview",
        sharing_scope="tenant_public",
        is_template=False,
        is_favorite=True,
        created_by=admin_user,
    )


@pytest.fixture
def saved_analysis_view_b(db, tenant_b, adhoc_query_b, admin_user_b):
    return SavedAnalysisView.objects.create(
        tenant=tenant_b,
        query=adhoc_query_b,
        name="Globex Executive View",
        slug="globex-executive-view",
        description="Executive sales performance overview",
        sharing_scope="tenant_public",
        is_template=False,
        is_favorite=True,
        created_by=admin_user_b,
    )


@pytest.fixture
def olap_cube_a(db, tenant_a, admin_user):
    return OlapCube.objects.create(
        tenant=tenant_a,
        name="Acme Financial Performance Cube",
        slug="acme-financial-performance-cube",
        description="Core multidimensional financial performance cube",
        storage_mode="molap",
        dimensions_config=[
            {"name": "Department", "field": "dept", "type": "string"},
            {"name": "FiscalPeriod", "field": "period", "type": "string"},
        ],
        measures_config=[
            {"name": "Actual Amount", "field": "amount", "agg": "sum"},
            {"name": "Budget Amount", "field": "budget", "agg": "sum"},
        ],
        status="active",
        created_by=admin_user,
    )


@pytest.fixture
def olap_cube_b(db, tenant_b, admin_user_b):
    return OlapCube.objects.create(
        tenant=tenant_b,
        name="Globex Financial Performance Cube",
        slug="globex-financial-performance-cube",
        description="Core multidimensional financial performance cube for Globex",
        storage_mode="molap",
        dimensions_config=[
            {"name": "Department", "field": "dept", "type": "string"},
            {"name": "FiscalPeriod", "field": "period", "type": "string"},
        ],
        measures_config=[
            {"name": "Actual Amount", "field": "amount", "agg": "sum"},
        ],
        status="active",
        created_by=admin_user_b,
    )


@pytest.fixture
def pivot_view_a(db, tenant_a, olap_cube_a, admin_user):
    return PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Acme Department Expense Matrix",
        slug="acme-department-expense-matrix",
        description="Expense matrix by department and period",
        row_dimensions=["Department"],
        column_dimensions=["FiscalPeriod"],
        measures_selection=["Actual Amount"],
        status="active",
        created_by=admin_user,
    )


@pytest.fixture
def pivot_view_b(db, tenant_b, olap_cube_b, admin_user_b):
    return PivotAnalysisView.objects.create(
        tenant=tenant_b,
        cube=olap_cube_b,
        name="Globex Department Expense Matrix",
        slug="globex-department-expense-matrix",
        description="Expense matrix by department and period for Globex",
        row_dimensions=["Department"],
        column_dimensions=["FiscalPeriod"],
        measures_selection=["Actual Amount"],
        status="active",
        created_by=admin_user_b,
    )


@pytest.fixture
def what_if_scenario_a(db, tenant_a, olap_cube_a, admin_user):
    return WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Acme FY2026 Optimistic Budget",
        slug="acme-fy2026-optimistic-budget",
        description="Optimistic budget scenario with 10% growth",
        fiscal_period="2026-FY",
        status="draft",
        total_baseline_amount=Decimal("100000.00"),
        total_adjusted_amount=Decimal("110000.00"),
        total_variance_amount=Decimal("10000.00"),
        created_by=admin_user,
    )


@pytest.fixture
def what_if_scenario_b(db, tenant_b, olap_cube_b, admin_user_b):
    return WhatIfScenario.objects.create(
        tenant=tenant_b,
        cube=olap_cube_b,
        name="Globex FY2026 Optimistic Budget",
        slug="globex-fy2026-optimistic-budget",
        description="Optimistic budget scenario for Globex",
        fiscal_period="2026-FY",
        status="draft",
        total_baseline_amount=Decimal("50000.00"),
        total_adjusted_amount=Decimal("55000.00"),
        total_variance_amount=Decimal("5000.00"),
        created_by=admin_user_b,
    )


@pytest.fixture
def writeback_cell_a(db, tenant_a, what_if_scenario_a, admin_user):
    return ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=what_if_scenario_a,
        coordinate_keys_json={"dept": "Sales", "period": "2026-Q1"},
        baseline_amount=Decimal("10000.00"),
        adjustment_delta=Decimal("2000.00"),
        simulated_amount=Decimal("12000.00"),
        adjustment_method="absolute",
        created_by=admin_user,
    )


@pytest.fixture
def writeback_cell_b(db, tenant_b, what_if_scenario_b, admin_user_b):
    return ScenarioWritebackCell.objects.create(
        tenant=tenant_b,
        scenario=what_if_scenario_b,
        coordinate_keys_json={"dept": "Operations", "period": "2026-Q1"},
        baseline_amount=Decimal("5000.00"),
        adjustment_delta=Decimal("1000.00"),
        simulated_amount=Decimal("6000.00"),
        adjustment_method="absolute",
        created_by=admin_user_b,
    )


@pytest.fixture
def kpi_definition_a(db, tenant_a, admin_user):
    return KpiDefinition.objects.create(
        tenant=tenant_a,
        number="BKPI-00001",
        code="REV_GROWTH_A",
        name="Acme Quarterly Revenue Growth",
        slug="acme-quarterly-revenue-growth",
        category="finance",
        perspective="financial",
        target_direction="maximize",
        unit_of_measure="percentage",
        tracking_frequency="quarterly",
        calculation_type="manual",
        target_value=Decimal("15.0000"),
        warning_threshold=Decimal("10.0000"),
        critical_threshold=Decimal("5.0000"),
        current_value=Decimal("14.5000"),
        status="active",
        owner=admin_user,
    )


@pytest.fixture
def kpi_definition_b(db, tenant_b, admin_user_b):
    return KpiDefinition.objects.create(
        tenant=tenant_b,
        number="BKPI-00002",
        code="REV_GROWTH_B",
        name="Globex Quarterly Revenue Growth",
        slug="globex-quarterly-revenue-growth",
        category="finance",
        perspective="financial",
        target_direction="maximize",
        unit_of_measure="percentage",
        tracking_frequency="quarterly",
        calculation_type="manual",
        target_value=Decimal("12.0000"),
        warning_threshold=Decimal("8.0000"),
        critical_threshold=Decimal("4.0000"),
        current_value=Decimal("11.5000"),
        status="active",
        owner=admin_user_b,
    )


@pytest.fixture
def performance_scorecard_a(db, tenant_a, admin_user):
    return PerformanceScorecard.objects.create(
        tenant=tenant_a,
        number="BSCR-00001",
        name="Acme Corporate Balanced Scorecard 2026",
        slug="acme-corporate-balanced-scorecard-2026",
        scorecard_type="balanced_scorecard",
        review_period="quarterly",
        fiscal_year=2026,
        status="active",
        is_published=True,
        owner=admin_user,
    )


@pytest.fixture
def performance_scorecard_b(db, tenant_b, admin_user_b):
    return PerformanceScorecard.objects.create(
        tenant=tenant_b,
        number="BSCR-00002",
        name="Globex Corporate Balanced Scorecard 2026",
        slug="globex-corporate-balanced-scorecard-2026",
        scorecard_type="balanced_scorecard",
        review_period="quarterly",
        fiscal_year=2026,
        status="active",
        is_published=True,
        owner=admin_user_b,
    )


@pytest.fixture
def strategic_objective_a(db, tenant_a, admin_user):
    return StrategicObjective.objects.create(
        tenant=tenant_a,
        number="BOBJ-00001",
        code="GROW_REV_A",
        name="Acme Accelerate Sustainable Revenue Growth",
        slug="acme-accelerate-sustainable-revenue-growth",
        perspective="financial",
        statement_of_intent="Expand enterprise software market share by 25%.",
        rag_status="green",
        status="active",
        owner=admin_user,
    )


@pytest.fixture
def strategic_objective_b(db, tenant_b, admin_user_b):
    return StrategicObjective.objects.create(
        tenant=tenant_b,
        number="BOBJ-00002",
        code="GROW_REV_B",
        name="Globex Accelerate Sustainable Revenue Growth",
        slug="globex-accelerate-sustainable-revenue-growth",
        perspective="financial",
        statement_of_intent="Expand manufacturing export share by 20%.",
        rag_status="green",
        status="active",
        owner=admin_user_b,
    )


@pytest.fixture
def scorecard_kpi_assignment_a(
    db, tenant_a, performance_scorecard_a, kpi_definition_a, strategic_objective_a
):
    return ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        number="BSCI-00001",
        scorecard=performance_scorecard_a,
        kpi=kpi_definition_a,
        objective=strategic_objective_a,
        perspective="financial",
        weight=Decimal("25.00"),
        target_value=Decimal("15.0000"),
        actual_value=Decimal("14.5000"),
        rag_status="green",
        trend_direction="improving",
        sort_order=10,
    )


@pytest.fixture
def scorecard_kpi_assignment_b(
    db, tenant_b, performance_scorecard_b, kpi_definition_b, strategic_objective_b
):
    return ScorecardKpiAssignment.objects.create(
        tenant=tenant_b,
        number="BSCI-00002",
        scorecard=performance_scorecard_b,
        kpi=kpi_definition_b,
        objective=strategic_objective_b,
        perspective="financial",
        weight=Decimal("25.00"),
        target_value=Decimal("12.0000"),
        actual_value=Decimal("11.5000"),
        rag_status="green",
        trend_direction="improving",
        sort_order=10,
    )

# ---------------------------------------------------------------------------
# Sub-module 10.13: Predictive & Advanced Analytics Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def predictive_model_a(db, tenant_a, semantic_model_a, admin_user):
    return PredictiveModel.objects.create(
        tenant=tenant_a,
        number="BPML-00001",
        name="Acme Demand Forecasting Model",
        code="acme_demand_forecast",
        problem_type="time_series_forecast",
        target_metric="sales_units",
        algorithm="auto_arima",
        cadence="monthly",
        status="active",
        owner=admin_user,
        features_list=["historical_sales", "promotions", "seasonality"],
        hyperparameters={"p": 1, "d": 1, "q": 1},
        semantic_model=semantic_model_a,
    )


@pytest.fixture
def predictive_model_b(db, tenant_b, semantic_model_b, admin_user_b):
    return PredictiveModel.objects.create(
        tenant=tenant_b,
        number="BPML-00002",
        name="Globex Churn Risk Classifier",
        code="globex_churn_classifier",
        problem_type="binary_classification",
        target_metric="churned",
        algorithm="random_forest",
        cadence="daily",
        status="active",
        owner=admin_user_b,
        features_list=["usage_frequency", "support_tickets"],
        hyperparameters={"n_estimators": 100},
        semantic_model=semantic_model_b,
    )


@pytest.fixture
def forecast_execution_a(
    db, tenant_a, predictive_model_a, semantic_model_a, kpi_definition_a, admin_user
):
    return ForecastExecution.objects.create(
        tenant=tenant_a,
        number="BFOR-00001",
        name="Acme H1 2027 Revenue Projection",
        model=predictive_model_a,
        semantic_model=semantic_model_a,
        kpi_definition=kpi_definition_a,
        cadence="monthly",
        horizon_periods=6,
        confidence_level="95",
        status="completed",
        baseline_value=Decimal("10000.0000"),
        projected_value=Decimal("11500.0000"),
        mape_score=Decimal("4.25"),
        executed_by=admin_user,
        forecast_output_data=[
            {"period": "2027-01", "predicted": 10200.0, "lower_bound": 9800.0, "upper_bound": 10600.0},
            {"period": "2027-02", "predicted": 10450.0, "lower_bound": 10000.0, "upper_bound": 10900.0},
        ],
    )


@pytest.fixture
def forecast_execution_b(
    db, tenant_b, predictive_model_b, semantic_model_b, kpi_definition_b, admin_user_b
):
    return ForecastExecution.objects.create(
        tenant=tenant_b,
        number="BFOR-00002",
        name="Globex Commercial Forecast Run",
        model=predictive_model_b,
        semantic_model=semantic_model_b,
        kpi_definition=kpi_definition_b,
        cadence="monthly",
        horizon_periods=3,
        confidence_level="90",
        status="completed",
        baseline_value=Decimal("5000.0000"),
        projected_value=Decimal("5300.0000"),
        mape_score=Decimal("5.10"),
        executed_by=admin_user_b,
        forecast_output_data=[
            {"period": "2027-01", "predicted": 5100.0, "lower_bound": 4900.0, "upper_bound": 5300.0},
        ],
    )


@pytest.fixture
def statistical_anomaly_a(
    db, tenant_a, predictive_model_a, semantic_model_a, kpi_definition_a, admin_user
):
    return StatisticalAnomaly.objects.create(
        tenant=tenant_a,
        number="BANM-00001",
        title="Unexpected Spike in Daily Server Latency",
        model=predictive_model_a,
        semantic_model=semantic_model_a,
        kpi_definition=kpi_definition_a,
        metric_name="response_latency_ms",
        anomaly_type="spike",
        detection_method="z_score",
        severity="critical",
        observed_value=Decimal("850.5000"),
        expected_value=Decimal("120.0000"),
        deviation_percentage=Decimal("608.75"),
        anomaly_timestamp=timezone.now(),
        triage_status="open",
        assigned_to=admin_user,
        root_cause_factors=[{"factor": "traffic_surge", "contribution_pct": 75.0}],
    )


@pytest.fixture
def statistical_anomaly_b(
    db, tenant_b, predictive_model_b, semantic_model_b, kpi_definition_b, admin_user_b
):
    return StatisticalAnomaly.objects.create(
        tenant=tenant_b,
        number="BANM-00002",
        title="Sudden Drop in User Engagement",
        model=predictive_model_b,
        semantic_model=semantic_model_b,
        kpi_definition=kpi_definition_b,
        metric_name="daily_active_users",
        anomaly_type="drop",
        detection_method="moving_average",
        severity="warning",
        observed_value=Decimal("350.0000"),
        expected_value=Decimal("1200.0000"),
        deviation_percentage=Decimal("-70.83"),
        anomaly_timestamp=timezone.now(),
        triage_status="open",
        assigned_to=admin_user_b,
        root_cause_factors=[{"factor": "auth_outage", "contribution_pct": 90.0}],
    )


@pytest.fixture
def optimization_scenario_a(db, tenant_a, kpi_definition_a, admin_user):
    return OptimizationScenario.objects.create(
        tenant=tenant_a,
        number="BOPT-00001",
        name="Acme Supply Chain Inventory Optimization",
        slug="acme-supply-chain-inventory-opt",
        objective_type="maximize",
        target_metric_name="gross_margin_profit",
        kpi_definition=kpi_definition_a,
        baseline_value=Decimal("50000.0000"),
        target_value=Decimal("65000.0000"),
        optimal_value=Decimal("62500.0000"),
        projected_lift_percentage=Decimal("25.00"),
        solver_algorithm="linear_programming",
        solver_status="optimal",
        status="active",
        owner=admin_user,
        decision_variables=[
            {"name": "safety_stock_level", "min_val": 100, "max_val": 500, "optimal_val": 320}
        ],
        constraint_rules=[
            {"rule": "budget_cap <= 100000", "status": "satisfied"}
        ],
        recommended_actions=[
            {"action": "Increase buffer stock in central distribution hub", "priority": "high"}
        ],
    )


@pytest.fixture
def optimization_scenario_b(db, tenant_b, kpi_definition_b, admin_user_b):
    return OptimizationScenario.objects.create(
        tenant=tenant_b,
        number="BOPT-00002",
        name="Globex Logistics Delivery Cost Minimization",
        slug="globex-logistics-delivery-cost-min",
        objective_type="minimize",
        target_metric_name="freight_expense",
        kpi_definition=kpi_definition_b,
        baseline_value=Decimal("80000.0000"),
        target_value=Decimal("60000.0000"),
        optimal_value=Decimal("64000.0000"),
        projected_lift_percentage=Decimal("-20.00"),
        solver_algorithm="mixed_integer_programming",
        solver_status="optimal",
        status="active",
        owner=admin_user_b,
        decision_variables=[
            {"name": "carrier_route_selection", "min_val": 1, "max_val": 10, "optimal_val": 4}
        ],
        constraint_rules=[
            {"rule": "service_sla_hours <= 24", "status": "satisfied"}
        ],
        recommended_actions=[
            {"action": "Consolidate regional shipments via Tier-1 carrier", "priority": "critical"}
        ],
    )

