import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReviewForm
from apps.quality.models.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReview
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def capa_effectiveness_review_list(request):
    qs = quality_scope(CapaEffectivenessReview.objects.all(), request).select_related(
        "capa", "evaluator"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(review_criteria__icontains=q)
            | Q(review_notes__icontains=q)
            | Q(capa__number__icontains=q)
        )

    outcome_filter = request.GET.get("outcome", "").strip()
    if outcome_filter:
        qs = qs.filter(outcome=outcome_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    capa_filter = request.GET.get("capa", "").strip()
    if capa_filter.isdigit():
        qs = qs.filter(capa_id=int(capa_filter))

    base_qs = quality_scope(CapaEffectivenessReview.objects.all(), request)
    stats = base_qs.aggregate(
        total_count=Count("id"),
        effective_count=Count("id", filter=Q(outcome="effective")),
        ineffective_count=Count("id", filter=Q(outcome="ineffective")),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "reviews": page_obj,
        "total_count": stats["total_count"] or 0,
        "effective_count": stats["effective_count"] or 0,
        "ineffective_count": stats["ineffective_count"] or 0,
        "q": q,
        "outcome_filter": outcome_filter,
        "status_filter": status_filter,
        "outcome_choices": CapaEffectivenessReview.OUTCOME_CHOICES,
        "status_choices": CapaEffectivenessReview.STATUS_CHOICES,
    }
    return render(request, "quality/capamanagement/capa_effectiveness_review/list.html", context)


@login_required
def capa_effectiveness_review_detail(request, pk):
    review = quality_object(
        request,
        CapaEffectivenessReview,
        pk,
        select_related=["capa", "evaluator", "formal_signature"],
    )
    context = {"review": review}
    return render(request, "quality/capamanagement/capa_effectiveness_review/detail.html", context)


@login_required
def capa_effectiveness_review_create(request):
    initial = {}
    capa_param = request.GET.get("capa", "").strip()
    if capa_param.isdigit():
        initial["capa"] = int(capa_param)

    if request.method == "POST":
        form = CapaEffectivenessReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            review = form.save()
            write_audit_log(request.user, review, "create", tenant=request.tenant)
            messages.success(request, f"Effectiveness Review {review.number} scheduled successfully.")
            return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)
    else:
        form = CapaEffectivenessReviewForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "quality/capamanagement/capa_effectiveness_review/form.html", context)


@login_required
def capa_effectiveness_review_edit(request, pk):
    review = quality_object(request, CapaEffectivenessReview, pk)
    if review.status == "completed":
        messages.warning(request, f"Effectiveness Review {review.number} has been completed and cannot be edited.")
        return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)

    if request.method == "POST":
        form = CapaEffectivenessReviewForm(request.POST, instance=review, tenant=request.tenant)
        if form.is_valid():
            review = form.save()
            write_audit_log(request.user, review, "update", tenant=request.tenant)
            messages.success(request, f"Effectiveness Review {review.number} updated successfully.")
            return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)
    else:
        form = CapaEffectivenessReviewForm(instance=review, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "review": review,
    }
    return render(request, "quality/capamanagement/capa_effectiveness_review/form.html", context)


@require_POST
@tenant_admin_required
def capa_effectiveness_review_delete(request, pk):
    review = quality_object(request, CapaEffectivenessReview, pk)
    num = review.number
    capa_pk = review.capa_id
    write_audit_log(request.user, review, "delete", tenant=request.tenant)
    review.delete()
    messages.success(request, f"Effectiveness Review {num} was deleted.")
    return redirect("quality:capa_investigation_detail", pk=capa_pk)


@require_POST
@login_required
def capa_effectiveness_review_sign_off(request, pk):
    review = quality_object(request, CapaEffectivenessReview, pk)

    if review.status == "completed":
        messages.error(request, "This review has already been signed off and completed.")
        return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    if request.user != review.evaluator and not is_admin:
        messages.error(request, "Only the assigned evaluator or a tenant administrator can sign off this review.")
        return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)

    outcome = request.POST.get("outcome", "").strip()
    notes = request.POST.get("review_notes", "").strip()

    valid_outcomes = [choice[0] for choice in CapaEffectivenessReview.OUTCOME_CHOICES if choice[0] != "pending"]
    if outcome not in valid_outcomes:
        messages.error(request, "Please choose a definitive outcome (Effective, Ineffective, or Inconclusive).")
        return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)

    if review.recurrence_observed and outcome == "effective":
        messages.error(request, "Cannot mark review as 'Effective' when recurrence has been observed.")
        return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)

    review.outcome = outcome
    review.status = "completed"
    review.actual_review_date = timezone.now().date()
    if notes:
        review.review_notes = notes
    review.save()

    write_audit_log(request.user, review, "approve", tenant=request.tenant)
    messages.success(request, f"Effectiveness Review {review.number} signed off as {review.get_outcome_display()}.")
    return redirect("quality:capa_effectiveness_review_detail", pk=review.pk)


@login_required
def capa_effectiveness_review_export(request):
    qs = quality_scope(CapaEffectivenessReview.objects.all(), request).select_related(
        "capa", "evaluator"
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"CAPA_Effectiveness_Reviews_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Review Number",
        "CAPA Number",
        "Method",
        "Planned Review Date",
        "Actual Review Date",
        "Evaluator",
        "Recurrence Observed",
        "Outcome",
        "Status",
        "Created At",
    ])

    for r in qs:
        writer.writerow([
            csv_safe(r.number),
            csv_safe(r.capa.number if r.capa else ""),
            csv_safe(r.get_verification_method_display()),
            csv_safe(r.planned_review_date),
            csv_safe(r.actual_review_date),
            csv_safe(r.evaluator.username if r.evaluator else ""),
            csv_safe("Yes" if r.recurrence_observed else "No"),
            csv_safe(r.get_outcome_display()),
            csv_safe(r.get_status_display()),
            csv_safe(r.created_at.strftime("%Y-%m-%d %H:%M")),
        ])

    write_audit_log(request.user, CapaEffectivenessReview(), "export", tenant=request.tenant)
    return response
