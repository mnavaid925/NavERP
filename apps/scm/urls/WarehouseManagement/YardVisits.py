"""SCM 4.4 Warehouse Management — YardVisit URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("yard/", views.yardvisit_list, name="yardvisit_list"),
    path("yard/add/", views.yardvisit_create, name="yardvisit_create"),
    path("yard/<int:pk>/", views.yardvisit_detail, name="yardvisit_detail"),
    path("yard/<int:pk>/edit/", views.yardvisit_edit, name="yardvisit_edit"),
    path("yard/<int:pk>/delete/", views.yardvisit_delete, name="yardvisit_delete"),
    path("yard/<int:pk>/arrive/", views.yardvisit_arrive, name="yardvisit_arrive"),
    path("yard/<int:pk>/dock/", views.yardvisit_dock, name="yardvisit_dock"),
    path("yard/<int:pk>/depart/", views.yardvisit_depart, name="yardvisit_depart"),
    path("yard/<int:pk>/cancel/", views.yardvisit_cancel, name="yardvisit_cancel"),
]
