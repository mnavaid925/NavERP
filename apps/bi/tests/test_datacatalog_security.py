"""Security and multi-tenant isolation tests for Sub-module 10.7 Data Catalog, Lineage & Governance.

Verifies:
- Cross-tenant IDOR protection (404 for foreign tenant objects across all endpoints)
- Tenant list isolation (no cross-tenant leakage)
- Cross-tenant foreign key injection rejection in forms (reject_foreign)
- Authorization and role gates (PermissionDenied / 403 on certify, deprecate, delete, edit)
- Authentication enforcement (@login_required redirects to login)
"""
import pytest
from django.urls import reverse

from apps.bi.forms import (
    CatalogAssetForm,
    CatalogLineageEdgeForm,
    CatalogTrustEndorsementForm,
)
from apps.bi.models import CatalogAsset, CatalogLineageEdge, DataGovernancePolicy, CatalogTrustEndorsement


# ---------------------------------------------------------------------------
# 1. Cross-Tenant IDOR Protection (Tenant A accessing Tenant B -> 404)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_asset_idor_protection(client_a, catalog_asset_b):
    """Assert Tenant A cannot access Tenant B catalog asset endpoints (all return 404)."""
    pk = catalog_asset_b.pk
    detail_url = reverse("bi:catalog_asset_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:catalog_asset_edit", kwargs={"pk": pk})
    del_url = reverse("bi:catalog_asset_delete", kwargs={"pk": pk})
    cert_url = reverse("bi:catalog_asset_certify", kwargs={"pk": pk})
    depr_url = reverse("bi:catalog_asset_deprecate", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404
    assert client_a.post(cert_url, {"certification_status": "certified"}).status_code == 404
    assert client_a.post(depr_url, {"deprecation_reason": "Hack"}).status_code == 404


@pytest.mark.django_db
def test_datacatalog_lineage_edge_idor_protection(client_a, catalog_lineage_edge_b):
    """Assert Tenant A cannot access Tenant B lineage edge endpoints (all return 404)."""
    pk = catalog_lineage_edge_b.pk
    detail_url = reverse("bi:catalog_lineage_edge_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:catalog_lineage_edge_edit", kwargs={"pk": pk})
    del_url = reverse("bi:catalog_lineage_edge_delete", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404


@pytest.mark.django_db
def test_datacatalog_governance_policy_idor_protection(client_a, data_governance_policy_b):
    """Assert Tenant A cannot access Tenant B governance policy endpoints (all return 404)."""
    pk = data_governance_policy_b.pk
    detail_url = reverse("bi:data_governance_policy_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:data_governance_policy_edit", kwargs={"pk": pk})
    del_url = reverse("bi:data_governance_policy_delete", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_idor_protection(client_a, catalog_trust_endorsement_b):
    """Assert Tenant A cannot access Tenant B trust endorsement endpoints (all return 404)."""
    pk = catalog_trust_endorsement_b.pk
    detail_url = reverse("bi:catalog_trust_endorsement_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:catalog_trust_endorsement_edit", kwargs={"pk": pk})
    del_url = reverse("bi:catalog_trust_endorsement_delete", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404


# ---------------------------------------------------------------------------
# 2. Tenant List Isolation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_list_views_tenant_isolation(
    client_a,
    catalog_asset_src_a,
    catalog_asset_b,
    catalog_lineage_edge_a,
    catalog_lineage_edge_b,
    data_governance_policy_a,
    data_governance_policy_b,
    catalog_trust_endorsement_a,
    catalog_trust_endorsement_b,
):
    """Assert list views for Tenant A contain 0 records belonging to Tenant B."""
    # Assets
    asset_resp = client_a.get(reverse("bi:catalog_asset_list"))
    assert catalog_asset_src_a.name in asset_resp.content.decode("utf-8")
    assert catalog_asset_b.name not in asset_resp.content.decode("utf-8")

    # Lineage edges
    edge_resp = client_a.get(reverse("bi:catalog_lineage_edge_list"))
    assert catalog_lineage_edge_a.number in edge_resp.content.decode("utf-8")
    assert catalog_lineage_edge_b.number not in edge_resp.content.decode("utf-8")

    # Governance policies
    policy_resp = client_a.get(reverse("bi:data_governance_policy_list"))
    assert data_governance_policy_a.name in policy_resp.content.decode("utf-8")
    assert data_governance_policy_b.name not in policy_resp.content.decode("utf-8")

    # Trust endorsements
    endorsement_resp = client_a.get(reverse("bi:catalog_trust_endorsement_list"))
    assert catalog_trust_endorsement_a.number in endorsement_resp.content.decode("utf-8")
    assert catalog_trust_endorsement_b.number not in endorsement_resp.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 3. Foreign Tenant Injection in Forms (reject_foreign)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_asset_form_rejects_foreign_tenant_fk(tenant_a, catalog_asset_b):
    """Test CatalogAssetForm rejects foreign tenant deprecation replacement."""
    form = CatalogAssetForm(
        data={
            "name": "Injection Attempt",
            "domain": "finance",
            "asset_type": "warehouse_table",
            "data_sensitivity": "internal",
            "enterprise_tier": "tier_2_production_core",
            "deprecation_replacement": catalog_asset_b.pk,  # Tenant B asset
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "deprecation_replacement" in form.errors


@pytest.mark.django_db
def test_datacatalog_lineage_edge_form_rejects_foreign_tenant_assets(tenant_a, catalog_asset_src_a, catalog_asset_b):
    """Test CatalogLineageEdgeForm rejects foreign tenant upstream or downstream asset."""
    form = CatalogLineageEdgeForm(
        data={
            "upstream_asset": catalog_asset_src_a.pk,
            "downstream_asset": catalog_asset_b.pk,  # Tenant B asset
            "lineage_type": "table_level",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "downstream_asset" in form.errors


@pytest.mark.django_db
def test_datacatalog_trust_endorsement_form_rejects_foreign_tenant_asset(tenant_a, catalog_asset_b):
    """Test CatalogTrustEndorsementForm rejects foreign tenant asset."""
    form = CatalogTrustEndorsementForm(
        data={
            "asset": catalog_asset_b.pk,  # Tenant B asset
            "endorsement_type": "peer_review",
            "verdict": "approved_certified",
            "rating_value": 5,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "asset" in form.errors


# ---------------------------------------------------------------------------
# 4. Authorization & Privilege Gates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_certify_deprecate_unauthorized_user_forbidden(client, member_user, catalog_asset_src_a):
    """Assert non-steward, non-admin user receives 403 on certify and deprecate (Finding C2)."""
    client.force_login(member_user)

    cert_url = reverse("bi:catalog_asset_certify", kwargs={"pk": catalog_asset_src_a.pk})
    cert_resp = client.post(cert_url, {"certification_status": "certified"})
    assert cert_resp.status_code == 403

    depr_url = reverse("bi:catalog_asset_deprecate", kwargs={"pk": catalog_asset_src_a.pk})
    depr_resp = client.post(depr_url, {"deprecation_reason": "Unauthorized deprecation"})
    assert depr_resp.status_code == 403


@pytest.mark.django_db
def test_datacatalog_delete_views_require_tenant_admin(
    client,
    member_user,
    catalog_asset_src_a,
    catalog_lineage_edge_a,
    data_governance_policy_a,
    catalog_trust_endorsement_a,
):
    """Assert non-admin member receives 403 on all delete endpoints (Finding I4)."""
    client.force_login(member_user)

    asset_del = reverse("bi:catalog_asset_delete", kwargs={"pk": catalog_asset_src_a.pk})
    assert client.post(asset_del).status_code == 403

    edge_del = reverse("bi:catalog_lineage_edge_delete", kwargs={"pk": catalog_lineage_edge_a.pk})
    assert client.post(edge_del).status_code == 403

    policy_del = reverse("bi:data_governance_policy_delete", kwargs={"pk": data_governance_policy_a.pk})
    assert client.post(policy_del).status_code == 403

    endorsement_del = reverse("bi:catalog_trust_endorsement_delete", kwargs={"pk": catalog_trust_endorsement_a.pk})
    assert client.post(endorsement_del).status_code == 403


@pytest.mark.django_db
def test_datacatalog_endorsement_edit_unauthorized_user_forbidden(client, member_user, catalog_trust_endorsement_a):
    """Assert user who is not author or admin cannot edit peer endorsement (Finding I4)."""
    client.force_login(member_user)
    url = reverse("bi:catalog_trust_endorsement_edit", kwargs={"pk": catalog_trust_endorsement_a.pk})
    response = client.post(url, {
        "asset": catalog_trust_endorsement_a.asset.pk,
        "endorsement_type": "formal_certification",
        "verdict": "rejected_unfit",
        "rating_value": 1,
    })
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 5. Authentication Enforcement (Anonymous Redirects)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_datacatalog_anonymous_redirects(client, catalog_asset_src_a):
    """Assert unauthenticated requests redirect to login."""
    urls = [
        reverse("bi:catalog_overview"),
        reverse("bi:catalog_asset_list"),
        reverse("bi:catalog_asset_create"),
        reverse("bi:catalog_asset_detail", kwargs={"pk": catalog_asset_src_a.pk}),
        reverse("bi:catalog_asset_edit", kwargs={"pk": catalog_asset_src_a.pk}),
        reverse("bi:catalog_lineage_edge_list"),
        reverse("bi:data_governance_policy_list"),
        reverse("bi:catalog_trust_endorsement_list"),
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response["Location"]
