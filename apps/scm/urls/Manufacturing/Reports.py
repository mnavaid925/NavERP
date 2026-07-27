"""SCM 4.8 Manufacturing — computed report routes (``mrp/``, ``production-schedule/``).

Both are read-only GET pages with no pk — they own no model.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("mrp/", views.mrp_report, name="mrp_report"),
    path("production-schedule/", views.production_schedule, name="production_schedule"),
]
