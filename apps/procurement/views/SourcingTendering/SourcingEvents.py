"""Procurement 6.5 Sourcing & Tendering — SourcingEvent views.

**Event Creation & Scheduling** bullet: setup of sourcing events, timelines and rules — full
CRUD for the header + evaluation matrix, plus the POST-only lifecycle verbs (open / close /
cancel) and the admin-gated award decision. Statuses never move through the edit form; the
verbs stamp their ``*_at`` timestamps together with the audit row so the timeline cannot drift.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count

from apps.core.crud import crud_list
from apps.procurement.forms import EventCriterionFormSet, SourcingEventForm
from apps.procurement.models import SourcingBid, SourcingEvent
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import evaluate_event, event_scores_map, weighted_from_map

STATUS_CHOICES = [("draft", "Draft"), ("open", "Open"), ("closed", "Closed"),
                  ("awarded", "Awarded"), ("cancelled", "Cancelled")]
TYPE_CHOICES = [value for value in SourcingEvent.TYPE_CHOICES]


def _get_event(request, pk):
    return get_object_or_404(
        SourcingEvent.objects.select_related("currency", "requisition", "created_by"),
        pk=pk, tenant=request.tenant)


@login_required
def event_list(request):
    qs = (SourcingEvent.objects.filter(tenant=request.tenant)
          .select_related("currency")
          # Aggregation ignores Meta.ordering, and an unordered queryset makes the paginator
          # warn (and page boundaries unstable) — restate it explicitly.
          .annotate(n_bids=Count("bids"))
          .order_by("-created_at", "-id"))
    return crud_list(
        request, qs, "procurement/sourcingtendering/events/list.html",
        search_fields=["number", "title", "description"],
        filters=[("status", "status", False), ("type", "event_type", False)],
        extra_context={"status_choices": STATUS_CHOICES, "type_choices": TYPE_CHOICES},
    )


@login_required
def event_detail(request, pk):
    obj = _get_event(request, pk)
    bids = list(obj.bids.select_related("supplier", "submitted_by"))
    # One fetch of the matrix + every score; the candidate ranking below re-uses both.
    criteria, score_map = event_scores_map(obj)
    for bid in bids:
        bid.score_value = weighted_from_map(score_map.get(bid.pk, {}), criteria)

    candidates = []
    recommended = None
    if obj.is_evaluating:
        candidates = evaluate_event(obj, criteria=criteria, score_map=score_map)
        recommended = candidates[0] if candidates else None
    total_weight = sum((c.weight_pct for c in criteria), Decimal("0"))
    return render(request, "procurement/sourcingtendering/events/detail.html", {
        "obj": obj,
        "criteria": criteria,
        "total_weight": total_weight,
        "bids": bids,
        "candidates": candidates,
        "recommended": recommended,
    })


@login_required
def event_create(request):
    return _event_form(request, instance=None)


@login_required
def event_edit(request, pk):
    obj = _get_event(request, pk)
    if not obj.is_editable:
        messages.error(request,
                       f"This event is {obj.get_status_display().lower()} — its header and "
                       f"rules are frozen; open a new tender instead.")
        return redirect("procurement:event_detail", pk=pk)
    return _event_form(request, instance=obj)


def _event_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating sourcing events.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = SourcingEventForm(request.POST, request.FILES, instance=instance,
                                 tenant=request.tenant)
        formset = EventCriterionFormSet(request.POST, instance=instance,
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
            messages.success(request, f"Sourcing event {event.number} saved.")
            return redirect("procurement:event_detail", pk=event.pk)
    else:
        form = SourcingEventForm(instance=instance, tenant=request.tenant)
        formset = EventCriterionFormSet(instance=instance,
                                        form_kwargs={"tenant": request.tenant})
    return render(request, "procurement/sourcingtendering/events/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def event_delete(request, pk):
    """Refused once ANY bid exists — CASCADE would silently destroy suppliers' submissions.

    The guard re-runs under a row lock so a bid recorded between check and delete cannot
    slip past it (TOCTOU).
    """
    obj = get_object_or_404(SourcingEvent, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        locked = SourcingEvent.objects.select_for_update().get(pk=obj.pk)
        if locked.bids.exists():
            messages.error(request,
                           "This event has bids recorded against it and cannot be deleted — "
                           "cancel it instead to keep the history.")
            return redirect("procurement:event_detail", pk=pk)
        locked.delete()
    write_audit_log(request.user, locked, "delete")
    messages.success(request, f"Sourcing event {locked.number} deleted.")
    return redirect("procurement:event_list")


# -- lifecycle verbs -------------------------------------------------------------------------------

def _verb(request, pk, allowed, apply, success_msg, audit_verb):
    """Shared guard rail for the status verbs: tenant-scoped fetch, state re-check, atomic
    apply under a row lock, honest audit verb. Returns the redirect to the detail page."""
    obj = _get_event(request, pk)
    if obj.status not in allowed:
        messages.error(request, f"Cannot do that while the event is {obj.get_status_display().lower()}.")
        return redirect("procurement:event_detail", pk=pk)
    with transaction.atomic():
        locked = SourcingEvent.objects.select_for_update().get(pk=obj.pk)
        if locked.status != obj.status:  # lost a race with another tab — re-check under lock
            messages.error(request, "The event was just changed by someone else — review it and retry.")
            return redirect("procurement:event_detail", pk=pk)
        apply(locked)
    write_audit_log(request.user, locked, audit_verb)
    messages.success(request, success_msg.format(obj=locked))
    return redirect("procurement:event_detail", pk=pk)


@login_required
@require_POST
def event_open(request, pk):
    return _verb(
        request, pk, ("draft",),
        lambda ev: (setattr(ev, "status", "open"),
                    setattr(ev, "opened_at", timezone.now())),
        "Sourcing event {obj.number} is open — suppliers may now submit bids.",
        "open")


@login_required
@tenant_admin_required
@require_POST
def event_close(request, pk):
    """Admin-gated (SEC-M2): closing ends the competition — the same class of spend-affecting
    decision as an amendment rejection, so it carries the same authority bar."""
    return _verb(
        request, pk, ("open",),
        lambda ev: (setattr(ev, "status", "closed"),
                    setattr(ev, "closed_at", timezone.now())),
        "Sourcing event {obj.number} closed — evaluate the bids, then record the award.",
        "close")


@login_required
@tenant_admin_required
@require_POST
def event_cancel(request, pk):
    """Admin-gated for the same reason as close: cancelling kills a live competition."""
    return _verb(
        request, pk, ("draft", "open", "closed"),
        lambda ev: (setattr(ev, "status", "cancelled"),),
        "Sourcing event {obj.number} cancelled.",
        "cancel")


@login_required
@tenant_admin_required
@require_POST
def event_award(request, pk):
    """Record the award against one bid (**Award Recommendation** decision).

    Admin-gated like the amendment decisions: exactly one bid ends ``won``, every other live
    bid ends ``lost``, all under one transaction with the event row locked.
    """
    obj = _get_event(request, pk)
    if not obj.is_evaluating:
        messages.error(request, "Only a closed event can be awarded.")
        return redirect("procurement:event_detail", pk=pk)
    try:
        bid_pk = int(request.POST.get("bid", ""))
    except ValueError:
        messages.error(request, "Choose the winning bid to record the award.")
        return redirect("procurement:event_detail", pk=pk)
    with transaction.atomic():
        locked_event = SourcingEvent.objects.select_for_update().get(pk=obj.pk)
        bid = get_object_or_404(SourcingBid.objects.select_for_update(),
                                pk=bid_pk, tenant=request.tenant)
        if not locked_event.award(bid):
            messages.error(request,
                           "That bid cannot win this event — it must be a compliant, "
                           "submitted or shortlisted bid on the event itself.")
            return redirect("procurement:event_detail", pk=pk)
    write_audit_log(request.user, locked_event, "award",
                    {"bid": str(bid), "supplier": str(bid.supplier)})
    write_audit_log(request.user, bid, "update", {"award": locked_event.number})
    messages.success(request,
                     f"Awarded to {bid.supplier.name} at {bid.total_price} — the other live "
                     f"bids were marked lost.")
    return redirect("procurement:event_detail", pk=pk)
