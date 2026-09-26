"""8.4 Sales Forecasting — the per-rep forecast call.

A ``ForecastSubmission`` is one rep's (or one org unit's) forecast call for a single
``ForecastPeriod``: five user-entered category amounts, the snapshot figures a service
writes when the call is submitted, and the AI block. 8.4 reuses the opportunity forecast
vocabulary — ``omitted | pipeline | best_case | commit | closed`` — rather than
re-spelling it, and never re-declares an opportunity, stage, quota or currency.

Four rulings are structural here and cannot be undone by a later edit:

* ``total_forecast_amount`` / ``variance_amount`` / ``attainment_pct`` / ``pace_pct`` are
  **properties**. There is no ``total_forecast_amount`` column, even though the name reads
  like a field — a stored total is a drift bug waiting to happen.
* ``weighted_amount`` / ``quota_amount`` / ``actual_amount`` are **service-written
  snapshots**, excluded from every ``ModelForm``. ``quota_ref`` carries CRM's own
  composite unique, so a quota is frozen *by value* and editing the quota never rewrites
  history.
* The two **actor** FKs (``submitted_by`` / ``reviewed_by``) use ``related_name="+"`` so
  four ``User`` reverse accessors cannot collide with ``crm_opportunities`` /
  ``crm_sales_quotas`` / ``crm_territories`` / ``crm_tasks`` (contract 3.2).
* A DB-level ``(tenant, period, owner)`` unique is **forbidden**: ``owner`` is nullable
  and NULLs do not collide in a SQL unique index, so it would silently permit unlimited
  duplicate drafts. It is enforced in ``clean()`` instead.

``ForecastAdjustment`` is entity 3 and does not exist yet, so it is resolved through the
app registry rather than imported and ``makemigrations`` stays safe.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.sales.models._base import TenantNumbered
from apps.sales.models.SalesForecasting.ForecastPeriods import _optional_sales_model

#: Every amount column on the model, in contract order. Used by the non-negative
#: ``clean()`` rule, by the database CheckConstraint and by the form, so the three never
#: drift apart.
AMOUNT_FIELDS = (
    "omitted_amount",
    "pipeline_amount",
    "best_case_amount",
    "commit_amount",
    "closed_amount",
    "weighted_amount",
    "quota_amount",
    "actual_amount",
)

#: The five user-entered category amounts, each mapping to its ``crm.Opportunity``
#: forecast-category value. The vocabulary is reused, never re-declared.
CATEGORY_AMOUNT_FIELDS = (
    ("omitted", "omitted_amount"),
    ("pipeline", "pipeline_amount"),
    ("best_case", "best_case_amount"),
    ("commit", "commit_amount"),
    ("closed", "closed_amount"),
)

class ForecastSubmission(TenantNumbered):
    NUMBER_PREFIX = "FCS"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("locked", "Locked"),
    ]

    #: The two states a submission is frozen in by its own status. A third freeze comes
    #: from ``period.is_locked``. The form disables every field in these states and the
    #: views re-check server-side, so hiding the Edit button is never the only guard (R9).
    FROZEN_STATES = frozenset({"approved", "locked"})

    period = models.ForeignKey(
        "sales.ForecastPeriod",
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_submissions",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_submissions",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_submissions",
    )
    pipeline = models.ForeignKey(
        "sales.Pipeline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_submissions",
    )
    # A quota is snapshotted BY VALUE into quota_amount, so editing the quota never
    # rewrites a historical forecast.
    quota_ref = models.ForeignKey(
        "crm.SalesQuota",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_submissions",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    omitted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    pipeline_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    best_case_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    commit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    closed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    # ---- service-written snapshots: never a form field, refreshed on submit ----
    weighted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    quota_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    actual_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])

    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_note = models.TextField(blank=True)

    # ---- AI block: storage + explanation only, never shown below the eligibility gate ----
    ai_predicted_pipeline = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    ai_predicted_best_case = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    ai_predicted_commit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    ai_confidence_pct = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    ai_model_name = models.CharField(max_length=120, blank=True)
    ai_model_version = models.CharField(max_length=60, blank=True)
    ai_generated_at = models.DateTimeField(null=True, blank=True)
    ai_explanation = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "forecast submissions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_fcs_tenant_number_uniq"),
            models.CheckConstraint(
                condition=Q(omitted_amount__gte=0)
                & Q(pipeline_amount__gte=0)
                & Q(best_case_amount__gte=0)
                & Q(commit_amount__gte=0)
                & Q(closed_amount__gte=0)
                & Q(weighted_amount__gte=0)
                & Q(quota_amount__gte=0)
                & Q(actual_amount__gte=0),
                name="sales_fcs_amounts_nonneg",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "period", "status"], name="sales_fcs_tnt_p_status_idx"),
            models.Index(fields=["tenant", "owner"], name="sales_fcs_tnt_owner_idx"),
            models.Index(fields=["tenant", "period", "org_unit"], name="sales_fcs_tnt_p_org_idx"),
        ]

    @property
    def total_forecast_amount(self):
        """Commit + best case + pipeline. Decimal-safe (``Decimal(x or 0)``)."""
        return (
            Decimal(self.commit_amount or 0)
            + Decimal(self.best_case_amount or 0)
            + Decimal(self.pipeline_amount or 0)
        )

    @property
    def variance_amount(self):
        """Forecast less actual. Negative means the call over-promised."""
        return self.total_forecast_amount - Decimal(self.actual_amount or 0)

    @property
    def attainment_pct(self):
        """Actual as a percentage of the snapshotted quota.

        ``None`` when the quota is zero or unset — never a division by zero, and never an
        ``Infinity`` / ``NaN`` for the template to render (R6).
        """
        quota = Decimal(self.quota_amount or 0)
        if quota <= 0:
            return None
        return ((Decimal(self.actual_amount or 0) / quota) * Decimal("100")).quantize(Decimal("0.01"))

    @property
    def pace_pct(self):
        """How much of the period window has elapsed, straight off the period."""
        if not self.period_id:
            return None
        return self.period.period_elapsed_pct

    @property
    def is_frozen(self):
        """True when neither the form nor the views may accept an edit."""
        if self.status in self.FROZEN_STATES:
            return True
        return bool(self.period_id and self.period.is_locked)

    @property
    def allowed_actions(self):
        """The actions the workflow allows from the current state, server-side.

        The template renders from this, so a button is never shown that the view would
        refuse, and every view re-derives the same list before writing. ``delete`` is a
        tenant-admin right, so ``ForecastSubmission.allowed_actions`` includes it as a
        candidate and the view narrows it out for a non-admin.
        """
        if self.status in self.FROZEN_STATES:
            return []
        if self.period_id and self.period.is_locked:
            return []
        if self.status in {"draft", "rejected"}:
            return ["edit", "submit", "delete"]
        if self.status == "submitted":
            return ["approve", "reject", "delete"]
        return []

    def _relation_belongs_to_tenant(self, field_name):
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def _duplicate_owner_rows(self):
        """Sibling calls for the same (tenant, period, owner), this row excluded.

        A NULL owner matches only other NULL owners — the SQL-unique semantics the
        forbidden DB constraint could never give us, so an un-owned team call is still
        one per period.
        """
        if not self.tenant_id or not self.period_id:
            return ForecastSubmission.objects.none()
        siblings = ForecastSubmission.objects.filter(
            tenant_id=self.tenant_id,
            period_id=self.period_id,
        ).exclude(pk=self.pk)
        if self.owner_id:
            return siblings.filter(owner_id=self.owner_id)
        return siblings.filter(owner__isnull=True)

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        for field_name, message in (
            ("period", "The forecast period must belong to this workspace."),
            ("owner", "The owner must belong to this workspace."),
            ("org_unit", "Choose an organizational unit from this workspace."),
            ("territory", "Choose a territory from this workspace."),
            ("pipeline", "Choose a pipeline from this workspace."),
            ("quota_ref", "Choose a quota from this workspace."),
            ("submitted_by", "The submitter must belong to this workspace."),
            ("reviewed_by", "The reviewer must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})
        for field_name in AMOUNT_FIELDS:
            value = getattr(self, field_name, None)
            if value is not None and Decimal(value) < 0:
                raise ValidationError({field_name: "An amount cannot be negative."})
        if self._duplicate_owner_rows().exists():
            raise ValidationError({
                "owner": "This workspace already has a forecast call for that owner and period.",
            })
        if self.period_id and self.period.is_locked and self.status != "locked":
            raise ValidationError({
                "status": "The period is locked, so this call's status cannot change.",
            })
        if self.status in {"approved", "rejected"} and not (self.reviewed_by_id and self.reviewed_at):
            raise ValidationError({
                "status": "A reviewed call must record who reviewed it and when.",
            })

    def adjustment_rows(self):
        """The manager-override rows on this call, newest first, bounded to 200.

        ``ForecastAdjustment`` is entity 3, so it is resolved through the registry; an
        empty list is the correct answer until it lands.
        """
        model = _optional_sales_model("ForecastAdjustment")
        if model is None or not self.pk:
            return []
        return list(
            model.objects.filter(submission_id=self.pk, tenant_id=self.tenant_id)
            .order_by("-created_at", "-id")[:200]
        )

    def mark_submitted(self, user):
        """Stamp the submit transition. The caller saves inside its own transaction."""
        self.status = "submitted"
        self.submitted_at = timezone.now()
        self.submitted_by = user
        return self

    def mark_reviewed(self, user, approved, note=""):
        """Stamp the approve / reject transition."""
        self.status = "approved" if approved else "rejected"
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        if note:
            self.review_note = note[:200]
        return self

    def mark_reverted(self):
        """Send a rejected call back to draft so the rep can revise and resubmit."""
        self.status = "draft"
        self.submitted_at = None
        self.submitted_by = None
        self.reviewed_by = None
        self.reviewed_at = None
        return self

    def __str__(self):
        return f"{self.number} · {self.owner or '—'} · {self.period if self.period_id else '—'}"
