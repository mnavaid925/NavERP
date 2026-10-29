from django.urls import path

from apps.ecommerce.views.CustomerProfile import CustomerPrivacyRequests as views

urlpatterns = [
    path(
        "privacy-requests/",
        views.customerprivacyrequest_list,
        name="customerprivacyrequest_list",
    ),
    path(
        "privacy-requests/create/",
        views.customerprivacyrequest_create,
        name="customerprivacyrequest_create",
    ),
    path(
        "privacy-requests/<int:pk>/",
        views.customerprivacyrequest_detail,
        name="customerprivacyrequest_detail",
    ),
    path(
        "privacy-requests/<int:pk>/edit/",
        views.customerprivacyrequest_edit,
        name="customerprivacyrequest_edit",
    ),
    path(
        "privacy-requests/<int:pk>/delete/",
        views.customerprivacyrequest_delete,
        name="customerprivacyrequest_delete",
    ),
    path(
        "privacy-requests/<int:pk>/generate-export/",
        views.customerprivacyrequest_generate_export,
        name="customerprivacyrequest_generate_export",
    ),
    path(
        "privacy-requests/<int:pk>/anonymize/",
        views.customerprivacyrequest_anonymize,
        name="customerprivacyrequest_anonymize",
    ),
]
