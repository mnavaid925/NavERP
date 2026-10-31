from django.urls import path

from apps.ecommerce.views.Marketplace import MarketplaceConsoleViews as views

urlpatterns = [
    path("marketplace/console/", views.marketplace_console, name="marketplace_console"),
]
