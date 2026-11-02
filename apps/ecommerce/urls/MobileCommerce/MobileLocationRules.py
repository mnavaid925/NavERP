from django.urls import path
from apps.ecommerce.views.MobileCommerce import MobileLocationRules as views

urlpatterns = [
    path("mobile/location-rules/", views.mobilelocationrule_list, name="mobilelocationrule_list"),
    path("mobile/location-rules/new/", views.mobilelocationrule_create, name="mobilelocationrule_create"),
    path("mobile/location-rules/<int:pk>/", views.mobilelocationrule_detail, name="mobilelocationrule_detail"),
    path("mobile/location-rules/<int:pk>/edit/", views.mobilelocationrule_edit, name="mobilelocationrule_edit"),
    path("mobile/location-rules/<int:pk>/delete/", views.mobilelocationrule_delete, name="mobilelocationrule_delete"),
    path("mobile/location-rules/<int:pk>/simulate/", views.mobilelocationrule_simulate, name="mobilelocationrule_simulate"),
]
