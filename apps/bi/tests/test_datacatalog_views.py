"""Unit tests for Sub-module 10.7 Data Catalog, Lineage & Governance views.

Views covered:
- Overview (catalog_overview)
- CatalogAsset views (list, create, detail, edit, delete, certify, deprecate)
- CatalogLineageEdge views (list, create, detail, edit, delete)
- DataGovernancePolicy views (list, create, detail, edit, delete)
- CatalogTrustEndorsement views (list, create, detail, edit, delete)
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.bi.models import CatalogAsset, CatalogLineageEdge, DataGovernancePolicy, CatalogTrustEndorsement


# ---------------------------------------------------------------------------
# 1. Overview Hub Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_overview_view(client_a, catalog_asset_src_a, catalog_lineage_edge_a, data_governance_policy_a):
    """Test catalog overview hub loads with correct metrics and distributions."""
    url = reverse("bi:catalog_overview")
    response = client_a.get(url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Enterprise Data Catalog & Lineage Hub" in content
    assert "Assets by Domain" in content
    assert "Assets by Sensitivity" in content
    assert response.context["total_assets"] >= 1
    assert response.context["total_lineage_edges"] >= 1
    assert response.context["total_policies"] >= 1


# ---------------------------------------------------------------------------
# 2. CatalogAsset View Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_asset_list_view(client_a, catalog_asset_src_a):
    """Test catalog asset list view with filtering and search."""
    url = reverse("bi:catalog_asset_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "Searchable Data Catalog" in response.content.decode("utf-8")
    assert catalog_asset_src_a.name in response.content.decode("utf-8")

    # Filter by domain
    resp_domain = client_a.get(f"{url}?domain=finance")
    assert resp_domain.status_code == 200
    assert catalog_asset_src_a.name in resp_domain.content.decode("utf-8")

    # Filter by non-matching status
    resp_empty = client_a.get(f"{url}?status=deprecated")
    assert resp_empty.status_code == 200
    assert catalog_asset_src_a.name not in resp_empty.content.decode("utf-8")


@pytest.mark.django_db
def test_datacatalog_asset_create_view(client_a, tenant_a, admin_user):
    """Test catalog asset creation view via GET and POST."""
    url = reverse("bi:catalog_asset_create")
    get_resp = client_a.get(url)
    assert get_resp.status_code == 200
    assert "Register New Catalog Asset" in get_resp.content.decode("utf-8")

    post_resp = client_a.post(url, {
        "name": "New Logistics Stream",
        "code": "new_logistics_stream",
        "domain": "supply_chain",
        "asset_type": "source_dataset",
        "data_sensitivity": "internal",
        "enterprise_tier": "tier_2_production_core",
        "data_steward": admin_user.pk,
        "is_active": True,
    })
    assert post_resp.status_code == 302
    created = CatalogAsset.objects.get(tenant=tenant_a, code="new_logistics_stream")
    assert created.name == "New Logistics Stream"
    assert created.certification_status == "draft"


@pytest.mark.django_db
def test_datacatalog_asset_detail_and_view_count(client_a, catalog_asset_src_a):
    """Test catalog asset detail view increments view_count in memory and DB."""
    initial_views = catalog_asset_src_a.view_count
    url = reverse("bi:catalog_asset_detail", kwargs={"pk": catalog_asset_src_a.pk})
    response = client_a.get(url)
    assert response.status_code == 200
    assert catalog_asset_src_a.name in response.content.decode("utf-8")

    catalog_asset_src_a.refresh_from_db()
    assert catalog_asset_src_a.view_count == initial_views + 1


@pytest.mark.django_db
def test_datacatalog_asset_certify_action_authorized(client_a, catalog_asset_src_a):
    """Test steward certifying asset updates status to certified."""
    url = reverse("bi:catalog_asset_certify", kwargs={"pk": catalog_asset_src_a.pk})
    response = client_a.post(url, {
        "certification_status": "certified",
        "certification_notes": "Meets regulatory compliance standard.",
    })
    assert response.status_code == 302
    catalog_asset_src_a.refresh_from_db()
    assert catalog_asset_src_a.certification_status == "certified"


@pytest.mark.django_db
def test_datacatalog_asset_deprecate_action_authorized(client_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test steward deprecating asset updates status and replacement pointer."""
    url = reverse("bi:catalog_asset_deprecate", kwargs={"pk": catalog_asset_src_a.pk})
    response = client_a.post(url, {
        "deprecation_replacement": catalog_asset_tgt_a.pk,
        "deprecation_reason": "Superseded by sales analytics mart.",
    })
    assert response.status_code == 302
    catalog_asset_src_a.refresh_from_db()
    assert catalog_asset_src_a.certification_status == "deprecated"
    assert catalog_asset_src_a.deprecation_replacement == catalog_asset_tgt_a


@pytest.mark.django_db
def test_datacatalog_asset_delete_action_admin(client_a, tenant_a, catalog_asset_src_a):
    """Test tenant administrator can delete catalog asset via POST."""
    url = reverse("bi:catalog_asset_delete", kwargs={"pk": catalog_asset_src_a.pk})
    response = client_a.post(url)
    assert response.status_code == 302
    assert not CatalogAsset.objects.filter(pk=catalog_asset_src_a.pk).exists()


# ---------------------------------------------------------------------------
# 3. CatalogLineageEdge View Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_lineage_edge_list_view(client_a, catalog_lineage_edge_a, catalog_asset_src_a):
    """Test lineage edge list view and asset filter parameter preservation."""
    url = reverse("bi:catalog_lineage_edge_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert catalog_lineage_edge_a.number in response.content.decode("utf-8")

    # Filter by asset
    resp_asset = client_a.get(f"{url}?asset={catalog_asset_src_a.pk}")
    assert resp_asset.status_code == 200
    assert catalog_lineage_edge_a.number in resp_asset.content.decode("utf-8")


@pytest.mark.django_db
def test_datacatalog_lineage_edge_create_and_detail(client_a, tenant_a, catalog_asset_src_a, catalog_asset_tgt_a):
    """Test creating and viewing a lineage edge."""
    create_url = reverse("bi:catalog_lineage_edge_create")
    post_resp = client_a.post(create_url, {
        "upstream_asset": catalog_asset_src_a.pk,
        "downstream_asset": catalog_asset_tgt_a.pk,
        "lineage_type": "column_level",
        "upstream_column": "amount",
        "downstream_column": "total_amount",
        "impact_criticality": "medium",
        "is_active": True,
    })
    assert post_resp.status_code == 302
    edge = CatalogLineageEdge.objects.get(tenant=tenant_a, upstream_column="amount")

    detail_url = reverse("bi:catalog_lineage_edge_detail", kwargs={"pk": edge.pk})
    detail_resp = client_a.get(detail_url)
    assert detail_resp.status_code == 200
    assert edge.number in detail_resp.content.decode("utf-8")


@pytest.mark.django_db
def test_datacatalog_lineage_edge_delete_admin(client_a, catalog_lineage_edge_a):
    """Test tenant admin can delete lineage edge."""
    url = reverse("bi:catalog_lineage_edge_delete", kwargs={"pk": catalog_lineage_edge_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CatalogLineageEdge.objects.filter(pk=catalog_lineage_edge_a.pk).exists()


# ---------------------------------------------------------------------------
# 4. DataGovernancePolicy View Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_governance_policy_list_and_detail(client_a, data_governance_policy_a):
    """Test policy list and detail views."""
    list_url = reverse("bi:data_governance_policy_list")
    resp_list = client_a.get(list_url)
    assert resp_list.status_code == 200
    assert data_governance_policy_a.name in resp_list.content.decode("utf-8")

    detail_url = reverse("bi:data_governance_policy_detail", kwargs={"pk": data_governance_policy_a.pk})
    resp_detail = client_a.get(detail_url)
    assert resp_detail.status_code == 200
    assert data_governance_policy_a.name in resp_detail.content.decode("utf-8")


@pytest.mark.django_db
def test_datacatalog_governance_policy_create_and_delete(client_a, tenant_a, admin_user):
    """Test creating policy and deleting via tenant admin."""
    create_url = reverse("bi:data_governance_policy_create")
    post_resp = client_a.post(create_url, {
        "name": "Audit Logging Policy",
        "code": "audit_logging_policy",
        "policy_type": "regulatory_compliance",
        "regulatory_framework": "iso_27001",
        "enforcement_level": "strict_blocking",
        "masking_algorithm": "none",
        "effective_date": "2026-01-01",
        "review_frequency_days": 365,
        "policy_owner": admin_user.pk,
        "is_active": True,
    })
    assert post_resp.status_code == 302
    policy = DataGovernancePolicy.objects.get(tenant=tenant_a, code="audit_logging_policy")

    del_url = reverse("bi:data_governance_policy_delete", kwargs={"pk": policy.pk})
    del_resp = client_a.post(del_url)
    assert del_resp.status_code == 302
    assert not DataGovernancePolicy.objects.filter(pk=policy.pk).exists()


# ---------------------------------------------------------------------------
# 5. CatalogTrustEndorsement View Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_list_renders_overall_average(client_a, catalog_trust_endorsement_a):
    """Test endorsement list view passes average_rating_overall in context (Finding I10)."""
    url = reverse("bi:catalog_trust_endorsement_list")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "average_rating_overall" in response.context
    assert response.context["average_rating_overall"] == Decimal("5.00")
    assert "5.00" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_create_and_recalc_rating(client_a, tenant_a, catalog_asset_src_a, admin_user):
    """Test creating endorsement sets attested_by=request.user and updates asset.average_rating (Findings C1 & I3)."""
    assert catalog_asset_src_a.average_rating == Decimal("0.00")
    create_url = reverse("bi:catalog_trust_endorsement_create")
    post_resp = client_a.post(create_url, {
        "asset": catalog_asset_src_a.pk,
        "endorsement_type": "formal_certification",
        "verdict": "approved_certified",
        "rating_value": 4,
        "review_comments": "Verified production quality standards.",
        "is_active": True,
    })
    assert post_resp.status_code == 302
    endorsement = CatalogTrustEndorsement.objects.get(tenant=tenant_a, asset=catalog_asset_src_a)
    assert endorsement.attested_by == admin_user
    assert endorsement.rating_value == 4

    catalog_asset_src_a.refresh_from_db()
    assert catalog_asset_src_a.average_rating == Decimal("4.00")


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_edit_recalcs_rating(client_a, catalog_trust_endorsement_a, catalog_asset_tgt_a):
    """Test editing endorsement rating atomically updates asset.average_rating (Finding I3)."""
    assert catalog_trust_endorsement_a.rating_value == 5
    edit_url = reverse("bi:catalog_trust_endorsement_edit", kwargs={"pk": catalog_trust_endorsement_a.pk})
    post_resp = client_a.post(edit_url, {
        "asset": catalog_asset_tgt_a.pk,
        "endorsement_type": "formal_certification",
        "verdict": "approved_certified",
        "rating_value": 2,
        "review_comments": "Downgraded due to missing lineage tests.",
        "is_active": True,
    })
    assert post_resp.status_code == 302
    catalog_trust_endorsement_a.refresh_from_db()
    assert catalog_trust_endorsement_a.rating_value == 2

    catalog_asset_tgt_a.refresh_from_db()
    assert catalog_asset_tgt_a.average_rating == Decimal("2.00")


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_delete_recalcs_rating(client_a, catalog_trust_endorsement_a, catalog_asset_tgt_a):
    """Test deleting endorsement resets average_rating on asset (Finding I3)."""
    del_url = reverse("bi:catalog_trust_endorsement_delete", kwargs={"pk": catalog_trust_endorsement_a.pk})
    del_resp = client_a.post(del_url)
    assert del_resp.status_code == 302
    assert not CatalogTrustEndorsement.objects.filter(pk=catalog_trust_endorsement_a.pk).exists()

    catalog_asset_tgt_a.refresh_from_db()
    assert catalog_asset_tgt_a.average_rating == Decimal("0.00")
