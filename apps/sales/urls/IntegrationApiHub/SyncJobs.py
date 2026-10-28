"""Sales 8.18 — SalesSyncJob URL patterns."""
from django.urls import path

from apps.sales.views.IntegrationApiHub.SyncJobs import (
    ssj_create,
    ssj_delete,
    ssj_detail,
    ssj_edit,
    ssj_list,
    ssj_trigger,
)

urlpatterns = [
    path("jobs/", ssj_list, name="ssj_list"),
    path("jobs/create/", ssj_create, name="ssj_create"),
    path("jobs/<int:pk>/", ssj_detail, name="ssj_detail"),
    path("jobs/<int:pk>/edit/", ssj_edit, name="ssj_edit"),
    path("jobs/<int:pk>/delete/", ssj_delete, name="ssj_delete"),
    path("jobs/<int:pk>/trigger/", ssj_trigger, name="ssj_trigger"),
]
