"""Security, Multi-Tenancy, and Authorization Tests for Sub-module 10.2 (ETL/ELT & Data Pipelines).

Covers:
- Cross-Tenant IDOR:
  Client A attempting to read, update, canvas, trigger, promote, or delete Tenant B's
  pipelines, transformation steps, pipeline versions, and runs returns 404 Not Found.
  Client B attempting to access Tenant A's objects returns 404 Not Found.
- Cross-Tenant Data Isolation in Lists:
  Client A never sees Tenant B entities in list views, context datasets, search queries,
  or CSV exports (and vice versa for Client B).
- Cross-Tenant Foreign Key Tampering / Injection:
  Submitting create/edit requests under Tenant A with foreign keys belonging to Tenant B
  (source ingestion pipelines, alert rules, parent ETL pipelines, mapping templates,
  environment instances) is rejected with validation errors and never creates or re-parents records.
- Authentication & Anonymous Access:
  Unauthenticated requests to all 10.2 endpoints are redirected (302) to login.
- HTTP Method Enforcement:
  Delete, trigger, and promote action routes enforce POST-only (@require_POST), returning 405 Method Not Allowed on GET.
- Tenant Admin Authorization:
  Non-admin workspace members (is_tenant_admin=False) are rejected with 403 Forbidden
  on privileged delete and promote endpoints (@tenant_admin_required).
"""
import pytest
from django.urls import reverse

from apps.bi.forms import EtlPipelineRunForm
from apps.bi.models import (
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    TransformationStep,
)
from apps.core.models.Backup import EnvironmentInstance
from apps.core.models.Integration import MappingTemplate
from apps.core.models.Monitoring import AlertRule, ServiceComponent

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Module Helpers (must be prefixed with _etlpipelines_)
# ---------------------------------------------------------------------------


def _etlpipelines_body(response):
    """Helper to decode response content as text."""
    return response.content.decode("utf-8", "replace")


def _etlpipelines_create_alert_rule(tenant, name="Test Alert Rule"):
    """Helper to create a tenant-scoped AlertRule with parent ServiceComponent."""
    service = ServiceComponent.objects.create(tenant=tenant, name=f"{name} Service")
    return AlertRule.objects.create(tenant=tenant, service=service, name=name)


def _etlpipelines_create_environment_instance(tenant, name="Test Environment"):
    """Helper to create a tenant-scoped EnvironmentInstance."""
    return EnvironmentInstance.objects.create(tenant=tenant, name=name)


def _etlpipelines_create_mapping_template(tenant, name="Test Mapping Template"):
    """Helper to create a tenant-scoped MappingTemplate."""
    return MappingTemplate.objects.create(tenant=tenant, name=name)


def _etlpipelines_create_draft_version(tenant, pipeline, version_number="v0.9.9"):
    """Helper to create a non-active draft version."""
    return EtlPipelineVersion.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        version_number=version_number,
        environment="development",
        status="draft",
        changelog="Draft test version",
    )


# ===========================================================================
# 1. Cross-Tenant IDOR (Insecure Direct Object Reference)
# ===========================================================================


def test_etlpipelines_cross_tenant_idor_pipeline_routes(
    client_a,
    etl_pipeline_b,
):
    """Tenant A admin cannot access or mutate Tenant B's ETL pipeline via IDOR."""
    # Detail
    url_detail = reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_b.pk})
    assert client_a.get(url_detail).status_code == 404
    assert client_a.post(url_detail).status_code == 404

    # Canvas
    url_canvas = reverse("bi:etl_pipeline_canvas", kwargs={"pk": etl_pipeline_b.pk})
    assert client_a.get(url_canvas).status_code == 404
    assert client_a.post(url_canvas).status_code == 404

    # Edit
    url_edit = reverse("bi:etl_pipeline_edit", kwargs={"pk": etl_pipeline_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, data={"name": "Hacked Name"}).status_code == 404

    # Delete (POST-only route: POST must return 404 IDOR, GET returns 405 Method Not Allowed)
    url_delete = reverse("bi:etl_pipeline_delete", kwargs={"pk": etl_pipeline_b.pk})
    assert client_a.post(url_delete).status_code == 404
    assert client_a.get(url_delete).status_code == 405

    # Trigger (POST-only route: POST must return 404 IDOR, GET returns 405 Method Not Allowed)
    url_trigger = reverse("bi:etl_pipeline_trigger", kwargs={"pk": etl_pipeline_b.pk})
    assert client_a.post(url_trigger).status_code == 404
    assert client_a.get(url_trigger).status_code == 405

    # Assert object still exists and was not altered
    etl_pipeline_b.refresh_from_db()
    assert etl_pipeline_b.name == "Globex Invoices Daily Mart"
    assert not etl_pipeline_b.runs.filter(trigger_type="manual", status="running").exists()


def test_etlpipelines_cross_tenant_idor_step_routes(
    client_a,
    etl_step_b,
):
    """Tenant A admin cannot access or mutate Tenant B's TransformationStep via IDOR."""
    # Detail
    url_detail = reverse("bi:transformation_step_detail", kwargs={"pk": etl_step_b.pk})
    assert client_a.get(url_detail).status_code == 404
    assert client_a.post(url_detail).status_code == 404

    # Edit
    url_edit = reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, data={"name": "Hacked Step"}).status_code == 404

    # Delete (POST-only: POST must return 404, GET returns 405)
    url_delete = reverse("bi:transformation_step_delete", kwargs={"pk": etl_step_b.pk})
    assert client_a.post(url_delete).status_code == 404
    assert client_a.get(url_delete).status_code == 405

    # Assert step still exists and was not renamed or deleted
    etl_step_b.refresh_from_db()
    assert etl_step_b.name == "Globex Customer Join"


def test_etlpipelines_cross_tenant_idor_version_routes(
    client_a,
    etl_version_b,
):
    """Tenant A admin cannot access or mutate Tenant B's EtlPipelineVersion via IDOR."""
    # Detail
    url_detail = reverse("bi:etl_pipeline_version_detail", kwargs={"pk": etl_version_b.pk})
    assert client_a.get(url_detail).status_code == 404
    assert client_a.post(url_detail).status_code == 404

    # Edit
    url_edit = reverse("bi:etl_pipeline_version_edit", kwargs={"pk": etl_version_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, data={"version_number": "v9.9.9"}).status_code == 404

    # Delete (POST-only: POST must return 404, GET returns 405)
    url_delete = reverse("bi:etl_pipeline_version_delete", kwargs={"pk": etl_version_b.pk})
    assert client_a.post(url_delete).status_code == 404
    assert client_a.get(url_delete).status_code == 405

    # Promote (POST-only: POST must return 404, GET returns 405)
    url_promote = reverse("bi:etl_pipeline_version_promote", kwargs={"pk": etl_version_b.pk})
    assert client_a.post(url_promote, data={"target_environment": "staging"}).status_code == 404
    assert client_a.get(url_promote).status_code == 405

    # Assert version was not altered
    etl_version_b.refresh_from_db()
    assert etl_version_b.version_number == "v1.0.0"


def test_etlpipelines_cross_tenant_idor_run_routes(
    client_a,
    etl_run_b,
):
    """Tenant A admin cannot access Tenant B's EtlPipelineRun execution logs or details."""
    url_detail = reverse("bi:etl_pipeline_run_detail", kwargs={"pk": etl_run_b.pk})
    assert client_a.get(url_detail).status_code == 404
    assert client_a.post(url_detail).status_code == 404


def test_etlpipelines_cross_tenant_idor_reverse_b_to_a(
    client_b,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
    etl_run_a,
):
    """Tenant B admin cannot access Tenant A's objects across any detail, edit, or action route."""
    routes_and_objects = [
        (reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk}), "get"),
        (reverse("bi:etl_pipeline_canvas", kwargs={"pk": etl_pipeline_a.pk}), "get"),
        (reverse("bi:etl_pipeline_edit", kwargs={"pk": etl_pipeline_a.pk}), "get"),
        (reverse("bi:etl_pipeline_delete", kwargs={"pk": etl_pipeline_a.pk}), "post"),
        (reverse("bi:etl_pipeline_trigger", kwargs={"pk": etl_pipeline_a.pk}), "post"),
        (reverse("bi:transformation_step_detail", kwargs={"pk": etl_step_a.pk}), "get"),
        (reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_a.pk}), "get"),
        (reverse("bi:transformation_step_delete", kwargs={"pk": etl_step_a.pk}), "post"),
        (reverse("bi:etl_pipeline_version_detail", kwargs={"pk": etl_version_a.pk}), "get"),
        (reverse("bi:etl_pipeline_version_edit", kwargs={"pk": etl_version_a.pk}), "get"),
        (reverse("bi:etl_pipeline_version_delete", kwargs={"pk": etl_version_a.pk}), "post"),
        (reverse("bi:etl_pipeline_version_promote", kwargs={"pk": etl_version_a.pk}), "post"),
        (reverse("bi:etl_pipeline_run_detail", kwargs={"pk": etl_run_a.pk}), "get"),
    ]
    for url, method in routes_and_objects:
        if method == "get":
            res = client_b.get(url)
        else:
            res = client_b.post(url)
        assert res.status_code == 404, f"Tenant B accessed Tenant A resource via {method.upper()} {url}"


# ===========================================================================
# 2. Cross-Tenant Data Isolation in Lists
# ===========================================================================


def test_etlpipelines_list_isolation_pipeline_list(
    client_a,
    etl_pipeline_a,
    etl_pipeline_b,
):
    """Tenant A's pipeline list never displays or leaks Tenant B's pipelines."""
    url = reverse("bi:etl_pipeline_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    body = _etlpipelines_body(resp)
    assert etl_pipeline_a.name in body
    assert etl_pipeline_b.name not in body
    assert "Globex" not in body

    # Context items must belong exclusively to Tenant A
    pipelines_in_context = list(resp.context["pipelines"])
    assert etl_pipeline_a in pipelines_in_context
    assert etl_pipeline_b not in pipelines_in_context
    assert etl_pipeline_b.pk not in [p.pk for p in pipelines_in_context]
    for p in pipelines_in_context:
        assert p.tenant_id == etl_pipeline_a.tenant_id

    # Targeted search for Tenant B's name returns empty, never leaks
    resp_search = client_a.get(url, {"q": "Globex"})
    assert resp_search.status_code == 200
    assert len(resp_search.context["pipelines"]) == 0
    assert etl_pipeline_b.name not in _etlpipelines_body(resp_search)

    # CSV Export never includes Tenant B's data
    resp_csv = client_a.get(url, {"export": "csv"})
    assert resp_csv.status_code == 200
    csv_body = _etlpipelines_body(resp_csv)
    assert etl_pipeline_a.name in csv_body
    assert etl_pipeline_b.name not in csv_body
    assert "Globex" not in csv_body


def test_etlpipelines_list_isolation_step_list(
    client_a,
    etl_step_a,
    etl_step_b,
    etl_pipeline_b,
):
    """Tenant A's transformation step list never displays Tenant B's steps."""
    url = reverse("bi:transformation_step_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    body = _etlpipelines_body(resp)
    assert etl_step_a.name in body
    assert etl_step_b.name not in body
    assert "Globex" not in body

    steps_in_context = list(resp.context["steps"])
    assert etl_step_a in steps_in_context
    assert etl_step_b not in steps_in_context
    assert etl_step_b.pk not in [s.pk for s in steps_in_context]
    for s in steps_in_context:
        assert s.tenant_id == etl_step_a.tenant_id

    # Pipeline dropdown only contains Tenant A pipelines
    dropdown_pipelines = list(resp.context["pipelines"])
    assert etl_pipeline_b not in dropdown_pipelines
    assert etl_pipeline_b.pk not in [p.pk for p in dropdown_pipelines]

    # Filtering by Tenant B's pipeline returns empty list
    resp_filter = client_a.get(url, {"pipeline_id": etl_pipeline_b.pk})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["steps"]) == 0

    # CSV Export does not contain Tenant B steps
    resp_csv = client_a.get(url, {"export": "csv"})
    csv_body = _etlpipelines_body(resp_csv)
    assert etl_step_a.name in csv_body
    assert etl_step_b.name not in csv_body
    assert "Globex" not in csv_body


def test_etlpipelines_list_isolation_version_list(
    client_a,
    etl_version_a,
    etl_version_b,
    etl_pipeline_b,
):
    """Tenant A's pipeline version list never displays Tenant B's versions."""
    url = reverse("bi:etl_pipeline_version_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    body = _etlpipelines_body(resp)
    assert etl_version_a.version_number in body
    assert etl_version_b.changelog not in body
    assert "Globex" not in body

    versions_in_context = list(resp.context["versions"])
    assert etl_version_a in versions_in_context
    assert etl_version_b not in versions_in_context
    assert etl_version_b.pk not in [v.pk for v in versions_in_context]
    for v in versions_in_context:
        assert v.tenant_id == etl_version_a.tenant_id

    # Pipeline dropdown only contains Tenant A pipelines
    dropdown_pipelines = list(resp.context["pipelines"])
    assert etl_pipeline_b not in dropdown_pipelines
    assert etl_pipeline_b.pk not in [p.pk for p in dropdown_pipelines]

    # Filtering by Tenant B's pipeline returns empty
    resp_filter = client_a.get(url, {"pipeline_id": etl_pipeline_b.pk})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["versions"]) == 0

    # CSV Export does not contain Tenant B versions
    resp_csv = client_a.get(url, {"export": "csv"})
    csv_body = _etlpipelines_body(resp_csv)
    assert etl_version_a.version_number in csv_body
    assert etl_version_b.changelog not in csv_body
    assert "Globex" not in csv_body


def test_etlpipelines_list_isolation_run_list(
    client_a,
    etl_run_a,
    etl_run_b,
    etl_pipeline_a,
    etl_pipeline_b,
):
    """Tenant A's pipeline run list never displays Tenant B's runs."""
    url = reverse("bi:etl_pipeline_run_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    body = _etlpipelines_body(resp)
    assert etl_pipeline_a.name in body
    assert etl_pipeline_b.name not in body
    assert "Globex" not in body

    runs_in_context = list(resp.context["runs"])
    assert etl_run_a in runs_in_context
    assert etl_run_b not in runs_in_context
    assert etl_run_b.pk not in [r.pk for r in runs_in_context]
    for r in runs_in_context:
        assert r.tenant_id == etl_run_a.tenant_id

    # Filtering by Tenant B's pipeline returns empty
    resp_filter = client_a.get(url, {"pipeline_id": etl_pipeline_b.pk})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["runs"]) == 0

    # CSV Export does not contain Tenant B runs
    resp_csv = client_a.get(url, {"export": "csv"})
    csv_body = _etlpipelines_body(resp_csv)
    assert etl_pipeline_a.name in csv_body
    assert etl_pipeline_b.name not in csv_body
    assert "Globex" not in csv_body


def test_etlpipelines_list_isolation_reverse_tenant_b(
    client_b,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
    etl_run_a,
):
    """Tenant B never sees Tenant A's objects in any of its 10.2 list views or CSV exports."""
    list_routes = [
        (reverse("bi:etl_pipeline_list"), etl_pipeline_a.name),
        (reverse("bi:transformation_step_list"), etl_step_a.name),
        (reverse("bi:etl_pipeline_version_list"), etl_version_a.changelog),
        (reverse("bi:etl_pipeline_run_list"), etl_pipeline_a.name),
    ]
    for url, tenant_a_identifier in list_routes:
        # Standard list
        resp = client_b.get(url)
        assert resp.status_code == 200
        assert tenant_a_identifier not in _etlpipelines_body(resp)

        # CSV export
        resp_csv = client_b.get(url, {"export": "csv"})
        assert resp_csv.status_code == 200
        assert tenant_a_identifier not in _etlpipelines_body(resp_csv)
        resp_csv = client_b.get(url, {"export": "csv"})
        assert resp_csv.status_code == 200
        assert tenant_a_identifier not in _etlpipelines_body(resp_csv)


# ===========================================================================
# 3. Cross-Tenant Foreign Key Tampering / Injection
# ===========================================================================


def test_etlpipelines_fk_tampering_pipeline_create_foreign_source(
    client_a,
    bi_pipeline_b,
):
    """Submitting EtlPipeline create with Tenant B source_ingestion_pipeline is rejected."""
    url = reverse("bi:etl_pipeline_create")
    data = {
        "name": "Malicious Pipeline Injection",
        "source_ingestion_pipeline": bi_pipeline_b.pk,
        "source_staging_table": "stg_accounting_invoices",
        "target_table": "fact_malicious",
        "target_layer": "warehouse_fact",
        "trigger_type": "manual",
        "sla_timeout_seconds": 3600,
        "status": "draft",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    assert "form" in resp.context
    form = resp.context["form"]
    assert not form.is_valid()
    assert "source_ingestion_pipeline" in form.errors

    # Verify no record was created linking to bi_pipeline_b
    assert not EtlPipeline.objects.filter(source_ingestion_pipeline=bi_pipeline_b).exists()


def test_etlpipelines_fk_tampering_pipeline_create_foreign_alert_rule(
    client_a,
    tenant_b,
):
    """Submitting EtlPipeline create with Tenant B alert_rule is rejected."""
    foreign_alert = _etlpipelines_create_alert_rule(tenant_b, "Foreign Alert Rule")
    url = reverse("bi:etl_pipeline_create")
    data = {
        "name": "Malicious Alert Rule Pipeline",
        "alert_rule": foreign_alert.pk,
        "target_table": "fact_malicious_alert",
        "target_layer": "warehouse_fact",
        "trigger_type": "manual",
        "sla_timeout_seconds": 3600,
        "status": "draft",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "alert_rule" in form.errors

    assert not EtlPipeline.objects.filter(alert_rule=foreign_alert).exists()


def test_etlpipelines_fk_tampering_pipeline_edit_foreign_source(
    client_a,
    etl_pipeline_a,
    bi_pipeline,
    bi_pipeline_b,
):
    """Editing EtlPipeline to point to Tenant B's source_ingestion_pipeline is rejected."""
    url = reverse("bi:etl_pipeline_edit", kwargs={"pk": etl_pipeline_a.pk})
    data = {
        "name": etl_pipeline_a.name,
        "source_ingestion_pipeline": bi_pipeline_b.pk,
        "source_staging_table": etl_pipeline_a.source_staging_table,
        "target_table": etl_pipeline_a.target_table,
        "target_layer": etl_pipeline_a.target_layer,
        "trigger_type": "scheduled_cron",
        "cron_expression": "0 2 * * *",
        "sla_timeout_seconds": 3600,
        "status": etl_pipeline_a.status,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "source_ingestion_pipeline" in form.errors

    # Verify pipeline was not altered to foreign connector/pipeline
    etl_pipeline_a.refresh_from_db()
    assert etl_pipeline_a.source_ingestion_pipeline_id == bi_pipeline.pk


def test_etlpipelines_fk_tampering_step_create_foreign_pipeline(
    client_a,
    etl_pipeline_b,
):
    """Submitting TransformationStep create with Tenant B pipeline is rejected."""
    url = reverse("bi:transformation_step_create")
    data = {
        "pipeline": etl_pipeline_b.pk,
        "name": "Malicious Cross-Tenant Step",
        "step_type": "join",
        "sequence": 1,
        "status": "active",
        "is_blocking": True,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "pipeline" in form.errors

    assert not TransformationStep.objects.filter(name="Malicious Cross-Tenant Step").exists()


def test_etlpipelines_fk_tampering_step_create_foreign_mapping_template(
    client_a,
    etl_pipeline_a,
    tenant_b,
):
    """Submitting TransformationStep create with Tenant B mapping_template is rejected."""
    foreign_mapping = _etlpipelines_create_mapping_template(tenant_b, "Foreign Template")
    url = reverse("bi:transformation_step_create")
    data = {
        "pipeline": etl_pipeline_a.pk,
        "mapping_template": foreign_mapping.pk,
        "name": "Malicious Template Step",
        "step_type": "column_mapping",
        "sequence": 2,
        "status": "active",
        "is_blocking": True,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "mapping_template" in form.errors

    assert not TransformationStep.objects.filter(mapping_template=foreign_mapping).exists()


def test_etlpipelines_fk_tampering_step_edit_foreign_pipeline(
    client_a,
    etl_step_a,
    etl_pipeline_a,
    etl_pipeline_b,
):
    """Editing TransformationStep to reparent to Tenant B's pipeline is rejected."""
    url = reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_a.pk})
    data = {
        "pipeline": etl_pipeline_b.pk,
        "name": etl_step_a.name,
        "step_type": etl_step_a.step_type,
        "sequence": etl_step_a.sequence,
        "status": etl_step_a.status,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "pipeline" in form.errors

    etl_step_a.refresh_from_db()
    assert etl_step_a.pipeline_id == etl_pipeline_a.pk


def test_etlpipelines_fk_tampering_step_edit_foreign_mapping_template(
    client_a,
    etl_step_a,
    etl_pipeline_a,
    tenant_b,
):
    """Editing TransformationStep to attach Tenant B's mapping_template is rejected."""
    foreign_mapping = _etlpipelines_create_mapping_template(tenant_b, "Foreign Template Edit")
    url = reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_a.pk})
    data = {
        "pipeline": etl_pipeline_a.pk,
        "mapping_template": foreign_mapping.pk,
        "name": etl_step_a.name,
        "step_type": etl_step_a.step_type,
        "sequence": etl_step_a.sequence,
        "status": etl_step_a.status,
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "mapping_template" in form.errors

    etl_step_a.refresh_from_db()
    assert etl_step_a.mapping_template_id != foreign_mapping.pk


def test_etlpipelines_fk_tampering_version_create_foreign_pipeline(
    client_a,
    etl_pipeline_b,
):
    """Submitting EtlPipelineVersion create with Tenant B pipeline is rejected."""
    url = reverse("bi:etl_pipeline_version_create")
    data = {
        "pipeline": etl_pipeline_b.pk,
        "version_number": "v9.0.0",
        "environment": "development",
        "status": "draft",
        "changelog": "Tampered pipeline version",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "pipeline" in form.errors

    assert not EtlPipelineVersion.objects.filter(version_number="v9.0.0").exists()


def test_etlpipelines_fk_tampering_version_create_foreign_environment(
    client_a,
    etl_pipeline_a,
    tenant_b,
):
    """Submitting EtlPipelineVersion create with Tenant B environment_instance is rejected."""
    foreign_env = _etlpipelines_create_environment_instance(tenant_b, "Foreign Staging Env")
    url = reverse("bi:etl_pipeline_version_create")
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v2.5.0",
        "environment": "staging",
        "environment_instance": foreign_env.pk,
        "status": "draft",
        "changelog": "Tampered environment version",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "environment_instance" in form.errors

    assert not EtlPipelineVersion.objects.filter(version_number="v2.5.0").exists()


def test_etlpipelines_fk_tampering_version_edit_foreign_pipeline(
    client_a,
    tenant_a,
    etl_pipeline_a,
    etl_pipeline_b,
):
    """Editing EtlPipelineVersion to reparent to Tenant B pipeline is rejected."""
    draft_ver = _etlpipelines_create_draft_version(tenant_a, etl_pipeline_a, "v0.8.0")
    url = reverse("bi:etl_pipeline_version_edit", kwargs={"pk": draft_ver.pk})
    data = {
        "pipeline": etl_pipeline_b.pk,
        "version_number": draft_ver.version_number,
        "environment": draft_ver.environment,
        "status": draft_ver.status,
        "changelog": "Attempted pipeline reparenting",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "pipeline" in form.errors

    draft_ver.refresh_from_db()
    assert draft_ver.pipeline_id == etl_pipeline_a.pk


def test_etlpipelines_fk_tampering_run_form_foreign_pipeline_and_version(
    tenant_a,
    etl_pipeline_a,
    etl_pipeline_b,
    etl_version_a,
    etl_version_b,
):
    """EtlPipelineRunForm strictly rejects foreign pipeline and foreign version."""
    # 1. Foreign pipeline
    form_foreign_pipeline = EtlPipelineRunForm(
        data={"pipeline": etl_pipeline_b.pk, "version": etl_version_a.pk, "trigger_type": "manual"},
        tenant=tenant_a,
    )
    assert not form_foreign_pipeline.is_valid()
    assert "pipeline" in form_foreign_pipeline.errors

    # 2. Foreign version
    form_foreign_version = EtlPipelineRunForm(
        data={"pipeline": etl_pipeline_a.pk, "version": etl_version_b.pk, "trigger_type": "manual"},
        tenant=tenant_a,
    )
    assert not form_foreign_version.is_valid()
    assert "version" in form_foreign_version.errors


# ===========================================================================
# 4. Authentication / Anonymous Access Redirection
# ===========================================================================


def test_etlpipelines_anonymous_access_redirects_all_get_routes(
    anon_client,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
    etl_run_a,
):
    """Anonymous user accessing any 10.2 GET view is redirected to login."""
    get_routes = [
        reverse("bi:etl_pipeline_list"),
        reverse("bi:etl_pipeline_create"),
        reverse("bi:etl_pipeline_detail", kwargs={"pk": etl_pipeline_a.pk}),
        reverse("bi:etl_pipeline_canvas", kwargs={"pk": etl_pipeline_a.pk}),
        reverse("bi:etl_pipeline_edit", kwargs={"pk": etl_pipeline_a.pk}),
        reverse("bi:transformation_step_list"),
        reverse("bi:transformation_step_create"),
        reverse("bi:transformation_step_detail", kwargs={"pk": etl_step_a.pk}),
        reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_a.pk}),
        reverse("bi:etl_pipeline_version_list"),
        reverse("bi:etl_pipeline_version_create"),
        reverse("bi:etl_pipeline_version_detail", kwargs={"pk": etl_version_a.pk}),
        reverse("bi:etl_pipeline_version_edit", kwargs={"pk": etl_version_a.pk}),
        reverse("bi:etl_pipeline_run_list"),
        reverse("bi:etl_pipeline_run_detail", kwargs={"pk": etl_run_a.pk}),
    ]
    for url in get_routes:
        res = anon_client.get(url)
        assert res.status_code == 302, f"Route {url} failed to redirect anonymous GET request"
        assert "/accounts/login" in res.url or "login" in res.url


def test_etlpipelines_anonymous_access_redirects_all_post_routes(
    anon_client,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
):
    """Anonymous user submitting POST to any 10.2 mutation route is redirected to login."""
    post_routes = [
        (reverse("bi:etl_pipeline_create"), {"name": "Anon Pipe"}),
        (reverse("bi:etl_pipeline_edit", kwargs={"pk": etl_pipeline_a.pk}), {"name": "Anon Edit"}),
        (reverse("bi:etl_pipeline_delete", kwargs={"pk": etl_pipeline_a.pk}), {}),
        (reverse("bi:etl_pipeline_trigger", kwargs={"pk": etl_pipeline_a.pk}), {}),
        (reverse("bi:transformation_step_create"), {"name": "Anon Step"}),
        (reverse("bi:transformation_step_edit", kwargs={"pk": etl_step_a.pk}), {"name": "Anon Step Edit"}),
        (reverse("bi:transformation_step_delete", kwargs={"pk": etl_step_a.pk}), {}),
        (reverse("bi:etl_pipeline_version_create"), {"version_number": "v1.1.1"}),
        (reverse("bi:etl_pipeline_version_edit", kwargs={"pk": etl_version_a.pk}), {"version_number": "v1.1.2"}),
        (reverse("bi:etl_pipeline_version_delete", kwargs={"pk": etl_version_a.pk}), {}),
        (reverse("bi:etl_pipeline_version_promote", kwargs={"pk": etl_version_a.pk}), {"target_environment": "staging"}),
    ]
    for url, data in post_routes:
        res = anon_client.post(url, data)
        assert res.status_code == 302, f"Route {url} failed to redirect anonymous POST request"
        assert "/accounts/login" in res.url or "login" in res.url


# ===========================================================================
# 5. Method Not Allowed (405 on POST-only Routes)
# ===========================================================================


def test_etlpipelines_method_not_allowed_on_delete_and_action_routes(
    client_a,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
):
    """GET requests to delete, trigger, or promote endpoints return 405 Method Not Allowed."""
    post_only_routes = [
        reverse("bi:etl_pipeline_delete", kwargs={"pk": etl_pipeline_a.pk}),
        reverse("bi:etl_pipeline_trigger", kwargs={"pk": etl_pipeline_a.pk}),
        reverse("bi:transformation_step_delete", kwargs={"pk": etl_step_a.pk}),
        reverse("bi:etl_pipeline_version_delete", kwargs={"pk": etl_version_a.pk}),
        reverse("bi:etl_pipeline_version_promote", kwargs={"pk": etl_version_a.pk}),
    ]
    for url in post_only_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {res.status_code}"

    # Verify no unintended mutations occurred
    assert EtlPipeline.objects.filter(pk=etl_pipeline_a.pk).exists()
    assert TransformationStep.objects.filter(pk=etl_step_a.pk).exists()
    assert EtlPipelineVersion.objects.filter(pk=etl_version_a.pk).exists()


# ===========================================================================
# 6. Tenant Admin Authorization (Role-Based Access Control)
# ===========================================================================


def test_etlpipelines_tenant_admin_required_gates_privileged_actions(
    member_client,
    etl_pipeline_a,
    etl_step_a,
    etl_version_a,
):
    """Non-admin workspace members (is_tenant_admin=False) are rejected with 403 Forbidden."""
    privileged_routes = [
        (reverse("bi:etl_pipeline_delete", kwargs={"pk": etl_pipeline_a.pk}), {}),
        (reverse("bi:transformation_step_delete", kwargs={"pk": etl_step_a.pk}), {}),
        (reverse("bi:etl_pipeline_version_delete", kwargs={"pk": etl_version_a.pk}), {}),
        (reverse("bi:etl_pipeline_version_promote", kwargs={"pk": etl_version_a.pk}), {"target_environment": "staging"}),
    ]
    for url, data in privileged_routes:
        res = member_client.post(url, data)
        assert res.status_code == 403, f"Expected 403 Forbidden for non-admin on POST {url}, got {res.status_code}"

    # Confirm objects remain intact in the database
    assert EtlPipeline.objects.filter(pk=etl_pipeline_a.pk).exists()
    assert TransformationStep.objects.filter(pk=etl_step_a.pk).exists()
    assert EtlPipelineVersion.objects.filter(pk=etl_version_a.pk).exists()
