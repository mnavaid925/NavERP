"""Procurement 6.5 Sourcing & Tendering — SourcingBid urlconf.

``bids/`` prefix: see SourcingEvents.py — the concatenated app urlconf is first-match-wins,
so unprefixed literal segments would collide with (or be shadowed by) sibling entities.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("bids/", views.bid_list, name="bid_list"),
    path("bids/add/", views.bid_create, name="bid_create"),
    path("bids/<int:pk>/", views.bid_detail, name="bid_detail"),
    path("bids/<int:pk>/edit/", views.bid_edit, name="bid_edit"),
    path("bids/<int:pk>/delete/", views.bid_delete, name="bid_delete"),
    path("bids/<int:pk>/submit/", views.bid_submit, name="bid_submit"),
    path("bids/<int:pk>/shortlist/", views.bid_shortlist, name="bid_shortlist"),
    path("bids/<int:pk>/disqualify/", views.bid_disqualify, name="bid_disqualify"),
]
