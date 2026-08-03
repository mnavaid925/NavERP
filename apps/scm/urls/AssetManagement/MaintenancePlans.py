"""SCM 4.13 Asset Management — ``MaintenancePlan`` routes (prefix ``maintenance-plans/``).

COLLISION CHECK — ``maintenance-plans/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: no existing ``scm`` first segment starts with ``maintenance``. It is a
distinct whole path component from 4.13's own ``maintenance-work-orders/`` and from 4.8's
``work-orders/`` — Django matches whole path components and never splits one at the hyphen, so none
of the three can shadow another, and none may be "tidied" to look like another. This module
introduces NO greedy ``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/`` remains the
app's only one.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "plan 'add' not found".

``generate/`` is the module's only action route and the only one that CREATES anything. It sits
under its own ``<int:pk>/`` and is POST-only at the view (``@require_POST`` +
``@tenant_admin_required``), so a GET is a 405 rather than a silent state change and a crawler
cannot raise a work order by following a link.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("maintenance-plans/", views.maintenanceplan_list, name="maintenanceplan_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("maintenance-plans/add/", views.maintenanceplan_create, name="maintenanceplan_create"),
    path("maintenance-plans/<int:pk>/", views.maintenanceplan_detail,
         name="maintenanceplan_detail"),
    path("maintenance-plans/<int:pk>/edit/", views.maintenanceplan_edit,
         name="maintenanceplan_edit"),
    path("maintenance-plans/<int:pk>/delete/", views.maintenanceplan_delete,
         name="maintenanceplan_delete"),
    # Raises the plan's next job, snapshots its checklist and rolls the schedule forward — one
    # explicit human press inside one transaction, never a background auto-post.
    path("maintenance-plans/<int:pk>/generate/", views.maintenanceplan_generate,
         name="maintenanceplan_generate"),
]
