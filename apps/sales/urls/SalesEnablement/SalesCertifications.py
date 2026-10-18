"""Sales 8.9 — URLs for `SalesCertification`."""
from django.urls import path

from apps.sales.views.SalesEnablement.SalesCertifications import (
    sales_certification_create,
    sales_certification_delete,
    sales_certification_detail,
    sales_certification_edit,
    sales_certification_list,
)

urlpatterns = [
    path("enablement/certifications/", sales_certification_list, name="sales_certification_list"),
    path("enablement/certifications/new/", sales_certification_create, name="sales_certification_create"),
    path("enablement/certifications/<int:pk>/", sales_certification_detail, name="sales_certification_detail"),
    path("enablement/certifications/<int:pk>/edit/", sales_certification_edit, name="sales_certification_edit"),
    path("enablement/certifications/<int:pk>/delete/", sales_certification_delete, name="sales_certification_delete"),
]
