from django.urls import path

from apps.ecommerce.views.MarketingCampaign import SeoMetadataRules as views

urlpatterns = [
    path("marketing/seo-rules/", views.seometadatarule_list, name="seometadatarule_list"),
    path("marketing/seo-rules/create/", views.seometadatarule_create, name="seometadatarule_create"),
    path("marketing/seo-rules/<int:pk>/", views.seometadatarule_detail, name="seometadatarule_detail"),
    path("marketing/seo-rules/<int:pk>/edit/", views.seometadatarule_edit, name="seometadatarule_edit"),
    path("marketing/seo-rules/<int:pk>/delete/", views.seometadatarule_delete, name="seometadatarule_delete"),
    path("marketing/seo-rules/<int:pk>/toggle/", views.seometadatarule_toggle, name="seometadatarule_toggle"),
]
