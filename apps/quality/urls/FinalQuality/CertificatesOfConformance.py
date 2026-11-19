from django.urls import path

from apps.quality.views.FinalQuality import CertificatesOfConformance as views

urlpatterns = [
    path("certificates-of-conformance/", views.certificate_of_conformance_list, name="certificate_of_conformance_list"),
    path("certificates-of-conformance/create/", views.certificate_of_conformance_create, name="certificate_of_conformance_create"),
    path("certificates-of-conformance/export/", views.certificate_of_conformance_export, name="certificate_of_conformance_export"),
    path("certificates-of-conformance/<int:pk>/", views.certificate_of_conformance_detail, name="certificate_of_conformance_detail"),
    path("certificates-of-conformance/<int:pk>/edit/", views.certificate_of_conformance_edit, name="certificate_of_conformance_edit"),
    path("certificates-of-conformance/<int:pk>/delete/", views.certificate_of_conformance_delete, name="certificate_of_conformance_delete"),
    path("certificates-of-conformance/<int:pk>/sign/", views.certificate_of_conformance_sign, name="certificate_of_conformance_sign"),
]
