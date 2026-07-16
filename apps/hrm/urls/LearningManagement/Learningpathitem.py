"""HRM 3.23 Learning Management (LMS) — Learningpathitem URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("learning-paths/<int:path_pk>/items/add/", views.learningpathitem_create, name="learningpathitem_create"),
    path("learning-path-items/", views.learningpathitem_list, name="learningpathitem_list"),
    path("learning-path-items/<int:pk>/", views.learningpathitem_detail, name="learningpathitem_detail"),
    path("learning-path-items/<int:pk>/edit/", views.learningpathitem_edit, name="learningpathitem_edit"),
    path("learning-path-items/<int:pk>/delete/", views.learningpathitem_delete, name="learningpathitem_delete"),
]
