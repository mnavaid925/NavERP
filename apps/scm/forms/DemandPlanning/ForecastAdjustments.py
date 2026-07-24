"""SCM 4.7 Demand Planning — ForecastAdjustment form + the accept/reject review form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _scope_to_parent
from apps.scm.models import DemandForecast, DemandForecastPeriod, ForecastAdjustment


class ForecastAdjustmentForm(TenantUniqueMixin, TenantModelForm):
    """One contributor's proposed override.

    EXCLUDES `number` (auto), `submitted_by` (stamped from request.user), `resolved_quantity`
    (derived in save()), `status` (the accept/reject gate) and `reviewed_by`/`reviewed_at`/
    `review_note` (captured by the review form).

    `period` MUST be hand-scoped: `DemandForecastPeriod` has no tenant FK of its own — it is reached
    through its forecast — so `TenantModelForm` cannot scope it and the select would otherwise list
    every tenant's periods. The parent forecast is resolved from the bound POST data through the
    TENANT-SCOPED forecast queryset, so a crafted `forecast` id cannot widen the period list either.
    """

    class Meta:
        model = ForecastAdjustment
        fields = ["forecast", "period", "contributor_function", "org_unit", "adjustment_type",
                  "proposed_quantity", "adjustment_pct", "reason_code", "rationale", "confidence"]
        widgets = {"rationale": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, forecast=None, **kwargs):
        super().__init__(*args, **kwargs)
        forecasts = (DemandForecast.objects.none() if self.tenant is None else
                     DemandForecast.objects.filter(tenant=self.tenant).select_related("item"))
        self.fields["forecast"].queryset = forecasts
        parent = forecast or (self.instance.forecast if self.instance.pk else None)
        if self.is_bound:
            submitted = self.data.get(self.add_prefix("forecast"), "")
            if str(submitted).isdigit():
                parent = forecasts.filter(pk=int(submitted)).first() or parent
        _scope_to_parent(self, "period",
                         parent.periods.all() if parent is not None
                         else DemandForecastPeriod.objects.none())


class ForecastAdjustmentReviewForm(forms.Form):
    """The reviewer's note recorded alongside an accept or reject — the audit of the decision."""

    review_note = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False,
                                  label="Review note")
