"""CRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-set fields (``resolved_at``/``completed_at``/``views_count``/``converted_party``).
"""
from apps.core.forms import TenantModelForm

from .models import Campaign, Case, CrmTask, KnowledgeArticle, Lead, Opportunity


class LeadForm(TenantModelForm):
    class Meta:
        model = Lead
        fields = ["name", "company", "title", "email", "phone", "source", "rating",
                  "status", "score", "est_value", "owner", "description"]


class OpportunityForm(TenantModelForm):
    class Meta:
        model = Opportunity
        fields = ["name", "account", "primary_contact", "stage", "amount", "probability",
                  "close_date", "owner", "source_lead", "campaign", "next_step", "description"]


class CampaignForm(TenantModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "type", "status", "start_date", "end_date", "budget_planned",
                  "budget_actual", "expected_revenue", "actual_revenue", "target_size",
                  "owner", "description"]


class CaseForm(TenantModelForm):
    class Meta:
        model = Case
        fields = ["subject", "account", "contact", "type", "priority", "status", "origin",
                  "owner", "due_at", "description"]


class KnowledgeArticleForm(TenantModelForm):
    class Meta:
        model = KnowledgeArticle
        fields = ["title", "category", "body", "visibility", "status", "owner"]


class CrmTaskForm(TenantModelForm):
    class Meta:
        model = CrmTask
        fields = ["subject", "type", "priority", "status", "due_date", "owner", "party",
                  "related_opportunity", "description"]
