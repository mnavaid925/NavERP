from django.urls import path

from apps.ecommerce.views.ContentManagement import CmsPages as views

urlpatterns = [
    path("cms/pages/", views.cmspage_list, name="cmspage_list"),
    path("cms/pages/create/", views.cmspage_create, name="cmspage_create"),
    path("cms/pages/<int:pk>/", views.cmspage_detail, name="cmspage_detail"),
    path("cms/pages/<int:pk>/edit/", views.cmspage_edit, name="cmspage_edit"),
    path("cms/pages/<int:pk>/delete/", views.cmspage_delete, name="cmspage_delete"),
    path("cms/pages/<int:pk>/preview/", views.cmspage_preview, name="cmspage_preview"),
]
