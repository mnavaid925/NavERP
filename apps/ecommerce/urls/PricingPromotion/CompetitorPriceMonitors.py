from django.urls import path

from apps.ecommerce.views.PricingPromotion import CompetitorPriceMonitors as views

urlpatterns = [
    path("pricing/competitors/", views.competitorpricemonitor_list, name="competitorpricemonitor_list"),
    path("pricing/competitors/create/", views.competitorpricemonitor_create, name="competitorpricemonitor_create"),
    path("pricing/competitors/<int:pk>/", views.competitorpricemonitor_detail, name="competitorpricemonitor_detail"),
    path("pricing/competitors/<int:pk>/edit/", views.competitorpricemonitor_edit, name="competitorpricemonitor_edit"),
    path("pricing/competitors/<int:pk>/delete/", views.competitorpricemonitor_delete, name="competitorpricemonitor_delete"),
    path("pricing/competitors/<int:pk>/sync/", views.competitorpricemonitor_sync, name="competitorpricemonitor_sync"),
]
