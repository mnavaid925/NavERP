import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.bi.forms.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsightForm
from apps.bi.models.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsight
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def augmented_insight_list(request):
    qs = bi_scope(AugmentedInsight.objects.all(), request).select_related(
        "semantic_model", "kpi_definition", "warehouse_table", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        critical=Count("id", filter=Q(severity="critical")),
        key_drivers=Count("id", filter=Q(insight_type="key_driver")),
    )
    total_count = counts["total"] or 0
    critical_count = counts["critical"] or 0
    key_driver_count = counts["key_drivers"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(metric_name__icontains=q)
            | Q(number__icontains=q)
            | Q(dimension_name__icontains=q)
            | Q(dimension_value__icontains=q)
            | Q(narrative_summary__icontains=q)
        )

    # Filters
    insight_type = request.GET.get("insight_type", "").strip()
    if insight_type:
        qs = qs.filter(insight_type=insight_type)

    impact_direction = request.GET.get("impact_direction", "").strip()
    if impact_direction:
        qs = qs.filter(impact_direction=impact_direction)

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "bi/ai_augmented_analytics/augmented_insight/list.html",
        {
            "insights": page_obj,
            "insight_type_choices": AugmentedInsight.INSIGHT_TYPE_CHOICES,
            "impact_choices": AugmentedInsight.IMPACT_DIRECTION_CHOICES,
            "severity_choices": AugmentedInsight.SEVERITY_CHOICES,
            "status_choices": AugmentedInsight.STATUS_CHOICES,
            "total_count": total_count,
            "critical_count": critical_count,
            "key_driver_count": key_driver_count,
        },
    )


@login_required
def augmented_insight_feed(request):
    qs = bi_scope(AugmentedInsight.objects.all(), request).select_related(
        "semantic_model", "kpi_definition", "warehouse_table", "created_by"
    )

    active_tab = request.GET.get("tab", "all").strip()
    if active_tab == "critical":
        qs = qs.filter(severity="critical")
    elif active_tab == "high":
        qs = qs.filter(severity__in=["critical", "high"])
    elif active_tab == "unfavorable":
        qs = qs.filter(impact_direction="unfavorable")
    elif active_tab == "bookmarked":
        qs = qs.filter(status="bookmarked")

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "bi/ai_augmented_analytics/feed.html",
        {
            "feed_items": page_obj,
            "severity_choices": AugmentedInsight.SEVERITY_CHOICES,
            "impact_choices": AugmentedInsight.IMPACT_DIRECTION_CHOICES,
            "active_tab": active_tab,
        },
    )


@login_required
def augmented_insight_detail(request, pk):
    insight = bi_object(
        request,
        AugmentedInsight,
        pk,
        select_related=("semantic_model", "kpi_definition", "warehouse_table", "created_by"),
    )

    normalized_drivers = []
    raw_drivers = []
    if isinstance(insight.driver_decomposition, list):
        raw_drivers = insight.driver_decomposition
    elif isinstance(insight.driver_decomposition, str) and insight.driver_decomposition.strip():
        try:
            raw_drivers = json.loads(insight.driver_decomposition)
        except json.JSONDecodeError:
            raw_drivers = []
    if isinstance(raw_drivers, list):
        for item in raw_drivers:
            if isinstance(item, dict):
                normalized_drivers.append({
                    "name": item.get("name") or item.get("factor") or item.get("dimension") or "Unknown Driver",
                    "weight": item.get("weight") or item.get("contribution") or 0,
                    "impact": item.get("impact") or item.get("direction") or "neutral",
                    "explanation": item.get("explanation") or item.get("description") or "—",
                })

    return render(
        request,
        "bi/ai_augmented_analytics/augmented_insight/detail.html",
        {
            "insight": insight,
            "drivers": normalized_drivers,
        },
    )


@login_required
@transaction.atomic
def augmented_insight_create(request):
    if request.method == "POST":
        form = AugmentedInsightForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            insight = form.save(commit=False)
            insight.tenant = request.tenant
            insight.created_by = request.user
            insight.save()
            write_audit_log(
                request.user,
                insight,
                "create",
                changes={"details": f"Created insight {insight.number}: {insight.title}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Augmented insight {insight.number} created successfully.")
            return redirect("bi:augmented_insight_detail", pk=insight.pk)
    else:
        form = AugmentedInsightForm(tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/augmented_insight/form.html",
        {
            "form": form,
            "insight": None,
            "is_edit": False,
        },
    )


@login_required
@transaction.atomic
def augmented_insight_edit(request, pk):
    insight = bi_object(request, AugmentedInsight, pk)
    if request.method == "POST":
        form = AugmentedInsightForm(request.POST, instance=insight, tenant=request.tenant)
        if form.is_valid():
            insight = form.save()
            write_audit_log(
                request.user,
                insight,
                "update",
                changes={"details": f"Updated insight {insight.number}: {insight.title}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Augmented insight {insight.number} updated successfully.")
            return redirect("bi:augmented_insight_detail", pk=insight.pk)
    else:
        form = AugmentedInsightForm(instance=insight, tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/augmented_insight/form.html",
        {
            "form": form,
            "insight": insight,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def augmented_insight_delete(request, pk):
    insight = bi_object(request, AugmentedInsight, pk)
    number = insight.number
    write_audit_log(
        request.user,
        insight,
        "delete",
        changes={"number": number, "details": f"Deleted insight {number}"},
        tenant=request.tenant,
    )
    insight.delete()
    messages.success(request, f"Augmented insight {number} was deleted.")
    return redirect("bi:augmented_insight_list")


@login_required
@require_POST
@transaction.atomic
def augmented_insight_triage(request, pk):
    insight = bi_object(request, AugmentedInsight, pk)
    new_status = request.POST.get("status", "").strip()
    action_notes = request.POST.get("action_notes", "").strip()

    valid_statuses = [choice[0] for choice in AugmentedInsight.STATUS_CHOICES]
    if new_status in valid_statuses:
        insight.status = new_status
        if action_notes:
            insight.action_notes = action_notes
        insight.save()
        write_audit_log(
            request.user,
            insight,
            "triage",
            changes={"status": new_status, "details": f"Triaged insight {insight.number} to status '{new_status}'"},
            tenant=request.tenant,
        )
        messages.success(request, f"Insight {insight.number} updated to {insight.get_status_display()}.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:augmented_insight_detail", pk=insight.pk)
