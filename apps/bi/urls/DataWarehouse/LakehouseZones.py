from django.urls import path

from apps.bi.views.DataWarehouse import LakehouseZones as views

urlpatterns = [
    path("lakehouse-zones/", views.lakehouse_zone_list, name="lakehouse_zone_list"),
    path("lakehouse-zones/create/", views.lakehouse_zone_create, name="lakehouse_zone_create"),
    path("lakehouse-zones/<int:pk>/", views.lakehouse_zone_detail, name="lakehouse_zone_detail"),
    path("lakehouse-zones/<int:pk>/edit/", views.lakehouse_zone_edit, name="lakehouse_zone_edit"),
    path("lakehouse-zones/<int:pk>/delete/", views.lakehouse_zone_delete, name="lakehouse_zone_delete"),
]
