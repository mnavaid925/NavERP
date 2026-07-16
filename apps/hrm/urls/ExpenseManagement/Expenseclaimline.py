"""HRM 3.34 Expense Management — Expenseclaimline URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("expense-claims/<int:claim_pk>/lines/add/", views.expenseclaimline_add, name="expenseclaimline_add"),
    path("expense-lines/<int:pk>/edit/", views.expenseclaimline_edit, name="expenseclaimline_edit"),
    path("expense-lines/<int:pk>/delete/", views.expenseclaimline_delete, name="expenseclaimline_delete"),
]
