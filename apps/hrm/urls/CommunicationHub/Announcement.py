"""HRM 3.27 Communication Hub — Announcement URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Announcements
    path("announcements/", views.announcement_list, name="announcement_list"),
    path("announcements/add/", views.announcement_create, name="announcement_create"),
    path("announcements/<int:pk>/", views.announcement_detail, name="announcement_detail"),
    path("announcements/<int:pk>/edit/", views.announcement_edit, name="announcement_edit"),
    path("announcements/<int:pk>/delete/", views.announcement_delete, name="announcement_delete"),
    path("announcements/<int:pk>/publish/", views.announcement_publish, name="announcement_publish"),
    path("announcements/<int:pk>/archive/", views.announcement_archive, name="announcement_archive"),
]
