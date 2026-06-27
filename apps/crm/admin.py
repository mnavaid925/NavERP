from django.contrib import admin

from .models import (
    AccountProfile,
    AnalyticsDashboard,
    AnalyticsReport,
    ApprovalRequest,
    CalendarEvent,
    Campaign,
    CampaignMember,
    Case,
    CaseComment,
    CommunicationLog,
    ContactProfile,
    ContractDocument,
    CrmMilestone,
    CrmProject,
    CrmTask,
    CustomerPortalAccess,
    DashboardWidget,
    DocTemplate,
    EmailCampaign,
    EmailTemplate,
    EventAttendee,
    Expense,
    FormSubmission,
    HealthScore,
    HealthScoreConfig,
    KbCategory,
    KnowledgeArticle,
    LandingPage,
    Lead,
    OnboardingPlan,
    OnboardingStep,
    Opportunity,
    OpportunitySplit,
    PartnerPortalAccess,
    PriceBook,
    Product,
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
    Quote,
    QuoteLine,
    SalesQuota,
    SignerRecord,
    SlaPolicy,
    ReportSnapshot,
    Survey,
    Territory,
    Timesheet,
    WorkflowLog,
    WorkflowRule,
)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "company", "status", "rating", "score", "owner", "tenant")
    list_filter = ("status", "rating", "source", "tenant")
    search_fields = ("number", "name", "company", "email")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "account", "stage", "forecast_category", "amount",
                    "probability", "territory", "owner", "tenant")
    list_filter = ("stage", "forecast_category", "tenant")
    search_fields = ("number", "name", "competitor")
    raw_id_fields = ("territory",)
    readonly_fields = ("number", "lost_at", "stage_changed_at", "created_at", "updated_at")


# ===== 1.2 Sales Force Automation (recreated) ===============================
@admin.register(Territory)
class TerritoryAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "region", "segment", "parent", "manager", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "name", "region", "segment")
    raw_id_fields = ("parent",)
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "sku", "product_type", "unit_price", "cost", "is_active", "tenant")
    list_filter = ("product_type", "is_active", "tenant")
    search_fields = ("number", "name", "sku")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(PriceBook)
class PriceBookAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "currency_code", "region", "tier", "price_adjustment_pct",
                    "is_default", "is_active", "tenant")
    list_filter = ("is_default", "is_active", "tenant")
    search_fields = ("number", "name", "region", "tier")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(OpportunitySplit)
class OpportunitySplitAdmin(admin.ModelAdmin):
    list_display = ("opportunity", "user", "split_type", "percentage", "tenant")
    list_filter = ("split_type", "tenant")
    search_fields = ("opportunity__name", "user__username")
    raw_id_fields = ("opportunity", "user")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "account", "opportunity", "status", "total", "owner", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "name", "account__name")
    raw_id_fields = ("opportunity", "account", "price_book")
    readonly_fields = ("number", "subtotal", "tax_total", "total", "sent_at", "accepted_at",
                       "created_at", "updated_at")


@admin.register(QuoteLine)
class QuoteLineAdmin(admin.ModelAdmin):
    list_display = ("quote", "description", "quantity", "unit_price", "discount_pct", "order", "tenant")
    list_filter = ("tenant",)
    search_fields = ("description",)
    raw_id_fields = ("quote", "product")
    readonly_fields = ("created_at",)


@admin.register(SalesQuota)
class SalesQuotaAdmin(admin.ModelAdmin):
    list_display = ("number", "owner", "territory", "period_type", "period_year",
                    "period_number", "target_amount", "tenant")
    list_filter = ("period_type", "period_year", "tenant")
    search_fields = ("number", "owner__username")
    raw_id_fields = ("territory",)
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "type", "objective", "status", "budget_actual", "owner", "tenant")
    list_filter = ("type", "objective", "status", "tenant")
    search_fields = ("number", "name")
    raw_id_fields = ("parent_campaign",)
    readonly_fields = ("number", "created_at", "updated_at")


# ===== 1.3 Marketing Automation (recreated) =================================
@admin.register(CampaignMember)
class CampaignMemberAdmin(admin.ModelAdmin):
    list_display = ("member_name", "campaign", "status", "member_email", "responded_at", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("member_name", "member_email", "campaign__name")
    raw_id_fields = ("campaign", "party", "lead")
    readonly_fields = ("responded_at", "created_at", "updated_at")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "category", "subject", "is_active", "owner", "tenant")
    list_filter = ("category", "is_active", "tenant")
    search_fields = ("number", "name", "subject")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "campaign", "send_type", "status", "sent_count",
                    "opened_count", "clicked_count", "tenant")
    list_filter = ("status", "send_type", "is_ab_test", "tenant")
    search_fields = ("number", "name", "campaign__name")
    raw_id_fields = ("campaign", "template", "variant_template")
    readonly_fields = ("number", "sent_at", "recipients_count", "sent_count", "opened_count",
                       "clicked_count", "bounced_count", "unsubscribed_count",
                       "created_at", "updated_at")


@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "campaign", "status", "submission_count", "routing_owner", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "name", "headline", "slug")
    raw_id_fields = ("campaign",)
    readonly_fields = ("number", "public_token", "submission_count", "created_at", "updated_at")


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = ("name", "landing_page", "email", "status", "routed_to", "created_at", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("name", "email", "company")
    raw_id_fields = ("landing_page", "converted_lead")
    readonly_fields = ("ip_address", "created_at")


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "account", "priority", "status", "sla_policy", "owner", "tenant")
    list_filter = ("status", "priority", "type", "tenant")
    search_fields = ("number", "subject")
    raw_id_fields = ("sla_policy",)
    readonly_fields = ("number", "resolved_at", "closed_at", "first_response_due", "first_responded_at",
                       "resolution_due", "satisfaction_rating", "satisfaction_comment", "satisfaction_at",
                       "public_token", "created_at", "updated_at")


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "kb_category", "visibility", "status",
                    "views_count", "helpful_count", "tenant")
    list_filter = ("status", "visibility", "tenant")
    search_fields = ("number", "title", "category")
    raw_id_fields = ("kb_category",)
    readonly_fields = ("number", "views_count", "helpful_count", "not_helpful_count",
                       "public_token", "created_at", "updated_at")


# ===== 1.4 Customer Service & Support (recreated) ===========================
@admin.register(SlaPolicy)
class SlaPolicyAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "is_default", "is_active", "tenant")
    list_filter = ("is_active", "is_default", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(CaseComment)
class CaseCommentAdmin(admin.ModelAdmin):
    list_display = ("case", "author", "is_public", "created_at", "tenant")
    list_filter = ("is_public", "tenant")
    search_fields = ("body", "author_name")
    raw_id_fields = ("case", "author")
    readonly_fields = ("created_at",)


@admin.register(KbCategory)
class KbCategoryAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "parent", "order", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "name")
    raw_id_fields = ("parent",)
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(CustomerPortalAccess)
class CustomerPortalAccessAdmin(admin.ModelAdmin):
    list_display = ("number", "customer_party", "portal_user", "can_submit_cases", "is_active", "tenant")
    list_filter = ("is_active", "can_submit_cases", "tenant")
    search_fields = ("number", "customer_party__name", "portal_user__username")
    raw_id_fields = ("customer_party", "portal_user")
    readonly_fields = ("number", "accepted_at", "created_at", "updated_at")


@admin.register(CrmTask)
class CrmTaskAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "type", "priority", "status", "due_date",
                    "recurrence", "owner", "tenant")
    list_filter = ("status", "priority", "type", "recurrence", "tenant")
    search_fields = ("number", "subject")
    raw_id_fields = ("recurrence_parent", "related_case", "related_opportunity")
    readonly_fields = ("number", "completed_at", "created_at", "updated_at")


# ===== 1.5 Activity & Communication Management (recreated) ===================
@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "event_type", "status", "start", "owner", "tenant")
    list_filter = ("status", "event_type", "sync_source", "tenant")
    search_fields = ("number", "title", "location")
    raw_id_fields = ("party", "related_opportunity", "related_case")
    readonly_fields = ("number", "public_token", "created_at", "updated_at")


@admin.register(EventAttendee)
class EventAttendeeAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "event", "rsvp_status", "is_organizer", "tenant")
    list_filter = ("rsvp_status", "is_organizer", "tenant")
    search_fields = ("name", "email", "event__title")
    raw_id_fields = ("event", "party")
    readonly_fields = ("responded_at", "created_at")


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ("number", "channel", "direction", "subject", "party", "occurred_at", "owner", "tenant")
    list_filter = ("channel", "direction", "logged_via", "tenant")
    search_fields = ("number", "subject", "body")
    raw_id_fields = ("party", "related_opportunity", "related_case")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("party", "industry", "phone", "employee_count", "owner", "tenant")
    list_filter = ("industry", "tenant")
    search_fields = ("party__name", "phone", "email")
    raw_id_fields = ("party", "parent_account")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("party", "owner", "tenant")


@admin.register(ContactProfile)
class ContactProfileAdmin(admin.ModelAdmin):
    list_display = ("party", "job_title", "department", "phone", "account", "owner", "tenant")
    list_filter = ("department", "tenant")
    search_fields = ("party__name", "job_title", "phone", "email")
    raw_id_fields = ("party", "account")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("party", "account", "owner", "tenant")


# ===== Module 1 Extension — Sub-modules 1.7–1.12 =============================
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("number", "category", "amount", "status", "submitted_by", "opportunity", "tenant")
    list_filter = ("status", "category", "tenant")
    search_fields = ("number", "description")
    raw_id_fields = ("opportunity", "project")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(CrmProject)
class CrmProjectAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "account", "status", "start_date", "end_date", "owner", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "name")
    raw_id_fields = ("account", "source_opportunity")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(CrmMilestone)
class CrmMilestoneAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "project", "kind", "status", "due_date", "assignee", "tenant")
    list_filter = ("kind", "status", "tenant")
    search_fields = ("number", "title")
    raw_id_fields = ("project", "parent")
    readonly_fields = ("number", "completed_at", "created_at", "updated_at")


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "employee", "date", "hours", "is_billable", "status", "tenant")
    list_filter = ("status", "is_billable", "tenant")
    search_fields = ("number", "description")
    raw_id_fields = ("project", "milestone", "client")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(DocTemplate)
class DocTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "template_type", "is_active", "owner", "tenant")
    list_filter = ("template_type", "is_active", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(ContractDocument)
class ContractDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "template", "status", "current_version", "owner", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "name")
    raw_id_fields = ("template", "opportunity", "account")
    readonly_fields = ("number", "signed_at", "created_at", "updated_at")


@admin.register(SignerRecord)
class SignerRecordAdmin(admin.ModelAdmin):
    list_display = ("contract", "signer_name", "signer_email", "order", "signed_at", "tenant")
    list_filter = ("tenant",)
    search_fields = ("signer_name", "signer_email")
    raw_id_fields = ("contract", "signer_party")
    readonly_fields = ("token", "viewed_at", "signed_at", "declined_at", "ip_address", "created_at")


@admin.register(WorkflowRule)
class WorkflowRuleAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "trigger_entity", "trigger_event", "is_active", "owner", "tenant")
    list_filter = ("trigger_entity", "trigger_event", "is_active", "tenant")
    search_fields = ("number", "name")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(WorkflowLog)
class WorkflowLogAdmin(admin.ModelAdmin):
    list_display = ("rule", "record_label", "status", "fired_at", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("record_label", "error_msg")
    raw_id_fields = ("rule",)
    readonly_fields = ("rule", "record_label", "fired_at", "status", "error_msg", "tenant")


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "subject", "approver", "status", "created_at", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "subject", "record_label")
    raw_id_fields = ("rule", "approver", "requested_by")
    readonly_fields = ("number", "approved_at", "rejected_at", "created_at", "updated_at")


@admin.register(OnboardingPlan)
class OnboardingPlanAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "account", "status", "target_date", "owner", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "name")
    raw_id_fields = ("account",)
    readonly_fields = ("number", "completed_at", "created_at", "updated_at")


@admin.register(OnboardingStep)
class OnboardingStepAdmin(admin.ModelAdmin):
    list_display = ("plan", "order", "title", "assignee", "due_date", "completed_at", "tenant")
    list_filter = ("tenant",)
    search_fields = ("title",)
    raw_id_fields = ("plan",)
    readonly_fields = ("completed_at", "created_at")


@admin.register(HealthScore)
class HealthScoreAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "score", "tier", "computed_at", "tenant")
    list_filter = ("tier", "tenant")
    search_fields = ("number", "account__name")
    raw_id_fields = ("account",)
    readonly_fields = ("number", "computed_at", "created_at", "updated_at")


@admin.register(HealthScoreConfig)
class HealthScoreConfigAdmin(admin.ModelAdmin):
    list_display = ("tenant", "weight_tickets", "weight_nps", "weight_tasks",
                    "weight_engagement", "red_threshold", "yellow_threshold")
    readonly_fields = ("updated_at",)


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "survey_type", "score", "classification",
                    "sent_at", "responded_at", "tenant")
    list_filter = ("survey_type", "classification", "trigger", "tenant")
    search_fields = ("number", "feedback_text")
    raw_id_fields = ("account", "contact", "related_case")
    readonly_fields = ("number", "classification", "token", "responded_at", "created_at", "updated_at")


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "sku", "on_hand_qty", "reorder_level", "is_active", "tenant")
    list_filter = ("is_active", "tenant")
    search_fields = ("number", "name", "sku")
    readonly_fields = ("number", "created_at", "updated_at")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "vendor", "status", "order_date", "total_amount", "owner", "tenant")
    list_filter = ("status", "tenant")
    search_fields = ("number", "vendor__name", "notes")
    raw_id_fields = ("vendor",)
    readonly_fields = ("number", "total_amount", "received_at", "created_at", "updated_at")


@admin.register(PurchaseOrderLine)
class PurchaseOrderLineAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "item_name", "quantity", "unit_price", "order", "tenant")
    list_filter = ("tenant",)
    search_fields = ("item_name",)
    raw_id_fields = ("purchase_order", "product")
    readonly_fields = ("created_at",)


@admin.register(PartnerPortalAccess)
class PartnerPortalAccessAdmin(admin.ModelAdmin):
    list_display = ("number", "partner_party", "portal_user", "access_level", "is_active", "tenant")
    list_filter = ("access_level", "is_active", "tenant")
    search_fields = ("number", "partner_party__name", "portal_user__username")
    raw_id_fields = ("partner_party", "portal_user")
    readonly_fields = ("number", "accepted_at", "created_at", "updated_at")


# ===== 1.6 Analytics & Reporting ===========================================

class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    fields = ("title", "metric", "chart_type", "date_range", "size", "position")


@admin.register(AnalyticsDashboard)
class AnalyticsDashboardAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "owner", "is_shared", "is_default", "layout", "tenant")
    list_filter = ("is_shared", "is_default", "layout", "tenant")
    search_fields = ("number", "name", "description")
    raw_id_fields = ("owner",)
    readonly_fields = ("number", "created_at", "updated_at")
    inlines = [DashboardWidgetInline]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ("title", "dashboard", "metric", "chart_type", "date_range", "size", "position", "tenant")
    list_filter = ("chart_type", "date_range", "tenant")
    search_fields = ("title",)
    raw_id_fields = ("dashboard",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AnalyticsReport)
class AnalyticsReportAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "report_type", "date_range", "group_by", "is_favorite", "owner", "tenant")
    list_filter = ("report_type", "is_favorite", "tenant")
    search_fields = ("number", "name", "description")
    raw_id_fields = ("owner",)
    readonly_fields = ("number", "last_run_at", "created_at", "updated_at")


@admin.register(ReportSnapshot)
class ReportSnapshotAdmin(admin.ModelAdmin):
    list_display = ("title", "report", "generated_by", "generated_at", "tenant")
    list_filter = ("tenant",)
    search_fields = ("title", "report__name")
    raw_id_fields = ("report", "generated_by")
    readonly_fields = ("generated_at",)
