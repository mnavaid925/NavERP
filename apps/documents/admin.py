from django.contrib import admin

from apps.documents.models.ApprovalWorkflow.DocumentApprovalRequests import (
    DocumentApprovalRequest,
)
from apps.documents.models.ApprovalWorkflow.DocumentApprovalWorkflows import (
    DocumentApprovalWorkflow,
)
from apps.documents.models.ApprovalWorkflow.DocumentReviewComments import (
    DocumentReviewComment,
)
from apps.documents.models.ApprovalWorkflow.DocumentSignatures import DocumentSignature
from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert
from apps.documents.models.CollaborationSharing.CoauthorSessions import CoauthorSession
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection
from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob
from apps.documents.models.MetadataIndexing.MetadataSchemas import MetadataSchema
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm
from apps.documents.models.RecordsManagement.DestructionCertificates import DestructionCertificate
from apps.documents.models.RecordsManagement.DocumentLegalHolds import DocumentLegalHold
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.models.RecordsManagement.RetentionSchedules import RetentionSchedule
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchAlerts import DocumentSearchAlert
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.SecurityAccessControl.DlpIncidents import DlpIncident
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy
from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import (
    DocumentAccessPermission,
)
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import (
    DocumentDrmPolicy,
)
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.models.StorageRepository.DocumentBatchImports import DocumentBatchImport
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.StorageRepository.StorageVolumes import StorageVolume
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "document_type", "classification", "status", "current_version_label", "is_locked", "owner", "tenant")
    list_filter = ("document_type", "classification", "status", "is_locked", "tenant")
    search_fields = ("number", "title", "description", "tags")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "version_label", "version_type", "is_official", "status", "author", "tenant")
    list_filter = ("version_type", "is_official", "status", "tenant")
    search_fields = ("number", "version_label", "change_summary", "file_name", "document__title")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentLock)
class DocumentLockAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "locked_by", "lock_type", "status", "checked_out_at", "expires_at", "tenant")
    list_filter = ("lock_type", "status", "tenant")
    search_fields = ("number", "checkout_note", "document__title", "locked_by__username")
    readonly_fields = ("number", "checked_out_at", "unlocked_at")


@admin.register(DocumentBranch)
class DocumentBranchAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "document", "branch_type", "status", "created_by", "created_at", "tenant")
    list_filter = ("branch_type", "status", "tenant")
    search_fields = ("number", "name", "description", "document__title")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "template_type", "is_active", "is_locked", "tenant")
    list_filter = ("template_type", "is_active", "is_locked", "tenant")
    search_fields = ("number", "name", "category")


@admin.register(TemplateSection)
class TemplateSectionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "template", "section_type", "order", "is_locked", "is_mandatory", "tenant")
    list_filter = ("section_type", "is_locked", "is_mandatory", "tenant")
    search_fields = ("number", "title")


@admin.register(DocumentDraft)
class DocumentDraftAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "template", "status", "author", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "title")


@admin.register(DraftCollaboration)
class DraftCollaborationAdmin(admin.ModelAdmin):
    list_display = ("number", "draft", "entry_type", "status", "author", "tenant")
    list_filter = ("entry_type", "status", "tenant")
    search_fields = ("number", "comment_text", "draft__title", "draft__number")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentApprovalWorkflow)
class DocumentApprovalWorkflowAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "document", "workflow_type", "status", "urgency", "current_stage", "total_stages", "initiator", "tenant")
    list_filter = ("workflow_type", "status", "urgency", "tenant")
    search_fields = ("number", "title", "document__title", "initiator__username")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentApprovalRequest)
class DocumentApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "workflow", "stage_number", "stage_name", "stage_type", "approver", "status", "due_date", "tenant")
    list_filter = ("stage_type", "status", "is_escalated", "tenant")
    search_fields = ("number", "workflow__title", "approver__username", "decision_comments")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentSignature)
class DocumentSignatureAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "signer_name", "signature_type", "signature_meaning", "is_valid", "signed_at", "tenant")
    list_filter = ("signature_type", "signature_meaning", "is_valid", "tenant")
    search_fields = ("number", "signer_name", "signature_token", "document__title", "document_checksum")
    readonly_fields = ("number", "signature_token", "signed_at", "created_at", "updated_at")


@admin.register(DocumentReviewComment)
class DocumentReviewCommentAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "page_number", "annotation_type", "status", "is_blocking", "author", "tenant")
    list_filter = ("annotation_type", "status", "is_blocking", "tenant")
    search_fields = ("number", "content", "selected_text", "document__title", "author__username")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentFolder)
class DocumentFolderAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "path", "parent", "department", "default_classification", "is_virtual", "is_active", "tenant")
    list_filter = ("default_classification", "is_virtual", "is_active", "tenant")
    search_fields = ("number", "name", "path", "slug")
    readonly_fields = ("number", "path", "created_at", "updated_at")


@admin.register(StorageVolume)
class StorageVolumeAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "backend_type", "tier", "utilized_percentage", "is_default", "is_active", "tenant")
    list_filter = ("backend_type", "tier", "is_default", "is_active", "tenant")
    search_fields = ("number", "name", "code", "base_path")
    readonly_fields = ("number", "utilized_percentage", "created_at", "updated_at")


@admin.register(DocumentRelationship)
class DocumentRelationshipAdmin(admin.ModelAdmin):
    list_display = ("number", "source_document", "relationship_type", "target_document", "dependency_level", "is_bidirectional", "tenant")
    list_filter = ("relationship_type", "dependency_level", "is_bidirectional", "tenant")
    search_fields = ("number", "source_document__title", "target_document__title", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentBatchImport)
class DocumentBatchImportAdmin(admin.ModelAdmin):
    list_display = ("number", "batch_name", "source_type", "target_folder", "storage_volume", "status", "processed_files_count", "tenant")
    list_filter = ("source_type", "status", "tenant")
    search_fields = ("number", "batch_name", "log_summary")
    readonly_fields = ("number", "total_files_detected", "processed_files_count", "success_files_count", "failed_files_count", "started_at", "completed_at", "created_at", "updated_at")


@admin.register(MetadataSchema)
class MetadataSchemaAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "code", "target_type", "inheritance_mode", "is_required", "is_active", "tenant")
    list_filter = ("target_type", "inheritance_mode", "is_required", "is_active", "tenant")
    search_fields = ("number", "name", "code", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentMetadataValue)
class DocumentMetadataValueAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "field_name", "data_type", "source", "validation_status", "is_overridden", "tenant")
    list_filter = ("data_type", "source", "validation_status", "is_overridden", "tenant")
    search_fields = ("number", "field_name", "field_label", "value_text", "document__title")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(TaxonomyTerm)
class TaxonomyTermAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "term_code", "category", "parent", "is_governed", "usage_count", "is_active", "tenant")
    list_filter = ("category", "is_governed", "is_active", "tenant")
    search_fields = ("number", "name", "term_code", "synonyms_json", "external_code")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentOcrJob)
class DocumentOcrJobAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "status", "ocr_engine", "confidence_score", "page_count", "applied_to_document", "tenant")
    list_filter = ("status", "ocr_engine", "applied_to_document", "tenant")
    search_fields = ("number", "document__title", "extracted_full_text", "suggested_category")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentSavedSearch)
class DocumentSavedSearchAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "owner", "visibility", "query_text", "sort_by", "is_pinned", "run_count", "is_active", "tenant")
    list_filter = ("visibility", "is_pinned", "is_active", "tenant")
    list_select_related = ("owner", "tenant")
    search_fields = ("number", "name", "description", "query_text", "owner__username")
    readonly_fields = ("number", "run_count", "last_run_at", "total_results_last_run", "created_at", "updated_at")


@admin.register(DocumentSearchAlert)
class DocumentSearchAlertAdmin(admin.ModelAdmin):
    list_display = ("number", "saved_search", "subscriber", "frequency", "delivery_channel", "status", "new_matches_count", "is_active", "tenant")
    list_filter = ("frequency", "delivery_channel", "status", "is_active", "tenant")
    list_select_related = ("saved_search", "subscriber", "tenant")
    search_fields = ("number", "saved_search__name", "subscriber__username", "notes")
    readonly_fields = ("number", "last_notified_at", "last_checked_at", "new_matches_count", "created_at", "updated_at")


@admin.register(DocumentSearchSynonym)
class DocumentSearchSynonymAdmin(admin.ModelAdmin):
    list_display = ("number", "term", "category", "is_bidirectional", "hit_count", "is_active", "tenant")
    list_filter = ("category", "is_bidirectional", "is_active", "tenant")
    list_select_related = ("created_by", "tenant")
    search_fields = ("number", "term", "synonyms")
    readonly_fields = ("number", "hit_count", "created_at", "updated_at")


@admin.register(DocumentSearchQueryLog)
class DocumentSearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ("number", "query_text", "user", "search_source", "results_count", "is_zero_result", "execution_time_ms", "created_at", "tenant")
    list_filter = ("search_source", "is_zero_result", "tenant")
    list_select_related = ("user", "tenant")
    search_fields = ("number", "query_text", "user__username")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentAccessPermission)
class DocumentAccessPermissionAdmin(admin.ModelAdmin):
    list_display = ("number", "grantee_type", "permission_level", "document", "folder", "user", "is_active", "access_count", "tenant")
    list_filter = ("grantee_type", "permission_level", "is_active", "tenant")
    list_select_related = ("document", "folder", "user", "tenant")
    search_fields = ("number", "role_name", "notes", "user__username", "document__title")
    readonly_fields = ("number", "access_count", "last_accessed_at", "created_at", "updated_at")


@admin.register(WatermarkPolicy)
class WatermarkPolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "classification", "position", "opacity_percent", "priority", "is_active", "tenant")
    list_filter = ("classification", "position", "is_active", "tenant")
    search_fields = ("number", "name", "watermark_text")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentDrmPolicy)
class DocumentDrmPolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "classification", "allow_download", "allow_print", "is_revoked", "is_active", "tenant")
    list_filter = ("classification", "allow_download", "allow_print", "is_revoked", "is_active", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("number", "revoked_at", "created_at", "updated_at")


@admin.register(DlpPolicy)
class DlpPolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "rule_type", "built_in_pattern", "action", "severity", "incident_count", "is_active", "tenant")
    list_filter = ("rule_type", "severity", "action", "is_active", "tenant")
    search_fields = ("number", "name", "description", "custom_regex")
    readonly_fields = ("number", "incident_count", "last_triggered_at", "created_at", "updated_at")


@admin.register(DlpIncident)
class DlpIncidentAdmin(admin.ModelAdmin):
    list_display = ("number", "policy", "document", "triggered_by", "severity", "action_taken", "resolution_status", "created_at", "tenant")
    list_filter = ("severity", "action_taken", "resolution_status", "tenant")
    list_select_related = ("policy", "document", "triggered_by", "tenant")
    search_fields = ("number", "snippet_redacted", "resolution_notes", "policy__name", "document__title")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "share_type", "access_level", "shared_by", "shared_with_user", "shared_with_email", "access_count", "expires_at", "is_active", "tenant")
    list_filter = ("share_type", "access_level", "is_active", "tenant")
    search_fields = ("number", "share_token", "shared_with_email", "document__title")
    readonly_fields = ("number", "share_token", "password_hash", "access_count", "last_accessed_at", "revoked_at", "created_at", "updated_at")


@admin.register(CoauthorSession)
class CoauthorSessionAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "user", "guest_name", "color_code", "status", "is_editing", "current_section", "last_heartbeat", "tenant")
    list_filter = ("status", "is_editing", "tenant")
    search_fields = ("number", "session_token", "guest_name", "current_section", "document__title")
    readonly_fields = ("number", "session_token", "joined_at", "last_heartbeat", "disconnected_at", "created_at", "updated_at")


@admin.register(DocumentTask)
class DocumentTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "document", "task_type", "priority", "status", "assigned_to", "assigned_org_unit", "due_date", "tenant")
    list_filter = ("task_type", "priority", "status", "tenant")
    search_fields = ("number", "title", "description", "document__title")
    readonly_fields = ("number", "completed_at", "created_at", "updated_at")


@admin.register(DocumentActivity)
class DocumentActivityAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "actor", "guest_name", "target_user", "action_type", "is_read", "created_at", "tenant")
    list_filter = ("action_type", "is_read", "notification_channel", "tenant")
    search_fields = ("number", "summary", "document__title")
    readonly_fields = ("number", "read_at", "created_at", "updated_at")


@admin.register(RetentionSchedule)
class RetentionScheduleAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "compliance_framework", "retention_mode", "is_permanent", "is_active", "department", "tenant")
    list_filter = ("compliance_framework", "retention_mode", "is_permanent", "is_active", "tenant")
    search_fields = ("number", "code", "name", "legal_citation", "description")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(RecordDeclaration)
class RecordDeclarationAdmin(admin.ModelAdmin):
    list_display = ("number", "document", "retention_schedule", "record_status", "is_vital_record", "is_locked", "cutoff_date", "disposition_due_date", "tenant")
    list_filter = ("record_status", "is_vital_record", "is_locked", "declaration_mode", "tenant")
    search_fields = ("number", "document__title", "document__number", "retention_schedule__code", "version_hash_snapshot")
    readonly_fields = ("number", "declaration_date", "cutoff_triggered_at", "version_hash_snapshot", "created_at", "updated_at")


@admin.register(DocumentLegalHold)
class DocumentLegalHoldAdmin(admin.ModelAdmin):
    list_display = ("number", "matter_name", "matter_number", "document", "hold_reason", "custodian", "is_active", "placed_at", "tenant")
    list_filter = ("hold_reason", "is_active", "custodian_notified", "tenant")
    search_fields = ("number", "matter_name", "matter_number", "document__title", "description")
    readonly_fields = ("number", "placed_at", "released_at", "custodian_acknowledged_at", "created_at", "updated_at")


@admin.register(DestructionCertificate)
class DestructionCertificateAdmin(admin.ModelAdmin):
    list_display = ("number", "document_title_snapshot", "disposition_type", "destruction_method", "status", "legal_hold_verified_clear", "authorized_by", "executed_by", "tenant")
    list_filter = ("disposition_type", "destruction_method", "status", "legal_hold_verified_clear", "tenant")
    search_fields = ("number", "document_title_snapshot", "document_number_snapshot", "schedule_name_snapshot", "content_verification_hash")
    readonly_fields = (
        "number",
        "status",
        "authorized_by",
        "executed_by",
        "authorized_at",
        "executed_at",
        "legal_hold_verified_clear",
        "content_verification_hash",
        "hold_verification_date",
        "created_at",
        "updated_at",
    )


@admin.register(DocumentAuditTrail)
class DocumentAuditTrailAdmin(admin.ModelAdmin):
    list_display = ("number", "action_type", "document_number_snapshot", "actor_email_snapshot", "is_success", "event_timestamp", "ip_address", "tenant")
    list_filter = ("action_type", "is_success", "tenant")
    search_fields = ("number", "document_number_snapshot", "document_title_snapshot", "actor_email_snapshot", "chain_hash")
    readonly_fields = ("number", "chain_hash", "prev_hash", "event_timestamp", "created_at", "updated_at")


@admin.register(AuditReportDefinition)
class AuditReportDefinitionAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "report_type", "is_system_preset", "status", "date_range_preset", "total_runs", "tenant")
    list_filter = ("report_type", "is_system_preset", "status", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("number", "total_runs", "last_run_at", "created_at", "updated_at")


@admin.register(DocumentSecurityAlert)
class DocumentSecurityAlertAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "alert_type", "severity", "risk_score", "status", "target_user", "tenant")
    list_filter = ("alert_type", "severity", "status", "tenant")
    search_fields = ("number", "title", "description", "triage_notes")
    readonly_fields = ("number", "detected_at", "resolved_at", "created_at", "updated_at")


@admin.register(ChainOfCustodyExport)
class ChainOfCustodyExportAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "regulatory_framework", "scope", "auditor_name", "is_portal_active", "expires_at", "tenant")
    list_filter = ("regulatory_framework", "scope", "is_portal_active", "tenant")
    search_fields = ("number", "title", "auditor_name", "auditor_email", "package_hash")
    readonly_fields = ("number", "access_token", "package_hash", "sealed_at", "created_at", "updated_at")







