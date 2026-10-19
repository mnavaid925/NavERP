"""Sales 8.12 — Sales Analytics & Intelligence: Stage Velocity Analysis model.

OWNERSHIP RULING (L36/L37): 8.12 declares NO pipeline, stage, benchmark or
velocity master of its own. It EXTENDS the Sales 8.2 spine
(``sales.Pipeline`` / ``sales.PipelineStage``) by FK and adds only the
*analysis* record — the period measurement of how long opportunities actually
sat in one pipeline stage.

MEASUREMENT GAP (``GAP-sales-8.12-01``): NavERP has **no stage-transition
history table**. The only transition evidence the spine keeps is
``crm.Opportunity.stage_changed_at`` (the LAST transition) and
``sales.OpportunityPipelinePlacement.stage_entered_at`` (the entry timestamp of
the CURRENT stage). Historical per-stage durations are therefore **not
derivable** from the spine. Consequently:

* ``median_days_in_stage`` / ``p90_days_in_stage`` / ``max_days_in_stage`` are
  the **persisted, recorded measurement** for the period — the record's own
  data, hence editable.
* ``is_bottleneck`` and ``bottleneck_rank`` are a manager's **judgement** at
  entry time (a stage's ``target_days`` is nullable and a rank is relative to
  its sibling rows). The console re-derives a *live* rank at render time and
  shows it beside the stored snapshot; the stored rank is the judgement that
  was captured when the record was written.

There is deliberately **NO** ``avg_days_in_stage`` field. A stage duration
distribution is right-skewed, and a plain average invites a reader to treat the
mean as typical. The record reports the **median** and the **p90** instead.
"""
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

VELOCITY_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("reviewed", "Reviewed"),
    ("approved", "Approved"),
]


class StageVelocityAnalysis(TenantNumbered):
    """One period's recorded stage-velocity measurement for a pipeline stage.

    A stage is measured over a closed period (``period_start`` …
    ``period_end``) so the median / p90 / max durations describe one window of
    time rather than a running figure that changes under the reader's feet.
    """

    NUMBER_PREFIX = "VCA"

    pipeline = models.ForeignKey(
        "sales.Pipeline",
        on_delete=models.PROTECT,
        related_name="sales_velocity_analyses",
    )
    pipeline_stage = models.ForeignKey(
        "sales.PipelineStage",
        on_delete=models.PROTECT,
        related_name="sales_velocity_analyses",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    opportunity_count = models.PositiveIntegerField(default=0)
    median_days_in_stage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    p90_days_in_stage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    max_days_in_stage = models.PositiveIntegerField(default=0)
    sales_cycle_days = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    velocity_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    is_bottleneck = models.BooleanField(default=False)
    bottleneck_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    recommendation = models.TextField(blank=True)
    benchmark_days = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    benchmark_source = models.CharField(max_length=120, blank=True)
    benchmark_as_of = models.DateField(null=True, blank=True)
    segment = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=12,
        choices=VELOCITY_STATUS_CHOICES,
        default="draft",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-period_start", "pipeline", "pipeline_stage"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_vca_tenant_number_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "pipeline_stage", "period_start"],
                name="sales_vca_stage_period_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_vca_tenant_status_idx"),
            models.Index(fields=["tenant", "is_bottleneck"], name="sales_vca_tenant_bottleneck_idx"),
            models.Index(fields=["tenant", "pipeline"], name="sales_vca_tenant_pipeline_idx"),
        ]

    def __str__(self):
        try:
            stage = self.pipeline_stage if self.pipeline_stage_id else None
        except ObjectDoesNotExist:
            stage = None
        return f"{self.number or 'VCA'} · {stage or '—'}"

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

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        for field_name, message in (
            ("pipeline", "Choose a pipeline from this workspace."),
            ("pipeline_stage", "Choose a stage from this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})

        if self.pipeline_stage_id and self.pipeline_id:
            try:
                stage = self.pipeline_stage
            except ObjectDoesNotExist:
                stage = None
            if stage is not None and stage.pipeline_id != self.pipeline_id:
                raise ValidationError(
                    {"pipeline_stage": "Choose a stage from the selected pipeline."}
                )

        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError(
                {"period_end": "The period end date must not be before the period start date."}
            )

    @property
    def status_badge_class(self):
        mapping = {
            "draft": "badge-muted",
            "reviewed": "badge-info",
            "approved": "badge-green",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def bottleneck_badge_class(self):
        return "badge-red" if self.is_bottleneck else "badge-muted"

    @property
    def days_over_target(self):
        """Median days in stage minus the stage's target — ``None`` when unknown.

        A stage without a ``target_days`` (the column is nullable) has no
        target to be over, and an unsaved record has no stage yet.
        """
        if not self.pipeline_stage_id or self.median_days_in_stage is None:
            return None
        try:
            stage = self.pipeline_stage
        except ObjectDoesNotExist:
            return None
        if stage is None or stage.target_days is None:
            return None
        return self.median_days_in_stage - stage.target_days

    @property
    def is_over_target(self):
        days = self.days_over_target
        return days is not None and days > 0
