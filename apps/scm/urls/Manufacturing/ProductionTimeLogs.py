"""SCM 4.8 Manufacturing — ProductionTimeLog routes (prefix ``time-logs/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("time-logs/", views.productiontimelog_list, name="productiontimelog_list"),
    path("time-logs/add/", views.productiontimelog_create, name="productiontimelog_create"),
    path("time-logs/<int:pk>/", views.productiontimelog_detail, name="productiontimelog_detail"),
    path("time-logs/<int:pk>/edit/", views.productiontimelog_edit, name="productiontimelog_edit"),
    path("time-logs/<int:pk>/delete/", views.productiontimelog_delete,
         name="productiontimelog_delete"),
]
