from django.urls import path
from apps.projects import views

urlpatterns = [
    path("activity-codes/", views.tac_list, name="tac_list"),
    path("activity-codes/new/", views.tac_create, name="tac_create"),
    path("activity-codes/<int:pk>/", views.tac_detail, name="tac_detail"),
    path("activity-codes/<int:pk>/edit/", views.tac_edit, name="tac_edit"),
    path("activity-codes/<int:pk>/delete/", views.tac_delete, name="tac_delete"),
]
