"""Sales 8.12 — Views for `RepPerformanceScorecard`.

Function-based views over the 8.12 Rep Performance Scorecard. Every queryset is
tenant-scoped, every write is audit-logged, and every integer FK filter is
guarded by ``_pk_filter`` (``.isdigit()`` plus a 64-bit range bound) so a
hand-edited URL is ignored rather than a 500 (L11).

``accounting.Currency`` is a **GLOBAL** master with no ``tenant`` FK (L29), so
the currency dropdown is deliberately NOT tenant-filtered — filtering it would
return an empty list. ``sales.QuotaPlan`` has **no ``name`` field**, so the
quota-plan dropdown is ordered by ``-created_at``.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Territory
from apps.sales.forms.SalesAnalytics.RepPerformanceScorecards import RepPerformanceScorecardForm
from apps.sales.models.SalesAnalytics.RepPerformanceScorecards import (
    SCORECARD_RATING_CHOICES,
    SCORECARD_STATUS_CHOICES,
    RepPerformanceScorecard,
)
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import QuotaPlan
from apps.sales.views.SalesAnalytics._helpers import _pk_filter


@login_required
def rep_performance_scorecard_list(request):
    qs = RepPerformanceScorecard.objects.filter(tenant=request.tenant).select_related(
        "rep",
        "territory",
        "manager",
        "currency",
        "quota_plan",
        "forecast_period",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(rep__username__icontains=q)
            | Q(rep__first_name__icontains=q)
            | Q(rep__last_name__icontains=q)
            | Q(strengths__icontains=q)
            | Q(notes__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    rating = request.GET.get("rating", "").strip()
    if rating:
        qs = qs.filter(rating=rating)

    rep_id = request.GET.get("rep", "").strip()
    rep_pk = _pk_filter(rep_id)
    if rep_pk is not None:
        qs = qs.filter(rep_id=rep_pk)

    territory_id = request.GET.get("territory", "").strip()
    territory_pk = _pk_filter(territory_id)
    if territory_pk is not None:
        qs = qs.filter(territory_id=territory_pk)

    period_id = request.GET.get("forecast_period", "").strip()
    period_pk = _pk_filter(period_id)
    if period_pk is not None:
        qs = qs.filter(forecast_period_id=period_pk)

    aggregate = qs.aggregate(
        total_count=Count("id"),
        avg_win_rate_pct=Avg("win_rate_pct"),
        total_revenue_closed=Sum("revenue_closed"),
        avg_quota_attainment_pct=Avg("quota_attainment_pct"),
        on_track_count=Count(
            "id",
            filter=Q(rating__in=["outstanding", "strong", "on_track"]),
        ),
    )
    stats = {
        "total_count": aggregate["total_count"],
        "avg_win_rate_pct": aggregate["avg_win_rate_pct"],
        "total_revenue_closed": aggregate["total_revenue_closed"],
        "avg_quota_attainment_pct": aggregate["avg_quota_attainment_pct"],
        "on_track_count": aggregate["on_track_count"],
    }

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    users = User.objects.filter(tenant=request.tenant, is_active=True).order_by("username")
    territories = Territory.objects.filter(tenant=request.tenant).order_by("name")
    # Currency is GLOBAL — no tenant FK (L29) — so it is NOT tenant-filtered.
    currencies = Currency.objects.all().order_by("code")
    # QuotaPlan has no `name` field; ordering by it would raise FieldError.
    quota_plans = QuotaPlan.objects.filter(tenant=request.tenant).order_by("-created_at")
    forecast_periods = ForecastPeriod.objects.filter(tenant=request.tenant).order_by("-start_date")

    context = {
        "scorecards": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status_choices": SCORECARD_STATUS_CHOICES,
        "rating_choices": SCORECARD_RATING_CHOICES,
        "reps": users,
        "territories": territories,
        "managers": users,
        "currencies": currencies,
        "quota_plans": quota_plans,
        "forecast_periods": forecast_periods,
        "stats": stats,
        "active_filters": {
            "q": q,
            "status": status,
            "rating": rating,
            "rep": rep_id,
            "territory": territory_id,
            "forecast_period": period_id,
        },
    }
    return render(request, "sales/salesanalytics/repperformancescorecard/list.html", context)


@login_required
def rep_performance_scorecard_detail(request, pk):
    obj = get_object_or_404(
        RepPerformanceScorecard.objects.filter(tenant=request.tenant).select_related(
            "rep",
            "territory",
            "manager",
            "currency",
            "quota_plan",
            "forecast_period",
            "coaching_scorecard",
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/salesanalytics/repperformancescorecard/detail.html",
        {"obj": obj, "scorecard": obj},
    )


@tenant_admin_required
def rep_performance_scorecard_create(request):
    if request.method == "POST":
        form = RepPerformanceScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Recorded rep performance scorecard {obj.number} for {obj.rep}",
                tenant=request.tenant,
            )
            messages.success(request, f"Rep performance scorecard {obj.number} created successfully.")
            return redirect("sales:rep_performance_scorecard_detail", pk=obj.pk)
    else:
        form = RepPerformanceScorecardForm(tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/repperformancescorecard/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@tenant_admin_required
def rep_performance_scorecard_edit(request, pk):
    obj = get_object_or_404(
        RepPerformanceScorecard.objects.filter(tenant=request.tenant).select_related(
            "rep",
            "territory",
            "manager",
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = RepPerformanceScorecardForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated rep performance scorecard {obj.number} for {obj.rep}",
                tenant=request.tenant,
            )
            messages.success(request, f"Rep performance scorecard {obj.number} updated successfully.")
            return redirect("sales:rep_performance_scorecard_detail", pk=obj.pk)
    else:
        form = RepPerformanceScorecardForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/repperformancescorecard/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def rep_performance_scorecard_delete(request, pk):
    obj = get_object_or_404(
        RepPerformanceScorecard.objects.filter(tenant=request.tenant).select_related("rep"),
        pk=pk,
    )
    number = obj.number
    rep_name = str(obj.rep) if obj.rep_id else "—"
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted rep performance scorecard {number} for {rep_name}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Rep performance scorecard {number} deleted.")
    return redirect("sales:rep_performance_scorecard_list")
