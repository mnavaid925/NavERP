"""Sales 8.18 — SalesSyncRun URL patterns."""
from django.urls import path

from apps.sales.views.IntegrationApiHub.SyncRuns import (
    ssr_delete,
    ssr_detail,
    ssr_list,
)

urlpatterns = [
    path("runs/", ssr_list, name="ssr_list"),
    path("runs/<int:pk>/", ssr_detail, name="ssr_detail"),
    path("runs/<int:pk>/delete/", ssr_delete, name="ssr_delete"),
]
