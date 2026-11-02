from django.urls import path
from apps.ecommerce.views.B2bWholesale import B2bCompanyUsers as views

urlpatterns = [
    path("b2b/users/", views.b2bcompanyuser_list, name="b2bcompanyuser_list"),
    path("b2b/users/new/", views.b2bcompanyuser_create, name="b2bcompanyuser_create"),
    path("b2b/users/<int:pk>/", views.b2bcompanyuser_detail, name="b2bcompanyuser_detail"),
    path("b2b/users/<int:pk>/edit/", views.b2bcompanyuser_edit, name="b2bcompanyuser_edit"),
    path("b2b/users/<int:pk>/delete/", views.b2bcompanyuser_delete, name="b2bcompanyuser_delete"),
]
