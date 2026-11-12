"""Views for the dedicated Infrastructure Asset Management Board (11.17)."""

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.assets.models.SpaceFacilityAsset.AssetBuildingSystems import AssetBuildingSystem
from apps.assets.models.SpaceFacilityAsset.AssetFacilitySpaces import AssetFacilitySpace
from apps.assets.views._common import assets_scope
from apps.assets.views.SpaceFacilityAsset._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
)


@login_required
def asset_infrastructure_board(request):
    """Dedicated Infrastructure Asset Management register covering electrical, plumbing, elevators, fire/life-safety, and structural systems."""
    today = timezone.now().date()
    infra_domains = AssetBuildingSystem.INFRASTRUCTURE_DOMAINS
    infra_domain_choices = [
        choice for choice in AssetBuildingSystem.SYSTEM_DOMAIN_CHOICES if choice[0] in infra_domains
    ]

    base_qs = assets_scope(AssetBuildingSystem.objects.all(), request).filter(
        system_domain__in=infra_domains
    )
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

    qs = base_qs.select_related(
        "facility_space",
        "operating_permit",
        "service_vendor",
    ).defer("notes")

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(load_or_voltage_rating__icontains=q)
            | Q(ashrae_nfpa_code_ref__icontains=q)
            | Q(facility_space__code__icontains=q)
        )

    qs = apply_choice_filter(qs, request, "system_domain", allowed_values=dict(infra_domain_choices))
    qs = apply_choice_filter(
        qs, request, "condition_grade", allowed_values=dict(AssetBuildingSystem.CONDITION_GRADE_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "criticality_tier", allowed_values=dict(AssetBuildingSystem.CRITICALITY_TIER_CHOICES)
    )
    qs = apply_choice_filter(
        qs, request, "status", allowed_values=dict(AssetBuildingSystem.STATUS_CHOICES)
    )
    qs = apply_fk_filter(qs, request, "facility_space")

    paginator = Paginator(qs.order_by("criticality_tier", "next_inspection_due_date", "-number"), PAGE_SIZE)
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
