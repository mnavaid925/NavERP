"""8.4 Sales Forecasting — the what-if scenario, and the isolation rule that defines it.

A ``ForecastScenario`` is a set of **percentage deltas** applied to a forecast call. It is
never an absolute restatement of the numbers, because an absolute would go stale the moment
the real pipeline moved; the deltas stay honest on their own and the projection is recomputed
from the live submission every time it is read.

Five rulings are structural here and cannot be undone by a later edit:

* **A scenario never mutates a ``ForecastSubmission``** — not in code, not in SQL. Applying
  one writes exactly four fields on this row: the two ``projected_*`` snapshots and the two
  booleans. The real forecast is an *input* to a scenario, never its output. Contract 0.6
  makes the smoke sweep assert this, and the ``select`` action is deliberately a **state
  flag**, not a write to any submission amount or status.
* **The deltas are the stored truth; the projection is a snapshot.** ``projected_commit_amount``
  and ``projected_total_amount`` are ``editable=False`` server-written values *labelled* as
  snapshots, so the detail page can show "what the scenario computed" beside the deltas that
  produced it without a stored figure ever standing in for a live one.
* **Only the baseline may be selected.** The ``sales_fsc_baseline_selected`` CheckConstraint
  makes ``is_baseline=True`` imply ``is_selected=True``, so "selected" *is* "this is the
  current plan" and there is exactly one selected scenario per tenant — the attainment board
  never has to break a tie (contract 3.4 / 13.4). ``is_selected`` is workflow-owned, absent
  from the form, and only the ``select`` action may move it.
* **``period`` is PROTECT** and ``owner`` is SET_NULL: a scenario without its author is
  still a readable what-if, but a period cannot be deleted out from under a live plan.
* ``sales_forecast_scenarios`` is the ``User`` reverse name (R3 — ``accounts.User`` is already
  crowded), and the two booleans are ordinary columns, never a second category table.

``effective_*`` are **properties** and are absent from ``_meta``: they read the period's
baseline submission, apply the delta and return ``None`` when there is no submission to
project at all. Decimal-safe throughout, and never a division, so no ``Infinity``/``NaN``
can reach a template.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.sales.models._base import TenantNumbered
from apps.sales.models.SalesForecasting.ForecastSubmissions import ForecastSubmission

#: The three percentages a scenario moves, each mapping to the ``ForecastSubmission`` amount
#: column it scales. Reused from the sibling entity rather than re-declared: the scenario and
#: the call it projects must never disagree about what "commit" means.
DELTA_FIELDS = (
    ("pipeline", "pipeline_delta_pct", "pipeline_amount"),
    ("best_case", "best_case_delta_pct", "best_case_amount"),
    ("commit", "commit_delta_pct", "commit_amount"),
)

#: A scenario is a multiplier band, not an unbounded multiplier. ``-100%`` wipes a line to
#: zero (a total loss of that bucket); ``+1000%`` is a tenfold absurdity nobody has to
#: defend at 5000%. Mirrored by the field validators and the form's ``clean()``.
DELTA_PCT_MIN = Decimal("-100.00")
DELTA_PCT_MAX = Decimal("1000.00")



class ForecastScenario(TenantNumbered):
    """One what-if: three deltas over a period, and the snapshot they produced."""

    NUMBER_PREFIX = "FSC"

    SCENARIO_TYPE_CHOICES = [
        ("upside", "Upside"),
        ("base", "Base"),
        ("downside", "Downside"),
        ("custom", "Custom"),
    ]

    period = models.ForeignKey(
        "sales.ForecastPeriod",
        on_delete=models.PROTECT,
        related_name="scenarios",
    )
    # A scenario is often the manager's own what-if, so owner is optional. The reverse name is
    # explicit (R3): accounts.User already carries crm_opportunities / crm_sales_quotas /
    # crm_territories / crm_tasks and the sibling sales_forecast_submissions.
    owner = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_scenarios",
    )
    name = models.CharField(max_length=160)
    scenario_type = models.CharField(
        max_length=12,
        choices=SCENARIO_TYPE_CHOICES,
        default="custom",
    )
    # Weight in the blended number, mirroring PipelineStage.probability's validated band
    # (the sales_pstage_probability_valid precedent).
    probability_pct = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    # The "current plan" row, and the only one the CheckConstraint lets be selected.
    is_baseline = models.BooleanField(default=False)
    is_selected = models.BooleanField(default=False)
    # DELTAS, not absolutes -- so the scenario stays honest as the pipeline moves.
    pipeline_delta_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(DELTA_PCT_MIN), MaxValueValidator(DELTA_PCT_MAX)],
    )
    best_case_delta_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(DELTA_PCT_MIN), MaxValueValidator(DELTA_PCT_MAX)],
    )
    commit_delta_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(DELTA_PCT_MIN), MaxValueValidator(DELTA_PCT_MAX)],
    )
    # Snapshot of WHAT THE SCENARIO COMPUTED, editable=False so it is structurally excluded
    # from every form and can only be written by the apply action. Decimal, never float.
    projected_commit_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0"))], editable=False,
    )
    projected_total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0"))], editable=False,
    )
    assumption_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_baseline", "name", "-created_at"]
        verbose_name_plural = "forecast scenarios"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_fsc_tenant_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "period", "name"],
                name="sales_fsc_tnt_period_name_uniq",
            ),
            models.CheckConstraint(
                condition=Q(probability_pct__gte=0) & Q(probability_pct__lte=100),
                name="sales_fsc_probability_valid",
            ),
            # "Selected" IS "this is the current plan", and the current plan is the baseline.
            # This is what makes the selected set single-valued, so a select POST can never
            # leave two rows claiming to be the plan.
            models.CheckConstraint(
                condition=Q(is_baseline=False) | Q(is_baseline=True, is_selected=True),
                name="sales_fsc_baseline_selected",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "period"], name="sales_fsc_tnt_period_idx"),
            models.Index(fields=["tenant", "is_selected"], name="sales_fsc_tnt_selected_idx"),
        ]

    # ------------------------------------------------------------------ isolation
    def baseline_submission(self):
        """The submission this scenario projects: the period's settled call, else the first.

        "Baseline" here is the *read* side of the isolation rule and is deliberately the
        simplest defensible answer: the period's own submitted/approved/locked call when there
        is one, otherwise its first call in a stable order. It is a **read** -- nothing here
        writes to the returned row, which is the whole point of the entity.
        """
        if not self.pk or not self.period_id:
            return None
        queryset = ForecastSubmission.objects.filter(
            tenant_id=self.tenant_id, period_id=self.period_id,
        ).order_by("-created_at", "-id")
        settled = queryset.filter(status__in=["approved", "locked", "submitted"]).first()
        return settled if settled is not None else queryset.first()

    def _project(self, delta_field, amount_field):
        """``amount * (1 + delta/100)``, or ``None`` when there is no call to project.

        Decimal-only. A scenario with no baseline submission is not zero, it is *unknown*, so
        it returns ``None`` and the template renders an em dash rather than a fake 0.00.
        """
        submission = self.baseline_submission()
        if submission is None:
            return None
        base = Decimal(getattr(submission, amount_field, 0) or 0)
        delta = Decimal(getattr(self, delta_field, 0) or 0)
        return (base * (Decimal("1") + delta / Decimal("100"))).quantize(Decimal("0.01"))

    @property
    def effective_pipeline_amount(self):
        """The pipeline line after this scenario's delta, or ``None``."""
        return self._project("pipeline_delta_pct", "pipeline_amount")

    @property
    def effective_best_case_amount(self):
        """The best-case line after this scenario's delta, or ``None``."""
        return self._project("best_case_delta_pct", "best_case_amount")

    @property
    def effective_commit_amount(self):
        """The commit line after this scenario's delta, or ``None``."""
        return self._project("commit_delta_pct", "commit_amount")

    def snapshot_projection(self):
        """Write the two ``projected_*`` snapshots from the current deltas. Returns ``self``.

        This is the **only** method in the entity that writes an amount, and it writes only to
        this row. It never touches a ``ForecastSubmission`` -- the deltas are read from the
        baseline call and the projection lands here. That asymmetry IS the isolation rule
        expressed in code, and it is what the smoke sweep asserts byte-for-byte.
        """
        commit = self.effective_commit_amount
        pipeline = self.effective_pipeline_amount
        best_case = self.effective_best_case_amount
        self.projected_commit_amount = max(Decimal("0"), commit or Decimal("0"))
        total = (pipeline or Decimal("0")) + (best_case or Decimal("0")) + (commit or Decimal("0"))
        self.projected_total_amount = max(Decimal("0"), total.quantize(Decimal("0.01")))
        return self

    def sync_selected_from_baseline(self):
        """Keep ``is_selected`` in step with ``is_baseline`` and return ``self``.

        The CheckConstraint makes ``is_baseline`` imply ``is_selected`` (contract 3.4), and the
        reverse is handled by the ``select`` action clearing the previous baseline first. Both
        halves live in code so neither a form POST nor a crafted ``QuerySet.update()`` from a
        sibling view can leave a baseline that is not the selected plan.
        """
        if self.is_baseline:
            self.is_selected = True
        return self

    def _relation_belongs_to_tenant(self, field_name):
        """The exact helper from ``OpportunityTeams.py:56-65`` -- one FK, one check."""
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
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
            ("period", "The forecast period must belong to this workspace."),
            ("owner", "The owner must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})
        # A locked period freezes the real forecast, and a what-if over a frozen forecast is a
        # claim about a number that can no longer move.
        if self.period_id and self.period.is_locked:
            raise ValidationError({
                "period": "The period is locked, so its scenarios are read-only.",
            })
        if self.probability_pct is not None and not 0 <= self.probability_pct <= 100:
            raise ValidationError({
                "probability_pct": "The blend weight must be between 0 and 100.",
            })
        for _, delta_field, _ in DELTA_FIELDS:
            value = getattr(self, delta_field, None)
            if value is not None and not DELTA_PCT_MIN <= Decimal(value) <= DELTA_PCT_MAX:
                raise ValidationError({
                    delta_field: (
                        f"A delta must be between {DELTA_PCT_MIN} and {DELTA_PCT_MAX} percent."
                    ),
                })
        # Surface the CheckConstraint as a form error rather than letting the DB raise an
        # IntegrityError at save time: baseline implies selected (3.4 / 13.4).
        if self.is_baseline and not self.is_selected:
            raise ValidationError({
                "is_baseline": "The baseline scenario is the current plan, so it is selected.",
            })

    def __str__(self):
        return f"{self.number} · {self.name} · {self.get_scenario_type_display()}"
