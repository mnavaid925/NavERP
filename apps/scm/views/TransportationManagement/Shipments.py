"""SCM 4.6 Transportation Management System — Shipment views (tracking + POD)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _tms_carrier_qs
from apps.scm.models import Shipment
from apps.scm.forms import ShipmentForm, TrackingEventForm


@login_required
def shipment_list(request):
    qs = Shipment.objects.filter(tenant=request.tenant).select_related("carrier", "carrier__party")
    return crud_list(
        request, qs, "scm/transportation/shipment/list.html",
        search_fields=["number", "carrier_tracking_number", "origin_text", "destination_text",
                       "carrier__party__name"],
        filters=[("status", "status", False), ("direction", "direction", False),
                 ("mode", "mode", False), ("carrier", "carrier_id", True)],
        extra_context={
            "status_choices": Shipment.STATUS_CHOICES,
            "direction_choices": Shipment.DIRECTION_CHOICES,
            "mode_choices": Shipment._meta.get_field("mode").choices,
            "carriers": _tms_carrier_qs(request.tenant),
        },
    )


@login_required
def shipment_create(request):
    return crud_create(
        request, form_class=ShipmentForm,
        template="scm/transportation/shipment/form.html",
        success_url="scm:shipment_list",
    )


@login_required
def shipment_edit(request, pk):
    obj = get_object_or_404(Shipment, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a planned/booked shipment can be edited — it is moving once in transit.")
        return redirect("scm:shipment_detail", pk=pk)
    return crud_edit(
        request, model=Shipment, pk=pk, form_class=ShipmentForm,
        template="scm/transportation/shipment/form.html",
        success_url="scm:shipment_list",
    )


@login_required
def shipment_detail(request, pk):
    obj = get_object_or_404(
        Shipment.objects.select_related("carrier__party", "load", "sales_order", "purchase_order",
                                        "ship_from_address", "ship_to_address"),
        pk=pk, tenant=request.tenant)
    events = list(obj.events.select_related("recorded_by"))
    return render(request, "scm/transportation/shipment/detail.html", {
        "obj": obj,
        "events": events,
        "event_form": TrackingEventForm(tenant=request.tenant),
    })


@login_required
@require_POST
def shipment_delete(request, pk):
    obj = get_object_or_404(Shipment, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a planned/booked shipment can be deleted — cancel it instead.")
        return redirect("scm:shipment_detail", pk=pk)
    return crud_delete(request, model=Shipment, pk=pk, success_url="scm:shipment_list")


@login_required
@require_POST
def shipment_book(request, pk):
    """Planned -> booked. Requires an assigned carrier (you can't tender to nobody)."""
    obj = get_object_or_404(Shipment, pk=pk, tenant=request.tenant)
    if obj.status != "planned":
        messages.info(request, "This shipment has already been booked.")
        return redirect("scm:shipment_detail", pk=pk)
    if obj.carrier_id is None:
        messages.error(request, "Assign a carrier before booking the shipment.")
        return redirect("scm:shipment_detail", pk=pk)
    obj.status = "booked"
    obj.current_status_text = "Booked"
    obj.save(update_fields=["status", "current_status_text", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "book"})
    messages.success(request, f"Shipment {obj.number} booked with {obj.carrier.name}.")
    return redirect("scm:shipment_detail", pk=pk)


@login_required
@require_POST
def shipment_add_event(request, pk):
    """Append an immutable tracking event and project it onto the shipment.

    The event drives the shipment's status: a `pickup` event moves it into transit and stamps the
    actual pickup, `delivered`/`pod_signed` closes it (and, for POD, records proof), and an
    `exception`/`delayed`/`customs_hold` event flags it. When a delivery closes a shipment its
    carrier's on-time scorecard is re-derived so performance stays evidence-based.
    """
    obj = get_object_or_404(Shipment, pk=pk, tenant=request.tenant)
    if obj.is_closed:
        messages.error(request, "This shipment is delivered or cancelled — no further events.")
        return redirect("scm:shipment_detail", pk=pk)
    form = TrackingEventForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "Couldn't add the tracking event — check the fields and try again.")
        return redirect("scm:shipment_detail", pk=pk)
    with transaction.atomic():
        event = form.save(commit=False)
        event.shipment = obj
        event.recorded_by = request.user
        event.save()
        obj.apply_tracking_event(event)
    # A delivery is the signal the carrier scorecard is built from — refresh it now.
    if obj.status == "delivered" and obj.carrier_id is not None:
        obj.carrier.recompute_scorecard()
    write_audit_log(request.user, obj, "update",
                    {"action": "add_event", "event_type": event.event_type, "status": obj.status})
    messages.success(request, f"Recorded “{event.get_event_type_display()}” on {obj.number}.")
    return redirect("scm:shipment_detail", pk=pk)


@login_required
@require_POST
def shipment_cancel(request, pk):
    obj = get_object_or_404(Shipment, pk=pk, tenant=request.tenant)
    if obj.is_closed:
        messages.error(request, "This shipment is already delivered or cancelled.")
        return redirect("scm:shipment_detail", pk=pk)
    reason = (request.POST.get("cancel_reason") or "").strip()
    obj.status = "cancelled"
    if reason:
        obj.notes = f"{obj.notes}\nCancelled by {request.user}: {reason}".strip()
        obj.save(update_fields=["status", "notes", "updated_at"])
    else:
        obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel", "reason": reason})
    messages.success(request, f"Shipment {obj.number} cancelled.")
    return redirect("scm:shipment_detail", pk=pk)
