from django.urls import path

from apps.documents.views.SecurityAccessControl.DlpPolicies import (
    dlp_policy_create,
    dlp_policy_delete,
    dlp_policy_detail,
    dlp_policy_edit,
    dlp_policy_list,
)

urlpatterns = [
    path("dlp-policies/", dlp_policy_list, name="dlp_policy_list"),
    path("dlp-policies/create/", dlp_policy_create, name="dlp_policy_create"),
    path("dlp-policies/<int:pk>/", dlp_policy_detail, name="dlp_policy_detail"),
    path("dlp-policies/<int:pk>/edit/", dlp_policy_edit, name="dlp_policy_edit"),
    path("dlp-policies/<int:pk>/delete/", dlp_policy_delete, name="dlp_policy_delete"),
]
