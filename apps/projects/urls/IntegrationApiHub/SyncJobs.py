"""Projects 7.18 — ProjectSyncJob URL patterns."""
from django.urls import path

from apps.projects.views.IntegrationApiHub import SyncJobs as views

urlpatterns = [
    path("integration/sync-jobs/", views.syj_list, name="syj_list"),
    path("integration/sync-jobs/add/", views.syj_create, name="syj_create"),
    path("integration/sync-jobs/<int:pk>/", views.syj_detail, name="syj_detail"),
    path("integration/sync-jobs/<int:pk>/edit/", views.syj_edit, name="syj_edit"),
    path("integration/sync-jobs/<int:pk>/delete/", views.syj_delete, name="syj_delete"),
    path("integration/sync-jobs/<int:pk>/run/", views.syj_run, name="syj_run"),
    path("integration/sync-jobs/<int:pk>/toggle/", views.syj_toggle_active, name="syj_toggle_active"),
]
