"""Tests for CRM forms: required fields, excluded system fields, tenant-scoped FK querysets."""
import pytest

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ System fields excluded
class TestLeadFormExclusions:
    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import LeadForm
        form = LeadForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import LeadForm
        form = LeadForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_converted_party_not_in_fields(self, tenant_a):
        from apps.crm.forms import LeadForm
        form = LeadForm(tenant=tenant_a)
        assert "converted_party" not in form.fields

    def test_created_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import LeadForm
        form = LeadForm(tenant=tenant_a)
        assert "created_at" not in form.fields


class TestOpportunityFormExclusions:
    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestCaseFormExclusions:
    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_resolved_at_not_in_fields(self, tenant_a):
        """resolved_at is system-set by Case.save(); must never appear in user form."""
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        assert "resolved_at" not in form.fields


class TestKnowledgeArticleFormExclusions:
    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_views_count_not_in_fields(self, tenant_a):
        """views_count is system-set on detail view; must not appear in user form."""
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "views_count" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestCrmTaskFormExclusions:
    def test_number_not_in_fields(self, tenant_a):
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm(tenant=tenant_a)
        assert "number" not in form.fields

    def test_completed_at_not_in_fields(self, tenant_a):
        """completed_at is system-set by CrmTask.save(); must not appear in user form."""
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm(tenant=tenant_a)
        assert "completed_at" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm(tenant=tenant_a)
        assert "tenant" not in form.fields


# ------------------------------------------------------------------ Valid form submissions
class TestLeadFormValid:
    def test_valid_minimal_lead(self, tenant_a):
        from apps.crm.forms import LeadForm
        form = LeadForm({"name": "Test Lead", "status": "new", "source": "web",
                         "rating": "warm", "score": 0, "est_value": "0.00"}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.crm.forms import LeadForm
        form = LeadForm({"name": "", "status": "new"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors


class TestOpportunityFormValid:
    def test_valid_minimal_opportunity(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm({
            "name": "Test Opp",
            "stage": "prospecting",
            "amount": "0.00",
            "probability": 10,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm({"name": "", "stage": "prospecting"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors


class TestCampaignFormValid:
    def test_valid_minimal_campaign(self, tenant_a):
        from apps.crm.forms import CampaignForm
        form = CampaignForm({
            "name": "Test Campaign",
            "type": "email",
            "status": "planned",
            "budget_planned": "0.00",
            "budget_actual": "0.00",
            "expected_revenue": "0.00",
            "actual_revenue": "0.00",
            "target_size": 0,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.crm.forms import CampaignForm
        form = CampaignForm({"name": "", "type": "email", "status": "planned"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors


class TestCaseFormValid:
    def test_valid_minimal_case(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm({
            "subject": "Test Case",
            "type": "question",
            "priority": "medium",
            "status": "new",
            "origin": "email",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_subject_required(self, tenant_a):
        from apps.crm.forms import CaseForm
        form = CaseForm({"subject": "", "status": "new"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "subject" in form.errors


class TestKnowledgeArticleFormValid:
    def test_valid_minimal_article(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm({
            "title": "Test Article",
            "visibility": "internal",
            "status": "draft",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_title_required(self, tenant_a):
        from apps.crm.forms import KnowledgeArticleForm
        form = KnowledgeArticleForm({"title": "", "visibility": "internal"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "title" in form.errors


class TestCrmTaskFormValid:
    def test_valid_minimal_task(self, tenant_a):
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm({
            "subject": "Test Task",
            "type": "todo",
            "priority": "medium",
            "status": "open",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_subject_required(self, tenant_a):
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm({"subject": "", "status": "open"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "subject" in form.errors


# ------------------------------------------------------------------ FK scoping (multi-tenant safety)
class TestFKTenantScoping:
    """A form for tenant A must NOT accept tenant B's Party/Lead/Campaign as a valid FK."""

    def test_opportunity_account_scoped_to_tenant(self, tenant_a, account_a, account_b):
        """OpportunityForm for tenant_a must exclude account_b from the account queryset."""
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        account_pks = list(form.fields["account"].queryset.values_list("pk", flat=True))
        assert account_a.pk in account_pks
        assert account_b.pk not in account_pks

    def test_opportunity_cross_tenant_account_fails_validation(self, tenant_a, account_b):
        """Submitting a cross-tenant account pk must make the form invalid."""
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm({
            "name": "Cross-Tenant Opp",
            "stage": "prospecting",
            "amount": "0.00",
            "probability": 10,
            "account": account_b.pk,  # belongs to tenant_b
        }, tenant=tenant_a)
        assert not form.is_valid()

    def test_opportunity_owner_scoped_to_tenant(self, tenant_a, admin_user, admin_b):
        """Owner queryset must only show users from tenant_a."""
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        owner_pks = list(form.fields["owner"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in owner_pks
        assert admin_b.pk not in owner_pks

    def test_case_account_scoped_to_tenant(self, tenant_a, account_a, account_b):
        """CaseForm for tenant_a must exclude account_b."""
        from apps.crm.forms import CaseForm
        form = CaseForm(tenant=tenant_a)
        account_pks = list(form.fields["account"].queryset.values_list("pk", flat=True))
        assert account_a.pk in account_pks
        assert account_b.pk not in account_pks

    def test_task_related_opportunity_scoped_to_tenant(self, tenant_a, opportunity_a, opportunity_b):
        """CrmTaskForm for tenant_a must not offer opportunity_b in related_opportunity."""
        from apps.crm.forms import CrmTaskForm
        form = CrmTaskForm(tenant=tenant_a)
        opp_pks = list(form.fields["related_opportunity"].queryset.values_list("pk", flat=True))
        assert opportunity_a.pk in opp_pks
        assert opportunity_b.pk not in opp_pks

    def test_opportunity_source_lead_scoped_to_tenant(self, tenant_a, lead_a, lead_b):
        """OpportunityForm for tenant_a must not include lead_b in source_lead choices."""
        from apps.crm.forms import OpportunityForm
        form = OpportunityForm(tenant=tenant_a)
        lead_pks = list(form.fields["source_lead"].queryset.values_list("pk", flat=True))
        assert lead_a.pk in lead_pks
        assert lead_b.pk not in lead_pks
