"""HRM 3.35 Travel Management — Travelbooking URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("travel-requests/<int:travel_request_pk>/bookings/add/", views.travelbooking_add, name="travelbooking_add"),
    path("travel-bookings/<int:pk>/edit/", views.travelbooking_edit, name="travelbooking_edit"),
    path("travel-bookings/<int:pk>/delete/", views.travelbooking_delete, name="travelbooking_delete"),
]
