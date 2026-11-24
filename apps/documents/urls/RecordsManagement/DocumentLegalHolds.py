from django.urls import path

from apps.documents.views.RecordsManagement import DocumentLegalHolds as views

urlpatterns = [
    path("records/holds/", views.legal_hold_list, name="legal_hold_list"),
    path("records/holds/create/", views.legal_hold_create, name="legal_hold_create"),
    path("records/holds/<int:pk>/", views.legal_hold_detail, name="legal_hold_detail"),
    path("records/holds/<int:pk>/release/", views.legal_hold_release, name="legal_hold_release"),
    path("records/holds/<int:pk>/acknowledge/", views.legal_hold_acknowledge, name="legal_hold_acknowledge"),
]
