"""HRM 3.9 Attendance Management — Geofence views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRecord,
    GeoFence,
)
from apps.hrm.forms import (
    GeoFenceForm,
)


# ============================================================ Geofences (3.9)
@login_required
def geofence_list(request):
    return crud_list(
        request,
        GeoFence.objects.filter(tenant=request.tenant)
        .annotate(punch_count=Count("attendance_records")).order_by("name"),
        "hrm/attendance/geofence/list.html",
        search_fields=["name", "address"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def geofence_create(request):
    return crud_create(request, form_class=GeoFenceForm, template="hrm/attendance/geofence/form.html",
                       success_url="hrm:geofence_list")


@login_required
def geofence_detail(request, pk):
    obj = get_object_or_404(GeoFence, pk=pk, tenant=request.tenant)
    # Materialise the punches and prime each row's geofence FK cache with the zone we already hold
    # — the template calls rec.geo_status() per row (touches rec.geofence); without this each row
    # would fire its own SELECT (Django caches the FK per-instance, not per-value).
    recent_punches = list(AttendanceRecord.objects.filter(tenant=request.tenant, geofence=obj)
                          .select_related("employee__party").order_by("-date")[:20])
    for rec in recent_punches:
        rec.geofence = obj
    return render(request, "hrm/attendance/geofence/detail.html", {
        "obj": obj,
        "recent_punches": recent_punches,
    })


@login_required
def geofence_edit(request, pk):
    return crud_edit(request, model=GeoFence, pk=pk, form_class=GeoFenceForm,
                     template="hrm/attendance/geofence/form.html", success_url="hrm:geofence_list")


@login_required
@require_POST
def geofence_delete(request, pk):
    obj = get_object_or_404(GeoFence, pk=pk, tenant=request.tenant)
    # Preserve the geo-audit trail on existing punches: block delete while any reference it.
    if AttendanceRecord.objects.filter(tenant=request.tenant, geofence=obj).exists():
        messages.error(request, "Cannot delete a geofence linked to attendance records. Deactivate it instead.")
        return redirect("hrm:geofence_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Geofence deleted.")
    return redirect("hrm:geofence_list")
