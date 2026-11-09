from django.urls import path

from apps.assets.views.AssetDepreciation.AssetDepreciationSchedules import (
    depreciation_schedule_calculate,
    depreciation_schedule_create,
    depreciation_schedule_delete,
    depreciation_schedule_detail,
    depreciation_schedule_edit,
    depreciation_schedule_list,
    depreciation_schedule_post,
)

urlpatterns = [
    path("depreciation/", depreciation_schedule_list, name="depreciation_schedule_list"),
    path("depreciation/create/", depreciation_schedule_create, name="depreciation_schedule_create"),
    path("depreciation/<int:pk>/", depreciation_schedule_detail, name="depreciation_schedule_detail"),
    path("depreciation/<int:pk>/edit/", depreciation_schedule_edit, name="depreciation_schedule_edit"),
    path("depreciation/<int:pk>/delete/", depreciation_schedule_delete, name="depreciation_schedule_delete"),
    path("depreciation/<int:pk>/calculate/", depreciation_schedule_calculate, name="depreciation_schedule_calculate"),
    path("depreciation/<int:pk>/post/", depreciation_schedule_post, name="depreciation_schedule_post"),
]
