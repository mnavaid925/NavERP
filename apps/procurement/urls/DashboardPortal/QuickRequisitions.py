"""Procurement 6.1 User Dashboard & Portal — Quick Requisition Entry route."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("quick-requisition/", views.quickreq_create, name="quickreq_create"),
]
