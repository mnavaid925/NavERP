"""HRM 3.37 Compensation & Benefits — Salarybenchmark URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.37 Compensation & Benefits
    path("compensation/salary-benchmarks/", views.salarybenchmark_list, name="salarybenchmark_list"),
    path("compensation/salary-benchmarks/add/", views.salarybenchmark_create, name="salarybenchmark_create"),
    path("compensation/salary-benchmarks/<int:pk>/", views.salarybenchmark_detail, name="salarybenchmark_detail"),
    path("compensation/salary-benchmarks/<int:pk>/edit/", views.salarybenchmark_edit, name="salarybenchmark_edit"),
    path("compensation/salary-benchmarks/<int:pk>/delete/", views.salarybenchmark_delete, name="salarybenchmark_delete"),
]
