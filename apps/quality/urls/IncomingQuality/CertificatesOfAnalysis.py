from django.urls import path

from apps.quality.views.IncomingQuality.CertificatesOfAnalysis import (
    certificate_of_analysis_create,
    certificate_of_analysis_delete,
    certificate_of_analysis_detail,
    certificate_of_analysis_edit,
    certificate_of_analysis_export,
    certificate_of_analysis_list,
    certificate_of_analysis_verify,
)

urlpatterns = [
    path("iqc/coas/", certificate_of_analysis_list, name="certificate_of_analysis_list"),
    path("iqc/coas/create/", certificate_of_analysis_create, name="certificate_of_analysis_create"),
    path("iqc/coas/export/", certificate_of_analysis_export, name="certificate_of_analysis_export"),
    path("iqc/coas/<int:pk>/", certificate_of_analysis_detail, name="certificate_of_analysis_detail"),
    path("iqc/coas/<int:pk>/edit/", certificate_of_analysis_edit, name="certificate_of_analysis_edit"),
    path("iqc/coas/<int:pk>/delete/", certificate_of_analysis_delete, name="certificate_of_analysis_delete"),
    path("iqc/coas/<int:pk>/verify/", certificate_of_analysis_verify, name="certificate_of_analysis_verify"),
]
