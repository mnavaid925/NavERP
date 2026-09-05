"""Procurement 6.16 Supplier Performance & Evaluation — SupplierFeedback URL patterns.

One first segment, ``supplier-feedback/``, collision-checked as a whole component against the
concatenated ``urls/__init__.py`` inventory. It is a LITERAL, like every other first component in
``apps/procurement/urls/`` — this app's standing guarantee is that no route anywhere in it opens
with a converter, and 6.16 does not break it.

Order is behaviour: Django resolves first-match-wins, so the literal ``add/`` is declared BEFORE
``<int:pk>/``. (``int`` would not swallow ``add`` anyway, but the ordering is the rule that keeps
that true when a ``<str:...>`` route is added next to it.)

**Four POST-only routes.** ``submit/``, ``decline/``, ``expire/`` and ``delete/`` are all
``@require_POST`` in the view; the list and detail pages post to them through a
``{% csrf_token %}`` form with an ``onclick`` confirm rather than linking to them. The three verbs
exist so every ``STATUS_CHOICES`` value is reachable — ``requested`` on create, and the other
three here. A status nothing can set is a lie in a dropdown.

``supplierfeedback_list`` and ``supplierfeedback_detail`` are also the two names Entity 1's KPI
detail page and Entity 2's evaluation detail page already emit ``{% url %}`` tags for, so this
module is what makes both of those pages resolvable. One of them sits inside an ``{% empty %}``
branch, which fires precisely when there is no data to link to — a smoke test over seeded rows
would never reach it.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("supplier-feedback/", views.supplierfeedback_list, name="supplierfeedback_list"),
    path("supplier-feedback/add/", views.supplierfeedback_create,
         name="supplierfeedback_create"),
    path("supplier-feedback/<int:pk>/", views.supplierfeedback_detail,
         name="supplierfeedback_detail"),
    path("supplier-feedback/<int:pk>/edit/", views.supplierfeedback_edit,
         name="supplierfeedback_edit"),
    path("supplier-feedback/<int:pk>/submit/", views.supplierfeedback_submit,
         name="supplierfeedback_submit"),
    path("supplier-feedback/<int:pk>/decline/", views.supplierfeedback_decline,
         name="supplierfeedback_decline"),
    path("supplier-feedback/<int:pk>/expire/", views.supplierfeedback_expire,
         name="supplierfeedback_expire"),
    path("supplier-feedback/<int:pk>/delete/", views.supplierfeedback_delete,
         name="supplierfeedback_delete"),
]
