"""HRM 3.25 Personal Information — Emergencycontact forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmergencyContact,
)


# ======================================================= 3.25 Personal Information (Self-Service)
# The child-entity ModelForms all EXCLUDE ``employee`` — the view sets it from
# ``_current_employee_profile(request)`` (non-admin) or an ``?employee=<id>`` picker (admin),
# mirroring the ``_employee_child_create`` pattern. ``verification_status`` is excluded from the bank
# form (model ``editable=False`` — set only by the verify/reject actions).
class EmergencyContactForm(TenantModelForm):
    class Meta:
        model = EmergencyContact
        fields = ["name", "relationship", "phone", "alt_phone", "email", "address",
                  "is_primary", "priority_order", "notes"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}),
                   "notes": forms.Textarea(attrs={"rows": 2})}
