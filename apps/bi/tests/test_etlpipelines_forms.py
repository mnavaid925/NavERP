"""Unit tests for Sub-module 10.2 forms (EtlPipelineForm, TransformationStepForm, EtlPipelineVersionForm, EtlPipelineRunForm)."""
import pytest

from apps.bi.forms import (
    EtlPipelineForm,
    EtlPipelineRunForm,
    EtlPipelineVersionForm,
    TransformationStepForm,
)
from apps.bi.models import (
    EtlPipeline,
    EtlPipelineRun,
    EtlPipelineVersion,
    IngestionPipeline,
    TransformationStep,
)
from apps.core.models.Backup import EnvironmentInstance
from apps.core.models.Integration import MappingTemplate
from apps.core.models.Monitoring import AlertRule, ServiceComponent


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


# ===========================================================================
# 1. EtlPipelineForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_system_field_exclusions(tenant_a):
    """Verify EtlPipelineForm excludes internal system fields from mass assignment."""
    form = EtlPipelineForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "canvas_layout",
        "active_version",
        "last_run_at",
        "next_run_due_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from EtlPipelineForm"


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_valid_creation(tenant_a, bi_pipeline):
    """Verify valid EtlPipelineForm submission parses raw JSON and assigns tenant."""
    data = {
        "name": "Fact Sales Aggregator",
        "description": "Daily fact table pipeline",
        "source_ingestion_pipeline": bi_pipeline.pk,
        "source_staging_table": "stg_accounting_invoices",
        "target_table": "fact_daily_sales",
        "target_layer": "warehouse_fact",
        "trigger_type": "scheduled_cron",
        "cron_expression": "0 2 * * *",
        "sla_timeout_seconds": 7200,
        "alert_on_sla_miss": True,
        "status": "active",
        "upstream_dependencies_raw": '["BETL-00001", "BETL-00002"]',
        "retry_policy_raw": '{"max_retries": 3, "retry_delay_seconds": 60, "backoff_factor": 2}',
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.name == "Fact Sales Aggregator"
    assert instance.upstream_dependencies == ["BETL-00001", "BETL-00002"]
    assert instance.retry_policy == {
        "max_retries": 3,
        "retry_delay_seconds": 60,
        "backoff_factor": 2,
    }


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_empty_json_raw_defaults(tenant_a):
    """Verify empty raw JSON strings default to empty list and dict respectively."""
    data = {
        "name": "Manual Ingest Pipe",
        "target_table": "stg_sales",
        "target_layer": "staging",
        "trigger_type": "manual",
        "cron_expression": "",
        "sla_timeout_seconds": 3600,
        "status": "draft",
        "upstream_dependencies_raw": "   ",
        "retry_policy_raw": "",
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.upstream_dependencies == []
    assert instance.retry_policy == {}


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_invalid_json_upstream_dependencies(tenant_a):
    """Verify malformed JSON in upstream_dependencies_raw raises validation error."""
    data = {
        "name": "Broken JSON Pipe",
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "manual",
        "upstream_dependencies_raw": "{broken_json: true}",
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "upstream_dependencies_raw" in form.errors
    assert "Invalid JSON" in str(form.errors["upstream_dependencies_raw"])


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_non_list_json_upstream_dependencies(tenant_a):
    """Verify non-list JSON in upstream_dependencies_raw raises array validation error."""
    data = {
        "name": "Dict Upstream Pipe",
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "manual",
        "upstream_dependencies_raw": '{"upstream": "BETL-00001"}',
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "upstream_dependencies_raw" in form.errors
    assert "Must be a valid JSON array" in str(form.errors["upstream_dependencies_raw"])


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_invalid_json_retry_policy(tenant_a):
    """Verify malformed JSON in retry_policy_raw raises validation error."""
    data = {
        "name": "Broken Retry Pipe",
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "manual",
        "retry_policy_raw": "[broken",
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "retry_policy_raw" in form.errors
    assert "Invalid JSON" in str(form.errors["retry_policy_raw"])


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_non_dict_json_retry_policy(tenant_a):
    """Verify non-dict JSON in retry_policy_raw raises object validation error."""
    data = {
        "name": "List Retry Pipe",
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "manual",
        "retry_policy_raw": '["max_retries", 3]',
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "retry_policy_raw" in form.errors
    assert "Must be a valid JSON object" in str(form.errors["retry_policy_raw"])


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_cron_required_for_scheduled_cron(tenant_a):
    """Verify cron_expression is required when trigger_type is scheduled_cron."""
    data = {
        "name": "Cron Without Expr",
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "scheduled_cron",
        "cron_expression": "   ",
        "status": "active",
    }
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cron_expression" in form.errors
    assert "Cron expression is required when trigger type is scheduled cron." in form.errors["cron_expression"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_cron_optional_for_non_cron_triggers(tenant_a):
    """Verify non-cron triggers allow blank cron_expression."""
    for trigger in ["manual", "event_on_ingest", "dependency_chained"]:
        data = {
            "name": f"Non Cron Pipe ({trigger})",
            "target_table": "fact_sales",
            "target_layer": "warehouse_fact",
            "sla_timeout_seconds": 3600,
            "trigger_type": trigger,
            "cron_expression": "",
            "status": "draft",
        }
        form = EtlPipelineForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected valid for trigger_type {trigger}, got {form.errors}"


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_reject_foreign_source_ingestion_pipeline(tenant_a, bi_pipeline_b):
    """Verify EtlPipelineForm rejects source_ingestion_pipeline from foreign tenant."""
    data = {
        "name": "Foreign Pipe Test",
        "source_ingestion_pipeline": bi_pipeline_b.pk,
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "manual",
    }
    # Scoped queryset rejects at field level
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "source_ingestion_pipeline" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = EtlPipelineForm(data=data, tenant=tenant_a)
    form_wide.fields["source_ingestion_pipeline"].queryset = IngestionPipeline.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["source_ingestion_pipeline"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_reject_foreign_alert_rule(tenant_a, tenant_b):
    """Verify EtlPipelineForm rejects alert_rule from foreign tenant."""
    foreign_alert = _etlpipelines_create_alert_rule(tenant_b, "Foreign Alert Rule")
    data = {
        "name": "Foreign Alert Test",
        "alert_rule": foreign_alert.pk,
        "target_table": "fact_sales",
        "target_layer": "warehouse_fact",
        "sla_timeout_seconds": 3600,
        "trigger_type": "manual",
    }
    # Scoped queryset rejects at field level
    form = EtlPipelineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "alert_rule" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = EtlPipelineForm(data=data, tenant=tenant_a)
    form_wide.fields["alert_rule"].queryset = AlertRule.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["alert_rule"]


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_queryset_scoping(tenant_a, tenant_b, bi_pipeline, bi_pipeline_b):
    """Verify choice querysets are scoped to form tenant."""
    alert_a = _etlpipelines_create_alert_rule(tenant_a, "Alert Acme")
    alert_b = _etlpipelines_create_alert_rule(tenant_b, "Alert Globex")

    form = EtlPipelineForm(tenant=tenant_a)
    pipe_qs = form.fields["source_ingestion_pipeline"].queryset
    alert_qs = form.fields["alert_rule"].queryset

    assert bi_pipeline in pipe_qs
    assert bi_pipeline_b not in pipe_qs
    assert alert_a in alert_qs
    assert alert_b not in alert_qs


@pytest.mark.django_db
def test_etlpipelines_pipeline_form_initial_data_on_edit(tenant_a, etl_pipeline_a):
    """Verify existing JSON values are formatted into raw initial textareas."""
    etl_pipeline_a.upstream_dependencies = ["BETL-00100", "BETL-00200"]
    etl_pipeline_a.retry_policy = {"max_retries": 5, "retry_delay_seconds": 120}
    etl_pipeline_a.save()

    form = EtlPipelineForm(instance=etl_pipeline_a, tenant=tenant_a)
    assert "BETL-00100" in form.fields["upstream_dependencies_raw"].initial
    assert "max_retries" in form.fields["retry_policy_raw"].initial


# ===========================================================================
# 2. TransformationStepForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_system_field_exclusions(tenant_a):
    """Verify TransformationStepForm excludes internal system fields from mass assignment."""
    form = TransformationStepForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "canvas_x",
        "canvas_y",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from TransformationStepForm"


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_valid_creation(tenant_a, etl_pipeline_a):
    """Verify valid TransformationStepForm submission parses raw JSON and assigns tenant."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Join Dim Customer",
        "step_type": "join",
        "sequence": 2,
        "status": "active",
        "is_blocking": True,
        "description": "Inner join on customer ID",
        "upstream_step_ids_raw": '["BTRN-00001"]',
        "step_config_raw": '{"join_type": "inner", "left_on": "customer_id", "right_on": "id"}',
    }
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.pipeline == etl_pipeline_a
    assert instance.upstream_step_ids == ["BTRN-00001"]
    assert instance.step_config == {
        "join_type": "inner",
        "left_on": "customer_id",
        "right_on": "id",
    }


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_empty_json_raw_defaults(tenant_a, etl_pipeline_a):
    """Verify empty raw JSON strings default to empty list and dict respectively."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Cast Types Step",
        "step_type": "cast",
        "sequence": 1,
        "status": "active",
        "upstream_step_ids_raw": "",
        "step_config_raw": "   ",
    }
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.upstream_step_ids == []
    assert instance.step_config == {}


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_invalid_json_upstream_step_ids(tenant_a, etl_pipeline_a):
    """Verify malformed JSON in upstream_step_ids_raw raises validation error."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Step Broken JSON",
        "step_type": "filter",
        "sequence": 1,
        "status": "active",
        "upstream_step_ids_raw": "[unclosed",
    }
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "upstream_step_ids_raw" in form.errors
    assert "Invalid JSON" in str(form.errors["upstream_step_ids_raw"])


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_non_list_json_upstream_step_ids(tenant_a, etl_pipeline_a):
    """Verify non-list JSON in upstream_step_ids_raw raises array validation error."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Step Non-Array",
        "step_type": "filter",
        "sequence": 1,
        "status": "active",
        "upstream_step_ids_raw": '{"step": "BTRN-00001"}',
    }
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "upstream_step_ids_raw" in form.errors
    assert "Must be a valid JSON array" in str(form.errors["upstream_step_ids_raw"])


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_invalid_json_step_config(tenant_a, etl_pipeline_a):
    """Verify malformed JSON in step_config_raw raises validation error."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Step Broken Config",
        "step_type": "aggregate",
        "sequence": 1,
        "status": "active",
        "step_config_raw": "{broken_config",
    }
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "step_config_raw" in form.errors
    assert "Invalid JSON" in str(form.errors["step_config_raw"])


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_non_dict_json_step_config(tenant_a, etl_pipeline_a):
    """Verify non-dict JSON in step_config_raw raises object validation error."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Step Non-Dict Config",
        "step_type": "aggregate",
        "sequence": 1,
        "status": "active",
        "step_config_raw": '["sum", "amount"]',
    }
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "step_config_raw" in form.errors
    assert "Must be a valid JSON object" in str(form.errors["step_config_raw"])


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_reject_foreign_pipeline(tenant_a, etl_pipeline_b):
    """Verify TransformationStepForm rejects pipeline belonging to foreign tenant."""
    data = {
        "pipeline": etl_pipeline_b.pk,
        "name": "Foreign Pipeline Step",
        "step_type": "filter",
        "sequence": 1,
        "status": "active",
    }
    # Scoped queryset rejects at field level
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pipeline" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = TransformationStepForm(data=data, tenant=tenant_a)
    form_wide.fields["pipeline"].queryset = EtlPipeline.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["pipeline"]


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_reject_foreign_mapping_template(tenant_a, tenant_b, etl_pipeline_a):
    """Verify TransformationStepForm rejects mapping_template belonging to foreign tenant."""
    foreign_template = _etlpipelines_create_mapping_template(tenant_b, "Foreign Mapping Template")
    data = {
        "pipeline": etl_pipeline_a.pk,
        "name": "Foreign Template Step",
        "step_type": "business_rule",
        "sequence": 1,
        "mapping_template": foreign_template.pk,
        "status": "active",
    }
    # Scoped queryset rejects at field level
    form = TransformationStepForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "mapping_template" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = TransformationStepForm(data=data, tenant=tenant_a)
    form_wide.fields["mapping_template"].queryset = MappingTemplate.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["mapping_template"]


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_queryset_scoping(tenant_a, tenant_b, etl_pipeline_a, etl_pipeline_b):
    """Verify pipeline and mapping_template querysets are scoped to form tenant."""
    map_a = _etlpipelines_create_mapping_template(tenant_a, "Map Acme")
    map_b = _etlpipelines_create_mapping_template(tenant_b, "Map Globex")

    form = TransformationStepForm(tenant=tenant_a)
    pipe_qs = form.fields["pipeline"].queryset
    map_qs = form.fields["mapping_template"].queryset

    assert etl_pipeline_a in pipe_qs
    assert etl_pipeline_b not in pipe_qs
    assert map_a in map_qs
    assert map_b not in map_qs


@pytest.mark.django_db
def test_etlpipelines_transformation_step_form_initial_data_on_edit(tenant_a, etl_step_a):
    """Verify existing step configuration is formatted into raw initial textareas."""
    etl_step_a.upstream_step_ids = ["BTRN-00005"]
    etl_step_a.step_config = {"filter_col": "status", "operator": "eq", "value": "active"}
    etl_step_a.save()

    form = TransformationStepForm(instance=etl_step_a, tenant=tenant_a)
    assert "BTRN-00005" in form.fields["upstream_step_ids_raw"].initial
    assert "filter_col" in form.fields["step_config_raw"].initial


# ===========================================================================
# 3. EtlPipelineVersionForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_version_form_system_field_exclusions(tenant_a):
    """Verify EtlPipelineVersionForm excludes internal system fields from mass assignment."""
    form = EtlPipelineVersionForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "dag_definition",
        "rollback_source",
        "promoted_by",
        "promoted_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from EtlPipelineVersionForm"


@pytest.mark.django_db
def test_etlpipelines_version_form_valid_semantic_versions(tenant_a, etl_pipeline_a):
    """Verify valid semantic version patterns pass version_number validation."""
    valid_versions = ["v1.0.0", "1.2.3", "v2.0-beta.1", "rel_2026.11", "v0.9.1-rc2"]
    for idx, ver_str in enumerate(valid_versions):
        data = {
            "pipeline": etl_pipeline_a.pk,
            "version_number": ver_str,
            "environment": "staging",
            "status": "draft",
            "changelog": f"Testing valid version {ver_str}",
        }
        form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Expected valid for version_number '{ver_str}', got {form.errors}"
        form.save()


@pytest.mark.django_db
def test_etlpipelines_version_form_invalid_version_number_regex(tenant_a, etl_pipeline_a):
    """Verify malicious or invalid characters in version_number raise regex validation error."""
    invalid_versions = [
        "<script>a</script>",
        "bad version",
        "v1.0@beta",
        "v1.0#patch",
        "v1.0/alpha",
        "v1$0",
        "v1%20",
        "v1*0",
        "v1:0",
    ]
    for bad_ver in invalid_versions:
        data = {
            "pipeline": etl_pipeline_a.pk,
            "version_number": bad_ver,
            "environment": "development",
            "status": "draft",
        }
        form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected invalid for version_number '{bad_ver}'"
        assert "version_number" in form.errors
        assert (
            "Version number can only contain alphanumeric characters, underscores, dots, and hyphens."
            in form.errors["version_number"]
        )


@pytest.mark.django_db
def test_etlpipelines_version_form_duplicate_version_number_same_pipeline_rejected(
    tenant_a, etl_pipeline_a, etl_version_a
):
    """Verify cannot create version with identical version_number for same pipeline."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": etl_version_a.version_number,
        "environment": "development",
        "status": "draft",
    }
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "version_number" in form.errors
    assert f"Version '{etl_version_a.version_number}' already exists for this pipeline." in form.errors["version_number"]


@pytest.mark.django_db
def test_etlpipelines_version_form_duplicate_version_number_different_pipeline_allowed(
    tenant_a, admin_user, etl_pipeline_a, etl_version_a
):
    """Verify same version_number is permitted for different pipelines in same tenant."""
    pipeline_2 = EtlPipeline.objects.create(
        tenant=tenant_a,
        name="Second Pipeline",
        target_table="fact_second",
        created_by=admin_user,
    )
    data = {
        "pipeline": pipeline_2.pk,
        "version_number": etl_version_a.version_number,
        "environment": "development",
        "status": "draft",
    }
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_etlpipelines_version_form_same_version_number_on_instance_edit_allowed(tenant_a, etl_version_a):
    """Verify editing existing version instance allows keeping same version_number."""
    data = {
        "pipeline": etl_version_a.pipeline.pk,
        "version_number": etl_version_a.version_number,
        "environment": etl_version_a.environment,
        "status": etl_version_a.status,
        "changelog": "Updated changelog note",
    }
    form = EtlPipelineVersionForm(data=data, instance=etl_version_a, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_etlpipelines_version_form_dag_definition_raw_valid(tenant_a, etl_pipeline_a):
    """Verify explicit dag_definition_raw JSON object is parsed and saved."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v2.0.0",
        "environment": "staging",
        "status": "draft",
        "dag_definition_raw": '{"engine": "spark", "nodes": ["node_1", "node_2"]}',
    }
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.dag_definition == {"engine": "spark", "nodes": ["node_1", "node_2"]}


@pytest.mark.django_db
def test_etlpipelines_version_form_dag_definition_raw_invalid_json(tenant_a, etl_pipeline_a):
    """Verify malformed JSON in dag_definition_raw raises validation error."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v2.0.1",
        "environment": "staging",
        "status": "draft",
        "dag_definition_raw": '{"unclosed": ',
    }
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dag_definition_raw" in form.errors
    assert "Invalid JSON" in str(form.errors["dag_definition_raw"])


@pytest.mark.django_db
def test_etlpipelines_version_form_dag_definition_raw_non_dict(tenant_a, etl_pipeline_a):
    """Verify non-dict JSON in dag_definition_raw raises object validation error."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v2.0.2",
        "environment": "staging",
        "status": "draft",
        "dag_definition_raw": '["node1", "node2"]',
    }
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dag_definition_raw" in form.errors
    assert "DAG definition must be a valid JSON object." in str(form.errors["dag_definition_raw"])


@pytest.mark.django_db
def test_etlpipelines_version_form_auto_snapshots_steps_when_dag_raw_empty(
    tenant_a, etl_pipeline_a, etl_step_a
):
    """Verify saving version with empty dag_definition_raw snapshots pipeline steps."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v2.1.0",
        "environment": "production",
        "status": "published",
        "dag_definition_raw": "",
    }
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    dag_def = instance.dag_definition

    assert dag_def["pipeline_number"] == etl_pipeline_a.number
    assert dag_def["pipeline_name"] == etl_pipeline_a.name
    assert dag_def["target_table"] == etl_pipeline_a.target_table
    assert len(dag_def["steps"]) == 1
    assert dag_def["steps"][0]["name"] == etl_step_a.name
    assert dag_def["steps"][0]["sequence"] == etl_step_a.sequence


@pytest.mark.django_db
def test_etlpipelines_version_form_reject_foreign_pipeline(tenant_a, etl_pipeline_b):
    """Verify EtlPipelineVersionForm rejects foreign tenant pipeline."""
    data = {
        "pipeline": etl_pipeline_b.pk,
        "version_number": "v1.0.0",
        "environment": "development",
        "status": "draft",
    }
    # Scoped queryset rejects at field level
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pipeline" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    form_wide.fields["pipeline"].queryset = EtlPipeline.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["pipeline"]


@pytest.mark.django_db
def test_etlpipelines_version_form_reject_foreign_environment_instance(tenant_a, tenant_b, etl_pipeline_a):
    """Verify EtlPipelineVersionForm rejects foreign tenant environment instance."""
    foreign_env = _etlpipelines_create_environment_instance(tenant_b, "Globex Staging")
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version_number": "v3.0.0",
        "environment": "staging",
        "environment_instance": foreign_env.pk,
        "status": "draft",
    }
    # Scoped queryset rejects at field level
    form = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "environment_instance" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = EtlPipelineVersionForm(data=data, tenant=tenant_a)
    form_wide.fields["environment_instance"].queryset = EnvironmentInstance.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["environment_instance"]


@pytest.mark.django_db
def test_etlpipelines_version_form_queryset_scoping(tenant_a, tenant_b, etl_pipeline_a, etl_pipeline_b):
    """Verify pipeline and environment_instance querysets are scoped to form tenant."""
    env_a = _etlpipelines_create_environment_instance(tenant_a, "Acme Staging")
    env_b = _etlpipelines_create_environment_instance(tenant_b, "Globex Staging")

    form = EtlPipelineVersionForm(tenant=tenant_a)
    pipe_qs = form.fields["pipeline"].queryset
    env_qs = form.fields["environment_instance"].queryset

    assert etl_pipeline_a in pipe_qs
    assert etl_pipeline_b not in pipe_qs
    assert env_a in env_qs
    assert env_b not in env_qs


# ===========================================================================
# 4. EtlPipelineRunForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_etlpipelines_run_form_system_field_exclusions(tenant_a):
    """Verify EtlPipelineRunForm excludes internal execution and metric fields."""
    form = EtlPipelineRunForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "created_at",
        "status",
        "started_at",
        "ended_at",
        "duration_seconds",
        "records_in",
        "records_transformed",
        "records_out",
        "records_rejected",
        "bytes_processed",
        "sla_missed",
        "retry_count",
        "step_progress",
        "error_message",
        "execution_log",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from EtlPipelineRunForm"


@pytest.mark.django_db
def test_etlpipelines_run_form_valid_creation(tenant_a, etl_pipeline_a, etl_version_a):
    """Verify valid EtlPipelineRunForm submission binds matching version and tenant."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version": etl_version_a.pk,
        "trigger_type": "manual",
        "is_backfill": False,
    }
    form = EtlPipelineRunForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.tenant == tenant_a
    assert instance.pipeline == etl_pipeline_a
    assert instance.version == etl_version_a
    assert instance.trigger_type == "manual"
    assert instance.is_backfill is False


@pytest.mark.django_db
def test_etlpipelines_run_form_cross_model_pipeline_version_mismatch(
    tenant_a, admin_user, etl_pipeline_a, etl_version_a
):
    """Verify validation error if chosen version belongs to a different pipeline."""
    other_pipeline = EtlPipeline.objects.create(
        tenant=tenant_a,
        name="Other Pipeline In Tenant A",
        target_table="fact_other",
        created_by=admin_user,
    )
    # etl_version_a belongs to etl_pipeline_a, NOT other_pipeline
    data = {
        "pipeline": other_pipeline.pk,
        "version": etl_version_a.pk,
        "trigger_type": "manual",
    }
    form = EtlPipelineRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "version" in form.errors
    assert "Selected pipeline version does not belong to the selected pipeline." in form.errors["version"]


@pytest.mark.django_db
def test_etlpipelines_run_form_reject_foreign_pipeline(tenant_a, etl_pipeline_b, etl_version_a):
    """Verify EtlPipelineRunForm rejects foreign tenant pipeline."""
    data = {
        "pipeline": etl_pipeline_b.pk,
        "version": etl_version_a.pk,
        "trigger_type": "manual",
    }
    # Scoped queryset rejects at field level
    form = EtlPipelineRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pipeline" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = EtlPipelineRunForm(data=data, tenant=tenant_a)
    form_wide.fields["pipeline"].queryset = EtlPipeline.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["pipeline"]


@pytest.mark.django_db
def test_etlpipelines_run_form_reject_foreign_version(tenant_a, etl_pipeline_a, etl_version_b):
    """Verify EtlPipelineRunForm rejects foreign tenant version."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version": etl_version_b.pk,
        "trigger_type": "manual",
    }
    # Scoped queryset rejects at field level
    form = EtlPipelineRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "version" in form.errors

    # reject_foreign defense-in-depth validator rejects explicitly
    form_wide = EtlPipelineRunForm(data=data, tenant=tenant_a)
    form_wide.fields["version"].queryset = EtlPipelineVersion.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["version"]


@pytest.mark.django_db
def test_etlpipelines_run_form_queryset_scoping(
    tenant_a, tenant_b, etl_pipeline_a, etl_pipeline_b, etl_version_a, etl_version_b
):
    """Verify pipeline and version querysets are scoped to form tenant."""
    form = EtlPipelineRunForm(tenant=tenant_a)
    pipe_qs = form.fields["pipeline"].queryset
    ver_qs = form.fields["version"].queryset

    assert etl_pipeline_a in pipe_qs
    assert etl_pipeline_b not in pipe_qs
    assert etl_version_a in ver_qs
    assert etl_version_b not in ver_qs


@pytest.mark.django_db
def test_etlpipelines_run_form_backfill_fields(tenant_a, etl_pipeline_a, etl_version_a):
    """Verify backfill range start and end dates validate cleanly when submitted."""
    data = {
        "pipeline": etl_pipeline_a.pk,
        "version": etl_version_a.pk,
        "trigger_type": "backfill",
        "is_backfill": True,
        "backfill_range_start": "2026-11-01 00:00:00",
        "backfill_range_end": "2026-11-02 23:59:59",
    }
    form = EtlPipelineRunForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.is_backfill is True
    assert instance.backfill_range_start is not None
    assert instance.backfill_range_end is not None
