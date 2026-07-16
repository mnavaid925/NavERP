"""HRM 3.26 Request Management — MyRequests views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AssetRequest,
    AttendanceRegularization,
    DocumentRequest,
    IdCardRequest,
    LeaveRequest,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _require_own_profile


# ---- My Requests hub ------------------------------------------------------------------------
@login_required
def my_requests(request):
    """3.26 self-service hub: the employee's open/total counts + five most-recent rows across all
    five request types, with deep links to each type's list/create. Leave Requests and Attendance
    Regularization reuse the existing 3.10/3.9 models (no new table)."""
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    tiles = []
    for label, model, list_name, create_name, detail_name, icon in [
        ("Leave Requests", LeaveRequest, "hrm:leaverequest_list",
         "hrm:leaverequest_create", "hrm:leaverequest_detail", "calendar-days"),
        ("Attendance Regularization", AttendanceRegularization, "hrm:attendanceregularization_list",
         "hrm:attendanceregularization_create", "hrm:attendanceregularization_detail", "clock"),
        ("Document Requests", DocumentRequest, "hrm:documentrequest_list",
         "hrm:documentrequest_create", "hrm:documentrequest_detail", "file-text"),
        ("ID Card Requests", IdCardRequest, "hrm:idcardrequest_list",
         "hrm:idcardrequest_create", "hrm:idcardrequest_detail", "credit-card"),
        ("Asset Requests", AssetRequest, "hrm:assetrequest_list",
         "hrm:assetrequest_create", "hrm:assetrequest_detail", "laptop"),
    ]:
        # "My Requests" is always the VIEWER's own rows — scope to their profile directly rather than
        # via _ss_scope (which returns the whole tenant for an admin; the per-type list pages are where
        # an admin sees everyone). `profile` is guaranteed non-None here by _require_own_profile above.
        qs = model.objects.filter(tenant=request.tenant, employee=profile)
        # One conditional aggregate instead of two COUNT round trips per tile.
        counts = qs.aggregate(total=Count("pk"),
                              open=Count("pk", filter=Q(status__in=model.OPEN_STATUSES)))
        tiles.append({
            "label": label,
            "list_url_name": list_name,
            "create_url_name": create_name,
            "detail_url_name": detail_name,
            "icon": icon,
            "open_count": counts["open"],
            "total_count": counts["total"],
            # qs is already scoped to `profile`, so the recent rows need no employee join.
            "recent": list(qs[:5]),
        })
    return render(request, "hrm/requests/my_requests.html", {
        "tiles": tiles, "is_admin": _is_admin(request.user), "profile": profile,
    })
