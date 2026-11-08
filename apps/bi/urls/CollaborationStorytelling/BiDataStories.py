from django.urls import path

from apps.bi.views.CollaborationStorytelling import BiDataStories as views

urlpatterns = [
    path("stories/", views.bi_data_story_list, name="bi_data_story_list"),
    path("stories/create/", views.bi_data_story_create, name="bi_data_story_create"),
    path("stories/<int:pk>/", views.bi_data_story_detail, name="bi_data_story_detail"),
    path("stories/<int:pk>/edit/", views.bi_data_story_edit, name="bi_data_story_edit"),
    path("stories/<int:pk>/delete/", views.bi_data_story_delete, name="bi_data_story_delete"),
    path("stories/<int:pk>/presentation/", views.bi_data_story_presentation, name="bi_data_story_presentation"),
    path("stories/<int:pk>/export-office/", views.bi_data_story_export_office, name="bi_data_story_export_office"),
]
