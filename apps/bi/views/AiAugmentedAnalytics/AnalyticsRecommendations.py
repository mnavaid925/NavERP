from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendationForm
from apps.bi.models.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendation
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def analytics_recommendation_list(request):
    qs = bi_scope(AnalyticsRecommendation.objects.all(), request).select_related(
        "user", "dashboard", "report", "kpi", "semantic_model"
    )

    counts = qs.aggregate(
        active=Count("id", filter=Q(status="active")),
    )
    active_count = counts["active"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(target_title__icontains=q)
            | Q(target_url__icontains=q)
            | Q(rationale_text__icontains=q)
            | Q(number__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
        )

    # Filters
    recommendation_type = request.GET.get("recommendation_type", "").strip()
    if recommendation_type:
        qs = qs.filter(recommendation_type=recommendation_type)

    reason = request.GET.get("reason", "").strip()
    if reason:
        qs = qs.filter(reason=reason)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "bi/ai_augmented_analytics/analytics_recommendation/list.html",
        {
            "recommendations": page_obj,
            "recommendation_type_choices": AnalyticsRecommendation.RECOMMENDATION_TYPE_CHOICES,
            "reason_choices": AnalyticsRecommendation.REASON_CHOICES,
            "status_choices": AnalyticsRecommendation.STATUS_CHOICES,
            "active_count": active_count,
        },
    )


@login_required
def analytics_recommendation_detail(request, pk):
    recommendation = bi_object(
        request,
        AnalyticsRecommendation,
        pk,
        select_related=("user", "dashboard", "report", "kpi", "semantic_model"),
    )

    return render(
        request,
        "bi/ai_augmented_analytics/analytics_recommendation/detail.html",
        {
            "recommendation": recommendation,
        },
    )


@login_required
def analytics_recommendation_create(request):
    if request.method == "POST":
        form = AnalyticsRecommendationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.tenant = request.tenant
            rec.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="AnalyticsRecommendation",
                object_id=str(rec.pk),
                object_repr=str(rec),
                details=f"Created recommendation {rec.number} for user {rec.user.username}",
            )
            messages.success(request, f"Recommendation {rec.number} created successfully.")
            return redirect("bi:analytics_recommendation_detail", pk=rec.pk)
    else:
        form = AnalyticsRecommendationForm(tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/analytics_recommendation/form.html",
        {
            "form": form,
            "recommendation": None,
            "is_edit": False,
        },
    )


@login_required
def analytics_recommendation_edit(request, pk):
    recommendation = bi_object(request, AnalyticsRecommendation, pk)
    if request.method == "POST":
        form = AnalyticsRecommendationForm(request.POST, instance=recommendation, tenant=request.tenant)
        if form.is_valid():
            recommendation = form.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="AnalyticsRecommendation",
                object_id=str(recommendation.pk),
                object_repr=str(recommendation),
                details=f"Updated recommendation {recommendation.number}",
            )
            messages.success(request, f"Recommendation {recommendation.number} updated successfully.")
            return redirect("bi:analytics_recommendation_detail", pk=recommendation.pk)
    else:
        form = AnalyticsRecommendationForm(instance=recommendation, tenant=request.tenant)

    return render(
        request,
        "bi/ai_augmented_analytics/analytics_recommendation/form.html",
        {
            "form": form,
            "recommendation": recommendation,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def analytics_recommendation_delete(request, pk):
    recommendation = bi_object(request, AnalyticsRecommendation, pk)
    number = recommendation.number
    recommendation.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="AnalyticsRecommendation",
        object_id=str(pk),
        object_repr=number,
        details=f"Deleted recommendation {number}",
    )
    messages.success(request, f"Recommendation {number} was deleted.")
    return redirect("bi:analytics_recommendation_list")


@login_required
@require_POST
def analytics_recommendation_interact(request, pk):
    recommendation = bi_object(request, AnalyticsRecommendation, pk)
    interaction_type = request.POST.get("interaction_type", "").strip()

    status_map = {
        "click": "clicked",
        "save": "saved",
        "dismiss": "dismissed",
    }

    if interaction_type in status_map:
        recommendation.status = status_map[interaction_type]
        recommendation.last_interacted_at = timezone.now()
        recommendation.save()

        write_audit_log(
            tenant=request.tenant,
            user=request.user,
            action=f"rec_{interaction_type}",
            model_name="AnalyticsRecommendation",
            object_id=str(recommendation.pk),
            object_repr=str(recommendation),
            details=f"User {request.user.username} {interaction_type}ed recommendation {recommendation.number}",
        )
        messages.success(request, f"Recommendation {recommendation.number} marked as {recommendation.get_status_display()}.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("bi:analytics_recommendation_detail", pk=recommendation.pk)
