"""Inventory 5.16 Alerts & Notifications — AlertRule [ARL-].

The RULE CATALOG of the alert engine: WHAT to watch (``alert_type``), HOW LOUD
(``severity`` + channels), and WHERE (optional ``item``/``location`` scope — blank
means "everywhere"). A rule never stores a stock figure: every threshold it needs is
either its own knob (``expiry_days``, ``overstock_pct``) or a number that already
lives on the spine it points at — reorder points stay on ``scm.ReorderRule``, bin
limits on 5.5's ``BinCapacity``, lot expiries on ``scm.LotSerial.expiry_date``
(L36: extend the spine, never re-declare it).

The engine that EVALUATES these rules lives on ``InventoryAlert.run_detection()``;
this model is deliberately dumb data so a rule can be edited without touching code.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class AlertRule(TenantNumbered):
    """A standing watch condition [ARL-] the detection engine evaluates on demand."""

    NUMBER_PREFIX = "ARL"

    TYPE_CHOICES = [
        ("low_stock", "Low Stock"),
        ("out_of_stock", "Out of Stock"),
        ("overstock", "Overstock"),
        ("expiry", "Expiry"),
        ("po_approval_pending", "PO Awaiting Approval"),
        ("shipment_delayed", "Delayed Shipment"),
    ]
    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("critical", "Critical"),
    ]

    name = models.CharField(max_length=120, help_text="Human-readable rule name")
    alert_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES,
        help_text="Which watch condition the engine evaluates")
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default="warning",
        help_text="Stamped onto every alert this rule raises")

    # --- scope (both blank = whole workspace) ------------------------------------------------------
    item = models.ForeignKey(
        "scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="alert_rules",
        help_text="Watch only this item (blank = all items; ignored for PO/shipment types)")
    location = models.ForeignKey(
        "scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="alert_rules",
        help_text="Watch only this location (blank = all locations; lots carry no location)")

    # --- thresholds (per type; unused knobs are simply ignored by the engine) ----------------------
    expiry_days = models.PositiveIntegerField(
        default=30,
        validators=[MaxValueValidator(3650)],
        help_text="Expiry rules: flag lots expiring within this many days (0 = expired only)")
    overstock_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=100,
        # Capped at what decimal(5,2) can actually hold (999.99) — a validator admitting
        # 1000 would pass the form and then DataError inside the driver.
        validators=[MinValueValidator(ZERO), MaxValueValidator(Decimal("999.99"))],
        help_text="Overstock rules: raise when bin utilisation exceeds this % of max_quantity")

    # --- channels -----------------------------------------------------------------------------------
    notify_inapp = models.BooleanField(default=True, help_text="Raise in the in-app alert inbox")
    notify_email = models.BooleanField(default=False, help_text="Queue an email delivery per recipient")
    notify_sms = models.BooleanField(default=False, help_text="Queue an SMS delivery")
    notify_push = models.BooleanField(default=False, help_text="Queue a push notification")
    email_recipients = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated email addresses for the email channel")

    cooldown_days = models.PositiveIntegerField(
        default=7,
        validators=[MaxValueValidator(365)],
        help_text="Do not re-raise the same condition within this many days")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("tenant", "name")]
        indexes = [
            models.Index(fields=["tenant", "alert_type", "is_active"], name="inv_alr_tnt_type_idx"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Re-serialise the normalised list back to the comma-separated column form.
        self.email_recipients = ",".join(self._normalized_recipients())
        return super().save(*args, **kwargs)

    def clean(self):
        """Crafted-POST guards: foreign scope rows, and an email channel nobody would receive."""
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            raise ValidationError({"item": "Item belongs to another workspace."})
        if self.location_id and getattr(self.location, "tenant_id", None) != tenant_id:
            raise ValidationError({"location": "Location belongs to another workspace."})
        if self.notify_email and not self._normalized_recipients():
            raise ValidationError({
                "email_recipients": "List at least one email address, or turn the email channel off."})

    def _normalized_recipients(self):
        """The comma-separated recipient list, split/stripped/lowercased/deduped, order kept."""
        seen, out = set(), []
        for raw in (self.email_recipients or "").replace(";", ",").split(","):
            addr = raw.strip().lower()
            if addr and addr not in seen:
                seen.add(addr)
                out.append(addr)
        return out

    @property
    def channels(self):
        """Enabled channel codes in a stable order — what the delivery writer walks."""
        return [code for code, enabled in (
            ("in_app", self.notify_inapp),
            ("email", self.notify_email),
            ("sms", self.notify_sms),
            ("push", self.notify_push),
        ) if enabled]

    def in_scope(self, item_id=None, location_id=None):
        """True when the observed row falls inside this rule's optional item/location scope."""
        if self.item_id and item_id != self.item_id:
            return False
        if self.location_id and location_id != self.location_id:
            return False
        return True
