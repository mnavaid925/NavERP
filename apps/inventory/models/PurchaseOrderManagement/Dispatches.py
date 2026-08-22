"""Inventory 5.3 Purchase Order (PO) Management — PurchaseOrderDispatch model.

**PO Dispatch bullet.** SCM's built-in send action flips an approved order to ``sent`` and
remembers nothing else — no channel, no recipient, no proof of transmission. For email and
EDI dispatch that record IS the feature: a buyer must be able to show WHAT left, WHEN, to
WHICH address/mailbox, under WHICH reference (message id / interchange control number).
This log is that proof; the spine's status stays the single source of truth for where the
order now sits.

A dispatch is created through its form against an order that has been APPROVED — drafting
or still-pending orders have nothing to send yet. The FIRST transmission of an
``approved`` order moves it to ``sent`` inside the same transaction (the spine's own
transition, scm's ``purchaseorder_send`` semantics); later rows are re-sends and change
nothing.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class PurchaseOrderDispatch(TenantNumbered):
    """One recorded transmission of a purchase order to a vendor [PD-]."""

    NUMBER_PREFIX = "PD"

    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("edi", "EDI"),
        ("print", "Print / PDF"),
    ]
    #: Channels whose ``recipient`` is a real address — print needs none. Decided in ONE
    #: place so the model check, the form and the template hint cannot drift apart.
    ADDRESSED_CHANNELS = ("email", "edi")
    CHANNEL_CSS = {
        "email": "badge-info",
        "edi": "badge-green",
        "print": "badge-slate",
    }

    # CASCADE for the same reason as PurchaseOrderApproval: scm's PO delete carries no
    # status guard, so PROTECT would 500 on any old dispatched order being cleaned up;
    # core.AuditLog keeps the provenance either way.
    purchase_order = models.ForeignKey(
        "scm.PurchaseOrder", on_delete=models.CASCADE, related_name="inventory_dispatches")
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="email")
    recipient = models.CharField(
        max_length=255,
        help_text="Vendor email address, or EDI mailbox/partner ID")
    reference = models.CharField(
        max_length=255, blank=True,
        help_text="Message-ID or interchange control number from the transport")
    dispatched_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-dispatched_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "purchase_order"], name="inv_pd_tnt_po_idx"),
            models.Index(fields=["tenant", "dispatched_at"], name="inv_pd_tnt_sent_idx"),
        ]

    def clean(self):
        """Addressed channels need a recipient, and the order must be this tenant's."""
        super().clean()
        if self.channel in self.ADDRESSED_CHANNELS and not (self.recipient or "").strip():
            raise ValidationError({"recipient": "An email/EDI dispatch needs a recipient."})
        if self.purchase_order_id and self.purchase_order.tenant_id != self.tenant_id:
            raise ValidationError({"purchase_order": "That order belongs to another workspace."})

    @property
    def channel_css(self):
        return self.CHANNEL_CSS.get(self.channel, "badge-muted")

    def __str__(self):
        po = self.purchase_order.number if self.purchase_order_id else "PO"
        return f"{self.number or 'PD'} · {po} · {self.get_channel_display()}"
