from django.urls import path

from apps.ecommerce.views.Marketplace import VendorSubOrderViews as views

urlpatterns = [
    path("marketplace/sub-orders/", views.vendorsuborder_list, name="vendorsuborder_list"),
    path("marketplace/sub-orders/create/", views.vendorsuborder_create, name="vendorsuborder_create"),
    path("marketplace/sub-orders/<int:pk>/", views.vendorsuborder_detail, name="vendorsuborder_detail"),
    path("marketplace/sub-orders/<int:pk>/edit/", views.vendorsuborder_edit, name="vendorsuborder_edit"),
    path("marketplace/sub-orders/<int:pk>/delete/", views.vendorsuborder_delete, name="vendorsuborder_delete"),
    path("marketplace/sub-orders/<int:pk>/fulfill/", views.vendorsuborder_fulfill, name="vendorsuborder_fulfill"),
    path("marketplace/sub-orders/<int:pk>/dispute/", views.vendorsuborder_dispute, name="vendorsuborder_dispute"),
]
