"""SCM 4.14 Labor Management — the three COMPUTED pages: ``labor-board/``,
``labor-payroll-export/`` and ``labor-scorecard/``.

Each is derived from rows that already exist — no new table, no new column, and therefore no
create/edit/delete route and **no ``<int:pk>`` anywhere in this module** (the ``pm_forecast`` /
``valuation_report`` / ``reorder_alerts`` precedent). Every option each page takes is a QUERY
STRING (``?kind=&assignee=&zone=&unassigned=&q=`` on the board; ``?date_from=&date_to=&format=csv``
on the payroll export; ``?date_from=&date_to=`` on the scorecard), so none of them adds a route
beyond the ones below.

COLLISION CHECK — all three first segments checked against the WHOLE concatenated urlconf, not
merely against this block: **nothing anywhere in ``scm`` starts with ``labor``.** Django matches
WHOLE path components and never splits one at a hyphen, so ``labor-board``,
``labor-payroll-export`` and ``labor-scorecard`` are three unrelated segments, unrelated in turn to
4.14's ``labor-standards`` / ``labor-sessions`` / ``labor-activities`` / ``labor-plans`` /
``labor-plan-lines``. In particular ``labor-scorecard`` is a DISTINCT component from 4.2's
``scorecards/`` and the two are different subjects — 4.2 grades a SUPPLIER from delivery and quality
signals, this grades a WORKER against an engineered standard — so neither may ever be "tidied" to
look like the other. This module introduces NO greedy ``<str:…>`` converter; 4.10's
``return-tracking/<str:token>/`` remains the app's only one. With no pk route here, there is nothing
that could swallow the two literal verb sub-routes.

**THE BOARD'S BULK VERBS LIVE ON ``labor-board/``, NOT UNDER 4.4's SEGMENTS.** 4.14 adds no route
under ``picks/``, ``putaway/`` or ``cycle-counts/`` — 4.4's urlconf is untouched. Both are POST-only
(``@require_POST`` + ``@tenant_admin_required``) because they write **another sub-module's table**:
the ONLY column they touch is 4.4's already-existing ``assigned_to`` on ``PickTask`` /
``PutawayTask`` / ``CycleCountTask``. **4.14 declares no task table and adds no assignee column** —
Task Assignment is a console over what 4.4 already owns, which is the 4.13 "Spare Parts Inventory is
computed over 4.3" precedent. The verbs cap the id list at ``MAX_BULK_ASSIGN`` before touching the
DB, re-fetch every id with ``tenant=request.tenant`` and silently skip + count foreign or non-open
ids rather than 500, and audit per changed row.

**``labor-payroll-export/`` performs NO writes at all** — not even a stamp. There is no
``exported_at`` column on ``LaborSession`` on purpose: ``approved`` IS the export lock, and stamping
a column from a download page would make a GET perform a write. ``?format=csv`` streams the same
aggregate the HTML page shows (the 4.11 export precedent), so the CSV needs no route of its own and
cannot drift from the page above it. The hand-off stops at the file: ``hrm.AttendanceRecord``,
``hrm.Timesheet`` and ``accounting.PayrollRun`` remain the systems of record and this module reads
nothing from them and writes nothing to them — **``apps/scm`` holds ZERO ``hrm.*`` references and
these routes add none.**

``labor-scorecard/`` exists as its own destination because the **Performance Tracking** sidebar
bullet points at ``laborstandard_list``, which is master data; the productivity figures that bullet
names therefore live one click away behind a header chip (the ``pm_forecast`` precedent), rather
than being a fourth tab nobody finds. Nothing on it is stored — every figure is a grouped aggregate
over ``LaborSession``/``LaborActivity``, and a worker under ``MIN_RANKED_MINUTES`` in the window is
left unranked rather than shown as a confident zero.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # 4.14 bullet "Task Assignment" — the open pick/putaway/count queue, grouped by assignee,
    # zone and kind, over 4.4's EXISTING rows.
    path("labor-board/", views.labor_board, name="labor_board"),
    # The two bulk verbs. Literal sub-routes under an already-claimed segment, so they add no new
    # first segment and no collision surface; there is no <int:pk> in this module to shadow them.
    path("labor-board/assign/", views.labor_board_assign, name="labor_board_assign"),
    path("labor-board/unassign/", views.labor_board_unassign, name="labor_board_unassign"),

    # 4.14 bullet "Payroll Integration" — approved sessions only, aggregated per worker per period.
    # Read-only, including the ?format=csv download.
    path("labor-payroll-export/", views.labor_payroll_export, name="labor_payroll_export"),

    # The productivity report the "Performance Tracking" bullet's page links out to.
    path("labor-scorecard/", views.labor_scorecard, name="labor_scorecard"),
]
