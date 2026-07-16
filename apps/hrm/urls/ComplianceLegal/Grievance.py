"""HRM 3.39 Compliance & Legal — Grievance URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compliance/grievances/", views.grievance_list, name="grievance_list"),
    path("compliance/grievances/add/", views.grievance_create, name="grievance_create"),
    path("compliance/grievances/<int:pk>/", views.grievance_detail, name="grievance_detail"),
    path("compliance/grievances/<int:pk>/edit/", views.grievance_edit, name="grievance_edit"),
    path("compliance/grievances/<int:pk>/delete/", views.grievance_delete, name="grievance_delete"),
    path("compliance/grievances/<int:pk>/assign/", views.grievance_assign, name="grievance_assign"),
    path("compliance/grievances/<int:pk>/resolve/", views.grievance_resolve, name="grievance_resolve"),
    path("compliance/grievances/<int:pk>/close/", views.grievance_close, name="grievance_close"),
    path("compliance/grievances/<int:pk>/withdraw/", views.grievance_withdraw, name="grievance_withdraw"),
]
