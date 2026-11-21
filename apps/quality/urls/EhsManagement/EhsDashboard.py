from django.urls import path

from apps.quality.views.EhsManagement import EhsDashboard as views

urlpatterns = [
    path("ehs-dashboard/", views.ehs_dashboard, name="ehs_dashboard"),
    path("ehs-dashboard/export/", views.ehs_dashboard_export, name="ehs_dashboard_export"),
]
