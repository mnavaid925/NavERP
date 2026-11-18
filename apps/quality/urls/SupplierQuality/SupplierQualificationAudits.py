from django.urls import path

from apps.quality.views.SupplierQuality import SupplierQualificationAudits as views

urlpatterns = [
    path("audits/", views.supplier_qualification_audit_list, name="supplier_qualification_audit_list"),
    path("audits/create/", views.supplier_qualification_audit_create, name="supplier_qualification_audit_create"),
    path("audits/export/", views.supplier_qualification_audit_export, name="supplier_qualification_audit_export"),
    path("audits/<int:pk>/", views.supplier_qualification_audit_detail, name="supplier_qualification_audit_detail"),
    path("audits/<int:pk>/edit/", views.supplier_qualification_audit_edit, name="supplier_qualification_audit_edit"),
    path("audits/<int:pk>/delete/", views.supplier_qualification_audit_delete, name="supplier_qualification_audit_delete"),
    path("audits/<int:pk>/status/", views.supplier_qualification_audit_status, name="supplier_qualification_audit_status"),
]
