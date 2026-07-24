"""SCM 4.7 Demand Planning — ForecastAdjustment views (collaborative / consensus planning)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import DemandForecast, ForecastAdjustment
from apps.scm.forms import ForecastAdjustmentForm, ForecastAdjustmentReviewForm

ZERO = Decimal("0")


@login_required
def forecastadjustment_list(request):
    """Doubles as the consensus review queue — ``?status=proposed`` is what a reviewer opens."""
    qs = (ForecastAdjustment.objects.filter(tenant=request.tenant)
          .select_related("forecast", "forecast__item", "period", "submitted_by", "org_unit"))
    return crud_list(
        request, qs, "scm/demandplanning/forecastadjustment/list.html",
        search_fields=["number", "rationale", "forecast__number", "forecast__name"],
        filters=[("status", "status", False),
                 ("contributor_function", "contributor_function", False),
                 ("reason_code", "reason_code", False),
                 ("adjustment_type", "adjustment_type", False),
                 ("forecast", "forecast_id", True)],
        extra_context={
            "status_choices": ForecastAdjustment.STATUS_CHOICES,
            "function_choices": ForecastAdjustment.FUNCTION_CHOICES,
            "reason_choices": ForecastAdjustment.REASON_CHOICES,
            "type_choices": ForecastAdjustment.TYPE_CHOICES,
            "forecasts": DemandForecast.objects.filter(tenant=request.tenant).select_related("item"),
            "proposed_count": qs.filter(status="proposed").count(),
        },
    )


def _preselected_forecast(request):
    """The forecast a "Propose adjustment" link arrived with — tenant-scoped, so a crafted id can't
    widen the period dropdown to another workspace's periods."""
    raw = request.GET.get("forecast", "")
    if not raw.isdigit() or request.tenant is None:
        return None
    return DemandForecast.objects.filter(tenant=request.tenant, pk=int(raw)).first()


@login_required
def forecastadjustment_create(request):
    return _forecastadjustment_form(request, instance=None)


@login_required
def forecastadjustment_edit(request, pk):
    obj = get_object_or_404(ForecastAdjustment, pk=pk, tenant=request.tenant)
    if not obj.is_reviewable:
        messages.error(request, "A reviewed adjustment is part of the consensus record — propose a "
                                "new one instead of editing it.")
        return redirect("scm:forecastadjustment_detail", pk=pk)
    return _forecastadjustment_form(request, instance=obj)


def _forecastadjustment_form(request, instance):
    """Hand-rolled so the form gets its parent forecast (to scope the tenant-less period dropdown)
    and so ``submitted_by`` is stamped from the session rather than trusted from the POST."""
    if instance is None and _need_tenant(request):
        return redirect("scm:forecastadjustment_list")
    is_edit = instance is not None
    preselected = _preselected_forecast(request)
    if request.method == "POST":
        form = ForecastAdjustmentForm(request.POST, instance=instance, tenant=request.tenant,
                                      forecast=preselected)
        if form.is_valid():
            adjustment = form.save(commit=False)
            adjustment.tenant = request.tenant
            if not is_edit:
                adjustment.submitted_by = request.user
            adjustment.save()
            write_audit_log(request.user, adjustment, "update" if is_edit else "create",
                            _changed(form))
            messages.success(request, f"Adjustment {adjustment.number} saved as a proposal.")
            return redirect("scm:forecastadjustment_detail", pk=adjustment.pk)
    else:
        initial = {"forecast": preselected} if preselected is not None else None
        form = ForecastAdjustmentForm(instance=instance, tenant=request.tenant,
                                      forecast=preselected, initial=initial)
    return render(request, "scm/demandplanning/forecastadjustment/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def forecastadjustment_detail(request, pk):
    obj = get_object_or_404(
        ForecastAdjustment.objects.select_related("forecast", "forecast__item", "period",
                                                  "submitted_by", "org_unit", "reviewed_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "scm/demandplanning/forecastadjustment/detail.html", {
        "obj": obj,
        "base_quantity": obj.base_quantity(),
        "review_form": ForecastAdjustmentReviewForm(),
    })


@login_required
@require_POST
def forecastadjustment_delete(request, pk):
    """Only an UNREVIEWED proposal may be deleted.

    An accepted adjustment's delta is already baked into the forecast's ``consensus_quantity`` and
    ``final_quantity``. Deleting the row would leave that number in the approved plan with nothing
    explaining it — and the next accept or reject, which rebuilds the roll-up from scratch, would
    then silently drop it back out. A reviewed decision is part of the consensus record; reverse it
    with a new proposal, not by erasing the evidence.
    """
    obj = get_object_or_404(ForecastAdjustment, pk=pk, tenant=request.tenant)
    if not obj.is_reviewable:
        messages.error(request, "A reviewed adjustment is part of the consensus record and can't be "
                                "deleted — propose a reversing adjustment instead.")
        return redirect("scm:forecastadjustment_detail", pk=pk)
    return crud_delete(request, model=ForecastAdjustment, pk=pk,
                       success_url="scm:forecastadjustment_list")


def _review(request, pk, *, to_status, verb):
    """Shared accept/reject gate. Proposed-only: a second accept would double-count the delta into
    ``consensus_quantity``, and re-rejecting an accepted one would leave the roll-up stale."""
    obj = get_object_or_404(ForecastAdjustment.objects.select_related("forecast"),
                            pk=pk, tenant=request.tenant)
    if not obj.is_reviewable:
        messages.error(request, "This adjustment has already been reviewed.")
        return redirect("scm:forecastadjustment_detail", pk=pk)
    form = ForecastAdjustmentReviewForm(request.POST)
    note = form.cleaned_data.get("review_note", "") if form.is_valid() else ""
    with transaction.atomic():
        obj.status, obj.reviewed_by, obj.reviewed_at = to_status, request.user, timezone.now()
        obj.review_note = note
        obj.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note",
                                "resolved_quantity", "updated_at"])
        # Rebuilt from scratch over every accepted adjustment, so a reject after an accept correctly
        # backs its delta out again.
        obj.forecast.recompute_consensus()
    write_audit_log(request.user, obj, "update",
                    {"action": verb, "resolved_quantity": str(obj.resolved_quantity)})
    messages.success(request, f"Adjustment {obj.number} {verb}.")
    return redirect("scm:forecastadjustment_detail", pk=pk)


@login_required
@require_POST
def forecastadjustment_accept(request, pk):
    return _review(request, pk, to_status="accepted", verb="accepted")


@login_required
@require_POST
def forecastadjustment_reject(request, pk):
    return _review(request, pk, to_status="rejected", verb="rejected")
