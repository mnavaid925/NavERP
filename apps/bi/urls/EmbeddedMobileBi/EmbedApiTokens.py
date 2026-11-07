from django.urls import path

from apps.bi.views.EmbeddedMobileBi import EmbedApiTokens as views

urlpatterns = [
    path("api-tokens/", views.embed_api_token_list, name="embed_api_token_list"),
    path("api-tokens/create/", views.embed_api_token_create, name="embed_api_token_create"),
    path("api-tokens/<int:pk>/", views.embed_api_token_detail, name="embed_api_token_detail"),
    path("api-tokens/<int:pk>/edit/", views.embed_api_token_edit, name="embed_api_token_edit"),
    path("api-tokens/<int:pk>/delete/", views.embed_api_token_delete, name="embed_api_token_delete"),
    path("api-tokens/<int:pk>/revoke/", views.embed_api_token_revoke, name="embed_api_token_revoke"),
]
