from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import FixedAsset
from apps.assets.forms.AssetPerformance.AssetPerformanceScorecards import AssetPerformanceScorecardForm
from apps.assets.models.AssetPerformance.AssetPerformanceScorecards import AssetPerformanceScorecard
from apps.assets.views._common import assets_object
from apps.core.utils import write_audit_log


@login_required
def asset_performance_scorecard_list(request):
    qs = AssetPerformanceScorecard.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "department", "evaluated_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(executive_summary__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(department__name__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_period = request.GET.get("period_type", "").strip()
    if selected_period:
        qs = qs.filter(period_type=selected_period)

    selected_grade = request.GET.get("grade", "").strip()
    if selected_grade:
        qs = qs.filter(benchmark_grade=selected_grade)

    fixed_asset_id = request.GET.get("fixed_asset", "").strip()
    if fixed_asset_id.isdigit():
        qs = qs.filter(fixed_asset_id=int(fixed_asset_id))

    all_tenant_scorecards = AssetPerformanceScorecard.objects.filter(tenant=request.tenant)
    agg = all_tenant_scorecards.aggregate(
        total_scorecards=Count("id"),
        avg_utilization=Avg("capacity_utilization_rate"),
        avg_mtbf=Avg("mtbf_hours"),
        grade_a_count=Count("id", filter=Q(benchmark_grade="grade_a")),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    fixed_assets = FixedAsset.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status": selected_status,
        "period_type": selected_period,
        "grade": selected_grade,
        "fixed_asset_id": fixed_asset_id,
        "status_choices": AssetPerformanceScorecard.STATUS_CHOICES,
        "period_choices": AssetPerformanceScorecard.PERIOD_TYPE_CHOICES,
        "grade_choices": AssetPerformanceScorecard.BENCHMARK_GRADE_CHOICES,
        "fixed_assets": fixed_assets,
        "status_css": AssetPerformanceScorecard.STATUS_CSS,
        "period_css": AssetPerformanceScorecard.PERIOD_CSS,
        "grade_css": AssetPerformanceScorecard.GRADE_CSS,
        "agg": agg,
    }
    return render(request, "assets/asset_performance/asset_performance_scorecard/list.html", context)


@login_required
def asset_performance_scorecard_detail(request, pk):
    scorecard = assets_object(
        request,
        AssetPerformanceScorecard,
        pk,
        select_related=["fixed_asset", "operational_asset", "department", "evaluated_by"],
    )
    context = {
        "scorecard": scorecard,
        "status_css": AssetPerformanceScorecard.STATUS_CSS,
        "period_css": AssetPerformanceScorecard.PERIOD_CSS,
        "grade_css": AssetPerformanceScorecard.GRADE_CSS,
    }
    return render(request, "assets/asset_performance/asset_performance_scorecard/detail.html", context)


@login_required
def asset_performance_scorecard_create(request):
    if request.method == "POST":
        form = AssetPerformanceScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save(commit=False)
            scorecard.tenant = request.tenant
            if not scorecard.evaluated_by:
                scorecard.evaluated_by = request.user
            scorecard.save()
            write_audit_log(request.user, scorecard, "create", tenant=request.tenant)
            messages.success(request, f"Scorecard {scorecard.number} created with API Score {scorecard.performance_index_score}.")
            return redirect("assets:asset_performance_scorecard_detail", pk=scorecard.pk)
    else:
        today = timezone.now().date()
        first_of_month = today.replace(day=1)
        initial = {
            "period_type": "monthly",
            "period_start": first_of_month,
            "period_end": today,
            "total_calendar_hours": Decimal("720.00"),
            "planned_operating_hours": Decimal("480.00"),
            "evaluated_by": request.user.pk,
        }
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id and fixed_asset_id.isdigit():
            initial["fixed_asset"] = int(fixed_asset_id)
        form = AssetPerformanceScorecardForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "scorecard": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_performance/asset_performance_scorecard/form.html", context)


@login_required
def asset_performance_scorecard_edit(request, pk):
    scorecard = assets_object(request, AssetPerformanceScorecard, pk)
    if request.method == "POST":
        form = AssetPerformanceScorecardForm(request.POST, instance=scorecard, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save()
            write_audit_log(request.user, scorecard, "update", tenant=request.tenant)
            messages.success(request, f"Scorecard {scorecard.number} updated. Recalculated Score: {scorecard.performance_index_score}.")
            return redirect("assets:asset_performance_scorecard_detail", pk=scorecard.pk)
    else:
        form = AssetPerformanceScorecardForm(instance=scorecard, tenant=request.tenant)

    context = {
        "form": form,
        "scorecard": scorecard,
        "is_edit": True,
    }
    return render(request, "assets/asset_performance/asset_performance_scorecard/form.html", context)


@login_required
@require_POST
def asset_performance_scorecard_delete(request, pk):
    scorecard = assets_object(request, AssetPerformanceScorecard, pk)
    number = scorecard.number
    write_audit_log(request.user, scorecard, "delete", tenant=request.tenant)
    scorecard.delete()
    messages.success(request, f"Scorecard {number} deleted.")
    return redirect("assets:asset_performance_scorecard_list")


@login_required
@require_POST
def asset_performance_scorecard_publish(request, pk):
    scorecard = assets_object(request, AssetPerformanceScorecard, pk)
    scorecard.status = "published"
    scorecard.save()
    write_audit_log(request.user, scorecard, "publish", tenant=request.tenant)
    messages.success(request, f"Scorecard {scorecard.number} certified and published.")
    return redirect("assets:asset_performance_scorecard_detail", pk=scorecard.pk)
