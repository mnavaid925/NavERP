from django.urls import path

from apps.sales import views

urlpatterns = [
    path("account-stakeholders/", views.account_stakeholder_list, name="account_stakeholder_list"),
    path("account-stakeholders/add/", views.account_stakeholder_create, name="account_stakeholder_create"),
    path("account-stakeholders/export/", views.account_stakeholder_export, name="account_stakeholder_export"),
    path("account-stakeholders/<int:pk>/", views.account_stakeholder_detail, name="account_stakeholder_detail"),
    path("account-stakeholders/<int:pk>/edit/", views.account_stakeholder_edit, name="account_stakeholder_edit"),
    path("account-stakeholders/<int:pk>/delete/", views.account_stakeholder_delete, name="account_stakeholder_delete"),
]
