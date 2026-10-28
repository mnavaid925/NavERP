"""URL patterns for SalesRegionalSetting entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration import SalesRegionalSettings as views

urlpatterns = [
    path("master-data/regional-settings/", views.srg_list, name="srg_list"),
    path("master-data/regional-settings/create/", views.srg_create, name="srg_create"),
    path("master-data/regional-settings/<int:pk>/", views.srg_detail, name="srg_detail"),
    path("master-data/regional-settings/<int:pk>/edit/", views.srg_edit, name="srg_edit"),
    path("master-data/regional-settings/<int:pk>/delete/", views.srg_delete, name="srg_delete"),
]
