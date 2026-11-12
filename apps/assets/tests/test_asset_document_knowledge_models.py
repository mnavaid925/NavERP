"""
Unit tests for Sub-module 11.16: Asset Document & Knowledge Management Models.
Covers AssetDocument [ADOC-], AssetOperatingProcedure [ASOP-],
AssetOperatorCertification [AOCT-], AssetKnowledgeArticle [AKBA-],
validators, file metadata sync, certification expiry transitions,
is_operator_certified() helper, constraints, and package re-exports.
"""

from datetime import timedelta
from decimal import Decimal
import hashlib

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.forms.AssetDocumentKnowledge._helpers import validate_safe_doc_upload
from apps.assets.models import (
    AssetDocument,
    AssetKnowledgeArticle,
    AssetOperatingProcedure,
    AssetOperatorCertification,
    is_operator_certified,
)
from apps.assets.models.AssetDocumentKnowledge import (
    AssetDocument as DirectAssetDocument,
    AssetKnowledgeArticle as DirectAssetKnowledgeArticle,
    AssetOperatingProcedure as DirectAssetOperatingProcedure,
    AssetOperatorCertification as DirectAssetOperatorCertification,
    is_operator_certified as direct_is_operator_certified,
)
from apps.assets.models.AssetDocumentKnowledge._validators import (
    FISHBONE_6M_KEYS,
    is_asset_document_readable,
    readable_asset_document_q,
    validate_contributing_factors,
    validate_dict_list_field,
)
from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.core.models import Party
from apps.hrm.models import EmployeeProfile
from apps.scm.models import Asset

pytestmark = pytest.mark.django_db

_ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES = {
    "badge-slate",
    "badge-info",
    "badge-amber",
    "badge-green",
    "badge-red",
    "badge-purple",
    "badge-muted",
}


# =====================================================================
# Module-level Helpers (Must start with _asset_document_knowledge_*)
# =====================================================================


def _asset_document_knowledge_create_doc(tenant, title="Controlled OEM Manual", **kwargs):
    data = {
        "tenant": tenant,
        "title": title,
        "document_class": "manual",
        "access_classification": "internal_tech",
        "revision_label": "Rev A",
        "change_type": "new_issue",
        "status": "draft",
    }
    data.update(kwargs)
    return AssetDocument.objects.create(**data)


def _asset_document_knowledge_create_proc(tenant, title="Standard Lockout SOP", **kwargs):
    data = {
        "tenant": tenant,
        "title": title,
        "procedure_type": "sop_operation",
        "safety_level": "standard",
        "revision_label": "Rev 1.0",
        "status": "draft",
    }
    data.update(kwargs)
    return AssetOperatingProcedure.objects.create(**data)


def _asset_document_knowledge_create_cert(
    tenant, title="CNC Operator Qualification", user=None, party=None, **kwargs
):
    data = {
        "tenant": tenant,
        "title": title,
        "qualification_type": "equipment_operator",
        "proficiency_level": "qualified_operator",
        "status": "active",
    }
    if user is not None:
        data["operator_user"] = user
    if party is not None:
        data["operator_party"] = party
    data.update(kwargs)
    return AssetOperatorCertification.objects.create(**data)


def _asset_document_knowledge_create_article(
    tenant, title="Bearing Overheat RCA", symptom_problem="Bearing exceeded 90C", **kwargs
):
    data = {
        "tenant": tenant,
        "title": title,
        "article_type": "rca_post_incident",
        "rca_methodology": "five_whys",
        "severity": "medium",
        "symptom_problem": symptom_problem,
        "status": "draft",
    }
    data.update(kwargs)
    return AssetKnowledgeArticle.objects.create(**data)


def _asset_document_knowledge_make_employee_profile(tenant, name="Operator Jane"):
    party = Party.objects.create(tenant=tenant, name=name, kind="person")
    return EmployeeProfile.objects.create(tenant=tenant, party=party)


# =====================================================================
# 1. Package Re-exports, Constraints & Indexes
# =====================================================================


class TestAssetDocumentKnowledgePackageAndMeta:
    def test_asset_document_knowledge_package_reexports(self):
        assert AssetDocument is DirectAssetDocument
        assert AssetOperatingProcedure is DirectAssetOperatingProcedure
        assert AssetOperatorCertification is DirectAssetOperatorCertification
        assert AssetKnowledgeArticle is DirectAssetKnowledgeArticle
        assert is_operator_certified is direct_is_operator_certified

    def test_asset_document_knowledge_unique_constraints_per_tenant(
        self, tenant_a, tenant_b, admin_user, admin_b
    ):
        doc_a = _asset_document_knowledge_create_doc(tenant_a, title="Doc A1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetDocument.objects.create(
                    tenant=tenant_a, title="Doc A Dup", number=doc_a.number
                )
        doc_b = AssetDocument.objects.create(
            tenant=tenant_b, title="Doc B Same Number", number=doc_a.number
        )
        assert doc_b.pk is not None

        proc_a = _asset_document_knowledge_create_proc(tenant_a, title="Proc A1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetOperatingProcedure.objects.create(
                    tenant=tenant_a, title="Proc A Dup", number=proc_a.number
                )
        proc_b = AssetOperatingProcedure.objects.create(
            tenant=tenant_b, title="Proc B Same Number", number=proc_a.number
        )
        assert proc_b.pk is not None

        cert_a = _asset_document_knowledge_create_cert(
            tenant_a, title="Cert A1", user=admin_user
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetOperatorCertification.objects.create(
                    tenant=tenant_a,
                    title="Cert A Dup",
                    number=cert_a.number,
                    operator_user=admin_user,
                )
        cert_b = AssetOperatorCertification.objects.create(
            tenant=tenant_b,
            title="Cert B Same Number",
            number=cert_a.number,
            operator_user=admin_b,
        )
        assert cert_b.pk is not None

        art_a = _asset_document_knowledge_create_article(tenant_a, title="Art A1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetKnowledgeArticle.objects.create(
                    tenant=tenant_a,
                    title="Art A Dup",
                    symptom_problem="Dup",
                    number=art_a.number,
                )
        art_b = AssetKnowledgeArticle.objects.create(
            tenant=tenant_b,
            title="Art B Same Number",
            symptom_problem="Other tenant",
            number=art_a.number,
        )
        assert art_b.pk is not None

    def test_asset_document_knowledge_meta_constraints_and_indexes_present(self):
        doc_constraints = {c.name for c in AssetDocument._meta.constraints}
        assert "assets_adoc_ten_num_uniq" in doc_constraints
        doc_indexes = {idx.name for idx in AssetDocument._meta.indexes}
        assert {
            "idx_adoc_ten_stat",
            "idx_adoc_ten_cls",
            "idx_adoc_ten_ast",
            "idx_adoc_ten_exp",
            "idx_adoc_ten_cur",
            "idx_adoc_ten_upd",
            "idx_adoc_ten_st_cur",
            "idx_adoc_ten_acc",
            "idx_adoc_ten_chg",
            "idx_adoc_ten_cat",
            "idx_adoc_ten_org",
        }.issubset(doc_indexes)

        proc_constraints = {c.name for c in AssetOperatingProcedure._meta.constraints}
        assert "assets_asop_ten_num_uniq" in proc_constraints
        proc_indexes = {idx.name for idx in AssetOperatingProcedure._meta.indexes}
        assert {
            "idx_asop_ten_stat",
            "idx_asop_ten_type",
            "idx_asop_ten_haz",
            "idx_asop_ten_rev",
            "idx_asop_ten_upd",
            "idx_asop_ten_st_rev",
            "idx_asop_ten_ast",
            "idx_asop_ten_cat",
            "idx_asop_ten_loto",
        }.issubset(proc_indexes)

        cert_constraints = {c.name for c in AssetOperatorCertification._meta.constraints}
        assert "assets_aoct_ten_num_uniq" in cert_constraints
        cert_indexes = {idx.name for idx in AssetOperatorCertification._meta.indexes}
        assert {
            "idx_aoct_ten_stat",
            "idx_aoct_ten_type",
            "idx_aoct_ten_exp",
            "idx_aoct_ten_usr",
            "idx_aoct_ten_pty",
            "idx_aoct_ten_prof",
            "idx_aoct_ten_ast",
            "idx_aoct_ten_sop",
        }.issubset(cert_indexes)

        art_constraints = {c.name for c in AssetKnowledgeArticle._meta.constraints}
        assert "assets_akba_ten_num_uniq" in art_constraints
        art_indexes = {idx.name for idx in AssetKnowledgeArticle._meta.indexes}
        assert {
            "idx_akba_ten_stat",
            "idx_akba_ten_type",
            "idx_akba_ten_sev",
            "idx_akba_ten_rca",
            "idx_akba_ten_ast",
            "idx_akba_ten_pub_upd",
            "idx_akba_ten_fm",
        }.issubset(art_indexes)


# =====================================================================
# 2. Auto-numbering & __str__ Representations
# =====================================================================


class TestAssetDocumentKnowledgeAutonumberAndStr:
    def test_asset_document_knowledge_autonumber_prefixes_and_sequences(
        self, tenant_a, tenant_b, admin_user, admin_b
    ):
        d1 = _asset_document_knowledge_create_doc(tenant_a, title="Doc 1")
        d2 = _asset_document_knowledge_create_doc(tenant_a, title="Doc 2")
        db1 = _asset_document_knowledge_create_doc(tenant_b, title="Doc B1")
        assert d1.number.startswith("ADOC-")
        assert int(d2.number.split("-")[1]) == int(d1.number.split("-")[1]) + 1
        assert db1.number == d1.number

        p1 = _asset_document_knowledge_create_proc(tenant_a, title="Proc 1")
        p2 = _asset_document_knowledge_create_proc(tenant_a, title="Proc 2")
        pb1 = _asset_document_knowledge_create_proc(tenant_b, title="Proc B1")
        assert p1.number.startswith("ASOP-")
        assert int(p2.number.split("-")[1]) == int(p1.number.split("-")[1]) + 1
        assert pb1.number == p1.number

        c1 = _asset_document_knowledge_create_cert(tenant_a, title="Cert 1", user=admin_user)
        c2 = _asset_document_knowledge_create_cert(tenant_a, title="Cert 2", user=admin_user)
        cb1 = _asset_document_knowledge_create_cert(tenant_b, title="Cert B1", user=admin_b)
        assert c1.number.startswith("AOCT-")
        assert int(c2.number.split("-")[1]) == int(c1.number.split("-")[1]) + 1
        assert cb1.number == c1.number

        a1 = _asset_document_knowledge_create_article(tenant_a, title="Art 1")
        a2 = _asset_document_knowledge_create_article(tenant_a, title="Art 2")
        ab1 = _asset_document_knowledge_create_article(tenant_b, title="Art B1")
        assert a1.number.startswith("AKBA-")
        assert int(a2.number.split("-")[1]) == int(a1.number.split("-")[1]) + 1
        assert ab1.number == a1.number

    def test_asset_document_knowledge_str_representations(
        self,
        tenant_a,
        adk_document_a,
        adk_procedure_a,
        adk_certification_a,
        adk_article_a,
        vendor_party_a,
        admin_user,
    ):
        assert (
            str(adk_document_a)
            == f"{adk_document_a.number} \u00b7 {adk_document_a.title} ({adk_document_a.revision_label})"
        )
        unsaved_doc = AssetDocument(tenant=tenant_a, title="Unsaved Doc")
        assert str(unsaved_doc) == "Unsaved Doc"

        assert (
            str(adk_procedure_a)
            == f"{adk_procedure_a.number} \u00b7 {adk_procedure_a.title} ({adk_procedure_a.revision_label})"
        )
        unsaved_proc = AssetOperatingProcedure(tenant=tenant_a, title="Unsaved Proc")
        assert str(unsaved_proc) == "Unsaved Proc"

        assert (
            str(adk_certification_a)
            == f"{adk_certification_a.number} \u00b7 {vendor_party_a} ({adk_certification_a.title})"
        )
        unsaved_cert = AssetOperatorCertification(tenant=tenant_a, title="Unsaved Cert")
        assert str(unsaved_cert) == "Unsaved Cert"

        assert str(adk_article_a) == f"{adk_article_a.number} \u00b7 {adk_article_a.title}"
        unsaved_art = AssetKnowledgeArticle(
            tenant=tenant_a, title="Unsaved Art", symptom_problem="Test"
        )
        assert str(unsaved_art) == "Unsaved Art"

    def test_asset_document_knowledge_operator_display_name_precedence(
        self, tenant_a, vendor_party_a, admin_user
    ):
        emp = _asset_document_knowledge_make_employee_profile(tenant_a, "Alex Rivera")
        admin_user.first_name = "Alice"
        admin_user.last_name = "Admin"
        admin_user.save()

        cert = AssetOperatorCertification(
            tenant=tenant_a,
            title="Precedence Check",
            operator_party=vendor_party_a,
            employee_profile=emp,
            operator_user=admin_user,
        )
        assert cert.operator_display_name == str(vendor_party_a)

        cert.operator_party = None
        assert cert.operator_display_name == str(emp)

        cert.employee_profile = None
        assert cert.operator_display_name == "Alice Admin"

        admin_user.first_name = ""
        admin_user.last_name = ""
        admin_user.save()
        cert.operator_user.refresh_from_db()
        assert cert.operator_display_name == admin_user.username

        cert.operator_user = None
        assert cert.operator_display_name == "\u2014"


# =====================================================================
# 3. Choices, CSS Mappings, Status Locking & Helper Properties
# =====================================================================


class TestAssetDocumentKnowledgeChoicesCssAndProperties:
    def test_asset_document_knowledge_document_choices_css_and_properties(
        self, tenant_a, adk_document_a
    ):
        assert {c[0] for c in AssetDocument.DOCUMENT_CLASS_CHOICES} == {
            "manual",
            "schematic_pid",
            "electrical_diagram",
            "datasheet",
            "warranty_cert",
            "calibration_cert",
            "compliance_cert",
            "inspection_dossier",
            "vendor_transmittal",
            "as_built_drawing",
        }
        assert {c[0] for c in AssetDocument.ACCESS_CLASSIFICATION_CHOICES} == {
            "public_floor",
            "internal_tech",
            "restricted_eng",
            "confidential",
        }
        assert {c[0] for c in AssetDocument.CHANGE_TYPE_CHOICES} == {
            "new_issue",
            "drawing_redline",
            "spec_update",
            "vendor_bulletin",
            "regulatory_update",
            "as_built_reconcile",
        }
        status_keys = {c[0] for c in AssetDocument.STATUS_CHOICES}
        assert status_keys == {"draft", "in_review", "approved", "superseded", "archived"}
        assert set(AssetDocument.STATUS_CSS.keys()) == status_keys
        assert AssetDocument.EDITABLE_STATUSES == {"draft", "in_review"}
        assert AssetDocument.LOCKED_STATUSES == {"approved", "superseded", "archived"}

        for val, css in AssetDocument.STATUS_CSS.items():
            adk_document_a.status = val
            assert adk_document_a.status_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
            assert adk_document_a.is_locked is (val in AssetDocument.LOCKED_STATUSES)
            assert (val in AssetDocument.EDITABLE_STATUSES) is (not adk_document_a.is_locked)
        adk_document_a.status = "unknown"
        assert adk_document_a.status_badge_class == "badge-slate"

        for val, css in AssetDocument.ACCESS_CLASSIFICATION_CSS.items():
            adk_document_a.access_classification = val
            assert adk_document_a.access_classification_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
        adk_document_a.access_classification = "unknown"
        assert adk_document_a.access_classification_badge_class == "badge-slate"

        today = timezone.localdate()
        doc = _asset_document_knowledge_create_doc(tenant_a, title="Expiry Helper Doc")
        assert doc.is_expired is False
        assert doc.is_expiring_soon is False
        assert doc.short_checksum == ""

        doc.expiry_date = today - timedelta(days=1)
        assert doc.is_expired is True
        assert doc.is_expiring_soon is False

        doc.expiry_date = today + timedelta(days=15)
        assert doc.is_expired is False
        assert doc.is_expiring_soon is True

        doc.expiry_date = today + timedelta(days=45)
        assert doc.is_expired is False
        assert doc.is_expiring_soon is False

        doc.file_checksum = "abcdef1234567890"
        assert doc.short_checksum == "abcdef123456"

    def test_asset_document_knowledge_procedure_choices_css_and_properties(
        self, tenant_a, adk_procedure_a
    ):
        assert {c[0] for c in AssetOperatingProcedure.PROCEDURE_TYPE_CHOICES} == {
            "sop_operation",
            "pm_protocol",
            "loto_isolation",
            "emergency_shutdown",
            "commissioning",
            "calibration_protocol",
            "inspection_checklist",
        }
        safety_keys = {c[0] for c in AssetOperatingProcedure.SAFETY_LEVEL_CHOICES}
        assert safety_keys == {
            "standard",
            "caution",
            "high_hazard_loto",
            "permit_required",
        }
        status_keys = {c[0] for c in AssetOperatingProcedure.STATUS_CHOICES}
        assert status_keys == {"draft", "under_review", "active", "superseded", "retired"}
        assert set(AssetOperatingProcedure.STATUS_CSS.keys()) == status_keys
        assert set(AssetOperatingProcedure.SAFETY_CSS.keys()) == safety_keys
        assert AssetOperatingProcedure.EDITABLE_STATUSES == {"draft", "under_review"}
        assert AssetOperatingProcedure.LOCKED_STATUSES == {
            "active",
            "superseded",
            "retired",
        }

        for val, css in AssetOperatingProcedure.STATUS_CSS.items():
            adk_procedure_a.status = val
            assert adk_procedure_a.status_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
            assert adk_procedure_a.is_locked is (
                val in AssetOperatingProcedure.LOCKED_STATUSES
            )
            assert (val in AssetOperatingProcedure.EDITABLE_STATUSES) is (
                not adk_procedure_a.is_locked
            )
        adk_procedure_a.status = "unknown"
        assert adk_procedure_a.status_badge_class == "badge-slate"

        for val, css in AssetOperatingProcedure.SAFETY_CSS.items():
            adk_procedure_a.safety_level = val
            assert adk_procedure_a.safety_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
        adk_procedure_a.safety_level = "unknown"
        assert adk_procedure_a.safety_badge_class == "badge-slate"

        today = timezone.localdate()
        proc = _asset_document_knowledge_create_proc(
            tenant_a,
            title="Review Overdue Proc",
            status="active",
            next_review_date=today - timedelta(days=2),
            procedure_steps=[{"step": "Verify zero energy"}, {"step": "Apply lock"}],
            loto_isolation_points=[{"tag": "BKR-101", "energy": "480V"}],
        )
        assert proc.is_review_overdue is True
        assert proc.step_count == 2
        assert proc.isolation_point_count == 1
        proc.status = "draft"
        assert proc.is_review_overdue is False

    def test_asset_document_knowledge_certification_choices_css_and_properties(
        self, adk_certification_a
    ):
        assert {c[0] for c in AssetOperatorCertification.QUALIFICATION_TYPE_CHOICES} == {
            "equipment_operator",
            "maintenance_technician",
            "loto_authorized",
            "electrical_hv",
            "confined_space",
            "crane_rigging",
            "pressure_welding",
            "calibration_specialist",
            "oem_certified",
        }
        prof_keys = {c[0] for c in AssetOperatorCertification.PROFICIENCY_LEVEL_CHOICES}
        assert prof_keys == {
            "trainee_supervised",
            "qualified_operator",
            "senior_technician",
            "lead_inspector",
            "trainer_assessor",
        }
        status_keys = {c[0] for c in AssetOperatorCertification.STATUS_CHOICES}
        assert status_keys == {"pending", "active", "expiring_soon", "expired", "revoked"}
        assert set(AssetOperatorCertification.STATUS_CSS.keys()) == status_keys
        assert set(AssetOperatorCertification.PROFICIENCY_CSS.keys()) == prof_keys
        assert AssetOperatorCertification.EDITABLE_STATUSES == {
            "pending",
            "active",
            "expiring_soon",
        }

        for val, css in AssetOperatorCertification.STATUS_CSS.items():
            adk_certification_a.status = val
            assert adk_certification_a.status_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
        adk_certification_a.status = "unknown"
        assert adk_certification_a.status_badge_class == "badge-slate"

        for val, css in AssetOperatorCertification.PROFICIENCY_CSS.items():
            adk_certification_a.proficiency_level = val
            assert adk_certification_a.proficiency_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
        adk_certification_a.proficiency_level = "unknown"
        assert adk_certification_a.proficiency_badge_class == "badge-slate"

        today = timezone.localdate()
        adk_certification_a.expires_on = None
        assert adk_certification_a.days_until_expiry is None
        assert adk_certification_a.is_expired is False
        assert adk_certification_a.is_renewal_due is False

        adk_certification_a.renewal_lead_days = 30
        adk_certification_a.expires_on = today + timedelta(days=10)
        assert adk_certification_a.days_until_expiry == 10
        assert adk_certification_a.is_expired is False
        assert adk_certification_a.is_renewal_due is True

        adk_certification_a.expires_on = today - timedelta(days=1)
        assert adk_certification_a.is_expired is True
        assert adk_certification_a.is_renewal_due is False

    def test_asset_document_knowledge_article_choices_css_and_properties(
        self, adk_article_a
    ):
        assert {c[0] for c in AssetKnowledgeArticle.ARTICLE_TYPE_CHOICES} == {
            "rca_post_incident",
            "lessons_learned",
            "troubleshooting_guide",
            "failure_bulletin",
            "oem_service_advisory",
            "pm_optimization_note",
        }
        assert {c[0] for c in AssetKnowledgeArticle.RCA_METHODOLOGY_CHOICES} == {
            "five_whys",
            "fishbone_ishikawa",
            "problem_cause_remedy",
            "fmea_feedback",
            "fault_tree",
            "general_kb",
        }
        sev_keys = {c[0] for c in AssetKnowledgeArticle.SEVERITY_CHOICES}
        assert sev_keys == {"low", "medium", "high", "critical"}
        status_keys = {c[0] for c in AssetKnowledgeArticle.STATUS_CHOICES}
        assert status_keys == {"draft", "peer_review", "published", "retired"}
        assert set(AssetKnowledgeArticle.STATUS_CSS.keys()) == status_keys
        assert set(AssetKnowledgeArticle.SEVERITY_CSS.keys()) == sev_keys
        assert AssetKnowledgeArticle.EDITABLE_STATUSES == {"draft", "peer_review"}
        assert AssetKnowledgeArticle.LOCKED_STATUSES == {"published", "retired"}

        for val, css in AssetKnowledgeArticle.STATUS_CSS.items():
            adk_article_a.status = val
            assert adk_article_a.status_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
            assert adk_article_a.is_locked is (val in AssetKnowledgeArticle.LOCKED_STATUSES)
            assert (val in AssetKnowledgeArticle.EDITABLE_STATUSES) is (
                not adk_article_a.is_locked
            )
        adk_article_a.status = "unknown"
        assert adk_article_a.status_badge_class == "badge-slate"

        for val, css in AssetKnowledgeArticle.SEVERITY_CSS.items():
            adk_article_a.severity = val
            assert adk_article_a.severity_badge_class == css
            assert css in _ASSET_DOCUMENT_KNOWLEDGE_VALID_BADGE_CLASSES
        adk_article_a.severity = "unknown"
        assert adk_article_a.severity_badge_class == "badge-slate"

        adk_article_a.tags = " spindle , , coolant, bearing "
        assert adk_article_a.tag_list == ["spindle", "coolant", "bearing"]
        adk_article_a.tags = ""
        assert adk_article_a.tag_list == []


# =====================================================================
# 4. Validation in clean() & Shared Validators
# =====================================================================


class TestAssetDocumentKnowledgeValidation:
    def test_asset_document_knowledge_cross_tenant_fk_rejection_document(
        self,
        tenant_a,
        adk_document_b,
        admin_b,
        org_unit_b,
        operational_asset_b,
        fixed_asset_b,
        asset_model_b,
        category_root_b,
        spec_template_b,
        compliance_framework_b,
        vendor_party_b,
    ):
        missing_tenant_doc = AssetDocument(title="No Tenant")
        with pytest.raises(ValidationError) as exc_missing:
            missing_tenant_doc.clean()
        assert "__all__" in exc_missing.value.message_dict

        bad_fks = {
            "supersedes": adk_document_b,
            "checked_out_by": admin_b,
            "owner": admin_b,
            "reviewer": admin_b,
            "approved_by": admin_b,
            "org_unit": org_unit_b,
            "operational_asset": operational_asset_b,
            "fixed_asset": fixed_asset_b,
            "asset_model": asset_model_b,
            "asset_category": category_root_b,
            "specification_template": spec_template_b,
            "compliance_framework": compliance_framework_b,
            "vendor_party": vendor_party_b,
        }
        for field_name, foreign_obj in bad_fks.items():
            doc = AssetDocument(
                tenant=tenant_a,
                title=f"Cross-Tenant {field_name}",
                **{field_name: foreign_obj},
            )
            with pytest.raises(ValidationError) as exc_info:
                doc.clean()
            assert field_name in exc_info.value.message_dict

    def test_asset_document_knowledge_cross_tenant_fk_rejection_procedure(
        self,
        tenant_a,
        adk_procedure_b,
        adk_document_b,
        admin_b,
        org_unit_b,
        operational_asset_b,
        category_root_b,
        asset_model_b,
        maintenance_schedule_b,
        compliance_framework_b,
    ):
        bad_fks = {
            "supersedes": adk_procedure_b,
            "author": admin_b,
            "safety_reviewer": admin_b,
            "approved_by": admin_b,
            "org_unit": org_unit_b,
            "operational_asset": operational_asset_b,
            "asset_category": category_root_b,
            "asset_model": asset_model_b,
            "maintenance_schedule": maintenance_schedule_b,
            "compliance_framework": compliance_framework_b,
            "primary_document": adk_document_b,
        }
        for field_name, foreign_obj in bad_fks.items():
            proc = AssetOperatingProcedure(
                tenant=tenant_a,
                title=f"Cross-Tenant {field_name}",
                **{field_name: foreign_obj},
            )
            with pytest.raises(ValidationError) as exc_info:
                proc.clean()
            assert field_name in exc_info.value.message_dict

    def test_asset_document_knowledge_cross_tenant_fk_rejection_certification(
        self,
        tenant_a,
        tenant_b,
        admin_user,
        admin_b,
        org_unit_b,
        vendor_party_b,
        operational_asset_b,
        category_root_b,
        asset_model_b,
        adk_procedure_b,
        compliance_framework_b,
    ):
        emp_b = _asset_document_knowledge_make_employee_profile(tenant_b, "Globex Tech")
        bad_fks = {
            "org_unit": org_unit_b,
            "operator_party": vendor_party_b,
            "operator_user": admin_b,
            "employee_profile": emp_b,
            "issuing_party": vendor_party_b,
            "assessor": admin_b,
            "operational_asset": operational_asset_b,
            "asset_category": category_root_b,
            "asset_model": asset_model_b,
            "operating_procedure": adk_procedure_b,
            "compliance_framework": compliance_framework_b,
        }
        for field_name, foreign_obj in bad_fks.items():
            kwargs = {"operator_user": admin_user} if field_name != "operator_user" else {}
            kwargs[field_name] = foreign_obj
            cert = AssetOperatorCertification(
                tenant=tenant_a,
                title=f"Cross-Tenant {field_name}",
                **kwargs,
            )
            with pytest.raises(ValidationError) as exc_info:
                cert.clean()
            assert field_name in exc_info.value.message_dict

    def test_asset_document_knowledge_cross_tenant_fk_rejection_article(
        self,
        tenant_a,
        admin_b,
        org_unit_b,
        operational_asset_b,
        fixed_asset_b,
        category_root_b,
        asset_model_b,
        failure_mode_b,
        maintenance_request_b,
        maintenance_log_b,
        incident_b,
        compliance_incident_b,
        adk_document_b,
        adk_procedure_b,
    ):
        bad_fks = {
            "author": admin_b,
            "reviewed_by": admin_b,
            "org_unit": org_unit_b,
            "operational_asset": operational_asset_b,
            "fixed_asset": fixed_asset_b,
            "asset_category": category_root_b,
            "asset_model": asset_model_b,
            "failure_mode": failure_mode_b,
            "maintenance_request": maintenance_request_b,
            "maintenance_log": maintenance_log_b,
            "incident_report": incident_b,
            "compliance_incident": compliance_incident_b,
            "related_document": adk_document_b,
            "recommended_procedure": adk_procedure_b,
        }
        for field_name, foreign_obj in bad_fks.items():
            article = AssetKnowledgeArticle(
                tenant=tenant_a,
                title=f"Cross-Tenant {field_name}",
                symptom_problem="Test symptom",
                **{field_name: foreign_obj},
            )
            with pytest.raises(ValidationError) as exc_info:
                article.clean()
            assert field_name in exc_info.value.message_dict

    def test_asset_document_knowledge_supersedes_self_and_cycle_rejection(
        self, tenant_a, tenant_b
    ):
        d1 = _asset_document_knowledge_create_doc(tenant_a, title="Rev 1")
        d2 = _asset_document_knowledge_create_doc(
            tenant_a, title="Rev 2", supersedes=d1, revision_label="Rev B"
        )
        d3 = _asset_document_knowledge_create_doc(
            tenant_a, title="Rev 3", supersedes=d2, revision_label="Rev C"
        )

        # Self-link rejection
        d1.supersedes = d1
        with pytest.raises(ValidationError) as exc_self:
            d1.clean()
        assert "supersedes" in exc_self.value.message_dict

        # Direct 2-hop cycle: d1 -> d2 -> d1
        d1.supersedes = d2
        with pytest.raises(ValidationError) as exc_direct:
            d1.clean()
        assert "supersedes" in exc_direct.value.message_dict

        # Multi-hop 3-node cycle: d1 -> d3 -> d2 -> d1
        d1.supersedes = d3
        with pytest.raises(ValidationError) as exc_multi:
            d1.clean()
        assert "supersedes" in exc_multi.value.message_dict

        # Procedure self-link & cycle
        p1 = _asset_document_knowledge_create_proc(tenant_a, title="SOP 1")
        p2 = _asset_document_knowledge_create_proc(
            tenant_a, title="SOP 2", supersedes=p1
        )
        p1.supersedes = p1
        with pytest.raises(ValidationError) as exc_pself:
            p1.clean()
        assert "supersedes" in exc_pself.value.message_dict

        p1.supersedes = p2
        with pytest.raises(ValidationError) as exc_pcycle:
            p1.clean()
        assert "supersedes" in exc_pcycle.value.message_dict

        # Tenant-scoped walk: if d2 was corrupted in DB to point into tenant_b,
        # walking from d3 (tenant_a) filters by tenant_id and stops cleanly at d2.
        db_doc = _asset_document_knowledge_create_doc(tenant_b, title="Other Tenant Doc")
        AssetDocument.objects.filter(pk=d2.pk).update(supersedes=db_doc)
        d1.supersedes = None
        d3.refresh_from_db()
        d3.clean()  # Should not follow across tenants

        # Depth overflow (>25 hops)
        AssetDocument.objects.filter(pk=d2.pk).update(supersedes=d1)
        head = d1
        for idx in range(26):
            head = _asset_document_knowledge_create_doc(
                tenant_a, title=f"Chain {idx}", supersedes=head
            )
        too_deep = AssetDocument(
            tenant=tenant_a, title="Too Deep", supersedes=head
        )
        with pytest.raises(ValidationError) as exc_depth:
            too_deep.clean()
        assert "supersedes" in exc_depth.value.message_dict

    def test_asset_document_knowledge_json_validators_dict_list_and_fishbone(
        self, tenant_a
    ):
        # Procedure steps & LOTO isolation points
        bad_proc = AssetOperatingProcedure(
            tenant=tenant_a,
            title="Bad JSON Proc",
            procedure_steps={"not": "a list"},
            loto_isolation_points=["not a dict"],
        )
        with pytest.raises(ValidationError) as exc_proc:
            bad_proc.clean()
        assert "procedure_steps" in exc_proc.value.message_dict
        assert "loto_isolation_points" in exc_proc.value.message_dict

        too_many_steps = AssetOperatingProcedure(
            tenant=tenant_a,
            title="101 Steps",
            procedure_steps=[{"step": f"S{i}"} for i in range(101)],
            loto_isolation_points=[{"tag": f"L{i}"} for i in range(51)],
        )
        with pytest.raises(ValidationError) as exc_max:
            too_many_steps.clean()
        assert "procedure_steps" in exc_max.value.message_dict
        assert "loto_isolation_points" in exc_max.value.message_dict

        # Direct required_keys check on validate_dict_list_field
        errs = {}
        validate_dict_list_field(
            [{"step": "   "}],
            errs,
            "procedure_steps",
            max_items=10,
            required_keys=("step",),
            label="Procedure steps",
        )
        assert "procedure_steps" in errs

        # Article 5-Whys & Fishbone 6M contributing_factors
        bad_article = AssetKnowledgeArticle(
            tenant=tenant_a,
            title="Bad JSON Article",
            symptom_problem="Motor trip",
            five_whys=[{"why": str(i)} for i in range(11)],
            contributing_factors=["not_a_dict"],
        )
        with pytest.raises(ValidationError) as exc_art:
            bad_article.clean()
        assert "five_whys" in exc_art.value.message_dict
        assert "contributing_factors" in exc_art.value.message_dict

        unknown_6m = AssetKnowledgeArticle(
            tenant=tenant_a,
            title="Unknown 6M Keys",
            symptom_problem="Motor trip",
            contributing_factors={"machine": "Bearing", "weather_unknown": "Bad"},
        )
        with pytest.raises(ValidationError) as exc_6m:
            unknown_6m.clean()
        assert "contributing_factors" in exc_6m.value.message_dict

        valid_6m = AssetKnowledgeArticle(
            tenant=tenant_a,
            title="Valid 6M Keys",
            symptom_problem="Motor trip",
            five_whys=[{"why": "1", "answer": "Overload"}],
            contributing_factors={k: f"Factor for {k}" for k in FISHBONE_6M_KEYS},
        )
        valid_6m.clean()

        errs_cf = {}
        validate_contributing_factors(None, errs_cf)
        validate_contributing_factors("", errs_cf)
        assert errs_cf == {}

    def test_asset_document_knowledge_date_and_numeric_bounds_in_clean(
        self, tenant_a, admin_user
    ):
        today = timezone.localdate()

        # AssetDocument bounds
        bad_doc = AssetDocument(
            tenant=tenant_a,
            title="Bad Dates Doc",
            effective_date=today,
            expiry_date=today - timedelta(days=1),
            revision_sequence=0,
            retention_years=0,
        )
        with pytest.raises(ValidationError) as exc_doc:
            bad_doc.clean()
        assert "expiry_date" in exc_doc.value.message_dict
        assert "revision_sequence" in exc_doc.value.message_dict
        assert "retention_years" in exc_doc.value.message_dict

        # AssetOperatingProcedure bounds
        bad_proc = AssetOperatingProcedure(
            tenant=tenant_a,
            title="Bad Bounds Proc",
            estimated_duration_minutes=0,
            review_cycle_months=0,
            effective_date=today,
            next_review_date=today - timedelta(days=1),
        )
        with pytest.raises(ValidationError) as exc_proc:
            bad_proc.clean()
        assert "estimated_duration_minutes" in exc_proc.value.message_dict
        assert "review_cycle_months" in exc_proc.value.message_dict
        assert "next_review_date" in exc_proc.value.message_dict

        # AssetOperatorCertification bounds
        no_operator = AssetOperatorCertification(
            tenant=tenant_a,
            title="No Operator Assigned",
        )
        with pytest.raises(ValidationError) as exc_no_op:
            no_operator.clean()
        assert "__all__" in exc_no_op.value.message_dict

        # Employee profile alone satisfies operator requirement
        emp = _asset_document_knowledge_make_employee_profile(tenant_a, "Emp Solo")
        emp_cert = AssetOperatorCertification(
            tenant=tenant_a,
            title="Emp Only Cert",
            employee_profile=emp,
            assessment_score=Decimal("100.00"),
            training_hours=Decimal("0.00"),
            renewal_lead_days=1,
        )
        emp_cert.clean()

        bad_cert = AssetOperatorCertification(
            tenant=tenant_a,
            title="Bad Bounds Cert",
            operator_user=admin_user,
            issued_date=today,
            expires_on=today - timedelta(days=1),
            training_hours=Decimal("-1.00"),
            assessment_score=Decimal("100.01"),
            renewal_lead_days=0,
        )
        with pytest.raises(ValidationError) as exc_cert:
            bad_cert.clean()
        assert "expires_on" in exc_cert.value.message_dict
        assert "training_hours" in exc_cert.value.message_dict
        assert "assessment_score" in exc_cert.value.message_dict
        assert "renewal_lead_days" in exc_cert.value.message_dict

        neg_score_cert = AssetOperatorCertification(
            tenant=tenant_a,
            title="Negative Score Cert",
            operator_user=admin_user,
            assessment_score=Decimal("-0.01"),
        )
        with pytest.raises(ValidationError) as exc_neg:
            neg_score_cert.clean()
        assert "assessment_score" in exc_neg.value.message_dict

        # AssetKnowledgeArticle bounds
        bad_art = AssetKnowledgeArticle(
            tenant=tenant_a,
            title="Bad Bounds Article",
            symptom_problem="Fault",
            downtime_hours_impacted=Decimal("-0.50"),
            recurrence_count=0,
        )
        with pytest.raises(ValidationError) as exc_art:
            bad_art.clean()
        assert "downtime_hours_impacted" in exc_art.value.message_dict
        assert "recurrence_count" in exc_art.value.message_dict

    def test_asset_document_knowledge_upload_extension_and_size_validators(self):
        assert ".pdf" in ALLOWED_DOC_EXTENSIONS
        assert ".svg" not in ALLOWED_DOC_EXTENSIONS
        assert MAX_UPLOAD_BYTES == 20 * 1024 * 1024

        for ext in sorted(ALLOWED_DOC_EXTENSIONS):
            f = SimpleUploadedFile(f"sample{ext}", b"ok", content_type="application/octet-stream")
            assert validate_safe_doc_upload(f) is f

        for bad_name in ("vector.svg", "payload.SVG", "script.exe", "page.html", "noextension"):
            bad_file = SimpleUploadedFile(bad_name, b"bad")
            with pytest.raises(ValidationError):
                validate_safe_doc_upload(bad_file)

        exact_limit = SimpleUploadedFile("exact.pdf", b"x")
        exact_limit.size = MAX_UPLOAD_BYTES
        assert validate_safe_doc_upload(exact_limit) is exact_limit

        oversized = SimpleUploadedFile("huge.pdf", b"x")
        oversized.size = MAX_UPLOAD_BYTES + 1
        with pytest.raises(ValidationError) as exc_size:
            validate_safe_doc_upload(oversized)
        assert "20 MB" in str(exc_size.value)


# =====================================================================
# 5. File Metadata Sync (MEDIA_ROOT isolated to tmp_path)
# =====================================================================


class TestAssetDocumentKnowledgeFileMetadataSync:
    def test_asset_document_knowledge_document_file_metadata_and_zero_byte_reset(
        self, tenant_a, settings, tmp_path
    ):
        settings.MEDIA_ROOT = str(tmp_path)

        payload_v1 = b"%PDF-1.4 controlled manual bytes"
        expected_sha_v1 = hashlib.sha256(payload_v1).hexdigest()
        doc = AssetDocument.objects.create(
            tenant=tenant_a,
            title="Manual With Attachment",
            file=SimpleUploadedFile("oem_manual.pdf", payload_v1, content_type="application/pdf"),
        )
        assert doc.original_filename == "oem_manual.pdf"
        assert doc.file_size_bytes == len(payload_v1)
        assert doc.file_checksum == expected_sha_v1
        assert doc.short_checksum == expected_sha_v1[:12]

        # Replacing with a 0-byte file MUST reset file_size_bytes to 0
        empty_sha = hashlib.sha256(b"").hexdigest()
        doc.file = SimpleUploadedFile("empty_replacement.pdf", b"", content_type="application/pdf")
        doc.save()
        doc.refresh_from_db()
        assert doc.original_filename == "empty_replacement.pdf"
        assert doc.file_size_bytes == 0
        assert doc.file_checksum == empty_sha

        # Clearing file resets all metadata fields
        doc.file = None
        doc.save()
        doc.refresh_from_db()
        assert doc.original_filename == ""
        assert doc.file_size_bytes == 0
        assert doc.file_checksum == ""

    def test_asset_document_knowledge_attachment_metadata_other_models(
        self, tenant_a, admin_user, settings, tmp_path
    ):
        settings.MEDIA_ROOT = str(tmp_path)

        sop_bytes = b"LOTO isolation diagram content"
        proc = AssetOperatingProcedure.objects.create(
            tenant=tenant_a,
            title="SOP With Attachment",
            attachment=SimpleUploadedFile("loto_map.png", sop_bytes),
        )
        assert proc.original_filename == "loto_map.png"
        assert proc.file_checksum == hashlib.sha256(sop_bytes).hexdigest()
        proc.attachment = None
        proc.save()
        assert proc.original_filename == ""
        assert proc.file_checksum == ""

        cert_bytes = b"Signed certificate bytes"
        cert = AssetOperatorCertification.objects.create(
            tenant=tenant_a,
            title="Cert With Scan",
            operator_user=admin_user,
            certificate_file=SimpleUploadedFile("cert_scan.pdf", cert_bytes),
        )
        assert cert.original_filename == "cert_scan.pdf"
        assert cert.file_checksum == hashlib.sha256(cert_bytes).hexdigest()
        cert.certificate_file = None
        cert.save()
        assert cert.original_filename == ""
        assert cert.file_checksum == ""

        art_bytes = b"RCA thermal photo bytes"
        article = AssetKnowledgeArticle.objects.create(
            tenant=tenant_a,
            title="Article With Evidence",
            symptom_problem="Hotspot detected",
            attachment=SimpleUploadedFile("thermal.jpg", art_bytes),
        )
        assert article.original_filename == "thermal.jpg"
        assert article.file_checksum == hashlib.sha256(art_bytes).hexdigest()
        article.attachment = None
        article.save()
        assert article.original_filename == ""
        assert article.file_checksum == ""


# =====================================================================
# 6. Certification Expiry Sync & is_operator_certified() Helper
# =====================================================================


class TestAssetDocumentKnowledgeCertificationLogic:
    def test_asset_document_knowledge_sync_expiry_status_transitions(
        self, tenant_a, admin_user
    ):
        today = timezone.localdate()
        cert = _asset_document_knowledge_create_cert(
            tenant_a,
            title="Transition Test Cert",
            user=admin_user,
            issued_date=today - timedelta(days=300),
            expires_on=today + timedelta(days=90),
            renewal_lead_days=30,
            status="active",
        )

        # Still well outside lead window -> no change
        assert cert.sync_expiry_status(as_of=today) is False
        assert cert.status == "active"

        # Within lead window (exact boundary days_left == 30) -> active -> expiring_soon
        cert.expires_on = today + timedelta(days=30)
        assert cert.sync_expiry_status(as_of=today) is True
        cert.refresh_from_db()
        assert cert.status == "expiring_soon"

        # Past expiry -> expiring_soon -> expired
        cert.expires_on = today - timedelta(days=1)
        assert cert.sync_expiry_status(as_of=today) is True
        cert.refresh_from_db()
        assert cert.status == "expired"

        # save=False updates in memory without persisting
        cert.expires_on = today + timedelta(days=60)
        cert.save(update_fields=["expires_on"])
        assert cert.sync_expiry_status(save=False, as_of=today) is True
        assert cert.status == "active"
        cert.refresh_from_db()
        assert cert.status == "expired"

        # save=True transitions expired -> active and persists
        assert cert.sync_expiry_status(save=True, as_of=today) is True
        cert.refresh_from_db()
        assert cert.status == "active"

        # Non-syncable statuses (pending, revoked) are untouched
        for frozen_status in ("pending", "revoked"):
            cert.status = frozen_status
            cert.expires_on = today - timedelta(days=10)
            cert.save(update_fields=["status", "expires_on"])
            assert cert.sync_expiry_status(as_of=today) is False
            cert.refresh_from_db()
            assert cert.status == frozen_status

    def test_asset_document_knowledge_is_operator_certified_resolution_and_fallbacks(
        self,
        tenant_a,
        tenant_b,
        admin_user,
        member_user,
        admin_b,
        vendor_party_a,
        vendor_party_b,
        operational_asset_a,
        category_root_a,
        category_child_a,
        adk_procedure_a,
        location_a,
    ):
        today = timezone.localdate()

        # Rejects missing tenant or missing operator
        assert is_operator_certified(None, user=admin_user) is False
        assert is_operator_certified(tenant_a) is False

        # Wildcard cert for member_user (no asset/category) with no expiry
        wildcard_cert = _asset_document_knowledge_create_cert(
            tenant_a,
            title="General Floor Safety",
            user=member_user,
            status="active",
            expires_on=None,
            qualification_code="GEN-01",
        )
        assert is_operator_certified(tenant_a, user=member_user) is True
        assert (
            is_operator_certified(
                tenant_a, user=member_user, operational_asset=operational_asset_a
            )
            is True
        )
        assert (
            is_operator_certified(
                tenant_a, user=member_user, qualification_code="GEN-01"
            )
            is True
        )
        assert (
            is_operator_certified(
                tenant_a, user=member_user, qualification_code="WRONG-CODE"
            )
            is False
        )
        # Cross-tenant denied
        assert is_operator_certified(tenant_b, user=member_user) is False

        # Party-only cert & combined user/party lookup
        party_cert = _asset_document_knowledge_create_cert(
            tenant_a,
            title="Contractor LOTO",
            party=vendor_party_a,
            operational_asset=operational_asset_a,
            operating_procedure=adk_procedure_a,
            qualification_code=adk_procedure_a.required_qualification_code,
            status="expiring_soon",
            expires_on=today + timedelta(days=5),
        )
        assert party_cert.operating_procedure == adk_procedure_a
        assert (
            is_operator_certified(
                tenant_a,
                party=vendor_party_a,
                operational_asset=operational_asset_a,
                qualification_code="LOTO-01",
            )
            is True
        )
        assert (
            is_operator_certified(
                tenant_a,
                user=admin_user,
                party=vendor_party_a,
                operational_asset=operational_asset_a,
            )
            is True
        )
        assert is_operator_certified(tenant_a, party=vendor_party_b) is False

        # Specific asset mismatch rejected
        other_asset = Asset.objects.create(
            tenant=tenant_a,
            code="AST-OTHER-02",
            name="Other Machine",
            asset_type="machine",
            location=location_a,
        )
        assert (
            is_operator_certified(
                tenant_a, party=vendor_party_a, operational_asset=other_asset
            )
            is False
        )

        # Category-scoped cert + scm.Asset.category string fallback (code & name, case-insensitive)
        cat_cert = _asset_document_knowledge_create_cert(
            tenant_a,
            title="Plant Equipment Category Cert",
            user=admin_user,
            asset_category=category_root_a,
            status="active",
            expires_on=today + timedelta(days=60),
        )
        assert (
            is_operator_certified(
                tenant_a, user=admin_user, asset_category=category_root_a
            )
            is True
        )
        assert (
            is_operator_certified(
                tenant_a, user=admin_user, asset_category=category_child_a
            )
            is False
        )

        # scm.Asset.category matches AssetCategory.code case-insensitively
        asset_by_code = Asset.objects.create(
            tenant=tenant_a,
            code="AST-CODE-FB",
            name="Fallback By Code",
            asset_type="machine",
            category=category_root_a.code.lower(),
            location=location_a,
        )
        assert (
            is_operator_certified(
                tenant_a, user=admin_user, operational_asset=asset_by_code
            )
            is True
        )

        # scm.Asset.category matches AssetCategory.name case-insensitively
        asset_by_name = Asset.objects.create(
            tenant=tenant_a,
            code="AST-NAME-FB",
            name="Fallback By Name",
            asset_type="machine",
            category=category_root_a.name.upper(),
            location=location_a,
        )
        assert (
            is_operator_certified(
                tenant_a, user=admin_user, operational_asset=asset_by_name
            )
            is True
        )

        # Unmatched category string does not qualify
        asset_unmatched = Asset.objects.create(
            tenant=tenant_a,
            code="AST-NONE-FB",
            name="Unmatched Category",
            asset_type="machine",
            category="Nonexistent Category",
            location=location_a,
        )
        assert (
            is_operator_certified(
                tenant_a, user=admin_user, operational_asset=asset_unmatched
            )
            is False
        )

        # Excluded statuses (expired, revoked, pending) & date cutoff
        for bad_status in ("expired", "revoked", "pending"):
            cat_cert.status = bad_status
            cat_cert.save(update_fields=["status"])
            assert (
                is_operator_certified(
                    tenant_a, user=admin_user, asset_category=category_root_a
                )
                is False
            )

        cat_cert.status = "active"
        cat_cert.expires_on = today + timedelta(days=10)
        cat_cert.save(update_fields=["status", "expires_on"])
        assert (
            is_operator_certified(
                tenant_a,
                user=admin_user,
                asset_category=category_root_a,
                as_of=today + timedelta(days=10),
            )
            is True
        )
        assert (
            is_operator_certified(
                tenant_a,
                user=admin_user,
                asset_category=category_root_a,
                as_of=today + timedelta(days=11),
            )
            is False
        )

        # Cleanup reference usage check
        assert wildcard_cert.pk is not None
        assert admin_b.pk is not None

    def test_asset_document_knowledge_document_access_classification_helpers(
        self,
        tenant_a,
        adk_document_a,
        adk_document_restricted_a,
        admin_user,
        member_user,
    ):
        assert is_asset_document_readable(None, admin_user) is False
        assert is_asset_document_readable(adk_document_a, None) is True
        assert is_asset_document_readable(adk_document_restricted_a, None) is False
        assert is_asset_document_readable(adk_document_restricted_a, member_user) is False
        assert is_asset_document_readable(adk_document_restricted_a, admin_user) is True

        adk_document_restricted_a.reviewer = member_user
        adk_document_restricted_a.save(update_fields=["reviewer"])
        assert is_asset_document_readable(adk_document_restricted_a, member_user) is True

        visible_to_none = AssetDocument.objects.filter(
            tenant=tenant_a
        ).filter(readable_asset_document_q(None))
        assert adk_document_a in visible_to_none
        assert adk_document_restricted_a not in visible_to_none

        visible_to_member = AssetDocument.objects.filter(
            tenant=tenant_a
        ).filter(readable_asset_document_q(member_user))
        assert adk_document_a in visible_to_member
        assert adk_document_restricted_a in visible_to_member
