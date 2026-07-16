"""HRM 3.15 Statutory Compliance — Employeestatutoryidentifier forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    EmployeeStatutoryIdentifier,
)


class EmployeeStatutoryIdentifierForm(TenantModelForm):
    class Meta:
        model = EmployeeStatutoryIdentifier
        fields = ["employee", "uan_number", "pf_number", "esi_number", "pt_state",
                  "is_pf_applicable", "is_esi_applicable"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "employee" in self.fields:
            qs = EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
            # On create (no instance pk) narrow to employees without an identifier row so the
            # OneToOne can't collide; on edit keep the current employee selectable.
            if self.instance.pk is None:
                qs = qs.exclude(statutory_identifiers__isnull=False)
            self.fields["employee"].queryset = qs.order_by("party__name")
