"""SCM 4.3 Inventory Management — report URL patterns (computed, no CRUD)."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("valuation/", views.valuation_report, name="valuation_report"),
    path("reorder-alerts/", views.reorder_alerts, name="reorder_alerts"),
    path("stock-ledger/", views.stock_ledger, name="stock_ledger"),
    path("on-hand/", views.on_hand_by_location, name="on_hand_by_location"),
]
