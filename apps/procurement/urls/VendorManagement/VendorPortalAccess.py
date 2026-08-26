from django.urls import path

from apps.procurement import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — first-match-wins.
    path("portal-access/", views.vpa_list, name="vpa_list"),
    path("portal-access/add/", views.vpa_create, name="vpa_create"),
    path("portal-access/<int:pk>/", views.vpa_detail, name="vpa_detail"),
    path("portal-access/<int:pk>/edit/", views.vpa_edit, name="vpa_edit"),
    path("portal-access/<int:pk>/delete/", views.vpa_delete, name="vpa_delete"),
]
