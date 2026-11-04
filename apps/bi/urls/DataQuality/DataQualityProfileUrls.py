from django.urls import path

from apps.bi.views.DataQuality import DataQualityProfiles as views

urlpatterns = [
    path("data-quality/profiles/", views.data_quality_profile_list, name="data_quality_profile_list"),
    path("data-quality/profiles/create/", views.data_quality_profile_create, name="data_quality_profile_create"),
    path("data-quality/profiles/<int:pk>/", views.data_quality_profile_detail, name="data_quality_profile_detail"),
    path("data-quality/profiles/<int:pk>/edit/", views.data_quality_profile_edit, name="data_quality_profile_edit"),
    path("data-quality/profiles/<int:pk>/delete/", views.data_quality_profile_delete, name="data_quality_profile_delete"),
    path("data-quality/profiles/<int:pk>/run/", views.data_quality_profile_run, name="data_quality_profile_run"),
]
