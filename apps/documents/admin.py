from django.contrib import admin

from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
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
