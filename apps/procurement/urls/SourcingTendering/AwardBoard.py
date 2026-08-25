"""Procurement 6.5 Sourcing & Tendering — award board urlconf (``awards/`` prefix)."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("awards/", views.award_board, name="award_board"),
]
