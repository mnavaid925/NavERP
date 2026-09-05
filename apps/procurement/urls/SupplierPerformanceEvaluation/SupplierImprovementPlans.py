"""Procurement 6.16 Supplier Performance & Evaluation — SupplierImprovementPlan URL patterns.

One first segment, ``improvement-plans/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory. It is a LITERAL, like every other first component
in ``apps/procurement/urls/`` — this app's standing guarantee is that no route anywhere in it
opens with a converter, and 6.16 does not break it. (``improvement-plans/`` is a distinct whole
component: Django matches path components, not string prefixes.)

Order is behaviour: Django resolves first-match-wins, so the literal ``add/`` is declared BEFORE
``<int:pk>/``. (``int`` would not swallow ``add`` anyway, but the ordering is the rule that keeps
that true when a ``<str:...>`` route is added next to it.)

**Six POST-only routes.** ``activate/``, ``monitor/``, ``acknowledge/``, ``close/``, ``cancel/``
and ``delete/`` are all ``@require_POST`` in the view; the list and detail pages post to them
through a ``{% csrf_token %}`` form with an ``onclick`` confirm rather than linking to them.
``close/`` additionally carries ``@tenant_admin_required`` — it signs the outcome the supplier
will be shown, which is a sign-off rather than an edit.

The five verbs are what make every ``STATUS_CHOICES`` and every ``OUTCOME_CHOICES`` value
reachable: ``draft`` on create, ``active`` / ``monitoring`` / ``closed`` / ``cancelled`` here, and
all four outcomes through ``close/`` alone. A status nothing can set is a lie in a dropdown.

``improvementplan_detail`` is the name Entity 1's KPI detail page and Entity 2's evaluation
detail page already emit ``{% url %}`` tags for, so this module is what makes both of those pages
resolvable. Both sit next to an ``{% empty %}`` branch, which fires precisely when there is no
data to link to — a smoke test over seeded rows would never reach it.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("improvement-plans/", views.improvementplan_list, name="improvementplan_list"),
    path("improvement-plans/add/", views.improvementplan_create,
         name="improvementplan_create"),
    path("improvement-plans/<int:pk>/", views.improvementplan_detail,
         name="improvementplan_detail"),
    path("improvement-plans/<int:pk>/edit/", views.improvementplan_edit,
         name="improvementplan_edit"),
    path("improvement-plans/<int:pk>/activate/", views.improvementplan_activate,
         name="improvementplan_activate"),
    path("improvement-plans/<int:pk>/monitor/", views.improvementplan_monitor,
         name="improvementplan_monitor"),
    path("improvement-plans/<int:pk>/acknowledge/", views.improvementplan_acknowledge,
         name="improvementplan_acknowledge"),
    path("improvement-plans/<int:pk>/close/", views.improvementplan_close,
         name="improvementplan_close"),
    path("improvement-plans/<int:pk>/cancel/", views.improvementplan_cancel,
         name="improvementplan_cancel"),
    path("improvement-plans/<int:pk>/delete/", views.improvementplan_delete,
         name="improvementplan_delete"),
]
