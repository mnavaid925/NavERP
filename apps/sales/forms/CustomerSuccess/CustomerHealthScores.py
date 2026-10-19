"""Sales 8.11 — Forms for `CustomerHealthScore`."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.CustomerSuccess.CustomerHealthScores import CustomerHealthScore


class CustomerHealthScoreForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerHealthScore
        fields = [
            "account",
            "evaluation_date",
            "overall_score",
            "health_band",
            "previous_score",
            "score_trend",
            "product_usage_score",
            "support_ticket_score",
            "nps_sentiment_score",
            "relationship_score",
            "renewal_risk_score",
            "risk_level",
            "active_alert_message",
            "is_churn_risk",
            "license_utilization_pct",
            "open_support_tickets",
            "latest_nps",
            "last_activity_date",
            "notes",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "form-select"}),
            "evaluation_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "overall_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "health_band": forms.Select(attrs={"class": "form-select"}),
            "previous_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "score_trend": forms.Select(attrs={"class": "form-select"}),
            "product_usage_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "support_ticket_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "nps_sentiment_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "relationship_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "renewal_risk_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "risk_level": forms.Select(attrs={"class": "form-select"}),
            "active_alert_message": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Critical support escalation pending executive sponsor check-in"}),
            "is_churn_risk": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "license_utilization_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0, "max": 100}),
            "open_support_tickets": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "latest_nps": forms.NumberInput(attrs={"class": "form-input", "min": -100, "max": 100}),
            "last_activity_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["account"])
        return cleaned_data
