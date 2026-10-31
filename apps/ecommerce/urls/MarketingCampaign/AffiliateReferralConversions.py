from django.urls import path

from apps.ecommerce.views.MarketingCampaign import AffiliateReferralConversions as views

urlpatterns = [
    path("marketing/conversions/", views.affiliatereferralconversion_list, name="affiliatereferralconversion_list"),
    path("marketing/conversions/create/", views.affiliatereferralconversion_create, name="affiliatereferralconversion_create"),
    path("marketing/conversions/<int:pk>/", views.affiliatereferralconversion_detail, name="affiliatereferralconversion_detail"),
    path("marketing/conversions/<int:pk>/edit/", views.affiliatereferralconversion_edit, name="affiliatereferralconversion_edit"),
    path("marketing/conversions/<int:pk>/delete/", views.affiliatereferralconversion_delete, name="affiliatereferralconversion_delete"),
    path("marketing/conversions/<int:pk>/approve/", views.affiliatereferralconversion_approve, name="affiliatereferralconversion_approve"),
    path("marketing/conversions/<int:pk>/void/", views.affiliatereferralconversion_void, name="affiliatereferralconversion_void"),
]
