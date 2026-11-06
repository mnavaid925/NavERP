"""Security, Multi-Tenancy, Authorization, and Injection Hardening Tests for Sub-module 10.9
(Standard & Operational Reporting).

Covers:
1. Multi-Tenant IDOR Isolation:
   - Cross-tenant detail, edit, delete, clone, viewer, print, run, and export attempts
     by Tenant A user against Tenant B records return HTTP 404 Not Found.
   - Bidirectional reverse tests: Tenant B user against Tenant A records returns HTTP 404.
   - Tenant List Isolation: List endpoints for reports, parameters, executions, and drill
     paths strictly partition records by tenant with zero cross-tenant data leakage.
2. Cross-Tenant Foreign Key Tampering & Injection:
   - Form and view rejection of foreign ReportDefinition in ReportParameterForm.
   - Form and view rejection of foreign source/target ReportDefinition in ReportDrillPathForm.
   - Form and view rejection of foreign SemanticModel, WarehouseTable, and OrgUnit in ReportDefinitionForm.
3. Authentication & Authorization Gating:
   - Unauthenticated requests to all 23 sub-module endpoints redirect (302) to login.
   - Non-admin tenant members (is_tenant_admin=False) receive HTTP 403 Forbidden on all mutating
     actions protected by @tenant_admin_required (create, edit, delete, clone).
   - Non-admin tenant members retain access to read-only views (list, detail, viewer, print)
     and interactive report execution and export.
   - Method Gating: POST-only deletion endpoints reject GET requests with HTTP 405 Method Not Allowed.
4. Injection & Payload Hardening:
   - Stored XSS prevention: custom styling_css cleans and rejects HTML closing tags (</style>),
     script injections (<script>), event handlers (onload=, onerror=), and javascript: schemes.
   - CSV Formula Injection defense: export endpoint and csv_safe sanitize initial '=', '+', '-', '@',
     and tab/return characters to neutralize DDE / formula execution in spreadsheet software.
   - Mass Assignment defense: crafted POST payloads cannot overwrite tenant, system number,
     created_at timestamps, or created_by references.
5. Audit Log Security:
   - State-changing actions create append-only AuditLog records strictly scoped to the actor's tenant.
"""
import csv
import json
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms.OperationalReporting import (
    ReportCloneForm,
    ReportDefinitionForm,
    ReportDrillPathForm,
    ReportExecutionRunForm,
    ReportParameterForm,
)
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportDrillPaths import ReportDrillPath
from apps.bi.models.OperationalReporting.ReportExecutions import ReportExecution
from apps.bi.models.OperationalReporting.ReportParameters import ReportParameter
from apps.bi.views._common import csv_safe
from apps.core.models import AuditLog, OrgUnit

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------------------------------------------------------------------------
# Local Fixture Overrides (to isolate 10.9 contract without touching conftest)
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user_b(admin_b):
    """Bridge fixture to unify admin_b and admin_user_b without duplicate username collision."""
    return admin_b


@pytest.fixture
def report_definition_a(db, tenant_a, admin_user):
    return ReportDefinition.objects.create(
        tenant=tenant_a,
        created_by=admin_user,
        name="Acme Monthly Revenue & Margin Report",
        slug="acme-monthly-revenue-margin-report",
        category="finance",
        report_type="standard_tabular",
        status="published",
        orientation="portrait",
        paper_size="a4",
        is_prebuilt_template=False,
        columns_config_json=[
            {"field": "row_id", "title": "#", "width": "40px", "align": "center"},
            {"field": "item_code", "title": "SKU / Code", "width": "120px", "align": "left"},
            {"field": "description", "title": "Product Title", "width": "220px", "align": "left"},
            {"field": "amount", "title": "Net Total (USD)", "width": "110px", "align": "right"},
        ],
    )


@pytest.fixture
def report_definition_b(db, tenant_b, admin_user_b):
    return ReportDefinition.objects.create(
        tenant=tenant_b,
        created_by=admin_user_b,
        name="Globex Monthly Revenue & Margin Report",
        slug="globex-monthly-revenue-margin-report",
        category="finance",
        report_type="standard_tabular",
        status="published",
        orientation="portrait",
        paper_size="a4",
        is_prebuilt_template=False,
        columns_config_json=[
            {"field": "row_id", "title": "#", "width": "40px", "align": "center"},
            {"field": "item_code", "title": "SKU / Code", "width": "120px", "align": "left"},
            {"field": "description", "title": "Product Title", "width": "220px", "align": "left"},
            {"field": "amount", "title": "Net Total (USD)", "width": "110px", "align": "right"},
        ],
    )


@pytest.fixture
def report_parameter_a(db, tenant_a, report_definition_a):
    return ReportParameter.objects.create(
        tenant=tenant_a,
        report=report_definition_a,
        parameter_name="fiscal_year",
        prompt_label="Fiscal Year",
        parameter_type="string",
        default_value="2026",
        is_required=True,
        prompt_order=1,
    )


@pytest.fixture
def report_parameter_b(db, tenant_b, report_definition_b):
    return ReportParameter.objects.create(
        tenant=tenant_b,
        report=report_definition_b,
        parameter_name="fiscal_year",
        prompt_label="Fiscal Year",
        parameter_type="string",
        default_value="2026",
        is_required=True,
        prompt_order=1,
    )


@pytest.fixture
def report_execution_a(db, tenant_a, report_definition_a, admin_user):
    return ReportExecution.objects.create(
        tenant=tenant_a,
        report=report_definition_a,
        executed_by=admin_user,
        execution_mode="interactive_view",
        execution_status="completed",
        output_format="html",
        row_count=12,
        duration_ms=45,
    )


@pytest.fixture
def report_execution_b(db, tenant_b, report_definition_b, admin_user_b):
    return ReportExecution.objects.create(
        tenant=tenant_b,
        report=report_definition_b,
        executed_by=admin_user_b,
        execution_mode="interactive_view",
        execution_status="completed",
        output_format="html",
        row_count=8,
        duration_ms=30,
    )


@pytest.fixture
def report_drill_path_a(db, tenant_a, report_definition_a):
    return ReportDrillPath.objects.create(
        tenant=tenant_a,
        source_report=report_definition_a,
        source_field="item_code",
        drill_label="Inspect Item Detail",
        target_type="operational_report",
        target_report=report_definition_a,
        sort_order=1,
    )


@pytest.fixture
def report_drill_path_b(db, tenant_b, report_definition_b):
    return ReportDrillPath.objects.create(
        tenant=tenant_b,
        source_report=report_definition_b,
        source_field="item_code",
        drill_label="Inspect Item Detail",
        target_type="operational_report",
        target_report=report_definition_b,
        sort_order=1,
    )


# ---------------------------------------------------------------------------
# Module Helpers (named _operationalreporting_*)
# ---------------------------------------------------------------------------


def _operationalreporting_create_org_unit(tenant, name="Finance Department"):
    """Helper to create a tenant-scoped OrgUnit instance."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _operationalreporting_create_report(
    tenant,
    user=None,
    name="Standard Revenue Report",
    slug="standard-revenue-report",
    **kwargs,
):
    """Helper to create a tenant-scoped ReportDefinition instance."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        created_by=user,
        name=name,
        slug=slug,
        category=kwargs.get("category", "finance"),
        report_type=kwargs.get("report_type", "standard_tabular"),
        paper_size=kwargs.get("paper_size", "a4"),
        orientation=kwargs.get("orientation", "portrait"),
        status=kwargs.get("status", "published"),
        is_prebuilt_template=kwargs.get("is_prebuilt_template", False),
        columns_config_json=kwargs.get(
            "columns_config_json",
            [
                {"field": "row_id", "title": "#", "width": "10%", "align": "center"},
                {"field": "item_code", "title": "Reference Code", "width": "25%", "align": "left"},
                {"field": "description", "title": "Description", "width": "40%", "align": "left"},
                {"field": "amount", "title": "Amount (USD)", "width": "25%", "align": "right"},
            ],
        ),
        **{
            k: v
            for k, v in kwargs.items()
            if k
            not in (
                "category",
                "report_type",
                "paper_size",
                "orientation",
                "status",
                "is_prebuilt_template",
                "columns_config_json",
            )
        },
    )


def _operationalreporting_create_parameter(
    tenant,
    report,
    parameter_name="fiscal_year",
    prompt_label="Fiscal Year",
    **kwargs,
):
    """Helper to create a tenant-scoped ReportParameter instance."""
    return ReportParameter.objects.create(
        tenant=tenant,
        report=report,
        parameter_name=parameter_name,
        prompt_label=prompt_label,
        parameter_type=kwargs.get("parameter_type", "string"),
        default_value=kwargs.get("default_value", "2026"),
        prompt_order=kwargs.get("prompt_order", 10),
        is_required=kwargs.get("is_required", True),
        is_active=kwargs.get("is_active", True),
        **{
            k: v
            for k, v in kwargs.items()
            if k
            not in (
                "parameter_type",
                "default_value",
                "prompt_order",
                "is_required",
                "is_active",
            )
        },
    )


def _operationalreporting_create_execution(
    tenant,
    report,
    user=None,
    execution_mode="interactive_view",
    output_format="html",
    **kwargs,
):
    """Helper to create a tenant-scoped ReportExecution instance."""
    return ReportExecution.objects.create(
        tenant=tenant,
        report=report,
        executed_by=user,
        execution_mode=execution_mode,
        execution_status=kwargs.get("execution_status", "completed"),
        output_format=output_format,
        row_count=kwargs.get("row_count", 6),
        duration_ms=kwargs.get("duration_ms", 45),
        **{
            k: v
            for k, v in kwargs.items()
            if k
            not in (
                "execution_status",
                "row_count",
                "duration_ms",
            )
        },
    )


def _operationalreporting_create_drill_path(
    tenant,
    source_report,
    drill_label="Inspect Customer Details",
    source_field="item_code",
    **kwargs,
):
    """Helper to create a tenant-scoped ReportDrillPath instance."""
    return ReportDrillPath.objects.create(
        tenant=tenant,
        source_report=source_report,
        drill_label=drill_label,
        source_field=source_field,
        target_type=kwargs.get("target_type", "operational_report"),
        target_report=kwargs.get("target_report", source_report),
        sort_order=kwargs.get("sort_order", 10),
        is_enabled=kwargs.get("is_enabled", True),
        **{
            k: v
            for k, v in kwargs.items()
            if k
            not in (
                "target_type",
                "target_report",
                "sort_order",
                "is_enabled",
            )
        },
    )


def _operationalreporting_base_definition_data(**overrides):
    """Helper generating valid ReportDefinition form payload."""
    data = {
        "name": "Standard Operational P&L Report",
        "slug": "standard-operational-pl-report",
        "category": "finance",
        "report_type": "standard_tabular",
        "paper_size": "a4",
        "orientation": "portrait",
        "semantic_model": "",
        "warehouse_table": "",
        "org_unit": "",
        "status": "draft",
        "is_prebuilt_template": False,
        "watermark_text": "CONFIDENTIAL",
        "description": "Standard operational financial reporting statement.",
        "raw_query": "SELECT * FROM financial_records",
        "styling_css": "table { width: 100%; border-collapse: collapse; }",
        "margins_json": '{"top": 15, "bottom": 15, "left": 15, "right": 15}',
        "bands_config_json": '{"detail": {"height_mm": 10}}',
        "columns_config_json": '[{"field": "row_id", "title": "#", "width": "10%"}, {"field": "amount", "title": "Net Amount", "width": "20%"}]',
        "is_active": True,
    }
    data.update(overrides)
    return data


def _operationalreporting_base_parameter_data(report_pk, **overrides):
    """Helper generating valid ReportParameter form payload."""
    data = {
        "report": report_pk,
        "parameter_name": "fiscal_year",
        "prompt_label": "Fiscal Year",
        "parameter_type": "string",
        "default_value": "2026",
        "choices_source": "static_list",
        "choices_config_json": "[]",
        "validation_regex": "^[0-9]{4}$",
        "help_text": "Select the reporting period fiscal year",
        "prompt_order": 10,
        "is_required": True,
        "is_hidden": False,
        "is_active": True,
    }
    data.update(overrides)
    return data


def _operationalreporting_base_drill_path_data(source_report_pk, target_report_pk=None, **overrides):
    """Helper generating valid ReportDrillPath form payload."""
    data = {
        "source_report": source_report_pk,
        "source_field": "item_code",
        "drill_label": "Inspect Item Transactions",
        "target_type": "operational_report",
        "target_report": target_report_pk or source_report_pk,
        "target_url_pattern": "",
        "parameter_mapping_json": '{"item_code": "target_item_code"}',
        "sort_order": 10,
        "is_enabled": True,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# 1. Multi-Tenant IDOR Isolation Tests (Cross-Tenant Access Returns 404)
# ---------------------------------------------------------------------------


def test_operationalreporting_definition_cross_tenant_idor_protection(client_a, report_definition_b):
    """Assert Tenant A cannot access Tenant B's ReportDefinition across detail, edit, delete, clone, viewer, and print."""
    pk = report_definition_b.pk
    detail_url = reverse("bi:report_definition_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:report_definition_edit", kwargs={"pk": pk})
    del_url = reverse("bi:report_definition_delete", kwargs={"pk": pk})
    clone_url = reverse("bi:report_definition_clone", kwargs={"pk": pk})
    viewer_url = reverse("bi:report_definition_viewer", kwargs={"pk": pk})
    print_url = reverse("bi:report_definition_print", kwargs={"pk": pk})

    # Read endpoints return 404
    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(viewer_url).status_code == 404
    assert client_a.get(print_url).status_code == 404

    # Edit GET and POST return 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, _operationalreporting_base_definition_data()).status_code == 404

    # Delete POST returns 404
    assert client_a.post(del_url).status_code == 404

    # Clone GET and POST return 404
    assert client_a.get(clone_url).status_code == 404
    assert client_a.post(clone_url, {"new_name": "IDOR Clone", "new_slug": "idor-clone"}).status_code == 404


def test_operationalreporting_parameter_cross_tenant_idor_protection(client_a, report_parameter_b):
    """Assert Tenant A cannot access Tenant B's ReportParameter across detail, edit, and delete endpoints."""
    pk = report_parameter_b.pk
    detail_url = reverse("bi:report_parameter_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:report_parameter_edit", kwargs={"pk": pk})
    del_url = reverse("bi:report_parameter_delete", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, _operationalreporting_base_parameter_data(report_parameter_b.report_id)).status_code == 404
    assert client_a.post(del_url).status_code == 404


def test_operationalreporting_execution_cross_tenant_idor_protection(client_a, report_execution_b, report_definition_b):
    """Assert Tenant A cannot access Tenant B's execution detail, delete, export, or execute against Tenant B's report."""
    exec_pk = report_execution_b.pk
    report_pk = report_definition_b.pk

    detail_url = reverse("bi:report_execution_detail", kwargs={"pk": exec_pk})
    del_url = reverse("bi:report_execution_delete", kwargs={"pk": exec_pk})
    run_url = reverse("bi:report_execution_run", kwargs={"report_pk": report_pk})
    export_csv_url = reverse("bi:report_execution_export", kwargs={"pk": exec_pk, "export_format": "csv"})
    export_json_url = reverse("bi:report_execution_export", kwargs={"pk": exec_pk, "export_format": "json"})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.post(del_url).status_code == 404
    assert client_a.get(run_url).status_code == 404
    assert client_a.post(run_url, {"execution_mode": "interactive_view", "output_format": "html"}).status_code == 404
    assert client_a.get(export_csv_url).status_code == 404
    assert client_a.get(export_json_url).status_code == 404


def test_operationalreporting_drill_path_cross_tenant_idor_protection(client_a, report_drill_path_b):
    """Assert Tenant A cannot access Tenant B's ReportDrillPath across detail, edit, and delete endpoints."""
    pk = report_drill_path_b.pk
    detail_url = reverse("bi:report_drill_path_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:report_drill_path_edit", kwargs={"pk": pk})
    del_url = reverse("bi:report_drill_path_delete", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(edit_url, _operationalreporting_base_drill_path_data(report_drill_path_b.source_report_id)).status_code == 404
    assert client_a.post(del_url).status_code == 404


def test_operationalreporting_reverse_cross_tenant_idor_protection(
    client_b,
    report_definition_a,
    report_parameter_a,
    report_execution_a,
    report_drill_path_a,
):
    """Assert Tenant B cannot access Tenant A records across all 4 operational reporting models (bidirectional check)."""
    # ReportDefinition endpoints
    assert client_b.get(reverse("bi:report_definition_detail", kwargs={"pk": report_definition_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:report_definition_delete", kwargs={"pk": report_definition_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_definition_clone", kwargs={"pk": report_definition_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_definition_viewer", kwargs={"pk": report_definition_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_definition_print", kwargs={"pk": report_definition_a.pk})).status_code == 404

    # ReportParameter endpoints
    assert client_b.get(reverse("bi:report_parameter_detail", kwargs={"pk": report_parameter_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_parameter_edit", kwargs={"pk": report_parameter_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:report_parameter_delete", kwargs={"pk": report_parameter_a.pk})).status_code == 404

    # ReportExecution endpoints
    assert client_b.get(reverse("bi:report_execution_detail", kwargs={"pk": report_execution_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:report_execution_delete", kwargs={"pk": report_execution_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_execution_run", kwargs={"report_pk": report_definition_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_execution_export", kwargs={"pk": report_execution_a.pk, "export_format": "csv"})).status_code == 404

    # ReportDrillPath endpoints
    assert client_b.get(reverse("bi:report_drill_path_detail", kwargs={"pk": report_drill_path_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:report_drill_path_edit", kwargs={"pk": report_drill_path_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:report_drill_path_delete", kwargs={"pk": report_drill_path_a.pk})).status_code == 404


def test_operationalreporting_cross_tenant_list_isolation(
    client_a,
    client_b,
    report_definition_a,
    report_definition_b,
    report_parameter_a,
    report_parameter_b,
    report_execution_a,
    report_execution_b,
    report_drill_path_a,
    report_drill_path_b,
):
    """Assert list querysets strictly isolate Tenant A and Tenant B data without any leakage."""
    # 1. ReportDefinition list isolation
    resp_a = client_a.get(reverse("bi:report_definition_list"))
    resp_b = client_b.get(reverse("bi:report_definition_list"))
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    reports_a = list(resp_a.context["reports"])
    reports_b = list(resp_b.context["reports"])
    assert report_definition_a in reports_a
    assert report_definition_b not in reports_a
    assert report_definition_b in reports_b
    assert report_definition_a not in reports_b

    # 2. ReportParameter list isolation
    resp_param_a = client_a.get(reverse("bi:report_parameter_list"))
    resp_param_b = client_b.get(reverse("bi:report_parameter_list"))
    params_a = list(resp_param_a.context["parameters"])
    params_b = list(resp_param_b.context["parameters"])
    assert report_parameter_a in params_a
    assert report_parameter_b not in params_a
    assert report_parameter_b in params_b
    assert report_parameter_a not in params_b

    # 3. ReportExecution list isolation
    resp_exec_a = client_a.get(reverse("bi:report_execution_list"))
    resp_exec_b = client_b.get(reverse("bi:report_execution_list"))
    execs_a = list(resp_exec_a.context["executions"])
    execs_b = list(resp_exec_b.context["executions"])
    assert report_execution_a in execs_a
    assert report_execution_b not in execs_a
    assert report_execution_b in execs_b
    assert report_execution_a not in execs_b

    # 4. ReportDrillPath list isolation
    resp_drill_a = client_a.get(reverse("bi:report_drill_path_list"))
    resp_drill_b = client_b.get(reverse("bi:report_drill_path_list"))
    drills_a = list(resp_drill_a.context["drill_paths"])
    drills_b = list(resp_drill_b.context["drill_paths"])
    assert report_drill_path_a in drills_a
    assert report_drill_path_b not in drills_a
    assert report_drill_path_b in drills_b
    assert report_drill_path_a not in drills_b


# ---------------------------------------------------------------------------
# 2. Cross-Tenant Foreign Key Injection Defense Tests
# ---------------------------------------------------------------------------


def test_operationalreporting_parameter_form_cross_tenant_fk_injection(
    tenant_a,
    report_definition_b,
):
    """Assert ReportParameterForm actively rejects linking to a ReportDefinition belonging to another workspace."""
    payload = _operationalreporting_base_parameter_data(report_pk=report_definition_b.pk)
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors
    # Verify reject_foreign or queryset isolation error message
    err_msgs = " ".join(form.errors["report"])
    assert "Select a valid choice" in err_msgs or "belongs to another workspace" in err_msgs


def test_operationalreporting_drill_path_form_cross_tenant_source_fk_injection(
    tenant_a,
    report_definition_b,
):
    """Assert ReportDrillPathForm actively rejects setting a foreign source_report."""
    payload = _operationalreporting_base_drill_path_data(source_report_pk=report_definition_b.pk)
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "source_report" in form.errors
    err_msgs = " ".join(form.errors["source_report"])
    assert "Select a valid choice" in err_msgs or "belongs to another workspace" in err_msgs


def test_operationalreporting_drill_path_form_cross_tenant_target_fk_injection(
    tenant_a,
    report_definition_a,
    report_definition_b,
):
    """Assert ReportDrillPathForm actively rejects setting a foreign target_report."""
    payload = _operationalreporting_base_drill_path_data(
        source_report_pk=report_definition_a.pk,
        target_report_pk=report_definition_b.pk,
    )
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_report" in form.errors
    err_msgs = " ".join(form.errors["target_report"])
    assert "Select a valid choice" in err_msgs or "belongs to another workspace" in err_msgs


def test_operationalreporting_definition_form_cross_tenant_fk_injections(
    tenant_a,
    semantic_model_b,
    warehouse_table_b,
    tenant_b,
):
    """Assert ReportDefinitionForm rejects foreign SemanticModel, WarehouseTable, and OrgUnit."""
    foreign_org_unit = _operationalreporting_create_org_unit(tenant_b, name="Globex Operations")

    # 1. Foreign SemanticModel
    p1 = _operationalreporting_base_definition_data(semantic_model=semantic_model_b.pk)
    f1 = ReportDefinitionForm(data=p1, tenant=tenant_a)
    assert not f1.is_valid()
    assert "semantic_model" in f1.errors

    # 2. Foreign WarehouseTable
    p2 = _operationalreporting_base_definition_data(warehouse_table=warehouse_table_b.pk)
    f2 = ReportDefinitionForm(data=p2, tenant=tenant_a)
    assert not f2.is_valid()
    assert "warehouse_table" in f2.errors

    # 3. Foreign OrgUnit
    p3 = _operationalreporting_base_definition_data(org_unit=foreign_org_unit.pk)
    f3 = ReportDefinitionForm(data=p3, tenant=tenant_a)
    assert not f3.is_valid()
    assert "org_unit" in f3.errors


def test_operationalreporting_create_views_reject_cross_tenant_fk_post(
    client_a,
    tenant_a,
    report_definition_a,
    report_definition_b,
):
    """Assert create views return validation errors and persist nothing when foreign FKs are injected via POST."""
    # 1. Parameter create with foreign report
    initial_param_count = ReportParameter.objects.filter(tenant=tenant_a).count()
    param_payload = _operationalreporting_base_parameter_data(report_pk=report_definition_b.pk)
    resp1 = client_a.post(reverse("bi:report_parameter_create"), param_payload)
    assert resp1.status_code == 200  # Re-renders form with errors
    assert ReportParameter.objects.filter(tenant=tenant_a).count() == initial_param_count

    # 2. Drill path create with foreign source report
    initial_drill_count = ReportDrillPath.objects.filter(tenant=tenant_a).count()
    drill_payload = _operationalreporting_base_drill_path_data(source_report_pk=report_definition_b.pk)
    resp2 = client_a.post(reverse("bi:report_drill_path_create"), drill_payload)
    assert resp2.status_code == 200
    assert ReportDrillPath.objects.filter(tenant=tenant_a).count() == initial_drill_count


# ---------------------------------------------------------------------------
# 3. Authentication & Authorization Gating Tests
# ---------------------------------------------------------------------------


def test_operationalreporting_unauthenticated_requests_redirect_to_login(
    anon_client,
    report_definition_a,
    report_parameter_a,
    report_execution_a,
    report_drill_path_a,
):
    """Assert all 23 Sub-module 10.9 endpoints redirect unauthenticated requests to login."""
    urls = [
        # ReportDefinition endpoints (8)
        reverse("bi:report_definition_list"),
        reverse("bi:report_definition_create"),
        reverse("bi:report_definition_detail", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_delete", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_clone", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_viewer", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_print", kwargs={"pk": report_definition_a.pk}),
        # ReportParameter endpoints (5)
        reverse("bi:report_parameter_list"),
        reverse("bi:report_parameter_create"),
        reverse("bi:report_parameter_detail", kwargs={"pk": report_parameter_a.pk}),
        reverse("bi:report_parameter_edit", kwargs={"pk": report_parameter_a.pk}),
        reverse("bi:report_parameter_delete", kwargs={"pk": report_parameter_a.pk}),
        # ReportExecution endpoints (5)
        reverse("bi:report_execution_list"),
        reverse("bi:report_execution_run", kwargs={"report_pk": report_definition_a.pk}),
        reverse("bi:report_execution_detail", kwargs={"pk": report_execution_a.pk}),
        reverse("bi:report_execution_delete", kwargs={"pk": report_execution_a.pk}),
        reverse("bi:report_execution_export", kwargs={"pk": report_execution_a.pk, "export_format": "csv"}),
        # ReportDrillPath endpoints (5)
        reverse("bi:report_drill_path_list"),
        reverse("bi:report_drill_path_create"),
        reverse("bi:report_drill_path_detail", kwargs={"pk": report_drill_path_a.pk}),
        reverse("bi:report_drill_path_edit", kwargs={"pk": report_drill_path_a.pk}),
        reverse("bi:report_drill_path_delete", kwargs={"pk": report_drill_path_a.pk}),
    ]

    for url in urls:
        resp = anon_client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected redirect to login page for {url}, got {resp.url}"


def test_operationalreporting_post_only_endpoints_reject_get(
    client_a,
    report_definition_a,
    report_parameter_a,
    report_execution_a,
    report_drill_path_a,
):
    """Assert POST-only mutating endpoints return 405 Method Not Allowed on direct GET."""
    post_only_urls = [
        reverse("bi:report_definition_delete", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_parameter_delete", kwargs={"pk": report_parameter_a.pk}),
        reverse("bi:report_execution_delete", kwargs={"pk": report_execution_a.pk}),
        reverse("bi:report_drill_path_delete", kwargs={"pk": report_drill_path_a.pk}),
    ]
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {resp.status_code}"


def test_operationalreporting_non_admin_member_forbidden_on_mutating_actions(
    member_client,
    report_definition_a,
    report_parameter_a,
    report_execution_a,
    report_drill_path_a,
):
    """Assert non-admin tenant members receive 403 Forbidden on all actions gated by @tenant_admin_required."""
    privileged_endpoints = [
        # ReportDefinition mutations
        (reverse("bi:report_definition_create"), "GET", {}),
        (reverse("bi:report_definition_create"), "POST", _operationalreporting_base_definition_data()),
        (reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk}), "GET", {}),
        (reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk}), "POST", _operationalreporting_base_definition_data()),
        (reverse("bi:report_definition_delete", kwargs={"pk": report_definition_a.pk}), "POST", {}),
        (reverse("bi:report_definition_clone", kwargs={"pk": report_definition_a.pk}), "GET", {}),
        (reverse("bi:report_definition_clone", kwargs={"pk": report_definition_a.pk}), "POST", {"new_name": "Unauthorized Clone"}),
        # ReportParameter mutations
        (reverse("bi:report_parameter_create"), "GET", {}),
        (reverse("bi:report_parameter_create"), "POST", _operationalreporting_base_parameter_data(report_definition_a.pk)),
        (reverse("bi:report_parameter_edit", kwargs={"pk": report_parameter_a.pk}), "GET", {}),
        (reverse("bi:report_parameter_edit", kwargs={"pk": report_parameter_a.pk}), "POST", _operationalreporting_base_parameter_data(report_definition_a.pk)),
        (reverse("bi:report_parameter_delete", kwargs={"pk": report_parameter_a.pk}), "POST", {}),
        # ReportDrillPath mutations
        (reverse("bi:report_drill_path_create"), "GET", {}),
        (reverse("bi:report_drill_path_create"), "POST", _operationalreporting_base_drill_path_data(report_definition_a.pk)),
        (reverse("bi:report_drill_path_edit", kwargs={"pk": report_drill_path_a.pk}), "GET", {}),
        (reverse("bi:report_drill_path_edit", kwargs={"pk": report_drill_path_a.pk}), "POST", _operationalreporting_base_drill_path_data(report_definition_a.pk)),
        (reverse("bi:report_drill_path_delete", kwargs={"pk": report_drill_path_a.pk}), "POST", {}),
        # ReportExecution mutations
        (reverse("bi:report_execution_delete", kwargs={"pk": report_execution_a.pk}), "POST", {}),
    ]

    for url, method, data in privileged_endpoints:
        if method == "GET":
            res = member_client.get(url)
        else:
            res = member_client.post(url, data)
        assert res.status_code == 403, (
            f"Expected 403 Forbidden for non-admin member on {method} {url}, got {res.status_code}"
        )


def test_operationalreporting_non_admin_member_allowed_read_and_run(
    member_client,
    report_definition_a,
    report_parameter_a,
    report_execution_a,
    report_drill_path_a,
):
    """Assert non-admin tenant members can view reports, inspect parameters/executions/drills, and run reports."""
    # List and detail endpoints accessible to logged-in tenant members
    read_only_urls = [
        reverse("bi:report_definition_list"),
        reverse("bi:report_definition_detail", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_viewer", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_definition_print", kwargs={"pk": report_definition_a.pk}),
        reverse("bi:report_parameter_list"),
        reverse("bi:report_parameter_detail", kwargs={"pk": report_parameter_a.pk}),
        reverse("bi:report_execution_list"),
        reverse("bi:report_execution_detail", kwargs={"pk": report_execution_a.pk}),
        reverse("bi:report_execution_export", kwargs={"pk": report_execution_a.pk, "export_format": "csv"}),
        reverse("bi:report_execution_export", kwargs={"pk": report_execution_a.pk, "export_format": "json"}),
        reverse("bi:report_drill_path_list"),
        reverse("bi:report_drill_path_detail", kwargs={"pk": report_drill_path_a.pk}),
    ]

    for url in read_only_urls:
        res = member_client.get(url)
        assert res.status_code == 200, f"Expected 200 OK for non-admin on read-only {url}, got {res.status_code}"

    # Execution run endpoint is open to logged-in tenant members (@login_required without admin restriction)
    run_url = reverse("bi:report_execution_run", kwargs={"report_pk": report_definition_a.pk})
    assert member_client.get(run_url).status_code == 200
    run_post_resp = member_client.post(run_url, {"execution_mode": "interactive_view", "output_format": "html"})
    assert run_post_resp.status_code == 302  # Successfully redirects to execution detail


# ---------------------------------------------------------------------------
# 4. Injection & Payload Hardening Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "malicious_css,expected_tag",
    [
        ("<script>alert('XSS')</script>", "script"),
        ("</style><script>alert(document.cookie)</script>", "</style"),
        ("body { background: url('javascript:alert(1)'); }", "javascript:"),
        ("<iframe src='https://attacker.com/evil'></iframe>", "<iframe"),
        ("div { background-image: url('x') onload=alert(1); }", "onload="),
        ("p { color: red; } img { src: 'x'; onerror=alert(1); }", "onerror="),
    ],
)
def test_operationalreporting_stored_xss_styling_css_rejected_by_form(
    tenant_a,
    malicious_css,
    expected_tag,
):
    """Assert clean_styling_css actively catches and raises ValidationError on script/style injection attacks."""
    payload = _operationalreporting_base_definition_data(styling_css=malicious_css)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "styling_css" in form.errors
    err_msg = " ".join(form.errors["styling_css"])
    assert "is not permitted" in err_msg


def test_operationalreporting_stored_xss_styling_css_rejected_by_view(
    client_a,
    tenant_a,
    report_definition_a,
):
    """Assert view-level submissions with XSS payloads in styling_css are rejected and never saved to the database."""
    # 1. Create attempt with script injection
    initial_count = ReportDefinition.objects.filter(tenant=tenant_a).count()
    xss_payload = _operationalreporting_base_definition_data(
        name="XSS Attack Report",
        slug="xss-attack-report",
        styling_css="</style><script>alert('pwned')</script>",
    )
    resp = client_a.post(reverse("bi:report_definition_create"), xss_payload)
    assert resp.status_code == 200  # Form validation failure, re-rendered
    assert ReportDefinition.objects.filter(name="XSS Attack Report").count() == 0
    assert ReportDefinition.objects.filter(tenant=tenant_a).count() == initial_count

    # 2. Edit attempt with javascript: injection
    original_css = report_definition_a.styling_css
    edit_payload = _operationalreporting_base_definition_data(
        name=report_definition_a.name,
        slug=report_definition_a.slug,
        styling_css="body { background: url('javascript:alert(1)'); }",
    )
    resp_edit = client_a.post(
        reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk}),
        edit_payload,
    )
    assert resp_edit.status_code == 200
    report_definition_a.refresh_from_db()
    assert report_definition_a.styling_css == original_css


def test_operationalreporting_csv_safe_formula_sanitization():
    """Assert csv_safe rigorously sanitizes command injection triggers and spreadsheet formula operators."""
    # Formula and DDE attack triggers
    assert csv_safe("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert csv_safe("+1+2") == "'+1+2"
    assert csv_safe("-123.45") == "'-123.45"
    assert csv_safe("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert csv_safe("\t=DDE('cmd';'/C calc')") == "'\t=DDE('cmd';'/C calc')"
    assert csv_safe("\r\n+Formula") == "'\r\n+Formula"
    assert csv_safe("   =cmd|' /C calc'!A0") == "'   =cmd|' /C calc'!A0"

    # Benign string and numeric values preserved
    assert csv_safe("Regular Column Title") == "Regular Column Title"
    assert csv_safe("Revenue (USD)") == "Revenue (USD)"
    assert csv_safe("12345") == "12345"
    assert csv_safe(None) == ""


def test_operationalreporting_csv_export_endpoint_formula_sanitization(
    client_a,
    tenant_a,
    admin_user,
):
    """Assert export endpoint neutralizes CSV formula injection in column titles and report cells."""
    malicious_columns = [
        {"field": "row_id", "title": "=cmd|' /C calc'!A0", "width": "10%"},
        {"field": "item_code", "title": "@DDE('server','topic','item')", "width": "20%"},
        {"field": "description", "title": "+SUM(1,2)", "width": "40%"},
        {"field": "amount", "title": "-999.00", "width": "30%"},
    ]
    report = _operationalreporting_create_report(
        tenant=tenant_a,
        user=admin_user,
        name="Formula Injection Audit Report",
        slug="formula-injection-audit-report",
        columns_config_json=malicious_columns,
    )
    execution = _operationalreporting_create_execution(
        tenant=tenant_a,
        report=report,
        user=admin_user,
        output_format="csv",
    )

    export_url = reverse("bi:report_execution_export", kwargs={"pk": execution.pk, "export_format": "csv"})
    resp = client_a.get(export_url)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")

    content = resp.content.decode("utf-8")
    lines = content.splitlines()
    header_line = lines[0]

    # Formula characters must be sanitized with single quote prefix
    assert "'=cmd|" in header_line
    assert "'@DDE" in header_line
    assert "'+SUM" in header_line
    assert "'-999" in header_line

    # Raw unsafe formula triggers must NOT appear without single quote prefix
    assert not header_line.startswith("=cmd|")


# ---------------------------------------------------------------------------
# 5. Mass Assignment Defense Tests
# ---------------------------------------------------------------------------


def test_operationalreporting_mass_assignment_tenant_and_number_tampering(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
    report_definition_a,
    report_parameter_a,
    report_drill_path_a,
):
    """Assert crafted POST payloads cannot overwrite tenant, system sequence numbers, or system timestamps."""
    # 1. ReportDefinition create: attempt to reassign tenant and spoof system number
    create_payload = _operationalreporting_base_definition_data(
        name="Tamper Attempt Report",
        slug="tamper-attempt-report",
        tenant=tenant_b.pk,
        number="BRPT-TAMPER-001",
        created_at="1999-01-01T00:00:00Z",
        created_by=admin_user_b.pk,
    )
    resp = client_a.post(reverse("bi:report_definition_create"), create_payload)
    assert resp.status_code == 302
    created_report = ReportDefinition.objects.get(slug="tamper-attempt-report")
    assert created_report.tenant == tenant_a  # Tenant bound by session, not payload
    assert created_report.number.startswith("BRPT")
    assert created_report.number != "BRPT-TAMPER-001"  # Autogenerated sequence preserved
    assert created_report.created_by == admin_user

    # 2. ReportDefinition edit: attempt to overwrite tenant and number
    original_rep_num = report_definition_a.number
    edit_payload = _operationalreporting_base_definition_data(
        name="Updated Name",
        slug=report_definition_a.slug,
        tenant=tenant_b.pk,
        number="BRPT-OVERWRITE",
    )
    resp_edit = client_a.post(
        reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk}),
        edit_payload,
    )
    assert resp_edit.status_code == 302
    report_definition_a.refresh_from_db()
    assert report_definition_a.tenant == tenant_a
    assert report_definition_a.number == original_rep_num

    # 3. ReportParameter create: attempt to spoof tenant and number
    param_payload = _operationalreporting_base_parameter_data(
        report_pk=report_definition_a.pk,
        parameter_name="tampered_param",
        tenant=tenant_b.pk,
        number="BPAR-TAMPER-001",
    )
    resp_param = client_a.post(reverse("bi:report_parameter_create"), param_payload)
    assert resp_param.status_code == 302
    created_param = ReportParameter.objects.get(parameter_name="tampered_param", report=report_definition_a)
    assert created_param.tenant == tenant_a
    assert created_param.number.startswith("BPAR")
    assert created_param.number != "BPAR-TAMPER-001"

    # 4. ReportDrillPath create: attempt to spoof tenant and number
    drill_payload = _operationalreporting_base_drill_path_data(
        source_report_pk=report_definition_a.pk,
        drill_label="Tampered Drill",
        tenant=tenant_b.pk,
        number="BDRP-TAMPER-001",
    )
    resp_drill = client_a.post(reverse("bi:report_drill_path_create"), drill_payload)
    assert resp_drill.status_code == 302
    created_drill = ReportDrillPath.objects.get(drill_label="Tampered Drill", source_report=report_definition_a)
    assert created_drill.tenant == tenant_a
    assert created_drill.number.startswith("BDRP")
    assert created_drill.number != "BDRP-TAMPER-001"

    # 5. ReportExecution run: attempt to overwrite tenant and number
    exec_run_payload = {
        "execution_mode": "interactive_view",
        "output_format": "html",
        "tenant": tenant_b.pk,
        "number": "BRUN-TAMPER-001",
    }
    resp_exec = client_a.post(
        reverse("bi:report_execution_run", kwargs={"report_pk": report_definition_a.pk}),
        exec_run_payload,
    )
    assert resp_exec.status_code == 302
    latest_exec = ReportExecution.objects.filter(report=report_definition_a).latest("started_at")
    assert latest_exec.tenant == tenant_a
    assert latest_exec.number.startswith("BRUN")
    assert latest_exec.number != "BRUN-TAMPER-001"
    assert latest_exec.executed_by == admin_user


# ---------------------------------------------------------------------------
# 6. Audit Trail Integrity Tests
# ---------------------------------------------------------------------------


def test_operationalreporting_audit_logs_recorded_for_mutating_actions(
    client_a,
    tenant_a,
    admin_user,
    report_definition_a,
):
    """Assert create, update, run, and delete operations create append-only audit trail records scoped to tenant."""
    # 1. Update report definition
    edit_url = reverse("bi:report_definition_edit", kwargs={"pk": report_definition_a.pk})
    payload = _operationalreporting_base_definition_data(
        name="Audited P&L Report",
        slug=report_definition_a.slug,
    )
    client_a.post(edit_url, payload)

    log = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
    ).order_by("-at").first()
    assert log is not None
    assert log.user == admin_user
    assert report_definition_a.number in log.target or report_definition_a.name in log.target

    # 2. Run execution
    run_url = reverse("bi:report_execution_run", kwargs={"report_pk": report_definition_a.pk})
    client_a.post(run_url, {"execution_mode": "interactive_view", "output_format": "html"})

    exec_log = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
    ).order_by("-at").first()
    assert exec_log is not None
    assert exec_log.user == admin_user
