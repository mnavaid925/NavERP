from django.urls import path

from apps.bi.views.SelfServiceAnalytics import SavedAnalysisViews as views

urlpatterns = [
    path("saved-views/", views.saved_analysis_view_list, name="saved_analysis_view_list"),
    path("saved-views/create/", views.saved_analysis_view_create, name="saved_analysis_view_create"),
    path("saved-views/<int:pk>/", views.saved_analysis_view_detail, name="saved_analysis_view_detail"),
    path("saved-views/<int:pk>/edit/", views.saved_analysis_view_edit, name="saved_analysis_view_edit"),
    path("saved-views/<int:pk>/delete/", views.saved_analysis_view_delete, name="saved_analysis_view_delete"),
    path("saved-views/<int:pk>/clone/", views.saved_analysis_view_clone, name="saved_analysis_view_clone"),
    path("saved-views/<int:pk>/share/", views.saved_analysis_view_share, name="saved_analysis_view_share"),
    path("saved-views/<int:pk>/explore/", views.saved_analysis_view_explore, name="saved_analysis_view_explore"),
]
