"""Django admin for the procurement app."""
from django.contrib import admin

from .models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    BidScore,
    EscalationPolicy,
    EventCriterion,
    ProcurementAlert,
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionApproval,
    RequisitionTemplate,
    RequisitionTemplateLine,
    EaucBid,
    EaucInvite,
    Eauction,
    RfxAnswer,
    RfxEvent,
    RfxQuestion,
    RfxResponse,
    SourcingBid,
    SourcingEvent,
    ContractAmendment,
    ContractClause,
    ContractClauseLink,
    ContractMilestone,
    ContractSigner,
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

    @staticmethod
    def _frozen(obj):
        # Questions are a DRAFT-stage activity (is_editable): an issued event's questionnaire is
        # the frozen artifact every response is compared against, so the admin may look at it on
        # issued events but never rewrite it.
        return obj is not None and not obj.is_editable

    def get_readonly_fields(self, request, obj=None):
        if self._frozen(obj):
            return ("section", "prompt", "help_text", "answer_type", "options",
                    "weight", "is_scored", "order")
        return ("order",)

    def has_add_permission(self, request, obj=None):
        return not self._frozen(obj)

    def has_delete_permission(self, request, obj=None):
        return not self._frozen(obj)


@admin.register(RfxEvent)
class RfxEventAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "rfx_type", "status", "is_template", "response_due")
    list_filter = ("tenant", "status", "rfx_type", "is_template")
    search_fields = ("number", "title", "description")
    raw_id_fields = ("requisition", "created_by")
    # status moves only through the issue/close/cancel views so each transition lands with its
    # audit row — the admin may look, never flip the state machine (SourcingEventAdmin posture).
    readonly_fields = ("number", "status", "issued_at", "closed_at", "created_by",
                       "created_at", "updated_at")
    inlines = [RfxQuestionInline]


class RfxAnswerInline(admin.TabularInline):
    model = RfxAnswer
    extra = 0

    @staticmethod
    def _frozen(obj):
        # A disqualified response — or any response of a cancelled event — is frozen everywhere,
        # admin included: scores must never be rewritten outside the guarded views.
        return obj is not None and (obj.is_locked or obj.event.status == "cancelled")

    def get_readonly_fields(self, request, obj=None):
        return ("answer_text", "score") if self._frozen(obj) else ()

    def has_add_permission(self, request, obj=None):
        return not self._frozen(obj)

    def has_delete_permission(self, request, obj=None):
        return not self._frozen(obj)


@admin.register(RfxResponse)
class RfxResponseAdmin(admin.ModelAdmin):
    list_display = ("number", "event", "supplier", "status", "submitted_at")
    list_filter = ("tenant", "status")
    search_fields = ("number", "notes", "supplier__name")
    raw_id_fields = ("event", "supplier", "recorded_by")
    # status moves only through rfx_response_set_status's STATUS_FLOW guard — a hand-flipped
    # admin status would bypass the transition rules entirely, so the admin may look, never flip.
    readonly_fields = ("number", "status", "submitted_at", "recorded_by",
                       "created_at", "updated_at")
    inlines = [RfxAnswerInline]


# -- 6.5 Sourcing & Tendering ------------------------------------------------------------------------

class EventCriterionInline(admin.TabularInline):
    model = EventCriterion
    extra = 0
    # The <=100% weight rule is enforced by the formset on the real screen; the admin inline
    # stays a convenience window and must not pretend to re-implement it.


@admin.register(SourcingEvent)
class SourcingEventAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "event_type", "status",
                    "budget_estimate", "opens_at", "closes_at", "awarded_at")
    list_filter = ("tenant", "status", "event_type")
    search_fields = ("number", "title", "description", "rules")
    raw_id_fields = ("requisition", "currency", "created_by")
    # status and the *_at stamps move only through the view verbs so each transition lands with
    # its audit row — the admin may look, never flip the state machine.
    readonly_fields = ("number", "status", "created_by", "opened_at", "closed_at",
                       "awarded_at", "created_at", "updated_at")
    inlines = [EventCriterionInline]

    def has_add_permission(self, request):
        return False


class BidScoreInline(admin.TabularInline):
    model = BidScore
    extra = 0
    readonly_fields = ("criterion", "score", "note")


@admin.register(SourcingBid)
class SourcingBidAdmin(admin.ModelAdmin):
    list_display = ("number", "event", "supplier", "total_price",
                    "is_compliant", "status", "submitted_by", "submitted_at")
    list_select_related = ("event", "supplier", "submitted_by")
    list_filter = ("tenant", "status", "is_compliant")
    search_fields = ("number", "supplier__name", "summary", "contact_ref", "decision_note")
    raw_id_fields = ("event", "supplier", "submitted_by")
    readonly_fields = ("number", "status", "submitted_by", "submitted_at",
                       "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


# -- 6.7 E-Auction Management ---------------------------------------------------------


class EaucInviteInline(admin.TabularInline):
    model = EaucInvite
    extra = 0
    raw_id_fields = ("supplier",)


@admin.register(Eauction)
class EauctionAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "auction_type", "status", "opens_at",
                    "closes_at", "extensions_used", "awarded_supplier")
    list_filter = ("tenant", "status", "auction_type")
    search_fields = ("number", "title")
    raw_id_fields = ("currency", "requisition", "created_by", "awarded_supplier")
    # The award decision is written ONCE through the view (which validates leader-only);
    # status/extensions_used/awarded_amount/awarded_at/award_note are state-machine outputs,
    # never inputs.
    readonly_fields = ("number", "extensions_used", "status", "awarded_supplier",
                       "awarded_amount", "award_note", "awarded_at", "created_by",
                       "created_at", "updated_at")
    inlines = [EaucInviteInline]


@admin.register(EaucBid)
class EaucBidAdmin(admin.ModelAdmin):
    # READ-ONLY BID LOG: bids are append-only auction history - rewriting one would corrupt
    # rankings and savings. The log may be inspected here, never altered.
    list_display = ("number", "auction", "supplier", "amount", "placed_at", "placed_by")
    list_select_related = ("auction", "supplier", "placed_by")
    list_filter = ("tenant",)
    search_fields = ("number", "supplier__name", "note")
    readonly_fields = [f.name for f in EaucBid._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# -- 6.8 Contract Management ----------------------------------------------------------


@admin.register(ContractClause)
class ContractClauseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "version", "is_pre_approved", "is_active")
    list_filter = ("tenant", "category", "is_pre_approved", "is_active")
    search_fields = ("title", "body")
    readonly_fields = ("created_at", "updated_at")


class ContractClauseLinkInline(admin.TabularInline):
    model = ContractClauseLink
    extra = 0
    raw_id_fields = ("clause",)


@admin.register(ContractSigner)
class ContractSignerAdmin(admin.ModelAdmin):
    list_display = ("signer_name", "contract", "role", "order",
                    "signed_at", "declined_at")
    list_filter = ("tenant", "role")
    search_fields = ("signer_name", "signer_email", "contract__number")
    # WARNING: never expose `token` in any form/list � it IS the bearer credential
    # for the public sign page. Admin sees outcomes (viewed/signed/declined), not secrets.
    exclude = ("token",)
    readonly_fields = ("viewed_at", "signed_at", "declined_at", "ip_address",
                       "created_at", "updated_at")


@admin.register(ContractAmendment)
class ContractAmendmentAdmin(admin.ModelAdmin):
    list_display = ("number", "contract", "status", "requested_by", "decided_by")
    list_filter = ("tenant", "status")
    search_fields = ("number", "reason", "contract__number")
    raw_id_fields = ("contract",)
    # Decisions are written ONCE through the view under the contract row lock;
    # the decision stamps are state-machine outputs, never admin inputs.
    readonly_fields = ("number", "status", "requested_by", "decided_by",
                       "decided_at", "applied_at", "created_at", "updated_at")


@admin.register(ContractMilestone)
class ContractMilestoneAdmin(admin.ModelAdmin):
    list_display = ("number", "contract", "kind", "title", "due_date",
                    "amount", "status")
    list_filter = ("tenant", "kind", "status")
    search_fields = ("number", "title", "contract__number")
    raw_id_fields = ("contract",)
    readonly_fields = ("number", "completed_at", "completed_by",
                       "created_at", "updated_at")
