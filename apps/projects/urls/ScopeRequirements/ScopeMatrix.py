"""Projects 7.7 — the computed scope-matrix route (prefix ``scope-matrix/``).

No model, no entity: the traceability matrix and the creep board are computed over the requirement
and change registers (the 7.3 ``capacity-demand/`` / 7.5 ``risk-analysis/`` precedent). The first
segment is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("scope-matrix/", views.scope_matrix, name="scope_matrix"),
]
