"""Unit tests for Sub-module 10.9 Standard & Operational Reporting views.

Views covered:
- ReportDefinition views: list, create, detail, edit, delete, clone, viewer, print
- ReportParameter views: list, create, detail, edit, delete
- ReportExecution views: list, run, detail, delete, export (csv, json)
- ReportDrillPath views: list, create, detail, edit, delete
"""
import json
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.bi.models import (
    ReportDefinition,
    ReportDrillPath,
    ReportExecution,
    ReportParameter,
)
from apps.core.models import AuditLog


# ---------------------------------------------------------------------------
# Module Helpers (named _operationalreporting_*)
# ---------------------------------------------------------------------------


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
        category=kwargs.get("category", "sales"),
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


# ---------------------------------------------------------------------------
# 1. ReportDefinition Views Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_definition_list_view(client_a, tenant_a, admin_user):
    """Test report definition list view with contract context keys and metric counts."""
    r1 = _operationalreporting_create_report(
        tenant=tenant_a,
        user=admin_user,
        name="Sales Performance Dashboard Report",
        slug="sales-perf-report",
        category="sales",
        status="published",
        is_prebuilt_template=False,
    )
    r2 = _operationalreporting_create_report(
        tenant=tenant_a,
        user=admin_user,
        name="Standard Prebuilt Profit and Loss",
        slug="standard-prebuilt-pl",
        category="finance",
        status="published",
        is_prebuilt_template=True,
    )

    url = reverse("bi:report_definition_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Assert view-template context contract
    assert "page_obj" in resp.context
    assert "reports" in resp.context
    assert "category_choices" in resp.context
    assert "type_choices" in resp.context
    assert "status_choices" in resp.context
    assert resp.context["total_count"] >= 2
    assert resp.context["published_count"] >= 2
    assert resp.context["prebuilt_count"] >= 1

    content = resp.content.decode("utf-8")
    assert r1.name in content
    assert r2.name in content


@pytest.mark.django_db
def test_operationalreporting_definition_list_search_and_filters(client_a, tenant_a, admin_user):
    """Test filtering by category, report_type, status, is_prebuilt, and search query ?q=."""
    r_finance = _operationalreporting_create_report(
        tenant=tenant_a,
        user=admin_user,
        name="Quarterly Financial Audit",
        slug="quarterly-financial-audit",
        category="finance",
        report_type="regulatory_filing",
        status="draft",
        is_prebuilt_template=True,
        description="Statutory reporting requirements",
    )
    r_sales = _operationalreporting_create_report(
        tenant=tenant_a,
        user=admin_user,
        name="Territory Sales Velocity",
        slug="territory-sales-velocity",
        category="sales",
        report_type="standard_tabular",
        status="published",
        is_prebuilt_template=False,
        description="Field sales velocity ledger",
    )

    url = reverse("bi:report_definition_list")

    # Filter by category
    resp_cat = client_a.get(f"{url}?category=finance")
    assert resp_cat.status_code == 200
    cat_names = [r.name for r in resp_cat.context["page_obj"]]
    assert r_finance.name in cat_names
    assert r_sales.name not in cat_names

    # Filter by report_type
    resp_type = client_a.get(f"{url}?report_type=regulatory_filing")
    assert resp_type.status_code == 200
    type_names = [r.name for r in resp_type.context["page_obj"]]
    assert r_finance.name in type_names
    assert r_sales.name not in type_names

    # Filter by status
    resp_status = client_a.get(f"{url}?status=draft")
    assert resp_status.status_code == 200
    status_names = [r.name for r in resp_status.context["page_obj"]]
    assert r_finance.name in status_names
    assert r_sales.name not in status_names

    # Filter by is_prebuilt
    resp_prebuilt = client_a.get(f"{url}?is_prebuilt=1")
    assert resp_prebuilt.status_code == 200
    pre_names = [r.name for r in resp_prebuilt.context["page_obj"]]
    assert r_finance.name in pre_names
    assert r_sales.name not in pre_names

    resp_not_prebuilt = client_a.get(f"{url}?is_prebuilt=0")
    assert resp_not_prebuilt.status_code == 200
    non_pre_names = [r.name for r in resp_not_prebuilt.context["page_obj"]]
    assert r_sales.name in non_pre_names
    assert r_finance.name not in non_pre_names

    # Search by ?q=
    resp_q = client_a.get(f"{url}?q=Velocity")
    assert resp_q.status_code == 200
    q_names = [r.name for r in resp_q.context["page_obj"]]
    assert r_sales.name in q_names
    assert r_finance.name not in q_names


@pytest.mark.django_db
def test_operationalreporting_definition_list_guarded_parameters(client_a, tenant_a, admin_user):
    """Test guarded non-numeric and out-of-range pagination (?page=999, ?page=invalid)."""
    _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_list")

    resp_invalid_page = client_a.get(f"{url}?page=invalid_page_str")
    assert resp_invalid_page.status_code == 200
    assert resp_invalid_page.context["page_obj"].number == 1

    resp_high_page = client_a.get(f"{url}?page=999")
    assert resp_high_page.status_code == 200
    assert resp_high_page.context["page_obj"].number == 1


@pytest.mark.django_db
def test_operationalreporting_definition_detail_view(client_a, tenant_a, admin_user):
    """Test report definition detail view contract: object instance, counts, and collections."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    p1 = _operationalreporting_create_parameter(tenant=tenant_a, report=report, prompt_order=1)
    p2 = _operationalreporting_create_parameter(
        tenant=tenant_a, report=report, parameter_name="department", prompt_label="Department", prompt_order=2
    )
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)
    exec1 = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)
    exec2 = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)

    url = reverse("bi:report_definition_detail", kwargs={"pk": report.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Assert view-template context keys and counts
    assert resp.context["report"] == report
    assert resp.context["parameters_count"] == 2
    assert len(resp.context["parameters"]) == 2
    assert resp.context["drill_paths_count"] == 1
    assert len(resp.context["drill_paths"]) == 1
    assert resp.context["total_executions_count"] == 2
    assert len(resp.context["executions"]) == 2
    assert "can_edit" in resp.context

    content = resp.content.decode("utf-8")
    assert report.name in content
    assert p1.prompt_label in content
    assert p2.prompt_label in content
    assert drill.drill_label in content


@pytest.mark.django_db
def test_operationalreporting_definition_create_view_get(client_a):
    """Test report definition create view GET renders form with is_edit=False."""
    url = reverse("bi:report_definition_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["report"] is None
    assert resp.context["is_edit"] is False


@pytest.mark.django_db
def test_operationalreporting_definition_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test report definition create view POST creates record, writes audit log, and redirects."""
    url = reverse("bi:report_definition_create")
    payload = {
        "name": "General Ledger Monthly Trial Balance",
        "slug": "gl-monthly-trial-balance",
        "category": "finance",
        "report_type": "standard_tabular",
        "paper_size": "a4",
        "orientation": "landscape",
        "status": "published",
        "is_prebuilt_template": False,
        "is_active": True,
        "description": "Standard balance verification ledger",
        "watermark_text": "OFFICIAL",
        "styling_css": "",
        "raw_query": "",
    }

    resp = client_a.post(url, data=payload, follow=False)
    assert resp.status_code == 302

    created = ReportDefinition.objects.get(tenant=tenant_a, slug="gl-monthly-trial-balance")
    assert created.name == "General Ledger Monthly Trial Balance"
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert created.orientation == "landscape"
    assert resp.url == reverse("bi:report_definition_detail", kwargs={"pk": created.pk})

    # Assert audit log
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-at").first()
    assert audit is not None
    assert str(created.pk) in str(audit.object_id) or "gl-monthly-trial-balance" in str(audit.changes)


@pytest.mark.django_db
def test_operationalreporting_definition_create_view_post_invalid(client_a, tenant_a):
    """Test report definition create view POST with missing required name re-renders form."""
    url = reverse("bi:report_definition_create")
    payload = {
        "name": "",  # invalid
        "slug": "empty-name-report",
        "category": "finance",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert "name" in resp.context["form"].errors
    assert not ReportDefinition.objects.filter(tenant=tenant_a, slug="empty-name-report").exists()


@pytest.mark.django_db
def test_operationalreporting_definition_edit_view_get(client_a, tenant_a, admin_user):
    """Test report definition edit view GET renders form with is_edit=True."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_edit", kwargs={"pk": report.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["report"] == report


@pytest.mark.django_db
def test_operationalreporting_definition_edit_view_post_valid(client_a, tenant_a, admin_user):
    """Test report definition edit view POST updates fields, writes audit log, and redirects."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_edit", kwargs={"pk": report.pk})
    payload = {
        "name": "Updated Operational Revenue Report",
        "slug": report.slug,
        "category": "sales",
        "report_type": "standard_tabular",
        "paper_size": "letter",
        "orientation": "landscape",
        "status": "published",
        "is_active": True,
        "description": "Updated detailed revenue scope",
    }

    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_definition_detail", kwargs={"pk": report.pk})

    report.refresh_from_db()
    assert report.name == "Updated Operational Revenue Report"
    assert report.paper_size == "letter"
    assert report.orientation == "landscape"

    # Assert audit log
    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_definition_edit_view_post_invalid(client_a, tenant_a, admin_user):
    """Test report definition edit view POST with invalid data re-renders form with errors."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_edit", kwargs={"pk": report.pk})
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_operationalreporting_definition_delete_view_get_rejected(client_a, tenant_a, admin_user):
    """Test report definition delete endpoint rejects GET requests with 405 MethodNotAllowed."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_delete", kwargs={"pk": report.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert ReportDefinition.objects.filter(pk=report.pk).exists()


@pytest.mark.django_db
def test_operationalreporting_definition_delete_view_post(client_a, tenant_a, admin_user):
    """Test report definition delete endpoint deletes object, writes audit log, and redirects."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_delete", kwargs={"pk": report.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_definition_list")
    assert not ReportDefinition.objects.filter(pk=report.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_definition_clone_view_get(client_a, tenant_a, admin_user):
    """Test clone view GET renders form with initial copy name."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_definition_clone", kwargs={"pk": report.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["source_report"] == report
    assert f"{report.name} (Copy)" in resp.context["form"].initial["new_name"]


@pytest.mark.django_db
def test_operationalreporting_definition_clone_view_post(client_a, tenant_a, admin_user):
    """Test clone view POST duplicates report, its active parameters, and drill paths."""
    source_report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    p1 = _operationalreporting_create_parameter(tenant=tenant_a, report=source_report, prompt_order=1)
    p2 = _operationalreporting_create_parameter(
        tenant=tenant_a, report=source_report, parameter_name="fiscal_month", prompt_label="Month", prompt_order=2
    )
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=source_report)

    url = reverse("bi:report_definition_clone", kwargs={"pk": source_report.pk})
    payload = {
        "new_name": "Executive Sales Clone 2026",
        "new_slug": "executive-sales-clone-2026",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    cloned = ReportDefinition.objects.get(tenant=tenant_a, slug="executive-sales-clone-2026")
    assert cloned.name == "Executive Sales Clone 2026"
    assert cloned.status == "draft"
    assert cloned.is_prebuilt_template is False
    assert resp.url == reverse("bi:report_definition_detail", kwargs={"pk": cloned.pk})

    # Assert duplicated parameters
    cloned_params = cloned.parameters.all()
    assert cloned_params.count() == 2
    assert set(cloned_params.values_list("parameter_name", flat=True)) == {"fiscal_year", "fiscal_month"}
    assert not cloned_params.filter(pk=p1.pk).exists()
    assert not cloned_params.filter(pk=p2.pk).exists()

    # Assert duplicated drill paths
    cloned_drills = cloned.source_drill_paths.all()
    assert cloned_drills.count() == 1
    assert cloned_drills.first().drill_label == drill.drill_label
    assert cloned_drills.first().pk != drill.pk

    # Assert audit log
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_definition_viewer_view(client_a, tenant_a, admin_user):
    """Test report viewer renders columns, evaluated rows, and applied parameters."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(
        tenant=tenant_a,
        report=report,
        parameter_name="fiscal_year",
        default_value="2026",
    )
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)

    url = reverse("bi:report_definition_viewer", kwargs={"pk": report.pk})
    resp = client_a.get(f"{url}?fiscal_year=2028")
    assert resp.status_code == 200

    assert resp.context["report"] == report
    assert len(resp.context["parameters"]) == 1
    assert resp.context["applied_params"]["fiscal_year"] == "2028"
    assert "columns" in resp.context
    assert "rows" in resp.context
    assert resp.context["row_count"] > 0
    assert resp.context["execution"] is None
    assert resp.context["is_print"] is False
    assert resp.context["duration_ms"] >= 1

    content = resp.content.decode("utf-8")
    assert report.name in content


@pytest.mark.django_db
def test_operationalreporting_definition_print_view(client_a, tenant_a, admin_user):
    """Test report print view contract: is_print=True, printed_at, columns, and rows."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    _operationalreporting_create_parameter(
        tenant=tenant_a,
        report=report,
        parameter_name="region",
        default_value="EMEA",
    )
    url = reverse("bi:report_definition_print", kwargs={"pk": report.pk})
    resp = client_a.get(f"{url}?region=APAC")
    assert resp.status_code == 200

    assert resp.context["report"] == report
    assert resp.context["is_print"] is True
    assert "printed_at" in resp.context
    assert resp.context["applied_params"]["region"] == "APAC"
    assert "columns" in resp.context
    assert "rows" in resp.context
    assert resp.context["row_count"] > 0


# ---------------------------------------------------------------------------
# 2. ReportParameter Views Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_parameter_list_view(client_a, tenant_a, admin_user):
    """Test parameter list view context contract: page_obj, type_choices, and reports."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    p = _operationalreporting_create_parameter(tenant=tenant_a, report=report)

    url = reverse("bi:report_parameter_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "page_obj" in resp.context
    assert "parameters" in resp.context
    assert "type_choices" in resp.context
    assert "reports" in resp.context
    assert p.prompt_label in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_operationalreporting_parameter_list_search_and_filters(client_a, tenant_a, admin_user):
    """Test parameter list filters by parameter_type, report, and query ?q=."""
    report1 = _operationalreporting_create_report(tenant=tenant_a, user=admin_user, name="Audit Report 1", slug="audit-1")
    report2 = _operationalreporting_create_report(tenant=tenant_a, user=admin_user, name="Audit Report 2", slug="audit-2")

    p_str = _operationalreporting_create_parameter(
        tenant=tenant_a,
        report=report1,
        parameter_name="customer_code",
        prompt_label="Customer Account Identifier",
        parameter_type="string",
    )
    p_date = _operationalreporting_create_parameter(
        tenant=tenant_a,
        report=report2,
        parameter_name="posting_date",
        prompt_label="General Ledger Posting Date",
        parameter_type="date",
    )

    url = reverse("bi:report_parameter_list")

    # Filter by parameter_type
    resp_type = client_a.get(f"{url}?parameter_type=date")
    assert resp_type.status_code == 200
    p_labels = [param.prompt_label for param in resp_type.context["page_obj"]]
    assert p_date.prompt_label in p_labels
    assert p_str.prompt_label not in p_labels

    # Filter by report
    resp_rep = client_a.get(f"{url}?report={report1.pk}")
    assert resp_rep.status_code == 200
    p_labels = [param.prompt_label for param in resp_rep.context["page_obj"]]
    assert p_str.prompt_label in p_labels
    assert p_date.prompt_label not in p_labels

    # Search query
    resp_q = client_a.get(f"{url}?q=Identifier")
    assert resp_q.status_code == 200
    p_labels = [param.prompt_label for param in resp_q.context["page_obj"]]
    assert p_str.prompt_label in p_labels
    assert p_date.prompt_label not in p_labels


@pytest.mark.django_db
def test_operationalreporting_parameter_list_guarded_parameters(client_a, tenant_a, admin_user):
    """Test parameter list handles non-numeric report filter and pagination safely."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    _operationalreporting_create_parameter(tenant=tenant_a, report=report)
    url = reverse("bi:report_parameter_list")

    resp_junk_report = client_a.get(f"{url}?report=not_a_digit")
    assert resp_junk_report.status_code == 200

    resp_junk_page = client_a.get(f"{url}?page=invalid_page")
    assert resp_junk_page.status_code == 200
    assert resp_junk_page.context["page_obj"].number == 1


@pytest.mark.django_db
def test_operationalreporting_parameter_detail_view(client_a, tenant_a, admin_user):
    """Test parameter detail view contract: parameter, report, can_edit."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(tenant=tenant_a, report=report)

    url = reverse("bi:report_parameter_detail", kwargs={"pk": param.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["parameter"] == param
    assert resp.context["report"] == report
    assert "can_edit" in resp.context
    assert param.prompt_label in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_operationalreporting_parameter_create_view_get(client_a, tenant_a, admin_user):
    """Test parameter create view GET with optional ?report= query pre-populating form."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_parameter_create")

    # Regular GET
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False

    # GET with ?report=<pk>
    resp_pre = client_a.get(f"{url}?report={report.pk}")
    assert resp_pre.status_code == 200
    assert resp_pre.context["form"].initial.get("report") == report


@pytest.mark.django_db
def test_operationalreporting_parameter_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test parameter create POST creates instance, writes audit log, and redirects."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_parameter_create")
    payload = {
        "report": report.pk,
        "parameter_name": "posting_period",
        "prompt_label": "Financial Posting Period",
        "parameter_type": "string",
        "default_value": "2026-11",
        "choices_source": "static_list",
        "prompt_order": 15,
        "is_required": True,
        "is_active": True,
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = ReportParameter.objects.get(tenant=tenant_a, report=report, parameter_name="posting_period")
    assert created.prompt_label == "Financial Posting Period"
    assert resp.url == reverse("bi:report_parameter_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_parameter_create_view_post_invalid(client_a, tenant_a, admin_user):
    """Test parameter create POST with missing prompt_label re-renders form with errors."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_parameter_create")
    payload = {
        "report": report.pk,
        "parameter_name": "missing_label_param",
        "prompt_label": "",  # invalid
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "prompt_label" in resp.context["form"].errors


@pytest.mark.django_db
def test_operationalreporting_parameter_edit_view_get(client_a, tenant_a, admin_user):
    """Test parameter edit view GET renders form with is_edit=True."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(tenant=tenant_a, report=report)
    url = reverse("bi:report_parameter_edit", kwargs={"pk": param.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["parameter"] == param


@pytest.mark.django_db
def test_operationalreporting_parameter_edit_view_post_valid(client_a, tenant_a, admin_user):
    """Test parameter edit view POST updates fields and redirects."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(tenant=tenant_a, report=report)
    url = reverse("bi:report_parameter_edit", kwargs={"pk": param.pk})
    payload = {
        "report": report.pk,
        "parameter_name": param.parameter_name,
        "prompt_label": "Renamed Fiscal Year Filter",
        "parameter_type": "string",
        "default_value": "2027",
        "choices_source": "static_list",
        "prompt_order": 20,
        "is_required": False,
        "is_active": True,
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_parameter_detail", kwargs={"pk": param.pk})

    param.refresh_from_db()
    assert param.prompt_label == "Renamed Fiscal Year Filter"
    assert param.default_value == "2027"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_parameter_delete_view_get_rejected(client_a, tenant_a, admin_user):
    """Test parameter delete rejects GET requests with 405 MethodNotAllowed."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(tenant=tenant_a, report=report)
    url = reverse("bi:report_parameter_delete", kwargs={"pk": param.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert ReportParameter.objects.filter(pk=param.pk).exists()


@pytest.mark.django_db
def test_operationalreporting_parameter_delete_view_post(client_a, tenant_a, admin_user):
    """Test parameter delete POST deletes record and redirects to report detail."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(tenant=tenant_a, report=report)
    url = reverse("bi:report_parameter_delete", kwargs={"pk": param.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_definition_detail", kwargs={"pk": report.pk})
    assert not ReportParameter.objects.filter(pk=param.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").order_by("-at").first()
    assert audit is not None


# ---------------------------------------------------------------------------
# 3. ReportExecution Views Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_execution_list_view(client_a, tenant_a, admin_user):
    """Test execution list view context contract: page_obj, status_choices, mode_choices, format_choices."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    exec1 = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)

    url = reverse("bi:report_execution_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "page_obj" in resp.context
    assert "executions" in resp.context
    assert "status_choices" in resp.context
    assert "mode_choices" in resp.context
    assert "format_choices" in resp.context
    assert "reports" in resp.context
    assert exec1.number in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_operationalreporting_execution_list_search_and_filters(client_a, tenant_a, admin_user):
    """Test execution list filtering by status, mode, format, report, and ?q=."""
    report1 = _operationalreporting_create_report(tenant=tenant_a, user=admin_user, name="Exec Report Alpha", slug="exec-alpha")
    report2 = _operationalreporting_create_report(tenant=tenant_a, user=admin_user, name="Exec Report Beta", slug="exec-beta")

    e_completed = _operationalreporting_create_execution(
        tenant=tenant_a,
        report=report1,
        user=admin_user,
        execution_mode="export_pdf",
        output_format="pdf",
        execution_status="completed",
    )
    e_failed = _operationalreporting_create_execution(
        tenant=tenant_a,
        report=report2,
        user=admin_user,
        execution_mode="interactive_view",
        output_format="html",
        execution_status="failed",
    )

    url = reverse("bi:report_execution_list")

    # Filter by status
    resp_stat = client_a.get(f"{url}?execution_status=failed")
    assert resp_stat.status_code == 200
    nums = [e.number for e in resp_stat.context["page_obj"]]
    assert e_failed.number in nums
    assert e_completed.number not in nums

    # Filter by mode
    resp_mode = client_a.get(f"{url}?execution_mode=export_pdf")
    assert resp_mode.status_code == 200
    nums = [e.number for e in resp_mode.context["page_obj"]]
    assert e_completed.number in nums
    assert e_failed.number not in nums

    # Filter by format
    resp_fmt = client_a.get(f"{url}?output_format=pdf")
    assert resp_fmt.status_code == 200
    nums = [e.number for e in resp_fmt.context["page_obj"]]
    assert e_completed.number in nums
    assert e_failed.number not in nums

    # Filter by report
    resp_rep = client_a.get(f"{url}?report={report1.pk}")
    assert resp_rep.status_code == 200
    nums = [e.number for e in resp_rep.context["page_obj"]]
    assert e_completed.number in nums
    assert e_failed.number not in nums

    # Search query
    resp_q = client_a.get(f"{url}?q=Alpha")
    assert resp_q.status_code == 200
    nums = [e.number for e in resp_q.context["page_obj"]]
    assert e_completed.number in nums
    assert e_failed.number not in nums


@pytest.mark.django_db
def test_operationalreporting_execution_list_guarded_parameters(client_a, tenant_a, admin_user):
    """Test execution list handles non-numeric report filter and pagination safely."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)
    url = reverse("bi:report_execution_list")

    resp_junk_report = client_a.get(f"{url}?report=abc")
    assert resp_junk_report.status_code == 200

    resp_junk_page = client_a.get(f"{url}?page=999")
    assert resp_junk_page.status_code == 200
    assert resp_junk_page.context["page_obj"].number == 1


@pytest.mark.django_db
def test_operationalreporting_execution_run_view_get(client_a, tenant_a, admin_user):
    """Test report execution run view GET renders form with report context."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_execution_run", kwargs={"report_pk": report.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["report"] == report


@pytest.mark.django_db
def test_operationalreporting_execution_run_view_post_valid(client_a, tenant_a, admin_user):
    """Test report execution run view POST creates execution trace and redirects to detail."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_execution_run", kwargs={"report_pk": report.pk})
    payload = {
        "execution_mode": "export_pdf",
        "output_format": "pdf",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created_exec = ReportExecution.objects.get(tenant=tenant_a, report=report)
    assert created_exec.executed_by == admin_user
    assert created_exec.execution_status == "completed"
    assert created_exec.duration_ms >= 16
    assert created_exec.row_count > 0
    assert created_exec.output_format == "pdf"
    assert resp.url == reverse("bi:report_execution_detail", kwargs={"pk": created_exec.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_execution_detail_view(client_a, tenant_a, admin_user):
    """Test execution detail view contract: execution, report, can_delete."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    execution = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)

    url = reverse("bi:report_execution_detail", kwargs={"pk": execution.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["execution"] == execution
    assert resp.context["report"] == report
    assert "can_delete" in resp.context
    assert execution.number in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_operationalreporting_execution_delete_view_get_rejected(client_a, tenant_a, admin_user):
    """Test execution delete rejects GET requests with 405 MethodNotAllowed."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    execution = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)
    url = reverse("bi:report_execution_delete", kwargs={"pk": execution.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert ReportExecution.objects.filter(pk=execution.pk).exists()


@pytest.mark.django_db
def test_operationalreporting_execution_delete_view_post(client_a, tenant_a, admin_user):
    """Test execution delete POST removes execution record and redirects to execution list."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    execution = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)
    url = reverse("bi:report_execution_delete", kwargs={"pk": execution.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_execution_list")
    assert not ReportExecution.objects.filter(pk=execution.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_execution_export_csv(client_a, tenant_a, admin_user):
    """Test export endpoint generates downloadable CSV with Content-Disposition header."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    execution = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)

    url = reverse(
        "bi:report_execution_export",
        kwargs={"pk": execution.pk, "export_format": "csv"},
    )
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment;" in resp["Content-Disposition"]
    assert f"{report.slug}_{execution.number}.csv" in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    assert "Reference Code" in content or "item_code" in content or "Amount" in content


@pytest.mark.django_db
def test_operationalreporting_execution_export_json(client_a, tenant_a, admin_user):
    """Test export endpoint generates structured JSON data payload."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    execution = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)

    url = reverse(
        "bi:report_execution_export",
        kwargs={"pk": execution.pk, "export_format": "json"},
    )
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/json"
    assert "attachment;" in resp["Content-Disposition"]
    assert f"{report.slug}_{execution.number}.json" in resp["Content-Disposition"]

    payload = json.loads(resp.content.decode("utf-8"))
    assert payload["report"] == report.name
    assert payload["number"] == report.number
    assert payload["execution"] == execution.number
    assert isinstance(payload["columns"], list)
    assert isinstance(payload["rows"], list)


@pytest.mark.django_db
def test_operationalreporting_execution_export_unknown_format_redirect(client_a, tenant_a, admin_user):
    """Test export endpoint redirects unknown format to the interactive report viewer."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    execution = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)

    url = reverse(
        "bi:report_execution_export",
        kwargs={"pk": execution.pk, "export_format": "unsupported_xyz"},
    )
    resp = client_a.get(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_definition_viewer", kwargs={"pk": report.pk})


# ---------------------------------------------------------------------------
# 4. ReportDrillPath Views Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_drill_path_list_view(client_a, tenant_a, admin_user):
    """Test drill path list view contract: page_obj, target_type_choices, and reports."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)

    url = reverse("bi:report_drill_path_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    assert "page_obj" in resp.context
    assert "drill_paths" in resp.context
    assert "target_type_choices" in resp.context
    assert "reports" in resp.context
    assert drill.drill_label in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_operationalreporting_drill_path_list_search_and_filters(client_a, tenant_a, admin_user):
    """Test drill path filtering by target_type, report, and query ?q=."""
    report1 = _operationalreporting_create_report(tenant=tenant_a, user=admin_user, name="Drill Source 1", slug="drill-src-1")
    report2 = _operationalreporting_create_report(tenant=tenant_a, user=admin_user, name="Drill Source 2", slug="drill-src-2")

    d_erp = _operationalreporting_create_drill_path(
        tenant=tenant_a,
        source_report=report1,
        drill_label="Inspect Direct ERP Entity",
        target_type="erp_record_url",
    )
    d_op = _operationalreporting_create_drill_path(
        tenant=tenant_a,
        source_report=report2,
        drill_label="Open Subordinate Operational Report",
        target_type="operational_report",
    )

    url = reverse("bi:report_drill_path_list")

    # Filter by target_type
    resp_type = client_a.get(f"{url}?target_type=erp_record_url")
    assert resp_type.status_code == 200
    labels = [d.drill_label for d in resp_type.context["page_obj"]]
    assert d_erp.drill_label in labels
    assert d_op.drill_label not in labels

    # Filter by report
    resp_rep = client_a.get(f"{url}?report={report1.pk}")
    assert resp_rep.status_code == 200
    labels = [d.drill_label for d in resp_rep.context["page_obj"]]
    assert d_erp.drill_label in labels
    assert d_op.drill_label not in labels

    # Search query
    resp_q = client_a.get(f"{url}?q=Subordinate")
    assert resp_q.status_code == 200
    labels = [d.drill_label for d in resp_q.context["page_obj"]]
    assert d_op.drill_label in labels
    assert d_erp.drill_label not in labels


@pytest.mark.django_db
def test_operationalreporting_drill_path_list_guarded_parameters(client_a, tenant_a, admin_user):
    """Test drill path list handles non-numeric report filter and pagination safely."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)
    url = reverse("bi:report_drill_path_list")

    resp_junk_report = client_a.get(f"{url}?report=not_a_number")
    assert resp_junk_report.status_code == 200

    resp_junk_page = client_a.get(f"{url}?page=999")
    assert resp_junk_page.status_code == 200
    assert resp_junk_page.context["page_obj"].number == 1


@pytest.mark.django_db
def test_operationalreporting_drill_path_detail_view(client_a, tenant_a, admin_user):
    """Test drill path detail view contract: drill_path, can_edit."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)

    url = reverse("bi:report_drill_path_detail", kwargs={"pk": drill.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["drill_path"] == drill
    assert "can_edit" in resp.context
    assert drill.drill_label in resp.content.decode("utf-8")


@pytest.mark.django_db
def test_operationalreporting_drill_path_create_view_get(client_a, tenant_a, admin_user):
    """Test drill path create view GET with optional ?report= query pre-populating form."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_drill_path_create")

    # Regular GET
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False

    # GET with ?report=<pk>
    resp_pre = client_a.get(f"{url}?report={report.pk}")
    assert resp_pre.status_code == 200
    assert resp_pre.context["form"].initial.get("source_report") == report


@pytest.mark.django_db
def test_operationalreporting_drill_path_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test drill path create POST creates instance, writes audit log, and redirects."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_drill_path_create")
    payload = {
        "source_report": report.pk,
        "source_field": "customer_id",
        "drill_label": "Jump to CRM Customer Record",
        "target_type": "erp_record_url",
        "target_url_pattern": "/crm/customers/{customer_id}/",
        "sort_order": 5,
        "is_enabled": True,
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = ReportDrillPath.objects.get(tenant=tenant_a, source_report=report, source_field="customer_id")
    assert created.drill_label == "Jump to CRM Customer Record"
    assert resp.url == reverse("bi:report_drill_path_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_drill_path_create_view_post_invalid(client_a, tenant_a, admin_user):
    """Test drill path create POST with missing drill_label re-renders form with errors."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    url = reverse("bi:report_drill_path_create")
    payload = {
        "source_report": report.pk,
        "source_field": "order_id",
        "drill_label": "",  # invalid
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert "drill_label" in resp.context["form"].errors


@pytest.mark.django_db
def test_operationalreporting_drill_path_edit_view_get(client_a, tenant_a, admin_user):
    """Test drill path edit view GET renders form with is_edit=True."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)
    url = reverse("bi:report_drill_path_edit", kwargs={"pk": drill.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["drill_path"] == drill


@pytest.mark.django_db
def test_operationalreporting_drill_path_edit_view_post_valid(client_a, tenant_a, admin_user):
    """Test drill path edit view POST updates fields, writes audit log, and redirects."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)
    url = reverse("bi:report_drill_path_edit", kwargs={"pk": drill.pk})
    payload = {
        "source_report": report.pk,
        "source_field": drill.source_field,
        "drill_label": "Updated Drill Through Destination",
        "target_type": "operational_report",
        "target_report": report.pk,
        "sort_order": 25,
        "is_enabled": False,
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_drill_path_detail", kwargs={"pk": drill.pk})

    drill.refresh_from_db()
    assert drill.drill_label == "Updated Drill Through Destination"
    assert drill.sort_order == 25
    assert drill.is_enabled is False

    audit = AuditLog.objects.filter(tenant=tenant_a, action="update").order_by("-at").first()
    assert audit is not None


@pytest.mark.django_db
def test_operationalreporting_drill_path_delete_view_get_rejected(client_a, tenant_a, admin_user):
    """Test drill path delete endpoint rejects GET requests with 405 MethodNotAllowed."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)
    url = reverse("bi:report_drill_path_delete", kwargs={"pk": drill.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert ReportDrillPath.objects.filter(pk=drill.pk).exists()


@pytest.mark.django_db
def test_operationalreporting_drill_path_delete_view_post(client_a, tenant_a, admin_user):
    """Test drill path delete endpoint deletes record and redirects to report detail."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)
    url = reverse("bi:report_drill_path_delete", kwargs={"pk": drill.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:report_definition_detail", kwargs={"pk": report.pk})
    assert not ReportDrillPath.objects.filter(pk=drill.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete").order_by("-at").first()
    assert audit is not None


# ---------------------------------------------------------------------------
# 5. Security & Isolation Views Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_anonymous_redirect(client, tenant_a, admin_user):
    """Test anonymous unauthenticated requests redirect to login view across all endpoints."""
    report = _operationalreporting_create_report(tenant=tenant_a, user=admin_user)
    param = _operationalreporting_create_parameter(tenant=tenant_a, report=report)
    exec_item = _operationalreporting_create_execution(tenant=tenant_a, report=report, user=admin_user)
    drill = _operationalreporting_create_drill_path(tenant=tenant_a, source_report=report)

    endpoints = [
        reverse("bi:report_definition_list"),
        reverse("bi:report_definition_create"),
        reverse("bi:report_definition_detail", kwargs={"pk": report.pk}),
        reverse("bi:report_definition_edit", kwargs={"pk": report.pk}),
        reverse("bi:report_definition_clone", kwargs={"pk": report.pk}),
        reverse("bi:report_definition_viewer", kwargs={"pk": report.pk}),
        reverse("bi:report_definition_print", kwargs={"pk": report.pk}),
        reverse("bi:report_parameter_list"),
        reverse("bi:report_parameter_create"),
        reverse("bi:report_parameter_detail", kwargs={"pk": param.pk}),
        reverse("bi:report_parameter_edit", kwargs={"pk": param.pk}),
        reverse("bi:report_execution_list"),
        reverse("bi:report_execution_run", kwargs={"report_pk": report.pk}),
        reverse("bi:report_execution_detail", kwargs={"pk": exec_item.pk}),
        reverse("bi:report_execution_export", kwargs={"pk": exec_item.pk, "export_format": "csv"}),
        reverse("bi:report_drill_path_list"),
        reverse("bi:report_drill_path_create"),
        reverse("bi:report_drill_path_detail", kwargs={"pk": drill.pk}),
        reverse("bi:report_drill_path_edit", kwargs={"pk": drill.pk}),
    ]

    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 302, f"Expected 302 redirect for unauthenticated access to {ep}"
        assert "/login" in resp.url or "accounts/login" in resp.url


@pytest.mark.django_db
def test_operationalreporting_cross_tenant_isolation_idor(client_a, tenant_b, admin_user_b):
    """Test cross-tenant IDOR protection: client_a receives 404 accessing tenant_b's entities."""
    report_b = _operationalreporting_create_report(tenant=tenant_b, user=admin_user_b)
    param_b = _operationalreporting_create_parameter(tenant=tenant_b, report=report_b)
    exec_b = _operationalreporting_create_execution(tenant=tenant_b, report=report_b, user=admin_user_b)
    drill_b = _operationalreporting_create_drill_path(tenant=tenant_b, source_report=report_b)

    # ReportDefinition detail / edit / clone / viewer / print
    assert client_a.get(reverse("bi:report_definition_detail", kwargs={"pk": report_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_definition_edit", kwargs={"pk": report_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_definition_clone", kwargs={"pk": report_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_definition_viewer", kwargs={"pk": report_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_definition_print", kwargs={"pk": report_b.pk})).status_code == 404

    # ReportParameter detail / edit
    assert client_a.get(reverse("bi:report_parameter_detail", kwargs={"pk": param_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_parameter_edit", kwargs={"pk": param_b.pk})).status_code == 404

    # ReportExecution detail / export
    assert client_a.get(reverse("bi:report_execution_detail", kwargs={"pk": exec_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_execution_export", kwargs={"pk": exec_b.pk, "export_format": "csv"})).status_code == 404

    # ReportDrillPath detail / edit
    assert client_a.get(reverse("bi:report_drill_path_detail", kwargs={"pk": drill_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:report_drill_path_edit", kwargs={"pk": drill_b.pk})).status_code == 404
