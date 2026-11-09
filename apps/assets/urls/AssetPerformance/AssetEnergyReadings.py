from django.urls import path

from apps.assets.views.AssetPerformance import AssetEnergyReadings as views

urlpatterns = [
    path("energy/", views.asset_energy_reading_list, name="asset_energy_reading_list"),
    path("energy/create/", views.asset_energy_reading_create, name="asset_energy_reading_create"),
    path("energy/<int:pk>/", views.asset_energy_reading_detail, name="asset_energy_reading_detail"),
    path("energy/<int:pk>/edit/", views.asset_energy_reading_edit, name="asset_energy_reading_edit"),
    path("energy/<int:pk>/delete/", views.asset_energy_reading_delete, name="asset_energy_reading_delete"),
    path("energy/<int:pk>/validate/", views.asset_energy_reading_validate, name="asset_energy_reading_validate"),
]
