"""CRM 1.11 Customer Success & Retention — Surveys views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Survey,
)
from apps.crm.forms import (
    SurveyForm,
)


_SURVEY_SCALE_MAX = {"nps": 10, "csat": 5, "ces": 7}  # per-type response scale ceiling


# ------------------------------------------------------------ 1.11 Surveys
@login_required
def survey_list(request):
    return crud_list(
        request,
        Survey.objects.filter(tenant=request.tenant).select_related("account", "contact", "related_case"),
        "crm/success/survey/list.html",
        search_fields=["number", "feedback_text", "account__name"],
        filters=[("survey_type", "survey_type", False), ("classification", "classification", False),
                 ("account", "account_id", True)],
        extra_context={"type_choices": Survey.TYPE_CHOICES,
                       "classification_choices": Survey.CLASSIFICATION_CHOICES,
                       "accounts": Party.objects.filter(tenant=request.tenant, kind="organization").order_by("name")},
    )


@login_required
def survey_create(request):
    return crud_create(request, form_class=SurveyForm, template="crm/success/survey/form.html",
                       success_url="crm:survey_list")


@login_required
def survey_detail(request, pk):
    obj = get_object_or_404(Survey.objects.select_related("account", "contact", "related_case"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/success/survey/detail.html", {"obj": obj})


@login_required
def survey_edit(request, pk):
    return crud_edit(request, model=Survey, pk=pk, form_class=SurveyForm,
                     template="crm/success/survey/form.html", success_url="crm:survey_list")


@login_required
@require_POST
def survey_delete(request, pk):
    return crud_delete(request, model=Survey, pk=pk, success_url="crm:survey_list")


@login_required
def survey_results(request):
    """Aggregate survey analytics (1.11): NPS = %promoters − %detractors, the P/P/D split,
    CSAT/CES averages, and the overall response rate — derived queries, no extra model."""
    responded = Q(responded_at__isnull=False)
    nps_r = responded & Q(survey_type="nps")
    a = Survey.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        sent=Count("id", filter=Q(sent_at__isnull=False)),
        responded_total=Count("id", filter=responded),
        nps_total=Count("id", filter=nps_r),
        promoters=Count("id", filter=nps_r & Q(classification="promoter")),
        passives=Count("id", filter=nps_r & Q(classification="passive")),
        detractors=Count("id", filter=nps_r & Q(classification="detractor")),
        csat_count=Count("id", filter=responded & Q(survey_type="csat")),
        csat_avg=Avg("score", filter=responded & Q(survey_type="csat")),
        ces_count=Count("id", filter=responded & Q(survey_type="ces")),
        ces_avg=Avg("score", filter=responded & Q(survey_type="ces")),
    )
    nps_total = a["nps_total"]
    pct = lambda n: round(n / nps_total * 100) if nps_total else 0  # noqa: E731
    return render(request, "crm/success/survey/results.html", {
        "total": a["total"], "sent": a["sent"], "responded_total": a["responded_total"],
        "response_rate": round(a["responded_total"] / a["sent"] * 100) if a["sent"] else None,
        "nps_total": nps_total, "promoters": a["promoters"], "passives": a["passives"], "detractors": a["detractors"],
        "nps_score": round((a["promoters"] - a["detractors"]) / nps_total * 100) if nps_total else None,
        "promoter_pct": pct(a["promoters"]), "passive_pct": pct(a["passives"]), "detractor_pct": pct(a["detractors"]),
        "csat_avg": a["csat_avg"], "csat_count": a["csat_count"],
        "ces_avg": a["ces_avg"], "ces_count": a["ces_count"],
    })


@tenant_admin_required  # sending a survey is a privileged outbound action
@require_POST
def survey_send(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.sent_at is None:
        survey.sent_at = timezone.now()
        survey.save(update_fields=["sent_at", "updated_at"])
        # WARNING: real email delivery is deferred. When wired, send the respond link to survey.contact's
        # email via a vetted transactional-email service; never expose the token to anyone but the recipient.
        write_audit_log(request.user, survey, "update")
        messages.success(request, f"Survey {survey.number} marked sent (email delivery deferred).")
    else:
        messages.info(request, "This survey was already sent.")
    return redirect("crm:survey_detail", pk=survey.pk)


def survey_respond(request, token):
    """Public survey-response page (1.11) — token-scoped, no login. Scale + clamp are type-aware.
    WARNING: unauthenticated endpoint — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    in production. A single token is single-use (responded_at guard), but a bulk campaign issues one
    token per contact, so scripted submission across many tokens is unthrottled at the app layer.
    """
    survey = get_object_or_404(Survey, token=token)
    scale_max = _SURVEY_SCALE_MAX.get(survey.survey_type, 10)
    scale_min = 0 if survey.survey_type == "nps" else 1  # NPS is 0–10; CSAT/CES start at 1
    error = ""
    if request.method == "POST" and survey.responded_at is None:
        try:
            parsed = int(request.POST.get("score", ""))  # int() not isdigit() — isdigit() accepts unicode (²) that int() rejects
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None:
            # Clamp to the type's scale — this is a public endpoint, never trust the POST.
            survey.score = max(scale_min, min(scale_max, parsed))
            # Public endpoint — cap feedback length to prevent unbounded-storage abuse.
            survey.feedback_text = request.POST.get("feedback_text", "").strip()[:4000]
            survey.responded_at = timezone.now()
            survey.save()  # save() auto-classifies by type
            return redirect("crm:survey_respond", token=token)
        error = "Please select a score before submitting."  # don't lock the survey on an empty submit
    return render(request, "crm/success/survey/respond.html", {
        "survey": survey, "scale": list(range(scale_min, scale_max + 1)), "error": error})
