"""Inventory 5.18 Accounting & Financial Integration — JournalSyncLog + the posting services.

The register of what the automation actually posted into Module 2's ledger, plus the two
service functions that do the posting. **Ownership ruling (L29/L36):** the ledger tables
stay ``accounting``'s — the services create rows in them exactly the way accounting's own
``_post_journal_entry`` helper does (balanced legs, an open fiscal period, status
"posted"), and never touch any other accounting document. Every run is one atomic block,
admin-gated at the view layer (money moves), and audited.

Two event kinds:

* ``adjustment`` — ONE posted ``scm.StockAdjustment`` per log row. Its signed value
  impact decides the direction: up → DR inventory / CR offset (found stock),
  down → DR offset / CR inventory (write-off). Idempotent by construction: a second
  run for the same adjustment is refused because its log row already exists.
* ``cogs_batch`` — ALL customer-outbound ``issue`` moves in a date window, valued at
  the unit cost each move was stamped with when it left stock (the spine writes
  ``unit_cost=item.average_cost`` at issue time, so the batch is historical fact, not
  a re-valuation). DR COGS offset / CR inventory as ONE balanced entry. Overlapping
  windows are refused so no move is ever expensed twice.
"""
from django.conf import settings
from django.db.models import Count, F

from apps.core.utils import write_audit_log
from apps.inventory.models._base import *  # noqa: F401,F403

from decimal import ROUND_HALF_UP


def _open_fiscal_period(tenant):
    """The newest open accounting period, or None. Mirrors accounting's own selector."""
    from apps.accounting.models import FiscalPeriod

    return (FiscalPeriod.objects.filter(tenant=tenant, status="open")
            .order_by("-start_date").first())


def _post_balanced_entry(tenant, user, *, description, reference, date, legs):
    """Create one POSTED, balanced ``accounting.JournalEntry`` from [(gl, debit, credit)].

    Returns None when the legs are empty, unbalanced or zero — callers surface that as a
    ValidationError rather than writing a half entry. Same contract as accounting's
    internal helper; kept local because peer apps don't import each other's internals.
    """
    from apps.accounting.models import JournalEntry, JournalLine

    legs = [l for l in legs if (l[1] or ZERO) or (l[2] or ZERO)]
    if not legs:
        return None
    debit = sum((l[1] or ZERO for l in legs), ZERO)
    credit = sum((l[2] or ZERO for l in legs), ZERO)
    if debit != credit or debit <= ZERO:
        return None
    je = JournalEntry.objects.create(
        tenant=tenant, entry_type="manual", status="posted",
        fiscal_period=_open_fiscal_period(tenant),
        entry_date=date, description=description[:255], reference=reference[:100],
        created_by=user, approved_by=user, posted_at=timezone.now(),
    )
    for gl, d, c in legs:
        JournalLine.objects.create(entry=je, gl_account=gl, debit=d or ZERO, credit=c or ZERO,
                                   description=description[:255])
    return je


class JournalSyncLog(TenantNumbered):
    """One automated GL posting [JSY-]: what moved, which JE it became."""

    NUMBER_PREFIX = "JSY"

    SOURCE_CHOICES = [
        ("adjustment", "Stock Adjustment"),
        ("cogs_batch", "COGS Batch"),
    ]

    source_kind = models.CharField(max_length=12, choices=SOURCE_CHOICES)
    # Typed source FKs — never a GenericForeignKey (cold-chain lesson): an adjustment row
    # points at its StockAdjustment; a cogs_batch row carries its window instead.
    stock_adjustment = models.ForeignKey(
        "scm.StockAdjustment", on_delete=models.PROTECT, null=True, blank=True,
        related_name="journal_sync_logs",
        help_text="Set on adjustment postings")
    date_from = models.DateField(null=True, blank=True, help_text="COGS batch window start")
    date_to = models.DateField(null=True, blank=True, help_text="COGS batch window end")
    moves_count = models.PositiveIntegerField(default=0)
    total_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_sync_logs", editable=False)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False)
    posted_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-posted_at", "-id"]
        indexes = [models.Index(fields=["tenant", "source_kind"], name="inv_jsy_tnt_kind_idx")]

    @property
    def source_label(self):
        if self.source_kind == "adjustment":
            return self.stock_adjustment.number if self.stock_adjustment_id else "—"
        return f"{self.date_from:%Y-%m-%d} → {self.date_to:%Y-%m-%d}"

    def __str__(self):
        return f"{self.number or 'JSY'} · {self.get_source_kind_display()} {self.source_label}"


# ----------------------------------------------------------------- the automation services

def post_adjustment_to_gl(tenant, user, adjustment, *, rule=None):
    """Post ONE posted StockAdjustment's value impact to the GL; return (log, journal_entry).

    Refuses (ValidationError): a non-posted adjustment, a missing/inactive rule, no open
    fiscal period, a zero value impact, or an adjustment that already has a log row.
    """
    from apps.scm.models import StockAdjustment

    from .GLPostRules import GLPostRule

    if rule is None:
        rule = GLPostRule.objects.filter(tenant=tenant, event_type="adjustment", is_active=True).first()
    if rule is None or not rule.is_active:
        raise ValidationError("No active GL posting rule for inventory adjustments — add one first.")
    if adjustment.status != "posted":
        raise ValidationError("Only a POSTED adjustment can be synced to the GL.")

    value = adjustment.value_impact()
    if value == ZERO:
        raise ValidationError(f"{adjustment.number} has a net-zero value impact — nothing to post.")

    period = _open_fiscal_period(tenant)
    if period is None:
        raise ValidationError("No open fiscal period — open one in Accounting before posting.")

    if value > ZERO:  # found stock: asset up, gain credited
        legs = [(rule.inventory_account, value, ZERO), (rule.offset_account, ZERO, value)]
    else:  # write-off: expense debited, asset down
        value = -value
        legs = [(rule.offset_account, value, ZERO), (rule.inventory_account, ZERO, value)]

    with transaction.atomic():
        # Lock the SOURCE row and re-check the log INSIDE the transaction so two concurrent
        # POSTs cannot both pass a pre-check and each write a JSY row + JE (the same
        # double-draft shape ap_sync_run guards against).
        locked = type(adjustment).objects.select_for_update().get(pk=adjustment.pk)
        if JournalSyncLog.objects.filter(tenant=tenant, stock_adjustment=locked).exists():
            raise ValidationError(f"{locked.number} has already been posted to the GL.")
        je = _post_balanced_entry(
            tenant, user,
            description=f"Inventory adjustment {locked.number}",
            reference=locked.number or "", date=locked.adjustment_date, legs=legs)
        if je is None:  # pragma: no cover — value>0 guarantees balance
            raise ValidationError("Posting refused: the entry did not balance.")
        log = JournalSyncLog.objects.create(
            tenant=tenant, source_kind="adjustment", stock_adjustment=locked,
            moves_count=locked.lines.count(), total_value=value,
            journal_entry=je, posted_by=user,
            notes=f"{locked.get_reason_display()} · {rule.name}")
        write_audit_log(user, log, "create",
                        {"action": "post_adjustment", "je": je.number, "value": str(value)})
    return log, je


def post_cogs_batch(tenant, user, date_from, date_to, *, rule=None):
    """Expense every customer-issue move between the dates as ONE COGS journal entry.

    Value comes off the ledger itself (|quantity| × each move's stamped unit_cost), grouped
    per item so the entry stays readable. Refuses: missing/inactive rule, no open fiscal
    period, an inverted/empty window, a window overlapping a previous batch, or a batch
    that nets to zero.
    """
    from apps.scm.models import StockMove

    from .GLPostRules import GLPostRule

    if date_from is None or date_to is None or date_from > date_to:
        raise ValidationError("Pick a valid date range (from ≤ to).")

    with transaction.atomic():
        if rule is None:
            # The locked rule row is the per-tenant serialization point: the overlap
            # check below only holds because every batch for this tenant takes the
            # same lock first (MariaDB cannot express an interval-exclusion constraint).
            rule = (GLPostRule.objects.select_for_update()
                    .filter(tenant=tenant, event_type="cogs", is_active=True).first())
        if rule is None or not rule.is_active:
            raise ValidationError("No active GL posting rule for COGS — add one first.")

        overlap = JournalSyncLog.objects.filter(
            tenant=tenant, source_kind="cogs_batch",
            date_from__lte=date_to, date_to__gte=date_from)
        if overlap.exists():
            prior = overlap.order_by("-date_to").first()
            raise ValidationError(
                f"Window overlaps the earlier batch {prior.number} "
                f"({prior.date_from:%Y-%m-%d} → {prior.date_to:%Y-%m-%d}) — moves would be expensed twice.")

        period = _open_fiscal_period(tenant)
        if period is None:
            raise ValidationError("No open fiscal period — open one in Accounting before posting.")

        groups = list(StockMove.objects
                      .filter(tenant=tenant, move_type="issue",
                              moved_at__date__gte=date_from, moved_at__date__lte=date_to)
                      .values("item_id")
                      .annotate(n=Count("id"), qty=Sum("quantity"),
                                value=Sum(F("quantity") * F("unit_cost"),
                                          output_field=models.DecimalField())))
        # Outbound issues carry NEGATIVE quantities; the expense is their magnitude.
        # Quantize to the ledger's cents BEFORE building legs so log.total_value equals
        # the posted entry exactly (unit_cost carries 4 dp; JournalLine carries 2).
        legs, count = [], 0
        for g in groups:
            magnitude = -(g["value"] or ZERO)
            magnitude = magnitude.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if magnitude == ZERO:
                continue
            legs.append((rule.offset_account, magnitude, ZERO))
            legs.append((rule.inventory_account, ZERO, magnitude))
            count += g["n"]
        if not legs:
            raise ValidationError(f"No customer issue moves found between {date_from:%Y-%m-%d} and {date_to:%Y-%m-%d}.")
        total = sum((l[1] for l in legs if l[1]), ZERO)

        je = _post_balanced_entry(
            tenant, user,
            description=f"COGS {date_from:%Y-%m-%d} → {date_to:%Y-%m-%d}",
            reference=f"ISSUES {date_from:%Y%m%d}-{date_to:%Y%m%d}", date=date_to, legs=legs)
        if je is None:  # pragma: no cover — magnitudes above guarantee balance
            raise ValidationError("Posting refused: the entry did not balance.")
        log = JournalSyncLog.objects.create(
            tenant=tenant, source_kind="cogs_batch",
            date_from=date_from, date_to=date_to,
            moves_count=int(count), total_value=total,
            journal_entry=je, posted_by=user,
            notes=f"{len(groups)} SKUs · {rule.name}")
        write_audit_log(user, log, "create",
                        {"action": "post_cogs", "je": je.number, "value": str(total)})
    return log, je
