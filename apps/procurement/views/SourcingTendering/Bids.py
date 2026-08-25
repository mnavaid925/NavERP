"""Procurement 6.5 Sourcing & Tendering — SourcingBid views.

**Bid Submission Portal** bullet: the register and detail surface for supplier proposals.
Bids are captured through the staff console this pass (the gated supplier page is 6.4's
portal-access follow-up); ``submitted_by`` is stamped by ``submit()`` so the trail carries
over when that lands. The evaluation matrix is scored right on the bid detail — one POST per
save, validated against each criterion's scale server-side.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.core.crud import crud_delete, crud_list
from apps.procurement.forms import SourcingBidForm
from apps.procurement.models import BidScore, SourcingBid, SourcingEvent
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import event_scores_map, weighted_from_map

STATUS_CHOICES = [value for value in SourcingBid.STATUS_CHOICES]


def _get_bid(request, pk):
    return get_object_or_404(
        SourcingBid.objects.select_related("event", "supplier", "submitted_by"),
        pk=pk, tenant=request.tenant)


@login_required
def bid_list(request):
    qs = (SourcingBid.objects.filter(tenant=request.tenant)
          .select_related("event", "supplier"))
    return crud_list(
        request, qs, "procurement/sourcingtendering/bids/list.html",
        search_fields=["number", "supplier__name", "contact_ref", "summary"],
        filters=[("status", "status", False), ("event", "event_id", True)],
        extra_context={
            "status_choices": STATUS_CHOICES,
            "events": list(SourcingEvent.objects.filter(tenant=request.tenant)
                           .order_by("-created_at")
                           .values("id", "number", "title")[:100]),
        },
    )


@login_required
def bid_detail(request, pk):
    obj = _get_bid(request, pk)
    criteria, score_map = event_scores_map(obj.event)
    row = score_map.get(obj.pk, {})
    scores = {criterion.pk: row.get(criterion.pk) for criterion in criteria}

    if request.method == "POST":
        # Scoring matrix save (**Bid Evaluation Matrix** bullet). Manual parse over one input
        # per criterion: a dynamic formset would need hidden criterion pks and prefix plumbing
        # for what is a bounded, fully server-validated grid. Blank clears; out-of-range or
        # non-numeric values are reported per criterion and nothing is written unless ALL pass.
        if not obj.is_evaluable:
            messages.error(request,
                           f"This bid is {obj.get_status_display().lower()} — its matrix is frozen.")
            return redirect("procurement:bid_detail", pk=pk)
        parsed, errors = {}, []
        for criterion in criteria:
            raw = (request.POST.get(f"c_{criterion.pk}") or "").strip()
            if not raw:
                continue
            try:
                value = Decimal(raw)
            except InvalidOperation:
                errors.append(f"'{criterion.name}' is not a number.")
                continue
            if value < 0 or value > criterion.max_score:
                errors.append(f"'{criterion.name}' must be between 0 and {criterion.max_score}.")
                continue
            parsed[criterion.pk] = value
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            with transaction.atomic():
                existing = {score.criterion_id: score
                            for score in obj.scores.select_related("criterion")}
                for criterion in criteria:
                    target, current = existing.get(criterion.pk), parsed.get(criterion.pk)
                    if target is None and current is None:
                        continue
                    if current is None:
                        target.delete()
                    elif target is None:
                        BidScore.objects.create(bid=obj, criterion=criterion, score=current)
                    elif target.score != current:
                        target.score = current
                        target.save(update_fields=["score"])
                obj.updated_at = timezone.now()
                obj.save(update_fields=["updated_at"])
            write_audit_log(request.user, obj, "score",
                            {"criteria": len(parsed), "event": obj.event.number})
            messages.success(request, "Evaluation scores saved.")
            return redirect("procurement:bid_detail", pk=pk)

    weighted = weighted_from_map(row, criteria) if criteria else None
    total_weight = sum((c.weight_pct for c in criteria), Decimal("0"))
    return render(request, "procurement/sourcingtendering/bids/detail.html", {
        "obj": obj,
        "criteria": criteria,
        "scores": scores,
        "weighted": weighted,
        "total_weight": total_weight,
        "can_score": obj.is_evaluable,
    })


@login_required
def bid_create(request):
    return _bid_form(request, instance=None)


@login_required
def bid_edit(request, pk):
    obj = _get_bid(request, pk)
    if obj.status not in SourcingBid.EDITABLE_STATUSES:
        messages.error(request,
                       f"A submitted bid can no longer be edited — use shortlist/disqualify "
                       f"or record evaluator notes instead.")
        return redirect("procurement:bid_detail", pk=pk)
    return _bid_form(request, instance=obj)


def _bid_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before recording bids.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = SourcingBidForm(request.POST, request.FILES, instance=instance,
                               tenant=request.tenant)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.tenant = request.tenant
            bid.save()
            write_audit_log(request.user, bid, "update" if is_edit else "create",
                            {"event": bid.event.number})
            messages.success(request, f"Bid {bid.number} saved.")
            return redirect("procurement:bid_detail", pk=bid.pk)
    else:
        form = SourcingBidForm(instance=instance, tenant=request.tenant)
        initial_event = request.GET.get("event", "").strip()
        if initial_event.isdigit():
            form.fields["event"].initial = int(initial_event)
    return render(request, "procurement/sourcingtendering/bids/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def bid_delete(request, pk):
    """Only drafts delete — once submitted, a bid is part of the competitive record."""
    obj = _get_bid(request, pk)
    if obj.status not in SourcingBid.EDITABLE_STATUSES:
        messages.error(request, "Only draft bids can be deleted; submitted ones stay on record.")
        return redirect("procurement:bid_detail", pk=pk)
    return crud_delete(request, model=SourcingBid, pk=pk,
                       success_url="procurement:bid_list")


# -- lifecycle verbs -------------------------------------------------------------------------------

@login_required
@require_POST
def bid_submit(request, pk):
    obj = _get_bid(request, pk)
    if obj.submit(request.user):
        write_audit_log(request.user, obj, "submit", {"event": obj.event.number})
        messages.success(request, f"Bid {obj.number} submitted for evaluation.")
    else:
        messages.error(request,
                       "This bid cannot be submitted — it was already sent or its sourcing "
                       "event is no longer open.")
    return redirect("procurement:bid_detail", pk=pk)


def _decide(request, pk, action, success_msg):
    obj = _get_bid(request, pk)
    new_status = obj.decide(action)
    if new_status is None:
        messages.error(request,
                       "Only a submitted or shortlisted bid can be moved again from here.")
        return redirect("procurement:bid_detail", pk=pk)
    note = (request.POST.get("note") or "").strip()
    if note:
        obj.decision_note = note
        obj.save(update_fields=["decision_note", "updated_at"])
    write_audit_log(request.user, obj, action, {"event": obj.event.number})
    messages.success(request, success_msg.format(obj=obj))
    return redirect("procurement:bid_detail", pk=pk)


@login_required
@require_POST
def bid_shortlist(request, pk):
    return _decide(request, pk, "shortlist",
                   "Bid {obj.number} shortlisted for the award scenarios.")


@login_required
@require_POST
def bid_disqualify(request, pk):
    """Disqualifying without a reason leaves an unexplainable register — require one."""
    if not (request.POST.get("note") or "").strip():
        messages.error(request, "A disqualification needs a reason — add it and retry.")
        return redirect("procurement:bid_detail", pk=pk)
    return _decide(request, pk, "disqualify",
                   "Bid {obj.number} disqualified — it is excluded from the award scenarios.")
