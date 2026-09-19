from django.contrib import admin

from .models import (
    BrandingSetting,
    EncryptionKey,
    HealthMetric,
    Subscription,
    SubscriptionInvoice,
    UsageRecord,
)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["tenant", "plan", "status", "billing_cycle", "amount", "seats", "renews_on"]
    list_filter = ["plan", "status", "billing_cycle", "tenant"]
    readonly_fields = ["stripe_customer_id", "stripe_subscription_id", "created_at"]


@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "tenant", "subscription", "status", "amount", "issued_on", "paid_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["number"]
    readonly_fields = ["number", "stripe_invoice_id", "created_at"]


@admin.register(BrandingSetting)
class BrandingSettingAdmin(admin.ModelAdmin):
    list_display = ["tenant", "primary_color", "accent_color", "updated_at"]


@admin.register(EncryptionKey)
class EncryptionKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "tenant", "prefix", "status", "last_rotated_at", "created_at"]
    list_filter = ["status", "tenant"]
    search_fields = ["name", "prefix"]
    readonly_fields = ["prefix", "key_hash", "last_rotated_at", "created_at"]


@admin.register(HealthMetric)
class HealthMetricAdmin(admin.ModelAdmin):
    list_display = ["metric", "value", "status", "tenant", "created_at"]
    list_filter = ["metric", "status", "tenant"]


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ["metric", "quantity", "tenant", "period_start", "period_end",
                    "is_billed", "billed_at"]
    list_filter = ["metric", "is_billed", "tenant"]
    search_fields = ["metric", "notes"]
    list_select_related = ["tenant", "subscription", "subscription_invoice"]
    # Evidence stamps: written only by usagerecord_mark_billed, never hand-edited here.
    readonly_fields = ["is_billed", "billed_at", "created_at"]
