"""Sales 8.6 Order Management — the ``orders/`` URL surface.

Five modules are concatenated here in a deliberate order, and the order is behaviour, not
decoration: Django resolves **first-match-wins**.

* ``board_patterns`` come FIRST. The boards carry the literal routes (``orders/``,
  ``orders/fulfillment/``, ``orders/reorder/``, …), and a literal route listed after a
  ``<int:pk>`` sibling is the classic way a sibling silently swallows it. This mirrors 8.5's
  ``QuoteOperations``-first precedent.
* The four entity modules follow, each with its own literals ahead of its own ``<int:pk>``:
  ``orders/holds/bulk-raise/`` and ``orders/holds/bulk-clear/`` precede ``orders/holds/<int:pk>/``,
  and ``orders/amendments/open/`` precedes ``orders/amendments/<int:pk>/``.

**The shadowing check is a standing obligation, not a one-off.** 8.5 ships
``quotes/portal/<str:token>/`` — a greedy ``<str>`` that will capture anything not already
claimed above it. Those routes sit inside ``quotes/<int:pk>/`` so they cannot reach ``orders/``,
but every route added here was re-checked against the WHOLE concatenated ``sales:urlpatterns``
list, not just against its own module. The prefix segment ``orders/`` was verified free against
all sixteen prefixes already mounted under ``sales:``.

**No route takes a child pk alone.** ``OrderAmendmentLine`` and ``PerformanceObligation`` are
edited through their parent (``…/lines/<int:line_pk>/…`` and
``…/obligations/<int:obligation_pk>/…`` are nested under the parent's pk), which is both the CRUD
completeness answer and the tenant-isolation guard.

``app_name`` stays ``"sales"`` — set once in ``apps/sales/urls/__init__.py``, not repeated here.
"""
from .OrderAmendments import urlpatterns as amendment_patterns
from .OrderHolds import urlpatterns as hold_patterns
from .OrderValidationRules import urlpatterns as rule_patterns
from .RevenueSchedules import urlpatterns as revenue_patterns

urlpatterns = (
    rule_patterns +
    hold_patterns +
    amendment_patterns +
    revenue_patterns
)
