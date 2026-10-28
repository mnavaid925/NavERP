"""URL patterns for SalesCustomEntityDefinition entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration import SalesCustomEntityDefinitions as views

urlpatterns = [
    path("master-data/custom-entities/", views.sco_list, name="sco_list"),
    path("master-data/custom-entities/create/", views.sco_create, name="sco_create"),
    path("master-data/custom-entities/<int:pk>/", views.sco_detail, name="sco_detail"),
    path("master-data/custom-entities/<int:pk>/edit/", views.sco_edit, name="sco_edit"),
    path("master-data/custom-entities/<int:pk>/delete/", views.sco_delete, name="sco_delete"),
]
