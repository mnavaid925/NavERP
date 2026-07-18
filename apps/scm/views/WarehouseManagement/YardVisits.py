"""SCM 4.4 Warehouse Management — YardVisit views (check-in → dock → depart)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import Location, YardVisit
from apps.scm.forms import YardVisitForm


@login_required
def yardvisit_list(request):
    qs = (YardVisit.objects.filter(tenant=request.tenant)
          .select_related("dock_door", "purchase_order"))
    return crud_list(
        request, qs, "scm/warehouse/yardvisit/list.html",
        search_fields=["number", "carrier_name", "vehicle_ref", "trailer_ref", "driver_name"],
        filters=[("status", "status", False), ("direction", "direction", False),
                 ("dock_door", "dock_door_id", True)],
        extra_context={
            "status_choices": YardVisit.STATUS_CHOICES,
            "direction_choices": YardVisit.DIRECTION_CHOICES,
            "dock_doors": Location.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def yardvisit_create(request):
    if _need_tenant(request):
        return redirect("scm:yardvisit_list")
    return crud_create(request, form_class=YardVisitForm,
                       template="scm/warehouse/yardvisit/form.html",
                       success_url="scm:yardvisit_list")


@login_required
def yardvisit_edit(request, pk):
    obj = get_object_or_404(YardVisit, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "A departed or cancelled visit can't be edited.")
        return redirect("scm:yardvisit_detail", pk=pk)
    return crud_edit(request, model=YardVisit, pk=pk, form_class=YardVisitForm,
                     template="scm/warehouse/yardvisit/form.html",
                     success_url="scm:yardvisit_list")


@login_required
def yardvisit_detail(request, pk):
    obj = get_object_or_404(YardVisit.objects.select_related("dock_door", "purchase_order"),
                            pk=pk, tenant=request.tenant)
    return render(request, "scm/warehouse/yardvisit/detail.html", {
        "obj": obj,
        "dwell": obj.dwell_minutes(),
    })


@login_required
@require_POST
def yardvisit_delete(request, pk):
    obj = get_object_or_404(YardVisit, pk=pk, tenant=request.tenant)
    if obj.status not in ("scheduled", "cancelled"):
        messages.error(request, "Only a scheduled or cancelled visit can be deleted.")
        return redirect("scm:yardvisit_detail", pk=pk)
    return crud_delete(request, model=YardVisit, pk=pk, success_url="scm:yardvisit_list")


@login_required
@require_POST
def yardvisit_arrive(request, pk):
    """Scheduled -> arrived. Stamps arrival, which starts the dwell clock."""
    obj = get_object_or_404(YardVisit, pk=pk, tenant=request.tenant)
    if obj.status != "scheduled":
        messages.info(request, "This vehicle has already arrived.")
        return redirect("scm:yardvisit_detail", pk=pk)
    obj.status = "arrived"
    obj.arrived_at = timezone.now()
    obj.save(update_fields=["status", "arrived_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "arrive"})
    messages.success(request, f"{obj.carrier_name} checked in.")
    return redirect("scm:yardvisit_detail", pk=pk)


@login_required
@require_POST
def yardvisit_dock(request, pk):
    """Arrived -> at dock. A dock door must be assigned before the vehicle can be docked."""
    obj = get_object_or_404(YardVisit, pk=pk, tenant=request.tenant)
    if obj.status != "arrived":
        messages.info(request, "Only an arrived vehicle can be sent to a dock.")
        return redirect("scm:yardvisit_detail", pk=pk)
    if not obj.dock_door_id:
        messages.error(request, "Assign a dock door before docking this vehicle.")
        return redirect("scm:yardvisit_detail", pk=pk)
    obj.status = "at_dock"
    obj.docked_at = timezone.now()
    obj.save(update_fields=["status", "docked_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "dock"})
    messages.success(request, f"{obj.carrier_name} docked at {obj.dock_door.code}.")
    return redirect("scm:yardvisit_detail", pk=pk)


@login_required
@require_POST
def yardvisit_depart(request, pk):
    """Send the vehicle off site and stop the dwell clock."""
    obj = get_object_or_404(YardVisit, pk=pk, tenant=request.tenant)
    if obj.status not in ("arrived", "at_dock"):
        messages.info(request, "Only a vehicle on site can depart.")
        return redirect("scm:yardvisit_detail", pk=pk)
    obj.status = "departed"
    obj.departed_at = timezone.now()
    obj.save(update_fields=["status", "departed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "depart"})
    messages.success(request, f"{obj.carrier_name} departed after {obj.dwell_minutes()} minutes on site.")
    return redirect("scm:yardvisit_detail", pk=pk)


@login_required
@require_POST
def yardvisit_cancel(request, pk):
    obj = get_object_or_404(YardVisit, pk=pk, tenant=request.tenant)
    if obj.status in ("departed", "cancelled"):
        messages.info(request, "This visit is already closed.")
        return redirect("scm:yardvisit_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Visit {obj.number} cancelled.")
    return redirect("scm:yardvisit_detail", pk=pk)
