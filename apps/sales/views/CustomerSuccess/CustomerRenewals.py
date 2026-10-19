"""Sales 8.11 — Views for `CustomerRenewal`."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.CustomerSuccess.CustomerRenewals import CustomerRenewalForm
from apps.sales.models.CustomerSuccess.CustomerRenewals import (
    CHURN_RISK_CHOICES,
    STAGE_CHOICES,
    CustomerRenewal,
)


@login_required
def customer_renewal_list(request):
    qs = (
        CustomerRenewal.objects.filter(tenant=request.tenant)
        .select_related("account", "owner", "currency", "expansion_opportunity", "original_order")
        .order_by("renewal_date", "-current_arr")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(renewal_name__icontains=q)
            | Q(number__icontains=q)
            | Q(contract_reference__icontains=q)
            | Q(account__name__icontains=q)
            | Q(notes__icontains=q)
        )

    stage = request.GET.get("stage", "").strip()
    if stage:
        qs = qs.filter(stage=stage)

    churn_risk = request.GET.get("churn_risk_flag", "").strip()
    if churn_risk:
        qs = qs.filter(churn_risk_flag=churn_risk)

    account_id = request.GET.get("account", "").strip()
    if account_id and account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))

    owner_id = request.GET.get("owner", "").strip()
    if owner_id and owner_id.isdigit():
        qs = qs.filter(owner_id=int(owner_id))

    stats = qs.aggregate(
        total_count=Count("id"),
        total_arr=Sum("current_arr"),
        projected_arr=Sum("projected_renewal_arr"),
        expansion_arr=Sum("expansion_amount"),
        churn_risk_count=Count("id", filter=Q(churn_risk_flag__in=["high", "critical"])),
        renewed_count=Count("id", filter=Q(stage__in=["renewed", "expanded"])),
        upcoming_count=Count("id", filter=Q(stage="upcoming")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    accounts = (
        Party.objects.filter(tenant=request.tenant, roles__role="customer")
        .distinct()
        .order_by("name")
    )
    owners = User.objects.filter(tenant=request.tenant).order_by("username")

    context = {
        "page_obj": page_obj,
        "renewals": page_obj.object_list,
        "stage_choices": STAGE_CHOICES,
        "churn_risk_choices": CHURN_RISK_CHOICES,
        "accounts": accounts,
        "owners": owners,
        "active_filters": {
            "q": q,
            "stage": stage,
            "churn_risk_flag": churn_risk,
            "account": account_id,
            "owner": owner_id,
        },
        "stats": stats,
    }
    return render(request, "sales/customersuccess/customerrenewal/list.html", context)


@login_required
def customer_renewal_detail(request, pk):
    obj = get_object_or_404(
        CustomerRenewal.objects.filter(tenant=request.tenant).select_related(
            "account", "owner", "currency", "expansion_opportunity", "original_order"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/customersuccess/customerrenewal/detail.html",
        {"obj": obj, "renewal": obj},
    )


@login_required
def customer_renewal_create(request):
    if request.method == "POST":
        form = CustomerRenewalForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                "CREATE",
                obj,
                f"Created renewal {obj.number} for {obj.account.name} (ARR: {obj.current_arr} {obj.currency.code})",
            )
            messages.success(request, f"Customer renewal {obj.number} created successfully.")
            return redirect("sales:customer_renewal_detail", pk=obj.pk)
    else:
        form = CustomerRenewalForm(tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customerrenewal/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def customer_renewal_edit(request, pk):
    obj = get_object_or_404(
        CustomerRenewal.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = CustomerRenewalForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                "UPDATE",
                obj,
                f"Updated renewal {obj.number} for {obj.account.name}",
            )
            messages.success(request, f"Customer renewal {obj.number} updated successfully.")
            return redirect("sales:customer_renewal_detail", pk=obj.pk)
    else:
        form = CustomerRenewalForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customerrenewal/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def customer_renewal_delete(request, pk):
    obj = get_object_or_404(
        CustomerRenewal.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    name = obj.renewal_name
    number = obj.number
    obj.delete()
    write_audit_log(
        request.user,
        "DELETE",
        obj,
        f"Deleted customer renewal {number} ({name})",
    )
    messages.success(request, f"Customer renewal {number} deleted.")
    return redirect("sales:customer_renewal_list")


@login_required
def customer_renewal_pipeline(request):
    """Derived Console 2 — Renewal & Retention Pipeline Kanban."""
    all_renewals = (
        CustomerRenewal.objects.filter(tenant=request.tenant)
        .select_related("account", "owner", "currency", "expansion_opportunity")
        .order_by("renewal_date")
    )

    today = timezone.localdate()
    in_30_days = today + timedelta(days=30)
    in_60_days = today + timedelta(days=60)
    in_90_days = today + timedelta(days=90)

    upcoming_30_days = all_renewals.filter(
        renewal_date__gte=today, renewal_date__lte=in_30_days, stage__in=["upcoming", "engagement", "proposal_sent", "negotiation"]
    )
    upcoming_60_days = all_renewals.filter(
        renewal_date__gt=in_30_days, renewal_date__lte=in_60_days, stage__in=["upcoming", "engagement", "proposal_sent", "negotiation"]
    )
    upcoming_90_days = all_renewals.filter(
        renewal_date__gt=in_60_days, renewal_date__lte=in_90_days, stage__in=["upcoming", "engagement", "proposal_sent", "negotiation"]
    )

    renewals_by_stage = {}
    stage_totals = {}
    for stage_code, stage_label in STAGE_CHOICES:
        stage_qs = [r for r in all_renewals if r.stage == stage_code]
        renewals_by_stage[stage_code] = stage_qs
        stage_totals[stage_code] = sum((r.current_arr or Decimal("0.00")) for r in stage_qs)

    stats = all_renewals.aggregate(
        total_count=Count("id"),
        total_arr=Sum("current_arr"),
        projected_arr=Sum("projected_renewal_arr"),
        expansion_arr=Sum("expansion_amount"),
        high_risk_arr=Sum("current_arr", filter=Q(churn_risk_flag__in=["high", "critical"])),
    )

    context = {
        "all_renewals": all_renewals,
        "renewals_by_stage": renewals_by_stage,
        "stage_totals": stage_totals,
        "stage_choices": STAGE_CHOICES,
        "upcoming_30_days": upcoming_30_days,
        "upcoming_60_days": upcoming_60_days,
        "upcoming_90_days": upcoming_90_days,
        "stats": stats,
    }
    return render(request, "sales/customersuccess/renewal_pipeline.html", context)
