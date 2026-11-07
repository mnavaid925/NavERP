from django.urls import path

from apps.bi.views.ConversationalBi import NarrativeExplanations as views

urlpatterns = [
    path("narratives/", views.narrative_explanation_list, name="narrative_explanation_list"),
    path("narratives/create/", views.narrative_explanation_create, name="narrative_explanation_create"),
    path("narratives/<int:pk>/", views.narrative_explanation_detail, name="narrative_explanation_detail"),
    path("narratives/<int:pk>/edit/", views.narrative_explanation_edit, name="narrative_explanation_edit"),
    path("narratives/<int:pk>/delete/", views.narrative_explanation_delete, name="narrative_explanation_delete"),
    path("narratives/<int:pk>/publish/", views.narrative_explanation_publish, name="narrative_explanation_publish"),
    path("narratives/<int:pk>/regenerate/", views.narrative_explanation_regenerate, name="narrative_explanation_regenerate"),
]
