"""Procurement 6.5 Sourcing & Tendering — SourcingBid forms.

Supplier choices mirror scm's own rule: a party tagged ``supplier`` OR ``vendor`` can be bid
from (peer apps deliberately don't import each other's internals, so this is a local copy of
that one-liner, documented the same way). Event choices exclude terminal events — a bid cannot
be filed against something already awarded or cancelled.
"""
from apps.core.models import Party

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import SourcingBid, SourcingEvent


def _supplier_parties(tenant):
    """Parties this tenant can buy from (same rule as scm 4.1's helper).

    ``core.PartyRole`` distinguishes ``supplier`` from ``vendor`` and in practice a party
    tagged by accounting carries ``vendor`` — accept BOTH rather than silently hiding half
    the counterparties from the buyer.
    """
    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


class SourcingBidForm(TenantModelForm):
    class Meta:
        model = SourcingBid
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save();
        # ``status`` moves only through the lifecycle verbs (submit/shortlist/disqualify/award);
        # ``submitted_by``/``submitted_at`` are stamped by submit() (never choosable).
        fields = ["event", "supplier", "total_price", "lead_time_days", "is_compliant",
                  "compliance_note", "summary", "contact_ref"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if tenant is not None:
            self.fields["event"].queryset = SourcingEvent.objects.filter(
                tenant=tenant,
                status__in=("draft", "open", "closed"),
            ).order_by("-created_at")
            self.fields["supplier"].queryset = _supplier_parties(tenant)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["event", "supplier"])
        event = cleaned.get("event")
        # A NEW bid may only target an event still accepting submissions; an EXISTING draft is
        # left alone here (its event may have closed after drafting — submitting will refuse).
        if event is not None and self.instance.pk is None and not event.bids_allowed:
            self.add_error("event", "That sourcing event is not open for bids.")
        if not cleaned.get("is_compliant") and not cleaned.get("compliance_note"):
            self.add_error("compliance_note",
                           "Say what is missing when the bid is marked not compliant.")
        return cleaned
