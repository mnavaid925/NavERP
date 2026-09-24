import re
from datetime import timedelta

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.crypto import is_encrypted
from apps.projects.models import (
    ConnectorFieldMapping,
    ProjectIntegrationConnector,
    ProjectSyncJob,
    ProjectSyncRun,
)
from apps.projects.models.IntegrationApiHub.SyncRuns import SYNC_BACKOFF_SECONDS
from apps.projects.tests.conftest import (
    _integrationapihub_connector,
    _integrationapihub_job,
    _integrationapihub_mapping,
    _integrationapihub_run,
)

pytestmark = pytest.mark.django_db


def _integrationapihub_index_map(model):
    return {index.name: tuple(index.fields) for index in model._meta.indexes}


def test_integrationapihub_numbered_models_mint_exact_prefixes(
    tenant_a,
    integrationapihub_project_a,
):
    connector = _integrationapihub_connector(
        tenant_a, project=integrationapihub_project_a, name="Prefix connector"
    )
    job = _integrationapihub_job(tenant_a, connector, name="Prefix job")
    run = _integrationapihub_run(tenant_a, job)

    assert ProjectIntegrationConnector.NUMBER_PREFIX == "IXC"
    assert ProjectSyncJob.NUMBER_PREFIX == "SYJ"
    assert ProjectSyncRun.NUMBER_PREFIX == "SYR"
    assert re.fullmatch(r"IXC-\d{5}", connector.number)
    assert re.fullmatch(r"SYJ-\d{5}", job.number)
    assert re.fullmatch(r"SYR-\d{5}", run.number)


def test_integrationapihub_numbering_is_per_tenant_and_sequential(
    tenant_a,
    tenant_b,
    integrationapihub_project_a,
    integrationapihub_project_b,
):
    connector_a1 = _integrationapihub_connector(
        tenant_a, project=integrationapihub_project_a, name="Tenant A connector 1"
    )
    connector_a2 = _integrationapihub_connector(
        tenant_a, project=integrationapihub_project_a, name="Tenant A connector 2"
    )
    connector_b1 = _integrationapihub_connector(
        tenant_b, project=integrationapihub_project_b, name="Tenant B connector 1"
    )
    job_a1 = _integrationapihub_job(tenant_a, connector_a1, name="Tenant A job 1")
    job_a2 = _integrationapihub_job(tenant_a, connector_a1, name="Tenant A job 2")
    job_b1 = _integrationapihub_job(tenant_b, connector_b1, name="Tenant B job 1")
    run_a1 = _integrationapihub_run(tenant_a, job_a1)
    run_a2 = _integrationapihub_run(tenant_a, job_a1)
    run_b1 = _integrationapihub_run(tenant_b, job_b1)

    assert connector_a1.number == connector_b1.number
    assert int(connector_a2.number.split("-")[1]) == int(connector_a1.number.split("-")[1]) + 1
    assert job_a1.number == job_b1.number
    assert int(job_a2.number.split("-")[1]) == int(job_a1.number.split("-")[1]) + 1
    assert run_a1.number == run_b1.number
    assert int(run_a2.number.split("-")[1]) == int(run_a1.number.split("-")[1]) + 1


def test_integrationapihub_numbered_models_keep_numbers_on_resave(
    tenant_a,
    integrationapihub_project_a,
):
    connector = _integrationapihub_connector(
        tenant_a, project=integrationapihub_project_a, name="Resaved connector"
    )
    job = _integrationapihub_job(tenant_a, connector, name="Resaved job")
    run = _integrationapihub_run(tenant_a, job)
    connector_number = connector.number
    job_number = job.number
    run_number = run.number

    connector.name = "Resaved connector renamed"
    connector.save()
    job.name = "Resaved job renamed"
    job.save()
    run.payload_excerpt = "Resaved payload"
    run.save()

    connector.refresh_from_db()
    job.refresh_from_db()
    run.refresh_from_db()
    assert connector.number == connector_number
    assert job.number == job_number
    assert run.number == run_number


def test_integrationapihub_mapping_is_unnumbered(
    tenant_a,
    integrationapihub_connector_a,
):
    mapping = _integrationapihub_mapping(tenant_a, integrationapihub_connector_a)

    assert not hasattr(mapping, "number")
    with pytest.raises(FieldDoesNotExist):
        ConnectorFieldMapping._meta.get_field("number")


def test_integrationapihub_connector_exact_choice_sets():
    assert ProjectIntegrationConnector.DOMAIN_CHOICES == [
        ("erp", "ERP & Finance"),
        ("crm", "CRM"),
        ("hris", "HR & Talent"),
        ("devops", "DevOps"),
        ("storage", "File Storage"),
        ("custom", "Custom / Other"),
    ]
    assert ProjectIntegrationConnector.PROVIDER_CHOICES == [
        ("sap", "SAP"),
        ("oracle", "Oracle"),
        ("netsuite", "NetSuite"),
        ("dynamics", "Microsoft Dynamics"),
        ("workday", "Workday"),
        ("salesforce", "Salesforce"),
        ("hubspot", "HubSpot"),
        ("dynamics_sales", "Dynamics Sales"),
        ("bamboohr", "BambooHR"),
        ("adp", "ADP"),
        ("jira", "Jira"),
        ("github", "GitHub"),
        ("gitlab", "GitLab"),
        ("azure_devops", "Azure DevOps"),
        ("ci_cd", "CI/CD Pipeline"),
        ("sharepoint", "SharePoint"),
        ("google_drive", "Google Drive"),
        ("dropbox", "Dropbox"),
        ("box", "Box"),
        ("custom", "Custom / Other"),
    ]
    assert ProjectIntegrationConnector.DIRECTION_CHOICES == [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]
    assert ProjectIntegrationConnector.AUTH_METHOD_CHOICES == [
        ("none", "None"),
        ("api_key", "API Key"),
        ("basic", "Basic Auth"),
        ("oauth2", "OAuth 2.0"),
        ("pat", "Personal Access Token"),
    ]
    assert ProjectIntegrationConnector.TRIGGER_MODE_CHOICES == [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
        ("event", "Event-driven"),
    ]
    assert ProjectIntegrationConnector.ENVIRONMENT_CHOICES == [
        ("production", "Production"),
        ("sandbox", "Sandbox"),
    ]
    assert ProjectIntegrationConnector.STATUS_CHOICES == [
        ("unverified", "Unverified"),
        ("connected", "Connected"),
        ("error", "Error"),
        ("disabled", "Disabled"),
        ("disconnected", "Disconnected"),
    ]


def test_integrationapihub_mapping_exact_choice_sets():
    assert ConnectorFieldMapping.DIRECTION_CHOICES == [
        ("to_remote", "Local → Remote"),
        ("from_remote", "Remote → Local"),
        ("both", "Bidirectional"),
    ]
    assert ConnectorFieldMapping.TRANSFORM_CHOICES == [
        ("none", "None"),
        ("upper", "Uppercase"),
        ("lower", "Lowercase"),
        ("trim", "Trim"),
        ("date_iso", "ISO date"),
        ("number", "Number"),
        ("bool", "Boolean"),
    ]


def test_integrationapihub_job_exact_choice_sets():
    assert ProjectSyncJob.SYNC_ENTITY_CHOICES == [
        ("tasks", "Tasks"),
        ("issues", "Issues"),
        ("risks", "Risks"),
        ("milestones", "Milestones"),
        ("time_entries", "Time Entries"),
        ("resources", "Resources"),
        ("documents", "Documents"),
        ("folders", "Folders"),
        ("budgets", "Budgets"),
        ("cost_lines", "Cost Lines"),
        ("journals", "Journal Entries"),
        ("custom", "Custom / Other"),
    ]
    assert ProjectSyncJob.DIRECTION_CHOICES == [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]
    assert ProjectSyncJob.TRIGGER_MODE_CHOICES == [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
        ("event", "Event-driven"),
    ]
    assert ProjectSyncJob.CONFLICT_POLICY_CHOICES == [
        ("local_wins", "Local Wins"),
        ("remote_wins", "Remote Wins"),
        ("newest_wins", "Newest Wins"),
        ("manual", "Manual"),
    ]


def test_integrationapihub_run_exact_choice_sets():
    assert ProjectSyncRun.RUN_STATUS_CHOICES == [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("partial", "Partial"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
        ("simulated", "Simulated"),
    ]
    assert ProjectSyncRun.DIRECTION_CHOICES == [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]
    assert ProjectSyncRun.TRIGGER_SOURCE_CHOICES == [
        ("manual", "Manual"),
        ("schedule", "Schedule"),
        ("event", "Event"),
    ]


def test_integrationapihub_connector_defaults_and_field_shapes(tenant_a):
    connector = ProjectIntegrationConnector(tenant=tenant_a, name="Connector defaults")

    assert connector.project is None
    assert connector.domain == "custom"
    assert connector.provider == "custom"
    assert connector.direction == "bidirectional"
    assert connector.auth_method == "api_key"
    assert connector.base_url == ""
    assert connector.remote_scope_ref == ""
    assert connector.trigger_mode == "manual"
    assert connector.schedule_note == ""
    assert connector.environment == "sandbox"
    assert connector.status == "unverified"
    assert connector.is_active is True
    assert connector.credential == ""
    assert connector.last_sync_at is None
    assert connector.last_success_at is None
    assert connector.consecutive_failures == 0
    assert connector.notify_webhook is None
    assert connector.owner is None
    assert connector.notes == ""
    assert ProjectIntegrationConnector._meta.get_field("project").null is True
    assert ProjectIntegrationConnector._meta.get_field("project").blank is True
    assert ProjectIntegrationConnector._meta.get_field("name").max_length == 120
    assert ProjectIntegrationConnector._meta.get_field("credential").max_length == 512
    assert ProjectIntegrationConnector._meta.get_field("credential").editable is False
    assert ProjectIntegrationConnector._meta.get_field("last_sync_at").editable is False
    assert ProjectIntegrationConnector._meta.get_field("last_success_at").editable is False
    assert ProjectIntegrationConnector._meta.get_field("consecutive_failures").editable is False
    assert ProjectIntegrationConnector._meta.get_field("notify_webhook").null is True
    assert ProjectIntegrationConnector._meta.get_field("owner").null is True


def test_integrationapihub_mapping_defaults_and_field_shapes(
    tenant_a,
    integrationapihub_connector_a,
):
    mapping = ConnectorFieldMapping(
        tenant=tenant_a,
        connector=integrationapihub_connector_a,
        local_field="local.default",
        remote_field="remote.default",
    )

    assert mapping.direction == "both"
    assert mapping.transform == "none"
    assert mapping.value_map == {}
    assert mapping.default_value == ""
    assert mapping.is_key is False
    assert mapping.is_required is False
    assert mapping.notes == ""
    assert ConnectorFieldMapping._meta.get_field("connector").null is False
    assert ConnectorFieldMapping._meta.get_field("local_field").max_length == 100
    assert ConnectorFieldMapping._meta.get_field("remote_field").max_length == 100
    assert ConnectorFieldMapping._meta.get_field("value_map").default is dict
    assert ConnectorFieldMapping._meta.get_field("default_value").max_length == 255
    assert ConnectorFieldMapping._meta.get_field("notes").max_length == 255


def test_integrationapihub_job_defaults_and_field_shapes(
    tenant_a,
    integrationapihub_connector_a,
):
    job = ProjectSyncJob(
        tenant=tenant_a,
        connector=integrationapihub_connector_a,
        name="Job defaults",
    )

    assert job.entity_scope == "custom"
    assert job.direction == "bidirectional"
    assert job.trigger_mode == "manual"
    assert job.interval_minutes is None
    assert job.schedule_note == ""
    assert job.filter_expression == ""
    assert job.conflict_policy == "manual"
    assert job.batch_size == 100
    assert job.is_active is True
    assert job.last_run_at is None
    assert job.next_run_at is None
    assert job.run_count == 0
    assert job.last_status == ""
    assert ProjectSyncJob._meta.get_field("connector").null is False
    assert ProjectSyncJob._meta.get_field("name").max_length == 255
    assert ProjectSyncJob._meta.get_field("entity_scope").max_length == 16
    assert ProjectSyncJob._meta.get_field("interval_minutes").null is True
    assert ProjectSyncJob._meta.get_field("interval_minutes").blank is True
    assert ProjectSyncJob._meta.get_field("last_run_at").editable is False
    assert ProjectSyncJob._meta.get_field("next_run_at").editable is False
    assert ProjectSyncJob._meta.get_field("run_count").editable is False
    assert ProjectSyncJob._meta.get_field("last_status").editable is False
    assert "project" not in {field.name for field in ProjectSyncJob._meta.fields}


def test_integrationapihub_run_defaults_and_field_shapes(
    tenant_a,
    integrationapihub_connector_a,
):
    job = _integrationapihub_job(tenant_a, integrationapihub_connector_a, name="Run defaults job")
    run = ProjectSyncRun(tenant=tenant_a, job=job)

    assert run.direction == "bidirectional"
    assert run.status == "pending"
    assert run.trigger_source == "manual"
    assert run.triggered_by is None
    assert run.records_read == 0
    assert run.records_created == 0
    assert run.records_updated == 0
    assert run.records_skipped == 0
    assert run.records_failed == 0
    assert run.error_code == ""
    assert run.error_message == ""
    assert run.payload_excerpt == ""
    assert run.attempt_no == 1
    assert run.next_retry_at is None
    assert run.started_at is not None
    assert run.finished_at is None
    assert run.duration_ms == 0
    assert ProjectSyncRun._meta.get_field("job").null is False
    assert ProjectSyncRun._meta.get_field("triggered_by").editable is False
    assert ProjectSyncRun._meta.get_field("started_at").editable is False
    assert ProjectSyncRun._meta.get_field("finished_at").editable is False
    assert ProjectSyncRun._meta.get_field("duration_ms").editable is False
    assert "project" not in {field.name for field in ProjectSyncRun._meta.fields}


def test_integrationapihub_connector_meta_ordering_unique_together_and_indexes():
    assert ProjectIntegrationConnector._meta.ordering == ["-created_at", "-id"]
    assert set(ProjectIntegrationConnector._meta.unique_together) == {
        ("tenant", "number"),
        ("tenant", "project", "name"),
    }
    assert _integrationapihub_index_map(ProjectIntegrationConnector) == {
        "ixc_tnt_domain_idx": ("tenant", "domain"),
        "ixc_tnt_status_idx": ("tenant", "status"),
        "ixc_tnt_prj_idx": ("tenant", "project"),
        "ixc_tnt_active_idx": ("tenant", "is_active"),
    }


def test_integrationapihub_mapping_meta_ordering_unique_together_and_indexes():
    assert ConnectorFieldMapping._meta.ordering == ["connector__name", "local_field", "id"]
    assert set(ConnectorFieldMapping._meta.unique_together) == {
        ("tenant", "connector", "local_field", "direction"),
    }
    assert _integrationapihub_index_map(ConnectorFieldMapping) == {
        "ixm_tnt_conn_idx": ("tenant", "connector"),
        "ixm_tnt_conn_key_idx": ("tenant", "connector", "is_key"),
    }


def test_integrationapihub_job_meta_ordering_unique_together_and_indexes():
    assert ProjectSyncJob._meta.ordering == ["-created_at", "-id"]
    assert set(ProjectSyncJob._meta.unique_together) == {
        ("tenant", "number"),
        ("tenant", "connector", "name"),
    }
    assert _integrationapihub_index_map(ProjectSyncJob) == {
        "syj_tnt_conn_idx": ("tenant", "connector"),
        "syj_tnt_conn_act_idx": ("tenant", "connector", "is_active"),
        "syj_tnt_status_idx": ("tenant", "last_status"),
        "syj_tnt_active_idx": ("tenant", "is_active"),
    }


def test_integrationapihub_run_meta_ordering_unique_together_and_indexes():
    assert ProjectSyncRun._meta.ordering == ["-started_at", "-id"]
    assert set(ProjectSyncRun._meta.unique_together) == {("tenant", "number")}
    assert _integrationapihub_index_map(ProjectSyncRun) == {
        "syr_tnt_job_stat_idx": ("tenant", "job", "status"),
        "syr_tnt_stat_strt_idx": ("tenant", "status", "started_at"),
        "syr_tnt_job_strt_idx": ("tenant", "job", "started_at"),
    }


def test_integrationapihub_connector_rejects_cross_tenant_project(
    tenant_a,
    integrationapihub_project_b,
):
    connector = ProjectIntegrationConnector(
        tenant=tenant_a,
        project=integrationapihub_project_b,
        name="Foreign project connector",
    )

    with pytest.raises(ValidationError) as exc_info:
        connector.full_clean()

    assert "project" in exc_info.value.message_dict
    assert "another workspace" in exc_info.value.message_dict["project"][0]


def test_integrationapihub_connector_rejects_cross_tenant_webhook(
    tenant_a,
    integrationapihub_project_a,
    workflowautomation_webhook_b,
):
    connector = ProjectIntegrationConnector(
        tenant=tenant_a,
        project=integrationapihub_project_a,
        notify_webhook=workflowautomation_webhook_b,
        name="Foreign webhook connector",
    )

    with pytest.raises(ValidationError) as exc_info:
        connector.clean()

    assert "notify_webhook" in exc_info.value.message_dict
    assert "another workspace" in exc_info.value.message_dict["notify_webhook"][0]


def test_integrationapihub_connector_workspace_duplicate_guard_excludes_current_row(
    tenant_a,
):
    existing = _integrationapihub_connector(
        tenant_a, project=None, name="Workspace connector"
    )
    duplicate = ProjectIntegrationConnector(
        tenant=tenant_a,
        project=None,
        name=existing.name,
    )

    with pytest.raises(ValidationError) as exc_info:
        duplicate.clean()
    assert "name" in exc_info.value.message_dict
    assert "workspace-wide connector" in exc_info.value.message_dict["name"][0]

    duplicate.pk = existing.pk
    duplicate.clean()
    existing.name = "Renamed workspace connector"
    existing.clean()


def test_integrationapihub_database_unique_constraints_are_enforced(
    tenant_a,
    integrationapihub_project_a,
    integrationapihub_connector_a,
):
    _integrationapihub_connector(
        tenant_a, project=integrationapihub_project_a, name="Unique connector name"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _integrationapihub_connector(
                tenant_a,
                project=integrationapihub_project_a,
                name="Unique connector name",
            )

    _integrationapihub_mapping(
        tenant_a,
        integrationapihub_connector_a,
        local_field="unique.local",
        remote_field="unique.remote",
        direction="to_remote",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ConnectorFieldMapping(
                tenant=tenant_a,
                connector=integrationapihub_connector_a,
                local_field="unique.local",
                remote_field="other.remote",
                direction="to_remote",
            ).save()

    _integrationapihub_job(
        tenant_a, integrationapihub_connector_a, name="Unique job name"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ProjectSyncJob(
                tenant=tenant_a,
                connector=integrationapihub_connector_a,
                name="Unique job name",
            ).save()


def test_integrationapihub_connector_credential_encrypts_round_trips_and_resaves_idempotently(
    integrationapihub_connector_credential_a,
):
    raw = "provider-secret-1234"
    stored = integrationapihub_connector_credential_a.credential

    assert stored != raw
    assert is_encrypted(stored)
    assert integrationapihub_connector_credential_a.get_credential() == raw
    assert integrationapihub_connector_credential_a.credential_set is True

    integrationapihub_connector_credential_a.save()
    assert integrationapihub_connector_credential_a.credential == stored

    integrationapihub_connector_credential_a.set_credential("rotated-secret")
    assert integrationapihub_connector_credential_a.credential != "rotated-secret"
    assert is_encrypted(integrationapihub_connector_credential_a.credential)
    integrationapihub_connector_credential_a.save()
    assert integrationapihub_connector_credential_a.get_credential() == "rotated-secret"


def test_integrationapihub_connector_credential_masking_and_clearing(tenant_a):
    connector = ProjectIntegrationConnector(tenant=tenant_a, name="Credential mask")
    assert connector.credential_masked == "(none)"

    connector.set_credential("secret-1234")
    assert connector.credential_masked == "••••1234"
    connector.set_credential("abc")
    assert connector.credential_masked == "••••"
    connector.credential = "legacy-plaintext"
    assert connector.credential_masked == "(set — legacy plaintext)"
    connector.credential = "fernet.v1:not-a-valid-token"
    assert connector.credential_masked == "(set — undecryptable with the current key)"
    connector.set_credential("")
    connector.save()
    assert connector.credential == ""
    assert connector.get_credential() == ""
    assert connector.credential_set is False
    assert connector.credential_masked == "(none)"


def test_integrationapihub_connector_status_badge_branches(tenant_a):
    connector = ProjectIntegrationConnector(tenant=tenant_a, name="Status badges")
    expected = {
        "connected": "badge-green",
        "error": "badge-red",
        "unverified": "badge-slate",
        "disabled": "badge-muted",
        "disconnected": "badge-amber",
        "unknown": "badge-slate",
    }

    for status, badge in expected.items():
        connector.status = status
        assert connector.status_badge == badge


def test_integrationapihub_connector_domain_badge_branches(tenant_a):
    connector = ProjectIntegrationConnector(tenant=tenant_a, name="Domain badges")
    assert connector.domain_badge == "badge-slate"
    for domain in ("erp", "crm", "hris", "devops", "storage"):
        connector.domain = domain
        assert connector.domain_badge == "badge-info"


def test_integrationapihub_connector_health_badge_branches(tenant_a):
    connector = ProjectIntegrationConnector(tenant=tenant_a, name="Health badges")
    assert connector.health_badge == "badge-slate"

    connector.last_sync_at = timezone.now()
    assert connector.health_badge == "badge-green"
    connector.consecutive_failures = 1
    assert connector.health_badge == "badge-amber"
    connector.consecutive_failures = 2
    assert connector.health_badge == "badge-amber"
    connector.consecutive_failures = 3
    assert connector.health_badge == "badge-red"
    connector.consecutive_failures = 8
    assert connector.health_badge == "badge-red"


def test_integrationapihub_model_string_representations(
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_failed_a,
):
    assert str(integrationapihub_connector_a) == (
        f"{integrationapihub_connector_a.number} — {integrationapihub_connector_a.name} (SAP)"
    )
    assert str(integrationapihub_mapping_a) == (
        f"{integrationapihub_mapping_a.local_field} → {integrationapihub_mapping_a.remote_field}"
    )
    assert str(integrationapihub_job_a) == f"{integrationapihub_job_a.number} — {integrationapihub_job_a.name}"
    assert str(integrationapihub_run_failed_a) == (
        f"{integrationapihub_run_failed_a.number} — {integrationapihub_run_failed_a.get_status_display()} @ "
        f"{integrationapihub_run_failed_a.started_at:%Y-%m-%d %H:%M}"
    )


def test_integrationapihub_mapping_rejects_foreign_connector_and_required_fields(
    tenant_a,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
):
    foreign_mapping = ConnectorFieldMapping(
        tenant=tenant_a,
        connector=integrationapihub_connector_b,
        local_field="foreign.local",
        remote_field="foreign.remote",
    )
    with pytest.raises(ValidationError) as exc_info:
        foreign_mapping.clean()
    assert "connector" in exc_info.value.message_dict
    assert "another workspace" in exc_info.value.message_dict["connector"][0]

    invalid_mapping = ConnectorFieldMapping(
        tenant=tenant_a,
        connector=integrationapihub_connector_a,
        local_field="",
        remote_field="",
    )
    with pytest.raises(ValidationError) as exc_info:
        invalid_mapping.full_clean()
    assert "local_field" in exc_info.value.message_dict
    assert "remote_field" in exc_info.value.message_dict


def test_integrationapihub_job_rejects_foreign_connector(
    tenant_a,
    integrationapihub_connector_b,
):
    job = ProjectSyncJob(
        tenant=tenant_a,
        connector=integrationapihub_connector_b,
        name="Foreign job",
    )

    with pytest.raises(ValidationError) as exc_info:
        job.clean()

    assert "connector" in exc_info.value.message_dict
    assert "another workspace" in exc_info.value.message_dict["connector"][0]


def test_integrationapihub_run_rejects_foreign_job(
    tenant_a,
    tenant_b,
    integrationapihub_connector_b,
):
    foreign_job = _integrationapihub_job(
        tenant_b,
        integrationapihub_connector_b,
        name="Foreign run job",
    )
    run = ProjectSyncRun(tenant=tenant_a, job=foreign_job)

    with pytest.raises(ValidationError) as exc_info:
        run.clean()

    assert "job" in exc_info.value.message_dict
    assert "another workspace" in exc_info.value.message_dict["job"][0]


def test_integrationapihub_run_record_defaults_snapshot_and_job_remain_unchanged(
    tenant_a,
    integrationapihub_connector_a,
):
    last_run_at = timezone.now() - timedelta(hours=1)
    next_run_at = timezone.now() + timedelta(hours=1)
    job = _integrationapihub_job(
        tenant_a,
        integrationapihub_connector_a,
        direction="outbound",
        run_count=7,
        last_run_at=last_run_at,
        next_run_at=next_run_at,
        last_status="failed",
    )
    before = (
        job.connector_id,
        job.direction,
        job.is_active,
        job.run_count,
        job.last_run_at,
        job.next_run_at,
        job.last_status,
        job.updated_at,
    )
    before_record = timezone.now()
    run = _integrationapihub_run(tenant_a, job)
    after_record = timezone.now()

    assert run.tenant_id == job.tenant_id
    assert run.job_id == job.pk
    assert run.direction == "outbound"
    assert run.status == "simulated"
    assert run.trigger_source == "manual"
    assert run.triggered_by is None
    assert run.records_read == 0
    assert run.records_created == 0
    assert run.records_updated == 0
    assert run.records_skipped == 0
    assert run.records_failed == 0
    assert run.error_code == ""
    assert run.error_message == ""
    assert run.payload_excerpt == ""
    assert run.attempt_no == 1
    assert run.next_retry_at is None
    assert before_record <= run.started_at <= after_record
    assert run.finished_at is None
    assert run.duration_ms == 0
    assert (
        job.connector_id,
        job.direction,
        job.is_active,
        job.run_count,
        job.last_run_at,
        job.next_run_at,
        job.last_status,
        job.updated_at,
    ) == before
    job.refresh_from_db()
    assert (
        job.connector_id,
        job.direction,
        job.is_active,
        job.run_count,
        job.last_run_at,
        job.next_run_at,
        job.last_status,
        job.updated_at,
    ) == before


def test_integrationapihub_run_record_snapshots_all_supplied_counters_and_stamps(
    tenant_a,
    admin_user,
    integrationapihub_connector_a,
):
    started_at = timezone.now() - timedelta(minutes=3)
    finished_at = started_at + timedelta(seconds=4)
    next_retry_at = finished_at + timedelta(minutes=2)
    job = _integrationapihub_job(
        tenant_a,
        integrationapihub_connector_a,
        direction="outbound",
        name="Supplied run job",
    )
    run = _integrationapihub_run(
        tenant_a,
        job,
        status="partial",
        trigger_source="event",
        triggered_by=admin_user,
        direction="inbound",
        records_read=11,
        records_created=2,
        records_updated=3,
        records_skipped=4,
        records_failed=5,
        error_code="PARTIAL_RESULT",
        error_message="Some records were skipped.",
        payload_excerpt="Truncated partner payload.",
        attempt_no=3,
        next_retry_at=next_retry_at,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=999,
    )

    assert run.tenant_id == job.tenant_id
    assert run.job_id == job.pk
    assert run.direction == "inbound"
    assert run.status == "partial"
    assert run.trigger_source == "event"
    assert run.triggered_by == admin_user
    assert run.records_read == 11
    assert run.records_created == 2
    assert run.records_updated == 3
    assert run.records_skipped == 4
    assert run.records_failed == 5
    assert run.error_code == "PARTIAL_RESULT"
    assert run.error_message == "Some records were skipped."
    assert run.payload_excerpt == "Truncated partner payload."
    assert run.attempt_no == 3
    assert run.next_retry_at == next_retry_at
    assert run.started_at == started_at
    assert run.finished_at == finished_at
    assert run.duration_ms == 999


def test_integrationapihub_sync_backoff_constant_is_exact():
    assert SYNC_BACKOFF_SECONDS == (0, 5, 300, 1800, 7200, 18000, 36000, 36000)


def test_integrationapihub_run_status_badge_branches(
    tenant_a,
    integrationapihub_connector_a,
):
    job = _integrationapihub_job(tenant_a, integrationapihub_connector_a, name="Badge run job")
    run = ProjectSyncRun(tenant=tenant_a, job=job)
    expected = {
        "success": "badge-green",
        "partial": "badge-amber",
        "failed": "badge-red",
        "simulated": "badge-info",
        "pending": "badge-slate",
        "running": "badge-slate",
        "skipped": "badge-muted",
        "unknown": "badge-slate",
    }

    for status, badge in expected.items():
        run.status = status
        assert run.status_badge == badge
