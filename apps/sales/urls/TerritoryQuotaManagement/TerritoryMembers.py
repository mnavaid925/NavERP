"""Sales 8.7 — URLs for territory membership (who is on which territory).

Five routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR, NOT STYLE**: Django resolves
first-match-wins, so the literal ``territories/members/add/`` MUST precede
``territories/members/<int:pk>/`` — listed below it, ``int("add")`` raises ``ValueError`` and
the roster is a 500 rather than a page. The same class of bug is why 8.5's greedy
``quotes/portal/<str:token>/`` is the cautionary tale everywhere in this sub-module.

``delete/`` is **POST-only** in the view. It removes a rep from a territory roster, so a GET
that deleted one would let a prefetch, a crawler or a link preview unstaff a territory by
touching a URL. Its list-row button is a POST form carrying ``{% csrf_token %}`` and an
``onclick="return confirm(…)"`` guard.

Both FKs on this model are read-only to 8.7 in the ownership sense: ``territory`` points at
CRM 1.2's ``crm.Territory`` and 8.7 never writes it. A member is also a
``crm.TerritoryMember``-shaped relationship owned here, not a new territory hierarchy
(contract §0.3).

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to
be phished; every POST here redirects to a name this module owns.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``territories/members/``, a **third** segment under ``territories/`` and distinct from
``territories/rules/`` and ``territories/assignments/``. Verified against the whole
concatenated ``sales:urlpatterns`` list.
"""
from django.urls import path

from apps.sales.views.TerritoryQuotaManagement.TerritoryMembers import (
    territory_member_create,
    territory_member_delete,
    territory_member_detail,
    territory_member_edit,
    territory_member_list,
)


urlpatterns = [
    path(
        "territories/members/",
        territory_member_list,
        name="territory_member_list",
    ),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path(
        "territories/members/add/",
        territory_member_create,
        name="territory_member_create",
    ),
    path(
        "territories/members/<int:pk>/edit/",
        territory_member_edit,
        name="territory_member_edit",
    ),
    path(
        "territories/members/<int:pk>/delete/",
        territory_member_delete,
        name="territory_member_delete",
    ),
    # The bare keyed page is LAST — it is the only pattern here a sibling literal could lose to.
    path(
        "territories/members/<int:pk>/",
        territory_member_detail,
        name="territory_member_detail",
    ),
]
