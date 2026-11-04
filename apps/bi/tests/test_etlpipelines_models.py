"""Unit tests for Sub-module 10.2 models (EtlPipeline, TransformationStep, EtlPipelineVersion, EtlPipelineRun)."""
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.bi.models import (
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    TransformationStep,
)


def _etlpipelines_get_choice_keys(choices_list):
    """Helper to extract keys from Django choices tuple/list."""
    return [c[0] for c in choices_list]


# ---------------------------------------------------------------------------
# 1. EtlPipeline Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_etlpipelines_pipeline_creation_and_prefix(tenant_a, admin_user, bi_pipeline):
    """Test EtlPipeline creation, BETL prefix, str format, and defaults."""
    pipeline = EtlPipeline.objects.create(
        tenant=tenant_a,
        name="GL Journal Aggregator",
        source_ingestion_pipeline=bi_pipeline,
        source_staging_table="stg_gl_journals",
        target_table="fact_gl_monthly",
        created_by=admin_user,
    )
    assert pipeline.number.startswith("BETL-")
    assert str(pipeline) == f"{pipeline.number} — GL Journal Aggregator"
    assert pipeline.target_layer == "warehouse_fact"
    assert pipeline.trigger_type == "scheduled_cron"
    assert pipeline.status == "draft"
    assert pipeline.sla_timeout_seconds == 3600
    assert pipeline.alert_on_sla_miss is True
    assert pipeline.upstream_dependencies == []
    assert pipeline.retry_policy == {}
    assert pipeline.canvas_layout == {}
    assert pipeline.description == ""
    assert pipeline.cron_expression == ""
    assert pipeline.created_at is not None
    assert pipeline.updated_at is not None


@pytest.mark.django_db
def test_etlpipelines_pipeline_choices_contract():
    """Verify EtlPipeline choice constants match frozen specification."""
    status_keys = _etlpipelines_get_choice_keys(EtlPipeline.STATUS_CHOICES)
    assert status_keys == ["draft", "active", "paused", "deprecated", "error"]

    trigger_keys = _etlpipelines_get_choice_keys(EtlPipeline.TRIGGER_TYPE_CHOICES)
    assert trigger_keys == ["manual", "scheduled_cron", "event_on_ingest", "dependency_chained"]

    target_layer_keys = _etlpipelines_get_choice_keys(EtlPipeline.TARGET_LAYER_CHOICES)
    assert target_layer_keys == ["staging", "warehouse_fact", "warehouse_dim", "data_mart"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_meta_indexes_and_constraints():
    """Verify EtlPipeline meta table name, ordering, indexes, and constraints."""
    meta = EtlPipeline._meta
    assert meta.db_table == "bi_etl_pipeline"
    assert meta.ordering == ["-created_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_betl_ten_stat_trig" in index_names
    assert "idx_betl_ten_tgt_layer" in index_names
    assert "idx_betl_ten_name" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_betl_tenant_num_uniq" in constraint_names


# ---------------------------------------------------------------------------
# 2. TransformationStep Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_etlpipelines_transformation_step_creation_and_prefix(tenant_a, etl_pipeline_a):
    """Test TransformationStep creation, BTRN prefix, str format, and defaults."""
    step = TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        name="Cast Dates and IDs",
        step_type="cast",
        sequence=2,
        step_config={"date_format": "%Y-%m-%d", "int_fields": ["id", "customer_id"]},
    )
    assert step.number.startswith("BTRN-")
    assert str(step) == f"{step.number} — #2 Cast Dates and IDs ({step.get_step_type_display()})"
    assert step.status == "active"
    assert step.is_blocking is True
    assert step.canvas_x == 100
    assert step.canvas_y == 100
    assert step.upstream_step_ids == []
    assert step.description == ""


@pytest.mark.django_db
def test_etlpipelines_transformation_step_choices_contract():
    """Verify TransformationStep choice constants match frozen specification."""
    step_types = _etlpipelines_get_choice_keys(TransformationStep.STEP_TYPE_CHOICES)
    assert step_types == [
        "join",
        "aggregate",
        "pivot",
        "unpivot",
        "cast",
        "filter",
        "derived_column",
        "lookup_enrichment",
        "deduplicate",
        "business_rule",
    ]

    status_keys = _etlpipelines_get_choice_keys(TransformationStep.STATUS_CHOICES)
    assert status_keys == ["active", "disabled", "draft"]


@pytest.mark.django_db
def test_etlpipelines_transformation_step_meta_indexes_and_ordering():
    """Verify TransformationStep meta table, ordering, indexes, and constraints."""
    meta = TransformationStep._meta
    assert meta.db_table == "bi_transformation_step"
    assert meta.ordering == ["pipeline", "sequence", "id"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_btrn_ten_pipe_seq" in index_names
    assert "idx_btrn_ten_type_stat" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_btrn_tenant_num_uniq" in constraint_names


# ---------------------------------------------------------------------------
# 3. EtlPipelineVersion Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_etlpipelines_version_creation_and_prefix(tenant_a, etl_pipeline_a):
    """Test EtlPipelineVersion creation, BPVR prefix, str format, and defaults."""
    version = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version_number="v1.1.0",
        environment="staging",
        status="draft",
        changelog="Added customer segment lookup step",
    )
    assert version.number.startswith("BPVR-")
    assert str(version) == f"{version.number} (v1.1.0 [{version.get_environment_display()}])"
    assert version.environment == "staging"
    assert version.status == "draft"
    assert version.dag_definition == {}
    assert version.promoted_by is None
    assert version.promoted_at is None
    assert version.rollback_source is None


@pytest.mark.django_db
def test_etlpipelines_version_promoted_and_rollback(tenant_a, etl_pipeline_a, admin_user):
    """Test EtlPipelineVersion promotion and rollback self-reference."""
    now = timezone.now()
    v1 = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version_number="v1.0.0",
        environment="production",
        status="published",
        promoted_by=admin_user,
        promoted_at=now,
        changelog="Base release",
    )
    assert v1.promoted_by == admin_user
    assert v1.promoted_at == now

    v2_rollback = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version_number="v1.0.1",
        environment="production",
        status="rolled_back",
        rollback_source=v1,
        changelog="Rollback due to upstream schema change",
    )
    assert v2_rollback.rollback_source == v1
    assert v1.rolled_back_versions.count() == 1
    assert v1.rolled_back_versions.first() == v2_rollback


@pytest.mark.django_db
def test_etlpipelines_version_choices_contract():
    """Verify EtlPipelineVersion choice constants match frozen specification."""
    env_keys = _etlpipelines_get_choice_keys(EtlPipelineVersion.ENVIRONMENT_CHOICES)
    assert env_keys == ["development", "staging", "production"]

    status_keys = _etlpipelines_get_choice_keys(EtlPipelineVersion.STATUS_CHOICES)
    assert status_keys == ["draft", "published", "archived", "rolled_back"]


@pytest.mark.django_db
def test_etlpipelines_version_meta_indexes():
    """Verify EtlPipelineVersion meta table, ordering, and indexes."""
    meta = EtlPipelineVersion._meta
    assert meta.db_table == "bi_etl_pipeline_version"
    assert meta.ordering == ["-created_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_bpvr_ten_created_desc" in index_names
    assert "idx_bpvr_ten_pipe_env" in index_names
    assert "idx_bpvr_ten_stat" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_bpvr_tenant_num_uniq" in constraint_names


# ---------------------------------------------------------------------------
# 4. EtlPipelineRun Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_etlpipelines_run_creation_and_defaults(tenant_a, etl_pipeline_a, etl_version_a):
    """Test EtlPipelineRun creation, BEXR prefix, str format, and metric defaults."""
    run = EtlPipelineRun.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version=etl_version_a,
    )
    assert run.number.startswith("BEXR-")
    assert str(run) == f"{run.number} ({run.get_status_display()})"
    assert run.trigger_type == "manual"
    assert run.status == "pending"
    assert run.duration_seconds == Decimal("0.00")
    assert run.records_in == 0
    assert run.records_transformed == 0
    assert run.records_out == 0
    assert run.records_rejected == 0
    assert run.bytes_processed == 0
    assert run.sla_missed is False
    assert run.is_backfill is False
    assert run.retry_count == 0
    assert run.step_progress == {}
    assert run.error_message == ""
    assert run.execution_log == ""
    assert run.started_at is not None
    assert run.ended_at is None


@pytest.mark.django_db
def test_etlpipelines_run_choices_contract():
    """Verify EtlPipelineRun choice constants match frozen specification."""
    trigger_keys = _etlpipelines_get_choice_keys(EtlPipelineRun.TRIGGER_TYPE_CHOICES)
    assert trigger_keys == ["manual", "scheduled", "event_upstream", "backfill"]

    status_keys = _etlpipelines_get_choice_keys(EtlPipelineRun.STATUS_CHOICES)
    assert status_keys == [
        "pending",
        "queued",
        "running",
        "completed",
        "warning",
        "failed",
        "cancelled",
        "timed_out",
    ]


@pytest.mark.django_db
def test_etlpipelines_run_meta_indexes():
    """Verify EtlPipelineRun meta table, ordering, and indexes."""
    meta = EtlPipelineRun._meta
    assert meta.db_table == "bi_etl_pipeline_run"
    assert meta.ordering == ["-started_at"]

    index_names = {idx.name for idx in meta.indexes}
    assert "idx_bexr_ten_pipe_start" in index_names
    assert "idx_bexr_ten_stat_start" in index_names

    constraint_names = {c.name for c in meta.constraints}
    assert "bi_bexr_tenant_num_uniq" in constraint_names


# ---------------------------------------------------------------------------
# 5. Relational & Cascade Lifecycle Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_etlpipelines_cascade_delete_on_pipeline(tenant_a, admin_user, bi_pipeline):
    """Test deleting EtlPipeline cascades to TransformationSteps, Versions, and Runs."""
    pipeline = EtlPipeline.objects.create(
        tenant=tenant_a,
        name="Temporary Pipeline for Deletion",
        target_table="stg_tmp_sales",
        created_by=admin_user,
    )
    step = TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=pipeline,
        name="Step To Delete",
        step_type="filter",
        sequence=1,
    )
    version = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=pipeline,
        version_number="v0.0.1",
    )
    run = EtlPipelineRun.objects.create(
        tenant=tenant_a,
        pipeline=pipeline,
        version=version,
    )

    pipeline_pk = pipeline.pk
    step_pk = step.pk
    version_pk = version.pk
    run_pk = run.pk

    # Delete parent pipeline
    pipeline.delete()

    assert not EtlPipeline.objects.filter(pk=pipeline_pk).exists()
    assert not TransformationStep.objects.filter(pk=step_pk).exists()
    assert not EtlPipelineVersion.objects.filter(pk=version_pk).exists()
    assert not EtlPipelineRun.objects.filter(pk=run_pk).exists()


@pytest.mark.django_db
def test_etlpipelines_version_set_null_on_run_delete(tenant_a, etl_pipeline_a):
    """Test deleting an EtlPipelineVersion sets version=NULL on associated EtlPipelineRun."""
    version = EtlPipelineVersion.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version_number="v2.0.0-rc",
    )
    run = EtlPipelineRun.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        version=version,
    )
    run_pk = run.pk

    version.delete()

    run.refresh_from_db()
    assert run.version is None
    assert EtlPipelineRun.objects.filter(pk=run_pk).exists()


# ---------------------------------------------------------------------------
# 6. Tenant Isolation & Unique Numbering Continuity Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_etlpipelines_unique_numbering_continuity(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test sequential numbering continuity within tenant and across models."""
    p1 = EtlPipeline.objects.create(tenant=tenant_a, name="Pipe A1", target_table="t1")
    p2 = EtlPipeline.objects.create(tenant=tenant_a, name="Pipe A2", target_table="t2")
    p_b1 = EtlPipeline.objects.create(tenant=tenant_b, name="Pipe B1", target_table="t1")

    assert p1.number != p2.number
    assert p1.number.startswith("BETL-")
    assert p2.number.startswith("BETL-")
    assert p_b1.number.startswith("BETL-")

    # Step numbering continuity
    s1 = TransformationStep.objects.create(tenant=tenant_a, pipeline=p1, name="S1")
    s2 = TransformationStep.objects.create(tenant=tenant_a, pipeline=p1, name="S2")
    assert s1.number != s2.number
    assert s1.number.startswith("BTRN-")
    assert s2.number.startswith("BTRN-")

    # Version numbering continuity
    v1 = EtlPipelineVersion.objects.create(tenant=tenant_a, pipeline=p1, version_number="v1.0")
    v2 = EtlPipelineVersion.objects.create(tenant=tenant_a, pipeline=p1, version_number="v2.0")
    assert v1.number != v2.number
    assert v1.number.startswith("BPVR-")
    assert v2.number.startswith("BPVR-")

    # Run numbering continuity
    r1 = EtlPipelineRun.objects.create(tenant=tenant_a, pipeline=p1)
    r2 = EtlPipelineRun.objects.create(tenant=tenant_a, pipeline=p1)
    assert r1.number != r2.number
    assert r1.number.startswith("BEXR-")
    assert r2.number.startswith("BEXR-")


@pytest.mark.django_db
def test_etlpipelines_tenant_number_unique_constraint(tenant_a, etl_pipeline_a):
    """Verify bi_betl_tenant_num_uniq prevents duplicate (tenant, number) pairs."""
    with pytest.raises(IntegrityError):
        # Manually bypass auto-generation by setting duplicate number on save
        dup_pipeline = EtlPipeline(
            tenant=tenant_a,
            name="Duplicate Number Pipeline",
            target_table="dummy_table",
            number=etl_pipeline_a.number,
        )
        super(EtlPipeline, dup_pipeline).save()
