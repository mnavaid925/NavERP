from django.urls import path
from apps.bi.views.MasterData import MdmGoldenRecords as views

urlpatterns = [
    path("mdm/golden-records/", views.mdm_golden_record_list, name="mdm_golden_record_list"),
    path("mdm/golden-records/create/", views.mdm_golden_record_create, name="mdm_golden_record_create"),
    path("mdm/golden-records/<int:pk>/", views.mdm_golden_record_detail, name="mdm_golden_record_detail"),
    path("mdm/golden-records/<int:pk>/edit/", views.mdm_golden_record_edit, name="mdm_golden_record_edit"),
    path("mdm/golden-records/<int:pk>/delete/", views.mdm_golden_record_delete, name="mdm_golden_record_delete"),
    path("mdm/golden-records/<int:pk>/merge/", views.mdm_golden_record_merge, name="mdm_golden_record_merge"),
    path("mdm/golden-records/<int:pk>/unmerge/", views.mdm_golden_record_unmerge, name="mdm_golden_record_unmerge"),
    path("mdm/golden-records/<int:pk>/approve/", views.mdm_golden_record_approve, name="mdm_golden_record_approve"),
]
