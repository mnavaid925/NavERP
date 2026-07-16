"""HRM 3.25 Personal Information — MyInfo views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PersonalInformation._helpers import _require_own_profile
from apps.hrm.models import (
    EmployeeProfile,
)
from apps.hrm.views.PersonalInformation._helpers import _require_own_profile


# ---------------------------------------------------------------- My Info hub (Profile/Contact)
@login_required
def my_info(request):
    """The employee's self-service landing page: read-only employment context, the direct-edit
    contact fields, the masked sensitive fields (each with a 'Request a Change' link), roster
    summaries, and the requester's recent change requests."""
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    # Employment.manager is a FK straight to core.Party (not EmployeeProfile), so the path stops at
    # employment__manager — and the profile.manager property returns that Party (use .name, not .party.name).
    profile = (EmployeeProfile.objects
               .select_related("party", "designation",
                               "employment__org_unit", "employment__manager")
               .get(pk=profile.pk))
    return render(request, "hrm/selfservice/my_info.html", {
        "profile": profile,
        "emergency_contacts": list(profile.emergency_contacts.all()[:3]),
        "bank_accounts": list(profile.bank_accounts.all()[:3]),
        "family_members": list(profile.family_members.all()[:3]),
        # The hub's mini-list renders only number/type/status/date — no FK columns, so no join needed.
        "my_requests": list(profile.info_change_requests.all()[:5]),
    })
