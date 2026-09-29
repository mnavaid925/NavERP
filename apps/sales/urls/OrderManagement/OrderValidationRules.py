"""Sales 8.6 — URLs for the typed order-validation rule set.

Five routes under ``orders/validation-rules/``. The literal routes (``''`` and ``create/``)
come FIRST: Django resolves first-match-wins, so a ``<int:pk>`` route listed above them would
be harmless here but the ordering is the house rule for a reason — 8.5's greedy
``quotes/portal/<str:token>/`` is exactly what a literal route placed late can fall into.

None of these patterns can be captured by another module's route: every one begins with the
literal segment ``orders/``, which was verified free against all sixteen mounted ``sales:``
prefixes at contract time.
"""
from django.urls import path

from apps.sales.views.OrderManagement.OrderValidationRules import (
    order_validation_rule_create,
    order_validation_rule_delete,
    order_validation_rule_detail,
    order_validation_rule_edit,
    order_validation_rule_list,
)


urlpatterns = [
    path(
        "orders/validation-rules/",
        order_validation_rule_list,
        name="order_validation_rule_list",
    ),
    path(
        "orders/validation-rules/create/",
        order_validation_rule_create,
        name="order_validation_rule_create",
    ),
    path(
        "orders/validation-rules/<int:pk>/",
        order_validation_rule_detail,
        name="order_validation_rule_detail",
    ),
    path(
        "orders/validation-rules/<int:pk>/edit/",
        order_validation_rule_edit,
        name="order_validation_rule_edit",
    ),
    path(
        "orders/validation-rules/<int:pk>/delete/",
        order_validation_rule_delete,
        name="order_validation_rule_delete",
    ),
]
