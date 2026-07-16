"""HRM 3.19 Performance Review — Performancereview URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Performance reviews (self/manager/peer/upward) + submit/share/acknowledge/calibrate workflow
    path("reviews/", views.performancereview_list, name="performancereview_list"),
    path("reviews/add/", views.performancereview_create, name="performancereview_create"),
    path("reviews/<int:pk>/", views.performancereview_detail, name="performancereview_detail"),
    path("reviews/<int:pk>/edit/", views.performancereview_edit, name="performancereview_edit"),
    path("reviews/<int:pk>/delete/", views.performancereview_delete, name="performancereview_delete"),
    path("reviews/<int:pk>/submit/", views.performancereview_submit, name="performancereview_submit"),
    path("reviews/<int:pk>/share/", views.performancereview_share, name="performancereview_share"),
    path("reviews/<int:pk>/acknowledge/", views.performancereview_acknowledge, name="performancereview_acknowledge"),
    path("reviews/<int:pk>/calibrate/", views.performancereview_calibrate, name="performancereview_calibrate"),
]
