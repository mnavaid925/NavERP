"""SCM 4.14 Labor Management — ``LaborActivity`` routes (prefix ``labor-activities/``), plus the
ONE parent-nested create route that hangs off its session.

COLLISION CHECK — ``labor-activities/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: nothing anywhere in ``scm`` starts with ``labor``. It is a distinct whole
path component from ``labor-standards`` / ``labor-sessions`` / ``labor-plans`` /
``labor-plan-lines`` / ``labor-board`` / ``labor-payroll-export`` / ``labor-scorecard`` — Django
matches whole components and never splits one at a hyphen — so none of the eight can shadow another
and none may be "tidied" to match another. This module introduces NO greedy ``<str:…>`` converter;
4.10's ``return-tracking/<str:token>/`` remains the app's only one.

**THE CREATE ROUTE IS NESTED UNDER THE SESSION, AND THAT IS THE SECURITY BOUNDARY.**
``labor-sessions/<int:pk>/activities/add/`` takes its parent from the URL because there is no child
yet, so the session has to come from *somewhere* — and taking it from a POST field would let a
crafted body graft booked minutes onto another worker's shift, in another workspace, on an
already-approved period. ``session`` is therefore excluded from ``LaborActivityForm`` entirely.
This is the ``assets/<int:pk>/spare-parts/add/`` precedent, verbatim.

That nested route lives in THIS module rather than in ``LaborSessions.py`` because the row it
creates is a ``LaborActivity`` and the entity module owns its own entity's writes. It cannot be
shadowed by ``labor-sessions/<int:pk>/`` regardless of which module the urlconf concatenates first:
Django matches the FULL path, and ``labor-sessions/5/activities/add/`` has three components the
detail route does not, so the detail route simply does not match it.

**The other three routes hang off the CHILD's own pk** — ``labor-activities/<int:pk>/edit/`` and
``…/delete/`` are not nested under the session, because a child pk already identifies its parent and
nesting would invite a caller to pair a real activity with somebody else's session id (the
``compliance-checks/`` rationale). ``LaborActivity`` carries its own ``tenant`` column AND a
``session`` FK, so every view here scopes on **both** (``tenant=request.tenant`` and
``session__tenant=request.tenant``): the belt is the row's own column, the braces are the join, and
a row whose two disagreed would be a pre-existing data fault rather than a page that leaks.

**There is no standalone ``labor-activities/add/``, and that is a decision.** Every activity is
minutes inside one shift's clock window, and ``clean()`` refuses an interval outside
``session.clock_in``…``clock_out`` and refuses any write at all to a ``closed`` / ``approved`` /
``cancelled`` session. A create page with a session dropdown would make the parent a typeable field
for no gain — the session's detail page is where the work is booked.

``labor-activities/`` (the list) is a workspace-wide read across every shift, which is what the
activity filters and the scorecard's underlying grain need; it is not a second place to file one.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("labor-activities/", views.laboractivity_list, name="laboractivity_list"),
    # No literal `add/` here — see the module docstring. Nothing above the pk route to shadow.
    path("labor-activities/<int:pk>/", views.laboractivity_detail, name="laboractivity_detail"),
    path("labor-activities/<int:pk>/edit/", views.laboractivity_edit, name="laboractivity_edit"),
    path("labor-activities/<int:pk>/delete/", views.laboractivity_delete,
         name="laboractivity_delete"),

    # The ONE parent-nested route in 4.14 — the session comes from the URL, never from the POST
    # body. Lives here because the row it writes is a LaborActivity.
    path("labor-sessions/<int:pk>/activities/add/", views.laborsession_add_activity,
         name="laborsession_add_activity"),
]
