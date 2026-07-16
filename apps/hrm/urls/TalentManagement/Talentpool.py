"""HRM 3.38 Talent Management & Succession — Talentpool URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.38 Talent Management & Succession Planning (all @tenant_admin_required — HR-confidential)
    path("talent/pools/", views.talentpool_list, name="talentpool_list"),
    path("talent/pools/add/", views.talentpool_create, name="talentpool_create"),
    path("talent/pools/<int:pk>/", views.talentpool_detail, name="talentpool_detail"),
    path("talent/pools/<int:pk>/edit/", views.talentpool_edit, name="talentpool_edit"),
    path("talent/pools/<int:pk>/delete/", views.talentpool_delete, name="talentpool_delete"),
]
