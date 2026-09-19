"""Projects 7.16 Reporting & Business Intelligence — DashboardWidgetForm.

``dashboard`` and ``tenant`` come from the URL and the parent row, and ``position`` is appended on create
and moved by ``wdg_move`` — none of the three is a field a user may type.
"""
from apps.projects.analytics import PRESET_RANGES
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.PortfolioProgramManagement.Portfolios import Portfolio
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.models.ReportingBusinessIntelligence.DashboardWidgets import DashboardWidget


class DashboardWidgetForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DashboardWidget
        fields = [
            "title", "metric", "chart_type", "date_range", "size", "target_value",
            "project", "portfolio",
        ]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # A1.3 rule 4: a tile stores one preset, never a date pair.
        self.fields["date_range"].choices = PRESET_RANGES
        if tenant is not None:
            self.fields["project"].queryset = Project.objects.filter(
                tenant=tenant).order_by("name")
            self.fields["portfolio"].queryset = Portfolio.objects.filter(
                tenant=tenant).order_by("name")

    def clean(self):
        # Imported here, not at module scope: analytics owns the metric vocabulary and a form is the only
        # layer allowed to reach across for it — the metric↔chart pair has no other home (models must not
        # import analytics, B3.0's one-way edge).
        from apps.projects.analytics import WIDGET_METRICS, allowed_charts

        cleaned = super().clean()
        metric = cleaned.get("metric")
        chart_type = cleaned.get("chart_type")
        if metric and chart_type and metric in WIDGET_METRICS:
            allowed = allowed_charts(metric)
            if chart_type not in allowed:
                self.add_error("chart_type", "This metric supports: " + ", ".join(allowed) + ".")
        _reject_foreign(self, cleaned, ["project", "portfolio"])
        return cleaned
