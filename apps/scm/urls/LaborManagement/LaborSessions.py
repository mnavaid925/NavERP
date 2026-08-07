"""SCM 4.14 Labor Management — ``LaborSession`` routes (prefix ``labor-sessions/``).

COLLISION CHECK — ``labor-sessions/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: nothing anywhere in ``scm`` starts with ``labor``. It is one whole path
component and Django never splits one at a hyphen, so it is unrelated to ``labor-standards``,
``labor-activities``, ``labor-plans``, ``labor-plan-lines``, ``labor-board``,
``labor-payroll-export`` and ``labor-scorecard``, and to 4.6's ``loads/`` and 4.3's ``locations/``.
This module introduces NO greedy ``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/``
remains the app's only one.

**A session is the warehouse-shift EXECUTION record, not a second attendance table.**
``hrm.AttendanceRecord`` is one row per employee per day and remains the system of record for
attendance; ``apps/scm`` holds ZERO ``hrm.*`` references and these routes add none. Nothing here
writes a ``StockMove`` or a ``JournalEntry`` either — 4.14 has no ledger effect at all.

``add/`` and ``clock-in/`` are literals and MUST precede every ``<int:pk>/`` route: Django is
first-match-wins, so a pk route above them would swallow both and 404 as "session 'add' not found".

**``clock-in/`` carries NO pk on purpose — it CREATES a session, it does not stamp one.**
``clock_in`` is a required column set at creation, so there is no prior row for a self-service
punch to hang off. The verb takes the worker from ``_acting_party(request)`` and the login from
``request.user`` rather than from the POST body, which is exactly what stops a member filing
somebody else's shift as a self-punch. ``clock-out/`` DOES take a pk, because it stamps an existing
open row. The two are deliberately not one route.

**Every verb below sits under ``@require_POST``**, so a GET is a 405 rather than a silent state
change: ``status``, ``source``, ``recorded_by``, ``login``, ``closed_at``, ``approved_at`` and
``approved_by`` are all ``editable=False`` and off the form, and these routes are the ONLY thing
that can move them. ``approve/``, ``reopen/`` and ``cancel/`` are additionally
``@tenant_admin_required`` — ``approved`` IS the payroll export lock (the export reads approved
sessions and nothing else), so approving admits a shift to a pay period, and reopening un-freezes
a period that has already been signed off.

There is deliberately no ``export/`` route here. The payroll hand-off is one page,
``labor-payroll-export/`` in ``Reports.py``, and it performs no writes — there is no ``exported_at``
column to stamp, because stamping one from a download would make a GET perform a write.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("labor-sessions/", views.laborsession_list, name="laborsession_list"),
    # Literals — both must stay above every <int:pk> route below them.
    path("labor-sessions/add/", views.laborsession_create, name="laborsession_create"),
    # No pk: this one raises the session. See the module docstring for why it is not `clock-out`'s
    # twin.
    path("labor-sessions/clock-in/", views.laborsession_clock_in, name="laborsession_clock_in"),

    path("labor-sessions/<int:pk>/", views.laborsession_detail, name="laborsession_detail"),
    path("labor-sessions/<int:pk>/edit/", views.laborsession_edit, name="laborsession_edit"),
    path("labor-sessions/<int:pk>/delete/", views.laborsession_delete, name="laborsession_delete"),

    # --- the ladder: open -> closed -> approved, with reopen back to open and cancel off any
    # non-approved status. `closed` and `approved` freeze the session AND its activities.
    path("labor-sessions/<int:pk>/clock-out/", views.laborsession_clock_out,
         name="laborsession_clock_out"),
    path("labor-sessions/<int:pk>/close/", views.laborsession_close, name="laborsession_close"),
    path("labor-sessions/<int:pk>/approve/", views.laborsession_approve,
         name="laborsession_approve"),
    path("labor-sessions/<int:pk>/reopen/", views.laborsession_reopen,
         name="laborsession_reopen"),
    path("labor-sessions/<int:pk>/cancel/", views.laborsession_cancel,
         name="laborsession_cancel"),
]
