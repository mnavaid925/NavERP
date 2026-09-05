"""Django admin for the procurement app."""
from django.contrib import admin

from .models import (
    AuditSeal,
    ComplianceScreening,
    FraudAlert,
    PolicyAttestation,
    ScreeningHit,
    SupplierRiskSignal,
    KnowledgeResource,
    ProcurementDocument,
    ProcurementDocumentRevision,
    ProcurementPolicy,
    AdvancedShipmentNotice,
    AsnLine,
    Backorder,
    DeliverySchedule,
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
    ContractMilestone,
    ContractSigner,
    CatalogItem,
    CatalogPriceTier,
    CatalogUploadBatch,
    PunchOutEndpoint,
    PurchaseOrderChange,
    PurchaseOrderChangeLine,
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    ReturnToVendor,
    ReturnToVendorLine,
    SupplierInvoice,
    SupplierInvoiceLine,
    InvoiceMatchVariance,
    InvoiceDispute,
    MaverickSpendFinding,
    SpendClassificationRule,
    SpendReport,
    SpendReportSnapshot,
    BudgetMapping,
    CostForecast,
    SupplierFeedback,
    SupplierImprovementPlan,
    SupplierKpi,
    MaterialIssue,
    MaterialIssueLine,
    ReplenishmentPolicy,
    ReplenishmentRun,
    ReplenishmentSuggestion,
    SupplierKpiScore,
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
    # the decision stamps are state-machine outputs, never admin inputs. The
    # proposal itself is equally frozen: once filed, its terms are evidence —
    # editing reason/proposed_* here would rewrite what was approved or rejected.
    readonly_fields = ("number", "status", "reason", "proposed_end_date",
                       "proposed_value", "proposed_auto_renew",
                       "proposed_notice_days", "proposed_summary",
                       "requested_by", "decided_by",
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


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "source_type", "status",
                    "supplier", "item", "base_price", "is_preferred")
    list_filter = ("tenant", "source_type", "status")
    search_fields = ("number", "name", "supplier_part_no", "category_text")
    raw_id_fields = ("item", "supplier", "contract", "uom", "currency")
    # The approval machine (submit/approve/reject/block) is written through the views;
    # admin sees the outcomes, it does not drive the workflow.
    readonly_fields = ("number", "status", "submitted_by", "submitted_at", "approved_by",
                       "approved_at", "rejection_reason", "created_by",
                       "created_at", "updated_at")


@admin.register(CatalogPriceTier)
class CatalogPriceTierAdmin(admin.ModelAdmin):
    list_display = ("catalog_item", "min_quantity", "unit_price", "discount_pct",
                    "valid_from", "valid_until", "contract", "status")
    list_filter = ("tenant", "status")
    search_fields = ("catalog_item__number", "catalog_item__name")
    raw_id_fields = ("catalog_item", "contract")
    # approve/retire/cancel move status only through the views — the admin may look,
    # never flip the state machine.
    readonly_fields = ("status", "submitted_by", "approved_by", "approved_at",
                       "created_at", "updated_at")


@admin.register(PunchOutEndpoint)
class PunchOutEndpointAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "party", "protocol", "enabled",
                    "last_session_at")
    list_filter = ("tenant", "protocol", "enabled")
    search_fields = ("number", "name", "party__name", "punchout_url")
    # WARNING: shared_secret is a credential - admin sees that it exists, never its value.
    exclude = ("shared_secret",)
    readonly_fields = ("number", "last_session_at", "created_at", "updated_at")


@admin.register(CatalogUploadBatch)
class CatalogUploadBatchAdmin(admin.ModelAdmin):
    list_display = ("number", "original_filename", "party", "status",
                    "rows_parsed", "rows_accepted", "rows_rejected")
    list_filter = ("tenant", "status")
    search_fields = ("number", "original_filename", "notes")
    raw_id_fields = ("party",)
    # Parse output is written once by validate_and_stage(); the error log is evidence.
    # Status moves only through the guarded validate/publish/reject verbs.
    readonly_fields = ("number", "status", "original_filename", "validated_by", "validated_at",
                       "rows_parsed", "rows_accepted", "rows_rejected", "error_log",
                       "created_at", "updated_at")


class PurchaseOrderChangeLineInline(admin.TabularInline):
    model = PurchaseOrderChangeLine
    extra = 0
    fields = ("action", "target_line", "item_description", "sku_hint", "uom_hint",
              "quantity", "unit_price", "tax_rate_pct")
    raw_id_fields = ("target_line",)


@admin.register(PurchaseOrderChange)
class PurchaseOrderChangeAdmin(admin.ModelAdmin):
    list_display = ("number", "purchase_order", "change_type", "status",
                    "requested_by", "decided_by", "decided_at")
    list_filter = ("tenant", "status", "change_type")
    search_fields = ("number", "reason", "purchase_order__number")
    raw_id_fields = ("purchase_order",)
    inlines = (PurchaseOrderChangeLineInline,)
    # Filing happens through the procurement views (which pin the order and enforce the
    # one-open-change rule); approve/reject/apply move state and stamps only there too —
    # the admin looks, it never decides.
    readonly_fields = ("number", "status", "requested_by", "decided_by", "decided_at",
                       "decision_note", "applied_at", "created_at", "updated_at")


class AsnLineInline(admin.TabularInline):
    model = AsnLine
    extra = 0
    fields = ("po_line", "item_description", "sku_hint", "uom_hint", "quantity_shipped",
              "package_ref", "lot_number", "serial_number", "expiry_date", "country_of_origin")
    raw_id_fields = ("po_line",)


@admin.register(AdvancedShipmentNotice)
class AdvancedShipmentNoticeAdmin(admin.ModelAdmin):
    list_display = ("number", "purchase_order", "supplier_reference", "status", "source",
                    "carrier", "tracking_number", "expected_delivery_date", "delivered_at")
    list_filter = ("tenant", "status", "source", "freight_terms")
    search_fields = ("number", "supplier_reference", "tracking_number", "bill_of_lading_ref",
                     "container_ref", "purchase_order__number")
    raw_id_fields = ("purchase_order", "carrier", "shipment")
    inlines = (AsnLineInline,)
    # status and the whole proof-of-delivery block move ONLY through the guarded verbs
    # (submit / mark_in_transit / confirm_delivery / cancel), which re-check their own
    # preconditions and refuse to re-stamp a delivery. The admin looks; it never arrives goods.
    readonly_fields = ("number", "status", "delivered_at", "arrival_condition", "pod_reference",
                       "received_signature_name", "confirmed_by", "created_by", "submitted_at",
                       "cancelled_at", "cancellation_reason", "created_at", "updated_at")


@admin.register(DeliverySchedule)
class DeliveryScheduleAdmin(admin.ModelAdmin):
    list_display = ("number", "po_line", "sequence", "scheduled_quantity", "need_by_date",
                    "promised_quantity", "promised_date", "status", "delivery_mode")
    list_filter = ("tenant", "status", "delivery_mode")
    search_fields = ("number", "po_line__item_description", "po_line__sku_hint",
                     "po_line__purchase_order__number")
    raw_id_fields = ("po_line", "ship_to", "asn")
    # status IS editable here (and on the form) by design: this ladder hangs no timestamps and
    # no who-stamps off its status, so it needs no verbs. Only the number and the audit stamps
    # are locked.
    readonly_fields = ("number", "created_by", "created_at", "updated_at")


@admin.register(Backorder)
class BackorderAdmin(admin.ModelAdmin):
    list_display = ("number", "po_line", "quantity_backordered", "reason", "status",
                    "original_promise_date", "revised_promise_date", "reschedule_count")
    list_filter = ("tenant", "status", "reason")
    search_fields = ("number", "reason_note", "notes", "po_line__item_description",
                     "po_line__purchase_order__number")
    raw_id_fields = ("po_line", "delivery_schedule", "asn")
    # reschedule / fulfil / cancel / raise_alert own status, the reschedule counter, the
    # closure stamps and the raised-alert link — each re-checking its guard inside itself.
    readonly_fields = ("number", "status", "reschedule_count", "closed_at", "closure_note",
                       "alert", "created_by", "created_at", "updated_at")


@admin.register(ReceiptTolerancePolicy)
class ReceiptTolerancePolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "item", "category", "vendor", "over_receipt_pct",
                    "under_receipt_pct", "over_receipt_qty", "allow_unlimited_over_receipt",
                    "early_receipt_days", "late_receipt_days", "action", "priority",
                    "is_active")
    list_filter = ("tenant", "action", "is_active", "allow_unlimited_over_receipt")
    search_fields = ("name", "notes", "item__sku", "item__name", "category__name",
                     "vendor__name")
    raw_id_fields = ("item", "category", "vendor")
    # A configuration master, not a workflow document: everything except the audit stamps is
    # meant to be edited. The policy is ADVISORY — it colours the console and drives the
    # exceptions board; it never blocks scm:goodsreceipt_receive.
    readonly_fields = ("created_at", "updated_at")


@admin.register(ReceiptDiscrepancy)
class ReceiptDiscrepancyAdmin(admin.ModelAdmin):
    list_display = ("number", "goods_receipt", "goods_receipt_line", "kind", "severity",
                    "quantity_affected", "remedy", "status", "vendor_notified_on",
                    "resolved_at")
    list_filter = ("tenant", "status", "kind", "severity", "remedy")
    search_fields = ("number", "description", "item_description", "sku_hint", "lot_number",
                     "serial_number", "vendor_reference", "goods_receipt__number")
    raw_id_fields = ("goods_receipt", "goods_receipt_line", "nonconformance",
                     "quarantine_order", "return_to_vendor")
    # notify_vendor / resolve / cancel own status and every stamp hanging off it, each
    # re-checking its guard inside itself so a double-submit cannot re-stamp. The admin looks;
    # it never resolves a claim. Nothing here posts stock or a journal entry.
    readonly_fields = ("number", "status", "vendor_notified_on", "resolved_at", "resolved_by",
                       "resolution_notes", "created_by", "created_at", "updated_at")


class ReturnToVendorLineInline(admin.TabularInline):
    model = ReturnToVendorLine
    extra = 0
    fields = ("goods_receipt_line", "po_line", "item_description", "sku_hint", "uom_hint",
              "quantity_returned", "lot_number", "serial_number", "condition_note")
    raw_id_fields = ("goods_receipt_line", "po_line")


@admin.register(ReturnToVendor)
class ReturnToVendorAdmin(admin.ModelAdmin):
    list_display = ("number", "vendor", "purchase_order", "goods_receipt", "reason", "remedy",
                    "status", "supplier_rma_number", "shipped_on", "credit_note_ref")
    list_filter = ("tenant", "status", "reason", "remedy")
    search_fields = ("number", "reason_note", "supplier_rma_number", "tracking_number",
                     "credit_note_ref", "notes", "vendor__name", "purchase_order__number",
                     "goods_receipt__number")
    raw_id_fields = ("vendor", "purchase_order", "goods_receipt", "discrepancy")
    inlines = (ReturnToVendorLineInline,)
    # authorize / ship / close / cancel own status and every stamp, each re-checking its own
    # guard. credit_note_ref is FREE TEXT and posts nothing: apps/accounting owns the ledger
    # (L29) and accounting.Bill has no vendor-credit kind yet, so the AP credit is recorded
    # here as a reference only. The physical stock removal is SCM's/inventory's, never this.
    readonly_fields = ("number", "status", "shipped_on", "authorized_by", "authorized_at",
                       "closed_at", "cancelled_at", "cancellation_reason", "created_by",
                       "created_at", "updated_at")


class SupplierInvoiceLineInline(admin.TabularInline):
    model = SupplierInvoiceLine
    extra = 0
    fields = ("description", "sku_hint", "uom_hint", "quantity", "unit_price", "tax_rate_pct",
              "line_total", "matched_qty", "po_line", "receipt_line", "gl_account")
    raw_id_fields = ("po_line", "receipt_line", "item", "gl_account", "tax_code")
    # line_total and matched_qty are DERIVED: save() computes the first, run_match() the second.
    readonly_fields = ("line_total", "matched_qty")


@admin.register(SupplierInvoice)
class SupplierInvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "invoice_number", "vendor", "invoice_type", "status",
                    "match_status", "invoice_date", "due_date", "discount_date", "total",
                    "currency")
    list_filter = ("tenant", "status", "match_status", "invoice_type", "source")
    search_fields = ("number", "invoice_number", "external_ref", "notes", "vendor__name",
                     "purchase_order__number", "goods_receipt__number")
    raw_id_fields = ("vendor", "purchase_order", "goods_receipt", "bill", "journal_entry",
                     "payment_term", "tax_code", "document", "source_submission", "duplicate_of")
    inlines = (SupplierInvoiceLineInline,)
    # The money columns, the three derived dates and the match verdict are all computed in
    # save()/recalc_totals()/run_match() — editing them here would desynchronise the header from
    # its lines. approve() is the ONE transition that writes the ledger (a Bill + a
    # JournalEntry), so this surface never posts; the verbs below are the only way status moves.
    readonly_fields = ("number", "invoice_number_norm", "subtotal", "tax_total", "total",
                       "amount_paid", "due_date", "discount_date", "discount_expiry_date",
                       "match_status", "match_notes", "bill", "journal_entry", "approved_by",
                       "approved_at", "created_at", "updated_at")


@admin.register(SupplierInvoiceLine)
class SupplierInvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("invoice", "description", "sku_hint", "quantity", "unit_price",
                    "tax_rate_pct", "line_total", "matched_qty", "gl_account")
    # NO tenant filter and NO tenant column: this is a PLAIN CHILD, scoped through invoice__tenant
    # the way scm.GoodsReceiptLine is scoped through goods_receipt__tenant.
    list_filter = ("invoice__tenant",)
    search_fields = ("description", "sku_hint", "invoice__number", "invoice__invoice_number",
                     "item__sku", "item__name")
    raw_id_fields = ("invoice", "po_line", "receipt_line", "item", "gl_account", "tax_code")
    readonly_fields = ("line_total", "matched_qty")


@admin.register(InvoiceMatchVariance)
class InvoiceMatchVarianceAdmin(admin.ModelAdmin):
    list_display = ("invoice", "variance_type", "basis", "expected_value", "actual_value",
                    "variance_abs", "variance_pct", "outcome", "resolution", "detected_at")
    list_filter = ("tenant", "variance_type", "basis", "outcome", "resolution")
    search_fields = ("message", "invoice__number", "invoice__invoice_number")
    raw_id_fields = ("invoice", "invoice_line", "dispute")
    # A variance is EVIDENCE written by run_match(): derived figures, the verdict and the bands
    # in force cannot be retyped without forging the audit trail. resolution is the one field AP
    # moves, and it moves through accept() and the dispute workflow, not through the admin.
    readonly_fields = ("variance_abs", "variance_pct", "outcome", "detected_at", "created_at",
                       "updated_at")


@admin.register(InvoiceDispute)
class InvoiceDisputeAdmin(admin.ModelAdmin):
    list_display = ("number", "invoice", "supplier", "reason_code", "status",
                    "disputed_amount", "assigned_to", "due_date", "resolved_at")
    list_filter = ("tenant", "status", "reason_code", "resolution")
    search_fields = ("number", "description", "resolution_note", "supplier_contact",
                     "invoice__number", "supplier__name")
    raw_id_fields = ("invoice", "invoice_line", "supplier", "assigned_to", "raised_by",
                     "credit_memo_invoice")
    # status is editable=False and moves only through the workflow verbs (await/escalate/resolve/
    # close/withdraw), each of which re-checks its own guard; supplier is denormalised from
    # invoice.vendor on save and due_date is armed once on create. The admin looks; it never
    # settles a claim.
    readonly_fields = ("number", "status", "supplier", "raised_by", "raised_at", "resolved_at",
                       "created_at", "updated_at")


# =================================================================================================
# 6.14 Spend Analytics & Reporting
# =================================================================================================
# Every derived stamp on these four models is in ``readonly_fields``. An admin surface that can
# retype a figure the code computed is a surface that can desynchronise the page from its source —
# the same defect 6.13 fixed. Nothing here posts to ``accounting.*``.

@admin.register(SpendClassificationRule)
class SpendClassificationRuleAdmin(admin.ModelAdmin):
    list_display = ("priority", "name", "match_type", "category", "applies_to", "is_active",
                    "match_count", "last_matched_at")
    list_filter = ("tenant", "match_type", "applies_to", "is_active")
    search_fields = ("name", "keyword", "notes", "category__name", "vendor__name")
    raw_id_fields = ("category", "vendor", "gl_account", "org_unit")
    # ``match_count`` / ``last_matched_at`` are stamped by the preview verb after it runs the rule
    # against real spend. Typed by hand they would claim evidence that was never gathered.
    readonly_fields = ("match_count", "last_matched_at", "created_at", "updated_at")


@admin.register(MaverickSpendFinding)
class MaverickSpendFindingAdmin(admin.ModelAdmin):
    list_display = ("number", "reason", "severity", "status", "vendor", "amount",
                    "leakage_amount", "document_date", "is_addressable")
    list_filter = ("tenant", "reason", "severity", "status", "is_addressable")
    search_fields = ("number", "detail", "resolution_note", "vendor__name", "dedupe_key")
    raw_id_fields = ("vendor", "category", "org_unit", "contract", "catalog_item",
                     "supplier_invoice", "invoice_line", "purchase_order", "resolved_by")
    # ``dedupe_key`` is what makes a re-scan idempotent — editing it would let the same fact be
    # raised twice. ``leakage_amount`` is derived in save() from amount vs benchmark, and the four
    # disposition stamps move only through acknowledge/justify/remediate/dismiss, each of which
    # re-checks its own guard. ``status`` is already ``editable=False`` on the model.
    readonly_fields = ("number", "dedupe_key", "leakage_amount", "detected_at", "resolved_by",
                       "resolved_at", "resolution_note", "created_at", "updated_at")


class SpendReportSnapshotInline(admin.TabularInline):
    model = SpendReportSnapshot
    extra = 0
    # A snapshot is a FROZEN run: it exists to be read, never edited. Every column is readonly, so
    # the inline is a window onto the report's history rather than a way to rewrite it.
    readonly_fields = ("title", "generated_at", "generated_by", "row_count", "summary", "data")
    can_delete = True


@admin.register(SpendReport)
class SpendReportAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "basis", "measure", "dimension_1", "dimension_2",
                    "date_range", "is_favorite", "is_shared", "owner", "last_run_at")
    list_filter = ("tenant", "basis", "measure", "date_range", "is_favorite", "is_shared")
    search_fields = ("number", "name", "description")
    raw_id_fields = ("vendor", "category", "org_unit", "gl_account", "owner")
    inlines = (SpendReportSnapshotInline,)
    # ``last_run_at`` is stamped by the run / snapshot POSTs only — opening a page is not a run,
    # and neither is opening this form.
    readonly_fields = ("number", "last_run_at", "created_at", "updated_at")


@admin.register(SpendReportSnapshot)
class SpendReportSnapshotAdmin(admin.ModelAdmin):
    list_display = ("title", "report", "generated_at", "generated_by", "row_count")
    list_filter = ("tenant",)
    search_fields = ("title", "report__number", "report__name")
    raw_id_fields = ("report", "generated_by")
    # EVERY field is readonly. A snapshot is created by one POST and rendered as-is forever after;
    # a hand-edited payload would be a figure with no run behind it, which is the one thing a
    # snapshot must never be.
    readonly_fields = ("report", "title", "generated_by", "generated_at", "summary", "data",
                       "row_count")


@admin.register(BudgetMapping)
class BudgetMappingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "budget", "org_unit", "project", "priority", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("budget__name", "budget__number", "org_unit__name", "project__name", "notes")
    raw_id_fields = ("budget", "org_unit", "project", "default_gl_account")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CostForecast)
class CostForecastAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "method", "budget", "horizon_months", "as_of",
                    "forecast_amount", "created_by")
    list_filter = ("tenant", "method")
    search_fields = ("number", "name", "assumptions", "budget__name")
    raw_id_fields = ("budget", "currency", "created_by")
    # The three amounts and the author are stamped ONCE by the create view from
    # compute_forecast_amounts — they are editable=False on the model and listed here again so
    # the reason is visible where the form is built. A hand-typed amount would be a projection
    # with no computation behind it.
    readonly_fields = ("number", "committed_amount", "historical_amount", "forecast_amount",
                       "created_by", "created_at", "updated_at")


# ---------------------------------------------------------------------------
# 6.19 Document & Knowledge Management
# ---------------------------------------------------------------------------


@admin.register(ProcurementDocument)
class ProcurementDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "doc_type", "status", "classification",
                    "current_revision_no", "expires_on", "owner")
    list_filter = ("tenant", "doc_type", "status", "classification", "supplier_visible")
    search_fields = ("number", "title", "description", "tags", "extracted_text")
    raw_id_fields = ("supplier", "contract", "purchase_order", "sourcing_event",
                     "owner", "checked_out_by", "created_by")
    # extracted_text is machine-written by the revision ingest, never typed. current_revision_no
    # is the pointer the approve verb moves under a row lock — editing it here by hand would
    # silently make a superseded revision the current one without any approval behind it.
    readonly_fields = ("number", "current_revision_no", "extracted_text",
                       "created_at", "updated_at")


@admin.register(ProcurementDocumentRevision)
class ProcurementDocumentRevisionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "document", "revision_no", "is_approved", "approved_by",
                    "approved_at", "file_size")
    list_filter = ("tenant", "is_approved")
    search_fields = ("document__number", "document__title", "change_note", "original_filename",
                     "sha256")
    raw_id_fields = ("document", "uploaded_by", "approved_by")
    # A revision is immutable by design: every column but change_note is editable=False on the
    # model, and the whole point of the chain is that history is never rewritten. Listing them
    # here too keeps the reason visible where the form is built.
    readonly_fields = ("revision_no", "file", "sha256", "file_size", "original_filename",
                       "extracted_text", "extraction_note", "is_approved", "approved_by",
                       "approved_at", "uploaded_by", "created_at", "updated_at")


@admin.register(ProcurementPolicy)
class ProcurementPolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "policy_type", "status", "effective_from",
                    "requires_acknowledgment", "owner")
    list_filter = ("tenant", "policy_type", "status", "requires_acknowledgment")
    search_fields = ("number", "title", "summary", "body", "tags")
    raw_id_fields = ("document", "applies_to", "previous_version", "owner")
    # published_at is stamped once by the publish verb, which also archives the predecessor in
    # the same transaction. Setting it by hand would put a policy "in force" with no supersession
    # behind it, and the library could then show two published versions of one rule.
    readonly_fields = ("number", "published_at", "created_at", "updated_at")


@admin.register(KnowledgeResource)
class KnowledgeResourceAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "resource_type", "status", "audience", "is_featured",
                    "usage_count", "last_used_at")
    list_filter = ("tenant", "resource_type", "status", "audience", "is_featured")
    search_fields = ("number", "title", "summary", "body", "tags")
    raw_id_fields = ("document", "owner")
    # usage_count is incremented atomically by the "use this resource" verb (an F() expression,
    # so concurrent presses both count). Typing a number here would invent usage that never
    # happened — and the counter is already documented as a click count, not an audit trail.
    readonly_fields = ("number", "usage_count", "last_used_at", "created_at", "updated_at")


# ---------------------------------------------------------------------------
# 6.16 Supplier Performance & Evaluation
# ---------------------------------------------------------------------------


@admin.register(SupplierKpi)
class SupplierKpiAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "source", "direction", "weight",
                    "scoring_method", "maps_to_dimension", "applies_to", "is_active")
    list_filter = ("tenant", "category", "source", "direction", "scoring_method",
                   "maps_to_dimension", "applies_to", "is_active")
    search_fields = ("code", "name", "number", "description", "notes")
    raw_id_fields = ("owner",)
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(SupplierKpiScore)
class SupplierKpiScoreAdmin(admin.ModelAdmin):
    list_display = ("__str__", "scorecard", "kpi", "measured_value", "score", "band",
                    "weight_applied", "computed_at")
    list_filter = ("tenant", "band", "kpi_category", "source_at_time")
    search_fields = ("kpi_name", "kpi__code", "kpi__name", "scorecard__number",
                     "scorecard__party__name", "comment")
    raw_id_fields = ("scorecard", "kpi", "computed_by")
    # Everything but measured_value / score / band / weight / comment is FROZEN at generation —
    # the model already declares those columns editable=False so they never reach a form here.
    # Listing the derivation columns explicitly keeps the reason visible where the form is
    # built: a line's history is what makes a closed period readable later, and hand-editing
    # target_at_time or breakdown would rewrite the evidence behind a figure somebody acted on.
    readonly_fields = ("target_at_time", "direction_at_time", "source_at_time", "unit_at_time",
                       "kpi_name", "kpi_category", "breakdown", "respondent_count",
                       "computed_at", "computed_by", "created_at", "updated_at")


@admin.register(SupplierFeedback)
class SupplierFeedbackAdmin(admin.ModelAdmin):
    list_display = ("number", "supplier", "respondent_kind", "respondent_function", "rating",
                    "importance", "status", "period_end", "due_date")
    list_filter = ("tenant", "status", "respondent_kind", "respondent_function", "rating")
    search_fields = ("number", "supplier__name", "respondent_name", "comment")
    raw_id_fields = ("supplier", "scorecard", "kpi", "respondent", "requested_by")
    # requested_at / submitted_at are stamped by the create path and the submit verb; both are
    # editable=False on the model. Setting submitted_at by hand would date a response that was
    # never given, and the survey aggregate reads these rows as evidence.
    readonly_fields = ("number", "requested_at", "submitted_at", "created_at", "updated_at")


@admin.register(SupplierImprovementPlan)
class SupplierImprovementPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "supplier", "severity", "status", "outcome",
                    "start_date", "target_close_date", "next_review_date", "owner")
    list_filter = ("tenant", "status", "severity", "outcome")
    search_fields = ("number", "title", "supplier__name", "finding", "root_cause",
                     "corrective_actions", "supplier_owner_name")
    raw_id_fields = ("supplier", "scorecard", "kpi", "owner", "escalated_suspension",
                     "acknowledged_by", "verified_by")
    # The close/acknowledge verbs own these: actual_close_date, the two acknowledgement stamps,
    # the two verification stamps and closure_note are all editable=False on the model. Typing
    # a closure by hand would sign off a plan nobody actually verified — and `outcome` stays
    # writable here only because it is a plain choice column the close verb sets from its POST.
    readonly_fields = ("number", "actual_close_date", "acknowledged_by", "acknowledged_at",
                       "verified_by", "verified_at", "closure_note", "created_at", "updated_at")


# ---------------------------------------------------------------------------
# 6.18 Inventory & Warehouse Integration
# ---------------------------------------------------------------------------

@admin.register(ReplenishmentPolicy)
class ReplenishmentPolicyAdmin(admin.ModelAdmin):
    list_display = ("item", "location", "preferred_vendor", "source_method", "trigger_mode",
                    "target_level", "include_on_order", "is_active", "tenant")
    list_filter = ("tenant", "is_active", "source_method", "trigger_mode", "include_on_order")
    search_fields = ("item__sku", "item__name", "location__code", "location__name",
                     "preferred_vendor__name", "notes")
    raw_id_fields = ("item", "location", "preferred_vendor", "default_org_unit",
                     "default_budget", "default_gl_account")
    readonly_fields = ("created_at", "updated_at")


class ReplenishmentSuggestionInline(admin.TabularInline):
    model = ReplenishmentSuggestion
    extra = 0
    raw_id_fields = ("item", "location", "reorder_rule", "policy", "vendor", "requisition")
    # Every quantity here is a SNAPSHOT taken at generate() time — editable=False on the model so
    # the row still explains the decision after stock has moved on. Listing them here would offer
    # an edit the model refuses.
    readonly_fields = ("on_hand_qty", "allocated_qty", "on_order_qty", "open_requisition_qty",
                       "available_qty", "reorder_point_snapshot", "target_level_snapshot",
                       "raw_suggested_qty", "suggested_qty", "unit_cost", "lead_time_days",
                       "requisition")


@admin.register(ReplenishmentRun)
class ReplenishmentRunAdmin(admin.ModelAdmin):
    list_display = ("number", "run_date", "location", "trigger", "status", "abc_class_filter",
                    "generated_by", "tenant")
    list_filter = ("tenant", "status", "trigger", "abc_class_filter")
    search_fields = ("number", "notes", "location__code", "location__name")
    raw_id_fields = ("location", "generated_by")
    inlines = [ReplenishmentSuggestionInline]
    readonly_fields = ("number", "generated_at", "released_at", "generated_by",
                       "created_at", "updated_at")


class MaterialIssueLineInline(admin.TabularInline):
    model = MaterialIssueLine
    extra = 0
    raw_id_fields = ("item", "lot_serial", "gl_account")
    # unit_cost is an Item.average_cost snapshot stamped in save(), not an input.
    readonly_fields = ("unit_cost",)


@admin.register(MaterialIssue)
class MaterialIssueAdmin(admin.ModelAdmin):
    list_display = ("number", "issue_date", "movement_type", "purpose", "location", "org_unit",
                    "status", "adjustment", "tenant")
    list_filter = ("tenant", "status", "movement_type", "purpose")
    search_fields = ("number", "reference", "notes", "location__code", "location__name",
                     "org_unit__name")
    raw_id_fields = ("location", "org_unit", "gl_account", "requested_by", "issued_by",
                     "adjustment", "reservation")
    inlines = [MaterialIssueLineInline]
    # `adjustment` is provenance written by post() — the DRAFT scm.StockAdjustment this document
    # minted. Pointing it at another adjustment by hand would forge the audit trail between a
    # procurement document and the stock ledger.
    readonly_fields = ("number", "adjustment", "issued_by", "posted_at", "cancelled_at",
                       "created_at", "updated_at")


# ---------------------------------------------------------------------------------------------
# 6.17 Risk & Compliance Management
#
# Every derived, workflow-set or digest column below is readonly here for the same reason it is
# absent from the corresponding ModelForm (L20/L22): a status, a disposition, a band, a counter
# and a hash are all things the system decides, and an admin text box that lets a human retype
# one is a quieter version of the bug the forms were written to avoid.
# ---------------------------------------------------------------------------------------------


class ScreeningHitInline(admin.TabularInline):
    model = ScreeningHit
    extra = 0
    # The disposition is a recorded adjudication with a mandatory note; it moves through the
    # dispose verb, which audits it, never through an inline edit.
    readonly_fields = ("disposition", "disposition_note", "disposed_by", "disposed_at",
                       "created_at")


@admin.register(ComplianceScreening)
class ComplianceScreeningAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "list_source", "checkpoint", "screened_on", "result",
                    "status", "hit_count", "open_hit_count", "next_rescreen_on", "tenant")
    list_filter = ("tenant", "status", "result", "list_source", "checkpoint", "method")
    search_fields = ("number", "party__name", "reference", "notes", "threshold_rationale")
    raw_id_fields = ("party", "evidence", "suspension", "screened_by", "decided_by")
    inlines = [ScreeningHitInline]
    # hit_count/open_hit_count are recomputed by recount_hits() from the live rows; status and the
    # decision stamps move only through the clear/escalate/block verbs, each of which writes an
    # audit row. `suspension` is provenance - the 6.4 block this screening caused.
    readonly_fields = ("number", "status", "hit_count", "open_hit_count", "suspension",
                       "screened_by", "decided_by", "decided_at", "decision_note",
                       "created_at", "updated_at")


@admin.register(ScreeningHit)
class ScreeningHitAdmin(admin.ModelAdmin):
    list_display = ("matched_name", "screening", "matched_list", "match_score", "match_type",
                    "disposition", "disposed_at")
    list_filter = ("disposition", "matched_list", "match_type")
    search_fields = ("matched_name", "entry_reference", "program", "country", "remarks",
                     "screening__number")
    raw_id_fields = ("screening", "disposed_by")
    readonly_fields = ("disposition", "disposition_note", "disposed_by", "disposed_at",
                       "created_at")


@admin.register(SupplierRiskSignal)
class SupplierRiskSignalAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "provider", "metric", "observed_on", "value", "band",
                    "trend", "review_status", "next_refresh_on", "tenant")
    list_filter = ("tenant", "band", "trend", "review_status", "provider", "metric")
    search_fields = ("number", "party__name", "source_ref", "notes")
    raw_id_fields = ("party", "evidence", "captured_by", "reviewed_by", "alert")
    # The whole model exists to say what a number MEANS on its own scale - FHR 100 is healthy,
    # D&B SER 9 is dangerous. scale_min/scale_max/higher_is_better/risk_position/band/trend and
    # previous_value are all derived in save() from METRIC_SCALES; a hand-edited band would be a
    # figure with no provenance sitting next to ones that have it.
    readonly_fields = ("number", "scale_min", "scale_max", "higher_is_better", "risk_position",
                       "band", "previous_value", "trend", "review_status", "review_note",
                       "reviewed_by", "reviewed_at", "captured_by", "alert",
                       "created_at", "updated_at")


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = ("number", "rule", "severity", "status", "vendor", "document_date", "amount",
                    "assigned_to", "detected_at", "tenant")
    list_filter = ("tenant", "rule", "severity", "status")
    search_fields = ("number", "detail", "matched_on", "vendor__name")
    raw_id_fields = ("vendor", "related_party", "requisition", "purchase_order",
                     "supplier_invoice", "approval", "screening", "assigned_to", "resolved_by",
                     "suspension")
    # dedupe_key is what makes scan() idempotent - editing it would let the same finding be
    # raised twice, which is the one failure a detector must not have.
    readonly_fields = ("number", "dedupe_key", "status", "detected_at", "resolution_note",
                       "resolved_by", "resolved_at", "suspension", "created_at", "updated_at")


@admin.register(PolicyAttestation)
class PolicyAttestationAdmin(admin.ModelAdmin):
    list_display = ("policy", "user", "status", "due_on", "acknowledged_at", "tenant")
    list_filter = ("tenant", "status")
    search_fields = ("policy__number", "policy__title", "user__username", "user__first_name",
                     "user__last_name", "acknowledgement_note", "exempt_reason")
    raw_id_fields = ("policy", "user", "alert")
    # A sign-off is evidence that a NAMED person acknowledged a policy. Letting an administrator
    # stamp acknowledged_at from here would forge exactly the record the ledger exists to hold -
    # the same reason attestation_sign is owner-only and refuses a tenant admin.
    readonly_fields = ("status", "acknowledged_at", "acknowledgement_note", "exempt_reason",
                       "exempted_by", "exempted_at", "alert", "created_at", "updated_at")


@admin.register(AuditSeal)
class AuditSealAdmin(admin.ModelAdmin):
    list_display = ("number", "sealed_at", "from_log_id", "to_log_id", "row_count",
                    "last_verify_ok", "last_verified_at", "sealed_by", "tenant")
    list_filter = ("tenant", "last_verify_ok", "algorithm")
    search_fields = ("number", "note", "chain_digest", "digest")
    raw_id_fields = ("sealed_by", "prev_seal")
    # EVERY column except the note is a computed digest, a derived boundary or a system stamp.
    # A seal whose range or digest can be retyped proves nothing whatsoever, so the admin gets no
    # add and no delete either - the same reason there is no auditseal_edit/auditseal_delete route.
    # row_fingerprints in particular is the per-row evidence verify() uses to name WHICH log id
    # broke the chain; editing it would let a tamperer relocate the blame.
    readonly_fields = ("number", "sealed_at", "from_log_id", "to_log_id", "period_start",
                       "period_end", "row_count", "digest", "prev_seal", "prev_digest",
                       "chain_digest", "algorithm", "row_fingerprints", "sealed_by",
                       "last_verified_at", "last_verify_ok", "last_verify_detail",
                       "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
