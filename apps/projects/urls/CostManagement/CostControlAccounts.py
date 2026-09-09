"""Projects 7.4 — CostControlAccount routes (prefix ``controlaccounts/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("controlaccounts/", views.cca_list, name="cca_list"),
    path("controlaccounts/add/", views.cca_create, name="cca_create"),
    path("controlaccounts/<int:pk>/", views.cca_detail, name="cca_detail"),
    path("controlaccounts/<int:pk>/edit/", views.cca_edit, name="cca_edit"),
    path("controlaccounts/<int:pk>/delete/", views.cca_delete, name="cca_delete"),
]
