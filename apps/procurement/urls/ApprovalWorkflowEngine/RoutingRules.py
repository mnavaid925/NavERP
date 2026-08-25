from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — first-match-wins.
    path("approvals/rules/", views.routingrule_list, name="routingrule_list"),
    path("approvals/rules/add/", views.routingrule_create, name="routingrule_create"),
    path("approvals/rules/<int:pk>/", views.routingrule_detail, name="routingrule_detail"),
    path("approvals/rules/<int:pk>/edit/", views.routingrule_edit, name="routingrule_edit"),
    path("approvals/rules/<int:pk>/delete/", views.routingrule_delete, name="routingrule_delete"),
]
