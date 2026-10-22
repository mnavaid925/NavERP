"""Sales 8.15 — Renewal Automation Dashboard view."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote


@login_required
def renewal_automation_dashboard(request):
    tenant = request.tenant
    today = timezone.localdate()
    in_30 = today + timedelta(days=30)
    in_60 = today + timedelta(days=60)
    in_90 = today + timedelta(days=90)

    contracts_qs = CustomerContract.objects.filter(tenant=tenant, status="active")

    # Consolidated horizon counts in a single query
    horizon_agg = contracts_qs.aggregate(
        exp_30=Count("id", filter=Q(end_date__gte=today, end_date__lte=in_30)),
        exp_60=Count("id", filter=Q(end_date__gt=in_30, end_date__lte=in_60)),
        exp_90=Count("id", filter=Q(end_date__gt=in_60, end_date__lte=in_90)),
    )
    expiring_30_days = horizon_agg["exp_30"] or 0
    expiring_60_days = horizon_agg["exp_60"] or 0
    expiring_90_days = horizon_agg["exp_90"] or 0

    upcoming_renewals = list(contracts_qs.filter(
        end_date__gte=today,
        end_date__lte=in_90,
    ).select_related("account", "owner", "currency").order_by("end_date"))

    # Reuse evaluated upcoming renewals for auto-renew candidates without secondary DB query
    auto_renew_candidates = [c for c in upcoming_renewals if c.auto_renew]

    # Projected uplift value
    projected_uplift_value = Decimal("0.00")
    for c in upcoming_renewals:
        if c.price_uplift_pct > Decimal("0.00"):
            base = c.annual_contract_value or c.total_contract_value
            projected_uplift_value += (base * (c.price_uplift_pct / Decimal("100.00"))).quantize(Decimal("0.01"))

    # Linked renewal quotes
    generated_quotes_count = CPQQuote.objects.filter(
        tenant=tenant,
        name__icontains="Renewal",
    ).count()

    context = {
        "upcoming_renewals": upcoming_renewals,
        "auto_renew_candidates": auto_renew_candidates,
        "expiring_30_days": expiring_30_days,
        "expiring_60_days": expiring_60_days,
        "expiring_90_days": expiring_90_days,
        "projected_uplift_value": projected_uplift_value,
        "generated_quotes_count": generated_quotes_count,
    }
    return render(request, "sales/contractsubscriptionmanagement/boards/renewal_automation_dashboard.html", context)
