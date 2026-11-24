from django.urls import path

from apps.documents.views.RecordsManagement import RetentionSchedules as views

urlpatterns = [
    path("records/schedules/", views.retention_schedule_list, name="retention_schedule_list"),
    path("records/schedules/create/", views.retention_schedule_create, name="retention_schedule_create"),
    path("records/schedules/<int:pk>/", views.retention_schedule_detail, name="retention_schedule_detail"),
    path("records/schedules/<int:pk>/edit/", views.retention_schedule_edit, name="retention_schedule_edit"),
    path("records/schedules/<int:pk>/delete/", views.retention_schedule_delete, name="retention_schedule_delete"),
]
