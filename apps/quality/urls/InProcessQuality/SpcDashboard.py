from django.urls import path

from apps.quality.views.InProcessQuality import SpcDashboard as views

urlpatterns = [
    path("spc-dashboard/", views.spc_dashboard, name="spc_dashboard"),
]
