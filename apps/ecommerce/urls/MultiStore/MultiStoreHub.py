from django.urls import path
from apps.ecommerce.views.MultiStore import MultiStoreHub as views

urlpatterns = [
    path("multi-store/", views.multi_store_hub, name="multi_store_hub"),
]
