"""HRM 3.21 Performance Improvement — Pipcheckin URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # PIP check-ins — created nested under a PIP
    path("pips/<int:pip_pk>/check-ins/add/", views.pipcheckin_create, name="pipcheckin_create"),
    path("pip-check-ins/<int:pk>/", views.pipcheckin_detail, name="pipcheckin_detail"),
    path("pip-check-ins/<int:pk>/edit/", views.pipcheckin_edit, name="pipcheckin_edit"),
    path("pip-check-ins/<int:pk>/delete/", views.pipcheckin_delete, name="pipcheckin_delete"),
]
