"""Procurement 6.11 Order Fulfillment & Tracking — Backorder model.

**Backorder Management** bullet: when a supplier cannot ship the whole ordered quantity on time,
the shortfall becomes a tracked, chased commitment rather than a note in somebody's inbox. A
``Backorder`` [BKO-] records HOW MUCH is outstanding against one ``scm.PurchaseOrderLine``, WHY,
what date was originally promised, what date is promised NOW, and how many times that promise has
already moved — which is the number that actually predicts whether the line will land.

**This model is READ-ONLY against the spine (L36).** It never writes ``PurchaseOrderLine.quantity``
/ ``unit_price`` / ``tax_rate_pct`` nor ``PurchaseOrder.expected_date`` / ``status`` / ``version``.
6.10's ``PurchaseOrderChange.apply()`` is the only mutator of a dispatched order; a backorder is a
FACT recorded alongside the order, not an amendment to it. If the buyer decides the order itself
must change, that is a change order — a different document with a different approval.

Escalation raises into the EXISTING 6.1 ``ProcurementAlert`` inbox (``kind="delivery"``, already in
its KIND_CHOICES) rather than a second alert table, so a procurement user still works one queue.
``raise_alert()`` is idempotent: an open alert is returned, not duplicated, so a double-click (or a
nightly sweep) cannot spam the inbox.

Everything time-derived here — days open, days late, the risk bucket — is a PROPERTY computed from
the stored dates (L29). Nothing about elapsed time is stored, because a stored "days late" is wrong
the moment the clock ticks past midnight.
"""
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models._base import *  # noqa: F401,F403


class Backorder(TenantNumbered):
    """One outstanding shortfall against a purchase order line [BKO-].

    Lifecycle: ``open`` -> ``rescheduled`` (the promise moved; still live) -> ``fulfilled`` or
    ``cancelled``. ``status`` is ``editable=False`` and moves ONLY through the verb methods below,
    every one of which re-checks its own guard INSIDE the method — hiding a button in a template
    does not stop a direct POST, and a guard that lives only in the view is a guard the model does
    not have (the 6.9 C1 lesson).
    """

    NUMBER_PREFIX = "BKO"

    REASON_CHOICES = [
        ("out_of_stock", "Out of Stock"),
        ("production_delay", "Production Delay"),
        ("allocation", "Allocation Shortfall"),
        ("material_shortage", "Material Shortage"),
        ("supplier_capacity", "Supplier Capacity"),
        ("logistics", "Logistics"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("rescheduled", "Rescheduled"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    ]
    #: Still live — the only states any verb may act from, and the only ones the risk board counts.
    OPEN_STATUSES = ("open", "rescheduled")
    #: Drives the ``?risk=`` filter widget on the list page. These are DERIVED buckets, not a stored
    #: column: the same four names are expressed as ORM date arithmetic in the list view so the
    #: filter, the stat cards and the per-row badge cannot drift apart.
    RISK_CHOICES = [
        ("past_due", "Past due"),
        ("at_risk", "At risk (7 days)"),
        ("no_commitment", "No commitment"),
        ("on_track", "On track"),
    ]
    #: How far ahead a live promise still counts as "at risk" rather than "on track".
    AT_RISK_DAYS = 7

    po_line = models.ForeignKey(
        "scm.PurchaseOrderLine", on_delete=models.PROTECT,
        related_name="procurement_backorders",
        help_text="The ordered line whose quantity is short")
    delivery_schedule = models.ForeignKey(
        "procurement.DeliverySchedule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="backorders",
        help_text="The split-delivery instalment that fell short, when there is one")
    asn = models.ForeignKey(
        "procurement.AdvancedShipmentNotice", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="backorders",
        help_text="The shipment whose declared quantity revealed the shortfall")

    quantity_backordered = models.DecimalField(
        max_digits=14, decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="How much of the ordered quantity is still outstanding")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default="out_of_stock")
    reason_note = models.CharField(
        max_length=255, blank=True,
        help_text="Required when the reason is 'Other'; also carries the latest reschedule note")

    original_promise_date = models.DateField(
        null=True, blank=True,
        help_text="The date first committed to — kept so slippage stays visible after a reschedule")
    revised_promise_date = models.DateField(
        null=True, blank=True, help_text="The date the supplier is committing to now")
    #: How many times the promise has already moved. Stamped by reschedule() only — a buyer must
    #: not be able to type this number down.
    reschedule_count = models.PositiveIntegerField(default=0, editable=False)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open",
                              editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    closure_note = models.CharField(max_length=255, blank=True, editable=False)

    #: The 6.1 inbox row this backorder escalated into, if any. ``related_name="+"`` because the
    #: alert side never needs to walk back — the link is one-directional by design.
    alert = models.ForeignKey("procurement.ProcurementAlert", on_delete=models.SET_NULL,
                              null=True, blank=True, editable=False, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False,
                                   related_name="procurement_backorders_created")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            # Every index below backs a filter the list page actually issues: the ?status= and
            # ?reason= selects, and the ?risk= date arithmetic (which orders on the revised promise).
            models.Index(fields=["tenant", "status"], name="prc_bko_tnt_status_idx"),
            models.Index(fields=["tenant", "reason"], name="prc_bko_tnt_reason_idx"),
            models.Index(fields=["tenant", "revised_promise_date"],
                         name="prc_bko_tnt_revdate_idx"),
        ]

    # -- validation --------------------------------------------------------------------------

    def clean(self):
        errors = {}

        line = self.po_line if self.po_line_id else None
        if line is not None:
            ordered = line.quantity or ZERO
            if self.quantity_backordered is not None and self.quantity_backordered > ordered:
                errors["quantity_backordered"] = (
                    f"Cannot backorder more than the {ordered} ordered on this line.")
            # A crafted POST can name ANY line pk — the narrowed <select> is UX, not a boundary.
            if line.purchase_order.tenant_id != self.tenant_id:
                errors["po_line"] = "That record belongs to another workspace."

        if self.reason == "other" and not (self.reason_note or "").strip():
            errors["reason_note"] = "Describe the reason when choosing Other."

        if self.delivery_schedule_id:
            schedule = self.delivery_schedule
            if schedule.tenant_id != self.tenant_id:
                errors["delivery_schedule"] = "That record belongs to another workspace."
            elif line is not None and schedule.po_line.purchase_order_id != line.purchase_order_id:
                errors["delivery_schedule"] = (
                    "That delivery schedule belongs to a different purchase order.")

        if self.asn_id:
            asn = self.asn
            if asn.tenant_id != self.tenant_id:
                errors["asn"] = "That record belongs to another workspace."
            elif line is not None and asn.purchase_order_id != line.purchase_order_id:
                errors["asn"] = "That shipment notice belongs to a different purchase order."

        if errors:
            raise ValidationError(errors)

    # -- verbs -------------------------------------------------------------------------------

    def reschedule(self, user, revised_promise_date, note):
        """Move the promised date. Returns ``False`` on anything already closed.

        The FIRST reschedule backfills ``original_promise_date`` from whatever was promised before
        it, so the slip is still measurable after the new date overwrites the old one. Subsequent
        reschedules leave the original alone — the point of the field is the FIRST commitment.
        """
        if self.status not in self.OPEN_STATUSES:
            return False
        if self.original_promise_date is None:
            self.original_promise_date = self.revised_promise_date
        self.revised_promise_date = revised_promise_date
        self.status = "rescheduled"
        # Plain increment, not F(): the caller holds a select_for_update() row lock, and an F()
        # expression would leave the in-memory instance stale for the audit log written next.
        self.reschedule_count = (self.reschedule_count or 0) + 1
        self.reason_note = (note or "")[:255]
        self.save(update_fields=["original_promise_date", "revised_promise_date", "status",
                                 "reschedule_count", "reason_note", "updated_at"])
        return True

    def fulfil(self, user, note=""):
        """Close out: the outstanding quantity finally arrived. A no-op once closed, so a
        double-submit cannot re-stamp ``closed_at`` and rewrite the closure trail."""
        if self.status not in self.OPEN_STATUSES:
            return False
        self.status = "fulfilled"
        self.closed_at = timezone.now()
        self.closure_note = (note or "")[:255]
        self.save(update_fields=["status", "closed_at", "closure_note", "updated_at"])
        return True

    def cancel(self, user, note=""):
        """Close out: the shortfall will never be delivered (order shrunk, sourced elsewhere)."""
        if self.status not in self.OPEN_STATUSES:
            return False
        self.status = "cancelled"
        self.closed_at = timezone.now()
        self.closure_note = (note or "")[:255]
        self.save(update_fields=["status", "closed_at", "closure_note", "updated_at"])
        return True

    def raise_alert(self, user):
        """Escalate into the 6.1 Task & Alert Center. IDEMPOTENT — returns the EXISTING open alert
        rather than raising a second one, so a double-click (or a future nightly sweep) cannot fill
        the inbox with duplicates of one shortfall.

        WARNING: ``link_url`` MUST come from ``reverse()``. ``ProcurementAlert.clean()`` rejects
        anything that is not a single-slash internal path (an absolute or scheme-relative value
        would turn the alert card into an open redirect), and a hardcoded string silently breaks the
        day the route moves.
        """
        from apps.procurement.models import ProcurementAlert  # deferred: same package, sibling module

        if self.alert_id and self.alert.status in ProcurementAlert.OPEN_STATUSES:
            return self.alert

        bucket = self.risk_bucket
        promise = self.effective_promise_date
        due_at = None
        if promise is not None:
            # End-of-day, so "due today" is not already overdue the moment it is raised.
            moment = datetime.combine(promise, time.max)
            due_at = timezone.make_aware(moment) if timezone.is_naive(moment) else moment

        line = self.po_line
        message = (f"{self.quantity_backordered} outstanding on "
                   f"{line.item_description[:80]} (order {line.purchase_order.number}).")
        message += (f" Promised {promise:%Y-%m-%d}." if promise
                    else " No delivery date has been committed yet.")

        alert = ProcurementAlert(
            tenant=self.tenant,
            kind="delivery",
            severity="critical" if bucket == "past_due" else "warning",
            status="open",
            title=f"Backorder {self.number} — {self.get_reason_display()}"[:200],
            message=message,
            due_at=due_at,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            link_url=reverse("procurement:backorder_detail", args=[self.pk]),
        )
        alert.full_clean()
        alert.save()
        self.alert = alert
        self.save(update_fields=["alert", "updated_at"])
        return alert

    # -- derived (never stored, L29) -----------------------------------------------------------

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def effective_promise_date(self):
        """The date currently being chased: the revised promise, else the original."""
        return self.revised_promise_date or self.original_promise_date

    @property
    def days_open(self):
        """Calendar days this shortfall has been live — FROZEN at ``closed_at`` once closed, so a
        finished backorder does not keep ageing on the report."""
        if not self.created_at:
            return 0
        end = self.closed_at or timezone.now()
        return max((end.date() - self.created_at.date()).days, 0)

    @property
    def is_late(self):
        promise = self.effective_promise_date
        return bool(self.is_open and promise and promise < timezone.localdate())

    @property
    def days_late(self):
        promise = self.effective_promise_date
        if not (self.is_open and promise):
            return 0
        return max((timezone.localdate() - promise).days, 0)

    @property
    def risk_bucket(self):
        """One of ``past_due`` / ``at_risk`` / ``no_commitment`` / ``on_track``.

        Deliberately mirrors the ORM ``Q()`` expressions in ``backorder_list`` clause for clause,
        so the badge on a row always agrees with the bucket that row was filtered into. Closed rows
        are ``on_track``: a fulfilled or cancelled backorder carries no risk at all.
        """
        if not self.is_open:
            return "on_track"
        today = timezone.localdate()
        revised, original = self.revised_promise_date, self.original_promise_date
        if revised is not None:
            if revised < today:
                return "past_due"
            if revised <= today + timedelta(days=self.AT_RISK_DAYS):
                return "at_risk"
            return "on_track"
        if original is not None:
            # Original-only: past-due mirrors the ORM's `revised IS NULL AND original < today`
            # branch. A FUTURE original-only date matches no ORM bucket (the at-risk clause keys on
            # the revised date), so it reads as on_track here rather than inventing a fifth name.
            return "past_due" if original < today else "on_track"
        return "no_commitment"

    # -- presentation helpers ------------------------------------------------------------------
    # Colour-NAMED classes only: theme.css ships badge-green/red/amber/info/muted/slate and nothing
    # else (L33 — a semantic badge-success/-danger renders completely unstyled).

    @property
    def status_css(self):
        return {"open": "badge-red", "rescheduled": "badge-amber",
                "fulfilled": "badge-green", "cancelled": "badge-muted",
                }.get(self.status, "badge-slate")

    @property
    def risk_css(self):
        return {"past_due": "badge-red", "at_risk": "badge-amber",
                "no_commitment": "badge-slate", "on_track": "badge-green",
                }.get(self.risk_bucket, "badge-slate")

    @property
    def reason_css(self):
        return {"out_of_stock": "badge-red", "production_delay": "badge-amber",
                "allocation": "badge-amber", "material_shortage": "badge-red",
                "supplier_capacity": "badge-info", "logistics": "badge-info",
                "other": "badge-slate"}.get(self.reason, "badge-slate")

    def __str__(self):
        return f"{self.number or 'BKO'} · {self.po_line}"
