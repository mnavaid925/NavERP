import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.projects.forms import MilestoneForm, ProjectForm, ProjectRiskForm, TaskForm
from apps.projects.forms.MasterDataConfiguration.CustomFieldMixin import ProjectCustomFieldFormMixin
from apps.projects.forms.MasterDataConfiguration.ProjectCustomFields import ProjectCustomFieldForm
from apps.projects.forms.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSettingForm
from apps.projects.forms.MasterDataConfiguration.ProjectTeams import (
    ProjectTeamForm,
    ProjectTeamMemberForm,
)
from apps.projects.forms.MasterDataConfiguration.ProjectTemplates import (
    ProjectTemplateForm,
    ProjectTemplateInstantiateForm,
)
from apps.projects.models import ProjectMilestone, ProjectRisk, ProjectTask
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam
from apps.projects.tests.masterdataconfiguration_helpers import (
    _masterdataconfiguration_custom_field,
    _masterdataconfiguration_custom_field_payload,
    _masterdataconfiguration_custom_value,
    _masterdataconfiguration_instantiate_payload,
    _masterdataconfiguration_locale_payload,
    _masterdataconfiguration_milestone_payload,
    _masterdataconfiguration_project,
    _masterdataconfiguration_project_payload,
    _masterdataconfiguration_risk_payload,
    _masterdataconfiguration_task_payload,
    _masterdataconfiguration_team,
    _masterdataconfiguration_team_member,
    _masterdataconfiguration_team_payload,
    _masterdataconfiguration_template_payload,
)


def _masterdataconfiguration_save_target(form, tenant, user, created_by=False):
    instance = form.save(commit=False)
    instance.tenant = tenant
    if created_by:
        instance.created_by = user
    instance.save()
    form.save_custom_values(instance, updated_by=user)
    return instance


def test_masterdataconfiguration_forms_template_round_trip(db, tenant_a):
    form = ProjectTemplateForm(_masterdataconfiguration_template_payload(), tenant=tenant_a)

    assert form.is_valid(), form.errors
    template = form.save(commit=False)
    template.tenant = tenant_a
    template.save()

    assert template.number.startswith("PTM-")
    assert template.default_roles == ["Project Manager", "Developer"]
    assert template.wbs_structure[0]["phase"] == "Discovery"
    assert template.workflow_config["rules"] == []


def test_masterdataconfiguration_forms_template_rejects_invalid_wbs(db, tenant_a):
    payload = _masterdataconfiguration_template_payload(
        wbs_structure_raw=json.dumps([{
            "phase": "Bad",
            "tasks": [{
                "name": "Invalid method",
                "duration_days": 1,
                "estimation_method": "invented",
            }],
        }]),
    )
    form = ProjectTemplateForm(payload, tenant=tenant_a)

    assert not form.is_valid()
    assert "wbs_structure_raw" in form.errors


def test_masterdataconfiguration_forms_custom_field_choice_validation(db, tenant_a):
    form = ProjectCustomFieldForm(
        _masterdataconfiguration_custom_field_payload(
            field_type="select",
            choices_list_raw="A\nA",
        ),
        tenant=tenant_a,
    )

    assert not form.is_valid()
    assert "choices_list_raw" in form.errors


def test_masterdataconfiguration_forms_custom_field_json_recursion_is_field_error(db, tenant_a):
    form = ProjectCustomFieldForm(
        _masterdataconfiguration_custom_field_payload(visibility_rule_raw="[" * 2000 + "]" * 2000),
        tenant=tenant_a,
    )

    assert not form.is_valid()
    assert "visibility_rule_raw" in form.errors


def test_masterdataconfiguration_forms_team_and_member_validation(db, tenant_a, admin_user):
    team = _masterdataconfiguration_team(tenant_a, admin_user, name="Existing", code="EXISTING")
    _masterdataconfiguration_team_member(tenant_a, team, admin_user)
    form = ProjectTeamForm(_masterdataconfiguration_team_payload(), tenant=tenant_a)
    member_form = ProjectTeamMemberForm(
        {"user": admin_user.pk, "role": "developer", "allocation_percentage": 50},
        tenant=tenant_a,
        team=team,
    )

    assert form.is_valid(), form.errors
    assert not member_form.is_valid()
    assert "user" in member_form.errors


def test_masterdataconfiguration_forms_locale_working_days(db, tenant_a):
    valid = ProjectLocaleSettingForm(_masterdataconfiguration_locale_payload(), tenant=tenant_a)
    invalid = ProjectLocaleSettingForm(
        _masterdataconfiguration_locale_payload(working_days_pattern=[]),
        tenant=tenant_a,
    )

    assert valid.is_valid(), valid.errors
    assert not invalid.is_valid()
    assert "working_days_pattern" in invalid.errors


def test_masterdataconfiguration_forms_locale_has_no_default_writer(db, tenant_a):
    form = ProjectLocaleSettingForm(
        _masterdataconfiguration_locale_payload(is_default="on"),
        tenant=tenant_a,
    )

    assert form.is_valid(), form.errors
    assert "is_default" not in form.fields


def test_masterdataconfiguration_forms_instantiate_date_order(db, tenant_a):
    valid = ProjectTemplateInstantiateForm(
        _masterdataconfiguration_instantiate_payload(),
        tenant=tenant_a,
    )
    invalid = ProjectTemplateInstantiateForm(
        _masterdataconfiguration_instantiate_payload(
            target_end_date=(timezone.localdate() - timedelta(days=1)).isoformat()
        ),
        tenant=tenant_a,
    )

    assert valid.is_valid(), valid.errors
    assert not invalid.is_valid()
    assert "target_end_date" in invalid.errors


def test_masterdataconfiguration_forms_custom_values_all_target_forms(
    db,
    tenant_a,
    admin_user,
):
    project_field = _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="project_code_value",
        name="Project code value",
        label="Project code value",
    )
    task_field = _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="task_score",
        name="Task score",
        label="Task score",
        target_entity="task",
        field_type="integer",
        min_value=0,
        max_value=10,
    )
    milestone_field = _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="gate_kind",
        name="Gate kind",
        label="Gate kind",
        target_entity="milestone",
        field_type="select",
        choices_list=["Alpha", "Beta"],
    )
    risk_field = _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="regulated",
        name="Regulated",
        label="Regulated",
        target_entity="risk",
        field_type="boolean",
    )
    team_field = _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="lead_user",
        name="Lead user",
        label="Lead user",
        target_entity="team",
        field_type="user_ref",
        is_required=False,
    )
    project = _masterdataconfiguration_project(tenant_a, admin_user)

    project_form = ProjectForm(
        _masterdataconfiguration_project_payload({"project_code_value": "P-1"}),
        tenant=tenant_a,
    )
    task_form = TaskForm(
        _masterdataconfiguration_task_payload(project, {"task_score": "7"}),
        tenant=tenant_a,
    )
    milestone_form = MilestoneForm(
        _masterdataconfiguration_milestone_payload(project, {"gate_kind": "Alpha"}),
        tenant=tenant_a,
    )
    risk_form = ProjectRiskForm(
        _masterdataconfiguration_risk_payload(project, {"regulated": "on"}),
        tenant=tenant_a,
    )
    team_form = ProjectTeamForm(
        _masterdataconfiguration_team_payload(
            name="Custom value team",
            code="CUSTOM-VALUE-TEAM",
            custom_lead_user=str(admin_user.pk),
        ),
        tenant=tenant_a,
    )

    for form in (project_form, task_form, milestone_form, risk_form, team_form):
        assert form.is_valid(), form.errors
    project_obj = _masterdataconfiguration_save_target(project_form, tenant_a, admin_user, True)
    task_obj = _masterdataconfiguration_save_target(task_form, tenant_a, admin_user, True)
    milestone_obj = _masterdataconfiguration_save_target(milestone_form, tenant_a, admin_user)
    risk_obj = _masterdataconfiguration_save_target(risk_form, tenant_a, admin_user, True)
    team_obj = _masterdataconfiguration_save_target(team_form, tenant_a, admin_user)

    assert _masterdataconfiguration_custom_value(project_field, project_obj, "project_code_value").value == "P-1"
    assert _masterdataconfiguration_custom_value(task_field, task_obj, "task_score").value == 7
    assert _masterdataconfiguration_custom_value(milestone_field, milestone_obj, "gate_kind").value == "Alpha"
    assert _masterdataconfiguration_custom_value(risk_field, risk_obj, "regulated").value is True
    assert _masterdataconfiguration_custom_value(team_field, team_obj, "lead_user").value == admin_user.pk


def test_masterdataconfiguration_forms_custom_value_range_and_visibility(
    db,
    tenant_a,
    admin_user,
):
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="bounded_score",
        name="Bounded score",
        label="Bounded score",
        target_entity="task",
        field_type="integer",
        min_value=1,
        max_value=5,
        is_required=True,
    )
    _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="gate_note",
        name="Gate note",
        label="Gate note",
        target_entity="milestone",
        is_required=True,
        visibility_rule={"depends_on": "is_phase_gate", "operator": "equals", "value": True},
    )
    invalid = TaskForm(
        _masterdataconfiguration_task_payload(project, {"bounded_score": "6"}),
        tenant=tenant_a,
    )
    hidden = MilestoneForm(
        _masterdataconfiguration_milestone_payload(project, {}),
        tenant=tenant_a,
    )

    assert not invalid.is_valid()
    assert "custom_bounded_score" in invalid.errors
    assert hidden.is_valid(), hidden.errors
    assert "custom_gate_note" not in hidden.cleaned_data


def test_masterdataconfiguration_forms_tenantless_querysets_are_empty(db):
    project_form = ProjectForm(tenant=None)
    team_form = ProjectTeamForm(tenant=None)
    locale_form = ProjectLocaleSettingForm(tenant=None)

    assert project_form.fields["client"].queryset.count() == 0
    assert team_form.fields["project"].queryset.count() == 0
    assert team_form.fields["team_lead"].queryset.count() == 0
    assert locale_form.fields["project"].queryset.count() == 0
    assert all(
        "custom_" not in name
        for form in (project_form, team_form, locale_form)
        for name in form.fields
    )


def test_masterdataconfiguration_forms_mixin_is_on_all_five_forms(db, tenant_a, admin_user):
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    forms = [
        ProjectForm(tenant=tenant_a),
        TaskForm(tenant=tenant_a),
        MilestoneForm(tenant=tenant_a),
        ProjectRiskForm(tenant=tenant_a),
        ProjectTeamForm(tenant=tenant_a),
    ]

    assert all(isinstance(form, ProjectCustomFieldFormMixin) for form in forms)
    assert ProjectTask._meta.model_name == "projecttask"
    assert ProjectMilestone._meta.model_name == "projectmilestone"
    assert ProjectRisk._meta.model_name == "projectrisk"
    assert ProjectTeam._meta.model_name == "projectteam"
