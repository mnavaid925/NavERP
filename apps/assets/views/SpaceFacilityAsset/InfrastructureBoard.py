"""Views for the dedicated Infrastructure Asset Management Board (11.17)."""

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.assets.models.SpaceFacilityAsset.AssetBuildingSystems import AssetBuildingSystem
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.views._common import assets_scope
from apps.assets.views.SpaceFacilityAsset._helpers import PAGE_SIZE
from apps.assets.views.SpaceFacilityAsset.AssetBuildingSystems import _filtered_systems_queryset


@login_required
def asset_infrastructure_board(request):
    """Dedicated Infrastructure Asset Management register covering electrical, plumbing, elevators, fire/life-safety, and structural systems."""
    infra_domains = AssetBuildingSystem.INFRASTRUCTURE_DOMAINS
    infra_domain_choices = [
        choice for choice in AssetBuildingSystem.SYSTEM_DOMAIN_CHOICES if choice[0] in infra_domains
    ]

    base_qs, qs, q, today = _filtered_systems_queryset(request, infra_only=True)
    kpis = base_qs.aggregate(
        total=Count("id"),
        life_safety=Count("id", filter=Q(criticality_tier="tier_1_life_safety")),
        poor_critical=Count("id", filter=Q(condition_grade__in=("poor", "critical"))),
        overdue_insp=Count(
            "id",
            filter=Q(next_inspection_due_date__lt=today) & ~Q(status="decommissioned"),
        ),
        exposure=Sum("replacement_cost_estimate", filter=~Q(status="decommissioned")),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    spaces = (
        assets_scope(AssetFacilitySpace.objects.all(), request)
        .only("id", "number", "code", "name")
        .order_by("code", "name")
    )

    return render(
        request,
        "assets/spacefacilityasset/infrastructure_board.html",
        {
            "systems": page_obj,
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "total_count": kpis["total"] or 0,
            "critical_life_safety_count": kpis["life_safety"] or 0,
            "poor_critical_condition_count": kpis["poor_critical"] or 0,
            "overdue_inspection_count": kpis["overdue_insp"] or 0,
            "total_replacement_exposure": kpis["exposure"] or Decimal("0.00"),
            "domain_choices": infra_domain_choices,
            "condition_choices": AssetBuildingSystem.CONDITION_GRADE_CHOICES,
            "criticality_choices": AssetBuildingSystem.CRITICALITY_TIER_CHOICES,
            "status_choices": AssetBuildingSystem.STATUS_CHOICES,
            "spaces": spaces,
            "search_query": q,
            "today": today,
        },
    )
