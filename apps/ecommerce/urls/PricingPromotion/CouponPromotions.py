from django.urls import path

from apps.ecommerce.views.PricingPromotion import CouponPromotions as views

urlpatterns = [
    path("pricing/coupons/", views.couponpromotion_list, name="couponpromotion_list"),
    path("pricing/coupons/create/", views.couponpromotion_create, name="couponpromotion_create"),
    path("pricing/coupons/<int:pk>/", views.couponpromotion_detail, name="couponpromotion_detail"),
    path("pricing/coupons/<int:pk>/edit/", views.couponpromotion_edit, name="couponpromotion_edit"),
    path("pricing/coupons/<int:pk>/delete/", views.couponpromotion_delete, name="couponpromotion_delete"),
]
