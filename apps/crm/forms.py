"""CRM forms — one ``TenantModelForm`` per model. The shared base
(``apps.core.forms.TenantModelForm``) auto-scopes every FK dropdown to the active tenant and
applies the theme widget classes. Excluded everywhere: ``tenant``, the auto ``number``, and
system-set fields (``resolved_at``/``completed_at``/``views_count``/``converted_party``).
"""
from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import Party

from .models import (
    AccountProfile,
    Campaign,
    Case,
    ContactProfile,
    CrmTask,
    KnowledgeArticle,
    Lead,
    Opportunity,
)


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


# Accounts & Contacts span two tables: the shared core.Party identity (name/tax_id) + the CRM
# profile. These forms are ModelForms on the *profile* with the Party fields declared inline; the
# view creates/updates the Party and links the profile.
class AccountForm(TenantModelForm):
    name = forms.CharField(max_length=255, label="Account name")
    tax_id = forms.CharField(max_length=64, required=False, label="Tax ID")

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
