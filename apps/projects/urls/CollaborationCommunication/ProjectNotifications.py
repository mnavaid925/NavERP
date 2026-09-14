"""Projects 7.9 — ProjectNotification routes (prefix ``notifications/``).

``notifications/read-all/`` is listed BEFORE ``notifications/<int:pk>/``. It cannot actually be
swallowed by the int converter (``read-all`` is not an integer), but keeping the literal first is
the app-wide ordering rule and it keeps the module readable — the ``tasks/bulk-update/`` precedent
in 7.8's ``ProjectTasks.py``.

The first segment ``notifications/`` is a disjoint literal from every other module's in this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("notifications/", views.ntf_list, name="ntf_list"),
    path("notifications/read-all/", views.ntf_mark_all_read, name="ntf_mark_all_read"),
    path("notifications/<int:pk>/", views.ntf_detail, name="ntf_detail"),
    path("notifications/<int:pk>/read/", views.ntf_mark_read, name="ntf_mark_read"),
    path("notifications/<int:pk>/delete/", views.ntf_delete, name="ntf_delete"),
]
