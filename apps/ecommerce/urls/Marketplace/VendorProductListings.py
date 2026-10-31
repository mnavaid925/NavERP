from django.urls import path

from apps.ecommerce.views.Marketplace import VendorProductListingViews as views

urlpatterns = [
    path("marketplace/listings/", views.vendorproductlisting_list, name="vendorproductlisting_list"),
    path("marketplace/listings/create/", views.vendorproductlisting_create, name="vendorproductlisting_create"),
    path("marketplace/listings/<int:pk>/", views.vendorproductlisting_detail, name="vendorproductlisting_detail"),
    path("marketplace/listings/<int:pk>/edit/", views.vendorproductlisting_edit, name="vendorproductlisting_edit"),
    path("marketplace/listings/<int:pk>/delete/", views.vendorproductlisting_delete, name="vendorproductlisting_delete"),
    path("marketplace/listings/<int:pk>/moderate/", views.vendorproductlisting_moderate, name="vendorproductlisting_moderate"),
]
