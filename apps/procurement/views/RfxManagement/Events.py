"""Procurement 6.6 RFx Management — RfxEvent views.

The event register, the questionnaire builder (header form + inline question formset + reorder
actions), the guarded lifecycle (issue / close / cancel), the **Side-by-Side Comparison** matrix
and the two tenant-wide surfaces the sidebar names: the Template Library and the scoring
leaderboard.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404

from apps.core.crud import crud_list, paginate
from apps.procurement.forms import RfxEventForm, RfxQuestionFormSet
from apps.procurement.models import (
    RfxAnswer,
    RfxEvent,
    RfxQuestion,
    RfxResponse,
    earned_score_map,
    possible_points_map,
    weighted_percent,
)
from apps.procurement.views._common import *  # noqa: F401,F403


def _scored_rows(responses):
    """Attach earned/possible/pct to a response list using ONE query per map (never per row)."""
    earned = earned_score_map([r.pk for r in responses])
    possible = possible_points_map({r.event_id for r in responses})
    rows = []
    for response in responses:
        p = possible.get(response.event_id)
        rows.append({
            "response": response,
            "earned": earned.get(response.pk),
            "possible": p,
            "pct": weighted_percent(earned.get(response.pk), p),
        })
    return rows


# -- event register + builder ---------------------------------------------------------------------


@login_required
def rfx_list(request):
    qs = (RfxEvent.objects.filter(tenant=request.tenant, is_template=False)
          .select_related("requisition")
          .annotate(
              n_questions=Count("questions", distinct=True),
              n_submitted=Count("responses", distinct=True,
                                filter=Q(responses__status__in=RfxResponse.SUBMITTED_STATUSES)),
          )
          # Aggregation ignores Meta.ordering; an unordered queryset makes pages unstable.
          .order_by("-created_at", "-id"))
    compare_mode = request.GET.get("compare") == "1"
    if compare_mode:
        # The comparison deep-link shows only events with enough submissions to be worth one.
        qs = qs.filter(n_submitted__gte=2)
    return crud_list(
        request, qs, "procurement/rfxmanagement/events/list.html",
        search_fields=["number", "title", "description"],
        filters=[("rfx_type", "rfx_type", False), ("status", "status", False)],
        extra_context={
            "type_choices": RfxEvent.RFX_TYPES,
            "status_choices": RfxEvent.STATUS_CHOICES,
            "compare_mode": compare_mode,
        },
    )


@login_required
def rfx_detail(request, pk):
    obj = get_object_or_404(
        RfxEvent.objects.select_related("requisition", "created_by"),
        pk=pk, tenant=request.tenant,
    )
    questions = list(obj.questions.all())
    responses = list(obj.responses.select_related("supplier")
                     .exclude(status="draft").order_by("-created_at"))
    # The comparison matrix excludes disqualified rows, so the Compare button must count
    # ADMISSIBLE submissions only — otherwise the button leads to an empty matrix.
    n_comparable = sum(1 for r in responses if r.status in RfxResponse.SUBMITTED_STATUSES)
    return render(request, "procurement/rfxmanagement/events/detail.html", {
        "obj": obj,
        "questions": questions,
        "response_rows": _scored_rows(responses),
        "n_comparable": n_comparable,
    })


@login_required
def rfx_create(request):
    return _event_form(request, instance=None)


@login_required
def rfx_edit(request, pk):
    obj = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"Event {obj.number} is {obj.status} — only drafts can be edited.")
        return redirect("procurement:rfx_detail", pk=obj.pk)
    return _event_form(request, instance=obj)


def _event_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating events.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = RfxEventForm(request.POST, request.FILES, instance=instance,
                            tenant=request.tenant)
        formset = RfxQuestionFormSet(request.POST, instance=instance,
                                     form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                event = form.save(commit=False)
                event.tenant = request.tenant
                if not is_edit:
                    event.created_by = request.user
                event.save()
                formset.instance = event
                formset.save()
            write_audit_log(request.user, event, "update" if is_edit else "create")
            messages.success(request, f"Event {event.number or event.title} saved.")
            return redirect("procurement:rfx_detail", pk=event.pk)
    else:
        form = RfxEventForm(instance=instance, tenant=request.tenant)
        formset = RfxQuestionFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "procurement/rfxmanagement/events/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def rfx_delete(request, pk):
    """Deleting cascades questions AND responses — allowed while nothing has been issued."""
    obj = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "cancelled"):
        messages.error(request, "Only draft or cancelled events can be deleted.")
        return redirect("procurement:rfx_detail", pk=obj.pk)
    return crud_delete(request, model=RfxEvent, pk=pk, success_url="procurement:rfx_list")


# -- lifecycle ------------------------------------------------------------------------------------


@login_required
@require_POST
def rfx_issue(request, pk):
    obj = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant)
    if obj.issue():
        write_audit_log(request.user, obj, "issue")
        messages.success(request, f"{obj.number} issued — responses may now be collected.")
    else:
        messages.error(request, "Only drafts with at least one question can be issued.")
    return redirect("procurement:rfx_detail", pk=obj.pk)


@login_required
@require_POST
def rfx_close(request, pk):
    obj = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant)
    if obj.close():
        write_audit_log(request.user, obj, "close")
        messages.success(request, f"{obj.number} closed — no further responses are accepted.")
    else:
        messages.error(request, "Only issued events can be closed.")
    return redirect("procurement:rfx_detail", pk=obj.pk)


@login_required
@require_POST
def rfx_cancel(request, pk):
    obj = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant)
    if obj.cancel():
        write_audit_log(request.user, obj, "cancel")
        messages.success(request, f"{obj.number} cancelled.")
    else:
        messages.error(request, "Only draft or issued events can be cancelled.")
    return redirect("procurement:rfx_detail", pk=obj.pk)


@login_required
@require_POST
def rfx_question_move(request, pk, q_pk):
    """The builder's reorder action: swap a question with its neighbour under a resequence."""
    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        messages.error(request, "Unknown move direction.")
        return redirect("procurement:rfx_detail", pk=pk)
    event = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant)
    if not event.is_editable:
        messages.error(request, "Questions are locked once an event is issued.")
        return redirect("procurement:rfx_detail", pk=event.pk)
    questions = list(event.questions.order_by("order", "id"))
    index = next((i for i, q in enumerate(questions) if q.pk == q_pk), None)
    if index is None:
        raise Http404("No matching question on this event.")
    neighbour = index - 1 if direction == "up" else index + 1
    if not 0 <= neighbour < len(questions):
        return redirect("procurement:rfx_detail", pk=event.pk)  # already at the edge — no-op
    # Resequence first so historical gaps/collapses can never make a swap ambiguous.
    for i, question in enumerate(questions):
        question.order = i + 1
    # Swap the ORDER VALUES, not the list slots — each object keeps its own identity here.
    questions[index].order, questions[neighbour].order = (
        neighbour + 1,
        index + 1,
    )
    with transaction.atomic():
        RfxQuestion.objects.bulk_update(questions, ["order"])
    write_audit_log(request.user, event, "update", {"questionnaire": "reordered"})
    return redirect("procurement:rfx_detail", pk=event.pk)


# -- comparison ------------------------------------------------------------------------------------


@login_required
def rfx_compare(request, pk):
    """**Side-by-Side Comparison**: questions down the side, submitted suppliers across the top.

    Drafts never appear (a working copy is not a bid) and neither do disqualified ones — the
    matrix compares real, admissible submissions like-for-like.
    """
    obj = get_object_or_404(RfxEvent.objects.select_related("requisition"),
                            pk=pk, tenant=request.tenant)
    questions = list(obj.questions.order_by("order", "id"))
    responses = list(obj.responses.filter(status__in=RfxResponse.SUBMITTED_STATUSES)
                     .select_related("supplier").order_by("-created_at"))
    answers = {
        (a.response_id, a.question_id): a
        for a in RfxAnswer.objects.filter(response_id__in=[r.pk for r in responses])
        .select_related("question")
    }
    rows = [{
        "question": q,
        "cells": [answers.get((r.pk, q.pk)) for r in responses],
    } for q in questions]
    scored = _scored_rows(responses)
    scored.sort(key=lambda row: (row["pct"] is None, -(row["pct"] or 0)))
    return render(request, "procurement/rfxmanagement/events/compare.html", {
        "obj": obj,
        "questions": questions,
        "responses": [row["response"] for row in scored],
        "matrix": rows,
        "scored_rows": scored,
    })


# -- template library -------------------------------------------------------------------------------


@login_required
def rfx_library(request):
    qs = (RfxEvent.objects.filter(tenant=request.tenant, is_template=True)
          .annotate(n_questions=Count("questions", distinct=True))
          .order_by("-created_at", "-id"))
    return crud_list(
        request, qs, "procurement/rfxmanagement/library.html",
        search_fields=["number", "title", "description"],
        filters=[("rfx_type", "rfx_type", False)],
        extra_context={"type_choices": RfxEvent.RFX_TYPES},
    )


@login_required
@require_POST
def rfx_clone(request, pk):
    """Use a library blueprint: clone header + questions into a fresh REAL draft event."""
    template = get_object_or_404(RfxEvent, pk=pk, tenant=request.tenant, is_template=True)
    clone = template.clone_as(request.user)
    write_audit_log(request.user, clone, "create", {"from_template": template.number})
    messages.success(request, f"Event {clone.number} drafted from {template.number}.")
    return redirect("procurement:rfx_detail", pk=clone.pk)


# -- scoring leaderboard ---------------------------------------------------------------------------


@login_required
def rfx_scoring(request):
    """**Scoring & Weighting System** leaderboard: every submitted response across the tenant,
    ranked by weighted percentage of its own event's possible points."""
    qs = (RfxResponse.objects.filter(tenant=request.tenant,
                                     status__in=RfxResponse.SUBMITTED_STATUSES)
          .select_related("event", "supplier"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(supplier__name__icontains=q) | Q(event__title__icontains=q)
                       | Q(number__icontains=q))
    responses = list(qs)
    rows = _scored_rows(responses)
    rows.sort(key=lambda row: (row["pct"] is None, -(row["pct"] or 0)))
    page_obj = paginate(request, rows, per_page=20)
    return render(request, "procurement/rfxmanagement/scoring.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
    })
