"""URL patterns for Asset Knowledge Base & Failure RCA Articles (11.16)."""

from django.urls import path

from apps.assets.views.AssetDocumentKnowledge import AssetKnowledgeArticles as views

urlpatterns = [
    path(
        "knowledge-base/",
        views.asset_knowledge_article_list,
        name="asset_knowledge_article_list",
    ),
    path(
        "knowledge-base/create/",
        views.asset_knowledge_article_create,
        name="asset_knowledge_article_create",
    ),
    path(
        "knowledge-base/export-csv/",
        views.asset_knowledge_article_export_csv,
        name="asset_knowledge_article_export_csv",
    ),
    path(
        "knowledge-base/<int:pk>/",
        views.asset_knowledge_article_detail,
        name="asset_knowledge_article_detail",
    ),
    path(
        "knowledge-base/<int:pk>/edit/",
        views.asset_knowledge_article_edit,
        name="asset_knowledge_article_edit",
    ),
    path(
        "knowledge-base/<int:pk>/delete/",
        views.asset_knowledge_article_delete,
        name="asset_knowledge_article_delete",
    ),
    path(
        "knowledge-base/<int:pk>/download/",
        views.asset_knowledge_article_download,
        name="asset_knowledge_article_download",
    ),
    path(
        "knowledge-base/<int:pk>/submit-review/",
        views.asset_knowledge_article_submit_review,
        name="asset_knowledge_article_submit_review",
    ),
    path(
        "knowledge-base/<int:pk>/publish/",
        views.asset_knowledge_article_publish,
        name="asset_knowledge_article_publish",
    ),
    path(
        "knowledge-base/<int:pk>/mark-helpful/",
        views.asset_knowledge_article_mark_helpful,
        name="asset_knowledge_article_mark_helpful",
    ),
    path(
        "knowledge-base/<int:pk>/retire/",
        views.asset_knowledge_article_retire,
        name="asset_knowledge_article_retire",
    ),
]
