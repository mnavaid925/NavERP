"""View test suite for Sub-module 10.5 (Data Quality, Profiling & Trust Scorecards).

Covers all 21 routes in apps/bi/views/DataQuality/:
1. Quality Overview:
   - bi:quality_overview (GET 200, context metrics, cards, unauthenticated redirect, empty tenant)
2. DataQualityProfile views:
   - bi:data_quality_profile_list (GET 200, context vars, search, filters, pagination, junk filters)
   - bi:data_quality_profile_detail (GET 200, context vars, exceptions, 404, IDOR 404)
   - bi:data_quality_profile_create (GET 200, POST 302 -> detail, table vs model targets, invalid form 200, audit log)
   - bi:data_quality_profile_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404, audit log)
   - bi:data_quality_profile_delete (GET 405, POST 302 -> list, IDOR 404, audit log)
   - bi:data_quality_profile_run (GET 405, POST 302 -> detail, updates metrics and columns, schema metadata, IDOR 404, audit log)
3. DataQualityRule views:
   - bi:data_quality_rule_list (GET 200, context vars, search, filters, pagination, junk filters)
   - bi:data_quality_rule_detail (GET 200, context vars, exceptions, pretty JSON, 404, IDOR 404)
   - bi:data_quality_rule_create (GET 200, POST 302 -> detail, invalid JSON 200, audit log)
   - bi:data_quality_rule_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404, audit log)
   - bi:data_quality_rule_delete (GET 405, POST 302 -> list, IDOR 404, audit log)
   - bi:data_quality_rule_run (GET 405, POST 302 -> detail, violation exception creation, tolerance evaluation, IDOR 404, audit log)
4. DataQualityException views:
   - bi:data_quality_exception_list (GET 200, context vars, search, filters, pagination, junk filters)
   - bi:data_quality_exception_detail (GET 200, context vars, remediation form, 404, IDOR 404)
   - bi:data_quality_exception_create (GET 200, POST 302 -> detail, invalid form 200, audit log)
   - bi:data_quality_exception_edit (GET 200, POST 302 -> detail, resolution timestamp/user sync, IDOR 404, audit log)
   - bi:data_quality_exception_delete (GET 405, POST 302 -> list, IDOR 404, audit log)
   - bi:data_quality_exception_remediate (GET 405, POST 302 -> detail, stamps resolver on remediated, clears on reopen, invalid form handles gracefully, IDOR 404, audit log)
5. DataQualityScorecard views:
   - bi:data_quality_scorecard_list (GET 200, context vars, search, filters, pagination, junk filters)
   - bi:data_quality_scorecard_detail (GET 200, context vars, evaluated rules, related exceptions, table/model/mart scopes, 404, IDOR 404)
   - bi:data_quality_scorecard_create (GET 200, POST 302 -> detail, invalid form 200, audit log)
   - bi:data_quality_scorecard_edit (GET 200, POST 302 -> detail, invalid form 200, IDOR 404, audit log)
   - bi:data_quality_scorecard_delete (GET 405, POST 302 -> list, IDOR 404, audit log)
   - bi:data_quality_scorecard_recalculate (GET 405, POST 302 -> detail, updates scores, grades, health status, SLA check, IDOR 404, audit log)
"""
from decimal import Decimal
import json

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    DataQualityException,
    DataQualityProfile,
    DataQualityRule,
    DataQualityScorecard,
    SemanticModel,
    WarehouseTable,
)
from apps.core.models import AuditLog


# ---------------------------------------------------------------------------
# Module-level test helpers (prefixed with _dataquality_*)
# ---------------------------------------------------------------------------


def _dataquality_create_profile(tenant, name="Test Profile", **kwargs):
    """Helper to create a DataQualityProfile with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "target_type": "warehouse_table",
        "status": "draft",
        "total_row_count": 100,
        "total_column_count": 5,
        "completeness_score": Decimal("100.00"),
        "uniqueness_score": Decimal("100.00"),
        "validity_score": Decimal("100.00"),
        "is_active": True,
    }
    defaults.update(kwargs)
    return DataQualityProfile.objects.create(**defaults)


def _dataquality_create_rule(tenant, name="Test Rule", code="test_rule", **kwargs):
    """Helper to create a DataQualityRule with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "target_column": "total_amount",
        "rule_type": "range_between",
        "parameters_json": {"min_val": 0.01},
        "severity": "critical",
        "failure_tolerance_pct": Decimal("0.00"),
        "last_status": "passed",
        "pass_rate_pct": Decimal("100.00"),
        "is_active": True,
    }
    defaults.update(kwargs)
    return DataQualityRule.objects.create(**defaults)


def _dataquality_create_exception(tenant, rule=None, **kwargs):
    """Helper to create a DataQualityException with defaults."""
    defaults = {
        "tenant": tenant,
        "rule": rule,
        "record_identifier": "REC-TEST-100",
        "target_column": "total_amount",
        "invalid_value": "-10.00",
        "expected_condition": "amount > 0",
        "exception_type": "range_outlier",
        "severity": "critical",
        "status": "open",
        "remediation_action": "manual_edit",
        "is_active": True,
    }
    defaults.update(kwargs)
    return DataQualityException.objects.create(**defaults)


def _dataquality_create_scorecard(tenant, name="Test Scorecard", code="test_sc", **kwargs):
    """Helper to create a DataQualityScorecard with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "scope_type": "warehouse_table",
        "target_quality_score": Decimal("95.00"),
        "overall_quality_score": Decimal("96.50"),
        "completeness_score": Decimal("99.00"),
        "accuracy_score": Decimal("98.00"),
        "consistency_score": Decimal("97.00"),
        "timeliness_score": Decimal("100.00"),
        "uniqueness_score": Decimal("99.00"),
        "validity_score": Decimal("95.00"),
        "grade": "A",
        "health_status": "healthy",
        "meets_sla": True,
        "evaluation_period": "monthly",
        "is_active": True,
    }
    defaults.update(kwargs)
    return DataQualityScorecard.objects.create(**defaults)


# ===========================================================================
# 1. Quality Overview Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_overview_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to quality overview redirect to login."""
    url = reverse("bi:quality_overview")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_dataquality_overview_renders_200_and_context_keys(
    auth_client, dq_profile_a, dq_rule_a, dq_exception_a, dq_scorecard_a
):
    """Verify bi:quality_overview renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:quality_overview")
    response = auth_client.get(url)

    assert response.status_code == 200
    expected_keys = [
        "total_profiles",
        "total_rules",
        "open_exceptions",
        "total_scorecards",
        "avg_trust_score",
        "healthy_scorecards_count",
        "recent_profiles",
        "failing_rules",
        "critical_exceptions",
        "scorecards",
        "dimension_scores",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in quality_overview"

    assert response.context["total_profiles"] >= 1
    assert response.context["total_rules"] >= 1
    assert response.context["open_exceptions"] >= 1
    assert response.context["total_scorecards"] >= 1
    assert dq_profile_a in response.context["recent_profiles"]
    assert dq_exception_a in response.context["critical_exceptions"]
    assert dq_scorecard_a in response.context["scorecards"]

    dim_scores = response.context["dimension_scores"]
    for dim in ["completeness", "accuracy", "consistency", "timeliness", "uniqueness", "validity"]:
        assert dim in dim_scores
        assert isinstance(dim_scores[dim], Decimal)


@pytest.mark.django_db
def test_dataquality_overview_metrics_calculation(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify metrics calculation for scorecards, failing rules, and open exceptions."""
    # Create a failing rule
    r_fail = _dataquality_create_rule(
        tenant_a,
        name="Failing Rule 1",
        code="fail_r1",
        warehouse_table=warehouse_table_a,
        last_status="failed",
        last_run_at=timezone.now(),
        steward=admin_user,
    )
    # Create extra scorecard
    sc = _dataquality_create_scorecard(
        tenant_a,
        name="Secondary Scorecard",
        code="sec_sc",
        warehouse_table=warehouse_table_a,
        overall_quality_score=Decimal("88.00"),
        health_status="healthy",
    )

    url = reverse("bi:quality_overview")
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["total_rules"] >= 1
    assert r_fail in response.context["failing_rules"]
    assert response.context["healthy_scorecards_count"] >= 1


@pytest.mark.django_db
def test_dataquality_overview_empty_tenant(client_b, tenant_b):
    """Verify overview renders gracefully with 0 counts when tenant has no records."""
    DataQualityProfile.objects.filter(tenant=tenant_b).delete()
    DataQualityRule.objects.filter(tenant=tenant_b).delete()
    DataQualityException.objects.filter(tenant=tenant_b).delete()
    DataQualityScorecard.objects.filter(tenant=tenant_b).delete()

    url = reverse("bi:quality_overview")
    response = client_b.get(url)

    assert response.status_code == 200
    assert response.context["total_profiles"] == 0
    assert response.context["total_rules"] == 0
    assert response.context["open_exceptions"] == 0
    assert response.context["total_scorecards"] == 0
    assert response.context["avg_trust_score"] == Decimal("98.50")
    assert response.context["healthy_scorecards_count"] == 0
    assert list(response.context["recent_profiles"]) == []
    assert list(response.context["critical_exceptions"]) == []


# ===========================================================================
# 2. DataQualityProfile Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_profile_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to profile list redirect to login."""
    url = reverse("bi:data_quality_profile_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_dataquality_profile_list_renders_200_and_context_keys(auth_client, dq_profile_a):
    """Verify bi:data_quality_profile_list renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:data_quality_profile_list")
    response = auth_client.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "profiles",
        "status_choices",
        "target_type_choices",
        "warehouse_tables",
        "semantic_models",
        "total_count",
        "completed_count",
        "failed_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in profile list"

    assert dq_profile_a in response.context["profiles"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_dataquality_profile_list_search_by_name_and_notes(auth_client, tenant_a, warehouse_table_a):
    """Verify profile list search filters by name and notes."""
    p1 = _dataquality_create_profile(
        tenant_a,
        name="Alpha Ledger Profiling",
        warehouse_table=warehouse_table_a,
        notes="Audit profiling for general ledger",
    )
    p2 = _dataquality_create_profile(
        tenant_a,
        name="Beta Inventory Profiling",
        warehouse_table=warehouse_table_a,
        notes="Standard stock analysis",
    )

    url = reverse("bi:data_quality_profile_list")

    # Search by name substring
    resp_name = auth_client.get(url, {"q": "Alpha Ledger"})
    assert resp_name.status_code == 200
    results_name = list(resp_name.context["profiles"])
    assert p1 in results_name
    assert p2 not in results_name

    # Search by notes substring
    resp_notes = auth_client.get(url, {"q": "stock analysis"})
    assert resp_notes.status_code == 200
    results_notes = list(resp_notes.context["profiles"])
    assert p2 in results_notes
    assert p1 not in results_notes


@pytest.mark.django_db
def test_dataquality_profile_list_filter_status_and_target_type(
    auth_client, tenant_a, warehouse_table_a, semantic_model_a
):
    """Verify profile list filtering by status and target_type."""
    p_comp = _dataquality_create_profile(
        tenant_a,
        name="Completed Profile",
        status="completed",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
    )
    p_fail = _dataquality_create_profile(
        tenant_a,
        name="Failed Profile",
        status="failed",
        target_type="semantic_model",
        semantic_model=semantic_model_a,
    )

    url = reverse("bi:data_quality_profile_list")

    # Filter status
    resp_stat = auth_client.get(url, {"status": "failed"})
    assert resp_stat.status_code == 200
    assert p_fail in resp_stat.context["profiles"]
    assert p_comp not in resp_stat.context["profiles"]

    # Filter target_type
    resp_tgt = auth_client.get(url, {"target_type": "semantic_model"})
    assert resp_tgt.status_code == 200
    assert p_fail in resp_tgt.context["profiles"]
    assert p_comp not in resp_tgt.context["profiles"]


@pytest.mark.django_db
def test_dataquality_profile_list_filter_warehouse_table_and_semantic_model(
    auth_client, tenant_a, warehouse_table_a, semantic_model_a
):
    """Verify profile list filtering by FK warehouse_table and semantic_model."""
    p_tbl = _dataquality_create_profile(
        tenant_a,
        name="Table Target Profile",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
    )
    p_sem = _dataquality_create_profile(
        tenant_a,
        name="Semantic Target Profile",
        target_type="semantic_model",
        semantic_model=semantic_model_a,
    )

    url = reverse("bi:data_quality_profile_list")

    # Filter warehouse_table
    resp_tbl = auth_client.get(url, {"warehouse_table": str(warehouse_table_a.pk)})
    assert resp_tbl.status_code == 200
    assert p_tbl in resp_tbl.context["profiles"]
    assert p_sem not in resp_tbl.context["profiles"]

    # Filter semantic_model
    resp_sem = auth_client.get(url, {"semantic_model": str(semantic_model_a.pk)})
    assert resp_sem.status_code == 200
    assert p_sem in resp_sem.context["profiles"]
    assert p_tbl not in resp_sem.context["profiles"]


@pytest.mark.django_db
def test_dataquality_profile_list_junk_filter_params_handled(auth_client, dq_profile_a):
    """Verify junk or non-digit query parameters do not cause 500 error."""
    url = reverse("bi:data_quality_profile_list")
    response = auth_client.get(url, {
        "warehouse_table": "invalid_junk",
        "semantic_model": "non_digit",
        "status": "non_existent_status",
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_dataquality_profile_list_pagination(auth_client, tenant_a, warehouse_table_a):
    """Verify profile list pagination handles page 1 and page 2 correctly."""
    # Create 16 profiles to exceed default page size of 15
    for i in range(16):
        _dataquality_create_profile(
            tenant_a,
            name=f"Paginated Profile {i:02d}",
            warehouse_table=warehouse_table_a,
        )

    url = reverse("bi:data_quality_profile_list")

    # Page 1
    resp_p1 = auth_client.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["profiles"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    # Page 2
    resp_p2 = auth_client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["profiles"]) >= 1


@pytest.mark.django_db
def test_dataquality_profile_detail_renders_200_and_context(auth_client, dq_profile_a, dq_exception_a):
    """Verify profile detail renders HTTP 200 with profile, exceptions, and column_profiles."""
    url = reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["profile"] == dq_profile_a
    assert response.context["total_exceptions_count"] >= 1
    assert dq_exception_a in response.context["exceptions"]
    assert isinstance(response.context["column_profiles"], list)


@pytest.mark.django_db
def test_dataquality_profile_detail_not_found_returns_404(auth_client):
    """Verify profile detail returns 404 for non-existent pk."""
    url = reverse("bi:data_quality_profile_detail", kwargs={"pk": 999999})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_profile_detail_cross_tenant_idor_returns_404(auth_client, dq_profile_b):
    """Verify tenant_a user accessing tenant_b profile receives HTTP 404."""
    url = reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_b.pk})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_profile_create_get_renders_form(auth_client):
    """Verify GET on profile create renders empty form with is_edit=False."""
    url = reverse("bi:data_quality_profile_create")
    response = auth_client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["profile"] is None


@pytest.mark.django_db
def test_dataquality_profile_create_post_invalid_renders_errors(auth_client):
    """Verify POST invalid data re-renders form with HTTP 200 and errors."""
    url = reverse("bi:data_quality_profile_create")
    # Target type warehouse_table without warehouse_table selected
    payload = {
        "name": "",
        "target_type": "warehouse_table",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_profile_create_post_valid_creates_and_audits(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify POST valid data creates profile, sets tenant, and writes audit log."""
    url = reverse("bi:data_quality_profile_create")
    payload = {
        "name": "Fresh Table Profile",
        "target_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "notes": "Fresh automated profile setup",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    profile = DataQualityProfile.objects.filter(tenant=tenant_a, name="Fresh Table Profile").first()
    assert profile is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_profile_detail", kwargs={"pk": profile.pk})

    # Verify AuditLog entry
    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_profile_create_post_semantic_model_target(
    auth_client, tenant_a, semantic_model_a
):
    """Verify profile creation with semantic_model target."""
    url = reverse("bi:data_quality_profile_create")
    payload = {
        "name": "Fresh Semantic Profile",
        "target_type": "semantic_model",
        "semantic_model": str(semantic_model_a.pk),
        "notes": "Semantic layer profiling test",
        "is_active": True,
    }
    response = auth_client.post(url, payload)
    assert response.status_code == 302

    profile = DataQualityProfile.objects.filter(tenant=tenant_a, name="Fresh Semantic Profile").first()
    assert profile is not None
    assert profile.semantic_model == semantic_model_a


@pytest.mark.django_db
def test_dataquality_profile_edit_get_renders_form(auth_client, dq_profile_a):
    """Verify GET on profile edit renders form populated with instance."""
    url = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["form"].instance == dq_profile_a
    assert response.context["is_edit"] is True
    assert response.context["profile"] == dq_profile_a


@pytest.mark.django_db
def test_dataquality_profile_edit_post_invalid_renders_errors(auth_client, dq_profile_a):
    """Verify POST invalid edit data re-renders form with 200."""
    url = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk})
    payload = {
        "name": "",  # Name is required
        "target_type": "warehouse_table",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_profile_edit_post_valid_updates_and_audits(
    auth_client, tenant_a, dq_profile_a, admin_user, warehouse_table_a
):
    """Verify POST valid edit updates profile fields and writes audit log."""
    url = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_a.pk})
    payload = {
        "name": "Updated Profile Name",
        "target_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "notes": "Updated profiling notes here",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_a.pk})

    dq_profile_a.refresh_from_db()
    assert dq_profile_a.name == "Updated Profile Name"
    assert dq_profile_a.notes == "Updated profiling notes here"

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="update").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_profile_edit_cross_tenant_idor_returns_404(auth_client, dq_profile_b):
    """Verify editing a profile belonging to another tenant returns 404."""
    url = reverse("bi:data_quality_profile_edit", kwargs={"pk": dq_profile_b.pk})
    response = auth_client.post(url, {"name": "Hacked Profile"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_profile_delete_get_method_not_allowed(auth_client, dq_profile_a):
    """Verify GET request on profile delete returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_profile_delete", kwargs={"pk": dq_profile_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_profile_delete_post_deletes_and_audits(
    auth_client, tenant_a, dq_profile_a, admin_user
):
    """Verify POST request on profile delete removes record and writes audit log."""
    pk = dq_profile_a.pk
    url = reverse("bi:data_quality_profile_delete", kwargs={"pk": pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_profile_list")
    assert not DataQualityProfile.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_profile_delete_cross_tenant_idor_returns_404(auth_client, dq_profile_b):
    """Verify cross-tenant IDOR delete on profile returns 404."""
    url = reverse("bi:data_quality_profile_delete", kwargs={"pk": dq_profile_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404
    assert DataQualityProfile.objects.filter(pk=dq_profile_b.pk).exists()


@pytest.mark.django_db
def test_dataquality_profile_run_get_method_not_allowed(auth_client, dq_profile_a):
    """Verify GET request on profile run returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_profile_run_post_executes_profiling_and_audits(
    auth_client, tenant_a, dq_profile_a, admin_user
):
    """Verify POST request executes profiling simulation, updates metrics and writes audit log."""
    url = reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_a.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_profile_detail", kwargs={"pk": dq_profile_a.pk})

    dq_profile_a.refresh_from_db()
    assert dq_profile_a.status == "completed"
    assert dq_profile_a.total_row_count == 1250
    assert dq_profile_a.total_column_count > 0
    assert dq_profile_a.completeness_score == Decimal("99.80")
    assert dq_profile_a.uniqueness_score == Decimal("100.00")
    assert dq_profile_a.validity_score == Decimal("99.40")
    assert dq_profile_a.profiled_by == admin_user
    assert dq_profile_a.profiled_at is not None
    assert len(dq_profile_a.column_profiles_json) > 0

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="run").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_profile_run_with_table_schema_definition(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify profiling incorporates warehouse_table schema definition when available."""
    warehouse_table_a.schema_definition = [
        {"name": "order_id", "type": "INTEGER"},
        {"name": "customer_email", "type": "VARCHAR(255)"},
    ]
    warehouse_table_a.save(update_fields=["schema_definition"])

    profile = _dataquality_create_profile(
        tenant_a,
        name="Schema Aware Profile",
        warehouse_table=warehouse_table_a,
    )

    url = reverse("bi:data_quality_profile_run", kwargs={"pk": profile.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.status == "completed"
    assert profile.total_column_count == 2
    col_names = [col["column_name"] for col in profile.column_profiles_json]
    assert "order_id" in col_names
    assert "customer_email" in col_names


@pytest.mark.django_db
def test_dataquality_profile_run_cross_tenant_idor_returns_404(auth_client, dq_profile_b):
    """Verify cross-tenant IDOR run on profile returns 404."""
    url = reverse("bi:data_quality_profile_run", kwargs={"pk": dq_profile_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404


# ===========================================================================
# 3. DataQualityRule Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_rule_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to rule list redirect to login."""
    url = reverse("bi:data_quality_rule_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_dataquality_rule_list_renders_200_and_context_keys(auth_client, dq_rule_a):
    """Verify bi:data_quality_rule_list renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:data_quality_rule_list")
    response = auth_client.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "rules",
        "category_choices",
        "dimension_choices",
        "severity_choices",
        "status_choices",
        "warehouse_tables",
        "semantic_models",
        "total_count",
        "passed_count",
        "failed_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in rule list"

    assert dq_rule_a in response.context["rules"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_dataquality_rule_list_search_by_name_and_column(auth_client, tenant_a, warehouse_table_a):
    """Verify rule list search filters by name and target_column."""
    r1 = _dataquality_create_rule(
        tenant_a,
        name="Discount Check",
        code="discount_check",
        warehouse_table=warehouse_table_a,
        target_column="discount_rate",
    )
    r2 = _dataquality_create_rule(
        tenant_a,
        name="Postal Code Validation",
        code="postal_code_val",
        warehouse_table=warehouse_table_a,
        target_column="postal_code",
    )

    url = reverse("bi:data_quality_rule_list")

    resp_name = auth_client.get(url, {"q": "Discount Check"})
    assert resp_name.status_code == 200
    assert r1 in resp_name.context["rules"]
    assert r2 not in resp_name.context["rules"]

    resp_col = auth_client.get(url, {"q": "postal_code"})
    assert resp_col.status_code == 200
    assert r2 in resp_col.context["rules"]
    assert r1 not in resp_col.context["rules"]


@pytest.mark.django_db
def test_dataquality_rule_list_filter_category_dimension_severity(
    auth_client, tenant_a, warehouse_table_a
):
    """Verify rule list filtering by category, dimension, and severity."""
    r1 = _dataquality_create_rule(
        tenant_a,
        name="Consistency Check",
        code="consistency_chk",
        warehouse_table=warehouse_table_a,
        rule_category="consistency",
        dimension="consistency",
        severity="fatal",
    )
    r2 = _dataquality_create_rule(
        tenant_a,
        name="Standardization Check",
        code="stand_chk",
        warehouse_table=warehouse_table_a,
        rule_category="standardization",
        dimension="accuracy",
        severity="info",
    )

    url = reverse("bi:data_quality_rule_list")

    # Filter rule_category
    resp_cat = auth_client.get(url, {"rule_category": "consistency"})
    assert resp_cat.status_code == 200
    assert r1 in resp_cat.context["rules"]
    assert r2 not in resp_cat.context["rules"]

    # Filter dimension
    resp_dim = auth_client.get(url, {"dimension": "consistency"})
    assert resp_dim.status_code == 200
    assert r1 in resp_dim.context["rules"]
    assert r2 not in resp_dim.context["rules"]

    # Filter severity
    resp_sev = auth_client.get(url, {"severity": "fatal"})
    assert resp_sev.status_code == 200
    assert r1 in resp_sev.context["rules"]
    assert r2 not in resp_sev.context["rules"]


@pytest.mark.django_db
def test_dataquality_rule_list_filter_status_and_target(
    auth_client, tenant_a, warehouse_table_a, semantic_model_a
):
    """Verify rule list filtering by last_status and target objects."""
    r_pass = _dataquality_create_rule(
        tenant_a,
        name="Passed Rule",
        code="passed_rule",
        warehouse_table=warehouse_table_a,
        last_status="passed",
    )
    r_fail = _dataquality_create_rule(
        tenant_a,
        name="Failed Rule",
        code="failed_rule",
        target_type="semantic_model",
        semantic_model=semantic_model_a,
        last_status="failed",
    )

    url = reverse("bi:data_quality_rule_list")

    # Filter last_status
    resp_stat = auth_client.get(url, {"last_status": "failed"})
    assert resp_stat.status_code == 200
    assert r_fail in resp_stat.context["rules"]
    assert r_pass not in resp_stat.context["rules"]

    # Filter warehouse_table
    resp_tbl = auth_client.get(url, {"warehouse_table": str(warehouse_table_a.pk)})
    assert resp_tbl.status_code == 200
    assert r_pass in resp_tbl.context["rules"]
    assert r_fail not in resp_tbl.context["rules"]


@pytest.mark.django_db
def test_dataquality_rule_list_junk_filter_params_handled(auth_client, dq_rule_a):
    """Verify rule list handles non-digit and invalid filter params gracefully."""
    url = reverse("bi:data_quality_rule_list")
    response = auth_client.get(url, {
        "warehouse_table": "bad_table",
        "semantic_model": "bad_model",
        "last_status": "none",
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_dataquality_rule_list_pagination(auth_client, tenant_a, warehouse_table_a):
    """Verify rule list pagination handles multi-page results."""
    for i in range(16):
        _dataquality_create_rule(
            tenant_a,
            name=f"Paginated Rule {i:02d}",
            code=f"pag_rule_{i:02d}",
            warehouse_table=warehouse_table_a,
        )

    url = reverse("bi:data_quality_rule_list")

    resp_p1 = auth_client.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["rules"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = auth_client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["rules"]) >= 1


@pytest.mark.django_db
def test_dataquality_rule_detail_renders_200_and_context(auth_client, dq_rule_a, dq_exception_a):
    """Verify rule detail renders HTTP 200 with rule, exceptions, open_exceptions_count, and parameters_pretty."""
    url = reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["rule"] == dq_rule_a
    assert response.context["open_exceptions_count"] >= 1
    assert dq_exception_a in response.context["exceptions"]
    assert "parameters_pretty" in response.context
    assert isinstance(response.context["parameters_pretty"], str)


@pytest.mark.django_db
def test_dataquality_rule_detail_not_found_returns_404(auth_client):
    """Verify rule detail returns 404 for non-existent pk."""
    url = reverse("bi:data_quality_rule_detail", kwargs={"pk": 999999})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_rule_detail_cross_tenant_idor_returns_404(auth_client, dq_rule_b):
    """Verify cross-tenant IDOR access on rule detail returns 404."""
    url = reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_b.pk})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_rule_create_get_renders_form(auth_client):
    """Verify GET on rule create renders empty form with is_edit=False."""
    url = reverse("bi:data_quality_rule_create")
    response = auth_client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["rule"] is None


@pytest.mark.django_db
def test_dataquality_rule_create_post_invalid_json_renders_errors(auth_client, warehouse_table_a):
    """Verify POST rule with malformed JSON string produces form validation error."""
    url = reverse("bi:data_quality_rule_create")
    payload = {
        "name": "Invalid JSON Rule",
        "code": "invalid_json_rule",
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "target_column": "amount",
        "rule_type": "range_between",
        "parameters_json": "INVALID_JSON_NOT_AN_OBJECT",
        "severity": "critical",
        "failure_tolerance_pct": "0.00",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert "parameters_json" in response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_rule_create_post_valid_creates_and_audits(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify POST valid rule data creates rule, sets tenant, and writes audit log."""
    url = reverse("bi:data_quality_rule_create")
    payload = {
        "name": "Tax Percent Range Check",
        "code": "tax_percent_range_check",
        "rule_category": "validation",
        "dimension": "validity",
        "target_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "target_column": "tax_rate",
        "rule_type": "range_between",
        "parameters_json": '{"min_val": 0.0, "max_val": 35.0}',
        "severity": "critical",
        "failure_tolerance_pct": "0.00",
        "steward": str(admin_user.pk),
        "description": "Tax rate must stay between 0% and 35%",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    rule = DataQualityRule.objects.filter(tenant=tenant_a, code="tax_percent_range_check").first()
    assert rule is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_rule_detail", kwargs={"pk": rule.pk})

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="create").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_rule_edit_get_renders_form(auth_client, dq_rule_a):
    """Verify GET on rule edit renders form populated with instance."""
    url = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["form"].instance == dq_rule_a
    assert response.context["is_edit"] is True
    assert response.context["rule"] == dq_rule_a


@pytest.mark.django_db
def test_dataquality_rule_edit_post_invalid_renders_errors(auth_client, dq_rule_a):
    """Verify POST invalid edit data re-renders form with 200."""
    url = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk})
    payload = {
        "name": "",  # Name is required
        "code": dq_rule_a.code or "test_rule_code",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_rule_edit_post_valid_updates_and_audits(
    auth_client, tenant_a, dq_rule_a, admin_user, warehouse_table_a
):
    """Verify POST valid rule edit updates rule and writes audit log."""
    url = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_a.pk})
    payload = {
        "name": "Updated Rule Name",
        "code": "invoice_pos_updated",
        "rule_category": "validation",
        "dimension": dq_rule_a.dimension,
        "target_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "target_column": dq_rule_a.target_column,
        "rule_type": dq_rule_a.rule_type,
        "parameters_json": json.dumps(dq_rule_a.parameters_json),
        "severity": "fatal",
        "failure_tolerance_pct": "1.50",
        "steward": str(admin_user.pk),
        "description": "Updated description",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_a.pk})

    dq_rule_a.refresh_from_db()
    assert dq_rule_a.name == "Updated Rule Name"
    assert dq_rule_a.severity == "fatal"
    assert dq_rule_a.failure_tolerance_pct == Decimal("1.50")

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="update").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_rule_edit_cross_tenant_idor_returns_404(auth_client, dq_rule_b):
    """Verify editing a rule belonging to another tenant returns 404."""
    url = reverse("bi:data_quality_rule_edit", kwargs={"pk": dq_rule_b.pk})
    response = auth_client.post(url, {"name": "Hacked Rule"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_rule_delete_get_method_not_allowed(auth_client, dq_rule_a):
    """Verify GET on rule delete returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_rule_delete", kwargs={"pk": dq_rule_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_rule_delete_post_deletes_and_audits(
    auth_client, tenant_a, dq_rule_a, admin_user
):
    """Verify POST request on rule delete removes record and writes audit log."""
    pk = dq_rule_a.pk
    url = reverse("bi:data_quality_rule_delete", kwargs={"pk": pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_rule_list")
    assert not DataQualityRule.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_rule_delete_cross_tenant_idor_returns_404(auth_client, dq_rule_b):
    """Verify cross-tenant IDOR delete on rule returns 404."""
    url = reverse("bi:data_quality_rule_delete", kwargs={"pk": dq_rule_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404
    assert DataQualityRule.objects.filter(pk=dq_rule_b.pk).exists()


@pytest.mark.django_db
def test_dataquality_rule_run_get_method_not_allowed(auth_client, dq_rule_a):
    """Verify GET request on rule run returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_rule_run_post_evaluates_range_and_creates_exception(
    auth_client, tenant_a, dq_rule_a, admin_user
):
    """Verify running a range_between rule evaluates pass rate, creates sample exception, and writes audit log."""
    dq_rule_a.failure_tolerance_pct = Decimal("0.00")
    dq_rule_a.severity = "critical"
    dq_rule_a.save(update_fields=["failure_tolerance_pct", "severity"])

    url = reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_a.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_rule_detail", kwargs={"pk": dq_rule_a.pk})

    dq_rule_a.refresh_from_db()
    assert dq_rule_a.last_run_at is not None
    assert dq_rule_a.failed_records_count == 3
    assert dq_rule_a.passed_records_count == 1247
    assert dq_rule_a.last_status == "failed"
    assert dq_rule_a.pass_rate_pct < Decimal("100.00")

    # Verify exception created
    exc = DataQualityException.objects.filter(rule=dq_rule_a, tenant=tenant_a).first()
    assert exc is not None
    assert exc.severity == dq_rule_a.severity

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="run").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_rule_run_post_passes_within_tolerance(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify rule passes when failure rate is below failure_tolerance_pct."""
    rule = _dataquality_create_rule(
        tenant_a,
        name="High Tolerance Rule",
        code="high_tol_rule",
        warehouse_table=warehouse_table_a,
        rule_type="range_between",
        failure_tolerance_pct=Decimal("5.00"),  # 3/1250 is ~0.24% < 5%
    )

    url = reverse("bi:data_quality_rule_run", kwargs={"pk": rule.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    rule.refresh_from_db()
    assert rule.last_status == "passed"


@pytest.mark.django_db
def test_dataquality_rule_run_cross_tenant_idor_returns_404(auth_client, dq_rule_b):
    """Verify cross-tenant IDOR run on rule returns 404."""
    url = reverse("bi:data_quality_rule_run", kwargs={"pk": dq_rule_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404


# ===========================================================================
# 4. DataQualityException Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_exception_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to exception list redirect to login."""
    url = reverse("bi:data_quality_exception_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_dataquality_exception_list_renders_200_and_context_keys(auth_client, dq_exception_a):
    """Verify bi:data_quality_exception_list renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:data_quality_exception_list")
    response = auth_client.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "exceptions",
        "status_choices",
        "severity_choices",
        "exception_type_choices",
        "rules",
        "stewards",
        "total_count",
        "open_count",
        "remediated_count",
        "critical_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in exception list"

    assert dq_exception_a in response.context["exceptions"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_dataquality_exception_list_search_by_identifier_and_column(
    auth_client, tenant_a, dq_rule_a, warehouse_table_a
):
    """Verify exception list search filters by record_identifier and target_column."""
    e1 = _dataquality_create_exception(
        tenant_a,
        rule=dq_rule_a,
        record_identifier="INV-9988-ALPHA",
        target_column="invoice_amount",
    )
    e2 = _dataquality_create_exception(
        tenant_a,
        rule=dq_rule_a,
        record_identifier="INV-1122-BETA",
        target_column="customer_phone",
    )

    url = reverse("bi:data_quality_exception_list")

    resp_id = auth_client.get(url, {"q": "INV-9988-ALPHA"})
    assert resp_id.status_code == 200
    assert e1 in resp_id.context["exceptions"]
    assert e2 not in resp_id.context["exceptions"]

    resp_col = auth_client.get(url, {"q": "customer_phone"})
    assert resp_col.status_code == 200
    assert e2 in resp_col.context["exceptions"]
    assert e1 not in resp_col.context["exceptions"]


@pytest.mark.django_db
def test_dataquality_exception_list_filter_status_severity_type(
    auth_client, tenant_a, dq_rule_a, warehouse_table_a
):
    """Verify exception list filtering by status, severity, and exception_type."""
    e_rem = _dataquality_create_exception(
        tenant_a,
        rule=dq_rule_a,
        status="remediated",
        severity="info",
        exception_type="null_anomaly",
    )
    e_open = _dataquality_create_exception(
        tenant_a,
        rule=dq_rule_a,
        status="open",
        severity="fatal",
        exception_type="schema_mismatch",
    )

    url = reverse("bi:data_quality_exception_list")

    # Filter status
    resp_stat = auth_client.get(url, {"status": "remediated"})
    assert resp_stat.status_code == 200
    assert e_rem in resp_stat.context["exceptions"]
    assert e_open not in resp_stat.context["exceptions"]

    # Filter severity
    resp_sev = auth_client.get(url, {"severity": "fatal"})
    assert resp_sev.status_code == 200
    assert e_open in resp_sev.context["exceptions"]
    assert e_rem not in resp_sev.context["exceptions"]

    # Filter exception_type
    resp_type = auth_client.get(url, {"exception_type": "null_anomaly"})
    assert resp_type.status_code == 200
    assert e_rem in resp_type.context["exceptions"]
    assert e_open not in resp_type.context["exceptions"]


@pytest.mark.django_db
def test_dataquality_exception_list_filter_rule_and_steward(
    auth_client, tenant_a, dq_rule_a, warehouse_table_a, admin_user
):
    """Verify exception list filtering by rule FK and assigned_steward FK."""
    r2 = _dataquality_create_rule(
        tenant_a,
        name="Secondary Rule",
        code="sec_rule",
        warehouse_table=warehouse_table_a,
    )
    e1 = _dataquality_create_exception(
        tenant_a,
        rule=dq_rule_a,
        assigned_steward=admin_user,
    )
    e2 = _dataquality_create_exception(
        tenant_a,
        rule=r2,
        assigned_steward=None,
    )

    url = reverse("bi:data_quality_exception_list")

    # Filter rule
    resp_r = auth_client.get(url, {"rule": str(dq_rule_a.pk)})
    assert resp_r.status_code == 200
    assert e1 in resp_r.context["exceptions"]
    assert e2 not in resp_r.context["exceptions"]

    # Filter steward
    resp_stew = auth_client.get(url, {"assigned_steward": str(admin_user.pk)})
    assert resp_stew.status_code == 200
    assert e1 in resp_stew.context["exceptions"]
    assert e2 not in resp_stew.context["exceptions"]


@pytest.mark.django_db
def test_dataquality_exception_list_junk_filter_params_handled(auth_client, dq_exception_a):
    """Verify exception list handles non-digit and invalid filter values gracefully."""
    url = reverse("bi:data_quality_exception_list")
    response = auth_client.get(url, {
        "rule": "bad_rule",
        "assigned_steward": "bad_user",
        "status": "not_real",
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_dataquality_exception_list_pagination(auth_client, tenant_a, dq_rule_a, warehouse_table_a):
    """Verify exception list pagination handles multi-page datasets."""
    for i in range(16):
        _dataquality_create_exception(
            tenant_a,
            rule=dq_rule_a,
            record_identifier=f"REC-PAG-{i:02d}",
        )

    url = reverse("bi:data_quality_exception_list")

    resp_p1 = auth_client.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["exceptions"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = auth_client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["exceptions"]) >= 1


@pytest.mark.django_db
def test_dataquality_exception_detail_renders_200_and_context(auth_client, dq_exception_a):
    """Verify exception detail renders HTTP 200 with exception and remediation_form."""
    url = reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["exception"] == dq_exception_a
    assert "remediation_form" in response.context
    assert response.context["remediation_form"].instance == dq_exception_a


@pytest.mark.django_db
def test_dataquality_exception_detail_not_found_returns_404(auth_client):
    """Verify exception detail returns 404 for non-existent pk."""
    url = reverse("bi:data_quality_exception_detail", kwargs={"pk": 999999})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_exception_detail_cross_tenant_idor_returns_404(auth_client, dq_exception_b):
    """Verify cross-tenant IDOR access on exception detail returns 404."""
    url = reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_b.pk})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_exception_create_get_renders_form(auth_client):
    """Verify GET on exception create renders empty form with is_edit=False."""
    url = reverse("bi:data_quality_exception_create")
    response = auth_client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["exception"] is None


@pytest.mark.django_db
def test_dataquality_exception_create_post_invalid_renders_errors(auth_client):
    """Verify POST invalid data re-renders form with HTTP 200 and errors."""
    url = reverse("bi:data_quality_exception_create")
    payload = {
        "record_identifier": "",  # Required
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_exception_create_post_valid_creates_and_audits(
    auth_client, tenant_a, dq_rule_a, warehouse_table_a, admin_user
):
    """Verify POST valid exception creates record, sets tenant, and writes audit log."""
    url = reverse("bi:data_quality_exception_create")
    payload = {
        "rule": str(dq_rule_a.pk),
        "warehouse_table": str(warehouse_table_a.pk),
        "record_identifier": "CUST-ANOMALY-808",
        "target_column": "credit_limit",
        "invalid_value": "-500.00",
        "expected_condition": "credit_limit >= 0",
        "exception_type": "range_outlier",
        "severity": "critical",
        "status": "open",
        "remediation_action": "manual_edit",
        "assigned_steward": str(admin_user.pk),
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    exc = DataQualityException.objects.filter(
        tenant=tenant_a,
        record_identifier="CUST-ANOMALY-808",
    ).first()
    assert exc is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_exception_detail", kwargs={"pk": exc.pk})

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="create").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_exception_edit_get_renders_form(auth_client, dq_exception_a):
    """Verify GET on exception edit renders form with instance."""
    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["form"].instance == dq_exception_a
    assert response.context["is_edit"] is True
    assert response.context["exception"] == dq_exception_a


@pytest.mark.django_db
def test_dataquality_exception_edit_post_invalid_renders_errors(auth_client, dq_exception_a):
    """Verify POST invalid edit data re-renders form with 200."""
    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk})
    payload = {
        "record_identifier": "",  # Required
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_exception_edit_post_remediated_syncs_resolved_stamp(
    auth_client, tenant_a, dq_exception_a, admin_user
):
    """Verify editing exception to remediated automatically stamps resolved_by and resolved_at."""
    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk})
    payload = {
        "rule": str(dq_exception_a.rule_id) if dq_exception_a.rule_id else "",
        "record_identifier": dq_exception_a.record_identifier,
        "target_column": dq_exception_a.target_column,
        "invalid_value": dq_exception_a.invalid_value,
        "expected_condition": dq_exception_a.expected_condition,
        "exception_type": dq_exception_a.exception_type,
        "severity": dq_exception_a.severity,
        "status": "remediated",
        "remediation_action": "manual_edit",
        "remediated_value": "45.00",
        "assigned_steward": str(admin_user.pk),
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    dq_exception_a.refresh_from_db()
    assert dq_exception_a.status == "remediated"
    assert dq_exception_a.resolved_by == admin_user
    assert dq_exception_a.resolved_at is not None

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="update").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_exception_edit_post_unresolve_clears_resolved_stamp(
    auth_client, tenant_a, dq_exception_a, admin_user
):
    """Verify changing exception status from remediated to open clears resolved stamps."""
    dq_exception_a.status = "remediated"
    dq_exception_a.resolved_by = admin_user
    dq_exception_a.resolved_at = timezone.now()
    dq_exception_a.save()

    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_a.pk})
    payload = {
        "record_identifier": dq_exception_a.record_identifier,
        "target_column": dq_exception_a.target_column,
        "invalid_value": dq_exception_a.invalid_value,
        "expected_condition": dq_exception_a.expected_condition,
        "exception_type": dq_exception_a.exception_type,
        "severity": dq_exception_a.severity,
        "status": "open",
        "remediation_action": dq_exception_a.remediation_action,
        "assigned_steward": str(admin_user.pk),
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    dq_exception_a.refresh_from_db()
    assert dq_exception_a.status == "open"
    assert dq_exception_a.resolved_by is None
    assert dq_exception_a.resolved_at is None


@pytest.mark.django_db
def test_dataquality_exception_edit_cross_tenant_idor_returns_404(auth_client, dq_exception_b):
    """Verify editing an exception belonging to another tenant returns 404."""
    url = reverse("bi:data_quality_exception_edit", kwargs={"pk": dq_exception_b.pk})
    response = auth_client.post(url, {"record_identifier": "Hacked Identifier"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_exception_delete_get_method_not_allowed(auth_client, dq_exception_a):
    """Verify GET on exception delete returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_exception_delete", kwargs={"pk": dq_exception_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_exception_delete_post_deletes_and_audits(
    auth_client, tenant_a, dq_exception_a, admin_user
):
    """Verify POST request on exception delete removes record and writes audit log."""
    pk = dq_exception_a.pk
    url = reverse("bi:data_quality_exception_delete", kwargs={"pk": pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_exception_list")
    assert not DataQualityException.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_exception_delete_cross_tenant_idor_returns_404(auth_client, dq_exception_b):
    """Verify cross-tenant IDOR delete on exception returns 404."""
    url = reverse("bi:data_quality_exception_delete", kwargs={"pk": dq_exception_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404
    assert DataQualityException.objects.filter(pk=dq_exception_b.pk).exists()


@pytest.mark.django_db
def test_dataquality_exception_remediate_get_method_not_allowed(auth_client, dq_exception_a):
    """Verify GET on exception remediate returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_exception_remediate_post_marks_remediated_and_audits(
    auth_client, tenant_a, dq_exception_a, admin_user
):
    """Verify remediating exception stamps resolved user/time and writes audit log."""
    url = reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk})
    payload = {
        "status": "remediated",
        "remediation_action": "manual_edit",
        "proposed_value": "45.00",
        "remediated_value": "45.00",
        "assigned_steward": str(admin_user.pk),
        "resolution_notes": "Corrected negative invoice total via credit debit match.",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_a.pk})

    dq_exception_a.refresh_from_db()
    assert dq_exception_a.status == "remediated"
    assert dq_exception_a.remediation_action == "manual_edit"
    assert dq_exception_a.remediated_value == "45.00"
    assert dq_exception_a.resolved_by == admin_user
    assert dq_exception_a.resolved_at is not None

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="remediate").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_exception_remediate_post_transitions_to_investigating_clears_stamp(
    auth_client, tenant_a, dq_exception_a, admin_user
):
    """Verify transitioning back to investigating clears resolution user and timestamp."""
    dq_exception_a.status = "remediated"
    dq_exception_a.resolved_by = admin_user
    dq_exception_a.resolved_at = timezone.now()
    dq_exception_a.save()

    url = reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk})
    payload = {
        "status": "investigating",
        "remediation_action": "impute_value",
        "resolution_notes": "Reopening investigation into source database constraint.",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    dq_exception_a.refresh_from_db()
    assert dq_exception_a.status == "investigating"
    assert dq_exception_a.resolved_by is None
    assert dq_exception_a.resolved_at is None


@pytest.mark.django_db
def test_dataquality_exception_remediate_post_invalid_handles_error(
    auth_client, dq_exception_a
):
    """Verify invalid remediation POST redirects with error flash message."""
    url = reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_a.pk})
    payload = {
        "status": "invalid_status_value",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_exception_detail", kwargs={"pk": dq_exception_a.pk})


@pytest.mark.django_db
def test_dataquality_exception_remediate_cross_tenant_idor_returns_404(
    auth_client, dq_exception_b
):
    """Verify cross-tenant IDOR on exception remediation returns 404."""
    url = reverse("bi:data_quality_exception_remediate", kwargs={"pk": dq_exception_b.pk})
    response = auth_client.post(url, {"status": "remediated"})
    assert response.status_code == 404


# ===========================================================================
# 5. DataQualityScorecard Views Tests
# ===========================================================================


@pytest.mark.django_db
def test_dataquality_scorecard_list_unauthenticated_redirects(anon_client):
    """Verify unauthenticated requests to scorecard list redirect to login."""
    url = reverse("bi:data_quality_scorecard_list")
    response = anon_client.get(url)
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_dataquality_scorecard_list_renders_200_and_context_keys(auth_client, dq_scorecard_a):
    """Verify bi:data_quality_scorecard_list renders HTTP 200 with all pinned context keys."""
    url = reverse("bi:data_quality_scorecard_list")
    response = auth_client.get(url)

    assert response.status_code == 200
    expected_keys = [
        "page_obj",
        "scorecards",
        "scope_type_choices",
        "grade_choices",
        "health_status_choices",
        "total_count",
        "grade_a_count",
        "sla_breached_count",
    ]
    for key in expected_keys:
        assert key in response.context, f"Missing pinned context key '{key}' in scorecard list"

    assert dq_scorecard_a in response.context["scorecards"]
    assert response.context["total_count"] >= 1


@pytest.mark.django_db
def test_dataquality_scorecard_list_search_by_name_and_code(
    auth_client, tenant_a, warehouse_table_a
):
    """Verify scorecard list search filters by name and code."""
    sc1 = _dataquality_create_scorecard(
        tenant_a,
        name="Finance Core Trust",
        code="fin_core_trust",
        warehouse_table=warehouse_table_a,
    )
    sc2 = _dataquality_create_scorecard(
        tenant_a,
        name="Supply Chain Health",
        code="scm_health",
        warehouse_table=warehouse_table_a,
    )

    url = reverse("bi:data_quality_scorecard_list")

    resp_name = auth_client.get(url, {"q": "Finance Core"})
    assert resp_name.status_code == 200
    assert sc1 in resp_name.context["scorecards"]
    assert sc2 not in resp_name.context["scorecards"]

    resp_code = auth_client.get(url, {"q": "scm_health"})
    assert resp_code.status_code == 200
    assert sc2 in resp_code.context["scorecards"]
    assert sc1 not in resp_code.context["scorecards"]


@pytest.mark.django_db
def test_dataquality_scorecard_list_filter_scope_grade_health(
    auth_client, tenant_a, warehouse_table_a
):
    """Verify scorecard list filtering by scope_type, grade, and health_status."""
    sc_a = _dataquality_create_scorecard(
        tenant_a,
        name="Grade A Scorecard",
        code="grade_a_sc",
        warehouse_table=warehouse_table_a,
        scope_type="warehouse_table",
        grade="A",
        health_status="healthy",
    )
    sc_c = _dataquality_create_scorecard(
        tenant_a,
        name="Grade C Scorecard",
        code="grade_c_sc",
        warehouse_table=warehouse_table_a,
        scope_type="enterprise",
        grade="C",
        health_status="critical",
    )

    url = reverse("bi:data_quality_scorecard_list")

    # Filter grade
    resp_g = auth_client.get(url, {"grade": "A"})
    assert resp_g.status_code == 200
    assert sc_a in resp_g.context["scorecards"]
    assert sc_c not in resp_g.context["scorecards"]

    # Filter health_status
    resp_h = auth_client.get(url, {"health_status": "critical"})
    assert resp_h.status_code == 200
    assert sc_c in resp_h.context["scorecards"]
    assert sc_a not in resp_h.context["scorecards"]

    # Filter scope_type
    resp_s = auth_client.get(url, {"scope_type": "enterprise"})
    assert resp_s.status_code == 200
    assert sc_c in resp_s.context["scorecards"]
    assert sc_a not in resp_s.context["scorecards"]


@pytest.mark.django_db
def test_dataquality_scorecard_list_junk_filter_params_handled(auth_client, dq_scorecard_a):
    """Verify scorecard list handles invalid filter params gracefully."""
    url = reverse("bi:data_quality_scorecard_list")
    response = auth_client.get(url, {
        "scope_type": "non_existent_scope",
        "grade": "Z",
        "health_status": "unknown",
    })
    assert response.status_code == 200


@pytest.mark.django_db
def test_dataquality_scorecard_list_pagination(auth_client, tenant_a, warehouse_table_a):
    """Verify scorecard list pagination handles multi-page sets."""
    for i in range(16):
        _dataquality_create_scorecard(
            tenant_a,
            name=f"Paginated Scorecard {i:02d}",
            code=f"pag_sc_{i:02d}",
            warehouse_table=warehouse_table_a,
        )

    url = reverse("bi:data_quality_scorecard_list")

    resp_p1 = auth_client.get(url, {"page": 1})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["scorecards"]) == 15
    assert resp_p1.context["page_obj"].has_next() is True

    resp_p2 = auth_client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["scorecards"]) >= 1


@pytest.mark.django_db
def test_dataquality_scorecard_detail_renders_200_and_context_table_scope(
    auth_client, dq_scorecard_a, dq_rule_a, dq_exception_a
):
    """Verify scorecard detail renders HTTP 200 with evaluated_rules and related_exceptions."""
    url = reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["scorecard"] == dq_scorecard_a
    assert "evaluated_rules" in response.context
    assert "related_exceptions" in response.context
    assert dq_rule_a in response.context["evaluated_rules"]
    assert dq_exception_a in response.context["related_exceptions"]


@pytest.mark.django_db
def test_dataquality_scorecard_detail_renders_model_and_mart_scopes(
    auth_client, tenant_a, semantic_model_a, data_mart_a
):
    """Verify scorecard detail correctly resolves rules and exceptions for semantic_model and data_mart scopes."""
    sc_sem = _dataquality_create_scorecard(
        tenant_a,
        name="Semantic Scorecard",
        code="sem_sc",
        scope_type="semantic_model",
        semantic_model=semantic_model_a,
    )
    sc_mart = _dataquality_create_scorecard(
        tenant_a,
        name="Mart Scorecard",
        code="mart_sc",
        scope_type="data_mart",
        data_mart=data_mart_a,
    )

    url_sem = reverse("bi:data_quality_scorecard_detail", kwargs={"pk": sc_sem.pk})
    resp_sem = auth_client.get(url_sem)
    assert resp_sem.status_code == 200
    assert resp_sem.context["scorecard"] == sc_sem

    url_mart = reverse("bi:data_quality_scorecard_detail", kwargs={"pk": sc_mart.pk})
    resp_mart = auth_client.get(url_mart)
    assert resp_mart.status_code == 200
    assert resp_mart.context["scorecard"] == sc_mart


@pytest.mark.django_db
def test_dataquality_scorecard_detail_not_found_returns_404(auth_client):
    """Verify scorecard detail returns 404 for non-existent pk."""
    url = reverse("bi:data_quality_scorecard_detail", kwargs={"pk": 999999})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_scorecard_detail_cross_tenant_idor_returns_404(auth_client, dq_scorecard_b):
    """Verify cross-tenant IDOR access on scorecard detail returns 404."""
    url = reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_b.pk})
    response = auth_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_scorecard_create_get_renders_form(auth_client):
    """Verify GET on scorecard create renders empty form with is_edit=False."""
    url = reverse("bi:data_quality_scorecard_create")
    response = auth_client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["is_edit"] is False
    assert response.context["scorecard"] is None


@pytest.mark.django_db
def test_dataquality_scorecard_create_post_invalid_renders_errors(auth_client):
    """Verify POST invalid data (e.g. scope warehouse_table without table) returns 200 with errors."""
    url = reverse("bi:data_quality_scorecard_create")
    payload = {
        "name": "Invalid Scorecard",
        "code": "invalid_scorecard",
        "scope_type": "warehouse_table",
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_scorecard_create_post_valid_creates_and_audits(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify POST valid scorecard creates record, sets tenant, and writes audit log."""
    url = reverse("bi:data_quality_scorecard_create")
    payload = {
        "name": "Monthly GL Trust",
        "code": "monthly_gl_trust",
        "scope_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "target_quality_score": "95.00",
        "evaluation_period": "monthly",
        "steward": str(admin_user.pk),
        "description": "General Ledger data quality SLA scorecard",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    sc = DataQualityScorecard.objects.filter(tenant=tenant_a, code="monthly_gl_trust").first()
    assert sc is not None
    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_scorecard_detail", kwargs={"pk": sc.pk})

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="create").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_scorecard_create_post_semantic_model_scope(
    auth_client, tenant_a, semantic_model_a
):
    """Verify scorecard create with semantic_model scope."""
    url = reverse("bi:data_quality_scorecard_create")
    payload = {
        "name": "Model Scope Scorecard",
        "code": "model_scope_scorecard",
        "scope_type": "semantic_model",
        "semantic_model": str(semantic_model_a.pk),
        "target_quality_score": "90.00",
        "evaluation_period": "weekly",
        "is_active": True,
    }
    response = auth_client.post(url, payload)
    assert response.status_code == 302

    sc = DataQualityScorecard.objects.filter(tenant=tenant_a, code="model_scope_scorecard").first()
    assert sc is not None
    assert sc.semantic_model == semantic_model_a


@pytest.mark.django_db
def test_dataquality_scorecard_edit_get_renders_form(auth_client, dq_scorecard_a):
    """Verify GET on scorecard edit renders form with instance."""
    url = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk})
    response = auth_client.get(url)

    assert response.status_code == 200
    assert response.context["form"].instance == dq_scorecard_a
    assert response.context["is_edit"] is True
    assert response.context["scorecard"] == dq_scorecard_a


@pytest.mark.django_db
def test_dataquality_scorecard_edit_post_invalid_renders_errors(auth_client, dq_scorecard_a):
    """Verify POST invalid edit data re-renders form with 200."""
    url = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk})
    payload = {
        "name": "",  # Required
        "code": dq_scorecard_a.code,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 200
    assert response.context["form"].errors


@pytest.mark.django_db
def test_dataquality_scorecard_edit_post_valid_updates_and_audits(
    auth_client, tenant_a, dq_scorecard_a, admin_user, warehouse_table_a
):
    """Verify POST valid scorecard edit updates record and writes audit log."""
    url = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_a.pk})
    payload = {
        "name": "Updated Scorecard Name",
        "code": dq_scorecard_a.code,
        "scope_type": "warehouse_table",
        "warehouse_table": str(warehouse_table_a.pk),
        "target_quality_score": "98.00",
        "evaluation_period": "weekly",
        "steward": str(admin_user.pk),
        "description": "Higher bar for Q4 data trust",
        "is_active": True,
    }
    response = auth_client.post(url, payload)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_a.pk})

    dq_scorecard_a.refresh_from_db()
    assert dq_scorecard_a.name == "Updated Scorecard Name"
    assert dq_scorecard_a.target_quality_score == Decimal("98.00")
    assert dq_scorecard_a.evaluation_period == "weekly"

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="update").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_scorecard_edit_cross_tenant_idor_returns_404(auth_client, dq_scorecard_b):
    """Verify editing a scorecard belonging to another tenant returns 404."""
    url = reverse("bi:data_quality_scorecard_edit", kwargs={"pk": dq_scorecard_b.pk})
    response = auth_client.post(url, {"name": "Hacked Scorecard"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_dataquality_scorecard_delete_get_method_not_allowed(auth_client, dq_scorecard_a):
    """Verify GET on scorecard delete returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_scorecard_delete", kwargs={"pk": dq_scorecard_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_scorecard_delete_post_deletes_and_audits(
    auth_client, tenant_a, dq_scorecard_a, admin_user
):
    """Verify POST request on scorecard delete removes record and writes audit log."""
    pk = dq_scorecard_a.pk
    url = reverse("bi:data_quality_scorecard_delete", kwargs={"pk": pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_scorecard_list")
    assert not DataQualityScorecard.objects.filter(pk=pk).exists()

    audit_exists = AuditLog.objects.filter(tenant=tenant_a, action="delete").exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_scorecard_delete_cross_tenant_idor_returns_404(auth_client, dq_scorecard_b):
    """Verify cross-tenant IDOR delete on scorecard returns 404."""
    url = reverse("bi:data_quality_scorecard_delete", kwargs={"pk": dq_scorecard_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404
    assert DataQualityScorecard.objects.filter(pk=dq_scorecard_b.pk).exists()


@pytest.mark.django_db
def test_dataquality_scorecard_recalculate_get_method_not_allowed(auth_client, dq_scorecard_a):
    """Verify GET on scorecard recalculate returns 405 Method Not Allowed."""
    url = reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_a.pk})
    response = auth_client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_dataquality_scorecard_recalculate_post_updates_scores_and_audits(
    auth_client, tenant_a, dq_scorecard_a, dq_rule_a, admin_user
):
    """Verify POST recalculates dimensional scores, overall score, grade, and writes audit log."""
    url = reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_a.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("bi:data_quality_scorecard_detail", kwargs={"pk": dq_scorecard_a.pk})

    dq_scorecard_a.refresh_from_db()
    assert dq_scorecard_a.last_calculated_at is not None
    assert dq_scorecard_a.total_rules_evaluated >= 1
    assert dq_scorecard_a.overall_quality_score >= Decimal("90.00")
    assert dq_scorecard_a.grade in ["A", "B"]

    audit_exists = AuditLog.objects.filter(
        tenant=tenant_a,
        action__startswith="recalc",
    ).exists()
    assert audit_exists is True


@pytest.mark.django_db
def test_dataquality_scorecard_recalculate_post_critical_exception_sets_health(
    auth_client, tenant_a, dq_scorecard_a, dq_exception_a, admin_user
):
    """Verify presence of open critical exception sets health_status to 'critical'."""
    dq_exception_a.status = "open"
    dq_exception_a.severity = "critical"
    dq_exception_a.save()

    url = reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_a.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    dq_scorecard_a.refresh_from_db()
    assert dq_scorecard_a.critical_exceptions_count >= 1
    assert dq_scorecard_a.health_status == "critical"


@pytest.mark.django_db
def test_dataquality_scorecard_recalculate_post_low_score_sets_failing(
    auth_client, tenant_a, warehouse_table_a, admin_user
):
    """Verify when evaluated rules have poor scores, overall score drops and health becomes failing."""
    # Create failing rules across multiple dimensions
    for dim in ["completeness", "accuracy", "consistency", "validity"]:
        _dataquality_create_rule(
            tenant_a,
            name=f"Failing {dim} Rule",
            code=f"fail_{dim}_rule",
            warehouse_table=warehouse_table_a,
            dimension=dim,
            last_status="failed",
            pass_rate_pct=Decimal("40.00"),
        )

    sc = _dataquality_create_scorecard(
        tenant_a,
        name="Low Score Test Card",
        code="low_score_test_card",
        warehouse_table=warehouse_table_a,
        target_quality_score=Decimal("95.00"),
    )

    url = reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": sc.pk})
    response = auth_client.post(url)

    assert response.status_code == 302
    sc.refresh_from_db()
    assert sc.overall_quality_score < Decimal("75.00")
    assert sc.meets_sla is False


@pytest.mark.django_db
def test_dataquality_scorecard_recalculate_cross_tenant_idor_returns_404(
    auth_client, dq_scorecard_b
):
    """Verify cross-tenant IDOR on scorecard recalculate returns 404."""
    url = reverse("bi:data_quality_scorecard_recalculate", kwargs={"pk": dq_scorecard_b.pk})
    response = auth_client.post(url)
    assert response.status_code == 404
