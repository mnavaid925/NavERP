"""HRM 3.2 Organizational Structure — Costcenter URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Cost Centers (3.2 — core.OrgUnit companion)
    path("cost-centers/", views.costcenter_list, name="costcenter_list"),
    path("cost-centers/add/", views.costcenter_create, name="costcenter_create"),
    path("cost-centers/<int:pk>/", views.costcenter_detail, name="costcenter_detail"),
    path("cost-centers/<int:pk>/edit/", views.costcenter_edit, name="costcenter_edit"),
    path("cost-centers/<int:pk>/delete/", views.costcenter_delete, name="costcenter_delete"),
]
