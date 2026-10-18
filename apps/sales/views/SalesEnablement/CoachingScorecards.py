"""Sales 8.9 — Views for `CoachingScorecard`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.utils import write_audit_log
from apps.sales.forms.SalesEnablement.CoachingScorecards import CoachingScorecardForm
from apps.sales.models.SalesEnablement.CoachingScorecards import (
    SCORECARD_STATUS_CHOICES,
    CoachingScorecard,
)


@login_required
def coaching_scorecard_list(request):
    qs = (
        CoachingScorecard.objects.filter(tenant=request.tenant)
        .select_related("communication_log", "activity_log", "coach", "coachee")
        .order_by("-evaluated_on", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(communication_log__subject__icontains=q)
            | Q(coachee__username__icontains=q)
            | Q(coachee__first_name__icontains=q)
            | Q(coachee__last_name__icontains=q)
            | Q(coach__username__icontains=q)
            | Q(number__icontains=q)
        )

    review_status = request.GET.get("review_status", "").strip()
    if review_status:
        qs = qs.filter(review_status=review_status)

    coach_id = request.GET.get("coach", "").strip()
    if coach_id.isdigit():
        qs = qs.filter(coach_id=int(coach_id))

    coachee_id = request.GET.get("coachee", "").strip()
    if coachee_id.isdigit():
        qs = qs.filter(coachee_id=int(coachee_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    users = User.objects.filter(tenant=request.tenant, is_active=True)

    context = {
        "scorecards": page_obj,
        "review_status_choices": SCORECARD_STATUS_CHOICES,
        "coaches": users,
        "coachees": users,
        "q": q,
        "review_status": review_status,
        "coach_id": coach_id,
        "coachee_id": coachee_id,
    }
    return render(request, "sales/salesenablement/coachingscorecard/list.html", context)


@login_required
def coaching_scorecard_detail(request, pk):
    scorecard = get_object_or_404(
        CoachingScorecard.objects.filter(tenant=request.tenant).select_related(
            "communication_log", "activity_log", "coach", "coachee"
        ),
        pk=pk,
    )
    context = {"scorecard": scorecard}
    return render(request, "sales/salesenablement/coachingscorecard/detail.html", context)


@login_required
def coaching_scorecard_create(request):
    if request.method == "POST":
        form = CoachingScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.coach_id:
                obj.coach = request.user
            obj.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="CoachingScorecard",
                object_id=str(obj.pk),
                details=f"Created coaching scorecard {obj.number} for {obj.coachee} (Score: {obj.overall_score}%)",
            )
            messages.success(request, f"Coaching scorecard for '{obj.coachee}' created.")
            return redirect("sales:coaching_scorecard_detail", pk=obj.pk)
    else:
        initial = {}
        comm_id = request.GET.get("communication_log")
        if comm_id and comm_id.isdigit():
            initial["communication_log"] = int(comm_id)
        act_id = request.GET.get("activity_log")
        if act_id and act_id.isdigit():
            initial["activity_log"] = int(act_id)
        form = CoachingScorecardForm(initial=initial, tenant=request.tenant)

    context = {"form": form, "scorecard": None, "is_edit": False}
    return render(request, "sales/salesenablement/coachingscorecard/form.html", context)


@login_required
def coaching_scorecard_edit(request, pk):
    obj = get_object_or_404(CoachingScorecard.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = CoachingScorecardForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="CoachingScorecard",
                object_id=str(obj.pk),
                details=f"Updated coaching scorecard {obj.number} for {obj.coachee}",
            )
            messages.success(request, f"Coaching scorecard {obj.number} updated.")
            return redirect("sales:coaching_scorecard_detail", pk=obj.pk)
    else:
        form = CoachingScorecardForm(instance=obj, tenant=request.tenant)

    context = {"form": form, "scorecard": obj, "is_edit": True}
    return render(request, "sales/salesenablement/coachingscorecard/form.html", context)


@login_required
@require_POST
def coaching_scorecard_delete(request, pk):
    obj = get_object_or_404(CoachingScorecard.objects.filter(tenant=request.tenant), pk=pk)
    number = obj.number
    coachee_str = str(obj.coachee)
    obj.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="CoachingScorecard",
        object_id=str(pk),
        details=f"Deleted coaching scorecard {number} for {coachee_str}",
    )
    messages.success(request, f"Coaching scorecard {number} deleted.")
    return redirect("sales:coaching_scorecard_list")


@login_required
@require_POST
def coaching_scorecard_acknowledge(request, pk):
    obj = get_object_or_404(CoachingScorecard.objects.filter(tenant=request.tenant), pk=pk)
    obj.review_status = "acknowledged"
    obj.save(update_fields=["review_status", "updated_at"])
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="update",
        model_name="CoachingScorecard",
        object_id=str(obj.pk),
        details=f"Acknowledged coaching scorecard {obj.number}",
    )
    messages.success(request, "Coaching evaluation acknowledged.")
    return redirect("sales:coaching_scorecard_detail", pk=obj.pk)
