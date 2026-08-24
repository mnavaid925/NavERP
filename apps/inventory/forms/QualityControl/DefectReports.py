"""Inventory 5.15 Quality Control (QC) & Inspection — DefectReportForm."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import MAX_UPLOAD_BYTES, TenantUniqueMixin, _reject_foreign
from apps.inventory.models import DefectReport


class DefectReportForm(TenantUniqueMixin, TenantModelForm):
    """One floor defect capture.

    ``status`` and the resolution timestamps are verb-owned (editable=False) — the form
    never sees them. Both photo pointers stay optional (logging speed beats mandatory
    evidence); an uploaded image is capped at the core 20 MB ceiling and allowlisted to
    images in the model's ``clean()``. The crafted-POST re-check covers every
    tenant-scoped FK, including the SCM escalation pointer.
    """

    class Meta:
        model = DefectReport
        fields = ["item", "location", "lot_serial", "quantity", "defect_type", "severity",
                  "discovered_during", "description", "photo", "photo_url",
                  "reported_by", "ncr"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["item", "location", "lot_serial", "reported_by", "ncr"])
        uploaded = cleaned.get("photo")
        if uploaded and uploaded.size > MAX_UPLOAD_BYTES:
            # Same ceiling and wording shape as ProductFile / the core document tooling.
            self.add_error("photo", "File too large. Maximum size is 20 MB.")
        return cleaned
