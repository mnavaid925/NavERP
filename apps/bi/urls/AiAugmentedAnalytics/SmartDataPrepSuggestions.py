from django.urls import path

from apps.bi.views.AiAugmentedAnalytics import SmartDataPrepSuggestions as views

urlpatterns = [
    path("data-prep-suggestions/", views.smart_data_prep_suggestion_list, name="smart_data_prep_suggestion_list"),
    path("data-prep-suggestions/new/", views.smart_data_prep_suggestion_create, name="smart_data_prep_suggestion_create"),
    path("data-prep-suggestions/<int:pk>/", views.smart_data_prep_suggestion_detail, name="smart_data_prep_suggestion_detail"),
    path("data-prep-suggestions/<int:pk>/edit/", views.smart_data_prep_suggestion_edit, name="smart_data_prep_suggestion_edit"),
    path("data-prep-suggestions/<int:pk>/delete/", views.smart_data_prep_suggestion_delete, name="smart_data_prep_suggestion_delete"),
    path("data-prep-suggestions/<int:pk>/action/", views.smart_data_prep_suggestion_action, name="smart_data_prep_suggestion_action"),
]
