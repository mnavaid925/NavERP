"""Unit tests for Sub-module 10.9 Standard & Operational Reporting models.

Models covered:
- ReportDefinition (BRPT)
- ReportParameter (BPAR)
- ReportExecution (BRUN)
- ReportDrillPath (BDRP)
"""
import pytest
from django.db import IntegrityError, transaction

from apps.bi.models import (
    ReportDefinition,
    ReportDrillPath,
    ReportExecution,
    ReportParameter,
)

_OPERATIONALREPORTING_VALID_BADGES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
}


def _operationalreporting_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


def _operationalreporting_assert_valid_badge(badge):
    """Helper to verify badge is in valid color-named badge classes and not purple."""
    assert badge in _OPERATIONALREPORTING_VALID_BADGES
    assert badge != "badge-purple"


# ---------------------------------------------------------------------------
# 1. ReportDefinition Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_definition_creation_and_autonumber(tenant_a, admin_user):
    """Test ReportDefinition creation, BRPT- auto-numbering, default fields, and str."""
    report = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Executive P&L Statement",
        slug="executive-pl-statement",
        description="Standard monthly Profit and Loss operational statement",
        category="finance",
        created_by=admin_user,
    )
    assert report.NUMBER_PREFIX == "BRPT"
    assert report.number.startswith("BRPT-")
    assert len(report.number) == 10  # BRPT-00001
    assert report.name == "Executive P&L Statement"
    assert report.slug == "executive-pl-statement"
    assert report.category == "finance"
    assert report.report_type == "standard_tabular"
    assert report.paper_size == "a4"
    assert report.orientation == "portrait"
    assert report.margins_json == {}
    assert report.bands_config_json == {}
    assert report.columns_config_json == []
    assert report.styling_css == ""
    assert report.watermark_text == ""
    assert report.semantic_model is None
    assert report.warehouse_table is None
    assert report.raw_query == ""
    assert report.org_unit is None
    assert report.created_by == admin_user
    assert report.status == "draft"
    assert report.is_prebuilt_template is False
    assert report.is_active is True

    # Check str representation and absolute URL
    assert str(report) == f"{report.name} ({report.number})"
    assert report.get_absolute_url() == f"/bi/reports/{report.pk}/"

    # Check badge properties
    _operationalreporting_assert_valid_badge(report.badge_status)
    assert report.badge_status == "badge-amber"
    _operationalreporting_assert_valid_badge(report.badge_category)
    assert report.badge_category == "badge-green"
    _operationalreporting_assert_valid_badge(report.badge_type)
    assert report.badge_type == "badge-info"


@pytest.mark.django_db
def test_operationalreporting_definition_unique_tenant_slug(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test that slug is unique per tenant, but same slug is permitted across tenants."""
    ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Monthly Revenue Summary",
        slug="monthly-revenue-summary",
        created_by=admin_user,
    )

    # Reusing same slug within tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportDefinition.objects.create(
                tenant=tenant_a,
                name="Monthly Revenue Summary Duplicate",
                slug="monthly-revenue-summary",
                created_by=admin_user,
            )

    # Same slug in tenant_b must succeed (tenant isolation)
    report_b = ReportDefinition.objects.create(
        tenant=tenant_b,
        name="Monthly Revenue Summary Globex",
        slug="monthly-revenue-summary",
        created_by=admin_user_b,
    )
    assert report_b.slug == "monthly-revenue-summary"
    assert report_b.tenant == tenant_b


@pytest.mark.django_db
def test_operationalreporting_definition_unique_tenant_number(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test compound unique constraint on (tenant, number)."""
    rpt1 = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Report Alpha",
        slug="report-alpha",
        created_by=admin_user,
    )
    rpt2 = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Report Beta",
        slug="report-beta",
        created_by=admin_user,
    )
    assert rpt1.number != rpt2.number

    # Attempting to duplicate number within tenant_a must violate uniqueness
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportDefinition.objects.create(
                tenant=tenant_a,
                number=rpt1.number,
                name="Report Clash",
                slug="report-clash",
                created_by=admin_user,
            )

    # Reusing the same number across tenants is permitted
    rpt_b = ReportDefinition.objects.create(
        tenant=tenant_b,
        number=rpt1.number,
        name="Report Globex Duplicate Number",
        slug="report-globex-dup",
        created_by=admin_user_b,
    )
    assert rpt_b.number == rpt1.number
    assert rpt_b.tenant == tenant_b


@pytest.mark.django_db
def test_operationalreporting_definition_choices():
    """Verify choice keys on ReportDefinition model."""
    categories = _operationalreporting_choice_keys(ReportDefinition.CATEGORY_CHOICES)
    assert "finance" in categories
    assert "sales" in categories
    assert "inventory" in categories
    assert "hr" in categories
    assert "procurement" in categories
    assert "production" in categories
    assert "compliance" in categories
    assert "custom" in categories

    report_types = _operationalreporting_choice_keys(ReportDefinition.REPORT_TYPE_CHOICES)
    assert "standard_tabular" in report_types
    assert "pixel_perfect_document" in report_types
    assert "regulatory_filing" in report_types
    assert "matrix_summary" in report_types
    assert "subreport" in report_types

    paper_sizes = _operationalreporting_choice_keys(ReportDefinition.PAPER_SIZE_CHOICES)
    assert "a4" in paper_sizes
    assert "letter" in paper_sizes
    assert "legal" in paper_sizes
    assert "tabloid" in paper_sizes
    assert "custom" in paper_sizes

    orientations = _operationalreporting_choice_keys(ReportDefinition.ORIENTATION_CHOICES)
    assert "portrait" in orientations
    assert "landscape" in orientations

    statuses = _operationalreporting_choice_keys(ReportDefinition.STATUS_CHOICES)
    assert "draft" in statuses
    assert "published" in statuses
    assert "archived" in statuses


@pytest.mark.django_db
def test_operationalreporting_definition_badges(tenant_a):
    """Test all badge methods on ReportDefinition for valid color classes and choices."""
    rpt = ReportDefinition(tenant=tenant_a, name="Badge Report", slug="badge-report")

    # Status badges
    rpt.status = "draft"
    assert rpt.badge_status == "badge-amber"
    _operationalreporting_assert_valid_badge(rpt.badge_status)

    rpt.status = "published"
    assert rpt.badge_status == "badge-green"
    _operationalreporting_assert_valid_badge(rpt.badge_status)

    rpt.status = "archived"
    assert rpt.badge_status == "badge-muted"
    _operationalreporting_assert_valid_badge(rpt.badge_status)

    rpt.status = "unknown_status"
    assert rpt.badge_status == "badge-slate"
    _operationalreporting_assert_valid_badge(rpt.badge_status)

    # Category badges
    cat_expected = {
        "finance": "badge-green",
        "sales": "badge-info",
        "inventory": "badge-amber",
        "hr": "badge-muted",
        "procurement": "badge-info",
        "production": "badge-slate",
        "compliance": "badge-green",
        "custom": "badge-slate",
    }
    for cat, expected_badge in cat_expected.items():
        rpt.category = cat
        assert rpt.badge_category == expected_badge
        _operationalreporting_assert_valid_badge(rpt.badge_category)

    rpt.category = "non_existent"
    assert rpt.badge_category == "badge-slate"
    _operationalreporting_assert_valid_badge(rpt.badge_category)

    # Report type badges
    type_expected = {
        "standard_tabular": "badge-info",
        "pixel_perfect_document": "badge-green",
        "regulatory_filing": "badge-amber",
        "matrix_summary": "badge-slate",
        "subreport": "badge-muted",
    }
    for rtype, expected_badge in type_expected.items():
        rpt.report_type = rtype
        assert rpt.badge_type == expected_badge
        _operationalreporting_assert_valid_badge(rpt.badge_type)

    rpt.report_type = "unknown_type"
    assert rpt.badge_type == "badge-slate"
    _operationalreporting_assert_valid_badge(rpt.badge_type)


# ---------------------------------------------------------------------------
# 2. ReportParameter Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_parameter_creation_and_autonumber(tenant_a, admin_user):
    """Test ReportParameter creation, BPAR- auto-numbering, default fields, and str."""
    report = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Quarterly Operational Metrics",
        slug="quarterly-operational-metrics",
        created_by=admin_user,
    )
    param = ReportParameter.objects.create(
        tenant=tenant_a,
        report=report,
        parameter_name="fiscal_year",
        prompt_label="Fiscal Year",
    )
    assert param.NUMBER_PREFIX == "BPAR"
    assert param.number.startswith("BPAR-")
    assert len(param.number) == 10  # BPAR-00001
    assert param.parameter_name == "fiscal_year"
    assert param.prompt_label == "Fiscal Year"
    assert param.parameter_type == "string"
    assert param.default_value == ""
    assert param.choices_source == "static_list"
    assert param.choices_config_json == []
    assert param.validation_regex == ""
    assert param.help_text == ""
    assert param.prompt_order == 10
    assert param.is_required is False
    assert param.is_hidden is False
    assert param.is_active is True

    # Check str representation and absolute URL
    assert str(param) == f"{param.prompt_label} ({param.parameter_name}) — {param.report.name}"
    assert param.get_absolute_url() == f"/bi/report-parameters/{param.pk}/"

    # Check badge
    _operationalreporting_assert_valid_badge(param.badge_type)
    assert param.badge_type == "badge-slate"


@pytest.mark.django_db
def test_operationalreporting_parameter_unique_compound_constraints(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test compound unique constraints on (tenant, report, parameter_name) and (tenant, number)."""
    rpt_a1 = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Report 1",
        slug="report-1",
        created_by=admin_user,
    )
    rpt_a2 = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Report 2",
        slug="report-2",
        created_by=admin_user,
    )
    rpt_b1 = ReportDefinition.objects.create(
        tenant=tenant_b,
        name="Report B1",
        slug="report-b1",
        created_by=admin_user_b,
    )

    param1 = ReportParameter.objects.create(
        tenant=tenant_a,
        report=rpt_a1,
        parameter_name="start_date",
        prompt_label="Start Date",
    )

    # Same parameter_name in same report in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportParameter.objects.create(
                tenant=tenant_a,
                report=rpt_a1,
                parameter_name="start_date",
                prompt_label="Another Start Date",
            )

    # Same parameter_name in DIFFERENT report in tenant_a is permitted
    param2 = ReportParameter.objects.create(
        tenant=tenant_a,
        report=rpt_a2,
        parameter_name="start_date",
        prompt_label="Start Date for Rpt 2",
    )
    assert param2.parameter_name == "start_date"

    # Same parameter_name in tenant_b is permitted
    param_b = ReportParameter.objects.create(
        tenant=tenant_b,
        report=rpt_b1,
        parameter_name="start_date",
        prompt_label="Start Date Globex",
    )
    assert param_b.parameter_name == "start_date"

    # Test (tenant, number) uniqueness
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportParameter.objects.create(
                tenant=tenant_a,
                report=rpt_a1,
                number=param1.number,
                parameter_name="other_date",
                prompt_label="Other Date",
            )


@pytest.mark.django_db
def test_operationalreporting_parameter_cascade_delete_with_report(tenant_a, admin_user):
    """Test that deleting a ReportDefinition cascades and deletes all its parameters."""
    report = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Temporary Report",
        slug="temp-report",
        created_by=admin_user,
    )
    param = ReportParameter.objects.create(
        tenant=tenant_a,
        report=report,
        parameter_name="temp_param",
        prompt_label="Temp Parameter",
    )
    report_id = report.id
    param_id = param.id

    report.delete()
    assert not ReportDefinition.objects.filter(id=report_id).exists()
    assert not ReportParameter.objects.filter(id=param_id).exists()


@pytest.mark.django_db
def test_operationalreporting_parameter_choices():
    """Verify choice keys on ReportParameter model."""
    param_types = _operationalreporting_choice_keys(ReportParameter.PARAMETER_TYPE_CHOICES)
    assert "string" in param_types
    assert "integer" in param_types
    assert "decimal" in param_types
    assert "date" in param_types
    assert "daterange" in param_types
    assert "boolean" in param_types
    assert "choice_single" in param_types
    assert "choice_multi" in param_types

    choices_sources = _operationalreporting_choice_keys(ReportParameter.CHOICES_SOURCE_CHOICES)
    assert "static_list" in choices_sources
    assert "semantic_dimension" in choices_sources
    assert "warehouse_column" in choices_sources


@pytest.mark.django_db
def test_operationalreporting_parameter_badges(tenant_a):
    """Test badge_type property for all parameter_type choices."""
    param = ReportParameter(tenant=tenant_a, parameter_name="test_p", prompt_label="Test")

    badge_mapping = {
        "string": "badge-slate",
        "integer": "badge-info",
        "decimal": "badge-info",
        "date": "badge-green",
        "daterange": "badge-green",
        "boolean": "badge-amber",
        "choice_single": "badge-info",
        "choice_multi": "badge-info",
    }
    for ptype, expected_badge in badge_mapping.items():
        param.parameter_type = ptype
        assert param.badge_type == expected_badge
        _operationalreporting_assert_valid_badge(param.badge_type)

    param.parameter_type = "unknown_type"
    assert param.badge_type == "badge-slate"
    _operationalreporting_assert_valid_badge(param.badge_type)


# ---------------------------------------------------------------------------
# 3. ReportExecution Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_execution_creation_and_autonumber(tenant_a, admin_user):
    """Test ReportExecution creation, BRUN- auto-numbering, default fields, and str."""
    report = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Sales Performance Audit",
        slug="sales-performance-audit",
        created_by=admin_user,
    )
    execution = ReportExecution.objects.create(
        tenant=tenant_a,
        report=report,
        executed_by=admin_user,
    )
    assert execution.NUMBER_PREFIX == "BRUN"
    assert execution.number.startswith("BRUN-")
    assert len(execution.number) == 10  # BRUN-00001
    assert execution.report == report
    assert execution.executed_by == admin_user
    assert execution.execution_mode == "interactive_view"
    assert execution.execution_status == "completed"
    assert execution.started_at is not None
    assert execution.completed_at is None
    assert execution.duration_ms == 0
    assert execution.parameter_values_json == {}
    assert execution.row_count == 0
    assert execution.output_format == "html"
    assert execution.output_file_name == ""
    assert execution.file_size_bytes == 0
    assert execution.error_message == ""
    assert execution.is_cached is False

    # Check str representation and absolute URL
    assert str(execution) == f"{execution.number} — {execution.report.name} ({execution.get_execution_status_display()})"
    assert execution.get_absolute_url() == f"/bi/report-executions/{execution.pk}/"

    # Check badge properties
    _operationalreporting_assert_valid_badge(execution.badge_status)
    assert execution.badge_status == "badge-green"
    _operationalreporting_assert_valid_badge(execution.badge_mode)
    assert execution.badge_mode == "badge-info"


@pytest.mark.django_db
def test_operationalreporting_execution_unique_tenant_number(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test compound unique constraint on (tenant, number) for ReportExecution."""
    report_a = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Report Exec A",
        slug="report-exec-a",
        created_by=admin_user,
    )
    report_b = ReportDefinition.objects.create(
        tenant=tenant_b,
        name="Report Exec B",
        slug="report-exec-b",
        created_by=admin_user_b,
    )

    exec1 = ReportExecution.objects.create(
        tenant=tenant_a,
        report=report_a,
        executed_by=admin_user,
    )

    # Duplicating number in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportExecution.objects.create(
                tenant=tenant_a,
                report=report_a,
                number=exec1.number,
                executed_by=admin_user,
            )

    # Same number in tenant_b is permitted
    exec_b = ReportExecution.objects.create(
        tenant=tenant_b,
        report=report_b,
        number=exec1.number,
        executed_by=admin_user_b,
    )
    assert exec_b.number == exec1.number
    assert exec_b.tenant == tenant_b


@pytest.mark.django_db
def test_operationalreporting_execution_cascade_delete_with_report(tenant_a, admin_user):
    """Test that deleting a ReportDefinition cascades and deletes all executions."""
    report = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Ephemeral Execution Report",
        slug="ephemeral-exec-report",
        created_by=admin_user,
    )
    execution = ReportExecution.objects.create(
        tenant=tenant_a,
        report=report,
        executed_by=admin_user,
    )
    report_id = report.id
    execution_id = execution.id

    report.delete()
    assert not ReportDefinition.objects.filter(id=report_id).exists()
    assert not ReportExecution.objects.filter(id=execution_id).exists()


@pytest.mark.django_db
def test_operationalreporting_execution_choices():
    """Verify choice keys on ReportExecution model."""
    modes = _operationalreporting_choice_keys(ReportExecution.EXECUTION_MODE_CHOICES)
    assert "interactive_view" in modes
    assert "export_pdf" in modes
    assert "export_excel" in modes
    assert "export_csv" in modes
    assert "export_docx" in modes
    assert "drill_through" in modes

    statuses = _operationalreporting_choice_keys(ReportExecution.EXECUTION_STATUS_CHOICES)
    assert "pending" in statuses
    assert "running" in statuses
    assert "completed" in statuses
    assert "failed" in statuses

    formats = _operationalreporting_choice_keys(ReportExecution.OUTPUT_FORMAT_CHOICES)
    assert "html" in formats
    assert "pdf" in formats
    assert "xlsx" in formats
    assert "csv" in formats
    assert "docx" in formats
    assert "json" in formats


@pytest.mark.django_db
def test_operationalreporting_execution_badges(tenant_a):
    """Test badge_status and badge_mode properties for ReportExecution."""
    execution = ReportExecution(tenant=tenant_a)

    status_mapping = {
        "pending": "badge-slate",
        "running": "badge-amber",
        "completed": "badge-green",
        "failed": "badge-red",
    }
    for stat, expected_badge in status_mapping.items():
        execution.execution_status = stat
        assert execution.badge_status == expected_badge
        _operationalreporting_assert_valid_badge(execution.badge_status)

    execution.execution_status = "unknown_stat"
    assert execution.badge_status == "badge-slate"
    _operationalreporting_assert_valid_badge(execution.badge_status)

    mode_mapping = {
        "interactive_view": "badge-info",
        "export_pdf": "badge-red",
        "export_excel": "badge-green",
        "export_csv": "badge-slate",
        "export_docx": "badge-info",
        "drill_through": "badge-info",
    }
    for mode, expected_badge in mode_mapping.items():
        execution.execution_mode = mode
        assert execution.badge_mode == expected_badge
        _operationalreporting_assert_valid_badge(execution.badge_mode)

    execution.execution_mode = "unknown_mode"
    assert execution.badge_mode == "badge-slate"
    _operationalreporting_assert_valid_badge(execution.badge_mode)


# ---------------------------------------------------------------------------
# 4. ReportDrillPath Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_drill_path_creation_and_autonumber(tenant_a, admin_user):
    """Test ReportDrillPath creation, BDRP- auto-numbering, default fields, and str."""
    source_rpt = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="General Ledger Master Summary",
        slug="gl-master-summary",
        created_by=admin_user,
    )
    target_rpt = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="GL Line Item Detail",
        slug="gl-line-item-detail",
        created_by=admin_user,
    )

    drill_path = ReportDrillPath.objects.create(
        tenant=tenant_a,
        source_report=source_rpt,
        source_field="account_code",
        drill_label="Inspect Account Journal Lines",
        target_report=target_rpt,
    )
    assert drill_path.NUMBER_PREFIX == "BDRP"
    assert drill_path.number.startswith("BDRP-")
    assert len(drill_path.number) == 10  # BDRP-00001
    assert drill_path.source_report == source_rpt
    assert drill_path.source_field == "account_code"
    assert drill_path.drill_label == "Inspect Account Journal Lines"
    assert drill_path.target_type == "operational_report"
    assert drill_path.target_report == target_rpt
    assert drill_path.target_url_pattern == ""
    assert drill_path.parameter_mapping_json == {}
    assert drill_path.sort_order == 10
    assert drill_path.is_enabled is True

    # Check str representation and absolute URL
    assert str(drill_path) == f"{drill_path.drill_label} ({drill_path.source_field} → {drill_path.get_target_type_display()})"
    assert drill_path.get_absolute_url() == f"/bi/report-drill-paths/{drill_path.pk}/"

    # Check badge property
    _operationalreporting_assert_valid_badge(drill_path.badge_target_type)
    assert drill_path.badge_target_type == "badge-slate"


@pytest.mark.django_db
def test_operationalreporting_drill_path_unique_tenant_number(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test compound unique constraint on (tenant, number) for ReportDrillPath."""
    source_a = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Source A",
        slug="source-a",
        created_by=admin_user,
    )
    source_b = ReportDefinition.objects.create(
        tenant=tenant_b,
        name="Source B",
        slug="source-b",
        created_by=admin_user_b,
    )

    path1 = ReportDrillPath.objects.create(
        tenant=tenant_a,
        source_report=source_a,
        source_field="cust_id",
        drill_label="Drill Cust",
    )

    # Duplicating number in tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReportDrillPath.objects.create(
                tenant=tenant_a,
                source_report=source_a,
                source_field="invoice_id",
                drill_label="Drill Invoice",
                number=path1.number,
            )

    # Same number in tenant_b is permitted
    path_b = ReportDrillPath.objects.create(
        tenant=tenant_b,
        source_report=source_b,
        source_field="cust_id",
        drill_label="Drill Cust Globex",
        number=path1.number,
    )
    assert path_b.number == path1.number
    assert path_b.tenant == tenant_b


@pytest.mark.django_db
def test_operationalreporting_drill_path_cascade_delete_and_set_null(tenant_a, admin_user):
    """Test cascade on source_report deletion and set_null on target_report deletion."""
    source_rpt = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Drill Source",
        slug="drill-source",
        created_by=admin_user,
    )
    target_rpt = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Drill Target",
        slug="drill-target",
        created_by=admin_user,
    )
    path = ReportDrillPath.objects.create(
        tenant=tenant_a,
        source_report=source_rpt,
        source_field="order_id",
        drill_label="Drill Order",
        target_report=target_rpt,
    )
    path_id = path.id

    # Deleting target_report should NOT delete path; it should SET NULL on target_report
    target_rpt.delete()
    path.refresh_from_db()
    assert path.target_report is None

    # Deleting source_report MUST cascade and delete the path
    source_rpt.delete()
    assert not ReportDrillPath.objects.filter(id=path_id).exists()


@pytest.mark.django_db
def test_operationalreporting_drill_path_choices():
    """Verify choice keys on ReportDrillPath model."""
    target_types = _operationalreporting_choice_keys(ReportDrillPath.TARGET_TYPE_CHOICES)
    assert "subreport" in target_types
    assert "operational_report" in target_types
    assert "erp_record_url" in target_types


@pytest.mark.django_db
def test_operationalreporting_drill_path_badges(tenant_a):
    """Test badge_target_type property for ReportDrillPath."""
    path = ReportDrillPath(tenant=tenant_a, source_field="item_id", drill_label="Inspect")

    target_type_mapping = {
        "subreport": "badge-info",
        "operational_report": "badge-slate",
        "erp_record_url": "badge-green",
    }
    for ttype, expected_badge in target_type_mapping.items():
        path.target_type = ttype
        assert path.badge_target_type == expected_badge
        _operationalreporting_assert_valid_badge(path.badge_target_type)

    path.target_type = "unknown_target"
    assert path.badge_target_type == "badge-slate"
    _operationalreporting_assert_valid_badge(path.badge_target_type)


# ---------------------------------------------------------------------------
# 5. Multi-Tenancy Isolation QuerySet Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_tenant_isolation_querysets(tenant_a, tenant_b, admin_user, admin_user_b):
    """Verify strict tenant isolation across all four models in querysets."""
    # Create Tenant A records
    rpt_a = ReportDefinition.objects.create(
        tenant=tenant_a,
        name="Acme Operational Overview",
        slug="acme-operational-overview",
        created_by=admin_user,
    )
    param_a = ReportParameter.objects.create(
        tenant=tenant_a,
        report=rpt_a,
        parameter_name="acme_scope",
        prompt_label="Acme Scope",
    )
    exec_a = ReportExecution.objects.create(
        tenant=tenant_a,
        report=rpt_a,
        executed_by=admin_user,
    )
    drill_a = ReportDrillPath.objects.create(
        tenant=tenant_a,
        source_report=rpt_a,
        source_field="acme_key",
        drill_label="Drill Acme Key",
    )

    # Create Tenant B records
    rpt_b = ReportDefinition.objects.create(
        tenant=tenant_b,
        name="Globex Operational Overview",
        slug="globex-operational-overview",
        created_by=admin_user_b,
    )
    param_b = ReportParameter.objects.create(
        tenant=tenant_b,
        report=rpt_b,
        parameter_name="globex_scope",
        prompt_label="Globex Scope",
    )
    exec_b = ReportExecution.objects.create(
        tenant=tenant_b,
        report=rpt_b,
        executed_by=admin_user_b,
    )
    drill_b = ReportDrillPath.objects.create(
        tenant=tenant_b,
        source_report=rpt_b,
        source_field="globex_key",
        drill_label="Drill Globex Key",
    )

    # Querysets for Tenant A must strictly exclude Tenant B
    a_reports = list(ReportDefinition.objects.filter(tenant=tenant_a))
    assert rpt_a in a_reports
    assert rpt_b not in a_reports

    a_params = list(ReportParameter.objects.filter(tenant=tenant_a))
    assert param_a in a_params
    assert param_b not in a_params

    a_execs = list(ReportExecution.objects.filter(tenant=tenant_a))
    assert exec_a in a_execs
    assert exec_b not in a_execs

    a_drills = list(ReportDrillPath.objects.filter(tenant=tenant_a))
    assert drill_a in a_drills
    assert drill_b not in a_drills

    # Querysets for Tenant B must strictly exclude Tenant A
    b_reports = list(ReportDefinition.objects.filter(tenant=tenant_b))
    assert rpt_b in b_reports
    assert rpt_a not in b_reports

    b_params = list(ReportParameter.objects.filter(tenant=tenant_b))
    assert param_b in b_params
    assert param_a not in b_params

    b_execs = list(ReportExecution.objects.filter(tenant=tenant_b))
    assert exec_b in b_execs
    assert exec_a not in b_execs

    b_drills = list(ReportDrillPath.objects.filter(tenant=tenant_b))
    assert drill_b in b_drills
    assert drill_a not in b_drills
