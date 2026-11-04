"""Unit and integration test suite for Sub-module 10.6 Master Data Management views.

Covers all 24 routes across the 5 Master Data Management components:
1. MDM Overview:
   - bi:mdm_overview (GET 200, context statistics, domain distribution, unauthenticated redirect, empty tenant)
2. MdmGoldenRecord:
   - bi:mdm_golden_record_list (GET 200, filters: domain/status/trust_tier/q, pagination, junk params)
   - bi:mdm_golden_record_detail (GET 200, context vars, absorbed records, hierarchy nodes, 404, IDOR 404)
   - bi:mdm_golden_record_create (GET 200, POST 302 -> detail, form validation errors 200, AuditLog created)
   - bi:mdm_golden_record_edit (GET 200, POST 302 -> detail, IDOR 404, AuditLog created)
   - bi:mdm_golden_record_delete (GET 405, POST 302 -> list, blocked if absorbed records exist, IDOR 404, AuditLog created)
   - bi:mdm_golden_record_merge (GET 405, POST 302 -> detail, crosswalk consolidation, guards for merged primary/secondary, AuditLog created)
   - bi:mdm_golden_record_unmerge (GET 405, POST 302 -> detail, restores pending_review, decrements parent count, AuditLog created)
   - bi:mdm_golden_record_approve (GET 405, POST 302 -> detail, status='approved', reviewed_by/reviewed_at, guard against merged, AuditLog created)
3. MdmSurvivorshipRule:
   - bi:mdm_survivorship_rule_list (GET 200, filters: domain/strategy/match_algorithm/q, pagination, junk params)
   - bi:mdm_survivorship_rule_detail (GET 200, context vars, 404, IDOR 404)
   - bi:mdm_survivorship_rule_create (GET 200, POST 302 -> detail, invalid form 200, AuditLog created)
   - bi:mdm_survivorship_rule_edit (GET 200, POST 302 -> detail, IDOR 404, AuditLog created)
   - bi:mdm_survivorship_rule_delete (GET 405, POST 302 -> list, IDOR 404, AuditLog created)
4. MdmHierarchyNode:
   - bi:mdm_hierarchy_node_list (GET 200, filters: hierarchy_type/level/q, pagination, junk params)
   - bi:mdm_hierarchy_node_detail (GET 200, context vars: node/ancestors/children, 404, IDOR 404)
   - bi:mdm_hierarchy_node_create (GET 200, POST 302 -> detail, invalid form 200, AuditLog created)
   - bi:mdm_hierarchy_node_edit (GET 200, POST 302 -> detail, IDOR 404, AuditLog created)
   - bi:mdm_hierarchy_node_delete (GET 405, POST 302 -> list, IDOR 404, AuditLog created)
5. MdmReferenceCode:
   - bi:mdm_reference_code_list (GET 200, filters: code_set/status/source_system/q, pagination, junk params)
   - bi:mdm_reference_code_detail (GET 200, context vars: reference_code/superseded_by/superseding_codes, 404, IDOR 404)
   - bi:mdm_reference_code_create (GET 200, POST 302 -> detail, invalid form 200, AuditLog created)
   - bi:mdm_reference_code_edit (GET 200, POST 302 -> detail, IDOR 404, AuditLog created)
   - bi:mdm_reference_code_delete (GET 405, POST 302 -> list, IDOR 404, AuditLog created)
"""
from decimal import Decimal
import json

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    MdmGoldenRecord,
    MdmHierarchyNode,
    MdmReferenceCode,
    MdmSurvivorshipRule,
)
from apps.core.models import AuditLog


# ---------------------------------------------------------------------------
# Module-level test helpers (prefixed with _masterdata_*)
# ---------------------------------------------------------------------------


def _masterdata_create_golden_record(tenant, name="Test Golden Record", code="test_golden_rec", **kwargs):
    """Helper to create an MdmGoldenRecord with sane defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "domain": "customer",
        "status": "pending_review",
        "trust_tier": "silver",
        "confidence_score": Decimal("85.00"),
        "source_record_count": 1,
        "source_crosswalks_json": [{"system": "CRM", "id": "100"}],
        "golden_attributes_json": {"city": "Metropolis"},
        "is_active": True,
    }
    defaults.update(kwargs)
    return MdmGoldenRecord.objects.create(**defaults)


def _masterdata_create_survivorship_rule(tenant, name="Test Survivorship Rule", code="test_surv_rule", **kwargs):
    """Helper to create an MdmSurvivorshipRule with sane defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "domain": "customer",
        "target_field": "*",
        "survivorship_strategy": "source_priority",
        "match_algorithm": "exact",
        "match_threshold_pct": Decimal("80.00"),
        "auto_merge_threshold_pct": Decimal("95.00"),
        "source_priority_list_json": ["CRM", "ERP"],
        "priority_order": 10,
        "is_active": True,
    }
    defaults.update(kwargs)
    return MdmSurvivorshipRule.objects.create(**defaults)


def _masterdata_create_hierarchy_node(tenant, name="Test Hierarchy Node", code="test_hier_node", **kwargs):
    """Helper to create an MdmHierarchyNode with sane defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "hierarchy_type": "corporate_legal",
        "relationship_kind": "holding_company",
        "parent": None,
        "level": 0,
        "sort_order": 10,
        "is_active": True,
    }
    defaults.update(kwargs)
    return MdmHierarchyNode.objects.create(**defaults)


def _masterdata_create_reference_code(
    tenant,
    code_set="ISO-4217-CURRENCY",
    canonical_code="USD",
    canonical_name="United States Dollar",
    **kwargs,
):
    """Helper to create an MdmReferenceCode with sane defaults."""
    defaults = {
        "tenant": tenant,
        "code_set": code_set,
        "canonical_code": canonical_code,
        "canonical_name": canonical_name,
        "source_system": "ERP",
        "source_code": canonical_code,
        "status": "active",
        "attributes_json": {"currency_symbol": "$"},
        "is_active": True,
    }
    defaults.update(kwargs)
    return MdmReferenceCode.objects.create(**defaults)


# ===========================================================================
# 1. MDM Overview Views Tests (bi:mdm_overview)
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_overview_unauthenticated_redirects(anon_client):
    """Verify unauthenticated request to bi:mdm_overview redirects to login."""
    url = reverse("bi:mdm_overview")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_masterdata_overview_renders_200_and_context_keys(
    auth_client,
    mdm_golden_record_a,
    mdm_survivorship_rule_a,
    mdm_hierarchy_node_root_a,
    mdm_reference_code_a,
):
    """Verify bi:mdm_overview renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:mdm_overview")
    response = auth_client.get(url)

    assert response.status_code == 200
    expected_keys = [
        "total_golden_records",
        "total_rules",
        "total_hierarchy_nodes",
        "total_reference_codes",
        "gold_tier_count",
        "pending_review_count",
        "domain_distribution",
        "recent_golden_records",
        "survivorship_rules",
        "root_hierarchies",
        "code_set_counts",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in mdm_overview"

    assert response.context["total_golden_records"] >= 1
    assert response.context["total_rules"] >= 1
    assert response.context["total_hierarchy_nodes"] >= 1
    assert response.context["total_reference_codes"] >= 1
    assert mdm_golden_record_a in response.context["recent_golden_records"]
    assert mdm_survivorship_rule_a in response.context["survivorship_rules"]
    assert mdm_hierarchy_node_root_a in response.context["root_hierarchies"]


@pytest.mark.django_db
def test_masterdata_overview_domain_distribution_and_stats(auth_client, tenant_a):
    """Verify statistics aggregation and domain distribution counts."""
    _masterdata_create_golden_record(
        tenant_a,
        name="Vendor Master Record 1",
        code="vmr_1",
        domain="vendor",
        trust_tier="gold",
        status="approved",
    )
    _masterdata_create_golden_record(
        tenant_a,
        name="Product Master Record 1",
        code="pmr_1",
        domain="product",
        trust_tier="silver",
        status="pending_review",
    )

    url = reverse("bi:mdm_overview")
    response = auth_client.get(url)

    assert response.status_code == 200
    distribution = response.context["domain_distribution"]
    domains_present = {d["domain"] for d in distribution}
    assert "vendor" in domains_present
    assert "product" in domains_present
    assert response.context["gold_tier_count"] >= 1
    assert response.context["pending_review_count"] >= 1


@pytest.mark.django_db
def test_masterdata_overview_empty_tenant(client_b, tenant_b):
    """Verify overview renders gracefully with 0 counts when tenant has no records."""
    MdmGoldenRecord.objects.filter(tenant=tenant_b).delete()
    MdmSurvivorshipRule.objects.filter(tenant=tenant_b).delete()
    MdmHierarchyNode.objects.filter(tenant=tenant_b).delete()
    MdmReferenceCode.objects.filter(tenant=tenant_b).delete()

    url = reverse("bi:mdm_overview")
    response = client_b.get(url)

    assert response.status_code == 200
    assert response.context["total_golden_records"] == 0
    assert response.context["total_rules"] == 0
    assert response.context["total_hierarchy_nodes"] == 0
    assert response.context["total_reference_codes"] == 0
    assert response.context["gold_tier_count"] == 0
    assert response.context["pending_review_count"] == 0
    assert list(response.context["domain_distribution"]) == []
    assert list(response.context["recent_golden_records"]) == []
    assert list(response.context["survivorship_rules"]) == []
    assert list(response.context["root_hierarchies"]) == []


# ===========================================================================
# 2. MdmGoldenRecord Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_golden_record_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated request to bi:mdm_golden_record_list redirects to login."""
    url = reverse("bi:mdm_golden_record_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_masterdata_golden_record_list_renders_200_and_context(client_a, mdm_golden_record_a):
    """Verify bi:mdm_golden_record_list renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_golden_record_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "golden_records",
        "domain_choices",
        "status_choices",
        "trust_tier_choices",
        "total_count",
        "gold_count",
        "pending_count",
        "merged_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in golden_record_list"

    assert mdm_golden_record_a in response.context["golden_records"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_masterdata_golden_record_list_filter_domain(client_a, tenant_a):
    """Verify golden record list filters by domain."""
    rec_customer = _masterdata_create_golden_record(
        tenant_a, name="Customer Record", code="cust_rec_f1", domain="customer"
    )
    rec_vendor = _masterdata_create_golden_record(
        tenant_a, name="Vendor Record", code="vend_rec_f1", domain="vendor"
    )

    url = reverse("bi:mdm_golden_record_list")
    response = client_a.get(url, {"domain": "vendor"})

    assert response.status_code == 200
    items = list(response.context["golden_records"])
    assert rec_vendor in items
    assert rec_customer not in items


@pytest.mark.django_db
def test_masterdata_golden_record_list_filter_status(client_a, tenant_a):
    """Verify golden record list filters by status."""
    rec_pending = _masterdata_create_golden_record(
        tenant_a, name="Pending Record", code="pend_rec_f1", status="pending_review"
    )
    rec_approved = _masterdata_create_golden_record(
        tenant_a, name="Approved Record", code="appr_rec_f1", status="approved"
    )

    url = reverse("bi:mdm_golden_record_list")
    response = client_a.get(url, {"status": "pending_review"})

    assert response.status_code == 200
    items = list(response.context["golden_records"])
    assert rec_pending in items
    assert rec_approved not in items


@pytest.mark.django_db
def test_masterdata_golden_record_list_filter_trust_tier(client_a, tenant_a):
    """Verify golden record list filters by trust_tier."""
    rec_gold = _masterdata_create_golden_record(
        tenant_a, name="Gold Tier Entity", code="gold_tier_f1", trust_tier="gold"
    )
    rec_bronze = _masterdata_create_golden_record(
        tenant_a, name="Bronze Tier Entity", code="bronze_tier_f1", trust_tier="bronze"
    )

    url = reverse("bi:mdm_golden_record_list")
    response = client_a.get(url, {"trust_tier": "gold"})

    assert response.status_code == 200
    items = list(response.context["golden_records"])
    assert rec_gold in items
    assert rec_bronze not in items


@pytest.mark.django_db
def test_masterdata_golden_record_list_search_query(client_a, tenant_a):
    """Verify search filter across name, code, number, tax_id, and email."""
    rec_tax = _masterdata_create_golden_record(
        tenant_a,
        name="Target Search Enterprise",
        code="target_search_ent",
        tax_id="US-99887766",
        primary_email="target@enterprise.example",
    )
    rec_other = _masterdata_create_golden_record(
        tenant_a, name="Unrelated Other", code="unrelated_other"
    )

    url = reverse("bi:mdm_golden_record_list")

    # Search by tax_id
    resp_tax = client_a.get(url, {"q": "99887766"})
    assert resp_tax.status_code == 200
    assert rec_tax in resp_tax.context["golden_records"]
    assert rec_other not in resp_tax.context["golden_records"]

    # Search by email
    resp_email = client_a.get(url, {"q": "target@enterprise"})
    assert resp_email.status_code == 200
    assert rec_tax in resp_email.context["golden_records"]

    # Search by code
    resp_code = client_a.get(url, {"q": "target_search"})
    assert resp_code.status_code == 200
    assert rec_tax in resp_code.context["golden_records"]


@pytest.mark.django_db
def test_masterdata_golden_record_list_pagination(client_a, tenant_a):
    """Verify 15 records per page pagination in golden record list."""
    MdmGoldenRecord.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _masterdata_create_golden_record(
            tenant_a, name=f"Pagination Record {i:02d}", code=f"pag_rec_{i:02d}"
        )

    url = reverse("bi:mdm_golden_record_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["page_obj"]) == 1
    assert resp_p2.context["page_obj"].has_previous() is True


@pytest.mark.django_db
def test_masterdata_golden_record_list_junk_parameters_returns_200(client_a, mdm_golden_record_a):
    """Verify junk parameters do not cause 500 error and return 200 gracefully."""
    url = reverse("bi:mdm_golden_record_list")
    response = client_a.get(
        url,
        {
            "domain": "invalid_domain_xyz",
            "status": "not_a_status",
            "trust_tier": "junk_tier",
            "page": "invalid_page_num",
        },
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_masterdata_golden_record_detail_unauthenticated_redirects(anon_client, mdm_golden_record_a):
    """Verify unauthenticated request to golden record detail redirects to login."""
    url = reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk})
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_masterdata_golden_record_detail_renders_200_and_context(client_a, mdm_golden_record_a):
    """Verify bi:mdm_golden_record_detail renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "golden_record",
        "crosswalks",
        "attributes_dict",
        "absorbed_records",
        "hierarchy_nodes",
        "merge_form",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in golden_record_detail"

    assert response.context["golden_record"] == mdm_golden_record_a


@pytest.mark.django_db
def test_masterdata_golden_record_detail_with_absorbed_records_and_hierarchy(
    client_a, tenant_a, mdm_golden_record_a, mdm_golden_record_secondary_a, mdm_hierarchy_node_child_a
):
    """Verify detail context includes absorbed records and hierarchy links."""
    mdm_golden_record_secondary_a.merged_into_record = mdm_golden_record_a
    mdm_golden_record_secondary_a.status = "merged"
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert mdm_golden_record_secondary_a in response.context["absorbed_records"]
    assert mdm_hierarchy_node_child_a in response.context["hierarchy_nodes"]


@pytest.mark.django_db
def test_masterdata_golden_record_detail_404_nonexistent(client_a):
    """Verify detail returns 404 for invalid non-existent primary key."""
    url = reverse("bi:mdm_golden_record_detail", kwargs={"pk": 999999})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_golden_record_detail_idor_404(client_a, mdm_golden_record_b):
    """Verify tenant isolation: accessing tenant B's golden record via client A returns 404."""
    url = reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_golden_record_create_get_renders_200(client_a):
    """Verify GET bi:mdm_golden_record_create renders form with 200."""
    url = reverse("bi:mdm_golden_record_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["golden_record"] is None


@pytest.mark.django_db
def test_masterdata_golden_record_create_post_success(client_a, tenant_a, admin_user):
    """Verify POST bi:mdm_golden_record_create creates record, redirects to detail, and logs audit."""
    url = reverse("bi:mdm_golden_record_create")
    payload = {
        "name": "Omni Global Tech Corp",
        "code": "omni_global_tech_corp",
        "domain": "customer",
        "status": "approved",
        "trust_tier": "gold",
        "confidence_score": "98.75",
        "tax_id": "US-88776655",
        "primary_email": "info@omniglobal.example",
        "assigned_steward": admin_user.pk,
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_rec = MdmGoldenRecord.objects.filter(
        tenant=tenant_a, code="omni_global_tech_corp"
    ).first()
    assert created_rec is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_detail", kwargs={"pk": created_rec.pk})

    # Verify AuditLog creation
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_golden_record_create_post_invalid_form_returns_200(client_a):
    """Verify invalid POST data returns 200 with form validation errors."""
    url = reverse("bi:mdm_golden_record_create")
    payload = {
        "name": "",  # Blank required name
        "confidence_score": "150.00",  # Exceeds max 100.00
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_masterdata_golden_record_edit_get_renders_200(client_a, mdm_golden_record_a):
    """Verify GET bi:mdm_golden_record_edit renders form with 200."""
    url = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["golden_record"] == mdm_golden_record_a


@pytest.mark.django_db
def test_masterdata_golden_record_edit_post_success(client_a, tenant_a, mdm_golden_record_a):
    """Verify POST bi:mdm_golden_record_edit updates record and logs audit."""
    url = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_a.pk})
    payload = {
        "name": "Acme Prime Corporation Revised",
        "code": mdm_golden_record_a.code,
        "domain": mdm_golden_record_a.domain,
        "status": "approved",
        "trust_tier": "silver",
        "confidence_score": "99.95",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk})

    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.name == "Acme Prime Corporation Revised"
    assert mdm_golden_record_a.trust_tier == "silver"
    assert mdm_golden_record_a.confidence_score == Decimal("99.95")

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_golden_record_edit_idor_404(client_a, mdm_golden_record_b):
    """Verify tenant isolation: editing tenant B record via client A returns 404."""
    url = reverse("bi:mdm_golden_record_edit", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url, {"name": "Hacked Name"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_golden_record_delete_get_method_not_allowed(client_a, mdm_golden_record_a):
    """Verify GET bi:mdm_golden_record_delete is rejected with 405 Method Not Allowed."""
    url = reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_golden_record_delete_post_success(client_a, tenant_a):
    """Verify POST bi:mdm_golden_record_delete deletes record and creates AuditLog."""
    rec = _masterdata_create_golden_record(
        tenant_a, name="Record To Delete", code="rec_to_delete_uniq"
    )
    url = reverse("bi:mdm_golden_record_delete", kwargs={"pk": rec.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_list")
    assert not MdmGoldenRecord.objects.filter(pk=rec.pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_golden_record_delete_blocked_if_absorbed_records_exist(
    client_a, tenant_a, mdm_golden_record_a, mdm_golden_record_secondary_a
):
    """Verify delete is blocked with warning message when absorbed duplicate records exist."""
    mdm_golden_record_secondary_a.merged_into_record = mdm_golden_record_a
    mdm_golden_record_secondary_a.status = "merged"
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.post(url)

    # Redirects to detail view with warning message rather than list
    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk})
    assert MdmGoldenRecord.objects.filter(pk=mdm_golden_record_a.pk).exists()

    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert any("has absorbed duplicate records" in m for m in messages)


@pytest.mark.django_db
def test_masterdata_golden_record_delete_idor_404(client_a, mdm_golden_record_b):
    """Verify tenant isolation: deleting tenant B record via client A returns 404."""
    url = reverse("bi:mdm_golden_record_delete", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_golden_record_merge_get_method_not_allowed(client_a, mdm_golden_record_a):
    """Verify GET bi:mdm_golden_record_merge is rejected with 405 Method Not Allowed."""
    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_golden_record_merge_post_success(
    client_a, tenant_a, mdm_golden_record_a, mdm_golden_record_secondary_a
):
    """Verify merge consolidates secondary into primary record, updates counts and logs audit."""
    mdm_golden_record_a.source_record_count = 1
    mdm_golden_record_a.source_crosswalks_json = [{"system": "CRM", "id": "101"}]
    mdm_golden_record_a.save()

    mdm_golden_record_secondary_a.source_record_count = 2
    mdm_golden_record_secondary_a.source_crosswalks_json = [{"system": "ERP", "id": "202"}]
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk})
    payload = {
        "secondary_record": mdm_golden_record_secondary_a.pk,
        "stewardship_notes": "Deterministic merge match validated by data steward.",
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_a.pk})

    mdm_golden_record_secondary_a.refresh_from_db()
    assert mdm_golden_record_secondary_a.status == "merged"
    assert mdm_golden_record_secondary_a.merged_into_record == mdm_golden_record_a
    assert mdm_golden_record_secondary_a.merged_at is not None

    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.source_record_count == 3  # 1 + 2
    crosswalk_systems = [c["system"] for c in mdm_golden_record_a.source_crosswalks_json]
    assert "CRM" in crosswalk_systems
    assert "ERP" in crosswalk_systems

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="merge",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_golden_record_merge_guard_rejects_already_merged_primary(
    client_a, mdm_golden_record_a, mdm_golden_record_secondary_a
):
    """Verify guard rejecting merge attempt when primary record is already merged (I1/I2)."""
    mdm_golden_record_a.status = "merged"
    mdm_golden_record_a.save()

    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk})
    payload = {"secondary_record": mdm_golden_record_secondary_a.pk}
    response = client_a.post(url, payload)

    assert response.status_code == 302
    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert any("already absorbed master record" in m for m in messages)


@pytest.mark.django_db
def test_masterdata_golden_record_merge_guard_rejects_already_merged_secondary(
    client_a, mdm_golden_record_a, mdm_golden_record_secondary_a
):
    """Verify guard rejecting candidate record that is already absorbed (merged)."""
    mdm_golden_record_secondary_a.status = "merged"
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_a.pk})
    payload = {"secondary_record": mdm_golden_record_secondary_a.pk}
    response = client_a.post(url, payload)

    assert response.status_code == 302
    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert any("already been absorbed" in m or "Invalid merge request" in m for m in messages)


@pytest.mark.django_db
def test_masterdata_golden_record_merge_idor_404(client_a, mdm_golden_record_b):
    """Verify tenant isolation: merging into tenant B record via client A returns 404."""
    url = reverse("bi:mdm_golden_record_merge", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url, {"secondary_record": 1})
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_golden_record_unmerge_get_method_not_allowed(client_a, mdm_golden_record_secondary_a):
    """Verify GET bi:mdm_golden_record_unmerge is rejected with 405 Method Not Allowed."""
    url = reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_secondary_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_golden_record_unmerge_post_success(
    client_a, tenant_a, mdm_golden_record_a, mdm_golden_record_secondary_a
):
    """Verify unmerge restores pending_review status, decrements surviving count, and logs audit."""
    mdm_golden_record_a.source_record_count = 5
    mdm_golden_record_a.save()

    mdm_golden_record_secondary_a.status = "merged"
    mdm_golden_record_secondary_a.merged_into_record = mdm_golden_record_a
    mdm_golden_record_secondary_a.merged_at = timezone.now()
    mdm_golden_record_secondary_a.source_record_count = 2
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_secondary_a.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_secondary_a.pk})

    mdm_golden_record_secondary_a.refresh_from_db()
    assert mdm_golden_record_secondary_a.status == "pending_review"
    assert mdm_golden_record_secondary_a.merged_into_record is None
    assert mdm_golden_record_secondary_a.merged_at is None

    mdm_golden_record_a.refresh_from_db()
    assert mdm_golden_record_a.source_record_count == 3  # 5 - 2

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="unmerge",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_golden_record_unmerge_not_merged_record_warning(client_a, mdm_golden_record_a):
    """Verify warning when attempting unmerge on a record that is not merged."""
    mdm_golden_record_a.merged_into_record = None
    mdm_golden_record_a.save()

    url = reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_a.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert any("not merged into any master record" in m for m in messages)


@pytest.mark.django_db
def test_masterdata_golden_record_unmerge_idor_404(client_a, mdm_golden_record_b):
    """Verify tenant isolation: unmerging tenant B record via client A returns 404."""
    url = reverse("bi:mdm_golden_record_unmerge", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_golden_record_approve_get_method_not_allowed(client_a, mdm_golden_record_secondary_a):
    """Verify GET bi:mdm_golden_record_approve is rejected with 405 Method Not Allowed."""
    url = reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_secondary_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_golden_record_approve_post_success(
    client_a, tenant_a, mdm_golden_record_secondary_a, admin_user
):
    """Verify approve sets status='approved', sets reviewer and timestamp, and logs audit."""
    mdm_golden_record_secondary_a.status = "pending_review"
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_secondary_a.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_golden_record_detail", kwargs={"pk": mdm_golden_record_secondary_a.pk})

    mdm_golden_record_secondary_a.refresh_from_db()
    assert mdm_golden_record_secondary_a.status == "approved"
    assert mdm_golden_record_secondary_a.reviewed_by == admin_user
    assert mdm_golden_record_secondary_a.reviewed_at is not None

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="approve",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_golden_record_approve_guard_rejects_merged_record(client_a, mdm_golden_record_secondary_a):
    """Verify guard rejecting certification approval for already merged records (I1)."""
    mdm_golden_record_secondary_a.status = "merged"
    mdm_golden_record_secondary_a.save()

    url = reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_secondary_a.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    mdm_golden_record_secondary_a.refresh_from_db()
    assert mdm_golden_record_secondary_a.status == "merged"

    messages = [m.message for m in get_messages(response.wsgi_request)]
    assert any("Merged records cannot be certified directly" in m for m in messages)


@pytest.mark.django_db
def test_masterdata_golden_record_approve_idor_404(client_a, mdm_golden_record_b):
    """Verify tenant isolation: approving tenant B record via client A returns 404."""
    url = reverse("bi:mdm_golden_record_approve", kwargs={"pk": mdm_golden_record_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


# ===========================================================================
# 3. MdmSurvivorshipRule Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_survivorship_rule_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated request to bi:mdm_survivorship_rule_list redirects to login."""
    url = reverse("bi:mdm_survivorship_rule_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_masterdata_survivorship_rule_list_renders_200_and_context(client_a, mdm_survivorship_rule_a):
    """Verify bi:mdm_survivorship_rule_list renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_survivorship_rule_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "rules",
        "domain_choices",
        "strategy_choices",
        "match_choices",
        "total_count",
        "active_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in survivorship_rule_list"

    assert mdm_survivorship_rule_a in response.context["rules"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_masterdata_survivorship_rule_list_filters(client_a, tenant_a):
    """Verify filtering by domain, survivorship_strategy, match_algorithm, and search query."""
    rule1 = _masterdata_create_survivorship_rule(
        tenant_a,
        name="Vendor Fuzzy Match Rule",
        code="vend_fuzzy_r1",
        domain="vendor",
        survivorship_strategy="most_recent",
        match_algorithm="fuzzy_levenshtein",
    )
    rule2 = _masterdata_create_survivorship_rule(
        tenant_a,
        name="Customer Exact Match Rule",
        code="cust_exact_r2",
        domain="customer",
        survivorship_strategy="source_priority",
        match_algorithm="exact",
    )

    url = reverse("bi:mdm_survivorship_rule_list")

    # Filter domain
    resp_dom = client_a.get(url, {"domain": "vendor"})
    assert resp_dom.status_code == 200
    assert rule1 in resp_dom.context["rules"]
    assert rule2 not in resp_dom.context["rules"]

    # Filter strategy
    resp_strat = client_a.get(url, {"survivorship_strategy": "most_recent"})
    assert resp_strat.status_code == 200
    assert rule1 in resp_strat.context["rules"]
    assert rule2 not in resp_strat.context["rules"]

    # Filter match algorithm
    resp_alg = client_a.get(url, {"match_algorithm": "fuzzy_levenshtein"})
    assert resp_alg.status_code == 200
    assert rule1 in resp_alg.context["rules"]
    assert rule2 not in resp_alg.context["rules"]

    # Search query
    resp_q = client_a.get(url, {"q": "Fuzzy Match"})
    assert resp_q.status_code == 200
    assert rule1 in resp_q.context["rules"]
    assert rule2 not in resp_q.context["rules"]


@pytest.mark.django_db
def test_masterdata_survivorship_rule_list_pagination(client_a, tenant_a):
    """Verify 15 records per page pagination in survivorship rule list."""
    MdmSurvivorshipRule.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _masterdata_create_survivorship_rule(
            tenant_a, name=f"Pagination Rule {i:02d}", code=f"pag_rule_{i:02d}"
        )

    url = reverse("bi:mdm_survivorship_rule_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["page_obj"]) == 1


@pytest.mark.django_db
def test_masterdata_survivorship_rule_list_junk_parameters_returns_200(client_a, mdm_survivorship_rule_a):
    """Verify junk filter values return 200 without error."""
    url = reverse("bi:mdm_survivorship_rule_list")
    response = client_a.get(
        url,
        {
            "domain": "junk_domain",
            "survivorship_strategy": "junk_strategy",
            "match_algorithm": "junk_algo",
            "page": "invalid",
        },
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_masterdata_survivorship_rule_detail_renders_200_and_context(client_a, mdm_survivorship_rule_a):
    """Verify bi:mdm_survivorship_rule_detail renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": mdm_survivorship_rule_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "rule" in response.context
    assert "source_priority_list" in response.context
    assert response.context["rule"] == mdm_survivorship_rule_a


@pytest.mark.django_db
def test_masterdata_survivorship_rule_detail_404_nonexistent(client_a):
    """Verify detail returns 404 for invalid rule pk."""
    url = reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": 999999})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_survivorship_rule_detail_idor_404(client_a, mdm_survivorship_rule_b):
    """Verify tenant isolation: accessing tenant B rule via client A returns 404."""
    url = reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_survivorship_rule_create_get_renders_200(client_a):
    """Verify GET bi:mdm_survivorship_rule_create renders 200 with empty form."""
    url = reverse("bi:mdm_survivorship_rule_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["rule"] is None


@pytest.mark.django_db
def test_masterdata_survivorship_rule_create_post_success(client_a, tenant_a, admin_user):
    """Verify POST bi:mdm_survivorship_rule_create creates rule, redirects to detail, and logs audit."""
    url = reverse("bi:mdm_survivorship_rule_create")
    payload = {
        "name": "Product SKU Canonical Rule",
        "code": "product_sku_canonical_rule",
        "domain": "product",
        "target_field": "sku",
        "survivorship_strategy": "source_priority",
        "source_priority_list_text": '["SAP_ERP", "LEGACY_CATALOG", "WEB_SHOP"]',
        "match_algorithm": "exact",
        "match_threshold_pct": "85.00",
        "auto_merge_threshold_pct": "98.00",
        "priority_order": "15",
        "steward": admin_user.pk,
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_rule = MdmSurvivorshipRule.objects.filter(
        tenant=tenant_a, code="product_sku_canonical_rule"
    ).first()
    assert created_rule is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": created_rule.pk})

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_survivorship_rule_create_post_invalid_thresholds_returns_200(client_a):
    """Verify validation error when auto-merge threshold is less than match threshold."""
    url = reverse("bi:mdm_survivorship_rule_create")
    payload = {
        "name": "Invalid Threshold Rule",
        "code": "inv_thresh_rule",
        "match_threshold_pct": "90.00",
        "auto_merge_threshold_pct": "80.00",  # Invalid: auto-merge < match
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "auto_merge_threshold_pct" in response.context["form"].errors


@pytest.mark.django_db
def test_masterdata_survivorship_rule_edit_get_renders_200(client_a, mdm_survivorship_rule_a):
    """Verify GET bi:mdm_survivorship_rule_edit renders form with 200."""
    url = reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["rule"] == mdm_survivorship_rule_a


@pytest.mark.django_db
def test_masterdata_survivorship_rule_edit_post_success(client_a, tenant_a, mdm_survivorship_rule_a):
    """Verify POST bi:mdm_survivorship_rule_edit updates rule and logs audit."""
    url = reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_a.pk})
    payload = {
        "name": "Acme Customer Survivorship Rule Modified",
        "code": mdm_survivorship_rule_a.code,
        "domain": mdm_survivorship_rule_a.domain,
        "target_field": "*",
        "survivorship_strategy": "highest_completeness",
        "match_algorithm": "exact",
        "match_threshold_pct": "82.50",
        "auto_merge_threshold_pct": "96.00",
        "priority_order": "5",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_survivorship_rule_detail", kwargs={"pk": mdm_survivorship_rule_a.pk})

    mdm_survivorship_rule_a.refresh_from_db()
    assert mdm_survivorship_rule_a.name == "Acme Customer Survivorship Rule Modified"
    assert mdm_survivorship_rule_a.survivorship_strategy == "highest_completeness"

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_survivorship_rule_edit_idor_404(client_a, mdm_survivorship_rule_b):
    """Verify tenant isolation: editing tenant B rule via client A returns 404."""
    url = reverse("bi:mdm_survivorship_rule_edit", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.post(url, {"name": "Hacked Rule"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_survivorship_rule_delete_get_method_not_allowed(client_a, mdm_survivorship_rule_a):
    """Verify GET bi:mdm_survivorship_rule_delete returns 405 Method Not Allowed."""
    url = reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_survivorship_rule_delete_post_success(client_a, tenant_a):
    """Verify POST bi:mdm_survivorship_rule_delete deletes rule and logs audit."""
    rule = _masterdata_create_survivorship_rule(
        tenant_a, name="Rule To Delete", code="rule_to_delete_uniq"
    )
    url = reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": rule.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_survivorship_rule_list")
    assert not MdmSurvivorshipRule.objects.filter(pk=rule.pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_survivorship_rule_delete_idor_404(client_a, mdm_survivorship_rule_b):
    """Verify tenant isolation: deleting tenant B rule via client A returns 404."""
    url = reverse("bi:mdm_survivorship_rule_delete", kwargs={"pk": mdm_survivorship_rule_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


# ===========================================================================
# 4. MdmHierarchyNode Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_hierarchy_node_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated request to bi:mdm_hierarchy_node_list redirects to login."""
    url = reverse("bi:mdm_hierarchy_node_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_masterdata_hierarchy_node_list_renders_200_and_context(client_a, mdm_hierarchy_node_root_a):
    """Verify bi:mdm_hierarchy_node_list renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_hierarchy_node_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "hierarchy_nodes",
        "hierarchy_type_choices",
        "total_count",
        "root_nodes_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in hierarchy_node_list"

    assert mdm_hierarchy_node_root_a in response.context["hierarchy_nodes"]
    assert response.context["total_count"] >= 1
    assert response.context["root_nodes_count"] >= 1


@pytest.mark.django_db
def test_masterdata_hierarchy_node_list_filters(client_a, tenant_a):
    """Verify hierarchy node list filters by hierarchy_type, level, and search query."""
    node1 = _masterdata_create_hierarchy_node(
        tenant_a,
        name="Sales North America",
        code="sales_na_f1",
        hierarchy_type="account_group",
        level=0,
    )
    node2 = _masterdata_create_hierarchy_node(
        tenant_a,
        name="Corporate Holding",
        code="corp_holding_f1",
        hierarchy_type="corporate_legal",
        level=0,
    )

    url = reverse("bi:mdm_hierarchy_node_list")

    # Filter hierarchy_type
    resp_type = client_a.get(url, {"hierarchy_type": "account_group"})
    assert resp_type.status_code == 200
    assert node1 in resp_type.context["hierarchy_nodes"]
    assert node2 not in resp_type.context["hierarchy_nodes"]

    # Filter level
    resp_lvl = client_a.get(url, {"level": "0"})
    assert resp_lvl.status_code == 200
    assert node1 in resp_lvl.context["hierarchy_nodes"]

    # Search query
    resp_q = client_a.get(url, {"q": "Sales North"})
    assert resp_q.status_code == 200
    assert node1 in resp_q.context["hierarchy_nodes"]
    assert node2 not in resp_q.context["hierarchy_nodes"]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_list_pagination(client_a, tenant_a):
    """Verify 15 records per page pagination in hierarchy node list."""
    MdmHierarchyNode.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _masterdata_create_hierarchy_node(
            tenant_a, name=f"Pagination Node {i:02d}", code=f"pag_node_{i:02d}"
        )

    url = reverse("bi:mdm_hierarchy_node_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["page_obj"]) == 1


@pytest.mark.django_db
def test_masterdata_hierarchy_node_list_junk_parameters_returns_200(client_a, mdm_hierarchy_node_root_a):
    """Verify junk filter parameters do not crash and return 200."""
    url = reverse("bi:mdm_hierarchy_node_list")
    response = client_a.get(
        url,
        {
            "hierarchy_type": "junk_type",
            "level": "not_an_int",
            "page": "junk_page",
        },
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_masterdata_hierarchy_node_detail_renders_200_and_context(
    client_a, mdm_hierarchy_node_root_a, mdm_hierarchy_node_child_a
):
    """Verify bi:mdm_hierarchy_node_detail renders HTTP 200 with node, ancestors, and children."""
    url = reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_root_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "node" in response.context
    assert "children" in response.context
    assert "ancestors" in response.context
    assert response.context["node"] == mdm_hierarchy_node_root_a
    assert mdm_hierarchy_node_child_a in response.context["children"]


@pytest.mark.django_db
def test_masterdata_hierarchy_node_detail_child_with_ancestors(
    client_a, mdm_hierarchy_node_root_a, mdm_hierarchy_node_child_a
):
    """Verify child node detail properly includes root ancestor in context."""
    url = reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_child_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    ancestors = list(response.context["ancestors"])
    assert mdm_hierarchy_node_root_a in ancestors


@pytest.mark.django_db
def test_masterdata_hierarchy_node_detail_404_nonexistent(client_a):
    """Verify detail returns 404 for invalid node pk."""
    url = reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": 999999})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_hierarchy_node_detail_idor_404(client_a, mdm_hierarchy_node_b):
    """Verify tenant isolation: accessing tenant B hierarchy node via client A returns 404."""
    url = reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_hierarchy_node_create_get_renders_200(client_a):
    """Verify GET bi:mdm_hierarchy_node_create renders 200 with empty form."""
    url = reverse("bi:mdm_hierarchy_node_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["node"] is None


@pytest.mark.django_db
def test_masterdata_hierarchy_node_create_post_success(client_a, tenant_a):
    """Verify POST bi:mdm_hierarchy_node_create creates node, redirects to detail, and logs audit."""
    url = reverse("bi:mdm_hierarchy_node_create")
    payload = {
        "name": "Western European Business Unit",
        "code": "weur_biz_unit",
        "hierarchy_type": "corporate_legal",
        "relationship_kind": "division",
        "sort_order": "25",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_node = MdmHierarchyNode.objects.filter(
        tenant=tenant_a, code="weur_biz_unit"
    ).first()
    assert created_node is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": created_node.pk})

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_hierarchy_node_create_post_invalid_mismatched_parent_type(
    client_a, tenant_a, mdm_hierarchy_node_root_a
):
    """Verify form rejection when node hierarchy_type does not match parent's hierarchy_type."""
    url = reverse("bi:mdm_hierarchy_node_create")
    payload = {
        "name": "Invalid Mismatched Child",
        "code": "inv_mismatched_child",
        "hierarchy_type": "product_taxonomy",  # Parent is corporate_legal
        "parent": mdm_hierarchy_node_root_a.pk,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "parent" in response.context["form"].errors


@pytest.mark.django_db
def test_masterdata_hierarchy_node_edit_get_renders_200(client_a, mdm_hierarchy_node_root_a):
    """Verify GET bi:mdm_hierarchy_node_edit renders form with 200."""
    url = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["node"] == mdm_hierarchy_node_root_a


@pytest.mark.django_db
def test_masterdata_hierarchy_node_edit_post_success(client_a, tenant_a, mdm_hierarchy_node_root_a):
    """Verify POST bi:mdm_hierarchy_node_edit updates node and logs audit."""
    url = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_root_a.pk})
    payload = {
        "name": "Acme Global Enterprise Group Updated",
        "code": mdm_hierarchy_node_root_a.code,
        "hierarchy_type": mdm_hierarchy_node_root_a.hierarchy_type,
        "relationship_kind": "holding_company",
        "sort_order": "5",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_hierarchy_node_detail", kwargs={"pk": mdm_hierarchy_node_root_a.pk})

    mdm_hierarchy_node_root_a.refresh_from_db()
    assert mdm_hierarchy_node_root_a.name == "Acme Global Enterprise Group Updated"
    assert mdm_hierarchy_node_root_a.sort_order == 5

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_hierarchy_node_edit_idor_404(client_a, mdm_hierarchy_node_b):
    """Verify tenant isolation: editing tenant B hierarchy node via client A returns 404."""
    url = reverse("bi:mdm_hierarchy_node_edit", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.post(url, {"name": "Hacked Node"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_hierarchy_node_delete_get_method_not_allowed(client_a, mdm_hierarchy_node_root_a):
    """Verify GET bi:mdm_hierarchy_node_delete returns 405 Method Not Allowed."""
    url = reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_root_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_hierarchy_node_delete_post_success(client_a, tenant_a):
    """Verify POST bi:mdm_hierarchy_node_delete deletes node and logs audit."""
    node = _masterdata_create_hierarchy_node(
        tenant_a, name="Node To Delete", code="node_to_delete_uniq"
    )
    url = reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": node.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_hierarchy_node_list")
    assert not MdmHierarchyNode.objects.filter(pk=node.pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_hierarchy_node_delete_idor_404(client_a, mdm_hierarchy_node_b):
    """Verify tenant isolation: deleting tenant B hierarchy node via client A returns 404."""
    url = reverse("bi:mdm_hierarchy_node_delete", kwargs={"pk": mdm_hierarchy_node_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


# ===========================================================================
# 5. MdmReferenceCode Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_masterdata_reference_code_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated request to bi:mdm_reference_code_list redirects to login."""
    url = reverse("bi:mdm_reference_code_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_masterdata_reference_code_list_renders_200_and_context(client_a, mdm_reference_code_a):
    """Verify bi:mdm_reference_code_list renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_reference_code_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "reference_codes",
        "status_choices",
        "code_sets",
        "total_count",
        "active_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in reference_code_list"

    assert mdm_reference_code_a in response.context["reference_codes"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_masterdata_reference_code_list_filters(client_a, tenant_a):
    """Verify filtering by code_set, status, source_system, and search query."""
    code1 = _masterdata_create_reference_code(
        tenant_a,
        code_set="ISO-3166-COUNTRY",
        canonical_code="USA",
        canonical_name="United States of America",
        source_system="SAP",
        source_code="US",
        status="active",
    )
    code2 = _masterdata_create_reference_code(
        tenant_a,
        code_set="PAYMENT-TERMS",
        canonical_code="NET30",
        canonical_name="Net 30 Days",
        source_system="ORACLE",
        source_code="N30",
        status="deprecated",
    )

    url = reverse("bi:mdm_reference_code_list")

    # Filter code_set
    resp_cset = client_a.get(url, {"code_set": "ISO-3166-COUNTRY"})
    assert resp_cset.status_code == 200
    assert code1 in resp_cset.context["reference_codes"]
    assert code2 not in resp_cset.context["reference_codes"]

    # Filter status
    resp_stat = client_a.get(url, {"status": "deprecated"})
    assert resp_stat.status_code == 200
    assert code2 in resp_stat.context["reference_codes"]
    assert code1 not in resp_stat.context["reference_codes"]

    # Filter source_system
    resp_src = client_a.get(url, {"source_system": "SAP"})
    assert resp_src.status_code == 200
    assert code1 in resp_src.context["reference_codes"]
    assert code2 not in resp_src.context["reference_codes"]

    # Search query
    resp_q = client_a.get(url, {"q": "NET30"})
    assert resp_q.status_code == 200
    assert code2 in resp_q.context["reference_codes"]
    assert code1 not in resp_q.context["reference_codes"]


@pytest.mark.django_db
def test_masterdata_reference_code_list_pagination(client_a, tenant_a):
    """Verify 15 records per page pagination in reference code list."""
    MdmReferenceCode.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _masterdata_create_reference_code(
            tenant_a,
            code_set="PAG-SET",
            canonical_code=f"CODE_{i:02d}",
            canonical_name=f"Pagination Code {i:02d}",
            source_system="CRM",
            source_code=f"SRC_{i:02d}",
        )

    url = reverse("bi:mdm_reference_code_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["page_obj"]) == 1


@pytest.mark.django_db
def test_masterdata_reference_code_list_junk_parameters_returns_200(client_a, mdm_reference_code_a):
    """Verify junk filter values return 200 without crashing."""
    url = reverse("bi:mdm_reference_code_list")
    response = client_a.get(
        url,
        {
            "code_set": "junk_set",
            "status": "junk_status",
            "source_system": "junk_system",
            "page": "junk_page",
        },
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_masterdata_reference_code_detail_renders_200_and_context(client_a, mdm_reference_code_a):
    """Verify bi:mdm_reference_code_detail renders HTTP 200 with required context keys."""
    url = reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = ["reference_code", "superseded_by", "superseding_codes"]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in reference_code_detail"

    assert response.context["reference_code"] == mdm_reference_code_a


@pytest.mark.django_db
def test_masterdata_reference_code_detail_superseding_codes(client_a, tenant_a, mdm_reference_code_a):
    """Verify detail context includes codes superseded by this canonical code."""
    superseded_code = _masterdata_create_reference_code(
        tenant_a,
        code_set="ISO-4217-CURRENCY",
        canonical_code="USN",
        canonical_name="US Dollar Next Day",
        source_system="LEGACY",
        source_code="USN",
        status="superseded",
        superseded_by=mdm_reference_code_a,
    )

    url = reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    superseding_list = list(response.context["superseding_codes"])
    assert superseded_code in superseding_list


@pytest.mark.django_db
def test_masterdata_reference_code_detail_404_nonexistent(client_a):
    """Verify detail returns 404 for invalid reference code pk."""
    url = reverse("bi:mdm_reference_code_detail", kwargs={"pk": 999999})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_reference_code_detail_idor_404(client_a, mdm_reference_code_b):
    """Verify tenant isolation: accessing tenant B reference code via client A returns 404."""
    url = reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_reference_code_create_get_renders_200(client_a):
    """Verify GET bi:mdm_reference_code_create renders 200 with empty form."""
    url = reverse("bi:mdm_reference_code_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["reference_code"] is None


@pytest.mark.django_db
def test_masterdata_reference_code_create_post_success(client_a, tenant_a):
    """Verify POST bi:mdm_reference_code_create creates reference code, redirects, and logs audit."""
    url = reverse("bi:mdm_reference_code_create")
    payload = {
        "code_set": "ISO-3166-COUNTRY",
        "canonical_code": "GBR",
        "canonical_name": "United Kingdom",
        "source_system": "SAP",
        "source_code": "GB",
        "category": "Europe",
        "status": "active",
        "attributes_text": '{"iso_numeric": "826", "dial_code": "+44"}',
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_code = MdmReferenceCode.objects.filter(
        tenant=tenant_a, code_set="ISO-3166-COUNTRY", canonical_code="GBR", source_system="SAP"
    ).first()
    assert created_code is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_reference_code_detail", kwargs={"pk": created_code.pk})

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_reference_code_create_post_invalid_json_attributes_returns_200(client_a):
    """Verify form rejection when attributes JSON string is malformed."""
    url = reverse("bi:mdm_reference_code_create")
    payload = {
        "code_set": "ISO-3166-COUNTRY",
        "canonical_code": "INVALID",
        "canonical_name": "Invalid JSON Test",
        "attributes_text": "{invalid json syntax",
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "attributes_text" in response.context["form"].errors


@pytest.mark.django_db
def test_masterdata_reference_code_edit_get_renders_200(client_a, mdm_reference_code_a):
    """Verify GET bi:mdm_reference_code_edit renders form with 200."""
    url = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["is_edit"] is True
    assert response.context["reference_code"] == mdm_reference_code_a


@pytest.mark.django_db
def test_masterdata_reference_code_edit_post_success(client_a, tenant_a, mdm_reference_code_a):
    """Verify POST bi:mdm_reference_code_edit updates reference code and logs audit."""
    url = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_a.pk})
    payload = {
        "code_set": mdm_reference_code_a.code_set,
        "canonical_code": mdm_reference_code_a.canonical_code,
        "canonical_name": "United States Dollar (Federal Reserve)",
        "source_system": mdm_reference_code_a.source_system,
        "source_code": mdm_reference_code_a.source_code,
        "status": "active",
        "attributes_text": '{"symbol": "$", "decimals": 2}',
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_reference_code_detail", kwargs={"pk": mdm_reference_code_a.pk})

    mdm_reference_code_a.refresh_from_db()
    assert mdm_reference_code_a.canonical_name == "United States Dollar (Federal Reserve)"
    assert mdm_reference_code_a.attributes_json.get("decimals") == 2

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_reference_code_edit_idor_404(client_a, mdm_reference_code_b):
    """Verify tenant isolation: editing tenant B reference code via client A returns 404."""
    url = reverse("bi:mdm_reference_code_edit", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.post(url, {"canonical_name": "Hacked Code"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_masterdata_reference_code_delete_get_method_not_allowed(client_a, mdm_reference_code_a):
    """Verify GET bi:mdm_reference_code_delete returns 405 Method Not Allowed."""
    url = reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_masterdata_reference_code_delete_post_success(client_a, tenant_a):
    """Verify POST bi:mdm_reference_code_delete deletes code and logs audit."""
    code_obj = _masterdata_create_reference_code(
        tenant_a,
        code_set="TEMP-SET",
        canonical_code="TEMP01",
        canonical_name="Temporary Reference Code",
        source_system="MIGRATION",
        source_code="TMP01",
    )
    url = reverse("bi:mdm_reference_code_delete", kwargs={"pk": code_obj.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:mdm_reference_code_list")
    assert not MdmReferenceCode.objects.filter(pk=code_obj.pk).exists()

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_masterdata_reference_code_delete_idor_404(client_a, mdm_reference_code_b):
    """Verify tenant isolation: deleting tenant B reference code via client A returns 404."""
    url = reverse("bi:mdm_reference_code_delete", kwargs={"pk": mdm_reference_code_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
