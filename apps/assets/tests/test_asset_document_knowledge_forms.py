"""
Unit, validation, tenant-isolation, access-classification, widget, and query-bound tests
for Sub-module 11.16: Asset Document & Knowledge Management Forms.

Covers AssetDocumentForm, AssetOperatingProcedureForm,
AssetOperatorCertificationForm, and AssetKnowledgeArticleForm:
1. Package root re-exports vs direct sub-package imports.
2. System/view-owned field exclusion invariant & mass-assignment resistance.
3. Widget assertions (forms.FileInput rather than ClearableFileInput, date/CSS/mono).
4. TenantUniqueMixin + TenantModelForm + scope_tenant_querysets (tenant=None fail-closed,
   tenant_a/tenant_b dropdown isolation across all _TENANT_FIELDS, cross-tenant PK rejection,
   and direct reject_foreign() coverage).
5. readable_asset_document_q(user) enforcement on document selector fields
   (AssetDocumentForm.supersedes, AssetOperatingProcedureForm.primary_document,
   AssetKnowledgeArticleForm.related_document) for anonymous/None, member, owner, reviewer, admin.
6. N+1 select_related optimization checks on AssetOperatorCertificationForm
   (employee_profile -> party, hrm_certificate -> employee__party) and
   AssetKnowledgeArticleForm (incident_report -> asset).
7. JSON field parsing, normalization, and schema validation (loto_isolation_points,
   procedure_steps, five_whys, contributing_factors Fishbone 6M).
8. File upload safety validation (ALLOWED_DOC_EXTENSIONS & MAX_UPLOAD_BYTES) using tmp_path.
9. Negative, date, score, and self-supersedes validation bounds.
"""

from datetime import timedelta
from decimal import Decimal
import json

import pytest
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.assets.forms import (
    AssetDocumentForm,
    AssetKnowledgeArticleForm,
    AssetOperatingProcedureForm,
    AssetOperatorCertificationForm,
    reject_foreign,
)
from apps.assets.forms.AssetDocumentKnowledge import (
    AssetDocumentForm as DirectAssetDocumentForm,
    AssetKnowledgeArticleForm as DirectAssetKnowledgeArticleForm,
    AssetOperatingProcedureForm as DirectAssetOperatingProcedureForm,
    AssetOperatorCertificationForm as DirectAssetOperatorCertificationForm,
)
from apps.assets.forms.AssetDocumentKnowledge._helpers import (
    normalize_json_dict_value,
    normalize_json_list_value,
    validate_safe_doc_upload,
)
from apps.assets.models import (
    AssetDocument,
    AssetKnowledgeArticle,
    AssetOperatingProcedure,
    AssetOperatorCertification,
)
from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.core.models import Document, Party
from apps.hrm.models import EmployeeProfile, TrainingCertificate, TrainingCourse

pytestmark = pytest.mark.django_db


_ASSET_DOCUMENT_KNOWLEDGE_SYSTEM_FIELDS = (
    "tenant",
    "number",
    "status",
    "owner",
    "author",
    "approved_by",
    "approved_at",
    "checked_out_by",
    "checked_out_at",
    "reviewed_by",
    "published_at",
    "original_filename",
    "file_size_bytes",
    "file_checksum",
    "helpful_votes",
    "view_count",
    "sop_acknowledged",
    "sop_acknowledged_at",
    "revision_sequence",
    "is_current_revision",
    "created_at",
    "updated_at",
)


# =====================================================================
# Module-level Helpers (_asset_document_knowledge_*)
# =====================================================================


def _asset_document_knowledge_doc_payload(**overrides):
    data = {
        "title": "Chiller Plant #2 OEM Manual",
        "document_class": "manual",
        "access_classification": "internal_tech",
        "tag_code": "P&ID-CHW-002",
        "manufacturer_ref": "Trane CVHF-770",
        "document_language": "en",
        "storage_location_ref": "Vault Rack B-04",
        "revision_label": "Rev A",
        "change_type": "new_issue",
        "effective_date": timezone.localdate().isoformat(),
        "expiry_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
        "retention_years": "7",
        "description": "Controlled OEM operation and service manual.",
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_proc_payload(**overrides):
    data = {
        "title": "Chiller Main Breaker LOTO SOP",
        "procedure_type": "loto_isolation",
        "safety_level": "high_hazard_loto",
        "revision_label": "Rev 1.0",
        "purpose_scope": "Safe electrical and refrigerant isolation.",
        "hazard_warnings": "480V 3-phase supply and pressurized refrigerant.",
        "required_ppe": "Arc-flash visor, Class 0 gloves",
        "loto_required": True,
        "loto_isolation_points": json.dumps(
            [
                {
                    "energy_source": "Electrical 480V",
                    "tag_id": "MCC-3B",
                    "isolation_point": "Main Disconnect",
                    "lock_device": "Red padlock",
                    "verification_step": "Zero-voltage check",
                }
            ]
        ),
        "procedure_steps": json.dumps(
            [
                {
                    "step_no": 1,
                    "title": "Verify standby",
                    "instruction": "Confirm chiller stopped at HMI",
                    "expected_reading": "0 RPM",
                    "is_mandatory_signoff": True,
                }
            ]
        ),
        "required_qualification_code": "QUAL-LOTO-HV",
        "estimated_duration_minutes": "45",
        "effective_date": timezone.localdate().isoformat(),
        "review_cycle_months": "12",
        "next_review_date": (timezone.localdate() + timedelta(days=180)).isoformat(),
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_cert_payload(operator_user=None, operator_party=None, **overrides):
    today = timezone.localdate()
    data = {
        "title": "LOTO Authorized Technician — High Voltage",
        "qualification_code": "QUAL-LOTO-HV",
        "qualification_type": "loto_authorized",
        "proficiency_level": "qualified_operator",
        "issuing_authority": "OSHA Training Institute",
        "certificate_reference": "CERT-2026-88412",
        "issued_date": today.isoformat(),
        "expires_on": (today + timedelta(days=365)).isoformat(),
        "renewal_lead_days": "30",
        "training_hours": "16.00",
        "assessment_score": "92.50",
        "notes": "Verified practical isolation sign-off.",
    }
    if operator_user is not None:
        data["operator_user"] = str(getattr(operator_user, "pk", operator_user))
    if operator_party is not None:
        data["operator_party"] = str(getattr(operator_party, "pk", operator_party))
    data.update(overrides)
    return data


def _asset_document_knowledge_article_payload(**overrides):
    data = {
        "title": "Chiller Bearing Overheating RCA",
        "article_type": "rca_post_incident",
        "rca_methodology": "five_whys",
        "severity": "high",
        "symptom_problem": "Compressor bearing temperature spiked above 90C.",
        "root_cause_summary": "Oil return strainer fouled with debris.",
        "five_whys": json.dumps(
            [
                {
                    "why_level": 1,
                    "question": "Why did the bearing overheat?",
                    "answer": "Insufficient oil flow",
                }
            ]
        ),
        "contributing_factors": json.dumps(
            {"machine": "Worn strainer", "method": "Missed PM flush"}
        ),
        "remedy_corrective_action": "Flush oil loop and replace strainer.",
        "preventive_lessons": "Add differential-pressure gauge check weekly.",
        "downtime_hours_impacted": "3.50",
        "recurrence_count": "1",
        "tags": "chiller,bearing,oil",
        "incident_occurred_on": timezone.localdate().isoformat(),
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_make_doc(tenant, title="Doc", access="public_floor", owner=None, reviewer=None):
    doc = AssetDocument(
        tenant=tenant,
        title=title,
        document_class="manual",
        access_classification=access,
        revision_label="Rev A",
        change_type="new_issue",
        status="approved",
        owner=owner,
        reviewer=reviewer,
    )
    doc.full_clean()
    doc.save()
    return doc


def _asset_document_knowledge_make_employee_and_cert(tenant, name_suffix, party_name):
    party = Party.objects.create(tenant=tenant, name=party_name, kind="person")
    emp = EmployeeProfile.objects.create(tenant=tenant, party=party, employee_type="full_time")
    course = TrainingCourse.objects.create(
        tenant=tenant,
        title=f"Safety Course {name_suffix}",
        category="safety",
        is_certification=True,
        certification_name=f"Cert {name_suffix}",
        certification_validity_months=12,
    )
    cert = TrainingCertificate.objects.create(
        tenant=tenant,
        employee=emp,
        course=course,
        title=f"HRM Cert {name_suffix}",
    )
    return emp, cert


def _asset_document_knowledge_make_core_doc(tenant, name="Core Doc"):
    return Document.objects.create(
        tenant=tenant,
        name=name,
        file="documents/2026/01/sample.pdf",
        classification="internal",
    )


# =====================================================================
# 1. Package Re-exports
# =====================================================================


def test_asset_document_knowledge_package_reexports():
    assert AssetDocumentForm is DirectAssetDocumentForm
    assert AssetOperatingProcedureForm is DirectAssetOperatingProcedureForm
    assert AssetOperatorCertificationForm is DirectAssetOperatorCertificationForm
    assert AssetKnowledgeArticleForm is DirectAssetKnowledgeArticleForm


# =====================================================================
# 2. System/View-Owned Field Exclusion & Mass-Assignment Resistance
# =====================================================================


@pytest.mark.parametrize(
    "form_cls",
    [
        AssetDocumentForm,
        AssetOperatingProcedureForm,
        AssetOperatorCertificationForm,
        AssetKnowledgeArticleForm,
    ],
)
def test_asset_document_knowledge_system_fields_excluded_from_meta_and_fields(form_cls):
    form = form_cls()
    meta_fields = set(form_cls.Meta.fields)
    for forbidden in _ASSET_DOCUMENT_KNOWLEDGE_SYSTEM_FIELDS:
        assert forbidden not in meta_fields, f"{form_cls.__name__}.Meta.fields leaked {forbidden}"
        assert forbidden not in form.fields, f"{form_cls.__name__}.fields leaked {forbidden}"


def test_asset_document_knowledge_document_form_ignores_tampered_system_fields(
    tenant_a, tenant_b, admin_user, admin_b
):
    tamper = {
        "tenant": str(tenant_b.pk),
        "number": "ADOC-99999",
        "status": "approved",
        "owner": str(admin_b.pk),
        "approved_by": str(admin_b.pk),
        "approved_at": "2026-01-01T00:00:00Z",
        "checked_out_by": str(admin_b.pk),
        "checked_out_at": "2026-01-01T00:00:00Z",
        "original_filename": "forged.pdf",
        "file_size_bytes": "999999",
        "file_checksum": "deadbeef" * 8,
        "revision_sequence": "99",
        "is_current_revision": False,
    }
    form = AssetDocumentForm(
        data=_asset_document_knowledge_doc_payload(**tamper),
        tenant=tenant_a,
        user=admin_user,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a
    assert obj.number != "ADOC-99999"
    assert obj.number.startswith("ADOC-")
    assert obj.status == "draft"
    assert obj.owner is None
    assert obj.approved_by is None
    assert obj.approved_at is None
    assert obj.checked_out_by is None
    assert obj.checked_out_at is None
    assert obj.original_filename == ""
    assert obj.file_size_bytes == 0
    assert obj.file_checksum == ""
    assert obj.revision_sequence == 1
    assert obj.is_current_revision is True


def test_asset_document_knowledge_procedure_form_ignores_tampered_system_fields(
    tenant_a, tenant_b, admin_user, admin_b
):
    tamper = {
        "tenant": str(tenant_b.pk),
        "number": "ASOP-99999",
        "status": "active",
        "author": str(admin_b.pk),
        "approved_by": str(admin_b.pk),
        "approved_at": "2026-01-01T00:00:00Z",
        "original_filename": "forged.pdf",
        "file_checksum": "deadbeef" * 8,
    }
    form = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(**tamper),
        tenant=tenant_a,
        user=admin_user,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a
    assert obj.number != "ASOP-99999"
    assert obj.number.startswith("ASOP-")
    assert obj.status == "draft"
    assert obj.author is None
    assert obj.approved_by is None
    assert obj.approved_at is None
    assert obj.original_filename == ""
    assert obj.file_checksum == ""


def test_asset_document_knowledge_certification_form_ignores_tampered_system_fields(
    tenant_a, tenant_b, admin_user
):
    tamper = {
        "tenant": str(tenant_b.pk),
        "number": "AOCT-99999",
        "status": "active",
        "sop_acknowledged": True,
        "sop_acknowledged_at": "2026-01-01T00:00:00Z",
        "original_filename": "forged.pdf",
        "file_checksum": "deadbeef" * 8,
    }
    form = AssetOperatorCertificationForm(
        data=_asset_document_knowledge_cert_payload(operator_user=admin_user, **tamper),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a
    assert obj.number != "AOCT-99999"
    assert obj.number.startswith("AOCT-")
    assert obj.status == "pending"
    assert obj.sop_acknowledged is False
    assert obj.sop_acknowledged_at is None
    assert obj.original_filename == ""
    assert obj.file_checksum == ""


def test_asset_document_knowledge_article_form_ignores_tampered_system_fields(
    tenant_a, tenant_b, admin_user, admin_b
):
    tamper = {
        "tenant": str(tenant_b.pk),
        "number": "AKBA-99999",
        "status": "published",
        "author": str(admin_b.pk),
        "reviewed_by": str(admin_b.pk),
        "published_at": "2026-01-01T00:00:00Z",
        "helpful_votes": "999",
        "view_count": "8888",
        "original_filename": "forged.pdf",
        "file_checksum": "deadbeef" * 8,
    }
    form = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(**tamper),
        tenant=tenant_a,
        user=admin_user,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a
    assert obj.number != "AKBA-99999"
    assert obj.number.startswith("AKBA-")
    assert obj.status == "draft"
    assert obj.author is None
    assert obj.reviewed_by is None
    assert obj.published_at is None
    assert obj.helpful_votes == 0
    assert obj.view_count == 0
    assert obj.original_filename == ""
    assert obj.file_checksum == ""


# =====================================================================
# 3. Widget & Styling Checks
# =====================================================================


@pytest.mark.parametrize(
    "form_cls,file_field",
    [
        (AssetDocumentForm, "file"),
        (AssetOperatingProcedureForm, "attachment"),
        (AssetOperatorCertificationForm, "certificate_file"),
        (AssetKnowledgeArticleForm, "attachment"),
    ],
)
def test_asset_document_knowledge_file_widgets_use_plain_fileinput_not_clearable(
    form_cls, file_field
):
    form = form_cls()
    widget = form.fields[file_field].widget
    assert type(widget) is forms.FileInput
    assert not isinstance(widget, forms.ClearableFileInput)
    assert "form-input" in widget.attrs.get("class", "")


def test_asset_document_knowledge_date_and_json_widgets_configured():
    doc_form = AssetDocumentForm()
    for field_name in ("effective_date", "expiry_date"):
        assert isinstance(doc_form.fields[field_name].widget, forms.DateInput)
        assert doc_form.fields[field_name].widget.input_type == "date"
        assert "form-input" in doc_form.fields[field_name].widget.attrs.get("class", "")

    proc_form = AssetOperatingProcedureForm()
    for field_name in ("loto_isolation_points", "procedure_steps"):
        css = proc_form.fields[field_name].widget.attrs.get("class", "")
        assert "font-mono" in css
        assert "form-textarea" in css

    art_form = AssetKnowledgeArticleForm()
    for field_name in ("five_whys", "contributing_factors"):
        css = art_form.fields[field_name].widget.attrs.get("class", "")
        assert "font-mono" in css
        assert "form-textarea" in css


# =====================================================================
# 4. Tenant Scoping (tenant=None fail-closed, tenant_a/tenant_b isolation, cross-tenant PK rejection)
# =====================================================================


@pytest.mark.parametrize(
    "form_cls",
    [
        AssetDocumentForm,
        AssetOperatingProcedureForm,
        AssetOperatorCertificationForm,
        AssetKnowledgeArticleForm,
    ],
)
def test_asset_document_knowledge_tenant_none_leaves_all_fk_dropdowns_empty(
    form_cls,
    adk_document_a,
    adk_procedure_a,
    operational_asset_a,
    fixed_asset_a,
    org_unit_a,
    vendor_party_a,
    admin_user,
):
    form = form_cls(tenant=None)
    for field_name in form._TENANT_FIELDS:
        assert field_name in form.fields
        assert form.fields[field_name].queryset.count() == 0


def test_asset_document_knowledge_document_form_fk_scoping_and_cross_tenant_rejection(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    adk_document_a,
    adk_document_b,
    org_unit_a,
    org_unit_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    asset_model_a,
    asset_model_b,
    category_root_a,
    category_root_b,
    spec_template_a,
    spec_template_b,
    warranty_a,
    warranty_b,
    compliance_framework_a,
    compliance_framework_b,
    vendor_party_a,
    vendor_party_b,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = str(tmp_path)
    core_doc_a = _asset_document_knowledge_make_core_doc(tenant_a, "Core A")
    core_doc_b = _asset_document_knowledge_make_core_doc(tenant_b, "Core B")

    form = AssetDocumentForm(tenant=tenant_a, user=admin_user)
    expected_pairs = {
        "supersedes": (adk_document_a, adk_document_b),
        "reviewer": (admin_user, admin_b),
        "org_unit": (org_unit_a, org_unit_b),
        "operational_asset": (operational_asset_a, operational_asset_b),
        "fixed_asset": (fixed_asset_a, fixed_asset_b),
        "asset_model": (asset_model_a, asset_model_b),
        "asset_category": (category_root_a, category_root_b),
        "specification_template": (spec_template_a, spec_template_b),
        "warranty": (warranty_a, warranty_b),
        "compliance_framework": (compliance_framework_a, compliance_framework_b),
        "vendor_party": (vendor_party_a, vendor_party_b),
        "core_document": (core_doc_a, core_doc_b),
    }
    assert set(expected_pairs.keys()) == set(AssetDocumentForm._TENANT_FIELDS.keys())

    for field_name, (own_obj, foreign_obj) in expected_pairs.items():
        qs_pks = set(form.fields[field_name].queryset.values_list("pk", flat=True))
        assert own_obj.pk in qs_pks, f"{field_name} missing tenant_a object"
        assert foreign_obj.pk not in qs_pks, f"{field_name} leaked tenant_b object"

        bad_form = AssetDocumentForm(
            data=_asset_document_knowledge_doc_payload(**{field_name: str(foreign_obj.pk)}),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_asset_document_knowledge_procedure_form_fk_scoping_and_cross_tenant_rejection(
    tenant_a,
    admin_user,
    admin_b,
    adk_procedure_a,
    adk_procedure_b,
    adk_document_a,
    adk_document_b,
    org_unit_a,
    org_unit_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    asset_model_a,
    asset_model_b,
    maintenance_schedule_a,
    maintenance_schedule_b,
    compliance_framework_a,
    compliance_framework_b,
):
    form = AssetOperatingProcedureForm(tenant=tenant_a, user=admin_user)
    expected_pairs = {
        "supersedes": (adk_procedure_a, adk_procedure_b),
        "safety_reviewer": (admin_user, admin_b),
        "org_unit": (org_unit_a, org_unit_b),
        "operational_asset": (operational_asset_a, operational_asset_b),
        "asset_category": (category_root_a, category_root_b),
        "asset_model": (asset_model_a, asset_model_b),
        "maintenance_schedule": (maintenance_schedule_a, maintenance_schedule_b),
        "compliance_framework": (compliance_framework_a, compliance_framework_b),
        "primary_document": (adk_document_a, adk_document_b),
    }
    assert set(expected_pairs.keys()) == set(AssetOperatingProcedureForm._TENANT_FIELDS.keys())

    for field_name, (own_obj, foreign_obj) in expected_pairs.items():
        qs_pks = set(form.fields[field_name].queryset.values_list("pk", flat=True))
        assert own_obj.pk in qs_pks, f"{field_name} missing tenant_a object"
        assert foreign_obj.pk not in qs_pks, f"{field_name} leaked tenant_b object"

        bad_form = AssetOperatingProcedureForm(
            data=_asset_document_knowledge_proc_payload(**{field_name: str(foreign_obj.pk)}),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_asset_document_knowledge_certification_form_fk_scoping_and_cross_tenant_rejection(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    org_unit_a,
    org_unit_b,
    vendor_party_a,
    vendor_party_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    asset_model_a,
    asset_model_b,
    adk_procedure_a,
    adk_procedure_b,
    compliance_framework_a,
    compliance_framework_b,
):
    emp_a, cert_a = _asset_document_knowledge_make_employee_and_cert(
        tenant_a, "A1", "Operator Alice"
    )
    emp_b, cert_b = _asset_document_knowledge_make_employee_and_cert(
        tenant_b, "B1", "Operator Bob"
    )

    form = AssetOperatorCertificationForm(tenant=tenant_a)
    expected_pairs = {
        "org_unit": (org_unit_a, org_unit_b),
        "operator_party": (vendor_party_a, vendor_party_b),
        "operator_user": (admin_user, admin_b),
        "employee_profile": (emp_a, emp_b),
        "hrm_certificate": (cert_a, cert_b),
        "issuing_party": (vendor_party_a, vendor_party_b),
        "assessor": (admin_user, admin_b),
        "operational_asset": (operational_asset_a, operational_asset_b),
        "asset_category": (category_root_a, category_root_b),
        "asset_model": (asset_model_a, asset_model_b),
        "operating_procedure": (adk_procedure_a, adk_procedure_b),
        "compliance_framework": (compliance_framework_a, compliance_framework_b),
    }
    assert set(expected_pairs.keys()) == set(AssetOperatorCertificationForm._TENANT_FIELDS.keys())

    for field_name, (own_obj, foreign_obj) in expected_pairs.items():
        qs_pks = set(form.fields[field_name].queryset.values_list("pk", flat=True))
        assert own_obj.pk in qs_pks, f"{field_name} missing tenant_a object"
        assert foreign_obj.pk not in qs_pks, f"{field_name} leaked tenant_b object"

        payload_kwargs = (
            {"operator_party": vendor_party_a}
            if field_name == "operator_user"
            else {"operator_user": admin_user}
        )
        payload_kwargs[field_name] = str(foreign_obj.pk)
        bad_form = AssetOperatorCertificationForm(
            data=_asset_document_knowledge_cert_payload(**payload_kwargs),
            tenant=tenant_a,
        )
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_asset_document_knowledge_article_form_fk_scoping_and_cross_tenant_rejection(
    tenant_a,
    admin_user,
    org_unit_a,
    org_unit_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    category_root_a,
    category_root_b,
    asset_model_a,
    asset_model_b,
    failure_mode_a,
    failure_mode_b,
    maintenance_request_a,
    maintenance_request_b,
    maintenance_log_a,
    maintenance_log_b,
    incident_a,
    incident_b,
    compliance_incident_a,
    compliance_incident_b,
    adk_document_a,
    adk_document_b,
    adk_procedure_a,
    adk_procedure_b,
):
    form = AssetKnowledgeArticleForm(tenant=tenant_a, user=admin_user)
    expected_pairs = {
        "org_unit": (org_unit_a, org_unit_b),
        "operational_asset": (operational_asset_a, operational_asset_b),
        "fixed_asset": (fixed_asset_a, fixed_asset_b),
        "asset_category": (category_root_a, category_root_b),
        "asset_model": (asset_model_a, asset_model_b),
        "failure_mode": (failure_mode_a, failure_mode_b),
        "maintenance_request": (maintenance_request_a, maintenance_request_b),
        "maintenance_log": (maintenance_log_a, maintenance_log_b),
        "incident_report": (incident_a, incident_b),
        "compliance_incident": (compliance_incident_a, compliance_incident_b),
        "related_document": (adk_document_a, adk_document_b),
        "recommended_procedure": (adk_procedure_a, adk_procedure_b),
    }
    assert set(expected_pairs.keys()) == set(AssetKnowledgeArticleForm._TENANT_FIELDS.keys())

    for field_name, (own_obj, foreign_obj) in expected_pairs.items():
        qs_pks = set(form.fields[field_name].queryset.values_list("pk", flat=True))
        assert own_obj.pk in qs_pks, f"{field_name} missing tenant_a object"
        assert foreign_obj.pk not in qs_pks, f"{field_name} leaked tenant_b object"

        bad_form = AssetKnowledgeArticleForm(
            data=_asset_document_knowledge_article_payload(**{field_name: str(foreign_obj.pk)}),
            tenant=tenant_a,
            user=admin_user,
        )
        assert not bad_form.is_valid()
        assert field_name in bad_form.errors


def test_asset_document_knowledge_reject_foreign_helper_and_none_tenant_save(
    tenant_a, tenant_b, org_unit_a, org_unit_b
):
    form = AssetDocumentForm(data=_asset_document_knowledge_doc_payload(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    reject_foreign(form, {"org_unit": org_unit_b}, ["org_unit"])
    assert "org_unit" in form.errors

    form_ok = AssetDocumentForm(data=_asset_document_knowledge_doc_payload(), tenant=tenant_a)
    assert form_ok.is_valid(), form_ok.errors
    reject_foreign(form_ok, {"org_unit": org_unit_a}, ["org_unit"])
    assert "org_unit" not in form_ok.errors

    # When tenant=None, bound submission hits TenantModelForm/model clean tenant requirement
    no_tenant_form = AssetDocumentForm(data=_asset_document_knowledge_doc_payload(), tenant=None)
    assert not no_tenant_form.is_valid()
    assert "__all__" in no_tenant_form.errors


# =====================================================================
# 5. Access-Classification Scoping via user= (readable_asset_document_q)
# =====================================================================


@pytest.mark.parametrize(
    "form_cls,doc_field,payload_fn",
    [
        (AssetDocumentForm, "supersedes", _asset_document_knowledge_doc_payload),
        (AssetOperatingProcedureForm, "primary_document", _asset_document_knowledge_proc_payload),
        (AssetKnowledgeArticleForm, "related_document", _asset_document_knowledge_article_payload),
    ],
)
def test_asset_document_knowledge_user_readable_document_q_enforcement(
    form_cls,
    doc_field,
    payload_fn,
    tenant_a,
    admin_user,
    member_user,
):
    pub_doc = _asset_document_knowledge_make_doc(
        tenant_a, "Floor Manual", access="public_floor", owner=admin_user
    )
    int_doc = _asset_document_knowledge_make_doc(
        tenant_a, "Internal Spec", access="internal_tech", owner=admin_user
    )
    rest_other = _asset_document_knowledge_make_doc(
        tenant_a, "Restricted Eng", access="restricted_eng", owner=admin_user
    )
    conf_other = _asset_document_knowledge_make_doc(
        tenant_a, "Confidential NDA", access="confidential", owner=admin_user
    )
    rest_owned = _asset_document_knowledge_make_doc(
        tenant_a, "Restricted Owned By Member", access="restricted_eng", owner=member_user
    )
    conf_reviewed = _asset_document_knowledge_make_doc(
        tenant_a,
        "Confidential Reviewed By Member",
        access="confidential",
        owner=admin_user,
        reviewer=member_user,
    )

    # Non-admin member: sees open docs + docs they own or review, NOT others' restricted/confidential
    member_form = form_cls(tenant=tenant_a, user=member_user)
    member_pks = set(member_form.fields[doc_field].queryset.values_list("pk", flat=True))
    assert {pub_doc.pk, int_doc.pk, rest_owned.pk, conf_reviewed.pk} <= member_pks
    assert rest_other.pk not in member_pks
    assert conf_other.pk not in member_pks

    # Member injecting unreadable restricted/confidential PK must fail validation
    for forbidden_doc in (rest_other, conf_other):
        bad = form_cls(
            data=payload_fn(**{doc_field: str(forbidden_doc.pk)}),
            tenant=tenant_a,
            user=member_user,
        )
        assert not bad.is_valid()
        assert doc_field in bad.errors

    # Member selecting owned restricted or reviewed confidential doc succeeds
    for allowed_doc in (rest_owned, conf_reviewed):
        good = form_cls(
            data=payload_fn(**{doc_field: str(allowed_doc.pk)}),
            tenant=tenant_a,
            user=member_user,
        )
        assert good.is_valid(), good.errors

    # Admin sees and can select every tenant_a document
    admin_form = form_cls(tenant=tenant_a, user=admin_user)
    admin_pks = set(admin_form.fields[doc_field].queryset.values_list("pk", flat=True))
    assert {
        pub_doc.pk,
        int_doc.pk,
        rest_other.pk,
        conf_other.pk,
        rest_owned.pk,
        conf_reviewed.pk,
    } <= admin_pks

    admin_select = form_cls(
        data=payload_fn(**{doc_field: str(conf_other.pk)}),
        tenant=tenant_a,
        user=admin_user,
    )
    assert admin_select.is_valid(), admin_select.errors

    # user=None: open classifications only
    anon_form = form_cls(tenant=tenant_a, user=None)
    anon_pks = set(anon_form.fields[doc_field].queryset.values_list("pk", flat=True))
    assert {pub_doc.pk, int_doc.pk} <= anon_pks
    assert rest_other.pk not in anon_pks
    assert conf_other.pk not in anon_pks


# =====================================================================
# 6. N+1 select_related Optimization Checks
# =====================================================================


def test_asset_document_knowledge_certification_form_select_related_and_bounded_queries(
    tenant_a, django_assert_max_num_queries
):
    for i in range(5):
        _asset_document_knowledge_make_employee_and_cert(
            tenant_a, f"N{i}", f"Employee Person {i}"
        )

    form = AssetOperatorCertificationForm(tenant=tenant_a)
    emp_sr = form.fields["employee_profile"].queryset.query.select_related
    cert_sr = form.fields["hrm_certificate"].queryset.query.select_related
    assert isinstance(emp_sr, dict) and "party" in emp_sr
    assert isinstance(cert_sr, dict) and "employee" in cert_sr and "party" in cert_sr["employee"]

    # Evaluating all choices (str(obj) accesses party / employee.party) must not trigger N+1
    with django_assert_max_num_queries(4):
        emp_labels = [label for _, label in form.fields["employee_profile"].choices]
        cert_labels = [label for _, label in form.fields["hrm_certificate"].choices]
    assert len(emp_labels) >= 6  # blank + 5
    assert len(cert_labels) >= 6


def test_asset_document_knowledge_article_form_incident_select_related_and_bounded_queries(
    tenant_a, operational_asset_a, location_a, admin_user, django_assert_max_num_queries
):
    from apps.assets.models import AssetIncidentReport

    for i in range(5):
        AssetIncidentReport.objects.create(
            tenant=tenant_a,
            title=f"Incident {i}",
            asset=operational_asset_a,
            incident_type="damage",
            severity="medium",
            incident_date=timezone.localdate(),
            last_known_location=location_a,
            reported_by=admin_user,
            incident_description="Test",
            status="reported",
        )

    form = AssetKnowledgeArticleForm(tenant=tenant_a, user=admin_user)
    inc_sr = form.fields["incident_report"].queryset.query.select_related
    assert isinstance(inc_sr, dict) and "asset" in inc_sr

    with django_assert_max_num_queries(2):
        inc_labels = [label for _, label in form.fields["incident_report"].choices]
    assert len(inc_labels) >= 6


# =====================================================================
# 7. JSON Field Parsing & Validation
# =====================================================================


def test_asset_document_knowledge_json_normalization_helpers():
    assert normalize_json_list_value(None) == []
    assert normalize_json_list_value("") == []
    assert normalize_json_list_value([{"a": 1}]) == [{"a": 1}]
    assert normalize_json_dict_value(None) == {}
    assert normalize_json_dict_value("") == {}
    assert normalize_json_dict_value({"machine": "pump"}) == {"machine": "pump"}


def test_asset_document_knowledge_procedure_json_fields_validation_and_round_trip(
    tenant_a, admin_user
):
    # Blank strings normalize to [] and validate cleanly
    blank_form = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            loto_isolation_points="", procedure_steps=""
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert blank_form.is_valid(), blank_form.errors
    assert blank_form.cleaned_data["loto_isolation_points"] == []
    assert blank_form.cleaned_data["procedure_steps"] == []

    # Invalid JSON syntax
    bad_syntax = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            loto_isolation_points="{bad-json", procedure_steps="[unclosed"
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_syntax.is_valid()
    assert "loto_isolation_points" in bad_syntax.errors
    assert "procedure_steps" in bad_syntax.errors

    # Invalid schema (dict instead of list, list of primitives instead of dicts)
    bad_schema = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            loto_isolation_points=json.dumps({"not": "a list"}),
            procedure_steps=json.dumps(["plain string"]),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_schema.is_valid()
    assert "loto_isolation_points" in bad_schema.errors
    assert "procedure_steps" in bad_schema.errors

    # Exceeding max items (>50 for LOTO, >100 for steps)
    too_many_loto = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            loto_isolation_points=json.dumps([{"tag_id": f"T-{i}"} for i in range(51)]),
            procedure_steps=json.dumps([{"step_no": i} for i in range(101)]),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not too_many_loto.is_valid()
    assert "loto_isolation_points" in too_many_loto.errors
    assert "procedure_steps" in too_many_loto.errors

    # Valid JSON round-trip save
    loto_payload = [{"energy_source": "Steam", "tag_id": "V-101"}]
    steps_payload = [{"step_no": 1, "title": "Close valve", "instruction": "Turn CW"}]
    good = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            loto_isolation_points=json.dumps(loto_payload),
            procedure_steps=json.dumps(steps_payload),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert good.is_valid(), good.errors
    proc = good.save()
    proc.refresh_from_db()
    assert proc.loto_isolation_points == loto_payload
    assert proc.procedure_steps == steps_payload


def test_asset_document_knowledge_article_json_fields_validation_and_round_trip(
    tenant_a, admin_user
):
    # Blank strings normalize to [] and {}
    blank = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            five_whys="", contributing_factors=""
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert blank.is_valid(), blank.errors
    assert blank.cleaned_data["five_whys"] == []
    assert blank.cleaned_data["contributing_factors"] == {}

    # Invalid JSON syntax
    bad_syntax = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            five_whys="[broken", contributing_factors="{broken"
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_syntax.is_valid()
    assert "five_whys" in bad_syntax.errors
    assert "contributing_factors" in bad_syntax.errors

    # Invalid schema: five_whys > 10 items, contributing_factors has non-6M key or list
    bad_schema = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            five_whys=json.dumps([{"why_level": i} for i in range(11)]),
            contributing_factors=json.dumps({"weather": "Humidity"}),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_schema.is_valid()
    assert "five_whys" in bad_schema.errors
    assert "contributing_factors" in bad_schema.errors

    bad_cf_type = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            contributing_factors=json.dumps(["not", "a", "dict"]),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_cf_type.is_valid()
    assert "contributing_factors" in bad_cf_type.errors

    # Valid 6M Fishbone & 5-Whys round-trip
    whys = [{"why_level": 1, "question": "Why?", "answer": "Seal worn"}]
    factors = {
        "machine": "Scored shaft",
        "method": "Missing torque check",
        "material": "Sub-grade O-ring",
        "manpower": "New shift tech",
        "measurement": "Uncalibrated gauge",
        "environment": "High dust",
    }
    good = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            five_whys=json.dumps(whys),
            contributing_factors=json.dumps(factors),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert good.is_valid(), good.errors
    art = good.save()
    art.refresh_from_db()
    assert art.five_whys == whys
    assert art.contributing_factors == factors


# =====================================================================
# 8. File Upload Validation (ALLOWED_DOC_EXTENSIONS & MAX_UPLOAD_BYTES)
# =====================================================================


def test_asset_document_knowledge_validate_safe_doc_upload_helper():
    assert validate_safe_doc_upload(None) is None
    assert validate_safe_doc_upload("existing/path/manual.pdf") == "existing/path/manual.pdf"

    for ext in (".pdf", ".txt", ".PDF", ".docx", ".png"):
        ok_file = SimpleUploadedFile(f"test{ext}", b"%PDF-1.4 sample")
        assert validate_safe_doc_upload(ok_file) is ok_file
        assert ext.lower() in ALLOWED_DOC_EXTENSIONS

    for bad_name in ("xss.svg", "payload.html", "malware.exe", "noextension"):
        bad_file = SimpleUploadedFile(bad_name, b"<svg/>")
        with pytest.raises(ValidationError):
            validate_safe_doc_upload(bad_file)

    oversized = SimpleUploadedFile("oversized.pdf", b"small-placeholder")
    oversized.size = MAX_UPLOAD_BYTES + 1
    with pytest.raises(ValidationError):
        validate_safe_doc_upload(oversized)


@pytest.mark.parametrize(
    "form_cls,file_field,payload_fn,extra_kwargs",
    [
        (AssetDocumentForm, "file", _asset_document_knowledge_doc_payload, {}),
        (AssetOperatingProcedureForm, "attachment", _asset_document_knowledge_proc_payload, {}),
        (
            AssetOperatorCertificationForm,
            "certificate_file",
            _asset_document_knowledge_cert_payload,
            {"needs_operator": True},
        ),
        (AssetKnowledgeArticleForm, "attachment", _asset_document_knowledge_article_payload, {}),
    ],
)
def test_asset_document_knowledge_all_forms_enforce_upload_safety_with_tmp_media(
    form_cls,
    file_field,
    payload_fn,
    extra_kwargs,
    tenant_a,
    admin_user,
    settings,
    tmp_path,
):
    settings.MEDIA_ROOT = str(tmp_path)
    base_data = (
        payload_fn(operator_user=admin_user)
        if extra_kwargs.get("needs_operator")
        else payload_fn()
    )

    # Accepts .pdf and .txt and saves cleanly inside tmp_path
    for filename, content, ctype in (
        ("manual.pdf", b"%PDF-1.4\nhello\n", "application/pdf"),
        ("notes.txt", b"Plain text procedure\n", "text/plain"),
    ):
        up = SimpleUploadedFile(filename, content, content_type=ctype)
        form = form_cls(data=base_data, files={file_field: up}, tenant=tenant_a)
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.original_filename
        assert saved.file_checksum

    # Rejects .svg, .html, .exe
    for bad_name in ("vector.svg", "page.html", "dropper.exe"):
        bad_up = SimpleUploadedFile(bad_name, b"bad-payload")
        bad_form = form_cls(data=base_data, files={file_field: bad_up}, tenant=tenant_a)
        assert not bad_form.is_valid()
        assert file_field in bad_form.errors

    # Rejects oversized (> 20 MB)
    huge_up = SimpleUploadedFile("huge.pdf", b"x")
    huge_up.size = MAX_UPLOAD_BYTES + 1
    huge_form = form_cls(data=base_data, files={file_field: huge_up}, tenant=tenant_a)
    assert not huge_form.is_valid()
    assert file_field in huge_form.errors


# =====================================================================
# 9. Negative / Date / Score / Self-Supersedes Validation Bounds
# =====================================================================


def test_asset_document_knowledge_document_form_bounds_and_self_supersedes(
    tenant_a, admin_user, adk_document_draft_a
):
    today = timezone.localdate()
    # expiry_date < effective_date
    bad_dates = AssetDocumentForm(
        data=_asset_document_knowledge_doc_payload(
            effective_date=today.isoformat(),
            expiry_date=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_dates.is_valid()
    assert "expiry_date" in bad_dates.errors

    # retention_years < 1
    bad_ret = AssetDocumentForm(
        data=_asset_document_knowledge_doc_payload(retention_years="0"),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_ret.is_valid()
    assert "retention_years" in bad_ret.errors

    # Edit mode excludes instance.pk from supersedes queryset and rejects self-supersedes
    edit_form = AssetDocumentForm(
        instance=adk_document_draft_a, tenant=tenant_a, user=admin_user
    )
    supersedes_pks = set(edit_form.fields["supersedes"].queryset.values_list("pk", flat=True))
    assert adk_document_draft_a.pk not in supersedes_pks

    self_sup = AssetDocumentForm(
        data=_asset_document_knowledge_doc_payload(supersedes=str(adk_document_draft_a.pk)),
        instance=adk_document_draft_a,
        tenant=tenant_a,
        user=admin_user,
    )
    assert not self_sup.is_valid()
    assert "supersedes" in self_sup.errors


def test_asset_document_knowledge_procedure_form_bounds_and_self_supersedes(
    tenant_a, admin_user, adk_procedure_draft_a
):
    today = timezone.localdate()
    bad_dates = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            effective_date=today.isoformat(),
            next_review_date=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_dates.is_valid()
    assert "next_review_date" in bad_dates.errors

    bad_duration = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(
            estimated_duration_minutes="0", review_cycle_months="0"
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_duration.is_valid()
    assert "estimated_duration_minutes" in bad_duration.errors
    assert "review_cycle_months" in bad_duration.errors

    edit_form = AssetOperatingProcedureForm(
        instance=adk_procedure_draft_a, tenant=tenant_a, user=admin_user
    )
    supersedes_pks = set(edit_form.fields["supersedes"].queryset.values_list("pk", flat=True))
    assert adk_procedure_draft_a.pk not in supersedes_pks

    self_sup = AssetOperatingProcedureForm(
        data=_asset_document_knowledge_proc_payload(supersedes=str(adk_procedure_draft_a.pk)),
        instance=adk_procedure_draft_a,
        tenant=tenant_a,
        user=admin_user,
    )
    assert not self_sup.is_valid()
    assert "supersedes" in self_sup.errors


def test_asset_document_knowledge_certification_form_bounds_and_operator_ref_rule(
    tenant_a, admin_user, vendor_party_a
):
    today = timezone.localdate()
    # Missing all operator references (operator_party, operator_user, employee_profile)
    no_op = AssetOperatorCertificationForm(
        data=_asset_document_knowledge_cert_payload(),
        tenant=tenant_a,
    )
    assert not no_op.is_valid()
    assert no_op.non_field_errors()

    # Valid with operator_party alone
    party_only = AssetOperatorCertificationForm(
        data=_asset_document_knowledge_cert_payload(operator_party=vendor_party_a),
        tenant=tenant_a,
    )
    assert party_only.is_valid(), party_only.errors

    # expires_on < issued_date
    bad_dates = AssetOperatorCertificationForm(
        data=_asset_document_knowledge_cert_payload(
            operator_user=admin_user,
            issued_date=today.isoformat(),
            expires_on=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=tenant_a,
    )
    assert not bad_dates.is_valid()
    assert "expires_on" in bad_dates.errors

    # assessment_score < 0 or > 100
    for bad_score in ("-0.10", "100.01", "150"):
        bad = AssetOperatorCertificationForm(
            data=_asset_document_knowledge_cert_payload(
                operator_user=admin_user, assessment_score=bad_score
            ),
            tenant=tenant_a,
        )
        assert not bad.is_valid()
        assert "assessment_score" in bad.errors

    # Boundary scores 0 and 100 are valid
    for ok_score in ("0.00", "100.00"):
        ok = AssetOperatorCertificationForm(
            data=_asset_document_knowledge_cert_payload(
                operator_user=admin_user, assessment_score=ok_score
            ),
            tenant=tenant_a,
        )
        assert ok.is_valid(), ok.errors

    # Negative training_hours and renewal_lead_days < 1
    bad_nums = AssetOperatorCertificationForm(
        data=_asset_document_knowledge_cert_payload(
            operator_user=admin_user,
            training_hours="-1.50",
            renewal_lead_days="0",
        ),
        tenant=tenant_a,
    )
    assert not bad_nums.is_valid()
    assert "training_hours" in bad_nums.errors
    assert "renewal_lead_days" in bad_nums.errors


def test_asset_document_knowledge_article_form_bounds(tenant_a, admin_user):
    # Blank symptom_problem rejected
    missing_sym = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(symptom_problem=""),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not missing_sym.is_valid()
    assert "symptom_problem" in missing_sym.errors

    # Negative downtime_hours_impacted & recurrence_count < 1
    bad_nums = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            downtime_hours_impacted="-0.25",
            recurrence_count="0",
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert not bad_nums.is_valid()
    assert "downtime_hours_impacted" in bad_nums.errors
    assert "recurrence_count" in bad_nums.errors

    # Boundary 0.00 downtime and 1 recurrence valid
    ok = AssetKnowledgeArticleForm(
        data=_asset_document_knowledge_article_payload(
            downtime_hours_impacted="0.00",
            recurrence_count="1",
        ),
        tenant=tenant_a,
        user=admin_user,
    )
    assert ok.is_valid(), ok.errors
