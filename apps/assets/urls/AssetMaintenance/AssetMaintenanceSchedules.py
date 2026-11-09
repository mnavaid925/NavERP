from django.urls import path

from apps.assets.views.AssetMaintenance import AssetMaintenanceSchedules as views

urlpatterns = [
    path("schedules/", views.asset_maintenance_schedule_list, name="asset_maintenance_schedule_list"),
    path("schedules/create/", views.asset_maintenance_schedule_create, name="asset_maintenance_schedule_create"),
    path("schedules/<int:pk>/", views.asset_maintenance_schedule_detail, name="asset_maintenance_schedule_detail"),
    path("schedules/<int:pk>/edit/", views.asset_maintenance_schedule_edit, name="asset_maintenance_schedule_edit"),
    path("schedules/<int:pk>/delete/", views.asset_maintenance_schedule_delete, name="asset_maintenance_schedule_delete"),
    path("schedules/<int:pk>/activate/", views.asset_maintenance_schedule_activate, name="asset_maintenance_schedule_activate"),
    path("schedules/<int:pk>/pause/", views.asset_maintenance_schedule_pause, name="asset_maintenance_schedule_pause"),
    path("schedules/<int:pk>/generate-request/", views.asset_maintenance_schedule_generate_request, name="asset_maintenance_schedule_generate_request"),
    path("schedules/<int:pk>/record-completion/", views.asset_maintenance_schedule_record_completion, name="asset_maintenance_schedule_record_completion"),
]
