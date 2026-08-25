"""Procurement 6.7 E-Auction Management — EaucBid form.

The **Live Bidding Interface** input: amount + optional note. WHO is bidding is decided by the
view (vendor-portal users are pinned to their bound supplier; staff pick from the invite list) —
never by trusting a posted supplier pk, so this form carries no supplier field at all.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403


class EaucBidForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2,
        label="Your bid",
        help_text="Must undercut your previous bid by at least the minimum decrement.")
    note = forms.CharField(max_length=255, required=False, label="Note (optional)")
