"""URL patterns for SalesMethodology entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration import SalesMethodologies as views

urlpatterns = [
    path("master-data/methodologies/", views.smd_list, name="smd_list"),
    path("master-data/methodologies/create/", views.smd_create, name="smd_create"),
    path("master-data/methodologies/<int:pk>/", views.smd_detail, name="smd_detail"),
    path("master-data/methodologies/<int:pk>/edit/", views.smd_edit, name="smd_edit"),
    path("master-data/methodologies/<int:pk>/delete/", views.smd_delete, name="smd_delete"),
]
