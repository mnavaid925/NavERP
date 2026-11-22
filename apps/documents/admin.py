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
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection
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

