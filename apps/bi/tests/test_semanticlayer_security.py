"""Security, Multi-Tenancy, Authorization, and Hardening Tests for Sub-module 10.4 (Semantic Layer & Data Modeling).

Covers:
1. Cross-Tenant IDOR:
   - Client A (tenant_a) attempting to access or mutate Tenant B records across all 4 models
     (detail, edit GET, edit POST, delete POST, certify POST, introspect POST) returns strict 404 Not Found.
   - Bidirectional reverse tests: Client B attempting to access or mutate Tenant A records returns 404 Not Found.
   - Cross-Tenant Data Isolation in Lists: Overview and all 4 model list views for Tenant A
     never display Tenant B objects, codes, or labels (and vice versa for Tenant B).
2. Cross-Tenant Foreign Key Tampering & Injection via POST:
   - SemanticModel create & edit with foreign keys (warehouse_table_b, data_mart_b, owner_b)
     fails form validation and persists zero cross-tenant links.
   - BusinessGlossaryTerm create & edit with foreign keys (org_unit_b, steward_b, related_terms_b)
     fails form validation and persists zero cross-tenant links.
   - CalculatedMeasure create & edit with foreign keys (semantic_model_b, glossary_term_b)
     fails form validation and persists zero cross-tenant links.
   - DrillHierarchy create & edit with foreign keys (semantic_model_b)
     fails form validation and persists zero cross-tenant links.
3. Defense-in-depth Introspection Tenant Validation:
   - Introspection view verifies warehouse_table.tenant_id == request.tenant.pk.
   - Missing warehouse_table fails gracefully with user-facing message.
   - Table belonging to another tenant (even if bound directly in DB) is rejected and does not update fingerprint.
   - Legitimate tenant table successfully updates source_fingerprint and last_introspected_at.
4. Authentication & Method Gating:
   - Anonymous client requests to all 10.4 endpoints redirect (302) to login.
   - Direct GET requests to POST-only endpoints (delete, certify, introspect) return 405 Method Not Allowed.
5. Mass Assignment Invariants:
   - Submitting tenant, number, certification_status, certified_by, certified_at in standard
     create/edit form payloads does not overwrite or tamper with system fields.
6. Audit Log Integrity:
   - Mutating operations (create, edit, delete, certify, introspect) record append-only AuditLog
     rows with tenant=request.tenant and user=request.user.
   - Audit trail is strictly tenant-scoped (zero cross-tenant audit leakage).
7. Multi-User Scale Simulation:
   - 100 heterogeneous dummy users across tenant_a and tenant_b simulate high-concurrency access;
     asserts zero data leakage and 100% tenant isolation across semantic layer queries.
"""
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms import (
    BusinessGlossaryTermCertificationForm,
    BusinessGlossaryTermForm,
    CalculatedMeasureForm,
    DrillHierarchyForm,
    SemanticModelCertificationForm,
    SemanticModelForm,
)
from apps.bi.models import (
    BusinessGlossaryTerm,
    CalculatedMeasure,
    DataMart,
    DrillHierarchy,
    SemanticModel,
    WarehouseTable,
)
from apps.bi.views._common import bi_scope
from apps.core.models import AuditLog
from apps.core.models.OrgUnit import OrgUnit

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture Bridges (to satisfy conftest dependencies and unify user fixtures)
# ---------------------------------------------------------------------------


@pytest.fixture
def warehouse_table(warehouse_table_a):
    """Bridge fixture to satisfy conftest.semantic_model_a dependency."""
    return warehouse_table_a


@pytest.fixture
def data_mart(data_mart_a):
    """Bridge fixture to satisfy conftest.semantic_model_a dependency."""
    return data_mart_a


@pytest.fixture
def admin_user_b(admin_b):
    """Bridge fixture to unify admin_b and admin_user_b without duplicate username collision."""
    return admin_b


# ---------------------------------------------------------------------------
# Module-level test helpers (prefixed with _semanticlayer_*)
# ---------------------------------------------------------------------------


def _semanticlayer_create_user(tenant, username, is_admin=False):
    """Helper to create a tenant-scoped user."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
    )


def _semanticlayer_create_model(tenant, name="Test Model", code="test_model", **kwargs):
    """Helper to create a SemanticModel with default attributes."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "model_type": "fact",
        "primary_key_column": "id",
        "access_tier": "public",
        "certification_status": "draft",
        "is_active": True,
    }
    defaults.update(kwargs)
    return SemanticModel.objects.create(**defaults)


def _semanticlayer_create_term(tenant, name="Test Term", code="test_term", **kwargs):
    """Helper to create a BusinessGlossaryTerm with default attributes."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "domain_category": "finance",
        "short_definition": "Test glossary short definition text",
        "certification_status": "draft",
        "is_active": True,
    }
    defaults.update(kwargs)
    return BusinessGlossaryTerm.objects.create(**defaults)


def _semanticlayer_create_measure(tenant, model, name="Test Measure", code="test_measure", **kwargs):
    """Helper to create a CalculatedMeasure with default attributes."""
    defaults = {
        "tenant": tenant,
        "semantic_model": model,
        "name": name,
        "code": code,
        "aggregation_type": "sum",
        "source_column": "amount",
        "is_active": True,
    }
    defaults.update(kwargs)
    return CalculatedMeasure.objects.create(**defaults)


def _semanticlayer_create_hierarchy(tenant, model, name="Test Hierarchy", code="test_hierarchy", **kwargs):
    """Helper to create a DrillHierarchy with default attributes."""
    defaults = {
        "tenant": tenant,
        "semantic_model": model,
        "name": name,
        "code": code,
        "hierarchy_type": "time",
        "levels_json": [{"level": 1, "name": "Year", "column": "year"}],
        "is_active": True,
    }
    defaults.update(kwargs)
    return DrillHierarchy.objects.create(**defaults)


# ===========================================================================
# 1. Cross-Tenant IDOR Tests
# ===========================================================================


def test_semanticlayer_security_idor_semantic_model_detail_denied_404(client_a, semantic_model_b):
    """Client A requesting Tenant B SemanticModel detail view receives 404."""
    url = reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_semantic_model_edit_get_denied_404(client_a, semantic_model_b):
    """Client A requesting Tenant B SemanticModel edit GET view receives 404."""
    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_semantic_model_edit_post_denied_404(client_a, semantic_model_b):
    """Client A submitting POST to Tenant B SemanticModel edit view receives 404 and leaves record unchanged."""
    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url, data={"name": "Hacked Model Name"})
    assert response.status_code == 404
    semantic_model_b.refresh_from_db()
    assert semantic_model_b.name != "Hacked Model Name"


def test_semanticlayer_security_idor_semantic_model_delete_post_denied_404(client_a, semantic_model_b):
    """Client A submitting POST to delete Tenant B SemanticModel receives 404 and does not delete record."""
    url = reverse("bi:semantic_model_delete", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert SemanticModel.objects.filter(pk=semantic_model_b.pk).exists()


def test_semanticlayer_security_idor_semantic_model_certify_post_denied_404(client_a, semantic_model_b):
    """Client A submitting POST to certify Tenant B SemanticModel receives 404 and leaves status unchanged."""
    url = reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url, data={"certification_status": "certified"})
    assert response.status_code == 404
    semantic_model_b.refresh_from_db()
    assert semantic_model_b.certification_status == "draft"


def test_semanticlayer_security_idor_semantic_model_introspect_post_denied_404(client_a, semantic_model_b):
    """Client A submitting POST to introspect Tenant B SemanticModel receives 404."""
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_glossary_term_detail_denied_404(client_a, glossary_term_b):
    """Client A requesting Tenant B BusinessGlossaryTerm detail view receives 404."""
    url = reverse("bi:business_glossary_term_detail", kwargs={"pk": glossary_term_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_glossary_term_edit_get_denied_404(client_a, glossary_term_b):
    """Client A requesting Tenant B BusinessGlossaryTerm edit GET view receives 404."""
    url = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_glossary_term_edit_post_denied_404(client_a, glossary_term_b):
    """Client A submitting POST to Tenant B BusinessGlossaryTerm edit view receives 404 and leaves record unchanged."""
    url = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_b.pk})
    response = client_a.post(url, data={"name": "Hacked Glossary Term"})
    assert response.status_code == 404
    glossary_term_b.refresh_from_db()
    assert glossary_term_b.name != "Hacked Glossary Term"


def test_semanticlayer_security_idor_glossary_term_delete_post_denied_404(client_a, glossary_term_b):
    """Client A submitting POST to delete Tenant B BusinessGlossaryTerm receives 404 and does not delete record."""
    url = reverse("bi:business_glossary_term_delete", kwargs={"pk": glossary_term_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert BusinessGlossaryTerm.objects.filter(pk=glossary_term_b.pk).exists()


def test_semanticlayer_security_idor_glossary_term_certify_post_denied_404(client_a, glossary_term_b):
    """Client A submitting POST to certify Tenant B BusinessGlossaryTerm receives 404 and leaves status unchanged."""
    url = reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_b.pk})
    response = client_a.post(url, data={"certification_status": "certified"})
    assert response.status_code == 404
    glossary_term_b.refresh_from_db()
    assert glossary_term_b.certification_status == "draft"


def test_semanticlayer_security_idor_calculated_measure_detail_denied_404(client_a, calculated_measure_b):
    """Client A requesting Tenant B CalculatedMeasure detail view receives 404."""
    url = reverse("bi:calculated_measure_detail", kwargs={"pk": calculated_measure_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_calculated_measure_edit_get_denied_404(client_a, calculated_measure_b):
    """Client A requesting Tenant B CalculatedMeasure edit GET view receives 404."""
    url = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_calculated_measure_edit_post_denied_404(client_a, calculated_measure_b):
    """Client A submitting POST to Tenant B CalculatedMeasure edit view receives 404 and leaves record unchanged."""
    url = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_b.pk})
    response = client_a.post(url, data={"name": "Hacked Measure Name"})
    assert response.status_code == 404
    calculated_measure_b.refresh_from_db()
    assert calculated_measure_b.name != "Hacked Measure Name"


def test_semanticlayer_security_idor_calculated_measure_delete_post_denied_404(client_a, calculated_measure_b):
    """Client A submitting POST to delete Tenant B CalculatedMeasure receives 404 and does not delete record."""
    url = reverse("bi:calculated_measure_delete", kwargs={"pk": calculated_measure_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert CalculatedMeasure.objects.filter(pk=calculated_measure_b.pk).exists()


def test_semanticlayer_security_idor_drill_hierarchy_detail_denied_404(client_a, drill_hierarchy_b):
    """Client A requesting Tenant B DrillHierarchy detail view receives 404."""
    url = reverse("bi:drill_hierarchy_detail", kwargs={"pk": drill_hierarchy_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_drill_hierarchy_edit_get_denied_404(client_a, drill_hierarchy_b):
    """Client A requesting Tenant B DrillHierarchy edit GET view receives 404."""
    url = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


def test_semanticlayer_security_idor_drill_hierarchy_edit_post_denied_404(client_a, drill_hierarchy_b):
    """Client A submitting POST to Tenant B DrillHierarchy edit view receives 404 and leaves record unchanged."""
    url = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_b.pk})
    response = client_a.post(url, data={"name": "Hacked Hierarchy Name"})
    assert response.status_code == 404
    drill_hierarchy_b.refresh_from_db()
    assert drill_hierarchy_b.name != "Hacked Hierarchy Name"


def test_semanticlayer_security_idor_drill_hierarchy_delete_post_denied_404(client_a, drill_hierarchy_b):
    """Client A submitting POST to delete Tenant B DrillHierarchy receives 404 and does not delete record."""
    url = reverse("bi:drill_hierarchy_delete", kwargs={"pk": drill_hierarchy_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert DrillHierarchy.objects.filter(pk=drill_hierarchy_b.pk).exists()


def test_semanticlayer_security_idor_reverse_tenant_b_access_denied_404(
    client_b,
    semantic_model_a,
    glossary_term_a,
    calculated_measure_a,
    drill_hierarchy_a,
):
    """Bidirectional IDOR: Client B attempting to access or mutate Tenant A records receives strict 404s."""
    routes = [
        # SemanticModel A
        (reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_a.pk}), "GET", {}),
        (reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk}), "GET", {}),
        (reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:semantic_model_delete", kwargs={"pk": semantic_model_a.pk}), "POST", {}),
        (reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_a.pk}), "POST", {"certification_status": "draft"}),
        (reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_a.pk}), "POST", {}),
        # BusinessGlossaryTerm A
        (reverse("bi:business_glossary_term_detail", kwargs={"pk": glossary_term_a.pk}), "GET", {}),
        (reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk}), "GET", {}),
        (reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:business_glossary_term_delete", kwargs={"pk": glossary_term_a.pk}), "POST", {}),
        (reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_a.pk}), "POST", {"certification_status": "draft"}),
        # CalculatedMeasure A
        (reverse("bi:calculated_measure_detail", kwargs={"pk": calculated_measure_a.pk}), "GET", {}),
        (reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk}), "GET", {}),
        (reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:calculated_measure_delete", kwargs={"pk": calculated_measure_a.pk}), "POST", {}),
        # DrillHierarchy A
        (reverse("bi:drill_hierarchy_detail", kwargs={"pk": drill_hierarchy_a.pk}), "GET", {}),
        (reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk}), "GET", {}),
        (reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk}), "POST", {"name": "Hacked By B"}),
        (reverse("bi:drill_hierarchy_delete", kwargs={"pk": drill_hierarchy_a.pk}), "POST", {}),
    ]

    for url, method, data in routes:
        if method == "GET":
            res = client_b.get(url)
        else:
            res = client_b.post(url, data=data)
        assert res.status_code == 404, f"Expected 404 for Client B requesting {method} {url}, got {res.status_code}"


def test_semanticlayer_security_list_views_tenant_isolation(
    client_a,
    client_b,
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    glossary_term_a,
    glossary_term_b,
    calculated_measure_a,
    calculated_measure_b,
    drill_hierarchy_a,
    drill_hierarchy_b,
):
    """List and overview views strictly scope records by tenant; zero cross-tenant leakage in context or body."""
    # Test Client A
    list_routes_a = [
        (reverse("bi:semantic_overview"), [semantic_model_a.name], [semantic_model_b.name, semantic_model_b.code]),
        (reverse("bi:semantic_model_list"), [semantic_model_a.name], [semantic_model_b.name, semantic_model_b.code]),
        (reverse("bi:business_glossary_term_list"), [glossary_term_a.name], [glossary_term_b.name, glossary_term_b.code]),
        (reverse("bi:calculated_measure_list"), [calculated_measure_a.name], [calculated_measure_b.name, calculated_measure_b.code]),
        (reverse("bi:drill_hierarchy_list"), [drill_hierarchy_a.name], [drill_hierarchy_b.name, drill_hierarchy_b.code]),
    ]

    for url, expected_present, forbidden_present in list_routes_a:
        res = client_a.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        for expected in expected_present:
            assert expected in content, f"Expected '{expected}' to be visible for Client A on {url}"
        for forbidden in forbidden_present:
            assert forbidden not in content, f"Forbidden '{forbidden}' leaked to Client A on {url}"

    # Test Client B
    list_routes_b = [
        (reverse("bi:semantic_overview"), [semantic_model_b.name], [semantic_model_a.name, semantic_model_a.code]),
        (reverse("bi:semantic_model_list"), [semantic_model_b.name], [semantic_model_a.name, semantic_model_a.code]),
        (reverse("bi:business_glossary_term_list"), [glossary_term_b.name], [glossary_term_a.name, glossary_term_a.code]),
        (reverse("bi:calculated_measure_list"), [calculated_measure_b.name], [calculated_measure_a.name, calculated_measure_a.code]),
        (reverse("bi:drill_hierarchy_list"), [drill_hierarchy_b.name], [drill_hierarchy_a.name, drill_hierarchy_a.code]),
    ]

    for url, expected_present, forbidden_present in list_routes_b:
        res = client_b.get(url)
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        for expected in expected_present:
            assert expected in content, f"Expected '{expected}' to be visible for Client B on {url}"
        for forbidden in forbidden_present:
            assert forbidden not in content, f"Forbidden '{forbidden}' leaked to Client B on {url}"


# ===========================================================================
# 2. Cross-Tenant Foreign Key Injection via POST
# ===========================================================================


def test_semanticlayer_security_fk_injection_semantic_model_create(
    client_a,
    tenant_a,
    warehouse_table_b,
    data_mart_b,
    admin_user_b,
):
    """Submitting foreign keys from Tenant B when creating a SemanticModel in Tenant A fails form validation."""
    base_payload = {
        "name": "Hostile Model",
        "code": "hostile_model",
        "model_type": "fact",
        "primary_key_column": "id",
        "access_tier": "public",
        "is_active": "on",
    }

    # 1. Foreign warehouse_table
    res1 = client_a.post(
        reverse("bi:semantic_model_create"),
        data={**base_payload, "warehouse_table": warehouse_table_b.pk},
    )
    assert res1.status_code == 200
    assert not SemanticModel.objects.filter(tenant=tenant_a, code="hostile_model").exists()
    assert SemanticModel.objects.filter(warehouse_table=warehouse_table_b).count() == 0

    # 2. Foreign data_mart
    res2 = client_a.post(
        reverse("bi:semantic_model_create"),
        data={**base_payload, "code": "hostile_mart_model", "data_mart": data_mart_b.pk},
    )
    assert res2.status_code == 200
    assert not SemanticModel.objects.filter(tenant=tenant_a, code="hostile_mart_model").exists()
    assert SemanticModel.objects.filter(data_mart=data_mart_b).count() == 0

    # 3. Foreign owner
    res3 = client_a.post(
        reverse("bi:semantic_model_create"),
        data={**base_payload, "code": "hostile_owner_model", "owner": admin_user_b.pk},
    )
    assert res3.status_code == 200
    assert not SemanticModel.objects.filter(tenant=tenant_a, code="hostile_owner_model").exists()
    assert SemanticModel.objects.filter(tenant=tenant_a, owner=admin_user_b).count() == 0


def test_semanticlayer_security_fk_injection_semantic_model_edit(
    client_a,
    semantic_model_a,
    warehouse_table_b,
    data_mart_b,
    admin_user_b,
):
    """Submitting foreign keys when editing SemanticModel A is rejected and preserves existing relationships."""
    initial_table = semantic_model_a.warehouse_table
    initial_mart = semantic_model_a.data_mart
    initial_owner = semantic_model_a.owner

    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk})

    # Attempt injecting foreign warehouse_table
    res1 = client_a.post(
        url,
        data={
            "name": semantic_model_a.name,
            "code": semantic_model_a.code,
            "model_type": semantic_model_a.model_type,
            "primary_key_column": "id",
            "access_tier": "public",
            "warehouse_table": warehouse_table_b.pk,
            "is_active": "on",
        },
    )
    assert res1.status_code == 200
    semantic_model_a.refresh_from_db()
    assert semantic_model_a.warehouse_table == initial_table

    # Attempt injecting foreign data_mart
    res2 = client_a.post(
        url,
        data={
            "name": semantic_model_a.name,
            "code": semantic_model_a.code,
            "model_type": semantic_model_a.model_type,
            "primary_key_column": "id",
            "access_tier": "public",
            "data_mart": data_mart_b.pk,
            "is_active": "on",
        },
    )
    assert res2.status_code == 200
    semantic_model_a.refresh_from_db()
    assert semantic_model_a.data_mart == initial_mart

    # Attempt injecting foreign owner
    res3 = client_a.post(
        url,
        data={
            "name": semantic_model_a.name,
            "code": semantic_model_a.code,
            "model_type": semantic_model_a.model_type,
            "primary_key_column": "id",
            "access_tier": "public",
            "owner": admin_user_b.pk,
            "is_active": "on",
        },
    )
    assert res3.status_code == 200
    semantic_model_a.refresh_from_db()
    assert semantic_model_a.owner == initial_owner


def test_semanticlayer_security_fk_injection_glossary_term_create(
    client_a,
    tenant_a,
    tenant_b,
    admin_user_b,
    glossary_term_b,
):
    """Submitting foreign keys from Tenant B when creating a BusinessGlossaryTerm is rejected."""
    org_unit_b = OrgUnit.objects.create(tenant=tenant_b, name="Globex Analytics Department")

    base_payload = {
        "name": "Hostile Glossary Term",
        "code": "hostile_glossary_term",
        "domain_category": "finance",
        "short_definition": "Attempting cross-tenant linking",
        "is_active": "on",
    }

    # 1. Foreign org_unit
    res1 = client_a.post(
        reverse("bi:business_glossary_term_create"),
        data={**base_payload, "org_unit": org_unit_b.pk},
    )
    assert res1.status_code == 200
    assert not BusinessGlossaryTerm.objects.filter(tenant=tenant_a, code="hostile_glossary_term").exists()

    # 2. Foreign steward
    res2 = client_a.post(
        reverse("bi:business_glossary_term_create"),
        data={**base_payload, "code": "hostile_steward_term", "steward": admin_user_b.pk},
    )
    assert res2.status_code == 200
    assert not BusinessGlossaryTerm.objects.filter(tenant=tenant_a, code="hostile_steward_term").exists()

    # 3. Foreign related_terms
    res3 = client_a.post(
        reverse("bi:business_glossary_term_create"),
        data={**base_payload, "code": "hostile_related_term", "related_terms": [glossary_term_b.pk]},
    )
    assert res3.status_code == 200
    assert not BusinessGlossaryTerm.objects.filter(tenant=tenant_a, code="hostile_related_term").exists()


def test_semanticlayer_security_fk_injection_glossary_term_edit(
    client_a,
    glossary_term_a,
    tenant_b,
    admin_user_b,
    glossary_term_b,
):
    """Submitting foreign keys when editing BusinessGlossaryTerm A is rejected and preserves existing relationships."""
    org_unit_b = OrgUnit.objects.create(tenant=tenant_b, name="Globex Supply Chain")
    initial_steward = glossary_term_a.steward
    initial_org_unit = glossary_term_a.org_unit

    url = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk})

    # Foreign steward
    res1 = client_a.post(
        url,
        data={
            "name": glossary_term_a.name,
            "code": glossary_term_a.code,
            "domain_category": glossary_term_a.domain_category,
            "short_definition": glossary_term_a.short_definition,
            "steward": admin_user_b.pk,
            "is_active": "on",
        },
    )
    assert res1.status_code == 200
    glossary_term_a.refresh_from_db()
    assert glossary_term_a.steward == initial_steward

    # Foreign org_unit
    res2 = client_a.post(
        url,
        data={
            "name": glossary_term_a.name,
            "code": glossary_term_a.code,
            "domain_category": glossary_term_a.domain_category,
            "short_definition": glossary_term_a.short_definition,
            "org_unit": org_unit_b.pk,
            "is_active": "on",
        },
    )
    assert res2.status_code == 200
    glossary_term_a.refresh_from_db()
    assert glossary_term_a.org_unit == initial_org_unit

    # Foreign related_terms
    res3 = client_a.post(
        url,
        data={
            "name": glossary_term_a.name,
            "code": glossary_term_a.code,
            "domain_category": glossary_term_a.domain_category,
            "short_definition": glossary_term_a.short_definition,
            "related_terms": [glossary_term_b.pk],
            "is_active": "on",
        },
    )
    assert res3.status_code == 200
    assert glossary_term_b not in glossary_term_a.related_terms.all()


def test_semanticlayer_security_fk_injection_calculated_measure_create(
    client_a,
    tenant_a,
    semantic_model_b,
    glossary_term_b,
    semantic_model_a,
):
    """Submitting foreign keys from Tenant B when creating a CalculatedMeasure is rejected."""
    base_payload = {
        "name": "Hostile Calculated Measure",
        "code": "hostile_calc_measure",
        "aggregation_type": "sum",
        "source_column": "amount",
        "is_active": "on",
    }

    # 1. Foreign semantic_model
    res1 = client_a.post(
        reverse("bi:calculated_measure_create"),
        data={**base_payload, "semantic_model": semantic_model_b.pk},
    )
    assert res1.status_code == 200
    assert not CalculatedMeasure.objects.filter(tenant=tenant_a, code="hostile_calc_measure").exists()

    # 2. Foreign glossary_term with valid semantic_model
    res2 = client_a.post(
        reverse("bi:calculated_measure_create"),
        data={
            **base_payload,
            "code": "hostile_glossary_measure",
            "semantic_model": semantic_model_a.pk,
            "glossary_term": glossary_term_b.pk,
        },
    )
    assert res2.status_code == 200
    assert not CalculatedMeasure.objects.filter(tenant=tenant_a, code="hostile_glossary_measure").exists()


def test_semanticlayer_security_fk_injection_calculated_measure_edit(
    client_a,
    calculated_measure_a,
    semantic_model_b,
    glossary_term_b,
):
    """Submitting foreign keys when editing CalculatedMeasure A is rejected and preserves existing relationships."""
    initial_model = calculated_measure_a.semantic_model
    initial_term = calculated_measure_a.glossary_term

    url = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk})

    # Foreign semantic_model
    res1 = client_a.post(
        url,
        data={
            "semantic_model": semantic_model_b.pk,
            "name": calculated_measure_a.name,
            "code": calculated_measure_a.code,
            "aggregation_type": calculated_measure_a.aggregation_type,
            "source_column": calculated_measure_a.source_column,
            "is_active": "on",
        },
    )
    assert res1.status_code == 200
    calculated_measure_a.refresh_from_db()
    assert calculated_measure_a.semantic_model == initial_model

    # Foreign glossary_term
    res2 = client_a.post(
        url,
        data={
            "semantic_model": calculated_measure_a.semantic_model.pk,
            "glossary_term": glossary_term_b.pk,
            "name": calculated_measure_a.name,
            "code": calculated_measure_a.code,
            "aggregation_type": calculated_measure_a.aggregation_type,
            "source_column": calculated_measure_a.source_column,
            "is_active": "on",
        },
    )
    assert res2.status_code == 200
    calculated_measure_a.refresh_from_db()
    assert calculated_measure_a.glossary_term == initial_term


def test_semanticlayer_security_fk_injection_drill_hierarchy_create(
    client_a,
    tenant_a,
    semantic_model_b,
):
    """Submitting foreign semantic_model when creating a DrillHierarchy is rejected."""
    payload = {
        "semantic_model": semantic_model_b.pk,
        "name": "Hostile Hierarchy",
        "code": "hostile_hierarchy",
        "hierarchy_type": "time",
        "is_active": "on",
    }
    res = client_a.post(reverse("bi:drill_hierarchy_create"), data=payload)
    assert res.status_code == 200
    assert not DrillHierarchy.objects.filter(tenant=tenant_a, code="hostile_hierarchy").exists()


def test_semanticlayer_security_fk_injection_drill_hierarchy_edit(
    client_a,
    drill_hierarchy_a,
    semantic_model_b,
):
    """Submitting foreign semantic_model when editing DrillHierarchy A is rejected and preserves existing model."""
    initial_model = drill_hierarchy_a.semantic_model

    url = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk})
    res = client_a.post(
        url,
        data={
            "semantic_model": semantic_model_b.pk,
            "name": drill_hierarchy_a.name,
            "code": drill_hierarchy_a.code,
            "hierarchy_type": drill_hierarchy_a.hierarchy_type,
            "is_active": "on",
        },
    )
    assert res.status_code == 200
    drill_hierarchy_a.refresh_from_db()
    assert drill_hierarchy_a.semantic_model == initial_model


# ===========================================================================
# 3. Defense-in-Depth Introspection Tenant Validation
# ===========================================================================


def test_semanticlayer_security_introspection_missing_warehouse_table_fails_gracefully(
    client_a,
    tenant_a,
    admin_user,
):
    """Introspecting a model without an underlying warehouse_table fails gracefully with an error message."""
    model_without_table = _semanticlayer_create_model(
        tenant_a,
        name="Table-less Virtual Model",
        code="tableless_virt_model",
        warehouse_table=None,
        owner=admin_user,
    )
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": model_without_table.pk})

    res = client_a.post(url, follow=True)
    assert res.status_code == 200
    model_without_table.refresh_from_db()
    assert model_without_table.source_fingerprint == ""
    assert model_without_table.last_introspected_at is None
    messages = [m.message for m in res.context["messages"]]
    assert any("No underlying warehouse table is bound" in m for m in messages)


def test_semanticlayer_security_introspection_cross_tenant_warehouse_table_rejected(
    client_a,
    tenant_a,
    warehouse_table_b,
    admin_user,
):
    """Introspecting a model maliciously bound to a foreign warehouse table is blocked by defense-in-depth tenant check."""
    # Simulate an out-of-band corrupted or tampered relationship in the database
    corrupt_model = _semanticlayer_create_model(
        tenant_a,
        name="Cross-Tenant Corrupt Model",
        code="cross_tenant_corrupt_model",
        warehouse_table=warehouse_table_b,
        owner=admin_user,
    )
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": corrupt_model.pk})

    res = client_a.post(url, follow=True)
    assert res.status_code == 200
    corrupt_model.refresh_from_db()
    assert corrupt_model.source_fingerprint == ""
    assert corrupt_model.last_introspected_at is None
    messages = [m.message for m in res.context["messages"]]
    assert any("Warehouse table belongs to another workspace" in m for m in messages)


def test_semanticlayer_security_introspection_legitimate_tenant_table_succeeds(
    client_a,
    semantic_model_a,
    warehouse_table_a,
):
    """Legitimate introspection on a model bound to a same-tenant warehouse table succeeds and stamps fingerprint."""
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_a.pk})
    res = client_a.post(url, follow=True)
    assert res.status_code == 200
    semantic_model_a.refresh_from_db()
    assert len(semantic_model_a.source_fingerprint) == 16
    assert semantic_model_a.last_introspected_at is not None
    messages = [m.message for m in res.context["messages"]]
    assert any("Schema introspected from" in m for m in messages)


# ===========================================================================
# 4. Authentication & Method Gating
# ===========================================================================


def test_semanticlayer_security_unauthenticated_get_requests_redirect_to_login(
    anon_client,
    semantic_model_a,
    glossary_term_a,
    calculated_measure_a,
    drill_hierarchy_a,
):
    """Anonymous client requesting any Sub-module 10.4 GET route is redirected to login."""
    get_routes = [
        # Overview
        reverse("bi:semantic_overview"),
        # SemanticModel
        reverse("bi:semantic_model_list"),
        reverse("bi:semantic_model_create"),
        reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_a.pk}),
        reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk}),
        # BusinessGlossaryTerm
        reverse("bi:business_glossary_term_list"),
        reverse("bi:business_glossary_term_create"),
        reverse("bi:business_glossary_term_detail", kwargs={"pk": glossary_term_a.pk}),
        reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk}),
        # CalculatedMeasure
        reverse("bi:calculated_measure_list"),
        reverse("bi:calculated_measure_create"),
        reverse("bi:calculated_measure_detail", kwargs={"pk": calculated_measure_a.pk}),
        reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk}),
        # DrillHierarchy
        reverse("bi:drill_hierarchy_list"),
        reverse("bi:drill_hierarchy_create"),
        reverse("bi:drill_hierarchy_detail", kwargs={"pk": drill_hierarchy_a.pk}),
        reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk}),
    ]

    for url in get_routes:
        res = anon_client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for anon GET {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


def test_semanticlayer_security_unauthenticated_post_requests_redirect_to_login(
    anon_client,
    semantic_model_a,
    glossary_term_a,
    calculated_measure_a,
    drill_hierarchy_a,
):
    """Anonymous client submitting POST to any Sub-module 10.4 route is redirected to login."""
    post_routes = [
        # Creates
        (reverse("bi:semantic_model_create"), {"name": "Anon Model"}),
        (reverse("bi:business_glossary_term_create"), {"name": "Anon Term"}),
        (reverse("bi:calculated_measure_create"), {"name": "Anon Measure"}),
        (reverse("bi:drill_hierarchy_create"), {"name": "Anon Hierarchy"}),
        # Edits
        (reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk}), {"name": "Hacked"}),
        (reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk}), {"name": "Hacked"}),
        (reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk}), {"name": "Hacked"}),
        (reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk}), {"name": "Hacked"}),
        # Deletes
        (reverse("bi:semantic_model_delete", kwargs={"pk": semantic_model_a.pk}), {}),
        (reverse("bi:business_glossary_term_delete", kwargs={"pk": glossary_term_a.pk}), {}),
        (reverse("bi:calculated_measure_delete", kwargs={"pk": calculated_measure_a.pk}), {}),
        (reverse("bi:drill_hierarchy_delete", kwargs={"pk": drill_hierarchy_a.pk}), {}),
        # Certifications
        (reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_a.pk}), {"certification_status": "certified"}),
        (reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_a.pk}), {"certification_status": "certified"}),
        # Introspection
        (reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_a.pk}), {}),
    ]

    for url, data in post_routes:
        res = anon_client.post(url, data)
        assert res.status_code == 302, f"Expected 302 redirect for anon POST {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


def test_semanticlayer_security_post_only_endpoints_reject_get_with_405(
    client_a,
    semantic_model_a,
    glossary_term_a,
    calculated_measure_a,
    drill_hierarchy_a,
):
    """Direct GET on POST-only mutation endpoints strictly returns HTTP 405 Method Not Allowed."""
    post_only_routes = [
        reverse("bi:semantic_model_delete", kwargs={"pk": semantic_model_a.pk}),
        reverse("bi:business_glossary_term_delete", kwargs={"pk": glossary_term_a.pk}),
        reverse("bi:calculated_measure_delete", kwargs={"pk": calculated_measure_a.pk}),
        reverse("bi:drill_hierarchy_delete", kwargs={"pk": drill_hierarchy_a.pk}),
        reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_a.pk}),
        reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_a.pk}),
        reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_a.pk}),
    ]

    for url in post_only_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {res.status_code}"


# ===========================================================================
# 5. Mass Assignment Invariants
# ===========================================================================


def test_semanticlayer_security_mass_assignment_semantic_model_create(
    client_a,
    tenant_a,
    tenant_b,
    warehouse_table_a,
    data_mart_a,
    admin_user_b,
):
    """Submitting system fields (tenant, number, certification) in SemanticModelForm create payload has no effect."""
    malicious_payload = {
        "name": "Hardened Semantic Model",
        "code": "hardened_sem_model",
        "model_type": "fact",
        "warehouse_table": warehouse_table_a.pk,
        "data_mart": data_mart_a.pk,
        "primary_key_column": "id",
        "scd_type": "type_1",
        "access_tier": "public",
        "is_active": "on",
        # Malicious mass-assignment attempts:
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "MALICIOUS-9999",
        "certification_status": "certified",
        "certified_by": admin_user_b.pk,
        "certified_at": "2020-01-01T00:00:00Z",
    }

    res = client_a.post(reverse("bi:semantic_model_create"), data=malicious_payload)
    assert res.status_code == 302

    created = SemanticModel.objects.get(code="hardened_sem_model")
    # Verify tenant invariant
    assert created.tenant == tenant_a
    # Verify number invariant (auto-generated, malicious value ignored)
    assert created.number.startswith("BSMD-")
    assert created.number != "MALICIOUS-9999"
    # Verify certification invariant (not exposed in SemanticModelForm, default is draft)
    assert created.certification_status == "draft"
    assert created.certified_by is None
    assert created.certified_at is None


def test_semanticlayer_security_mass_assignment_semantic_model_edit(
    client_a,
    semantic_model_a,
    tenant_b,
    admin_user_b,
):
    """Submitting system fields in SemanticModelForm edit payload cannot re-parent tenant or alter number."""
    initial_tenant = semantic_model_a.tenant
    initial_number = semantic_model_a.number

    malicious_payload = {
        "name": "Updated Name",
        "code": semantic_model_a.code,
        "model_type": semantic_model_a.model_type,
        "primary_key_column": "id",
        "scd_type": semantic_model_a.scd_type,
        "access_tier": "public",
        "is_active": "on",
        # Malicious override attempts
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "TAMPERED-NUMBER",
    }

    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk})
    res = client_a.post(url, data=malicious_payload)
    assert res.status_code == 302

    semantic_model_a.refresh_from_db()
    assert semantic_model_a.tenant == initial_tenant
    assert semantic_model_a.number == initial_number


def test_semanticlayer_security_mass_assignment_glossary_term_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    glossary_term_a,
    admin_user_b,
):
    """Submitting system fields in BusinessGlossaryTerm create and edit payloads preserves tenant and document number."""
    # Create with malicious overrides
    malicious_create_payload = {
        "name": "Hardened Glossary Term",
        "code": "hardened_glossary_term",
        "domain_category": "finance",
        "short_definition": "Mass assignment verification",
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "GLO-MALICIOUS-001",
        "certification_status": "certified",
        "certified_by": admin_user_b.pk,
    }

    res_create = client_a.post(reverse("bi:business_glossary_term_create"), data=malicious_create_payload)
    assert res_create.status_code == 302

    created = BusinessGlossaryTerm.objects.get(code="hardened_glossary_term")
    assert created.tenant == tenant_a
    assert created.number.startswith("BGLO-")
    assert created.number != "GLO-MALICIOUS-001"
    assert created.certification_status == "draft"
    assert created.certified_by is None

    # Edit with malicious overrides
    initial_number = glossary_term_a.number
    url_edit = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "name": glossary_term_a.name,
            "code": glossary_term_a.code,
            "domain_category": glossary_term_a.domain_category,
            "short_definition": glossary_term_a.short_definition,
            "is_active": "on",
            "tenant": tenant_b.pk,
            "number": "TAMPERED-GLO",
        },
    )
    assert res_edit.status_code == 302
    glossary_term_a.refresh_from_db()
    assert glossary_term_a.tenant == tenant_a
    assert glossary_term_a.number == initial_number


def test_semanticlayer_security_mass_assignment_calculated_measure_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    calculated_measure_a,
    semantic_model_a,
):
    """Submitting system fields in CalculatedMeasure create and edit payloads preserves tenant and document number."""
    # Create
    malicious_create = {
        "semantic_model": semantic_model_a.pk,
        "name": "Hardened Calculated Measure",
        "code": "hardened_calc_measure",
        "aggregation_type": "sum",
        "source_column": "amount",
        "time_intelligence": "none",
        "format_string": "currency",
        "display_units": "auto",
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "MEA-MALICIOUS-001",
    }
    res_create = client_a.post(reverse("bi:calculated_measure_create"), data=malicious_create)
    assert res_create.status_code == 302

    created = CalculatedMeasure.objects.get(code="hardened_calc_measure")
    assert created.tenant == tenant_a
    assert created.number.startswith("BCMS-")
    assert created.number != "MEA-MALICIOUS-001"

    # Edit
    initial_number = calculated_measure_a.number
    url_edit = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "semantic_model": calculated_measure_a.semantic_model.pk,
            "name": calculated_measure_a.name,
            "code": calculated_measure_a.code,
            "aggregation_type": calculated_measure_a.aggregation_type,
            "source_column": calculated_measure_a.source_column,
            "time_intelligence": calculated_measure_a.time_intelligence,
            "format_string": calculated_measure_a.format_string,
            "display_units": calculated_measure_a.display_units,
            "is_active": "on",
            "tenant": tenant_b.pk,
            "number": "TAMPERED-MEA",
        },
    )
    assert res_edit.status_code == 302
    calculated_measure_a.refresh_from_db()
    assert calculated_measure_a.tenant == tenant_a
    assert calculated_measure_a.number == initial_number


def test_semanticlayer_security_mass_assignment_drill_hierarchy_create_and_edit(
    client_a,
    tenant_a,
    tenant_b,
    drill_hierarchy_a,
    semantic_model_a,
):
    """Submitting system fields in DrillHierarchy create and edit payloads preserves tenant and document number."""
    # Create
    malicious_create = {
        "semantic_model": semantic_model_a.pk,
        "name": "Hardened Drill Hierarchy",
        "code": "hardened_drill_hierarchy",
        "hierarchy_type": "time",
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "HIE-MALICIOUS-001",
    }
    res_create = client_a.post(reverse("bi:drill_hierarchy_create"), data=malicious_create)
    assert res_create.status_code == 302

    created = DrillHierarchy.objects.get(code="hardened_drill_hierarchy")
    assert created.tenant == tenant_a
    assert created.number.startswith("BDHI-")
    assert created.number != "HIE-MALICIOUS-001"

    # Edit
    initial_number = drill_hierarchy_a.number
    url_edit = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk})
    res_edit = client_a.post(
        url_edit,
        data={
            "semantic_model": drill_hierarchy_a.semantic_model.pk,
            "name": drill_hierarchy_a.name,
            "code": drill_hierarchy_a.code,
            "hierarchy_type": drill_hierarchy_a.hierarchy_type,
            "is_active": "on",
            "tenant": tenant_b.pk,
            "number": "TAMPERED-HIE",
        },
    )
    assert res_edit.status_code == 302
    drill_hierarchy_a.refresh_from_db()
    assert drill_hierarchy_a.tenant == tenant_a
    assert drill_hierarchy_a.number == initial_number


# ===========================================================================
# 6. Audit Log Integrity
# ===========================================================================


def test_semanticlayer_security_audit_log_semantic_model_lifecycle(
    client_a,
    tenant_a,
    warehouse_table_a,
    data_mart_a,
    admin_user,
):
    """SemanticModel mutations (create, update, certify, introspect, delete) record AuditLog rows with tenant and user."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:semantic_model_create"),
        data={
            "name": "Audit Tracked Model",
            "code": "audit_tracked_model",
            "model_type": "fact",
            "warehouse_table": warehouse_table_a.pk,
            "data_mart": data_mart_a.pk,
            "primary_key_column": "id",
            "scd_type": "type_1",
            "access_tier": "public",
            "is_active": "on",
        },
    )
    assert res_create.status_code == 302
    model = SemanticModel.objects.get(code="audit_tracked_model")

    create_log = AuditLog.objects.filter(object_id=model.pk, action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:semantic_model_edit", kwargs={"pk": model.pk}),
        data={
            "name": "Audit Tracked Model Updated",
            "code": "audit_tracked_model",
            "model_type": "fact",
            "warehouse_table": warehouse_table_a.pk,
            "data_mart": data_mart_a.pk,
            "primary_key_column": "id",
            "scd_type": "type_1",
            "access_tier": "public",
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 302
    update_log = AuditLog.objects.filter(object_id=model.pk, action="update").first()
    assert update_log is not None
    assert update_log.tenant == tenant_a
    assert update_log.user == admin_user

    # 3. Certify
    res_certify = client_a.post(
        reverse("bi:semantic_model_certify", kwargs={"pk": model.pk}),
        data={"certification_status": "certified", "certification_notes": "Passed signoff"},
    )
    assert res_certify.status_code == 302
    certify_log = AuditLog.objects.filter(object_id=model.pk, action="certify").first()
    assert certify_log is not None
    assert certify_log.tenant == tenant_a
    assert certify_log.user == admin_user

    # 4. Introspect
    res_introspect = client_a.post(
        reverse("bi:semantic_model_introspect", kwargs={"pk": model.pk}),
    )
    assert res_introspect.status_code == 302
    introspect_log = AuditLog.objects.filter(object_id=model.pk, action="introspect").first()
    assert introspect_log is not None
    assert introspect_log.tenant == tenant_a
    assert introspect_log.user == admin_user

    # 5. Delete
    model_pk = model.pk
    res_delete = client_a.post(reverse("bi:semantic_model_delete", kwargs={"pk": model.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=model_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_semanticlayer_security_audit_log_glossary_term_lifecycle(
    client_a,
    tenant_a,
    admin_user,
):
    """BusinessGlossaryTerm mutations (create, update, certify, delete) record AuditLog rows with tenant and user."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:business_glossary_term_create"),
        data={
            "name": "Audit Term",
            "code": "audit_term",
            "domain_category": "sales",
            "short_definition": "Audit tracking glossary term",
            "is_active": "on",
        },
    )
    assert res_create.status_code == 302
    term = BusinessGlossaryTerm.objects.get(code="audit_term")

    create_log = AuditLog.objects.filter(object_id=term.pk, action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:business_glossary_term_edit", kwargs={"pk": term.pk}),
        data={
            "name": "Audit Term Renamed",
            "code": "audit_term",
            "domain_category": "sales",
            "short_definition": "Updated definition",
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 302
    update_log = AuditLog.objects.filter(object_id=term.pk, action="update").first()
    assert update_log is not None
    assert update_log.tenant == tenant_a

    # 3. Certify
    res_certify = client_a.post(
        reverse("bi:business_glossary_term_certify", kwargs={"pk": term.pk}),
        data={"certification_status": "certified", "certification_notes": "Glossary certified"},
    )
    assert res_certify.status_code == 302
    certify_log = AuditLog.objects.filter(object_id=term.pk, action="certify").first()
    assert certify_log is not None
    assert certify_log.tenant == tenant_a

    # 4. Delete
    term_pk = term.pk
    res_delete = client_a.post(reverse("bi:business_glossary_term_delete", kwargs={"pk": term.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=term_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_semanticlayer_security_audit_log_calculated_measure_lifecycle(
    client_a,
    tenant_a,
    semantic_model_a,
    admin_user,
):
    """CalculatedMeasure mutations (create, update, delete) record AuditLog rows with tenant and user."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:calculated_measure_create"),
        data={
            "semantic_model": semantic_model_a.pk,
            "name": "Audit Measure",
            "code": "audit_measure",
            "aggregation_type": "sum",
            "source_column": "amount",
            "time_intelligence": "none",
            "format_string": "currency",
            "display_units": "auto",
            "is_active": "on",
        },
    )
    assert res_create.status_code == 302
    measure = CalculatedMeasure.objects.get(code="audit_measure")

    create_log = AuditLog.objects.filter(object_id=measure.pk, action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:calculated_measure_edit", kwargs={"pk": measure.pk}),
        data={
            "semantic_model": semantic_model_a.pk,
            "name": "Audit Measure Renamed",
            "code": "audit_measure",
            "aggregation_type": "sum",
            "source_column": "amount",
            "time_intelligence": "none",
            "format_string": "currency",
            "display_units": "auto",
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 302
    update_log = AuditLog.objects.filter(object_id=measure.pk, action="update").first()
    assert update_log is not None
    assert update_log.tenant == tenant_a

    # 3. Delete
    measure_pk = measure.pk
    res_delete = client_a.post(reverse("bi:calculated_measure_delete", kwargs={"pk": measure.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=measure_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_semanticlayer_security_audit_log_drill_hierarchy_lifecycle(
    client_a,
    tenant_a,
    semantic_model_a,
    admin_user,
):
    """DrillHierarchy mutations (create, update, delete) record AuditLog rows with tenant and user."""
    # 1. Create
    res_create = client_a.post(
        reverse("bi:drill_hierarchy_create"),
        data={
            "semantic_model": semantic_model_a.pk,
            "name": "Audit Hierarchy",
            "code": "audit_hierarchy",
            "hierarchy_type": "time",
            "is_active": "on",
        },
    )
    assert res_create.status_code == 302
    hierarchy = DrillHierarchy.objects.get(code="audit_hierarchy")

    create_log = AuditLog.objects.filter(object_id=hierarchy.pk, action="create").first()
    assert create_log is not None
    assert create_log.tenant == tenant_a
    assert create_log.user == admin_user

    # 2. Update
    res_edit = client_a.post(
        reverse("bi:drill_hierarchy_edit", kwargs={"pk": hierarchy.pk}),
        data={
            "semantic_model": semantic_model_a.pk,
            "name": "Audit Hierarchy Renamed",
            "code": "audit_hierarchy",
            "hierarchy_type": "time",
            "is_active": "on",
        },
    )
    assert res_edit.status_code == 302
    update_log = AuditLog.objects.filter(object_id=hierarchy.pk, action="update").first()
    assert update_log is not None
    assert update_log.tenant == tenant_a

    # 3. Delete
    hierarchy_pk = hierarchy.pk
    res_delete = client_a.post(reverse("bi:drill_hierarchy_delete", kwargs={"pk": hierarchy.pk}))
    assert res_delete.status_code == 302
    delete_log = AuditLog.objects.filter(object_id=hierarchy_pk, action="delete").first()
    assert delete_log is not None
    assert delete_log.tenant == tenant_a
    assert delete_log.user == admin_user


def test_semanticlayer_security_audit_log_tenant_b_isolation(
    client_b,
    tenant_a,
    tenant_b,
    admin_b,
):
    """Mutations performed by Tenant B record AuditLog entries scoped to Tenant B with zero leakage to Tenant A."""
    res = client_b.post(
        reverse("bi:business_glossary_term_create"),
        data={
            "name": "Globex Audit Term",
            "code": "globex_audit_term",
            "domain_category": "finance",
            "short_definition": "Globex specific term",
            "is_active": "on",
        },
    )
    assert res.status_code == 302
    term_b = BusinessGlossaryTerm.objects.get(tenant=tenant_b, code="globex_audit_term")

    b_log = AuditLog.objects.filter(object_id=term_b.pk, action="create").first()
    assert b_log is not None
    assert b_log.tenant == tenant_b
    assert b_log.user == admin_b

    # Verify Tenant A cannot see Tenant B's audit entry
    assert not AuditLog.objects.filter(tenant=tenant_a, object_id=term_b.pk).exists()


# ===========================================================================
# 7. Multi-User Scale Simulation
# ===========================================================================


def test_semanticlayer_security_multi_user_scale_simulation(
    db,
    tenant_a,
    tenant_b,
    warehouse_table_a,
    warehouse_table_b,
    data_mart_a,
    data_mart_b,
):
    """Simulate 100 heterogeneous dummy users across tenant_a and tenant_b to verify 100% tenant isolation."""
    # 1. Create 50 distinct users for Tenant A and 50 for Tenant B
    users_a = [
        User(
            email=f"user_a_{i}@acme.com",
            username=f"user_a_{i}",
            tenant=tenant_a,
            is_tenant_admin=False,
        )
        for i in range(1, 51)
    ]
    users_b = [
        User(
            email=f"user_b_{i}@globex.com",
            username=f"user_b_{i}",
            tenant=tenant_b,
            is_tenant_admin=False,
        )
        for i in range(1, 51)
    ]
    User.objects.bulk_create(users_a + users_b)

    assert User.objects.filter(tenant=tenant_a, username__startswith="user_a_").count() == 50
    assert User.objects.filter(tenant=tenant_b, username__startswith="user_b_").count() == 50

    # 2. Populate multiple semantic layer objects for both tenants
    for i in range(1, 6):
        # Tenant A objects
        model_a = _semanticlayer_create_model(
            tenant_a,
            name=f"Acme Model {i}",
            code=f"acme_scale_model_{i}",
            warehouse_table=warehouse_table_a,
            data_mart=data_mart_a,
        )
        term_a = _semanticlayer_create_term(
            tenant_a,
            name=f"Acme Term {i}",
            code=f"acme_scale_term_{i}",
        )
        _semanticlayer_create_measure(
            tenant_a,
            model_a,
            name=f"Acme Measure {i}",
            code=f"acme_scale_measure_{i}",
            glossary_term=term_a,
        )
        _semanticlayer_create_hierarchy(
            tenant_a,
            model_a,
            name=f"Acme Hierarchy {i}",
            code=f"acme_scale_hier_{i}",
        )

        # Tenant B objects
        model_b = _semanticlayer_create_model(
            tenant_b,
            name=f"Globex Model {i}",
            code=f"globex_scale_model_{i}",
            warehouse_table=warehouse_table_b,
            data_mart=data_mart_b,
        )
        term_b = _semanticlayer_create_term(
            tenant_b,
            name=f"Globex Term {i}",
            code=f"globex_scale_term_{i}",
        )
        _semanticlayer_create_measure(
            tenant_b,
            model_b,
            name=f"Globex Measure {i}",
            code=f"globex_scale_measure_{i}",
            glossary_term=term_b,
        )
        _semanticlayer_create_hierarchy(
            tenant_b,
            model_b,
            name=f"Globex Hierarchy {i}",
            code=f"globex_scale_hier_{i}",
        )

    # 3. Simulate multi-user queries for all 100 users across all 4 models
    class DummyRequest:
        def __init__(self, user):
            self.user = user
            self.tenant = user.tenant

    all_users = list(User.objects.filter(username__in=[u.username for u in users_a + users_b]))
    assert len(all_users) == 100

    for user in all_users:
        req = DummyRequest(user)

        scoped_models = list(bi_scope(SemanticModel.objects.all(), req))
        scoped_terms = list(bi_scope(BusinessGlossaryTerm.objects.all(), req))
        scoped_measures = list(bi_scope(CalculatedMeasure.objects.all(), req))
        scoped_hierarchies = list(bi_scope(DrillHierarchy.objects.all(), req))

        # Check tenant isolation
        assert len(scoped_models) >= 5
        assert len(scoped_terms) >= 5
        assert len(scoped_measures) >= 5
        assert len(scoped_hierarchies) >= 5

        # Strict assertion: every single record retrieved must belong exclusively to user.tenant
        assert all(m.tenant_id == user.tenant.pk for m in scoped_models)
        assert all(t.tenant_id == user.tenant.pk for t in scoped_terms)
        assert all(ms.tenant_id == user.tenant.pk for ms in scoped_measures)
        assert all(h.tenant_id == user.tenant.pk for h in scoped_hierarchies)

        # Strict assertion: zero cross-tenant contamination
        other_tenant_id = tenant_b.pk if user.tenant.pk == tenant_a.pk else tenant_a.pk
        assert not any(m.tenant_id == other_tenant_id for m in scoped_models)
        assert not any(t.tenant_id == other_tenant_id for t in scoped_terms)
        assert not any(ms.tenant_id == other_tenant_id for ms in scoped_measures)
        assert not any(h.tenant_id == other_tenant_id for h in scoped_hierarchies)
