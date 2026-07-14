"""CRM 1.4 Customer Service & Support — PublicPages URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    path("cases/track/<str:token>/", views.case_public, name="case_public"),  # public status page
    path("kb/<str:token>/", views.kb_public, name="kb_public"),                # public article page
    path("kb/<str:token>/helpful/", views.kb_helpful, name="kb_helpful"),      # public vote
]
