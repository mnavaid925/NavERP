from django.urls import path

from apps.quality.views.LimsManagement import LimsDashboard as views

urlpatterns = [
    path("lims/", views.lims_dashboard, name="lims_dashboard"),
    path("lims/export/", views.lims_export_csv, name="lims_export_csv"),
]
