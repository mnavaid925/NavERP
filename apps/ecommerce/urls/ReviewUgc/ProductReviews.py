from django.urls import path

from apps.ecommerce.views.ReviewUgc import ProductReviews as views

urlpatterns = [
    path("reviews/", views.productreview_list, name="productreview_list"),
    path("reviews/create/", views.productreview_create, name="productreview_create"),
    path("reviews/<int:pk>/", views.productreview_detail, name="productreview_detail"),
    path("reviews/<int:pk>/edit/", views.productreview_edit, name="productreview_edit"),
    path("reviews/<int:pk>/delete/", views.productreview_delete, name="productreview_delete"),
    path("reviews/<int:pk>/moderate/", views.productreview_moderate, name="productreview_moderate"),
]
