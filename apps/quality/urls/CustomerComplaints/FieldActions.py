from django.urls import path

from apps.quality.views.CustomerComplaints import FieldActions as views

urlpatterns = [
    path("field-actions/", views.field_action_list, name="field_action_list"),
    path("field-actions/create/", views.field_action_create, name="field_action_create"),
    path("field-actions/export/csv/", views.field_action_export_csv, name="field_action_export_csv"),
    path("field-actions/<int:pk>/", views.field_action_detail, name="field_action_detail"),
    path("field-actions/<int:pk>/edit/", views.field_action_edit, name="field_action_edit"),
    path("field-actions/<int:pk>/delete/", views.field_action_delete, name="field_action_delete"),
    path("field-actions/<int:pk>/close/", views.field_action_close, name="field_action_close"),
]
