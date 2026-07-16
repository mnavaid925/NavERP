"""HRM 3.23 Learning Management (LMS) — Learningcontentitem URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.23 Learning Management (LMS) ----
    # Learning content items (lessons, nested-create under a course)
    path("training-courses/<int:course_pk>/content/add/", views.learningcontentitem_create, name="learningcontentitem_create"),
    path("learning-content/", views.learningcontentitem_list, name="learningcontentitem_list"),
    path("learning-content/<int:pk>/", views.learningcontentitem_detail, name="learningcontentitem_detail"),
    path("learning-content/<int:pk>/edit/", views.learningcontentitem_edit, name="learningcontentitem_edit"),
    path("learning-content/<int:pk>/delete/", views.learningcontentitem_delete, name="learningcontentitem_delete"),
]
