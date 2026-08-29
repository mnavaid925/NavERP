"""Procurement 6.11 Order Fulfillment & Tracking — DeliverySchedule URL patterns.

**Split Delivery Management**: the instalment register plus the split console.

Django is FIRST-MATCH-WINS, so the literal ``add/`` and ``split/`` routes are declared BEFORE
``<int:pk>/``. (Neither literal would in fact convert as an int, so the ordering costs nothing
today — but the rule is behaviour, not decoration: the moment a ``<str:…>`` segment is added
anywhere in the concatenated procurement urlconf, declaration order is the only thing standing
between these pages and a wrong match.)

The ``delivery-schedules/`` first segment is NEW and distinct from every existing procurement
segment, and the app still has no greedy ``<str:…>`` route that could shadow it.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("delivery-schedules/", views.deliveryschedule_list, name="deliveryschedule_list"),
    path("delivery-schedules/add/", views.deliveryschedule_create,
         name="deliveryschedule_create"),
    path("delivery-schedules/split/", views.deliveryschedule_split,
         name="deliveryschedule_split"),
    path("delivery-schedules/<int:pk>/", views.deliveryschedule_detail,
         name="deliveryschedule_detail"),
    path("delivery-schedules/<int:pk>/edit/", views.deliveryschedule_edit,
         name="deliveryschedule_edit"),
    path("delivery-schedules/<int:pk>/delete/", views.deliveryschedule_delete,
         name="deliveryschedule_delete"),
]
