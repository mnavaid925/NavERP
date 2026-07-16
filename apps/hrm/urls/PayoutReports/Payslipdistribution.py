"""HRM 3.17 Payout & Reports — Payslipdistribution URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Payslip distribution (send / view / download tracking)
    path("payslip-distributions/", views.payslipdistribution_list, name="payslipdistribution_list"),
    path("payslip-distributions/<int:pk>/", views.payslipdistribution_detail, name="payslipdistribution_detail"),
    path("payslip-distributions/<int:pk>/send/", views.payslipdistribution_send, name="payslipdistribution_send"),
    path("payslip-distributions/<int:pk>/mark-viewed/", views.payslipdistribution_mark_viewed, name="payslipdistribution_mark_viewed"),
    path("payslip-distributions/<int:pk>/mark-downloaded/", views.payslipdistribution_mark_downloaded, name="payslipdistribution_mark_downloaded"),
    path("payslip-distributions/send-cycle/", views.payslipdistribution_send_cycle, name="payslipdistribution_send_cycle"),
]
