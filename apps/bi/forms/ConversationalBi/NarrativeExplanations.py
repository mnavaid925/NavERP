from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsight
from apps.bi.models.ConversationalBi.NarrativeExplanations import NarrativeExplanation
from apps.bi.models.ConversationalBi.NaturalLanguageQueries import NaturalLanguageQuery
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.core.forms import TenantModelForm


class NarrativeExplanationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = NarrativeExplanation
        fields = [
            "title",
            "headline",
            "target_artifact_type",
            "dashboard",
            "report",
            "kpi",
            "query",
            "insight",
            "narrative_style",
            "narrative_body",
            "top_positive_driver",
            "top_negative_driver",
            "language",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Q4 Executive Financial Performance Briefing",
                }
            ),
            "headline": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Gross Margin improved +3.4% driven by European direct sales expansion",
                }
            ),
            "target_artifact_type": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "kpi": forms.Select(attrs={"class": "form-select"}),
            "query": forms.Select(attrs={"class": "form-select"}),
            "insight": forms.Select(attrs={"class": "form-select"}),
            "narrative_style": forms.Select(attrs={"class": "form-select"}),
            "narrative_body": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 5,
                    "placeholder": "Auto-generated natural language commentary or analyst notes...",
                }
            ),
            "top_positive_driver": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. European Direct Sales Volume"}
            ),
            "top_negative_driver": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Freight Surcharges"}
            ),
            "language": forms.TextInput(attrs={"class": "form-input", "placeholder": "en"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant)
            self.fields["report"].queryset = ReportDefinition.objects.filter(tenant=self.tenant)
            self.fields["kpi"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)
            self.fields["query"].queryset = NaturalLanguageQuery.objects.filter(tenant=self.tenant)
            self.fields["insight"].queryset = AugmentedInsight.objects.filter(tenant=self.tenant)

        self.fields["dashboard"].required = False
        self.fields["report"].required = False
        self.fields["kpi"].required = False
        self.fields["query"].required = False
        self.fields["insight"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["dashboard", "report", "kpi", "query", "insight"],
        )
        return cleaned_data
