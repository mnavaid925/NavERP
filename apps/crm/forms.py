"""CRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-set fields (``resolved_at``/``completed_at``/``views_count``/``converted_party``).
"""
import os

from django import forms

from apps.core.forms import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES, TenantModelForm
from apps.core.models import Party

from .models import (
    AccountProfile,
    Campaign,
    CampaignMember,
    Case,
    CaseComment,
    ContactProfile,
    CrmTask,
    CustomerPortalAccess,
    EmailCampaign,
    EmailTemplate,
    KbCategory,
    KnowledgeArticle,
    LandingPage,
    Lead,
    Opportunity,
    OpportunitySplit,
    PriceBook,
    Product,
    Quote,
    QuoteLine,
    SalesQuota,
    SlaPolicy,
    Territory,
)


class LeadForm(TenantModelForm):
    class Meta:
        model = Lead
        fields = ["name", "company", "title", "email", "phone", "source", "rating",
                  "status", "score", "est_value", "owner", "description"]


class OpportunityForm(TenantModelForm):
    class Meta:
        model = Opportunity
        # lost_at + stage_changed_at are system-stamped in Opportunity.save() — excluded.
        fields = ["name", "account", "primary_contact", "stage", "forecast_category", "amount",
                  "probability", "close_date", "competitor", "loss_reason", "territory", "owner",
                  "source_lead", "campaign", "next_step", "description"]


# ===== 1.2 Sales Force Automation (recreated) ===============================
class TerritoryForm(TenantModelForm):
    class Meta:
        model = Territory
        fields = ["name", "region", "segment", "parent", "manager", "is_active", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A territory can't be its own parent.
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)


class ProductForm(TenantModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "product_type", "unit_price", "cost", "tax_pct",
                  "is_active", "description"]


class PriceBookForm(TenantModelForm):
    class Meta:
        model = PriceBook
        fields = ["name", "currency_code", "region", "tier", "price_adjustment_pct",
                  "is_default", "is_active", "description"]


class QuoteForm(TenantModelForm):
    class Meta:
        model = Quote
        # WARNING: status + subtotal/tax_total/total + sent_at/accepted_at are system-managed
        # (set only by recalc_totals() and the quote_send/_accept/_decline actions). Excluded so a
        # member can't forge a total, back-date a send, or self-accept a quote via POST.
        fields = ["name", "opportunity", "account", "price_book", "valid_until",
                  "currency_code", "discount_pct", "terms", "owner"]
        widgets = {"terms": forms.Textarea(attrs={"rows": 4})}


class QuoteLineForm(TenantModelForm):
    """Inline on the quote detail page; tenant/quote/order set in the view."""

    class Meta:
        model = QuoteLine
        fields = ["product", "description", "quantity", "unit_price", "discount_pct", "tax_pct"]


class OpportunitySplitForm(TenantModelForm):
    """Inline on the opportunity detail page; tenant/opportunity set in the view."""

    class Meta:
        model = OpportunitySplit
        fields = ["user", "split_type", "percentage", "notes"]


class SalesQuotaForm(TenantModelForm):
    class Meta:
        model = SalesQuota
        fields = ["owner", "territory", "period_type", "period_year", "period_number",
                  "target_amount", "notes"]

    def clean(self):
        # Block a duplicate quota at the form level so the user gets a friendly error instead of
        # an IntegrityError 500 — also covers the null-territory case the DB constraint won't catch.
        cleaned = super().clean()
        if self.tenant is None:
            return cleaned
        qs = SalesQuota.objects.filter(
            tenant=self.tenant, owner=cleaned.get("owner"), territory=cleaned.get("territory"),
            period_type=cleaned.get("period_type"), period_year=cleaned.get("period_year"),
            period_number=cleaned.get("period_number"))
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "A quota already exists for this rep, territory and period — edit that one instead.")
        return cleaned


class CampaignForm(TenantModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "type", "objective", "status", "parent_campaign", "start_date",
                  "end_date", "budget_planned", "budget_actual", "expected_revenue",
                  "actual_revenue", "target_size", "utm_source", "utm_medium",
                  "utm_campaign", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A campaign can't be its own parent program.
        if self.instance and self.instance.pk:
            self.fields["parent_campaign"].queryset = self.fields["parent_campaign"].queryset.exclude(pk=self.instance.pk)


# ===== 1.3 Marketing Automation (recreated) =================================
class CampaignMemberForm(TenantModelForm):
    """Target-list membership. ``responded_at`` is system-set (stamped in save())."""

    class Meta:
        model = CampaignMember
        fields = ["campaign", "party", "lead", "member_name", "member_email", "status", "notes"]


class EmailTemplateForm(TenantModelForm):
    class Meta:
        model = EmailTemplate
        fields = ["name", "category", "subject", "preheader", "body", "from_name",
                  "from_email", "is_active", "owner"]
        widgets = {"body": forms.Textarea(attrs={"rows": 16})}


class EmailCampaignForm(TenantModelForm):
    class Meta:
        model = EmailCampaign
        # WARNING: sent_at + every *_count metric are system-managed (set only by the
        # emailcampaign_send action / seeder). Excluded so a user can't fabricate engagement
        # numbers or back-date a send via POST. `status` is ALSO excluded: draft→sent happens
        # only through the admin-gated emailcampaign_send action — accepting status from POST
        # would let a member mark a blast "sent" (sent_at NULL, counts 0), corrupt metrics, and
        # permanently lock out the send workflow.
        fields = ["name", "campaign", "template", "variant_template", "is_ab_test",
                  "send_type", "scheduled_at", "owner"]


class LandingPageForm(TenantModelForm):
    class Meta:
        model = LandingPage
        # WARNING: public_token (unguessable URL key) + submission_count are system-managed —
        # excluded so they can't be forged/reset via POST. `status` is excluded too: making a
        # page public (status=published) exposes a live web-to-lead URL, so that transition is
        # gated to admins via the dedicated landingpage_publish action, not this content form.
        fields = ["name", "campaign", "slug", "headline", "subheadline", "body",
                  "capture_phone", "capture_company", "capture_message", "cta_label",
                  "routing_owner", "lead_source", "owner"]
        widgets = {"body": forms.Textarea(attrs={"rows": 8})}


class PublicLeadForm(forms.Form):
    """The capture form on a public LandingPage — a plain Form (no tenant binding, no model
    mass-assignment). The view decides which optional fields are required from the page's
    capture toggles and builds the FormSubmission/Lead itself."""

    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "form-input"}))
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={"class": "form-input"}))
    phone = forms.CharField(max_length=40, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    company = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"class": "form-input"}))
    message = forms.CharField(max_length=2000, required=False,
                              widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4}))


class CaseForm(TenantModelForm):
    class Meta:
        model = Case
        # WARNING: first_response_due/first_responded_at/resolution_due/closed_at/public_token +
        # satisfaction_* are system-managed (SLA save() / portal / public CSAT page). Excluded so a
        # member can't forge SLA timers, back-date a close, or fake a satisfaction score via POST.
        fields = ["subject", "account", "contact", "type", "priority", "status", "origin",
                  "sla_policy", "owner", "due_at", "description"]


class KnowledgeArticleForm(TenantModelForm):
    class Meta:
        model = KnowledgeArticle
        # helpful_count/not_helpful_count/public_token/views_count are system-managed — excluded.
        fields = ["title", "kb_category", "category", "slug", "body", "visibility", "status", "owner"]


# ===== 1.4 Customer Service & Support (recreated) ===========================
class SlaPolicyForm(TenantModelForm):
    class Meta:
        model = SlaPolicy
        fields = ["name", "description", "is_active", "is_default",
                  "response_low", "response_medium", "response_high", "response_critical",
                  "resolution_low", "resolution_medium", "resolution_high", "resolution_critical"]


class KbCategoryForm(TenantModelForm):
    class Meta:
        model = KbCategory
        fields = ["name", "description", "slug", "parent", "order", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A category can't be its own parent.
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)


class CustomerPortalAccessForm(TenantModelForm):
    class Meta:
        model = CustomerPortalAccess
        # accepted_at is system-set when the customer activates — excluded.
        fields = ["customer_party", "portal_user", "can_submit_cases", "is_active"]


class CaseCommentForm(TenantModelForm):
    """Inline on the case detail page; tenant/case/author set in the view."""

    class Meta:
        model = CaseComment
        fields = ["body", "is_public"]


class PublicSatisfactionForm(forms.Form):
    """CSAT on the public case-status page — a plain Form (no tenant binding)."""

    rating = forms.ChoiceField(choices=[(i, str(i)) for i in range(1, 6)],
                               widget=forms.Select(attrs={"class": "form-select"}))
    comment = forms.CharField(max_length=2000, required=False,
                              widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))


class PublicCommentForm(forms.Form):
    """A public reply on the case-status page / portal — plain Form, length-capped."""

    body = forms.CharField(max_length=4000,
                           widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))


class CrmTaskForm(TenantModelForm):
    class Meta:
        model = CrmTask
        fields = ["subject", "type", "priority", "status", "due_date", "owner", "party",
                  "related_opportunity", "description"]


# Accounts & Contacts span two tables: the shared core.Party identity (name/tax_id) + the CRM
# profile. These forms are ModelForms on the *profile* with the Party fields declared inline; the
# view creates/updates the Party and links the profile.
class AccountForm(TenantModelForm):
    name = forms.CharField(max_length=255, label="Account name")
    tax_id = forms.CharField(max_length=64, required=False, label="Tax ID")
    # Explicit form field with the permanent assume_scheme API (avoids the Django 6.0 URLField
    # default-scheme deprecation warning).
    website = forms.URLField(required=False, assume_scheme="https")

    field_order = ["name", "tax_id", "industry", "website", "phone", "email", "annual_revenue",
                   "employee_count", "parent_account", "address_line", "address_city",
                   "address_state", "address_postal", "address_country", "source", "owner",
                   "description"]

    class Meta:
        model = AccountProfile
        fields = ["industry", "website", "phone", "email", "annual_revenue", "employee_count",
                  "parent_account", "address_line", "address_city", "address_state",
                  "address_postal", "address_country", "source", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            qs = Party.objects.filter(tenant=self.tenant, kind="organization")
            if self.instance and self.instance.party_id:
                qs = qs.exclude(pk=self.instance.party_id)  # an account can't be its own parent
            self.fields["parent_account"].queryset = qs.order_by("name")


class ContactForm(TenantModelForm):
    name = forms.CharField(max_length=255, label="Contact name")
    linkedin = forms.URLField(required=False, assume_scheme="https")

    field_order = ["name", "job_title", "department", "email", "phone", "mobile", "account",
                   "address_line", "address_city", "address_state", "address_postal",
                   "address_country", "linkedin", "source", "owner", "description"]

    class Meta:
        model = ContactProfile
        fields = ["job_title", "department", "email", "phone", "mobile", "account",
                  "address_line", "address_city", "address_state", "address_postal",
                  "address_country", "linkedin", "source", "owner", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["account"].queryset = Party.objects.filter(
                tenant=self.tenant, kind="organization").order_by("name")


# ============================================================================
# ===== Module 1 Extension — Sub-modules 1.7–1.12 forms ======================
# ============================================================================
# TenantModelForm auto-scopes every FK/OneToOne dropdown (incl. User FKs — User has a
# tenant field) to the active tenant, so these need no custom __init__ for scoping.
from .models import (  # noqa: E402  (after the base forms above)
    ApprovalRequest,
    ContractDocument,
    CrmMilestone,
    CrmProject,
    DocTemplate,
    Expense,
    HealthScore,
    HealthScoreConfig,
    OnboardingPlan,
    OnboardingStep,
    PartnerPortalAccess,
    ProductStock,
    PurchaseOrder,
    PurchaseOrderLine,
    SignerRecord,
    Survey,
    Timesheet,
    WorkflowRule,
)


class ExpenseForm(TenantModelForm):
    class Meta:
        model = Expense
        # WARNING: status/submitted_by/approved_by are system-managed and MUST NOT be here —
        # submitted_by is set in the view; status/approved_by only by the
        # @tenant_admin_required approve/reject actions. Accepting them from POST would let any
        # member self-approve an expense.
        fields = ["opportunity", "project", "category", "amount", "currency_code",
                  "expense_date", "description", "receipt"]

    def clean_receipt(self):
        # WARNING: without an extension allowlist + size cap, a member could upload .html/.svg
        # and have it served same-origin from MEDIA_ROOT (stored XSS). Mirrors core.DocumentForm.
        f = self.cleaned_data.get("receipt")
        if f and hasattr(f, "name"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(f, "size", 0) and f.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError("File exceeds the 20 MB limit.")
        return f


class CrmProjectForm(TenantModelForm):
    class Meta:
        model = CrmProject
        fields = ["name", "account", "source_opportunity", "status", "start_date",
                  "end_date", "budget", "owner", "description"]


class CrmMilestoneForm(TenantModelForm):
    class Meta:
        model = CrmMilestone
        fields = ["project", "title", "kind", "status", "assignee", "start_date",
                  "due_date", "order", "parent", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A milestone can't be its own parent.
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)


class TimesheetForm(TenantModelForm):
    class Meta:
        model = Timesheet
        # approved_by is system-set (not forgeable via the form); status stays editable as the
        # timesheet's draft→submitted→approved workflow has no separate action view.
        fields = ["project", "milestone", "employee", "client", "date", "hours",
                  "description", "is_billable", "status"]


class DocTemplateForm(TenantModelForm):
    class Meta:
        model = DocTemplate
        fields = ["name", "template_type", "body", "is_active", "owner"]
        widgets = {"body": forms.Textarea(attrs={"rows": 18})}


class ContractDocumentForm(TenantModelForm):
    class Meta:
        model = ContractDocument
        # WARNING: status/current_version are system-managed (the public signing flow + system
        # transitions own them). Excluded so a member can't forge a "signed" contract via POST.
        fields = ["name", "template", "opportunity", "account",
                  "body_snapshot", "expires_at", "owner"]
        widgets = {"body_snapshot": forms.Textarea(attrs={"rows": 12})}


class SignerRecordForm(TenantModelForm):
    """Inline on the ContractDocument detail page; tenant/contract/token set in the view."""

    class Meta:
        model = SignerRecord
        fields = ["signer_party", "signer_name", "signer_email"]  # order auto-assigned in the view


class WorkflowRuleForm(TenantModelForm):
    class Meta:
        model = WorkflowRule
        fields = ["name", "is_active", "trigger_entity", "trigger_event", "trigger_field",
                  "trigger_value", "conditions", "actions", "delay_value", "delay_unit", "owner"]
        widgets = {"conditions": forms.Textarea(attrs={"rows": 4}),
                   "actions": forms.Textarea(attrs={"rows": 4})}


class ApprovalRequestForm(TenantModelForm):
    class Meta:
        model = ApprovalRequest
        fields = ["rule", "subject", "record_label", "approver", "requested_by",
                  "threshold_field", "threshold_value"]


class OnboardingPlanForm(TenantModelForm):
    class Meta:
        model = OnboardingPlan
        fields = ["account", "name", "status", "target_date", "owner", "description"]


class OnboardingStepForm(TenantModelForm):
    """Inline on the OnboardingPlan detail page; tenant/plan set in the view."""

    class Meta:
        model = OnboardingStep
        fields = ["title", "description", "assignee", "due_date"]  # order auto-assigned in the view


class HealthScoreForm(TenantModelForm):
    """Manual score entry/override; breakdown + computed_at are system-set."""

    class Meta:
        model = HealthScore
        fields = ["account", "score", "tier"]

    def clean_account(self):
        # One score row per account (unique_together) — block a duplicate at the form
        # level so a manual create returns a friendly error instead of an IntegrityError 500.
        account = self.cleaned_data.get("account")
        if account is not None and self.tenant is not None:
            qs = HealthScore.objects.filter(tenant=self.tenant, account=account)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A health score already exists for this account — edit or recompute it instead.")
        return account


class HealthScoreConfigForm(TenantModelForm):
    class Meta:
        model = HealthScoreConfig
        fields = ["weight_tickets", "weight_nps", "weight_tasks", "weight_engagement",
                  "red_threshold", "yellow_threshold"]


class SurveyForm(TenantModelForm):
    class Meta:
        model = Survey
        fields = ["account", "contact", "survey_type", "trigger", "related_case",
                  "score", "feedback_text", "sent_at"]


class ProductStockForm(TenantModelForm):
    class Meta:
        model = ProductStock
        # WARNING: on_hand_qty is system-managed via PO receipt (crm_po_receive) — excluded so
        # members can't directly rewrite inventory counts that the partner portal exposes.
        fields = ["name", "sku", "reorder_level", "unit_cost", "is_active", "description"]


class PurchaseOrderForm(TenantModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["vendor", "status", "order_date", "expected_date", "notes", "owner"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Vendors are organization Parties.
        if self.tenant is not None:
            self.fields["vendor"].queryset = Party.objects.filter(
                tenant=self.tenant, kind="organization").order_by("name")


class PurchaseOrderLineForm(TenantModelForm):
    """Inline on the PurchaseOrder form/detail; tenant/purchase_order set in the view."""

    class Meta:
        model = PurchaseOrderLine
        fields = ["item_name", "product", "quantity", "unit_price"]  # order auto-assigned in the view


class PartnerPortalAccessForm(TenantModelForm):
    class Meta:
        model = PartnerPortalAccess
        fields = ["partner_party", "portal_user", "access_level", "can_view_stock",
                  "can_register_leads", "is_active"]
