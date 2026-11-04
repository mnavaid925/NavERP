from django.urls import path

from apps.bi.views.SemanticLayer import SemanticOverviewViews as views

urlpatterns = [
    path("semantic/", views.semantic_overview, name="semantic_overview"),
]
