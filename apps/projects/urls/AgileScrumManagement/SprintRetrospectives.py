"""Projects 7.13 Agile & Scrum Management — SprintRetrospective URLs.
"""
from django.urls import path

from apps.projects.views.AgileScrumManagement import (
    SprintRetrospectives as views,
)

urlpatterns = [
    path("agile/retrospectives/", views.ret_list, name="ret_list"),
    path("agile/retrospectives/add/", views.ret_create, name="ret_create"),
    path("agile/retrospectives/<int:pk>/", views.ret_detail, name="ret_detail"),
    path("agile/retrospectives/<int:pk>/edit/", views.ret_edit, name="ret_edit"),
    path("agile/retrospectives/<int:pk>/delete/", views.ret_delete, name="ret_delete"),
    path("agile/retrospectives/<int:pk>/open/", views.ret_open, name="ret_open"),
    path("agile/retrospectives/<int:pk>/close/", views.ret_close, name="ret_close"),
]
