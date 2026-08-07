"""SCM 4.14 Labor Management — ``LaborPlan`` routes (prefix ``labor-plans/``) and its per-bucket
child ``LaborPlanLine`` (prefix ``labor-plan-lines/``).

COLLISION CHECK — both prefixes were checked against the WHOLE concatenated urlconf, not merely
against this block: nothing anywhere in ``scm`` starts with ``labor``. **``labor-plans`` and
``labor-plan-lines`` are two DISTINCT whole path components, not one plus a suffix** — Django
matches whole components and never splits one at a hyphen, so ``labor-plans/<int:pk>/`` cannot
capture anything under ``labor-plan-lines/`` and vice versa. The same holds against 4.13's
``maintenance-plans/`` (a different first segment entirely, and a different subject: that one
schedules machine servicing, this one forecasts headcount). This module introduces NO greedy
``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/`` remains the app's only one.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "labor plan 'add' not found".

**``generate/`` is the only route in 4.14 that creates rows in bulk**, and it is POST-only
(``@require_POST`` + ``@tenant_admin_required``) so a crawler cannot rebuild a staffing plan by
following a link. It READS 4.3's append-only ``StockMove`` ledger (and 4.4's pick lines / 4.1's
receipt lines / 4.7's forecast periods, depending on ``volume_source``) to derive volume **at
generate time** — 4.14 writes no ``StockMove`` and no ``JournalEntry`` anywhere, including here.
Regenerating is idempotent: the view deletes this plan's previous lines inside the same transaction
before the ``bulk_create``, and it refuses up front when ``periods × standards`` would exceed
``MAX_PLAN_LINES``, naming both numbers — the count happens BEFORE any row is built.

``approve/`` and ``archive/`` are the rest of the ladder (draft → planned → approved → archived) and
are POST-only for the same reason: ``status`` is ``editable=False`` and off the form, and approving
is the statement "this is the roster we are staffing to".

**THE CHILD HANGS OFF ITS OWN PK.** ``labor-plan-lines/<int:pk>/edit/`` is deliberately NOT nested
under the plan — a line pk already identifies its parent, and nesting invites a caller to pair a
real line with somebody else's plan id (the ``compliance-checks/`` rationale). ``LaborPlanLine``
carries **no ``tenant`` column**, so the view resolves it through ``plan__tenant=request.tenant``
and that join IS the authorization check.

``labor-plan-lines/`` has NO list, NO detail and NO create/delete route, and each absence is a
decision. A plan's lines are the grid ON its detail page, and a workspace-wide "every bucket of
every plan" list would be a table nobody reads. The generated half of a line (forecast volume,
standard minutes, required minutes, required headcount) is **regenerated, never typed** — the edit
form exposes ``planned_headcount`` and ``notes`` only, which is the planner's decision against the
generator's arithmetic. A line is created by ``generate/`` and destroyed by the next ``generate/``
or by the plan's own delete; a hand-made line would be a bucket the generator does not know exists.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("labor-plans/", views.laborplan_list, name="laborplan_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("labor-plans/add/", views.laborplan_create, name="laborplan_create"),
    path("labor-plans/<int:pk>/", views.laborplan_detail, name="laborplan_detail"),
    path("labor-plans/<int:pk>/edit/", views.laborplan_edit, name="laborplan_edit"),
    path("labor-plans/<int:pk>/delete/", views.laborplan_delete, name="laborplan_delete"),

    # Derives volume from the chosen source, snapshots a standard per line and rolls the required
    # headcount — one explicit human press inside one transaction, never a background auto-post.
    path("labor-plans/<int:pk>/generate/", views.laborplan_generate, name="laborplan_generate"),
    path("labor-plans/<int:pk>/approve/", views.laborplan_approve, name="laborplan_approve"),
    path("labor-plans/<int:pk>/archive/", views.laborplan_archive, name="laborplan_archive"),

    # --- the child, on its OWN pk and on its OWN first segment. See the module docstring.
    path("labor-plan-lines/<int:pk>/edit/", views.laborplanline_edit, name="laborplanline_edit"),
]
