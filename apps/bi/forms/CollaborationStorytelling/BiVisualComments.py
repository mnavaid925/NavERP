from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.CollaborationStorytelling.BiDataStories import BiDataStory
from apps.bi.models.CollaborationStorytelling.BiVisualComments import BiVisualComment
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.Dashboards.BiDashboardWidgets import BiDashboardWidget
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.core.forms import TenantModelForm


class BiVisualCommentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = BiVisualComment
        fields = [
            "target_type",
            "dashboard",
            "widget",
            "report",
            "story",
            "slide_id",
            "parent_comment",
            "content",
            "status",
            "priority",
            "coordinate_x",
            "coordinate_y",
        ]
        widgets = {
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "widget": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "story": forms.Select(attrs={"class": "form-select"}),
            "slide_id": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "parent_comment": forms.Select(attrs={"class": "form-select"}),
            "content": forms.Textarea(attrs={"rows": 4, "class": "form-textarea", "placeholder": "Share thoughts, ask questions, or record visual findings..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "coordinate_x": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "placeholder": "X %"}),
            "coordinate_y": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "placeholder": "Y %"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant)
            self.fields["widget"].queryset = BiDashboardWidget.objects.filter(dashboard__tenant=self.tenant)
            self.fields["report"].queryset = ReportDefinition.objects.filter(tenant=self.tenant)
            self.fields["story"].queryset = BiDataStory.objects.filter(tenant=self.tenant)
            self.fields["parent_comment"].queryset = BiVisualComment.objects.filter(tenant=self.tenant)

    def clean_dashboard(self):
        d = self.cleaned_data.get("dashboard")
        return reject_foreign(d, self.tenant, "Dashboard")

    def clean_report(self):
        r = self.cleaned_data.get("report")
        return reject_foreign(r, self.tenant, "Report")

    def clean_story(self):
        s = self.cleaned_data.get("story")
        return reject_foreign(s, self.tenant, "Story")

    def clean_parent_comment(self):
        p = self.cleaned_data.get("parent_comment")
        return reject_foreign(p, self.tenant, "Parent Comment")
