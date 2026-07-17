"""SCM 4.2 SRM — SupplierContract URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("contracts/", views.contract_list, name="contract_list"),
    path("contracts/add/", views.contract_create, name="contract_create"),
    path("contracts/<int:pk>/", views.contract_detail, name="contract_detail"),
    path("contracts/<int:pk>/edit/", views.contract_edit, name="contract_edit"),
    path("contracts/<int:pk>/delete/", views.contract_delete, name="contract_delete"),
    path("contracts/<int:pk>/activate/", views.contract_activate, name="contract_activate"),
    path("contracts/<int:pk>/renew/", views.contract_renew, name="contract_renew"),
    path("contracts/<int:pk>/terminate/", views.contract_terminate, name="contract_terminate"),
]
