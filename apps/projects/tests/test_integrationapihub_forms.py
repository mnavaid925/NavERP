import json

import pytest
from django import forms
from django.contrib.auth import get_user_model

from apps.core.crypto import is_encrypted
from apps.projects.forms import (
    ConnectorFieldMappingForm,
    ConnectorTestForm,
    ProjectIntegrationConnectorForm,
    ProjectSyncJobForm,
    TenantModelForm,
    TenantUniqueMixin,
)
from apps.projects.models import (
    ConnectorFieldMapping,
    ProjectIntegrationConnector,
    ProjectSyncJob,
    ProjectSyncRun,
)

User = get_user_model()
pytestmark = pytest.mark.django_db

_INTEGRATIONAPIHUB_CONNECTOR_FIELDS = [
    "project", "name", "domain", "provider", "direction", "auth_method",
    "base_url", "remote_scope_ref", "trigger_mode", "schedule_note",
    "environment", "status", "is_active", "notify_webhook", "owner", "notes",
]
_INTEGRATIONAPIHUB_MAPPING_FIELDS = [
    "connector", "local_field", "remote_field", "direction", "transform",
    "value_map", "default_value", "is_key", "is_required", "notes",
]
_INTEGRATIONAPIHUB_JOB_FIELDS = [
    "connector", "name", "entity_scope", "direction", "trigger_mode",
    "interval_minutes", "schedule_note", "filter_expression", "conflict_policy",
    "batch_size", "is_active",
]
_INTEGRATIONAPIHUB_CONNECTOR_REQUIRED = {
    "name", "domain", "direction", "auth_method", "trigger_mode", "environment", "status",
}
_INTEGRATIONAPIHUB_MAPPING_REQUIRED = {
    "connector", "local_field", "remote_field", "direction", "transform",
}
_INTEGRATIONAPIHUB_JOB_REQUIRED = {
    "connector", "name", "entity_scope", "direction", "trigger_mode", "conflict_policy", "batch_size",
}
_INTEGRATIONAPIHUB_MAPPING_DIRECTIONS = ["to_remote", "from_remote", "both"]
_INTEGRATIONAPIHUB_MAPPING_TRANSFORMS = ["none", "upper", "lower", "trim", "date_iso", "number", "bool"]
_INTEGRATIONAPIHUB_JOB_ENTITIES = [
    "tasks", "issues", "risks", "milestones", "time_entries", "resources", "documents", "folders",
    "budgets", "cost_lines", "journals", "custom",
]
_INTEGRATIONAPIHUB_JOB_DIRECTIONS = ["inbound", "outbound", "bidirectional"]
_INTEGRATIONAPIHUB_JOB_TRIGGERS = ["manual", "scheduled", "event"]
_INTEGRATIONAPIHUB_JOB_CONFLICTS = ["local_wins", "remote_wins", "newest_wins", "manual"]


def _integrationapihub_connector_payload(project=None, owner=None, **overrides):
    data = {
        "project": "" if project is None else str(project.pk),
        "name": "Form-created connector",
        "domain": "erp",
        "provider": "sap",
        "direction": "bidirectional",
        "auth_method": "api_key",
        "base_url": "https://config.example.invalid",
        "remote_scope_ref": "NAVERP",
        "trigger_mode": "manual",
        "schedule_note": "Recorded intent only.",
        "environment": "sandbox",
        "status": "unverified",
        "is_active": "on",
        "notify_webhook": "",
        "owner": "" if owner is None else str(owner.pk),
        "notes": "",
        "credential": "",
    }
    data.update(overrides)
    return data


def _integrationapihub_mapping_payload(connector, **overrides):
    data = {
        "connector": str(connector.pk),
        "local_field": "task.form_field",
        "remote_field": "fields.FormField",
        "direction": "both",
        "transform": "none",
        "value_map": "{}",
        "default_value": "",
        "is_key": "",
        "is_required": "",
        "notes": "",
    }
    data.update(overrides)
    return data


def _integrationapihub_job_payload(connector, **overrides):
    data = {
        "connector": str(connector.pk),
        "name": "Form-created sync job",
        "entity_scope": "tasks",
        "direction": "bidirectional",
        "trigger_mode": "manual",
        "interval_minutes": "",
        "schedule_note": "",
        "filter_expression": "",
        "conflict_policy": "manual",
        "batch_size": "100",
        "is_active": "on",
    }
    data.update(overrides)
    return data


def _integrationapihub_widen(form, *names):
    for name in names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


def _integrationapihub_pks(form, name):
    return set(form.fields[name].queryset.values_list("pk", flat=True))


def _integrationapihub_inactive_user(tenant):
    return User.objects.create_user(
        email="integration-inactive@example.com",
        username="integration_inactive",
        password="TestPass123!",
        tenant=tenant,
        is_active=False,
    )


def test_integrationapihub_forms_reexport_three_model_forms_and_test_form():
    import apps.projects.forms as project_forms

    for form_class in (
        ProjectIntegrationConnectorForm,
        ConnectorFieldMappingForm,
        ProjectSyncJobForm,
        ConnectorTestForm,
    ):
        assert isinstance(form_class, type)
    assert not hasattr(project_forms, "ProjectSyncRunForm")


def test_integrationapihub_model_forms_use_tenant_model_and_unique_mixins():
    cases = (
        (ProjectIntegrationConnectorForm, ProjectIntegrationConnector),
        (ConnectorFieldMappingForm, ConnectorFieldMapping),
        (ProjectSyncJobForm, ProjectSyncJob),
    )
    for form_class, model in cases:
        assert form_class.Meta.model is model
        assert issubclass(form_class, TenantModelForm)
        mro = form_class.__mro__
        assert mro.index(TenantUniqueMixin) < mro.index(TenantModelForm)


def test_integrationapihub_forms_accept_tenant_keyword_and_preserve_it(tenant_a):
    for form_class in (
        ProjectIntegrationConnectorForm,
        ConnectorFieldMappingForm,
        ProjectSyncJobForm,
    ):
        form = form_class(tenant=tenant_a)
        assert form.tenant == tenant_a
        assert form.instance.tenant_id == tenant_a.pk


def test_integrationapihub_connector_form_has_exact_meta_and_runtime_field_order(tenant_a):
    form = ProjectIntegrationConnectorForm(tenant=tenant_a)
    assert ProjectIntegrationConnectorForm.Meta.fields == _INTEGRATIONAPIHUB_CONNECTOR_FIELDS
    assert list(form.fields) == _INTEGRATIONAPIHUB_CONNECTOR_FIELDS + ["credential"]
    assert "credential" not in ProjectIntegrationConnectorForm.Meta.fields
    assert len(form.fields) == 17


def test_integrationapihub_mapping_form_has_exact_meta_and_runtime_field_order(tenant_a):
    form = ConnectorFieldMappingForm(tenant=tenant_a)
    assert ConnectorFieldMappingForm.Meta.fields == _INTEGRATIONAPIHUB_MAPPING_FIELDS
    assert list(form.fields) == _INTEGRATIONAPIHUB_MAPPING_FIELDS
    assert len(form.fields) == 10


def test_integrationapihub_job_form_has_exact_meta_and_runtime_field_order(tenant_a):
    form = ProjectSyncJobForm(tenant=tenant_a)
    assert ProjectSyncJobForm.Meta.fields == _INTEGRATIONAPIHUB_JOB_FIELDS
    assert list(form.fields) == _INTEGRATIONAPIHUB_JOB_FIELDS
    assert len(form.fields) == 11


def test_integrationapihub_forms_exclude_tenant_number_and_system_fields(tenant_a):
    connector = ProjectIntegrationConnectorForm(tenant=tenant_a)
    mapping = ConnectorFieldMappingForm(tenant=tenant_a)
    job = ProjectSyncJobForm(tenant=tenant_a)
    connector_forbidden = {
        "tenant", "number", "last_sync_at", "last_success_at", "consecutive_failures",
        "created_at", "updated_at",
    }
    mapping_forbidden = {"tenant", "number", "created_at", "updated_at"}
    job_forbidden = {
        "tenant", "number", "last_run_at", "next_run_at", "run_count", "last_status",
        "created_at", "updated_at",
    }
    assert connector_forbidden.isdisjoint(connector.fields)
    assert mapping_forbidden.isdisjoint(mapping.fields)
    assert job_forbidden.isdisjoint(job.fields)


def test_integrationapihub_connector_form_reports_its_required_fields(tenant_a):
    form = ProjectIntegrationConnectorForm({}, tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _INTEGRATIONAPIHUB_CONNECTOR_REQUIRED
    assert not form.is_valid()
    assert _INTEGRATIONAPIHUB_CONNECTOR_REQUIRED <= set(form.errors)


def test_integrationapihub_mapping_form_reports_its_required_fields(tenant_a):
    form = ConnectorFieldMappingForm({}, tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _INTEGRATIONAPIHUB_MAPPING_REQUIRED
    assert not form.is_valid()
    assert _INTEGRATIONAPIHUB_MAPPING_REQUIRED <= set(form.errors)


def test_integrationapihub_job_form_reports_its_required_fields(tenant_a):
    form = ProjectSyncJobForm({}, tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _INTEGRATIONAPIHUB_JOB_REQUIRED
    assert not form.is_valid()
    assert _INTEGRATIONAPIHUB_JOB_REQUIRED <= set(form.errors)


def test_integrationapihub_connector_form_valid_payload_saves_tenant_number_and_values(
    tenant_a,
    integrationapihub_project_a,
    admin_user,
):
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            owner=admin_user,
            name="Saved integration connector",
            status="connected",
            base_url="https://configuration.example.invalid/tenant-a",
            notes="No outbound request is made.",
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.instance.tenant_id == tenant_a.pk
    connector = form.save()
    connector.refresh_from_db()
    assert connector.tenant_id == tenant_a.pk
    assert connector.number.startswith("IXC-")
    assert connector.project_id == integrationapihub_project_a.pk
    assert connector.owner_id == admin_user.pk
    assert connector.status == "connected"
    assert connector.notes == "No outbound request is made."


def test_integrationapihub_mapping_form_valid_payload_saves_dict_and_tenant(
    tenant_a,
    integrationapihub_connector_a,
):
    value_map = {"todo": "To Do", "done": "Done"}
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.form_status",
            remote_field="fields.status.name",
            value_map=value_map,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    mapping = form.save()
    mapping.refresh_from_db()
    assert mapping.tenant_id == tenant_a.pk
    assert mapping.connector_id == integrationapihub_connector_a.pk
    assert mapping.value_map == value_map
    assert not hasattr(mapping, "number")


def test_integrationapihub_job_form_valid_payload_saves_filter_as_recorded_intent(
    tenant_a,
    integrationapihub_connector_a,
):
    expression = "status == active && this is intentionally not evaluated"
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name="Recorded intent job",
            filter_expression=expression,
            interval_minutes="15",
            batch_size="25",
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    job = form.save()
    job.refresh_from_db()
    assert job.tenant_id == tenant_a.pk
    assert job.number.startswith("SYJ-")
    assert job.filter_expression == expression
    assert job.interval_minutes == 15
    assert job.batch_size == 25


def test_integrationapihub_connector_form_ignores_tenant_number_and_system_values(
    tenant_a,
    tenant_b,
    integrationapihub_project_a,
):
    payload = _integrationapihub_connector_payload(
        project=integrationapihub_project_a,
        name="System value connector",
        tenant=str(tenant_b.pk),
        number="IXC-99999",
        last_sync_at="2020-01-01T00:00",
        last_success_at="2020-01-01T00:00",
        consecutive_failures="99",
        created_at="2020-01-01T00:00",
        updated_at="2020-01-01T00:00",
    )
    form = ProjectIntegrationConnectorForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    connector = form.save()
    connector.refresh_from_db()
    assert connector.tenant_id == tenant_a.pk
    assert connector.number != "IXC-99999"
    assert connector.number.startswith("IXC-")
    assert connector.last_sync_at is None
    assert connector.last_success_at is None
    assert connector.consecutive_failures == 0


def test_integrationapihub_mapping_form_ignores_tenant_and_number_values(
    tenant_a,
    tenant_b,
    integrationapihub_connector_a,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.smuggled",
            tenant=str(tenant_b.pk),
            number="IXM-99999",
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    mapping = form.save()
    mapping.refresh_from_db()
    assert mapping.tenant_id == tenant_a.pk
    assert not hasattr(mapping, "number")


def test_integrationapihub_job_form_ignores_tenant_number_and_run_system_values(
    tenant_a,
    tenant_b,
    integrationapihub_connector_a,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name="System value job",
            tenant=str(tenant_b.pk),
            number="SYJ-99999",
            last_run_at="2020-01-01T00:00",
            next_run_at="2020-01-02T00:00",
            run_count="88",
            last_status="success",
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    job = form.save()
    job.refresh_from_db()
    assert job.tenant_id == tenant_a.pk
    assert job.number != "SYJ-99999"
    assert job.last_run_at is None
    assert job.next_run_at is None
    assert job.run_count == 0
    assert job.last_status == ""


def test_integrationapihub_connector_owner_queryset_is_active_and_tenant_scoped(
    tenant_a,
    admin_user,
    member_user,
    admin_b,
):
    inactive = _integrationapihub_inactive_user(tenant_a)
    form = ProjectIntegrationConnectorForm(tenant=tenant_a)
    pks = _integrationapihub_pks(form, "owner")
    assert admin_user.pk in pks
    assert member_user.pk in pks
    assert admin_b.pk not in pks
    assert inactive.pk not in pks


def test_integrationapihub_connector_owner_rejects_inactive_and_foreign_pks(
    tenant_a,
    admin_b,
):
    inactive = _integrationapihub_inactive_user(tenant_a)
    inactive_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(owner=inactive), tenant=tenant_a)
    foreign_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(owner=admin_b), tenant=tenant_a)
    assert not inactive_form.is_valid()
    assert "owner" in inactive_form.errors
    assert not foreign_form.is_valid()
    assert "owner" in foreign_form.errors


def test_integrationapihub_connector_tenantless_owner_queryset_is_empty(
    tenant_a,
    admin_user,
):
    form = ProjectIntegrationConnectorForm(tenant=None)
    assert list(form.fields["owner"].queryset) == []
    assert admin_user.pk not in _integrationapihub_pks(form, "owner")


def test_integrationapihub_connector_owner_can_be_saved_from_the_tenant_queryset(
    tenant_a,
    integrationapihub_project_a,
    member_user,
):
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            owner=member_user,
            name="Owned form connector",
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.save().owner_id == member_user.pk


def test_integrationapihub_connector_normal_querysets_reject_foreign_project_and_webhook(
    tenant_a,
    integrationapihub_project_a,
    integrationapihub_project_b,
    workflowautomation_webhook_b,
):
    form = ProjectIntegrationConnectorForm(tenant=tenant_a)
    pks = _integrationapihub_pks(form, "project")
    webhook_pks = _integrationapihub_pks(form, "notify_webhook")
    assert integrationapihub_project_a.pk in pks
    assert integrationapihub_project_b.pk not in pks
    assert workflowautomation_webhook_b.pk not in webhook_pks
    foreign_project_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(project=integrationapihub_project_b), tenant=tenant_a)
    foreign_webhook_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            notify_webhook=workflowautomation_webhook_b,
        ),
        tenant=tenant_a,
    )
    assert not foreign_project_form.is_valid()
    assert "project" in foreign_project_form.errors
    assert not foreign_webhook_form.is_valid()
    assert "notify_webhook" in foreign_webhook_form.errors


def test_integrationapihub_connector_widened_project_queryset_rejects_foreign_project(
    tenant_a,
    integrationapihub_project_b,
):
    payload = _integrationapihub_connector_payload(
        project=integrationapihub_project_b,
        name="Foreign project widened",
    )
    form = ProjectIntegrationConnectorForm(payload, tenant=tenant_a)
    _integrationapihub_widen(form, "project")
    assert not form.is_valid()
    assert form.errors["project"] == ["That record belongs to another workspace."]


def test_integrationapihub_connector_widened_webhook_queryset_rejects_foreign_webhook(
    tenant_a,
    integrationapihub_project_a,
    workflowautomation_webhook_b,
):
    payload = _integrationapihub_connector_payload(
        project=integrationapihub_project_a,
        notify_webhook=workflowautomation_webhook_b,
        name="Foreign webhook widened",
    )
    form = ProjectIntegrationConnectorForm(payload, tenant=tenant_a)
    _integrationapihub_widen(form, "notify_webhook")
    assert not form.is_valid()
    assert form.errors["notify_webhook"] == ["That record belongs to another workspace."]


def test_integrationapihub_mapping_widened_connector_queryset_rejects_foreign_connector(
    tenant_a,
    integrationapihub_connector_b,
):
    payload = _integrationapihub_mapping_payload(
        integrationapihub_connector_b,
        local_field="task.foreign.widened",
    )
    form = ConnectorFieldMappingForm(payload, tenant=tenant_a)
    _integrationapihub_widen(form, "connector")
    assert not form.is_valid()
    assert form.errors["connector"] == ["That record belongs to another workspace."]


def test_integrationapihub_job_widened_connector_queryset_rejects_foreign_connector(
    tenant_a,
    integrationapihub_connector_b,
):
    payload = _integrationapihub_job_payload(
        integrationapihub_connector_b,
        name="Foreign job widened",
    )
    form = ProjectSyncJobForm(payload, tenant=tenant_a)
    _integrationapihub_widen(form, "connector")
    assert not form.is_valid()
    assert form.errors["connector"] == ["That record belongs to another workspace."]


def test_integrationapihub_tenant_argument_is_checked_when_project_queryset_is_widened(
    tenant_b,
    integrationapihub_project_a,
):
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            name="Tenant argument check",
        ),
        tenant=tenant_b,
    )
    _integrationapihub_widen(form, "project")
    assert not form.is_valid()
    assert form.errors["project"] == ["That record belongs to another workspace."]


def test_integrationapihub_mapping_and_job_normal_connector_querysets_are_tenant_scoped(
    tenant_a,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
):
    mapping_form = ConnectorFieldMappingForm(tenant=tenant_a)
    job_form = ProjectSyncJobForm(tenant=tenant_a)
    assert integrationapihub_connector_a.pk in _integrationapihub_pks(mapping_form, "connector")
    assert integrationapihub_connector_b.pk not in _integrationapihub_pks(mapping_form, "connector")
    assert integrationapihub_connector_a.pk in _integrationapihub_pks(job_form, "connector")
    assert integrationapihub_connector_b.pk not in _integrationapihub_pks(job_form, "connector")


def test_integrationapihub_tenant_fk_fields_use_select_widgets(tenant_a):
    connector = ProjectIntegrationConnectorForm(tenant=tenant_a)
    mapping = ConnectorFieldMappingForm(tenant=tenant_a)
    job = ProjectSyncJobForm(tenant=tenant_a)
    cases = (
        (connector, "project"),
        (connector, "notify_webhook"),
        (connector, "owner"),
        (mapping, "connector"),
        (job, "connector"),
    )
    for form, name in cases:
        field = form.fields[name]
        assert isinstance(field, forms.ModelChoiceField), name
        assert isinstance(field.widget, forms.Select), name
        assert field.widget.attrs["class"] == "form-select", name


def test_integrationapihub_connector_form_rejects_workspace_duplicate_name(
    tenant_a,
    integrationapihub_connector_workspace_a,
):
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(name=integrationapihub_connector_workspace_a.name),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert form.errors["name"] == [
        "A workspace-wide connector with this name already exists."
    ]


def test_integrationapihub_connector_edit_allows_its_workspace_name(
    tenant_a,
    integrationapihub_connector_workspace_a,
):
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            name=integrationapihub_connector_workspace_a.name,
            notes="Edited workspace connector",
        ),
        instance=integrationapihub_connector_workspace_a,
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()
    assert saved.name == integrationapihub_connector_workspace_a.name
    assert saved.notes == "Edited workspace connector"


def test_integrationapihub_connector_form_rejects_project_scoped_duplicate_name(
    tenant_a,
    integrationapihub_connector_a,
):
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_connector_a.project,
            name=integrationapihub_connector_a.name,
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert ProjectIntegrationConnector.objects.filter(
        tenant=tenant_a, project=integrationapihub_connector_a.project,
        name=integrationapihub_connector_a.name,
    ).count() == 1


def test_integrationapihub_mapping_form_rejects_duplicate_unique_tuple(
    tenant_a,
    integrationapihub_mapping_a,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_mapping_a.connector,
            local_field=integrationapihub_mapping_a.local_field,
            direction=integrationapihub_mapping_a.direction,
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert ConnectorFieldMapping.objects.filter(pk=integrationapihub_mapping_a.pk).count() == 1


def test_integrationapihub_job_form_rejects_duplicate_connector_name(
    tenant_a,
    integrationapihub_job_a,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_job_a.connector,
            name=integrationapihub_job_a.name,
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert ProjectSyncJob.objects.filter(pk=integrationapihub_job_a.pk).count() == 1


def test_integrationapihub_connector_credential_field_is_write_only_password_input(
    integrationapihub_connector_credential_a,
):
    raw = "provider-secret-1234"
    form = ProjectIntegrationConnectorForm(
        instance=integrationapihub_connector_credential_a,
        tenant=integrationapihub_connector_credential_a.tenant,
    )
    field = form.fields["credential"]
    assert field.required is False
    assert field.help_text == (
        "Paste the provider token/API key. Stored encrypted; leave blank on edit to keep the current one."
    )
    assert isinstance(field.widget, forms.PasswordInput)
    assert field.widget.input_type == "password"
    assert field.widget.render_value is False
    assert field.widget.attrs["class"] == "form-input"
    rendered = str(form["credential"])
    assert raw not in rendered
    assert integrationapihub_connector_credential_a.credential not in rendered


def test_integrationapihub_connector_blank_credential_edit_preserves_ciphertext(
    integrationapihub_connector_credential_a,
):
    original = integrationapihub_connector_credential_a.credential
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_connector_credential_a.project,
            name=integrationapihub_connector_credential_a.name,
            credential="",
        ),
        instance=integrationapihub_connector_credential_a,
        tenant=integrationapihub_connector_credential_a.tenant,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()
    assert saved.credential == original
    assert saved.get_credential() == "provider-secret-1234"


def test_integrationapihub_connector_nonblank_credential_is_encrypted_without_plaintext_leak(
    tenant_a,
    integrationapihub_project_a,
):
    raw = "new-provider-secret-9876"
    form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            name="Encrypted credential connector",
            credential=raw,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()
    assert saved.credential != raw
    assert is_encrypted(saved.credential)
    assert saved.get_credential() == raw
    assert raw not in saved.credential
    assert raw not in str(form["credential"])


def test_integrationapihub_mapping_value_map_blank_is_an_empty_dictionary(
    tenant_a,
    integrationapihub_connector_a,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.blank_map",
            value_map="",
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value_map"] == {}
    assert form.save().value_map == {}


def test_integrationapihub_mapping_value_map_object_text_is_parsed(
    tenant_a,
    integrationapihub_connector_a,
):
    value_map = {"todo": "To Do", "done": "Done"}
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.object_map",
            value_map=json.dumps(value_map),
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value_map"] == value_map
    assert form.save().value_map == value_map


def test_integrationapihub_mapping_value_map_python_dictionary_passes_through(
    tenant_a,
    integrationapihub_connector_a,
):
    value_map = {"Closed Won": "active"}
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.dict_map",
            value_map=value_map,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["value_map"] == value_map


def test_integrationapihub_mapping_value_map_non_dict_json_is_rejected(
    tenant_a,
    integrationapihub_connector_a,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.non_dict_map",
            value_map=json.dumps(["todo", "done"]),
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert form.errors["value_map"] == [
        "Value map must be a JSON object (key-value dictionary)."
    ]


def test_integrationapihub_mapping_malformed_bound_json_is_rejected(
    tenant_a,
    integrationapihub_connector_a,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field="task.malformed_map",
            value_map="{not valid",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "value_map" in form.errors
    assert form.errors["value_map"][0].startswith("Invalid JSON for value map:")


def test_integrationapihub_mapping_clean_value_map_handles_malformed_text_directly(tenant_a):
    form = ConnectorFieldMappingForm(tenant=tenant_a)
    form.cleaned_data = {"value_map": "{not valid"}
    with pytest.raises(forms.ValidationError, match="Invalid JSON for value map"):
        form.clean_value_map()


def test_integrationapihub_mapping_clean_value_map_treats_none_and_whitespace_as_empty(tenant_a):
    form = ConnectorFieldMappingForm(tenant=tenant_a)
    form.cleaned_data = {"value_map": None}
    assert form.clean_value_map() == {}
    form.cleaned_data = {"value_map": "   "}
    assert form.clean_value_map() == {}


@pytest.mark.parametrize("direction", _INTEGRATIONAPIHUB_MAPPING_DIRECTIONS)
def test_integrationapihub_mapping_accepts_every_direction(
    tenant_a, integrationapihub_connector_a, direction,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field=f"task.direction.{direction}",
            direction=direction,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["direction"] == direction


@pytest.mark.parametrize("transform", _INTEGRATIONAPIHUB_MAPPING_TRANSFORMS)
def test_integrationapihub_mapping_accepts_every_transform(
    tenant_a, integrationapihub_connector_a, transform,
):
    form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a,
            local_field=f"task.transform.{transform}",
            transform=transform,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["transform"] == transform


def test_integrationapihub_mapping_rejects_unknown_direction_and_transform(
    tenant_a,
    integrationapihub_connector_a,
):
    direction_form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a, direction="sideways",
        ),
        tenant=tenant_a,
    )
    transform_form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_a, transform="encrypt",
        ),
        tenant=tenant_a,
    )
    assert not direction_form.is_valid()
    assert "direction" in direction_form.errors
    assert not transform_form.is_valid()
    assert "transform" in transform_form.errors


@pytest.mark.parametrize("value", ["", "0", "15"])
def test_integrationapihub_job_accepts_blank_and_nonnegative_interval_values(
    tenant_a, integrationapihub_connector_a, value,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Interval {value or 'blank'}",
            interval_minutes=value,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.save().interval_minutes == (None if value == "" else int(value))


@pytest.mark.parametrize("value", ["-1", "abc", "1.5"])
def test_integrationapihub_job_rejects_invalid_interval_values(
    tenant_a, integrationapihub_connector_a, value,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Invalid interval {value}",
            interval_minutes=value,
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "interval_minutes" in form.errors


@pytest.mark.parametrize("value", ["0", "1", "1000"])
def test_integrationapihub_job_accepts_nonnegative_batch_sizes(
    tenant_a, integrationapihub_connector_a, value,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Batch {value}",
            batch_size=value,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.save().batch_size == int(value)


@pytest.mark.parametrize("value", ["-1", "abc", ""])
def test_integrationapihub_job_rejects_invalid_batch_sizes(
    tenant_a, integrationapihub_connector_a, value,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Invalid batch {value or 'blank'}",
            batch_size=value,
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "batch_size" in form.errors


@pytest.mark.parametrize("entity_scope", _INTEGRATIONAPIHUB_JOB_ENTITIES)
def test_integrationapihub_job_accepts_every_entity_scope(
    tenant_a, integrationapihub_connector_a, entity_scope,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Entity {entity_scope}",
            entity_scope=entity_scope,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["entity_scope"] == entity_scope


@pytest.mark.parametrize("direction", _INTEGRATIONAPIHUB_JOB_DIRECTIONS)
def test_integrationapihub_job_accepts_every_direction(
    tenant_a, integrationapihub_connector_a, direction,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Job direction {direction}",
            direction=direction,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["direction"] == direction


@pytest.mark.parametrize("trigger_mode", _INTEGRATIONAPIHUB_JOB_TRIGGERS)
def test_integrationapihub_job_accepts_every_trigger_mode(
    tenant_a, integrationapihub_connector_a, trigger_mode,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Trigger {trigger_mode}",
            trigger_mode=trigger_mode,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["trigger_mode"] == trigger_mode


@pytest.mark.parametrize("conflict_policy", _INTEGRATIONAPIHUB_JOB_CONFLICTS)
def test_integrationapihub_job_accepts_every_conflict_policy(
    tenant_a, integrationapihub_connector_a, conflict_policy,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Conflict {conflict_policy}",
            conflict_policy=conflict_policy,
        ),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["conflict_policy"] == conflict_policy


@pytest.mark.parametrize(
    "field,value",
    [
        ("entity_scope", "unknown"),
        ("direction", "sideways"),
        ("trigger_mode", "never"),
        ("conflict_policy", "coin_flip"),
    ],
)
def test_integrationapihub_job_rejects_unknown_choice_values(
    tenant_a, integrationapihub_connector_a, field, value,
):
    form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name=f"Bad {field}",
            **{field: value},
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert field in form.errors


def test_integrationapihub_job_filter_expression_help_text_and_intent_are_pinned(
    tenant_a,
    integrationapihub_connector_a,
):
    form = ProjectSyncJobForm(tenant=tenant_a)
    field = form.fields["filter_expression"]
    assert isinstance(field.widget, forms.Textarea)
    assert field.widget.attrs["rows"] == 2
    assert field.widget.attrs["class"] == "form-textarea font-mono text-sm"
    assert field.help_text == (
        "Recorded intent only — NavERP never evaluates this expression."
    )
    expression = "not executable &&&"
    submitted = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_a,
            name="Intent-only expression",
            filter_expression=expression,
        ),
        tenant=tenant_a,
    )
    assert submitted.is_valid(), submitted.errors
    assert submitted.save().filter_expression == expression


def test_integrationapihub_connector_notes_widget_is_three_row_textarea(tenant_a):
    field = ProjectIntegrationConnectorForm(tenant=tenant_a).fields["notes"]
    assert isinstance(field.widget, forms.Textarea)
    assert field.widget.attrs["rows"] == 3
    assert field.widget.attrs["class"] == "form-textarea"


def test_integrationapihub_mapping_value_map_widget_is_json_textarea(tenant_a):
    field = ConnectorFieldMappingForm(tenant=tenant_a).fields["value_map"]
    assert isinstance(field, forms.CharField)
    assert isinstance(field.widget, forms.Textarea)
    assert field.widget.attrs["rows"] == 3
    assert field.widget.attrs["class"] == "form-textarea font-mono text-sm"
    assert field.widget.attrs["placeholder"] == '{"done": "completed"}'


def test_integrationapihub_job_filter_expression_widget_is_monospaced_textarea(tenant_a):
    field = ProjectSyncJobForm(tenant=tenant_a).fields["filter_expression"]
    assert isinstance(field.widget, forms.Textarea)
    assert field.widget.attrs["rows"] == 2
    assert field.widget.attrs["class"] == "form-textarea font-mono text-sm"


def test_integrationapihub_connector_test_form_is_optional_two_row_textarea():
    form = ConnectorTestForm()
    assert not issubclass(ConnectorTestForm, forms.ModelForm)
    assert list(form.fields) == ["note"]
    assert form.fields["note"].required is False
    assert isinstance(form.fields["note"].widget, forms.Textarea)
    assert form.fields["note"].widget.attrs["rows"] == 2
    assert form.fields["note"].widget.attrs["class"] == "form-textarea"
    assert form.fields["note"].widget.attrs["placeholder"] == (
        "Optional note recorded on the simulated test run."
    )
    assert ConnectorTestForm(data={}).is_valid()
    assert ConnectorTestForm(data={"note": "No request was made."}).is_valid()


def test_integrationapihub_form_choice_fields_expose_model_vocabularies(tenant_a):
    connector = ProjectIntegrationConnectorForm(tenant=tenant_a)
    mapping = ConnectorFieldMappingForm(tenant=tenant_a)
    job = ProjectSyncJobForm(tenant=tenant_a)
    cases = (
        (connector, ProjectIntegrationConnector, "domain", ProjectIntegrationConnector.DOMAIN_CHOICES),
        (connector, ProjectIntegrationConnector, "provider", ProjectIntegrationConnector.PROVIDER_CHOICES),
        (connector, ProjectIntegrationConnector, "direction", ProjectIntegrationConnector.DIRECTION_CHOICES),
        (connector, ProjectIntegrationConnector, "auth_method", ProjectIntegrationConnector.AUTH_METHOD_CHOICES),
        (connector, ProjectIntegrationConnector, "trigger_mode", ProjectIntegrationConnector.TRIGGER_MODE_CHOICES),
        (connector, ProjectIntegrationConnector, "environment", ProjectIntegrationConnector.ENVIRONMENT_CHOICES),
        (connector, ProjectIntegrationConnector, "status", ProjectIntegrationConnector.STATUS_CHOICES),
        (mapping, ConnectorFieldMapping, "direction", ConnectorFieldMapping.DIRECTION_CHOICES),
        (mapping, ConnectorFieldMapping, "transform", ConnectorFieldMapping.TRANSFORM_CHOICES),
        (job, ProjectSyncJob, "entity_scope", ProjectSyncJob.SYNC_ENTITY_CHOICES),
        (job, ProjectSyncJob, "direction", ProjectSyncJob.DIRECTION_CHOICES),
        (job, ProjectSyncJob, "trigger_mode", ProjectSyncJob.TRIGGER_MODE_CHOICES),
        (job, ProjectSyncJob, "conflict_policy", ProjectSyncJob.CONFLICT_POLICY_CHOICES),
    )
    for form, model, name, choices in cases:
        assert isinstance(form.fields[name], forms.TypedChoiceField), name
        assert [value for value, _label in form.fields[name].choices if value != ""] == [
            value for value, _label in model._meta.get_field(name).choices
        ]


def test_integrationapihub_run_model_has_no_form_write_surface():
    import apps.projects.forms as project_forms

    assert not hasattr(project_forms, "ProjectSyncRunForm")
    assert all(
        form_class.Meta.model is not ProjectSyncRun
        for form_class in (
            ProjectIntegrationConnectorForm,
            ConnectorFieldMappingForm,
            ProjectSyncJobForm,
        )
    )
