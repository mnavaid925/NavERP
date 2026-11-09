from django.urls import path

from apps.assets.views.AssetDepreciation.AssetRevaluations import (
    revaluation_approve,
    revaluation_create,
    revaluation_delete,
    revaluation_detail,
    revaluation_edit,
    revaluation_list,
)

urlpatterns = [
    path("revaluations/", revaluation_list, name="revaluation_list"),
    path("revaluations/create/", revaluation_create, name="revaluation_create"),
    path("revaluations/<int:pk>/", revaluation_detail, name="revaluation_detail"),
    path("revaluations/<int:pk>/edit/", revaluation_edit, name="revaluation_edit"),
    path("revaluations/<int:pk>/delete/", revaluation_delete, name="revaluation_delete"),
    path("revaluations/<int:pk>/approve/", revaluation_approve, name="revaluation_approve"),
]
