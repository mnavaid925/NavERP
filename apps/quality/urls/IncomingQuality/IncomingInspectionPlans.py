from django.urls import path

from apps.quality.views.IncomingQuality.IncomingInspectionPlans import (
    incoming_inspection_plan_create,
    incoming_inspection_plan_delete,
    incoming_inspection_plan_detail,
    incoming_inspection_plan_edit,
    incoming_inspection_plan_export,
    incoming_inspection_plan_list,
)

urlpatterns = [
    path("iqc/plans/", incoming_inspection_plan_list, name="incoming_inspection_plan_list"),
    path("iqc/plans/create/", incoming_inspection_plan_create, name="incoming_inspection_plan_create"),
    path("iqc/plans/export/", incoming_inspection_plan_export, name="incoming_inspection_plan_export"),
    path("iqc/plans/<int:pk>/", incoming_inspection_plan_detail, name="incoming_inspection_plan_detail"),
    path("iqc/plans/<int:pk>/edit/", incoming_inspection_plan_edit, name="incoming_inspection_plan_edit"),
    path("iqc/plans/<int:pk>/delete/", incoming_inspection_plan_delete, name="incoming_inspection_plan_delete"),
]
