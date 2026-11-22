from django.urls import path

from apps.documents.views.DocumentAuthoring import DocumentTemplates as views

urlpatterns = [
    path("templates/", views.template_list, name="template_list"),
    path("templates/create/", views.template_create, name="template_create"),
    path("templates/<int:pk>/", views.template_detail, name="template_detail"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("templates/<int:pk>/delete/", views.template_delete, name="template_delete"),
    path("templates/<int:pk>/instantiate/", views.template_instantiate, name="template_instantiate"),
]
