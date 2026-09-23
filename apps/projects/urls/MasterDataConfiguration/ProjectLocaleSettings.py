"""Projects 7.19 — ProjectLocaleSetting URLs."""
from django.urls import path

from apps.projects.views.MasterDataConfiguration import ProjectLocaleSettings as views

urlpatterns = [
    path("master-data/locale-settings/", views.pls_list, name="pls_list"),
    path("master-data/locale-settings/add/", views.pls_create, name="pls_create"),
    path("master-data/locale-settings/<int:pk>/", views.pls_detail, name="pls_detail"),
    path("master-data/locale-settings/<int:pk>/edit/", views.pls_edit, name="pls_edit"),
    path("master-data/locale-settings/<int:pk>/delete/", views.pls_delete, name="pls_delete"),
    path("master-data/locale-settings/<int:pk>/set-default/", views.pls_set_default, name="pls_set_default"),
]
