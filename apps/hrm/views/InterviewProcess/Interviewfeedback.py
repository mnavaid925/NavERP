"""HRM 3.7 Interview Process — Interviewfeedback views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.InterviewProcess._helpers import _form_changes
from apps.hrm.models import (
    Interview,
    InterviewFeedback,
    RECOMMENDATION_CHOICES,
)
from apps.hrm.forms import (
    FeedbackCriterionForm,
    InterviewFeedbackForm,
)
from apps.hrm.views.InterviewProcess._helpers import _form_changes


# --------------------------------------------------------------- Interview Feedback / Scorecards (3.7)
@login_required
def interviewfeedback_list(request):
    qs = (InterviewFeedback.objects.filter(tenant=request.tenant)
          .select_related("interview__application__candidate", "submitted_by")
          .annotate(avg_rating=Avg("criteria__rating"),
                    criteria_count=Count("criteria", distinct=True))
          .order_by("-created_at"))  # explicit ordering after annotate (paginator needs it)
    return crud_list(
        request, qs, "hrm/interview/interviewfeedback/list.html",
        search_fields=["number", "summary", "interview__title",
                       "interview__application__candidate__first_name",
                       "interview__application__candidate__last_name"],
        filters=[("recommendation", "overall_recommendation", False),
                 ("submitted", "is_submitted", False),
                 ("interview", "interview_id", True)],
        extra_context={
            "recommendation_choices": RECOMMENDATION_CHOICES,
            "interviews": Interview.objects.filter(tenant=request.tenant).order_by("-scheduled_at")[:200],
        },
    )


@login_required
def interviewfeedback_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = InterviewFeedbackForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            # Scorecards are created as drafts; submission is the dedicated submit action (stamps
            # submitted_by/at), so there's no submission metadata to set here.
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Scorecard {obj.number} created.")
            return redirect("hrm:interviewfeedback_detail", pk=obj.pk)
    else:
        form = InterviewFeedbackForm(tenant=request.tenant,
                                     initial={"interview": request.GET.get("interview") or None})
    return render(request, "hrm/interview/interviewfeedback/form.html", {"form": form, "is_edit": False})


@login_required
def interviewfeedback_detail(request, pk):
    obj = get_object_or_404(
        InterviewFeedback.objects.filter(tenant=request.tenant)
        .select_related("interview__application__candidate", "submitted_by", "panelist__interviewer"), pk=pk)
    return render(request, "hrm/interview/interviewfeedback/detail.html", {
        "obj": obj,
        "criteria": obj.criteria.all(),
        "avg_rating": obj.criteria.aggregate(avg=Avg("rating"))["avg"],
        "criterion_form": FeedbackCriterionForm(tenant=request.tenant),
    })


@login_required
def interviewfeedback_edit(request, pk):
    obj = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = InterviewFeedbackForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            # `is_submitted` isn't on the form, so editing a submitted card can't un-submit it.
            obj = form.save()
            write_audit_log(request.user, obj, "update", _form_changes(form))
            messages.success(request, "Scorecard updated.")
            return redirect("hrm:interviewfeedback_detail", pk=obj.pk)
    else:
        form = InterviewFeedbackForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/interview/interviewfeedback/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # a submitted scorecard is an auditable attestation; admin-only delete to match
@require_POST           # the template's gated delete button (security-review #2)
def interviewfeedback_delete(request, pk):
    return crud_delete(request, model=InterviewFeedback, pk=pk, success_url="hrm:interviewfeedback_list")


@login_required
@require_POST
def interviewfeedback_submit(request, pk):
    obj = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.is_submitted:
        obj.is_submitted = True
        obj.submitted_at = timezone.now()
        obj.submitted_by = request.user
        obj.save(update_fields=["is_submitted", "submitted_at", "submitted_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, "Scorecard submitted.")
    else:
        messages.info(request, "This scorecard is already submitted.")
    return redirect("hrm:interviewfeedback_detail", pk=obj.pk)
