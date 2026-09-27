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
    # Usage metering (0.1 Subscription & Billing). Literal routes BEFORE the <int:pk> routes.
    path("usage/", views.usagerecord_list, name="usagerecord_list"),
    path("usage/add/", views.usagerecord_create, name="usagerecord_create"),
    path("usage/<int:pk>/", views.usagerecord_detail, name="usagerecord_detail"),
    path("usage/<int:pk>/edit/", views.usagerecord_edit, name="usagerecord_edit"),
    path("usage/<int:pk>/delete/", views.usagerecord_delete, name="usagerecord_delete"),
    path("usage/<int:pk>/mark-billed/", views.usagerecord_mark_billed, name="usagerecord_mark_billed"),
    # Onboarding
    path("onboarding/", views.onboarding, name="onboarding"),
    # Tenant isolation & security (0.1 bullet 3 — computed, no model)
    path("isolation/", views.isolation_overview, name="isolation_overview"),
    # ===================== 0.19 License & Subscription Administration =====================
    # The two computed boards come FIRST: `quota/` and `renewals/` are literal segments, and
    # Django is first-match-wins, so a literal route placed after a `<str:...>` sibling would be
    # swallowed by it.
    path("licensing/quota-board/", views.quota_board, name="quota_board"),
    path("licensing/renewal-board/", views.renewal_board, name="renewal_board"),
    # Entitlement feature catalog (bullet 2)
    path("licensing/features/", views.entitlementfeature_list, name="entitlementfeature_list"),
    path("licensing/features/add/", views.entitlementfeature_create, name="entitlementfeature_create"),
    path("licensing/features/<int:pk>/", views.entitlementfeature_detail, name="entitlementfeature_detail"),
    path("licensing/features/<int:pk>/edit/", views.entitlementfeature_edit, name="entitlementfeature_edit"),
    path("licensing/features/<int:pk>/delete/", views.entitlementfeature_delete, name="entitlementfeature_delete"),
    # Plan entitlements (bullet 2)
    path("licensing/entitlements/", views.planentitlement_list, name="planentitlement_list"),
    path("licensing/entitlements/add/", views.planentitlement_create, name="planentitlement_create"),
    path("licensing/entitlements/<int:pk>/", views.planentitlement_detail, name="planentitlement_detail"),
    path("licensing/entitlements/<int:pk>/edit/", views.planentitlement_edit, name="planentitlement_edit"),
    path("licensing/entitlements/<int:pk>/delete/", views.planentitlement_delete, name="planentitlement_delete"),
    # Usage quotas (bullet 3 — the CEILING; the consumption rows are 0.1's UsageRecord)
    path("licensing/quotas/", views.usagequota_list, name="usagequota_list"),
    path("licensing/quotas/add/", views.usagequota_create, name="usagequota_create"),
    path("licensing/quotas/<int:pk>/", views.usagequota_detail, name="usagequota_detail"),
    path("licensing/quotas/<int:pk>/edit/", views.usagequota_edit, name="usagequota_edit"),
    path("licensing/quotas/<int:pk>/delete/", views.usagequota_delete, name="usagequota_delete"),
    path("licensing/quotas/<int:pk>/mark-breached/", views.usagequota_mark_breached, name="usagequota_mark_breached"),
    # License assignments / seats (bullet 1)
    path("licensing/seats/", views.licenseassignment_list, name="licenseassignment_list"),
    path("licensing/seats/add/", views.licenseassignment_create, name="licenseassignment_create"),
    path("licensing/seats/<int:pk>/", views.licenseassignment_detail, name="licenseassignment_detail"),
    path("licensing/seats/<int:pk>/edit/", views.licenseassignment_edit, name="licenseassignment_edit"),
    path("licensing/seats/<int:pk>/delete/", views.licenseassignment_delete, name="licenseassignment_delete"),
    path("licensing/seats/<int:pk>/reclaim/", views.licenseassignment_reclaim, name="licenseassignment_reclaim"),
]
