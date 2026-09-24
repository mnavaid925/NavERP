"""CRM 1.1 Core Data Management — Leads forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Lead,
)


class LeadForm(TenantModelForm):
    class Meta:
        model = Lead
        fields = ["name", "company", "title", "email", "phone", "source",
                  "status", "est_value", "owner", "description"]

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if user is not None and not (getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False)):
            self.fields.pop("status", None)
            self.fields.pop("owner", None)

    def clean(self):
        cleaned = super().clean()
        has_status = "status" in self.fields
        has_owner = "owner" in self.fields
        status = cleaned.get("status")
        if has_status and status == "converted":
            self.add_error("status", "Use the conversion action to mark a lead converted.")
        if self.instance.pk and self.instance.status == "converted":
            if has_status and status != "converted":
                self.add_error("status", "A converted lead cannot be reopened through this form.")
            if has_owner and cleaned.get("owner_id") != self.instance.owner_id:
                self.add_error("owner", "A converted lead cannot be reassigned through this form.")
        return cleaned
