"""Unit tests for Sub-module 10.7 Data Catalog, Lineage & Governance forms.

Forms covered:
- CatalogAssetForm
- CatalogAssetCertifyForm
- CatalogAssetDeprecateForm
- CatalogLineageEdgeForm
- DataGovernancePolicyForm
- CatalogTrustEndorsementForm
"""
import pytest
from django.utils import timezone

from apps.bi.forms import (
    CatalogAssetForm,
    CatalogAssetCertifyForm,
    CatalogAssetDeprecateForm,
    CatalogLineageEdgeForm,
    DataGovernancePolicyForm,
    CatalogTrustEndorsementForm,
)
from apps.bi.models import CatalogAsset, CatalogLineageEdge, DataGovernancePolicy, CatalogTrustEndorsement


# ---------------------------------------------------------------------------
# 1. CatalogAssetForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_asset_form_valid(tenant_a, admin_user):
    """Test valid CatalogAssetForm submission with explicit code."""
    data = {
        "name": "Acme Enterprise Financial Ledger",
        "code": "acme_fin_ledger",
        "domain": "finance",
        "asset_type": "warehouse_table",
        "data_sensitivity": "confidential",
        "enterprise_tier": "tier_1_mission_critical",
        "data_steward": admin_user.pk,
        "is_active": True,
    }
    form = CatalogAssetForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    asset = form.save(commit=False)
    asset.tenant = tenant_a
    asset.save()
    assert asset.code == "acme_fin_ledger"
    assert asset.name == "Acme Enterprise Financial Ledger"


@pytest.mark.django_db
def test_datacatalog_asset_form_autoslug_code(tenant_a):
    """Test that leaving code blank automatically slugifies name (Finding I2)."""
    data = {
        "name": "Customer Master Dataset",
        "code": "",  # Blank code
        "domain": "customer",
        "asset_type": "source_dataset",
        "data_sensitivity": "internal",
        "enterprise_tier": "tier_2_production_core",
        "is_active": True,
    }
    form = CatalogAssetForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["code"] == "customer_master_dataset"


@pytest.mark.django_db
def test_datacatalog_asset_form_system_fields_excluded(tenant_a):
    """Verify system and workflow-controlled fields are excluded (Finding I5)."""
    form = CatalogAssetForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "certification_status" not in form.fields
    assert "view_count" not in form.fields
    assert "average_rating" not in form.fields


# ---------------------------------------------------------------------------
# 2. CatalogAssetCertifyForm & DeprecateForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_asset_certify_form_valid():
    """Test CatalogAssetCertifyForm valid status choice and notes."""
    form = CatalogAssetCertifyForm(data={
        "certification_status": "certified",
        "certification_notes": "Passed data quality SLAs and security audit.",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["certification_status"] == "certified"


@pytest.mark.django_db
def test_datacatalog_asset_certify_form_invalid():
    """Test CatalogAssetCertifyForm rejects invalid status choices."""
    form = CatalogAssetCertifyForm(data={"certification_status": "super_certified"})
    assert not form.is_valid()
    assert "certification_status" in form.errors


@pytest.mark.django_db
def test_datacatalog_asset_deprecate_form_valid(tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test CatalogAssetDeprecateForm with replacement and reason."""
    form = CatalogAssetDeprecateForm(
        data={
            "deprecation_replacement": catalog_asset_tgt_a.pk,
            "deprecation_reason": "Migrated to enhanced sales analytics mart.",
        },
        tenant=tenant_a,
        current_asset=catalog_asset_src_a,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["deprecation_replacement"] == catalog_asset_tgt_a


@pytest.mark.django_db
def test_datacatalog_asset_deprecate_form_requires_reason(tenant_a, catalog_asset_src_a):
    """Test CatalogAssetDeprecateForm rejects empty deprecation reason."""
    form = CatalogAssetDeprecateForm(
        data={"deprecation_reason": ""},
        tenant=tenant_a,
        current_asset=catalog_asset_src_a,
    )
    assert not form.is_valid()
    assert "deprecation_reason" in form.errors


# ---------------------------------------------------------------------------
# 3. CatalogLineageEdgeForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_lineage_edge_form_valid(tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test valid CatalogLineageEdgeForm submission."""
    data = {
        "upstream_asset": catalog_asset_src_a.pk,
        "downstream_asset": catalog_asset_tgt_a.pk,
        "upstream_column": "customer_id",
        "downstream_column": "customer_id",
        "lineage_type": "column_level",
        "impact_criticality": "high",
        "is_active": True,
    }
    form = CatalogLineageEdgeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    edge = form.save(commit=False)
    edge.tenant = tenant_a
    edge.save()
    assert edge.upstream_asset == catalog_asset_src_a
    assert edge.downstream_asset == catalog_asset_tgt_a


@pytest.mark.django_db
def test_datacatalog_lineage_edge_form_excludes_system_fields(tenant_a):
    """Verify tenant and number are excluded from lineage form."""
    form = CatalogLineageEdgeForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields


# ---------------------------------------------------------------------------
# 4. DataGovernancePolicyForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_governance_policy_form_valid(tenant_a, admin_user):
    """Test valid DataGovernancePolicyForm with auto-slugged code."""
    data = {
        "name": "Internal Payment Records Archival Schedule",
        "code": "",  # Blank code
        "policy_type": "retention_archival",
        "regulatory_framework": "sox_financial",
        "enforcement_level": "strict_blocking",
        "masking_algorithm": "none",
        "retention_period_days": 2555,
        "policy_owner": admin_user.pk,
        "effective_date": "2026-01-01",
        "review_frequency_days": 365,
        "is_active": True,
    }
    form = DataGovernancePolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["code"] == "internal_payment_records_archival_schedule"


@pytest.mark.django_db
def test_datacatalog_governance_policy_form_requires_effective_date(tenant_a):
    """Test effective_date is required on policy form."""
    data = {
        "name": "Missing Date Policy",
        "policy_type": "data_retention",
        "enforcement_level": "audit_warning",
    }
    form = DataGovernancePolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "effective_date" in form.errors


# ---------------------------------------------------------------------------
# 5. CatalogTrustEndorsementForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_form_attested_by_excluded(tenant_a):
    """Verify attested_by is excluded to prevent identity spoofing (Finding C1)."""
    form = CatalogTrustEndorsementForm(tenant=tenant_a)
    assert "attested_by" not in form.fields
    assert "tenant" not in form.fields
    assert "number" not in form.fields


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_form_valid(tenant_a, catalog_asset_tgt_a):
    """Test valid CatalogTrustEndorsementForm submission."""
    data = {
        "asset": catalog_asset_tgt_a.pk,
        "endorsement_type": "formal_certification",
        "verdict": "approved_certified",
        "rating_value": 5,
        "review_comments": "Verified dataset schemas and freshness SLAs.",
        "is_active": True,
    }
    form = CatalogTrustEndorsementForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    endorsement = form.save(commit=False)
    assert endorsement.asset == catalog_asset_tgt_a
    assert endorsement.rating_value == 5
