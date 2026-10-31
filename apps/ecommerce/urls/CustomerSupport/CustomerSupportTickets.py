from django.urls import path

from apps.ecommerce.views.CustomerSupport import CustomerSupportTickets as views

urlpatterns = [
    path("customer-support/tickets/", views.customersupportticket_list, name="customersupportticket_list"),
    path("customer-support/tickets/create/", views.customersupportticket_create, name="customersupportticket_create"),
    path("customer-support/tickets/<int:pk>/", views.customersupportticket_detail, name="customersupportticket_detail"),
    path("customer-support/tickets/<int:pk>/edit/", views.customersupportticket_edit, name="customersupportticket_edit"),
    path("customer-support/tickets/<int:pk>/delete/", views.customersupportticket_delete, name="customersupportticket_delete"),
]
