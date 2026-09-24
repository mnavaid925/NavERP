import json
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import CustomFieldValue
from apps.projects.models import Project
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import ProjectCustomField
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import (
    ProjectLocaleSetting,
    resolve_project_locale,
)
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeamMember
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate
from apps.projects.tests.masterdataconfiguration_helpers import (
    _masterdataconfiguration_core_definition,
    _masterdataconfiguration_custom_field,
    _masterdataconfiguration_locale,
    _masterdataconfiguration_project,
    _masterdataconfiguration_risk,
    _masterdataconfiguration_task,
    _masterdataconfiguration_team,
    _masterdataconfiguration_team_member,
    _masterdataconfiguration_template,
    _masterdataconfiguration_wbs,
)


def test_masterdataconfiguration_models_numbering(db, tenant_a, admin_user):
    template = _masterdataconfiguration_template(tenant_a, admin_user)
    field = _masterdataconfiguration_custom_field(tenant_a)
    team = _masterdataconfiguration_team(tenant_a, admin_user)
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    locale = _masterdataconfiguration_locale(tenant_a, project)

    assert template.number.startswith("PTM-")
    assert field.number.startswith("PCF-")
    assert team.number.startswith("PTE-")
    assert project.number.startswith("PRJ-")
    assert locale.number.startswith("PLS-")


def test_masterdataconfiguration_models_template_default_is_unique(db, tenant_a, admin_user):
    first = _masterdataconfiguration_template(
        tenant_a,
        admin_user,
        methodology="agile",
        code="MDC-AGILE-1",
        is_default=True,
    )
    second = ProjectTemplate(
        tenant=tenant_a,
        name="Second default",
        code="MDC-AGILE-2",
        methodology="agile",
        is_default=True,
    )

    with pytest.raises(ValidationError):
        second.full_clean()


def test_masterdataconfiguration_models_template_rejects_invalid_wbs(db, tenant_a, admin_user):
    template = ProjectTemplate(
        tenant=tenant_a,
        name="Invalid WBS",
        methodology="hybrid",
        wbs_structure=[{
            "phase": "Invalid",
            "tasks": [{
                "name": "Bad task",
                "duration_days": 1,
                "estimation_method": "invented",
                "confidence": "unknown",
            }],
        }],
    )

    with pytest.raises(ValidationError):
        template.full_clean()


def test_masterdataconfiguration_models_template_valid_wbs_counts(db, tenant_a, admin_user):
    template = _masterdataconfiguration_template(tenant_a, admin_user)

    assert len(template.wbs_structure) == 2
    assert template.get_methodology_badge() == "badge-info"
    assert template.target_budget >= Decimal("0.00")
    assert json.dumps(template.workflow_config)


def test_masterdataconfiguration_models_custom_definition_sync_and_history(db, tenant_a, admin_user):
    definition = _masterdataconfiguration_custom_field(tenant_a)
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    core = _masterdataconfiguration_core_definition(definition)
    value = CustomFieldValue.objects.create(
        tenant=tenant_a,
        definition=core,
        entity_label="projects.Project",
        object_id=project.pk,
        value="CLIENT-1",
        updated_by=admin_user,
    )

    definition.delete()

    core.refresh_from_db()
    assert core.is_active is False
    assert CustomFieldValue.objects.filter(pk=value.pk).exists()


def test_masterdataconfiguration_models_custom_field_validation(db, tenant_a):
    invalid = ProjectCustomField(
        tenant=tenant_a,
        name="Bad",
        field_key="bad",
        label="Bad",
        field_type="select",
        choices_list=["A", "A"],
    )

    with pytest.raises(ValidationError):
        invalid.full_clean()


def test_masterdataconfiguration_models_team_current_member_count(db, tenant_a, admin_user, member_user):
    team = _masterdataconfiguration_team(tenant_a, admin_user)
    current = _masterdataconfiguration_team_member(tenant_a, team, member_user)
    departed = _masterdataconfiguration_team_member(
        tenant_a,
        team,
        admin_user,
        left_date=timezone.localdate(),
    )

    assert current.is_current is True
    assert departed.is_current is False
    assert team.member_count() == 1
    assert team.members.count() == 2


def test_masterdataconfiguration_models_team_member_tenant_guard(db, tenant_a, tenant_b, admin_user):
    team = _masterdataconfiguration_team(tenant_a, admin_user)
    member = ProjectTeamMember(
        tenant=tenant_b,
        team=team,
        user=admin_user,
        allocation_percentage=10,
    )

    with pytest.raises(ValidationError):
        member.full_clean()


def test_masterdataconfiguration_models_locale_resolver_prefers_override(db, tenant_a, admin_user):
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    override = _masterdataconfiguration_locale(
        tenant_a,
        project,
        working_hours_per_day="7.50",
        working_days_pattern=[1, 2, 3, 4, 5],
    )
    resolved = resolve_project_locale(project)

    assert resolved["override"] == override
    assert resolved["working_hours_per_day"] == Decimal("7.50")
    assert resolved["working_days"] == [1, 2, 3, 4, 5]


def test_masterdataconfiguration_models_locale_rejects_cross_tenant_project(db, tenant_a, tenant_b, admin_user):
    project = _masterdataconfiguration_project(tenant_b, admin_user)
    locale = ProjectLocaleSetting(
        tenant=tenant_a,
        name="Invalid",
        project=project,
        working_days_pattern=[1, 2, 3, 4, 5],
    )

    with pytest.raises(ValidationError):
        locale.full_clean()


def test_masterdataconfiguration_models_workflow_schema_and_wbs_bounds(db, tenant_a, admin_user):
    template = _masterdataconfiguration_template(
        tenant_a,
        admin_user,
        wbs_structure=_masterdataconfiguration_wbs(),
        workflow_config={"rules": []},
    )

    assert template.wbs_structure[0]["phase"] == "Discovery"
    assert isinstance(template.estimated_duration_days, int)
    assert template.estimated_duration_days <= 3650
    assert _masterdataconfiguration_wbs()[0]["tasks"]
