from django.urls import path

from apps.ecommerce.views.CustomerSupport import OrderIssueClaims as views

urlpatterns = [
    path("customer-support/claims/", views.orderissueclaim_list, name="orderissueclaim_list"),
    path("customer-support/claims/create/", views.orderissueclaim_create, name="orderissueclaim_create"),
    path("customer-support/claims/<int:pk>/", views.orderissueclaim_detail, name="orderissueclaim_detail"),
    path("customer-support/claims/<int:pk>/edit/", views.orderissueclaim_edit, name="orderissueclaim_edit"),
    path("customer-support/claims/<int:pk>/delete/", views.orderissueclaim_delete, name="orderissueclaim_delete"),
]
