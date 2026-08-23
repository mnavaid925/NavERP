"""Inventory 5.7 Stock Movement & Transfers — StockTransfer governance routes (``transfers/``).

The lifecycle verbs are literal segments BEFORE the ``<int:pk>`` routes, and each ends
in its own token, so none can shadow the panel pattern. The board root is ``""`` — the
sub-module's landing register.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("transfers/", views.transfer_board, name="transfer_board"),
    path("transfers/queue/", views.transfer_queue, name="transfer_queue"),
    path("transfers/<int:pk>/panel/", views.transfer_detail_panel, name="transfer_panel"),
    path("transfers/<int:pk>/submit/", views.transfer_submit, name="transfer_submit"),
    path("transfers/<int:pk>/decide/<int:tier>/approve/",
         views.transfer_tier_approve, name="transfer_tier_approve"),
    path("transfers/<int:pk>/decide/<int:tier>/reject/",
         views.transfer_tier_reject, name="transfer_tier_reject"),
]
