from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — first-match-wins.
    path("suspensions/", views.vsu_list, name="vsu_list"),
    path("suspensions/add/", views.vsu_create, name="vsu_create"),
    path("suspensions/<int:pk>/", views.vsu_detail, name="vsu_detail"),
    path("suspensions/<int:pk>/edit/", views.vsu_edit, name="vsu_edit"),
    path("suspensions/<int:pk>/approve/", views.vsu_approve, name="vsu_approve"),
    path("suspensions/<int:pk>/reject/", views.vsu_reject, name="vsu_reject"),
    path("suspensions/<int:pk>/lift/", views.vsu_lift, name="vsu_lift"),
    path("suspensions/<int:pk>/delete/", views.vsu_delete, name="vsu_delete"),
]
