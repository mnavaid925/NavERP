from django.urls import path

from apps.ecommerce.views.ContentManagement import ContentBlocks as views

urlpatterns = [
    path("cms/blocks/", views.contentblock_list, name="contentblock_list"),
    path("cms/blocks/create/", views.contentblock_create, name="contentblock_create"),
    path("cms/blocks/<int:pk>/", views.contentblock_detail, name="contentblock_detail"),
    path("cms/blocks/<int:pk>/edit/", views.contentblock_edit, name="contentblock_edit"),
    path("cms/blocks/<int:pk>/delete/", views.contentblock_delete, name="contentblock_delete"),
]
