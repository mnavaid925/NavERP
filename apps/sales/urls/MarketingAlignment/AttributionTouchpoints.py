"""Sales 8.13 — URLs for `AttributionTouchpoint`."""
from django.urls import path

from apps.sales.views.MarketingAlignment import AttributionTouchpoints as views

urlpatterns = [
    path("marketing-alignment/touchpoints/", views.attribution_touchpoint_list, name="attribution_touchpoint_list"),
    path("marketing-alignment/touchpoints/create/", views.attribution_touchpoint_create, name="attribution_touchpoint_create"),
    path("marketing-alignment/touchpoints/<int:pk>/", views.attribution_touchpoint_detail, name="attribution_touchpoint_detail"),
    path("marketing-alignment/touchpoints/<int:pk>/edit/", views.attribution_touchpoint_edit, name="attribution_touchpoint_edit"),
    path("marketing-alignment/touchpoints/<int:pk>/delete/", views.attribution_touchpoint_delete, name="attribution_touchpoint_delete"),
]
