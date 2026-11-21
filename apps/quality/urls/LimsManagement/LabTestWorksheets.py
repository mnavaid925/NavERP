from django.urls import path

from apps.quality.views.LimsManagement import LabTestWorksheets as views

urlpatterns = [
    path("lims/worksheets/", views.lab_test_worksheet_list, name="lab_test_worksheet_list"),
    path("lims/worksheets/create/", views.lab_test_worksheet_create, name="lab_test_worksheet_create"),
    path("lims/worksheets/<int:pk>/", views.lab_test_worksheet_detail, name="lab_test_worksheet_detail"),
    path("lims/worksheets/<int:pk>/edit/", views.lab_test_worksheet_edit, name="lab_test_worksheet_edit"),
    path("lims/worksheets/<int:pk>/delete/", views.lab_test_worksheet_delete, name="lab_test_worksheet_delete"),
    path("lims/worksheets/<int:pk>/complete/", views.lab_test_worksheet_complete, name="lab_test_worksheet_complete"),
]
