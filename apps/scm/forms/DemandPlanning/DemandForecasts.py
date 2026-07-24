"""SCM 4.7 Demand Planning — DemandForecast form, period formset and the generate action form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _active_currencies, _customer_parties
from apps.scm.models import DemandForecast, DemandForecastPeriod


class DemandForecastForm(TenantUniqueMixin, TenantModelForm):
    """The forecast header.

    EXCLUDES everything the app owns: `number` (auto), `selected_method` (what best_fit chose),
    `revision`/`supersedes` (set by the revise action), `status` (action-driven), `generated_at` and
    `approved_by`/`approved_at`. `item`, `location`, `reference_item` and `seasonality_profile` are
    tenant-scoped by the base class; `customer` and `currency` need hand-scoping (see below).
    """

    class Meta:
        model = DemandForecast
        fields = ["name", "item", "location", "customer", "demand_source", "bucket",
                  "horizon_start", "horizon_end", "history_months", "method", "method_parameter",
                  "seasonality_profile", "reference_item", "reference_scale_pct",
                  "exclude_outliers", "outlier_threshold_sigma", "currency", "scenario", "notes"]
        widgets = {
            "horizon_start": forms.DateInput(attrs={"type": "date"}),
            "horizon_end": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A customer is a PartyRole, so the tenant's whole party list would offer suppliers and
        # carriers as forecast channels. Currency is GLOBAL (no tenant FK) so the base can't scope it.
        if "customer" in self.fields:
            self.fields["customer"].queryset = _customer_parties(self.tenant)
        _active_currencies(self)


class DemandForecastPeriodForm(TenantModelForm):
    """One horizon bucket.

    `historical_quantity`, `signal_adjustment_quantity` and `consensus_quantity` are NOT editable
    here — they are a snapshot, the signal engine's output and the consensus roll-up respectively.
    The detail page shows all three; letting them be typed would break the waterfall's meaning.
    """

    class Meta:
        model = DemandForecastPeriod
        fields = ["sequence", "period_start", "period_end", "period_label", "baseline_quantity",
                  "seasonal_index_applied", "event_uplift_quantity", "final_quantity",
                  "unit_price", "is_locked"]
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
        }


class BaseDemandForecastPeriodFormSet(forms.BaseInlineFormSet):
    """Validates ``sequence`` against the periods ALREADY on the forecast.

    The built-in cross-form uniqueness check only compares the forms in this POST, and each form's
    own check excludes the inline FK — so a crafted POST that raises ``TOTAL_FORMS`` and reuses an
    existing sequence would pass validation and hit the ``unique_together`` as an IntegrityError
    (a 500) inside the atomic save.
    """

    def clean(self):
        super().clean()
        if not self.instance.pk:
            return
        editing = [form.instance.pk for form in self.forms if form.instance.pk]
        taken = set(self.instance.periods.exclude(pk__in=editing)
                    .values_list("sequence", flat=True))
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            if form.cleaned_data.get("sequence") in taken:
                form.add_error("sequence", "That period sequence already exists on this forecast.")


#: extra=0 — the grid is BUILT by the generate action from the derived history, so an edit screen
#: offering blank rows would invite a hand-typed period that the next regenerate silently renumbers.
DemandForecastPeriodFormSet = inlineformset_factory(
    DemandForecast, DemandForecastPeriod, form=DemandForecastPeriodForm,
    formset=BaseDemandForecastPeriodFormSet, extra=0, can_delete=True,
)


class DemandForecastGenerateForm(forms.Form):
    """The generate action's only choice: whether to overwrite periods a planner locked."""

    regenerate_locked = forms.BooleanField(
        required=False, label="Also regenerate locked periods",
        help_text="Locked periods are normally left exactly as the planner committed them.")
