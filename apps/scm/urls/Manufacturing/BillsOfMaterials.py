"""SCM 4.8 Manufacturing — BillOfMaterials routes (prefix ``boms/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("boms/", views.billofmaterials_list, name="billofmaterials_list"),
    path("boms/add/", views.billofmaterials_create, name="billofmaterials_create"),
    path("boms/<int:pk>/", views.billofmaterials_detail, name="billofmaterials_detail"),
    path("boms/<int:pk>/edit/", views.billofmaterials_edit, name="billofmaterials_edit"),
    path("boms/<int:pk>/delete/", views.billofmaterials_delete, name="billofmaterials_delete"),
]
