"""Tests for CRM views: CRUD, list/filter, detail, delete, overview, account/contact lenses."""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ Leads
class TestLeadListView:
    def test_list_200(self, client_a, lead_a):
        resp = client_a.get(reverse("crm:lead_list"))
        assert resp.status_code == 200

    def test_list_shows_own_lead(self, client_a, lead_a):
        resp = client_a.get(reverse("crm:lead_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lead_a.pk in pks

    def test_list_excludes_other_tenant_lead(self, client_a, lead_a, lead_b):
        resp = client_a.get(reverse("crm:lead_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lead_b.pk not in pks

    def test_search_filters_results(self, client_a, lead_a, tenant_a):
        from apps.crm.models import Lead
        Lead.objects.create(tenant=tenant_a, name="Unrelated Person")
        resp = client_a.get(reverse("crm:lead_list") + "?q=Jane")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lead_a.pk in pks
        assert all("jane" in str(obj.name).lower() or "jane" in str(obj.company).lower()
                   or "jane" in str(obj.email).lower()
                   for obj in resp.context["object_list"])

    def test_status_filter(self, client_a, lead_a, tenant_a):
        from apps.crm.models import Lead
        Lead.objects.create(tenant=tenant_a, name="Contacted Lead", status="contacted")
        resp = client_a.get(reverse("crm:lead_list") + "?status=contacted")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "contacted" for s in statuses)
        assert "new" not in statuses

    def test_context_has_status_choices(self, client_a):
        resp = client_a.get(reverse("crm:lead_list"))
        assert "status_choices" in resp.context

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:lead_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestLeadCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:lead_create"))
        assert resp.status_code == 200

    def test_post_creates_lead_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import Lead
        resp = client_a.post(reverse("crm:lead_create"), {
            "name": "New Lead",
            "status": "new",
            "source": "web",
            "rating": "warm",
            "score": 0,
            "est_value": "0.00",
        })
        assert resp.status_code == 302
        lead = Lead.objects.filter(tenant=tenant_a, name="New Lead").first()
        assert lead is not None
        assert lead.number.startswith("LEAD-")

    def test_post_auto_assigns_number(self, client_a, tenant_a):
        from apps.crm.models import Lead
        client_a.post(reverse("crm:lead_create"), {
            "name": "Numbered Lead",
            "status": "new",
            "source": "web",
            "rating": "warm",
            "score": 0,
            "est_value": "0.00",
        })
        lead = Lead.objects.get(tenant=tenant_a, name="Numbered Lead")
        assert lead.number == "LEAD-00001"

    def test_anon_redirects(self, client):
        resp = client.post(reverse("crm:lead_create"), {})
        assert resp.status_code == 302


class TestLeadDetailView:
    def test_detail_200(self, client_a, lead_a):
        resp = client_a.get(reverse("crm:lead_detail", args=[lead_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, lead_a):
        resp = client_a.get(reverse("crm:lead_detail", args=[lead_a.pk]))
        assert resp.context["obj"].pk == lead_a.pk

    def test_anon_redirects(self, client, lead_a):
        resp = client.get(reverse("crm:lead_detail", args=[lead_a.pk]))
        assert resp.status_code == 302


class TestLeadEditView:
    def test_get_200(self, client_a, lead_a):
        resp = client_a.get(reverse("crm:lead_edit", args=[lead_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_lead(self, client_a, lead_a):
        resp = client_a.post(reverse("crm:lead_edit", args=[lead_a.pk]), {
            "name": "Updated Jane",
            "status": "contacted",
            "source": "referral",
            "rating": "hot",
            "score": 50,
            "est_value": "2000.00",
        })
        assert resp.status_code == 302
        lead_a.refresh_from_db()
        assert lead_a.name == "Updated Jane"
        assert lead_a.status == "contacted"


class TestLeadDeleteView:
    def test_post_deletes_lead(self, client_a, lead_a):
        from apps.crm.models import Lead
        pk = lead_a.pk
        resp = client_a.post(reverse("crm:lead_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Lead.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, lead_a):
        """lead_delete is @require_POST; GET must return 405."""
        resp = client_a.get(reverse("crm:lead_delete", args=[lead_a.pk]))
        assert resp.status_code == 405

    def test_anon_redirects(self, client, lead_a):
        resp = client.post(reverse("crm:lead_delete", args=[lead_a.pk]))
        assert resp.status_code == 302


# ================================================================ Opportunities
class TestOpportunityListView:
    def test_list_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_list"))
        assert resp.status_code == 200

    def test_list_shows_own_opportunity(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert opportunity_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, opportunity_a, opportunity_b):
        resp = client_a.get(reverse("crm:opportunity_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert opportunity_b.pk not in pks

    def test_stage_filter(self, client_a, opportunity_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        Opportunity.objects.create(
            tenant=tenant_a, name="Closed Deal", account=account_a,
            stage="closed_won", amount="1000.00", probability=100,
        )
        resp = client_a.get(reverse("crm:opportunity_list") + "?stage=prospecting")
        stages = [obj.stage for obj in resp.context["object_list"]]
        assert all(s == "prospecting" for s in stages)

    def test_account_filter(self, client_a, opportunity_a, tenant_a, account_a):
        from apps.crm.models import Opportunity
        from apps.core.models import Party
        other_account = Party.objects.create(tenant=tenant_a, kind="organization", name="Other Org")
        Opportunity.objects.create(
            tenant=tenant_a, name="Other Deal",
            account=other_account, stage="prospecting",
        )
        resp = client_a.get(reverse("crm:opportunity_list") + f"?account={account_a.pk}")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert opportunity_a.pk in pks
        assert all(obj.account_id == account_a.pk for obj in resp.context["object_list"])

    def test_context_has_stage_choices(self, client_a):
        resp = client_a.get(reverse("crm:opportunity_list"))
        assert "stage_choices" in resp.context

    def test_context_has_accounts(self, client_a, account_a):
        resp = client_a.get(reverse("crm:opportunity_list"))
        assert "accounts" in resp.context


class TestOpportunityCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:opportunity_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a):
        from apps.crm.models import Opportunity
        resp = client_a.post(reverse("crm:opportunity_create"), {
            "name": "New Opp",
            "stage": "prospecting",
            "amount": "0.00",
            "probability": 10,
        })
        assert resp.status_code == 302
        assert Opportunity.objects.filter(tenant=tenant_a, name="New Opp").exists()


class TestOpportunityDetailView:
    def test_detail_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_detail", args=[opportunity_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_detail", args=[opportunity_a.pk]))
        assert resp.context["obj"].pk == opportunity_a.pk


class TestOpportunityEditView:
    def test_get_200(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_edit", args=[opportunity_a.pk]))
        assert resp.status_code == 200

    def test_post_updates(self, client_a, opportunity_a):
        resp = client_a.post(reverse("crm:opportunity_edit", args=[opportunity_a.pk]), {
            "name": "Updated Opp",
            "stage": "qualification",
            "amount": "9000.00",
            "probability": 30,
        })
        assert resp.status_code == 302
        opportunity_a.refresh_from_db()
        assert opportunity_a.name == "Updated Opp"
        assert opportunity_a.stage == "qualification"


class TestOpportunityDeleteView:
    def test_post_deletes(self, client_a, opportunity_a):
        from apps.crm.models import Opportunity
        pk = opportunity_a.pk
        resp = client_a.post(reverse("crm:opportunity_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Opportunity.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, opportunity_a):
        resp = client_a.get(reverse("crm:opportunity_delete", args=[opportunity_a.pk]))
        assert resp.status_code == 405


# ================================================================ Campaigns
class TestCampaignListView:
    def test_list_200(self, client_a, campaign_a):
        resp = client_a.get(reverse("crm:campaign_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, campaign_a):
        resp = client_a.get(reverse("crm:campaign_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert campaign_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, campaign_a, campaign_b):
        resp = client_a.get(reverse("crm:campaign_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert campaign_b.pk not in pks

    def test_status_filter(self, client_a, campaign_a, tenant_a):
        from apps.crm.models import Campaign
        Campaign.objects.create(tenant=tenant_a, name="Active Cam", status="active")
        resp = client_a.get(reverse("crm:campaign_list") + "?status=planned")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "planned" for s in statuses)


class TestCampaignCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:campaign_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.crm.models import Campaign
        resp = client_a.post(reverse("crm:campaign_create"), {
            "name": "Summer Campaign",
            "type": "webinar",
            "status": "planned",
            "budget_planned": "500.00",
            "budget_actual": "0.00",
            "expected_revenue": "0.00",
            "actual_revenue": "0.00",
            "target_size": 0,
        })
        assert resp.status_code == 302
        assert Campaign.objects.filter(tenant=tenant_a, name="Summer Campaign").exists()


class TestCampaignDetailView:
    def test_detail_200(self, client_a, campaign_a):
        resp = client_a.get(reverse("crm:campaign_detail", args=[campaign_a.pk]))
        assert resp.status_code == 200


class TestCampaignEditView:
    def test_post_updates(self, client_a, campaign_a):
        resp = client_a.post(reverse("crm:campaign_edit", args=[campaign_a.pk]), {
            "name": "Updated Promo",
            "type": "social",
            "status": "active",
            "budget_planned": "3000.00",
            "budget_actual": "0.00",
            "expected_revenue": "0.00",
            "actual_revenue": "0.00",
            "target_size": 0,
        })
        assert resp.status_code == 302
        campaign_a.refresh_from_db()
        assert campaign_a.name == "Updated Promo"
        assert campaign_a.status == "active"


class TestCampaignDeleteView:
    def test_post_deletes(self, client_a, campaign_a):
        from apps.crm.models import Campaign
        pk = campaign_a.pk
        resp = client_a.post(reverse("crm:campaign_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Campaign.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, campaign_a):
        resp = client_a.get(reverse("crm:campaign_delete", args=[campaign_a.pk]))
        assert resp.status_code == 405


# ================================================================ Cases
class TestCaseListView:
    def test_list_200(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert case_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, case_a, case_b):
        resp = client_a.get(reverse("crm:case_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert case_b.pk not in pks

    def test_status_filter(self, client_a, case_a, tenant_a):
        from apps.crm.models import Case
        Case.objects.create(tenant=tenant_a, subject="Resolved Case", status="resolved")
        resp = client_a.get(reverse("crm:case_list") + "?status=new")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "new" for s in statuses)

    def test_priority_filter(self, client_a, case_a, tenant_a):
        from apps.crm.models import Case
        Case.objects.create(tenant=tenant_a, subject="High Priority", priority="high", status="new")
        resp = client_a.get(reverse("crm:case_list") + "?priority=medium")
        priorities = [obj.priority for obj in resp.context["object_list"]]
        assert all(p == "medium" for p in priorities)

    def test_context_has_priority_choices(self, client_a):
        resp = client_a.get(reverse("crm:case_list"))
        assert "priority_choices" in resp.context


class TestCaseCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:case_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.crm.models import Case
        resp = client_a.post(reverse("crm:case_create"), {
            "subject": "New Support Ticket",
            "type": "problem",
            "priority": "high",
            "status": "new",
            "origin": "email",
        })
        assert resp.status_code == 302
        assert Case.objects.filter(tenant=tenant_a, subject="New Support Ticket").exists()


class TestCaseDetailView:
    def test_detail_200(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_detail", args=[case_a.pk]))
        assert resp.status_code == 200


class TestCaseEditView:
    def test_post_updates(self, client_a, case_a):
        resp = client_a.post(reverse("crm:case_edit", args=[case_a.pk]), {
            "subject": "Updated Widget",
            "type": "incident",
            "priority": "critical",
            "status": "in_progress",
            "origin": "phone",
        })
        assert resp.status_code == 302
        case_a.refresh_from_db()
        assert case_a.subject == "Updated Widget"
        assert case_a.priority == "critical"


class TestCaseDeleteView:
    def test_post_deletes(self, client_a, case_a):
        from apps.crm.models import Case
        pk = case_a.pk
        resp = client_a.post(reverse("crm:case_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Case.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, case_a):
        resp = client_a.get(reverse("crm:case_delete", args=[case_a.pk]))
        assert resp.status_code == 405


# ================================================================ KnowledgeArticle
class TestKnowledgeArticleListView:
    def test_list_200(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert article_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, article_a, article_b):
        resp = client_a.get(reverse("crm:knowledgearticle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert article_b.pk not in pks

    def test_status_filter(self, client_a, article_a, tenant_a):
        from apps.crm.models import KnowledgeArticle
        KnowledgeArticle.objects.create(tenant=tenant_a, title="Published Art", status="published")
        resp = client_a.get(reverse("crm:knowledgearticle_list") + "?status=draft")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "draft" for s in statuses)


class TestKnowledgeArticleCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:knowledgearticle_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.crm.models import KnowledgeArticle
        resp = client_a.post(reverse("crm:knowledgearticle_create"), {
            "title": "Setup Guide",
            "visibility": "internal",
            "status": "draft",
            "category": "Onboarding",
            "body": "Step 1...",
        })
        assert resp.status_code == 302
        assert KnowledgeArticle.objects.filter(tenant=tenant_a, title="Setup Guide").exists()


class TestKnowledgeArticleDetailView:
    def test_detail_200(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_detail", args=[article_a.pk]))
        assert resp.status_code == 200

    def test_detail_increments_views_count(self, client_a, article_a):
        """Viewing the detail page should increment views_count via F() update."""
        old_count = article_a.views_count
        client_a.get(reverse("crm:knowledgearticle_detail", args=[article_a.pk]))
        article_a.refresh_from_db()
        assert article_a.views_count == old_count + 1

    def test_detail_increments_on_each_visit(self, client_a, article_a):
        client_a.get(reverse("crm:knowledgearticle_detail", args=[article_a.pk]))
        client_a.get(reverse("crm:knowledgearticle_detail", args=[article_a.pk]))
        article_a.refresh_from_db()
        assert article_a.views_count == 2


class TestKnowledgeArticleDeleteView:
    def test_post_deletes(self, client_a, article_a):
        from apps.crm.models import KnowledgeArticle
        pk = article_a.pk
        resp = client_a.post(reverse("crm:knowledgearticle_delete", args=[pk]))
        assert resp.status_code == 302
        assert not KnowledgeArticle.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, article_a):
        resp = client_a.get(reverse("crm:knowledgearticle_delete", args=[article_a.pk]))
        assert resp.status_code == 405


# ================================================================ CRM Tasks
class TestTaskListView:
    def test_list_200(self, client_a, task_a):
        resp = client_a.get(reverse("crm:task_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, task_a):
        resp = client_a.get(reverse("crm:task_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert task_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, task_a, task_b):
        resp = client_a.get(reverse("crm:task_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert task_b.pk not in pks

    def test_status_filter(self, client_a, task_a, tenant_a):
        from apps.crm.models import CrmTask
        CrmTask.objects.create(tenant=tenant_a, subject="Done Task", status="done")
        resp = client_a.get(reverse("crm:task_list") + "?status=open")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "open" for s in statuses)


class TestTaskCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:task_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.crm.models import CrmTask
        resp = client_a.post(reverse("crm:task_create"), {
            "subject": "New Task",
            "type": "call",
            "priority": "high",
            "status": "open",
        })
        assert resp.status_code == 302
        assert CrmTask.objects.filter(tenant=tenant_a, subject="New Task").exists()


class TestTaskDetailView:
    def test_detail_200(self, client_a, task_a):
        resp = client_a.get(reverse("crm:task_detail", args=[task_a.pk]))
        assert resp.status_code == 200


class TestTaskEditView:
    def test_post_updates(self, client_a, task_a):
        resp = client_a.post(reverse("crm:task_edit", args=[task_a.pk]), {
            "subject": "Updated Task",
            "type": "meeting",
            "priority": "low",
            "status": "in_progress",
        })
        assert resp.status_code == 302
        task_a.refresh_from_db()
        assert task_a.subject == "Updated Task"
        assert task_a.status == "in_progress"


class TestTaskDeleteView:
    def test_post_deletes(self, client_a, task_a):
        from apps.crm.models import CrmTask
        pk = task_a.pk
        resp = client_a.post(reverse("crm:task_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CrmTask.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, task_a):
        resp = client_a.get(reverse("crm:task_delete", args=[task_a.pk]))
        assert resp.status_code == 405


# ================================================================ Account / Contact lenses
class TestAccountListView:
    def test_list_200(self, client_a, account_a):
        resp = client_a.get(reverse("crm:account_list"))
        assert resp.status_code == 200

    def test_list_only_shows_own_tenant_orgs(self, client_a, account_a, account_b):
        resp = client_a.get(reverse("crm:account_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert account_a.pk in pks
        assert account_b.pk not in pks


class TestAccountDetailView:
    def test_detail_200(self, client_a, account_a):
        resp = client_a.get(reverse("crm:account_detail", args=[account_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, account_a):
        resp = client_a.get(reverse("crm:account_detail", args=[account_a.pk]))
        assert resp.context["obj"].pk == account_a.pk


class TestContactListView:
    def test_list_200(self, client_a, contact_a):
        resp = client_a.get(reverse("crm:contact_list"))
        assert resp.status_code == 200

    def test_list_only_shows_own_tenant_persons(self, client_a, contact_a, contact_b):
        resp = client_a.get(reverse("crm:contact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert contact_a.pk in pks
        assert contact_b.pk not in pks


class TestContactDetailView:
    def test_detail_200(self, client_a, contact_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[contact_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, contact_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[contact_a.pk]))
        assert resp.context["obj"].pk == contact_a.pk


# ================================================================ Overview
class TestOverviewView:
    def test_overview_200(self, client_a):
        resp = client_a.get(reverse("crm:overview"))
        assert resp.status_code == 200

    def test_overview_has_stats_context(self, client_a):
        resp = client_a.get(reverse("crm:overview"))
        assert "stats" in resp.context
        stats = resp.context["stats"]
        for key in ("open_leads", "pipeline", "weighted", "win_rate", "open_cases",
                    "open_tasks", "active_campaigns"):
            assert key in stats

    def test_overview_has_chart_context_keys(self, client_a):
        resp = client_a.get(reverse("crm:overview"))
        assert "chart_stage_labels" in resp.context
        assert "chart_stage_data" in resp.context
        assert "chart_rating_labels" in resp.context
        assert "chart_rating_data" in resp.context

    def test_overview_has_recent_opps(self, client_a):
        resp = client_a.get(reverse("crm:overview"))
        assert "recent_opps" in resp.context

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:overview"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_open_leads_count(self, client_a, lead_a, tenant_a):
        """Stats open_leads must count non-converted, non-unqualified leads."""
        from apps.crm.models import Lead
        Lead.objects.create(tenant=tenant_a, name="Converted", status="converted")
        Lead.objects.create(tenant=tenant_a, name="Unqualified", status="unqualified")
        resp = client_a.get(reverse("crm:overview"))
        # lead_a (new) counts; converted + unqualified do not
        assert resp.context["stats"]["open_leads"] == 1

    def test_active_campaigns_count(self, client_a, tenant_a):
        from apps.crm.models import Campaign
        Campaign.objects.create(tenant=tenant_a, name="Active", status="active")
        Campaign.objects.create(tenant=tenant_a, name="Planned", status="planned")
        resp = client_a.get(reverse("crm:overview"))
        assert resp.context["stats"]["active_campaigns"] == 1
