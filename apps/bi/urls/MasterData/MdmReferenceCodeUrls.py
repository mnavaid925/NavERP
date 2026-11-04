from django.urls import path
from apps.bi.views.MasterData import MdmReferenceCodes as views

urlpatterns = [
    path("mdm/reference-codes/", views.mdm_reference_code_list, name="mdm_reference_code_list"),
    path("mdm/reference-codes/create/", views.mdm_reference_code_create, name="mdm_reference_code_create"),
    path("mdm/reference-codes/<int:pk>/", views.mdm_reference_code_detail, name="mdm_reference_code_detail"),
    path("mdm/reference-codes/<int:pk>/edit/", views.mdm_reference_code_edit, name="mdm_reference_code_edit"),
    path("mdm/reference-codes/<int:pk>/delete/", views.mdm_reference_code_delete, name="mdm_reference_code_delete"),
]
