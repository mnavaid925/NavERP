"""Accounting 2.14 Audit & Controls — InternalControls URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.14 Audit & controls
    path("controls/", views.internal_control_list, name="internal_control_list"),
    path("controls/add/", views.internal_control_create, name="internal_control_create"),
    path("controls/<int:pk>/", views.internal_control_detail, name="internal_control_detail"),
    path("controls/<int:pk>/edit/", views.internal_control_edit, name="internal_control_edit"),
    path("controls/<int:pk>/delete/", views.internal_control_delete, name="internal_control_delete"),
]
