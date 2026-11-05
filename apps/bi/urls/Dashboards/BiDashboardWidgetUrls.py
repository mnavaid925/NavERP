from django.urls import path

from apps.bi.views.Dashboards import BiDashboardWidgets as views

urlpatterns = [
    path("dashboards/widgets/", views.bi_dashboard_widget_list, name="bi_dashboard_widget_list"),
    path("dashboards/widgets/create/", views.bi_dashboard_widget_create, name="bi_dashboard_widget_create"),
    path("dashboards/widgets/<int:pk>/", views.bi_dashboard_widget_detail, name="bi_dashboard_widget_detail"),
    path("dashboards/widgets/<int:pk>/edit/", views.bi_dashboard_widget_edit, name="bi_dashboard_widget_edit"),
    path("dashboards/widgets/<int:pk>/delete/", views.bi_dashboard_widget_delete, name="bi_dashboard_widget_delete"),
    path("dashboards/widgets/<int:pk>/data/", views.bi_dashboard_widget_data, name="bi_dashboard_widget_data"),
]
