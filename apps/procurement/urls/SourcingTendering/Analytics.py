"""Procurement 6.5 Sourcing & Tendering — analytics urlconf (``analytics/`` prefix)."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("analytics/", views.sourcing_analytics, name="sourcing_analytics"),
]
