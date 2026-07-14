"""CRM 1.4 Customer Service & Support — KnowledgeBase URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Knowledge base / Solutions (1.4)
    path("knowledge/", views.knowledgearticle_list, name="knowledgearticle_list"),
    path("knowledge/add/", views.knowledgearticle_create, name="knowledgearticle_create"),
    path("knowledge/<int:pk>/", views.knowledgearticle_detail, name="knowledgearticle_detail"),
    path("knowledge/<int:pk>/edit/", views.knowledgearticle_edit, name="knowledgearticle_edit"),
    path("knowledge/<int:pk>/delete/", views.knowledgearticle_delete, name="knowledgearticle_delete"),
]
