from django.contrib import admin

from .models import (
    BrandingSetting,
    EncryptionKey,
    EntitlementFeature,
    HealthMetric,
    LicenseAssignment,
    PlanEntitlement,
    Subscription,
    SubscriptionInvoice,
    UsageQuota,
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


# ===================== 0.19 License & Subscription Administration =====================
# The evidence stamps are readonly in every one of these: a staff user with admin access could
# otherwise forge the very attribution the one-writer verbs exist to establish (the 0.18
# IpAccessRuleAdmin gap).


class TenantScopedSubscriptionMixin:
    """Scope the `subscription` picker to the row's own workspace (I15).

    The Django admin is **not** tenant-scoped, and the admin path is the one way past the form's
    `TenantModelForm` FK scoping. Without this a superuser can pair a tenant-A row with a tenant-B
    subscription. Each model now also refuses the pair in `clean()`, so this is the first of two
    independent defences rather than the only one.

    Deliberately NOT a `clean()` on the ModelAdmin: the models already own that rule, and a second
    copy is exactly the duplicated-guard pattern the reviews flagged elsewhere in 0.19.
    """

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "subscription" and "tenant" in {
            f.name for f in db_field.related_model._meta.fields
        }:
            kwargs["queryset"] = db_field.related_model.objects.filter(
                tenant_id=getattr(request, "tenant", None)
            ) if getattr(request, "tenant", None) is not None else db_field.related_model.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(EntitlementFeature)
class EntitlementFeatureAdmin(admin.ModelAdmin):
    list_display = ["number", "code", "name", "privilege_type", "status", "is_add_on",
                    "is_active", "tenant"]
    list_filter = ["privilege_type", "status", "is_add_on", "is_active", "tenant"]
    search_fields = ["number", "code", "name"]
    list_select_related = ["tenant"]
    readonly_fields = ["number", "created_at"]


@admin.register(PlanEntitlement)
class PlanEntitlementAdmin(TenantScopedSubscriptionMixin, admin.ModelAdmin):
    list_display = ["number", "plan", "feature", "privilege_value", "subscription",
                    "effective_to", "is_enabled", "tenant"]
    list_filter = ["plan", "is_add_on", "is_enabled", "tenant"]
    search_fields = ["number", "privilege_value"]
    list_select_related = ["tenant", "feature", "subscription"]
    readonly_fields = ["number", "created_at"]


@admin.register(UsageQuota)
class UsageQuotaAdmin(TenantScopedSubscriptionMixin, admin.ModelAdmin):
    list_display = ["number", "subscription", "metric", "quota_limit", "warn_at_pct",
                    "action_on_breach", "is_fair_use", "breached_at", "tenant"]
    list_filter = ["metric", "action_on_breach", "period", "is_fair_use", "tenant"]
    search_fields = ["number"]
    list_select_related = ["tenant", "subscription"]
    # `breached_at` is the sole-writer evidence stamp of `usagequota_mark_breached`.
    readonly_fields = ["number", "breached_at", "created_at"]


@admin.register(LicenseAssignment)
class LicenseAssignmentAdmin(TenantScopedSubscriptionMixin, admin.ModelAdmin):
    list_display = ["number", "user", "module_slug", "status", "assignment_source",
                    "subscription", "expires_on", "reclaimed_on", "tenant"]
    list_filter = ["status", "assignment_source", "tenant"]
    search_fields = ["number", "module_slug", "notes"]
    list_select_related = ["tenant", "user", "subscription"]
    # `status` is off the user-facing form too — the sole writer is `licenseassignment_reclaim`,
    # so it is readonly here for the same reason (a staff user must not re-activate a reclaimed seat).
    readonly_fields = ["number", "status", "reclaimed_on", "reclaim_reason", "created_at"]
