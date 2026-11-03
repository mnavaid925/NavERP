from django.urls import path
from apps.ecommerce.views.MultiStore import PlatformEnvironments as views

urlpatterns = [
    path("multi-store/environments/", views.platform_environment_list, name="platform_environment_list"),
    path("multi-store/environments/create/", views.platform_environment_create, name="platform_environment_create"),
    path("multi-store/environments/<int:pk>/", views.platform_environment_detail, name="platform_environment_detail"),
    path("multi-store/environments/<int:pk>/edit/", views.platform_environment_edit, name="platform_environment_edit"),
    path("multi-store/environments/<int:pk>/delete/", views.platform_environment_delete, name="platform_environment_delete"),
]
