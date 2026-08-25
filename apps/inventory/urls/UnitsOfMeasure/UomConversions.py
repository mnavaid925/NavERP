from django.urls import path

from apps.inventory import views

urlpatterns = [
    # Literal routes BEFORE the <int:pk> ones — first-match-wins.
    path("conversions/", views.uomconversion_list, name="uomconversion_list"),
    path("conversions/add/", views.uomconversion_create, name="uomconversion_create"),
    path("conversions/<int:pk>/", views.uomconversion_detail, name="uomconversion_detail"),
    path("conversions/<int:pk>/edit/", views.uomconversion_edit, name="uomconversion_edit"),
    path("conversions/<int:pk>/delete/", views.uomconversion_delete, name="uomconversion_delete"),
]
