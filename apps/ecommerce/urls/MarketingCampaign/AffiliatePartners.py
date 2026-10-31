from django.urls import path

from apps.ecommerce.views.MarketingCampaign import AffiliatePartners as views

urlpatterns = [
    path("marketing/affiliates/", views.affiliatepartner_list, name="affiliatepartner_list"),
    path("marketing/affiliates/create/", views.affiliatepartner_create, name="affiliatepartner_create"),
    path("marketing/affiliates/<int:pk>/", views.affiliatepartner_detail, name="affiliatepartner_detail"),
    path("marketing/affiliates/<int:pk>/edit/", views.affiliatepartner_edit, name="affiliatepartner_edit"),
    path("marketing/affiliates/<int:pk>/delete/", views.affiliatepartner_delete, name="affiliatepartner_delete"),
    path("marketing/affiliates/<int:pk>/approve/", views.affiliatepartner_approve, name="affiliatepartner_approve"),
]
