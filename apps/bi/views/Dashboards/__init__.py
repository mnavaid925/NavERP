from apps.bi.views.Dashboards.BiDashboardBookmarks import (
    bi_dashboard_bookmark_apply,
    bi_dashboard_bookmark_create,
    bi_dashboard_bookmark_delete,
    bi_dashboard_bookmark_detail,
    bi_dashboard_bookmark_edit,
    bi_dashboard_bookmark_list,
)
from apps.bi.views.Dashboards.BiDashboardCanvasViews import (
    bi_dashboard_canvas_builder,
    bi_dashboard_canvas_view,
    bi_dashboard_kiosk_view,
)
from apps.bi.views.Dashboards.BiDashboardFilters import (
    bi_dashboard_filter_create,
    bi_dashboard_filter_delete,
    bi_dashboard_filter_detail,
    bi_dashboard_filter_edit,
    bi_dashboard_filter_list,
)
from apps.bi.views.Dashboards.BiDashboards import (
    bi_dashboard_create,
    bi_dashboard_delete,
    bi_dashboard_detail,
    bi_dashboard_duplicate,
    bi_dashboard_edit,
    bi_dashboard_list,
    bi_dashboard_publish,
)
from apps.bi.views.Dashboards.BiDashboardWidgets import (
    bi_dashboard_widget_create,
    bi_dashboard_widget_data,
    bi_dashboard_widget_delete,
    bi_dashboard_widget_detail,
    bi_dashboard_widget_edit,
    bi_dashboard_widget_list,
)

__all__ = [
    "bi_dashboard_list",
    "bi_dashboard_detail",
    "bi_dashboard_create",
    "bi_dashboard_edit",
    "bi_dashboard_delete",
    "bi_dashboard_publish",
    "bi_dashboard_duplicate",
    "bi_dashboard_canvas_view",
    "bi_dashboard_kiosk_view",
    "bi_dashboard_canvas_builder",
    "bi_dashboard_widget_list",
    "bi_dashboard_widget_detail",
    "bi_dashboard_widget_create",
    "bi_dashboard_widget_edit",
    "bi_dashboard_widget_delete",
    "bi_dashboard_widget_data",
    "bi_dashboard_bookmark_list",
    "bi_dashboard_bookmark_detail",
    "bi_dashboard_bookmark_create",
    "bi_dashboard_bookmark_edit",
    "bi_dashboard_bookmark_delete",
    "bi_dashboard_bookmark_apply",
    "bi_dashboard_filter_list",
    "bi_dashboard_filter_detail",
    "bi_dashboard_filter_create",
    "bi_dashboard_filter_edit",
    "bi_dashboard_filter_delete",
]
