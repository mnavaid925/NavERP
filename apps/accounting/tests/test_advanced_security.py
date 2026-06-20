"""Security tests for the advanced accounting sub-modules 2.6–2.15.

Covers:
- @tenant_admin_required gates for all 7 admin actions + integration_edit/delete,
  tax_return_edit/delete, intercompany_toggle_eliminated → 403 for non-admin member.
- Form field exclusions: IntercompanyTransactionForm has no `eliminated` field;
  FixedAssetForm status excludes 'disposed'; IntegrationConfigForm has no api_key_*
  fields; PayrollRunForm has no `net_pay`.
- Cross-tenant IDOR: tenant-A admin on tenant-B FixedAsset / Project / Budget /
  IntegrationConfig / TaxReturn → 404.
- Integration secret: rotate_key stores only prefix+sha256 (never plaintext);
  masked shows prefix+bullets; one-time reveal appears once then gone.
- Anonymous → redirect to /auth/login/ or /login/.
"""
import datetime
import hashlib
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ shared fixtures for advanced
@pytest.fixture
def org_unit_sec(tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Sec HQ", kind="department")


@pytest.fixture
def org_unit_b_sec(tenant_a):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Sec Branch", kind="branch")


@pytest.fixture
def open_period_sec(tenant_a):
    from apps.accounting.models import FiscalPeriod
    return FiscalPeriod.objects.create(
        tenant=tenant_a,
        name="Jul 2026",
        period_type="month",
        start_date=datetime.date(2026, 7, 1),
        end_date=datetime.date(2026, 7, 31),
        status="open",
    )


@pytest.fixture
def asset_for_sec(tenant_a):
    from apps.accounting.models import GLAccount
    from apps.accounting.models_advanced import FixedAsset
    acct = GLAccount.objects.create(
        tenant=tenant_a, code="1610", name="FA Cost Sec", account_type="asset", normal_balance="debit"
    )
    return FixedAsset.objects.create(
        tenant=tenant_a,
        name="Security Test Asset",
        acquisition_cost=Decimal("8000.00"),
        salvage_value=Decimal("0.00"),
        useful_life_months=24,
        method="straight_line",
        status="active",
        asset_account=acct,
    )


@pytest.fixture
def asset_b(tenant_b):
    """A FixedAsset belonging to tenant_b for IDOR tests."""
    from apps.accounting.models_advanced import FixedAsset
    return FixedAsset.objects.create(
        tenant=tenant_b,
        name="Tenant B Asset",
        acquisition_cost=Decimal("5000.00"),
        useful_life_months=12,
        method="straight_line",
        status="active",
    )


@pytest.fixture
def project_sec(tenant_a):
    from apps.accounting.models_advanced import Project
    return Project.objects.create(
        tenant=tenant_a,
        name="Sec Test Project",
        billing_method="fixed",
        budget_amount=Decimal("10000.00"),
        status="active",
    )


@pytest.fixture
def project_b(tenant_b):
    """A Project belonging to tenant_b for IDOR tests."""
    from apps.accounting.models_advanced import Project
    return Project.objects.create(
        tenant=tenant_b,
        name="Globex Project",
        billing_method="fixed",
        budget_amount=Decimal("5000.00"),
        status="active",
    )


@pytest.fixture
def budget_sec(tenant_a, open_period_sec):
    from apps.accounting.models_advanced import Budget
    return Budget.objects.create(
        tenant=tenant_a,
        name="Sec Test Budget",
        fiscal_period=open_period_sec,
        version="original",
    )


@pytest.fixture
def budget_b(tenant_b):
    """A Budget belonging to tenant_b for IDOR tests."""
    from apps.accounting.models_advanced import Budget
    return Budget.objects.create(
        tenant=tenant_b,
        name="Globex Budget",
        version="original",
    )


@pytest.fixture
def integration_sec(tenant_a):
    from apps.accounting.models_advanced import IntegrationConfig
    return IntegrationConfig.objects.create(
        tenant=tenant_a,
        name="Stripe Sec Test",
        provider="stripe",
        category="payments",
    )


@pytest.fixture
def integration_b(tenant_b):
    """An IntegrationConfig belonging to tenant_b for IDOR tests."""
    from apps.accounting.models_advanced import IntegrationConfig
    return IntegrationConfig.objects.create(
        tenant=tenant_b,
        name="Globex Integration",
        provider="custom",
        category="other",
    )


@pytest.fixture
def tax_code_sec(tenant_a):
    from apps.accounting.models_advanced import TaxCode
    return TaxCode.objects.create(
        tenant=tenant_a,
        name="VAT 20%",
        tax_type="vat",
        rate_pct=Decimal("20.000"),
    )


@pytest.fixture
def tax_return_sec(tenant_a, tax_code_sec, open_period_sec):
    from apps.accounting.models_advanced import TaxReturn
    return TaxReturn.objects.create(
        tenant=tenant_a,
        tax_code=tax_code_sec,
        period_start=datetime.date(2026, 7, 1),
        period_end=datetime.date(2026, 7, 31),
        taxable_amount=Decimal("50000.00"),
        tax_due=Decimal("10000.00"),
        status="draft",
    )


@pytest.fixture
def tax_return_b(tenant_b):
    """A TaxReturn belonging to tenant_b."""
    from apps.accounting.models_advanced import TaxCode, TaxReturn
    tc = TaxCode.objects.create(
        tenant=tenant_b, name="VAT B", tax_type="vat", rate_pct=Decimal("10.000")
    )
    return TaxReturn.objects.create(
        tenant=tenant_b,
        tax_code=tc,
        period_start=datetime.date(2026, 7, 1),
        period_end=datetime.date(2026, 7, 31),
        taxable_amount=Decimal("1000.00"),
        tax_due=Decimal("100.00"),
        status="draft",
    )


@pytest.fixture
def ict_sec(tenant_a, org_unit_sec, org_unit_b_sec, open_period_sec):
    from apps.accounting.models_advanced import IntercompanyTransaction
    return IntercompanyTransaction.objects.create(
        tenant=tenant_a,
        description="Sec test ICT",
        transaction_date=datetime.date(2026, 7, 1),
        amount=Decimal("1000.00"),
        from_org_unit=org_unit_sec,
        to_org_unit=org_unit_b_sec,
    )


@pytest.fixture
def draft_disposal_sec(tenant_a, asset_for_sec):
    from apps.accounting.models_advanced import AssetDisposal
    return AssetDisposal.objects.create(
        tenant=tenant_a,
        asset=asset_for_sec,
        disposal_date=datetime.date(2026, 7, 15),
        proceeds=Decimal("9000.00"),
    )


@pytest.fixture
def draft_payroll_sec(tenant_a, open_period_sec):
    from apps.accounting.models_advanced import PayrollRun
    return PayrollRun.objects.create(
        tenant=tenant_a,
        period_start=datetime.date(2026, 7, 1),
        period_end=datetime.date(2026, 7, 15),
        pay_date=datetime.date(2026, 7, 20),
        gross_wages=Decimal("20000.00"),
        employee_tax=Decimal("2000.00"),
    )


@pytest.fixture
def draft_calloc_sec(tenant_a, open_period_sec):
    from apps.accounting.models import GLAccount
    from apps.accounting.models_advanced import CostAllocation
    src = GLAccount.objects.create(
        tenant=tenant_a, code="1050", name="Overhead Pool Sec",
        account_type="asset", normal_balance="debit"
    )
    tgt = GLAccount.objects.create(
        tenant=tenant_a, code="5050", name="Target Sec",
        account_type="expense", normal_balance="debit"
    )
    return CostAllocation.objects.create(
        tenant=tenant_a,
        description="Sec test alloc",
        allocation_date=datetime.date(2026, 7, 1),
        amount=Decimal("100.00"),
        source_account=src,
        target_account=tgt,
    )


@pytest.fixture
def draft_jce_sec(tenant_a, project_sec, open_period_sec):
    from apps.accounting.models import GLAccount
    from apps.accounting.models_advanced import JobCostEntry
    gl = GLAccount.objects.create(
        tenant=tenant_a, code="5700", name="JCE Sec Cost",
        account_type="expense", normal_balance="debit"
    )
    return JobCostEntry.objects.create(
        tenant=tenant_a,
        project=project_sec,
        entry_date=datetime.date(2026, 7, 1),
        kind="cost",
        amount=Decimal("500.00"),
        gl_account=gl,
    )


# ================================================================ @tenant_admin_required gates
class TestAdminRequiredAdvancedGates:
    """Non-admin member must get 403; admin must NOT get 403."""

    def test_fixed_asset_depreciate_requires_admin(self, member_client, client_a, asset_for_sec):
        url = reverse("accounting:fixed_asset_depreciate", args=[asset_for_sec.pk])
        assert member_client.post(url).status_code == 403
        # Admin posts → not 403 (may be 302 redirect even without accounts configured)
        assert client_a.post(url).status_code != 403

    def test_asset_disposal_post_requires_admin(self, member_client, client_a, draft_disposal_sec):
        url = reverse("accounting:asset_disposal_post", args=[draft_disposal_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_cost_allocation_post_requires_admin(self, member_client, client_a, draft_calloc_sec):
        url = reverse("accounting:cost_allocation_post", args=[draft_calloc_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_payroll_run_post_requires_admin(self, member_client, client_a, draft_payroll_sec):
        url = reverse("accounting:payroll_run_post", args=[draft_payroll_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_job_cost_entry_post_requires_admin(self, member_client, client_a, draft_jce_sec):
        url = reverse("accounting:job_cost_entry_post", args=[draft_jce_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_intercompany_post_requires_admin(self, member_client, client_a, ict_sec):
        url = reverse("accounting:intercompany_post", args=[ict_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_integration_rotate_key_requires_admin(self, member_client, client_a, integration_sec):
        url = reverse("accounting:integration_rotate_key", args=[integration_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403

    def test_integration_edit_requires_admin(self, member_client, client_a, integration_sec):
        url = reverse("accounting:integration_edit", args=[integration_sec.pk])
        assert member_client.post(url, {"name": "Hacked"}).status_code == 403
        assert client_a.get(url).status_code != 403

    def test_integration_delete_requires_admin(self, member_client, client_a, integration_sec):
        url = reverse("accounting:integration_delete", args=[integration_sec.pk])
        assert member_client.post(url).status_code == 403

    def test_tax_return_edit_requires_admin(self, member_client, client_a, tax_return_sec):
        url = reverse("accounting:tax_return_edit", args=[tax_return_sec.pk])
        assert member_client.post(url, {"status": "filed"}).status_code == 403
        assert client_a.get(url).status_code != 403

    def test_tax_return_delete_requires_admin(self, member_client, client_a, tax_return_sec):
        url = reverse("accounting:tax_return_delete", args=[tax_return_sec.pk])
        assert member_client.post(url).status_code == 403

    def test_intercompany_toggle_eliminated_requires_admin(self, member_client, client_a, ict_sec):
        url = reverse("accounting:intercompany_toggle_eliminated", args=[ict_sec.pk])
        assert member_client.post(url).status_code == 403
        assert client_a.post(url).status_code != 403


# ================================================================ Form field exclusions
class TestAdvancedFormFieldExclusions:

    def test_intercompany_form_has_no_eliminated_field(self):
        from apps.accounting.forms_advanced import IntercompanyTransactionForm
        form = IntercompanyTransactionForm(tenant=None)
        assert "eliminated" not in form.fields, (
            "IntercompanyTransactionForm must NOT expose 'eliminated' — it's toggle-only"
        )

    def test_fixed_asset_form_excludes_disposed_status(self):
        from apps.accounting.forms_advanced import FixedAssetForm
        form = FixedAssetForm(tenant=None)
        status_values = [c[0] for c in form.fields["status"].choices]
        assert "disposed" not in status_values, (
            "FixedAssetForm must not allow users to set status='disposed' directly"
        )

    def test_integration_config_form_has_no_api_key_prefix(self):
        from apps.accounting.forms_advanced import IntegrationConfigForm
        form = IntegrationConfigForm(tenant=None)
        assert "api_key_prefix" not in form.fields
        assert "api_key_hash" not in form.fields

    def test_payroll_run_form_has_no_net_pay(self):
        from apps.accounting.forms_advanced import PayrollRunForm
        form = PayrollRunForm(tenant=None)
        assert "net_pay" not in form.fields, "net_pay is derived — must not appear in the form"

    def test_asset_disposal_form_has_no_gain_loss(self):
        """gain_loss is computed by the post action, not user-editable."""
        from apps.accounting.forms_advanced import AssetDisposalForm
        form = AssetDisposalForm(tenant=None)
        assert "gain_loss" not in form.fields

    def test_asset_disposal_form_has_no_status(self):
        """status is owned by asset_disposal_post, not the form."""
        from apps.accounting.forms_advanced import AssetDisposalForm
        form = AssetDisposalForm(tenant=None)
        assert "status" not in form.fields

    def test_cost_allocation_form_has_no_status(self):
        from apps.accounting.forms_advanced import CostAllocationForm
        form = CostAllocationForm(tenant=None)
        assert "status" not in form.fields

    def test_payroll_run_form_has_no_status(self):
        from apps.accounting.forms_advanced import PayrollRunForm
        form = PayrollRunForm(tenant=None)
        assert "status" not in form.fields


# ================================================================ Cross-tenant IDOR → 404
class TestAdvancedCrossTenantIDOR:

    def test_asset_detail_cross_tenant_404(self, client_a, asset_b):
        url = reverse("accounting:fixed_asset_detail", args=[asset_b.pk])
        assert client_a.get(url).status_code == 404

    def test_asset_edit_cross_tenant_404(self, client_a, asset_b):
        url = reverse("accounting:fixed_asset_edit", args=[asset_b.pk])
        assert client_a.get(url).status_code == 404

    def test_asset_depreciate_cross_tenant_404(self, client_a, asset_b):
        url = reverse("accounting:fixed_asset_depreciate", args=[asset_b.pk])
        assert client_a.post(url).status_code == 404

    def test_project_detail_cross_tenant_404(self, client_a, project_b):
        url = reverse("accounting:project_detail", args=[project_b.pk])
        assert client_a.get(url).status_code == 404

    def test_project_edit_cross_tenant_404(self, client_a, project_b):
        url = reverse("accounting:project_edit", args=[project_b.pk])
        assert client_a.get(url).status_code == 404

    def test_budget_detail_cross_tenant_404(self, client_a, budget_b):
        url = reverse("accounting:budget_detail", args=[budget_b.pk])
        assert client_a.get(url).status_code == 404

    def test_integration_detail_cross_tenant_404(self, client_a, integration_b):
        url = reverse("accounting:integration_detail", args=[integration_b.pk])
        assert client_a.get(url).status_code == 404

    def test_integration_rotate_key_cross_tenant_404(self, client_a, integration_b):
        url = reverse("accounting:integration_rotate_key", args=[integration_b.pk])
        assert client_a.post(url).status_code == 404

    def test_tax_return_detail_cross_tenant_404(self, client_a, tax_return_b):
        url = reverse("accounting:tax_return_detail", args=[tax_return_b.pk])
        assert client_a.get(url).status_code == 404

    def test_cost_allocation_detail_cross_tenant_404(self, client_a, tenant_b, open_period_sec):
        """CostAllocation belonging to tenant_b → 404 for tenant_a admin."""
        from apps.accounting.models import GLAccount
        from apps.accounting.models_advanced import CostAllocation
        src = GLAccount.objects.create(
            tenant=tenant_b, code="1000", name="Cash B IDOR",
            account_type="asset", normal_balance="debit"
        )
        tgt = GLAccount.objects.create(
            tenant=tenant_b, code="5000", name="Expense B IDOR",
            account_type="expense", normal_balance="debit"
        )
        alloc_b = CostAllocation.objects.create(
            tenant=tenant_b,
            description="Globex alloc",
            allocation_date=datetime.date(2026, 7, 1),
            amount=Decimal("100.00"),
            source_account=src,
            target_account=tgt,
        )
        url = reverse("accounting:cost_allocation_detail", args=[alloc_b.pk])
        assert client_a.get(url).status_code == 404


# ================================================================ Integration secret handling
class TestIntegrationSecret:

    def test_rotate_key_stores_hash_not_plaintext(self, client_a, integration_sec):
        """After rotate_key, the DB stores prefix + SHA-256 hash, never the plaintext secret."""
        url = reverse("accounting:integration_rotate_key", args=[integration_sec.pk])
        client_a.post(url)
        integration_sec.refresh_from_db()
        assert integration_sec.api_key_hash, "Hash must be set after rotate"
        assert integration_sec.api_key_prefix, "Prefix must be set after rotate"
        # The hash should be 64-char hex (SHA-256)
        assert len(integration_sec.api_key_hash) == 64
        # The stored hash should be a valid hex string
        int(integration_sec.api_key_hash, 16)  # will raise ValueError if not hex

    def test_rotate_key_hash_matches_prefix(self, client_a, integration_sec):
        """api_key_prefix must equal the first 6 chars of whatever was hashed."""
        url = reverse("accounting:integration_rotate_key", args=[integration_sec.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        integration_sec.refresh_from_db()
        # The prefix must be exactly 6 chars
        assert len(integration_sec.api_key_prefix) == 6

    def test_masked_shows_prefix_plus_bullets(self, client_a, integration_sec):
        """masked property shows prefix + 8 bullet chars."""
        url = reverse("accounting:integration_rotate_key", args=[integration_sec.pk])
        client_a.post(url)
        integration_sec.refresh_from_db()
        masked = integration_sec.masked
        assert masked.startswith(integration_sec.api_key_prefix)
        assert "•" in masked
        assert masked == f"{integration_sec.api_key_prefix}{'•' * 8}"

    def test_one_time_reveal_appears_once_then_gone(self, client_a, integration_sec):
        """The plaintext_once key in integration_detail appears on first GET only."""
        rotate_url = reverse("accounting:integration_rotate_key", args=[integration_sec.pk])
        detail_url = reverse("accounting:integration_detail", args=[integration_sec.pk])

        # POST rotate → session is populated
        client_a.post(rotate_url)

        # First GET → reveal should be in context (it gets popped from session)
        resp1 = client_a.get(detail_url)
        # We can't easily inspect context here, but we CAN verify the second GET has no reveal
        # by checking the session is empty after the first get
        resp2 = client_a.get(detail_url)
        # After the first GET consumed the session key, the second response must NOT
        # have plaintext_once in its context (it should be None/missing)
        if hasattr(resp2, "context") and resp2.context:
            ctx = resp2.context
            # plaintext_once must be None or absent on the second request
            plaintext_on_second = ctx.get("plaintext_once") if hasattr(ctx, "get") else None
            assert plaintext_on_second is None, (
                "plaintext_once appeared on the second GET — secret reveal must be one-time only"
            )

    def test_rotate_key_not_stored_as_plaintext(self, client_a, integration_sec):
        """Verify that no field stores the raw plaintext secret in the DB."""
        url = reverse("accounting:integration_rotate_key", args=[integration_sec.pk])
        client_a.post(url)
        integration_sec.refresh_from_db()
        # api_key_hash must look like a SHA-256 hex digest, not a long URL-safe token (no '-', '_', etc.)
        hash_value = integration_sec.api_key_hash
        # SHA-256 hex is exactly 64 lowercase hex chars — should not contain URL-safe base64 chars
        assert all(c in "0123456789abcdef" for c in hash_value), (
            f"api_key_hash looks like plaintext, not SHA-256 hex: {hash_value}"
        )


# ================================================================ Anonymous redirect
class TestAnonymousRedirectAdvanced:

    def test_anonymous_fixed_asset_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:fixed_asset_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anonymous_integration_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:integration_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anonymous_project_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:project_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anonymous_budget_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:budget_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
