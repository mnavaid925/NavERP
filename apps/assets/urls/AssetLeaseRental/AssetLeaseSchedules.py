from django.urls import path

from apps.assets.views.AssetLeaseRental import AssetLeaseSchedules as views

urlpatterns = [
    path("schedules/", views.asset_lease_schedule_list, name="asset_lease_schedule_list"),
    path("schedules/create/", views.asset_lease_schedule_create, name="asset_lease_schedule_create"),
    path("schedules/<int:pk>/", views.asset_lease_schedule_detail, name="asset_lease_schedule_detail"),
    path("schedules/<int:pk>/edit/", views.asset_lease_schedule_edit, name="asset_lease_schedule_edit"),
    path("schedules/<int:pk>/delete/", views.asset_lease_schedule_delete, name="asset_lease_schedule_delete"),
    path("schedules/<int:pk>/mark-paid/", views.asset_lease_schedule_mark_paid, name="asset_lease_schedule_mark_paid"),
    path("schedules/<int:pk>/accrue/", views.asset_lease_schedule_accrue, name="asset_lease_schedule_accrue"),
]
