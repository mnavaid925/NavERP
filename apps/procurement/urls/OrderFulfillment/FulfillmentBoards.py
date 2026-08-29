"""Procurement 6.11 Order Fulfillment & Tracking — computed board URL patterns.

Two literal single-segment routes, no kwargs, no ``<int:pk>`` to order against. ``inbound-tracking/``
and ``delivery-confirmation/`` are both NEW segments — distinct from 6.10's ``po-tracking/`` and
from every other segment the app registers — and the procurement URLconf still has no greedy
``<str:...>`` route that could shadow them (Django resolves first-match-wins).

Neither route mutates anything, so neither is POST-only: the delivery-confirmation board's inline
confirm form posts to ``procurement:asn_confirm_delivery`` instead of to a second confirm path.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("inbound-tracking/", views.inbound_tracking, name="inbound_tracking"),
    path("delivery-confirmation/", views.delivery_confirmation, name="delivery_confirmation"),
]
