from django.urls import path

from apps.ecommerce.views.CustomerSupport import CustomerSatisfactionSurveys as views

urlpatterns = [
    path("customer-support/surveys/", views.customersatisfactionsurvey_list, name="customersatisfactionsurvey_list"),
    path("customer-support/surveys/create/", views.customersatisfactionsurvey_create, name="customersatisfactionsurvey_create"),
    path("customer-support/surveys/<int:pk>/", views.customersatisfactionsurvey_detail, name="customersatisfactionsurvey_detail"),
    path("customer-support/surveys/<int:pk>/edit/", views.customersatisfactionsurvey_edit, name="customersatisfactionsurvey_edit"),
    path("customer-support/surveys/<int:pk>/delete/", views.customersatisfactionsurvey_delete, name="customersatisfactionsurvey_delete"),
]
