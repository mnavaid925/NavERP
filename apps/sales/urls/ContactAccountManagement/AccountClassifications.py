from django.urls import path

from apps.sales import views

urlpatterns = [
    path("account-classifications/", views.account_classification_list, name="account_classification_list"),
    path("account-classifications/add/", views.account_classification_create, name="account_classification_create"),
    path("account-classifications/export/", views.account_classification_export, name="account_classification_export"),
    path("account-classifications/<int:pk>/", views.account_classification_detail, name="account_classification_detail"),
    path("account-classifications/<int:pk>/edit/", views.account_classification_edit, name="account_classification_edit"),
    path("account-classifications/<int:pk>/delete/", views.account_classification_delete, name="account_classification_delete"),
]
