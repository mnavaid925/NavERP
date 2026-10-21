from django.contrib import admin

from .models import (
    AccountClassification,
    AccountPlan,
    AccountStakeholder,
    CompetitorProfile,
    ForecastAdjustment,
    ForecastPeriod,
    ForecastScenario,
    ForecastSubmission,
    LeadNurtureEnrollment,
    LeadQualification,
    LeadRoutingRule,
    LeadScoreEvent,
    OpportunityCompetitor,
    OpportunityOutcome,
    OpportunityPipelinePlacement,
    OpportunityTeamMember,
    PartyEnrichmentEvent,
    Pipeline,
    PipelineStage,
    WinLossReason,
    CPQQuote,
    CPQQuoteLine,
    ProductBundleOption,
    QuoteApprovalRule,
    # 8.6 Order Management
    OrderValidationRule,
    OrderHold,
    OrderAmendment,
    OrderAmendmentLine,
    RevenueSchedule,
    PerformanceObligation,
    # 8.7 Territory & Quota Management
    TerritoryRule,
    AccountTerritoryAssignment,
    TerritoryMember,
    QuotaPlan,
    # 8.8 Sales Activity & Task Management
    ActivityType,
    ActivityLog,
    TaskTemplate,
    TaskTemplateStep,
    SalesPlanCycle,
    ActivityGoal,
    # 8.9 Sales Enablement
    EnablementContent,
    SalesPlaybook,
    SalesCertification,
    CoachingScorecard,
    # 8.10 Incentive Compensation Management
    CommissionPlan,
    CommissionEarning,
    CommissionStatement,
    CommissionAdjustment,
    # 8.11 Customer Success & Account Management
    CustomerHealthScore,
    CustomerRenewal,
    CustomerOnboarding,
    CustomerBusinessReview,
    # 8.13 Marketing Alignment & Attribution
    AttributionTouchpoint,
    CampaignAttribution,
    MqlHandoff,
    ContentEngagement,
    MarketingEvent,
    EventRegistration,
    # 8.12 Sales Analytics & Intelligence
    WinLossDebrief,
    StageVelocityAnalysis,
    FunnelConversionRecord,
    RepPerformanceScorecard,
    # 8.14 Partner & Channel Management
    PartnerProfile,
    DealRegistration,
    JointAccountPlan,
    ChannelConflict,
)






@admin.register(LeadScoreEvent)
class LeadScoreEventAdmin(admin.ModelAdmin):
    list_display = ("lead", "event_type", "score_delta", "source_kind", "occurred_at", "recorded_by", "tenant")
    list_filter = ("signal_category", "event_type", "source_kind", "tenant")
    search_fields = ("lead__number", "lead__name", "source_ref", "reason")
    readonly_fields = ("tenant", "lead", "signal_category", "event_type", "score_delta", "source_kind", "source_ref", "reason", "effective_until", "idempotency_key", "corrects_event", "occurred_at", "recorded_by", "created_at")
    list_select_related = ("lead", "recorded_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LeadQualification)
class LeadQualificationAdmin(admin.ModelAdmin):
    list_display = ("lead", "framework", "status", "next_review_on", "assessed_by", "tenant")
    list_filter = ("framework", "status", "tenant")
    search_fields = ("lead__number", "lead__name", "notes")
    readonly_fields = ("tenant", "status", "disqualification_reason", "assessed_by", "assessed_at", "created_at", "updated_at")
    list_select_related = ("lead", "assessed_by")
    raw_id_fields = ("lead",)
    assessment_fields = (
        "lead", "framework", "country_code", "region", "city", "industry", "employee_count",
        "seniority", "budget_status", "budget_amount", "budget_currency", "authority_level",
        "need_summary", "expected_purchase_on", "economic_buyer", "decision_criteria",
        "decision_process", "technical_requirements", "pain_points", "success_metrics",
        "next_review_on", "notes",
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj is not None and obj.status in {"qualified", "disqualified", "archived"}:
            fields.extend(self.assessment_fields)
        return tuple(dict.fromkeys(fields))


@admin.register(LeadRoutingRule)
class LeadRoutingRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "assignment_mode", "priority", "is_active", "last_assigned_owner", "tenant")
    list_filter = ("assignment_mode", "match_mode", "is_active", "tenant")
    search_fields = ("name", "description")
    readonly_fields = ("tenant", "cursor", "last_assigned_owner", "last_assigned_at", "created_at", "updated_at")
    list_select_related = ("default_owner", "territory", "fallback_owner", "last_assigned_owner")
    filter_horizontal = ("eligible_owners",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if db_field.name in {"default_owner", "fallback_owner"} and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        if db_field.name == "territory" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if db_field.name == "eligible_owners" and tenant is not None:
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(tenant=tenant, is_active=True)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(LeadNurtureEnrollment)
class LeadNurtureEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("number", "lead", "email_campaign", "status", "next_touch_at", "owner", "tenant")
    list_filter = ("status", "trigger_kind", "tenant")
    search_fields = ("number", "lead__number", "lead__name", "email_campaign__name")
    readonly_fields = ("tenant", "number", "status", "score_at_enrollment", "started_at", "last_touch_at", "touch_count", "completed_at", "created_at", "updated_at")
    list_select_related = ("lead", "email_campaign", "owner", "consent_purpose")
    raw_id_fields = ("lead", "email_campaign", "consent_purpose")
    identity_fields = ("lead", "email_campaign", "trigger_kind", "consent_purpose", "consent_evidence", "owner", "notes")

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj is not None and obj.status != "pending":
            fields.extend(self.identity_fields)
        return tuple(dict.fromkeys(fields))


@admin.register(PartyEnrichmentEvent)
class PartyEnrichmentEventAdmin(admin.ModelAdmin):
    list_display = ("party", "kind", "source_kind", "status", "occurred_at", "requested_by", "tenant")
    list_filter = ("kind", "source_kind", "status", "tenant")
    search_fields = ("party__name", "source_name", "source_reference", "error_code", "error_summary")
    readonly_fields = ("tenant", "party", "kind", "source_kind", "source_name", "source_reference", "status", "match_confidence", "changes", "legal_basis_purpose", "requested_by", "reviewed_by", "occurred_at", "applied_at", "idempotency_key", "error_code", "error_summary", "created_at")
    list_select_related = ("party", "legal_basis_purpose", "requested_by", "reviewed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccountStakeholder)
class AccountStakeholderAdmin(admin.ModelAdmin):
    list_display = ("account", "contact", "role", "influence", "attitude", "status", "tenant")
    list_filter = ("role", "influence", "attitude", "relationship_strength", "status", "tenant")
    search_fields = ("account__name", "contact__name", "notes")
    list_select_related = ("account", "contact")
    raw_id_fields = ("account", "contact")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if request.tenant is not None and db_field.name in {"account", "contact"}:
            kind = "organization" if db_field.name == "account" else "person"
            ids = list(db_field.remote_field.model._default_manager.filter(
                tenant=request.tenant, kind=kind
            ).order_by("name").values_list("pk", flat=True)[:500])
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(pk__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(AccountClassification)
class AccountClassificationAdmin(admin.ModelAdmin):
    list_display = ("account", "tier", "lifecycle_stage", "strategic_priority", "review_due_on", "classified_by", "tenant")
    list_filter = ("tier", "lifecycle_stage", "strategic_priority", "revenue_potential", "wallet_category", "tenant")
    search_fields = ("account__name", "rationale")
    readonly_fields = ("tenant", "classified_by", "created_at", "updated_at")
    list_select_related = ("account", "classified_by")
    raw_id_fields = ("account",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if request.tenant is not None and db_field.name == "account":
            ids = list(db_field.remote_field.model._default_manager.filter(
                tenant=request.tenant, kind="organization"
            ).order_by("name").values_list("pk", flat=True)[:500])
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(pk__in=ids)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(AccountPlan)
class AccountPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "title", "status", "owner", "period_end", "next_review_on", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "account__name", "title", "objectives", "strategy")
    readonly_fields = ("tenant", "number", "status", "created_at", "updated_at")
    list_select_related = ("account", "owner")
    raw_id_fields = ("account",)
    filter_horizontal = ("related_opportunities",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if request.tenant is not None and db_field.name == "account":
            ids = list(db_field.remote_field.model._default_manager.filter(
                tenant=request.tenant, kind="organization"
            ).order_by("name").values_list("pk", flat=True)[:500])
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(pk__in=ids)

        if request.tenant is not None and db_field.name == "owner":
            ids = list(db_field.remote_field.model._default_manager.filter(
                tenant=request.tenant, is_active=True
            ).order_by("username").values_list("pk", flat=True)[:500])
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(pk__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
        if tenant is not None and db_field.name == "related_opportunities":
            queryset = db_field.remote_field.model._default_manager.filter(tenant=tenant)
            account_id = request.POST.get("account", "")
            if not account_id and request.resolver_match:
                object_id = request.resolver_match.kwargs.get("object_id")
                if object_id and str(object_id).isdecimal():
                    current = self.model.objects.filter(pk=object_id, tenant=tenant).only("account_id").first()
                    account_id = str(current.account_id) if current is not None else ""
            if account_id and account_id.isdecimal():
                queryset = queryset.filter(account_id=account_id)
            ids = list(queryset.order_by("-created_at").values_list("pk", flat=True)[:500])
            kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(pk__in=ids)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.status != "draft":
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "is_default", "is_active", "tenant")
    list_filter = ("is_default", "is_active", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ("pipeline", "sequence", "name", "stage_kind", "crm_stage_key", "probability", "is_active", "tenant")
    list_filter = ("stage_kind", "crm_stage_key", "forecast_category", "is_active", "tenant")
    search_fields = ("name", "code", "pipeline__name")
    readonly_fields = ("tenant", "created_at", "updated_at")
    list_select_related = ("pipeline", "tenant")
    raw_id_fields = ("pipeline",)


@admin.register(OpportunityPipelinePlacement)
class OpportunityPipelinePlacementAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "pipeline", "current_stage", "probability_override", "stage_entered_at", "tenant")
    list_filter = ("pipeline", "current_stage", "tenant")
    search_fields = ("opportunity__number", "opportunity__name", "pipeline__name")
    readonly_fields = ("tenant", "stage_entered_at", "created_at", "updated_at")
    list_select_related = ("opportunity", "pipeline", "current_stage", "tenant")
    raw_id_fields = ("opportunity", "pipeline", "current_stage")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OpportunityTeamMember)
class OpportunityTeamMemberAdmin(admin.ModelAdmin):
    list_display = ("number", "opportunity", "user", "role", "is_active", "tenant")
    list_filter = ("role", "is_active", "tenant")
    search_fields = ("number", "opportunity__number", "opportunity__name", "user__username")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("opportunity", "user", "org_unit", "tenant")
    raw_id_fields = ("opportunity", "user", "org_unit")


@admin.register(CompetitorProfile)
class CompetitorProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "website_url", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "party__name", "aliases", "market_positioning")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("party", "tenant")
    raw_id_fields = ("party",)


@admin.register(OpportunityCompetitor)
class OpportunityCompetitorAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "competitor_profile", "relationship", "is_primary", "tenant")
    list_filter = ("relationship", "is_primary", "tenant")
    search_fields = ("opportunity__name", "competitor_profile__party__name")
    readonly_fields = ("tenant", "created_at", "updated_at")
    list_select_related = ("opportunity", "competitor_profile__party", "tenant")
    raw_id_fields = ("opportunity", "competitor_profile")


@admin.register(WinLossReason)
class WinLossReasonAdmin(admin.ModelAdmin):
    list_display = ("number", "code", "name", "result", "category", "is_active", "tenant")
    list_filter = ("result", "category", "is_active", "tenant")
    search_fields = ("number", "code", "name", "description")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")


@admin.register(OpportunityOutcome)
class OpportunityOutcomeAdmin(admin.ModelAdmin):
    list_display = ("number", "opportunity", "result", "reason", "closed_at", "recorded_by", "tenant")
    list_filter = ("result", "reason", "tenant")
    search_fields = ("number", "opportunity__number", "opportunity__name", "notes")
    readonly_fields = ("tenant", "number", "opportunity", "result", "reason", "competitor_link", "notes", "closed_at", "recorded_by", "created_at", "updated_at")
    list_select_related = ("opportunity", "reason", "competitor_link", "recorded_by", "tenant")
    raw_id_fields = ("opportunity", "reason", "competitor_link", "recorded_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------- 8.4 Sales Forecasting
# Django admin is a SECOND WRITER. Every workflow- and service-controlled field below is
# readonly, or the append-only / snapshot / isolation rulings are bypassable from /admin/.


@admin.register(ForecastPeriod)
class ForecastPeriodAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "period_type", "period_year", "period_number", "rollup_dimension", "is_active", "is_locked", "tenant")
    list_filter = ("period_type", "rollup_dimension", "is_active", "is_locked", "tenant")
    search_fields = ("number", "name")
    # start_date / end_date are computed in clean()/save() (editable=False) and the number
    # is minted by TenantNumbered.save(); none of them may be typed in.
    readonly_fields = ("tenant", "number", "start_date", "end_date", "created_at", "updated_at")
    list_select_related = ("reporting_currency", "tenant")
    raw_id_fields = ("reporting_currency",)

    def get_readonly_fields(self, request, obj=None):
        # A locked period's shape is frozen; only is_active / fx_rate_source_date may move.
        fields = list(self.readonly_fields)
        if obj is not None and obj.is_locked:
            fields.extend(["name", "period_type", "period_year", "period_number", "rollup_dimension", "is_locked"])
        return tuple(dict.fromkeys(fields))


@admin.register(ForecastSubmission)
class ForecastSubmissionAdmin(admin.ModelAdmin):
    list_display = ("number", "period", "owner", "org_unit", "territory", "status", "commit_amount", "weighted_amount", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "owner__username", "owner__first_name", "owner__last_name", "review_note", "notes")
    # status is the workflow, the three *_amount snapshots are service-written, and the whole
    # ai_* block is storage + explanation only. Readonly here so none of them is editable.
    readonly_fields = (
        "tenant", "number", "status",
        "weighted_amount", "quota_amount", "actual_amount",
        "submitted_at", "reviewed_at",
        "ai_predicted_pipeline", "ai_predicted_best_case", "ai_predicted_commit",
        "ai_confidence_pct", "ai_model_name", "ai_model_version",
        "ai_generated_at", "ai_explanation",
        "created_at", "updated_at",
    )
    list_select_related = ("period", "owner", "org_unit", "territory", "pipeline", "quota_ref", "tenant")
    raw_id_fields = ("period", "owner", "org_unit", "territory", "pipeline", "quota_ref", "submitted_by", "reviewed_by")


@admin.register(ForecastAdjustment)
class ForecastAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("number", "submission", "adjustment_kind", "target_field", "reason_code", "is_reverted", "created_by", "tenant")
    list_filter = ("adjustment_kind", "target_field", "reason_code", "is_reverted", "tenant")
    search_fields = ("number", "submission__number", "note", "revert_reason")
    # original_value / original_category are the system snapshot and is_reverted / reverted_at
    # are the Reset action's; editing any of them from /admin/ would forge the audit trail.
    readonly_fields = (
        "tenant", "number", "adjustment_kind",
        "original_value", "original_category",
        "is_reverted", "reverted_at", "revert_reason",
        "created_at", "updated_at",
    )
    list_select_related = ("submission", "opportunity", "placement", "created_by", "tenant")
    raw_id_fields = ("submission", "opportunity", "placement", "created_by")

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj is not None and obj.is_reverted:
            fields.extend(["target_field", "adjusted_value", "adjusted_category", "reason_code"])
        return tuple(dict.fromkeys(fields))


@admin.register(ForecastScenario)
class ForecastScenarioAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "period", "owner", "scenario_type", "is_baseline", "is_selected", "tenant")
    list_filter = ("scenario_type", "is_baseline", "is_selected", "tenant")
    search_fields = ("number", "name", "assumption_notes")
    # is_selected is set by the select action and the projected_* figures by the apply action.
    readonly_fields = (
        "tenant", "number", "is_selected",
        "projected_commit_amount", "projected_total_amount",
        "created_at", "updated_at",
    )
    list_select_related = ("period", "owner", "tenant")
    raw_id_fields = ("period", "owner")


# ---------------------------------------------------------------- 8.5 Quote & Proposal Management (CPQ)


@admin.register(CPQQuote)
class CPQQuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "revision_number", "account", "opportunity", "status", "approval_status", "total", "margin_pct", "is_primary", "tenant")
    list_filter = ("status", "approval_status", "is_primary", "tenant")
    search_fields = ("number", "name", "quote_group_id", "account__name", "opportunity__name")
    readonly_fields = (
        "tenant", "number", "quote_group_id", "revision_number",
        "subtotal", "discount_total", "tax_total", "total",
        "cost_total", "margin_total", "margin_pct",
        "proposal_rendered_content", "signing_token",
        "signer_name", "signer_title", "signer_email", "signed_at", "signature_data",
        "converted_order", "created_at", "updated_at",
    )
    list_select_related = ("account", "contact", "opportunity", "currency", "owner", "approval_rule", "tenant")
    raw_id_fields = ("account", "contact", "opportunity", "price_book", "proposal_template", "approval_rule", "approved_by", "converted_order", "crm_quote", "owner")


@admin.register(CPQQuoteLine)
class CPQQuoteLineAdmin(admin.ModelAdmin):
    list_display = ("quote", "sequence", "description", "line_type", "quantity", "unit_price", "discount_pct", "line_total", "margin_pct", "is_optional", "is_selected", "tenant")
    list_filter = ("line_type", "is_optional", "is_selected", "tenant")
    search_fields = ("quote__number", "description", "product__name")
    readonly_fields = ("tenant", "line_subtotal", "line_tax", "line_total", "line_cost", "line_margin", "margin_pct", "created_at", "updated_at")
    list_select_related = ("quote", "product", "item", "uom", "parent_line", "tenant")
    raw_id_fields = ("quote", "parent_line", "product", "item")


@admin.register(ProductBundleOption)
class ProductBundleOptionAdmin(admin.ModelAdmin):
    list_display = ("number", "bundle_product", "component_product", "option_group", "default_quantity", "is_required", "compatibility_rule", "is_active", "tenant")
    list_filter = ("option_group", "is_required", "is_default", "compatibility_rule", "is_active", "tenant")
    search_fields = ("number", "name", "bundle_product__name", "component_product__name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("bundle_product", "component_product", "component_item", "depends_on_product", "tenant")
    raw_id_fields = ("bundle_product", "component_product", "component_item", "depends_on_product")


@admin.register(QuoteApprovalRule)
class QuoteApprovalRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "rule_type", "discount_threshold_pct", "min_margin_pct", "amount_threshold", "approver_role", "priority", "is_active", "tenant")
    list_filter = ("rule_type", "approver_role", "is_active", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")


# ---------------------------------------------------------------- 8.6 Order Management
#
# 8.6 EXTENDS `scm.SalesOrder` (owned by SCM 4.5) by FK. None of the models below is a second
# order master, and none of them posts a JournalEntry (L29). The four REGISTERED admins are the
# four numbered headers; the two tenant-less children get inlines on their parent instead of
# registrations of their own, because a child row is never edited from the admin list.


@admin.register(OrderValidationRule)
class OrderValidationRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "rule_type", "severity", "active_on", "party", "priority", "is_active", "tenant")
    list_filter = ("rule_type", "severity", "active_on", "is_active", "tenant")
    search_fields = ("number", "name", "description", "party__name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("party", "tenant")
    raw_id_fields = ("party",)


@admin.register(OrderHold)
class OrderHoldAdmin(admin.ModelAdmin):
    list_display = ("number", "sales_order", "hold_type", "severity", "status", "raised_at", "raised_by", "checked_out_by", "tenant")
    list_filter = ("hold_type", "severity", "status", "tenant")
    search_fields = ("number", "reason", "clear_note", "sales_order__number", "party__name")
    # status / severity / evaluation_snapshot and EVERY lifecycle stamp are written by a named
    # POST verb, never by hand. An editable snapshot from /admin/ would be a forgeable record of
    # why an order was held (L22), and an editable status would bypass the checkout guards.
    readonly_fields = (
        "tenant", "number", "status", "severity", "evaluation_snapshot",
        "raised_at", "raised_by", "checked_out_by", "checked_out_at",
        "cleared_by", "cleared_at", "superseded_by",
        "created_at", "updated_at",
    )
    list_select_related = ("sales_order", "rule", "party", "raised_by", "checked_out_by", "cleared_by", "tenant")
    raw_id_fields = ("sales_order", "rule", "party", "raised_by", "checked_out_by", "cleared_by", "superseded_by")


class OrderAmendmentLineInline(admin.TabularInline):
    model = OrderAmendmentLine
    extra = 0
    # The child is TENANT-LESS (reached via amendment.tenant), matching the scm sibling
    # convention. sales_order_line is nullable + SET_NULL because an `add_line` amendment has no
    # original line — that is the field's meaning, not a data-integrity gap.
    fields = ("sales_order_line", "operation", "new_quantity", "new_unit_price", "note")
    raw_id_fields = ("sales_order_line",)


@admin.register(OrderAmendment)
class OrderAmendmentAdmin(admin.ModelAdmin):
    list_display = ("number", "sales_order", "change_type", "status", "requested_by", "requested_at", "decided_by", "applied_at", "tenant")
    list_filter = ("change_type", "status", "tenant")
    search_fields = ("number", "reason", "notes", "decision_note", "sales_order__number")
    # impact_snapshot is the frozen pre-approval impact read-out and the decision stamps are
    # written by their own verbs; both stay read-only here.
    readonly_fields = (
        "tenant", "number", "status", "impact_snapshot",
        "requested_by", "requested_at", "decided_by", "decided_at",
        "applied_by", "applied_at",
        "created_at", "updated_at",
    )
    list_select_related = ("sales_order", "requested_by", "decided_by", "applied_by", "tenant")
    raw_id_fields = ("sales_order", "document", "requested_by", "decided_by", "applied_by")
    inlines = [OrderAmendmentLineInline]


class PerformanceObligationInline(admin.TabularInline):
    model = PerformanceObligation
    extra = 0
    # allocated_amount / recognized_amount are the ONLY stored money columns in 8.6, both
    # editable=False, and recompute() is their only writer. They are NOT in `fields`, so the
    # admin cannot mint a recognised figure that the schedule never derived.
    fields = (
        "sales_order_line", "item", "obligation_type", "description",
        "allocation_pct", "recognition_method", "recognize_on",
        "milestone_label", "evidence_reference",
    )
    raw_id_fields = ("sales_order_line", "item")


@admin.register(RevenueSchedule)
class RevenueScheduleAdmin(admin.ModelAdmin):
    list_display = ("number", "sales_order", "status", "method", "compliance_standard", "fiscal_period", "contract_amount", "recognized_amount", "deferred_amount", "tenant")
    list_filter = ("status", "method", "compliance_standard", "tenant")
    search_fields = ("number", "notes", "sales_order__number")
    # contract_amount / allocated / recognized / deferred are DERIVED properties, not columns, so
    # there is nothing here to make editable — which is the point. journal_entry is a
    # reference-only FK: 8.6 posts nothing (L29).
    readonly_fields = (
        "tenant", "number", "journal_entry",
        "created_at", "updated_at",
    )
    list_select_related = ("sales_order", "fiscal_period", "journal_entry", "tenant")
    raw_id_fields = ("sales_order", "fiscal_period", "journal_entry")
    inlines = [PerformanceObligationInline]


# 8.7 Territory & Quota Management — all four models registered; the four boards get no admin.
@admin.register(TerritoryRule)
class TerritoryRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "segment_type", "match_mode", "alignment_type", "assignment_scope", "target_territory", "priority", "is_active", "tenant")
    list_filter = ("segment_type", "match_mode", "alignment_type", "assignment_scope", "is_active", "is_catch_all", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("tenant", "number", "last_run_at", "last_run_matched_count", "created_at", "updated_at")
    list_select_related = ("target_territory", "tenant")
    raw_id_fields = ("target_territory",)


@admin.register(AccountTerritoryAssignment)
class AccountTerritoryAssignmentAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "territory", "rule", "owner", "alignment_type", "assignment_source", "effective_from", "effective_to", "tenant")
    list_filter = ("alignment_type", "assignment_source", "tenant")
    search_fields = ("number", "account__name", "notes")
    readonly_fields = ("tenant", "number", "assigned_by", "created_at", "updated_at")
    list_select_related = ("account", "territory", "rule", "owner", "assigned_by", "tenant")
    raw_id_fields = ("account", "territory", "rule", "owner", "assigned_by")


@admin.register(TerritoryMember)
class TerritoryMemberAdmin(admin.ModelAdmin):
    list_display = ("number", "territory", "user", "member_role", "assignment_type", "coverage_split_pct", "paired_user", "is_primary", "tenant")
    list_filter = ("member_role", "assignment_type", "is_primary", "tenant")
    search_fields = ("number", "user__username", "territory__name", "notes")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("territory", "user", "paired_user", "tenant")
    raw_id_fields = ("territory", "user", "paired_user")


@admin.register(QuotaPlan)
class QuotaPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "quota_ref", "forecast_period", "owner", "territory", "method", "status", "growth_target_pct", "is_active", "tenant")
    list_filter = ("method", "status", "allocation_basis", "baseline_source", "target_type", "phasing", "is_active", "tenant")
    search_fields = ("number", "quota_ref__number", "owner__username", "notes")
    readonly_fields = ("tenant", "number", "submitted_by", "submitted_at", "approved_by", "approved_at", "calculated_at", "created_at", "updated_at")
    list_select_related = ("quota_ref", "forecast_period", "owner", "territory", "submitted_by", "approved_by", "tenant")
    raw_id_fields = ("quota_ref", "forecast_period", "owner", "territory", "submitted_by", "approved_by")






# 8.8 Sales Activity & Task Management — all six models registered; the three boards get no admin.
#
# OWNERSHIP (L36/L37): there is no `Activity`/`Task`/`Meeting`/`EmailLog` admin here, because 8.8
# declares no such master. `ActivityLog.communication_log` is a raw-id FK to CRM 1.5's
# `CommunicationLog` and `ActivityLog.account` is a raw-id FK to `core.Party` — neither is edited
# from this admin, and the frozen evidence columns are readonly so they cannot be typed either.
@admin.register(ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "kind", "default_outcome", "default_duration_seconds", "default_priority", "requires_opportunity", "is_billable", "is_active", "tenant")
    list_filter = ("kind", "default_priority", "requires_opportunity", "is_billable", "is_active", "tenant")
    search_fields = ("number", "name", "description")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("tenant",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("number", "communication_log", "activity_type", "owner", "opportunity", "account", "territory", "capture_source", "occurred_on", "tenant")
    list_filter = ("capture_source", "is_auto_captured", "activity_type", "territory", "tenant")
    search_fields = ("number", "next_best_action", "communication_log__number")
    # The seven frozen-evidence columns are readonly HERE as well as `editable=False` on the model.
    # Two layers, because an admin is a second authoring surface: an admin who can hand-type
    # "open_count = 47" bypasses the whole point of L20/L22, which is that a rep cannot.
    readonly_fields = (
        "tenant", "number", "occurred_on", "planned_minutes",
        "opened_at", "open_count", "clicked_at", "click_count", "replied_at",
        "created_at", "updated_at",
    )
    list_select_related = ("communication_log", "activity_type", "owner", "opportunity", "account", "territory", "tenant")
    raw_id_fields = ("communication_log", "activity_type", "owner", "opportunity", "account", "territory")


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "cadence", "target_type", "task_type", "priority", "territory", "owner", "is_active", "last_generated_on", "tenant")
    list_filter = ("cadence", "target_type", "task_type", "priority", "is_active", "tenant")
    search_fields = ("number", "name", "description")
    # `last_generated_on` / `generated_count` are the FROZEN RECEIPT. Readonly in admin too: the
    # generate verb is their only writer, inside the transaction that creates the tasks.
    readonly_fields = ("tenant", "number", "last_generated_on", "generated_count", "created_at", "updated_at")
    list_select_related = ("activity_type", "territory", "owner", "tenant")
    raw_id_fields = ("activity_type", "territory", "owner")


@admin.register(TaskTemplateStep)
class TaskTemplateStepAdmin(admin.ModelAdmin):
    list_display = ("template", "order", "title", "task_type", "priority", "offset_days", "tenant")
    list_filter = ("task_type", "priority", "tenant")
    search_fields = ("title", "instructions")
    readonly_fields = ("tenant", "created_at")
    list_select_related = ("template", "tenant")
    raw_id_fields = ("template",)


@admin.register(SalesPlanCycle)
class SalesPlanCycleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "cadence", "period_start", "period_end", "owner", "territory", "status", "suggestion_mode", "closed_at", "tenant")
    list_filter = ("cadence", "status", "suggestion_mode", "tenant")
    search_fields = ("number", "name", "notes")
    # `closed_at` is SYSTEM-SET on the transition. Readonly here so an admin cannot type a closing
    # date either — the same rule that keeps it off the ModelForm (L22).
    readonly_fields = ("tenant", "number", "closed_at", "created_at", "updated_at")
    list_select_related = ("owner", "territory", "tenant")
    raw_id_fields = ("owner", "territory")


@admin.register(ActivityGoal)
class ActivityGoalAdmin(admin.ModelAdmin):
    list_display = ("cycle", "metric", "target_count", "tenant")
    list_filter = ("metric", "tenant")
    readonly_fields = ("tenant", "created_at")
    list_select_related = ("cycle", "tenant")
    raw_id_fields = ("cycle",)


# 8.9 Sales Enablement
@admin.register(EnablementContent)
class EnablementContentAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "content_type", "target_stage", "target_persona", "competitor", "is_client_facing", "is_active", "view_count", "share_count", "tenant")
    list_filter = ("content_type", "target_stage", "target_persona", "is_client_facing", "is_active", "tenant")
    search_fields = ("number", "title", "description", "tags")
    readonly_fields = ("tenant", "number", "view_count", "share_count", "created_at", "updated_at")
    list_select_related = ("competitor", "document", "pipeline_stage", "author", "tenant")
    raw_id_fields = ("competitor", "document", "pipeline_stage", "author")


@admin.register(SalesPlaybook)
class SalesPlaybookAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "motion_type", "pipeline", "status", "target_audience", "owner", "version", "is_active", "tenant")
    list_filter = ("motion_type", "status", "is_active", "tenant")
    search_fields = ("number", "name", "summary", "target_audience")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("pipeline", "owner", "tenant")
    raw_id_fields = ("pipeline", "owner")


@admin.register(SalesCertification)
class SalesCertificationAdmin(admin.ModelAdmin):
    list_display = ("number", "curriculum_name", "category", "rep", "status", "score_percent", "passing_score_percent", "certified_at", "expires_at", "tenant")
    list_filter = ("category", "status", "tenant")
    search_fields = ("number", "curriculum_name", "rep__username", "rep__first_name", "rep__last_name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("rep", "certified_by", "hrm_course", "tenant")
    raw_id_fields = ("rep", "certified_by", "hrm_course")


@admin.register(CoachingScorecard)
class CoachingScorecardAdmin(admin.ModelAdmin):
    list_display = ("number", "coachee", "coach", "overall_score", "discovery_score", "value_prop_score", "objection_handling_score", "next_steps_score", "talk_listen_ratio_percent", "call_sentiment", "review_status", "evaluated_on", "tenant")
    list_filter = ("review_status", "call_sentiment", "tenant")
    search_fields = ("number", "coachee__username", "coachee__first_name", "coachee__last_name", "coach__username", "transcript_summary")
    readonly_fields = ("tenant", "number", "overall_score", "created_at", "updated_at")
    list_select_related = ("communication_log", "activity_log", "coach", "coachee", "tenant")
    raw_id_fields = ("communication_log", "activity_log", "coach", "coachee")


# 8.10 Incentive Compensation Management
@admin.register(CommissionPlan)
class CommissionPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "plan_type", "tier_mode", "base_rate_pct", "currency", "target_region", "status", "effective_start", "tenant")
    list_filter = ("plan_type", "tier_mode", "status", "tenant")
    search_fields = ("number", "name", "code", "description", "target_region")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("currency", "sales_quota", "owner", "tenant")
    raw_id_fields = ("sales_quota", "owner", "currency")


@admin.register(CommissionEarning)
class CommissionEarningAdmin(admin.ModelAdmin):
    list_display = ("number", "payee", "plan", "opportunity", "deal_amount", "credited_volume", "applied_rate_pct", "gross_commission", "status", "earned_date", "tenant")
    list_filter = ("status", "credit_type", "tenant")
    search_fields = ("number", "payee__username", "payee__first_name", "payee__last_name", "opportunity__name")
    readonly_fields = ("tenant", "number", "credited_volume", "base_commission_amount", "gross_commission", "functional_amount", "created_at", "updated_at")
    list_select_related = ("plan", "payee", "opportunity", "sales_order", "clawback_parent", "statement", "deal_currency", "tenant")
    raw_id_fields = ("plan", "payee", "opportunity", "sales_order", "clawback_parent", "statement", "deal_currency")


@admin.register(CommissionStatement)
class CommissionStatementAdmin(admin.ModelAdmin):
    list_display = ("statement_number", "payee", "plan", "period_start", "period_end", "gross_earnings", "draw_recovered", "net_payout", "status", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("statement_number", "number", "payee__username", "payee__first_name", "payee__last_name")
    readonly_fields = ("tenant", "number", "total_credited_volume", "total_base_commission", "total_accelerator_amount", "total_spif_amount", "gross_earnings", "draw_recovered", "net_payout", "approved_at", "locked_at", "created_at", "updated_at")
    list_select_related = ("payee", "plan", "approved_by", "payroll_run", "tenant")
    raw_id_fields = ("payee", "plan", "approved_by", "payroll_run")


@admin.register(CommissionAdjustment)
class CommissionAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("number", "payee", "adjustment_type", "amount", "status", "effective_date", "tenant")
    list_filter = ("adjustment_type", "status", "tenant")
    search_fields = ("number", "reason", "payee__username", "payee__first_name", "payee__last_name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("statement", "earning", "payee", "requested_by", "approved_by", "tenant")
    raw_id_fields = ("statement", "earning", "payee", "requested_by", "approved_by")


# 8.11 Customer Success & Account Management
@admin.register(CustomerHealthScore)
class CustomerHealthScoreAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "evaluation_date", "overall_score", "health_band", "score_trend", "risk_level", "is_churn_risk", "tenant")
    list_filter = ("health_band", "score_trend", "risk_level", "is_churn_risk", "tenant")
    search_fields = ("number", "account__name", "account__number", "active_alert_message", "notes")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("account", "tenant")
    raw_id_fields = ("account",)


@admin.register(CustomerRenewal)
class CustomerRenewalAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "renewal_name", "renewal_date", "target_close_date", "current_arr", "stage", "churn_risk_flag", "tenant")
    list_filter = ("stage", "churn_risk_flag", "auto_renewal", "tenant")
    search_fields = ("number", "renewal_name", "contract_reference", "account__name", "account__number")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("account", "owner", "currency", "expansion_opportunity", "original_order", "tenant")
    raw_id_fields = ("account", "owner", "currency", "expansion_opportunity", "original_order")


@admin.register(CustomerOnboarding)
class CustomerOnboardingAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "title", "playbook_template", "stage", "status", "kickoff_date", "target_go_live_date", "progress_pct", "tenant")
    list_filter = ("playbook_template", "stage", "status", "tenant")
    search_fields = ("number", "title", "account__name", "account__number", "executive_sponsor_name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("account", "lead_csm", "sales_order", "tenant")
    raw_id_fields = ("account", "lead_csm", "sales_order")


@admin.register(CustomerBusinessReview)
class CustomerBusinessReviewAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "title", "review_period", "review_year", "scheduled_date", "completed_date", "status", "is_referenceable", "tenant")
    list_filter = ("review_period", "status", "template_type", "is_referenceable", "case_study_status", "tenant")
    search_fields = ("number", "title", "account__name", "account__number", "client_attendees")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("account", "lead_csm", "account_plan", "tenant")
    raw_id_fields = ("account", "lead_csm", "account_plan")


# ---------------------------------------------------------------- 8.13 Marketing Alignment & Attribution
#
# OWNERSHIP (L36/L37): there is no Campaign / Lead / Opportunity / Content admin here, because
# 8.13 declares no such master. `crm.Campaign` (budget, actual spend, UTM tags) is the campaign
# master, `crm.Lead` and `crm.Opportunity` are the journey and the conversion endpoint, and
# `sales.EnablementContent` (8.9) is the content master. Every FK below points at one of them.
#
# `responded_at` and `attended_at` are SYSTEM-SET on the workflow transition, so they are
# readonly here as well as `editable=False` on the model: an admin must not be able to type a
# response time that the workflow never recorded. The auto-`number` is minted by
# TenantNumbered.save() and is likewise never typed in.


@admin.register(AttributionTouchpoint)
class AttributionTouchpointAdmin(admin.ModelAdmin):
    list_display = ("number", "campaign", "lead", "opportunity", "channel", "touch_type", "touch_date", "touch_position", "cost", "tenant")
    list_filter = ("channel", "touch_type", "touch_position", "tenant")
    search_fields = ("number", "campaign__name", "lead__name", "opportunity__name", "source_reference")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("campaign", "lead", "opportunity", "currency", "tenant")
    raw_id_fields = ("campaign", "lead", "opportunity", "currency")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is not None and db_field.name in {"campaign", "lead", "opportunity"}:
            model = db_field.remote_field.model
            kwargs["queryset"] = model._default_manager.filter(tenant=tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class TenantScopedFKAdmin(admin.ModelAdmin):
    """Base admin for the 8.13 and 8.12 entities: narrows EVERY tenant-scoped FK to the tenant.

    ``accounts.User.tenant`` is nullable -- the platform superuser has no tenant -- so a user FK
    is filtered on ``tenant=request.tenant, is_active=True``, which also excludes that
    superuser. ``accounting.Currency`` is a GLOBAL master with no tenant and is never narrowed
    (L29).
    """

    tenant_fk_fields = ()
    tenant_user_fk_fields = ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            if db_field.name in self.tenant_user_fk_fields:
                kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(
                    tenant=tenant, is_active=True
                )
            elif db_field.name in self.tenant_fk_fields:
                kwargs["queryset"] = db_field.remote_field.model._default_manager.filter(
                    tenant=tenant
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CampaignAttribution)
class CampaignAttributionAdmin(TenantScopedFKAdmin):
    list_display = ("number", "touchpoint", "attribution_model", "credit_pct", "attributed_revenue", "attributed_cost", "status", "computed_on", "tenant")
    list_filter = ("attribution_model", "status", "tenant")
    search_fields = ("number", "touchpoint__number", "notes")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("touchpoint", "computed_by", "tenant")
    raw_id_fields = ("touchpoint", "computed_by")
    tenant_fk_fields = ("touchpoint",)
    tenant_user_fk_fields = ("computed_by",)


@admin.register(MqlHandoff)
class MqlHandoffAdmin(TenantScopedFKAdmin):
    list_display = ("number", "lead", "campaign", "account", "assigned_to", "status", "source_kind", "handoff_at", "sla_due_at", "responded_at", "tenant")
    list_filter = ("status", "source_kind", "tenant")
    search_fields = ("number", "lead__name", "lead__number", "account__name", "acceptance_reason", "rejection_reason")
    # responded_at is stamped by save() on the first sales response -- readonly so it cannot be
    # typed, which would make the SLA compliance figure on the console meaningless.
    readonly_fields = ("tenant", "number", "responded_at", "created_at", "updated_at")
    list_select_related = ("lead", "campaign", "account", "owner", "assigned_to", "opportunity", "currency", "tenant")
    raw_id_fields = ("lead", "campaign", "account", "owner", "assigned_to", "opportunity", "currency")
    tenant_fk_fields = ("lead", "campaign", "account", "opportunity")
    tenant_user_fk_fields = ("owner", "assigned_to")


@admin.register(ContentEngagement)
class ContentEngagementAdmin(TenantScopedFKAdmin):
    list_display = ("number", "content", "account", "lead", "campaign", "engagement_type", "engagement_channel", "engagement_score", "revenue_attributed", "tenant")
    list_filter = ("engagement_type", "engagement_channel", "tenant")
    search_fields = ("number", "content__title", "account__name", "lead__name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("content", "account", "lead", "campaign", "currency", "tenant")
    raw_id_fields = ("content", "account", "lead", "campaign", "currency")
    tenant_fk_fields = ("content", "account", "lead", "campaign")


@admin.register(MarketingEvent)
class MarketingEventAdmin(TenantScopedFKAdmin):
    list_display = ("number", "name", "event_type", "status", "start_at", "end_at", "venue", "capacity", "budget", "tenant")
    list_filter = ("event_type", "status", "tenant")
    search_fields = ("number", "name", "venue", "description")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("owner", "campaign", "currency", "tenant")
    raw_id_fields = ("owner", "campaign", "currency")
    tenant_fk_fields = ("campaign",)
    tenant_user_fk_fields = ("owner",)


@admin.register(EventRegistration)
class EventRegistrationAdmin(TenantScopedFKAdmin):
    list_display = ("event", "registrant_name", "registrant_email", "registration_status", "source_channel", "followup_status", "engagement_score", "registered_at", "attended_at", "tenant")
    list_filter = ("registration_status", "source_channel", "followup_status", "tenant")
    search_fields = ("registrant_name", "registrant_email", "event__name", "followup_notes")
    # attended_at is stamped by save() on the transition to "attended" -- readonly for the same
    # reason as MqlHandoff.responded_at above.
    readonly_fields = ("tenant", "attended_at", "created_at", "updated_at")
    list_select_related = ("event", "lead", "account", "campaign", "opportunity", "tenant")
    raw_id_fields = ("event", "lead", "account", "campaign", "opportunity")
    tenant_fk_fields = ("event", "lead", "account", "campaign", "opportunity")


# ---------------------------------------------------------------- 8.12 Sales Analytics & Intelligence
#
# OWNERSHIP (L36/L37): there is no Reason / Outcome / Competitor / Quota / Currency / Activity /
# Report / Coaching admin registered here, because 8.12 declares no such master. Every FK below
# points at an existing spine row: crm.Opportunity, crm.CommunicationLog, core.Party, accounts.User,
# sales.WinLossReason + sales.OpportunityOutcome (8.2), sales.Pipeline + sales.PipelineStage (8.2),
# sales.QuotaPlan (8.7), sales.ForecastPeriod (8.4) and sales.CoachingScorecard (8.9).
# `accounting.Currency` is a GLOBAL master with no tenant and is never narrowed (L29).


@admin.register(WinLossDebrief)
class WinLossDebriefAdmin(TenantScopedFKAdmin):
    list_display = ("number", "opportunity", "outcome", "primary_reason", "feedback_team", "status", "debriefed_on", "tenant")
    list_filter = ("status", "interview_channel", "feedback_team", "tenant")
    search_fields = ("number", "opportunity__name", "buyer_quote", "action_items", "notes")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("opportunity", "outcome", "primary_reason", "account", "interviewer", "action_owner", "tenant")
    raw_id_fields = ("opportunity", "outcome", "primary_reason", "account", "interviewer", "action_owner", "communication_log")
    tenant_fk_fields = ("opportunity", "outcome", "primary_reason", "account", "communication_log")
    tenant_user_fk_fields = ("interviewer", "action_owner")


@admin.register(StageVelocityAnalysis)
class StageVelocityAnalysisAdmin(TenantScopedFKAdmin):
    list_display = ("number", "pipeline", "pipeline_stage", "median_days_in_stage", "p90_days_in_stage", "is_bottleneck", "bottleneck_rank", "status", "tenant")
    list_filter = ("status", "is_bottleneck", "tenant")
    search_fields = ("number", "pipeline__name", "pipeline_stage__name", "recommendation", "notes")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("pipeline", "pipeline_stage", "tenant")
    raw_id_fields = ("pipeline", "pipeline_stage")
    tenant_fk_fields = ("pipeline", "pipeline_stage")


@admin.register(FunnelConversionRecord)
class FunnelConversionRecordAdmin(TenantScopedFKAdmin):
    list_display = ("number", "label", "funnel_scope", "entered_count", "converted_count", "conversion_rate_pct", "dropoff_count", "period_start", "period_end", "tenant")
    list_filter = ("funnel_scope", "tenant")
    search_fields = ("number", "label", "source_channel", "segment", "notes")
    # conversion_rate_pct and dropoff_count are DERIVED in save() -- readonly so they can never be
    # typed and drift away from the entered/converted counts they are computed from (L28).
    readonly_fields = ("tenant", "number", "conversion_rate_pct", "dropoff_count", "created_at", "updated_at")
    list_select_related = ("from_stage", "to_stage", "territory", "owner", "tenant")
    raw_id_fields = ("from_stage", "to_stage", "territory", "owner")
    tenant_fk_fields = ("from_stage", "to_stage", "territory")
    tenant_user_fk_fields = ("owner",)


@admin.register(RepPerformanceScorecard)
class RepPerformanceScorecardAdmin(TenantScopedFKAdmin):
    list_display = ("number", "rep", "territory", "period_start", "period_end", "win_rate_pct", "quota_attainment_pct", "goal_gap_value", "rating", "status", "tenant")
    list_filter = ("rating", "status", "tenant")
    search_fields = ("number", "rep__username", "strengths", "coaching_actions", "notes")
    # The four outcome figures are DERIVED in save() -- readonly so they can never be typed and
    # drift away from the counts they are computed from (L28).
    readonly_fields = ("tenant", "number", "win_rate_pct", "average_deal_size", "quota_attainment_pct", "goal_gap_value", "created_at", "updated_at")
    list_select_related = ("rep", "territory", "manager", "currency", "quota_plan", "forecast_period", "tenant")
    raw_id_fields = ("rep", "territory", "manager", "forecast_period", "quota_plan", "coaching_scorecard", "currency")
    tenant_fk_fields = ("territory", "forecast_period", "quota_plan", "coaching_scorecard")
    tenant_user_fk_fields = ("rep", "manager")


# 8.14 Partner & Channel Management Admins
@admin.register(PartnerProfile)
class PartnerProfileAdmin(TenantScopedFKAdmin):
    list_display = ("number", "partner", "partner_type", "tier", "onboarding_status", "channel_manager", "annual_revenue_target", "actual_revenue_ytd", "tenant")
    list_filter = ("partner_type", "tier", "onboarding_status", "portal_access_enabled", "tenant")
    search_fields = ("number", "partner__name", "notes")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("partner", "channel_manager", "authorized_territory", "currency", "tenant")
    raw_id_fields = ("partner", "channel_manager", "authorized_territory", "agreement_document", "currency")
    tenant_fk_fields = ("partner", "authorized_territory", "agreement_document")
    tenant_user_fk_fields = ("channel_manager",)


@admin.register(DealRegistration)
class DealRegistrationAdmin(TenantScopedFKAdmin):
    list_display = ("number", "deal_name", "partner", "customer_account", "estimated_value", "status", "exclusivity_status", "protection_end_date", "tenant")
    list_filter = ("status", "exclusivity_status", "is_conflicted", "tenant")
    search_fields = ("number", "deal_name", "partner__name", "customer_account__name", "partner_rep_name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("partner", "customer_account", "currency", "reviewed_by", "opportunity", "tenant")
    raw_id_fields = ("partner", "customer_account", "opportunity", "reviewed_by", "currency")
    tenant_fk_fields = ("partner", "customer_account", "opportunity")
    tenant_user_fk_fields = ("reviewed_by",)


@admin.register(JointAccountPlan)
class JointAccountPlanAdmin(TenantScopedFKAdmin):
    list_display = ("number", "plan_name", "partner", "client_account", "plan_year", "co_sell_motion", "status", "target_revenue", "actual_revenue", "tenant")
    list_filter = ("status", "co_sell_motion", "plan_year", "tenant")
    search_fields = ("number", "plan_name", "partner__name", "client_account__name", "partner_lead_name")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("partner", "client_account", "currency", "vendor_lead", "collateral_document", "tenant")
    raw_id_fields = ("partner", "client_account", "vendor_lead", "collateral_document", "currency")
    tenant_fk_fields = ("partner", "client_account", "collateral_document")
    tenant_user_fk_fields = ("vendor_lead",)


@admin.register(ChannelConflict)
class ChannelConflictAdmin(TenantScopedFKAdmin):
    list_display = ("number", "conflict_type", "severity", "status", "claimant_partner", "client_account", "escalation_level", "resolution_outcome", "tenant")
    list_filter = ("conflict_type", "severity", "status", "escalation_level", "resolution_outcome", "tenant")
    search_fields = ("number", "claimant_partner__name", "client_account__name", "description", "resolution_rationale")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")
    list_select_related = ("claimant_partner", "competing_partner", "client_account", "direct_sales_rep", "territory", "deal_registration", "opportunity", "escalated_to", "resolved_by", "tenant")
    raw_id_fields = ("claimant_partner", "competing_partner", "client_account", "direct_sales_rep", "territory", "deal_registration", "opportunity", "escalated_to", "resolved_by")
    tenant_fk_fields = ("claimant_partner", "competing_partner", "client_account", "territory", "deal_registration", "opportunity")
    tenant_user_fk_fields = ("direct_sales_rep", "escalated_to", "resolved_by")




