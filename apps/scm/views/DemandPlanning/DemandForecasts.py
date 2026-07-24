"""SCM 4.7 Demand Planning — DemandForecast views (sales forecasting + the period waterfall)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import DemandForecast, DemandForecastPeriod, Item, Location
from apps.scm.forms import (DemandForecastForm, DemandForecastGenerateForm,
                            DemandForecastPeriodFormSet)

ZERO = Decimal("0")


@login_required
def demandforecast_list(request):
    qs = (DemandForecast.objects.filter(tenant=request.tenant)
          .select_related("item", "location", "customer", "seasonality_profile"))
    return crud_list(
        request, qs, "scm/demandplanning/demandforecast/list.html",
        search_fields=["number", "name", "item__sku", "item__name", "notes"],
        filters=[("status", "status", False), ("method", "method", False),
                 ("bucket", "bucket", False), ("scenario", "scenario", False),
                 ("item", "item_id", True), ("location", "location_id", True)],
        extra_context={
            "status_choices": DemandForecast.STATUS_CHOICES,
            "method_choices": DemandForecast.METHOD_CHOICES,
            "bucket_choices": DemandForecast.BUCKET_CHOICES,
            "scenario_choices": DemandForecast.SCENARIO_CHOICES,
            "items": Item.objects.filter(tenant=request.tenant),
            "locations": Location.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def demandforecast_create(request):
    return _demandforecast_form(request, instance=None)


@login_required
def demandforecast_edit(request, pk):
    obj = get_object_or_404(DemandForecast, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "An approved or archived forecast is the plan of record — revise it "
                                "instead of editing it.")
        return redirect("scm:demandforecast_detail", pk=pk)
    return _demandforecast_form(request, instance=obj)


def _demandforecast_form(request, instance):
    """Header + period grid saved in ONE transaction (the _load_form pattern)."""
    if instance is None and _need_tenant(request):
        return redirect("scm:demandforecast_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = DemandForecastForm(request.POST, instance=instance, tenant=request.tenant)
        formset = DemandForecastPeriodFormSet(request.POST, instance=instance,
                                              form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                forecast = form.save(commit=False)
                forecast.tenant = request.tenant
                forecast.save()
                formset.instance = forecast
                formset.save()
            write_audit_log(request.user, forecast, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Forecast {forecast.number} saved. "
                                      f"Run Generate to build the period grid from history.")
            return redirect("scm:demandforecast_detail", pk=forecast.pk)
    else:
        form = DemandForecastForm(instance=instance, tenant=request.tenant)
        formset = DemandForecastPeriodFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/demandplanning/demandforecast/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def demandforecast_detail(request, pk):
    obj = get_object_or_404(
        DemandForecast.objects.select_related("item", "location", "customer", "currency",
                                              "seasonality_profile", "reference_item",
                                              "approved_by", "supersedes"),
        pk=pk, tenant=request.tenant)
    periods = list(obj.periods.all())
    # ONE derived-history pass feeds both the per-period actuals column and the accuracy panel — the
    # panel is handed the map it already built rather than deriving the series a second time.
    actuals = obj.period_actuals_map()
    rows, total_value = [], ZERO
    for period in periods:
        rows.append({"period": period, "actual": actuals.get(period.period_start)})
        total_value += period.forecast_value
    return render(request, "scm/demandplanning/demandforecast/detail.html", {
        "obj": obj,
        "rows": rows,
        "accuracy": obj.accuracy_metrics(periods=periods, actuals=actuals),
        "total_quantity": sum((row.final_quantity or ZERO for row in periods), ZERO),
        "total_value": total_value,
        "generate_form": DemandForecastGenerateForm(),
        "signals": obj.applied_signals.select_related("item")[:10],
        "adjustments": obj.adjustments.select_related("period", "submitted_by", "org_unit")[:10],
    })


@login_required
@require_POST
def demandforecast_delete(request, pk):
    obj = get_object_or_404(DemandForecast, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "An approved or archived forecast can't be deleted — archive it.")
        return redirect("scm:demandforecast_detail", pk=pk)
    return crud_delete(request, model=DemandForecast, pk=pk, success_url="scm:demandforecast_list")


@login_required
@require_POST
def demandforecast_generate(request, pk):
    """(Re)build the period grid from derived history using the chosen statistical method."""
    obj = get_object_or_404(DemandForecast, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Generate is only available while the forecast is still open — "
                                "revise an approved plan instead.")
        return redirect("scm:demandforecast_detail", pk=pk)
    form = DemandForecastGenerateForm(request.POST)
    regenerate_locked = form.is_valid() and form.cleaned_data.get("regenerate_locked")
    written = obj.generate_periods(regenerate_locked=regenerate_locked)
    if not written:
        messages.error(request, "Nothing to generate — check the horizon dates cover at least one "
                                "period.")
        return redirect("scm:demandforecast_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "generate", "periods": written,
                                                  "method": obj.effective_method})
    locked_note = "" if regenerate_locked else " Locked periods were left untouched."
    messages.success(request, f"Generated {written} periods using "
                              f"{obj.get_method_display()}"
                              f"{f' → {obj.selected_method}' if obj.selected_method else ''}."
                              f"{locked_note}")
    return redirect("scm:demandforecast_detail", pk=pk)


def _forecast_transition(request, pk, *, from_statuses, to_status, verb, stamp_user=False):
    """Shared lifecycle helper — the _load_transition pattern."""
    obj = get_object_or_404(DemandForecast, pk=pk, tenant=request.tenant)
    if obj.status not in from_statuses:
        messages.error(request, f"This forecast can't be {verb} from its current status.")
        return redirect("scm:demandforecast_detail", pk=pk)
    fields = ["status", "updated_at"]
    obj.status = to_status
    if stamp_user:
        obj.approved_by, obj.approved_at = request.user, timezone.now()
        fields += ["approved_by", "approved_at"]
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"Forecast {obj.number} {verb}.")
    return redirect("scm:demandforecast_detail", pk=pk)


@login_required
@require_POST
def demandforecast_submit_review(request, pk):
    return _forecast_transition(request, pk, from_statuses=("draft", "statistical"),
                                to_status="in_review", verb="submitted for review")


@tenant_admin_required
@require_POST
def demandforecast_approve(request, pk):
    """Approving makes this the plan of record — a privileged write, hence the admin gate."""
    return _forecast_transition(request, pk, from_statuses=("statistical", "in_review"),
                                to_status="approved", verb="approved", stamp_user=True)


@tenant_admin_required
@require_POST
def demandforecast_archive(request, pk):
    """Retiring the plan of record is as privileged as approving it — same gate as
    ``salesorder_cancel`` / ``purchaseorder_cancel``, which close a live commitment."""
    return _forecast_transition(request, pk, from_statuses=("draft", "statistical", "in_review",
                                                            "approved"),
                                to_status="archived", verb="archived")


@tenant_admin_required
@require_POST
def demandforecast_revise(request, pk):
    """Clone the forecast as the next revision and archive the original.

    An approved plan is never edited in place — the version that was agreed has to stay readable, so
    a revision is a new row pointing back at what it supersedes. Admin-gated because it ARCHIVES the
    original: the same retirement of the plan of record that ``demandforecast_archive`` performs.
    """
    obj = get_object_or_404(DemandForecast, pk=pk, tenant=request.tenant)
    if obj.status == "archived":
        messages.error(request, "This forecast is already archived — revise its successor instead.")
        return redirect("scm:demandforecast_detail", pk=pk)
    with transaction.atomic():
        periods = list(obj.periods.all())
        revision = DemandForecast.objects.get(pk=obj.pk)
        revision.pk, revision.id, revision.number = None, None, ""
        revision._state.adding = True
        revision.revision = (obj.revision or 1) + 1
        revision.supersedes = obj
        revision.status = "draft" if obj.status == "draft" else "statistical"
        revision.approved_by, revision.approved_at = None, None
        revision.save()
        DemandForecastPeriod.objects.bulk_create([
            DemandForecastPeriod(
                forecast=revision, sequence=row.sequence, period_start=row.period_start,
                period_end=row.period_end, period_label=row.period_label,
                historical_quantity=row.historical_quantity, baseline_quantity=row.baseline_quantity,
                seasonal_index_applied=row.seasonal_index_applied,
                event_uplift_quantity=row.event_uplift_quantity,
                signal_adjustment_quantity=row.signal_adjustment_quantity,
                consensus_quantity=row.consensus_quantity, final_quantity=row.final_quantity,
                unit_price=row.unit_price, is_locked=row.is_locked)
            for row in periods])
        obj.status = "archived"
        obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, revision, "create",
                    {"action": "revise", "supersedes": obj.number, "revision": revision.revision})
    messages.success(request, f"Created revision {revision.revision} as {revision.number}; "
                              f"{obj.number} was archived.")
    return redirect("scm:demandforecast_detail", pk=revision.pk)
