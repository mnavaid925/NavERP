from django.urls import path

from apps.quality.views.SupplierQuality import SupplierQualityDirectory as views

urlpatterns = [
    path("avl/", views.avl_directory, name="avl_directory"),
]
