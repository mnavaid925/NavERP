"""HRM 3.25 Personal Information — MyInfoEdit views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PersonalInformation._helpers import _require_own_profile
from apps.hrm.forms import (
    EmployeeProfileMyInfoForm,
)
from apps.hrm.views.PersonalInformation._helpers import _require_own_profile


@login_required
def my_info_edit(request):
    """Direct-edit the non-sensitive contact subset (address / personal email / mobile / photo)."""
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    if request.method == "POST":
        form = EmployeeProfileMyInfoForm(request.POST, request.FILES, instance=profile, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", {"action": "self_update_contact"})
            messages.success(request, "Your contact information was updated.")
            return redirect("hrm:my_info")
    else:
        form = EmployeeProfileMyInfoForm(instance=profile, tenant=request.tenant)
    return render(request, "hrm/selfservice/my_info_edit.html",
                  {"form": form, "profile": profile, "is_edit": True})
