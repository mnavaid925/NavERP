"""SCM 4.17 Third-Party Logistics (3PL) — ``ClientRateCard`` routes: the tariff and its rate lines.

Django is first-match-wins, so ORDER IS BEHAVIOUR: every literal segment sits before the
``<int:pk>`` route it would otherwise be swallowed by (``client-rate-cards/add/`` before
``client-rate-cards/<int:pk>/``).

COLLISION CHECK — run against the WHOLE concatenated urlconf, not just this module. **Nothing
anywhere in ``apps/scm`` starts with ``client``**, so both first segments introduced here are new.
The near neighbours were checked rather than assumed: 4.16's ``portal-*``, 4.10's
``return-portal/``, 4.2's ``contracts/``, 4.6's ``carriers/`` and 4.11's ``logistics-kpis/``. This
module introduces **no greedy ``<str:…>`` converter**.

``client-rate-cards`` and ``client-rate-card-lines`` are two DISTINCT whole path components —
Django never splits a component at a hyphen, so neither can shadow the other, and neither may ever
be "tidied" to look like the other. They are different things: one is a priced agreement, the other
is one charge inside it.

**The line routes split deliberately, and the split is the security argument.**

* ``client-rate-cards/<int:pk>/lines/add/`` is NESTED (``pk`` = the RATE CARD) because on the create
  path the parent must come from the ROUTE and never from a POST body — a parent pk in a body is how
  a caller grafts a priced line onto somebody else's tariff. This is the 4.15
  ``cold-chain-monitors/<int:pk>/readings/add/`` precedent exactly.
* ``client-rate-card-lines/<int:pk>/edit/`` and ``.../delete/`` hang off the LINE's own pk, because
  a child pk already identifies its parent and nesting would only invite a caller to pair a real
  child with somebody else's parent id (the 4.12 ``compliance-checks/`` rationale). Both views
  resolve through ``rate_card__tenant`` **and** ``rate_card__client__tenant`` regardless.

The nested create route carries more path segments than ``client-rate-cards/<int:pk>/``, so its
position after that route in this list cannot shadow it.

**No standalone line list and no line detail route** — that is a decision, not an omission. The
parent card's detail page IS the line list: a rate line is only meaningful beside the other lines of
its own tariff, and a register of every priced charge in the workspace would be a table nobody can
read. ``clientratecard_delete`` / ``_activate`` / ``_supersede`` and both line-mutating routes are
POST-only **at the view** (``@require_POST``), so a GET is a 405 rather than a side effect.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # --- the tariff -----------------------------------------------------------------------------
    path("client-rate-cards/", views.clientratecard_list, name="clientratecard_list"),
    # LITERAL, and it must stay above the <int:pk> routes below.
    path("client-rate-cards/add/", views.clientratecard_create, name="clientratecard_create"),
    path("client-rate-cards/<int:pk>/", views.clientratecard_detail, name="clientratecard_detail"),
    path("client-rate-cards/<int:pk>/edit/", views.clientratecard_edit, name="clientratecard_edit"),
    path("client-rate-cards/<int:pk>/delete/", views.clientratecard_delete,
         name="clientratecard_delete"),
    # The ladder. Both POST-only at the view, both write their own audit row inside the row lock.
    path("client-rate-cards/<int:pk>/activate/", views.clientratecard_activate,
         name="clientratecard_activate"),
    path("client-rate-cards/<int:pk>/supersede/", views.clientratecard_supersede,
         name="clientratecard_supersede"),

    # --- the rate lines -------------------------------------------------------------------------
    # NESTED: `pk` is the RATE CARD, so the parent comes from the route and never from the body.
    path("client-rate-cards/<int:pk>/lines/add/", views.clientratecardline_create,
         name="clientratecardline_create"),
    # The LINE's own pk from here down — see the module docstring for why these two are not nested.
    path("client-rate-card-lines/<int:pk>/edit/", views.clientratecardline_edit,
         name="clientratecardline_edit"),
    path("client-rate-card-lines/<int:pk>/delete/", views.clientratecardline_delete,
         name="clientratecardline_delete"),
]
