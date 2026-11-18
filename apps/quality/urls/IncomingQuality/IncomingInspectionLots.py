from django.urls import path

from apps.quality.views.IncomingQuality.IncomingInspectionLots import (
    incoming_inspection_lot_create,
    incoming_inspection_lot_delete,
    incoming_inspection_lot_detail,
    incoming_inspection_lot_edit,
    incoming_inspection_lot_export,
    incoming_inspection_lot_list,
    incoming_inspection_lot_make_decision,
    incoming_inspection_lot_record_sample,
)

urlpatterns = [
    path("iqc/lots/", incoming_inspection_lot_list, name="incoming_inspection_lot_list"),
    path("iqc/lots/create/", incoming_inspection_lot_create, name="incoming_inspection_lot_create"),
    path("iqc/lots/export/", incoming_inspection_lot_export, name="incoming_inspection_lot_export"),
    path("iqc/lots/<int:pk>/", incoming_inspection_lot_detail, name="incoming_inspection_lot_detail"),
    path("iqc/lots/<int:pk>/edit/", incoming_inspection_lot_edit, name="incoming_inspection_lot_edit"),
    path("iqc/lots/<int:pk>/delete/", incoming_inspection_lot_delete, name="incoming_inspection_lot_delete"),
    path("iqc/lots/<int:pk>/sample/", incoming_inspection_lot_record_sample, name="incoming_inspection_lot_record_sample"),
    path("iqc/lots/<int:pk>/decision/", incoming_inspection_lot_make_decision, name="incoming_inspection_lot_make_decision"),
]
