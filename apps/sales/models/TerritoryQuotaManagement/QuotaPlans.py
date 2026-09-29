"""Sales 8.7 — the quota-plan envelope (``QPA-``). Serves NavERP bullet 3 in full.

**8.7 extends CRM 1.2's ``crm.SalesQuota`` and 8.4's ``sales.ForecastPeriod`` by FK, and owns
neither.** The *number* is CRM's ``SalesQuota.target_amount`` and 8.7 never writes it; the *window*
is 8.4's ``ForecastPeriod`` and 8.7 never re-spells year/quarter/month. What this model adds is the
**derivation**: how the target was set, from what baseline, with what growth and relief, whether
uplift was permitted, and how it phases across the period.

That is why there is no money column here at all. ``derived_baseline`` and ``derived_stretch_amount``
are **view-computed context keys** (``quota_plan_detail``), never stored columns and never ``F()``
expressions — a second stored target is a second source of truth for the same number (L37).

**THE BINDING CROSS-CHECK IS THE POINT OF THIS MODEL.** ``crm.SalesQuota`` and
``sales.ForecastPeriod`` each carry their own ``period_type`` / ``period_year`` / ``period_number``,
and **nothing in either schema stops them disagreeing**. A mismatch does not fail loudly — it
produces an attainment board quietly comparing a Q2 quota against a Q1 forecast, which reads as a
*data* problem rather than a schema one. So ``clean()`` refuses to save unless all three match, and
keys the error to ``forecast_period`` with a message naming both sides (research §5.3).

``QuotaPlan`` deliberately carries **NO** ``accounting.Currency``: the reporting currency is inherited
from ``ForecastPeriod.reporting_currency``, and ``accounting.Currency`` is a GLOBAL master with no
``tenant`` FK, so it is never tenant-checked (L29). The performance board sums amounts only when the
fetched rows share one reporting currency, and reports anything else as a **caveat, not a number**.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered, settings
from apps.sales.models.SalesForecasting.ForecastSubmissions import ForecastSubmission

#: The permitted keys of `parameters`, per `method`. A closed dict, but UNKNOWN KEYS ARE IGNORED
#: rather than rejected, so a plan written by a newer build survives a rollback (same policy as
#: `OrderValidationRule.parameters`).
PLAN_PARAMETER_KEYS = {
    "top_down": {"custom_baseline", "seasonal_weights", "cut_off_day", "notes"},
    "bottom_up": {"custom_baseline", "seasonal_weights", "cut_off_day", "notes"},
}


class QuotaPlan(TenantNumbered):
    """How one CRM quota target for one forecast period was derived."""

    NUMBER_PREFIX = "QPA"

    METHOD_CHOICES = [
        ("top_down", "Top-Down"),
        ("bottom_up", "Bottom-Up"),
    ]
    ALLOCATION_BASIS_CHOICES = [
        ("historical_revenue", "Historical Revenue"),
        ("pipeline", "Open Pipeline"),
        ("account_count", "Account Count"),
        ("territory_potential", "Territory Potential"),
        ("manual", "Manual"),
    ]
    BASELINE_SOURCE_CHOICES = [
        ("previous_period", "Previous Period"),
        ("previous_year", "Previous Year"),
        ("custom", "Custom"),
    ]
    #: IMPORTED from 8.4's ForecastSubmission, never re-spelled — draft|submitted|approved|rejected|locked.
    STATUS_CHOICES = ForecastSubmission.STATUS_CHOICES
    TARGET_TYPE_CHOICES = [
        ("revenue", "Revenue"),
        ("units", "Units"),
        ("bookings", "Bookings"),
    ]
    PHASING_CHOICES = [
        ("equal", "Equal"),
        ("seasonal", "Seasonal"),
    ]
    #: SAME constant name and meaning as ForecastSubmission.FROZEN_STATES. The form disables every
    #: field in these states AND the views re-check server-side, so hiding the Edit button is never
    #: the only guard (research §5.5, R9).
    FROZEN_STATES = frozenset({"approved", "locked"})

    quota_ref = models.ForeignKey(
        "crm.SalesQuota",
        on_delete=models.PROTECT,
        related_name="sales_quota_plans",
    )
    forecast_period = models.ForeignKey(
        "sales.ForecastPeriod",
        on_delete=models.PROTECT,
        related_name="quota_plans",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_quota_plans",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_quota_plans",
    )
    #: NO default — a plan must declare its method. "top_down" and "bottom_up" have different
    #: validity rules, so guessing one would make a saved row mean something its author never chose.
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    allocation_basis = models.CharField(max_length=20, choices=ALLOCATION_BASIS_CHOICES, default="historical_revenue")
    baseline_source = models.CharField(max_length=16, choices=BASELINE_SOURCE_CHOICES, default="previous_year")
    growth_target_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    attrition_relief_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    #: A percentage UPLIFT, deliberately NOT a second money column (see the module docstring).
    stretch_target_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    uplift_allowed = models.BooleanField(default=False)
    #: The LABEL for what the CRM money number means. It adds NO unit-count column to the quota.
    target_type = models.CharField(max_length=10, choices=TARGET_TYPE_CHOICES, default="revenue")
    phasing = models.CharField(max_length=8, choices=PHASING_CHOICES, default="equal")
    parameters = models.JSONField(default=dict, blank=True)
    #: ACTION-DRIVEN — moved only by the submit/approve/reject/lock POST views, never typed.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    # --- FROZEN EVIDENCE. editable=False, so auto-excluded from every ModelForm (L22).
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="sales_submitted_quota_plans",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="sales_approved_quota_plans",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    calculated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-forecast_period__period_year", "owner"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "quota_ref"], name="sales_qplan_tenant_quota_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "method"], name="sales_qplan_tnt_method_idx"),
            models.Index(fields=["tenant", "territory"], name="sales_qplan_tnt_terr_idx"),
            models.Index(fields=["tenant", "status"], name="sales_qplan_tnt_status_idx"),
        ]

    # ------------------------------------------------------------------ helpers

    def _relation_belongs_to_tenant(self, field_name):
        """The one-FK-one-check helper shared by every 8.7 model — see AccountTerritoryAssignments."""
        if not self.tenant_id:
            return True
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    @property
    def is_frozen(self):
        """True once the plan is approved or locked. Mirrors ForecastSubmission's own property."""
        return self.status in self.FROZEN_STATES

    # ------------------------------------------------------------------ validation

    def clean(self):
        super().clean()
        if not isinstance(self.parameters or {}, dict):
            raise ValidationError({"parameters": "Parameters must be a JSON object."})
        if not self.tenant_id:
            return
        errors = {}
        for field_name in ("quota_ref", "forecast_period", "owner", "territory"):
            if not self._relation_belongs_to_tenant(field_name):
                errors[field_name] = "That record must belong to this workspace."
        # A plan may not point at a different territory than the quota it annotates.
        if self.territory_id and self.quota_ref_id and self.territory_id != self.quota_ref.territory_id:
            errors["territory"] = "The plan territory must match the territory on the quota it annotates."
        # --- THE BINDING CROSS-CHECK (research §5.3). Both sides are named in the message on
        # purpose: a silent mismatch is an attainment board quietly comparing Q2 to Q1, and the
        # reader has to be able to see WHICH pair of periods disagreed.
        if self.quota_ref_id and self.forecast_period_id:
            quota, period = self.quota_ref, self.forecast_period
            if (
                quota.period_type != period.period_type
                or quota.period_year != period.period_year
                or quota.period_number != period.period_number
            ):
                errors["forecast_period"] = (
                    f"The quota covers {quota.get_period_type_display()} "
                    f"{quota.period_year} number {quota.period_number}, but the forecast period "
                    f"is {period.get_period_type_display()} {period.period_year} "
                    f"number {period.period_number}. They must be the same window."
                )
        # Uplift is a top-down-only setting (SAP). A bottom-up plan that also claims uplift is
        # asserting two contradictory things about how its number was produced.
        if self.method == "bottom_up" and self.uplift_allowed:
            errors["uplift_allowed"] = "Uplift applies to a top-down plan only."
        if self.stretch_target_pct is not None and not self.uplift_allowed:
            errors["stretch_target_pct"] = "Allow uplift before setting a stretch target."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # A direct .save() (seeder, service, shell) skips full_clean(), and every reader in 8.7
        # assumes a mapping here. Coerce rather than persist a shape the readers would choke on.
        if not isinstance(self.parameters, dict):
            self.parameters = {}
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or '—'} · {self.quota_ref} · {self.get_method_display()}"

