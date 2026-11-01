from django.urls import path

from apps.ecommerce.views.ContentManagement import MediaAssets as views

urlpatterns = [
    path("cms/media/", views.mediaasset_list, name="mediaasset_list"),
    path("cms/media/create/", views.mediaasset_create, name="mediaasset_create"),
    path("cms/media/<int:pk>/", views.mediaasset_detail, name="mediaasset_detail"),
    path("cms/media/<int:pk>/edit/", views.mediaasset_edit, name="mediaasset_edit"),
    path("cms/media/<int:pk>/delete/", views.mediaasset_delete, name="mediaasset_delete"),
]
