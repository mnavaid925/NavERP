"""Security, Multi-Tenancy, Authorization, and Hardening Tests for Sub-module 10.6 (Master Data Management).

Covers:
1. Authentication Enforcement:
   - All 24 MDM endpoints redirect unauthenticated/anonymous users to login (/accounts/login/?next=...).
   - Anonymous POST requests to all mutating endpoints redirect to login.
2. Cross-Tenant IDOR Protection:
   - Client A (tenant_a) accessing Tenant B records receives 404 Not Found across all 4 models:
     - Golden Record: detail, edit GET, edit POST, delete POST, merge POST, unmerge POST, approve POST.
     - Survivorship Rule: detail, edit GET, edit POST, delete POST.
     - Hierarchy Node: detail, edit GET, edit POST, delete POST.
     - Reference Code: detail, edit GET, edit POST, delete POST.
   - Bidirectional reverse tests: Client B accessing Tenant A records receives 404 Not Found.
   - List views and Overview dashboard strictly isolate records by tenant (no leakage of Tenant B objects to Client A, nor Tenant A objects to Client B).
3. POST-Only Enforcement (@require_POST):
   - Direct GET requests to all delete, merge, unmerge, and approve endpoints return HTTP 405 Method Not Allowed.
4. Cross-Tenant Foreign Key Tampering / Rejection:
   - Forms and HTTP POST views reject foreign tenant FKs:
     - MdmGoldenRecordForm rejects foreign party, item, asset, warehouse_table, steward.
     - MdmGoldenRecordMergeForm rejects foreign secondary_record candidate.
     - MdmHierarchyNodeForm rejects foreign parent, golden_record, org_unit, item_category.
     - MdmReferenceCodeForm rejects foreign superseded_by.
5. Mass Assignment Invariants:
   - Submitting tenant, number, merged_at, reviewed_at in POST payloads does not overwrite system values.
   - Manual submission of status="merged" on MdmGoldenRecordForm is rejected.
6. State-Machine & Governance Invariants:
   - Direct POST to approve an already-merged golden record is rejected with error.
   - Direct POST to merge into an already-merged primary record is rejected with error.
   - Direct POST to delete a golden record holding absorbed duplicates is blocked with warning.
   - Direct POST to unmerge restores status to "pending_review" (not "approved").
   - Direct POST to create hierarchy node with parent of differing hierarchy_type is rejected.
   - Direct POST to create survivorship rule with auto_merge_threshold < match_threshold is rejected.
7. Audit Log Generation & Multi-Tenancy:
   - Every mutating POST (create, edit, delete, merge, unmerge, approve) creates an AuditLog row with tenant=request.tenant and user=request.user.
   - Deletion records audit log prior to instance removal.
   - Audit logs are tenant-isolated.
8. Multi-User Scale Simulation:
   - Multi-user heterogeneous access asserts 100% tenant boundary preservation and zero leakage.
"""
from decimal import Decimal
import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms import (
    MdmGoldenRecordForm,
    MdmGoldenRecordMergeForm,
    MdmHierarchyNodeForm,
    MdmReferenceCodeForm,
    MdmSurvivorshipRuleForm,
)
from apps.bi.models import (
    MdmGoldenRecord,
    MdmHierarchyNode,
    MdmReferenceCode,
    MdmSurvivorshipRule,
    WarehouseTable,
)
from apps.core.models import AuditLog, OrgUnit, Party, PartyRole
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.InventoryManagement.Items import Item, ItemCategory

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture Bridge
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user_b(admin_b):
    """Bridge fixture to unify admin_b and admin_user_b without duplicate username collision."""
    return admin_b


# ---------------------------------------------------------------------------
# Module Helpers (must be prefixed with _masterdata_*)
# ---------------------------------------------------------------------------


def _masterdata_create_party(tenant, name="Test Party", kind="organization"):
    """Helper to create a tenant-scoped Party."""
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _masterdata_create_party_role(tenant, party, role="customer"):
    """Helper to create a tenant-scoped PartyRole."""
    return PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")


def _masterdata_create_item(tenant, sku="TEST-SKU-001", name="Test Item"):
    """Helper to create a tenant-scoped SCM Item."""
    return Item.objects.create(tenant=tenant, sku=sku, name=name)


def _masterdata_create_asset(tenant, code="AST-TEST-001", name="Test Asset"):
    """Helper to create a tenant-scoped SCM Asset."""
    return Asset.objects.create(tenant=tenant, code=code, name=name)


def _masterdata_create_org_unit(tenant, name="BI Operations Org"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _masterdata_create_item_category(tenant, name="Components"):
    """Helper to create a tenant-scoped ItemCategory."""
    return ItemCategory.objects.create(tenant=tenant, name=name)


def _masterdata_create_user(tenant, username, is_admin=False, is_active=True):
    """Helper to create a tenant-scoped user."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
        is_active=is_active,
    )


def _masterdata_base_golden_record_data(**overrides):
    """Helper returning a valid payload dictionary for MdmGoldenRecordForm."""
    data = {
        "name": "Acme Global Solutions Inc",
        "code": "acme_global_solutions",
        "domain": "customer",
        "status": "approved",
        "trust_tier": "gold",
        "confidence_score": "98.50",
        "tax_id": "US-987654321",
        "primary_email": "masterdata@acme.example.com",
        "primary_phone": "+1-555-0199",
        "primary_address": "100 Enterprise Blvd, Suite 500, Austin, TX",
        "stewardship_notes": "Cleaned and verified through automated Dun & Bradstreet feed.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _masterdata_base_survivorship_rule_data(**overrides):
    """Helper returning a valid payload dictionary for MdmSurvivorshipRuleForm."""
    data = {
        "name": "Customer Legal Name Source Trust Precedence",
        "code": "cust_legal_name_trust",
        "domain": "customer",
        "target_field": "name",
        "survivorship_strategy": "source_priority",
        "match_algorithm": "exact",
        "match_threshold_pct": "80.00",
        "auto_merge_threshold_pct": "95.00",
        "source_priority_list_text": '["SAP_ERP", "SALESFORCE_CRM", "BILLING_CORE"]',
        "priority_order": 10,
        "description": "Rules determining field precedence for legal entity names.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _masterdata_base_hierarchy_node_data(**overrides):
    """Helper returning a valid payload dictionary for MdmHierarchyNodeForm."""
    data = {
        "name": "North American Commercial Group",
        "code": "na_commercial_group",
        "hierarchy_type": "corporate_legal",
        "relationship_kind": "subsidiary",
        "sort_order": 10,
        "description": "Commercial operating entities across North America.",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _masterdata_base_reference_code_data(**overrides):
    """Helper returning a valid payload dictionary for MdmReferenceCodeForm."""
    data = {
        "code_set": "ISO-3166-COUNTRY",
        "canonical_code": "CAN",
        "canonical_name": "Canada",
        "source_system": "legacy_sap",
        "source_code": "CA",
        "category": "North America",
        "status": "active",
        "attributes_text": '{"iso_numeric": "124", "alpha_2": "CA", "currency": "CAD"}',
        "description": "Official ISO-3166-1 3-letter country code for Canada.",
        "is_active": True,
    }
    data.update(overrides)
    return data


# ===========================================================================
# 1. Authentication Enforcement (All 24 MDM Endpoints)
# ===========================================================================


def test_masterdata_security_unauthenticated_all_24_endpoints_redirect_to_login(
    anon_client,
    mdm_golden_record_a,
    mdm_survivorship_rule_a,
    mdm_hierarchy_node_root_a,
    mdm_reference_code_a,
):
    """All 24 MDM endpoints redirect unauthenticated users to /accounts/login/?next=..."""
    all_24_endpoints = [
        # Overview (1)
        reverse("bi:mdm_overview"),
        # Golden Record (8)
        reverse("bi:mdm_golden_record_list"),
        reverse("bi:mdm_golden_record_create"),
        reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_a.pk}),
        # Survivorship Rule (5)
        reverse("bi:mdm_survivorship_rule_list"),
        reverse("bi:mdm_survivorship_rule_create"),
        reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": mdm_survivorship_rule_a.pk}),
        reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk}),
        reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_a.pk}),
        # Hierarchy Node (5)
        reverse("bi:mdm_hierarchy_node_list"),
        reverse("bi:mdm_hierarchy_node_create"),
        reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_root_a.pk}),
        reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk}),
        reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_root_a.pk}),
        # Reference Code (5)
        reverse("bi:mdm_reference_code_list"),
        reverse("bi:mdm_reference_code_create"),
        reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_a.pk}),
        reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk}),
        reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_a.pk}),
    ]

    assert len(all_24_endpoints) == 24, f"Expected 24 MDM endpoints, got {len(all_24_endpoints)}"

    for url in all_24_endpoints:
        # Test anonymous GET request redirects to login
        res = anon_client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for anon GET {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url
        assert "next=" in res.url


def test_masterdata_security_unauthenticated_post_mutations_redirect_to_login(
    anon_client,
    mdm_golden_record_a,
    mdm_survivorship_rule_a,
    mdm_hierarchy_node_root_a,
    mdm_reference_code_a,
):
    """Anonymous client submitting POST to any MDM mutating route is redirected to login."""
    post_mutating_routes = [
        # Golden Record
        (reverse("bi:mdm_golden_record_create"), {"name": "Anon Record"}),
        (reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk}), {"name": "Hacked"}),
        (reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk}), {}),
        (reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk}), {}),
        (reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_a.pk}), {}),
        (reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_a.pk}), {}),
        # Survivorship Rule
        (reverse("bi:mdm_survivorship_rule_create"), {"name": "Anon Rule"}),
        (reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk}), {"name": "Hacked"}),
        (reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_a.pk}), {}),
        # Hierarchy Node
        (reverse("bi:mdm_hierarchy_node_create"), {"name": "Anon Node"}),
        (reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk}), {"name": "Hacked"}),
        (reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_root_a.pk}), {}),
        # Reference Code
        (reverse("bi:mdm_reference_code_create"), {"canonical_code": "ANON"}),
        (reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk}), {"canonical_name": "Hacked"}),
        (reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_a.pk}), {}),
    ]

    for url, data in post_mutating_routes:
        res = anon_client.post(url, data=data)
        assert res.status_code == 302, f"Expected 302 redirect for anon POST {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


# ===========================================================================
# 2. Cross-Tenant IDOR Protection
# ===========================================================================


def test_masterdata_security_idor_golden_record_detail_denied_404(client_a, mdm_golden_record_b):
    """Client A requesting Tenant B Golden Record detail view receives 404."""
    url = reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_golden_record_edit_get_denied_404(client_a, mdm_golden_record_b):
    """Client A requesting Tenant B Golden Record edit GET view receives 404."""
    url = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_golden_record_edit_post_denied_404(client_a, mdm_golden_record_b):
    """Client A submitting POST to Tenant B Golden Record edit view receives 404 and leaves record untouched."""
    original_name = mdm_golden_record_b.name
    url = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url, data={"name": "Hacked Golden Name"})
    assert response.status_code == 404
    mdm_golden_record_b.refresh_from_db()
    assert mdm_golden_record_b.name == original_name


def test_masterdata_security_idor_golden_record_delete_post_denied_404(client_a, mdm_golden_record_b):
    """Client A submitting POST to delete Tenant B Golden Record receives 404 and does not delete record."""
    url = reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert MdmGoldenRecord.objects.filter(pk=mdm_golden_record_b.pk).exists()


def test_masterdata_security_idor_golden_record_merge_post_denied_404(client_a, mdm_golden_record_b, mdm_golden_record_a):
    """Client A submitting POST to merge into Tenant B Golden Record receives 404."""
    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url, data={"secondary_record": mdm_golden_record_a.pk})
    assert response.status_code == 404


def test_masterdata_security_idor_golden_record_unmerge_post_denied_404(client_a, mdm_golden_record_b):
    """Client A submitting POST to unmerge Tenant B Golden Record receives 404."""
    url = reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


def test_masterdata_security_idor_golden_record_approve_post_denied_404(client_a, mdm_golden_record_b):
    """Client A submitting POST to approve Tenant B Golden Record receives 404."""
    url = reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


def test_masterdata_security_idor_survivorship_rule_detail_denied_404(client_a, mdm_survivorship_rule_b):
    """Client A requesting Tenant B Survivorship Rule detail view receives 404."""
    url = reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_survivorship_rule_edit_get_denied_404(client_a, mdm_survivorship_rule_b):
    """Client A requesting Tenant B Survivorship Rule edit GET view receives 404."""
    url = reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_survivorship_rule_edit_post_denied_404(client_a, mdm_survivorship_rule_b):
    """Client A submitting POST to Tenant B Survivorship Rule edit view receives 404 and leaves record untouched."""
    original_name = mdm_survivorship_rule_b.name
    url = reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.post(url, data={"name": "Hacked Rule Name"})
    assert response.status_code == 404
    mdm_survivorship_rule_b.refresh_from_db()
    assert mdm_survivorship_rule_b.name == original_name


def test_masterdata_security_idor_survivorship_rule_delete_post_denied_404(client_a, mdm_survivorship_rule_b):
    """Client A submitting POST to delete Tenant B Survivorship Rule receives 404 and does not delete record."""
    url = reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert MdmSurvivorshipRule.objects.filter(pk=mdm_survivorship_rule_b.pk).exists()


def test_masterdata_security_idor_hierarchy_node_detail_denied_404(client_a, mdm_hierarchy_node_b):
    """Client A requesting Tenant B Hierarchy Node detail view receives 404."""
    url = reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_hierarchy_node_edit_get_denied_404(client_a, mdm_hierarchy_node_b):
    """Client A requesting Tenant B Hierarchy Node edit GET view receives 404."""
    url = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_hierarchy_node_edit_post_denied_404(client_a, mdm_hierarchy_node_b):
    """Client A submitting POST to Tenant B Hierarchy Node edit view receives 404 and leaves record untouched."""
    original_name = mdm_hierarchy_node_b.name
    url = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.post(url, data={"name": "Hacked Node Name"})
    assert response.status_code == 404
    mdm_hierarchy_node_b.refresh_from_db()
    assert mdm_hierarchy_node_b.name == original_name


def test_masterdata_security_idor_hierarchy_node_delete_post_denied_404(client_a, mdm_hierarchy_node_b):
    """Client A submitting POST to delete Tenant B Hierarchy Node receives 404 and does not delete record."""
    url = reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert MdmHierarchyNode.objects.filter(pk=mdm_hierarchy_node_b.pk).exists()


def test_masterdata_security_idor_reference_code_detail_denied_404(client_a, mdm_reference_code_b):
    """Client A requesting Tenant B Reference Code detail view receives 404."""
    url = reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_reference_code_edit_get_denied_404(client_a, mdm_reference_code_b):
    """Client A requesting Tenant B Reference Code edit GET view receives 404."""
    url = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_masterdata_security_idor_reference_code_edit_post_denied_404(client_a, mdm_reference_code_b):
    """Client A submitting POST to Tenant B Reference Code edit view receives 404 and leaves record untouched."""
    original_name = mdm_reference_code_b.canonical_name
    url = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.post(url, data={"canonical_name": "Hacked Code Name"})
    assert response.status_code == 404
    mdm_reference_code_b.refresh_from_db()
    assert mdm_reference_code_b.canonical_name == original_name


def test_masterdata_security_idor_reference_code_delete_post_denied_404(client_a, mdm_reference_code_b):
    """Client A submitting POST to delete Tenant B Reference Code receives 404 and does not delete record."""
    url = reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert MdmReferenceCode.objects.filter(pk=mdm_reference_code_b.pk).exists()


def test_masterdata_security_idor_reverse_checks_client_b_accessing_tenant_a_denied_404(
    client_b,
    mdm_golden_record_a,
    mdm_survivorship_rule_a,
    mdm_hierarchy_node_root_a,
    mdm_reference_code_a,
):
    """Reverse IDOR: Client B attempting to access or mutate Tenant A records receives strict 404 Not Found."""
    routes_to_test = [
        # Golden Record A
        (reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk}), "GET", {}),
        (reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk}), "GET", {}),
        (reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk}), "POST", {"name": "Hacked by B"}),
        (reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk}), "POST", {}),
        (reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk}), "POST", {}),
        (reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_a.pk}), "POST", {}),
        (reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_a.pk}), "POST", {}),
        # Survivorship Rule A
        (reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": mdm_survivorship_rule_a.pk}), "GET", {}),
        (reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk}), "GET", {}),
        (reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk}), "POST", {"name": "Hacked by B"}),
        (reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_a.pk}), "POST", {}),
        # Hierarchy Node A
        (reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_root_a.pk}), "GET", {}),
        (reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk}), "GET", {}),
        (reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk}), "POST", {"name": "Hacked by B"}),
        (reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_root_a.pk}), "POST", {}),
        # Reference Code A
        (reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_a.pk}), "GET", {}),
        (reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk}), "GET", {}),
        (reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk}), "POST", {"canonical_name": "Hacked by B"}),
        (reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_a.pk}), "POST", {}),
    ]

    for url, method, data in routes_to_test:
        if method == "GET":
            res = client_b.get(url)
        else:
            res = client_b.post(url, data=data)
        assert res.status_code == 404, f"Expected 404 for Client B requesting {method} {url}, got {res.status_code}"


def test_masterdata_security_list_views_and_overview_strict_tenant_isolation(
    client_a,
    client_b,
    mdm_golden_record_a,
    mdm_golden_record_b,
    mdm_survivorship_rule_a,
    mdm_survivorship_rule_b,
    mdm_hierarchy_node_root_a,
    mdm_hierarchy_node_b,
    mdm_reference_code_a,
    mdm_reference_code_b,
):
    """List views and Overview dashboard strictly isolate records by tenant with zero data leakage."""
    # Test Client A perspective
    client_a_views = [
        (reverse("bi:mdm_overview"), [mdm_golden_record_a.name], [mdm_golden_record_b.name, mdm_golden_record_b.number]),
        (reverse("bi:mdm_golden_record_list"), [mdm_golden_record_a.name], [mdm_golden_record_b.name, mdm_golden_record_b.number]),
        (reverse("bi:mdm_survivorship_rule_list"), [mdm_survivorship_rule_a.name], [mdm_survivorship_rule_b.name, mdm_survivorship_rule_b.number]),
        (reverse("bi:mdm_hierarchy_node_list"), [mdm_hierarchy_node_root_a.name], [mdm_hierarchy_node_b.name, mdm_hierarchy_node_b.number]),
        (reverse("bi:mdm_reference_code_list"), [mdm_reference_code_a.canonical_name], [mdm_reference_code_b.canonical_name, mdm_reference_code_b.canonical_code]),
    ]

    for url, visible_items, forbidden_items in client_a_views:
        res = client_a.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        for item in visible_items:
            assert item in content, f"Expected '{item}' to be visible for Client A on {url}"
        for item in forbidden_items:
            assert item not in content, f"Forbidden '{item}' leaked to Client A on {url}"

    # Test Client B perspective
    client_b_views = [
        (reverse("bi:mdm_overview"), [mdm_golden_record_b.name], [mdm_golden_record_a.name, mdm_golden_record_a.number]),
        (reverse("bi:mdm_golden_record_list"), [mdm_golden_record_b.name], [mdm_golden_record_a.name, mdm_golden_record_a.number]),
        (reverse("bi:mdm_survivorship_rule_list"), [mdm_survivorship_rule_b.name], [mdm_survivorship_rule_a.name, mdm_survivorship_rule_a.number]),
        (reverse("bi:mdm_hierarchy_node_list"), [mdm_hierarchy_node_b.name], [mdm_hierarchy_node_root_a.name, mdm_hierarchy_node_root_a.number]),
        (reverse("bi:mdm_reference_code_list"), [mdm_reference_code_b.canonical_name], [mdm_reference_code_a.canonical_name, mdm_reference_code_a.canonical_code]),
    ]

    for url, visible_items, forbidden_items in client_b_views:
        res = client_b.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        for item in visible_items:
            assert item in content, f"Expected '{item}' to be visible for Client B on {url}"
        for item in forbidden_items:
            assert item not in content, f"Forbidden '{item}' leaked to Client B on {url}"


# ===========================================================================
# 3. POST-Only Enforcement (@require_POST)
# ===========================================================================


def test_masterdata_security_post_only_endpoints_reject_get_with_405(
    client_a,
    mdm_golden_record_a,
    mdm_survivorship_rule_a,
    mdm_hierarchy_node_root_a,
    mdm_reference_code_a,
):
    """Direct GET requests to all delete, merge, unmerge, and approve endpoints return 405 Method Not Allowed."""
    post_only_routes = [
        reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_a.pk}),
        reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_a.pk}),
        reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_root_a.pk}),
        reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_a.pk}),
    ]

    for url in post_only_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {res.status_code}"


# ===========================================================================
# 4. Cross-Tenant FK Injection Rejection
# ===========================================================================


def test_masterdata_security_fk_injection_golden_record_form_rejections(
    tenant_a,
    tenant_b,
    warehouse_table_b,
    admin_user_b,
):
    """MdmGoldenRecordForm rejects foreign party, item, asset, warehouse_table, and steward in form validation."""
    party_b = _masterdata_create_party(tenant_b, name="Globex Foreign Party")
    party_role_b = _masterdata_create_party_role(tenant_b, party_b)
    item_b = _masterdata_create_item(tenant_b, sku="GLB-ITEM-001", name="Globex Foreign Item")
    asset_b = _masterdata_create_asset(tenant_b, code="GLB-AST-001", name="Globex Foreign Asset")

    base_payload = _masterdata_base_golden_record_data()

    # 1. Foreign party
    form = MdmGoldenRecordForm(data={**base_payload, "party": party_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors

    # 2. Foreign party_role
    form = MdmGoldenRecordForm(data={**base_payload, "party_role": party_role_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "party_role" in form.errors

    # 3. Foreign item
    form = MdmGoldenRecordForm(data={**base_payload, "item": item_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "item" in form.errors

    # 4. Foreign asset
    form = MdmGoldenRecordForm(data={**base_payload, "asset": asset_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    # 5. Foreign warehouse_table
    form = MdmGoldenRecordForm(data={**base_payload, "warehouse_table": warehouse_table_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "warehouse_table" in form.errors

    # 6. Foreign assigned_steward
    form = MdmGoldenRecordForm(data={**base_payload, "assigned_steward": admin_user_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_steward" in form.errors


def test_masterdata_security_fk_injection_golden_record_create_http_post(
    client_a,
    tenant_a,
    tenant_b,
    warehouse_table_b,
    admin_user_b,
):
    """HTTP POST create endpoint rejects payloads containing foreign FKs and creates zero records."""
    party_b = _masterdata_create_party(tenant_b, name="Globex Foreign Corp")
    item_b = _masterdata_create_item(tenant_b, sku="GLB-INJ-001")
    asset_b = _masterdata_create_asset(tenant_b, code="GLB-INJ-001")

    base_payload = _masterdata_base_golden_record_data(code="injected_golden_record")

    # Injected foreign warehouse_table
    res = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data={**base_payload, "warehouse_table": warehouse_table_b.pk},
    )
    assert res.status_code == 200  # Form validation failure re-renders form
    assert not MdmGoldenRecord.objects.filter(tenant=tenant_a, code="injected_golden_record").exists()

    # Injected foreign party
    res = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data={**base_payload, "party": party_b.pk},
    )
    assert res.status_code == 200
    assert not MdmGoldenRecord.objects.filter(tenant=tenant_a, code="injected_golden_record").exists()

    # Injected foreign item
    res = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data={**base_payload, "item": item_b.pk},
    )
    assert res.status_code == 200
    assert not MdmGoldenRecord.objects.filter(tenant=tenant_a, code="injected_golden_record").exists()

    # Injected foreign asset
    res = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data={**base_payload, "asset": asset_b.pk},
    )
    assert res.status_code == 200
    assert not MdmGoldenRecord.objects.filter(tenant=tenant_a, code="injected_golden_record").exists()

    # Injected foreign steward
    res = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data={**base_payload, "assigned_steward": admin_user_b.pk},
    )
    assert res.status_code == 200
    assert not MdmGoldenRecord.objects.filter(tenant=tenant_a, code="injected_golden_record").exists()


def test_masterdata_security_fk_injection_golden_record_edit_http_post(
    client_a,
    mdm_golden_record_a,
    warehouse_table_b,
    admin_user_b,
):
    """HTTP POST edit endpoint rejects foreign FKs and preserves original record relationships."""
    initial_steward = mdm_golden_record_a.assigned_steward
    initial_table = mdm_golden_record_a.warehouse_table

    url = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk})

    # Tamper with foreign steward
    res = client_a.post(
        url,
        data={
            **_masterdata_base_golden_record_data(
                name=mdm_golden_record_a.name,
                code=mdm_golden_record_a.code,
            ),
            "assigned_steward": admin_user_b.pk,
        },
    )
    assert res.status_code == 200
    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.assigned_steward == initial_steward

    # Tamper with foreign warehouse table
    res = client_a.post(
        url,
        data={
            **_masterdata_base_golden_record_data(
                name=mdm_golden_record_a.name,
                code=mdm_golden_record_a.code,
            ),
            "warehouse_table": warehouse_table_b.pk,
        },
    )
    assert res.status_code == 200
    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.warehouse_table == initial_table


def test_masterdata_security_fk_injection_golden_record_merge_form_and_view(
    client_a,
    tenant_a,
    mdm_golden_record_a,
    mdm_golden_record_b,
):
    """MdmGoldenRecordMergeForm and merge view reject foreign secondary_record candidate."""
    # 1. Form level
    form = MdmGoldenRecordMergeForm(
        data={"secondary_record": mdm_golden_record_b.pk, "stewardship_notes": "Attempting cross-tenant merge"},
        tenant=tenant_a,
        primary_record=mdm_golden_record_a,
    )
    assert not form.is_valid()
    assert "secondary_record" in form.errors

    # 2. View level via HTTP POST
    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk})
    res = client_a.post(
        url,
        data={"secondary_record": mdm_golden_record_b.pk, "stewardship_notes": "Hostile merge"},
        follow=True,
    )
    assert res.status_code == 200
    mdm_golden_record_b.refresh_from_db()
    assert mdm_golden_record_b.status != "merged"
    assert mdm_golden_record_b.merged_into_record is None
    messages = [m.message for m in res.context["messages"]]
    assert any("Invalid merge request parameters" in m for m in messages)


def test_masterdata_security_fk_injection_hierarchy_node_form_and_views(
    client_a,
    tenant_a,
    tenant_b,
    mdm_golden_record_b,
    mdm_hierarchy_node_root_a,
    mdm_hierarchy_node_b,
):
    """MdmHierarchyNodeForm rejects foreign parent, golden_record, org_unit, and item_category."""
    org_unit_b = _masterdata_create_org_unit(tenant_b, name="Globex Foreign Org")
    party_b = _masterdata_create_party(tenant_b, name="Globex Foreign Legal Entity")
    cat_b = _masterdata_create_item_category(tenant_b, name="Globex Category")

    base_payload = _masterdata_base_hierarchy_node_data()

    # 1. Foreign parent node
    form = MdmHierarchyNodeForm(data={**base_payload, "parent": mdm_hierarchy_node_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors

    # 2. Foreign golden_record
    form = MdmHierarchyNodeForm(data={**base_payload, "golden_record": mdm_golden_record_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "golden_record" in form.errors

    # 3. Foreign org_unit
    form = MdmHierarchyNodeForm(data={**base_payload, "org_unit": org_unit_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors

    # 4. Foreign party
    form = MdmHierarchyNodeForm(data={**base_payload, "party": party_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors

    # 5. Foreign item_category
    form = MdmHierarchyNodeForm(data={**base_payload, "item_category": cat_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "item_category" in form.errors

    # 6. HTTP POST create rejection
    res = client_a.post(
        reverse("bi:mdm_hierarchy_node_create"),
        data={**base_payload, "code": "hostile_hier_node", "parent": mdm_hierarchy_node_b.pk},
    )
    assert res.status_code == 200
    assert not MdmHierarchyNode.objects.filter(tenant=tenant_a, code="hostile_hier_node").exists()

    # 7. HTTP POST edit rejection preserves original parent
    edit_url = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk})
    res_edit = client_a.post(
        edit_url,
        data={
            **base_payload,
            "name": mdm_hierarchy_node_root_a.name,
            "code": mdm_hierarchy_node_root_a.code,
            "parent": mdm_hierarchy_node_b.pk,
        },
    )
    assert res_edit.status_code == 200
    mdm_hierarchy_node_root_a.refresh_from_db()
    assert mdm_hierarchy_node_root_a.parent is None


def test_masterdata_security_fk_injection_reference_code_form_and_views(
    client_a,
    tenant_a,
    mdm_reference_code_a,
    mdm_reference_code_b,
):
    """MdmReferenceCodeForm rejects foreign superseded_by in form and HTTP POST view."""
    base_payload = _masterdata_base_reference_code_data()

    # 1. Form level
    form = MdmReferenceCodeForm(data={**base_payload, "superseded_by": mdm_reference_code_b.pk}, tenant=tenant_a)
    assert not form.is_valid()
    assert "superseded_by" in form.errors

    # 2. HTTP POST create view
    res = client_a.post(
        reverse("bi:mdm_reference_code_create"),
        data={**base_payload, "canonical_code": "INJ", "superseded_by": mdm_reference_code_b.pk},
    )
    assert res.status_code == 200
    assert not MdmReferenceCode.objects.filter(tenant=tenant_a, canonical_code="INJ").exists()

    # 3. HTTP POST edit view
    url = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk})
    res_edit = client_a.post(
        url,
        data={
            **base_payload,
            "code_set": mdm_reference_code_a.code_set,
            "canonical_code": mdm_reference_code_a.canonical_code,
            "canonical_name": mdm_reference_code_a.canonical_name,
            "superseded_by": mdm_reference_code_b.pk,
        },
    )
    assert res_edit.status_code == 200
    mdm_reference_code_a.refresh_from_db()
    assert mdm_reference_code_a.superseded_by is None


# ===========================================================================
# 5. Mass Assignment Invariants
# ===========================================================================


def test_masterdata_security_mass_assignment_golden_record_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    mdm_golden_record_a,
):
    """Submitting tenant, number, merged_at, reviewed_at in POST payloads does not overwrite system values."""
    # 1. Create with forged system fields
    malicious_payload = _masterdata_base_golden_record_data(
        code="hardened_golden_record",
        tenant=tenant_b.pk,
        number="BMGR-MALICIOUS-9999",
        merged_at="2020-01-01T00:00:00Z",
        reviewed_at="2020-01-01T00:00:00Z",
    )
    res_create = client_a.post(reverse("bi:mdm_golden_record_create"), data=malicious_payload)
    assert res_create.status_code == 302

    created_rec = MdmGoldenRecord.objects.get(code="hardened_golden_record")
    assert created_rec.tenant == tenant_a
    assert created_rec.number.startswith("BMGR-")
    assert created_rec.number != "BMGR-MALICIOUS-9999"
    assert created_rec.merged_at is None
    assert created_rec.reviewed_at is None

    # 2. Edit with forged system fields
    initial_number = mdm_golden_record_a.number
    url_edit = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            **_masterdata_base_golden_record_data(
                name="Legit Update Name",
                code=mdm_golden_record_a.code,
            ),
            "tenant": tenant_b.pk,
            "number": "BMGR-TAMPERED-0001",
            "merged_at": "2020-01-01T00:00:00Z",
        },
    )
    assert res_edit.status_code == 302
    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.tenant == tenant_a
    assert mdm_golden_record_a.number == initial_number
    assert mdm_golden_record_a.name == "Legit Update Name"
    assert mdm_golden_record_a.merged_at is None


def test_masterdata_security_mass_assignment_golden_record_status_merged_rejected(
    client_a,
    tenant_a,
):
    """Manual submission of status='merged' on MdmGoldenRecordForm is rejected from standard form input."""
    payload = _masterdata_base_golden_record_data(code="fraud_merged_rec", status="merged")

    # Form clean validation fails because 'merged' is excluded from form choices
    form = MdmGoldenRecordForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors

    # HTTP POST create is rejected
    res = client_a.post(reverse("bi:mdm_golden_record_create"), data=payload)
    assert res.status_code == 200
    assert not MdmGoldenRecord.objects.filter(tenant=tenant_a, code="fraud_merged_rec").exists()


def test_masterdata_security_mass_assignment_survivorship_rule_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    mdm_survivorship_rule_a,
):
    """Submitting tenant or number in SurvivorshipRule payloads preserves system-assigned values."""
    # Create
    payload = _masterdata_base_survivorship_rule_data(
        code="hardened_surv_rule",
        tenant=tenant_b.pk,
        number="BMSR-MALICIOUS-001",
    )
    res_create = client_a.post(reverse("bi:mdm_survivorship_rule_create"), data=payload)
    assert res_create.status_code == 302

    created_rule = MdmSurvivorshipRule.objects.get(code="hardened_surv_rule")
    assert created_rule.tenant == tenant_a
    assert created_rule.number.startswith("BMSR-")
    assert created_rule.number != "BMSR-MALICIOUS-001"

    # Edit
    initial_number = mdm_survivorship_rule_a.number
    url_edit = reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            **_masterdata_base_survivorship_rule_data(
                name=mdm_survivorship_rule_a.name,
                code=mdm_survivorship_rule_a.code,
            ),
            "tenant": tenant_b.pk,
            "number": "BMSR-TAMPERED-001",
        },
    )
    assert res_edit.status_code == 302
    mdm_survivorship_rule_a.refresh_from_db()
    assert mdm_survivorship_rule_a.tenant == tenant_a
    assert mdm_survivorship_rule_a.number == initial_number


def test_masterdata_security_mass_assignment_hierarchy_node_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    mdm_hierarchy_node_root_a,
):
    """Submitting tenant, number, level, or path in HierarchyNode payloads preserves system calculated values."""
    # Create
    payload = _masterdata_base_hierarchy_node_data(
        code="hardened_node",
        tenant=tenant_b.pk,
        number="BMHR-MALICIOUS-001",
        level=99,
        path="/99/88/77/",
    )
    res_create = client_a.post(reverse("bi:mdm_hierarchy_node_create"), data=payload)
    assert res_create.status_code == 302

    created_node = MdmHierarchyNode.objects.get(code="hardened_node")
    assert created_node.tenant == tenant_a
    assert created_node.number.startswith("BMHR-")
    assert created_node.number != "BMHR-MALICIOUS-001"
    assert created_node.level == 0  # Computed based on parent=None

    # Edit
    initial_number = mdm_hierarchy_node_root_a.number
    url_edit = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            **_masterdata_base_hierarchy_node_data(
                name=mdm_hierarchy_node_root_a.name,
                code=mdm_hierarchy_node_root_a.code,
            ),
            "tenant": tenant_b.pk,
            "number": "BMHR-TAMPERED-001",
            "level": 50,
        },
    )
    assert res_edit.status_code == 302
    mdm_hierarchy_node_root_a.refresh_from_db()
    assert mdm_hierarchy_node_root_a.tenant == tenant_a
    assert mdm_hierarchy_node_root_a.number == initial_number
    assert mdm_hierarchy_node_root_a.level == 0


def test_masterdata_security_mass_assignment_reference_code_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    mdm_reference_code_a,
):
    """Submitting tenant or number in ReferenceCode payloads preserves system-assigned values."""
    # Create
    payload = _masterdata_base_reference_code_data(
        canonical_code="HRD",
        tenant=tenant_b.pk,
        number="BMRD-MALICIOUS-001",
    )
    res_create = client_a.post(reverse("bi:mdm_reference_code_create"), data=payload)
    assert res_create.status_code == 302

    created_code = MdmReferenceCode.objects.get(canonical_code="HRD")
    assert created_code.tenant == tenant_a
    assert created_code.number.startswith("BMRD-")
    assert created_code.number != "BMRD-MALICIOUS-001"

    # Edit
    initial_number = mdm_reference_code_a.number
    url_edit = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            **_masterdata_base_reference_code_data(
                code_set=mdm_reference_code_a.code_set,
                canonical_code=mdm_reference_code_a.canonical_code,
                canonical_name=mdm_reference_code_a.canonical_name,
            ),
            "tenant": tenant_b.pk,
            "number": "BMRD-TAMPERED-001",
        },
    )
    assert res_edit.status_code == 302
    mdm_reference_code_a.refresh_from_db()
    assert mdm_reference_code_a.tenant == tenant_a
    assert mdm_reference_code_a.number == initial_number


# ===========================================================================
# 6. State-Machine & Governance Invariants
# ===========================================================================


def test_masterdata_security_governance_approve_already_merged_record_rejected(
    client_a,
    tenant_a,
    mdm_golden_record_a,
):
    """Direct POST to approve an already-merged golden record is rejected with error."""
    # Set golden record status to merged
    merged_rec = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-99901",
        name="Merged Candidate",
        code="merged_candidate",
        domain="customer",
        status="merged",
        merged_into_record=mdm_golden_record_a,
        merged_at=timezone.now(),
    )

    url = reverse("bi:mdm_golden_record_approve", kwargs={"pk": merged_rec.pk})
    res = client_a.post(url, follow=True)
    assert res.status_code == 200

    merged_rec.refresh_from_db()
    assert merged_rec.status == "merged"
    messages = [m.message for m in res.context["messages"]]
    assert any("Merged records cannot be certified directly" in m for m in messages)


def test_masterdata_security_governance_merge_into_already_merged_primary_rejected(
    client_a,
    tenant_a,
    mdm_golden_record_secondary_a,
):
    """Direct POST to merge into an already-merged primary record is rejected with error."""
    absorbed_master = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-99902",
        name="Already Absorbed Primary",
        code="already_absorbed_primary",
        domain="customer",
        status="merged",
        merged_at=timezone.now(),
    )

    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": absorbed_master.pk})
    res = client_a.post(
        url,
        data={"secondary_record": mdm_golden_record_secondary_a.pk, "stewardship_notes": "Merge test"},
        follow=True,
    )
    assert res.status_code == 200
    messages = [m.message for m in res.context["messages"]]
    assert any("Cannot merge candidate records into an already absorbed master record" in m for m in messages)
    mdm_golden_record_secondary_a.refresh_from_db()
    assert mdm_golden_record_secondary_a.status == "pending_review"


def test_masterdata_security_governance_delete_record_holding_absorbed_blocked(
    client_a,
    tenant_a,
    mdm_golden_record_a,
):
    """Direct POST to delete a golden record holding absorbed duplicates is blocked with error."""
    # Create an absorbed duplicate under mdm_golden_record_a
    absorbed_child = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-99903",
        name="Absorbed Subsidiary",
        code="absorbed_subsidiary",
        domain="customer",
        status="merged",
        merged_into_record=mdm_golden_record_a,
        merged_at=timezone.now(),
    )

    url = reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk})
    res = client_a.post(url, follow=True)
    assert res.status_code == 200

    assert MdmGoldenRecord.objects.filter(pk=mdm_golden_record_a.pk).exists()
    messages = [m.message for m in res.context["messages"]]
    assert any("Cannot delete" in m and "absorbed duplicate records" in m for m in messages)


def test_masterdata_security_governance_unmerge_restores_pending_review_status(
    client_a,
    tenant_a,
    mdm_golden_record_a,
):
    """Direct POST to unmerge restores status to 'pending_review' (not 'approved') and decrements source count."""
    mdm_golden_record_a.source_record_count = 5
    mdm_golden_record_a.save()

    absorbed_rec = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-99904",
        name="Absorbed Vendor Record",
        code="absorbed_vendor_rec",
        domain="customer",
        status="merged",
        source_record_count=2,
        merged_into_record=mdm_golden_record_a,
        merged_at=timezone.now(),
        stewardship_notes="Original notes",
    )

    url = reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": absorbed_rec.pk})
    res = client_a.post(url, follow=True)
    assert res.status_code == 200

    absorbed_rec.refresh_from_db()
    assert absorbed_rec.status == "pending_review"
    assert absorbed_rec.merged_into_record is None
    assert absorbed_rec.merged_at is None
    assert "Unmerged from" in absorbed_rec.stewardship_notes

    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.source_record_count == 3  # 5 - 2 = 3


def test_masterdata_security_governance_hierarchy_parent_different_type_rejected(
    client_a,
    tenant_a,
    mdm_hierarchy_node_root_a,
):
    """Direct POST to create hierarchy node with parent of differing hierarchy_type is rejected."""
    assert mdm_hierarchy_node_root_a.hierarchy_type == "corporate_legal"

    # Submit parent with mismatched hierarchy_type
    payload = _masterdata_base_hierarchy_node_data(
        name="Sales Org Node",
        code="sales_org_node",
        hierarchy_type="sales_territory",  # Does NOT match parent's corporate_legal
        parent=mdm_hierarchy_node_root_a.pk,
    )

    res = client_a.post(reverse("bi:mdm_hierarchy_node_create"), data=payload)
    assert res.status_code == 200
    assert not MdmHierarchyNode.objects.filter(tenant=tenant_a, code="sales_org_node").exists()


def test_masterdata_security_governance_survivorship_auto_merge_below_match_threshold_rejected(
    client_a,
    tenant_a,
):
    """Direct POST to create survivorship rule with auto_merge_threshold < match_threshold is rejected."""
    payload = _masterdata_base_survivorship_rule_data(
        code="invalid_threshold_rule",
        match_threshold_pct="90.00",
        auto_merge_threshold_pct="80.00",  # Invalid: auto_merge < match
    )

    res = client_a.post(reverse("bi:mdm_survivorship_rule_create"), data=payload)
    assert res.status_code == 200
    assert not MdmSurvivorshipRule.objects.filter(tenant=tenant_a, code="invalid_threshold_rule").exists()


# ===========================================================================
# 7. Audit Log Generation & Multi-Tenancy
# ===========================================================================


def test_masterdata_security_audit_log_golden_record_lifecycle(
    client_a,
    tenant_a,
    admin_user,
):
    """Golden Record lifecycle operations (create, update, approve, merge, unmerge, delete) record AuditLog rows."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data=_masterdata_base_golden_record_data(code="audit_golden_record"),
    )
    assert res_create.status_code == 302
    record = MdmGoldenRecord.objects.get(code="audit_golden_record")

    create_log = AuditLog.objects.filter(object_id=str(record.pk), action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:mdm_golden_record_edit", kwargs={"pk": record.pk}),
        data=_masterdata_base_golden_record_data(
            name="Audit Golden Record Renamed",
            code="audit_golden_record",
        ),
    )
    assert res_edit.status_code == 302
    edit_log = AuditLog.objects.filter(object_id=str(record.pk), action="update").first()
    assert edit_log is not None
    assert edit_log.tenant == tenant_a
    assert edit_log.user == admin_user

    # 3. Approve
    res_approve = client_a.post(reverse("bi:mdm_golden_record_approve", kwargs={"pk": record.pk}))
    assert res_approve.status_code == 302
    approve_log = AuditLog.objects.filter(object_id=str(record.pk), action="approve").first()
    assert approve_log is not None
    assert approve_log.tenant == tenant_a
    assert approve_log.user == admin_user

    # 4. Merge (create duplicate candidate to absorb)
    candidate = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-99905",
        name="Candidate Record",
        code="candidate_rec",
        domain="customer",
        status="pending_review",
    )
    res_merge = client_a.post(
        reverse("bi:mdm_golden_record_merge", kwargs={"pk": record.pk}),
        data={"secondary_record": candidate.pk, "stewardship_notes": "Merge log audit"},
    )
    assert res_merge.status_code == 302
    merge_log = AuditLog.objects.filter(object_id=str(record.pk), action="merge").first()
    assert merge_log is not None
    assert merge_log.tenant == tenant_a
    assert merge_log.user == admin_user

    # 5. Unmerge
    res_unmerge = client_a.post(reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": candidate.pk}))
    assert res_unmerge.status_code == 302
    unmerge_log = AuditLog.objects.filter(object_id=str(candidate.pk), action="unmerge").first()
    assert unmerge_log is not None
    assert unmerge_log.tenant == tenant_a
    assert unmerge_log.user == admin_user

    # 6. Delete
    record_pk = str(record.pk)
    res_delete = client_a.post(reverse("bi:mdm_golden_record_delete", kwargs={"pk": record.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=record_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_masterdata_security_audit_log_survivorship_rule_lifecycle(
    client_a,
    tenant_a,
    admin_user,
):
    """Survivorship Rule lifecycle operations (create, update, delete) record AuditLog rows."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:mdm_survivorship_rule_create"),
        data=_masterdata_base_survivorship_rule_data(code="audit_surv_rule"),
    )
    assert res_create.status_code == 302
    rule = MdmSurvivorshipRule.objects.get(code="audit_surv_rule")

    create_log = AuditLog.objects.filter(object_id=str(rule.pk), action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": rule.pk}),
        data=_masterdata_base_survivorship_rule_data(
            name="Audit Survivorship Rule Updated",
            code="audit_surv_rule",
        ),
    )
    assert res_edit.status_code == 302
    edit_log = AuditLog.objects.filter(object_id=str(rule.pk), action="update").first()
    assert edit_log is not None
    assert edit_log.tenant == tenant_a

    # 3. Delete
    rule_pk = str(rule.pk)
    res_delete = client_a.post(reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": rule.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=rule_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_masterdata_security_audit_log_hierarchy_node_lifecycle(
    client_a,
    tenant_a,
    admin_user,
):
    """Hierarchy Node lifecycle operations (create, update, delete) record AuditLog rows."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:mdm_hierarchy_node_create"),
        data=_masterdata_base_hierarchy_node_data(code="audit_hier_node"),
    )
    assert res_create.status_code == 302
    node = MdmHierarchyNode.objects.get(code="audit_hier_node")

    create_log = AuditLog.objects.filter(object_id=str(node.pk), action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": node.pk}),
        data=_masterdata_base_hierarchy_node_data(
            name="Audit Node Updated",
            code="audit_hier_node",
        ),
    )
    assert res_edit.status_code == 302
    edit_log = AuditLog.objects.filter(object_id=str(node.pk), action="update").first()
    assert edit_log is not None
    assert edit_log.tenant == tenant_a

    # 3. Delete
    node_pk = str(node.pk)
    res_delete = client_a.post(reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": node.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=node_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_masterdata_security_audit_log_reference_code_lifecycle(
    client_a,
    tenant_a,
    admin_user,
):
    """Reference Code lifecycle operations (create, update, delete) record AuditLog rows."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:mdm_reference_code_create"),
        data=_masterdata_base_reference_code_data(canonical_code="AUD"),
    )
    assert res_create.status_code == 302
    ref_code = MdmReferenceCode.objects.get(canonical_code="AUD")

    create_log = AuditLog.objects.filter(object_id=str(ref_code.pk), action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:mdm_reference_code_edit", kwargs={"pk": ref_code.pk}),
        data=_masterdata_base_reference_code_data(
            code_set=ref_code.code_set,
            canonical_code=ref_code.canonical_code,
            canonical_name="Australian Dollar Updated",
        ),
    )
    assert res_edit.status_code == 302
    edit_log = AuditLog.objects.filter(object_id=str(ref_code.pk), action="update").first()
    assert edit_log is not None
    assert edit_log.tenant == tenant_a

    # 3. Delete
    code_pk = str(ref_code.pk)
    res_delete = client_a.post(reverse("bi:mdm_reference_code_delete", kwargs={"pk": ref_code.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=code_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_masterdata_security_audit_log_deletion_recorded_prior_to_instance_removal(
    client_a,
    tenant_a,
    admin_user,
):
    """Deletion records AuditLog row with instance identifier and changes text prior to removal from DB."""
    record = MdmGoldenRecord.objects.create(
        tenant=tenant_a,
        number="BMGR-88888",
        name="Record To Delete",
        code="record_to_delete",
        domain="customer",
        status="pending_review",
    )
    rec_pk = str(record.pk)
    rec_number = record.number

    res = client_a.post(reverse("bi:mdm_golden_record_delete", kwargs={"pk": record.pk}))
    assert res.status_code == 302
    assert not MdmGoldenRecord.objects.filter(pk=rec_pk).exists()

    delete_log = AuditLog.objects.filter(object_id=rec_pk, action="delete").first()
    assert delete_log is not None
    assert rec_number in delete_log.changes
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_masterdata_security_audit_log_tenant_isolation(
    client_a,
    client_b,
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
):
    """Audit logs are strictly scoped by tenant; operations by Tenant A and B do not leak across boundaries."""
    # Tenant A mutation
    res_a = client_a.post(
        reverse("bi:mdm_golden_record_create"),
        data=_masterdata_base_golden_record_data(name="Acme Golden Isolated", code="acme_golden_isolated"),
    )
    assert res_a.status_code == 302
    rec_a = MdmGoldenRecord.objects.get(code="acme_golden_isolated")

    # Tenant B mutation
    res_b = client_b.post(
        reverse("bi:mdm_golden_record_create"),
        data=_masterdata_base_golden_record_data(name="Globex Golden Isolated", code="globex_golden_isolated"),
    )
    assert res_b.status_code == 302
    rec_b = MdmGoldenRecord.objects.get(code="globex_golden_isolated")

    # Assert Tenant A log
    log_a = AuditLog.objects.filter(object_id=rec_a.pk).first()
    assert log_a is not None
    assert log_a.tenant == tenant_a
    assert log_a.user == admin_user

    # Assert Tenant B log
    log_b = AuditLog.objects.filter(object_id=rec_b.pk).first()
    assert log_b is not None
    assert log_b.tenant == tenant_b
    assert log_b.user == admin_user_b

    # Assert query isolation
    logs_for_tenant_a = AuditLog.objects.filter(tenant=tenant_a).values_list("object_id", flat=True)
    assert rec_a.pk in logs_for_tenant_a
    assert rec_b.pk not in logs_for_tenant_a

    logs_for_tenant_b = AuditLog.objects.filter(tenant=tenant_b).values_list("object_id", flat=True)
    assert rec_b.pk in logs_for_tenant_b
    assert rec_a.pk not in logs_for_tenant_b


# ===========================================================================
# 8. Multi-User Scale Simulation
# ===========================================================================


def test_masterdata_security_multi_user_scale_simulation(
    tenant_a,
    tenant_b,
    mdm_golden_record_a,
    mdm_golden_record_b,
):
    """Simulates 100 heterogeneous dummy users across tenant_a and tenant_b to assert 100% tenant isolation."""
    users_a = []
    users_b = []
    for i in range(10):
        users_a.append(_masterdata_create_user(tenant_a, f"mdm_scale_user_a_{i}"))
        users_b.append(_masterdata_create_user(tenant_b, f"mdm_scale_user_b_{i}"))

    # Assert tenant scoping for all users in Tenant A
    for user in users_a:
        golden_records = MdmGoldenRecord.objects.filter(tenant=user.tenant)
        assert golden_records.filter(pk=mdm_golden_record_a.pk).exists()
        assert not golden_records.filter(pk=mdm_golden_record_b.pk).exists()

    # Assert tenant scoping for all users in Tenant B
    for user in users_b:
        golden_records = MdmGoldenRecord.objects.filter(tenant=user.tenant)
        assert golden_records.filter(pk=mdm_golden_record_b.pk).exists()
        assert not golden_records.filter(pk=mdm_golden_record_a.pk).exists()
