"""HRM 3.36 Helpdesk — Knowledgearticle URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("helpdesk/knowledge-base/", views.knowledgearticle_list, name="knowledgearticle_list"),
    path("helpdesk/knowledge-base/add/", views.knowledgearticle_create, name="knowledgearticle_create"),
    path("helpdesk/knowledge-base/<int:pk>/", views.knowledgearticle_detail, name="knowledgearticle_detail"),
    path("helpdesk/knowledge-base/<int:pk>/edit/", views.knowledgearticle_edit, name="knowledgearticle_edit"),
    path("helpdesk/knowledge-base/<int:pk>/delete/", views.knowledgearticle_delete, name="knowledgearticle_delete"),
    path("helpdesk/knowledge-base/<int:pk>/helpful/", views.knowledgearticle_helpful, name="knowledgearticle_helpful"),
]
