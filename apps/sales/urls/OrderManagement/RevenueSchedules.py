"""Sales 8.6 — URLs for the revenue register.

Nine routes under ``orders/revenue-schedules/``. Order inside the file is BEHAVIOUR, not style:
Django resolves first-match-wins, so the two LITERAL segments (``create/`` and
``obligations/add/``) MUST precede the ``<int:pk>/`` routes — listed below those, ``int("create")``
raises ``ValueError`` and the page is a 500 rather than a form. The same class of bug is why
8.5's greedy ``quotes/portal/<str:token>/`` is the cautionary tale everywhere in this sub-module.

The three obligation routes are NESTED under the parent (``<int:pk>/obligations/<int:obligation_pk>/``)
and there is deliberately no route that takes a child pk alone. That is simultaneously the
CRUD-completeness answer (the child still has add / edit / delete) and the tenant-isolation
guard: an obligation is only ever reachable through the schedule that owns it, and the view
re-fetches it through that parent, so an obligation id from another workspace is a 404 rather
than an edit. ``scm.SalesOrderAllocation`` is a tenant-less-adjacent SCM row with a related
name of its own; nothing here reaches it by URL.

``revenue_schedule_recognize`` is the one route that moves money, and it is POST-only — a GET
that recognises revenue would let a prefetch, a crawler or a link preview recognise a customer's
revenue by touching a URL.

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to be
phished; every POST redirects to a name this module owns.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``orders/revenue-schedules/``, verified free against the mounted ``sales:`` prefixes at
contract time.
"""
from django.urls import path

from apps.sales.views.OrderManagement.RevenueSchedules import (
    revenue_schedule_create,
    revenue_schedule_delete,
    revenue_schedule_detail,
    revenue_schedule_edit,
    revenue_schedule_list,
    revenue_schedule_obligation_add,
    revenue_schedule_obligation_delete,
    revenue_schedule_obligation_edit,
    revenue_schedule_recognize,
)


urlpatterns = [
    path(
        "orders/revenue-schedules/",
        revenue_schedule_list,
        name="revenue_schedule_list",
    ),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path(
        "orders/revenue-schedules/create/",
        revenue_schedule_create,
        name="revenue_schedule_create",
    ),
    path(
        "orders/revenue-schedules/<int:pk>/",
        revenue_schedule_detail,
        name="revenue_schedule_detail",
    ),
    path(
        "orders/revenue-schedules/<int:pk>/edit/",
        revenue_schedule_edit,
        name="revenue_schedule_edit",
    ),
    path(
        "orders/revenue-schedules/<int:pk>/delete/",
        revenue_schedule_delete,
        name="revenue_schedule_delete",
    ),
    # The child routes are NESTED: no route anywhere takes an obligation pk on its own.
    # ``add/`` is a literal and must also precede the <int:obligation_pk> route below it.
    path(
        "orders/revenue-schedules/<int:pk>/obligations/add/",
        revenue_schedule_obligation_add,
        name="revenue_schedule_obligation_add",
    ),
    path(
        "orders/revenue-schedules/<int:pk>/obligations/<int:obligation_pk>/edit/",
        revenue_schedule_obligation_edit,
        name="revenue_schedule_obligation_edit",
    ),
    path(
        "orders/revenue-schedules/<int:pk>/obligations/<int:obligation_pk>/delete/",
        revenue_schedule_obligation_delete,
        name="revenue_schedule_obligation_delete",
    ),
    path(
        "orders/revenue-schedules/<int:pk>/recognize/",
        revenue_schedule_recognize,
        name="revenue_schedule_recognize",
    ),
]
