from django.urls import path

from . import views

app_name = "core"


def crud(slug, name):
    """Generate the 5 standard CRUD routes for a model."""
    return [
        path(f"{slug}/", getattr(views, f"{name}_list"), name=f"{name}_list"),
        path(f"{slug}/add/", getattr(views, f"{name}_create"), name=f"{name}_create"),
        path(f"{slug}/<int:pk>/", getattr(views, f"{name}_detail"), name=f"{name}_detail"),
        path(f"{slug}/<int:pk>/edit/", getattr(views, f"{name}_edit"), name=f"{name}_edit"),
        path(f"{slug}/<int:pk>/delete/", getattr(views, f"{name}_delete"), name=f"{name}_delete"),
    ]


urlpatterns = (
    crud("org-units", "orgunit")
    + crud("parties", "party")
    + crud("party-roles", "partyrole")
    + crud("addresses", "address")
    + crud("contact-methods", "contactmethod")
    + crud("relationships", "partyrelationship")
    + crud("employments", "employment")
    + crud("activities", "activity")
    + crud("documents", "document")
    + [
        path("audit-logs/", views.auditlog_list, name="auditlog_list"),
        path("audit-logs/<int:pk>/", views.auditlog_detail, name="auditlog_detail"),
        # Global header search
        path("search/", views.global_search, name="search"),
        path("search/suggest/", views.global_search_suggest, name="search_suggest"),
        # 0.6 module access scope — literal segments BEFORE the <int:pk> routes
        path("module-scopes/", views.module_scope_list, name="module_scope_list"),
        path("module-scopes/sync/", views.module_scope_sync, name="module_scope_sync"),
        path("module-scopes/add/", views.module_scope_create, name="module_scope_create"),
        path("module-scopes/<int:pk>/", views.module_scope_detail, name="module_scope_detail"),
        path("module-scopes/<int:pk>/edit/", views.module_scope_edit, name="module_scope_edit"),
        path("module-scopes/<int:pk>/delete/", views.module_scope_delete, name="module_scope_delete"),
        path("field-masks/", views.field_mask_list, name="field_mask_list"),
        path("field-masks/add/", views.field_mask_create, name="field_mask_create"),
        path("field-masks/<int:pk>/edit/", views.field_mask_edit, name="field_mask_edit"),
        path("field-masks/<int:pk>/delete/", views.field_mask_delete, name="field_mask_delete"),
        path("access-matrix/", views.access_matrix, name="access_matrix"),
        # 0.8 Privacy & Data Protection. Literal segments BEFORE the <int:pk> routes.
        path("privacy/", views.privacy_overview, name="privacy_overview"),
        path("consent-purposes/", views.consent_purpose_list, name="consent_purpose_list"),
        path("consent-purposes/add/", views.consent_purpose_create, name="consent_purpose_create"),
        path("consent-purposes/<int:pk>/edit/", views.consent_purpose_edit, name="consent_purpose_edit"),
        path("consent-purposes/<int:pk>/delete/", views.consent_purpose_delete, name="consent_purpose_delete"),
        path("consent-records/", views.consent_record_list, name="consent_record_list"),
        path("consent-records/add/", views.consent_record_create, name="consent_record_create"),
        path("consent-records/<int:pk>/delete/", views.consent_record_delete, name="consent_record_delete"),
        path("consent-matrix/", views.consent_matrix, name="consent_matrix"),
        path("dsars/", views.dsar_list, name="dsar_list"),
        path("dsars/add/", views.dsar_create, name="dsar_create"),
        path("dsars/<int:pk>/", views.dsar_detail, name="dsar_detail"),
        path("dsars/<int:pk>/edit/", views.dsar_edit, name="dsar_edit"),
        path("dsars/<int:pk>/delete/", views.dsar_delete, name="dsar_delete"),
        path("dsars/<int:pk>/verify/", views.dsar_verify, name="dsar_verify"),
        path("dsars/<int:pk>/complete/", views.dsar_complete, name="dsar_complete"),
        path("dsars/<int:pk>/refuse/", views.dsar_refuse, name="dsar_refuse"),
        path("dsars/<int:pk>/withdraw/", views.dsar_withdraw, name="dsar_withdraw"),
        path("retention-policies/", views.retention_policy_list, name="retention_policy_list"),
        path("retention-policies/add/", views.retention_policy_create, name="retention_policy_create"),
        path("retention-policies/<int:pk>/edit/", views.retention_policy_edit, name="retention_policy_edit"),
        path("retention-policies/<int:pk>/delete/", views.retention_policy_delete, name="retention_policy_delete"),
        path("disposals/", views.disposal_list, name="disposal_list"),
        path("disposals/add/", views.disposal_create, name="disposal_create"),
        path("retention-board/", views.retention_board, name="retention_board"),
        path("pii-map/", views.pii_map, name="pii_map"),
        path("pii-map/scan/", views.pii_scan, name="pii_scan"),
        path("pii-map/<int:pk>/classify/", views.pii_classify, name="pii_classify"),
        path("regulatory/", views.regulatory_list, name="regulatory_list"),
        path("regulatory/sync/", views.regulatory_sync, name="regulatory_sync"),
        path("regulatory/<int:pk>/edit/", views.regulatory_edit, name="regulatory_edit"),
        # 0.10 System Configuration & Settings. Literal segments before the <int:pk> routes.
        path("config/", views.config_overview, name="config_overview"),
        path("config/settings/", views.settings_overview, name="settings_overview"),
        path("config/settings/definitions/", views.setting_definition_list, name="setting_definition_list"),
        path("config/settings/definitions/add/", views.setting_definition_create, name="setting_definition_create"),
        path("config/settings/definitions/<int:pk>/edit/", views.setting_definition_edit, name="setting_definition_edit"),
        path("config/settings/definitions/<int:pk>/delete/", views.setting_definition_delete, name="setting_definition_delete"),
        path("config/settings/<int:pk>/override/", views.setting_value_edit, name="setting_value_edit"),
        path("config/features/", views.feature_flag_list, name="feature_flag_list"),
        path("config/features/add/", views.feature_flag_create, name="feature_flag_create"),
        path("config/features/<int:pk>/edit/", views.feature_flag_edit, name="feature_flag_edit"),
        path("config/features/<int:pk>/delete/", views.feature_flag_delete, name="feature_flag_delete"),
        path("config/numbering/", views.numbering_scheme_list, name="numbering_scheme_list"),
        path("config/numbering/board/", views.numbering_board, name="numbering_board"),
        path("config/numbering/add/", views.numbering_scheme_create, name="numbering_scheme_create"),
        path("config/numbering/<int:pk>/edit/", views.numbering_scheme_edit, name="numbering_scheme_edit"),
        path("config/numbering/<int:pk>/delete/", views.numbering_scheme_delete, name="numbering_scheme_delete"),
        path("config/calendar/", views.calendar_board, name="calendar_board"),
        path("config/calendar/edit/", views.calendar_edit, name="calendar_edit"),
        path("config/calendar/holidays/", views.holiday_list, name="holiday_list"),
        path("config/calendar/holidays/add/", views.holiday_create, name="holiday_create"),
        path("config/calendar/holidays/<int:pk>/edit/", views.holiday_edit, name="holiday_edit"),
        path("config/calendar/holidays/<int:pk>/delete/", views.holiday_delete, name="holiday_delete"),
        path("config/custom-fields/", views.custom_field_list, name="custom_field_list"),
        path("config/custom-fields/add/", views.custom_field_create, name="custom_field_create"),
        path("config/custom-fields/<int:pk>/", views.custom_field_detail, name="custom_field_detail"),
        path("config/custom-fields/<int:pk>/edit/", views.custom_field_edit, name="custom_field_edit"),
        path("config/custom-fields/<int:pk>/delete/", views.custom_field_delete, name="custom_field_delete"),
        path("config/custom-fields/<int:pk>/values/add/", views.custom_field_value_create, name="custom_field_value_create"),
        path("config/custom-fields/values/<int:pk>/delete/", views.custom_field_value_delete, name="custom_field_value_delete"),
        # 0.11 Workflow & Approval Administration. Literal segments before the <int:pk> routes.
        path("workflows/", views.workflow_overview, name="workflow_overview"),
        path("workflows/monitor/", views.process_monitor, name="process_monitor"),
        path("workflows/definitions/", views.workflow_definition_list, name="workflow_definition_list"),
        path("workflows/definitions/add/", views.workflow_definition_create, name="workflow_definition_create"),
        path("workflows/definitions/<int:pk>/", views.workflow_definition_detail, name="workflow_definition_detail"),
        path("workflows/definitions/<int:pk>/edit/", views.workflow_definition_edit, name="workflow_definition_edit"),
        path("workflows/definitions/<int:pk>/delete/", views.workflow_definition_delete, name="workflow_definition_delete"),
        path("workflows/definitions/<int:pk>/steps/add/", views.workflow_step_create, name="workflow_step_create"),
        path("workflows/steps/<int:pk>/edit/", views.workflow_step_edit, name="workflow_step_edit"),
        path("workflows/steps/<int:pk>/delete/", views.workflow_step_delete, name="workflow_step_delete"),
        path("workflows/limits/", views.approval_limit_list, name="approval_limit_list"),
        path("workflows/limits/add/", views.approval_limit_create, name="approval_limit_create"),
        path("workflows/limits/<int:pk>/edit/", views.approval_limit_edit, name="approval_limit_edit"),
        path("workflows/limits/<int:pk>/delete/", views.approval_limit_delete, name="approval_limit_delete"),
        path("workflows/sla/", views.sla_rule_list, name="sla_rule_list"),
        path("workflows/sla/add/", views.sla_rule_create, name="sla_rule_create"),
        path("workflows/sla/<int:pk>/edit/", views.sla_rule_edit, name="sla_rule_edit"),
        path("workflows/sla/<int:pk>/delete/", views.sla_rule_delete, name="sla_rule_delete"),
        path("workflows/rules/", views.business_rule_list, name="business_rule_list"),
        path("workflows/rules/add/", views.business_rule_create, name="business_rule_create"),
        path("workflows/rules/log/", views.rule_log_list, name="rule_log_list"),
        path("workflows/rules/<int:pk>/", views.business_rule_detail, name="business_rule_detail"),
        path("workflows/rules/<int:pk>/edit/", views.business_rule_edit, name="business_rule_edit"),
        path("workflows/rules/<int:pk>/delete/", views.business_rule_delete, name="business_rule_delete"),
        path("workflows/rules/<int:pk>/test/", views.business_rule_test, name="business_rule_test"),
        # 0.12 Notification & Communication. Literal segments before the <int:pk> routes.
        path("notifications/", views.notification_overview, name="notification_overview"),
        path("notifications/delivery/", views.delivery_board, name="delivery_board"),
        path("notifications/my-preferences/", views.my_preferences, name="my_preferences"),
        path("notifications/channels/", views.channel_list, name="channel_list"),
        path("notifications/channels/add/", views.channel_create, name="channel_create"),
        path("notifications/channels/<int:pk>/edit/", views.channel_edit, name="channel_edit"),
        path("notifications/channels/<int:pk>/delete/", views.channel_delete, name="channel_delete"),
        path("notifications/templates/", views.template_list, name="template_list"),
        path("notifications/templates/add/", views.template_create, name="template_create"),
        path("notifications/templates/<int:pk>/", views.template_detail, name="template_detail"),
        path("notifications/templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
        path("notifications/templates/<int:pk>/delete/", views.template_delete, name="template_delete"),
        path("notifications/templates/<int:pk>/preview/", views.template_preview, name="template_preview"),
        path("notifications/rules/", views.rule_list, name="rule_list"),
        path("notifications/rules/add/", views.rule_create, name="rule_create"),
        path("notifications/rules/<int:pk>/edit/", views.rule_edit, name="rule_edit"),
        path("notifications/rules/<int:pk>/delete/", views.rule_delete, name="rule_delete"),
        path("notifications/rules/<int:pk>/resolve/", views.rule_resolve, name="rule_resolve"),
        path("notifications/preferences/", views.preference_list, name="preference_list"),
        path("notifications/preferences/add/", views.preference_create, name="preference_create"),
        path("notifications/preferences/<int:pk>/edit/", views.preference_edit, name="preference_edit"),
        path("notifications/preferences/<int:pk>/delete/", views.preference_delete, name="preference_delete"),
        path("notifications/providers/", views.provider_list, name="provider_list"),
        path("notifications/providers/add/", views.provider_create, name="provider_create"),
        path("notifications/providers/<int:pk>/edit/", views.provider_edit, name="provider_edit"),
        path("notifications/providers/<int:pk>/delete/", views.provider_delete, name="provider_delete"),
        # 0.13 Integration & API Management. Literal segments before the <int:pk> routes.
        path("integrations/", views.integration_overview, name="integration_overview"),
        path("integrations/health/", views.integration_board, name="integration_board"),
        path("integrations/credentials/", views.credential_list, name="credential_list"),
        path("integrations/credentials/issue/", views.credential_issue, name="credential_issue"),
        path("integrations/credentials/<int:pk>/edit/", views.credential_edit, name="credential_edit"),
        path("integrations/credentials/<int:pk>/revoke/", views.credential_revoke, name="credential_revoke"),
        path("integrations/credentials/<int:pk>/delete/", views.credential_delete, name="credential_delete"),
        path("integrations/rate-limits/", views.rate_limit_list, name="rate_limit_list"),
        path("integrations/rate-limits/add/", views.rate_limit_create, name="rate_limit_create"),
        path("integrations/rate-limits/<int:pk>/edit/", views.rate_limit_edit, name="rate_limit_edit"),
        path("integrations/rate-limits/<int:pk>/delete/", views.rate_limit_delete, name="rate_limit_delete"),
        path("integrations/connectors/", views.connector_list, name="connector_list"),
        path("integrations/connectors/add/", views.connector_create, name="connector_create"),
        path("integrations/connectors/<int:pk>/edit/", views.connector_edit, name="connector_edit"),
        path("integrations/connectors/<int:pk>/delete/", views.connector_delete, name="connector_delete"),
        path("integrations/mappings/", views.mapping_list, name="mapping_list"),
        path("integrations/mappings/add/", views.mapping_create, name="mapping_create"),
        path("integrations/mappings/<int:pk>/", views.mapping_detail, name="mapping_detail"),
        path("integrations/mappings/<int:pk>/edit/", views.mapping_edit, name="mapping_edit"),
        path("integrations/mappings/<int:pk>/delete/", views.mapping_delete, name="mapping_delete"),
        path("integrations/syncs/", views.sync_list, name="sync_list"),
        path("integrations/syncs/add/", views.sync_create, name="sync_create"),
        path("integrations/syncs/<int:pk>/edit/", views.sync_edit, name="sync_edit"),
        path("integrations/syncs/<int:pk>/delete/", views.sync_delete, name="sync_delete"),
        # 0.15 Localization & Regional Settings. Literal segments before the <int:pk> routes.
        path("localization/", views.localization_overview, name="localization_overview"),
        path("localization/board/", views.localization_board, name="localization_board"),
        path("localization/languages/", views.language_list, name="language_list"),
        path("localization/time-zones/", views.timezone_list, name="timezone_list"),
        path("localization/profile/", views.locale_profile_edit, name="locale_profile_edit"),
        path("localization/my-settings/", views.user_locale_edit, name="user_locale_edit"),
        path("localization/statutory/", views.statutory_rule_list, name="statutory_rule_list"),
        path("localization/statutory/add/", views.statutory_rule_create,
             name="statutory_rule_create"),
        path("localization/statutory/<int:pk>/", views.statutory_rule_detail,
             name="statutory_rule_detail"),
        path("localization/statutory/<int:pk>/edit/", views.statutory_rule_edit,
             name="statutory_rule_edit"),
        path("localization/statutory/<int:pk>/delete/", views.statutory_rule_delete,
             name="statutory_rule_delete"),
        # 0.16 Backup, Recovery & Data Lifecycle. Literal segments before the <int:pk> routes, and the
        # five registers use the same `crud()` factory as the spine above.
        path("backup/", views.backup_overview, name="backup_overview"),
        path("backup/board/", views.backup_board, name="backup_board"),
        # `recovery_posture_edit` is a SINGLETON, so it is NOT one of the `crud()` models: there is
        # nothing to list, create or delete, only the one row to edit.
        path("backup/posture/", views.recovery_posture_edit, name="recovery_posture_edit"),
    ]
    + crud("backup/jobs", "backup_job")
    + [
        # POST-only action, declared after the literal `add/` route above so it cannot shadow it.
        path("backup/jobs/<int:pk>/verify/", views.backup_job_verify, name="backup_job_verify"),
    ]
    + crud("backup/restores", "restore_record")
    + crud("backup/archives", "data_archive")
    + crud("backup/holds", "legal_hold")
    + crud("backup/environments", "environment_instance")
    + crud("backup/drills", "recovery_drill")
)
