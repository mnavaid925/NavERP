from django.urls import path

from apps.bi.views.Dashboards import BiDashboards as views

urlpatterns = [
    path("dashboards/", views.bi_dashboard_list, name="bi_dashboard_list"),
    path("dashboards/create/", views.bi_dashboard_create, name="bi_dashboard_create"),
    path("dashboards/<int:pk>/", views.bi_dashboard_detail, name="bi_dashboard_detail"),
    path("dashboards/<int:pk>/edit/", views.bi_dashboard_edit, name="bi_dashboard_edit"),
    path("dashboards/<int:pk>/delete/", views.bi_dashboard_delete, name="bi_dashboard_delete"),
    path("dashboards/<int:pk>/publish/", views.bi_dashboard_publish, name="bi_dashboard_publish"),
    path("dashboards/<int:pk>/duplicate/", views.bi_dashboard_duplicate, name="bi_dashboard_duplicate"),
]
