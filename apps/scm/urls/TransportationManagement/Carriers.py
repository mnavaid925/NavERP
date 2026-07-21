"""SCM 4.6 Transportation Management System — Carrier routes (prefix ``carriers/``).

Prefix is unique within the concatenated scm urlconf (``orders/``/``sales-orders/`` are taken).
Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("carriers/", views.carrier_list, name="carrier_list"),
    path("carriers/add/", views.carrier_create, name="carrier_create"),
    path("carriers/<int:pk>/", views.carrier_detail, name="carrier_detail"),
    path("carriers/<int:pk>/edit/", views.carrier_edit, name="carrier_edit"),
    path("carriers/<int:pk>/delete/", views.carrier_delete, name="carrier_delete"),
    path("carriers/<int:pk>/recompute-scorecard/", views.carrier_recompute_scorecard,
         name="carrier_recompute_scorecard"),
]
