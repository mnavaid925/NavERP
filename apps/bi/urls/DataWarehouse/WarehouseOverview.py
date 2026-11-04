from django.urls import path

from apps.bi.views.DataWarehouse import WarehouseOverview as views

urlpatterns = [
    path("warehouse-overview/", views.warehouse_overview, name="warehouse_overview"),
]
