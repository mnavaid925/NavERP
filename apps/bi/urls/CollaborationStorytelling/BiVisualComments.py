from django.urls import path

from apps.bi.views.CollaborationStorytelling import BiVisualComments as views

urlpatterns = [
    path("comments/", views.bi_visual_comment_list, name="bi_visual_comment_list"),
    path("comments/create/", views.bi_visual_comment_create, name="bi_visual_comment_create"),
    path("comments/<int:pk>/", views.bi_visual_comment_detail, name="bi_visual_comment_detail"),
    path("comments/<int:pk>/edit/", views.bi_visual_comment_edit, name="bi_visual_comment_edit"),
    path("comments/<int:pk>/delete/", views.bi_visual_comment_delete, name="bi_visual_comment_delete"),
    path("comments/<int:pk>/resolve/", views.bi_visual_comment_resolve, name="bi_visual_comment_resolve"),
]
