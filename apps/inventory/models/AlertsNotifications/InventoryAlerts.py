"""Inventory 5.16 Alerts & Notifications — InventoryAlert [ALT-] + the detection engine.

One row per RAISED condition. The alert is a SNAPSHOT: type, severity, message and the
observed metric are frozen at raise time so later edits to the rule (or to the spine)
cannot rewrite what an operator was shown when they triaged it.

**The engine is deterministic and explainable — never AI.** ``run_detection()`` walks the
tenant's active rules and evaluates each watch condition against data that ALREADY lives
elsewhere (L36 — read the spine, never re-derive a second copy of it):

* low/out-of-stock → ``scm.ReorderRule`` + the append-only ``StockMove`` ledger
  (``ReorderRule.on_hand_map`` does both in one grouped query);
* overstock → 5.5's ``BinCapacity`` envelopes (utilisation is that model's own derived
  property; a bin with no declared limit can honestly raise nothing);
* expiry → ``scm.LotSerial.expiry_date``;
* PO approvals / delayed shipments → ``scm.PurchaseOrder.status == "pending_approval"``
  and ``scm.Shipment.planned_delivery_date`` in the past while not delivered/cancelled.

Dedup: ONE open-or-acknowledged alert per ``dedup_key`` — MariaDB cannot express that
partial unique constraint, so it is an engine guard, not a DB constraint (the 4.15
precedent). A cooldown window stops a flapping condition from re-raising daily.
"""
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.inventory.models._base import *  # noqa: F401,F403
from apps.inventory.models.AlertsNotifications.AlertRules import AlertRule


class InventoryAlert(TenantNumbered):
    """A raised alert [ALT-]: a snapshot of one watch condition, open until triaged."""

    NUMBER_PREFIX = "ALT"

    STATUS_CHOICES = [
        ("open", "Open"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]
    TYPE_CHOICES = AlertRule.TYPE_CHOICES
    SEVERITY_CHOICES = AlertRule.SEVERITY_CHOICES

    rule = models.ForeignKey(
        "inventory.AlertRule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="alerts",
        help_text="Rule that raised this alert (kept after the rule is deleted)")
    alert_type = models.CharField(max_length=20, choices=TYPE_CHOICES, editable=False,
                                  help_text="Snapshot of the rule's type at raise time")
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, editable=False,
                                help_text="Snapshot of the rule's severity at raise time")
    dedup_key = models.CharField(
        max_length=180, editable=False,
        help_text="Condition identity used to suppress duplicates while one is still open")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)

    # --- what the alert points at (all optional; expiry alerts point at lots, workflow at documents)
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="inventory_alerts")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="inventory_alerts")
    lot_serial = models.ForeignKey("scm.LotSerial", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="inventory_alerts")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="inventory_alerts")
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="inventory_alerts")

    metric_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, editable=False,
        help_text="Observed figure at raise time: qty on hand, % utilisation or days to expiry")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")
    acknowledged_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="+", editable=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolved_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+", editable=False)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolution_note = models.TextField(blank=True)

    raised_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["-raised_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="inv_alt_tnt_status_idx"),
            models.Index(fields=["tenant", "alert_type"], name="inv_alt_tnt_type_idx"),
        ]

    def __str__(self):
        return f"{self.number} {self.title}"

    # --------------------------------------------------------------------- lifecycle verbs
    def acknowledge(self, user):
        if self.status != "open":
            raise ValidationError(f"A {self.get_status_display()} alert cannot be acknowledged.")
        self.status = "acknowledged"
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])

    def resolve(self, user, note=""):
        if self.status == "resolved":
            raise ValidationError("This alert is already resolved.")
        self.status = "resolved"
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_note = note or ""
        self.save(update_fields=["status", "resolved_by", "resolved_at", "resolution_note",
                                 "updated_at"])

    # --------------------------------------------------------------------- detection engine
    @classmethod
    def run_detection(cls, tenant):
        """Evaluate every active rule of ``tenant`` once and raise what conditions warrant.

        Returns an explainable summary dict — the caller renders it, so a run that raises
        nothing still says WHY (nothing breached vs. suppressed as duplicate vs. cooling down).
        Whole run inside one transaction: alerts and their deliveries land together or not at all.
        """
        from apps.scm.models import LotSerial, PurchaseOrder, ReorderRule, Shipment
        from apps.inventory.models.WarehousingBinManagement.BinCapacities import BinCapacity

        now = timezone.now()
        today = timezone.localdate()
        rules = list(AlertRule.objects.filter(tenant=tenant, is_active=True).order_by("pk"))

        with transaction.atomic():
            # One alert per condition until it is triaged away...
            open_keys = set(
                cls.objects.filter(tenant=tenant).exclude(status="resolved")
                .values_list("dedup_key", flat=True))
            # ...and nothing re-raised inside the rule's cooldown window.
            last_raised = {
                row["dedup_key"]: row["last"]
                for row in cls.objects.filter(tenant=tenant)
                .values("dedup_key").annotate(last=Max("raised_at"))
            }

            summary = {"rules_evaluated": len(rules), "raised": [], "skipped_open": 0,
                       "skipped_cooldown": 0, "deliveries": 0}

            def _raise(rule, *, dedup_key, title, message, item=None, location=None,
                       lot_serial=None, purchase_order=None, shipment=None, metric=None):
                if dedup_key in open_keys:
                    summary["skipped_open"] += 1
                    return
                last = last_raised.get(dedup_key)
                if last is not None and (now - last).days < rule.cooldown_days:
                    summary["skipped_cooldown"] += 1
                    return
                alert = cls.objects.create(
                    tenant=tenant, rule=rule, alert_type=rule.alert_type,
                    severity=rule.severity, dedup_key=dedup_key, title=title, message=message,
                    item=item, location=location, lot_serial=lot_serial,
                    purchase_order=purchase_order, shipment=shipment, metric_value=metric)
                summary["deliveries"] += _write_deliveries(alert, rule)
                open_keys.add(dedup_key)
                summary["raised"].append(alert)

            by_type = {}
            for rule in rules:
                by_type.setdefault(rule.alert_type, []).append(rule)

            # --- stock-level watches (one grouped ledger aggregate for ALL rules) ---------------
            stock_rules = by_type.get("low_stock", []) + by_type.get("out_of_stock", [])
            if stock_rules:
                reorder_rules = list(ReorderRule.objects.filter(tenant=tenant, is_active=True)
                                     .select_related("item", "location"))
                on_hand = ReorderRule.on_hand_map(tenant, reorder_rules)
                for rr in reorder_rules:
                    qty = on_hand.get((rr.item_id, rr.location_id))
                    if qty is None:
                        continue
                    if qty <= ZERO:
                        for rule in by_type.get("out_of_stock", []):
                            if rule.in_scope(rr.item_id, rr.location_id):
                                _raise(rule,
                                       dedup_key=f"out_of_stock:{rr.item_id}:{rr.location_id}",
                                       title=f"Out of stock: {rr.item.sku} @ {rr.location.code}",
                                       message=(f"On-hand for {rr.item.sku} at {rr.location.code} "
                                                f"is {qty} (reorder point {rr.reorder_point})."),
                                       item=rr.item, location=rr.location, metric=qty)
                    elif qty <= rr.reorder_point:
                        for rule in by_type.get("low_stock", []):
                            if rule.in_scope(rr.item_id, rr.location_id):
                                _raise(rule,
                                       dedup_key=f"low_stock:{rr.item_id}:{rr.location_id}",
                                       title=f"Low stock: {rr.item.sku} @ {rr.location.code}",
                                       message=(f"On-hand for {rr.item.sku} at "
                                                f"{rr.location.code} is {qty}, at/below the "
                                                f"reorder point {rr.reorder_point}."),
                                       item=rr.item, location=rr.location, metric=qty)

            # --- overstock watches (only bins with a DECLARED limit can breach one) -------------
            overstock_rules = by_type.get("overstock", [])
            if overstock_rules:
                profiles = (BinCapacity.objects.filter(tenant=tenant)
                            .select_related("location"))
                for profile in profiles:
                    utilisation = profile.quantity_utilisation
                    if utilisation is None:
                        continue  # no max_quantity declared — honestly nothing to compare against
                    for rule in overstock_rules:
                        if rule.in_scope(item_id=None, location_id=profile.location_id) \
                                and utilisation > rule.overstock_pct:
                            _raise(rule, dedup_key=f"overstock:{profile.location_id}",
                                   title=f"Overstock: {profile.location.code}",
                                   message=(f"{profile.location.code} holds {profile.on_hand} units, "
                                            f"{utilisation.quantize(Decimal('0.1'))}% of its declared "
                                            f"maximum {profile.max_quantity} "
                                            f"(threshold {rule.overstock_pct}%)."),
                                   location=profile.location,
                                   metric=utilisation.quantize(Decimal("0.1")))

            # --- expiry watches -------------------------------------------------------------------
            # Hoisted above the rule loop: N rules of this type share ONE queryset, mirroring
            # the stock block (a pair with zero StockMove history yields None from on_hand_map
            # and is SKIPPED on purpose - no history means no observable level, and answering
            # zero would cry wolf on freshly created rules).
            expiry_rules = by_type.get("expiry", [])
            lots = None
            if expiry_rules:
                lots = list(LotSerial.objects.filter(tenant=tenant, expiry_date__isnull=False)
                            .exclude(status="consumed").select_related("item"))
            for rule in expiry_rules:
                for lot in lots or ():
                    days_left = (lot.expiry_date - today).days
                    if days_left > rule.expiry_days:
                        continue
                    if days_left < ZERO:
                        title = f"Expired: {lot.item.sku} · {lot.number}"
                        message = (f"Lot {lot.number} of {lot.item.sku} expired "
                                   f"{abs(days_left)} day(s) ago ({lot.expiry_date}).")
                    else:
                        title = f"Expiring: {lot.item.sku} · {lot.number}"
                        message = (f"Lot {lot.number} of {lot.item.sku} expires in {days_left} "
                                   f"day(s) on {lot.expiry_date} (within the "
                                   f"{rule.expiry_days}-day window).")
                    _raise(rule, dedup_key=f"expiry:{lot.pk}", title=title, message=message,
                           item=lot.item, lot_serial=lot, metric=days_left)

            # --- workflow triggers ------------------------------------------------------------------
            pending_pos = None
            if by_type.get("po_approval_pending"):
                pending_pos = list(PurchaseOrder.objects.filter(tenant=tenant,
                                                                status="pending_approval"))
            for rule in by_type.get("po_approval_pending", []):
                for po in pending_pos or ():
                    _raise(rule, dedup_key=f"po_approval:{po.pk}",
                           title=f"PO {po.number} awaiting approval",
                           message=(f"Purchase order {po.number} has been sitting in "
                                    f"pending approval since "
                                    f"{po.order_date or 'an unrecorded date'}."),
                           purchase_order=po)

            late_shipments = None
            if by_type.get("shipment_delayed"):
                late_shipments = list(Shipment.objects.filter(
                    tenant=tenant, planned_delivery_date__lt=today)
                    .exclude(status__in=("delivered", "cancelled")))
            for rule in by_type.get("shipment_delayed", []):
                for shipment in late_shipments or ():
                    days_late = (today - shipment.planned_delivery_date).days
                    _raise(rule, dedup_key=f"shipment_delayed:{shipment.pk}",
                           title=f"Shipment {shipment.number} delayed",
                           message=(f"Shipment {shipment.number} was due "
                                    f"{shipment.planned_delivery_date} and is {days_late} "
                                    f"day(s) late (status: {shipment.get_status_display()})."),
                           shipment=shipment, purchase_order=shipment.purchase_order,
                           metric=days_late)

        return summary


def _write_deliveries(alert, rule):
    """Queue one NotificationDelivery per enabled channel (email: one per recipient).

    # WARNING: NO real SMTP/SMS/push gateway is wired in NavERP yet — every delivery is
    # recorded with status "queued" and a detail line saying so, which is the HONEST state.
    # Integrate real gateways behind this writer before claiming anything was "sent".
    """
    from apps.inventory.models.AlertsNotifications.NotificationDeliveries import (
        NotificationDelivery,
    )

    created = 0
    for channel in rule.channels:
        if channel == "email":
            targets = rule._normalized_recipients()
        else:
            targets = [NotificationDelivery.BROADCAST]
        for recipient in targets:
            NotificationDelivery.objects.create(
                tenant=alert.tenant, alert=alert, channel=channel, recipient=recipient,
                status="queued",
                detail="Queued only — no gateway configured; dispatch integration deferred.")
            created += 1
    return created
