from django.urls import path

from apps.documents import views

urlpatterns = [
    path("bpm/processes/", views.process_definition_list, name="process_definition_list"),
    path("bpm/processes/create/", views.process_definition_create, name="process_definition_create"),
    path("bpm/processes/<int:pk>/", views.process_definition_detail, name="process_definition_detail"),
    path("bpm/processes/<int:pk>/edit/", views.process_definition_edit, name="process_definition_edit"),
    path("bpm/processes/<int:pk>/delete/", views.process_definition_delete, name="process_definition_delete"),
    path("bpm/processes/<int:pk>/designer/", views.process_definition_designer, name="process_definition_designer"),
    path("bpm/processes/<int:pk>/publish/", views.process_definition_publish, name="process_definition_publish"),
    path("bpm/processes/<int:pk>/deprecate/", views.process_definition_deprecate, name="process_definition_deprecate"),
]
