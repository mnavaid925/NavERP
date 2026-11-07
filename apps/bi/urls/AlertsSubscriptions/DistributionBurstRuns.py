from django.urls import path

from apps.bi.views.AlertsSubscriptions import DistributionBurstRuns as views

urlpatterns = [
    path("burst-runs/", views.distribution_burst_run_list, name="distribution_burst_run_list"),
    path("burst-runs/create/", views.distribution_burst_run_create, name="distribution_burst_run_create"),
    path("burst-runs/<int:pk>/", views.distribution_burst_run_detail, name="distribution_burst_run_detail"),
    path("burst-runs/<int:pk>/edit/", views.distribution_burst_run_edit, name="distribution_burst_run_edit"),
    path("burst-runs/<int:pk>/delete/", views.distribution_burst_run_delete, name="distribution_burst_run_delete"),
]
