from django.urls import path

from apps.quality.views.IncomingQuality.QualityReturnAuthorizations import (
    quality_return_authorization_advance,
    quality_return_authorization_create,
    quality_return_authorization_delete,
    quality_return_authorization_detail,
    quality_return_authorization_edit,
    quality_return_authorization_export,
    quality_return_authorization_list,
)

urlpatterns = [
    path("iqc/rmas/", quality_return_authorization_list, name="quality_return_authorization_list"),
    path("iqc/rmas/create/", quality_return_authorization_create, name="quality_return_authorization_create"),
    path("iqc/rmas/export/", quality_return_authorization_export, name="quality_return_authorization_export"),
    path("iqc/rmas/<int:pk>/", quality_return_authorization_detail, name="quality_return_authorization_detail"),
    path("iqc/rmas/<int:pk>/edit/", quality_return_authorization_edit, name="quality_return_authorization_edit"),
    path("iqc/rmas/<int:pk>/delete/", quality_return_authorization_delete, name="quality_return_authorization_delete"),
    path("iqc/rmas/<int:pk>/advance/", quality_return_authorization_advance, name="quality_return_authorization_advance"),
]
