"""SCM 4.18 Finance & Accounting Integration — ``DutyTariff`` routes (prefix ``duty-tariffs/``).

Plain CRUD: list / create / detail / edit / delete. No verbs — a tariff is a master row, not a
document with a lifecycle — and therefore no POST route other than the delete, which is POST-only
**at the view** (``@require_POST``), so a GET to it is a 405 rather than a silent state change.

--------------------------------------------------------------------------------------------------
ORDER IS BEHAVIOUR
--------------------------------------------------------------------------------------------------
``duty-tariffs/add/`` **MUST stay above the ``<int:pk>/`` block.** Django is first-match-wins and
matches WHOLE path components, so a ``<int:pk>`` route placed first would be offered ``add`` — the
``int`` converter refuses it today, which is precisely why the ordering looks harmless right up until
somebody adds a ``<str:…>`` route under this prefix and the create page starts 404ing as *"tariff
'add' not found"*.

--------------------------------------------------------------------------------------------------
COLLISION CHECK — against the WHOLE concatenated urlconf, not merely against this block
--------------------------------------------------------------------------------------------------
``apps/scm/urls/__init__.py`` concatenates every entity module's ``urlpatterns`` into ONE flat list
under the ``scm:`` namespace, so a collision check that only reads this file is not a check at all.

``duty-tariffs`` is a NEW first segment: **nothing anywhere in ``apps/scm`` starts with ``duty``**
(grepped over ``apps/scm/urls/`` this session). Its near neighbours were checked rather than assumed,
and every one of them is an unrelated WHOLE component — Django never splits a component at a hyphen,
so none of these can shadow another and none may ever be "tidied" to look like another:

* 4.11's ``disruption-risk/`` and 4.2's ``risk-assessments/`` — different first components entirely;
* 4.12's ``trade-documents/`` and ``trade-licenses/``, which share this module's *subject matter*
  (customs) but not one path segment with it;
* this sub-module's own siblings ``landed-cost-vouchers/``, ``landed-cost-charges/`` and the four
  ``finance-*`` / ``landed-cost-variance`` report routes.

**VIEW-NAME check** against the flat ``scm:`` namespace: ``dutytariff_list`` / ``_create`` /
``_detail`` / ``_edit`` / ``_delete`` are new names; no shipped scm view is called ``dutytariff_*``
or ``duty*``.

This module introduces **no greedy ``<str:…>`` converter** — 4.10's ``return-tracking/<str:token>/``
and 4.16's ``portal-documents/<str:token>/`` remain the app's only two, and adding a third under this
prefix is exactly what the ordering note above is guarding against.

The sidebar reaches this list as **4.18 → Tax Management** (``scm:dutytariff_list``); the
``LIVE_LINKS`` entry belongs to ``apps/core/navigation.py``, a single-writer file this module never
touches.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("duty-tariffs/", views.dutytariff_list, name="dutytariff_list"),

    # LITERAL — must stay above the <int:pk> block below. See the ordering note in the docstring.
    path("duty-tariffs/add/", views.dutytariff_create, name="dutytariff_create"),

    path("duty-tariffs/<int:pk>/", views.dutytariff_detail, name="dutytariff_detail"),
    path("duty-tariffs/<int:pk>/edit/", views.dutytariff_edit, name="dutytariff_edit"),
    # POST-only at the view (@require_POST) — a GET is a 405, never a deletion.
    path("duty-tariffs/<int:pk>/delete/", views.dutytariff_delete, name="dutytariff_delete"),
]
