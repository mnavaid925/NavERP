"""CRM 1.2 Sales Force Automation — Territories forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Territory,
)


# ===== 1.2 Sales Force Automation (recreated) ===============================
class TerritoryForm(TenantModelForm):
    class Meta:
        model = Territory
        fields = ["name", "region", "segment", "parent", "manager", "is_active", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A territory can't be its own parent.
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)
