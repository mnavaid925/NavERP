"""CRM 1.6 Analytics & Reporting — Widgets forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    DashboardWidget,
)


class DashboardWidgetForm(TenantModelForm):
    """Widget tile editor. ``dashboard`` + ``tenant`` are set in the view (the widget is created
    under a known dashboard), so they are out of the form. ``clean()`` rejects a chart type the
    chosen metric can't render (e.g. a table metric drawn as a line)."""

    class Meta:
        model = DashboardWidget
        fields = ["title", "metric", "chart_type", "date_range", "size", "target_value"]

    def clean(self):
        from apps.crm.analytics import WIDGET_METRICS, allowed_charts
        cleaned = super().clean()
        metric = cleaned.get("metric")
        chart_type = cleaned.get("chart_type")
        if metric and chart_type and metric in WIDGET_METRICS:
            ok = allowed_charts(metric)
            if chart_type not in ok:
                self.add_error("chart_type",
                               "This metric supports: " + ", ".join(ok) + ".")
        return cleaned
