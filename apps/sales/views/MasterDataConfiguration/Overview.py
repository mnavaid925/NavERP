"""Central Overview Dashboard for 8.19 Master Data & Configuration."""
from django.contrib.auth.decorators import login_required
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

    kpis = {
        "total_price_book_entries": pbe_qs.count(),
        "active_price_book_entries": pbe_qs.filter(is_active=True).count(),
        "total_custom_definitions": sco_qs.count(),
        "active_custom_definitions": sco_qs.filter(is_active=True).count(),
        "total_methodologies": smd_qs.count(),
        "mandatory_gate_methodologies": smd_qs.filter(is_mandatory_gate=True).count(),
        "total_regional_settings": srg_qs.count(),
        "default_regional_profile": srg_qs.filter(is_default=True).first(),
    }

    recent_price_book_entries = pbe_qs.select_related("price_book", "product")[:5]
    recent_custom_entities = sco_qs[:5]
    recent_methodologies = smd_qs.select_related("pipeline", "gating_stage")[:5]
    recent_regional_settings = srg_qs[:5]

    context = {
        "kpis": kpis,
        "recent_price_book_entries": recent_price_book_entries,
        "recent_custom_entities": recent_custom_entities,
        "recent_methodologies": recent_methodologies,
        "recent_regional_settings": recent_regional_settings,
    }
    return render(request, "sales/masterdataconfiguration/overview.html", context)
