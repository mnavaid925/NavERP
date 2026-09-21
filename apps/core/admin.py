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
    WorkflowDefinition,
    WorkflowStep,
    ApprovalLimit,
    SlaRule,
    BusinessRule,
    BusinessRuleLog,
    NotificationChannel,
    NotificationTemplate,
    NotificationRule,
    NotificationPreference,
    ProviderConfig,
    ApiCredential,
    RateLimitPolicy,
    ConnectorDefinition,
    MappingTemplate,
    SyncSchedule,
    Language,
    TimeZone,
    LocaleProfile,
    UserLocalePreference,
    StatutoryRule,
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


class WorkflowStepInline(admin.TabularInline):
    model = WorkflowStep
    extra = 0
    fields = ["sequence", "name", "approver_role", "is_parallel", "threshold_amount"]
    ordering = ["sequence", "id"]


@admin.register(WorkflowDefinition)
class WorkflowDefinitionAdmin(admin.ModelAdmin):
    list_display = ["name", "module_slug", "engine_label", "owner_role", "is_active", "tenant"]
    list_filter = ["module_slug", "is_active", "tenant"]
    search_fields = ["name", "engine_label"]
    list_select_related = ["owner_role", "tenant"]
    readonly_fields = ["created_at"]
    inlines = [WorkflowStepInline]


@admin.register(WorkflowStep)
class WorkflowStepAdmin(admin.ModelAdmin):
    list_display = ["definition", "sequence", "name", "approver_role", "is_parallel"]
    list_filter = ["is_parallel", "tenant"]
    search_fields = ["name", "definition__name"]
    list_select_related = ["definition", "approver_role"]


@admin.register(ApprovalLimit)
class ApprovalLimitAdmin(admin.ModelAdmin):
    list_display = ["module_slug", "role", "max_amount", "currency_code", "tenant"]
    list_filter = ["module_slug", "tenant"]
    search_fields = ["module_slug", "role__name"]
    list_select_related = ["role", "tenant"]
    readonly_fields = ["updated_at"]


@admin.register(SlaRule)
class SlaRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "module_slug", "hours", "action", "escalate_to_role", "is_active"]
    list_filter = ["module_slug", "action", "is_active", "tenant"]
    search_fields = ["name", "engine_label"]
    list_select_related = ["escalate_to_role", "tenant"]
    readonly_fields = ["updated_at"]


@admin.register(BusinessRule)
class BusinessRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "module_slug", "trigger", "action", "priority", "is_active", "tenant"]
    list_filter = ["module_slug", "trigger", "action", "is_active", "tenant"]
    search_fields = ["name", "notes"]
    list_select_related = ["tenant"]
    readonly_fields = ["created_at"]


@admin.register(BusinessRuleLog)
class BusinessRuleLogAdmin(admin.ModelAdmin):
    list_display = ["module_slug", "trigger", "matched", "rule", "evaluated_at", "tenant"]
    list_filter = ["module_slug", "trigger", "matched", "tenant"]
    search_fields = ["module_slug", "action_taken"]
    list_select_related = ["rule", "evaluated_by", "tenant"]
    # An evaluation log is a record of what happened; nothing here is editable.
    readonly_fields = ["tenant", "rule", "module_slug", "trigger", "context", "matched",
                       "action_taken", "evaluated_by", "evaluated_at"]

    def has_add_permission(self, request):
        return False


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ["kind", "label", "is_enabled", "tenant"]
    list_filter = ["kind", "is_enabled", "tenant"]
    search_fields = ["label"]
    readonly_fields = ["updated_at"]


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "channel_kind", "locale", "module_slug", "is_active", "tenant"]
    list_filter = ["channel_kind", "locale", "is_active", "tenant"]
    search_fields = ["code", "name", "subject"]
    readonly_fields = ["created_at"]


@admin.register(NotificationRule)
class NotificationRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "event", "module_slug", "channel", "audience_kind", "digest",
                    "is_active", "tenant"]
    list_filter = ["event", "audience_kind", "digest", "is_active", "tenant"]
    search_fields = ["name", "event"]
    list_select_related = ["channel", "template", "audience_role", "audience_user", "tenant"]
    readonly_fields = ["created_at"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "event", "channel_kind", "is_enabled", "tenant"]
    list_filter = ["channel_kind", "is_enabled", "tenant"]
    search_fields = ["event", "user__email"]
    list_select_related = ["user", "tenant"]
    readonly_fields = ["updated_at"]


@admin.register(ProviderConfig)
class ProviderConfigAdmin(admin.ModelAdmin):
    list_display = ["channel_kind", "label", "priority", "host", "is_active", "tenant"]
    list_filter = ["channel_kind", "is_active", "tenant"]
    search_fields = ["label", "host", "from_address"]
    list_select_related = ["tenant"]
    # The credential is never stored here, so there is nothing secret to render — only the NAME of
    # the environment variable holding it.
    readonly_fields = ["updated_at"]


@admin.register(ApiCredential)
class ApiCredentialAdmin(admin.ModelAdmin):
    list_display = ["label", "kind", "prefix", "is_active", "last_used_at", "expires_at", "tenant"]
    list_filter = ["kind", "is_active", "tenant"]
    search_fields = ["label", "prefix", "scopes"]
    list_select_related = ["created_by", "tenant"]
    # The plaintext was never stored, so there is nothing secret to render — only the prefix and the
    # hash, both of which are safe to display and useful for identifying a key in a log.
    readonly_fields = ["prefix", "key_hash", "last_used_at", "created_by", "created_at"]


@admin.register(RateLimitPolicy)
class RateLimitPolicyAdmin(admin.ModelAdmin):
    list_display = ["name", "credential", "max_requests", "window", "is_active", "tenant"]
    list_filter = ["window", "is_active", "tenant"]
    search_fields = ["name"]
    list_select_related = ["credential", "tenant"]
    readonly_fields = ["updated_at"]


@admin.register(ConnectorDefinition)
class ConnectorDefinitionAdmin(admin.ModelAdmin):
    list_display = ["name", "vendor", "category", "engine_label", "is_installed", "is_active",
                    "tenant"]
    list_filter = ["category", "is_installed", "is_active", "tenant"]
    search_fields = ["name", "vendor", "engine_label"]
    list_select_related = ["tenant"]
    readonly_fields = ["created_at"]


@admin.register(MappingTemplate)
class MappingTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "direction", "source_format", "target_label", "is_active", "tenant"]
    list_filter = ["direction", "is_active", "tenant"]
    search_fields = ["name", "source_format", "target_label"]
    list_select_related = ["tenant"]
    readonly_fields = ["created_at"]


@admin.register(SyncSchedule)
class SyncScheduleAdmin(admin.ModelAdmin):
    list_display = ["name", "direction", "transport", "frequency", "is_active", "tenant"]
    list_filter = ["direction", "transport", "frequency", "is_active", "tenant"]
    search_fields = ["name", "entity_label"]
    list_select_related = ["mapping_template", "connector", "tenant"]
    readonly_fields = ["updated_at"]


# ---------------------------------------------------------------- 0.15 Localization & Regional Settings
@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "native_name", "is_rtl", "is_default", "is_active"]
    list_filter = ["is_rtl", "is_default", "is_active"]
    search_fields = ["code", "name", "native_name"]


@admin.register(TimeZone)
class TimeZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "label", "utc_offset_minutes", "observes_dst", "is_active"]
    list_filter = ["observes_dst", "is_active"]
    search_fields = ["name", "label"]


@admin.register(LocaleProfile)
class LocaleProfileAdmin(admin.ModelAdmin):
    list_display = ["tenant", "language", "base_currency", "time_zone", "first_day_of_week",
                    "updated_at"]
    list_filter = ["first_day_of_week", "language", "time_zone"]
    search_fields = ["tenant__name"]
    list_select_related = ["tenant", "language", "base_currency", "time_zone"]
    readonly_fields = ["updated_at"]


@admin.register(UserLocalePreference)
class UserLocalePreferenceAdmin(admin.ModelAdmin):
    list_display = ["user", "language", "time_zone", "date_format", "tenant", "updated_at"]
    list_filter = ["language", "time_zone", "tenant"]
    search_fields = ["user__email"]
    list_select_related = ["user", "language", "time_zone", "tenant"]
    readonly_fields = ["updated_at"]


@admin.register(StatutoryRule)
class StatutoryRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "jurisdiction", "tax_code", "e_invoicing_scheme",
                    "e_invoicing_required", "effective_from", "is_active", "tenant"]
    list_filter = ["e_invoicing_scheme", "e_invoicing_required", "is_active", "tenant"]
    search_fields = ["name", "jurisdiction", "statutory_report"]
    list_select_related = ["tax_code", "tenant"]
    readonly_fields = ["created_at", "updated_at"]
