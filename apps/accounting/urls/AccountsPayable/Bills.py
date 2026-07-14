"""Accounting 2.3 Accounts Payable — Bills URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.3 AP — Bills
    path("bills/", views.bill_list, name="bill_list"),
    path("bills/add/", views.bill_create, name="bill_create"),
    path("bills/<int:pk>/", views.bill_detail, name="bill_detail"),
    path("bills/<int:pk>/edit/", views.bill_edit, name="bill_edit"),
    path("bills/<int:pk>/delete/", views.bill_delete, name="bill_delete"),
    path("bills/<int:pk>/approve/", views.bill_approve, name="bill_approve"),
]
