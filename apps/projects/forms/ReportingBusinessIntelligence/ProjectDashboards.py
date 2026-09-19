"""Projects 7.16 Reporting & Business Intelligence — ProjectDashboardForm.

The grid definition only. ``owner`` is the creating user — ``save()`` stamps it, because a board
authored in the UI that belonged to nobody would come back as a tenant template (A2.3 reserves
``owner=NULL`` for a seeder-authored row). ``is_default`` is reachable by neither form: no route in
B1 writes it, so it stays a seeder-authored flag and two edit forms saved one after the other can
never leave two home dashboards for one owner.
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

    def __init__(self, *args, tenant=None, user=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.user = user
        # A1.2 rule 4: a tile carries no date pair, so `custom` could only ever come back as an error.
        self.fields["default_range"].choices = PRESET_RANGES
        if tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=tenant).order_by("name")
            self.fields["portfolio"].queryset = Portfolio.objects.filter(
                tenant=tenant).order_by("name")

    def save(self, *args, **kwargs):
        # A create only. `crud_create` hands a form class no user can reach, so without this the
        # board saved as owner=None — which this table reads as "a tenant template every member of
        # the workspace can land on", not "my new board". Keying on `pk is None` rather than on
        # "owner is unset" is the difference that matters here: an edit of a real tenant template
        # would otherwise hand that shared row to whoever pressed Save.
        if self.instance.pk is None and self.user is not None:
            self.instance.owner = self.user
        return super().save(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "portfolio"])
        return cleaned
