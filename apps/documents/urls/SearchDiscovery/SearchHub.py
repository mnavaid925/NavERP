from django.urls import path

from apps.documents import views

urlpatterns = [
    path("search/", views.search_hub, name="search_hub"),
    path("search/click/<int:pk>/", views.search_click_track, name="search_click_track"),
    path("search/export/", views.search_export_csv, name="search_export_csv"),
]
