"""Sales 8.16 — FieldSalesRoute URL patterns."""
from django.urls import path

from apps.sales.views.MobileSales import FieldSalesRoutes as views

urlpatterns = [
    path("routes/", views.field_sales_route_list, name="field_sales_route_list"),
    path("routes/create/", views.field_sales_route_create, name="field_sales_route_create"),
    path("routes/<int:pk>/", views.field_sales_route_detail, name="field_sales_route_detail"),
    path("routes/<int:pk>/edit/", views.field_sales_route_edit, name="field_sales_route_edit"),
    path("routes/<int:pk>/delete/", views.field_sales_route_delete, name="field_sales_route_delete"),
    path("routes/<int:pk>/optimize/", views.field_sales_route_optimize, name="field_sales_route_optimize"),
]
