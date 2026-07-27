"""SCM 4.8 Manufacturing — WorkCenter routes (prefix ``work-centers/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("work-centers/", views.workcenter_list, name="workcenter_list"),
    path("work-centers/add/", views.workcenter_create, name="workcenter_create"),
    path("work-centers/<int:pk>/", views.workcenter_detail, name="workcenter_detail"),
    path("work-centers/<int:pk>/edit/", views.workcenter_edit, name="workcenter_edit"),
    path("work-centers/<int:pk>/delete/", views.workcenter_delete, name="workcenter_delete"),
]
