from django.urls import path

from apps.ecommerce.views.ContentManagement import BlogArticles as views

urlpatterns = [
    path("cms/blog/", views.blogarticle_list, name="blogarticle_list"),
    path("cms/blog/create/", views.blogarticle_create, name="blogarticle_create"),
    path("cms/blog/<int:pk>/", views.blogarticle_detail, name="blogarticle_detail"),
    path("cms/blog/<int:pk>/edit/", views.blogarticle_edit, name="blogarticle_edit"),
    path("cms/blog/<int:pk>/delete/", views.blogarticle_delete, name="blogarticle_delete"),
]
