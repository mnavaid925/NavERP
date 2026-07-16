"""HRM 3.34 Expense Management — Expensecategory URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.34 Expense Management
    path("expense-categories/", views.expensecategory_list, name="expensecategory_list"),
    path("expense-categories/add/", views.expensecategory_create, name="expensecategory_create"),
    path("expense-categories/<int:pk>/", views.expensecategory_detail, name="expensecategory_detail"),
    path("expense-categories/<int:pk>/edit/", views.expensecategory_edit, name="expensecategory_edit"),
    path("expense-categories/<int:pk>/delete/", views.expensecategory_delete, name="expensecategory_delete"),
]
