from django.urls import path

from apps.assets.views.AssetLeaseRental import AssetLeaseSchedules as views

urlpatterns = [
    path("lease-schedules/", views.asset_lease_schedule_list, name="asset_lease_schedule_list"),
    path("lease-schedules/create/", views.asset_lease_schedule_create, name="asset_lease_schedule_create"),
    path("lease-schedules/<int:pk>/", views.asset_lease_schedule_detail, name="asset_lease_schedule_detail"),
    path("lease-schedules/<int:pk>/edit/", views.asset_lease_schedule_edit, name="asset_lease_schedule_edit"),
    path("lease-schedules/<int:pk>/delete/", views.asset_lease_schedule_delete, name="asset_lease_schedule_delete"),
    path("lease-schedules/<int:pk>/mark-paid/", views.asset_lease_schedule_mark_paid, name="asset_lease_schedule_mark_paid"),
    path("lease-schedules/<int:pk>/accrue/", views.asset_lease_schedule_accrue, name="asset_lease_schedule_accrue"),
]
