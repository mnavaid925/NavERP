"""Sales 8.7 Territory & Quota Management — the ``territories/`` + ``quota-plans/`` URL surface.

Five modules are concatenated here in a deliberate order, and the order is **behaviour, not
decoration**: Django resolves **first-match-wins**.

* ``board_patterns`` come FIRST. The four boards carry the literal routes
  (``territories/performance/``, ``territories/white-space/``, …), and a literal route listed
  after a keyed sibling is the classic way a sibling silently swallows it. This mirrors 8.5's
  ``QuoteOperations``-first and 8.6's ``board_patterns``-first precedent.
* The four entity modules follow, each with its own literals ahead of its own ``<int:pk>``:
  ``territories/rules/add/`` and ``quota-plans/add/`` each precede their module's bare
  ``<int:pk>/`` detail page.

**The shadowing check is a standing obligation, not a one-off.** 8.5 ships
``quotes/portal/<str:token>/`` — a greedy ``<str>`` that captures anything not already
claimed above it. That route is scoped inside the literal prefix ``quotes/``, so it cannot
reach ``territories/`` or ``quota-plans/``; every route below was still re-checked against
the WHOLE concatenated ``sales:urlpatterns`` list, not just against its own module. The
prefix segments ``territories/`` and ``quota-plans/`` were verified free against every prefix
already mounted under ``sales:``.

**The four entity prefixes are distinct on purpose.** ``territories/rules/``,
``territories/assignments/`` and ``territories/members/`` all sit under the same first
segment but are three different literals at the second, so no member route can be captured
by a rule route or vice versa. A future ``territories/<int:pk>/`` would have to be checked
against all three — which is exactly why none is proposed here.

**The ownership ruling, recorded here as well as in the models package, the views package and
``apps/core/navigation.py``:**

    `crm.Territory` / `crm.SalesQuota` are CRM 1.2's. 8.7 EXTENDS both by FK and declares NEITHER again.
    There is NO `class Territory` and NO `class SalesQuota` anywhere in `apps/sales` — a class by either
    name in this app is a **bug, not a variant**.

Nothing under this package writes either CRM table. CRM also already serves a ``territories/``
URL surface under the **``crm:``** namespace (``crm:territory_list``); that is a different
namespace from ``sales:`` and the two cannot collide.

``app_name`` stays ``"sales"`` — set once in ``apps/sales/urls/__init__.py``, not repeated here.
"""
from .AccountTerritoryAssignments import urlpatterns as assignment_patterns
from .QuotaPlans import urlpatterns as plan_patterns
from .TerritoryBoards import urlpatterns as board_patterns
from .TerritoryMembers import urlpatterns as member_patterns
from .TerritoryRules import urlpatterns as rule_patterns

urlpatterns = (
    board_patterns +
    rule_patterns +
    assignment_patterns +
    member_patterns +
    plan_patterns
)
