from django.urls import path

from apps.assets.views.AssetDepreciation.CapitalizationPolicies import (
    capitalization_policy_create,
    capitalization_policy_delete,
    capitalization_policy_detail,
    capitalization_policy_edit,
    capitalization_policy_list,
)

urlpatterns = [
    path("capitalization-policies/", capitalization_policy_list, name="capitalization_policy_list"),
    path("capitalization-policies/create/", capitalization_policy_create, name="capitalization_policy_create"),
    path("capitalization-policies/<int:pk>/", capitalization_policy_detail, name="capitalization_policy_detail"),
    path("capitalization-policies/<int:pk>/edit/", capitalization_policy_edit, name="capitalization_policy_edit"),
    path("capitalization-policies/<int:pk>/delete/", capitalization_policy_delete, name="capitalization_policy_delete"),
]
