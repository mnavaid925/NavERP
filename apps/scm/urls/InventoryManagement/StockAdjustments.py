"""SCM 4.3 Inventory Management — StockAdjustment URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("adjustments/", views.stockadjustment_list, name="stockadjustment_list"),
    path("adjustments/add/", views.stockadjustment_create, name="stockadjustment_create"),
    path("adjustments/<int:pk>/", views.stockadjustment_detail, name="stockadjustment_detail"),
    path("adjustments/<int:pk>/edit/", views.stockadjustment_edit, name="stockadjustment_edit"),
    path("adjustments/<int:pk>/delete/", views.stockadjustment_delete, name="stockadjustment_delete"),
    path("adjustments/<int:pk>/post/", views.stockadjustment_post, name="stockadjustment_post"),
    path("adjustments/<int:pk>/cancel/", views.stockadjustment_cancel, name="stockadjustment_cancel"),
]
