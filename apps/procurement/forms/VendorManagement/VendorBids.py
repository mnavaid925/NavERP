"""Procurement 6.4 Vendor Management — the supplier-facing bid form.

The **gated supplier page** 6.5's SourcingBid docstring deferred: once a vendor login is
bound (VendorPortalAccess), the supplier can complete and submit their OWN draft bids from
the portal. The form deliberately excludes ``event`` and ``supplier`` — the view forces
both server-side, so a crafted POST can neither re-point the bid to another event nor file
under another company. Lifecycle stays owned by ``SourcingBid.submit()``; this form only
edits DRAFT content.
"""
from django import forms

from apps.procurement.forms._common import TenantModelForm, TenantUniqueMixin
from apps.procurement.models import SourcingBid


class VendorBidForm(TenantUniqueMixin, TenantModelForm):
    """Edit the DRAFT content of one of the bound supplier's own bids."""

    class Meta:
        model = SourcingBid
        fields = ["total_price", "lead_time_days", "is_compliant",
                  "compliance_note", "summary", "contact_ref"]

    def clean(self):
        cleaned = super().clean()
        # Same honesty rule the staff-side SourcingBidForm enforces: a bid declared
        # non-compliant must say what is missing, or evaluation cannot score it fairly.
        if not cleaned.get("is_compliant") and not cleaned.get("compliance_note"):
            self.add_error("compliance_note",
                           "Say what is missing when the bid is marked not compliant.")
        return cleaned
