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
    ModuleAccessScope,
    SensitiveFieldMask,
    ConsentPurpose,
    ConsentRecord,
    DataSubjectRequest,
    RetentionPolicy,
    DisposalRecord,
    PiiClassification,
    RegulatoryFramework,
    SettingDefinition,
    SettingValue,
    FeatureFlag,
    NumberingScheme,
    BusinessCalendar,
    Holiday,
    CustomFieldDefinition,
    CustomFieldValue,
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


@admin.register(ModuleAccessScope)
class ModuleAccessScopeAdmin(admin.ModelAdmin):
    list_display = ["module_number", "module_slug", "module_title", "is_enabled", "data_scope",
                    "requires_approval", "mask_sensitive", "tenant"]
    list_filter = ["is_enabled", "data_scope", "requires_approval", "tenant"]
    search_fields = ["module_slug", "module_title"]
    list_select_related = ["tenant"]
    readonly_fields = ["updated_at"]


@admin.register(SensitiveFieldMask)
class SensitiveFieldMaskAdmin(admin.ModelAdmin):
    list_display = ["scope", "field_name", "mask_style", "tenant"]
    list_filter = ["mask_style", "tenant"]
    search_fields = ["field_name", "scope__module_slug"]
    list_select_related = ["scope", "tenant"]
    filter_horizontal = ["exempt_roles"]
    readonly_fields = ["created_at"]


@admin.register(ConsentPurpose)
class ConsentPurposeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "lawful_basis", "is_optional", "is_active", "tenant"]
    list_filter = ["lawful_basis", "is_active", "tenant"]
    search_fields = ["name", "code"]


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ["party", "purpose", "action", "source", "occurred_at", "tenant"]
    list_filter = ["action", "source", "tenant"]
    search_fields = ["party__name", "purpose__name", "evidence"]
    list_select_related = ["party", "purpose", "recorded_by"]
    # A consent event is a record of something that happened; only the audit trail may change it.
    readonly_fields = ["recorded_by", "created_at"]


@admin.register(DataSubjectRequest)
class DataSubjectRequestAdmin(admin.ModelAdmin):
    list_display = ["subject", "kind", "status", "identity_verified", "due_at", "tenant"]
    list_filter = ["status", "kind", "identity_verified", "tenant"]
    search_fields = ["subject__name", "detail"]
    list_select_related = ["subject", "handled_by"]
    # Verb-written evidence: hand-editing these would forge a verification or a completion.
    readonly_fields = ["identity_verified", "completed_at", "handled_by", "created_at"]


@admin.register(RetentionPolicy)
class RetentionPolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "data_category", "model_label", "retention_months", "action",
                    "is_active", "tenant"]
    list_filter = ["action", "basis", "is_active", "tenant"]
    search_fields = ["name", "data_category", "model_label"]
    readonly_fields = ["updated_at"]


@admin.register(DisposalRecord)
class DisposalRecordAdmin(admin.ModelAdmin):
    list_display = ["model_label", "policy", "record_count", "method", "performed_at", "tenant"]
    list_filter = ["method", "tenant"]
    search_fields = ["model_label", "evidence", "notes"]
    list_select_related = ["policy", "performed_by"]
    readonly_fields = ["created_at"]


@admin.register(PiiClassification)
class PiiClassificationAdmin(admin.ModelAdmin):
    list_display = ["model_label", "field_name", "category", "sensitivity", "confirmation", "tenant"]
    list_filter = ["category", "sensitivity", "confirmation", "tenant"]
    search_fields = ["model_label", "field_name", "notes"]
    list_select_related = ["reviewed_by", "tenant"]
    readonly_fields = ["reviewed_by", "reviewed_at", "created_at"]


@admin.register(RegulatoryFramework)
class RegulatoryFrameworkAdmin(admin.ModelAdmin):
    list_display = ["code", "label", "is_enabled", "dsar_window_days", "data_residency_region", "tenant"]
    list_filter = ["code", "is_enabled", "tenant"]
    search_fields = ["label", "data_residency_region"]
    readonly_fields = ["updated_at"]


@admin.register(SettingDefinition)
class SettingDefinitionAdmin(admin.ModelAdmin):
    list_display = ["key", "label", "module_slug", "value_type", "default_value", "is_locked"]
    list_filter = ["value_type", "module_slug", "is_locked"]
    search_fields = ["key", "label"]
    readonly_fields = ["created_at"]


@admin.register(SettingValue)
class SettingValueAdmin(admin.ModelAdmin):
    list_display = ["tenant", "definition", "value", "updated_at"]
    list_filter = ["tenant"]
    search_fields = ["definition__key", "value"]
    list_select_related = ["tenant", "definition"]
    readonly_fields = ["updated_by", "updated_at"]


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ["key", "label", "is_enabled", "applies_to_plan", "tenant"]
    list_filter = ["is_enabled", "applies_to_plan", "tenant"]
    search_fields = ["key", "label"]
    list_select_related = ["tenant"]
    filter_horizontal = ["exempt_roles"]
    readonly_fields = ["updated_at"]


@admin.register(NumberingScheme)
class NumberingSchemeAdmin(admin.ModelAdmin):
    list_display = ["document_kind", "prefix", "padding_width", "reset_rule", "is_active", "tenant"]
    list_filter = ["reset_rule", "is_active", "tenant"]
    search_fields = ["document_kind", "prefix"]
    readonly_fields = ["updated_at"]


@admin.register(BusinessCalendar)
class BusinessCalendarAdmin(admin.ModelAdmin):
    list_display = ["tenant", "timezone_name", "working_days", "updated_at"]
    list_select_related = ["tenant"]
    readonly_fields = ["updated_at"]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ["date", "name", "is_recurring", "region", "tenant"]
    list_filter = ["is_recurring", "tenant"]
    search_fields = ["name", "region"]
    list_select_related = ["tenant"]


@admin.register(CustomFieldDefinition)
class CustomFieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ["entity_label", "field_key", "label", "field_type", "is_required",
                    "is_active", "tenant"]
    list_filter = ["field_type", "is_required", "is_active", "tenant"]
    search_fields = ["entity_label", "field_key", "label"]
    list_select_related = ["tenant"]
    readonly_fields = ["created_at"]


@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ["entity_label", "object_id", "definition", "value", "updated_at", "tenant"]
    list_filter = ["tenant"]
    search_fields = ["entity_label", "definition__field_key"]
    list_select_related = ["tenant", "definition"]
    readonly_fields = ["updated_by", "updated_at"]
