"""Projects 7.9 — the activity feed's single computed route (prefix ``activity-feed/``).

One literal route and no ``<int:pk>`` sibling: the feed is a computed page over the four 7.9
registers plus the audit trail, not an entity (the ``task-board/`` / ``gantt-timeline/``
precedent). The first segment ``activity-feed/`` is a disjoint literal from every other module's in
this app.
"""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("activity-feed/", views.activity_feed, name="activity_feed"),
]
