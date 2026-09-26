"""8.4 Sales Forecasting — ForecastScenario forms.

Three rulings are enforced server-side here rather than in the template:

* **The deltas are the only numbers a user types.** ``projected_commit_amount`` /
  ``projected_total_amount`` are ``editable=False`` on the model, so they are structurally
  absent from ``Meta.fields`` and cannot be smuggled in by a crafted POST. ``is_selected`` is
  likewise absent: it is workflow-owned, and only the ``select`` action may move it.
* **``is_baseline`` is disabled on edit.** Only the baseline may be selected (the
  ``sales_fsc_baseline_selected`` CheckConstraint), so a baseline flag is decided once, at
  creation, and cannot be traded between two rows afterwards.
* **A locked period refuses the whole form**, re-checked in ``clean()`` so hiding the button
  is never the only guard.

``ForecastScenarioApplyForm`` is the ``target`` / ``threshold`` form the apply action reads.
It is a plain ``TenantActionForm`` because it writes no model of its own -- applying a
scenario writes two snapshot columns on one ``ForecastScenario`` row and nothing else.
"""
from decimal import Decimal

from django import forms

from apps.accounts.models import User
from apps.sales.forms._common import TenantActionForm, TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod
from apps.sales.models.SalesForecasting.ForecastScenarios import (
    DELTA_FIELDS,
    DELTA_PCT_MAX,
    DELTA_PCT_MIN,
    ForecastScenario,
)

#: What the projection is judged against once a scenario is applied. Reused as the
#: ``target`` choices of the apply form so the two can never disagree.
APPLY_TARGET_CHOICES = [
    ("weighted", "Weighted pipeline"),
    ("commit", "Commit"),
    ("total", "Total forecast"),
]

#: Beyond this share of movement the apply action refuses and says why: a projection that
#: moved further than the threshold is a modelling error, not a forecast.
DEFAULT_VARIANCE_THRESHOLD_PCT = Decimal("20.00")


def _bounded(queryset, limit=500):
    """A ``[:500]``-bounded list of ids, then the queryset itself.

    The ``AccountPlanForm`` pattern: an unbounded period / user dropdown is a page-weight bug,
    and slicing a queryset the form then re-filters on would evaluate the whole table anyway.
    """
    ids = list(queryset.values_list("pk", flat=True)[:limit])
    return queryset.filter(pk__in=ids)



class ForecastScenarioForm(TenantUniqueMixin, TenantModelForm):
    """The what-if. Deltas only; the projection is the server's arithmetic."""

    class Meta:
        model = ForecastScenario
        fields = [
            "period", "owner", "name", "scenario_type", "probability_pct",
            "is_baseline", "pipeline_delta_pct", "best_case_delta_pct",
            "commit_delta_pct", "assumption_notes",
        ]
        widgets = {
            "assumption_notes": forms.Textarea(attrs={"rows": 4}),
            "pipeline_delta_pct": forms.NumberInput(attrs={"step": "0.01"}),
            "best_case_delta_pct": forms.NumberInput(attrs={"step": "0.01"}),
            "commit_delta_pct": forms.NumberInput(attrs={"step": "0.01"}),
        }

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.user = user
        if tenant is None:
            for field_name in ("period", "owner"):
                self.fields[field_name].queryset = self.fields[field_name].queryset.none()
        else:
            self.fields["period"].queryset = _bounded(
                ForecastPeriod.objects.filter(tenant=tenant).order_by(
                    "-period_year", "period_number", "name",
                )
            )
            self.fields["owner"].queryset = _bounded(
                User.objects.filter(tenant=tenant, is_active=True).order_by("username")
            )
        # The baseline flag is decided once, at creation. Trading it afterwards would mean two
        # rows each claiming to be the current plan, which is precisely what the CheckConstraint
        # forbids -- so on edit it is shown read-only rather than offered.
        if self.instance.pk:
            self.fields["is_baseline"].disabled = True
        # A locked period's scenarios are read-only. Disabled, not hidden, so the reason stays
        # visible instead of the field simply vanishing.
        if self.instance.pk and self.instance.period_id and self.instance.period.is_locked:
            for field_name in self.fields:
                self.fields[field_name].disabled = True

    def clean(self):
        cleaned = super().clean()
        if self.tenant is None:
            self.add_error(None, "A tenant workspace is required.")
        _reject_foreign(self, cleaned, ["period", "owner"])
        probability_pct = cleaned.get("probability_pct")
        if probability_pct is not None and not 0 <= probability_pct <= 100:
            self.add_error("probability_pct", "The blend weight must be between 0 and 100.")
        for _, delta_field, _ in DELTA_FIELDS:
            value = cleaned.get(delta_field)
            if value is None:
                continue
            if not DELTA_PCT_MIN <= Decimal(value) <= DELTA_PCT_MAX:
                self.add_error(
                    delta_field,
                    f"A delta must be between {DELTA_PCT_MIN} and {DELTA_PCT_MAX} percent.",
                )
        period = cleaned.get("period")
        if period is not None and period.is_locked:
            self.add_error(None, "This period is locked, so its scenarios are read-only.")
        # Baseline implies selected (the CheckConstraint, 3.4 / 13.4). `is_selected` is not a
        # form field at all, so the pairing is settled here through the model's own helper
        # rather than by asking the user to tick two boxes to express one idea -- and the
        # re-check below catches an instance that arrives already contradicting the rule,
        # surfacing it as a field error instead of a database IntegrityError.
        if cleaned.get("is_baseline"):
            self.instance.sync_selected_from_baseline()
            if not self.instance.is_selected:
                self.add_error(
                    "is_baseline", "The baseline scenario is the current plan, so it is selected.",
                )
        return cleaned


class ForecastScenarioApplyForm(TenantActionForm):
    """The apply action's own form: which period, which target, how much drift is tolerable.

    A plain action form because it creates nothing. Applying a scenario writes two snapshot
    columns on one ``ForecastScenario`` row; it never writes a ``ForecastSubmission``, which
    is the isolation rule this whole entity is built on.
    """

    period = forms.ModelChoiceField(
        queryset=ForecastPeriod.objects.none(),
        label="Period",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    target = forms.ChoiceField(
        choices=APPLY_TARGET_CHOICES,
        initial="commit",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    variance_threshold_pct = forms.DecimalField(
        required=False,
        initial=DEFAULT_VARIANCE_THRESHOLD_PCT,
        min_value=Decimal("0"),
        max_value=Decimal("1000"),
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # A tenant with no workspace gets an empty dropdown, never every period in the system.
        if tenant is None:
            self.fields["period"].queryset = ForecastPeriod.objects.none()
        else:
            self.fields["period"].queryset = _bounded(
                ForecastPeriod.objects.filter(tenant=tenant, is_active=True).order_by(
                    "-period_year", "period_number", "name",
                )
            )

    def clean(self):
        cleaned = super().clean()
        if self.tenant is None:
            self.add_error(None, "A tenant workspace is required.")
        period = cleaned.get("period")
        if period is not None:
            if period.tenant_id != (self.tenant.pk if self.tenant is not None else None):
                self.add_error("period", "That period belongs to another workspace.")
            if period.is_locked:
                self.add_error(None, "This period is locked, so its scenarios are read-only.")
        # A junk ?target= is reset rather than trusted; a blank threshold means the default.
        if cleaned.get("target") not in dict(APPLY_TARGET_CHOICES):
            self.add_error("target", "That target is not recognised.")
        if cleaned.get("variance_threshold_pct") is None:
            cleaned["variance_threshold_pct"] = DEFAULT_VARIANCE_THRESHOLD_PCT
        return cleaned

