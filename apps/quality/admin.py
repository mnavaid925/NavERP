from django.contrib import admin

from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord


@admin.register(DesignProject)
class DesignProjectAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "device_name",
        "device_class",
        "regulatory_pathway",
        "current_phase",
        "status",
        "project_lead",
        "dhf_locked",
        "tenant",
    )
    list_filter = ("device_class", "regulatory_pathway", "current_phase", "status", "dhf_locked", "tenant")
    search_fields = ("number", "title", "device_name", "project_lead__username")
    list_select_related = ("tenant", "project_lead", "quality_lead", "department")


@admin.register(DesignInput)
class DesignInputAdmin(admin.ModelAdmin):
    list_display = (
        "identifier",
        "number",
        "title",
        "project",
        "input_type",
        "priority",
        "status",
        "owner",
        "tenant",
    )
    list_filter = ("input_type", "priority", "status", "tenant")
    search_fields = ("identifier", "number", "title", "project__number", "project__title")
    list_select_related = ("tenant", "project", "owner", "user_need_parent", "controlled_document")


@admin.register(DesignReview)
class DesignReviewAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "project",
        "review_stage",
        "review_date",
        "status",
        "lead_reviewer",
        "independent_reviewer",
        "action_items_resolved",
        "tenant",
    )
    list_filter = ("review_stage", "status", "action_items_resolved", "tenant")
    search_fields = ("number", "title", "project__number", "lead_reviewer__username", "independent_reviewer__username")
    list_select_related = ("tenant", "project", "lead_reviewer", "independent_reviewer", "electronic_signature")


@admin.register(DesignVerification)
class DesignVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "project",
        "primary_input",
        "activity_type",
        "test_method",
        "pass_fail_result",
        "status",
        "tenant",
    )
    list_filter = ("activity_type", "test_method", "pass_fail_result", "status", "tenant")
    search_fields = ("number", "title", "primary_input__identifier", "project__number")
    list_select_related = ("tenant", "project", "primary_input", "executed_by", "protocol_document", "report_document")


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
