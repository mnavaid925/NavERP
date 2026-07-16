"""HRM 3.25 Personal Information — Employeebankaccount URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Bank Accounts (admin-gated writes; verify/reject workflow)
    path("bank-accounts/", views.employeebankaccount_list, name="employeebankaccount_list"),
    path("bank-accounts/add/", views.employeebankaccount_create, name="employeebankaccount_create"),
    path("bank-accounts/<int:pk>/", views.employeebankaccount_detail, name="employeebankaccount_detail"),
    path("bank-accounts/<int:pk>/edit/", views.employeebankaccount_edit, name="employeebankaccount_edit"),
    path("bank-accounts/<int:pk>/delete/", views.employeebankaccount_delete, name="employeebankaccount_delete"),
    path("bank-accounts/<int:pk>/verify/", views.employeebankaccount_verify, name="employeebankaccount_verify"),
    path("bank-accounts/<int:pk>/reject/", views.employeebankaccount_reject, name="employeebankaccount_reject"),
]
