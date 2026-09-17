from django.urls import path
from apps.projects import views

urlpatterns = [
    path("overtime-records/", views.pot_list, name="pot_list"),
    path("overtime-records/new/", views.pot_create, name="pot_create"),
    path("overtime-records/<int:pk>/", views.pot_detail, name="pot_detail"),
    path("overtime-records/<int:pk>/edit/", views.pot_edit, name="pot_edit"),
    path("overtime-records/<int:pk>/delete/", views.pot_delete, name="pot_delete"),
    path("overtime-records/<int:pk>/submit/", views.pot_submit, name="pot_submit"),
    path("overtime-records/<int:pk>/approve/", views.pot_approve, name="pot_approve"),
    path("overtime-records/<int:pk>/reject/", views.pot_reject, name="pot_reject"),
]
