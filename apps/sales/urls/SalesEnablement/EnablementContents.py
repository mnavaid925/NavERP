"""Sales 8.9 — URLs for `EnablementContent`."""
from django.urls import path

from apps.sales.views.SalesEnablement.EnablementContents import (
    enablement_content_create,
    enablement_content_delete,
    enablement_content_detail,
    enablement_content_edit,
    enablement_content_list,
    enablement_content_share,
)

urlpatterns = [
    path("enablement/content/", enablement_content_list, name="enablement_content_list"),
    path("enablement/content/new/", enablement_content_create, name="enablement_content_create"),
    path("enablement/content/<int:pk>/", enablement_content_detail, name="enablement_content_detail"),
    path("enablement/content/<int:pk>/edit/", enablement_content_edit, name="enablement_content_edit"),
    path("enablement/content/<int:pk>/delete/", enablement_content_delete, name="enablement_content_delete"),
    path("enablement/content/<int:pk>/share/", enablement_content_share, name="enablement_content_share"),
]
