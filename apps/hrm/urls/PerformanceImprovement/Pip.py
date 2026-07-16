"""HRM 3.21 Performance Improvement — Pip URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.21 Performance Improvement ----
    # Performance Improvement Plans (PIPs)
    path("pips/", views.pip_list, name="pip_list"),
    path("pips/add/", views.pip_create, name="pip_create"),
    path("pips/<int:pk>/", views.pip_detail, name="pip_detail"),
    path("pips/<int:pk>/edit/", views.pip_edit, name="pip_edit"),
    path("pips/<int:pk>/delete/", views.pip_delete, name="pip_delete"),
    path("pips/<int:pk>/submit/", views.pip_submit, name="pip_submit"),
    path("pips/<int:pk>/hr-approve/", views.pip_hr_approve, name="pip_hr_approve"),
    path("pips/<int:pk>/acknowledge/", views.pip_acknowledge, name="pip_acknowledge"),
    path("pips/<int:pk>/close/", views.pip_close, name="pip_close"),
    path("pips/<int:pk>/extend/", views.pip_extend, name="pip_extend"),
]
