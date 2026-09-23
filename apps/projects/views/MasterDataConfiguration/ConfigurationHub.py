"""Projects 7.19 — Master Data & Configuration Hub view."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import ProjectCustomField
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSetting
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam, ProjectTeamMember
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate


@login_required
def configuration_hub(request):
    """The landing and operational governance cockpit for project master data & configuration."""
    tenant = request.tenant

    templates_qs = ProjectTemplate.objects.filter(tenant=tenant)
    fields_qs = ProjectCustomField.objects.filter(tenant=tenant)
    teams_qs = ProjectTeam.objects.filter(tenant=tenant)
    locales_qs = ProjectLocaleSetting.objects.filter(tenant=tenant)
    members_qs = ProjectTeamMember.objects.filter(tenant=tenant)

    templates_count = templates_qs.count()
    active_templates = templates_qs.filter(is_active=True).count()
    custom_fields_count = fields_qs.count()
    teams_count = teams_qs.count()
    team_members_count = members_qs.count()
    locale_profiles_count = locales_qs.count()

    stats = {
        "templates_count": templates_count,
        "active_templates": active_templates,
        "custom_fields_count": custom_fields_count,
        "teams_count": teams_count,
        "team_members_count": team_members_count,
        "locale_profiles_count": locale_profiles_count,
    }

    # Methodology distribution
    methodology_counts = {
        row["methodology"]: row["c"]
        for row in templates_qs.values("methodology").annotate(c=Count("id"))
    }
    methodologies = []
    for val, lbl in ProjectTemplate.METHODOLOGY_CHOICES:
        cnt = methodology_counts.get(val, 0)
        pct = round((cnt / templates_count * 100), 1) if templates_count > 0 else 0
        methodologies.append({
            "value": val,
            "label": lbl,
            "count": cnt,
            "percentage": pct,
        })

    # Target entity custom field distribution
    entity_counts = {
        row["target_entity"]: row["c"]
        for row in fields_qs.values("target_entity").annotate(c=Count("id"))
    }
    target_entities = []
    for val, lbl in ProjectCustomField.TARGET_ENTITY_CHOICES:
        cnt = entity_counts.get(val, 0)
        target_entities.append({
            "value": val,
            "label": lbl,
            "count": cnt,
        })

    # Recent active templates
    recent_templates = (
        templates_qs.filter(is_active=True)
        .select_related("project_type", "created_by")
        .order_by("-updated_at")[:5]
    )

    # Recent active teams with member count
    recent_teams = (
        teams_qs.filter(is_active=True)
        .select_related("team_lead", "org_unit", "project")
        .annotate(member_count=Count("members"))
        .order_by("-updated_at")[:5]
    )

    return render(
        request,
        "projects/masterdataconfiguration/boards/hub.html",
        {
            "stats": stats,
            "methodologies": methodologies,
            "target_entities": target_entities,
            "recent_templates": recent_templates,
            "recent_teams": recent_teams,
        },
    )
