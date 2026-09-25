from django.contrib import admin

from .models import (
    AccountClassification,
    AccountPlan,
    AccountStakeholder,
    CompetitorProfile,
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


@admin.register(OpportunityPipelinePlacement)
class OpportunityPipelinePlacementAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "pipeline", "current_stage", "probability_override", "stage_entered_at", "tenant")
    list_filter = ("pipeline", "current_stage", "tenant")
    search_fields = ("opportunity__number", "opportunity__name", "pipeline__name")
    readonly_fields = ("tenant", "stage_entered_at", "created_at", "updated_at")

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


@admin.register(CompetitorProfile)
class CompetitorProfileAdmin(admin.ModelAdmin):
    list_display = ("number", "party", "website_url", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "party__name", "aliases", "market_positioning")
    readonly_fields = ("tenant", "number", "created_at", "updated_at")


@admin.register(OpportunityCompetitor)
class OpportunityCompetitorAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "competitor_profile", "relationship", "is_primary", "tenant")
    list_filter = ("relationship", "is_primary", "tenant")
    search_fields = ("opportunity__name", "competitor_profile__party__name")
    readonly_fields = ("tenant", "created_at", "updated_at")


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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

