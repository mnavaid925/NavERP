from django.urls import path

from apps.bi.views.EmbeddedMobileBi import MobileBiConfigurations as views

urlpatterns = [
    path("mobile-configs/", views.mobile_bi_config_list, name="mobile_bi_config_list"),
    path("mobile-configs/create/", views.mobile_bi_config_create, name="mobile_bi_config_create"),
    path("mobile-configs/<int:pk>/", views.mobile_bi_config_detail, name="mobile_bi_config_detail"),
    path("mobile-configs/<int:pk>/edit/", views.mobile_bi_config_edit, name="mobile_bi_config_edit"),
    path("mobile-configs/<int:pk>/delete/", views.mobile_bi_config_delete, name="mobile_bi_config_delete"),
]
