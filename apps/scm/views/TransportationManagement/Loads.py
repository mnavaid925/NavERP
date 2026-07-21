"""SCM 4.6 Transportation Management System — Load views (route planning + load optimization)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _tms_carrier_qs
from apps.scm.models import Load
from apps.scm.forms import LoadForm, LoadStopFormSet

ZERO = Decimal("0")


@login_required
def load_list(request):
    qs = Load.objects.filter(tenant=request.tenant).select_related("carrier", "carrier__party")
    return crud_list(
        request, qs, "scm/transportation/load/list.html",
        search_fields=["number", "origin_text", "destination_text", "driver_name", "vehicle_ref"],
        filters=[("status", "status", False), ("mode", "mode", False),
                 ("equipment_type", "equipment_type", False), ("carrier", "carrier_id", True)],
        extra_context={
            "status_choices": Load.STATUS_CHOICES,
            "mode_choices": Load._meta.get_field("mode").choices,
            "equipment_choices": Load._meta.get_field("equipment_type").choices,
            "carriers": _tms_carrier_qs(request.tenant),
        },
    )


@login_required
def load_create(request):
    return _load_form(request, instance=None)


@login_required
def load_edit(request, pk):
    obj = get_object_or_404(Load, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a planning/tendered load can be edited — it is executing once booked.")
        return redirect("scm:load_detail", pk=pk)
    return _load_form(request, instance=obj)


def _load_form(request, instance):
    """Header + stop formset saved in ONE transaction (mirrors _salesorder_form)."""
    if instance is None and _need_tenant(request):
        return redirect("scm:load_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = LoadForm(request.POST, instance=instance, tenant=request.tenant)
        formset = LoadStopFormSet(request.POST, instance=instance, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                load = form.save(commit=False)
                load.tenant = request.tenant
                load.save()
                formset.instance = load
                formset.save()
            write_audit_log(request.user, load, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Load {load.number} saved.")
            return redirect("scm:load_detail", pk=load.pk)
    else:
        form = LoadForm(instance=instance, tenant=request.tenant)
        formset = LoadStopFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/transportation/load/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def load_detail(request, pk):
    obj = get_object_or_404(Load.objects.select_related("carrier", "carrier__party"),
                            pk=pk, tenant=request.tenant)
    stops = list(obj.stops.select_related("address"))
    shipments = list(obj.shipments.select_related("carrier__party"))
    # Cube utilization: aggregate BOTH dimensions in ONE query, then pass each precomputed total into
    # the utilization property so it never re-aggregates (the no-arg path).
    totals = obj.shipments.aggregate(w=Sum("weight_kg"), v=Sum("volume_cbm"))
    planned_weight = totals["w"] or ZERO
    planned_volume = totals["v"] or ZERO
    return render(request, "scm/transportation/load/detail.html", {
        "obj": obj,
        "stops": stops,
        "shipments": shipments,
        "planned_weight": planned_weight,
        "planned_volume": planned_volume,
        "weight_util": obj.weight_utilization_pct(planned_weight),
        "volume_util": obj.volume_utilization_pct(planned_volume),
    })


@login_required
@require_POST
def load_delete(request, pk):
    obj = get_object_or_404(Load, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a planning/tendered load can be deleted — cancel it instead.")
        return redirect("scm:load_detail", pk=pk)
    return crud_delete(request, model=Load, pk=pk, success_url="scm:load_list")


def _load_transition(request, pk, *, from_statuses, to_status, verb, require_carrier=False,
                     stamp=None, admin=False):
    """Shared status-transition helper for the load lifecycle actions."""
    obj = get_object_or_404(Load, pk=pk, tenant=request.tenant)
    if obj.status not in from_statuses:
        messages.error(request, f"This load can't be {verb} from its current status.")
        return redirect("scm:load_detail", pk=pk)
    if require_carrier and obj.carrier_id is None:
        messages.error(request, "Assign a carrier before tendering or booking the load.")
        return redirect("scm:load_detail", pk=pk)
    fields = ["status", "updated_at"]
    obj.status = to_status
    if stamp:
        setattr(obj, stamp, timezone.now())
        fields.append(stamp)
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"Load {obj.number} {verb}.")
    return redirect("scm:load_detail", pk=pk)


@login_required
@require_POST
def load_tender(request, pk):
    return _load_transition(request, pk, from_statuses=("planning",), to_status="tendered",
                            verb="tendered", require_carrier=True)


@login_required
@require_POST
def load_book(request, pk):
    return _load_transition(request, pk, from_statuses=("planning", "tendered"), to_status="booked",
                            verb="booked", require_carrier=True)


@tenant_admin_required
@require_POST
def load_dispatch(request, pk):
    return _load_transition(request, pk, from_statuses=("booked",), to_status="in_transit",
                            verb="dispatched", stamp="actual_departure")


@tenant_admin_required
@require_POST
def load_deliver(request, pk):
    return _load_transition(request, pk, from_statuses=("in_transit",), to_status="delivered",
                            verb="delivered", stamp="actual_arrival")


@tenant_admin_required
@require_POST
def load_cancel(request, pk):
    obj = get_object_or_404(Load, pk=pk, tenant=request.tenant)
    if obj.status in Load.CLOSED_STATUSES:
        messages.error(request, "This load is already delivered or cancelled.")
        return redirect("scm:load_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Load {obj.number} cancelled.")
    return redirect("scm:load_detail", pk=pk)
