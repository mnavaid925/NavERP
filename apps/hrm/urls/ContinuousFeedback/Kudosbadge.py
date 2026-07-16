"""HRM 3.20 Continuous Feedback — Kudosbadge URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.20 Continuous Feedback ----
    # KudosBadge (recognition catalog)
    path("kudos-badges/", views.kudosbadge_list, name="kudosbadge_list"),
    path("kudos-badges/add/", views.kudosbadge_create, name="kudosbadge_create"),
    path("kudos-badges/<int:pk>/", views.kudosbadge_detail, name="kudosbadge_detail"),
    path("kudos-badges/<int:pk>/edit/", views.kudosbadge_edit, name="kudosbadge_edit"),
    path("kudos-badges/<int:pk>/delete/", views.kudosbadge_delete, name="kudosbadge_delete"),
]
