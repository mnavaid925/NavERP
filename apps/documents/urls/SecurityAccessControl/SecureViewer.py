from django.urls import path

from apps.documents.views.SecurityAccessControl.SecureViewer import secure_viewer

urlpatterns = [
    path("secure-viewer/", secure_viewer, name="secure_viewer"),
    path("secure-viewer/<int:pk>/", secure_viewer, name="secure_viewer_doc"),
]
