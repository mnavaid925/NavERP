"""Django admin for the procurement app."""
from django.contrib import admin

from .models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    EscalationPolicy,
    ProcurementAlert,
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionApproval,
    RequisitionTemplate,
    RequisitionTemplateLine,
    RfxAnswer,
    RfxEvent,
    RfxQuestion,
    RfxResponse,
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
    WidgetPreference,
)


class RequisitionTemplateLineInline(admin.TabularInline):
    model = RequisitionTemplateLine
    extra = 0


@admin.register(RequisitionTemplate)
class RequisitionTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "org_unit", "currency", "is_active", "created_by")
    list_filter = ("tenant", "is_active")
    search_fields = ("number", "name", "description")
    raw_id_fields = ("org_unit", "currency", "created_by")
    readonly_fields = ("number", "created_by", "created_at", "updated_at")
    inlines = [RequisitionTemplateLineInline]


class RequisitionAmendmentLineInline(admin.TabularInline):
    model = RequisitionAmendmentLine
    extra = 0


@admin.register(RequisitionAmendment)
class RequisitionAmendmentAdmin(admin.ModelAdmin):
    list_display = ("number", "requisition", "amendment_type", "status",
                    "requested_by", "decided_by", "decided_at")
    list_filter = ("tenant", "status", "amendment_type")
    search_fields = ("number", "reason", "decision_note")
    raw_id_fields = ("requisition", "requested_by", "decided_by")
    # status/amendment_type are read-only here ON PURPOSE: the admin must not be able to flip a
    # pending amendment to approved without apply() running — decisions go through the view.
    readonly_fields = ("number", "amendment_type", "status", "applied_at",
                       "requested_by", "decided_by", "decided_at",
                       "created_at", "updated_at")
    inlines = [RequisitionAmendmentLineInline]


@admin.register(ProcurementAlert)
class ProcurementAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "severity", "status", "assigned_to", "due_at", "raised_at")
    list_filter = ("tenant", "status", "kind", "severity")
    search_fields = ("title", "message")
    raw_id_fields = ("assigned_to", "created_by", "acknowledged_by", "resolved_by")
    readonly_fields = ("created_by", "acknowledged_by", "acknowledged_at",
                       "resolved_by", "resolved_at", "raised_at",
                       "created_at", "updated_at")


@admin.register(WidgetPreference)
class WidgetPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "widget_key", "is_visible", "updated_at")
    list_filter = ("tenant", "widget_key", "is_visible")
    search_fields = ("user__username",)


@admin.register(ApprovalRoutingRule)
class ApprovalRoutingRuleAdmin(admin.ModelAdmin):
    list_display = ("__str__", "org_unit", "commodity", "min_total",
                    "max_total", "required_tiers", "escalation_hours", "is_active")
    list_select_related = ("org_unit",)
    list_filter = ("tenant", "is_active")
    search_fields = ("commodity", "notes", "org_unit__name")


@admin.register(RequisitionApproval)
class RequisitionApprovalAdmin(admin.ModelAdmin):
    # READ-ONLY REGISTER, enforced: signatures append through the deciding view
    # under the spine row lock - the admin may look, never write (the model
    # docstring's "unalterable log" claim is only as good as this).
    list_display = ("number", "requisition", "tier", "tier_count", "decision",
                    "approver", "via_delegation", "decided_at")
    list_select_related = ("requisition", "approver", "via_delegation")
    list_filter = ("tenant", "decision")
    search_fields = ("number", "requisition__number", "comment")
    readonly_fields = [f.name for f in RequisitionApproval._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApprovalDelegation)
class ApprovalDelegationAdmin(admin.ModelAdmin):
    list_display = ("delegator", "delegate", "scope_org_unit", "valid_from",
                    "valid_until", "is_active")
    list_select_related = ("delegator", "delegate", "scope_org_unit")
    list_filter = ("tenant", "is_active")
    search_fields = ("delegator__username", "delegate__username", "reason")
    raw_id_fields = ("delegator", "delegate", "scope_org_unit")


@admin.register(EscalationPolicy)
class EscalationPolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "idle_hours", "escalate_to", "is_active")
    list_filter = ("tenant", "is_active")
    raw_id_fields = ("escalate_to",)


# -- 6.4 Vendor Management ------------------------------------------------------------------------

@admin.register(VendorPortalAccess)
class VendorPortalAccessAdmin(admin.ModelAdmin):
    list_display = ("number", "supplier", "portal_user", "is_active",
                    "invited_by", "created_at")
    list_select_related = ("supplier", "portal_user", "invited_by")
    list_filter = ("tenant", "is_active")
    search_fields = ("number", "supplier__name", "portal_user__username", "note")
    raw_id_fields = ("supplier", "portal_user", "invited_by")


@admin.register(VendorSuspension)
class VendorSuspensionAdmin(admin.ModelAdmin):
    # The register's lifecycle columns are read-only here ON PURPOSE: requested → active/rejected
    # and the lift go through the view so decided_by/at and lifted_by/at are stamped together
    # with the audit row — the admin may look, never decide.
    list_display = ("number", "supplier", "kind", "reason_category", "status",
                    "starts_on", "ends_on", "requested_by", "decided_by", "lifted_at")
    list_select_related = ("supplier", "po_reference", "requested_by", "decided_by", "lifted_by")
    list_filter = ("tenant", "status", "kind", "reason_category")
    search_fields = ("number", "supplier__name", "reason", "decision_note", "lift_note")
    raw_id_fields = ("supplier", "po_reference", "requested_by", "decided_by", "lifted_by")
    readonly_fields = ("number", "status", "requested_by", "decision_note", "decided_by",
                       "decided_at", "lifted_by", "lifted_at", "lift_note",
                       "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(VendorInvoiceSubmission)
class VendorInvoiceSubmissionAdmin(admin.ModelAdmin):
    # Same posture as the suspension register: review decisions happen in the view so
    # reviewed_by/at land atomically; the admin is a read window over the register.
    list_display = ("number", "invoice_ref", "supplier", "purchase_order", "amount",
                    "status", "submitted_by", "reviewed_by", "reviewed_at")
    list_select_related = ("supplier", "purchase_order", "submitted_by", "reviewed_by")
    list_filter = ("tenant", "status")
    search_fields = ("number", "invoice_ref", "supplier__name", "note", "review_note")
    raw_id_fields = ("supplier", "purchase_order", "submitted_by", "reviewed_by")
    readonly_fields = ("number", "supplier", "purchase_order", "submitted_by", "status",
                       "reviewed_by", "reviewed_at", "review_note",
                       "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

# -- 6.6 RFx Management --------------------------------------------------------------


class RfxQuestionInline(admin.TabularInline):
    model = RfxQuestion
    extra = 0


@admin.register(RfxEvent)
class RfxEventAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "rfx_type", "status", "is_template", "response_due")
    list_filter = ("tenant", "status", "rfx_type", "is_template")
    search_fields = ("number", "title", "description")
    raw_id_fields = ("requisition", "created_by")
    readonly_fields = ("number", "issued_at", "closed_at", "created_by",
                       "created_at", "updated_at")
    inlines = [RfxQuestionInline]


class RfxAnswerInline(admin.TabularInline):
    model = RfxAnswer
    extra = 0


@admin.register(RfxResponse)
class RfxResponseAdmin(admin.ModelAdmin):
    list_display = ("number", "event", "supplier", "status", "submitted_at")
    list_filter = ("tenant", "status")
    search_fields = ("number", "notes", "supplier__name")
    raw_id_fields = ("event", "supplier", "recorded_by")
    readonly_fields = ("number", "submitted_at", "recorded_by", "created_at", "updated_at")
    inlines = [RfxAnswerInline]
