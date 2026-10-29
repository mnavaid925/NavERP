from django.urls import path

from apps.ecommerce.views.PricingPromotion import FlashSales as views

urlpatterns = [
    path("pricing/flash-sales/", views.flashsale_list, name="flashsale_list"),
    path("pricing/flash-sales/create/", views.flashsale_create, name="flashsale_create"),
    path("pricing/flash-sales/<int:pk>/", views.flashsale_detail, name="flashsale_detail"),
    path("pricing/flash-sales/<int:pk>/edit/", views.flashsale_edit, name="flashsale_edit"),
    path("pricing/flash-sales/<int:pk>/delete/", views.flashsale_delete, name="flashsale_delete"),
]
