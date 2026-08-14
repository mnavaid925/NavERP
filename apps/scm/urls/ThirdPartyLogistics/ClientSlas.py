"""SCM 4.17 Third-Party Logistics (3PL) — ``ClientSLA`` routes (prefix ``client-slas/``).

Full CRUD plus two measurement verbs: the per-SLA recompute and the workspace-wide sweep.

--------------------------------------------------------------------------------------------------
ORDER IS BEHAVIOUR — AND HERE IT IS NOT MERELY A CONVENTION
--------------------------------------------------------------------------------------------------
``client-slas/recompute-all/`` **MUST stay above the ``<int:pk>/`` block.** Django is first-match-wins
and matches WHOLE path components, so a ``<int:pk>`` route placed first would be offered
``recompute-all`` — the ``int`` converter refuses it today, which is exactly why this looks harmless
until the day somebody adds a ``<str:…>`` route to this prefix and the create/sweep pages start 404ing
as *"SLA 'recompute-all' not found"*. ``add/`` sits above the same block for the same reason.

``recompute-all`` is deliberately hyphenated to match ``client-slas`` and every other multi-word
segment in this app; it is a WHOLE component and cannot be confused with the per-row
``<int:pk>/recompute/``, which carries a different number of segments.

--------------------------------------------------------------------------------------------------
COLLISION CHECK — against the WHOLE concatenated urlconf, not merely against this block
--------------------------------------------------------------------------------------------------
``client-slas`` is a NEW first segment; nothing anywhere in ``apps/scm`` used it before. Its near
neighbours were checked rather than assumed, and every one of them is an unrelated WHOLE component —
Django never splits a component at a hyphen, so none of these can shadow another and **none may ever
be "tidied" to look like another**:

* this sub-module's own siblings — ``client-billing-runs/`` + ``client-billing-run-lines/``,
  ``client-rate-cards/`` + ``client-rate-card-lines/``, ``client-inventory/``, ``client-space/`` and
  ``logistics-clients/``;
* 4.11's ``logistics-kpis/``, which shares nothing with ``logistics-clients/`` but the first word;
* 4.10's ``return-portal/``, 4.2's ``contracts/``, 4.6's ``carriers/`` and 4.16's ``portal-*``.

There is no ``slas/`` or ``sla/`` route anywhere in the app, so the shorter spelling is free for a
future module and is not being consumed here.

This module introduces **no greedy ``<str:…>`` converter** — 4.10's ``return-tracking/<str:token>/``
remains the app's only one, and adding a second under this prefix is what the ordering note above is
guarding against.

Both verb routes are POST-only **at the view** (``@require_POST``), so a GET to either is a 405 rather
than a silent state change.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("client-slas/", views.clientsla_list, name="clientsla_list"),

    # LITERAL — both must stay above the <int:pk> block below. See the ordering note in the module
    # docstring: `recompute-all` is the one that would actually break.
    path("client-slas/add/", views.clientsla_create, name="clientsla_create"),
    # The workspace-wide measurement sweep. POST-only, bounded, and it redirects back to the list
    # because the list is what the pass changes.
    path("client-slas/recompute-all/", views.clientsla_recompute_all,
         name="clientsla_recompute_all"),

    path("client-slas/<int:pk>/", views.clientsla_detail, name="clientsla_detail"),
    path("client-slas/<int:pk>/edit/", views.clientsla_edit, name="clientsla_edit"),
    path("client-slas/<int:pk>/delete/", views.clientsla_delete, name="clientsla_delete"),
    # The per-SLA measurement — the button on its detail page.
    path("client-slas/<int:pk>/recompute/", views.clientsla_recompute, name="clientsla_recompute"),
]
