from django.urls import path

from apps.quality.views.DesignControls import DesignVerifications as views

urlpatterns = [
    path("design-controls/verifications/", views.design_verification_list, name="design_verification_list"),
    path("design-controls/verifications/export/", views.design_verification_export, name="design_verification_export"),
    path("design-controls/verifications/create/", views.design_verification_create, name="design_verification_create"),
    path("design-controls/verifications/<int:pk>/", views.design_verification_detail, name="design_verification_detail"),
    path("design-controls/verifications/<int:pk>/edit/", views.design_verification_edit, name="design_verification_edit"),
    path("design-controls/verifications/<int:pk>/delete/", views.design_verification_delete, name="design_verification_delete"),
]
