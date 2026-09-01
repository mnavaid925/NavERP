"""Procurement 6.15 Budget & Cost Management — Commitment Register URL pattern.

One GET route, ``commitments/`` — a read-only union of open purchase orders and approved
requisitions, so there is no ``add/``/``<int:pk>/`` family (the rows link OUT to scm's purchase
orders and this app's requisitions). The segment is collision-checked as a whole component
against the concatenated ``urls/__init__.py`` inventory.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("commitments/", views.commitment_register, name="commitment_register"),
]
