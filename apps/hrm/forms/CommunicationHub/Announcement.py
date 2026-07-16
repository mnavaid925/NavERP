"""HRM 3.27 Communication Hub — Announcement forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Announcement,
)


class AnnouncementForm(TenantModelForm):
    """Admin-authored announcement. `status`/`published_at`/`author` are workflow-owned (set by the
    publish action + server-side on create) and excluded. The department/designation targets are
    tenant-scoped automatically by TenantModelForm; `clean()` mirrors the model's matching-target rule
    so a mismatch surfaces inline on the form, not only at full_clean()."""

    class Meta:
        model = Announcement
        fields = ["title", "body", "category", "audience_type",
                  "target_department", "target_designation", "is_pinned", "expires_at"]
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get("audience_type")
        if audience == "department" and not cleaned.get("target_department"):
            self.add_error("target_department", "Select the department this announcement targets.")
        if audience == "designation" and not cleaned.get("target_designation"):
            self.add_error("target_designation", "Select the designation this announcement targets.")
        return cleaned
