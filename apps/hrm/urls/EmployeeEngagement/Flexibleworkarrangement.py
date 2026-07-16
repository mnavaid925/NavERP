"""HRM 3.41 Employee Engagement & Wellbeing — Flexibleworkarrangement URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("engagement/flexible-work/", views.flexibleworkarrangement_list, name="flexibleworkarrangement_list"),
    path("engagement/flexible-work/add/", views.flexibleworkarrangement_create, name="flexibleworkarrangement_create"),
    path("engagement/flexible-work/<int:pk>/", views.flexibleworkarrangement_detail, name="flexibleworkarrangement_detail"),
    path("engagement/flexible-work/<int:pk>/edit/", views.flexibleworkarrangement_edit, name="flexibleworkarrangement_edit"),
    path("engagement/flexible-work/<int:pk>/delete/", views.flexibleworkarrangement_delete, name="flexibleworkarrangement_delete"),
    path("engagement/flexible-work/<int:pk>/submit/", views.flexibleworkarrangement_submit, name="flexibleworkarrangement_submit"),
    path("engagement/flexible-work/<int:pk>/cancel/", views.flexibleworkarrangement_cancel, name="flexibleworkarrangement_cancel"),
    path("engagement/flexible-work/<int:pk>/approve/", views.flexibleworkarrangement_approve, name="flexibleworkarrangement_approve"),
    path("engagement/flexible-work/<int:pk>/reject/", views.flexibleworkarrangement_reject, name="flexibleworkarrangement_reject"),
]
