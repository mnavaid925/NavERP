"""HRM 3.27 Communication Hub — Survey views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.CommunicationHub._helpers import _is_number
from apps.hrm.models import (
    Survey,
    SurveyResponse,
)
from apps.hrm.forms import (
    SurveyForm,
    build_survey_response_form,
)
from apps.hrm.views.CommunicationHub._helpers import _is_number
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _require_own_profile


# ---- Surveys --------------------------------------------------------------------------------
@login_required
def survey_list(request):
    # Explicit order_by — annotate() drops the Meta ordering, so pagination needs one (avoids the
    # UnorderedObjectListWarning + inconsistent pages).
    qs = (Survey.objects.filter(tenant=request.tenant)
          .annotate(response_count=Count("responses")).order_by("-created_at"))
    is_admin = _is_admin(request.user)
    if not is_admin:
        qs = qs.filter(status__in=("open", "closed"))  # employees don't see drafts
    extra = {"is_admin": is_admin, "status_choices": Survey.STATUS_CHOICES}
    profile = _current_employee_profile(request)
    extra["responded_ids"] = set(
        SurveyResponse.objects.filter(tenant=request.tenant, employee=profile).values_list("survey_id", flat=True)
    ) if profile is not None else set()
    filters = [("status", "status", False)] if is_admin else []
    return crud_list(request, qs, "hrm/communication/survey/list.html",
                     search_fields=("number", "title", "description"), filters=filters, extra_context=extra)


@login_required
def survey_detail(request, pk):
    survey = get_object_or_404(
        Survey.objects.annotate(response_count=Count("responses")), pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request.user)
    if not is_admin and survey.status == "draft":
        raise PermissionDenied("This survey isn't available yet.")
    profile = _current_employee_profile(request)
    has_responded = bool(profile) and SurveyResponse.objects.filter(
        tenant=request.tenant, survey=survey, employee=profile).exists()
    return render(request, "hrm/communication/survey/detail.html",
                  {"obj": survey, "is_admin": is_admin, "has_responded": has_responded})


@tenant_admin_required
def survey_create(request):
    if request.tenant is None:  # the superuser has tenant=None — don't create an orphan row (IntegrityError)
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = SurveyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.author = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Survey {obj.number} created.")
            return redirect("hrm:survey_detail", pk=obj.pk)
    else:
        form = SurveyForm(tenant=request.tenant)
    return render(request, "hrm/communication/survey/form.html", {"form": form, "is_edit": False})


@tenant_admin_required
def survey_edit(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status != "draft":
        messages.error(request, "Only a draft survey can be edited (it has no responses yet).")
        return redirect("hrm:survey_detail", pk=survey.pk)
    return crud_edit(request, model=Survey, pk=pk, form_class=SurveyForm,
                     template="hrm/communication/survey/form.html", success_url="hrm:survey_list")


@tenant_admin_required
@require_POST
def survey_delete(request, pk):
    # Status guard at the VIEW layer (not just the template) — deleting an opened/closed survey would
    # CASCADE-delete every SurveyResponse already collected. Only a draft (no responses) is deletable.
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status != "draft":
        messages.error(request, "Only a draft survey can be deleted (an opened survey has responses).")
        return redirect("hrm:survey_detail", pk=survey.pk)
    return crud_delete(request, model=Survey, pk=pk, success_url="hrm:survey_list")


@tenant_admin_required
@require_POST
def survey_open(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status != "draft":
        messages.error(request, "Only a draft survey can be opened.")
    elif not survey.questions:
        messages.error(request, "Add at least one question before opening the survey.")
    else:
        survey.status = "open"
        survey.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, survey, "update", {"action": "open"})
        messages.success(request, f"Survey {survey.number} is now open for responses.")
    return redirect("hrm:survey_detail", pk=survey.pk)


@tenant_admin_required
@require_POST
def survey_close(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status == "open":
        survey.status = "closed"
        survey.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, survey, "update", {"action": "close"})
        messages.success(request, f"Survey {survey.number} is now closed.")
    else:
        messages.error(request, "Only an open survey can be closed.")
    return redirect("hrm:survey_detail", pk=survey.pk)


@login_required
def survey_respond(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    if survey.status != "open":
        messages.error(request, "This survey isn't open for responses.")
        return redirect("hrm:survey_detail", pk=survey.pk)
    if SurveyResponse.objects.filter(tenant=request.tenant, survey=survey, employee=profile).exists():
        messages.info(request, "You've already responded to this survey.")
        return redirect("hrm:survey_detail", pk=survey.pk)
    form_class = build_survey_response_form(survey.questions)
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            answers = {str(i): form.cleaned_data.get(f"q_{i}") for i in range(len(survey.questions or []))}
            try:
                SurveyResponse.objects.create(
                    tenant=request.tenant, survey=survey, employee=profile, answers=answers)
            except IntegrityError:
                # respond-once race (double-click / duplicate tab) — the unique_together caught it.
                messages.info(request, "You've already responded to this survey.")
                return redirect("hrm:survey_detail", pk=survey.pk)
            write_audit_log(request.user, survey, "update", {"action": "respond"})
            messages.success(request, "Thanks — your response was recorded.")
            return redirect("hrm:survey_detail", pk=survey.pk)
    else:
        form = form_class()
    return render(request, "hrm/communication/survey/respond.html", {"survey": survey, "form": form})


@tenant_admin_required
def survey_results(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    responses = list(survey.responses.select_related("employee__party"))
    results = []
    for idx, q in enumerate(survey.questions or []):
        key, qtype = str(idx), q.get("type")
        entry = {"text": q.get("text", ""), "type": qtype}
        if qtype == "rating":
            nums = [float(r.answers.get(key)) for r in responses
                    if r.answers and _is_number(r.answers.get(key))]
            entry["average"] = round(sum(nums) / len(nums), 2) if nums else None
            entry["count"] = len(nums)
        elif qtype == "single_choice":
            counts = {}
            for r in responses:
                v = (r.answers or {}).get(key)
                if v:
                    counts[v] = counts.get(v, 0) + 1
            entry["choices"] = [{"option": o, "count": counts.get(o, 0)} for o in (q.get("options") or [])]
        else:  # text — when anonymous, never attach the respondent's identity
            entry["answers"] = [
                {"text": (r.answers or {}).get(key),
                 "who": (None if survey.is_anonymous else r.employee.party.name)}
                for r in responses if (r.answers or {}).get(key)]
        results.append(entry)
    return render(request, "hrm/communication/survey/results.html",
                  {"survey": survey, "results": results, "response_count": len(responses)})
