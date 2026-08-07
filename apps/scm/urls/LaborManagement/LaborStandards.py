"""SCM 4.14 Labor Management — ``LaborStandard`` routes (prefix ``labor-standards/``).

COLLISION CHECK — ``labor-standards/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: **nothing anywhere in ``scm`` starts with ``labor``.** Django matches
WHOLE path components and never splits one at a hyphen, so ``labor-standards`` is one first segment
that neither shadows nor is shadowed by 4.14's own ``labor-sessions`` / ``labor-activities`` /
``labor-plans`` / ``labor-plan-lines`` / ``labor-board`` / ``labor-payroll-export`` /
``labor-scorecard`` — eight unrelated components, and none of them may ever be "tidied" into
another's shape. Near neighbours that are NOT collisions: 4.6's ``loads/``, 4.3's ``locations/`` and
``lot-serials/``, and 4.2's ``scorecards/`` (a SUPPLIER scorecard — a distinct segment from
``labor-scorecard`` and a distinct subject).

This module introduces NO greedy ``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/``
remains the app's only one.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "labor standard 'add' not found".

**``activate/`` and ``archive/`` are the only things that can move ``status``** — it is
``editable=False`` on the model and off the form — and both are POST-only at the view
(``@require_POST`` + ``@tenant_admin_required``), so a GET is a 405 rather than a silent state
change. The privilege is not ceremony: ``select_standard()`` considers ``active`` rows only, so
activating a standard changes what every FUTURE ``LaborActivity`` snapshots and therefore what
every future performance % is measured against. Archiving is the other half of the same lever —
and it is one-way in practice, because ``clean()``'s overlap guard ignores archived rows, so an
archived standard is deliberately frozen rather than editable back into a live date range.

There is no route that re-measures history: an activity carries its own
``standard_*_snapshot`` columns, so re-timing a standard here cannot rewrite a minute already
booked. That is the whole reason ``active`` is an editable status.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("labor-standards/", views.laborstandard_list, name="laborstandard_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("labor-standards/add/", views.laborstandard_create, name="laborstandard_create"),
    path("labor-standards/<int:pk>/", views.laborstandard_detail, name="laborstandard_detail"),
    path("labor-standards/<int:pk>/edit/", views.laborstandard_edit, name="laborstandard_edit"),
    path("labor-standards/<int:pk>/delete/", views.laborstandard_delete,
         name="laborstandard_delete"),

    # --- the two-step ladder: draft -> active -> archived. Neither verb touches an existing
    # activity; both change what the NEXT one resolves through select_standard().
    path("labor-standards/<int:pk>/activate/", views.laborstandard_activate,
         name="laborstandard_activate"),
    path("labor-standards/<int:pk>/archive/", views.laborstandard_archive,
         name="laborstandard_archive"),
]
