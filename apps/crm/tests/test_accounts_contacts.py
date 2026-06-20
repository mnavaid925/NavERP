"""Tests for the Accounts & Contacts CRUD enhancement (AccountProfile / ContactProfile).

Covers:
  1. Models: __str__, OneToOne uniqueness, Party cascade, FK acceptance.
  2. Forms: valid data, name required, excluded fields, cross-tenant FK rejection,
     javascript: URL scheme blocked.
  3. CRUD views: create/edit/detail (profile-less Party too).
  4. Authorization: non-admin POST -> 403; tenant-admin POST -> 302; GET -> 405; anon -> redirect.
  5. Multi-tenant IDOR: cross-tenant detail/edit/delete -> 404; wrong-kind pk -> 404.
  6. Filters: account_list ?industry= and ?source= narrow results; contact_list ?source=.
"""
import pytest
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ========================================================================= Fixtures
@pytest.fixture
def org_party_a(db, tenant_a):
    """An organization Party for tenant_a (no CRM profile yet)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Acme Inc")


@pytest.fixture
def org_party_b(db, tenant_b):
    """An organization Party for tenant_b."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Inc")


@pytest.fixture
def person_party_a(db, tenant_a):
    """A person Party for tenant_a (no CRM profile yet)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="person", name="Alice Smith")


@pytest.fixture
def person_party_b(db, tenant_b):
    """A person Party for tenant_b."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="person", name="Bob Jones")


@pytest.fixture
def account_profile_a(db, tenant_a, org_party_a):
    """AccountProfile for tenant_a's org_party_a."""
    from apps.crm.models import AccountProfile
    return AccountProfile.objects.create(
        tenant=tenant_a,
        party=org_party_a,
        industry="technology",
        website="https://acme.example.com",
        phone="+1-555-0100",
        source="web",
        description="A tech firm.",
    )


@pytest.fixture
def account_profile_b(db, tenant_b, org_party_b):
    """AccountProfile for tenant_b's org_party_b."""
    from apps.crm.models import AccountProfile
    return AccountProfile.objects.create(
        tenant=tenant_b,
        party=org_party_b,
        industry="finance",
        source="referral",
    )


@pytest.fixture
def contact_profile_a(db, tenant_a, person_party_a, org_party_a):
    """ContactProfile for tenant_a's person_party_a, linked to org_party_a."""
    from apps.crm.models import ContactProfile
    return ContactProfile.objects.create(
        tenant=tenant_a,
        party=person_party_a,
        job_title="Engineer",
        phone="+1-555-0200",
        account=org_party_a,
        source="web",
        linkedin="https://linkedin.com/in/alice",
    )


@pytest.fixture
def contact_profile_b(db, tenant_b, person_party_b):
    """ContactProfile for tenant_b's person_party_b."""
    from apps.crm.models import ContactProfile
    return ContactProfile.objects.create(
        tenant=tenant_b,
        party=person_party_b,
        source="event",
    )


# ========================================================================= 1. Model tests
class TestAccountProfileModel:
    def test_str(self, account_profile_a, org_party_a):
        assert str(account_profile_a) == f"Account · {org_party_a.name}"

    def test_str_format_exact(self, account_profile_a):
        assert str(account_profile_a).startswith("Account · ")

    def test_oneto_one_uniqueness(self, tenant_a, org_party_a, account_profile_a):
        """A second AccountProfile for the same Party must raise IntegrityError."""
        from apps.crm.models import AccountProfile
        with pytest.raises(IntegrityError):
            AccountProfile.objects.create(tenant=tenant_a, party=org_party_a, industry="retail")

    def test_deleting_party_cascades_profile(self, org_party_a, account_profile_a):
        """Deleting the Party must also delete the AccountProfile."""
        from apps.crm.models import AccountProfile
        profile_pk = account_profile_a.pk
        org_party_a.delete()
        assert not AccountProfile.objects.filter(pk=profile_pk).exists()

    def test_parent_account_accepts_org_party(self, tenant_a, org_party_a, account_profile_a):
        """parent_account FK accepts another organization Party."""
        from apps.core.models import Party
        parent = Party.objects.create(tenant=tenant_a, kind="organization", name="ParentCo")
        account_profile_a.parent_account = parent
        account_profile_a.save()
        account_profile_a.refresh_from_db()
        assert account_profile_a.parent_account_id == parent.pk

    def test_industry_choices_include_technology(self):
        from apps.crm.models import INDUSTRY_CHOICES
        keys = [k for k, _ in INDUSTRY_CHOICES]
        assert "technology" in keys

    def test_source_mirrors_lead_source_choices(self):
        from apps.crm.models import Lead, AccountProfile
        lead_sources = {k for k, _ in Lead.SOURCE_CHOICES}
        # AccountProfile.source uses Lead.SOURCE_CHOICES; field choices must be the same set
        model_field = AccountProfile._meta.get_field("source")
        profile_sources = {k for k, _ in model_field.choices}
        assert profile_sources == lead_sources

    def test_defaults(self, tenant_a, org_party_a):
        """Fields with defaults should be set without explicit values."""
        from apps.crm.models import AccountProfile
        from decimal import Decimal
        profile = AccountProfile.objects.create(tenant=tenant_a, party=org_party_a)
        profile.refresh_from_db()
        assert profile.annual_revenue == Decimal("0")
        assert profile.employee_count == 0
        assert profile.industry == ""
        assert profile.source == ""


class TestContactProfileModel:
    def test_str(self, contact_profile_a, person_party_a):
        assert str(contact_profile_a) == f"Contact · {person_party_a.name}"

    def test_str_format_exact(self, contact_profile_a):
        assert str(contact_profile_a).startswith("Contact · ")

    def test_oneto_one_uniqueness(self, tenant_a, person_party_a, contact_profile_a):
        """A second ContactProfile for the same Party must raise IntegrityError."""
        from apps.crm.models import ContactProfile
        with pytest.raises(IntegrityError):
            ContactProfile.objects.create(tenant=tenant_a, party=person_party_a, job_title="Dup")

    def test_deleting_party_cascades_profile(self, person_party_a, contact_profile_a):
        """Deleting the Party must also delete the ContactProfile."""
        from apps.crm.models import ContactProfile
        profile_pk = contact_profile_a.pk
        person_party_a.delete()
        assert not ContactProfile.objects.filter(pk=profile_pk).exists()

    def test_account_accepts_org_party(self, tenant_a, person_party_a, org_party_a):
        """ContactProfile.account FK accepts an organization Party."""
        from apps.crm.models import ContactProfile
        profile = ContactProfile.objects.create(
            tenant=tenant_a, party=person_party_a, account=org_party_a
        )
        profile.refresh_from_db()
        assert profile.account_id == org_party_a.pk

    def test_source_mirrors_lead_source_choices(self):
        from apps.crm.models import Lead, ContactProfile
        lead_sources = {k for k, _ in Lead.SOURCE_CHOICES}
        model_field = ContactProfile._meta.get_field("source")
        profile_sources = {k for k, _ in model_field.choices}
        assert profile_sources == lead_sources


# ========================================================================= 2. Form tests
class TestAccountFormValid:
    def test_valid_minimal_account(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Test Org",
            "annual_revenue": "0.00",
            "employee_count": 0,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    _ACCOUNT_BASE = {
        "annual_revenue": "0.00",
        "employee_count": 0,
    }

    def test_valid_with_all_fields(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Full Org",
            "tax_id": "TAX-123",
            "industry": "technology",
            "website": "https://example.com",
            "phone": "+1-555-1234",
            "email": "info@example.com",
            "annual_revenue": "1000000.00",
            "employee_count": 50,
            "address_line": "123 Main St",
            "address_city": "Springfield",
            "address_state": "IL",
            "address_postal": "62701",
            "address_country": "US",
            "source": "web",
            "description": "A fine company.",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm({"name": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_name_blank_required(self, tenant_a):
        """Blank name (whitespace only) must be invalid."""
        from apps.crm.forms import AccountForm
        form = AccountForm({"name": "   "}, tenant=tenant_a)
        # CharField strips; empty stripped value is invalid
        assert not form.is_valid()

    def test_party_not_in_fields(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm(tenant=tenant_a)
        assert "party" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_created_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm(tenant=tenant_a)
        assert "created_at" not in form.fields

    def test_updated_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm(tenant=tenant_a)
        assert "updated_at" not in form.fields

    def test_javascript_website_invalid(self, tenant_a):
        """javascript: URL must fail URLField validation."""
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Evil Corp",
            "website": "javascript:alert(1)",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "website" in form.errors

    def test_data_uri_website_invalid(self, tenant_a):
        """data: URL scheme must also be rejected by URLValidator."""
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Data Corp",
            "website": "data:text/html,<h1>XSS</h1>",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "website" in form.errors

    def test_valid_https_website_accepted(self, tenant_a):
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Safe Corp",
            "website": "https://safe.example.com",
            "annual_revenue": "0.00",
            "employee_count": 0,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_parent_account_cross_tenant_rejected(self, tenant_a, org_party_b):
        """parent_account pk from another tenant must make the form invalid."""
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Tenant A Org",
            "parent_account": org_party_b.pk,  # belongs to tenant_b
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "parent_account" in form.errors

    def test_owner_cross_tenant_rejected(self, tenant_a, admin_b):
        """owner pk from another tenant must make the form invalid."""
        from apps.crm.forms import AccountForm
        form = AccountForm({
            "name": "Owner Test Org",
            "owner": admin_b.pk,  # belongs to tenant_b
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "owner" in form.errors

    def test_parent_account_same_tenant_accepted(self, tenant_a, org_party_a):
        """parent_account from the same tenant is valid."""
        from apps.crm.forms import AccountForm
        # Need a different party to use as parent (can't use org_party_a as its own parent)
        from apps.core.models import Party
        parent = Party.objects.create(tenant=tenant_a, kind="organization", name="ParentCo")
        form = AccountForm({
            "name": "Child Org",
            "parent_account": parent.pk,
            "annual_revenue": "0.00",
            "employee_count": 0,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_parent_account_self_excluded_on_edit(self, tenant_a, org_party_a, account_profile_a):
        """On edit, the current account must be excluded from parent_account queryset."""
        from apps.crm.forms import AccountForm
        form = AccountForm(
            instance=account_profile_a,
            tenant=tenant_a,
            initial={"name": org_party_a.name},
        )
        qs = form.fields["parent_account"].queryset
        assert org_party_a.pk not in list(qs.values_list("pk", flat=True))


class TestContactFormValid:
    def test_valid_minimal_contact(self, tenant_a):
        from apps.crm.forms import ContactForm
        form = ContactForm({"name": "John Doe"}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_valid_with_all_fields(self, tenant_a, org_party_a, admin_user):
        from apps.crm.forms import ContactForm
        form = ContactForm({
            "name": "Full Contact",
            "job_title": "Engineer",
            "department": "R&D",
            "email": "full@example.com",
            "phone": "+1-555-9876",
            "mobile": "+1-555-5432",
            "account": org_party_a.pk,
            "address_line": "456 Elm St",
            "address_city": "Shelbyville",
            "address_state": "IL",
            "address_postal": "62702",
            "address_country": "US",
            "linkedin": "https://linkedin.com/in/full",
            "source": "referral",
            "owner": admin_user.pk,
            "description": "A contact.",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.crm.forms import ContactForm
        form = ContactForm({"name": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_party_not_in_fields(self, tenant_a):
        from apps.crm.forms import ContactForm
        form = ContactForm(tenant=tenant_a)
        assert "party" not in form.fields

    def test_tenant_not_in_fields(self, tenant_a):
        from apps.crm.forms import ContactForm
        form = ContactForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_created_at_not_in_fields(self, tenant_a):
        from apps.crm.forms import ContactForm
        form = ContactForm(tenant=tenant_a)
        assert "created_at" not in form.fields

    def test_javascript_linkedin_invalid(self, tenant_a):
        """javascript: URL must fail URLField validation for linkedin."""
        from apps.crm.forms import ContactForm
        form = ContactForm({
            "name": "Hacker",
            "linkedin": "javascript:alert(document.cookie)",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "linkedin" in form.errors

    def test_valid_https_linkedin_accepted(self, tenant_a):
        from apps.crm.forms import ContactForm
        form = ContactForm({
            "name": "Safe Contact",
            "linkedin": "https://linkedin.com/in/safe",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_account_cross_tenant_rejected(self, tenant_a, org_party_b):
        """account (employer) pk from another tenant must make the form invalid."""
        from apps.crm.forms import ContactForm
        form = ContactForm({
            "name": "Cross-Tenant Contact",
            "account": org_party_b.pk,  # belongs to tenant_b
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "account" in form.errors

    def test_owner_cross_tenant_rejected(self, tenant_a, admin_b):
        from apps.crm.forms import ContactForm
        form = ContactForm({
            "name": "Owner Test Contact",
            "owner": admin_b.pk,  # belongs to tenant_b
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "owner" in form.errors

    def test_account_same_tenant_accepted(self, tenant_a, org_party_a):
        from apps.crm.forms import ContactForm
        form = ContactForm({
            "name": "Linked Contact",
            "account": org_party_a.pk,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_account_queryset_scoped_to_org_parties(self, tenant_a, org_party_a, person_party_a):
        """account queryset must include organizations but not persons."""
        from apps.crm.forms import ContactForm
        form = ContactForm(tenant=tenant_a)
        qs = form.fields["account"].queryset
        pks = list(qs.values_list("pk", flat=True))
        assert org_party_a.pk in pks
        assert person_party_a.pk not in pks


# ========================================================================= 3. CRUD view tests
class TestAccountCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:account_create"))
        assert resp.status_code == 200

    def test_post_creates_party_and_profile(self, client_a, tenant_a):
        from apps.core.models import Party
        from apps.crm.models import AccountProfile
        resp = client_a.post(reverse("crm:account_create"), {
            "name": "New Account Co",
            "industry": "technology",
            "website": "https://newco.example.com",
            "phone": "+1-555-3001",
            "source": "web",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        assert resp.status_code == 302
        party = Party.objects.filter(tenant=tenant_a, name="New Account Co", kind="organization").first()
        assert party is not None
        assert AccountProfile.objects.filter(tenant=tenant_a, party=party).exists()

    def test_post_sets_correct_tenant(self, client_a, tenant_a):
        from apps.core.models import Party
        client_a.post(reverse("crm:account_create"), {
            "name": "TenantCheck Co",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        party = Party.objects.filter(name="TenantCheck Co").first()
        assert party is not None
        assert party.tenant == tenant_a

    def test_post_sets_kind_organization(self, client_a, tenant_a):
        from apps.core.models import Party
        client_a.post(reverse("crm:account_create"), {
            "name": "Kind Check Co",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        party = Party.objects.filter(tenant=tenant_a, name="Kind Check Co").first()
        assert party is not None
        assert party.kind == "organization"

    def test_post_persists_industry(self, client_a, tenant_a):
        from apps.core.models import Party
        from apps.crm.models import AccountProfile
        client_a.post(reverse("crm:account_create"), {
            "name": "Industry Co",
            "industry": "finance",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        party = Party.objects.filter(tenant=tenant_a, name="Industry Co").first()
        assert party is not None
        profile = AccountProfile.objects.filter(party=party).first()
        assert profile is not None
        assert profile.industry == "finance"

    def test_post_missing_name_re_renders(self, client_a, tenant_a):
        """POST with no name must not create a Party and must re-render the form."""
        from apps.core.models import Party
        count_before = Party.objects.filter(tenant=tenant_a).count()
        resp = client_a.post(reverse("crm:account_create"), {"name": ""})
        assert resp.status_code == 200
        assert Party.objects.filter(tenant=tenant_a).count() == count_before

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:account_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestAccountDetailView:
    def test_detail_200(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert resp.context["obj"].pk == org_party_a.pk

    def test_detail_context_profile(self, client_a, org_party_a, account_profile_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert resp.context["profile"] is not None
        assert resp.context["profile"].pk == account_profile_a.pk

    def test_detail_profile_less_party_returns_200(self, client_a, org_party_a):
        """A Party without a CRM profile must still render without error."""
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert resp.status_code == 200
        # profile should be None when there is no AccountProfile
        assert resp.context["profile"] is None

    def test_detail_context_has_opportunities(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert "opportunities" in resp.context

    def test_detail_context_has_cases(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert "cases" in resp.context

    def test_detail_context_has_child_accounts(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert "child_accounts" in resp.context

    def test_detail_context_has_stakeholders(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert "stakeholders" in resp.context

    def test_anon_redirects(self, client, org_party_a):
        resp = client.get(reverse("crm:account_detail", args=[org_party_a.pk]))
        assert resp.status_code == 302


class TestAccountEditView:
    def test_get_200(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:account_edit", args=[org_party_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_party_name(self, client_a, org_party_a):
        resp = client_a.post(reverse("crm:account_edit", args=[org_party_a.pk]), {
            "name": "Renamed Acme",
            "industry": "retail",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        assert resp.status_code == 302
        org_party_a.refresh_from_db()
        assert org_party_a.name == "Renamed Acme"

    def test_post_updates_profile_field(self, client_a, org_party_a, account_profile_a):
        """Editing should update the linked AccountProfile."""
        from apps.crm.models import AccountProfile
        resp = client_a.post(reverse("crm:account_edit", args=[org_party_a.pk]), {
            "name": org_party_a.name,
            "industry": "healthcare",
            "source": "referral",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        assert resp.status_code == 302
        account_profile_a.refresh_from_db()
        assert account_profile_a.industry == "healthcare"
        assert account_profile_a.source == "referral"

    def test_post_creates_profile_if_missing(self, client_a, org_party_a):
        """Editing an account without a profile should create the profile."""
        from apps.crm.models import AccountProfile
        assert not AccountProfile.objects.filter(party=org_party_a).exists()
        resp = client_a.post(reverse("crm:account_edit", args=[org_party_a.pk]), {
            "name": org_party_a.name,
            "industry": "education",
            "annual_revenue": "0.00",
            "employee_count": 0,
        })
        assert resp.status_code == 302
        assert AccountProfile.objects.filter(party=org_party_a).exists()


class TestAccountDeleteView:
    def test_tenant_admin_post_deletes_party(self, client_a, org_party_a, tenant_a):
        """A tenant admin POST must delete the Party (and cascade the profile)."""
        from apps.core.models import Party
        pk = org_party_a.pk
        resp = client_a.post(reverse("crm:account_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Party.objects.filter(pk=pk).exists()

    def test_tenant_admin_delete_also_removes_profile(self, client_a, org_party_a, account_profile_a):
        """Deleting the Party via the view must cascade to the AccountProfile."""
        from apps.crm.models import AccountProfile
        profile_pk = account_profile_a.pk
        client_a.post(reverse("crm:account_delete", args=[org_party_a.pk]))
        assert not AccountProfile.objects.filter(pk=profile_pk).exists()

    def test_non_admin_post_gets_403(self, member_client, org_party_a):
        """A non-admin member POST must receive 403 PermissionDenied."""
        resp = member_client.post(reverse("crm:account_delete", args=[org_party_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_post_party_still_exists(self, member_client, org_party_a):
        """After a rejected (403) delete, the Party must still exist."""
        from apps.core.models import Party
        member_client.post(reverse("crm:account_delete", args=[org_party_a.pk]))
        assert Party.objects.filter(pk=org_party_a.pk).exists()

    def test_get_returns_405(self, client_a, org_party_a):
        """account_delete is @require_POST; GET must return 405."""
        resp = client_a.get(reverse("crm:account_delete", args=[org_party_a.pk]))
        assert resp.status_code == 405

    def test_anon_redirects_to_login(self, client, org_party_a):
        resp = client.post(reverse("crm:account_delete", args=[org_party_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestContactCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:contact_create"))
        assert resp.status_code == 200

    def test_post_creates_party_and_profile(self, client_a, tenant_a):
        from apps.core.models import Party
        from apps.crm.models import ContactProfile
        resp = client_a.post(reverse("crm:contact_create"), {
            "name": "Jane Contact",
            "job_title": "Sales Rep",
            "source": "referral",
        })
        assert resp.status_code == 302
        party = Party.objects.filter(tenant=tenant_a, name="Jane Contact", kind="person").first()
        assert party is not None
        assert ContactProfile.objects.filter(tenant=tenant_a, party=party).exists()

    def test_post_sets_correct_tenant(self, client_a, tenant_a):
        from apps.core.models import Party
        client_a.post(reverse("crm:contact_create"), {"name": "TenantCheck Person"})
        party = Party.objects.filter(name="TenantCheck Person").first()
        assert party is not None
        assert party.tenant == tenant_a

    def test_post_sets_kind_person(self, client_a, tenant_a):
        from apps.core.models import Party
        client_a.post(reverse("crm:contact_create"), {"name": "Kind Check Person"})
        party = Party.objects.filter(tenant=tenant_a, name="Kind Check Person").first()
        assert party is not None
        assert party.kind == "person"

    def test_post_persists_job_title(self, client_a, tenant_a):
        from apps.core.models import Party
        from apps.crm.models import ContactProfile
        client_a.post(reverse("crm:contact_create"), {
            "name": "Job Title Person",
            "job_title": "CTO",
        })
        party = Party.objects.filter(tenant=tenant_a, name="Job Title Person").first()
        assert party is not None
        profile = ContactProfile.objects.filter(party=party).first()
        assert profile is not None
        assert profile.job_title == "CTO"

    def test_post_missing_name_re_renders(self, client_a, tenant_a):
        from apps.core.models import Party
        count_before = Party.objects.filter(tenant=tenant_a, kind="person").count()
        resp = client_a.post(reverse("crm:contact_create"), {"name": ""})
        assert resp.status_code == 200
        assert Party.objects.filter(tenant=tenant_a, kind="person").count() == count_before

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:contact_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestContactDetailView:
    def test_detail_200(self, client_a, person_party_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, person_party_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_a.pk]))
        assert resp.context["obj"].pk == person_party_a.pk

    def test_detail_context_profile(self, client_a, person_party_a, contact_profile_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_a.pk]))
        assert resp.context["profile"] is not None
        assert resp.context["profile"].pk == contact_profile_a.pk

    def test_detail_profile_less_party_returns_200(self, client_a, person_party_a):
        """A person Party without a CRM profile must still render without error."""
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_a.pk]))
        assert resp.status_code == 200
        assert resp.context["profile"] is None

    def test_detail_context_has_opportunities(self, client_a, person_party_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_a.pk]))
        assert "opportunities" in resp.context

    def test_detail_context_has_cases(self, client_a, person_party_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_a.pk]))
        assert "cases" in resp.context


class TestContactEditView:
    def test_get_200(self, client_a, person_party_a):
        resp = client_a.get(reverse("crm:contact_edit", args=[person_party_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_party_name(self, client_a, person_party_a):
        resp = client_a.post(reverse("crm:contact_edit", args=[person_party_a.pk]), {
            "name": "Alice Updated",
            "job_title": "Senior Engineer",
        })
        assert resp.status_code == 302
        person_party_a.refresh_from_db()
        assert person_party_a.name == "Alice Updated"

    def test_post_updates_profile_field(self, client_a, person_party_a, contact_profile_a):
        resp = client_a.post(reverse("crm:contact_edit", args=[person_party_a.pk]), {
            "name": person_party_a.name,
            "job_title": "VP Engineering",
            "source": "event",
        })
        assert resp.status_code == 302
        contact_profile_a.refresh_from_db()
        assert contact_profile_a.job_title == "VP Engineering"
        assert contact_profile_a.source == "event"

    def test_post_creates_profile_if_missing(self, client_a, person_party_a):
        from apps.crm.models import ContactProfile
        assert not ContactProfile.objects.filter(party=person_party_a).exists()
        resp = client_a.post(reverse("crm:contact_edit", args=[person_party_a.pk]), {
            "name": person_party_a.name,
            "job_title": "Designer",
        })
        assert resp.status_code == 302
        assert ContactProfile.objects.filter(party=person_party_a).exists()


class TestContactDeleteView:
    def test_tenant_admin_post_deletes_party(self, client_a, person_party_a):
        from apps.core.models import Party
        pk = person_party_a.pk
        resp = client_a.post(reverse("crm:contact_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Party.objects.filter(pk=pk).exists()

    def test_tenant_admin_delete_also_removes_profile(self, client_a, person_party_a, contact_profile_a):
        from apps.crm.models import ContactProfile
        profile_pk = contact_profile_a.pk
        client_a.post(reverse("crm:contact_delete", args=[person_party_a.pk]))
        assert not ContactProfile.objects.filter(pk=profile_pk).exists()

    def test_non_admin_post_gets_403(self, member_client, person_party_a):
        resp = member_client.post(reverse("crm:contact_delete", args=[person_party_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_post_party_still_exists(self, member_client, person_party_a):
        from apps.core.models import Party
        member_client.post(reverse("crm:contact_delete", args=[person_party_a.pk]))
        assert Party.objects.filter(pk=person_party_a.pk).exists()

    def test_get_returns_405(self, client_a, person_party_a):
        resp = client_a.get(reverse("crm:contact_delete", args=[person_party_a.pk]))
        assert resp.status_code == 405

    def test_anon_redirects_to_login(self, client, person_party_a):
        resp = client.post(reverse("crm:contact_delete", args=[person_party_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ========================================================================= 4. CSRF enforcement
class TestAccountContactCSRF:
    def test_account_delete_enforces_csrf(self, admin_user, org_party_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:account_delete", args=[org_party_a.pk]))
        assert resp.status_code == 403

    def test_contact_delete_enforces_csrf(self, admin_user, person_party_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:contact_delete", args=[person_party_a.pk]))
        assert resp.status_code == 403


# ========================================================================= 5. Multi-tenant IDOR
class TestAccountIDOR:
    def test_detail_cross_tenant_404(self, client_a, org_party_b):
        """Tenant A accessing tenant B's account detail must get 404."""
        resp = client_a.get(reverse("crm:account_detail", args=[org_party_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, org_party_b):
        resp = client_a.get(reverse("crm:account_edit", args=[org_party_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, org_party_b):
        resp = client_a.post(reverse("crm:account_edit", args=[org_party_b.pk]), {
            "name": "Hijacked",
            "industry": "retail",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, org_party_b):
        resp = client_a.post(reverse("crm:account_delete", args=[org_party_b.pk]))
        assert resp.status_code == 404

    def test_wrong_kind_person_pk_on_account_edit_404(self, client_a, person_party_a):
        """Using a person Party pk on account_edit (which requires kind=organization) must 404."""
        resp = client_a.get(reverse("crm:account_edit", args=[person_party_a.pk]))
        assert resp.status_code == 404

    def test_wrong_kind_person_pk_on_account_detail_404(self, client_a, person_party_a):
        """account_detail with a person Party pk must 404."""
        resp = client_a.get(reverse("crm:account_detail", args=[person_party_a.pk]))
        assert resp.status_code == 404

    def test_account_list_excludes_b_orgs(self, client_a, org_party_a, org_party_b):
        resp = client_a.get(reverse("crm:account_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert org_party_a.pk in pks
        assert org_party_b.pk not in pks


class TestContactIDOR:
    def test_detail_cross_tenant_404(self, client_a, person_party_b):
        resp = client_a.get(reverse("crm:contact_detail", args=[person_party_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, person_party_b):
        resp = client_a.get(reverse("crm:contact_edit", args=[person_party_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, person_party_b):
        resp = client_a.post(reverse("crm:contact_edit", args=[person_party_b.pk]), {
            "name": "Hijacked Person",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, person_party_b):
        resp = client_a.post(reverse("crm:contact_delete", args=[person_party_b.pk]))
        assert resp.status_code == 404

    def test_wrong_kind_org_pk_on_contact_edit_404(self, client_a, org_party_a):
        """Using an org Party pk on contact_edit (which requires kind=person) must 404."""
        resp = client_a.get(reverse("crm:contact_edit", args=[org_party_a.pk]))
        assert resp.status_code == 404

    def test_wrong_kind_org_pk_on_contact_detail_404(self, client_a, org_party_a):
        resp = client_a.get(reverse("crm:contact_detail", args=[org_party_a.pk]))
        assert resp.status_code == 404

    def test_contact_list_excludes_b_persons(self, client_a, person_party_a, person_party_b):
        resp = client_a.get(reverse("crm:contact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert person_party_a.pk in pks
        assert person_party_b.pk not in pks


# ========================================================================= 6. Filter tests
class TestAccountListFilters:
    def test_industry_filter_narrows_results(self, client_a, tenant_a, org_party_a, account_profile_a):
        """?industry=technology must only return accounts with that industry."""
        from apps.core.models import Party
        from apps.crm.models import AccountProfile
        # Create a second account with a different industry
        other_party = Party.objects.create(tenant=tenant_a, kind="organization", name="FinanceCo")
        AccountProfile.objects.create(tenant=tenant_a, party=other_party, industry="finance")

        resp = client_a.get(reverse("crm:account_list") + "?industry=technology")
        assert resp.status_code == 200
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert org_party_a.pk in pks
        assert other_party.pk not in pks

    def test_industry_filter_excludes_non_matching(self, client_a, tenant_a, org_party_a, account_profile_a):
        resp = client_a.get(reverse("crm:account_list") + "?industry=healthcare")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert org_party_a.pk not in pks  # org_party_a has industry=technology

    def test_source_filter_narrows_account_results(self, client_a, tenant_a, org_party_a, account_profile_a):
        """?source=web must only return accounts with source=web."""
        from apps.core.models import Party
        from apps.crm.models import AccountProfile
        other_party = Party.objects.create(tenant=tenant_a, kind="organization", name="ReferralCo")
        AccountProfile.objects.create(tenant=tenant_a, party=other_party, source="referral")

        resp = client_a.get(reverse("crm:account_list") + "?source=web")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert org_party_a.pk in pks
        assert other_party.pk not in pks

    def test_account_list_context_has_industry_choices(self, client_a):
        resp = client_a.get(reverse("crm:account_list"))
        assert "industry_choices" in resp.context

    def test_account_list_context_has_source_choices(self, client_a):
        resp = client_a.get(reverse("crm:account_list"))
        assert "source_choices" in resp.context

    def test_no_filter_returns_all_own_accounts(self, client_a, tenant_a, org_party_a, account_profile_a):
        """Without filters, all tenant-A org parties should be in the list."""
        from apps.core.models import Party
        second_party = Party.objects.create(tenant=tenant_a, kind="organization", name="Second Co")
        resp = client_a.get(reverse("crm:account_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert org_party_a.pk in pks
        assert second_party.pk in pks


class TestContactListFilters:
    def test_source_filter_narrows_contact_results(self, client_a, tenant_a, person_party_a, contact_profile_a):
        """?source=web must only return contacts with source=web."""
        from apps.core.models import Party
        from apps.crm.models import ContactProfile
        other_person = Party.objects.create(tenant=tenant_a, kind="person", name="Event Person")
        ContactProfile.objects.create(tenant=tenant_a, party=other_person, source="event")

        resp = client_a.get(reverse("crm:contact_list") + "?source=web")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert person_party_a.pk in pks
        assert other_person.pk not in pks

    def test_source_filter_excludes_non_matching(self, client_a, tenant_a, person_party_a, contact_profile_a):
        resp = client_a.get(reverse("crm:contact_list") + "?source=cold_call")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert person_party_a.pk not in pks

    def test_contact_list_context_has_source_choices(self, client_a):
        resp = client_a.get(reverse("crm:contact_list"))
        assert "source_choices" in resp.context

    def test_no_filter_returns_all_own_contacts(self, client_a, tenant_a, person_party_a, contact_profile_a):
        from apps.core.models import Party
        second_person = Party.objects.create(tenant=tenant_a, kind="person", name="Second Person")
        resp = client_a.get(reverse("crm:contact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert person_party_a.pk in pks
        assert second_person.pk in pks
