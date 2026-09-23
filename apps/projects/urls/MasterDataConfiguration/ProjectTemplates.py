"""Projects 7.19 — ProjectTemplate URLs."""
from django.urls import path

from apps.projects.views.MasterDataConfiguration import ProjectTemplates as views

urlpatterns = [
    path("master-data/templates/", views.ptm_list, name="ptm_list"),
    path("master-data/templates/add/", views.ptm_create, name="ptm_create"),
    path("master-data/templates/<int:pk>/", views.ptm_detail, name="ptm_detail"),
    path("master-data/templates/<int:pk>/edit/", views.ptm_edit, name="ptm_edit"),
    path("master-data/templates/<int:pk>/delete/", views.ptm_delete, name="ptm_delete"),
    path("master-data/templates/<int:pk>/instantiate/", views.ptm_instantiate, name="ptm_instantiate"),
]
