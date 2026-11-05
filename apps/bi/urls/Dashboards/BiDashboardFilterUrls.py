from django.urls import path

from apps.bi.views.Dashboards import BiDashboardFilters as views

urlpatterns = [
    path("dashboards/filters/", views.bi_dashboard_filter_list, name="bi_dashboard_filter_list"),
    path("dashboards/filters/create/", views.bi_dashboard_filter_create, name="bi_dashboard_filter_create"),
    path("dashboards/filters/<int:pk>/", views.bi_dashboard_filter_detail, name="bi_dashboard_filter_detail"),
    path("dashboards/filters/<int:pk>/edit/", views.bi_dashboard_filter_edit, name="bi_dashboard_filter_edit"),
    path("dashboards/filters/<int:pk>/delete/", views.bi_dashboard_filter_delete, name="bi_dashboard_filter_delete"),
]
