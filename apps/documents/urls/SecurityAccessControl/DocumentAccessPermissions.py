from django.urls import path

from apps.documents.views.SecurityAccessControl.DocumentAccessPermissions import (
    permission_create,
    permission_delete,
    permission_detail,
    permission_edit,
    permission_list,
    permission_simulate,
)

urlpatterns = [
    path("access-permissions/", permission_list, name="permission_list"),
    path("access-permissions/create/", permission_create, name="permission_create"),
    path("access-permissions/simulate/", permission_simulate, name="permission_simulate"),
    path("access-permissions/<int:pk>/", permission_detail, name="permission_detail"),
    path("access-permissions/<int:pk>/edit/", permission_edit, name="permission_edit"),
    path("access-permissions/<int:pk>/delete/", permission_delete, name="permission_delete"),
]
