"""View tests for Sub-module 10.2 (ETL/ELT & Data Pipelines).

Covers all 20 routes under apps/bi for Sub-module 10.2:
- bi:etl_pipeline_list (200, context keys, filter params, search, CSV export)
- bi:etl_pipeline_create (GET 200, POST 302 redirect)
- bi:etl_pipeline_detail (200, context keys: pipeline, steps, versions, recent_runs, active_version)
- bi:etl_pipeline_edit (GET 200, POST 302 redirect)
- bi:etl_pipeline_delete (POST 302 redirect to list)
- bi:etl_pipeline_canvas (GET 200, POST 200 layout save)
- bi:etl_pipeline_trigger (POST 302 creates run; concurrency guard when already running)
- bi:transformation_step_list (200, filter params)
- bi:transformation_step_create (GET 200, POST 302 redirect)
- bi:transformation_step_detail (200, context keys: step, pipeline)
- bi:transformation_step_edit (GET 200, POST 302 redirect)
- bi:transformation_step_delete (POST 302 redirect)
- bi:etl_pipeline_version_list (200, filter params)
- bi:etl_pipeline_version_create (GET 200, POST 302 redirect)
- bi:etl_pipeline_version_detail (200, context keys: version, pipeline)
- bi:etl_pipeline_version_edit (GET 200, POST 302 redirect)
- bi:etl_pipeline_version_delete (POST 302; active version deletion protection)
- bi:etl_pipeline_version_promote (POST 302; target_environment validation)
- bi:etl_pipeline_run_list (200, filter params, context keys)
- bi:etl_pipeline_run_detail (200, context keys: run, pipeline)
- Resilience against junk/invalid GET parameters
"""
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.bi.models import (
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    TransformationStep,
)


def _etlpipelines_create_pipeline(tenant, name="Auxiliary ETL Pipeline", **kwargs):
    """Helper to create an EtlPipeline for view tests."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "description": "Auxiliary pipeline for test isolation",
        "source_staging_table": "stg_aux_table",
        "target_table": "fact_aux_mart",
        "target_layer": "warehouse_fact",
        "trigger_type": "manual",
        "status": "draft",
    }
    defaults.update(kwargs)
    return EtlPipeline.objects.create(**defaults)


def _etlpipelines_create_draft_version(tenant, pipeline, version_number="v0.1.0"):
    """Helper to create a non-active draft version for deletion/promotion tests."""
    return EtlPipelineVersion.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        version_number=version_number,
        environment="development",
        status="draft",
        changelog="Draft version changelog",
    )


# ===========================================================================
# 1. Pipeline Routes
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_pipeline_list_renders_200_and_context(auth_client, etl_pipeline_a):
    """Verify bi:etl_pipeline_list returns 200 and passes all required context keys."""
    url = reverse("bi:etl_pipeline_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "pipelines",
        "page_obj",
        "paginator",
        "q",
        "status_filter",
        "trigger_filter",
        "target_layer_filter",
        "status_choices",
        "trigger_type_choices",
        "target_layer_choices",
        "total_count",
        "active_count",
        "running_count",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key {key} missing from etl_pipeline_list"

    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert etl_pipeline_a in resp.context["pipelines"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_list_filtering_and_search(auth_client, tenant_a, etl_pipeline_a):
    """Verify filtering by status, trigger_type, target_layer, and search query q."""
    # Create a secondary pipeline with distinct attributes
    pipe_b = _etlpipelines_create_pipeline(
        tenant_a,
        name="Unique Aggregate Dimension Mart",
        target_layer="warehouse_dim",
        trigger_type="event_on_ingest",
        status="paused",
    )

    url = reverse("bi:etl_pipeline_list")

    # Filter by status
    resp = auth_client.get(f"{url}?status=paused")
    assert resp.status_code == 200
    listed_ids = [p.id for p in resp.context["pipelines"]]
    assert pipe_b.id in listed_ids
    assert etl_pipeline_a.id not in listed_ids

    # Filter by trigger_type
    resp = auth_client.get(f"{url}?trigger_type=event_on_ingest")
    assert resp.status_code == 200
    listed_ids = [p.id for p in resp.context["pipelines"]]
    assert pipe_b.id in listed_ids
    assert etl_pipeline_a.id not in listed_ids

    # Filter by target_layer
    resp = auth_client.get(f"{url}?target_layer=warehouse_dim")
    assert resp.status_code == 200
    listed_ids = [p.id for p in resp.context["pipelines"]]
    assert pipe_b.id in listed_ids
    assert etl_pipeline_a.id not in listed_ids

    # Search by keyword in name
    resp = auth_client.get(f"{url}?q=Unique Aggregate")
    assert resp.status_code == 200
    listed_ids = [p.id for p in resp.context["pipelines"]]
    assert pipe_b.id in listed_ids
    assert etl_pipeline_a.id not in listed_ids


@pytest.mark.django_db
def test_etlpipelines_pipeline_list_csv_export(auth_client, etl_pipeline_a):
    """Verify ?export=csv generates attachment with CSV content and proper headers."""
    url = reverse("bi:etl_pipeline_list")
    resp = auth_client.get(f"{url}?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'attachment; filename="etl_pipelines.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Number,Name,Source Staging,Target Table,Layer,Trigger,Status,Last Run" in content
    assert etl_pipeline_a.number in content
    assert etl_pipeline_a.name in content


@pytest.mark.django_db
def test_etlpipelines_pipeline_create_get_and_post(auth_client, tenant_a, bi_pipeline):
    """Verify bi:etl_pipeline_create renders GET form and POST creates instance & redirects."""
    url = reverse("bi:etl_pipeline_create")

    # GET request with source_id prefill
    resp = auth_client.get(f"{url}?source_id={bi_pipeline.pk}")
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["form"].initial.get("source_ingestion_pipeline") == bi_pipeline.pk

    # POST request creates new pipeline
    payload = {
        "name": "Brand New Orders Fact Mart",
        "description": "Transforms orders into analytical mart",
        "source_ingestion_pipeline": bi_pipeline.pk,
        "source_staging_table": "stg_orders",
        "target_table": "fact_orders",
        "target_layer": "warehouse_fact",
        "trigger_type": "manual",
        "cron_expression": "",
        "sla_timeout_seconds": 3600,
        "alert_on_sla_miss": True,
        "status": "draft",
        "upstream_dependencies_raw": "",
        "retry_policy_raw": "",
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 302

    created_pipe = EtlPipeline.objects.filter(tenant=tenant_a, name="Brand New Orders Fact Mart").first()
    assert created_pipe is not None
    assert created_pipe.target_table == "fact_orders"
    assert resp.url == reverse("bi:etl_pipeline_detail", kwargs={"pk": created_pipe.pk})


@pytest.mark.django_db
def test_etlpipelines_pipeline_detail_renders_200_and_context(
    auth_client, etl_pipeline_a, etl_step_a, etl_version_a, etl_run_a
):
    """Verify bi:etl_pipeline_detail returns 200 with steps, versions, runs, and active_version."""
    url = reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["pipeline"] == etl_pipeline_a
    assert resp.context["active_version"] == etl_version_a
    assert etl_step_a in resp.context["steps"]
    assert etl_version_a in resp.context["versions"]
    assert etl_run_a in resp.context["recent_runs"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_edit_get_and_post(auth_client, etl_pipeline_a):
    """Verify bi:etl_pipeline_edit renders populated form and POST updates instance."""
    url = reverse("bi:etl_pipeline_edit", kwargs={"pk": etl_pipeline_a.pk})

    # GET edit
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["pipeline"] == etl_pipeline_a
    assert resp.context["is_edit"] is True

    # POST update
    payload = {
        "name": "Updated Daily Sales Fact Mart",
        "description": "Updated description for pipeline",
        "source_staging_table": etl_pipeline_a.source_staging_table,
        "target_table": "fact_daily_sales_v2",
        "target_layer": "warehouse_fact",
        "trigger_type": "manual",
        "status": "active",
        "sla_timeout_seconds": 1800,
        "alert_on_sla_miss": False,
        "upstream_dependencies_raw": "",
        "retry_policy_raw": "",
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk})

    etl_pipeline_a.refresh_from_db()
    assert etl_pipeline_a.name == "Updated Daily Sales Fact Mart"
    assert etl_pipeline_a.target_table == "fact_daily_sales_v2"
    assert etl_pipeline_a.sla_timeout_seconds == 1800


@pytest.mark.django_db
def test_etlpipelines_pipeline_delete_post(auth_client, tenant_a):
    """Verify bi:etl_pipeline_delete deletes the pipeline and redirects to list."""
    pipeline_to_delete = _etlpipelines_create_pipeline(tenant_a, name="Pipeline To Be Deleted")
    url = reverse("bi:etl_pipeline_delete", kwargs={"pk": pipeline_to_delete.pk})

    resp = auth_client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_list")

    assert not EtlPipeline.objects.filter(pk=pipeline_to_delete.pk).exists()


@pytest.mark.django_db
def test_etlpipelines_pipeline_canvas_get_and_post(auth_client, etl_pipeline_a, etl_step_a):
    """Verify bi:etl_pipeline_canvas renders GET and accepts POST layout save."""
    url = reverse("bi:etl_pipeline_canvas", kwargs={"pk": etl_pipeline_a.pk})

    # GET canvas
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert resp.context["pipeline"] == etl_pipeline_a
    assert etl_step_a in resp.context["steps"]
    assert "step_type_choices" in resp.context
    assert "available_sources" in resp.context

    # POST canvas (returns 200 template render)
    resp = auth_client.post(url, data={"canvas_data": "sample"})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_etlpipelines_pipeline_trigger_success_and_concurrency_guard(auth_client, tenant_a, etl_pipeline_a):
    """Verify bi:etl_pipeline_trigger initiates run, and blocks trigger when already running."""
    url = reverse("bi:etl_pipeline_trigger", kwargs={"pk": etl_pipeline_a.pk})

    initial_runs = etl_pipeline_a.runs.count()

    # 1. First trigger creates a running execution
    resp = auth_client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk})

    assert etl_pipeline_a.runs.count() == initial_runs + 1
    new_run = etl_pipeline_a.runs.order_by("-started_at").first()
    assert new_run.status == "running"
    assert new_run.trigger_type == "manual"

    etl_pipeline_a.refresh_from_db()
    assert etl_pipeline_a.last_run_at is not None

    # 2. Concurrency guard: triggering while a run is in 'running' status blocks a second run
    resp = auth_client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk})

    # Run count must not increase
    assert etl_pipeline_a.runs.count() == initial_runs + 1
    messages = list(get_messages(resp.wsgi_request))
    assert any("already in progress" in str(m) for m in messages)


# ===========================================================================
# 2. Transformation Step Routes
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_transformation_step_list_renders_200_and_context(auth_client, etl_step_a):
    """Verify bi:transformation_step_list returns 200 and passes all context keys."""
    url = reverse("bi:transformation_step_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "steps",
        "page_obj",
        "paginator",
        "q",
        "step_type_filter",
        "status_filter",
        "pipeline_filter",
        "step_type_choices",
        "status_choices",
        "pipelines",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key {key} missing from transformation_step_list"

    assert etl_step_a in resp.context["steps"]


@pytest.mark.django_db
def test_etlpipelines_transformation_step_list_filtering_and_search(auth_client, tenant_a, etl_pipeline_a, etl_step_a):
    """Verify step list filtering by step_type, status, pipeline_id, and q search."""
    step_b = TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        name="Filter Null Customer Keys",
        step_type="filter",
        sequence=2,
        status="draft",
        is_blocking=False,
    )

    url = reverse("bi:transformation_step_list")

    # Filter by step_type
    resp = auth_client.get(f"{url}?step_type=filter")
    assert resp.status_code == 200
    step_ids = [s.id for s in resp.context["steps"]]
    assert step_b.id in step_ids
    assert etl_step_a.id not in step_ids

    # Filter by status
    resp = auth_client.get(f"{url}?status=draft")
    assert resp.status_code == 200
    step_ids = [s.id for s in resp.context["steps"]]
    assert step_b.id in step_ids
    assert etl_step_a.id not in step_ids

    # Filter by pipeline_id
    resp = auth_client.get(f"{url}?pipeline_id={etl_pipeline_a.pk}")
    assert resp.status_code == 200
    step_ids = [s.id for s in resp.context["steps"]]
    assert step_b.id in step_ids
    assert etl_step_a.id in step_ids

    # Search by q
    resp = auth_client.get(f"{url}?q=Null Customer")
    assert resp.status_code == 200
    step_ids = [s.id for s in resp.context["steps"]]
    assert step_b.id in step_ids
    assert etl_step_a.id not in step_ids


@pytest.mark.django_db
def test_etlpipelines_transformation_step_list_csv_export(auth_client, etl_step_a):
    """Verify ?export=csv returns CSV export for transformation steps."""
    url = reverse("bi:transformation_step_list")
    resp = auth_client.get(f"{url}?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'attachment; filename="transformation_steps.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Step Number,Pipeline,Seq,Name,Type,Status,Blocking" in content
    assert etl_step_a.number in content
    assert etl_step_a.name in content


@pytest.mark.django_db
def test_etlpipelines_transformation_step_create_get_and_post(auth_client, tenant_a, etl_pipeline_a):
    """Verify bi:transformation_step_create renders GET and POST saves new step."""
    url = reverse("bi:transformation_step_create")

    # GET with pipeline param
    resp = auth_client.get(f"{url}?pipeline_id={etl_pipeline_a.pk}")
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["pipeline"] == etl_pipeline_a

    # POST create
    payload = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Aggregate Revenue By Customer",
        "step_type": "aggregate",
        "sequence": 3,
        "status": "active",
        "is_blocking": True,
        "description": "Calculates revenue sums",
        "upstream_step_ids_raw": "",
        "step_config_raw": '{"group_by": ["customer_id"], "metrics": ["sum(total)"]}',
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 302

    created_step = TransformationStep.objects.filter(tenant=tenant_a, name="Aggregate Revenue By Customer").first()
    assert created_step is not None
    assert created_step.step_type == "aggregate"
    assert resp.url == reverse("bi:transformation_step_detail", kwargs={"pk": created_step.pk})


@pytest.mark.django_db
def test_etlpipelines_transformation_step_detail_renders_200_and_context(auth_client, etl_step_a, etl_pipeline_a):
    """Verify bi:transformation_step_detail returns 200 with step, pipeline, and mapping_template."""
    url = reverse("bi:transformation_step_detail", kwargs={"pk": etl_step_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["step"] == etl_step_a
    assert resp.context["pipeline"] == etl_pipeline_a
    assert "mapping_template" in resp.context


@pytest.mark.django_db
def test_etlpipelines_transformation_step_edit_get_and_post(auth_client, etl_step_a, etl_pipeline_a):
    """Verify bi:transformation_step_edit renders GET and POST updates step."""
    url = reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_a.pk})

    # GET edit
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["step"] == etl_step_a
    assert resp.context["is_edit"] is True
    assert resp.context["pipeline"] == etl_pipeline_a

    # POST update
    payload = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Join Customer Master Updated",
        "step_type": "join",
        "sequence": 5,
        "status": "active",
        "is_blocking": False,
        "description": "Updated join rule",
        "upstream_step_ids_raw": "",
        "step_config_raw": '{"join_type": "left"}',
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:transformation_step_detail", kwargs={"pk": etl_step_a.pk})

    etl_step_a.refresh_from_db()
    assert etl_step_a.name == "Join Customer Master Updated"
    assert etl_step_a.sequence == 5
    assert etl_step_a.is_blocking is False


@pytest.mark.django_db
def test_etlpipelines_transformation_step_delete_post(auth_client, tenant_a, etl_pipeline_a):
    """Verify bi:transformation_step_delete removes step and supports next redirect."""
    step = TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        name="Step To Delete",
        step_type="filter",
        sequence=10,
        status="active",
    )
    url = reverse("bi:transformation_step_delete", kwargs={"pk": step.pk})

    # Delete with next=list
    resp = auth_client.post(f"{url}?next=list")
    assert resp.status_code == 302
    assert resp.url == reverse("bi:transformation_step_list")
    assert not TransformationStep.objects.filter(pk=step.pk).exists()

    # Second step delete without next redirects to pipeline detail
    step2 = TransformationStep.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        name="Step To Delete 2",
        step_type="filter",
        sequence=11,
        status="active",
    )
    url2 = reverse("bi:transformation_step_delete", kwargs={"pk": step2.pk})
    resp2 = auth_client.post(url2)
    assert resp2.status_code == 302
    assert resp2.url == reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk})
    assert not TransformationStep.objects.filter(pk=step2.pk).exists()


# ===========================================================================
# 3. Pipeline Version Routes
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_list_renders_200_and_context(auth_client, etl_version_a):
    """Verify bi:etl_pipeline_version_list returns 200 with all context keys."""
    url = reverse("bi:etl_pipeline_version_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "versions",
        "page_obj",
        "paginator",
        "q",
        "environment_filter",
        "status_filter",
        "pipeline_filter",
        "environment_choices",
        "status_choices",
        "pipelines",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key {key} missing from etl_pipeline_version_list"

    assert etl_version_a in resp.context["versions"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_list_filtering_and_search(auth_client, tenant_a, etl_pipeline_a, etl_version_a):
    """Verify version list filtering by environment, status, pipeline_id, and q."""
    v_draft = _etlpipelines_create_draft_version(tenant_a, etl_pipeline_a, version_number="v2.0.0-draft")

    url = reverse("bi:etl_pipeline_version_list")

    # Filter by environment
    resp = auth_client.get(f"{url}?environment=development")
    assert resp.status_code == 200
    v_ids = [v.id for v in resp.context["versions"]]
    assert v_draft.id in v_ids
    assert etl_version_a.id not in v_ids

    # Filter by status
    resp = auth_client.get(f"{url}?status=draft")
    assert resp.status_code == 200
    v_ids = [v.id for v in resp.context["versions"]]
    assert v_draft.id in v_ids
    assert etl_version_a.id not in v_ids

    # Filter by pipeline_id
    resp = auth_client.get(f"{url}?pipeline_id={etl_pipeline_a.pk}")
    assert resp.status_code == 200
    v_ids = [v.id for v in resp.context["versions"]]
    assert v_draft.id in v_ids
    assert etl_version_a.id in v_ids

    # Search by q
    resp = auth_client.get(f"{url}?q=v2.0.0")
    assert resp.status_code == 200
    v_ids = [v.id for v in resp.context["versions"]]
    assert v_draft.id in v_ids
    assert etl_version_a.id not in v_ids


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_list_csv_export(auth_client, etl_version_a):
    """Verify ?export=csv generates pipeline versions CSV download."""
    url = reverse("bi:etl_pipeline_version_list")
    resp = auth_client.get(f"{url}?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'attachment; filename="pipeline_versions.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Version ID,Pipeline,Version Number,Environment,Status,Promoted By,Promoted At" in content
    assert etl_version_a.number in content
    assert etl_version_a.version_number in content


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_create_get_and_post(auth_client, tenant_a, etl_pipeline_a, etl_step_a):
    """Verify bi:etl_pipeline_version_create renders GET and POST creates version snapshot."""
    url = reverse("bi:etl_pipeline_version_create")

    # GET create
    resp = auth_client.get(f"{url}?pipeline_id={etl_pipeline_a.pk}")
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False

    # POST create
    payload = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v1.2.0",
        "environment": "staging",
        "status": "draft",
        "changelog": "Staging candidate for Q4 reporting mart",
        "dag_definition_raw": "",  # Auto-snapshots pipeline steps
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 302

    new_v = EtlPipelineVersion.objects.filter(tenant=tenant_a, version_number="v1.2.0").first()
    assert new_v is not None
    assert new_v.environment == "staging"
    assert "steps" in new_v.dag_definition
    assert resp.url == reverse("bi:etl_pipeline_version_detail", kwargs={"pk": new_v.pk})


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_detail_renders_200_and_context(auth_client, etl_version_a, etl_pipeline_a):
    """Verify bi:etl_pipeline_version_detail returns 200 with version, pipeline, and promoted_by."""
    url = reverse("bi:etl_pipeline_version_detail", kwargs={"pk": etl_version_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["version"] == etl_version_a
    assert resp.context["pipeline"] == etl_pipeline_a
    assert "environment_instance" in resp.context
    assert "promoted_by" in resp.context


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_edit_get_and_post(auth_client, tenant_a, etl_pipeline_a):
    """Verify bi:etl_pipeline_version_edit renders GET and POST updates version."""
    version = _etlpipelines_create_draft_version(tenant_a, etl_pipeline_a, version_number="v1.3.0")
    url = reverse("bi:etl_pipeline_version_edit", kwargs={"pk": version.pk})

    # GET edit
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["version"] == version
    assert resp.context["is_edit"] is True

    # POST update
    payload = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v1.3.0",
        "environment": "staging",
        "status": "draft",
        "changelog": "Updated changelog notes",
        "dag_definition_raw": '{"engine": "custom"}',
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_version_detail", kwargs={"pk": version.pk})

    version.refresh_from_db()
    assert version.environment == "staging"
    assert version.changelog == "Updated changelog notes"


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_delete_protection_active_version(auth_client, etl_version_a, etl_pipeline_a):
    """Verify active production version CANNOT be deleted (protection guard)."""
    assert etl_pipeline_a.active_version_id == etl_version_a.pk
    url = reverse("bi:etl_pipeline_version_delete", kwargs={"pk": etl_version_a.pk})

    resp = auth_client.post(url)
    assert resp.status_code == 302

    # Verify version was NOT deleted
    assert EtlPipelineVersion.objects.filter(pk=etl_version_a.pk).exists()

    messages = list(get_messages(resp.wsgi_request))
    assert any("Cannot delete Version" in str(m) and "active production version" in str(m) for m in messages)


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_delete_draft_success(auth_client, tenant_a, etl_pipeline_a):
    """Verify non-active draft version is deleted successfully."""
    draft_v = _etlpipelines_create_draft_version(tenant_a, etl_pipeline_a, version_number="v0.9.9")
    url = reverse("bi:etl_pipeline_version_delete", kwargs={"pk": draft_v.pk})

    resp = auth_client.post(f"{url}?next=list")
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_version_list")
    assert not EtlPipelineVersion.objects.filter(pk=draft_v.pk).exists()


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_promote_valid_environment(auth_client, tenant_a, etl_pipeline_a, admin_user):
    """Verify bi:etl_pipeline_version_promote promotes version and updates active_version if production."""
    candidate_v = _etlpipelines_create_draft_version(tenant_a, etl_pipeline_a, version_number="v2.0.0")
    url = reverse("bi:etl_pipeline_version_promote", kwargs={"pk": candidate_v.pk})

    resp = auth_client.post(url, data={"target_environment": "production"})
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_version_detail", kwargs={"pk": candidate_v.pk})

    candidate_v.refresh_from_db()
    assert candidate_v.environment == "production"
    assert candidate_v.status == "published"
    assert candidate_v.promoted_by == admin_user
    assert candidate_v.promoted_at is not None

    etl_pipeline_a.refresh_from_db()
    assert etl_pipeline_a.active_version == candidate_v


@pytest.mark.django_db
def test_etlpipelines_pipeline_version_promote_invalid_environment(auth_client, tenant_a, etl_pipeline_a):
    """Verify bi:etl_pipeline_version_promote rejects invalid target_environment."""
    candidate_v = _etlpipelines_create_draft_version(tenant_a, etl_pipeline_a, version_number="v2.1.0")
    url = reverse("bi:etl_pipeline_version_promote", kwargs={"pk": candidate_v.pk})

    resp = auth_client.post(url, data={"target_environment": "invalid_environment_xyz"})
    assert resp.status_code == 302
    assert resp.url == reverse("bi:etl_pipeline_version_detail", kwargs={"pk": candidate_v.pk})

    candidate_v.refresh_from_db()
    assert candidate_v.environment == "development"
    assert candidate_v.status == "draft"

    messages = list(get_messages(resp.wsgi_request))
    assert any("Invalid target environment" in str(m) for m in messages)


# ===========================================================================
# 4. Pipeline Run Routes
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_pipeline_run_list_renders_200_and_context(auth_client, etl_run_a):
    """Verify bi:etl_pipeline_run_list returns 200 with all context keys and aggregate counts."""
    url = reverse("bi:etl_pipeline_run_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "runs",
        "page_obj",
        "paginator",
        "q",
        "status_filter",
        "trigger_filter",
        "pipeline_filter",
        "status_choices",
        "trigger_type_choices",
        "pipelines",
        "total_count",
        "success_count",
        "failed_count",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key {key} missing from etl_pipeline_run_list"

    assert etl_run_a in resp.context["runs"]
    assert resp.context["total_count"] >= 1
    assert resp.context["success_count"] >= 1


@pytest.mark.django_db
def test_etlpipelines_pipeline_run_list_filtering_and_search(auth_client, tenant_a, etl_pipeline_a, etl_run_a):
    """Verify run list filtering by status, trigger_type, pipeline_id, and q."""
    failed_run = EtlPipelineRun.objects.create(
        tenant=tenant_a,
        pipeline=etl_pipeline_a,
        trigger_type="manual",
        status="failed",
        error_message="UniqueTransformError: division by zero",
    )

    url = reverse("bi:etl_pipeline_run_list")

    # Filter by status
    resp = auth_client.get(f"{url}?status=failed")
    assert resp.status_code == 200
    run_ids = [r.id for r in resp.context["runs"]]
    assert failed_run.id in run_ids
    assert etl_run_a.id not in run_ids

    # Filter by trigger_type
    resp = auth_client.get(f"{url}?trigger_type=manual")
    assert resp.status_code == 200
    run_ids = [r.id for r in resp.context["runs"]]
    assert failed_run.id in run_ids
    assert etl_run_a.id not in run_ids

    # Filter by pipeline_id
    resp = auth_client.get(f"{url}?pipeline_id={etl_pipeline_a.pk}")
    assert resp.status_code == 200
    run_ids = [r.id for r in resp.context["runs"]]
    assert failed_run.id in run_ids
    assert etl_run_a.id in run_ids

    # Search by q in error_message
    resp = auth_client.get(f"{url}?q=UniqueTransformError")
    assert resp.status_code == 200
    run_ids = [r.id for r in resp.context["runs"]]
    assert failed_run.id in run_ids
    assert etl_run_a.id not in run_ids


@pytest.mark.django_db
def test_etlpipelines_pipeline_run_list_csv_export(auth_client, etl_run_a):
    """Verify ?export=csv generates pipeline execution runs CSV export."""
    url = reverse("bi:etl_pipeline_run_list")
    resp = auth_client.get(f"{url}?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'attachment; filename="etl_runs.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Run Number,Pipeline,Trigger,Status,Started At,Duration (s),Records In,Transformed,Records Out,Rejected,SLA Missed" in content
    assert etl_run_a.number in content
    assert etl_run_a.pipeline.name in content


@pytest.mark.django_db
def test_etlpipelines_pipeline_run_detail_renders_200_and_context(auth_client, etl_run_a, etl_pipeline_a, etl_version_a):
    """Verify bi:etl_pipeline_run_detail returns 200 with run, pipeline, and version."""
    url = reverse("bi:etl_pipeline_run_detail", kwargs={"pk": etl_run_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["run"] == etl_run_a
    assert resp.context["pipeline"] == etl_pipeline_a
    assert resp.context["version"] == etl_version_a


# ===========================================================================
# 5. Resilience & Smoke Tests
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_junk_params_resilience(auth_client):
    """Verify list views gracefully return 200 with invalid/junk filter params without 500 errors."""
    endpoints = [
        reverse("bi:etl_pipeline_list"),
        reverse("bi:transformation_step_list"),
        reverse("bi:etl_pipeline_version_list"),
        reverse("bi:etl_pipeline_run_list"),
    ]
    junk_query = "?status=invalid_xyz&pipeline_id=notanint&page=999&trigger_type=nonexistent&target_layer=garbage&environment=mars"

    for endpoint in endpoints:
        resp = auth_client.get(f"{endpoint}{junk_query}")
        assert resp.status_code == 200, f"Endpoint {endpoint} failed with junk params: status {resp.status_code}"


@pytest.mark.django_db
def test_etlpipelines_all_20_routes_smoke(
    auth_client,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
    etl_run_a,
):
    """Verify all 20 Sub-module 10.2 routes render 200 with authenticated client."""
    routes = [
        # 1. Pipeline routes
        ("bi:etl_pipeline_list", {}),
        ("bi:etl_pipeline_create", {}),
        ("bi:etl_pipeline_detail", {"pk": etl_pipeline_a.pk}),
        ("bi:etl_pipeline_edit", {"pk": etl_pipeline_a.pk}),
        ("bi:etl_pipeline_canvas", {"pk": etl_pipeline_a.pk}),
        # 2. Transformation step routes
        ("bi:transformation_step_list", {}),
        ("bi:transformation_step_create", {}),
        ("bi:transformation_step_detail", {"pk": etl_step_a.pk}),
        ("bi:transformation_step_edit", {"pk": etl_step_a.pk}),
        # 3. Pipeline version routes
        ("bi:etl_pipeline_version_list", {}),
        ("bi:etl_pipeline_version_create", {}),
        ("bi:etl_pipeline_version_detail", {"pk": etl_version_a.pk}),
        ("bi:etl_pipeline_version_edit", {"pk": etl_version_a.pk}),
        # 4. Pipeline run routes
        ("bi:etl_pipeline_run_list", {}),
        ("bi:etl_pipeline_run_detail", {"pk": etl_run_a.pk}),
    ]

    for name, kwargs in routes:
        url = reverse(name, kwargs=kwargs)
        resp = auth_client.get(url)
        assert resp.status_code == 200, f"Route {name} returned status {resp.status_code}"
