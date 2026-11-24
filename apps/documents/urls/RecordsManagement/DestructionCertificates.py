from django.urls import path

from apps.documents.views.RecordsManagement import DestructionCertificates as views

urlpatterns = [
    path("records/certificates/", views.destruction_certificate_list, name="destruction_certificate_list"),
    path("records/certificates/create/", views.destruction_certificate_create, name="destruction_certificate_create"),
    path("records/certificates/<int:pk>/", views.destruction_certificate_detail, name="destruction_certificate_detail"),
    path("records/certificates/<int:pk>/authorize/", views.destruction_certificate_authorize, name="destruction_certificate_authorize"),
    path("records/certificates/<int:pk>/execute/", views.destruction_certificate_execute, name="destruction_certificate_execute"),
]
