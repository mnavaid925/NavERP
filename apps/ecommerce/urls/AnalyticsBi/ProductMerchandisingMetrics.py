from django.urls import path

from apps.ecommerce.views.AnalyticsBi import ProductMerchandisingMetrics as views

urlpatterns = [
    path("analytics/merchandising/", views.productmerchandisingmetric_list, name="productmerchandisingmetric_list"),
    path("analytics/merchandising/create/", views.productmerchandisingmetric_create, name="productmerchandisingmetric_create"),
    path("analytics/merchandising/reclassify/", views.productmerchandisingmetric_reclassify, name="productmerchandisingmetric_reclassify"),
    path("analytics/merchandising/<int:pk>/", views.productmerchandisingmetric_detail, name="productmerchandisingmetric_detail"),
    path("analytics/merchandising/<int:pk>/edit/", views.productmerchandisingmetric_edit, name="productmerchandisingmetric_edit"),
    path("analytics/merchandising/<int:pk>/delete/", views.productmerchandisingmetric_delete, name="productmerchandisingmetric_delete"),
]
