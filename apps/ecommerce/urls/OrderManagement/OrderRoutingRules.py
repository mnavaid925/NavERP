from django.urls import path

from apps.ecommerce.views.OrderManagement import OrderRoutingRules as views

urlpatterns = [
    path("routing-rules/", views.orderroutingrule_list, name="orderroutingrule_list"),
    path("routing-rules/create/", views.orderroutingrule_create, name="orderroutingrule_create"),
    path("routing-rules/<int:pk>/", views.orderroutingrule_detail, name="orderroutingrule_detail"),
    path("routing-rules/<int:pk>/edit/", views.orderroutingrule_edit, name="orderroutingrule_edit"),
    path("routing-rules/<int:pk>/delete/", views.orderroutingrule_delete, name="orderroutingrule_delete"),
]
