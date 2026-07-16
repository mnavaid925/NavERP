"""HRM 3.10 Leave Management — Type URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Leave Types (3.10)
    path("leave-types/", views.leavetype_list, name="leavetype_list"),
    path("leave-types/add/", views.leavetype_create, name="leavetype_create"),
    path("leave-types/<int:pk>/", views.leavetype_detail, name="leavetype_detail"),
    path("leave-types/<int:pk>/edit/", views.leavetype_edit, name="leavetype_edit"),
    path("leave-types/<int:pk>/delete/", views.leavetype_delete, name="leavetype_delete"),
]
