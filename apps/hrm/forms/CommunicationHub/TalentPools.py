"""HRM 3.27 Communication Hub — TalentPools forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    TalentPool,
)


class TalentPoolForm(TenantModelForm):
    class Meta:
        model = TalentPool
        fields = ["name", "pool_type", "description", "owner", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "owner" in self.fields:
            self.fields["owner"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, name) — Django skips validate_unique because tenant is form-excluded.
        name = cleaned.get("name")
        if name and self.tenant is not None:
            dupe = TalentPool.objects.filter(tenant=self.tenant, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "A talent pool with this name already exists.")
        return cleaned
