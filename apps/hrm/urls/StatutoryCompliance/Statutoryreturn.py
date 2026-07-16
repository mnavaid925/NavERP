"""HRM 3.15 Statutory Compliance — Statutoryreturn URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Statutory returns / challans (PF/ESI/PT/TDS/LWF) — CRUD + aggregation + filing workflow
    path("statutory-returns/", views.statutoryreturn_list, name="statutoryreturn_list"),
    path("statutory-returns/add/", views.statutoryreturn_create, name="statutoryreturn_create"),
    path("statutory-returns/<int:pk>/", views.statutoryreturn_detail, name="statutoryreturn_detail"),
    path("statutory-returns/<int:pk>/edit/", views.statutoryreturn_edit, name="statutoryreturn_edit"),
    path("statutory-returns/<int:pk>/delete/", views.statutoryreturn_delete, name="statutoryreturn_delete"),
    path("statutory-returns/<int:pk>/generate/", views.statutoryreturn_generate, name="statutoryreturn_generate"),
    path("statutory-returns/<int:pk>/mark-filed/", views.statutoryreturn_mark_filed, name="statutoryreturn_mark_filed"),
    path("statutory-returns/<int:pk>/mark-paid/", views.statutoryreturn_mark_paid, name="statutoryreturn_mark_paid"),
]
