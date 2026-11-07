from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AiAugmentedAnalytics.AnalyticsRecommendations import AnalyticsRecommendation
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm

User = get_user_model()


class AnalyticsRecommendationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AnalyticsRecommendation
        fields = [
            "user",
            "recommendation_type",
            "target_title",
            "target_url",
            "reason",
            "rationale_text",
            "affinity_score",
            "status",
            "dashboard",
            "report",
            "kpi",
            "semantic_model",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "recommendation_type": forms.Select(attrs={"class": "form-select"}),
            "target_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Executive Revenue Dashboard"}),
            "target_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. /bi/dashboards/1/"}),
            "reason": forms.Select(attrs={"class": "form-select"}),
            "rationale_text": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Why this asset is suggested to user..."}),
            "affinity_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "kpi": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["user"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant)
            self.fields["report"].queryset = ReportDefinition.objects.filter(tenant=self.tenant)
            self.fields["kpi"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
        self.fields["dashboard"].required = False
        self.fields["report"].required = False
        self.fields["kpi"].required = False
        self.fields["semantic_model"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["user", "dashboard", "report", "kpi", "semantic_model"])
        return cleaned_data
