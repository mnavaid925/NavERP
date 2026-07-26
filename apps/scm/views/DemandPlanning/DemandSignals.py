"""SCM 4.7 Demand Planning — DemandSignal views (demand sensing triage)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _guard_plan_of_record, _item_qs, _location_qs, _need_tenant
from apps.scm.models import DemandSignal
from apps.scm.models.DemandPlanning.DemandSignals import detect_order_surge, expire_stale_signals
from apps.scm.forms import DemandSignalApplyForm, DemandSignalDismissForm, DemandSignalForm

ZERO = Decimal("0")


@login_required
def demandsignal_list(request):
    qs = (DemandSignal.objects.filter(tenant=request.tenant)
          .select_related("item", "category", "location", "customer", "applied_to_forecast"))
    return crud_list(
        request, qs, "scm/demandplanning/demandsignal/list.html",
        search_fields=["number", "source_reference", "notes", "item__sku", "item__name"],
        filters=[("status", "status", False), ("signal_type", "signal_type", False),
                 ("source", "source", False), ("impact_direction", "impact_direction", False),
                 ("item", "item_id", True), ("location", "location_id", True)],
        extra_context={
            "status_choices": DemandSignal.STATUS_CHOICES,
            "type_choices": DemandSignal.SIGNAL_TYPE_CHOICES,
            "source_choices": DemandSignal.SOURCE_CHOICES,
            "direction_choices": DemandSignal.DIRECTION_CHOICES,
            "items": _item_qs(request.tenant),
            "locations": _location_qs(request.tenant),
        },
    )


@login_required
def demandsignal_create(request):
    return crud_create(request, form_class=DemandSignalForm,
                       template="scm/demandplanning/demandsignal/form.html",
                       success_url="scm:demandsignal_list")


@login_required
def demandsignal_edit(request, pk):
    obj = get_object_or_404(DemandSignal, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "An applied or dismissed signal is a closed observation — it can't "
                                "be edited.")
        return redirect("scm:demandsignal_detail", pk=pk)
    return crud_edit(request, model=DemandSignal, pk=pk, form_class=DemandSignalForm,
                     template="scm/demandplanning/demandsignal/form.html",
                     success_url="scm:demandsignal_list")


@login_required
def demandsignal_detail(request, pk):
    obj = get_object_or_404(
        DemandSignal.objects.select_related("item", "category", "location", "customer",
                                            "applied_to_forecast", "reviewed_by"),
        pk=pk, tenant=request.tenant)
    window_from, window_to = obj.effective_window()
    return render(request, "scm/demandplanning/demandsignal/detail.html", {
        "obj": obj,
        "window_from": window_from,
        "window_to": window_to,
        "apply_form": DemandSignalApplyForm(tenant=request.tenant, signal=obj),
        "dismiss_form": DemandSignalDismissForm(),
    })


@login_required
@require_POST
def demandsignal_delete(request, pk):
    """Only an OPEN signal may be deleted.

    An applied signal's impact already sits in the forecast periods' ``signal_adjustment_quantity``;
    deleting it would leave the "+ Signal" column on the waterfall with nothing to point at. A
    dismissed one is the record of a decision. Both are closed observations, not drafts.
    """
    obj = get_object_or_404(DemandSignal, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.error(request, "An applied or dismissed signal is part of the record and can't be "
                                "deleted.")
        return redirect("scm:demandsignal_detail", pk=pk)
    return crud_delete(request, model=DemandSignal, pk=pk, success_url="scm:demandsignal_list")


@login_required
@require_POST
def demandsignal_detect(request):
    """Run the internal order-surge detector, and retire signals whose window has passed.

    The detector run doubles as the sweep: an open signal whose effective window has already ended
    was never acted on and is no longer actionable, so it moves to ``expired`` rather than sitting in
    the triage queue forever.
    """
    if _need_tenant(request):
        return redirect("scm:demandsignal_list")
    expired = expire_stale_signals(request.tenant)
    created = detect_order_surge(request.tenant)
    # Batch actions have no single target object — `obj=None` + an explicit tenant is how the
    # codebase records them (crm HealthScores.recompute, hrm leave-policy actions).
    write_audit_log(request.user, None, "update",
                    {"action": "detect_order_surge", "created": len(created), "expired": expired},
                    tenant=request.tenant)
    if created:
        messages.success(request, f"Detected {len(created)} order-pattern signals from live sales "
                                  f"orders.")
    else:
        messages.info(request, "No order-pattern deviations beyond the threshold — needs an approved "
                               "forecast covering today with orders running against it.")
    if expired:
        messages.info(request, f"{expired} signal(s) whose window has passed were marked expired.")
    return redirect("scm:demandsignal_list")


@login_required
@require_POST
def demandsignal_review(request, pk):
    obj = get_object_or_404(DemandSignal, pk=pk, tenant=request.tenant)
    if obj.status != "new":
        messages.error(request, "Only a new signal can be moved into review.")
        return redirect("scm:demandsignal_detail", pk=pk)
    obj.status, obj.reviewed_by, obj.reviewed_at = "under_review", request.user, timezone.now()
    obj.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "review", "status": obj.status})
    messages.success(request, f"Signal {obj.number} is under review.")
    return redirect("scm:demandsignal_detail", pk=pk)


@login_required
@require_POST
def demandsignal_apply(request, pk):
    """Push this signal's impact into a forecast's overlapping periods.

    Guarded to the triage statuses: re-applying an already-applied signal would double-count its
    impact into ``signal_adjustment_quantity``, and a dismissed one was explicitly rejected.
    """
    obj = get_object_or_404(DemandSignal, pk=pk, tenant=request.tenant)
    if obj.status not in DemandSignal.APPLICABLE_STATUSES:
        messages.error(request, "This signal has already been applied or dismissed.")
        return redirect("scm:demandsignal_detail", pk=pk)
    form = DemandSignalApplyForm(request.POST, tenant=request.tenant, signal=obj)
    if not form.is_valid():
        messages.error(request, "Pick a forecast to apply this signal to.")
        return redirect("scm:demandsignal_detail", pk=pk)
    forecast = form.cleaned_data["forecast"]
    blocked = _guard_plan_of_record(request, forecast, "Applying a signal")
    if blocked:
        messages.error(request, blocked)
        return redirect("scm:demandsignal_detail", pk=pk)
    quantity = form.cleaned_data.get("impact_quantity")
    with transaction.atomic():
        moved = obj.apply_to_forecast(forecast, quantity=quantity)
        if moved:
            obj.reviewed_by, obj.reviewed_at = request.user, timezone.now()
            obj.save(update_fields=["reviewed_by", "reviewed_at", "updated_at"])
    if not moved:
        messages.error(request, "That forecast has no periods inside this signal's effective window "
                                "— generate its grid first.")
        return redirect("scm:demandsignal_detail", pk=pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "apply", "forecast": forecast.number, "periods": moved})
    messages.success(request, f"Applied {obj.number} across {moved} periods of {forecast.number}.")
    return redirect("scm:demandsignal_detail", pk=pk)


@login_required
@require_POST
def demandsignal_dismiss(request, pk):
    obj = get_object_or_404(DemandSignal, pk=pk, tenant=request.tenant)
    if obj.status not in DemandSignal.APPLICABLE_STATUSES:
        messages.error(request, "This signal has already been applied or dismissed.")
        return redirect("scm:demandsignal_detail", pk=pk)
    form = DemandSignalDismissForm(request.POST)
    note = form.cleaned_data.get("notes", "") if form.is_valid() else ""
    obj.status, obj.reviewed_by, obj.reviewed_at = "dismissed", request.user, timezone.now()
    if note:
        # Appended, never overwritten — the observer's own note is part of the record.
        obj.notes = f"{obj.notes}\n\nDismissed: {note}".strip()
    obj.save(update_fields=["status", "reviewed_by", "reviewed_at", "notes", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "dismiss"})
    messages.success(request, f"Signal {obj.number} dismissed.")
    return redirect("scm:demandsignal_detail", pk=pk)
