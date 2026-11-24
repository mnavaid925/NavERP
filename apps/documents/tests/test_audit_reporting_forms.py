"""Unit tests for Sub-module 13.10: Audit Trail & Reporting forms in apps.documents.

Covers all forms in apps/documents/forms/AuditReporting/:
1. DocumentAuditTrailFilterForm:
   - Valid inputs, choices for action_type, boolean filter for is_success, date range validation.
   - Clean handling of empty strings and missing filters.
   - Date validation: date_from <= date_to, invalid date strings.
   - Widget attributes and CSS classes.

2. AuditReportDefinitionForm:
   - Valid inputs for custom report definitions.
   - System field exclusion check: verify tenant, number, is_system_preset, last_run_at,
     last_run_by, total_runs, created_by, filter_criteria_json are excluded.
   - Date range validation: preset vs custom date range (requires start_date and end_date, start <= end).
   - Report type, output format, and status choice validations.
   - Editing existing instances.

3. AuditReportRunForm:
   - Optional parameters for ad-hoc execution (output_format, date_from, date_to).
   - Valid outputs and empty inputs handling.
   - Date range validation: date_from <= date_to, partial dates.

4. DocumentSecurityAlertTriageForm:
   - Form signature (*args, tenant=None, **kwargs) with tenant scoping on assigned_to.
   - Cross-tenant foreign user rejection via reject_foreign.
   - Unassigned investigator support.
   - Status transitions, severity choices, action_taken choices.
   - Form save and instance mutation.

5. DocumentSecurityAlertFilterForm:
   - Search query, severity, status, and alert_type filtering.
   - Choice validations and empty handling.

6. ChainOfCustodyExportForm:
   - Form signature (*args, tenant=None, **kwargs) with tenant scoping on document and folder.
   - Scope validation: single_document requires document; folder_tree requires folder; date_range.
   - Cross-tenant foreign document and folder rejection via reject_foreign.
   - Excluded fields check: verify tenant, number, access_token, passcode_hash, package_hash,
     manifest_json, access_count, last_accessed_at, created_by, revoked_at, revoked_by are excluded.
   - Default initial expiration calculation (~14 days).
   - Portal passcode extra field and password widget.

7. AuditorPortalPasscodeForm:
   - Passcode entry validation, required field enforcement.
   - PasswordInput widget with autofocus and mono styling.
"""
from datetime import date, timedelta
import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.documents.forms.AuditReporting.AuditReportDefinitions import (
    AuditReportDefinitionForm,
    AuditReportRunForm,
)
from apps.documents.forms.AuditReporting.ChainOfCustodyExports import (
    AuditorPortalPasscodeForm,
    ChainOfCustodyExportForm,
)
from apps.documents.forms.AuditReporting.DocumentAuditTrails import DocumentAuditTrailFilterForm
from apps.documents.forms.AuditReporting.DocumentSecurityAlerts import (
    DocumentSecurityAlertFilterForm,
    DocumentSecurityAlertTriageForm,
)
from apps.documents.models.AuditReporting.AuditReportDefinitions import AuditReportDefinition
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail
from apps.documents.models.AuditReporting.DocumentSecurityAlerts import DocumentSecurityAlert
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document

User = get_user_model()

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Module-level test helpers (prefix _audit_reporting_*)
# ---------------------------------------------------------------------------

def _audit_reporting_create_user(tenant, username, email=None):
    """Helper to create a user for tenant scoping tests."""
    email = email or f"{username}@example.com"
    return User.objects.create_user(
        username=username,
        email=email,
        password="TestPassword123!",
        tenant=tenant,
    )


def _audit_reporting_create_document(tenant, owner, title="Cross-Tenant Test Document"):
    """Helper to create a Document for tenant isolation testing."""
    return Document.objects.create(
        tenant=tenant,
        title=title,
        document_type="report",
        owner=owner,
    )


def _audit_reporting_create_folder(tenant, owner, name="Cross-Tenant Test Folder"):
    """Helper to create a DocumentFolder for tenant isolation testing."""
    return DocumentFolder.objects.create(
        tenant=tenant,
        name=name,
        owner=owner,
    )


# ===========================================================================
# 1. DocumentAuditTrailFilterForm Tests
# ===========================================================================

def test_audit_reporting_audit_trail_filter_form_empty():
    """Verify empty dictionary passes validation with defaults."""
    form = DocumentAuditTrailFilterForm(data={})
    assert form.is_valid() is True
    assert form.cleaned_data["q"] == ""
    assert form.cleaned_data["action_type"] == ""
    assert form.cleaned_data["is_success"] == ""
    assert form.cleaned_data["date_from"] is None
    assert form.cleaned_data["date_to"] is None


def test_audit_reporting_audit_trail_filter_form_blank_strings():
    """Verify form handles explicit empty strings cleanly."""
    form = DocumentAuditTrailFilterForm(
        data={
            "q": "",
            "action_type": "",
            "is_success": "",
            "date_from": "",
            "date_to": "",
        }
    )
    assert form.is_valid() is True
    assert form.cleaned_data["q"] == ""
    assert form.cleaned_data["action_type"] == ""
    assert form.cleaned_data["is_success"] == ""
    assert form.cleaned_data["date_from"] is None
    assert form.cleaned_data["date_to"] is None


def test_audit_reporting_audit_trail_filter_form_valid_inputs():
    """Verify complete valid filtering data is parsed into correct types."""
    form = DocumentAuditTrailFilterForm(
        data={
            "q": "confidential_export",
            "action_type": "downloaded",
            "is_success": "1",
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
        }
    )
    assert form.is_valid() is True
    assert form.cleaned_data["q"] == "confidential_export"
    assert form.cleaned_data["action_type"] == "downloaded"
    assert form.cleaned_data["is_success"] == "1"
    assert form.cleaned_data["date_from"] == date(2026, 3, 1)
    assert form.cleaned_data["date_to"] == date(2026, 3, 31)


def test_audit_reporting_audit_trail_filter_form_action_type_choices():
    """Verify all valid action type choices and rejection of unrecognized values."""
    for action_choice, _ in DocumentAuditTrail.ACTION_TYPE_CHOICES:
        form = DocumentAuditTrailFilterForm(data={"action_type": action_choice})
        assert form.is_valid() is True
        assert form.cleaned_data["action_type"] == action_choice

    # Invalid choice
    form_invalid = DocumentAuditTrailFilterForm(data={"action_type": "unauthorized_tampering"})
    assert form_invalid.is_valid() is False
    assert "action_type" in form_invalid.errors


def test_audit_reporting_audit_trail_filter_form_is_success_choices():
    """Verify is_success accepts '1', '0', '' and rejects other values."""
    for val in ["", "1", "0"]:
        form = DocumentAuditTrailFilterForm(data={"is_success": val})
        assert form.is_valid() is True
        assert form.cleaned_data["is_success"] == val

    for invalid_val in ["true", "false", "2", "yes", "-1"]:
        form = DocumentAuditTrailFilterForm(data={"is_success": invalid_val})
        assert form.is_valid() is False
        assert "is_success" in form.errors


def test_audit_reporting_audit_trail_filter_form_date_ordering():
    """Verify date_from must be on or before date_to."""
    # Inverted date range
    form_inverted = DocumentAuditTrailFilterForm(
        data={
            "date_from": "2026-12-31",
            "date_to": "2026-01-01",
        }
    )
    assert form_inverted.is_valid() is False
    assert "date_to" in form_inverted.errors
    assert "Date to must be on or after date from." in form_inverted.errors["date_to"]

    # Same day date range
    form_same = DocumentAuditTrailFilterForm(
        data={
            "date_from": "2026-05-15",
            "date_to": "2026-05-15",
        }
    )
    assert form_same.is_valid() is True

    # Valid span
    form_span = DocumentAuditTrailFilterForm(
        data={
            "date_from": "2026-01-01",
            "date_to": "2026-06-30",
        }
    )
    assert form_span.is_valid() is True


def test_audit_reporting_audit_trail_filter_form_invalid_date_format():
    """Verify invalid date strings trigger validation errors."""
    form = DocumentAuditTrailFilterForm(data={"date_from": "not-a-valid-date"})
    assert form.is_valid() is False
    assert "date_from" in form.errors


def test_audit_reporting_audit_trail_filter_form_widgets():
    """Verify filter form widgets and styling classes."""
    form = DocumentAuditTrailFilterForm()
    assert "form-input" in form.fields["q"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["action_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["is_success"].widget.attrs.get("class", "")
    assert isinstance(form.fields["date_from"].widget, forms.DateInput)
    assert form.fields["date_from"].widget.input_type == "date"
    assert "form-input" in form.fields["date_from"].widget.attrs.get("class", "")
    assert isinstance(form.fields["date_to"].widget, forms.DateInput)
    assert form.fields["date_to"].widget.input_type == "date"
    assert "form-input" in form.fields["date_to"].widget.attrs.get("class", "")


# ===========================================================================
# 2. AuditReportDefinitionForm Tests
# ===========================================================================

def test_audit_reporting_report_definition_form_valid(tenant_a, admin_user):
    """Verify valid report definition creation with preset date range."""
    form_data = {
        "name": "SOC 2 Type II Confidential Access Audit",
        "description": "Annual audit review of all confidential document views and downloads.",
        "report_type": "confidential_access",
        "date_range_preset": "last_90_days",
        "output_format": "table_view",
        "status": "active",
    }
    form = AuditReportDefinitionForm(data=form_data)
    assert form.is_valid() is True

    report_def = form.save(commit=False)
    report_def.tenant = tenant_a
    report_def.created_by = admin_user
    report_def.save()

    assert report_def.pk is not None
    assert report_def.name == "SOC 2 Type II Confidential Access Audit"
    assert report_def.report_type == "confidential_access"
    assert report_def.date_range_preset == "last_90_days"
    assert report_def.is_system_preset is False
    assert report_def.number.startswith("DRPT-")


def test_audit_reporting_report_definition_form_required_fields():
    """Verify name and report_type are required fields."""
    form_no_name = AuditReportDefinitionForm(
        data={
            "name": "",
            "report_type": "user_activity",
            "date_range_preset": "today",
            "output_format": "csv",
            "status": "active",
        }
    )
    assert form_no_name.is_valid() is False
    assert "name" in form_no_name.errors

    form_no_type = AuditReportDefinitionForm(
        data={
            "name": "Audit Name",
            "report_type": "",
            "date_range_preset": "today",
            "output_format": "csv",
            "status": "active",
        }
    )
    assert form_no_type.is_valid() is False
    assert "report_type" in form_no_type.errors


def test_audit_reporting_report_definition_form_system_field_exclusions():
    """Verify system fields (tenant, number, is_system_preset, last_run_at, total_runs, etc.) are excluded."""
    form = AuditReportDefinitionForm()
    excluded = [
        "tenant",
        "number",
        "is_system_preset",
        "last_run_at",
        "last_run_by",
        "total_runs",
        "created_by",
        "filter_criteria_json",
        "created_at",
        "updated_at",
    ]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must not be in form fields"

    expected_fields = {
        "name",
        "description",
        "report_type",
        "date_range_preset",
        "custom_start_date",
        "custom_end_date",
        "output_format",
        "status",
    }
    assert set(form.fields.keys()) == expected_fields


def test_audit_reporting_report_definition_form_presets_do_not_require_dates():
    """Verify standard date presets don't require custom_start_date or custom_end_date."""
    for preset, _ in AuditReportDefinition.DATE_RANGE_CHOICES:
        if preset == "custom":
            continue
        form = AuditReportDefinitionForm(
            data={
                "name": f"Audit {preset}",
                "report_type": "document_history",
                "date_range_preset": preset,
                "output_format": "table_view",
                "status": "active",
            }
        )
        assert form.is_valid() is True, f"Preset {preset} should be valid without dates: {form.errors}"


def test_audit_reporting_report_definition_form_custom_range_missing_start():
    """Verify custom date range requires custom_start_date."""
    form = AuditReportDefinitionForm(
        data={
            "name": "Custom Range Audit",
            "report_type": "security_exceptions",
            "date_range_preset": "custom",
            "custom_start_date": "",
            "custom_end_date": "2026-11-20",
            "output_format": "table_view",
            "status": "active",
        }
    )
    assert form.is_valid() is False
    assert "custom_start_date" in form.errors
    assert "Start date is required when using a custom date range." in form.errors["custom_start_date"]


def test_audit_reporting_report_definition_form_custom_range_missing_end():
    """Verify custom date range requires custom_end_date."""
    form = AuditReportDefinitionForm(
        data={
            "name": "Custom Range Audit",
            "report_type": "security_exceptions",
            "date_range_preset": "custom",
            "custom_start_date": "2026-11-01",
            "custom_end_date": "",
            "output_format": "table_view",
            "status": "active",
        }
    )
    assert form.is_valid() is False
    assert "custom_end_date" in form.errors
    assert "End date is required when using a custom date range." in form.errors["custom_end_date"]


def test_audit_reporting_report_definition_form_custom_range_missing_both():
    """Verify custom date range reports errors for both missing dates."""
    form = AuditReportDefinitionForm(
        data={
            "name": "Custom Range Audit",
            "report_type": "security_exceptions",
            "date_range_preset": "custom",
            "custom_start_date": "",
            "custom_end_date": "",
            "output_format": "table_view",
            "status": "active",
        }
    )
    assert form.is_valid() is False
    assert "custom_start_date" in form.errors
    assert "custom_end_date" in form.errors


def test_audit_reporting_report_definition_form_custom_range_inverted():
    """Verify start date after end date raises validation error on custom_end_date."""
    form = AuditReportDefinitionForm(
        data={
            "name": "Custom Range Inverted",
            "report_type": "security_exceptions",
            "date_range_preset": "custom",
            "custom_start_date": "2026-12-01",
            "custom_end_date": "2026-11-01",
            "output_format": "table_view",
            "status": "active",
        }
    )
    assert form.is_valid() is False
    assert "custom_end_date" in form.errors
    assert "End date must be on or after start date." in form.errors["custom_end_date"]


def test_audit_reporting_report_definition_form_custom_range_valid():
    """Verify valid custom date range passes cleanly."""
    form = AuditReportDefinitionForm(
        data={
            "name": "Valid Custom Audit",
            "report_type": "deletion_purge",
            "date_range_preset": "custom",
            "custom_start_date": "2026-10-01",
            "custom_end_date": "2026-10-31",
            "output_format": "csv",
            "status": "active",
        }
    )
    assert form.is_valid() is True
    assert form.cleaned_data["custom_start_date"] == date(2026, 10, 1)
    assert form.cleaned_data["custom_end_date"] == date(2026, 10, 31)

    # Same day custom range
    form_same = AuditReportDefinitionForm(
        data={
            "name": "Single Day Custom Audit",
            "report_type": "deletion_purge",
            "date_range_preset": "custom",
            "custom_start_date": "2026-10-15",
            "custom_end_date": "2026-10-15",
            "output_format": "json",
            "status": "active",
        }
    )
    assert form_same.is_valid() is True


def test_audit_reporting_report_definition_form_choices():
    """Verify report_type, output_format, and status choice validations."""
    for rtype, _ in AuditReportDefinition.REPORT_TYPE_CHOICES:
        form = AuditReportDefinitionForm(
            data={
                "name": f"Test {rtype}",
                "report_type": rtype,
                "date_range_preset": "last_30_days",
                "output_format": "table_view",
                "status": "active",
            }
        )
        assert form.is_valid() is True

    # Invalid report_type
    form_bad_type = AuditReportDefinitionForm(
        data={
            "name": "Bad Type",
            "report_type": "unsupported_report_type",
            "date_range_preset": "last_30_days",
            "output_format": "table_view",
            "status": "active",
        }
    )
    assert form_bad_type.is_valid() is False
    assert "report_type" in form_bad_type.errors

    # Invalid output_format
    form_bad_fmt = AuditReportDefinitionForm(
        data={
            "name": "Bad Format",
            "report_type": "confidential_access",
            "date_range_preset": "last_30_days",
            "output_format": "xml_format",
            "status": "active",
        }
    )
    assert form_bad_fmt.is_valid() is False
    assert "output_format" in form_bad_fmt.errors

    # Invalid status
    form_bad_status = AuditReportDefinitionForm(
        data={
            "name": "Bad Status",
            "report_type": "confidential_access",
            "date_range_preset": "last_30_days",
            "output_format": "table_view",
            "status": "deleted",
        }
    )
    assert form_bad_status.is_valid() is False
    assert "status" in form_bad_status.errors


def test_audit_reporting_report_definition_form_edit_existing_instance(audit_report_definition):
    """Verify editing an existing custom report definition via form."""
    form = AuditReportDefinitionForm(
        instance=audit_report_definition,
        data={
            "name": "Updated Audit Definition Name",
            "description": "Updated scope and objectives.",
            "report_type": "permission_audit",
            "date_range_preset": "last_7_days",
            "output_format": "json",
            "status": "archived",
        },
    )
    assert form.is_valid() is True
    updated = form.save()
    assert updated.pk == audit_report_definition.pk
    assert updated.name == "Updated Audit Definition Name"
    assert updated.report_type == "permission_audit"
    assert updated.date_range_preset == "last_7_days"
    assert updated.output_format == "json"
    assert updated.status == "archived"


def test_audit_reporting_report_definition_form_widgets():
    """Verify form widgets apply correct UI classes and attributes."""
    form = AuditReportDefinitionForm()
    assert "form-input" in form.fields["name"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["description"].widget.attrs.get("class", "")
    assert form.fields["description"].widget.attrs.get("rows") == 3
    assert "form-select" in form.fields["report_type"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["date_range_preset"].widget.attrs.get("class", "")
    assert isinstance(form.fields["custom_start_date"].widget, forms.DateInput)
    assert form.fields["custom_start_date"].widget.input_type == "date"
    assert isinstance(form.fields["custom_end_date"].widget, forms.DateInput)
    assert form.fields["custom_end_date"].widget.input_type == "date"


# ===========================================================================
# 3. AuditReportRunForm Tests
# ===========================================================================

def test_audit_reporting_report_run_form_empty():
    """Verify empty dictionary validates cleanly with defaults for ad-hoc execution."""
    form = AuditReportRunForm(data={})
    assert form.is_valid() is True
    assert form.cleaned_data["output_format"] == ""
    assert form.cleaned_data["date_from"] is None
    assert form.cleaned_data["date_to"] is None


def test_audit_reporting_report_run_form_valid_parameters():
    """Verify valid ad-hoc run parameters are parsed properly."""
    form = AuditReportRunForm(
        data={
            "output_format": "csv",
            "date_from": "2026-01-01",
            "date_to": "2026-06-30",
        }
    )
    assert form.is_valid() is True
    assert form.cleaned_data["output_format"] == "csv"
    assert form.cleaned_data["date_from"] == date(2026, 1, 1)
    assert form.cleaned_data["date_to"] == date(2026, 6, 30)


def test_audit_reporting_report_run_form_output_format_choices():
    """Verify output_format accepts supported formats and empty default."""
    for fmt in ["", "table_view", "csv", "json"]:
        form = AuditReportRunForm(data={"output_format": fmt})
        assert form.is_valid() is True
        assert form.cleaned_data["output_format"] == fmt

    # Invalid choice
    form_invalid = AuditReportRunForm(data={"output_format": "pdf_export"})
    assert form_invalid.is_valid() is False
    assert "output_format" in form_invalid.errors


def test_audit_reporting_report_run_form_date_ordering():
    """Verify date_from must be on or before date_to for report run."""
    # Inverted dates
    form = AuditReportRunForm(
        data={
            "date_from": "2026-12-01",
            "date_to": "2026-01-01",
        }
    )
    assert form.is_valid() is False
    assert "date_to" in form.errors
    assert "Date to must be on or after date from." in form.errors["date_to"]

    # Same day
    form_same = AuditReportRunForm(
        data={
            "date_from": "2026-08-15",
            "date_to": "2026-08-15",
        }
    )
    assert form_same.is_valid() is True


def test_audit_reporting_report_run_form_single_date():
    """Verify single date parameters (only date_from or only date_to) are valid."""
    form_from = AuditReportRunForm(data={"date_from": "2026-01-01"})
    assert form_from.is_valid() is True
    assert form_from.cleaned_data["date_from"] == date(2026, 1, 1)
    assert form_from.cleaned_data["date_to"] is None

    form_to = AuditReportRunForm(data={"date_to": "2026-12-31"})
    assert form_to.is_valid() is True
    assert form_to.cleaned_data["date_from"] is None
    assert form_to.cleaned_data["date_to"] == date(2026, 12, 31)


def test_audit_reporting_report_run_form_invalid_date_format():
    """Verify malformed date strings fail validation."""
    form = AuditReportRunForm(data={"date_from": "not-a-date"})
    assert form.is_valid() is False
    assert "date_from" in form.errors


def test_audit_reporting_report_run_form_widgets():
    """Verify widgets and CSS classes on ad-hoc run form."""
    form = AuditReportRunForm()
    assert "form-select" in form.fields["output_format"].widget.attrs.get("class", "")
    assert isinstance(form.fields["date_from"].widget, forms.DateInput)
    assert form.fields["date_from"].widget.input_type == "date"
    assert "form-input" in form.fields["date_from"].widget.attrs.get("class", "")
    assert isinstance(form.fields["date_to"].widget, forms.DateInput)
    assert form.fields["date_to"].widget.input_type == "date"
    assert "form-input" in form.fields["date_to"].widget.attrs.get("class", "")


# ===========================================================================
# 4. DocumentSecurityAlertTriageForm Tests
# ===========================================================================

def test_audit_reporting_security_alert_triage_form_valid(tenant_a, admin_user, document_security_alert):
    """Verify valid alert triage updates status, severity, mitigation, and notes."""
    form_data = {
        "status": "resolved",
        "severity": "medium",
        "action_taken": "user_warned",
        "assigned_to": admin_user.pk,
        "triage_notes": "Contacted user. Confirmed that mass download was approved for offline fieldwork.",
    }
    form = DocumentSecurityAlertTriageForm(
        instance=document_security_alert,
        data=form_data,
        tenant=tenant_a,
    )
    assert form.is_valid() is True, form.errors

    updated_alert = form.save()
    assert updated_alert.status == "resolved"
    assert updated_alert.severity == "medium"
    assert updated_alert.action_taken == "user_warned"
    assert updated_alert.assigned_to == admin_user
    assert "offline fieldwork" in updated_alert.triage_notes


def test_audit_reporting_security_alert_triage_form_unassigned_user(tenant_a, document_security_alert):
    """Verify assigned_to is optional during triage."""
    form_data = {
        "status": "investigating",
        "severity": "high",
        "action_taken": "logged_only",
        "assigned_to": "",
        "triage_notes": "Awaiting assignment to SOC analyst.",
    }
    form = DocumentSecurityAlertTriageForm(
        instance=document_security_alert,
        data=form_data,
        tenant=tenant_a,
    )
    assert form.is_valid() is True, form.errors
    assert form.cleaned_data["assigned_to"] is None

    updated = form.save()
    assert updated.assigned_to is None


def test_audit_reporting_security_alert_triage_form_tenant_scoping(tenant_a, tenant_b, admin_user, member_user):
    """Verify assigned_to queryset is strictly scoped to tenant users."""
    user_b = _audit_reporting_create_user(tenant_b, "intruder_user")

    # Bound to tenant_a
    form_a = DocumentSecurityAlertTriageForm(tenant=tenant_a)
    qs_a = form_a.fields["assigned_to"].queryset
    assert admin_user in qs_a
    assert member_user in qs_a
    assert user_b not in qs_a

    # No tenant provided -> empty queryset
    form_no_tenant = DocumentSecurityAlertTriageForm(tenant=None)
    assert form_no_tenant.fields["assigned_to"].queryset.count() == 0


def test_audit_reporting_security_alert_triage_form_reject_foreign_user(tenant_a, tenant_b, document_security_alert):
    """Verify reject_foreign rejects foreign tenant users assigned as investigators."""
    foreign_user = _audit_reporting_create_user(tenant_b, "foreign_investigator")

    form = DocumentSecurityAlertTriageForm(
        instance=document_security_alert,
        data={
            "status": "investigating",
            "severity": "critical",
            "action_taken": "session_terminated",
            "assigned_to": foreign_user.pk,
            "triage_notes": "Cross-tenant injection attempt.",
        },
        tenant=tenant_a,
    )
    assert form.is_valid() is False
    assert "assigned_to" in form.errors


def test_audit_reporting_security_alert_triage_form_status_choices(tenant_a, document_security_alert):
    """Verify all valid triage statuses and rejection of invalid statuses."""
    for st, _ in DocumentSecurityAlert.STATUS_CHOICES:
        form = DocumentSecurityAlertTriageForm(
            instance=document_security_alert,
            data={
                "status": st,
                "severity": "low",
                "action_taken": "logged_only",
                "triage_notes": "",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True, f"Status {st} should be valid: {form.errors}"

    # Invalid status
    form_invalid = DocumentSecurityAlertTriageForm(
        instance=document_security_alert,
        data={
            "status": "closed_permanently",
            "severity": "low",
            "action_taken": "logged_only",
        },
        tenant=tenant_a,
    )
    assert form_invalid.is_valid() is False
    assert "status" in form_invalid.errors


def test_audit_reporting_security_alert_triage_form_severity_choices(tenant_a, document_security_alert):
    """Verify severity choices validation."""
    for sev, _ in DocumentSecurityAlert.SEVERITY_CHOICES:
        form = DocumentSecurityAlertTriageForm(
            instance=document_security_alert,
            data={
                "status": "new",
                "severity": sev,
                "action_taken": "logged_only",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True, f"Severity {sev} should be valid: {form.errors}"

    form_invalid = DocumentSecurityAlertTriageForm(
        instance=document_security_alert,
        data={
            "status": "new",
            "severity": "apocalyptic",
            "action_taken": "logged_only",
        },
        tenant=tenant_a,
    )
    assert form_invalid.is_valid() is False
    assert "severity" in form_invalid.errors


def test_audit_reporting_security_alert_triage_form_action_taken_choices(tenant_a, document_security_alert):
    """Verify action_taken choices validation."""
    for act, _ in DocumentSecurityAlert.ACTION_TAKEN_CHOICES:
        form = DocumentSecurityAlertTriageForm(
            instance=document_security_alert,
            data={
                "status": "resolved",
                "severity": "medium",
                "action_taken": act,
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True, f"Action {act} should be valid: {form.errors}"

    form_invalid = DocumentSecurityAlertTriageForm(
        instance=document_security_alert,
        data={
            "status": "resolved",
            "severity": "medium",
            "action_taken": "press_charges",
        },
        tenant=tenant_a,
    )
    assert form_invalid.is_valid() is False
    assert "action_taken" in form_invalid.errors


def test_audit_reporting_security_alert_triage_form_widgets():
    """Verify widget classes on triage workbench form."""
    form = DocumentSecurityAlertTriageForm()
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["severity"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["action_taken"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["assigned_to"].widget.attrs.get("class", "")
    assert "form-textarea" in form.fields["triage_notes"].widget.attrs.get("class", "")
    assert form.fields["triage_notes"].widget.attrs.get("rows") == 4


# ===========================================================================
# 5. DocumentSecurityAlertFilterForm Tests
# ===========================================================================

def test_audit_reporting_security_alert_filter_form_empty():
    """Verify empty dictionary or missing parameters passes validation."""
    form = DocumentSecurityAlertFilterForm(data={})
    assert form.is_valid() is True
    assert form.cleaned_data["q"] == ""
    assert form.cleaned_data["severity"] == ""
    assert form.cleaned_data["status"] == ""
    assert form.cleaned_data["alert_type"] == ""


def test_audit_reporting_security_alert_filter_form_valid_data():
    """Verify valid security alert search parameters."""
    form = DocumentSecurityAlertFilterForm(
        data={
            "q": "mass download",
            "severity": "critical",
            "status": "investigating",
            "alert_type": "mass_download",
        }
    )
    assert form.is_valid() is True
    assert form.cleaned_data["q"] == "mass download"
    assert form.cleaned_data["severity"] == "critical"
    assert form.cleaned_data["status"] == "investigating"
    assert form.cleaned_data["alert_type"] == "mass_download"


def test_audit_reporting_security_alert_filter_form_choices():
    """Verify choice fields reject unauthorized values."""
    for alert_t, _ in DocumentSecurityAlert.ALERT_TYPE_CHOICES:
        form = DocumentSecurityAlertFilterForm(data={"alert_type": alert_t})
        assert form.is_valid() is True

    # Bad choices
    form_bad_sev = DocumentSecurityAlertFilterForm(data={"severity": "super_critical"})
    assert form_bad_sev.is_valid() is False
    assert "severity" in form_bad_sev.errors

    form_bad_type = DocumentSecurityAlertFilterForm(data={"alert_type": "zero_day_exploit"})
    assert form_bad_type.is_valid() is False
    assert "alert_type" in form_bad_type.errors


def test_audit_reporting_security_alert_filter_form_widgets():
    """Verify widget styling on alert filter form."""
    form = DocumentSecurityAlertFilterForm()
    assert "form-input" in form.fields["q"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["severity"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["status"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["alert_type"].widget.attrs.get("class", "")


# ===========================================================================
# 6. ChainOfCustodyExportForm Tests
# ===========================================================================

def test_audit_reporting_custody_export_form_valid_single_document(tenant_a, document):
    """Verify valid chain of custody export creation targeting a single document."""
    form_data = {
        "title": "FDA Form 483 Response Custody Package",
        "regulatory_framework": "fda_21cfr11",
        "scope": "single_document",
        "document": document.pk,
        "folder": "",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "auditor_name": "Special Agent Dana Scully",
        "auditor_email": "scully@fbi.gov",
        "auditor_organization": "Federal Bureau of Investigation",
        "portal_passcode": "ScullyAudit2026!",
        "expires_at": "2026-12-31T23:59",
    }
    form = ChainOfCustodyExportForm(data=form_data, tenant=tenant_a)
    assert form.is_valid() is True, form.errors

    pkg = form.save(commit=False)
    pkg.tenant = tenant_a
    assert pkg.document == document
    assert pkg.scope == "single_document"
    assert pkg.regulatory_framework == "fda_21cfr11"
    assert form.cleaned_data["portal_passcode"] == "ScullyAudit2026!"


def test_audit_reporting_custody_export_form_valid_folder_tree(tenant_a, document_folder):
    """Verify valid chain of custody export targeting a folder hierarchy."""
    form_data = {
        "title": "ISO 27001 Surveillance Audit Repository Package",
        "regulatory_framework": "iso_27001",
        "scope": "folder_tree",
        "document": "",
        "folder": document_folder.pk,
        "auditor_name": "Lead Assessor John Doe",
        "auditor_email": "j.doe@bsigroup.com",
        "auditor_organization": "BSI Group",
        "expires_at": "2026-12-31T23:59",
    }
    form = ChainOfCustodyExportForm(data=form_data, tenant=tenant_a)
    assert form.is_valid() is True, form.errors
    pkg = form.save(commit=False)
    assert pkg.folder == document_folder
    assert pkg.scope == "folder_tree"


def test_audit_reporting_custody_export_form_valid_date_range_scope(tenant_a):
    """Verify date_range scope does not require document or folder."""
    form_data = {
        "title": "Full Enterprise SOC 2 Custody Package",
        "regulatory_framework": "soc2_type2",
        "scope": "date_range",
        "document": "",
        "folder": "",
        "auditor_name": "Audit Partner PwC",
        "auditor_email": "auditor@pwc.com",
        "auditor_organization": "PricewaterhouseCoopers",
        "expires_at": "2026-12-31T23:59",
    }
    form = ChainOfCustodyExportForm(data=form_data, tenant=tenant_a)
    assert form.is_valid() is True, form.errors


def test_audit_reporting_custody_export_form_scope_single_document_missing_doc(tenant_a):
    """Verify single_document scope requires a target document."""
    form_data = {
        "title": "Missing Doc Scope",
        "regulatory_framework": "hipaa",
        "scope": "single_document",
        "document": "",
        "auditor_name": "Auditor",
        "auditor_email": "auditor@agency.gov",
        "expires_at": "2026-12-31T23:59",
    }
    form = ChainOfCustodyExportForm(data=form_data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "document" in form.errors
    assert "Please select a target document for single document scope." in form.errors["document"]


def test_audit_reporting_custody_export_form_scope_folder_tree_missing_folder(tenant_a):
    """Verify folder_tree scope requires a target folder."""
    form_data = {
        "title": "Missing Folder Scope",
        "regulatory_framework": "hipaa",
        "scope": "folder_tree",
        "folder": "",
        "auditor_name": "Auditor",
        "auditor_email": "auditor@agency.gov",
        "expires_at": "2026-12-31T23:59",
    }
    form = ChainOfCustodyExportForm(data=form_data, tenant=tenant_a)
    assert form.is_valid() is False
    assert "folder" in form.errors
    assert "Please select a target folder for folder tree scope." in form.errors["folder"]


def test_audit_reporting_custody_export_form_tenant_scoping_document(tenant_a, tenant_b, admin_user, admin_b, document):
    """Verify document queryset strictly excludes documents from other tenants."""
    foreign_doc = _audit_reporting_create_document(tenant_b, admin_b, "Foreign Tenant Doc")

    form = ChainOfCustodyExportForm(tenant=tenant_a)
    doc_qs = form.fields["document"].queryset
    assert document in doc_qs
    assert foreign_doc not in doc_qs

    form_no_tenant = ChainOfCustodyExportForm(tenant=None)
    assert form_no_tenant.fields["document"].queryset.count() == 0


def test_audit_reporting_custody_export_form_tenant_scoping_folder(tenant_a, tenant_b, admin_user, admin_b, document_folder):
    """Verify folder queryset strictly excludes folders from other tenants."""
    foreign_folder = _audit_reporting_create_folder(tenant_b, admin_b, "Foreign Tenant Folder")

    form = ChainOfCustodyExportForm(tenant=tenant_a)
    folder_qs = form.fields["folder"].queryset
    assert document_folder in folder_qs
    assert foreign_folder not in folder_qs

    form_no_tenant = ChainOfCustodyExportForm(tenant=None)
    assert form_no_tenant.fields["folder"].queryset.count() == 0


def test_audit_reporting_custody_export_form_reject_foreign_document(tenant_a, tenant_b, admin_b):
    """Verify reject_foreign stops cross-tenant document assignment."""
    foreign_doc = _audit_reporting_create_document(tenant_b, admin_b, "Attack Document")

    form = ChainOfCustodyExportForm(
        data={
            "title": "Cross Tenant Exploitation",
            "regulatory_framework": "general_compliance",
            "scope": "single_document",
            "document": foreign_doc.pk,
            "auditor_name": "Attacker",
            "auditor_email": "attacker@evil.com",
            "expires_at": "2026-12-31T23:59",
        },
        tenant=tenant_a,
    )
    assert form.is_valid() is False
    assert "document" in form.errors


def test_audit_reporting_custody_export_form_reject_foreign_folder(tenant_a, tenant_b, admin_b):
    """Verify reject_foreign stops cross-tenant folder assignment."""
    foreign_folder = _audit_reporting_create_folder(tenant_b, admin_b, "Attack Folder")

    form = ChainOfCustodyExportForm(
        data={
            "title": "Cross Tenant Exploitation Folder",
            "regulatory_framework": "general_compliance",
            "scope": "folder_tree",
            "folder": foreign_folder.pk,
            "auditor_name": "Attacker",
            "auditor_email": "attacker@evil.com",
            "expires_at": "2026-12-31T23:59",
        },
        tenant=tenant_a,
    )
    assert form.is_valid() is False
    assert "folder" in form.errors


def test_audit_reporting_custody_export_form_excluded_fields():
    """Verify sensitive and immutable system fields are excluded from the form."""
    form = ChainOfCustodyExportForm()
    excluded = [
        "tenant",
        "number",
        "access_token",
        "passcode_hash",
        "package_hash",
        "manifest_json",
        "access_count",
        "last_accessed_at",
        "created_by",
        "revoked_at",
        "revoked_by",
        "created_at",
        "updated_at",
    ]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} must not be an editable form field"

    expected_fields = {
        "title",
        "regulatory_framework",
        "scope",
        "document",
        "folder",
        "start_date",
        "end_date",
        "auditor_name",
        "auditor_email",
        "auditor_organization",
        "expires_at",
        "portal_passcode",
    }
    assert set(form.fields.keys()) == expected_fields


def test_audit_reporting_custody_export_form_initial_expires_at(tenant_a):
    """Verify unbound form defaults expires_at to approximately 14 days in the future."""
    form = ChainOfCustodyExportForm(tenant=tenant_a)
    assert "expires_at" in form.initial
    expires_str = form.initial["expires_at"]
    # Check format YYYY-MM-DDTHH:MM
    assert "T" in expires_str
    # Expiration is in future
    expected_approx = (timezone.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    assert expires_str.startswith(expected_approx[:7])  # Matches year and month


def test_audit_reporting_custody_export_form_invalid_email(tenant_a, document):
    """Verify auditor_email validates email format."""
    form = ChainOfCustodyExportForm(
        data={
            "title": "Bad Email Export",
            "regulatory_framework": "general_compliance",
            "scope": "single_document",
            "document": document.pk,
            "auditor_name": "Auditor",
            "auditor_email": "not-an-email-address",
            "expires_at": "2026-12-31T23:59",
        },
        tenant=tenant_a,
    )
    assert form.is_valid() is False
    assert "auditor_email" in form.errors


def test_audit_reporting_custody_export_form_framework_choices(tenant_a, document):
    """Verify regulatory_framework choices and rejection of unrecognized values."""
    for framework, _ in ChainOfCustodyExport.REGULATORY_FRAMEWORK_CHOICES:
        form = ChainOfCustodyExportForm(
            data={
                "title": f"Audit {framework}",
                "regulatory_framework": framework,
                "scope": "single_document",
                "document": document.pk,
                "auditor_name": "Auditor Name",
                "auditor_email": "auditor@compliance.org",
                "expires_at": "2026-12-31T23:59",
            },
            tenant=tenant_a,
        )
        assert form.is_valid() is True

    # Bad framework
    form_bad = ChainOfCustodyExportForm(
        data={
            "title": "Bad Framework",
            "regulatory_framework": "unrecognized_law",
            "scope": "single_document",
            "document": document.pk,
            "auditor_name": "Auditor",
            "auditor_email": "auditor@compliance.org",
            "expires_at": "2026-12-31T23:59",
        },
        tenant=tenant_a,
    )
    assert form_bad.is_valid() is False
    assert "regulatory_framework" in form_bad.errors


def test_audit_reporting_custody_export_form_widgets():
    """Verify widgets and CSS styling on custody export form."""
    form = ChainOfCustodyExportForm()
    assert "form-input" in form.fields["title"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["regulatory_framework"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["scope"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["document"].widget.attrs.get("class", "")
    assert "form-select" in form.fields["folder"].widget.attrs.get("class", "")
    assert isinstance(form.fields["portal_passcode"].widget, forms.PasswordInput)
    assert isinstance(form.fields["start_date"].widget, forms.DateInput)
    assert form.fields["start_date"].widget.input_type == "date"
    assert isinstance(form.fields["end_date"].widget, forms.DateInput)
    assert form.fields["end_date"].widget.input_type == "date"
    assert isinstance(form.fields["expires_at"].widget, forms.DateTimeInput)
    assert form.fields["expires_at"].widget.input_type == "datetime-local"


# ===========================================================================
# 7. AuditorPortalPasscodeForm Tests
# ===========================================================================

def test_audit_reporting_portal_passcode_form_valid():
    """Verify valid guest passcode entry is accepted."""
    form = AuditorPortalPasscodeForm(data={"passcode": "AuditSecure2026!"})
    assert form.is_valid() is True
    assert form.cleaned_data["passcode"] == "AuditSecure2026!"


def test_audit_reporting_portal_passcode_form_required():
    """Verify passcode is required and empty submission fails."""
    form_empty = AuditorPortalPasscodeForm(data={})
    assert form_empty.is_valid() is False
    assert "passcode" in form_empty.errors

    form_blank = AuditorPortalPasscodeForm(data={"passcode": ""})
    assert form_blank.is_valid() is False
    assert "passcode" in form_blank.errors


def test_audit_reporting_portal_passcode_form_widget():
    """Verify passcode uses PasswordInput widget with specialized styling and autofocus."""
    form = AuditorPortalPasscodeForm()
    widget = form.fields["passcode"].widget
    assert isinstance(widget, forms.PasswordInput)
    css = widget.attrs.get("class", "")
    assert "font-mono" in css
    assert "text-center" in css
    assert widget.attrs.get("autofocus") == "autofocus"
