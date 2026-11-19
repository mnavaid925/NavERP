from django.urls import path

from apps.quality.views.FinalQuality import FinalInspectionLots as views

urlpatterns = [
    path("final-inspections/", views.final_inspection_lot_list, name="final_inspection_lot_list"),
    path("final-inspections/create/", views.final_inspection_lot_create, name="final_inspection_lot_create"),
    path("final-inspections/export/", views.final_inspection_lot_export, name="final_inspection_lot_export"),
    path("final-inspections/<int:pk>/", views.final_inspection_lot_detail, name="final_inspection_lot_detail"),
    path("final-inspections/<int:pk>/edit/", views.final_inspection_lot_edit, name="final_inspection_lot_edit"),
    path("final-inspections/<int:pk>/delete/", views.final_inspection_lot_delete, name="final_inspection_lot_delete"),
    path("final-inspections/<int:pk>/toggle-hold/", views.final_inspection_lot_toggle_hold, name="final_inspection_lot_toggle_hold"),
]
