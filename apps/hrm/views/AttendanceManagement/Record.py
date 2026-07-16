"""HRM 3.9 Attendance Management — Record views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRecord,
    EmployeeProfile,
)
from apps.hrm.forms import (
    AttendanceRecordForm,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


# ============================================================ Attendance (3.9)
@login_required
def attendancerecord_list(request):
    qs = (AttendanceRecord.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "shift", "geofence"))
    # Parse the date-range GET params defensively — a malformed string passed straight to
    # .filter(date__gte=...) would raise a 500 (ValueError/DataError); ignore bad input instead.
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return crud_list(
        request, qs, "hrm/attendance/record/list.html",
        search_fields=["number", "employee__party__name", "notes"],
        filters=[("status", "status", False), ("source", "source", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": AttendanceRecord.STATUS_CHOICES,
                       "source_choices": AttendanceRecord.SOURCE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
        per_page=30,
    )


@login_required
def attendancerecord_create(request):
    return crud_create(request, form_class=AttendanceRecordForm,
                       template="hrm/attendance/record/form.html", success_url="hrm:attendancerecord_list")


@login_required
def attendancerecord_detail(request, pk):
    obj = get_object_or_404(
        AttendanceRecord.objects.select_related("employee__party", "shift", "geofence"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/record/detail.html", {
        "obj": obj,
        "regularizations": obj.regularizations.select_related("approver").order_by("-created_at"),
    })


@login_required
def attendancerecord_edit(request, pk):
    return crud_edit(request, model=AttendanceRecord, pk=pk, form_class=AttendanceRecordForm,
                     template="hrm/attendance/record/form.html", success_url="hrm:attendancerecord_list")


@login_required
@require_POST
def attendancerecord_delete(request, pk):
    return crud_delete(request, model=AttendanceRecord, pk=pk, success_url="hrm:attendancerecord_list")
