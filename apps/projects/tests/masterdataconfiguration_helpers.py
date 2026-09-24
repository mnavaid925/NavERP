import json
from decimal import Decimal

from django.utils import timezone

from apps.core.models import CustomFieldDefinition, CustomFieldValue
from apps.projects.models import Project, ProjectMilestone, ProjectRisk, ProjectTask
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import (
    CUSTOM_FIELD_ENTITY_LABELS,
    ProjectCustomField,
)
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSetting
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam, ProjectTeamMember
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate


def _masterdataconfiguration_wbs():
    return [
        {
            "phase": "Discovery",
            "tasks": [
                {"name": "Assessment", "duration_days": 2},
                {"name": "Gate approved", "duration_days": 1, "is_milestone": True, "is_phase_gate": True},
            ],
        },
        {
            "phase": "Delivery",
            "tasks": [
                {"name": "Implementation", "duration_days": 3, "estimation_method": "bottom_up", "confidence": "medium"},
            ],
        },
    ]


def _masterdataconfiguration_template(tenant, user=None, **overrides):
    values = {
        "tenant": tenant,
        "name": "Standard hybrid template",
        "code": "MDC-HYBRID",
        "methodology": "hybrid",
        "category": "software",
        "complexity": "medium",
        "description": "Test template",
        "estimated_duration_days": 10,
        "target_budget": Decimal("10000.00"),
        "default_roles": ["project_manager", "developer"],
        "wbs_structure": _masterdataconfiguration_wbs(),
        "workflow_config": {"rules": []},
        "is_active": True,
        "is_default": False,
        "created_by": user,
    }
    values.update(overrides)
    return ProjectTemplate.objects.create(**values)


def _masterdataconfiguration_custom_field(tenant, **overrides):
    values = {
        "tenant": tenant,
        "name": "Client code",
        "label": "Client code",
        "field_key": "client_code",
        "target_entity": "project",
        "field_type": "text",
        "form_section": "general",
        "description": "Client reference",
        "is_required": True,
        "display_order": 10,
        "is_active": True,
    }
    values.update(overrides)
    return ProjectCustomField.objects.create(**values)


def _masterdataconfiguration_team(tenant, user=None, project=None, **overrides):
    values = {
        "tenant": tenant,
        "name": "Delivery team",
        "code": "MDC-TEAM",
        "team_type": "cross_functional",
        "team_lead": user,
        "project": project,
        "description": "Test team",
        "location": "Remote",
        "is_active": True,
    }
    values.update(overrides)
    return ProjectTeam.objects.create(**values)


def _masterdataconfiguration_team_member(tenant, team, user, **overrides):
    values = {
        "tenant": tenant,
        "team": team,
        "user": user,
        "role": "developer",
        "allocation_percentage": 50,
        "is_primary_contact": False,
        "joined_date": timezone.localdate(),
    }
    values.update(overrides)
    return ProjectTeamMember.objects.create(**values)


def _masterdataconfiguration_locale(tenant, project=None, **overrides):
    values = {
        "tenant": tenant,
        "name": "Project override",
        "code": "MDC-LOCALE",
        "project": project,
        "date_format": "YYYY-MM-DD",
        "time_format": "24h",
        "first_day_of_week": 1,
        "number_format": "#,##0.00",
        "working_hours_per_day": Decimal("8.00"),
        "working_days_pattern": [1, 2, 3, 4, 5],
        "is_default": False,
        "is_active": True,
    }
    values.update(overrides)
    return ProjectLocaleSetting.objects.create(**values)


def _masterdataconfiguration_project(tenant, user=None, **overrides):
    values = {
        "tenant": tenant,
        "name": "Master data project",
        "methodology": "hybrid",
        "status": "draft",
        "created_by": user,
    }
    values.update(overrides)
    return Project.objects.create(**values)


def _masterdataconfiguration_task(tenant, project, user=None, **overrides):
    values = {
        "tenant": tenant,
        "project": project,
        "node_type": "work_package",
        "name": "Master data task",
        "status": "planned",
        "estimation_method": "bottom_up",
        "confidence": "medium",
        "sequence": 1,
        "created_by": user,
    }
    values.update(overrides)
    return ProjectTask.objects.create(**values)


def _masterdataconfiguration_milestone(tenant, project, **overrides):
    values = {
        "tenant": tenant,
        "project": project,
        "name": "Master data milestone",
        "target_date": timezone.localdate(),
        "status": "planned",
    }
    values.update(overrides)
    return ProjectMilestone.objects.create(**values)


def _masterdataconfiguration_risk(tenant, project, user=None, **overrides):
    values = {
        "tenant": tenant,
        "project": project,
        "title": "Master data risk",
        "description": "Test risk",
        "category": "compliance",
        "risk_type": "threat",
        "probability": 2,
        "impact": 2,
        "cost_impact": Decimal("0.00"),
        "response_strategy": "mitigate",
        "identified_date": timezone.localdate(),
        "created_by": user,
    }
    values.update(overrides)
    return ProjectRisk.objects.create(**values)


def _masterdataconfiguration_template_payload(**overrides):
    payload = {
        "name": "Created template",
        "code": "MDC-CREATED",
        "methodology": "agile",
        "category": "software",
        "complexity": "small",
        "description": "Created through the form",
        "estimated_duration_days": "8",
        "target_budget": "5000.00",
        "default_roles_raw": "Project Manager\nDeveloper",
        "wbs_structure_raw": json.dumps(_masterdataconfiguration_wbs()),
        "workflow_config_raw": json.dumps({"rules": []}),
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _masterdataconfiguration_custom_field_payload(**overrides):
    payload = {
        "name": "Client code",
        "field_key": "client_code",
        "label": "Client code",
        "target_entity": "project",
        "field_type": "text",
        "form_section": "general",
        "description": "Client reference",
        "is_required": "on",
        "display_order": "10",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _masterdataconfiguration_team_payload(**overrides):
    payload = {
        "name": "Created team",
        "code": "MDC-CREATED-TEAM",
        "team_type": "cross_functional",
        "description": "Created through the form",
        "location": "Remote",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _masterdataconfiguration_locale_payload(**overrides):
    payload = {
        "name": "Created locale",
        "code": "MDC-CREATED-LOCALE",
        "date_format": "YYYY-MM-DD",
        "time_format": "24h",
        "first_day_of_week": "1",
        "number_format": "#,##0.00",
        "working_hours_per_day": "8.00",
        "working_days_pattern": ["1", "2", "3", "4", "5"],
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _masterdataconfiguration_instantiate_payload(**overrides):
    payload = {
        "project_name": "Instantiated project",
        "project_code": "MDC-INST",
        "start_date": timezone.localdate().isoformat(),
        "target_end_date": "",
        "clone_wbs_tasks": "on",
    }
    payload.update(overrides)
    return payload


def _masterdataconfiguration_project_payload(custom_values=None, **overrides):
    payload = {
        "name": "Custom project",
        "methodology": "hybrid",
    }
    payload.update({f"custom_{key}": value for key, value in (custom_values or {}).items()})
    payload.update(overrides)
    return payload


def _masterdataconfiguration_task_payload(project, custom_values=None, **overrides):
    payload = {
        "project": str(project.pk),
        "node_type": "work_package",
        "name": "Custom task",
        "status": "planned",
        "estimation_method": "bottom_up",
        "confidence": "medium",
        "sequence": "1",
    }
    payload.update({f"custom_{key}": value for key, value in (custom_values or {}).items()})
    payload.update(overrides)
    return payload


def _masterdataconfiguration_milestone_payload(project, custom_values=None, **overrides):
    payload = {
        "project": str(project.pk),
        "name": "Custom milestone",
        "target_date": timezone.localdate().isoformat(),
    }
    payload.update({f"custom_{key}": value for key, value in (custom_values or {}).items()})
    payload.update(overrides)
    return payload


def _masterdataconfiguration_risk_payload(project, custom_values=None, **overrides):
    payload = {
        "project": str(project.pk),
        "title": "Custom risk",
        "description": "Custom risk description",
        "category": "compliance",
        "risk_type": "threat",
        "probability": "2",
        "impact": "2",
        "cost_impact": "0.00",
        "response_strategy": "mitigate",
        "identified_date": timezone.localdate().isoformat(),
    }
    payload.update({f"custom_{key}": value for key, value in (custom_values or {}).items()})
    payload.update(overrides)
    return payload


def _masterdataconfiguration_core_definition(definition):
    return CustomFieldDefinition.objects.get(
        tenant_id=definition.tenant_id,
        module_slug="projects",
        entity_label=CUSTOM_FIELD_ENTITY_LABELS[definition.target_entity],
        field_key=definition.field_key,
    )


def _masterdataconfiguration_custom_value(definition, obj, field_key):
    return CustomFieldValue.objects.get(
        tenant_id=obj.tenant_id,
        entity_label=CUSTOM_FIELD_ENTITY_LABELS[definition.target_entity],
        object_id=obj.pk,
        definition__field_key=field_key,
    )
