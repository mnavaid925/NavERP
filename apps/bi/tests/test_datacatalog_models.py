"""Unit tests for Sub-module 10.7 Data Catalog, Lineage & Governance models.

Models covered:
- CatalogAsset (BCAT)
- CatalogLineageEdge (BLIN)
- DataGovernancePolicy (BGOV)
- CatalogTrustEndorsement (BTRU)
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.bi.models import (
    CatalogAsset,
    CatalogLineageEdge,
    DataGovernancePolicy,
    CatalogTrustEndorsement,
)


def _datacatalog_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


# ---------------------------------------------------------------------------
# 1. CatalogAsset Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_asset_creation_and_autonumber(tenant_a, admin_user):
    """Test CatalogAsset creation, BCAT- auto-numbering, and default values."""
    asset = CatalogAsset.objects.create(
        tenant=tenant_a,
        name="Customer 360 Analytical Mart",
        code="customer_360_analytical_mart",
        domain="customer",
        asset_type="warehouse_table",
        data_sensitivity="restricted_pii",
        enterprise_tier="tier_1_mission_critical",
        data_steward=admin_user,
    )
    assert asset.NUMBER_PREFIX == "BCAT"
    assert asset.number.startswith("BCAT-")
    assert asset.name == "Customer 360 Analytical Mart"
    assert asset.code == "customer_360_analytical_mart"
    assert asset.certification_status == "draft"
    assert asset.average_rating == Decimal("0.00")
    assert asset.view_count == 0
    assert asset.is_active is True
    assert str(asset) == f"{asset.number} - Customer 360 Analytical Mart"


@pytest.mark.django_db
def test_datacatalog_asset_unique_tenant_code(tenant_a, tenant_b, admin_user):
    """Test that code is unique per tenant but allowed across tenants."""
    CatalogAsset.objects.create(
        tenant=tenant_a,
        name="Asset 1",
        code="sales_ledger",
        data_steward=admin_user,
    )
    with pytest.raises(IntegrityError):
        CatalogAsset.objects.create(
            tenant=tenant_a,
            name="Asset Duplicate",
            code="sales_ledger",
            data_steward=admin_user,
        )

    # Allowed in Tenant B
    asset_b = CatalogAsset.objects.create(
        tenant=tenant_b,
        name="Asset Tenant B",
        code="sales_ledger",
    )
    assert asset_b.code == "sales_ledger"
    assert asset_b.tenant == tenant_b


@pytest.mark.django_db
def test_datacatalog_asset_choices():
    """Verify standard choice tuples match requirements."""
    domain_keys = _datacatalog_choice_keys(CatalogAsset.DOMAIN_CHOICES)
    assert "sales" in domain_keys
    assert "finance" in domain_keys
    assert "customer" in domain_keys
    assert "human_resources" in domain_keys

    type_keys = _datacatalog_choice_keys(CatalogAsset.ASSET_TYPE_CHOICES)
    assert "warehouse_table" in type_keys
    assert "golden_record" in type_keys
    assert "source_dataset" in type_keys
    assert "semantic_model" in type_keys

    cert_keys = _datacatalog_choice_keys(CatalogAsset.CERTIFICATION_STATUS_CHOICES)
    assert "draft" in cert_keys
    assert "certified" in cert_keys
    assert "deprecated" in cert_keys


@pytest.mark.django_db
def test_datacatalog_asset_deprecation_pointer(tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test deprecation pointers to successor assets."""
    catalog_asset_src_a.certification_status = "deprecated"
    catalog_asset_src_a.deprecation_replacement = catalog_asset_tgt_a
    catalog_asset_src_a.save(update_fields=["certification_status", "deprecation_replacement"])

    catalog_asset_src_a.refresh_from_db()
    assert catalog_asset_src_a.certification_status == "deprecated"
    assert catalog_asset_src_a.deprecation_replacement == catalog_asset_tgt_a


# ---------------------------------------------------------------------------
# 2. CatalogLineageEdge Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_lineage_edge_creation(tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test CatalogLineageEdge creation, BLIN- auto-number, and directional link."""
    edge = CatalogLineageEdge.objects.create(
        tenant=tenant_a,
        upstream_asset=catalog_asset_src_a,
        downstream_asset=catalog_asset_tgt_a,
        lineage_type="table_level",
        impact_criticality="critical",
    )
    assert edge.NUMBER_PREFIX == "BLIN"
    assert edge.number.startswith("BLIN-")
    assert edge.upstream_asset == catalog_asset_src_a
    assert edge.downstream_asset == catalog_asset_tgt_a
    assert edge.is_active is True
    assert "BLIN-" in str(edge)
    assert catalog_asset_src_a.code in str(edge)
    assert catalog_asset_tgt_a.code in str(edge)


@pytest.mark.django_db
def test_datacatalog_lineage_edge_column_level(tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test column-level lineage edge string representation and uniqueness."""
    edge = CatalogLineageEdge.objects.create(
        tenant=tenant_a,
        upstream_asset=catalog_asset_src_a,
        downstream_asset=catalog_asset_tgt_a,
        upstream_column="customer_id",
        downstream_column="dim_customer_sk",
        lineage_type="column_level",
        impact_criticality="high",
    )
    assert "customer_id" in str(edge)
    assert "dim_customer_sk" in str(edge)


@pytest.mark.django_db
def test_datacatalog_lineage_edge_multiple_edges(tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test that multiple directional edges can exist (e.g. table-level and column-level)."""
    edge1 = CatalogLineageEdge.objects.create(
        tenant=tenant_a,
        upstream_asset=catalog_asset_src_a,
        downstream_asset=catalog_asset_tgt_a,
        lineage_type="table_level",
    )
    edge2 = CatalogLineageEdge.objects.create(
        tenant=tenant_a,
        upstream_asset=catalog_asset_src_a,
        downstream_asset=catalog_asset_tgt_a,
        upstream_column="id",
        downstream_column="src_id",
        lineage_type="column_level",
    )
    assert edge1.pk != edge2.pk
    assert edge1.number != edge2.number


# ---------------------------------------------------------------------------
# 3. DataGovernancePolicy Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_governance_policy_creation(tenant_a, admin_user):
    """Test DataGovernancePolicy creation, BGOV- auto-number, and default values."""
    policy = DataGovernancePolicy.objects.create(
        tenant=tenant_a,
        name="CCPA Consumer Privacy Policy",
        code="ccpa_consumer_privacy_policy",
        policy_type="regulatory_compliance",
        regulatory_framework="ccpa",
        enforcement_level="strict_blocking",
        retention_period_days=730,
        policy_owner=admin_user,
        effective_date=timezone.now().date(),
    )
    assert policy.NUMBER_PREFIX == "BGOV"
    assert policy.number.startswith("BGOV-")
    assert policy.name == "CCPA Consumer Privacy Policy"
    assert policy.code == "ccpa_consumer_privacy_policy"
    assert policy.enforcement_level == "strict_blocking"
    assert policy.retention_period_days == 730
    assert policy.policy_owner == admin_user
    assert str(policy) == f"{policy.number} - CCPA Consumer Privacy Policy"


@pytest.mark.django_db
def test_datacatalog_governance_policy_unique_code(tenant_a, tenant_b, admin_user):
    """Test unique_together tenant and code on DataGovernancePolicy."""
    DataGovernancePolicy.objects.create(
        tenant=tenant_a,
        name="Policy 1",
        code="global_sec_pol",
        effective_date="2026-01-01",
        policy_owner=admin_user,
    )
    with pytest.raises(IntegrityError):
        DataGovernancePolicy.objects.create(
            tenant=tenant_a,
            name="Policy 2",
            code="global_sec_pol",
            effective_date="2026-01-01",
            policy_owner=admin_user,
        )

    # Allowed in Tenant B
    policy_b = DataGovernancePolicy.objects.create(
        tenant=tenant_b,
        name="Policy Tenant B",
        code="global_sec_pol",
        effective_date="2026-01-01",
    )
    assert policy_b.code == "global_sec_pol"


# ---------------------------------------------------------------------------
# 4. CatalogTrustEndorsement Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_creation(tenant_a, catalog_asset_tgt_a, admin_user):
    """Test CatalogTrustEndorsement creation, BTRU- prefix, and defensive string format."""
    endorsement = CatalogTrustEndorsement.objects.create(
        tenant=tenant_a,
        asset=catalog_asset_tgt_a,
        endorsement_type="formal_certification",
        verdict="approved_certified",
        rating_value=5,
        attested_by=admin_user,
    )
    assert endorsement.NUMBER_PREFIX == "BTRU"
    assert endorsement.number.startswith("BTRU-")
    assert endorsement.rating_value == 5
    assert endorsement.verdict == "approved_certified"
    assert endorsement.attested_by == admin_user
    assert "BTRU-" in str(endorsement)
    assert catalog_asset_tgt_a.name in str(endorsement)


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_ratings(tenant_a, catalog_asset_tgt_a, admin_user):
    """Test trust endorsement ratings and multiple endorsements on single asset."""
    end1 = CatalogTrustEndorsement.objects.create(
        tenant=tenant_a,
        asset=catalog_asset_tgt_a,
        endorsement_type="formal_certification",
        verdict="approved_certified",
        rating_value=5,
        attested_by=admin_user,
    )
    end2 = CatalogTrustEndorsement.objects.create(
        tenant=tenant_a,
        asset=catalog_asset_tgt_a,
        endorsement_type="peer_review",
        verdict="approved_certified",
        rating_value=4,
        attested_by=admin_user,
    )
    assert end1.pk != end2.pk
    assert end1.rating_value == 5
    assert end2.rating_value == 4
