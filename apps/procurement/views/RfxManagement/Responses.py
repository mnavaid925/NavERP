"""Procurement 6.6 RFx Management — RfxResponse views.

**Response Collection**: the centralized register of supplier replies, the recording flow
(pre-creates one blank answer per question so the scoring grid is always complete) and the
guarded evaluation lifecycle (submit → under review → scored / disqualified).
"""
from django.db import transaction

from apps.procurement.forms import RfxAnswerFormSet, RfxResponseForm
from apps.procurement.models import RfxAnswer, RfxEvent, RfxResponse
from apps.procurement.views._common import *  # noqa: F401,F403


@login_required
def rfx_response_list(request):
    qs = (RfxResponse.objects.filter(tenant=request.tenant)
          .select_related("event", "supplier")
          .order_by("-created_at", "-id"))
    return crud_list(
        request, qs, "procurement/rfxmanagement/responses/list.html",
        search_fields=["number", "notes", "supplier__name", "event__title", "event__number"],
        filters=[("status", "status", False), ("event", "event_id", True)],
        extra_context={
            "status_choices": RfxResponse.STATUS_CHOICES,
            "event_choices": RfxEvent.objects.filter(tenant=request.tenant, is_template=False),
        },
    )


#: Button labels for each legal move — kept next to the flow so wording never drifts from it.
TRANSITION_LABELS = {
    "submitted": "Mark submitted",
    "under_review": "Start review",
    "scored": "Finalize scoring",
    "disqualified": "Disqualify",
}


@login_required
def rfx_response_detail(request, pk):
    obj = get_object_or_404(
        RfxResponse.objects.select_related("event", "supplier", "recorded_by"),
        pk=pk, tenant=request.tenant,
    )
    answers = list(obj.answers.select_related("question").order_by("question__order",
                                                                   "question__id"))
    allowed_actions = [(to, TRANSITION_LABELS.get(to, to.title()))
                       for to in sorted(obj.allowed_transitions())]
    return render(request, "procurement/rfxmanagement/responses/detail.html", {
        "obj": obj,
        "answers": answers,
        "allowed_actions": allowed_actions,
        "status_choices": dict(RfxResponse.STATUS_CHOICES),
    })


@login_required
def rfx_response_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before recording responses.")
        return redirect("dashboard:home")
    event_id = request.GET.get("event")
    initial = {}
    if event_id and event_id.isdecimal():
        initial["event"] = RfxEvent.objects.filter(pk=int(event_id), tenant=request.tenant).first()
    if request.method == "POST":
        form = RfxResponseForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                response = form.save(commit=False)
                response.tenant = request.tenant
                response.recorded_by = request.user
                response.save()
                # PRE-CREATE the answer grid: one blank row per question, so the scoring
                # workspace always renders every question exactly once.
                response.answers.bulk_create([
                    RfxAnswer(response=response, question=q)
                    for q in response.event.questions.all()
                ])
            write_audit_log(request.user, response, "create", {"event": response.event.number})
            messages.success(request, f"Response {response.number} recorded — enter the "
                                      f"supplier's answers next.")
            return redirect("procurement:rfx_response_detail", pk=response.pk)
    else:
        form = RfxResponseForm(tenant=request.tenant, initial=initial)
    return render(request, "procurement/rfxmanagement/responses/form.html",
                  {"form": form, "is_edit": False, "obj": None})


@login_required
def rfx_response_edit(request, pk):
    """The scoring workspace: cover note + attachment + every answer/score on one screen."""
    obj = get_object_or_404(RfxResponse.objects.select_related("event"),
                            pk=pk, tenant=request.tenant)
    if obj.is_locked or obj.event.status == "cancelled":
        messages.error(request, "This response is frozen — it was disqualified or its event "
                                "was cancelled.")
        return redirect("procurement:rfx_response_detail", pk=obj.pk)
    if request.method == "POST":
        form = RfxResponseForm(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        formset = RfxAnswerFormSet(request.POST, instance=obj,
                                   queryset=obj.answers.select_related("question"))
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, f"Response {obj.number} saved.")
            return redirect("procurement:rfx_response_detail", pk=obj.pk)
    else:
        form = RfxResponseForm(instance=obj, tenant=request.tenant)
        formset = RfxAnswerFormSet(instance=obj,
                                   queryset=obj.answers.select_related("question"))
    return render(request, "procurement/rfxmanagement/responses/form.html",
                  {"form": form, "formset": formset, "is_edit": True, "obj": obj})


@login_required
@require_POST
def rfx_response_set_status(request, pk):
    """Guarded lifecycle move — STATUS_FLOW decides what is legal, never the client."""
    obj = get_object_or_404(RfxResponse.objects.select_related("event"), pk=pk,
                            tenant=request.tenant)
    to_status = request.POST.get("to", "")
    if obj.transition(to_status):
        write_audit_log(request.user, obj, "update", {"status": to_status})
        label = obj.get_status_display()
        messages.success(request, f"Response {obj.number} marked “{label}”.")
    else:
        messages.error(request, f"“{to_status or '?'}” is not a valid move from "
                                f"“{obj.get_status_display()}”.")
    return redirect("procurement:rfx_response_detail", pk=obj.pk)


@login_required
@require_POST
def rfx_response_delete(request, pk):
    """A recorded-but-not-submitted working copy can be dropped; once submitted (or after close)
    the repository keeps it — that is what makes it a repository."""
    obj = get_object_or_404(RfxResponse.objects.select_related("event"), pk=pk,
                            tenant=request.tenant)
    if obj.status != "draft" and obj.event.status == "closed":
        messages.error(request, "Submitted responses of a closed event cannot be deleted.")
        return redirect("procurement:rfx_response_detail", pk=obj.pk)
    return crud_delete(request, model=RfxResponse, pk=pk,
                       success_url="procurement:rfx_response_list")
