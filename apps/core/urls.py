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
    ]
)
