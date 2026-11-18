from django.urls import path

from apps.quality.views.InProcessQuality import FirstArticleInspections as views

urlpatterns = [
    path("first-article-inspections/", views.first_article_inspection_list, name="first_article_inspection_list"),
    path("first-article-inspections/create/", views.first_article_inspection_create, name="first_article_inspection_create"),
    path("first-article-inspections/export/csv/", views.first_article_inspection_export_csv, name="first_article_inspection_export_csv"),
    path("first-article-inspections/<int:pk>/", views.first_article_inspection_detail, name="first_article_inspection_detail"),
    path("first-article-inspections/<int:pk>/edit/", views.first_article_inspection_edit, name="first_article_inspection_edit"),
    path("first-article-inspections/<int:pk>/release/", views.first_article_inspection_release, name="first_article_inspection_release"),
    path("first-article-inspections/<int:pk>/delete/", views.first_article_inspection_delete, name="first_article_inspection_delete"),
]
