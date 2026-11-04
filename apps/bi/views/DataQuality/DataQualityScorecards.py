from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.DataQuality.DataQualityScorecardForms import DataQualityScorecardForm
from apps.bi.models.DataQuality.DataQualityExceptions import DataQualityException
from apps.bi.models.DataQuality.DataQualityRules import DataQualityRule
from apps.bi.models.DataQuality.DataQualityScorecards import DataQualityScorecard
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def data_quality_scorecard_list(request):
    queryset = (
        bi_scope(DataQualityScorecard.objects.all(), request)
        .select_related("warehouse_table", "semantic_model", "data_mart", "org_unit", "steward")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    scope_type_filter = request.GET.get("scope_type", "").strip()
    if scope_type_filter:
        queryset = queryset.filter(scope_type=scope_type_filter)

    grade_filter = request.GET.get("grade", "").strip()
    if grade_filter:
        queryset = queryset.filter(grade=grade_filter)

    health_status_filter = request.GET.get("health_status", "").strip()
    if health_status_filter:
        queryset = queryset.filter(health_status=health_status_filter)

    total_count = bi_scope(DataQualityScorecard.objects.all(), request).count()
    grade_a_count = bi_scope(DataQualityScorecard.objects.all(), request).filter(grade="A").count()
    sla_breached_count = bi_scope(DataQualityScorecard.objects.all(), request).filter(meets_sla=False).count()

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "scorecards": page_obj,
        "scope_type_choices": DataQualityScorecard.SCOPE_TYPE_CHOICES,
        "grade_choices": DataQualityScorecard.GRADE_CHOICES,
        "health_status_choices": DataQualityScorecard.HEALTH_STATUS_CHOICES,
        "total_count": total_count,
        "grade_a_count": grade_a_count,
        "sla_breached_count": sla_breached_count,
    }
    return render(request, "bi/data_quality/data_quality_scorecard/list.html", context)


@login_required
def data_quality_scorecard_detail(request, pk):
    scorecard = bi_object(
        request,
        DataQualityScorecard,
        pk,
        select_related=["warehouse_table", "semantic_model", "data_mart", "org_unit", "steward"],
    )

    # Resolve evaluated rules based on scope
    rules_qs = bi_scope(DataQualityRule.objects.all(), request)
    exceptions_qs = bi_scope(DataQualityException.objects.all(), request).filter(status__in=["open", "investigating"])

    if scorecard.scope_type == "warehouse_table" and scorecard.warehouse_table:
        evaluated_rules = rules_qs.filter(warehouse_table=scorecard.warehouse_table)[:25]
        related_exceptions = exceptions_qs.filter(warehouse_table=scorecard.warehouse_table)[:15]
    elif scorecard.scope_type == "semantic_model" and scorecard.semantic_model:
        evaluated_rules = rules_qs.filter(semantic_model=scorecard.semantic_model)[:25]
        related_exceptions = exceptions_qs.filter(semantic_model=scorecard.semantic_model)[:15]
    elif scorecard.scope_type == "data_mart" and scorecard.data_mart:
        evaluated_rules = rules_qs.filter(
            Q(warehouse_table__data_mart=scorecard.data_mart) | Q(semantic_model__data_mart=scorecard.data_mart)
        )[:25]
        related_exceptions = exceptions_qs.filter(
            Q(warehouse_table__data_mart=scorecard.data_mart) | Q(semantic_model__data_mart=scorecard.data_mart)
        )[:15]
    else:
        evaluated_rules = rules_qs[:25]
        related_exceptions = exceptions_qs[:15]

    context = {
        "scorecard": scorecard,
        "evaluated_rules": evaluated_rules,
        "related_exceptions": related_exceptions,
    }
    return render(request, "bi/data_quality/data_quality_scorecard/detail.html", context)


@login_required
def data_quality_scorecard_create(request):
    if request.method == "POST":
        form = DataQualityScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save(commit=False)
            scorecard.tenant = request.tenant
            scorecard.save()
            write_audit_log(request.user, scorecard, "create", tenant=request.tenant)
            messages.success(request, f"Quality scorecard '{scorecard.name}' created successfully.")
            return redirect("bi:data_quality_scorecard_detail", pk=scorecard.pk)
    else:
        form = DataQualityScorecardForm(tenant=request.tenant)

    context = {
        "form": form,
        "scorecard": None,
        "is_edit": False,
    }
    return render(request, "bi/data_quality/data_quality_scorecard/form.html", context)


@login_required
def data_quality_scorecard_edit(request, pk):
    scorecard = bi_object(request, DataQualityScorecard, pk)
    if request.method == "POST":
        form = DataQualityScorecardForm(request.POST, instance=scorecard, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save()
            write_audit_log(request.user, scorecard, "update", tenant=request.tenant)
            messages.success(request, f"Quality scorecard '{scorecard.name}' updated successfully.")
            return redirect("bi:data_quality_scorecard_detail", pk=scorecard.pk)
    else:
        form = DataQualityScorecardForm(instance=scorecard, tenant=request.tenant)

    context = {
        "form": form,
        "scorecard": scorecard,
        "is_edit": True,
    }
    return render(request, "bi/data_quality/data_quality_scorecard/form.html", context)


@login_required
@require_POST
def data_quality_scorecard_delete(request, pk):
    scorecard = bi_object(request, DataQualityScorecard, pk)
    sc_name = scorecard.name
    write_audit_log(request.user, scorecard, "delete", tenant=request.tenant)
    scorecard.delete()
    messages.success(request, f"Quality scorecard '{sc_name}' deleted successfully.")
    return redirect("bi:data_quality_scorecard_list")


@login_required
@require_POST
def data_quality_scorecard_recalculate(request, pk):
    scorecard = bi_object(request, DataQualityScorecard, pk)
    now = timezone.now()

    # Query matching rules and exceptions
    rules_qs = bi_scope(DataQualityRule.objects.all(), request)
    exceptions_qs = bi_scope(DataQualityException.objects.all(), request)

    if scorecard.scope_type == "warehouse_table" and scorecard.warehouse_table:
        rules_qs = rules_qs.filter(warehouse_table=scorecard.warehouse_table)
        exceptions_qs = exceptions_qs.filter(warehouse_table=scorecard.warehouse_table)
    elif scorecard.scope_type == "semantic_model" and scorecard.semantic_model:
        rules_qs = rules_qs.filter(semantic_model=scorecard.semantic_model)
        exceptions_qs = exceptions_qs.filter(semantic_model=scorecard.semantic_model)
    elif scorecard.scope_type == "data_mart" and scorecard.data_mart:
        rules_qs = rules_qs.filter(
            Q(warehouse_table__data_mart=scorecard.data_mart) | Q(semantic_model__data_mart=scorecard.data_mart)
        )
        exceptions_qs = exceptions_qs.filter(
            Q(warehouse_table__data_mart=scorecard.data_mart) | Q(semantic_model__data_mart=scorecard.data_mart)
        )

    rule_counts = rules_qs.aggregate(
        total=Count("id"),
        passed=Count("id", filter=Q(last_status="passed")),
        failed=Count("id", filter=Q(last_status__in=["failed", "error"])),
    )
    total_rules = rule_counts["total"]
    passed_rules = rule_counts["passed"]
    failed_rules = rule_counts["failed"]

    exc_counts = exceptions_qs.aggregate(
        open_exc=Count("id", filter=Q(status__in=["open", "investigating"])),
        critical_exc=Count("id", filter=Q(status__in=["open", "investigating"], severity__in=["critical", "fatal"])),
    )
    open_exceptions = exc_counts["open_exc"]
    critical_exceptions = exc_counts["critical_exc"]

    # Calculate dimension scores or defaults
    dim_defaults = {
        "completeness": Decimal("99.20"),
        "accuracy": Decimal("98.50"),
        "consistency": Decimal("97.80"),
        "timeliness": Decimal("100.00"),
        "uniqueness": Decimal("99.90"),
        "validity": Decimal("96.40"),
    }
    dim_rows = rules_qs.values("dimension").annotate(avg_pass=Avg("pass_rate_pct"))
    dim_avgs = {r["dimension"]: r["avg_pass"] for r in dim_rows}

    def get_dim_score(dim_name):
        avg = dim_avgs.get(dim_name)
        return Decimal(str(round(avg, 2))) if avg is not None else dim_defaults[dim_name]

    scorecard.completeness_score = get_dim_score("completeness")
    scorecard.accuracy_score = get_dim_score("accuracy")
    scorecard.consistency_score = get_dim_score("consistency")
    scorecard.timeliness_score = get_dim_score("timeliness")
    scorecard.uniqueness_score = get_dim_score("uniqueness")
    scorecard.validity_score = get_dim_score("validity")

    # Weighted or overall average
    dims = [
        scorecard.completeness_score,
        scorecard.accuracy_score,
        scorecard.consistency_score,
        scorecard.timeliness_score,
        scorecard.uniqueness_score,
        scorecard.validity_score,
    ]
    overall = sum(dims) / Decimal(len(dims))
    scorecard.overall_quality_score = Decimal(str(round(overall, 2)))

    # Determine Grade & Health Status
    if scorecard.overall_quality_score >= Decimal("95.00"):
        scorecard.grade = "A"
    elif scorecard.overall_quality_score >= Decimal("85.00"):
        scorecard.grade = "B"
    elif scorecard.overall_quality_score >= Decimal("75.00"):
        scorecard.grade = "C"
    elif scorecard.overall_quality_score >= Decimal("60.00"):
        scorecard.grade = "D"
    else:
        scorecard.grade = "F"

    scorecard.meets_sla = (scorecard.overall_quality_score >= scorecard.target_quality_score)
    if scorecard.meets_sla and critical_exceptions == 0:
        scorecard.health_status = "healthy"
    elif critical_exceptions > 0:
        scorecard.health_status = "critical"
    elif not scorecard.meets_sla:
        scorecard.health_status = "needs_attention"
    else:
        scorecard.health_status = "failing"

    scorecard.total_rules_evaluated = total_rules
    scorecard.rules_passed_count = passed_rules
    scorecard.rules_failed_count = failed_rules
    scorecard.open_exceptions_count = open_exceptions
    scorecard.critical_exceptions_count = critical_exceptions
    scorecard.last_calculated_at = now
    scorecard.save()

    write_audit_log(
        request.user,
        scorecard,
        "recalculate",
        changes={"score": str(scorecard.overall_quality_score), "grade": scorecard.grade},
        tenant=request.tenant,
    )
    messages.success(request, f"Scorecard '{scorecard.name}' recalculated: Data Trust Index {scorecard.overall_quality_score}% (Grade {scorecard.grade}).")
    return redirect("bi:data_quality_scorecard_detail", pk=scorecard.pk)
