from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    # Subscriptions + billing
    path("subscriptions/", views.subscription_list, name="subscription_list"),
    path("subscriptions/add/", views.subscription_create, name="subscription_create"),
    path("subscriptions/<int:pk>/", views.subscription_detail, name="subscription_detail"),
    path("subscriptions/<int:pk>/edit/", views.subscription_edit, name="subscription_edit"),
    path("subscriptions/<int:pk>/delete/", views.subscription_delete, name="subscription_delete"),
    path("subscriptions/<int:pk>/checkout/", views.subscription_checkout, name="subscription_checkout"),
    path("subscriptions/<int:pk>/mark-paid/", views.subscription_mark_paid, name="subscription_mark_paid"),
    path("stripe/return/", views.stripe_return, name="stripe_return"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    # Subscription invoices
    path("subscription-invoices/", views.subscriptioninvoice_list, name="subscriptioninvoice_list"),
    path("subscription-invoices/add/", views.subscriptioninvoice_create, name="subscriptioninvoice_create"),
    path("subscription-invoices/<int:pk>/", views.subscriptioninvoice_detail, name="subscriptioninvoice_detail"),
    path("subscription-invoices/<int:pk>/edit/", views.subscriptioninvoice_edit, name="subscriptioninvoice_edit"),
    path("subscription-invoices/<int:pk>/delete/", views.subscriptioninvoice_delete, name="subscriptioninvoice_delete"),
    # Branding
    path("branding/", views.brandingsetting_list, name="brandingsetting_list"),
    path("branding/add/", views.brandingsetting_create, name="brandingsetting_create"),
    path("branding/<int:pk>/", views.brandingsetting_detail, name="brandingsetting_detail"),
    path("branding/<int:pk>/edit/", views.brandingsetting_edit, name="brandingsetting_edit"),
    path("branding/<int:pk>/delete/", views.brandingsetting_delete, name="brandingsetting_delete"),
    # Encryption keys
    path("encryption-keys/", views.encryptionkey_list, name="encryptionkey_list"),
    path("encryption-keys/add/", views.encryptionkey_create, name="encryptionkey_create"),
    path("encryption-keys/<int:pk>/", views.encryptionkey_detail, name="encryptionkey_detail"),
    path("encryption-keys/<int:pk>/edit/", views.encryptionkey_edit, name="encryptionkey_edit"),
    path("encryption-keys/<int:pk>/rotate/", views.encryptionkey_rotate, name="encryptionkey_rotate"),
    path("encryption-keys/<int:pk>/delete/", views.encryptionkey_delete, name="encryptionkey_delete"),
    # Health metrics
    path("health/", views.healthmetric_list, name="healthmetric_list"),
    path("health/add/", views.healthmetric_create, name="healthmetric_create"),
    path("health/<int:pk>/", views.healthmetric_detail, name="healthmetric_detail"),
    path("health/<int:pk>/edit/", views.healthmetric_edit, name="healthmetric_edit"),
    path("health/<int:pk>/delete/", views.healthmetric_delete, name="healthmetric_delete"),
    # Onboarding
    path("onboarding/", views.onboarding, name="onboarding"),
]
