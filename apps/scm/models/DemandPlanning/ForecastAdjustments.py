"""SCM 4.7 Demand Planning — ForecastAdjustment (collaborative / consensus planning).

The structured way sales, marketing, finance and operations put their number on the table. Each
contributor proposes an override against a forecast (optionally against one period), states WHY via a
reason code plus free-text rationale, and a reviewer accepts or rejects it. Only ACCEPTED adjustments
roll up into ``DemandForecastPeriod.consensus_quantity`` — the accept/reject gate IS the consensus
process, so a proposal never silently moves the plan of record.

The mandatory ``rationale`` is not ceremony: an unexplained override is untraceable six months later
when someone asks why the plan diverged from the statistics, and forecast-value-added (does human
input actually beat the model?) can only be argued from documented assumptions.

``resolved_quantity`` is always stored as a **signed delta** whatever the contributor typed — an
absolute target, a delta or a percentage all reduce to "move the number by this much". It is a
resolved-at-the-time figure: ``DemandForecast.recompute_consensus()`` re-resolves every accepted
adjustment against the number as it stands when its turn comes and writes the result back, so an
"absolute" override still means *end at this figure* after the baseline moves or another
contributor's proposal is accepted ahead of it.
"""
from apps.scm.models._base import *  # noqa: F401,F403


class ForecastAdjustment(TenantNumbered):
    """One contributor's proposed override on a forecast [FA-]."""

    NUMBER_PREFIX = "FA"

    FUNCTION_CHOICES = [
        ("sales", "Sales"),
        ("marketing", "Marketing"),
        ("finance", "Finance"),
        ("supply_chain", "Supply Chain"),
        ("operations", "Operations"),
        ("executive", "Executive"),
        ("customer", "Customer"),
    ]
    TYPE_CHOICES = [
        ("absolute", "Absolute"),
        ("delta", "Delta"),
        ("percent", "Percent"),
    ]
    REASON_CHOICES = [
        ("promotion", "Promotion"),
        ("new_customer", "New Customer"),
        ("lost_customer", "Lost Customer"),
        ("price_change", "Price Change"),
        ("market_shift", "Market Shift"),
        ("competitor_action", "Competitor Action"),
        ("product_launch", "Product Launch"),
        ("discontinuation", "Discontinuation"),
        ("budget_target", "Budget Target"),
        ("known_bias", "Known Bias"),
        ("supply_constraint", "Supply Constraint"),
        ("other", "Other"),
    ]
    CONFIDENCE_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("superseded", "Superseded"),
    ]
    #: Only a proposal may be reviewed — a second accept must not double-count into consensus.
    REVIEWABLE_STATUSES = ("proposed",)

    forecast = models.ForeignKey("scm.DemandForecast", on_delete=models.CASCADE,
                                 related_name="adjustments")
    period = models.ForeignKey("scm.DemandForecastPeriod", on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="adjustments",
                               help_text="Leave blank to adjust the whole horizon (split pro-rata)")
    contributor_function = models.CharField(max_length=14, choices=FUNCTION_CHOICES, default="sales")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, editable=False,
                                     related_name="scm_forecast_adjustments")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_forecast_adjustments")
    adjustment_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="absolute")
    proposed_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0,
                                            help_text="The target (absolute) or the movement (delta)")
    adjustment_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                         help_text="Used by the percent type — may be negative")
    # Always the signed delta the roll-up sums, whatever type was chosen. Derived in save().
    resolved_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0, editable=False)
    reason_code = models.CharField(max_length=20, choices=REASON_CHOICES, default="market_shift")
    rationale = models.TextField(help_text="Required — an unexplained override is untraceable later")
    confidence = models.CharField(max_length=8, choices=CONFIDENCE_CHOICES, default="medium")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="proposed", editable=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False,
                                    related_name="scm_forecast_adjustments_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_note = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_fa_tnt_status_idx"),
            models.Index(fields=["tenant", "forecast"], name="scm_fa_tnt_fcst_idx"),
        ]

    def clean(self):
        # A crafted POST must not hang an adjustment off another forecast's period — the roll-up
        # would then move a plan this record does not belong to.
        if self.period_id and self.forecast_id and self.period.forecast_id != self.forecast_id:
            raise ValidationError({"period": "That period belongs to a different forecast."})

    def base_quantity(self):
        """What the override is measured against: the period's pre-consensus number, or the whole
        horizon's when no period is named."""
        if self.period_id:
            return self.period.pre_adjustment_quantity
        if not self.forecast_id:
            return ZERO
        return sum((row.pre_adjustment_quantity for row in self.forecast.periods.all()), ZERO)

    def delta_against(self, base):
        """Reduce whichever type the contributor used to a single signed delta, measured against
        ``base``.

        The roll-up passes the number as it stands when this adjustment's turn comes, so "absolute
        40" always means *end at 40* — replaying a delta that was resolved days ago would land
        somewhere else entirely once the baseline or an earlier adjustment moved.
        """
        if self.adjustment_type == "delta":
            return self.proposed_quantity or ZERO
        if self.adjustment_type == "percent":
            return Decimal(base or ZERO) * (self.adjustment_pct or ZERO) / Decimal("100")
        return (self.proposed_quantity or ZERO) - Decimal(base or ZERO)

    def resolve_quantity(self):
        """The delta as it stands right now — the preview shown before the roll-up runs."""
        return self.delta_against(self.base_quantity())

    @property
    def is_reviewable(self):
        return self.status in self.REVIEWABLE_STATUSES

    def save(self, *args, **kwargs):
        # q4 clamps as well as quantizes. The roll-up writer (recompute_consensus) already does,
        # and an unclamped sibling writer of the same column could still poison a bulk_update.
        self.resolved_quantity = q4(self.resolve_quantity())
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "resolved_quantity" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["resolved_quantity"]
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or 'FA'} · {self.get_contributor_function_display()}"
