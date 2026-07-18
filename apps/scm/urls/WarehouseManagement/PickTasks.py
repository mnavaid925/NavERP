"""SCM 4.4 Warehouse Management — PickTask URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("picks/", views.picktask_list, name="picktask_list"),
    path("picks/add/", views.picktask_create, name="picktask_create"),
    path("picks/<int:pk>/", views.picktask_detail, name="picktask_detail"),
    path("picks/<int:pk>/edit/", views.picktask_edit, name="picktask_edit"),
    path("picks/<int:pk>/delete/", views.picktask_delete, name="picktask_delete"),
    path("picks/<int:pk>/release/", views.picktask_release, name="picktask_release"),
    path("picks/<int:pk>/confirm/", views.picktask_confirm, name="picktask_confirm"),
    path("picks/<int:pk>/pack/", views.picktask_pack, name="picktask_pack"),
    path("picks/<int:pk>/cancel/", views.picktask_cancel, name="picktask_cancel"),
]
