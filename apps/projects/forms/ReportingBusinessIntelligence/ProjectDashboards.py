"""Projects 7.16 Reporting & Business Intelligence — ProjectDashboardForm.

The grid definition only. ``owner`` is the creating user, and ``is_default`` is set by the set-home verb,
never by this form — otherwise two edit forms saved one after the other could leave two home dashboards.
"""
from django import forms

from apps.projects.analytics import PRESET_RANGES
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ReportingBusinessIntelligence.ProjectDashboards import ProjectDashboard


class ProjectDashboardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectDashboard
        fields = [
            "name", "description", "audience", "default_range", "layout",
            "is_shared", "project", "portfolio",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # A1.2 rule 4: a tile carries no date pair, so `custom` could only ever come back as an error.
        self.fields["default_range"].choices = PRESET_RANGES
        if tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=tenant).order_by("name")
            self.fields["portfolio"].queryset = Portfolio.objects.filter(
                tenant=tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "portfolio"])
        return cleaned
