from django.urls import path

from apps.quality.views.FinalQuality import PackagingLabelVerifications as views

urlpatterns = [
    path("packaging-verifications/", views.packaging_label_verification_list, name="packaging_label_verification_list"),
    path("packaging-verifications/create/", views.packaging_label_verification_create, name="packaging_label_verification_create"),
    path("packaging-verifications/export/", views.packaging_label_verification_export, name="packaging_label_verification_export"),
    path("packaging-verifications/<int:pk>/", views.packaging_label_verification_detail, name="packaging_label_verification_detail"),
    path("packaging-verifications/<int:pk>/edit/", views.packaging_label_verification_edit, name="packaging_label_verification_edit"),
    path("packaging-verifications/<int:pk>/delete/", views.packaging_label_verification_delete, name="packaging_label_verification_delete"),
]
