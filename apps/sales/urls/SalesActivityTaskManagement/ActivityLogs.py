"""Sales 8.8 — URLs for the sales activity register.

Nine routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR**: the literal ``activity-log/add/`` MUST
precede ``activity-log/<int:pk>/``, and the three engagement verbs are listed before the keyed pages
so they stay reachable.

The three verbs — ``mark_opened/``, ``mark_clicked/`` and ``mark_replied/`` — are **POST-only** in
the view. They are the only writers of ``ActivityLog``'s frozen email counters, so a GET that moved
them would let a prefetch, a crawler or a link preview change a rep's engagement numbers by touching
a URL. ``@require_POST`` in the view is the enforcement; the ordering here only makes them findable.

Every pattern begins with the literal ``activity-log/``, verified free against the whole concatenated
``sales:urlpatterns`` list.
"""
from django.urls import path

from apps.sales.views.SalesActivityTaskManagement.ActivityLogs import (
    activity_log_create,
    activity_log_delete,
    activity_log_detail,
    activity_log_edit,
    activity_log_list,
    activity_log_mark_clicked,
    activity_log_mark_opened,
    activity_log_mark_replied,
)

urlpatterns = [
    path("activity-log/", activity_log_list, name="activity_log_list"),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path("activity-log/add/", activity_log_create, name="activity_log_create"),
    # ---- the three POST-only engagement verbs, listed before the keyed pages for readability ----
    path("activity-log/<int:pk>/opened/", activity_log_mark_opened, name="activity_log_mark_opened"),
    path("activity-log/<int:pk>/clicked/", activity_log_mark_clicked, name="activity_log_mark_clicked"),
    path("activity-log/<int:pk>/replied/", activity_log_mark_replied, name="activity_log_mark_replied"),
    path("activity-log/<int:pk>/edit/", activity_log_edit, name="activity_log_edit"),
    path("activity-log/<int:pk>/delete/", activity_log_delete, name="activity_log_delete"),
    # The bare keyed page is LAST.
    path("activity-log/<int:pk>/", activity_log_detail, name="activity_log_detail"),
]