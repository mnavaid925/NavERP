from django.urls import path
from apps.documents.views.MetadataIndexing import DocumentOcrJobs as views

urlpatterns = [
    path("ocr-jobs/", views.document_ocr_job_list, name="document_ocr_job_list"),
    path("ocr-jobs/create/", views.document_ocr_job_create, name="document_ocr_job_create"),
    path("ocr-jobs/<int:pk>/", views.document_ocr_job_detail, name="document_ocr_job_detail"),
    path("ocr-jobs/<int:pk>/viewer/", views.document_ocr_job_viewer, name="document_ocr_job_viewer"),
    path("ocr-jobs/<int:pk>/process/", views.document_ocr_job_process, name="document_ocr_job_process"),
    path("ocr-jobs/<int:pk>/apply/", views.document_ocr_job_apply, name="document_ocr_job_apply"),
    path("ocr-jobs/<int:pk>/delete/", views.document_ocr_job_delete, name="document_ocr_job_delete"),
]
