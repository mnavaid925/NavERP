"""HRM 3.27 Communication Hub — HelpdeskCategorys forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskCategory,
    HelpdeskSLAPolicy,
)


class HelpdeskCategoryForm(TenantModelForm):
    class Meta:
        model = HelpdeskCategory
        fields = ["name", "department", "description", "default_assignee", "default_sla_policy", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "default_sla_policy" in self.fields:
            self.fields["default_sla_policy"].queryset = (
                HelpdeskSLAPolicy.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))
