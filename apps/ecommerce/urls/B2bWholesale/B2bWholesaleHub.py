from django.urls import path
from apps.ecommerce.views.B2bWholesale import B2bWholesaleHub as views

urlpatterns = [
    path("b2b/hub/", views.b2b_wholesale_hub, name="b2b_wholesale_hub"),
]
