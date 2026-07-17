"""SCM 4.3 Inventory Management — Location URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("locations/", views.location_list, name="location_list"),
    path("locations/add/", views.location_create, name="location_create"),
    path("locations/<int:pk>/", views.location_detail, name="location_detail"),
    path("locations/<int:pk>/edit/", views.location_edit, name="location_edit"),
    path("locations/<int:pk>/delete/", views.location_delete, name="location_delete"),
]
