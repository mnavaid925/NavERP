"""Security tests for the CRM module: IDOR (cross-tenant isolation), auth, CSRF, lead_convert."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ IDOR — tenant A accessing tenant B records
class TestLeadIDOR:
    def test_detail_cross_tenant_404(self, client_a, lead_b):
        resp = client_a.get(reverse("crm:lead_detail", args=[lead_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, lead_b):
        resp = client_a.get(reverse("crm:lead_edit", args=[lead_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, lead_b):
        resp = client_a.post(reverse("crm:lead_edit", args=[lead_b.pk]), {
            "name": "Hijacked", "status": "new", "source": "web",
            "rating": "hot", "score": 0, "est_value": "0.00",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, lead_b):
        resp = client_a.post(reverse("crm:lead_delete", args=[lead_b.pk]))
        assert resp.status_code == 404

    def test_convert_cross_tenant_404(self, client_a, lead_b):
        resp = client_a.post(reverse("crm:lead_convert", args=[lead_b.pk]))
        assert resp.status_code == 404


class TestOpportunityIDOR:
    def test_detail_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.get(reverse("crm:opportunity_detail", args=[opportunity_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.get(reverse("crm:opportunity_edit", args=[opportunity_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, opportunity_b):
        resp = client_a.post(reverse("crm:opportunity_delete", args=[opportunity_b.pk]))
        assert resp.status_code == 404


class TestCampaignIDOR:
    def test_detail_cross_tenant_404(self, client_a, campaign_b):
        resp = client_a.get(reverse("crm:campaign_detail", args=[campaign_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, campaign_b):
        resp = client_a.get(reverse("crm:campaign_edit", args=[campaign_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, campaign_b):
        resp = client_a.post(reverse("crm:campaign_delete", args=[campaign_b.pk]))
        assert resp.status_code == 404


class TestCaseIDOR:
    def test_detail_cross_tenant_404(self, client_a, case_b):
        resp = client_a.get(reverse("crm:case_detail", args=[case_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, case_b):
        resp = client_a.get(reverse("crm:case_edit", args=[case_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, case_b):
        resp = client_a.post(reverse("crm:case_delete", args=[case_b.pk]))
        assert resp.status_code == 404


class TestArticleIDOR:
    def test_detail_cross_tenant_404(self, client_a, article_b):
        resp = client_a.get(reverse("crm:knowledgearticle_detail", args=[article_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, article_b):
        resp = client_a.get(reverse("crm:knowledgearticle_edit", args=[article_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, article_b):
        resp = client_a.post(reverse("crm:knowledgearticle_delete", args=[article_b.pk]))
        assert resp.status_code == 404


class TestTaskIDOR:
    def test_detail_cross_tenant_404(self, client_a, task_b):
        resp = client_a.get(reverse("crm:task_detail", args=[task_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, task_b):
        resp = client_a.get(reverse("crm:task_edit", args=[task_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, task_b):
        resp = client_a.post(reverse("crm:task_delete", args=[task_b.pk]))
        assert resp.status_code == 404


class TestAccountContactLensIDOR:
    def test_account_detail_cross_tenant_404(self, client_a, account_b):
        """account_detail must 404 for a Party that belongs to tenant_b."""
        resp = client_a.get(reverse("crm:account_detail", args=[account_b.pk]))
        assert resp.status_code == 404

    def test_contact_detail_cross_tenant_404(self, client_a, contact_b):
        """contact_detail must 404 for a person Party that belongs to tenant_b."""
        resp = client_a.get(reverse("crm:contact_detail", args=[contact_b.pk]))
        assert resp.status_code == 404

    def test_account_list_excludes_b_orgs(self, client_a, account_a, account_b):
        resp = client_a.get(reverse("crm:account_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert account_a.pk in pks
        assert account_b.pk not in pks

    def test_contact_list_excludes_b_persons(self, client_a, contact_a, contact_b):
        resp = client_a.get(reverse("crm:contact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert contact_a.pk in pks
        assert contact_b.pk not in pks


# ================================================================ Anonymous user → redirect
class TestAnonymousBlocked:
    CRM_URLS = [
        ("crm:lead_list", []),
        ("crm:opportunity_list", []),
        ("crm:campaign_list", []),
        ("crm:case_list", []),
        ("crm:knowledgearticle_list", []),
        ("crm:task_list", []),
        ("crm:account_list", []),
        ("crm:contact_list", []),
        ("crm:overview", []),
    ]

    @pytest.mark.parametrize("url_name,args", [
        ("crm:lead_list", []),
        ("crm:opportunity_list", []),
        ("crm:campaign_list", []),
        ("crm:case_list", []),
        ("crm:knowledgearticle_list", []),
        ("crm:task_list", []),
        ("crm:account_list", []),
        ("crm:contact_list", []),
        ("crm:overview", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_lead_delete_enforces_csrf(self, admin_user, lead_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:lead_delete", args=[lead_a.pk]))
        assert resp.status_code == 403

    def test_opportunity_delete_enforces_csrf(self, admin_user, opportunity_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:opportunity_delete", args=[opportunity_a.pk]))
        assert resp.status_code == 403

    def test_lead_convert_enforces_csrf(self, admin_user, lead_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        assert resp.status_code == 403

    def test_case_delete_enforces_csrf(self, admin_user, case_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:case_delete", args=[case_a.pk]))
        assert resp.status_code == 403


# ================================================================ lead_convert
class TestLeadConvert:
    def test_convert_creates_opportunity(self, client_a, lead_a, tenant_a):
        from apps.crm.models import Opportunity
        resp = client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        assert resp.status_code == 302
        assert Opportunity.objects.filter(tenant=tenant_a, source_lead=lead_a).exists()

    def test_convert_sets_lead_status_converted(self, client_a, lead_a):
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        lead_a.refresh_from_db()
        assert lead_a.status == "converted"

    def test_convert_sets_converted_party(self, client_a, lead_a):
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        lead_a.refresh_from_db()
        assert lead_a.converted_party is not None

    def test_convert_with_company_creates_org_party(self, client_a, lead_a, tenant_a):
        """Lead with company → converted_party is the org Party (account)."""
        from apps.core.models import Party
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        lead_a.refresh_from_db()
        assert lead_a.converted_party.kind == "organization"
        assert lead_a.converted_party.name == lead_a.company

    def test_convert_without_company_creates_person_party(self, client_a, tenant_a):
        """Lead with no company → converted_party is the contact (person) Party."""
        from apps.crm.models import Lead
        lead = Lead.objects.create(
            tenant=tenant_a, name="Solo Person", company="", email="solo@example.com"
        )
        client_a.post(reverse("crm:lead_convert", args=[lead.pk]))
        lead.refresh_from_db()
        assert lead.converted_party.kind == "person"
        assert lead.converted_party.name == lead.name

    def test_convert_creates_contact_method_if_email(self, client_a, lead_a, tenant_a):
        """If the lead has an email, a ContactMethod should be created for the person party."""
        from apps.core.models import ContactMethod
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        assert ContactMethod.objects.filter(tenant=tenant_a, kind="email", value=lead_a.email).exists()

    def test_convert_opportunity_is_tenant_scoped(self, client_a, lead_a, tenant_a):
        from apps.crm.models import Opportunity
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        opp = Opportunity.objects.get(tenant=tenant_a, source_lead=lead_a)
        assert opp.tenant == tenant_a

    def test_already_converted_is_idempotent(self, client_a, lead_a, tenant_a):
        """Converting the same lead twice must not create duplicate Party/Opportunity."""
        from apps.crm.models import Opportunity
        from apps.core.models import Party
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        opp_count_before = Opportunity.objects.filter(tenant=tenant_a, source_lead=lead_a).count()
        party_count_before = Party.objects.filter(tenant=tenant_a).count()

        # Second conversion attempt
        resp = client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        assert resp.status_code == 302

        opp_count_after = Opportunity.objects.filter(tenant=tenant_a, source_lead=lead_a).count()
        party_count_after = Party.objects.filter(tenant=tenant_a).count()
        assert opp_count_after == opp_count_before
        assert party_count_after == party_count_before

    def test_convert_get_not_allowed(self, client_a, lead_a):
        """lead_convert is @require_POST; GET must return 405."""
        resp = client_a.get(reverse("crm:lead_convert", args=[lead_a.pk]))
        assert resp.status_code == 405

    def test_convert_cross_tenant_404(self, client_a, lead_b):
        """Tenant A must get 404 when trying to convert Tenant B's lead."""
        resp = client_a.post(reverse("crm:lead_convert", args=[lead_b.pk]))
        assert resp.status_code == 404

    def test_convert_creates_party_roles(self, client_a, lead_a, tenant_a):
        """Conversion must create PartyRole records (customer for org, contact for person)."""
        from apps.core.models import PartyRole
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        # Lead has company → org with "customer" role + person with "contact" role
        assert PartyRole.objects.filter(tenant=tenant_a, role="customer").exists()
        assert PartyRole.objects.filter(tenant=tenant_a, role="contact").exists()

    def test_convert_opportunity_has_lead_est_value(self, client_a, lead_a, tenant_a):
        """The created Opportunity amount should match the lead's est_value."""
        from decimal import Decimal
        from apps.crm.models import Opportunity
        client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        # lead_a.est_value is a str until refresh_from_db; opp.amount is Decimal from DB.
        lead_a.refresh_from_db()
        opp = Opportunity.objects.get(tenant=tenant_a, source_lead=lead_a)
        assert opp.amount == lead_a.est_value

    def test_convert_redirects_to_opportunity_detail(self, client_a, lead_a, tenant_a):
        """After conversion, the view should redirect to the new opportunity detail page."""
        from apps.crm.models import Opportunity
        resp = client_a.post(reverse("crm:lead_convert", args=[lead_a.pk]))
        opp = Opportunity.objects.get(tenant=tenant_a, source_lead=lead_a)
        assert resp["Location"].endswith(reverse("crm:opportunity_detail", args=[opp.pk]))
