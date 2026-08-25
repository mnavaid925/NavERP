"""Procurement 6.5 Sourcing & Tendering — analytics urlconf."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("", views.sourcing_analytics, name="sourcing_analytics"),
]
