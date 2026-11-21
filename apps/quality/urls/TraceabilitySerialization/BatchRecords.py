from django.urls import path

from apps.quality.views.TraceabilitySerialization import BatchRecords as views

urlpatterns = [
    path("traceability/batch-records/", views.batch_record_list, name="batch_record_list"),
    path("traceability/batch-records/create/", views.batch_record_create, name="batch_record_create"),
    path("traceability/batch-records/<int:pk>/", views.batch_record_detail, name="batch_record_detail"),
    path("traceability/batch-records/<int:pk>/edit/", views.batch_record_edit, name="batch_record_edit"),
    path("traceability/batch-records/<int:pk>/delete/", views.batch_record_delete, name="batch_record_delete"),
    path("traceability/batch-records/<int:pk>/release/", views.batch_record_release, name="batch_record_release"),
]
