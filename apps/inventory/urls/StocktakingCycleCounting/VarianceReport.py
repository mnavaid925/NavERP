"""Inventory 5.11 Stocktaking & Cycle Counting — variance report route (computed page)."""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("variance-report/", views.variance_report, name="variance_report"),
]
