"""Sales 8.7 — URLs for the territory rule register.

Seven routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR, NOT STYLE**: Django resolves
first-match-wins, so the literal ``territories/rules/add/`` MUST precede
``territories/rules/<int:pk>/`` — listed below it, ``int("add")`` raises ``ValueError`` and the
register is a 500 rather than a page. The same class of bug is why 8.5's greedy
``quotes/portal/<str:token>/`` is the cautionary tale everywhere in this sub-module.

The two verbs, ``run/`` and ``toggle/``, are **POST-only** in the view. ``territory_rule_run``
evaluates the rule against every account in the tenant and writes the resulting
``AccountTerritoryAssignment`` rows in one transaction, and ``territory_rule_toggle`` flips
``is_active``. A GET that did either would let a prefetch, a crawler or a link preview perform
it by touching a URL, so both are routed before the keyed detail page purely so they are
reachable, and both are protected by ``@require_POST`` in the view itself.

``run/`` also writes the frozen-evidence columns ``last_run_at`` / ``last_run_matched_count``,
which are ``editable=False`` and therefore off every form — this route is their sole writer
(contract §12).

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to
be phished; every POST here redirects to a name this module owns.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``territories/rules/``, verified free against the whole concatenated ``sales:urlpatterns``
list, not just against this module.
"""
from django.urls import path

from apps.sales.views.TerritoryQuotaManagement.TerritoryRules import (
    territory_rule_create,
    territory_rule_delete,
    territory_rule_detail,
    territory_rule_edit,
    territory_rule_list,
    territory_rule_run,
    territory_rule_toggle,
)


urlpatterns = [
    path(
        "territories/rules/",
        territory_rule_list,
        name="territory_rule_list",
    ),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path(
        "territories/rules/add/",
        territory_rule_create,
        name="territory_rule_create",
    ),
    # ---- the two POST-only verbs, listed before the keyed pages for readability ----
    path(
        "territories/rules/<int:pk>/run/",
        territory_rule_run,
        name="territory_rule_run",
    ),
    path(
        "territories/rules/<int:pk>/toggle/",
        territory_rule_toggle,
        name="territory_rule_toggle",
    ),
    path(
        "territories/rules/<int:pk>/edit/",
        territory_rule_edit,
        name="territory_rule_edit",
    ),
    path(
        "territories/rules/<int:pk>/delete/",
        territory_rule_delete,
        name="territory_rule_delete",
    ),
    # The bare keyed page is LAST — it is the only pattern here a sibling literal could lose to.
    path(
        "territories/rules/<int:pk>/",
        territory_rule_detail,
        name="territory_rule_detail",
    ),
]
