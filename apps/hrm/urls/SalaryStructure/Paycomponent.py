"""HRM 3.13 Salary Structure — Paycomponent URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Pay Components (3.13 Salary Structure)
    path("pay-components/", views.paycomponent_list, name="paycomponent_list"),
    path("pay-components/add/", views.paycomponent_create, name="paycomponent_create"),
    path("pay-components/<int:pk>/", views.paycomponent_detail, name="paycomponent_detail"),
    path("pay-components/<int:pk>/edit/", views.paycomponent_edit, name="paycomponent_edit"),
    path("pay-components/<int:pk>/delete/", views.paycomponent_delete, name="paycomponent_delete"),
]
