"""HRM 3.20 Continuous Feedback — Oneononemeeting URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 1:1 Meetings
    path("one-on-ones/", views.oneononemeeting_list, name="oneononemeeting_list"),
    path("one-on-ones/add/", views.oneononemeeting_create, name="oneononemeeting_create"),
    path("one-on-ones/<int:pk>/", views.oneononemeeting_detail, name="oneononemeeting_detail"),
    path("one-on-ones/<int:pk>/edit/", views.oneononemeeting_edit, name="oneononemeeting_edit"),
    path("one-on-ones/<int:pk>/delete/", views.oneononemeeting_delete, name="oneononemeeting_delete"),
    path("one-on-ones/<int:pk>/complete/", views.oneononemeeting_complete, name="oneononemeeting_complete"),
    path("one-on-ones/<int:pk>/cancel/", views.oneononemeeting_cancel, name="oneononemeeting_cancel"),
]
