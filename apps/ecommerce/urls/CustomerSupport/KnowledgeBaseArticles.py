from django.urls import path

from apps.ecommerce.views.CustomerSupport import KnowledgeBaseArticles as views

urlpatterns = [
    path("customer-support/articles/", views.knowledgebasearticle_list, name="knowledgebasearticle_list"),
    path("customer-support/articles/create/", views.knowledgebasearticle_create, name="knowledgebasearticle_create"),
    path("customer-support/articles/<int:pk>/", views.knowledgebasearticle_detail, name="knowledgebasearticle_detail"),
    path("customer-support/articles/<int:pk>/edit/", views.knowledgebasearticle_edit, name="knowledgebasearticle_edit"),
    path("customer-support/articles/<int:pk>/delete/", views.knowledgebasearticle_delete, name="knowledgebasearticle_delete"),
]
