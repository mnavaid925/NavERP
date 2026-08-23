"""Inventory 5.8 Lot & Serial Number Tracking — LotNumberRule.

**Lot/Batch Generation** bullet: "Assigning unique batch numbers upon receiving or
manufacturing." The lot/serial ROWS themselves are 4.3's ``scm.LotSerial`` (L36 — extend
the spine, never re-declare it); what the spine's create form lacks is a NUMBERING
CONVENTION: every user free-types ``LOT001``-style codes and the scheme drifts. This is
the management layer: a pattern rule (prefix + optional date component + zero-padded
sequence, per item or the tenant default) whose :meth:`LotNumberRule.generate` mints the
next ``scm.LotSerial`` under the resolved rule.

Resolution is most-specific-wins, mirroring 5.4's putaway resolver: an active item rule
beats the active tenant default; no rule at all means generation is refused with a
message pointing here rather than silently falling back to an arbitrary format.

Generation posts NO StockMove (L37 discipline): minting a number claims no stock. A
generated lot simply starts with zero ledger history; the receipt/production document
that actually receives against it posts those moves and this sub-module's trace page
reads them back.
"""
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403


class LotNumberRule(TenantOwned):
    """A batch/serial numbering pattern [of 5.8] — the generator behind scm.LotSerial rows."""

    KIND_CHOICES = [("lot", "Lot / Batch"), ("serial", "Serial")]

    name = models.CharField(max_length=64)
    # None = the tenant-wide default fallback. An item-scoped rule outranks it.
    item = models.ForeignKey(
        "scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lot_number_rules",
        help_text="Leave empty for the tenant-wide default; an item rule overrides it")
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, default="lot",
                            help_text="What kind of tracked number this rule mints")
    prefix = models.CharField(
        max_length=12, default="LOT",
        help_text="Literal stem of the number, upper-cased on save, e.g. LOT / BATCH-A")
    include_date = models.BooleanField(
        default=True, help_text="Append a YYMMDD date component after the prefix")
    sequence_padding = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(9)],
        help_text="Zero-padded width of the running sequence, e.g. 5 → 00001")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["item__sku", "name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="inv_lnr_tnt_active_idx")]

    # -- resolution ------------------------------------------------------------------------------

    @classmethod
    def resolve(cls, tenant, item):
        """The active rule that governs ``item`` — its own rule, else the tenant default.

        Returns ``None`` when nothing governs: the generate view refuses rather than
        inventing a format nobody agreed on.
        """
        rules = cls.objects.filter(tenant=tenant, is_active=True)
        if item is not None:
            specific = rules.filter(item=item).order_by("pk").first()
            if specific is not None:
                return specific
        return rules.filter(item__isnull=True).order_by("pk").first()

    def sample_number(self, seq=1):
        """A representative number under this pattern — for previews, never persisted."""
        date_part = timezone.localdate().strftime("%y%m%d") if self.include_date else ""
        return f"{self.prefix}{date_part}-{seq:0{self.sequence_padding}d}"

    def _next_sequence(self, item):
        """One past the highest suffix already minted under today's stem for this item.

        The uniqueness key is LotSerial's ``(tenant, item, number)``, so the scan is
        scoped to exactly the pool this number must be unique within.
        """
        from apps.scm.models import LotSerial

        stem = self.sample_number(seq=0).rsplit("-", 1)[0] + "-"
        top = 0
        for existing in (LotSerial.objects.filter(tenant_id=self.tenant_id, item=item,
                                                  number__startswith=stem)
                         .values_list("number", flat=True)):
            suffix = existing[len(stem):]
            if suffix.isdigit():
                top = max(top, int(suffix))
        return top + 1

    def generate(self, user, item, expiry_date=None, notes=""):
        """Mint the next ``scm.LotSerial`` under this rule and return it.

        Refuses untracked items (a tracked number on an ``tracking='none'`` SKU is
        master-data noise — set tracking on the SCM item first) and foreign items.
        The retry loop is the TenantNumbered collision guard: two concurrent clicks
        can race past ``_next_sequence`` together, and the loser retries one higher.
        A double-CLICK still mints two distinct valid numbers (each POST resolves its
        own next sequence) — deliberate: the master is append-only and an accidental
        extra number is deleted from the SCM master before any move references it,
        whereas a lock would turn a stuck request into a blocked receiving line.
        """
        from apps.core.utils import write_audit_log
        from apps.scm.models import LotSerial

        if item is None:
            raise ValidationError("Choose the item the number is being generated for.")
        if item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})
        if item.tracking == "none":
            raise ValidationError(
                f"{item.sku} is not lot/serial-tracked — set its tracking mode on the "
                "SCM item first.")
        if item.tracking != self.kind:
            raise ValidationError(
                f"{item.sku} tracks by {item.get_tracking_display().lower()}, but this "
                f"rule mints {self.get_kind_display().lower()} numbers.")

        seq = self._next_sequence(item)
        for _ in range(5):
            number = self.sample_number(seq=seq)
            try:
                with transaction.atomic():
                    # An already past-dated expiry enters the master as expired — the
                    # spine's status is what spine-side flows filter on, and minting
                    # must not contradict this module's own red badge.
                    initial_status = ("expired" if expiry_date is not None
                                      and expiry_date < timezone.localdate()
                                      else "available")
                    lot = LotSerial.objects.create(
                        tenant_id=self.tenant_id, item=item, kind=self.kind,
                        number=number, expiry_date=expiry_date,
                        status=initial_status, notes=notes or "")
                    write_audit_log(user, lot, "generate",
                                    {"via": self.name, "number": number})
                    return lot
            except IntegrityError:
                seq += 1
        raise ValidationError(
            "Could not allocate a unique number after several attempts — try again.")

    def clean(self):
        super().clean()
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})

    def save(self, *args, **kwargs):
        self.prefix = (self.prefix or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        scope = self.item.sku if self.item_id else "All items"
        return f"{self.name} ({scope})"
