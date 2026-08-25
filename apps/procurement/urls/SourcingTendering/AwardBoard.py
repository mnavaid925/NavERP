"""Procurement 6.5 Sourcing & Tendering — award board + analytics urlconf."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("", views.award_board, name="award_board"),
]
