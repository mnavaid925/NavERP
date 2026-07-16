"""HRM 3.27 Communication Hub — HRDashboardWidgets forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HRDashboardWidget,
)


class HRDashboardWidgetForm(TenantModelForm):
    """Widget tile editor. ``dashboard``/``tenant``/``position`` are set in the view. ``clean()``
    rejects a chart type the chosen metric can't render (e.g. a table metric drawn as a line)."""

    class Meta:
        model = HRDashboardWidget
        fields = ["title", "metric", "chart_type", "date_range", "size", "target_value"]

    def clean(self):
        from apps.hrm.analytics import WIDGET_METRICS, allowed_charts
        cleaned = super().clean()
        metric = cleaned.get("metric")
        chart_type = cleaned.get("chart_type")
        if metric and chart_type and metric in WIDGET_METRICS:
            ok = allowed_charts(metric)
            if chart_type not in ok:
                self.add_error("chart_type", "This metric supports: " + ", ".join(ok) + ".")
        return cleaned
