"""SCM 4.4 Warehouse Management — PutawayTask URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("putaway/", views.putawaytask_list, name="putawaytask_list"),
    path("putaway/add/", views.putawaytask_create, name="putawaytask_create"),
    path("putaway/<int:pk>/", views.putawaytask_detail, name="putawaytask_detail"),
    path("putaway/<int:pk>/edit/", views.putawaytask_edit, name="putawaytask_edit"),
    path("putaway/<int:pk>/delete/", views.putawaytask_delete, name="putawaytask_delete"),
    path("putaway/<int:pk>/start/", views.putawaytask_start, name="putawaytask_start"),
    path("putaway/<int:pk>/complete/", views.putawaytask_complete, name="putawaytask_complete"),
    path("putaway/<int:pk>/cancel/", views.putawaytask_cancel, name="putawaytask_cancel"),
]
