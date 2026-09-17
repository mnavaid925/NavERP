from django.urls import path
from apps.projects import views

urlpatterns = [
    path("overtime-rules/", views.otr_list, name="otr_list"),
    path("overtime-rules/new/", views.otr_create, name="otr_create"),
    path("overtime-rules/<int:pk>/", views.otr_detail, name="otr_detail"),
    path("overtime-rules/<int:pk>/edit/", views.otr_edit, name="otr_edit"),
    path("overtime-rules/<int:pk>/delete/", views.otr_delete, name="otr_delete"),
]
