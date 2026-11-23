from django.urls import path

from apps.documents.views.SecurityAccessControl.WatermarkPolicies import (
    watermark_create,
    watermark_delete,
    watermark_detail,
    watermark_edit,
    watermark_list,
    watermark_preview,
)

urlpatterns = [
    path("watermark-policies/", watermark_list, name="watermark_list"),
    path("watermark-policies/create/", watermark_create, name="watermark_create"),
    path("watermark-policies/preview/", watermark_preview, name="watermark_preview"),
    path("watermark-policies/<int:pk>/", watermark_detail, name="watermark_detail"),
    path("watermark-policies/<int:pk>/edit/", watermark_edit, name="watermark_edit"),
    path("watermark-policies/<int:pk>/delete/", watermark_delete, name="watermark_delete"),
]
