from django.urls import path

from apps.quality.views.IncomingQuality.IqcSpcDashboard import iqc_spc_dashboard

urlpatterns = [
    path("iqc/spc-dashboard/", iqc_spc_dashboard, name="iqc_spc_dashboard"),
]
