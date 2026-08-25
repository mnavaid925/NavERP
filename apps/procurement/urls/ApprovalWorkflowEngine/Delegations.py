from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — first-match-wins.
    path("delegations/", views.delegation_list, name="delegation_list"),
    path("delegations/add/", views.delegation_create, name="delegation_create"),
    path("delegations/<int:pk>/", views.delegation_detail, name="delegation_detail"),
    path("delegations/<int:pk>/edit/", views.delegation_edit, name="delegation_edit"),
    path("delegations/<int:pk>/delete/", views.delegation_delete, name="delegation_delete"),
]
