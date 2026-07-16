"""HRM 3.21 Performance Improvement — Warningletter URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Warning letters
    path("warning-letters/", views.warningletter_list, name="warningletter_list"),
    path("warning-letters/add/", views.warningletter_create, name="warningletter_create"),
    path("warning-letters/<int:pk>/", views.warningletter_detail, name="warningletter_detail"),
    path("warning-letters/<int:pk>/edit/", views.warningletter_edit, name="warningletter_edit"),
    path("warning-letters/<int:pk>/delete/", views.warningletter_delete, name="warningletter_delete"),
    path("warning-letters/<int:pk>/issue/", views.warningletter_issue, name="warningletter_issue"),
    path("warning-letters/<int:pk>/acknowledge/", views.warningletter_acknowledge, name="warningletter_acknowledge"),
    path("warning-letters/<int:pk>/print/", views.warningletter_print, name="warningletter_print"),
]
