"""Procurement 6.7 E-Auction Management — Eauction forms.

The setup form IS the **Auction Setup & Configuration** bullet: window, pricing ladder
(start/reserve/min-decrement) and the anti-snipe trio live here; the invite form admits
suppliers one POST at a time (an auction rarely invites more than a handful, and each add needs
its own narrowed supplier dropdown).
"""
from apps.core.models import Party

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import EaucInvite, Eauction


class EauctionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Eauction
        # EXCLUDED and why: number/extensions_used/awarded_* are stamped by actions; status moves
        # only through publish/close/cancel/award.
        fields = ["title", "description", "auction_type", "currency", "requisition",
                  "start_price", "reserve_price", "min_decrement",
                  "extension_trigger_seconds", "extension_seconds", "max_extensions",
                  "opens_at", "closes_at"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["requisition"])
        # The instance clean() (close-after-open) runs through full_clean; this adds the
        # crafted-POST shape check for the anti-snipe pair.
        trigger = cleaned.get("extension_trigger_seconds")
        if trigger is not None and trigger < 5:
            self.add_error("extension_trigger_seconds",
                           "Give bidders at least 5 seconds of extension zone.")
        return cleaned


class EaucInviteForm(forms.Form):
    """Admit ONE supplier (tenant parties carrying the supplier role, not yet invited)."""

    supplier = forms.ModelChoiceField(
        queryset=Party.objects.none(), label="Supplier",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Only workspace parties with the supplier role are listed.")
    contact_note = forms.CharField(max_length=255, required=False, label="Note (optional)",
                                   widget=forms.TextInput(attrs={"class": "form-input"}))

    def __init__(self, *args, tenant=None, auction=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.auction = auction
        invited = (auction.invites.values_list("supplier_id", flat=True)
                   if auction is not None else [])
        self.fields["supplier"].queryset = (
            Party.objects.filter(tenant=tenant,
                                 roles__role="supplier")
            .exclude(pk__in=list(invited))
            .distinct()
            .order_by("name"))

    def save(self):
        """get_or_create on the (auction, supplier) pair — a double-submitted POST must
        land as a no-op, not an IntegrityError 500."""
        invite, _created = EaucInvite.objects.get_or_create(
            tenant=self.tenant,
            auction=self.auction,
            supplier=self.cleaned_data["supplier"],
            defaults={"contact_note": self.cleaned_data.get("contact_note", "")},
        )
        return invite
