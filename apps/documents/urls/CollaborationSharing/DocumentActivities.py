from django.urls import path

from apps.documents.views.CollaborationSharing import DocumentActivities as views

urlpatterns = [
    path("activities/", views.document_activity_list, name="document_activity_list"),
    path("activities/<int:pk>/", views.document_activity_detail, name="document_activity_detail"),
    path("activities/<int:pk>/mark-read/", views.document_activity_mark_read, name="document_activity_mark_read"),
    path("activities/mark-all-read/", views.document_activity_mark_all_read, name="document_activity_mark_all_read"),
]
