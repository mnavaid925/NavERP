"""Projects 7.15 Financial & Billing Management — ProjectRateCard URLs.
"""
from django.urls import path

from apps.projects.views.FinancialBillingManagement import RateCards as views

urlpatterns = [
    path("financial/rate-cards/", views.rtc_list, name="rtc_list"),
    path("financial/rate-cards/create/", views.rtc_create, name="rtc_create"),
    path("financial/rate-cards/<int:pk>/", views.rtc_detail, name="rtc_detail"),
    path("financial/rate-cards/<int:pk>/edit/", views.rtc_edit, name="rtc_edit"),
    path("financial/rate-cards/<int:pk>/delete/", views.rtc_delete, name="rtc_delete"),
]
