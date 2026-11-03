from django.urls import path
from apps.ecommerce.views.MultiStore import StorefrontInstances as views

urlpatterns = [
    path("multi-store/storefronts/", views.storefront_instance_list, name="storefront_instance_list"),
    path("multi-store/storefronts/create/", views.storefront_instance_create, name="storefront_instance_create"),
    path("multi-store/storefronts/<int:pk>/", views.storefront_instance_detail, name="storefront_instance_detail"),
    path("multi-store/storefronts/<int:pk>/edit/", views.storefront_instance_edit, name="storefront_instance_edit"),
    path("multi-store/storefronts/<int:pk>/delete/", views.storefront_instance_delete, name="storefront_instance_delete"),
    path("multi-store/storefronts/<int:pk>/toggle-status/", views.storefront_toggle_status, name="storefront_toggle_status"),
]
