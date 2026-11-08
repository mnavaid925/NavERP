from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.CollaborationStorytelling.BiDecisionLogs import BiDecisionLog
from apps.bi.models.CollaborationStorytelling.BiSharedWorkspaces import BiSharedWorkspace
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.core.forms import TenantModelForm


class BiDecisionLogForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiDecisionLog
        fields = [
            "title",
            "slug",
            "category",
            "status",
            "decision_date",
            "problem_statement",
            "rationale",
            "alternatives_considered",
            "expected_impact",
            "actual_outcome",
            "workspace",
            "dashboard",
            "widget",
            "kpi",
            "decision_maker",
            "show_on_charts",
            "marker_style",
            "marker_color",
            "review_date",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "decision_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "problem_statement": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "rationale": forms.Textarea(attrs={"rows": 4, "class": "form-textarea"}),
            "alternatives_considered": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "expected_impact": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "actual_outcome": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "workspace": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "widget": forms.Select(attrs={"class": "form-select"}),
            "kpi": forms.Select(attrs={"class": "form-select"}),
            "decision_maker": forms.Select(attrs={"class": "form-select"}),
            "show_on_charts": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "marker_style": forms.Select(attrs={"class": "form-select"}),
            "marker_color": forms.TextInput(attrs={"type": "color", "class": "form-input h-10 w-20 p-1"}),
            "review_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["workspace"].queryset = BiSharedWorkspace.objects.filter(tenant=self.tenant)
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant)
            self.fields["widget"].queryset = BiDashboardWidget.objects.filter(dashboard__tenant=self.tenant)
            self.fields["kpi"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)

    def clean_workspace(self):
        w = self.cleaned_data.get("workspace")
        return reject_foreign(w, self.tenant, "Workspace")

    def clean_dashboard(self):
        d = self.cleaned_data.get("dashboard")
        return reject_foreign(d, self.tenant, "Dashboard")

    def clean_kpi(self):
        k = self.cleaned_data.get("kpi")
        return reject_foreign(k, self.tenant, "KPI")
