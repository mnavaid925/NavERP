"""Sales 8.6 — URLs for the order hold workbench.

Twelve routes under ``orders/holds/``. The four literal routes (``''``, ``create/``,
``bulk-raise/`` and ``bulk-clear/``) come FIRST: Django resolves first-match-wins, so
``bulk-raise/`` listed below ``<int:pk>/`` would be captured as a pk lookup and 500 on
``int("bulk-raise")`` — 8.5's greedy ``quotes/portal/<str:token>/`` is exactly the class of
route a literal placed late falls into, and this module has two such literals.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``orders/``, verified free against all sixteen mounted ``sales:`` prefixes at
contract time.
"""
from django.urls import path

from apps.sales.views.OrderManagement.OrderHolds import (
    order_hold_bulk_clear,
    order_hold_bulk_raise,
    order_hold_checkout,
    order_hold_clear,
    order_hold_clear_and_submit,
    order_hold_create,
    order_hold_delete,
    order_hold_detail,
    order_hold_edit,
    order_hold_list,
    order_hold_raise,
    order_hold_release_checkout,
)


urlpatterns = [
    path(
        "orders/holds/",
        order_hold_list,
        name="order_hold_list",
    ),
    path(
        "orders/holds/create/",
        order_hold_create,
        name="order_hold_create",
    ),
    # The two bulk literals MUST precede the <int:pk> routes below.
    path(
        "orders/holds/bulk-raise/",
        order_hold_bulk_raise,
        name="order_hold_bulk_raise",
    ),
    path(
        "orders/holds/bulk-clear/",
        order_hold_bulk_clear,
        name="order_hold_bulk_clear",
    ),
    # Raises a hold set from an ORDER, not from a hold, so it keys on the order's id.
    path(
        "orders/raise/<int:order_id>/",
        order_hold_raise,
        name="order_hold_raise",
    ),
    path(
        "orders/holds/<int:pk>/",
        order_hold_detail,
        name="order_hold_detail",
    ),
    path(
        "orders/holds/<int:pk>/edit/",
        order_hold_edit,
        name="order_hold_edit",
    ),
    path(
        "orders/holds/<int:pk>/delete/",
        order_hold_delete,
        name="order_hold_delete",
    ),
    path(
        "orders/holds/<int:pk>/checkout/",
        order_hold_checkout,
        name="order_hold_checkout",
    ),
    path(
        "orders/holds/<int:pk>/release-checkout/",
        order_hold_release_checkout,
        name="order_hold_release_checkout",
    ),
    path(
        "orders/holds/<int:pk>/clear/",
        order_hold_clear,
        name="order_hold_clear",
    ),
    path(
        "orders/holds/<int:pk>/clear-and-submit/",
        order_hold_clear_and_submit,
        name="order_hold_clear_and_submit",
    ),
]
