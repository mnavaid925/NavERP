"""HRM 3.36 Helpdesk — Helpdeskcategory URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("helpdesk/categories/", views.helpdeskcategory_list, name="helpdeskcategory_list"),
    path("helpdesk/categories/add/", views.helpdeskcategory_create, name="helpdeskcategory_create"),
    path("helpdesk/categories/<int:pk>/", views.helpdeskcategory_detail, name="helpdeskcategory_detail"),
    path("helpdesk/categories/<int:pk>/edit/", views.helpdeskcategory_edit, name="helpdeskcategory_edit"),
    path("helpdesk/categories/<int:pk>/delete/", views.helpdeskcategory_delete, name="helpdeskcategory_delete"),
]
