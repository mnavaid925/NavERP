from django.contrib import admin

from apps.documents.models import (
    DocumentDraft,
    DocumentTemplate,
    DraftCollaboration,
    TemplateSection,
)


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "template_type", "category", "version", "is_active", "is_locked")
    search_fields = ("number", "name", "description")
    list_filter = ("template_type", "category", "is_active", "is_locked")


@admin.register(TemplateSection)
class TemplateSectionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "section_type", "template", "order", "is_locked", "is_mandatory")
    search_fields = ("number", "title", "content")
    list_filter = ("section_type", "is_locked", "is_mandatory")


@admin.register(DocumentDraft)
class DocumentDraftAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "document_type", "status", "draft_version", "author", "sync_status")
    search_fields = ("number", "title", "content")
    list_filter = ("status", "document_type", "sync_status")


@admin.register(DraftCollaboration)
class DraftCollaborationAdmin(admin.ModelAdmin):
    list_display = ("number", "draft", "entry_type", "author", "status", "created_at")
    search_fields = ("number", "comment_text", "selected_text")
    list_filter = ("entry_type", "status")
