"""Sales 8.11 — Views for `CustomerHealthScore`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.CustomerSuccess.CustomerHealthScores import CustomerHealthScoreForm
from apps.sales.models.CustomerSuccess.CustomerHealthScores import (
    HEALTH_BAND_CHOICES,
    RISK_LEVEL_CHOICES,
    TREND_CHOICES,
    CustomerHealthScore,
)


@login_required
def customer_health_score_list(request):
    qs = (
        CustomerHealthScore.objects.filter(tenant=request.tenant)
        .select_related("account")
        .order_by("-evaluation_date", "-overall_score")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(account__name__icontains=q)
            | Q(number__icontains=q)
            | Q(active_alert_message__icontains=q)
            | Q(notes__icontains=q)
        )

    health_band = request.GET.get("health_band", "").strip()
    if health_band:
        qs = qs.filter(health_band=health_band)

    risk_level = request.GET.get("risk_level", "").strip()
    if risk_level:
        qs = qs.filter(risk_level=risk_level)

    account_id = request.GET.get("account", "").strip()
    if account_id and account_id.isdigit():
        qs = qs.filter(account_id=int(account_id))

    is_churn_risk = request.GET.get("is_churn_risk", "").strip()
    if is_churn_risk in ("1", "true", "True"):
        qs = qs.filter(is_churn_risk=True)

    stats = qs.aggregate(
        total_count=Count("id"),
        healthy_count=Count("id", filter=Q(health_band="green")),
        attention_count=Count("id", filter=Q(health_band="yellow")),
        at_risk_count=Count("id", filter=Q(health_band="red")),
        churn_risk_count=Count("id", filter=Q(is_churn_risk=True)),
        avg_score=Avg("overall_score"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    accounts = (
        Party.objects.filter(tenant=request.tenant, roles__role="customer")
        .distinct()
        .order_by("name")
    )

    context = {
        "page_obj": page_obj,
        "health_scores": page_obj.object_list,
        "health_band_choices": HEALTH_BAND_CHOICES,
        "risk_level_choices": RISK_LEVEL_CHOICES,
        "trend_choices": TREND_CHOICES,
        "accounts": accounts,
        "active_filters": {
            "q": q,
            "health_band": health_band,
            "risk_level": risk_level,
            "account": account_id,
            "is_churn_risk": is_churn_risk,
        },
        "stats": stats,
    }
    return render(request, "sales/customersuccess/customerhealthscore/list.html", context)


@login_required
def customer_health_score_detail(request, pk):
    obj = get_object_or_404(
        CustomerHealthScore.objects.filter(tenant=request.tenant).select_related("account"),
        pk=pk,
    )
    return render(
        request,
        "sales/customersuccess/customerhealthscore/detail.html",
        {"obj": obj, "health_score": obj},
    )


@login_required
def customer_health_score_create(request):
    if request.method == "POST":
        form = CustomerHealthScoreForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Evaluated health score for {obj.account.name}: {obj.overall_score} ({obj.get_health_band_display()})",
                tenant=request.tenant,
            )
            messages.success(request, f"Customer health score {obj.number} created successfully.")
            return redirect("sales:customer_health_score_detail", pk=obj.pk)
    else:
        form = CustomerHealthScoreForm(tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customerhealthscore/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@login_required
def customer_health_score_edit(request, pk):
    obj = get_object_or_404(
        CustomerHealthScore.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = CustomerHealthScoreForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated health score {obj.number} for {obj.account.name}",
                tenant=request.tenant,
            )
            messages.success(request, f"Customer health score {obj.number} updated successfully.")
            return redirect("sales:customer_health_score_detail", pk=obj.pk)
    else:
        form = CustomerHealthScoreForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/customersuccess/customerhealthscore/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def customer_health_score_delete(request, pk):
    obj = get_object_or_404(
        CustomerHealthScore.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    account_name = obj.account.name
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted customer health score {number} for {account_name}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Customer health score {number} deleted.")
    return redirect("sales:customer_health_score_list")


@login_required
def customer_health_console(request):
    """Derived Console 1 — Customer Health & Risk Console."""
    all_scores = (
        CustomerHealthScore.objects.filter(tenant=request.tenant)
        .select_related("account")
        .order_by("-evaluation_date", "-overall_score")
    )

    healthy_scores = all_scores.filter(health_band="green")[:10]
    attention_scores = all_scores.filter(health_band="yellow")[:10]
    at_risk_scores = all_scores.filter(health_band="red")[:10]
    churn_alerts = all_scores.filter(is_churn_risk=True)[:10]

    stats = all_scores.aggregate(
        total_count=Count("id"),
        healthy_count=Count("id", filter=Q(health_band="green")),
        attention_count=Count("id", filter=Q(health_band="yellow")),
        at_risk_count=Count("id", filter=Q(health_band="red")),
        churn_alerts_count=Count("id", filter=Q(is_churn_risk=True)),
        avg_overall=Avg("overall_score"),
        avg_product=Avg("product_usage_score"),
        avg_support=Avg("support_ticket_score"),
        avg_nps=Avg("nps_sentiment_score"),
    )

    context = {
        "all_scores": all_scores[:25],
        "healthy_scores": healthy_scores,
        "attention_scores": attention_scores,
        "at_risk_scores": at_risk_scores,
        "churn_alerts": churn_alerts,
        "stats": stats,
    }
    return render(request, "sales/customersuccess/health_console.html", context)
