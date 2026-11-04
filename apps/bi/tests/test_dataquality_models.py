"""Unit tests for Sub-module 10.5 Data Quality & Cleansing models.

Models covered:
- DataQualityProfile (BDQP)
- DataQualityRule (BDQR)
- DataQualityException (BDQE)
- DataQualityScorecard (BDQS)
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.bi.models import (
    DataMart,
    DataQualityException,
    DataQualityProfile,
    DataQualityRule,
    DataQualityScorecard,
    SemanticModel,
    WarehouseTable,
)


# ---------------------------------------------------------------------------
# Module Helpers
# ---------------------------------------------------------------------------


def _dataquality_extract_choice_keys(choices_list):
    """Helper to extract keys from Django choices tuple/list."""
    return [c[0] for c in choices_list]


# ---------------------------------------------------------------------------
# 1. DataQualityProfile Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dataquality_profile_creation_and_autonumber(tenant_a, warehouse_table_a):
    """Test DataQualityProfile creation, BDQP auto-number prefix, and fields."""
    profile = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Orders Ingestion Profile",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
    )
    assert profile.NUMBER_PREFIX == "BDQP"
    assert profile.number.startswith("BDQP-")
    assert profile.name == "Orders Ingestion Profile"
    assert profile.warehouse_table == warehouse_table_a
    assert profile.tenant == tenant_a


@pytest.mark.django_db
def test_dataquality_profile_str_representation(dq_profile_a):
    """Test string representation format 'name (number)'."""
    expected_str = f"{dq_profile_a.name} ({dq_profile_a.number})"
    assert str(dq_profile_a) == expected_str


@pytest.mark.django_db
def test_dataquality_profile_absolute_url(dq_profile_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/data-quality/profiles/{dq_profile_a.pk}/"
    assert dq_profile_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_dataquality_profile_defaults_and_fields(tenant_a):
    """Verify default field values for DataQualityProfile."""
    profile = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Minimal DQ Profile",
    )
    assert profile.target_type == "warehouse_table"
    assert profile.warehouse_table is None
    assert profile.semantic_model is None
    assert profile.status == "pending"
    assert profile.total_row_count == 0
    assert profile.total_column_count == 0
    assert profile.completeness_score == Decimal("100.00")
    assert profile.uniqueness_score == Decimal("100.00")
    assert profile.validity_score == Decimal("100.00")
    assert profile.column_profiles_json == []
    assert profile.profiled_by is None
    assert profile.profiled_at is None
    assert profile.duration_seconds == Decimal("0.00")
    assert profile.error_message == ""
    assert profile.notes == ""
    assert profile.is_active is True


@pytest.mark.django_db
def test_dataquality_profile_choices():
    """Verify choice keys for DataQualityProfile."""
    target_type_keys = _dataquality_extract_choice_keys(DataQualityProfile.TARGET_TYPE_CHOICES)
    assert target_type_keys == ["warehouse_table", "semantic_model"]

    status_keys = _dataquality_extract_choice_keys(DataQualityProfile.STATUS_CHOICES)
    assert status_keys == ["pending", "profiling", "completed", "failed"]


@pytest.mark.django_db
def test_dataquality_profile_relationships(tenant_a, warehouse_table_a, semantic_model_a, admin_user):
    """Verify relationships with warehouse_table, semantic_model, and profiled_by."""
    profile_tbl = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Table Profile",
        target_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        profiled_by=admin_user,
        profiled_at=timezone.now(),
    )
    assert profile_tbl in warehouse_table_a.quality_profiles.all()
    assert profile_tbl.profiled_by == admin_user

    profile_sm = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Semantic Profile",
        target_type="semantic_model",
        semantic_model=semantic_model_a,
        profiled_by=admin_user,
    )
    assert profile_sm in semantic_model_a.quality_profiles.all()
    assert profile_sm.warehouse_table is None


@pytest.mark.django_db
def test_dataquality_profile_column_profiles_json_payload(tenant_a, warehouse_table_a):
    """Verify column_profiles_json stores statistical metadata correctly."""
    metadata = [
        {
            "column": "total_amount",
            "data_type": "NUMERIC(14, 2)",
            "null_count": 0,
            "distinct_count": 1420,
            "min_val": "0.50",
            "max_val": "99999.99",
            "completeness_pct": 100.0,
        },
        {
            "column": "customer_id",
            "data_type": "INTEGER",
            "null_count": 5,
            "distinct_count": 350,
            "completeness_pct": 99.66,
        },
    ]
    profile = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Stats Metadata Profile",
        warehouse_table=warehouse_table_a,
        column_profiles_json=metadata,
        total_column_count=2,
    )
    profile.refresh_from_db()
    assert len(profile.column_profiles_json) == 2
    assert profile.column_profiles_json[0]["column"] == "total_amount"
    assert profile.column_profiles_json[1]["null_count"] == 5


@pytest.mark.django_db
def test_dataquality_profile_cascade_delete_table(tenant_a, lakehouse_zone_a):
    """Deleting warehouse table cascades to its data quality profiles."""
    table = WarehouseTable.objects.create(
        tenant=tenant_a,
        lakehouse_zone=lakehouse_zone_a,
        name="Temp Fact Table",
        table_name="fact_temp_profile_cascade",
    )
    profile = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Temporary Table Profile",
        target_type="warehouse_table",
        warehouse_table=table,
    )
    profile_id = profile.id
    table.delete()
    assert not DataQualityProfile.objects.filter(id=profile_id).exists()


@pytest.mark.django_db
def test_dataquality_profile_tenant_isolation(tenant_a, tenant_b, dq_profile_a, dq_profile_b):
    """Verify tenant isolation for DataQualityProfile querysets."""
    tenant_a_profiles = DataQualityProfile.objects.filter(tenant=tenant_a)
    tenant_b_profiles = DataQualityProfile.objects.filter(tenant=tenant_b)

    assert dq_profile_a in tenant_a_profiles
    assert dq_profile_a not in tenant_b_profiles
    assert dq_profile_b in tenant_b_profiles
    assert dq_profile_b not in tenant_a_profiles


@pytest.mark.django_db
def test_dataquality_profile_number_tenant_unique_constraint(tenant_a, dq_profile_a):
    """Duplicate number for the same tenant violates UniqueConstraint."""
    with pytest.raises(IntegrityError):
        DataQualityProfile.objects.create(
            tenant=tenant_a,
            number=dq_profile_a.number,
            name="Conflicting Profile Number",
        )


# ---------------------------------------------------------------------------
# 2. DataQualityRule Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dataquality_rule_creation_and_autonumber(tenant_a, warehouse_table_a):
    """Test DataQualityRule creation, BDQR auto-number prefix, and fields."""
    rule = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Revenue Greater Than Zero",
        code="revenue_gt_zero",
        warehouse_table=warehouse_table_a,
        target_column="amount",
    )
    assert rule.NUMBER_PREFIX == "BDQR"
    assert rule.number.startswith("BDQR-")
    assert rule.name == "Revenue Greater Than Zero"
    assert rule.code == "revenue_gt_zero"
    assert rule.warehouse_table == warehouse_table_a


@pytest.mark.django_db
def test_dataquality_rule_str_representation(dq_rule_a):
    """Test string representation format 'name (number)'."""
    expected_str = f"{dq_rule_a.name} ({dq_rule_a.number})"
    assert str(dq_rule_a) == expected_str


@pytest.mark.django_db
def test_dataquality_rule_absolute_url(dq_rule_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/data-quality/rules/{dq_rule_a.pk}/"
    assert dq_rule_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_dataquality_rule_defaults_and_fields(tenant_a):
    """Verify default field values for DataQualityRule."""
    rule = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Default Rule Check",
        code="default_rule_check",
    )
    assert rule.rule_category == "validation"
    assert rule.dimension == "validity"
    assert rule.target_type == "warehouse_table"
    assert rule.warehouse_table is None
    assert rule.semantic_model is None
    assert rule.target_column == ""
    assert rule.rule_type == "not_null"
    assert rule.parameters_json == {}
    assert rule.severity == "warning"
    assert rule.failure_tolerance_pct == Decimal("0.00")
    assert rule.last_run_at is None
    assert rule.last_status == "passed"
    assert rule.passed_records_count == 0
    assert rule.failed_records_count == 0
    assert rule.pass_rate_pct == Decimal("100.00")
    assert rule.steward is None
    assert rule.description == ""
    assert rule.is_active is True


@pytest.mark.django_db
def test_dataquality_rule_choices():
    """Verify choice keys for DataQualityRule."""
    category_keys = _dataquality_extract_choice_keys(DataQualityRule.RULE_CATEGORY_CHOICES)
    assert category_keys == ["validation", "consistency", "uniqueness", "standardization", "custom_sql"]

    dim_keys = _dataquality_extract_choice_keys(DataQualityRule.DIMENSION_CHOICES)
    assert dim_keys == ["completeness", "accuracy", "consistency", "timeliness", "uniqueness", "validity"]

    target_type_keys = _dataquality_extract_choice_keys(DataQualityRule.TARGET_TYPE_CHOICES)
    assert target_type_keys == ["warehouse_table", "semantic_model"]

    rule_type_keys = _dataquality_extract_choice_keys(DataQualityRule.RULE_TYPE_CHOICES)
    assert rule_type_keys == [
        "not_null",
        "unique",
        "range_between",
        "regex_pattern",
        "set_membership",
        "referential_integrity",
        "date_freshness",
        "string_standardization",
        "duplicate_cluster",
        "custom_sql",
    ]

    severity_keys = _dataquality_extract_choice_keys(DataQualityRule.SEVERITY_CHOICES)
    assert severity_keys == ["info", "warning", "critical", "fatal"]

    status_keys = _dataquality_extract_choice_keys(DataQualityRule.STATUS_CHOICES)
    assert status_keys == ["passed", "warning", "failed", "error", "skipped"]


@pytest.mark.django_db
def test_dataquality_rule_parameters_json_structures(tenant_a, warehouse_table_a):
    """Verify parameters_json handles diverse assertions (range, regex, enum, sql)."""
    r_range = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Age Range Check",
        code="age_range_check",
        rule_type="range_between",
        parameters_json={"min_val": 18, "max_val": 120},
    )
    assert r_range.parameters_json["min_val"] == 18

    r_regex = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Postal Code Regex Check",
        code="postal_code_regex_check",
        rule_type="regex_pattern",
        parameters_json={"pattern": r"^[0-9]{5}(-[0-9]{4})?$"},
    )
    assert "pattern" in r_regex.parameters_json

    r_enum = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Order Status Enum Check",
        code="order_status_enum_check",
        rule_type="set_membership",
        parameters_json={"allowed_values": ["draft", "confirmed", "shipped", "cancelled"]},
    )
    assert "draft" in r_enum.parameters_json["allowed_values"]

    r_sql = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Custom SQL Check",
        code="custom_sql_check",
        rule_category="custom_sql",
        rule_type="custom_sql",
        parameters_json={"sql_clause": "discount_pct <= 50.00"},
    )
    assert "discount_pct" in r_sql.parameters_json["sql_clause"]


@pytest.mark.django_db
def test_dataquality_rule_relationships_and_steward(tenant_a, warehouse_table_a, semantic_model_a, admin_user):
    """Verify relationships with warehouse_table, semantic_model, and steward."""
    rule_table = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Table Rule",
        code="table_rule_rel",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    assert rule_table in warehouse_table_a.quality_rules.all()
    assert rule_table in admin_user.stewarded_quality_rules.all()

    rule_sm = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Semantic Rule",
        code="semantic_rule_rel",
        target_type="semantic_model",
        semantic_model=semantic_model_a,
        steward=admin_user,
    )
    assert rule_sm in semantic_model_a.quality_rules.all()
    assert rule_sm.warehouse_table is None


@pytest.mark.django_db
def test_dataquality_rule_code_unique_per_tenant(tenant_a, tenant_b):
    """Rule code must be unique within a tenant, but can duplicate across tenants."""
    DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Acme Postal Check",
        code="common_postal_rule",
    )
    with pytest.raises(IntegrityError):
        DataQualityRule.objects.create(
            tenant=tenant_a,
            name="Acme Another Postal Check",
            code="common_postal_rule",
        )

    globex_rule = DataQualityRule.objects.create(
        tenant=tenant_b,
        name="Globex Postal Check",
        code="common_postal_rule",
    )
    assert globex_rule.code == "common_postal_rule"


@pytest.mark.django_db
def test_dataquality_rule_number_unique_per_tenant(tenant_a, dq_rule_a):
    """Rule number must be unique within a tenant."""
    with pytest.raises(IntegrityError):
        DataQualityRule.objects.create(
            tenant=tenant_a,
            number=dq_rule_a.number,
            name="Conflicting Number Rule",
            code="conflicting_num_rule",
        )


@pytest.mark.django_db
def test_dataquality_rule_tenant_isolation(tenant_a, tenant_b, dq_rule_a, dq_rule_b):
    """Verify tenant isolation for DataQualityRule querysets."""
    tenant_a_rules = DataQualityRule.objects.filter(tenant=tenant_a)
    tenant_b_rules = DataQualityRule.objects.filter(tenant=tenant_b)

    assert dq_rule_a in tenant_a_rules
    assert dq_rule_a not in tenant_b_rules
    assert dq_rule_b in tenant_b_rules
    assert dq_rule_b not in tenant_a_rules


@pytest.mark.django_db
def test_dataquality_rule_metrics_update(tenant_a, dq_rule_a):
    """Verify updating execution counts and pass rate percentage."""
    dq_rule_a.last_run_at = timezone.now()
    dq_rule_a.passed_records_count = 9850
    dq_rule_a.failed_records_count = 150
    dq_rule_a.pass_rate_pct = Decimal("98.50")
    dq_rule_a.last_status = "warning"
    dq_rule_a.save()

    dq_rule_a.refresh_from_db()
    assert dq_rule_a.passed_records_count == 9850
    assert dq_rule_a.failed_records_count == 150
    assert dq_rule_a.pass_rate_pct == Decimal("98.50")
    assert dq_rule_a.last_status == "warning"


# ---------------------------------------------------------------------------
# 3. DataQualityException Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dataquality_exception_creation_and_autonumber(tenant_a, dq_rule_a, dq_profile_a, warehouse_table_a, admin_user):
    """Test DataQualityException creation, BDQE auto-number prefix, and fields."""
    exc = DataQualityException.objects.create(
        tenant=tenant_a,
        rule=dq_rule_a,
        profile=dq_profile_a,
        warehouse_table=warehouse_table_a,
        target_column="total_amount",
        record_identifier="INV-TEST-001",
        invalid_value="-100.00",
        expected_condition="amount > 0",
        exception_type="range_outlier",
        severity="critical",
        status="open",
        assigned_steward=admin_user,
    )
    assert exc.NUMBER_PREFIX == "BDQE"
    assert exc.number.startswith("BDQE-")
    assert exc.record_identifier == "INV-TEST-001"
    assert exc.assigned_steward == admin_user
    assert exc.warehouse_table == warehouse_table_a


@pytest.mark.django_db
def test_dataquality_exception_str_representation(dq_exception_a):
    """Test string representation format 'number: record_identifier (exception_type_display)'."""
    expected_str = f"{dq_exception_a.number}: {dq_exception_a.record_identifier} ({dq_exception_a.get_exception_type_display()})"
    assert str(dq_exception_a) == expected_str


@pytest.mark.django_db
def test_dataquality_exception_absolute_url(dq_exception_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/data-quality/exceptions/{dq_exception_a.pk}/"
    assert dq_exception_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_dataquality_exception_defaults(tenant_a):
    """Verify default field values for DataQualityException."""
    exc = DataQualityException.objects.create(
        tenant=tenant_a,
        record_identifier="REC-MINIMAL-01",
    )
    assert exc.rule is None
    assert exc.profile is None
    assert exc.warehouse_table is None
    assert exc.semantic_model is None
    assert exc.target_column == ""
    assert exc.invalid_value == ""
    assert exc.expected_condition == ""
    assert exc.exception_type == "rule_violation"
    assert exc.severity == "warning"
    assert exc.status == "open"
    assert exc.remediation_action == "none"
    assert exc.proposed_value == ""
    assert exc.remediated_value == ""
    assert exc.assigned_steward is None
    assert exc.resolved_by is None
    assert exc.resolved_at is None
    assert exc.resolution_notes == ""
    assert exc.is_active is True


@pytest.mark.django_db
def test_dataquality_exception_choices():
    """Verify choice keys for DataQualityException."""
    etype_keys = _dataquality_extract_choice_keys(DataQualityException.EXCEPTION_TYPE_CHOICES)
    assert etype_keys == [
        "rule_violation",
        "duplicate_candidate",
        "null_anomaly",
        "range_outlier",
        "format_invalid",
        "referential_orphan",
    ]

    severity_keys = _dataquality_extract_choice_keys(DataQualityException.SEVERITY_CHOICES)
    assert severity_keys == ["info", "warning", "critical", "fatal"]

    status_keys = _dataquality_extract_choice_keys(DataQualityException.STATUS_CHOICES)
    assert status_keys == [
        "open",
        "investigating",
        "remediated",
        "suppressed_false_positive",
        "accepted_risk",
        "rejected",
    ]

    remediation_keys = _dataquality_extract_choice_keys(DataQualityException.REMEDIATION_ACTION_CHOICES)
    assert remediation_keys == [
        "none",
        "manual_edit",
        "automated_standardize",
        "merge_duplicate",
        "impute_value",
        "quarantine_row",
    ]


@pytest.mark.django_db
def test_dataquality_exception_resolution_and_steward_tracking(tenant_a, dq_exception_a, admin_user):
    """Verify lifecycle transition from open to remediated with steward tracking."""
    now = timezone.now()
    dq_exception_a.status = "remediated"
    dq_exception_a.remediation_action = "manual_edit"
    dq_exception_a.proposed_value = "0.00"
    dq_exception_a.remediated_value = "10.00"
    dq_exception_a.resolved_by = admin_user
    dq_exception_a.resolved_at = now
    dq_exception_a.resolution_notes = "Corrected negative invoice amount following merchant confirmation."
    dq_exception_a.save()

    dq_exception_a.refresh_from_db()
    assert dq_exception_a.status == "remediated"
    assert dq_exception_a.remediation_action == "manual_edit"
    assert dq_exception_a.remediated_value == "10.00"
    assert dq_exception_a.resolved_by == admin_user
    assert dq_exception_a.resolved_at is not None
    assert "merchant confirmation" in dq_exception_a.resolution_notes


@pytest.mark.django_db
def test_dataquality_exception_semantic_model_target(tenant_a, semantic_model_a, dq_rule_a):
    """Verify exception linked to semantic model."""
    exc = DataQualityException.objects.create(
        tenant=tenant_a,
        rule=dq_rule_a,
        semantic_model=semantic_model_a,
        record_identifier="SM-ROW-1092",
        target_column="revenue",
        exception_type="null_anomaly",
    )
    assert exc in semantic_model_a.quality_exceptions.all()
    assert exc.warehouse_table is None


@pytest.mark.django_db
def test_dataquality_exception_fk_set_null_on_rule_deletion(tenant_a):
    """Deleting a rule sets rule FK to NULL on exceptions (audit trail preservation)."""
    rule = DataQualityRule.objects.create(
        tenant=tenant_a,
        name="Ephemeral Rule Check",
        code="ephemeral_rule_check",
    )
    exc = DataQualityException.objects.create(
        tenant=tenant_a,
        rule=rule,
        record_identifier="REC-EPH-1",
    )
    rule.delete()
    exc.refresh_from_db()
    assert exc.rule is None


@pytest.mark.django_db
def test_dataquality_exception_fk_set_null_on_profile_deletion(tenant_a):
    """Deleting a profile sets profile FK to NULL on exceptions."""
    profile = DataQualityProfile.objects.create(
        tenant=tenant_a,
        name="Ephemeral Profile Run",
    )
    exc = DataQualityException.objects.create(
        tenant=tenant_a,
        profile=profile,
        record_identifier="REC-EPH-2",
    )
    profile.delete()
    exc.refresh_from_db()
    assert exc.profile is None


@pytest.mark.django_db
def test_dataquality_exception_number_unique_per_tenant(tenant_a, dq_exception_a):
    """Exception number must be unique within a tenant."""
    with pytest.raises(IntegrityError):
        DataQualityException.objects.create(
            tenant=tenant_a,
            number=dq_exception_a.number,
            record_identifier="REC-DUPLICATE-NUMBER",
        )


@pytest.mark.django_db
def test_dataquality_exception_tenant_isolation(tenant_a, tenant_b, dq_exception_a, dq_exception_b):
    """Verify tenant isolation for DataQualityException querysets."""
    tenant_a_exceptions = DataQualityException.objects.filter(tenant=tenant_a)
    tenant_b_exceptions = DataQualityException.objects.filter(tenant=tenant_b)

    assert dq_exception_a in tenant_a_exceptions
    assert dq_exception_a not in tenant_b_exceptions
    assert dq_exception_b in tenant_b_exceptions
    assert dq_exception_b not in tenant_a_exceptions


# ---------------------------------------------------------------------------
# 4. DataQualityScorecard Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dataquality_scorecard_creation_and_autonumber(tenant_a, warehouse_table_a, admin_user):
    """Test DataQualityScorecard creation, BDQS auto-number prefix, and fields."""
    scorecard = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Finance Invoices Trust Scorecard",
        code="fin_inv_trust_scorecard",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    assert scorecard.NUMBER_PREFIX == "BDQS"
    assert scorecard.number.startswith("BDQS-")
    assert scorecard.name == "Finance Invoices Trust Scorecard"
    assert scorecard.code == "fin_inv_trust_scorecard"
    assert scorecard.warehouse_table == warehouse_table_a
    assert scorecard.steward == admin_user


@pytest.mark.django_db
def test_dataquality_scorecard_str_representation(dq_scorecard_a):
    """Test string representation format 'name (number) — Grade grade (score%)'."""
    expected_str = f"{dq_scorecard_a.name} ({dq_scorecard_a.number}) — Grade {dq_scorecard_a.grade} ({dq_scorecard_a.overall_quality_score}%)"
    assert str(dq_scorecard_a) == expected_str


@pytest.mark.django_db
def test_dataquality_scorecard_absolute_url(dq_scorecard_a):
    """Verify get_absolute_url returns canonical detail route."""
    expected_url = f"/bi/data-quality/scorecards/{dq_scorecard_a.pk}/"
    assert dq_scorecard_a.get_absolute_url() == expected_url


@pytest.mark.django_db
def test_dataquality_scorecard_defaults_and_fields(tenant_a):
    """Verify default field values for DataQualityScorecard."""
    scorecard = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Default Scorecard",
        code="default_scorecard",
    )
    assert scorecard.scope_type == "warehouse_table"
    assert scorecard.warehouse_table is None
    assert scorecard.semantic_model is None
    assert scorecard.data_mart is None
    assert scorecard.org_unit is None
    assert scorecard.overall_quality_score == Decimal("100.00")
    assert scorecard.completeness_score == Decimal("100.00")
    assert scorecard.accuracy_score == Decimal("100.00")
    assert scorecard.consistency_score == Decimal("100.00")
    assert scorecard.timeliness_score == Decimal("100.00")
    assert scorecard.uniqueness_score == Decimal("100.00")
    assert scorecard.validity_score == Decimal("100.00")
    assert scorecard.grade == "A"
    assert scorecard.health_status == "healthy"
    assert scorecard.target_quality_score == Decimal("95.00")
    assert scorecard.meets_sla is True
    assert scorecard.total_rules_evaluated == 0
    assert scorecard.rules_passed_count == 0
    assert scorecard.rules_failed_count == 0
    assert scorecard.open_exceptions_count == 0
    assert scorecard.critical_exceptions_count == 0
    assert scorecard.evaluation_period == "ad_hoc"
    assert scorecard.last_calculated_at is None
    assert scorecard.steward is None
    assert scorecard.description == ""
    assert scorecard.is_active is True


@pytest.mark.django_db
def test_dataquality_scorecard_choices():
    """Verify choice keys for DataQualityScorecard."""
    scope_keys = _dataquality_extract_choice_keys(DataQualityScorecard.SCOPE_TYPE_CHOICES)
    assert scope_keys == ["warehouse_table", "semantic_model", "data_mart", "tenant_wide"]

    grade_keys = _dataquality_extract_choice_keys(DataQualityScorecard.GRADE_CHOICES)
    assert grade_keys == ["A", "B", "C", "D", "F"]

    health_keys = _dataquality_extract_choice_keys(DataQualityScorecard.HEALTH_STATUS_CHOICES)
    assert health_keys == ["healthy", "needs_attention", "critical", "failing"]

    eval_keys = _dataquality_extract_choice_keys(DataQualityScorecard.EVALUATION_PERIOD_CHOICES)
    assert eval_keys == ["ad_hoc", "daily", "weekly", "monthly"]


@pytest.mark.django_db
def test_dataquality_scorecard_code_unique_per_tenant(tenant_a, tenant_b):
    """Scorecard code must be unique within a tenant, but can duplicate across tenants."""
    DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Acme Executive Trust Index",
        code="exec_trust_index",
    )
    with pytest.raises(IntegrityError):
        DataQualityScorecard.objects.create(
            tenant=tenant_a,
            name="Acme Conflicting Trust Index",
            code="exec_trust_index",
        )

    globex_sc = DataQualityScorecard.objects.create(
        tenant=tenant_b,
        name="Globex Executive Trust Index",
        code="exec_trust_index",
    )
    assert globex_sc.code == "exec_trust_index"


@pytest.mark.django_db
def test_dataquality_scorecard_number_unique_per_tenant(tenant_a, dq_scorecard_a):
    """Scorecard number must be unique within a tenant."""
    with pytest.raises(IntegrityError):
        DataQualityScorecard.objects.create(
            tenant=tenant_a,
            number=dq_scorecard_a.number,
            name="Conflicting Number Scorecard",
            code="conflicting_num_scorecard",
        )


@pytest.mark.django_db
def test_dataquality_scorecard_sla_compliance_metrics(tenant_a, dq_scorecard_a):
    """Verify metrics calculation and SLA threshold tracking."""
    dq_scorecard_a.total_rules_evaluated = 50
    dq_scorecard_a.rules_passed_count = 42
    dq_scorecard_a.rules_failed_count = 8
    dq_scorecard_a.open_exceptions_count = 12
    dq_scorecard_a.critical_exceptions_count = 3
    dq_scorecard_a.overall_quality_score = Decimal("84.00")
    dq_scorecard_a.grade = "C"
    dq_scorecard_a.health_status = "needs_attention"
    dq_scorecard_a.meets_sla = False
    dq_scorecard_a.last_calculated_at = timezone.now()
    dq_scorecard_a.save()

    dq_scorecard_a.refresh_from_db()
    assert dq_scorecard_a.total_rules_evaluated == 50
    assert dq_scorecard_a.rules_passed_count == 42
    assert dq_scorecard_a.rules_failed_count == 8
    assert dq_scorecard_a.open_exceptions_count == 12
    assert dq_scorecard_a.critical_exceptions_count == 3
    assert dq_scorecard_a.overall_quality_score == Decimal("84.00")
    assert dq_scorecard_a.grade == "C"
    assert dq_scorecard_a.health_status == "needs_attention"
    assert dq_scorecard_a.meets_sla is False


@pytest.mark.django_db
def test_dataquality_scorecard_relationships(tenant_a, warehouse_table_a, semantic_model_a, data_mart_a, admin_user):
    """Verify relationships with warehouse_table, semantic_model, data_mart, and steward."""
    sc_table = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Table Scorecard",
        code="table_scorecard_rel",
        scope_type="warehouse_table",
        warehouse_table=warehouse_table_a,
        steward=admin_user,
    )
    assert sc_table in warehouse_table_a.scorecards.all()
    assert sc_table in admin_user.stewarded_scorecards.all()

    sc_sm = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Semantic Scorecard",
        code="semantic_scorecard_rel",
        scope_type="semantic_model",
        semantic_model=semantic_model_a,
    )
    assert sc_sm in semantic_model_a.scorecards.all()

    sc_mart = DataQualityScorecard.objects.create(
        tenant=tenant_a,
        name="Mart Scorecard",
        code="mart_scorecard_rel",
        scope_type="data_mart",
        data_mart=data_mart_a,
    )
    assert sc_mart in data_mart_a.scorecards.all()


@pytest.mark.django_db
def test_dataquality_scorecard_tenant_isolation(tenant_a, tenant_b, dq_scorecard_a, dq_scorecard_b):
    """Verify tenant isolation for DataQualityScorecard querysets."""
    tenant_a_scorecards = DataQualityScorecard.objects.filter(tenant=tenant_a)
    tenant_b_scorecards = DataQualityScorecard.objects.filter(tenant=tenant_b)

    assert dq_scorecard_a in tenant_a_scorecards
    assert dq_scorecard_a not in tenant_b_scorecards
    assert dq_scorecard_b in tenant_b_scorecards
    assert dq_scorecard_b not in tenant_a_scorecards
