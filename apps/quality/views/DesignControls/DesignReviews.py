import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.DesignControls.DesignReviews import DesignReviewForm
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def design_review_list(request):
    qs = quality_scope(DesignReview.objects.all(), request).select_related(
        "project", "lead_reviewer", "independent_reviewer", "electronic_signature"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains(q)) | Q(title__icontains(q)) | Q(conclusions__icontains(q))
        )

    selected_project = request.GET.get("project", "").strip()
    if selected_project and selected_project.isdigit():
        qs = qs.filter(project_id=int(selected_project))

    selected_stage = request.GET.get("stage", "").strip()
    if selected_stage:
        qs = qs.filter(review_stage=selected_stage)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    projects = quality_scope(DesignProject.objects.all(), request).order_by("number")
    total_count = quality_scope(DesignReview.objects.all(), request).count()
    approved_count = quality_scope(DesignReview.objects.filter(status="approved"), request).count()
    pending_count = quality_scope(DesignReview.objects.filter(status__in=["scheduled", "in_progress", "conditional"]), request).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    reviews = paginator.get_page(page_number)

    return render(
        request,
        "quality/designcontrols/design_review/list.html",
        {
            "reviews": reviews,
            "projects": projects,
            "stage_choices": DesignReview.REVIEW_STAGE_CHOICES,
            "status_choices": DesignReview.STATUS_CHOICES,
            "total_count": total_count,
            "approved_count": approved_count,
            "pending_count": pending_count,
            "q": q,
            "selected_project": selected_project,
            "selected_stage": selected_stage,
            "selected_status": selected_status,
        },
    )


@login_required
def design_review_export(request):
    qs = quality_scope(DesignReview.objects.all(), request).select_related(
        "project", "lead_reviewer", "independent_reviewer"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="design_reviews.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number", "Title", "Project", "Stage", "Review Date", "Status",
        "Lead Reviewer", "Independent Reviewer", "Action Items Resolved"
    ])
    for rev in qs.iterator(chunk_size=500):
        writer.writerow([
            csv_safe(rev.number),
            csv_safe(rev.title),
            csv_safe(rev.project.number if rev.project else ""),
            csv_safe(rev.get_review_stage_display()),
            csv_safe(rev.review_date),
            csv_safe(rev.get_status_display()),
            csv_safe(rev.lead_reviewer.get_full_name() or rev.lead_reviewer.username if rev.lead_reviewer else ""),
            csv_safe(rev.independent_reviewer.get_full_name() or rev.independent_reviewer.username if rev.independent_reviewer else ""),
            csv_safe("Yes" if rev.action_items_resolved else "No"),
        ])
    return response


@login_required
def design_review_create(request):
    initial = {}
    project_id = request.GET.get("project", "").strip()
    if project_id and project_id.isdigit():
        project = quality_object(request, DesignProject, int(project_id))
        initial["project"] = project

    if request.method == "POST":
        form = DesignReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rev = form.save(commit=False)
            rev.tenant = request.tenant
            rev.save()
            write_audit_log(request.user, rev, "create", tenant=request.tenant)
            messages.success(request, f"Design review {rev.number} scheduled successfully.")
            return redirect("quality:design_review_detail", pk=rev.pk)
    else:
        form = DesignReviewForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_review/form.html",
        {"form": form, "title": "Schedule Stage-Gate Design Review", "action": "Schedule Review"},
    )


@login_required
def design_review_detail(request, pk):
    review = quality_object(
        request,
        DesignReview,
        pk,
        select_related=["project", "lead_reviewer", "independent_reviewer", "electronic_signature"],
    )

    return render(
        request,
        "quality/designcontrols/design_review/detail.html",
        {"review": review},
    )


@login_required
def design_review_edit(request, pk):
    review = quality_object(request, DesignReview, pk)
    if review.project.dhf_locked:
        messages.error(request, "Parent project DHF is locked. Modifying design reviews requires a Document Change Order.")
        return redirect("quality:design_review_detail", pk=review.pk)

    if request.method == "POST":
        form = DesignReviewForm(request.POST, instance=review, tenant=request.tenant)
        if form.is_valid():
            review = form.save()
            write_audit_log(request.user, review, "update", tenant=request.tenant)
            messages.success(request, f"Design review {review.number} updated successfully.")
            return redirect("quality:design_review_detail", pk=review.pk)
    else:
        form = DesignReviewForm(instance=review, tenant=request.tenant)

    return render(
        request,
        "quality/designcontrols/design_review/form.html",
        {"form": form, "review": review, "title": f"Edit {review.number}", "action": "Save Changes"},
    )


@login_required
@require_POST
def design_review_delete(request, pk):
    review = quality_object(request, DesignReview, pk)
    if review.project.dhf_locked:
        messages.error(request, "Cannot delete design review from a locked Design History File.")
        return redirect("quality:design_review_detail", pk=review.pk)

    num = review.number
    write_audit_log(request.user, review, "delete", tenant=request.tenant)
    review.delete()
    messages.success(request, f"Design review {num} removed.")
    return redirect("quality:design_review_list")


@login_required
@require_POST
def design_review_approve_gate(request, pk):
    review = quality_object(request, DesignReview, pk)
    review.status = "approved"
    review.action_items_resolved = True
    review.save(update_fields=["status", "action_items_resolved", "updated_at"])
    write_audit_log(request.user, review, "approve", tenant=request.tenant)
    messages.success(request, f"Stage-gate review {review.number} approved and cleared.")
    return redirect("quality:design_review_detail", pk=review.pk)
