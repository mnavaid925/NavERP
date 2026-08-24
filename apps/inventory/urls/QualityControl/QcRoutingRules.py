"""Inventory 5.15 — QcRoutingRule URL patterns (prefix ``qc-routing-rules/``).

Literal routes precede the ``<int:pk>`` ones (first-match-wins).
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("qc-routing-rules/", views.qcroutingrule_list, name="qcroutingrule_list"),
    path("qc-routing-rules/add/", views.qcroutingrule_create, name="qcroutingrule_create"),
    path("qc-routing-rules/<int:pk>/", views.qcroutingrule_detail, name="qcroutingrule_detail"),
    path("qc-routing-rules/<int:pk>/edit/", views.qcroutingrule_edit, name="qcroutingrule_edit"),
    path("qc-routing-rules/<int:pk>/delete/", views.qcroutingrule_delete, name="qcroutingrule_delete"),
]
