"""SCM 4.2 SRM — SupplierProfile URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("suppliers/", views.supplierprofile_list, name="supplierprofile_list"),
    path("suppliers/add/", views.supplierprofile_create, name="supplierprofile_create"),
    path("suppliers/<int:pk>/", views.supplierprofile_detail, name="supplierprofile_detail"),
    path("suppliers/<int:pk>/edit/", views.supplierprofile_edit, name="supplierprofile_edit"),
    path("suppliers/<int:pk>/delete/", views.supplierprofile_delete, name="supplierprofile_delete"),
    path("suppliers/<int:pk>/submit/", views.supplierprofile_submit, name="supplierprofile_submit"),
    path("suppliers/<int:pk>/approve/", views.supplierprofile_approve, name="supplierprofile_approve"),
    path("suppliers/<int:pk>/reject/", views.supplierprofile_reject, name="supplierprofile_reject"),
    path("suppliers/<int:pk>/reopen/", views.supplierprofile_reopen, name="supplierprofile_reopen"),
    path("suppliers/<int:pk>/suspend/", views.supplierprofile_suspend, name="supplierprofile_suspend"),
]
