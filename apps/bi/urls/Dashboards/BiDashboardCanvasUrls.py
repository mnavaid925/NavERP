from django.urls import path

from apps.bi.views.Dashboards import BiDashboardCanvasViews as views

urlpatterns = [
    path("dashboards/<int:pk>/view/", views.bi_dashboard_canvas_view, name="bi_dashboard_canvas_view"),
    path("dashboards/<int:pk>/builder/", views.bi_dashboard_canvas_builder, name="bi_dashboard_canvas_builder"),
    path("dashboards/<int:pk>/kiosk/", views.bi_dashboard_kiosk_view, name="bi_dashboard_kiosk_view"),
]
