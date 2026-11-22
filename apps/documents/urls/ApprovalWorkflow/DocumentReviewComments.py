from django.urls import path

from apps.documents.views.ApprovalWorkflow import DocumentReviewComments as views

urlpatterns = [
    path("comments/", views.review_comment_list, name="review_comment_list"),
    path("comments/create/", views.review_comment_create, name="review_comment_create"),
    path("comments/<int:pk>/", views.review_comment_detail, name="review_comment_detail"),
    path("comments/<int:pk>/edit/", views.review_comment_edit, name="review_comment_edit"),
    path("comments/<int:pk>/delete/", views.review_comment_delete, name="review_comment_delete"),
    path("comments/<int:pk>/resolve/", views.review_comment_resolve, name="review_comment_resolve"),
    path("comments/<int:pk>/reply/", views.review_comment_reply, name="review_comment_reply"),
]
