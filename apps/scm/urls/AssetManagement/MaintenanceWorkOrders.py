"""SCM 4.13 Asset Management — ``MaintenanceWorkOrder`` routes (prefix
``maintenance-work-orders/``) and its checklist child (prefix ``maintenance-work-order-tasks/``).

COLLISION CHECK — both prefixes were checked against the WHOLE concatenated urlconf, not merely
against this block: no existing ``scm`` first segment starts with ``maintenance``.

**``maintenance-work-orders/`` is a DISTINCT whole path component from 4.8's ``work-orders/``, and
the two have nothing to do with each other.** Django matches whole path components and never splits
one at a hyphen, so ``maintenance-work-orders`` is one component that neither shadows nor is
shadowed by ``work-orders`` (nor by 4.1's ``orders/`` or 4.5's ``sales-orders/``). The two documents
are also genuinely different things — 4.8's ``WorkOrder`` MAKES product and consumes components
against a BOM, this one REPAIRS a machine and consumes spares against an asset — so neither route
may ever be "tidied" to look like the other. The same applies to ``maintenance-work-order-tasks/``:
one component, not ``maintenance-work-orders`` + ``-tasks``, so the pk route above it cannot capture
it and it cannot capture anything of the parent's.

This module introduces NO greedy ``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/``
remains the app's only one.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "job 'add' not found".

**Every one of the ten verb routes sits under its own ``<int:pk>/`` and is POST-only at the view**
(``@require_POST``), so a GET to one is a 405 rather than a silent state change — ``status`` is
``editable=False`` on the model and these routes are the ONLY thing that can move it, which is
exactly why none of them may be reachable by following a link. ``approve/``, ``cancel/`` and
``issue-parts/`` are additionally ``@tenant_admin_required``, the last because it writes the
ledger.

THE CHECKLIST CHILD HANGS OFF ITS OWN PK. ``maintenance-work-order-tasks/<int:pk>/toggle/`` is not
nested under the job — a task pk already identifies its parent, and nesting would invite a caller to
pair a real step with somebody else's job id (the ``compliance-checks/`` rationale).
``MaintenanceWorkOrderTask`` carries no ``tenant`` column, so the view resolves it through
``work_order__tenant`` and that join IS the authorization check.

There is deliberately no route to CREATE or DELETE a task: the checklist is a SNAPSHOT written by
``maintenanceplan_generate`` and must not be editable after the fact. Ticking a step is the only
change a job's checklist accepts.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("maintenance-work-orders/", views.maintenanceworkorder_list,
         name="maintenanceworkorder_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("maintenance-work-orders/add/", views.maintenanceworkorder_create,
         name="maintenanceworkorder_create"),
    path("maintenance-work-orders/<int:pk>/", views.maintenanceworkorder_detail,
         name="maintenanceworkorder_detail"),
    path("maintenance-work-orders/<int:pk>/edit/", views.maintenanceworkorder_edit,
         name="maintenanceworkorder_edit"),
    path("maintenance-work-orders/<int:pk>/delete/", views.maintenanceworkorder_delete,
         name="maintenanceworkorder_delete"),

    # --- the ladder: requested -> approved -> scheduled -> in_progress -> completed -> closed,
    # with hold/resume off in_progress and cancel reachable from any open status. No stock effect.
    path("maintenance-work-orders/<int:pk>/approve/", views.maintenanceworkorder_approve,
         name="maintenanceworkorder_approve"),
    path("maintenance-work-orders/<int:pk>/schedule/", views.maintenanceworkorder_schedule,
         name="maintenanceworkorder_schedule"),
    path("maintenance-work-orders/<int:pk>/start/", views.maintenanceworkorder_start,
         name="maintenanceworkorder_start"),
    path("maintenance-work-orders/<int:pk>/hold/", views.maintenanceworkorder_hold,
         name="maintenanceworkorder_hold"),
    path("maintenance-work-orders/<int:pk>/resume/", views.maintenanceworkorder_resume,
         name="maintenanceworkorder_resume"),
    path("maintenance-work-orders/<int:pk>/complete/", views.maintenanceworkorder_complete,
         name="maintenanceworkorder_complete"),
    path("maintenance-work-orders/<int:pk>/close/", views.maintenanceworkorder_close,
         name="maintenanceworkorder_close"),
    path("maintenance-work-orders/<int:pk>/cancel/", views.maintenanceworkorder_cancel,
         name="maintenanceworkorder_cancel"),

    # --- the ONE ledger write in the whole of 4.13: a negative `maintenance` StockMove per
    # un-issued part line. It posts no JournalEntry (L29).
    path("maintenance-work-orders/<int:pk>/issue-parts/", views.maintenanceworkorder_issue_parts,
         name="maintenanceworkorder_issue_parts"),
    # --- a meter capture against this job's asset, without waiting for completion.
    path("maintenance-work-orders/<int:pk>/record-reading/",
         views.maintenanceworkorder_record_reading,
         name="maintenanceworkorder_record_reading"),

    # --- the checklist child, on its OWN pk. See the module docstring.
    path("maintenance-work-order-tasks/<int:pk>/toggle/", views.maintenanceworkordertask_toggle,
         name="maintenanceworkordertask_toggle"),
]
