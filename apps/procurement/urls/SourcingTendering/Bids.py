"""Procurement 6.5 Sourcing & Tendering — SourcingBid urlconf."""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("", views.bid_list, name="bid_list"),
    path("add/", views.bid_create, name="bid_create"),
    path("<int:pk>/", views.bid_detail, name="bid_detail"),
    path("<int:pk>/edit/", views.bid_edit, name="bid_edit"),
    path("<int:pk>/delete/", views.bid_delete, name="bid_delete"),
    path("<int:pk>/submit/", views.bid_submit, name="bid_submit"),
    path("<int:pk>/shortlist/", views.bid_shortlist, name="bid_shortlist"),
    path("<int:pk>/disqualify/", views.bid_disqualify, name="bid_disqualify"),
]
