"""Procurement 6.17 Risk & Compliance Management — ComplianceScreening URL patterns.

Two first segments, both collision-checked as whole components against the concatenated
inventory in ``apps/procurement/urls/__init__.py``: ``screenings/`` and ``rescreening-due/``.
The app registers no greedy ``<str:…>`` converter, so nothing can shadow either.

Django is first-match-wins, so **every literal route is declared before the ``<int:pk>/`` one it
would otherwise fall into** — here that is ``screenings/add/``.

``screenings/<int:pk>/hits/add/`` routes a ScreeningHits view but lives in THIS module on
purpose: it is a child of the ``screenings/`` segment, and keeping one module per first segment
is what makes the first-match-wins ordering above reviewable in one place. Every
``screening-hits/`` route lives in ``ScreeningHits.py``.

**``screening_batch`` is deliberately NOT registered.** The plan marks it P2/cuttable, and it is
the one route here that WRITES rows in bulk (one screening per un-screened supplier, capped at
``BATCH_PARTY_LIMIT``). It is cut from this entity rather than shipped half-guarded; the
re-screening board already surfaces exactly which suppliers it would have minted a screening for,
so nothing is unreachable without it.

``delete/`` and the three decision verbs are POST-only through their view decorators — the list
and detail pages carry ``{% csrf_token %}`` forms with an ``onsubmit`` confirm rather than a
confirmation template.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("screenings/", views.screening_list, name="screening_list"),
    # Literal before <int:pk> — first-match-wins IS behaviour.
    path("screenings/add/", views.screening_create, name="screening_create"),
    path("screenings/<int:pk>/", views.screening_detail, name="screening_detail"),
    path("screenings/<int:pk>/edit/", views.screening_edit, name="screening_edit"),
    path("screenings/<int:pk>/delete/", views.screening_delete, name="screening_delete"),
    # The three decision verbs — @tenant_admin_required + @require_POST on the views.
    path("screenings/<int:pk>/clear/", views.screening_clear, name="screening_clear"),
    path("screenings/<int:pk>/escalate/", views.screening_escalate, name="screening_escalate"),
    path("screenings/<int:pk>/block/", views.screening_block, name="screening_block"),
    # Child route: ``pk`` is the SCREENING's, and the hit's parent is stamped from it rather than
    # from the payload (a screening pk in a POST body would be an IDOR).
    path("screenings/<int:pk>/hits/add/", views.screeninghit_create, name="screeninghit_create"),
    path("rescreening-due/", views.screening_rescreen_board, name="screening_rescreen_board"),
]
