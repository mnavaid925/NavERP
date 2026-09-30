"""Sales 8.7 — URLs for the account→territory assignment ledger.

Five routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR, NOT STYLE**: Django resolves
first-match-wins, so the literal ``territories/assignments/add/`` MUST precede
``territories/assignments/<int:pk>/`` — listed below it, ``int("add")`` raises ``ValueError``
and the ledger is a 500 rather than a page. The same class of bug is why 8.5's greedy
``quotes/portal/<str:token>/`` is the cautionary tale everywhere in this sub-module.

``delete/`` is **POST-only** in the view. It removes a coverage row, so a GET that deleted
one would let a prefetch, a crawler or a link preview destroy a customer's coverage history by
touching a URL. Its list-row button is a POST form carrying ``{% csrf_token %}`` and an
``onclick="return confirm(…)"`` guard.

``assigned_by`` is ``editable=False`` and therefore off every form; it is stamped by the
create view, not authored (contract §12). The FK itself belongs to CRM 1.2's
``crm.Territory`` and is read-only to 8.7 — an assignment records *which* territory holds an
account, the territory row itself is CRM's to edit (contract §0.3).

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to
be phished; every POST here redirects to a name this module owns.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``territories/assignments/``, which is a **third** segment under ``territories/`` and
so can never be reached by a board literal (``territories/performance/`` and friends) or by
``territories/rules/…``. Verified against the whole concatenated ``sales:urlpatterns`` list.
"""
from django.urls import path

from apps.sales.views.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    account_territory_assignment_create,
    account_territory_assignment_delete,
    account_territory_assignment_detail,
    account_territory_assignment_edit,
    account_territory_assignment_list,
)


urlpatterns = [
    path(
        "territories/assignments/",
        account_territory_assignment_list,
        name="account_territory_assignment_list",
    ),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path(
        "territories/assignments/add/",
        account_territory_assignment_create,
        name="account_territory_assignment_create",
    ),
    path(
        "territories/assignments/<int:pk>/edit/",
        account_territory_assignment_edit,
        name="account_territory_assignment_edit",
    ),
    path(
        "territories/assignments/<int:pk>/delete/",
        account_territory_assignment_delete,
        name="account_territory_assignment_delete",
    ),
    # The bare keyed page is LAST — it is the only pattern here a sibling literal could lose to.
    path(
        "territories/assignments/<int:pk>/",
        account_territory_assignment_detail,
        name="account_territory_assignment_detail",
    ),
]
