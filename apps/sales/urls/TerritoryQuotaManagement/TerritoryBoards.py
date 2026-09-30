"""Sales 8.7 — URLs for the four derived territory boards.

Four routes, and there is **no ``<int:pk>`` anywhere in this file**, so nothing here can be
shadowed by a sibling and nothing here can shadow a sibling. Every pattern is a pure literal
under the ``territories/`` prefix, which is why this module is concatenated FIRST into
``apps/sales/urls/TerritoryQuotaManagement/__init__.py`` — the 8.5 ``QuoteOperations``-first
and 8.6 ``board_patterns``-first precedent. Order is behaviour: Django resolves
first-match-wins, and a board literal listed after a keyed sibling is the classic way a
sibling silently swallows it.

These are read-only boards, not models. Per contract §1 non-goal 13 they get **no table, no
seeder row and no admin registration** — each is a pure function of tables that already have
owners (``crm.Territory``, ``crm.SalesQuota``, ``sales.AccountTerritoryAssignment``). The
precedent is 8.3's ``AccountBoards.py`` and 8.4's ``ForecastBoards.py``; 8.7 is the third
module in a row to make this call.

**The ownership ruling, repeated because this is the module that reads both tables:**

    `crm.Territory` / `crm.SalesQuota` are CRM 1.2's. 8.7 EXTENDS both by FK and declares NEITHER again.
    There is NO `class Territory` and NO `class SalesQuota` anywhere in `apps/sales` — a class by either
    name in this app is a **bug, not a variant**.

``territory_boards`` reads those two tables and **never writes either one**: the quota amount
is edited on the CRM quota, in CRM's form, by CRM's permission set (contract §0.3).

Each of the four board literals is deliberately distinct from a keyed sibling that a future
pass might add under the same ``territories/`` prefix: ``territories/performance/`` and
``territories/white-space/`` are board pages, and neither can be reached by
``territories/<something>/<int:pk>/`` because ``performance`` and ``white-space`` sit where a
literal segment is required.

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to
be phished.

The ``territories/`` prefix was verified free against **every** route already mounted under
``sales:`` — the 8.5 greedy ``quotes/portal/<str:token>/`` is scoped inside ``quotes/`` and
cannot reach it, and no other mounted prefix begins with ``territories/`` or ``quota-plans/``.
"""
from django.urls import path

from apps.sales.views.TerritoryQuotaManagement.TerritoryBoards import (
    territory_coverage_gap,
    territory_performance,
    territory_rebalance_preview,
    territory_white_space,
)


urlpatterns = [
    # ---- the four literal board routes. No <int:…> in this file, so nothing to order against. ----
    path(
        "territories/rebalance-preview/",
        territory_rebalance_preview,
        name="territory_rebalance_preview",
    ),
    path(
        "territories/coverage-gap/",
        territory_coverage_gap,
        name="territory_coverage_gap",
    ),
    path(
        "territories/performance/",
        territory_performance,
        name="territory_performance",
    ),
    path(
        "territories/white-space/",
        territory_white_space,
        name="territory_white_space",
    ),
]
