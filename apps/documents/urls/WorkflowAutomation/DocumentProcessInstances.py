from django.urls import path

from apps.documents import views

urlpatterns = [
    path("bpm/instances/", views.process_instance_list, name="process_instance_list"),
    path("bpm/instances/create/", views.process_instance_create, name="process_instance_create"),
    path("bpm/instances/<int:pk>/", views.process_instance_detail, name="process_instance_detail"),
    path("bpm/instances/<int:pk>/edit/", views.process_instance_edit, name="process_instance_edit"),
    path("bpm/instances/<int:pk>/delete/", views.process_instance_delete, name="process_instance_delete"),
    path("bpm/instances/<int:pk>/advance/", views.process_instance_advance, name="process_instance_advance"),
    path("bpm/instances/<int:pk>/cancel/", views.process_instance_cancel, name="process_instance_cancel"),
]
