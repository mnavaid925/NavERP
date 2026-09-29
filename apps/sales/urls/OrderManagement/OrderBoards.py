"""Sales 8.6 — URLs for the seven boards and their three POST verbs.

Ten routes, and the ORDER INSIDE THIS FILE IS BEHAVIOUR, not style. Django resolves
first-match-wins, so **every literal route is listed before every ``<int:…>`` route**. The seven
literals — ``orders/``, ``orders/fulfillment/``, ``orders/history/``, ``orders/reorder/``,
``orders/renewals/``, ``orders/recognition-board/`` and the two verb prefixes — all come first, and
only then do ``orders/timeline/<int:pk>/``, ``orders/validate/<int:order_pk>/``,
``orders/repeat/<int:pk>/`` and ``orders/backorders/<int:allocation_pk>/resolve/`` follow. Listed the
other way round, ``orders/reorder/`` would be captured by a sibling ``<int:pk>`` and raise
``ValueError`` inside ``int()`` — a 500 rather than a page. 8.5's greedy
``quotes/portal/<str:token>/`` is the cautionary tale this whole sub-module is written against.

**This module is concatenated FIRST** into ``apps/sales/urls/OrderManagement/__init__.py``, ahead of
the four entity modules, precisely because it carries the literals. That is the 8.5
``QuoteOperations``-first precedent, and it is the reason ``orders/holds/bulk-raise/`` (in a
different module) still cannot be shadowed by anything here.

The three verbs are POST-only. ``order_backorder_resolve`` releases or cancels a customer's stock
reservation, ``order_repeat`` creates a customer order, and ``order_validate`` runs every
validation rule in the workspace — a GET that did any of those would let a prefetch, a crawler or a
link preview perform it by touching a URL.

**The prefix segments are distinct on purpose.** ``orders/repeat/<int:pk>/`` and
``orders/validate/<int:order_pk>/`` both key on an order id, and they are separate prefixes rather
than one ``orders/<int:pk>/…`` tree: an action hung off a bare order pk would be indistinguishable
from a detail route, and a future ``orders/<int:pk>/`` list route would swallow both.

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to be
phished; every POST here redirects to a name this file owns or to ``scm:``, which 4.5 owns.

No pattern here can be captured by another module's route: every one begins with the literal segment
``orders/``, verified free against all sixteen mounted ``sales:`` prefixes at contract time, and
re-checked against the whole concatenated ``sales:urlpatterns`` list.
"""
from django.urls import path

from apps.sales.views.OrderManagement.OrderBoards import (
    order_backorder_resolve,
    order_capture_board,
    order_fulfillment_board,
    order_history_board,
    order_repeat,
    order_timeline,
    order_validate,
    renewals_due_board,
    reorder_customers_board,
    revenue_recognition_board,
)


urlpatterns = [
    # ---- the seven literal board routes. ALL OF THEM PRECEDE EVERY <int:…> BELOW. ----
    path(
        "orders/",
        order_capture_board,
        name="order_capture_board",
    ),
    path(
        "orders/fulfillment/",
        order_fulfillment_board,
        name="order_fulfillment_board",
    ),
    path(
        "orders/history/",
        order_history_board,
        name="order_history_board",
    ),
    path(
        "orders/reorder/",
        reorder_customers_board,
        name="reorder_customers_board",
    ),
    path(
        "orders/renewals/",
        renewals_due_board,
        name="renewals_due_board",
    ),
    path(
        "orders/recognition-board/",
        revenue_recognition_board,
        name="revenue_recognition_board",
    ),
    # ---- the three POST verbs, each on its own literal prefix ----
    path(
        "orders/validate/<int:order_pk>/",
        order_validate,
        name="order_validate",
    ),
    path(
        "orders/repeat/<int:pk>/",
        order_repeat,
        name="order_repeat",
    ),
    path(
        "orders/backorders/<int:allocation_pk>/resolve/",
        order_backorder_resolve,
        name="order_backorder_resolve",
    ),
    # ---- the only keyed board route, last because it is the only <int:…> that is a PAGE ----
    path(
        "orders/timeline/<int:pk>/",
        order_timeline,
        name="order_timeline",
    ),
]