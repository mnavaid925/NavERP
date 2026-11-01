from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin
from apps.ecommerce.models.AnalyticsBi.CustomerCohortMetrics import CustomerCohortMetric


class CustomerCohortMetricForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerCohortMetric
        fields = [
            "cohort_month",
            "period_offset_months",
            "initial_cohort_size",
            "active_customers",
            "retention_rate_pct",
            "cohort_orders_count",
            "cumulative_gross_revenue",
            "cumulative_net_revenue",
            "cumulative_margin",
            "cumulative_ltv_per_customer",
            "churn_rate_pct",
            "acquisition_channel_tag",
        ]
        widgets = {
            "cohort_month": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "period_offset_months": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 120}),
            "initial_cohort_size": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "active_customers": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "retention_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cohort_orders_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "cumulative_gross_revenue": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cumulative_net_revenue": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cumulative_margin": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cumulative_ltv_per_customer": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "churn_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "acquisition_channel_tag": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. organic, paid_search, influencer"}),
        }
