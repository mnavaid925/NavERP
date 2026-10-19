"""Sales 8.13 — URLs for the Marketing Alignment & Attribution console."""
from django.urls import path

from apps.sales.views.MarketingAlignment import AttributionConsole as views

urlpatterns = [
    path("marketing-alignment/console/", views.marketing_attribution_console, name="marketing_attribution_console"),
]
