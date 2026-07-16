"""HRM 3.20 Continuous Feedback — Meetingactionitem URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Meeting action items — created nested under a 1:1
    path("one-on-ones/<int:meeting_pk>/action-items/add/", views.meetingactionitem_create, name="meetingactionitem_create"),
    path("action-items/<int:pk>/", views.meetingactionitem_detail, name="meetingactionitem_detail"),
    path("action-items/<int:pk>/edit/", views.meetingactionitem_edit, name="meetingactionitem_edit"),
    path("action-items/<int:pk>/delete/", views.meetingactionitem_delete, name="meetingactionitem_delete"),
    path("action-items/<int:pk>/toggle/", views.meetingactionitem_toggle, name="meetingactionitem_toggle"),
]
