from django.urls import path

from apps.ecommerce.views.Marketplace import VendorPayoutViews as views

urlpatterns = [
    path("marketplace/payouts/", views.vendorpayout_list, name="vendorpayout_list"),
    path("marketplace/payouts/create/", views.vendorpayout_create, name="vendorpayout_create"),
    path("marketplace/payouts/<int:pk>/", views.vendorpayout_detail, name="vendorpayout_detail"),
    path("marketplace/payouts/<int:pk>/edit/", views.vendorpayout_edit, name="vendorpayout_edit"),
    path("marketplace/payouts/<int:pk>/delete/", views.vendorpayout_delete, name="vendorpayout_delete"),
    path("marketplace/payouts/<int:pk>/approve/", views.vendorpayout_approve, name="vendorpayout_approve"),
    path("marketplace/payouts/<int:pk>/execute/", views.vendorpayout_execute, name="vendorpayout_execute"),
]
