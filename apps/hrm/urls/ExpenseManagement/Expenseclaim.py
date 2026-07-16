"""HRM 3.34 Expense Management — Expenseclaim URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("expense-claims/", views.expenseclaim_list, name="expenseclaim_list"),
    path("expense-claims/add/", views.expenseclaim_create, name="expenseclaim_create"),
    path("expense-claims/<int:pk>/", views.expenseclaim_detail, name="expenseclaim_detail"),
    path("expense-claims/<int:pk>/edit/", views.expenseclaim_edit, name="expenseclaim_edit"),
    path("expense-claims/<int:pk>/delete/", views.expenseclaim_delete, name="expenseclaim_delete"),
    path("expense-claims/<int:pk>/submit/", views.expenseclaim_submit, name="expenseclaim_submit"),
    path("expense-claims/<int:pk>/manager-approve/", views.expenseclaim_manager_approve, name="expenseclaim_manager_approve"),
    path("expense-claims/<int:pk>/approve/", views.expenseclaim_approve, name="expenseclaim_approve"),
    path("expense-claims/<int:pk>/reject/", views.expenseclaim_reject, name="expenseclaim_reject"),
    path("expense-claims/<int:pk>/cancel/", views.expenseclaim_cancel, name="expenseclaim_cancel"),
    path("expense-claims/<int:pk>/reimburse/", views.expenseclaim_reimburse, name="expenseclaim_reimburse"),
]
