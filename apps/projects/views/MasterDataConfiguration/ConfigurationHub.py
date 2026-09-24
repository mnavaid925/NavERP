"""Projects 7.19 — Master Data & Configuration Hub view."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
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
    members_qs = ProjectTeamMember.objects.filter(
        tenant=tenant,
        left_date__isnull=True,
    )

    template_stats = templates_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    field_stats = fields_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    team_stats = teams_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    member_count = members_qs.aggregate(total=Count("id"))["total"] or 0
    locale_stats = locales_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    configured_total = (
        template_stats["total"] + field_stats["total"] + team_stats["total"]
        + locale_stats["total"]
    )
    active_total = (
        template_stats["active"] + field_stats["active"] + team_stats["active"]
        + locale_stats["active"]
    )
    standardization_pct = round((active_total / configured_total) * 100, 1) if configured_total else 0

    stats = {
        "templates_count": template_stats["total"],
        "active_templates": template_stats["active"],
        "custom_fields_count": field_stats["total"],
        "active_custom_fields": field_stats["active"],
        "teams_count": team_stats["total"],
        "active_teams": team_stats["active"],
        "team_members_count": member_count,
        "locale_profiles_count": locale_stats["total"],
        "active_locale_profiles": locale_stats["active"],
        "standardization_pct": standardization_pct,
    }

    # Methodology distribution
    methodology_counts = {
        row["methodology"]: row["c"]
        for row in templates_qs.values("methodology").annotate(c=Count("id"))
    }
    methodologies = []
    for val, lbl in ProjectTemplate.METHODOLOGY_CHOICES:
        cnt = methodology_counts.get(val, 0)
        pct = round((cnt / template_stats["total"] * 100), 1) if template_stats["total"] > 0 else 0
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
        .select_related("created_by")
        .defer("description", "default_roles", "wbs_structure", "workflow_config")
        .order_by("-updated_at", "-id")[:5]
    )

    # Recent active teams with member count
    recent_teams = (
        teams_qs.filter(is_active=True)
        .select_related("team_lead", "org_unit", "project")
        .defer("description")
        .annotate(
            member_count=Coalesce(
                Subquery(
                    ProjectTeamMember.objects.filter(
                        team_id=OuterRef("pk"),
                        tenant_id=OuterRef("tenant_id"),
                        left_date__isnull=True,
                    )
                    .values("team")
                    .annotate(c=Count("id"))
                    .values("c")[:1],
                    output_field=IntegerField(),
                ),
                Value(0),
            )
        )
        .order_by("-updated_at", "-id")[:5]
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
