from django.urls import path

from apps.documents.views.CollaborationSharing import PublicShare as views

urlpatterns = [
    path("shares/public/<str:share_token>/", views.public_share_preview, name="public_share_preview"),
    path("shares/public/<str:share_token>/download/", views.public_share_download, name="public_share_download"),
]
