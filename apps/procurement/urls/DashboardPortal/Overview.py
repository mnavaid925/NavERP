"""Procurement 6.1 User Dashboard & Portal — the module landing page.

The landing route is "" so /procurement/ IS the personalized overview. Widget customization
POSTs back to this same URL — no separate settings route to get lost.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
