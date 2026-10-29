from django.urls import path

from apps.ecommerce.views.PricingPromotion import DynamicPriceRules as views

urlpatterns = [
    path("pricing/rules/", views.dynamicpricerule_list, name="dynamicpricerule_list"),
    path("pricing/rules/create/", views.dynamicpricerule_create, name="dynamicpricerule_create"),
    path("pricing/rules/<int:pk>/", views.dynamicpricerule_detail, name="dynamicpricerule_detail"),
    path("pricing/rules/<int:pk>/edit/", views.dynamicpricerule_edit, name="dynamicpricerule_edit"),
    path("pricing/rules/<int:pk>/delete/", views.dynamicpricerule_delete, name="dynamicpricerule_delete"),
]
