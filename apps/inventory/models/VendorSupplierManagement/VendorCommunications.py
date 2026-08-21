"""Inventory 5.2 Vendor / Supplier Management — VendorCommunication model.

**The one genuinely new table in 5.2.** The sub-module's other three bullets are already
served by SCM 4.2 Supplier Relationship Management, which owns the supplier spine (L36 —
extend the spine, never re-declare it): the directory is ``scm.SupplierProfile``,
performance is the signal-derived ``scm.SupplierScorecard``, and contract & terms live on
``scm.SupplierContract`` (payment terms) plus ``SupplierCatalogItem`` (per-line lead times
and MOQs). A second copy of any of those here would be two sources of truth for the same
supplier.

What nothing else records is the conversation itself — the calls, emails, meetings and
site visits a buyer has with a vendor. This log points at the vendor ``core.Party``
directly (not at ``SupplierProfile``) so history survives even for a party whose SRM
profile was never finished, and PROTECTs so deleting a party cannot silently destroy the
interaction record an auditor or a successor buyer would need.

"Logged by" is deliberately NOT a column: every create/edit/delete writes a
``core.AuditLog`` row via the shared CRUD helpers, so provenance already exists and a
second who-wrote-this figure could only drift from it.
"""
import datetime

from django.core.exceptions import ValidationError

from apps.inventory.models._base import *  # noqa: F401,F403


class VendorCommunication(TenantNumbered):
    """One logged interaction with a vendor [VC-] — call/email/meeting/site visit/note."""

    NUMBER_PREFIX = "VC"

    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("call", "Call"),
        ("meeting", "Meeting"),
        ("site_visit", "Site Visit"),
        ("note", "Note"),
    ]
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]

    #: Badge colour per channel, decided in ONE place. theme.css only ships colour-named badge
    #: modifiers (green/red/amber/info/muted/slate) — the semantic -success/-warning/-danger
    #: variants do not exist and render unstyled (lesson L33).
    CHANNEL_CSS = {
        "email": "badge-info",
        "call": "badge-green",
        "meeting": "badge-amber",
        "site_visit": "badge-slate",
        "note": "badge-muted",
    }

    party = models.ForeignKey(
        "core.Party", on_delete=models.PROTECT, related_name="inventory_vendor_communications",
        help_text="The vendor this interaction belongs to")
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES, default="email")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    occurred_at = models.DateTimeField(
        default=timezone.now, help_text="When the interaction actually happened")
    follow_up_on = models.DateField(
        null=True, blank=True, help_text="Optional next-action date; drives the due/overdue filters")

    class Meta:
        ordering = ["-occurred_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "party"], name="inv_vc_tnt_party_idx"),
            models.Index(fields=["tenant", "channel"], name="inv_vc_tnt_channel_idx"),
            models.Index(fields=["tenant", "follow_up_on"], name="inv_vc_tnt_followup_idx"),
        ]

    def clean(self):
        """A crafted POST must not attach this log to another workspace's vendor."""
        super().clean()
        if self.party_id and self.party.tenant_id != self.tenant_id:
            raise ValidationError({"party": "That vendor belongs to another workspace."})

    @property
    def channel_css(self):
        """The badge class for this row's channel — see :attr:`CHANNEL_CSS`."""
        return self.CHANNEL_CSS.get(self.channel, "badge-muted")

    @property
    def is_follow_up_overdue(self):
        """True when the next action date has passed with no recorded completion.

        A follow-up dated TODAY is still due, not overdue — "call them back on Friday"
        is not broken until Friday ends."""
        return bool(self.follow_up_on and self.follow_up_on < datetime.date.today())

    def __str__(self):
        return f"{self.number or 'VC'} · {self.get_channel_display()} · {self.party_id and self.party.name}"
