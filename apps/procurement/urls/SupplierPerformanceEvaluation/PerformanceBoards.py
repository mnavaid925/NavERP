"""Procurement 6.16 Supplier Performance & Evaluation — the three board URL patterns.

ONE first segment, ``supplier-benchmarking/``, collision-checked as a whole component against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. It is a **LITERAL**, like every
other first component in this app: ``apps/procurement/urls/`` registers no route anywhere that
opens with a converter, and 6.16 does not become the first. That guarantee is what makes every
other module's routing reasoning local — the day one greedy ``<str:token>`` claims first position,
every literal segment in the app has to be re-checked against it.

**No converters at all in this lane**, first position or any other. All three pages are
whole-workspace views whose selection rides as a query string — ``?period=`` and ``?tier=`` and
``?category=`` on the benchmark board, ``?supplier=`` and ``?kpi=`` on the trend board,
``?supplier=`` and ``?period=`` on the perception gap. That is the right shape for a board: a
filter combination is not a resource, the three pages share pickers, and a bookmarked board with
its filters intact is one URL rather than a path the router has to know how to spell.

**Order is behaviour** — Django resolves first-match-wins. The two literal children
(``trend/``, ``perception-gap/``) are declared AFTER the bare board but they cannot be shadowed by
it: ``supplier-benchmarking/`` is an exact match, not a prefix. They are listed in reading order
(the cohort, then one supplier through time, then that supplier's two sides) rather than
alphabetically, so the table reads the way the pages are used.

**Three routes, all GET, all ``@login_required``, all read-only.** There is no create, no edit
and no delete here, and nothing in this lane writes: every figure these pages render was frozen
onto a ``SupplierKpiScore`` row by ``supplierevaluation_generate``, which is the one writer. A
verb on a board would be a second way to change a measurement.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("supplier-benchmarking/", views.supplier_benchmark_board,
         name="supplier_benchmark_board"),
    path("supplier-benchmarking/trend/", views.supplier_trend_board,
         name="supplier_trend_board"),
    path("supplier-benchmarking/perception-gap/", views.supplier_perception_gap,
         name="supplier_perception_gap"),
]
