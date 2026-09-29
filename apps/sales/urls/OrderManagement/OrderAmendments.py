"""Sales 8.6 — URLs for the change order.

Thirteen routes under ``orders/amendments/``. Order inside the file is BEHAVIOUR, not style:
Django resolves first-match-wins, so the literal ``open/`` MUST precede ``<int:pk>/`` — listed
below it, ``int("open")`` raises ``ValueError`` and the queue is a 500 rather than a page. The
same class of bug is why 8.5's greedy ``quotes/portal/<str:token>/`` is the cautionary tale
everywhere in this sub-module.

The two line routes are NESTED under the parent (``<int:pk>/lines/<int:line_pk>/``) and there is
deliberately no route that takes a child pk alone. That is simultaneously the CRUD-completeness
answer (the child still has add / edit / delete) and the tenant-isolation guard: a line is only
ever reachable through the amendment that owns it, and the view re-fetches it through that
parent, so a line id from another workspace is a 404 rather than an edit.

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to
be phished; every POST redirects to a name this module owns.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``orders/amendments/``, verified free against the mounted ``sales:`` prefixes at
contract time.
"""
from django.urls import path

from apps.sales.views.OrderManagement.OrderAmendments import (
    order_amendment_apply,
    order_amendment_create,
    order_amendment_decide,
    order_amendment_delete,
    order_amendment_detail,
    order_amendment_edit,
    order_amendment_impact,
    order_amendment_line_add,
    order_amendment_line_delete,
    order_amendment_line_edit,
    order_amendment_list,
    order_amendment_open_queue,
    order_amendment_withdraw,
)


urlpatterns = [
    path(
        "orders/amendments/",
        order_amendment_list,
        name="order_amendment_list",
    ),
    path(
        "orders/amendments/create/",
        order_amendment_create,
        name="order_amendment_create",
    ),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path(
        "orders/amendments/open/",
        order_amendment_open_queue,
        name="order_amendment_open_queue",
    ),
    path(
        "orders/amendments/<int:pk>/",
        order_amendment_detail,
        name="order_amendment_detail",
    ),
    path(
        "orders/amendments/<int:pk>/edit/",
        order_amendment_edit,
        name="order_amendment_edit",
    ),
    path(
        "orders/amendments/<int:pk>/delete/",
        order_amendment_delete,
        name="order_amendment_delete",
    ),
    path(
        "orders/amendments/<int:pk>/impact/",
        order_amendment_impact,
        name="order_amendment_impact",
    ),
    path(
        "orders/amendments/<int:pk>/decide/",
        order_amendment_decide,
        name="order_amendment_decide",
    ),
    path(
        "orders/amendments/<int:pk>/apply/",
        order_amendment_apply,
        name="order_amendment_apply",
    ),
    path(
        "orders/amendments/<int:pk>/withdraw/",
        order_amendment_withdraw,
        name="order_amendment_withdraw",
    ),
    # The child routes are NESTED: no route anywhere takes a line pk on its own.
    path(
        "orders/amendments/<int:pk>/lines/add/",
        order_amendment_line_add,
        name="order_amendment_line_add",
    ),
    path(
        "orders/amendments/<int:pk>/lines/<int:line_pk>/edit/",
        order_amendment_line_edit,
        name="order_amendment_line_edit",
    ),
    path(
        "orders/amendments/<int:pk>/lines/<int:line_pk>/delete/",
        order_amendment_line_delete,
        name="order_amendment_line_delete",
    ),
]
