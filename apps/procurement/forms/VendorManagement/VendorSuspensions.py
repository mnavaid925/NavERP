"""Procurement 6.4 Vendor Management — VendorSuspension forms."""
from django import forms

from apps.procurement.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
)
from apps.procurement.models import VendorSuspension


class VendorSuspensionForm(TenantUniqueMixin, TenantModelForm):
    """Raise a suspension/blacklist REQUEST (staff decide it separately)."""

    class Meta:
        model = VendorSuspension
        fields = ["supplier", "kind", "reason_category", "reason", "po_reference",
                  "starts_on", "ends_on"]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["supplier", "po_reference"])
        return cleaned


class SuspensionDecisionForm(forms.Form):
    """Note captured when approving or rejecting a request (optional on approve)."""

    note = forms.CharField(required=False, max_length=2000,
                           widget=forms.Textarea(attrs={"class": "form-textarea",
                                                        "rows": 2}),
                           help_text="Recorded against the decision")


class SuspensionLiftForm(forms.Form):
    """Reason recorded when lifting a block — mandatory."""

    lift_note = forms.CharField(required=True, max_length=2000,
                                widget=forms.Textarea(attrs={"class": "form-textarea",
                                                             "rows": 2}),
                                help_text="Why the vendor is being unblocked")
