"""HRM 3.25 Personal Information — MyInfoEdit URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("my-info/edit/", views.my_info_edit, name="my_info_edit"),
]
