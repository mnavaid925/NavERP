"""HRM 3.4 Employee Offboarding — Finalsettlement URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Final Settlements (3.4) — CRUD + workflow
    path("settlements/", views.finalsettlement_list, name="finalsettlement_list"),
    path("settlements/add/", views.finalsettlement_create, name="finalsettlement_create"),
    path("settlements/<int:pk>/", views.finalsettlement_detail, name="finalsettlement_detail"),
    path("settlements/<int:pk>/edit/", views.finalsettlement_edit, name="finalsettlement_edit"),
    path("settlements/<int:pk>/delete/", views.finalsettlement_delete, name="finalsettlement_delete"),
    path("settlements/<int:pk>/compute/", views.finalsettlement_compute, name="finalsettlement_compute"),
    path("settlements/<int:pk>/hr-approve/", views.finalsettlement_hr_approve, name="finalsettlement_hr_approve"),
    path("settlements/<int:pk>/finance-approve/", views.finalsettlement_finance_approve, name="finalsettlement_finance_approve"),
    path("settlements/<int:pk>/mark-paid/", views.finalsettlement_mark_paid, name="finalsettlement_mark_paid"),
]
