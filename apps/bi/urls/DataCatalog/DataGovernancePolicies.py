from django.urls import path

from apps.bi.views.DataCatalog.DataGovernancePolicies import (
    data_governance_policy_list,
    data_governance_policy_create,
    data_governance_policy_detail,
    data_governance_policy_edit,
    data_governance_policy_delete,
)

urlpatterns = [
    path("catalog/policies/", data_governance_policy_list, name="data_governance_policy_list"),
    path("catalog/policies/create/", data_governance_policy_create, name="data_governance_policy_create"),
    path("catalog/policies/<int:pk>/", data_governance_policy_detail, name="data_governance_policy_detail"),
    path("catalog/policies/<int:pk>/edit/", data_governance_policy_edit, name="data_governance_policy_edit"),
    path("catalog/policies/<int:pk>/delete/", data_governance_policy_delete, name="data_governance_policy_delete"),
]
