from django.core.exceptions import ValidationError

from apps.core.crud import as_db_int, crud_list
from apps.crm.models import Lead
from apps.sales.forms import LeadScoreAdjustmentForm, LeadScoreCorrectionForm
from apps.sales.models import LeadScoreEvent
from apps.sales.services import project_lead_score, record_score_event, recompute_lead_score
from apps.sales.views._common import *


@login_required
def lead_score_event_list(request):
    queryset = sales_scope(
        LeadScoreEvent.objects.filter(tenant=request.tenant).select_related("lead", "recorded_by", "corrects_event"),
        request,
        "lead__owner",
    )
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    parsed_from = None
    parsed_to = None
    if date_from:
        try:
            parsed_from = parse_date(date_from)
        except ValueError:
            parsed_from = None
    if date_to:
        try:
            parsed_to = parse_date(date_to)
        except ValueError:
            parsed_to = None
    if parsed_from:
        queryset = queryset.filter(occurred_at__date__gte=parsed_from)
    if parsed_to:
        queryset = queryset.filter(occurred_at__date__lte=parsed_to)
    return crud_list(
        request,
        queryset,
        "sales/leadmanagement/leadscoreevent/list.html",
        search_fields=["lead__number", "lead__name", "source_ref", "reason", "event_type"],
        filters=[
            ("signal_category", "signal_category", False),
            ("event_type", "event_type", False),
            ("source_kind", "source_kind", False),
            ("lead", "lead_id", True),
        ],
        extra_context={
            "date_from": date_from,
            "date_to": date_to,
            "signal_category_choices": LeadScoreEvent.SIGNAL_CATEGORY_CHOICES,
            "event_type_choices": LeadScoreEvent.EVENT_TYPE_CHOICES,
            "source_kind_choices": LeadScoreEvent.SOURCE_KIND_CHOICES,
            "leads": sales_leads(request).only("pk", "number", "name"),
        },
    )


@login_required
def lead_score_event_detail(request, pk):
    obj = sales_object(
        request,
        LeadScoreEvent,
        "lead__owner",
        pk,
        select_related=("lead", "recorded_by", "corrects_event"),
    )
    projection = project_lead_score(obj.lead, request.tenant)
    return render(request, "sales/leadmanagement/leadscoreevent/detail.html", {
        "obj": obj,
        "lead": obj.lead,
        "projection_score": projection,
        "projection_rating": "hot" if projection >= 70 else "warm" if projection >= 40 else "cold",
        "inverse_score_delta": -obj.score_delta,
        "can_correct": obj.event_type != "correction" and not obj.corrections.exists(),
    })


@require_POST
@tenant_admin_required
def lead_score_event_adjust(request):
    form = LeadScoreAdjustmentForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        try:
            record_score_event(
                form.cleaned_data["lead"],
                request.tenant,
                event_type="manual_adjustment",
                signal_category="manual",
                score_delta=form.cleaned_data["score_delta"],
                source_kind="manual",
                reason=form.cleaned_data["reason"],
                recorded_by=request.user,
            )
            messages.success(request, "Manual score adjustment recorded.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "The score adjustment could not be recorded.")
    return redirect("sales:lead_score_event_list")


@require_POST
@tenant_admin_required
def lead_score_event_correct(request, pk):
    event = get_object_or_404(LeadScoreEvent, pk=pk, tenant=request.tenant)
    form = LeadScoreCorrectionForm(request.POST, tenant=request.tenant)
    if form.is_valid() and form.cleaned_data["corrects_event"] == event:
        try:
            record_score_event(
                event.lead,
                request.tenant,
                event_type="correction",
                signal_category="correction",
                score_delta=form.cleaned_data["score_delta"],
                source_kind="manual",
                source_ref=f"corrects:{event.pk}",
                reason=form.cleaned_data["reason"],
                recorded_by=request.user,
                corrects_event=event,
                idempotency_key=f"score-correction:{event.pk}",
            )
            messages.success(request, "Score correction recorded.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(request, "The score correction could not be recorded.")
    return redirect("sales:lead_score_event_detail", pk=event.pk)


@require_POST
@tenant_admin_required
def lead_score_event_recompute(request):
    lead_id = as_db_int(request.POST.get("lead_id", ""))
    if lead_id is None or lead_id <= 0:
        messages.error(request, "Choose a valid lead.")
        return redirect("sales:lead_score_event_list")
    lead = get_object_or_404(Lead, pk=lead_id, tenant=request.tenant)
    try:
        recompute_lead_score(lead, request.tenant, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:lead_score_event_list")
    messages.success(request, f"Score projection refreshed for {lead.number}.")
    return redirect("sales:lead_score_event_list")
