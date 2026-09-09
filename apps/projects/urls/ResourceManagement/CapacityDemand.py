"""Projects 7.3 — the Capacity & Demand board route (computed page, no model; GET-only)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("capacity-demand/", views.capacity_demand, name="capacity_demand"),
]
