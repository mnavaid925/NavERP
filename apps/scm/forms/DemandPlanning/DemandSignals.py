"""SCM 4.7 Demand Planning — DemandSignal form + the apply/dismiss action forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _customer_parties
from apps.scm.models import DemandForecast, DemandSignal


class DemandSignalForm(TenantUniqueMixin, TenantModelForm):
    """A hand-entered signal.

    EXCLUDES `number` (auto), `status` (triage-driven), `applied_to_forecast` (set by the apply
    action, which picks the forecast in its own form) and `reviewed_by`/`reviewed_at`.
    """

    class Meta:
        model = DemandSignal
        fields = ["signal_type", "source", "source_reference", "item", "category", "location",
                  "customer", "observed_at", "effective_from", "effective_to", "horizon_days",
                  "signal_value", "baseline_value", "impact_direction", "impact_pct",
                  "impact_quantity", "confidence", "notes"]
        widgets = {
            "observed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "customer" in self.fields:
            self.fields["customer"].queryset = _customer_parties(self.tenant)


class DemandSignalApplyForm(forms.Form):
    """Which forecast this signal moves, and by how much.

    The forecast queryset is scoped to the tenant AND to the statuses whose periods may still move —
    a draft has no grid yet and an archived plan is history, so neither should be offered.
    """

    forecast = forms.ModelChoiceField(queryset=DemandForecast.objects.none(),
                                      label="Apply to forecast")
    impact_quantity = forms.DecimalField(
        max_digits=14, decimal_places=4, required=False,
        label="Units to apply (signed)",
        help_text="Leave blank to use the signal's own impact, carrying its direction.")

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["forecast"].queryset = (
            DemandForecast.objects.none() if tenant is None else
            DemandForecast.objects.filter(tenant=tenant,
                                          status__in=DemandForecast.ADJUSTABLE_STATUSES)
            .select_related("item"))


class DemandSignalDismissForm(forms.Form):
    """Why a signal was not acted on — kept so the triage log explains itself later."""

    notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False,
                            label="Dismissal note")
