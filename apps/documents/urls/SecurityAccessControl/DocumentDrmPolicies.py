from django.urls import path

from apps.documents.views.SecurityAccessControl.DocumentDrmPolicies import (
    drm_kill_switch,
    drm_policy_create,
    drm_policy_delete,
    drm_policy_detail,
    drm_policy_edit,
    drm_policy_list,
)

urlpatterns = [
    path("drm-policies/", drm_policy_list, name="drm_policy_list"),
    path("drm-policies/create/", drm_policy_create, name="drm_policy_create"),
    path("drm-policies/<int:pk>/", drm_policy_detail, name="drm_policy_detail"),
    path("drm-policies/<int:pk>/edit/", drm_policy_edit, name="drm_policy_edit"),
    path("drm-policies/<int:pk>/delete/", drm_policy_delete, name="drm_policy_delete"),
    path("drm-policies/<int:pk>/kill-switch/", drm_kill_switch, name="drm_kill_switch"),
]
