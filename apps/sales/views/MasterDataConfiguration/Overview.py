"""Central Overview Dashboard for 8.19 Master Data & Configuration."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.sales.models.MasterDataConfiguration.SalesCustomEntityDefinitions import SalesCustomEntityDefinition
from apps.sales.models.MasterDataConfiguration.SalesMethodologies import SalesMethodology
from apps.sales.models.MasterDataConfiguration.SalesPriceBookEntries import SalesPriceBookEntry
from apps.sales.models.MasterDataConfiguration.SalesRegionalSettings import SalesRegionalSetting


@login_required
def master_data_overview(request):
    """Central Master Data & Configuration Overview Dashboard."""
    tenant = request.tenant

    pbe_qs = SalesPriceBookEntry.objects.filter(tenant=tenant)
    sco_qs = SalesCustomEntityDefinition.objects.filter(tenant=tenant)
    smd_qs = SalesMethodology.objects.filter(tenant=tenant)
    srg_qs = SalesRegionalSetting.objects.filter(tenant=tenant)

    pbe_counts = pbe_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    sco_counts = sco_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    smd_counts = smd_qs.aggregate(
        total=Count("id"),
        mandatory_gates=Count("id", filter=Q(is_mandatory_gate=True)),
    )

    kpis = {
        "total_price_book_entries": pbe_counts["total"] or 0,
        "active_price_book_entries": pbe_counts["active"] or 0,
        "total_custom_definitions": sco_counts["total"] or 0,
        "active_custom_definitions": sco_counts["active"] or 0,
        "total_methodologies": smd_counts["total"] or 0,
        "mandatory_gate_methodologies": smd_counts["mandatory_gates"] or 0,
        "total_regional_settings": srg_qs.count(),
        "default_regional_profile": srg_qs.filter(is_default=True).first(),
    }

    recent_price_book_entries = pbe_qs.select_related("price_book", "product")[:5]
    recent_custom_entities = sco_qs[:5]
    recent_methodologies = smd_qs.select_related("pipeline", "gating_stage")[:5]
    recent_regional_settings = srg_qs[:5]

    context = {
        "kpis": kpis,
        "overview_stats": kpis,
        "recent_price_book_entries": recent_price_book_entries,
        "recent_custom_entities": recent_custom_entities,
        "recent_methodologies": recent_methodologies,
        "recent_regional_settings": recent_regional_settings,
    }
    return render(request, "sales/masterdataconfiguration/overview.html", context)
