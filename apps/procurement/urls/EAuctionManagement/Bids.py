"""Procurement 6.7 E-Auction Management — bidding + award URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("eauc/<int:pk>/bid/", views.eauc_bid, name="eauc_bid"),
    path("eauc/<int:pk>/results/", views.eauc_results, name="eauc_results"),
    path("eauc/<int:pk>/award/", views.eauc_award, name="eauc_award"),
]
