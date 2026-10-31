from django.urls import path

from apps.ecommerce.views.ReviewUgc import VisualUgcMedia as views

urlpatterns = [
    path("ugc/", views.visualugcmedia_list, name="visualugcmedia_list"),
    path("ugc/create/", views.visualugcmedia_create, name="visualugcmedia_create"),
    path("ugc/<int:pk>/", views.visualugcmedia_detail, name="visualugcmedia_detail"),
    path("ugc/<int:pk>/edit/", views.visualugcmedia_edit, name="visualugcmedia_edit"),
    path("ugc/<int:pk>/delete/", views.visualugcmedia_delete, name="visualugcmedia_delete"),
]
