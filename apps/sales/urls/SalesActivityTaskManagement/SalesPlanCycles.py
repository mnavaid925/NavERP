"""Sales 8.8 — URLs for the plan-cycle register and the three read-only boards.

Seven routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR**: the literal ``plan-cycles/add/`` MUST
precede ``plan-cycles/<int:pk>/``, and ``plan-cycles/goals/<int:goal_pk>/delete/`` must precede
``plan-cycles/<int:pk>/`` — otherwise ``<int:pk>`` claims ``goals`` and raises ``ValueError``.

The two verbs — ``toggle/`` and ``goals/<goal_pk>/delete/`` — plus ``goals/add/`` are **POST-only** in
the views. ``toggle/`` closes or re-opens a period and is the writer of the system-set ``closed_at``
column.

The three board routes are at the top level of the module (``plan/``, ``next-best-actions/``,
``email-engagement/``) rather than under an entity prefix, because a board belongs to no single
model. Their literals are verified free against the whole concatenated ``sales:urlpatterns`` list.
"""
from django.urls import path

from apps.sales.views.SalesActivityTaskManagement.Boards import (
    sales_activity_plan,
    sales_email_engagement,
    sales_next_best_actions,
)
from apps.sales.views.SalesActivityTaskManagement.SalesPlanCycles import (
    sales_plan_cycle_create,
    sales_plan_cycle_delete,
    sales_plan_cycle_detail,
    sales_plan_cycle_edit,
    sales_plan_cycle_list,
    sales_plan_cycle_toggle,
    sales_plan_goal_add,
    sales_plan_goal_delete,
)

urlpatterns = [
    # ---- the three read-only boards, first: they carry no pk and no siblings to shadow ----
    path("plan/", sales_activity_plan, name="sales_activity_plan"),
    path("next-best-actions/", sales_next_best_actions, name="sales_next_best_actions"),
    path("email-engagement/", sales_email_engagement, name="sales_email_engagement"),
    # ---- the plan-cycle register ----
    path("plan-cycles/", sales_plan_cycle_list, name="sales_plan_cycle_list"),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path("plan-cycles/add/", sales_plan_cycle_create, name="sales_plan_cycle_create"),
    path("plan-cycles/<int:pk>/goals/add/", sales_plan_goal_add, name="sales_plan_goal_add"),
    # The nested goal delete must precede the bare <int:pk>/ detail route.
    path(
        "plan-cycles/<int:pk>/goals/<int:goal_pk>/delete/",
        sales_plan_goal_delete,
        name="sales_plan_goal_delete",
    ),
    path("plan-cycles/<int:pk>/toggle/", sales_plan_cycle_toggle, name="sales_plan_cycle_toggle"),
    path("plan-cycles/<int:pk>/edit/", sales_plan_cycle_edit, name="sales_plan_cycle_edit"),
    path("plan-cycles/<int:pk>/delete/", sales_plan_cycle_delete, name="sales_plan_cycle_delete"),
    path("plan-cycles/<int:pk>/", sales_plan_cycle_detail, name="sales_plan_cycle_detail"),
]