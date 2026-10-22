"""Sales 8.15 — Contract & Subscription Workspace view."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.ContractSubscriptionManagement.CustomerSubscriptions import CustomerSubscription
from apps.sales.models.ContractSubscriptionManagement.UsageMeterRecords import UsageMeterRecord
from apps.sales.models.ContractSubscriptionManagement.ContractObligations import ContractObligation


@login_required
def contract_subscription_workspace(request):
    tenant = request.tenant
    today = timezone.localdate()
    in_30_days = today + timedelta(days=30)
    in_60_days = today + timedelta(days=60)

    # Contracts aggregates
    contracts_qs = CustomerContract.objects.filter(tenant=tenant)
    active_contracts_count = contracts_qs.filter(status="active").count()
    total_tcv = contracts_qs.filter(status="active").aggregate(total=Sum("total_contract_value"))["total"] or Decimal("0.00")

    # Subscriptions aggregates
    subs_qs = CustomerSubscription.objects.filter(tenant=tenant)
    total_mrr = subs_qs.filter(status="active").aggregate(total=Sum("mrr"))["total"] or Decimal("0.00")
    total_arr = (total_mrr * Decimal("12.00")).quantize(Decimal("0.01"))

    # Expirations radar
    expiring_30_count = contracts_qs.filter(status="active", end_date__gte=today, end_date__lte=in_30_days).count()
    expiring_60_count = contracts_qs.filter(status="active", end_date__gt=in_30_days, end_date__lte=in_60_days).count()

    # Usage Overages
    usage_qs = UsageMeterRecord.objects.filter(tenant=tenant)
    unbilled_overages_total = usage_qs.filter(status="calculated").aggregate(total=Sum("overage_total_charge"))["total"] or Decimal("0.00")

    # SLA Compliance
    obligations_qs = ContractObligation.objects.filter(tenant=tenant)
    total_obligations = obligations_qs.count()
    fulfilled_obligations = obligations_qs.filter(status="fulfilled").count()
    sla_compliance_rate = round((fulfilled_obligations / total_obligations * 100), 1) if total_obligations > 0 else 100.0

    # Urgent tables
    urgent_contracts = contracts_qs.filter(
        status="active",
        end_date__gte=today,
        end_date__lte=in_60_days,
    ).select_related("account", "owner").order_date() if hasattr(contracts_qs, "order_date") else contracts_qs.filter(
        status="active",
        end_date__gte=today,
        end_date__lte=in_60_days,
    ).select_related("account", "owner").order_by("end_date")[:5]

    urgent_subscriptions = subs_qs.filter(
        status="active",
        current_term_end__gte=today,
        current_term_end__lte=in_60_days,
    ).select_related("account").order_by("current_term_end")[:5]

    at_risk_obligations = obligations_qs.filter(
        status__in=["at_risk", "breached"]
    ).select_related("contract", "assigned_to")[:5]

    context = {
        "active_contracts_count": active_contracts_count,
        "total_tcv": total_tcv,
        "total_arr": total_arr,
        "total_mrr": total_mrr,
        "expiring_30_count": expiring_30_count,
        "expiring_60_count": expiring_60_count,
        "unbilled_overages_total": unbilled_overages_total,
        "sla_compliance_rate": sla_compliance_rate,
        "urgent_contracts": urgent_contracts,
        "urgent_subscriptions": urgent_subscriptions,
        "at_risk_obligations": at_risk_obligations,
    }
    return render(request, "sales/contractsubscriptionmanagement/boards/contract_subscription_workspace.html", context)
