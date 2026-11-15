from django.contrib import admin

from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord


@admin.register(ControlledDocument)
class ControlledDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "document_type",
        "revision",
        "lifecycle_state",
        "is_latest_revision",
        "department",
        "owner",
        "effective_date",
        "tenant",
    )
    list_filter = ("lifecycle_state", "document_type", "is_latest_revision", "classification", "tenant")
    search_fields = ("number", "title", "revision", "owner__username", "department__name")
    list_select_related = ("tenant", "owner", "department", "supersedes", "superseded_by")


@admin.register(DocumentChangeOrder)
class DocumentChangeOrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "change_type",
        "priority",
        "document",
        "target_revision",
        "status",
        "ccb_decision",
        "requested_by",
        "tenant",
    )
    list_filter = ("status", "change_type", "priority", "ccb_decision", "tenant")
    search_fields = ("number", "title", "document__number", "document__title", "requested_by__username")
    list_select_related = ("tenant", "document", "requested_by", "ccb_decision_by")


@admin.register(ElectronicSignatureRecord)
class ElectronicSignatureRecordAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "document",
        "document_revision",
        "signer_name",
        "signature_meaning",
        "signature_timestamp",
        "tenant",
    )
    list_filter = ("signature_meaning", "tenant")
    search_fields = ("number", "signer_name", "signer__username", "document__number", "document__title")
    list_select_related = ("tenant", "document", "change_order", "signer")
    readonly_fields = ("signature_timestamp", "signature_hash", "ip_address")


@admin.register(DocumentAcknowledgment)
class DocumentAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "document",
        "document_revision",
        "user",
        "due_date",
        "status",
        "acknowledged_at",
        "tenant",
    )
    list_filter = ("status", "tenant")
    search_fields = ("number", "user__username", "document__number", "document__title")
    list_select_related = ("tenant", "document", "user", "employee", "signature_record")
