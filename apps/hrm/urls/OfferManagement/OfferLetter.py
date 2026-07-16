"""HRM 3.8 Offer Management — OfferLetter URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("offers/<int:pk>/letter/", views.offer_letter_print, name="offer_letter_print"),
]
