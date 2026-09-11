"""Projects 7.6 — the Continuous Improvement board route (prefix ``quality-improvement/``).

A computed page — GET-only, no model behind it (the 7.3 ``capacity-demand`` / 7.5
``risk-analysis`` precedent). The first segment is a disjoint literal from every other module's
in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("quality-improvement/", views.quality_improvement, name="quality_improvement"),
]
