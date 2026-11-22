from django.urls import path

from apps.documents.views.DocumentAuthoring import TemplateSections as views

urlpatterns = [
    path("sections/", views.template_section_list, name="template_section_list"),
    path("sections/create/", views.template_section_create, name="template_section_create"),
    path("sections/<int:pk>/", views.template_section_detail, name="template_section_detail"),
    path("sections/<int:pk>/edit/", views.template_section_edit, name="template_section_edit"),
    path("sections/<int:pk>/delete/", views.template_section_delete, name="template_section_delete"),
]
