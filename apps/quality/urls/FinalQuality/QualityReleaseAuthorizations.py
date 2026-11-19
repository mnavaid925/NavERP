from django.urls import path

from apps.quality.views.FinalQuality import QualityReleaseAuthorizations as views

urlpatterns = [
    path("quality-releases/", views.quality_release_authorization_list, name="quality_release_authorization_list"),
    path("quality-releases/create/", views.quality_release_authorization_create, name="quality_release_authorization_create"),
    path("quality-releases/export/", views.quality_release_authorization_export, name="quality_release_authorization_export"),
    path("quality-releases/<int:pk>/", views.quality_release_authorization_detail, name="quality_release_authorization_detail"),
    path("quality-releases/<int:pk>/edit/", views.quality_release_authorization_edit, name="quality_release_authorization_edit"),
    path("quality-releases/<int:pk>/delete/", views.quality_release_authorization_delete, name="quality_release_authorization_delete"),
    path("quality-releases/<int:pk>/toggle-hold/", views.quality_release_authorization_toggle_hold, name="quality_release_authorization_toggle_hold"),
]
