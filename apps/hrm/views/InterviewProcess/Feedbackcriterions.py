"""HRM 3.7 Interview Process — Feedbackcriterions views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    FeedbackCriterion,
    InterviewFeedback,
)
from apps.hrm.forms import (
    FeedbackCriterionForm,
)


@login_required
@require_POST
def feedbackcriterion_add(request, pk):
    feedback = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    form = FeedbackCriterionForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        FeedbackCriterion.objects.create(
            tenant=request.tenant, feedback=feedback, criterion_name=cd["criterion_name"],
            rating=cd["rating"], notes=cd["notes"])
        messages.success(request, "Criterion added.")
    else:
        messages.error(request, "Enter a criterion name and a rating of 1–5.")
    return redirect("hrm:interviewfeedback_detail", pk=feedback.pk)


@login_required
@require_POST
def feedbackcriterion_delete(request, pk, criterion_pk):
    feedback = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    crit = get_object_or_404(FeedbackCriterion, pk=criterion_pk, feedback=feedback, tenant=request.tenant)
    crit.delete()
    messages.success(request, "Criterion removed.")
    return redirect("hrm:interviewfeedback_detail", pk=feedback.pk)
