from django.urls import path

from apps.quality.views.DataIntegrity import DataIntegrityDashboard as views

urlpatterns = [
    path("dashboard/", views.data_integrity_dashboard, name="data_integrity_dashboard"),
]
