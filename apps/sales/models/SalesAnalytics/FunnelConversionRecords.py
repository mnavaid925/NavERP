"""Sales 8.12 — Sales Analytics & Intelligence: Funnel Conversion Record model.

OWNERSHIP RULING (L36/L37): 8.12 declares NO funnel, funnel-stage or benchmark
master of its own. It EXTENDS the Sales 8.2 spine (``sales.Pipeline`` /
``sales.PipelineStage``) and CRM 1.2's ``crm.Territory`` by FK, and adds only the
*conversion record* — the recorded measurement of how many records entered a
funnel step and how many converted out of it.

The funnel is NOT re-computed here. ``crm.analytics.compute_report`` owns the
live funnel aggregation for a saved ``crm.AnalyticsReport``; this table is the
period-measured, human-verified counterpart of it: the counts a rep or a
manager entered for one window of time, for one scope (lead-to-opportunity,
opportunity-to-close, stage-to-stage, or overall).

DERIVED FIELDS: ``conversion_rate_pct`` and ``dropoff_count`` are ratios /
differences of two fields on the same row, so they are computed in ``save()``
and marked ``editable=False`` — Django's ModelForm excludes them automatically
and the form never lets a reader type a rate that contradicts the counts.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from apps.sales.models._base import TenantNumbered

FUNNEL_SCOPE_CHOICES = [
    ("lead_to_opportunity", "Lead to Opportunity"),
    ("opportunity_to_close", "Opportunity to Close"),
    ("stage_to_stage", "Stage to Stage"),
    ("overall", "Overall"),
]


class FunnelConversionRecord(TenantNumbered):
    """One period's measured conversion through a funnel step.

    The counts (``entered_count`` / ``converted_count`` / ``skipped_count``) are
    the record's own measured data and stay editable; the rate and the dropoff
    are derived from them on every save.
    """

    NUMBER_PREFIX = "FNL"

    label = models.CharField(max_length=160)
    funnel_scope = models.CharField(
        max_length=24,
        choices=FUNNEL_SCOPE_CHOICES,
        default="lead_to_opportunity",
    )
    from_stage = models.ForeignKey(
        "sales.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_funnel_from_records",
    )
    to_stage = models.ForeignKey(
        "sales.PipelineStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_funnel_to_records",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_funnel_records",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_funnel_records",
    )
    source_channel = models.CharField(max_length=60, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    entered_count = models.PositiveIntegerField(default=0)
    converted_count = models.PositiveIntegerField(default=0)
    conversion_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        editable=False,
        default=0,
    )
    dropoff_count = models.PositiveIntegerField(editable=False, default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    avg_cycle_days = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    benchmark_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    benchmark_source = models.CharField(max_length=120, blank=True)
    benchmark_as_of = models.DateField(null=True, blank=True)
    segment = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-period_start", "label"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_fnl_tenant_number_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "label", "period_start"],
                name="sales_fnl_label_period_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "funnel_scope"], name="sales_fnl_tenant_scope_idx"),
            models.Index(fields=["tenant", "period_end"], name="sales_fnl_tenant_period_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'FNL'} · {self.label or '—'}"

    def _relation_belongs_to_tenant(self, field_name):
        """True when the FK at ``field_name`` points at a row of this tenant.

        Copied from ``apps/sales/models/SalesAnalytics/WinLossDebriefs.py`` —
        a DB existence probe, so a cross-tenant pick is rejected without
        dereferencing the (foreign) object.
        """
        relation_id = getattr(self, f"{field_name}_id", None)
        if not self.tenant_id or not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def save(self, *args, **kwargs):
        """Recompute the two derived fields, then persist.

        ``conversion_rate_pct`` is the converted share of the entered count and
        ``dropoff_count`` is what fell out of the funnel. Both are derived
        (never typed), so they are recomputed on every save rather than
        trusted from the caller.
        """
        entered = int(self.entered_count or 0)
        converted = int(self.converted_count or 0)
        self.conversion_rate_pct = (
            min(
                (Decimal(converted) / Decimal(entered) * Decimal(100)).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                ),
                Decimal("999.99"),
            )
            if entered > 0
            else Decimal("0.00")
        )
        self.dropoff_count = max(0, entered - converted)
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        entered = int(self.entered_count or 0)
        converted = int(self.converted_count or 0)
        if converted > entered:
            raise ValidationError(
                {"converted_count": "Converted count cannot exceed the entered count."}
            )

        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError(
                {"period_end": "The period end date must not be before the period start date."}
            )

        if not self.tenant_id:
            return

        for field_name, message in (
            ("from_stage", "Choose a stage from this workspace."),
            ("to_stage", "Choose a stage from this workspace."),
            ("territory", "Choose a territory from this workspace."),
            ("owner", "The owner must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})

        if self.funnel_scope == "stage_to_stage" and self.from_stage_id and self.to_stage_id:
            try:
                from_stage = self.from_stage
                to_stage = self.to_stage
            except ObjectDoesNotExist:
                from_stage = None
                to_stage = None
            if (
                from_stage is not None
                and to_stage is not None
                and to_stage.sequence <= from_stage.sequence
            ):
                raise ValidationError(
                    {"to_stage": "The destination stage must follow the source stage."}
                )

    @property
    def scope_badge_class(self):
        mapping = {
            "lead_to_opportunity": "badge-info",
            "opportunity_to_close": "badge-slate",
            "stage_to_stage": "badge-amber",
            "overall": "badge-muted",
        }
        return mapping.get(self.funnel_scope, "badge-slate")

    @property
    def is_below_benchmark(self):
        """True when a benchmark is set and the record falls short of it."""
        if self.benchmark_pct is None or self.conversion_rate_pct is None:
            return False
        return self.conversion_rate_pct < self.benchmark_pct

    @property
    def benchmark_gap_pct(self):
        """Rate minus benchmark — negative when the record beats the benchmark."""
        if self.benchmark_pct is None or self.conversion_rate_pct is None:
            return None
        return self.conversion_rate_pct - self.benchmark_pct
