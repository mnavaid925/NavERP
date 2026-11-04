"""View test suite for Sub-module 10.4 (Semantic Layer & Data Modeling).

Covers all 18 routes in apps/bi/views/SemanticLayer/:
1. Overview:
   - bi:semantic_overview (GET 200, context metrics, cards, unauthenticated redirect, empty tenant)
2. SemanticModel views:
   - bi:semantic_model_list (HTTP 200, context vars, search, filters, junk ?data_mart=invalid -> 200, pagination)
   - bi:semantic_model_detail (GET 200, context vars, measures & hierarchies context, 404, IDOR 404)
   - bi:semantic_model_create (GET 200, POST 302 -> detail, auto-owner, invalid form 200)
   - bi:semantic_model_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404)
   - bi:semantic_model_delete (GET 405, POST 302 -> list, IDOR 404)
   - bi:semantic_model_certify (GET 405, POST 302 to certified stamps user/time, uncertify clears, invalid status, IDOR 404)
   - bi:semantic_model_introspect (GET 405, POST 302 schema fingerprint, missing table, cross-tenant table, IDOR 404)
3. BusinessGlossaryTerm views:
   - bi:business_glossary_term_list (HTTP 200, context vars, search, filters, pagination)
   - bi:business_glossary_term_detail (GET 200, context vars, related measures, 404, IDOR 404)
   - bi:business_glossary_term_create (GET 200, POST 302 -> detail, auto-steward, m2m, invalid form 200)
   - bi:business_glossary_term_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404)
   - bi:business_glossary_term_delete (GET 405, POST 302 -> list, IDOR 404)
   - bi:business_glossary_term_certify (GET 405, POST 302 to certified stamps user/time, uncertify clears, invalid status, IDOR 404)
4. CalculatedMeasure views:
   - bi:calculated_measure_list (HTTP 200, context vars, search, filters, junk ?model=invalid -> 200, pagination)
   - bi:calculated_measure_detail (GET 200, context vars, 404, IDOR 404)
   - bi:calculated_measure_create (GET 200 prefill, POST 302 -> detail, formula validation 200)
   - bi:calculated_measure_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404)
   - bi:calculated_measure_delete (GET 405, POST 302 -> list, IDOR 404)
5. DrillHierarchy views:
   - bi:drill_hierarchy_list (HTTP 200, context vars, search, filters, junk ?model=invalid -> 200, pagination)
   - bi:drill_hierarchy_detail (GET 200, context vars, 404, IDOR 404)
   - bi:drill_hierarchy_create (GET 200 prefill, POST 302 -> detail, invalid JSON levels 200)
   - bi:drill_hierarchy_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404)
   - bi:drill_hierarchy_delete (GET 405, POST 302 -> list, IDOR 404)
"""
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    BusinessGlossaryTerm,
    CalculatedMeasure,
    DataMart,
    DrillHierarchy,
    SemanticModel,
    WarehouseTable,
)
from apps.core.models import AuditLog


# ---------------------------------------------------------------------------
# Fixture Bridges (to support semantic_model_a when conftest expects warehouse_table/data_mart)
# ---------------------------------------------------------------------------


@pytest.fixture
def warehouse_table(warehouse_table_a):
    """Bridge fixture to satisfy conftest.semantic_model_a dependency."""
    return warehouse_table_a


@pytest.fixture
def data_mart(data_mart_a):
    """Bridge fixture to satisfy conftest.semantic_model_a dependency."""
    return data_mart_a


# ---------------------------------------------------------------------------
# Module-level test helpers (prefixed with _semanticlayer_*)
# ---------------------------------------------------------------------------


def _semanticlayer_create_model(tenant, name="Test Semantic Model", code="test_sem_model", **kwargs):
    """Helper to create a SemanticModel with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "model_type": "fact",
        "primary_key_column": "id",
        "scd_type": "type_1",
        "access_tier": "public",
        "certification_status": "draft",
        "is_active": True,
    }
    defaults.update(kwargs)
    return SemanticModel.objects.create(**defaults)


def _semanticlayer_create_term(tenant, name="Test Glossary Term", code="test_term", **kwargs):
    """Helper to create a BusinessGlossaryTerm with defaults."""
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


def _semanticlayer_create_measure(tenant, semantic_model, name="Test Measure", code="test_measure", **kwargs):
    """Helper to create a CalculatedMeasure with defaults."""
    defaults = {
        "tenant": tenant,
        "semantic_model": semantic_model,
        "name": name,
        "code": code,
        "aggregation_type": "sum",
        "source_column": "amount",
        "time_intelligence": "none",
        "format_string": "decimal",
        "display_units": "auto",
        "is_active": True,
    }
    defaults.update(kwargs)
    return CalculatedMeasure.objects.create(**defaults)


def _semanticlayer_create_hierarchy(tenant, semantic_model, name="Test Hierarchy", code="test_hierarchy", **kwargs):
    """Helper to create a DrillHierarchy with defaults."""
    defaults = {
        "tenant": tenant,
        "semantic_model": semantic_model,
        "name": name,
        "code": code,
        "hierarchy_type": "time",
        "levels_json": [
            {"level": 1, "name": "Year", "column": "year"},
            {"level": 2, "name": "Quarter", "column": "quarter"},
        ],
        "primary_drill_path": True,
        "is_active": True,
    }
    defaults.update(kwargs)
    return DrillHierarchy.objects.create(**defaults)


# ===========================================================================
# 1. Semantic Overview Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_overview_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to overview redirect to login."""
    url = reverse("bi:semantic_overview")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_semanticlayer_overview_renders_200_and_context_keys(
    client_a, semantic_model_a, glossary_term_a, calculated_measure_a, drill_hierarchy_a
):
    """Verify bi:semantic_overview renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:semantic_overview")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "total_models",
        "total_certified_models",
        "total_glossary_terms",
        "total_certified_terms",
        "total_measures",
        "total_hierarchies",
        "recent_models",
        "recent_terms",
        "model_type_counts",
        "domain_term_counts",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in overview"

    assert response.context["total_models"] >= 1
    assert response.context["total_certified_models"] >= 1
    assert response.context["total_glossary_terms"] >= 1
    assert response.context["total_certified_terms"] >= 1
    assert response.context["total_measures"] >= 1
    assert response.context["total_hierarchies"] >= 1
    assert semantic_model_a in response.context["recent_models"]
    assert glossary_term_a in response.context["recent_terms"]


@pytest.mark.django_db
def test_semanticlayer_overview_metrics_calculation(client_a, tenant_a, warehouse_table, data_mart, admin_user):
    """Verify metric calculations for certified vs draft counts, distributions, and recent items."""
    # Create extra certified and draft models
    m1 = _semanticlayer_create_model(tenant_a, name="M1 Fact", code="m1_fact", model_type="fact", certification_status="certified")
    m2 = _semanticlayer_create_model(tenant_a, name="M2 Dim", code="m2_dim", model_type="dimension", certification_status="draft")
    t1 = _semanticlayer_create_term(tenant_a, name="T1 Fin", code="t1_fin", domain_category="finance", certification_status="certified")
    t2 = _semanticlayer_create_term(tenant_a, name="T2 Ops", code="t2_ops", domain_category="operations", certification_status="draft")

    url = reverse("bi:semantic_overview")
    response = client_a.get(url)

    assert response.status_code == 200
    assert response.context["total_models"] >= 2
    assert response.context["total_certified_models"] >= 1
    assert response.context["total_glossary_terms"] >= 2
    assert response.context["total_certified_terms"] >= 1

    # Check breakdown structures
    model_type_counts = response.context["model_type_counts"]
    assert isinstance(model_type_counts, list)
    types_found = [item["model_type"] for item in model_type_counts]
    assert any("Fact" in t for t in types_found)

    domain_counts = response.context["domain_term_counts"]
    assert isinstance(domain_counts, list)
    domains_found = [item["domain_category"] for item in domain_counts]
    assert any("Finance" in d for d in domains_found)


@pytest.mark.django_db
def test_semanticlayer_overview_empty_tenant(client_b, tenant_b):
    """Verify overview renders gracefully with 0 counts when tenant has no records."""
    SemanticModel.objects.filter(tenant=tenant_b).delete()
    BusinessGlossaryTerm.objects.filter(tenant=tenant_b).delete()
    CalculatedMeasure.objects.filter(tenant=tenant_b).delete()
    DrillHierarchy.objects.filter(tenant=tenant_b).delete()

    url = reverse("bi:semantic_overview")
    response = client_b.get(url)

    assert response.status_code == 200
    assert response.context["total_models"] == 0
    assert response.context["total_certified_models"] == 0
    assert response.context["total_glossary_terms"] == 0
    assert response.context["total_certified_terms"] == 0
    assert response.context["total_measures"] == 0
    assert response.context["total_hierarchies"] == 0
    assert list(response.context["recent_models"]) == []
    assert list(response.context["recent_terms"]) == []


# ===========================================================================
# 2. SemanticModel Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to semantic model list redirect to login."""
    url = reverse("bi:semantic_model_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_renders_200_and_context_keys(client_a, semantic_model_a):
    """Verify bi:semantic_model_list renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:semantic_model_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "models",
        "semantic_models",
        "object_list",
        "page_obj",
        "is_paginated",
        "total_count",
        "search_query",
        "model_type_filter",
        "certification_status_filter",
        "scd_type_filter",
        "data_mart_filter",
        "is_active_filter",
        "model_type_choices",
        "certification_status_choices",
        "scd_type_choices",
        "data_marts",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in semantic_model_list"

    assert semantic_model_a in response.context["models"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_search_by_name_and_code(client_a, tenant_a):
    """Verify semantic model list search filter by name and code."""
    m1 = _semanticlayer_create_model(tenant_a, name="Alpha Revenue Model", code="alpha_rev_model")
    m2 = _semanticlayer_create_model(tenant_a, name="Beta Cost Model", code="beta_cost_model")

    url = reverse("bi:semantic_model_list")

    # Search by name substring
    resp_name = client_a.get(url, {"q": "Alpha"})
    assert resp_name.status_code == 200
    results = list(resp_name.context["models"])
    assert m1 in results
    assert m2 not in results

    # Search by code substring
    resp_code = client_a.get(url, {"q": "beta_cost"})
    assert resp_code.status_code == 200
    results = list(resp_code.context["models"])
    assert m2 in results
    assert m1 not in results


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_search_by_primary_natural_keys_and_description(client_a, tenant_a):
    """Verify search matches primary_key_column, natural_key_columns, and description."""
    m1 = _semanticlayer_create_model(
        tenant_a,
        name="Key Model",
        code="key_model",
        primary_key_column="telemetry_packet_id",
        natural_key_columns="sensor_device_code",
    )
    m2 = _semanticlayer_create_model(
        tenant_a,
        name="Desc Model",
        code="desc_model",
        description="Enterprise warehouse unified entity",
    )

    url = reverse("bi:semantic_model_list")

    resp1 = client_a.get(url, {"q": "sensor_device"})
    assert m1 in resp1.context["models"]
    assert m2 not in resp1.context["models"]

    resp2 = client_a.get(url, {"q": "unified entity"})
    assert m2 in resp2.context["models"]
    assert m1 not in resp2.context["models"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_filter_model_type(client_a, tenant_a):
    """Verify model_type dropdown filter works accurately."""
    m_fact = _semanticlayer_create_model(tenant_a, name="Order Fact", code="order_fact", model_type="fact")
    m_dim = _semanticlayer_create_model(tenant_a, name="Customer Dim", code="customer_dim", model_type="dimension")

    url = reverse("bi:semantic_model_list")

    resp_dim = client_a.get(url, {"model_type": "dimension"})
    results = list(resp_dim.context["models"])
    assert m_dim in results
    assert m_fact not in results


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_filter_certification_status(client_a, tenant_a):
    """Verify certification_status filter works accurately."""
    m_cert = _semanticlayer_create_model(tenant_a, name="Certified M", code="cert_m", certification_status="certified")
    m_draft = _semanticlayer_create_model(tenant_a, name="Draft M", code="draft_m", certification_status="draft")

    url = reverse("bi:semantic_model_list")

    resp = client_a.get(url, {"certification_status": "certified"})
    results = list(resp.context["models"])
    assert m_cert in results
    assert m_draft not in results


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_filter_scd_type(client_a, tenant_a):
    """Verify scd_type filter works accurately."""
    m_type1 = _semanticlayer_create_model(tenant_a, name="Type 1 M", code="type1_m", scd_type="type_1")
    m_type2 = _semanticlayer_create_model(tenant_a, name="Type 2 M", code="type2_m", scd_type="type_2")

    url = reverse("bi:semantic_model_list")

    resp = client_a.get(url, {"scd_type": "type_2"})
    results = list(resp.context["models"])
    assert m_type2 in results
    assert m_type1 not in results


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_filter_data_mart(client_a, tenant_a, data_mart_a):
    """Verify data_mart ID filter works accurately."""
    mart2 = DataMart.objects.create(
        tenant=tenant_a,
        name="Operations Mart",
        code="ops_mart",
        subject_area="operations",
        access_tier="department",
        refresh_cadence="daily",
        is_active=True,
    )
    m1 = _semanticlayer_create_model(tenant_a, name="Sales M", code="sales_m", data_mart=data_mart_a)
    m2 = _semanticlayer_create_model(tenant_a, name="Ops M", code="ops_m", data_mart=mart2)

    url = reverse("bi:semantic_model_list")

    resp = client_a.get(url, {"data_mart": str(mart2.pk)})
    results = list(resp.context["models"])
    assert m2 in results
    assert m1 not in results


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_filter_data_mart_junk_non_digit_returns_200(client_a, semantic_model_a):
    """Verify junk ?data_mart=invalid does not crash and returns 200."""
    url = reverse("bi:semantic_model_list")
    response = client_a.get(url, {"data_mart": "invalid_not_a_digit"})
    assert response.status_code == 200
    assert semantic_model_a in response.context["models"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_filter_is_active(client_a, tenant_a):
    """Verify is_active filter (1 vs 0)."""
    m_act = _semanticlayer_create_model(tenant_a, name="Active M", code="act_m", is_active=True)
    m_inact = _semanticlayer_create_model(tenant_a, name="Inactive M", code="inact_m", is_active=False)

    url = reverse("bi:semantic_model_list")

    resp_act = client_a.get(url, {"is_active": "1"})
    assert m_act in resp_act.context["models"]
    assert m_inact not in resp_act.context["models"]

    resp_inact = client_a.get(url, {"is_active": "0"})
    assert m_inact in resp_inact.context["models"]
    assert m_act not in resp_inact.context["models"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_list_pagination_15_per_page(client_a, tenant_a):
    """Verify 15 records per page pagination."""
    # Ensure fresh set of 16 records
    SemanticModel.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _semanticlayer_create_model(tenant_a, name=f"Pagination Model {i:02d}", code=f"pag_model_{i:02d}")

    url = reverse("bi:semantic_model_list")

    # Page 1
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["is_paginated"] is True
    assert resp_p1.context["page_obj"].has_next() is True

    # Page 2
    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["page_obj"]) == 1
    assert resp_p2.context["page_obj"].has_previous() is True


@pytest.mark.django_db
def test_semanticlayer_semantic_model_detail_renders_200_and_context_keys(
    client_a, semantic_model_a, calculated_measure_a, drill_hierarchy_a
):
    """Verify bi:semantic_model_detail returns HTTP 200 and pinned context keys."""
    url = reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = ["model", "semantic_model", "object", "measures", "drill_hierarchies", "certify_form"]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in semantic_model_detail"

    assert response.context["model"] == semantic_model_a
    assert calculated_measure_a in response.context["measures"]
    assert drill_hierarchy_a in response.context["drill_hierarchies"]


@pytest.mark.django_db
def test_semanticlayer_semantic_model_detail_non_existent_404(client_a):
    """Verify 404 for non-existent semantic model PK."""
    url = reverse("bi:semantic_model_detail", kwargs={"pk": 999999})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_semanticlayer_semantic_model_detail_cross_tenant_idor_404(client_a, semantic_model_b):
    """Verify cross-tenant IDOR access to semantic model detail returns 404."""
    url = reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_semanticlayer_semantic_model_create_get_renders_200_and_context_keys(client_a):
    """Verify GET on semantic model create view renders 200 and context keys."""
    url = reverse("bi:semantic_model_create")
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False


@pytest.mark.django_db
def test_semanticlayer_semantic_model_create_post_success_redirect_and_audit(client_a, tenant_a, warehouse_table, data_mart):
    """Verify successful POST creates model, stamps tenant, logs audit, and redirects to detail."""
    url = reverse("bi:semantic_model_create")
    payload = {
        "name": "Created Revenue Model",
        "code": "created_revenue_model",
        "model_type": "fact",
        "warehouse_table": warehouse_table.pk,
        "data_mart": data_mart.pk,
        "primary_key_column": "id",
        "natural_key_columns": "invoice_num",
        "grain_description": "Per line item",
        "scd_type": "type_1",
        "access_tier": "department",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_model = SemanticModel.objects.filter(tenant=tenant_a, code="created_revenue_model").first()
    assert created_model is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:semantic_model_detail", kwargs={"pk": created_model.pk})
    assert created_model.tenant == tenant_a
    assert created_model.name == "Created Revenue Model"

    # Verify audit log
    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="create").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_semanticlayer_semantic_model_create_post_auto_assigns_owner_if_blank(client_a, tenant_a, admin_user):
    """Verify model owner is auto-assigned to request.user if left blank."""
    url = reverse("bi:semantic_model_create")
    payload = {
        "name": "Auto Owner Model",
        "code": "auto_owner_model",
        "model_type": "fact",
        "primary_key_column": "id",
        "scd_type": "type_1",
        "access_tier": "public",
        "is_active": True,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 302

    created_model = SemanticModel.objects.get(tenant=tenant_a, code="auto_owner_model")
    assert created_model.owner == admin_user


@pytest.mark.django_db
def test_semanticlayer_semantic_model_create_post_invalid_virtual_view_without_sql_definition(client_a):
    """Verify validation error when is_virtual_view is enabled without sql_definition."""
    url = reverse("bi:semantic_model_create")
    payload = {
        "name": "Virtual View Model",
        "code": "virtual_view_model",
        "model_type": "virtual_view",
        "is_virtual_view": True,
        "sql_definition": "",  # missing required SQL
        "primary_key_column": "id",
        "scd_type": "type_0",
        "access_tier": "public",
        "is_active": True,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "form" in response.context
    assert "sql_definition" in response.context["form"].errors


@pytest.mark.django_db
def test_semanticlayer_semantic_model_edit_get_renders_200_and_context_keys(client_a, semantic_model_a):
    """Verify GET on edit renders 200 with instance context and is_edit=True."""
    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["model"] == semantic_model_a
    assert response.context["semantic_model"] == semantic_model_a
    assert response.context["object"] == semantic_model_a


@pytest.mark.django_db
def test_semanticlayer_semantic_model_edit_post_success_redirect_and_audit(client_a, tenant_a, semantic_model_a):
    """Verify successful POST updates model, logs audit, and redirects to detail."""
    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk})
    payload = {
        "name": "Updated Model Name",
        "code": semantic_model_a.code,
        "model_type": "dimension",
        "primary_key_column": "id",
        "grain_description": "Updated grain narrative",
        "scd_type": "type_2",
        "access_tier": "restricted",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_a.pk})

    semantic_model_a.refresh_from_db()
    assert semantic_model_a.name == "Updated Model Name"
    assert semantic_model_a.model_type == "dimension"
    assert semantic_model_a.scd_type == "type_2"

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="update").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_semanticlayer_semantic_model_edit_post_invalid_renders_errors(client_a, semantic_model_a):
    """Verify invalid edit POST returns 200 with form errors."""
    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_a.pk})
    payload = {
        "name": "",  # Name is required
        "code": semantic_model_a.code,
        "model_type": "fact",
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "name" in response.context["form"].errors


@pytest.mark.django_db
def test_semanticlayer_semantic_model_edit_cross_tenant_idor_404(client_a, semantic_model_b):
    """Verify cross-tenant edit returns 404."""
    url = reverse("bi:semantic_model_edit", kwargs={"pk": semantic_model_b.pk})
    response = client_a.get(url)
    assert response.status_code == 404

    resp_post = client_a.post(url, {"name": "Hacked Name"})
    assert resp_post.status_code == 404


@pytest.mark.django_db
def test_semanticlayer_semantic_model_delete_get_method_not_allowed_405(client_a, semantic_model_a):
    """Verify GET on delete endpoint returns HTTP 405 Method Not Allowed."""
    url = reverse("bi:semantic_model_delete", kwargs={"pk": semantic_model_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_semanticlayer_semantic_model_delete_post_success_redirect_and_audit(client_a, tenant_a):
    """Verify POST delete removes object, logs audit, and redirects to list."""
    model = _semanticlayer_create_model(tenant_a, name="To Delete Model", code="to_delete_model")
    url = reverse("bi:semantic_model_delete", kwargs={"pk": model.pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("bi:semantic_model_list")

    assert not SemanticModel.objects.filter(pk=model.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_semanticlayer_semantic_model_delete_cross_tenant_idor_404(client_a, semantic_model_b):
    """Verify cross-tenant delete returns 404."""
    url = reverse("bi:semantic_model_delete", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert SemanticModel.objects.filter(pk=semantic_model_b.pk).exists()


@pytest.mark.django_db
def test_semanticlayer_semantic_model_certify_get_method_not_allowed_405(client_a, semantic_model_a):
    """Verify GET on certify returns HTTP 405."""
    url = reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_semanticlayer_semantic_model_certify_post_to_certified_stamps_user_and_time(
    client_a, tenant_a, warehouse_table, data_mart, admin_user
):
    """Verify certify POST transition to certified stamps certified_by and certified_at."""
    model = _semanticlayer_create_model(tenant_a, name="Certify Test", code="certify_test", certification_status="draft")
    url = reverse("bi:semantic_model_certify", kwargs={"pk": model.pk})

    response = client_a.post(url, {"certification_status": "certified", "certification_notes": "Signoff complete"})
    assert response.status_code == 302
    assert response.url == reverse("bi:semantic_model_detail", kwargs={"pk": model.pk})

    model.refresh_from_db()
    assert model.certification_status == "certified"
    assert model.certified_by == admin_user
    assert model.certified_at is not None
    assert model.certification_notes == "Signoff complete"
    assert AuditLog.objects.filter(tenant=tenant_a, action="certify").exists()


@pytest.mark.django_db
def test_semanticlayer_semantic_model_certify_post_to_draft_clears_user_and_time(client_a, semantic_model_a):
    """Verify uncertifying model (transitioning back to draft) clears certified_by and certified_at."""
    assert semantic_model_a.certification_status == "certified"
    assert semantic_model_a.certified_by is not None

    url = reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_a.pk})
    response = client_a.post(url, {"certification_status": "draft", "certification_notes": "Revoking status"})
    assert response.status_code == 302

    semantic_model_a.refresh_from_db()
    assert semantic_model_a.certification_status == "draft"
    assert semantic_model_a.certified_by is None
    assert semantic_model_a.certified_at is None


@pytest.mark.django_db
def test_semanticlayer_semantic_model_certify_post_invalid_status_sets_error_message(client_a, semantic_model_a):
    """Verify invalid certification_status choice rejects update."""
    original_status = semantic_model_a.certification_status
    url = reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_a.pk})

    response = client_a.post(url, {"certification_status": "not_a_real_status"})
    assert response.status_code == 302

    semantic_model_a.refresh_from_db()
    assert semantic_model_a.certification_status == original_status


@pytest.mark.django_db
def test_semanticlayer_semantic_model_certify_cross_tenant_idor_404(client_a, semantic_model_b):
    """Verify cross-tenant certify returns 404."""
    url = reverse("bi:semantic_model_certify", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url, {"certification_status": "certified"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_semanticlayer_semantic_model_introspect_get_method_not_allowed_405(client_a, semantic_model_a):
    """Verify GET on introspect returns 405."""
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_a.pk})
    response = client_a.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_semanticlayer_semantic_model_introspect_post_success_computes_fingerprint_and_stamps_time(
    client_a, tenant_a, semantic_model_a, warehouse_table
):
    """Verify introspect POST computes SHA256 fingerprint from warehouse table schema."""
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_a.pk})
    response = client_a.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:semantic_model_detail", kwargs={"pk": semantic_model_a.pk})

    semantic_model_a.refresh_from_db()
    assert semantic_model_a.source_fingerprint != ""
    assert semantic_model_a.last_introspected_at is not None
    assert AuditLog.objects.filter(tenant=tenant_a, action="introspect").exists()


@pytest.mark.django_db
def test_semanticlayer_semantic_model_introspect_post_without_warehouse_table_sets_error(client_a, tenant_a):
    """Verify introspect fails with message if model has no bound warehouse table."""
    model_without_table = _semanticlayer_create_model(tenant_a, name="No Table Model", code="no_tbl_model", warehouse_table=None)
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": model_without_table.pk})

    response = client_a.post(url)
    assert response.status_code == 302
    model_without_table.refresh_from_db()
    assert model_without_table.source_fingerprint == ""


@pytest.mark.django_db
def test_semanticlayer_semantic_model_introspect_post_cross_tenant_warehouse_table_sets_error(
    client_a, tenant_a, warehouse_table_b
):
    """Verify introspect checks table.tenant_id matching request.tenant."""
    model_cross_bound = _semanticlayer_create_model(
        tenant_a, name="Cross Bound", code="cross_bound", warehouse_table=warehouse_table_b
    )
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": model_cross_bound.pk})

    response = client_a.post(url)
    assert response.status_code == 302
    model_cross_bound.refresh_from_db()
    assert model_cross_bound.source_fingerprint == ""


@pytest.mark.django_db
def test_semanticlayer_semantic_model_introspect_cross_tenant_idor_404(client_a, semantic_model_b):
    """Verify cross-tenant introspect returns 404."""
    url = reverse("bi:semantic_model_introspect", kwargs={"pk": semantic_model_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404


# ===========================================================================
# 3. BusinessGlossaryTerm Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to glossary term list redirect to login."""
    url = reverse("bi:business_glossary_term_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_renders_200_and_context_keys(client_a, glossary_term_a):
    """Verify bi:business_glossary_term_list returns HTTP 200 with all pinned context keys."""
    url = reverse("bi:business_glossary_term_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "terms",
        "glossary_terms",
        "object_list",
        "page_obj",
        "is_paginated",
        "total_count",
        "search_query",
        "domain_filter",
        "certification_status_filter",
        "is_active_filter",
        "domain_category_choices",
        "certification_status_choices",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in business_glossary_term_list"

    assert glossary_term_a in response.context["terms"]


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_search_by_name_definition_and_synonyms(client_a, tenant_a):
    """Verify search matches name, short_definition, and synonyms."""
    t1 = _semanticlayer_create_term(
        tenant_a,
        name="Customer Churn Rate",
        code="churn_rate",
        short_definition="Percentage of lost subscribers",
        synonyms="Attrition, Loss Rate",
    )
    t2 = _semanticlayer_create_term(
        tenant_a,
        name="Gross Profit Margin",
        code="gpm",
        short_definition="Net sales minus COGS",
        synonyms="GPM, Margin %",
    )

    url = reverse("bi:business_glossary_term_list")

    resp_syn = client_a.get(url, {"q": "Attrition"})
    assert t1 in resp_syn.context["terms"]
    assert t2 not in resp_syn.context["terms"]

    resp_def = client_a.get(url, {"q": "COGS"})
    assert t2 in resp_def.context["terms"]
    assert t1 not in resp_def.context["terms"]


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_filter_domain(client_a, tenant_a):
    """Verify domain_category dropdown filter."""
    t_fin = _semanticlayer_create_term(tenant_a, name="EBITDA", code="ebitda", domain_category="finance")
    t_hr = _semanticlayer_create_term(tenant_a, name="Headcount", code="headcount", domain_category="hr")

    url = reverse("bi:business_glossary_term_list")
    resp = client_a.get(url, {"domain": "hr"})

    results = list(resp.context["terms"])
    assert t_hr in results
    assert t_fin not in results


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_filter_certification_status(client_a, tenant_a):
    """Verify certification_status filter on glossary list."""
    t_cert = _semanticlayer_create_term(tenant_a, name="Cert Term", code="cert_term", certification_status="certified")
    t_rev = _semanticlayer_create_term(tenant_a, name="Review Term", code="rev_term", certification_status="in_review")

    url = reverse("bi:business_glossary_term_list")
    resp = client_a.get(url, {"certification_status": "in_review"})

    results = list(resp.context["terms"])
    assert t_rev in results
    assert t_cert not in results


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_filter_is_active(client_a, tenant_a):
    """Verify is_active filter (1 vs 0) on glossary terms."""
    t_act = _semanticlayer_create_term(tenant_a, name="Active Term", code="act_term", is_active=True)
    t_inact = _semanticlayer_create_term(tenant_a, name="Inactive Term", code="inact_term", is_active=False)

    url = reverse("bi:business_glossary_term_list")

    resp_act = client_a.get(url, {"is_active": "1"})
    assert t_act in resp_act.context["terms"]
    assert t_inact not in resp_act.context["terms"]

    resp_inact = client_a.get(url, {"is_active": "0"})
    assert t_inact in resp_inact.context["terms"]
    assert t_act not in resp_inact.context["terms"]


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_list_pagination_15_per_page(client_a, tenant_a):
    """Verify 15 terms per page pagination."""
    BusinessGlossaryTerm.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _semanticlayer_create_term(tenant_a, name=f"Term {i:02d}", code=f"term_{i:02d}")

    url = reverse("bi:business_glossary_term_list")
    resp_p1 = client_a.get(url)
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["is_paginated"] is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert len(resp_p2.context["page_obj"]) == 1


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_detail_renders_200_and_context_keys(
    client_a, glossary_term_a, calculated_measure_a
):
    """Verify bi:business_glossary_term_detail returns HTTP 200 with pinned keys."""
    url = reverse("bi:business_glossary_term_detail", kwargs={"pk": glossary_term_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = ["term", "glossary_term", "object", "related_measures", "certify_form"]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in business_glossary_term_detail"

    assert response.context["term"] == glossary_term_a
    assert calculated_measure_a in response.context["related_measures"]


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_detail_non_existent_404(client_a):
    """Verify 404 for non-existent glossary term."""
    url = reverse("bi:business_glossary_term_detail", kwargs={"pk": 999999})
    assert client_a.get(url).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_detail_cross_tenant_idor_404(client_a, glossary_term_b):
    """Verify cross-tenant detail access returns 404."""
    url = reverse("bi:business_glossary_term_detail", kwargs={"pk": glossary_term_b.pk})
    assert client_a.get(url).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_create_get_renders_200_and_context_keys(client_a):
    """Verify GET on glossary create view renders 200 and context keys."""
    url = reverse("bi:business_glossary_term_create")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_create_post_success_redirect_and_audit(client_a, tenant_a):
    """Verify successful POST creates glossary term, logs audit, and redirects to detail."""
    url = reverse("bi:business_glossary_term_create")
    payload = {
        "name": "Customer Lifetime Value",
        "code": "clv",
        "domain_category": "marketing",
        "short_definition": "Estimated total revenue a customer will generate throughout their engagement.",
        "calculation_rule": "ARPU * Average Lifetime Duration",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_term = BusinessGlossaryTerm.objects.filter(tenant=tenant_a, code="clv").first()
    assert created_term is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:business_glossary_term_detail", kwargs={"pk": created_term.pk})
    assert created_term.tenant == tenant_a
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_create_post_auto_assigns_steward_if_omitted(client_a, tenant_a, admin_user):
    """Verify steward is auto-assigned to request.user if omitted."""
    url = reverse("bi:business_glossary_term_create")
    payload = {
        "name": "Auto Steward Term",
        "code": "auto_steward_term",
        "domain_category": "sales",
        "short_definition": "Term created without steward explicit selection",
        "is_active": True,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 302

    term = BusinessGlossaryTerm.objects.get(tenant=tenant_a, code="auto_steward_term")
    assert term.steward == admin_user


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_create_post_with_related_terms_and_m2m(client_a, tenant_a, glossary_term_a):
    """Verify M2M related_terms association on create."""
    url = reverse("bi:business_glossary_term_create")
    payload = {
        "name": "Annual Recurring Revenue",
        "code": "arr",
        "domain_category": "finance",
        "short_definition": "Annualized recurring revenue run rate",
        "related_terms": [glossary_term_a.pk],
        "is_active": True,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 302

    created_term = BusinessGlossaryTerm.objects.get(tenant=tenant_a, code="arr")
    assert glossary_term_a in created_term.related_terms.all()


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_create_post_invalid_renders_errors(client_a):
    """Verify invalid create POST returns 200 with form errors."""
    url = reverse("bi:business_glossary_term_create")
    payload = {
        "name": "",  # missing required name
        "code": "bad_code",
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "name" in response.context["form"].errors


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_edit_get_renders_200_and_context_keys(client_a, glossary_term_a):
    """Verify GET on edit renders 200 with instance context and is_edit=True."""
    url = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["term"] == glossary_term_a
    assert response.context["glossary_term"] == glossary_term_a
    assert response.context["object"] == glossary_term_a


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_edit_post_success_redirect_and_audit(client_a, tenant_a, glossary_term_a):
    """Verify successful POST updates glossary term, logs audit, and redirects to detail."""
    url = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_a.pk})
    payload = {
        "name": "Updated NRR Title",
        "code": glossary_term_a.code,
        "domain_category": "sales",
        "short_definition": "Updated corporate definition narrative",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:business_glossary_term_detail", kwargs={"pk": glossary_term_a.pk})

    glossary_term_a.refresh_from_db()
    assert glossary_term_a.name == "Updated NRR Title"
    assert glossary_term_a.domain_category == "sales"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_edit_cross_tenant_idor_404(client_a, glossary_term_b):
    """Verify cross-tenant edit returns 404."""
    url = reverse("bi:business_glossary_term_edit", kwargs={"pk": glossary_term_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"name": "Hacked Name"}).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_delete_get_method_not_allowed_405(client_a, glossary_term_a):
    """Verify GET on delete returns 405."""
    url = reverse("bi:business_glossary_term_delete", kwargs={"pk": glossary_term_a.pk})
    assert client_a.get(url).status_code == 405


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_delete_post_success_redirect_and_audit(client_a, tenant_a):
    """Verify POST delete removes term, logs audit, and redirects to list."""
    term = _semanticlayer_create_term(tenant_a, name="Term To Delete", code="term_to_delete")
    url = reverse("bi:business_glossary_term_delete", kwargs={"pk": term.pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("bi:business_glossary_term_list")

    assert not BusinessGlossaryTerm.objects.filter(pk=term.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_delete_cross_tenant_idor_404(client_a, glossary_term_b):
    """Verify cross-tenant delete returns 404."""
    url = reverse("bi:business_glossary_term_delete", kwargs={"pk": glossary_term_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert BusinessGlossaryTerm.objects.filter(pk=glossary_term_b.pk).exists()


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_certify_get_method_not_allowed_405(client_a, glossary_term_a):
    """Verify GET on term certify returns 405."""
    url = reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_a.pk})
    assert client_a.get(url).status_code == 405


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_certify_post_to_certified_stamps_user_and_time(
    client_a, tenant_a, admin_user
):
    """Verify certify POST stamps certified_by and certified_at."""
    term = _semanticlayer_create_term(tenant_a, name="Draft Term", code="draft_term", certification_status="draft")
    url = reverse("bi:business_glossary_term_certify", kwargs={"pk": term.pk})

    response = client_a.post(url, {"certification_status": "certified", "certification_notes": "Data council approved"})
    assert response.status_code == 302
    assert response.url == reverse("bi:business_glossary_term_detail", kwargs={"pk": term.pk})

    term.refresh_from_db()
    assert term.certification_status == "certified"
    assert term.certified_by == admin_user
    assert term.certified_at is not None
    assert term.certification_notes == "Data council approved"
    assert AuditLog.objects.filter(tenant=tenant_a, action="certify").exists()


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_certify_post_to_draft_clears_user_and_time(client_a, glossary_term_a):
    """Verify uncertifying term clears certified_by and certified_at."""
    assert glossary_term_a.certification_status == "certified"

    url = reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_a.pk})
    response = client_a.post(url, {"certification_status": "draft", "certification_notes": "Demoting to draft"})
    assert response.status_code == 302

    glossary_term_a.refresh_from_db()
    assert glossary_term_a.certification_status == "draft"
    assert glossary_term_a.certified_by is None
    assert glossary_term_a.certified_at is None


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_certify_post_invalid_status_sets_error_message(client_a, glossary_term_a):
    """Verify invalid status input leaves term status unchanged."""
    url = reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_a.pk})
    response = client_a.post(url, {"certification_status": "garbage_status"})
    assert response.status_code == 302

    glossary_term_a.refresh_from_db()
    assert glossary_term_a.certification_status == "certified"


@pytest.mark.django_db
def test_semanticlayer_business_glossary_term_certify_cross_tenant_idor_404(client_a, glossary_term_b):
    """Verify cross-tenant certify returns 404."""
    url = reverse("bi:business_glossary_term_certify", kwargs={"pk": glossary_term_b.pk})
    assert client_a.post(url, {"certification_status": "certified"}).status_code == 404


# ===========================================================================
# 4. CalculatedMeasure Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to measure list redirect to login."""
    url = reverse("bi:calculated_measure_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_renders_200_and_context_keys(client_a, calculated_measure_a):
    """Verify bi:calculated_measure_list returns HTTP 200 with pinned context keys."""
    url = reverse("bi:calculated_measure_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "measures",
        "calculated_measures",
        "object_list",
        "page_obj",
        "is_paginated",
        "total_count",
        "search_query",
        "model_filter",
        "aggregation_filter",
        "time_intelligence_filter",
        "is_active_filter",
        "aggregation_type_choices",
        "time_intelligence_choices",
        "semantic_models",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in calculated_measure_list"

    assert calculated_measure_a in response.context["measures"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_search_by_name_and_column(client_a, tenant_a, semantic_model_a):
    """Verify search filter on calculated measure by name and source_column."""
    cm1 = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Total Revenue", code="tot_rev", source_column="extended_amount")
    cm2 = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Unit Count", code="unit_cnt", source_column="quantity")

    url = reverse("bi:calculated_measure_list")

    resp_name = client_a.get(url, {"q": "Total Revenue"})
    assert cm1 in resp_name.context["measures"]
    assert cm2 not in resp_name.context["measures"]

    resp_col = client_a.get(url, {"q": "quantity"})
    assert cm2 in resp_col.context["measures"]
    assert cm1 not in resp_col.context["measures"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_filter_model(client_a, tenant_a, semantic_model_a):
    """Verify model ID filter on calculated measure list."""
    other_model = _semanticlayer_create_model(tenant_a, name="Other Model", code="other_model")
    cm1 = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="M1 Measure", code="m1_meas")
    cm2 = _semanticlayer_create_measure(tenant_a, other_model, name="M2 Measure", code="m2_meas")

    url = reverse("bi:calculated_measure_list")
    resp = client_a.get(url, {"model": str(other_model.pk)})

    results = list(resp.context["measures"])
    assert cm2 in results
    assert cm1 not in results


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_filter_model_junk_non_digit_returns_200(client_a, calculated_measure_a):
    """Verify junk ?model=invalid does not crash and returns 200."""
    url = reverse("bi:calculated_measure_list")
    response = client_a.get(url, {"model": "invalid_model_param"})
    assert response.status_code == 200
    assert calculated_measure_a in response.context["measures"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_filter_aggregation(client_a, tenant_a, semantic_model_a):
    """Verify aggregation_type filter."""
    cm_sum = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Sum Measure", code="sum_meas", aggregation_type="sum")
    cm_avg = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Avg Measure", code="avg_meas", aggregation_type="avg")

    url = reverse("bi:calculated_measure_list")
    resp = client_a.get(url, {"aggregation": "avg"})

    results = list(resp.context["measures"])
    assert cm_avg in results
    assert cm_sum not in results


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_filter_time_intelligence(client_a, tenant_a, semantic_model_a):
    """Verify time_intelligence filter."""
    cm_none = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Raw Measure", code="raw_meas", time_intelligence="none")
    cm_yoy = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="YoY Measure", code="yoy_meas", time_intelligence="yoy_growth")

    url = reverse("bi:calculated_measure_list")
    resp = client_a.get(url, {"time_intelligence": "yoy_growth"})

    results = list(resp.context["measures"])
    assert cm_yoy in results
    assert cm_none not in results


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_filter_is_active(client_a, tenant_a, semantic_model_a):
    """Verify is_active filter (1 vs 0)."""
    cm_act = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Active Meas", code="act_meas", is_active=True)
    cm_inact = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="Inactive Meas", code="inact_meas", is_active=False)

    url = reverse("bi:calculated_measure_list")

    resp_act = client_a.get(url, {"is_active": "1"})
    assert cm_act in resp_act.context["measures"]
    assert cm_inact not in resp_act.context["measures"]

    resp_inact = client_a.get(url, {"is_active": "0"})
    assert cm_inact in resp_inact.context["measures"]
    assert cm_act not in resp_inact.context["measures"]


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_list_pagination_15_per_page(client_a, tenant_a, semantic_model_a):
    """Verify 15 measures per page pagination."""
    CalculatedMeasure.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _semanticlayer_create_measure(tenant_a, semantic_model_a, name=f"Measure {i:02d}", code=f"meas_{i:02d}")

    url = reverse("bi:calculated_measure_list")
    resp_p1 = client_a.get(url)
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["is_paginated"] is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert len(resp_p2.context["page_obj"]) == 1


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_detail_renders_200_and_context_keys(client_a, calculated_measure_a):
    """Verify bi:calculated_measure_detail returns HTTP 200 with pinned keys."""
    url = reverse("bi:calculated_measure_detail", kwargs={"pk": calculated_measure_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = ["measure", "calculated_measure", "object"]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in calculated_measure_detail"

    assert response.context["measure"] == calculated_measure_a


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_detail_non_existent_404(client_a):
    """Verify 404 for non-existent measure."""
    url = reverse("bi:calculated_measure_detail", kwargs={"pk": 999999})
    assert client_a.get(url).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_detail_cross_tenant_idor_404(client_a, calculated_measure_b):
    """Verify cross-tenant detail access returns 404."""
    url = reverse("bi:calculated_measure_detail", kwargs={"pk": calculated_measure_b.pk})
    assert client_a.get(url).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_create_get_prefills_model_and_term(client_a, semantic_model_a, glossary_term_a):
    """Verify GET prefill with ?model= and ?glossary_term= query params."""
    url = reverse("bi:calculated_measure_create")
    response = client_a.get(url, {"model": str(semantic_model_a.pk), "glossary_term": str(glossary_term_a.pk)})

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["form"].initial.get("semantic_model") == str(semantic_model_a.pk)
    assert response.context["form"].initial.get("glossary_term") == str(glossary_term_a.pk)


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_create_post_success_redirect_and_audit(
    client_a, tenant_a, semantic_model_a, glossary_term_a
):
    """Verify successful POST creates calculated measure, logs audit, and redirects to detail."""
    url = reverse("bi:calculated_measure_create")
    payload = {
        "semantic_model": semantic_model_a.pk,
        "glossary_term": glossary_term_a.pk,
        "name": "Average Deal Size",
        "code": "avg_deal_size",
        "aggregation_type": "avg",
        "source_column": "deal_amount",
        "time_intelligence": "none",
        "format_string": "currency",
        "display_units": "auto",
        "target_value": "50000.00",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_measure = CalculatedMeasure.objects.filter(tenant=tenant_a, code="avg_deal_size").first()
    assert created_measure is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:calculated_measure_detail", kwargs={"pk": created_measure.pk})
    assert created_measure.tenant == tenant_a
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_create_post_formula_validation_error(client_a, semantic_model_a):
    """Verify formula validation error when aggregation_type='formula' but formula_expression is empty."""
    url = reverse("bi:calculated_measure_create")
    payload = {
        "semantic_model": semantic_model_a.pk,
        "name": "Formula Measure",
        "code": "formula_meas",
        "aggregation_type": "formula",
        "formula_expression": "",  # missing formula
        "is_active": True,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "formula_expression" in response.context["form"].errors


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_edit_get_renders_200_and_context_keys(client_a, calculated_measure_a):
    """Verify GET on edit renders 200 with instance context and is_edit=True."""
    url = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["measure"] == calculated_measure_a
    assert response.context["calculated_measure"] == calculated_measure_a
    assert response.context["object"] == calculated_measure_a


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_edit_post_success_redirect_and_audit(client_a, tenant_a, calculated_measure_a):
    """Verify successful POST updates measure, logs audit, and redirects to detail."""
    url = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_a.pk})
    payload = {
        "semantic_model": calculated_measure_a.semantic_model.pk,
        "name": "Updated Measure Name",
        "code": calculated_measure_a.code,
        "aggregation_type": "count",
        "source_column": "id",
        "time_intelligence": "none",
        "format_string": "integer",
        "display_units": "auto",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:calculated_measure_detail", kwargs={"pk": calculated_measure_a.pk})

    calculated_measure_a.refresh_from_db()
    assert calculated_measure_a.name == "Updated Measure Name"
    assert calculated_measure_a.aggregation_type == "count"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_edit_cross_tenant_idor_404(client_a, calculated_measure_b):
    """Verify cross-tenant edit returns 404."""
    url = reverse("bi:calculated_measure_edit", kwargs={"pk": calculated_measure_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"name": "Hacked"}).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_delete_get_method_not_allowed_405(client_a, calculated_measure_a):
    """Verify GET on delete returns 405."""
    url = reverse("bi:calculated_measure_delete", kwargs={"pk": calculated_measure_a.pk})
    assert client_a.get(url).status_code == 405


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_delete_post_success_redirect_and_audit(client_a, tenant_a, semantic_model_a):
    """Verify POST delete removes measure, logs audit, and redirects to list."""
    meas = _semanticlayer_create_measure(tenant_a, semantic_model_a, name="To Del Meas", code="to_del_meas")
    url = reverse("bi:calculated_measure_delete", kwargs={"pk": meas.pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("bi:calculated_measure_list")

    assert not CalculatedMeasure.objects.filter(pk=meas.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_semanticlayer_calculated_measure_delete_cross_tenant_idor_404(client_a, calculated_measure_b):
    """Verify cross-tenant delete returns 404."""
    url = reverse("bi:calculated_measure_delete", kwargs={"pk": calculated_measure_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert CalculatedMeasure.objects.filter(pk=calculated_measure_b.pk).exists()


# ===========================================================================
# 5. DrillHierarchy Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to drill hierarchy list redirect to login."""
    url = reverse("bi:drill_hierarchy_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_renders_200_and_context_keys(client_a, drill_hierarchy_a):
    """Verify bi:drill_hierarchy_list returns HTTP 200 with pinned context keys."""
    url = reverse("bi:drill_hierarchy_list")
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = [
        "hierarchies",
        "drill_hierarchies",
        "object_list",
        "page_obj",
        "is_paginated",
        "total_count",
        "search_query",
        "model_filter",
        "hierarchy_type_filter",
        "is_active_filter",
        "hierarchy_type_choices",
        "semantic_models",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in drill_hierarchy_list"

    assert drill_hierarchy_a in response.context["hierarchies"]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_search_by_name_and_description(client_a, tenant_a, semantic_model_a):
    """Verify search filter on drill hierarchies by name and description."""
    dh1 = _semanticlayer_create_hierarchy(
        tenant_a, semantic_model_a, name="Geographic Drill", code="geo_drill", description="Territory drill path"
    )
    dh2 = _semanticlayer_create_hierarchy(
        tenant_a, semantic_model_a, name="Product Drill", code="prod_drill", description="SKU hierarchy path"
    )

    url = reverse("bi:drill_hierarchy_list")

    resp_name = client_a.get(url, {"q": "Geographic"})
    assert dh1 in resp_name.context["hierarchies"]
    assert dh2 not in resp_name.context["hierarchies"]

    resp_desc = client_a.get(url, {"q": "SKU hierarchy"})
    assert dh2 in resp_desc.context["hierarchies"]
    assert dh1 not in resp_desc.context["hierarchies"]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_filter_model(client_a, tenant_a, semantic_model_a):
    """Verify model ID filter on drill hierarchy list."""
    other_model = _semanticlayer_create_model(tenant_a, name="Model Two", code="model_two")
    dh1 = _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name="M1 Hierarchy", code="m1_hier")
    dh2 = _semanticlayer_create_hierarchy(tenant_a, other_model, name="M2 Hierarchy", code="m2_hier")

    url = reverse("bi:drill_hierarchy_list")
    resp = client_a.get(url, {"model": str(other_model.pk)})

    results = list(resp.context["hierarchies"])
    assert dh2 in results
    assert dh1 not in results


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_filter_model_junk_non_digit_returns_200(client_a, drill_hierarchy_a):
    """Verify junk ?model=invalid does not crash and returns 200."""
    url = reverse("bi:drill_hierarchy_list")
    response = client_a.get(url, {"model": "not_an_int"})
    assert response.status_code == 200
    assert drill_hierarchy_a in response.context["hierarchies"]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_filter_hierarchy_type(client_a, tenant_a, semantic_model_a):
    """Verify hierarchy_type filter."""
    dh_time = _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name="Time Path", code="time_p", hierarchy_type="time")
    dh_geo = _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name="Geo Path", code="geo_p", hierarchy_type="geography")

    url = reverse("bi:drill_hierarchy_list")
    resp = client_a.get(url, {"hierarchy_type": "geography"})

    results = list(resp.context["hierarchies"])
    assert dh_geo in results
    assert dh_time not in results


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_filter_is_active(client_a, tenant_a, semantic_model_a):
    """Verify is_active filter (1 vs 0)."""
    dh_act = _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name="Active Hier", code="act_h", is_active=True)
    dh_inact = _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name="Inactive Hier", code="inact_h", is_active=False)

    url = reverse("bi:drill_hierarchy_list")

    resp_act = client_a.get(url, {"is_active": "1"})
    assert dh_act in resp_act.context["hierarchies"]
    assert dh_inact not in resp_act.context["hierarchies"]

    resp_inact = client_a.get(url, {"is_active": "0"})
    assert dh_inact in resp_inact.context["hierarchies"]
    assert dh_act not in resp_inact.context["hierarchies"]


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_list_pagination_15_per_page(client_a, tenant_a, semantic_model_a):
    """Verify 15 drill hierarchies per page pagination."""
    DrillHierarchy.objects.filter(tenant=tenant_a).delete()
    for i in range(16):
        _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name=f"Hierarchy {i:02d}", code=f"hier_{i:02d}")

    url = reverse("bi:drill_hierarchy_list")
    resp_p1 = client_a.get(url)
    assert len(resp_p1.context["page_obj"]) == 15
    assert resp_p1.context["is_paginated"] is True

    resp_p2 = client_a.get(url, {"page": 2})
    assert len(resp_p2.context["page_obj"]) == 1


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_detail_renders_200_and_context_keys(client_a, drill_hierarchy_a):
    """Verify bi:drill_hierarchy_detail returns HTTP 200 with pinned keys."""
    url = reverse("bi:drill_hierarchy_detail", kwargs={"pk": drill_hierarchy_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    expected_keys = ["hierarchy", "drill_hierarchy", "object"]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in drill_hierarchy_detail"

    assert response.context["hierarchy"] == drill_hierarchy_a


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_detail_non_existent_404(client_a):
    """Verify 404 for non-existent hierarchy."""
    url = reverse("bi:drill_hierarchy_detail", kwargs={"pk": 999999})
    assert client_a.get(url).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_detail_cross_tenant_idor_404(client_a, drill_hierarchy_b):
    """Verify cross-tenant detail access returns 404."""
    url = reverse("bi:drill_hierarchy_detail", kwargs={"pk": drill_hierarchy_b.pk})
    assert client_a.get(url).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_create_get_prefills_model(client_a, semantic_model_a):
    """Verify GET prefill with ?model= query param."""
    url = reverse("bi:drill_hierarchy_create")
    response = client_a.get(url, {"model": str(semantic_model_a.pk)})

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["form"].initial.get("semantic_model") == str(semantic_model_a.pk)


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_create_post_success_redirect_and_audit(client_a, tenant_a, semantic_model_a):
    """Verify successful POST creates hierarchy, parses levels_json, logs audit, and redirects to detail."""
    url = reverse("bi:drill_hierarchy_create")
    levels = [
        {"level": 1, "name": "Region", "column": "region"},
        {"level": 2, "name": "Country", "column": "country"},
    ]
    payload = {
        "semantic_model": semantic_model_a.pk,
        "name": "Org Territory Drill",
        "code": "org_territory_drill",
        "hierarchy_type": "geography",
        "levels_json_raw": json.dumps(levels),
        "primary_drill_path": True,
        "description": "Territory hierarchy path",
        "is_active": True,
    }
    response = client_a.post(url, payload)

    created_hier = DrillHierarchy.objects.filter(tenant=tenant_a, code="org_territory_drill").first()
    assert created_hier is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:drill_hierarchy_detail", kwargs={"pk": created_hier.pk})
    assert created_hier.tenant == tenant_a
    assert created_hier.levels_json == levels
    assert AuditLog.objects.filter(tenant=tenant_a, action="create").exists()


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_create_post_invalid_json_levels_error(client_a, semantic_model_a):
    """Verify invalid JSON string in levels_json_raw triggers validation error."""
    url = reverse("bi:drill_hierarchy_create")
    payload = {
        "semantic_model": semantic_model_a.pk,
        "name": "Bad JSON Drill",
        "code": "bad_json_drill",
        "hierarchy_type": "time",
        "levels_json_raw": "{broken-json",
        "is_active": True,
    }
    response = client_a.post(url, payload)
    assert response.status_code == 200
    assert "levels_json_raw" in response.context["form"].errors


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_edit_get_renders_200_and_context_keys(client_a, drill_hierarchy_a):
    """Verify GET on edit renders 200 with instance context and is_edit=True."""
    url = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk})
    response = client_a.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is True
    assert response.context["hierarchy"] == drill_hierarchy_a
    assert response.context["drill_hierarchy"] == drill_hierarchy_a
    assert response.context["object"] == drill_hierarchy_a


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_edit_post_success_redirect_and_audit(client_a, tenant_a, drill_hierarchy_a):
    """Verify successful POST updates hierarchy, logs audit, and redirects to detail."""
    url = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_a.pk})
    new_levels = [
        {"level": 1, "name": "Company", "column": "company_name"},
        {"level": 2, "name": "Department", "column": "dept_name"},
    ]
    payload = {
        "semantic_model": drill_hierarchy_a.semantic_model.pk,
        "name": "Updated Hierarchy Name",
        "code": drill_hierarchy_a.code,
        "hierarchy_type": "organizational",
        "levels_json_raw": json.dumps(new_levels),
        "primary_drill_path": False,
        "is_active": True,
    }
    response = client_a.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:drill_hierarchy_detail", kwargs={"pk": drill_hierarchy_a.pk})

    drill_hierarchy_a.refresh_from_db()
    assert drill_hierarchy_a.name == "Updated Hierarchy Name"
    assert drill_hierarchy_a.hierarchy_type == "organizational"
    assert drill_hierarchy_a.levels_json == new_levels
    assert AuditLog.objects.filter(tenant=tenant_a, action="update").exists()


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_edit_cross_tenant_idor_404(client_a, drill_hierarchy_b):
    """Verify cross-tenant edit returns 404."""
    url = reverse("bi:drill_hierarchy_edit", kwargs={"pk": drill_hierarchy_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, {"name": "Hacked"}).status_code == 404


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_delete_get_method_not_allowed_405(client_a, drill_hierarchy_a):
    """Verify GET on delete returns 405."""
    url = reverse("bi:drill_hierarchy_delete", kwargs={"pk": drill_hierarchy_a.pk})
    assert client_a.get(url).status_code == 405


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_delete_post_success_redirect_and_audit(client_a, tenant_a, semantic_model_a):
    """Verify POST delete removes hierarchy, logs audit, and redirects to list."""
    hier = _semanticlayer_create_hierarchy(tenant_a, semantic_model_a, name="To Del Hier", code="to_del_hier")
    url = reverse("bi:drill_hierarchy_delete", kwargs={"pk": hier.pk})

    response = client_a.post(url)
    assert response.status_code == 302
    assert response.url == reverse("bi:drill_hierarchy_list")

    assert not DrillHierarchy.objects.filter(pk=hier.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()


@pytest.mark.django_db
def test_semanticlayer_drill_hierarchy_delete_cross_tenant_idor_404(client_a, drill_hierarchy_b):
    """Verify cross-tenant delete returns 404."""
    url = reverse("bi:drill_hierarchy_delete", kwargs={"pk": drill_hierarchy_b.pk})
    response = client_a.post(url)
    assert response.status_code == 404
    assert DrillHierarchy.objects.filter(pk=drill_hierarchy_b.pk).exists()
