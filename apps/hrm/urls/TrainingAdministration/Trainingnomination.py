"""HRM 3.24 Training Administration — Trainingnomination URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ---- 3.24 Training Administration ----
    # Nominations + approval workflow
    path("training-nominations/", views.trainingnomination_list, name="trainingnomination_list"),
    path("training-nominations/add/", views.trainingnomination_create, name="trainingnomination_create"),
    path("training-nominations/<int:pk>/", views.trainingnomination_detail, name="trainingnomination_detail"),
    path("training-nominations/<int:pk>/edit/", views.trainingnomination_edit, name="trainingnomination_edit"),
    path("training-nominations/<int:pk>/delete/", views.trainingnomination_delete, name="trainingnomination_delete"),
    path("training-nominations/<int:pk>/approve/", views.trainingnomination_approve, name="trainingnomination_approve"),
    path("training-nominations/<int:pk>/reject/", views.trainingnomination_reject, name="trainingnomination_reject"),
    path("training-nominations/<int:pk>/waitlist/", views.trainingnomination_waitlist, name="trainingnomination_waitlist"),
    path("training-nominations/<int:pk>/cancel/", views.trainingnomination_cancel, name="trainingnomination_cancel"),
    path("training-nominations/<int:pk>/withdraw/", views.trainingnomination_withdraw, name="trainingnomination_withdraw"),
]
