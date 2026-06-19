from django.contrib import admin

from .models import (
    Activity,
    Address,
    AuditLog,
    ContactMethod,
    Document,
    Employment,
    OrgUnit,
    Party,
    PartyRelationship,
    PartyRole,
    Tenant,
)


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "plan", "is_active", "created_at"]
    list_filter = ["plan", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "parent", "tenant"]
    list_filter = ["kind", "tenant"]
    search_fields = ["name"]


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "tax_id", "tenant"]
    list_filter = ["kind", "tenant"]
    search_fields = ["name", "tax_id"]


@admin.register(PartyRole)
class PartyRoleAdmin(admin.ModelAdmin):
    list_display = ["party", "role", "status", "tenant"]
    list_filter = ["role", "status", "tenant"]
    search_fields = ["party__name"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["party", "kind", "line1", "city", "country", "tenant"]
    list_filter = ["kind", "tenant"]
    search_fields = ["line1", "city"]


@admin.register(ContactMethod)
class ContactMethodAdmin(admin.ModelAdmin):
    list_display = ["party", "kind", "value", "tenant"]
    list_filter = ["kind", "tenant"]
    search_fields = ["value"]


@admin.register(PartyRelationship)
class PartyRelationshipAdmin(admin.ModelAdmin):
    list_display = ["from_party", "kind", "to_party", "tenant"]
    list_filter = ["kind", "tenant"]


@admin.register(Employment)
class EmploymentAdmin(admin.ModelAdmin):
    list_display = ["party", "job_title", "org_unit", "manager", "status", "tenant"]
    list_filter = ["status", "tenant"]
    search_fields = ["party__name", "job_title"]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["subject", "kind", "status", "owner", "party", "due_at", "tenant"]
    list_filter = ["kind", "status", "tenant"]
    search_fields = ["subject"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["name", "classification", "version", "uploaded_at", "tenant"]
    list_filter = ["classification", "tenant"]
    search_fields = ["name"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "target", "user", "at", "tenant"]
    list_filter = ["action", "tenant"]
    search_fields = ["target"]
    readonly_fields = ["tenant", "user", "content_type", "object_id", "target", "action", "changes", "at"]
