from django.urls import path
from apps.ecommerce.views.MobileCommerce import MobileHub as views

urlpatterns = [
    path("mobile/hub/", views.mobile_hub, name="mobile_hub"),
]
