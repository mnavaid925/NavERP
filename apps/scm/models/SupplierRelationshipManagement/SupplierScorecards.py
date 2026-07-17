"""SCM 4.2 Supplier Relationship Management — SupplierScorecard model.

A periodic performance rating for a supplier across four dimensions (delivery, quality, price,
responsiveness). The scores can be entered by hand, but the whole point of living inside the same app
as 4.1 Procurement is that ``recompute_from_signals()`` derives them from REAL transaction history —
on-time goods receipts, reject rates, quote competitiveness — so a scorecard is evidence, not opinion.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class SupplierScorecard(TenantNumbered):
    """A supplier's performance rating for one period [SCR-]. ``overall_score`` is a weighted blend."""

    NUMBER_PREFIX = "SCR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    # Dimension weights (sum to 100). Delivery and quality dominate; price and responsiveness temper.
    WEIGHTS = {"delivery": 35, "quality": 35, "price": 15, "responsiveness": 15}

    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="scm_scorecards")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    # Each score is 0-100. Nullable so an un-scored dimension is visibly absent rather than a false 0.
    delivery_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(ZERO)])
    quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                        validators=[MinValueValidator(ZERO)])
    price_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                      validators=[MinValueValidator(ZERO)])
    responsiveness_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                               validators=[MinValueValidator(ZERO)])
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, editable=False)
    grade = models.CharField(max_length=2, blank=True, editable=False)

    # True once a human has hand-adjusted a score — recompute_from_signals then leaves it alone.
    manual_override = models.BooleanField(default=False)
    signal_summary = models.TextField(blank=True, editable=False,
                                      help_text="How each derived score was calculated")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_scr_tnt_status_idx"),
            models.Index(fields=["tenant", "party"], name="scm_scr_tnt_party_idx"),
        ]

    def recompute_overall(self, save=True):
        """Weighted blend of whichever dimensions are scored (re-weighted over the present ones)."""
        parts = [
            (self.delivery_score, self.WEIGHTS["delivery"]),
            (self.quality_score, self.WEIGHTS["quality"]),
            (self.price_score, self.WEIGHTS["price"]),
            (self.responsiveness_score, self.WEIGHTS["responsiveness"]),
        ]
        present = [(score, weight) for score, weight in parts if score is not None]
        total_weight = sum(weight for _, weight in present)
        if total_weight:
            blended = sum(score * weight for score, weight in present) / total_weight
            self.overall_score = blended.quantize(Decimal("0.01"))
            self.grade = self._grade_for(self.overall_score)
        else:
            self.overall_score = None
            self.grade = ""
        if save:
            self.save(update_fields=["overall_score", "grade", "updated_at"])

    @staticmethod
    def _grade_for(score):
        if score is None:
            return ""
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 40:
            return "D"
        return "F"

    def recompute_from_signals(self, save=True):
        """Derive the four dimension scores from real 4.1 procurement history in this period.

        Skips entirely when ``manual_override`` is set — a human has taken over. Each dimension falls
        back to leaving its existing value untouched when there is no signal to score it from, so a
        recompute never wipes a hand-entered figure with a phantom zero.

        Imported here (not at module top) to avoid a models-package import cycle: the procurement
        models import the same _base, and both are pulled together by the package __init__.
        """
        if self.manual_override:
            return
        from apps.scm.models import GoodsReceiptNote, RFQQuote

        notes = []
        # --- delivery: share of this supplier's receipts booked on/before the PO expected date ----
        receipts = list(
            GoodsReceiptNote.objects
            .filter(tenant=self.tenant, purchase_order__vendor=self.party, status="received",
                    receipt_date__range=(self.period_start, self.period_end))
            .select_related("purchase_order")
        )
        if receipts:
            on_time = sum(
                1 for r in receipts
                if r.purchase_order.expected_date and r.receipt_date <= r.purchase_order.expected_date
            )
            datable = [r for r in receipts if r.purchase_order.expected_date]
            if datable:
                self.delivery_score = (Decimal(on_time) * 100 / len(datable)).quantize(Decimal("0.01"))
                notes.append(f"Delivery: {on_time}/{len(datable)} receipts on time.")

        # --- quality: 100 minus the reject rate across those receipts' lines --------------------
        if receipts:
            received = ZERO
            rejected = ZERO
            for r in receipts:
                for line in r.lines.all():
                    received += line.quantity_received or ZERO
                    rejected += line.quantity_rejected or ZERO
            total = received + rejected
            if total > ZERO:
                self.quality_score = (Decimal(100) - rejected * 100 / total).quantize(Decimal("0.01"))
                notes.append(f"Quality: {rejected} rejected of {total} received.")

        # --- price: how close this supplier's quotes were to the winning price on shared RFQs -----
        quotes = list(
            RFQQuote.objects
            .filter(tenant=self.tenant, party=self.party,
                    received_date__range=(self.period_start, self.period_end))
            .select_related("rfq")
        )
        if quotes:
            ratios = []
            for q in quotes:
                best = (RFQQuote.objects.filter(rfq=q.rfq).exclude(total__lte=ZERO)
                        .order_by("total").values_list("total", flat=True).first())
                if best and q.total and q.total > ZERO:
                    ratios.append(min(Decimal(1), best / q.total))
            if ratios:
                avg = sum(ratios) / len(ratios)
                self.price_score = (avg * 100).quantize(Decimal("0.01"))
                notes.append(f"Price: avg {round(avg * 100)}% of best quote across {len(ratios)} RFQ(s).")

        # --- responsiveness: quote turnaround vs the RFQ issue date -------------------------------
        if quotes:
            turnarounds = [
                (q.received_date - q.rfq.issue_date).days
                for q in quotes if q.received_date and q.rfq and q.rfq.issue_date
            ]
            if turnarounds:
                avg_days = sum(turnarounds) / len(turnarounds)
                # 0 days -> 100; degrade ~7 points/day, floored at 0.
                score = max(Decimal(0), Decimal(100) - Decimal(str(avg_days)) * 7)
                self.responsiveness_score = score.quantize(Decimal("0.01"))
                notes.append(f"Responsiveness: avg {round(avg_days, 1)}d quote turnaround.")

        self.signal_summary = " ".join(notes) if notes else "No procurement signals in this period."
        self.recompute_overall(save=False)
        if save:
            self.save()

    def __str__(self):
        return f"{self.number or 'SCR'} · {self.party_id and self.party.name}"
