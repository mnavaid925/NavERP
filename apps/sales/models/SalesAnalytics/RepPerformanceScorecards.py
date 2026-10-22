"""Sales 8.12 — Sales Analytics & Intelligence: Rep Performance Scorecard model.

OWNERSHIP RULING (L36/L37): 8.12 declares NO rep table, NO benchmark master, NO
quota/period table and NO currency table of its own. It EXTENDS the spine by FK
(``accounts.User`` for the rep and the manager, ``crm.Territory``,
``sales.ForecastPeriod``, ``sales.QuotaPlan``, ``sales.CoachingScorecard`` and the
GLOBAL ``accounting.Currency``) and adds only the *scorecard* — one manager's
recorded assessment of one rep over one window.

WHAT THIS RECORD IS, AND WHAT IT IS NOT
--------------------------------------
This is the **measurement half** of NavERP bullet 5. It is a **snapshot of what was
recorded for one period**, not a live leaderboard: the counters are the evidence
that existed when the scorecard was written.

* The **activity counters** (``activities_logged``, ``calls_logged``,
  ``emails_logged``, ``meetings_logged``, ``meetings_booked``,
  ``follow_ups_completed``, plus ``activity_minutes`` and
  ``response_time_hours``) are the period's **recorded evidence** and stay
  **editable** — they are what the rep and the manager agreed had happened.
* The console shows the **live** ``sales.ActivityLog``-derived counts **beside**
  the stored snapshot so that any divergence is visible. It **never overwrites**
  the stored snapshot: the snapshot is a point-in-time record, and a live count
  that silently replaced it would erase the evidence the review is based on.
* **Leading indicators** = the activity block (the effort that happens before a
  deal closes). **Lagging indicators** = the outcome block (the wins, the losses,
  the revenue). Both live on the same row so a scorecard reads as one argument,
  not two.

SINGLE CURRENCY, ON PURPOSE
---------------------------
The scorecard is **single-currency**. ``crm.Opportunity.currency`` is
**per-opportunity**, so a rep who closed deals in two currencies would have two
incomparable revenue figures. NavERP holds **no FX rates** (the GL has
``accounting.Currency`` but no rate table), so a cross-currency leaderboard
cannot be computed honestly and is not attempted. This is the documented gap
``GAP-sales-8.12-11``.

DERIVED FIELDS
--------------
``win_rate_pct``, ``average_deal_size``, ``quota_attainment_pct`` and
``goal_gap_value`` are ratios / differences of two fields on the same row, so
they are computed in ``save()`` and marked ``editable=False`` — Django's
ModelForm excludes them automatically and a reader can never type a rate that
contradicts the counts behind it. ``goal_gap_value`` is **negative when the
target is exceeded**; the gap is target − actual.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

SCORECARD_RATING_CHOICES = [
    ("outstanding", "Outstanding"),
    ("strong", "Strong"),
    ("on_track", "On Track"),
    ("needs_improvement", "Needs Improvement"),
    ("underperforming", "Underperforming"),
]

SCORECARD_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("shared", "Shared"),
    ("acknowledged", "Acknowledged"),
    ("approved", "Approved"),
]

#: The largest value each DERIVED column can hold. The derived fields are ``editable=False``,
#: so Django's ModelForm EXCLUDES them from model validation -- a ratio that overflows its
#: column would otherwise never be validated and would be silently clamped by the driver on
#: this project's non-strict MariaDB (``apps/core/utils.py``) or raise a ``DataError`` -> 500
#: on a strict-mode host. ``save()`` clamps to these instead.
_MAX_AVERAGE_DEAL_SIZE = Decimal("999999999999.99")  # DECIMAL(14,2)
_MAX_QUOTA_ATTAINMENT_PCT = Decimal("9999.99")  # DECIMAL(6,2)


class RepPerformanceScorecard(TenantNumbered):
    """One rep's performance scorecard for one period.

    One scorecard per rep per period start (enforced by a unique constraint), so
    a period's assessment is a single row that can be reviewed, shared,
    acknowledged and approved rather than a pile of overlapping drafts.
    """

    NUMBER_PREFIX = "RPS"

    rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_rep_scorecards",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_rep_scorecards",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_managed_rep_scorecards",
    )
    forecast_period = models.ForeignKey(
        "sales.ForecastPeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_rep_scorecards",
    )
    quota_plan = models.ForeignKey(
        "sales.QuotaPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_rep_scorecards",
    )
    coaching_scorecard = models.ForeignKey(
        "sales.CoachingScorecard",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_rep_scorecards",
    )
    period_start = models.DateField()
    period_end = models.DateField()

    # --- LEADING INDICATORS: the period's recorded evidence (editable).
    activities_logged = models.PositiveIntegerField(default=0)
    calls_logged = models.PositiveIntegerField(default=0)
    emails_logged = models.PositiveIntegerField(default=0)
    meetings_logged = models.PositiveIntegerField(default=0)
    meetings_booked = models.PositiveIntegerField(default=0)
    follow_ups_completed = models.PositiveIntegerField(default=0)
    activity_minutes = models.PositiveIntegerField(default=0)
    response_time_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # --- LAGGING INDICATORS: the outcome block.
    opportunities_created = models.PositiveIntegerField(default=0)
    opportunities_won = models.PositiveIntegerField(default=0)
    opportunities_lost = models.PositiveIntegerField(default=0)
    pipeline_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    weighted_pipeline_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    win_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        editable=False,
        default=0,
    )
    revenue_closed = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_rep_scorecards",
    )
    average_deal_size = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
        default=0,
    )
    sales_cycle_days = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    quota_target = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    quota_attainment_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        editable=False,
        default=0,
    )
    goal_gap_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        editable=False,
        default=0,
    )
    overall_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    rating = models.CharField(
        max_length=20,
        choices=SCORECARD_RATING_CHOICES,
        default="on_track",
    )
    strengths = models.TextField(blank=True)
    areas_for_improvement = models.TextField(blank=True)
    coaching_actions = models.TextField(blank=True)

    benchmark_win_rate_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    benchmark_cycle_days = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    benchmark_quota_attainment_pct = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    benchmark_source = models.CharField(max_length=120, blank=True)
    benchmark_as_of = models.DateField(null=True, blank=True)
    segment = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=12,
        choices=SCORECARD_STATUS_CHOICES,
        default="draft",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-period_start", "rep"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_rps_tenant_number_uniq"),
            models.UniqueConstraint(
                fields=["tenant", "rep", "period_start"],
                name="sales_rps_rep_period_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_rps_tenant_status_idx"),
            models.Index(fields=["tenant", "rating"], name="sales_rps_tenant_rating_idx"),
            models.Index(fields=["tenant", "rep"], name="sales_rps_tenant_rep_idx"),
            models.Index(fields=["tenant", "-period_end"], name="sales_rps_ten_pend_idx"),
        ]

    def __str__(self):
        try:
            rep = self.rep if self.rep_id else None
        except ObjectDoesNotExist:
            rep = None
        name = rep.get_full_name() if rep is not None else ""
        return f"{self.number or 'RPS'} · {name or (rep.username if rep is not None else '—')}"

    def _relation_belongs_to_tenant(self, field_name):
        """True when the FK at ``field_name`` points at a row of this tenant.

        Copied from ``apps/sales/models/SalesAnalytics/WinLossDebriefs.py`` —
        a DB existence probe, so a cross-tenant pick is rejected without
        dereferencing the (foreign) object.

        ``currency`` is deliberately NOT checked here: ``accounting.Currency`` is
        a GLOBAL master with no ``tenant`` FK (L29), so there is nothing to
        compare.
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
        """Recompute the four derived fields, then persist.

        ``win_rate_pct`` is the won share of the decided opportunities,
        ``average_deal_size`` is the revenue per win, ``quota_attainment_pct`` is
        the revenue against the target, and ``goal_gap_value`` is the target
        minus the actual — **negative when the target was exceeded**. All four
        are derived, so they are recomputed on every save rather than trusted
        from the caller.
        """
        won = int(self.opportunities_won or 0)
        lost = int(self.opportunities_lost or 0)
        revenue = Decimal(self.revenue_closed or 0)
        quota = Decimal(self.quota_target or 0)
        self.win_rate_pct = (
            (Decimal(won) / Decimal(won + lost) * Decimal(100)).quantize(
                Decimal("0.01"),
                ROUND_HALF_UP,
            )
            if (won + lost)
            else Decimal("0.00")
        )
        self.average_deal_size = (
            min(
                (revenue / Decimal(won)).quantize(Decimal("0.01"), ROUND_HALF_UP),
                _MAX_AVERAGE_DEAL_SIZE,
            )
            if won
            else Decimal("0.00")
        )
        self.quota_attainment_pct = (
            min(
                (revenue / quota * Decimal(100)).quantize(Decimal("0.01"), ROUND_HALF_UP),
                _MAX_QUOTA_ATTAINMENT_PCT,
            )
            if quota > 0
            else Decimal("0.00")
        )
        self.goal_gap_value = (quota - revenue).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError(
                {"period_end": "The period end date must not be before the period start date."}
            )

        if not self.tenant_id:
            return

        for field_name, message in (
            ("rep", "The rep must belong to this workspace."),
            ("territory", "Choose a territory from this workspace."),
            ("manager", "The manager must belong to this workspace."),
            ("forecast_period", "Choose a forecast period from this workspace."),
            ("quota_plan", "Choose a quota plan from this workspace."),
            ("coaching_scorecard", "Choose a coaching scorecard from this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})

    @property
    def rating_badge_class(self):
        mapping = {
            "outstanding": "badge-green",
            "strong": "badge-green",
            "on_track": "badge-info",
            "needs_improvement": "badge-amber",
            "underperforming": "badge-red",
        }
        return mapping.get(self.rating, "badge-slate")

    @property
    def status_badge_class(self):
        mapping = {
            "draft": "badge-muted",
            "shared": "badge-slate",
            "acknowledged": "badge-info",
            "approved": "badge-green",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def goal_gap_badge_class(self):
        """Green when the target was met, amber when it is close, red when it is not.

        The gap is ``target - actual``, so it is **negative** (or zero) once the
        target is met or exceeded — that is a green scorecard, not a red one.
        "Within 10%" means the shortfall is at most a tenth of the quota target,
        which is the same statement as an attainment of 90% or better.
        """
        gap = Decimal(self.goal_gap_value or 0)
        if gap <= 0:
            return "badge-green"
        quota = Decimal(self.quota_target or 0)
        if quota > 0:
            if gap <= (quota * Decimal("0.10")).quantize(Decimal("0.01"), ROUND_HALF_UP):
                return "badge-amber"
            return "badge-red"
        return "badge-slate"

    @property
    def is_on_track(self):
        return self.rating in {"outstanding", "strong", "on_track"}

    @property
    def total_activities(self):
        """The sum of the six recorded activity counters."""
        return (
            int(self.activities_logged or 0)
            + int(self.calls_logged or 0)
            + int(self.emails_logged or 0)
            + int(self.meetings_logged or 0)
            + int(self.meetings_booked or 0)
            + int(self.follow_ups_completed or 0)
        )
