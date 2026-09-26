"""8.4 Sales Forecasting — the manager override, and its own audit trail.

A ``ForecastAdjustment`` is one manager's override of a rep's forecast call. Microsoft's
taxonomy is reused verbatim: ``direct`` is a hand-made override, ``indirect`` is
system-written when a manager's total propagates down to a team, and ``revert`` is the
row the Reset action writes. Optional ``opportunity`` / ``placement`` FKs target a single
deal; without them the row moves the whole call.

Five rulings are structural here and cannot be undone by a later edit:

* **The post-override figure is NEVER stored.** There is no ``adjusted_total`` and no
  ``calculated_value`` column: the system value is snapshotted into ``original_value`` /
  ``original_category`` and the *applied delta* is what the user enters. That asymmetry
  is precisely what makes Reset always possible -- there is no cached "current" figure to
  invalidate. ``net_delta`` is a property for the same reason.
* **There is no ``status`` field.** Unlike ``ForecastSubmission`` this is an audit trail,
  not a workflow document, so the generic "wrap Edit/Delete in ``status == 'draft'``"
  template rule was deliberately dropped (contract 6.3 / 13.3).
* ``reason_code`` is **required with no default** and is the whole point of the entity: an
  override with no reason is exactly the sandbagging signal bullet 4 hunts.
* ``submission`` is ``PROTECT`` -- an audit row is never cascaded away -- and the actor FK
  uses ``related_name="+"`` per the actor-FK convention.
* ``original_value`` / ``original_category`` are **system snapshots** excluded from every
  ``ModelForm``; ``reverted_at`` is ``editable=False`` (L22) and so is auto-excluded.

``ForecastScenario`` is entity 4 and does not exist yet, so nothing here references it:
a scenario never mutates a submission, and an adjustment never mutates a scenario.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.crm.models import Opportunity
from apps.sales.models._base import TenantNumbered


class ForecastAdjustment(TenantNumbered):
    """One manager override of one forecast call, with a mandatory reason."""

    NUMBER_PREFIX = "FAD"

    #: Microsoft's taxonomy, verbatim. ``indirect`` rows are system-written when a manager
    #: total propagates down; ``revert`` rows are written by the Reset action. Neither is
    #: ever hand-typed, which is why the form disables the field (contract 4.3).
    ADJUSTMENT_KIND_CHOICES = [
        ("direct", "Direct"),
        ("indirect", "Indirect"),
        ("revert", "Revert"),
    ]

    #: What the override touches: the deal's forecast bucket, or its amount.
    TARGET_FIELD_CHOICES = [
        ("category", "Forecast Category"),
        ("amount", "Amount"),
    ]

    #: The sandbagging signal. Required, no default, enforced in the form's ``clean()``.
    REASON_CODE_CHOICES = [
        ("new_deal", "New Deal Added"),
        ("deal_advanced", "Deal Advanced A Stage"),
        ("deal_slipped", "Deal Slipped"),
        ("deal_lost", "Deal Lost"),
        ("deal_won", "Deal Won"),
        ("amount_revised", "Amount Revised"),
        ("timing_revised", "Timing Revised"),
        ("territory_reassigned", "Territory Reassigned"),
        ("manager_judgement", "Manager Judgement"),
        ("correction", "Data Correction"),
    ]

    submission = models.ForeignKey(
        "sales.ForecastSubmission",
        on_delete=models.PROTECT,
        related_name="adjustments",
    )
    # Optional per-deal targeting. SET_NULL on both: a closed-lost deal keeps its history
    # even after the deal or its placement is removed.
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_adjustments",
    )
    placement = models.ForeignKey(
        "sales.OpportunityPipelinePlacement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_forecast_adjustments",
    )
    # Actor FK: related_name="+" per the actor-FK convention (contract 3.2 / R3).
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    adjustment_kind = models.CharField(
        max_length=12,
        choices=ADJUSTMENT_KIND_CHOICES,
        default="direct",
    )
    target_field = models.CharField(
        max_length=12,
        choices=TARGET_FIELD_CHOICES,
        default="category",
    )
    # System snapshot of what the forecast said BEFORE the override. Never a form field.
    original_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # The applied delta the manager enters. The post-override figure is NOT stored.
    adjusted_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
    )
    original_category = models.CharField(
        max_length=12, choices=Opportunity.FORECAST_CATEGORY_CHOICES, null=True, blank=True,
    )
    adjusted_category = models.CharField(
        max_length=12, choices=Opportunity.FORECAST_CATEGORY_CHOICES, null=True, blank=True,
    )
    # REQUIRED, no default -- an override with no reason is the sandbagging signal.
    reason_code = models.CharField(max_length=32, choices=REASON_CODE_CHOICES)
    note = models.TextField(blank=True)
    is_reverted = models.BooleanField(default=False)
    # editable=False (L22) -- system-stamped by the Reset action, auto-excluded from forms.
    reverted_at = models.DateTimeField(null=True, blank=True, editable=False)
    # REQUIRED on revert -- Dynamics' mandatory-reason Reset.
    revert_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "forecast adjustments"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_fad_tenant_number_uniq",
            ),
            # A reverted row always carries its stamp: `is_reverted` is a claim, `reverted_at`
            # is the evidence, and the two may never disagree.
            models.CheckConstraint(
                condition=Q(is_reverted=False) | Q(is_reverted=True, reverted_at__isnull=False),
                name="sales_fad_reverted_stamped",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "submission"], name="sales_fad_tnt_submission_idx"),
            models.Index(fields=["tenant", "reason_code"], name="sales_fad_tnt_reason_idx"),
            models.Index(fields=["tenant", "adjustment_kind"], name="sales_fad_tnt_kind_idx"),
            models.Index(fields=["tenant", "opportunity"], name="sales_fad_tnt_opp_idx"),
        ]

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
            ("submission", "The forecast call must belong to this workspace."),
            ("opportunity", "The opportunity must belong to this workspace."),
            ("placement", "The pipeline placement must belong to this workspace."),
            ("created_by", "The author must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})
        if not (self.reason_code or "").strip():
            raise ValidationError({"reason_code": "An adjustment requires a reason code."})
        if self.reason_code not in dict(self.REASON_CODE_CHOICES):
            raise ValidationError({"reason_code": "That reason code is not recognised."})
        # A reverted row carries BOTH halves of the Reset: when and why.
        if self.is_reverted and (self.reverted_at is None or not (self.revert_reason or "").strip()):
            raise ValidationError({
                "revert_reason": "A reverted adjustment needs a revert reason and a timestamp.",
            })
        # target_field decides which pair of fields is live; the other pair must be empty.
        if self.target_field == "category":
            if not self.adjusted_category:
                raise ValidationError({
                    "adjusted_category": "A category override must choose a forecast category.",
                })
            if self.adjusted_value is not None or self.original_value is not None:
                raise ValidationError({
                    "adjusted_value": "A category override cannot also carry an amount.",
                })
        elif self.target_field == "amount":
            if self.adjusted_value is None:
                raise ValidationError({
                    "adjusted_value": "An amount override must carry the applied amount.",
                })
            if self.adjusted_category or self.original_category:
                raise ValidationError({
                    "adjusted_category": "An amount override cannot also carry a category.",
                })
        else:
            raise ValidationError({"target_field": "That target field is not recognised."})
        # A placement belongs to exactly one opportunity; naming both must agree.
        if self.opportunity_id and self.placement_id:
            if self.placement.opportunity_id != self.opportunity_id:
                raise ValidationError({
                    "placement": "That placement belongs to a different opportunity.",
                })
        if self.submission_id and self.submission.period_id and self.submission.period.is_locked:
            raise ValidationError({
                "submission": "The period is locked, so its forecast calls are read-only.",
            })

    @property
    def net_delta(self):
        """``adjusted_value - original_value`` for an ``amount`` row, else ``None``.

        Decimal-safe (never ``float``), and ``None`` rather than ``0`` for a category row so
        the template renders an em dash instead of a meaningless zero.
        """
        if self.target_field != "amount":
            return None
        return Decimal(self.adjusted_value or 0) - Decimal(self.original_value or 0)

    @property
    def is_resettable(self):
        """Whether the Reset action may still fire -- an override can be undone once."""
        return not self.is_reverted

    def snapshot_system_value(self, value=None, category=None):
        """Record what the forecast said BEFORE the override. Server-side, never a form field.

        The post-override figure is deliberately not written: it is recomputed from the
        submission and the applied delta, which is exactly what makes Reset always possible.
        """
        if self.target_field == "amount":
            self.original_value = None if value is None else Decimal(value)
        else:
            self.original_category = category or None
        return self

    def mark_reverted(self, user, revert_reason):
        """Stamp the Reset transition. The caller saves inside its own transaction."""
        reason = (revert_reason or "").strip()[:255]
        if not reason:
            raise ValidationError({"revert_reason": "A Reset must say why."})
        self.is_reverted = True
        self.reverted_at = timezone.now()
        self.revert_reason = reason
        self.created_by = user
        return self

    def __str__(self):
        return f"{self.number} · {self.get_adjustment_kind_display()} · {self.reason_code}"
