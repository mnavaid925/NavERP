from django.urls import path
from apps.ecommerce.views.IntegrationApi import IntegrationSyncJobs as views

urlpatterns = [
    path("integration-api/sync-jobs/", views.integration_sync_job_list, name="integrationsyncjob_list"),
    path("integration-api/sync-jobs/create/", views.integration_sync_job_create, name="integrationsyncjob_create"),
    path("integration-api/sync-jobs/<int:pk>/", views.integration_sync_job_detail, name="integrationsyncjob_detail"),
    path("integration-api/sync-jobs/<int:pk>/edit/", views.integration_sync_job_edit, name="integrationsyncjob_edit"),
    path("integration-api/sync-jobs/<int:pk>/delete/", views.integration_sync_job_delete, name="integrationsyncjob_delete"),
    path("integration-api/sync-jobs/<int:pk>/retry/", views.integration_sync_job_retry, name="integrationsyncjob_retry"),
]
