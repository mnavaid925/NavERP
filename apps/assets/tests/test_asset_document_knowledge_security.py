"""
Security, multi-tenant isolation, RBAC, access-classification, checkout-lock,
file-hardening, XSS, CSV formula injection, and audit-log tests for
Sub-module 11.16: Asset Document & Knowledge Management.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.assets.forms import (
    AssetDocumentForm,
    AssetKnowledgeArticleForm,
    AssetOperatingProcedureForm,
    AssetOperatorCertificationForm,
)
from apps.assets.models import (
    AssetDocument,
    AssetKnowledgeArticle,
    AssetOperatingProcedure,
    AssetOperatorCertification,
)
from apps.core.forms._common import MAX_UPLOAD_BYTES
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_asset_document_knowledge_*)
# =====================================================================


def _asset_document_knowledge_doc_payload(**overrides):
    data = {
        "title": "Security Test Controlled Manual",
        "document_class": "manual",
        "access_classification": "internal_tech",
        "tag_code": "SEC-DOC-01",
        "manufacturer_ref": "OEM-SEC",
        "document_language": "en",
        "storage_location_ref": "Vault S-01",
        "revision_label": "Rev A",
        "change_type": "new_issue",
        "change_request_ref": "ECR-SEC-01",
        "redline_summary": "Baseline controlled release.",
        "spec_delta_notes": "Nominal operating range.",
        "effective_date": timezone.localdate().isoformat(),
        "expiry_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
        "retention_years": "7",
        "description": "Controlled technical manual.",
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_sop_payload(**overrides):
    data = {
        "title": "Security Test LOTO SOP",
        "procedure_type": "loto_isolation",
        "safety_level": "high_hazard_loto",
        "revision_label": "Rev 1.0",
        "purpose_scope": "Isolate energy sources before maintenance.",
        "hazard_warnings": "480V electrical hazard.",
        "required_ppe": "Arc-flash shield, Class 0 gloves",
        "loto_required": "on",
        "loto_isolation_points": json.dumps(
            [
                {
                    "energy_source": "480V AC",
                    "tag_id": "MCC-SEC-1",
                    "isolation_point": "Main Disconnect",
                    "lock_device": "Red Lock + Tag",
                    "verification_step": "Verify 0V",
                }
            ]
        ),
        "procedure_steps": json.dumps(
            [
                {
                    "step_no": 1,
                    "title": "Power off",
                    "instruction": "Open main breaker.",
                    "expected_reading": "0V",
                }
            ]
        ),
        "required_qualification_code": "LOTO-SEC-01",
        "estimated_duration_minutes": "30",
        "review_cycle_months": "12",
        "effective_date": timezone.localdate().isoformat(),
        "next_review_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_cert_payload(operator_party=None, operator_user=None, **overrides):
    data = {
        "title": "Security Test LOTO Qualification",
        "qualification_code": "LOTO-SEC-01",
        "qualification_type": "loto_authorized",
        "proficiency_level": "qualified_operator",
        "issuing_authority": "EHS Academy",
        "certificate_reference": "CERT-SEC-01",
        "issued_date": timezone.localdate().isoformat(),
        "expires_on": (timezone.localdate() + timedelta(days=180)).isoformat(),
        "renewal_lead_days": "30",
        "training_hours": "8.00",
        "assessment_score": "92.00",
        "notes": "Verified qualification.",
    }
    if operator_party is not None:
        data["operator_party"] = str(operator_party.pk)
    if operator_user is not None:
        data["operator_user"] = str(operator_user.pk)
    data.update(overrides)
    return data


def _asset_document_knowledge_article_payload(**overrides):
    data = {
        "title": "Security Test Bearing Failure RCA",
        "article_type": "rca_post_incident",
        "rca_methodology": "five_whys",
        "severity": "high",
        "symptom_problem": "High vibration trip on drive end.",
        "root_cause_summary": "Inadequate lubrication schedule.",
        "five_whys": json.dumps(
            [{"why_level": 1, "question": "Why did bearing seize?", "answer": "Dry raceway."}]
        ),
        "contributing_factors": json.dumps({"machine": "Blocked grease line"}),
        "remedy_corrective_action": "Replace bearing and clear grease line.",
        "preventive_lessons": "Inspect grease fittings weekly.",
        "downtime_hours_impacted": "3.50",
        "recurrence_count": "1",
        "tags": "bearing,lubrication",
        "incident_occurred_on": timezone.localdate().isoformat(),
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_make_doc(tenant, owner=None, **overrides):
    defaults = {
        "tenant": tenant,
        "title": "Draft Controlled Doc",
        "document_class": "manual",
        "access_classification": "public_floor",
        "revision_label": "Rev A",
        "revision_sequence": 1,
        "is_current_revision": True,
        "change_type": "new_issue",
        "status": "draft",
        "owner": owner,
    }
    defaults.update(overrides)
    doc = AssetDocument(**defaults)
    doc.save()
    return doc


def _asset_document_knowledge_make_sop(tenant, author=None, **overrides):
    defaults = {
        "tenant": tenant,
        "title": "Draft Controlled SOP",
        "procedure_type": "sop_operation",
        "safety_level": "standard",
        "revision_label": "Rev 1.0",
        "loto_required": False,
        "estimated_duration_minutes": 30,
        "review_cycle_months": 12,
        "status": "draft",
        "author": author,
    }
    defaults.update(overrides)
    sop = AssetOperatingProcedure(**defaults)
    sop.save()
    return sop


def _asset_document_knowledge_make_cert(tenant, operator_party=None, operator_user=None, **overrides):
    defaults = {
        "tenant": tenant,
        "title": "Operator Qualification",
        "qualification_code": "QUAL-SEC-1",
        "qualification_type": "equipment_operator",
        "proficiency_level": "qualified_operator",
        "issued_date": timezone.localdate() - timedelta(days=15),
        "expires_on": timezone.localdate() + timedelta(days=180),
        "renewal_lead_days": 30,
        "status": "pending",
        "operator_party": operator_party,
        "operator_user": operator_user,
    }
    defaults.update(overrides)
    cert = AssetOperatorCertification(**defaults)
    cert.save()
    return cert


def _asset_document_knowledge_make_article(tenant, author=None, **overrides):
    defaults = {
        "tenant": tenant,
        "title": "Draft RCA Note",
        "article_type": "lessons_learned",
        "rca_methodology": "five_whys",
        "severity": "medium",
        "symptom_problem": "Observed pressure drop on discharge line.",
        "status": "draft",
        "author": author,
    }
    defaults.update(overrides)
    art = AssetKnowledgeArticle(**defaults)
    art.save()
    return art


def _asset_document_knowledge_get_urls(doc, sop, cert, art):
    return [
        reverse("assets:asset_document_list"),
        reverse("assets:asset_document_change_list"),
        reverse("assets:asset_document_create"),
        reverse("assets:asset_document_export_csv"),
        reverse("assets:asset_document_detail", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_edit", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_download", kwargs={"pk": doc.pk}),
        reverse("assets:asset_operating_procedure_list"),
        reverse("assets:asset_operating_procedure_create"),
        reverse("assets:asset_operating_procedure_export_csv"),
        reverse("assets:asset_operating_procedure_detail", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_print", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_edit", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_download", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operator_certification_list"),
        reverse("assets:asset_operator_certification_create"),
        reverse("assets:asset_operator_certification_export_csv"),
        reverse("assets:asset_operator_certification_detail", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_download", kwargs={"pk": cert.pk}),
        reverse("assets:asset_knowledge_article_list"),
        reverse("assets:asset_knowledge_article_create"),
        reverse("assets:asset_knowledge_article_export_csv"),
        reverse("assets:asset_knowledge_article_detail", kwargs={"pk": art.pk}),
        reverse("assets:asset_knowledge_article_edit", kwargs={"pk": art.pk}),
        reverse("assets:asset_knowledge_article_download", kwargs={"pk": art.pk}),
    ]


def _asset_document_knowledge_post_only_urls(doc, sop, cert, art):
    return [
        reverse("assets:asset_document_delete", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_submit_review", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_approve_release", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_return_to_draft", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_checkout", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_checkin", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_create_revision", kwargs={"pk": doc.pk}),
        reverse("assets:asset_document_archive", kwargs={"pk": doc.pk}),
        reverse("assets:asset_operating_procedure_delete", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_submit_review", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_activate", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_clone_revision", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operating_procedure_retire", kwargs={"pk": sop.pk}),
        reverse("assets:asset_operator_certification_delete", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_verify_activate", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_acknowledge_sop", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_renew", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_revoke", kwargs={"pk": cert.pk}),
        reverse("assets:asset_operator_certification_refresh_alerts"),
        reverse("assets:asset_knowledge_article_delete", kwargs={"pk": art.pk}),
        reverse("assets:asset_knowledge_article_submit_review", kwargs={"pk": art.pk}),
        reverse("assets:asset_knowledge_article_publish", kwargs={"pk": art.pk}),
        reverse("assets:asset_knowledge_article_mark_helpful", kwargs={"pk": art.pk}),
        reverse("assets:asset_knowledge_article_retire", kwargs={"pk": art.pk}),
    ]


# =====================================================================
# 1. Anonymous Access Redirects
# =====================================================================


class TestAssetDocumentKnowledgeAnonymousAccess:
    def test_asset_document_knowledge_anon_get_endpoints_redirect_to_login(
        self,
        adk_document_draft_a,
        adk_procedure_draft_a,
        adk_certification_pending_a,
        adk_article_draft_a,
    ):
        anon = Client()
        urls = _asset_document_knowledge_get_urls(
            adk_document_draft_a,
            adk_procedure_draft_a,
            adk_certification_pending_a,
            adk_article_draft_a,
        )
        for url in urls:
            res = anon.get(url)
            assert res.status_code == 302, f"Expected 302 redirect on GET {url}, got {res.status_code}"
            assert "login" in res["Location"], f"Expected login redirect for {url}, got {res['Location']}"

    def test_asset_document_knowledge_anon_post_endpoints_redirect_to_login_no_mutation(
        self,
        vendor_party_a,
        adk_document_draft_a,
        adk_procedure_draft_a,
        adk_certification_pending_a,
        adk_article_draft_a,
    ):
        anon = Client()
        doc_count = AssetDocument.objects.count()
        sop_count = AssetOperatingProcedure.objects.count()
        cert_count = AssetOperatorCertification.objects.count()
        art_count = AssetKnowledgeArticle.objects.count()

        post_cases = [
            (reverse("assets:asset_document_create"), _asset_document_knowledge_doc_payload()),
            (
                reverse("assets:asset_document_edit", kwargs={"pk": adk_document_draft_a.pk}),
                _asset_document_knowledge_doc_payload(title="Anon Tamper"),
            ),
            (reverse("assets:asset_operating_procedure_create"), _asset_document_knowledge_sop_payload()),
            (
                reverse("assets:asset_operating_procedure_edit", kwargs={"pk": adk_procedure_draft_a.pk}),
                _asset_document_knowledge_sop_payload(title="Anon SOP Tamper"),
            ),
            (
                reverse("assets:asset_operator_certification_create"),
                _asset_document_knowledge_cert_payload(operator_party=vendor_party_a),
            ),
            (
                reverse("assets:asset_operator_certification_edit", kwargs={"pk": adk_certification_pending_a.pk}),
                _asset_document_knowledge_cert_payload(operator_party=vendor_party_a, title="Anon Cert Tamper"),
            ),
            (reverse("assets:asset_knowledge_article_create"), _asset_document_knowledge_article_payload()),
            (
                reverse("assets:asset_knowledge_article_edit", kwargs={"pk": adk_article_draft_a.pk}),
                _asset_document_knowledge_article_payload(title="Anon KB Tamper"),
            ),
        ]
        for url in _asset_document_knowledge_post_only_urls(
            adk_document_draft_a,
            adk_procedure_draft_a,
            adk_certification_pending_a,
            adk_article_draft_a,
        ):
            post_cases.append((url, {}))

        for url, payload in post_cases:
            res = anon.post(url, data=payload)
            assert res.status_code == 302, f"Expected 302 redirect on POST {url}, got {res.status_code}"
            assert "login" in res["Location"], f"Expected login redirect for {url}, got {res['Location']}"

        assert AssetDocument.objects.count() == doc_count
        assert AssetOperatingProcedure.objects.count() == sop_count
        assert AssetOperatorCertification.objects.count() == cert_count
        assert AssetKnowledgeArticle.objects.count() == art_count
        adk_document_draft_a.refresh_from_db()
        adk_procedure_draft_a.refresh_from_db()
        adk_certification_pending_a.refresh_from_db()
        adk_article_draft_a.refresh_from_db()
        assert adk_document_draft_a.status == "draft"
        assert adk_procedure_draft_a.status == "draft"
        assert adk_certification_pending_a.status == "pending"
        assert adk_article_draft_a.status == "draft"


# =====================================================================
# 2. Cross-Tenant IDOR & Tenant Isolation
# =====================================================================


class TestAssetDocumentKnowledgeCrossTenantIDOR:
    def test_asset_document_knowledge_cross_tenant_idor_read_edit_download_print_404(
        self,
        tmp_path,
        client_b,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            doc_a = _asset_document_knowledge_make_doc(
                tenant_a,
                owner=admin_user,
                title="Acme Confidential Spec",
                access_classification="confidential",
                file=SimpleUploadedFile("acme.pdf", b"%PDF-1.4 acme", content_type="application/pdf"),
            )
            sop_a = _asset_document_knowledge_make_sop(
                tenant_a,
                author=admin_user,
                title="Acme LOTO SOP",
                attachment=SimpleUploadedFile("sop.pdf", b"%PDF-1.4 sop", content_type="application/pdf"),
            )
            cert_a = _asset_document_knowledge_make_cert(
                tenant_a,
                operator_party=vendor_party_a,
                operator_user=admin_user,
                title="Acme Operator Cert",
                certificate_file=SimpleUploadedFile("cert.pdf", b"%PDF-1.4 cert", content_type="application/pdf"),
            )
            art_a = _asset_document_knowledge_make_article(
                tenant_a,
                author=admin_user,
                title="Acme RCA Evidence",
                attachment=SimpleUploadedFile("rca.pdf", b"%PDF-1.4 rca", content_type="application/pdf"),
            )

            get_targets = [
                reverse("assets:asset_document_detail", kwargs={"pk": doc_a.pk}),
                reverse("assets:asset_document_download", kwargs={"pk": doc_a.pk}),
                reverse("assets:asset_document_edit", kwargs={"pk": doc_a.pk}),
                reverse("assets:asset_operating_procedure_detail", kwargs={"pk": sop_a.pk}),
                reverse("assets:asset_operating_procedure_print", kwargs={"pk": sop_a.pk}),
                reverse("assets:asset_operating_procedure_download", kwargs={"pk": sop_a.pk}),
                reverse("assets:asset_operating_procedure_edit", kwargs={"pk": sop_a.pk}),
                reverse("assets:asset_operator_certification_detail", kwargs={"pk": cert_a.pk}),
                reverse("assets:asset_operator_certification_download", kwargs={"pk": cert_a.pk}),
                reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert_a.pk}),
                reverse("assets:asset_knowledge_article_detail", kwargs={"pk": art_a.pk}),
                reverse("assets:asset_knowledge_article_download", kwargs={"pk": art_a.pk}),
                reverse("assets:asset_knowledge_article_edit", kwargs={"pk": art_a.pk}),
            ]
            for url in get_targets:
                res = client_b.get(url)
                assert res.status_code == 404, f"Cross-tenant GET {url} returned {res.status_code}"

            edit_posts = [
                (
                    reverse("assets:asset_document_edit", kwargs={"pk": doc_a.pk}),
                    _asset_document_knowledge_doc_payload(title="IDOR Overwrite Doc"),
                ),
                (
                    reverse("assets:asset_operating_procedure_edit", kwargs={"pk": sop_a.pk}),
                    _asset_document_knowledge_sop_payload(title="IDOR Overwrite SOP"),
                ),
                (
                    reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert_a.pk}),
                    _asset_document_knowledge_cert_payload(operator_party=vendor_party_a, title="IDOR Overwrite Cert"),
                ),
                (
                    reverse("assets:asset_knowledge_article_edit", kwargs={"pk": art_a.pk}),
                    _asset_document_knowledge_article_payload(title="IDOR Overwrite KB"),
                ),
            ]
            for url, payload in edit_posts:
                res = client_b.post(url, data=payload)
                assert res.status_code == 404, f"Cross-tenant POST {url} returned {res.status_code}"

            doc_a.refresh_from_db()
            sop_a.refresh_from_db()
            cert_a.refresh_from_db()
            art_a.refresh_from_db()
            assert doc_a.title == "Acme Confidential Spec"
            assert sop_a.title == "Acme LOTO SOP"
            assert cert_a.title == "Acme Operator Cert"
            assert art_a.title == "Acme RCA Evidence"

    def test_asset_document_knowledge_cross_tenant_idor_delete_and_workflow_404(
        self,
        client_b,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        doc_draft = _asset_document_knowledge_make_doc(tenant_a, owner=admin_user, status="draft")
        doc_review = _asset_document_knowledge_make_doc(tenant_a, owner=admin_user, status="in_review")
        sop_draft = _asset_document_knowledge_make_sop(tenant_a, author=admin_user, status="draft")
        cert_pending = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=admin_user, status="pending"
        )
        cert_active = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=admin_user, status="active"
        )
        art_draft = _asset_document_knowledge_make_article(tenant_a, author=admin_user, status="draft")

        doc_count = AssetDocument.objects.count()
        sop_count = AssetOperatingProcedure.objects.count()
        cert_count = AssetOperatorCertification.objects.count()
        art_count = AssetKnowledgeArticle.objects.count()

        urls = [
            reverse("assets:asset_document_delete", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_document_submit_review", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_document_approve_release", kwargs={"pk": doc_review.pk}),
            reverse("assets:asset_document_return_to_draft", kwargs={"pk": doc_review.pk}),
            reverse("assets:asset_document_checkout", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_document_checkin", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_document_create_revision", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_document_archive", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_operating_procedure_delete", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operating_procedure_submit_review", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operating_procedure_activate", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operating_procedure_clone_revision", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operating_procedure_retire", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operator_certification_delete", kwargs={"pk": cert_pending.pk}),
            reverse("assets:asset_operator_certification_verify_activate", kwargs={"pk": cert_pending.pk}),
            reverse("assets:asset_operator_certification_acknowledge_sop", kwargs={"pk": cert_active.pk}),
            reverse("assets:asset_operator_certification_renew", kwargs={"pk": cert_active.pk}),
            reverse("assets:asset_operator_certification_revoke", kwargs={"pk": cert_active.pk}),
            reverse("assets:asset_knowledge_article_delete", kwargs={"pk": art_draft.pk}),
            reverse("assets:asset_knowledge_article_submit_review", kwargs={"pk": art_draft.pk}),
            reverse("assets:asset_knowledge_article_publish", kwargs={"pk": art_draft.pk}),
            reverse("assets:asset_knowledge_article_mark_helpful", kwargs={"pk": art_draft.pk}),
            reverse("assets:asset_knowledge_article_retire", kwargs={"pk": art_draft.pk}),
        ]

        for url in urls:
            res = client_b.post(url)
            assert res.status_code == 404, f"Cross-tenant workflow POST {url} returned {res.status_code}"

        assert AssetDocument.objects.count() == doc_count
        assert AssetOperatingProcedure.objects.count() == sop_count
        assert AssetOperatorCertification.objects.count() == cert_count
        assert AssetKnowledgeArticle.objects.count() == art_count

        doc_draft.refresh_from_db()
        doc_review.refresh_from_db()
        sop_draft.refresh_from_db()
        cert_pending.refresh_from_db()
        cert_active.refresh_from_db()
        art_draft.refresh_from_db()
        assert doc_draft.status == "draft"
        assert doc_draft.checked_out_by is None
        assert doc_review.status == "in_review"
        assert sop_draft.status == "draft"
        assert cert_pending.status == "pending"
        assert cert_active.status == "active"
        assert cert_active.sop_acknowledged is False
        assert art_draft.status == "draft"
        assert art_draft.helpful_votes == 0

    def test_asset_document_knowledge_list_and_export_csv_tenant_isolation(
        self,
        client_a,
        tenant_b,
        admin_b,
        vendor_party_b,
        adk_document_a,
        adk_document_b,
        adk_procedure_a,
        adk_procedure_b,
        adk_certification_a,
        adk_certification_b,
        adk_article_a,
        adk_article_b,
    ):
        doc_draft_b = _asset_document_knowledge_make_doc(
            tenant_b, owner=admin_b, title="Globex Secret Draft Revision", status="draft"
        )
        sop_b2 = _asset_document_knowledge_make_sop(
            tenant_b, author=admin_b, title="Globex Secret SOP Two", status="draft"
        )
        cert_b2 = _asset_document_knowledge_make_cert(
            tenant_b,
            operator_party=vendor_party_b,
            operator_user=admin_b,
            title="Globex Secret Cert Two",
            status="pending",
        )
        art_b2 = _asset_document_knowledge_make_article(
            tenant_b, author=admin_b, title="Globex Secret RCA Two", status="draft"
        )

        endpoints = [
            (
                reverse("assets:asset_document_list"),
                adk_document_a.title,
                [
                    adk_document_b.title,
                    doc_draft_b.title,
                    doc_draft_b.number,
                    reverse("assets:asset_document_detail", kwargs={"pk": adk_document_b.pk}),
                ],
            ),
            (
                reverse("assets:asset_document_change_list"),
                None,
                [
                    doc_draft_b.title,
                    doc_draft_b.number,
                    reverse("assets:asset_document_detail", kwargs={"pk": doc_draft_b.pk}),
                ],
            ),
            (
                reverse("assets:asset_document_export_csv"),
                adk_document_a.number,
                [adk_document_b.title, doc_draft_b.title, doc_draft_b.number],
            ),
            (
                reverse("assets:asset_operating_procedure_list"),
                adk_procedure_a.title,
                [
                    adk_procedure_b.title,
                    sop_b2.title,
                    sop_b2.number,
                    reverse("assets:asset_operating_procedure_detail", kwargs={"pk": adk_procedure_b.pk}),
                ],
            ),
            (
                reverse("assets:asset_operating_procedure_export_csv"),
                adk_procedure_a.number,
                [adk_procedure_b.title, sop_b2.title, sop_b2.number],
            ),
            (
                reverse("assets:asset_operator_certification_list"),
                adk_certification_a.title,
                [
                    adk_certification_b.title,
                    cert_b2.title,
                    cert_b2.number,
                    reverse("assets:asset_operator_certification_detail", kwargs={"pk": adk_certification_b.pk}),
                ],
            ),
            (
                reverse("assets:asset_operator_certification_export_csv"),
                adk_certification_a.number,
                [adk_certification_b.title, cert_b2.title, cert_b2.number],
            ),
            (
                reverse("assets:asset_knowledge_article_list"),
                adk_article_a.title,
                [
                    adk_article_b.title,
                    art_b2.title,
                    art_b2.number,
                    reverse("assets:asset_knowledge_article_detail", kwargs={"pk": adk_article_b.pk}),
                ],
            ),
            (
                reverse("assets:asset_knowledge_article_export_csv"),
                adk_article_a.number,
                [adk_article_b.title, art_b2.title, art_b2.number],
            ),
        ]
        for url, expected_a, forbidden_b_list in endpoints:
            res = client_a.get(url)
            assert res.status_code == 200
            body = res.content.decode("utf-8")
            if expected_a:
                assert expected_a in body
            for secret_b in forbidden_b_list:
                assert secret_b not in body, f"Tenant B leak '{secret_b}' in {url}"

    def test_asset_document_knowledge_cross_tenant_fk_injection_rejected(
        self,
        client_a,
        tenant_a,
        operational_asset_b,
        vendor_party_a,
        vendor_party_b,
        adk_document_b,
        adk_procedure_b,
    ):
        # 1. AssetDocument create with tenant_b operational_asset & supersedes
        doc_count = AssetDocument.objects.count()
        res_doc = client_a.post(
            reverse("assets:asset_document_create"),
            data=_asset_document_knowledge_doc_payload(
                title="Injected Foreign Asset Doc",
                operational_asset=str(operational_asset_b.pk),
                supersedes=str(adk_document_b.pk),
            ),
        )
        assert res_doc.status_code == 200
        assert AssetDocument.objects.count() == doc_count

        # 2. AssetOperatingProcedure create with tenant_b primary_document & operational_asset
        sop_count = AssetOperatingProcedure.objects.count()
        res_sop = client_a.post(
            reverse("assets:asset_operating_procedure_create"),
            data=_asset_document_knowledge_sop_payload(
                title="Injected Foreign SOP",
                operational_asset=str(operational_asset_b.pk),
                primary_document=str(adk_document_b.pk),
            ),
        )
        assert res_sop.status_code == 200
        assert AssetOperatingProcedure.objects.count() == sop_count

        # 3. AssetOperatorCertification create with tenant_b operator_party & operating_procedure
        cert_count = AssetOperatorCertification.objects.count()
        res_cert = client_a.post(
            reverse("assets:asset_operator_certification_create"),
            data=_asset_document_knowledge_cert_payload(
                operator_party=vendor_party_b,
                operating_procedure=str(adk_procedure_b.pk),
            ),
        )
        assert res_cert.status_code == 200
        assert AssetOperatorCertification.objects.count() == cert_count

        # 4. AssetKnowledgeArticle create with tenant_b related_document & recommended_procedure
        art_count = AssetKnowledgeArticle.objects.count()
        res_art = client_a.post(
            reverse("assets:asset_knowledge_article_create"),
            data=_asset_document_knowledge_article_payload(
                title="Injected Foreign KB",
                related_document=str(adk_document_b.pk),
                recommended_procedure=str(adk_procedure_b.pk),
            ),
        )
        assert res_art.status_code == 200
        assert AssetKnowledgeArticle.objects.count() == art_count
        assert not AssetOperatorCertification.objects.filter(
            tenant=tenant_a, operator_party=vendor_party_b
        ).exists()
        assert vendor_party_a.tenant == tenant_a


# =====================================================================
# 3. Non-Admin RBAC Enforcement
# =====================================================================


class TestAssetDocumentKnowledgeRBAC:
    def test_asset_document_knowledge_member_forbidden_on_all_admin_endpoints(
        self,
        member_client,
        tenant_a,
        member_user,
        vendor_party_a,
    ):
        doc_draft = _asset_document_knowledge_make_doc(tenant_a, owner=member_user, status="draft")
        doc_review = _asset_document_knowledge_make_doc(tenant_a, owner=member_user, status="in_review")
        sop_draft = _asset_document_knowledge_make_sop(tenant_a, author=member_user, status="draft")
        cert_pending = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=member_user, status="pending"
        )
        cert_active = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=member_user, status="active"
        )
        art_draft = _asset_document_knowledge_make_article(tenant_a, author=member_user, status="draft")

        # Certification edit must return 403 on BOTH GET and POST (prevents qualification self-extension)
        edit_url = reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert_pending.pk})
        assert member_client.get(edit_url).status_code == 403
        res_edit_post = member_client.post(
            edit_url,
            data=_asset_document_knowledge_cert_payload(
                operator_party=vendor_party_a,
                operator_user=member_user,
                title="Self-Extended Qualification",
                expires_on=(timezone.localdate() + timedelta(days=3650)).isoformat(),
            ),
        )
        assert res_edit_post.status_code == 403

        admin_post_endpoints = [
            reverse("assets:asset_document_delete", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_document_approve_release", kwargs={"pk": doc_review.pk}),
            reverse("assets:asset_document_return_to_draft", kwargs={"pk": doc_review.pk}),
            reverse("assets:asset_document_archive", kwargs={"pk": doc_draft.pk}),
            reverse("assets:asset_operating_procedure_delete", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operating_procedure_activate", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operating_procedure_retire", kwargs={"pk": sop_draft.pk}),
            reverse("assets:asset_operator_certification_delete", kwargs={"pk": cert_pending.pk}),
            reverse("assets:asset_operator_certification_verify_activate", kwargs={"pk": cert_pending.pk}),
            reverse("assets:asset_operator_certification_renew", kwargs={"pk": cert_active.pk}),
            reverse("assets:asset_operator_certification_revoke", kwargs={"pk": cert_active.pk}),
            reverse("assets:asset_operator_certification_refresh_alerts"),
            reverse("assets:asset_knowledge_article_delete", kwargs={"pk": art_draft.pk}),
            reverse("assets:asset_knowledge_article_publish", kwargs={"pk": art_draft.pk}),
            reverse("assets:asset_knowledge_article_retire", kwargs={"pk": art_draft.pk}),
        ]
        for url in admin_post_endpoints:
            res = member_client.post(url)
            assert res.status_code == 403, f"Expected 403 for member POST {url}, got {res.status_code}"

        # Zero mutations
        doc_draft.refresh_from_db()
        doc_review.refresh_from_db()
        sop_draft.refresh_from_db()
        cert_pending.refresh_from_db()
        cert_active.refresh_from_db()
        art_draft.refresh_from_db()
        assert doc_draft.status == "draft"
        assert doc_review.status == "in_review"
        assert sop_draft.status == "draft"
        assert cert_pending.status == "pending"
        assert cert_pending.title == "Operator Qualification"
        assert cert_active.status == "active"
        assert art_draft.status == "draft"

    def test_asset_document_knowledge_admin_buttons_hidden_for_member_in_html(
        self,
        client_a,
        member_client,
        tenant_a,
        member_user,
        vendor_party_a,
    ):
        doc_review = _asset_document_knowledge_make_doc(
            tenant_a, owner=member_user, status="in_review", access_classification="public_floor"
        )
        sop_draft = _asset_document_knowledge_make_sop(tenant_a, author=member_user, status="draft")
        cert_pending = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=member_user, status="pending"
        )
        cert_active = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=member_user, status="active"
        )
        art_draft = _asset_document_knowledge_make_article(tenant_a, author=member_user, status="draft")

        checks = [
            (
                reverse("assets:asset_document_list"),
                [reverse("assets:asset_document_delete", kwargs={"pk": doc_review.pk})],
            ),
            (
                reverse("assets:asset_document_change_list"),
                [reverse("assets:asset_document_delete", kwargs={"pk": doc_review.pk})],
            ),
            (
                reverse("assets:asset_document_detail", kwargs={"pk": doc_review.pk}),
                [
                    reverse("assets:asset_document_delete", kwargs={"pk": doc_review.pk}),
                    reverse("assets:asset_document_approve_release", kwargs={"pk": doc_review.pk}),
                    reverse("assets:asset_document_return_to_draft", kwargs={"pk": doc_review.pk}),
                    reverse("assets:asset_document_archive", kwargs={"pk": doc_review.pk}),
                ],
            ),
            (
                reverse("assets:asset_operating_procedure_list"),
                [reverse("assets:asset_operating_procedure_delete", kwargs={"pk": sop_draft.pk})],
            ),
            (
                reverse("assets:asset_operating_procedure_detail", kwargs={"pk": sop_draft.pk}),
                [
                    reverse("assets:asset_operating_procedure_delete", kwargs={"pk": sop_draft.pk}),
                    reverse("assets:asset_operating_procedure_activate", kwargs={"pk": sop_draft.pk}),
                    reverse("assets:asset_operating_procedure_retire", kwargs={"pk": sop_draft.pk}),
                ],
            ),
            (
                reverse("assets:asset_operator_certification_list"),
                [
                    reverse("assets:asset_operator_certification_refresh_alerts"),
                    reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert_pending.pk}),
                    reverse("assets:asset_operator_certification_delete", kwargs={"pk": cert_pending.pk}),
                ],
            ),
            (
                reverse("assets:asset_operator_certification_detail", kwargs={"pk": cert_pending.pk}),
                [
                    reverse("assets:asset_operator_certification_verify_activate", kwargs={"pk": cert_pending.pk}),
                    reverse("assets:asset_operator_certification_revoke", kwargs={"pk": cert_pending.pk}),
                    reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert_pending.pk}),
                    reverse("assets:asset_operator_certification_delete", kwargs={"pk": cert_pending.pk}),
                ],
            ),
            (
                reverse("assets:asset_operator_certification_detail", kwargs={"pk": cert_active.pk}),
                [
                    reverse("assets:asset_operator_certification_renew", kwargs={"pk": cert_active.pk}),
                    reverse("assets:asset_operator_certification_revoke", kwargs={"pk": cert_active.pk}),
                    reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert_active.pk}),
                    reverse("assets:asset_operator_certification_delete", kwargs={"pk": cert_active.pk}),
                ],
            ),
            (
                reverse("assets:asset_knowledge_article_list"),
                [reverse("assets:asset_knowledge_article_delete", kwargs={"pk": art_draft.pk})],
            ),
            (
                reverse("assets:asset_knowledge_article_detail", kwargs={"pk": art_draft.pk}),
                [
                    reverse("assets:asset_knowledge_article_delete", kwargs={"pk": art_draft.pk}),
                    reverse("assets:asset_knowledge_article_publish", kwargs={"pk": art_draft.pk}),
                    reverse("assets:asset_knowledge_article_retire", kwargs={"pk": art_draft.pk}),
                ],
            ),
        ]

        for page_url, admin_action_urls in checks:
            member_html = member_client.get(page_url).content.decode("utf-8")
            admin_html = client_a.get(page_url).content.decode("utf-8")
            for action_url in admin_action_urls:
                assert action_url not in member_html, f"Admin action {action_url} leaked in member HTML at {page_url}"
                assert action_url in admin_html, f"Admin action {action_url} missing in admin HTML at {page_url}"

    def test_asset_document_knowledge_sop_acknowledgment_restricted_to_assigned_operator_or_admin(
        self,
        member_client,
        client_a,
        tenant_a,
        admin_user,
        member_user,
        vendor_party_a,
    ):
        cert_other = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=admin_user, status="active"
        )
        res_forbidden = member_client.post(
            reverse("assets:asset_operator_certification_acknowledge_sop", kwargs={"pk": cert_other.pk})
        )
        assert res_forbidden.status_code == 302
        cert_other.refresh_from_db()
        assert cert_other.sop_acknowledged is False

        # Assigned operator member can acknowledge their own SOP
        cert_own = _asset_document_knowledge_make_cert(
            tenant_a, operator_party=vendor_party_a, operator_user=member_user, status="active"
        )
        res_own = member_client.post(
            reverse("assets:asset_operator_certification_acknowledge_sop", kwargs={"pk": cert_own.pk})
        )
        assert res_own.status_code == 302
        cert_own.refresh_from_db()
        assert cert_own.sop_acknowledged is True

        # Admin can acknowledge on behalf of another operator
        res_admin = client_a.post(
            reverse("assets:asset_operator_certification_acknowledge_sop", kwargs={"pk": cert_other.pk})
        )
        assert res_admin.status_code == 302
        cert_other.refresh_from_db()
        assert cert_other.sop_acknowledged is True


# =====================================================================
# 4. Access Classification Enforcement (restricted_eng & confidential)
# =====================================================================


class TestAssetDocumentKnowledgeAccessClassification:
    def test_asset_document_knowledge_restricted_and_confidential_hidden_in_lists_filters_exports_and_forms(
        self,
        member_client,
        tenant_a,
        admin_user,
        adk_document_a,
    ):
        restricted_doc = _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title="Restricted Turbine Blueprint",
            access_classification="restricted_eng",
            status="draft",
        )
        confidential_doc = _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title="Confidential NDA Calibration Spec",
            access_classification="confidential",
            status="approved",
        )

        # Hidden in repository list, change list, filtered queries, and CSV export
        hidden_targets = [
            reverse("assets:asset_document_list"),
            reverse("assets:asset_document_list") + "?access_classification=confidential",
            reverse("assets:asset_document_list") + "?access_classification=restricted_eng",
            reverse("assets:asset_document_change_list"),
            reverse("assets:asset_document_export_csv"),
            reverse("assets:asset_document_export_csv") + "?scope=changes",
        ]
        for url in hidden_targets:
            res = member_client.get(url)
            assert res.status_code == 200
            body = res.content.decode("utf-8")
            assert restricted_doc.title not in body
            assert restricted_doc.number not in body
            assert confidential_doc.title not in body
            assert confidential_doc.number not in body

        # Open document remains visible in list & export
        assert adk_document_a.title in member_client.get(reverse("assets:asset_document_list")).content.decode("utf-8")

        # Hidden from form dropdowns (`supersedes`, `primary_document`, `related_document`)
        for form_url in (
            reverse("assets:asset_document_create"),
            reverse("assets:asset_operating_procedure_create"),
            reverse("assets:asset_knowledge_article_create"),
        ):
            html = member_client.get(form_url).content.decode("utf-8")
            assert restricted_doc.title not in html
            assert restricted_doc.number not in html
            assert confidential_doc.title not in html
            assert confidential_doc.number not in html

        # Submitting raw PK of restricted/confidential doc in POST is rejected by form queryset
        doc_count = AssetDocument.objects.count()
        res_doc_post = member_client.post(
            reverse("assets:asset_document_create"),
            data=_asset_document_knowledge_doc_payload(
                title="Attempt Link Restricted Supersedes",
                supersedes=str(confidential_doc.pk),
            ),
        )
        assert res_doc_post.status_code == 200
        assert AssetDocument.objects.count() == doc_count

        sop_count = AssetOperatingProcedure.objects.count()
        res_sop_post = member_client.post(
            reverse("assets:asset_operating_procedure_create"),
            data=_asset_document_knowledge_sop_payload(
                title="Attempt Link Restricted Primary Doc",
                primary_document=str(restricted_doc.pk),
            ),
        )
        assert res_sop_post.status_code == 200
        assert AssetOperatingProcedure.objects.count() == sop_count

        art_count = AssetKnowledgeArticle.objects.count()
        res_art_post = member_client.post(
            reverse("assets:asset_knowledge_article_create"),
            data=_asset_document_knowledge_article_payload(
                title="Attempt Link Confidential Related Doc",
                related_document=str(confidential_doc.pk),
            ),
        )
        assert res_art_post.status_code == 200
        assert AssetKnowledgeArticle.objects.count() == art_count

    def test_asset_document_knowledge_restricted_and_confidential_404_on_direct_endpoints_for_non_permitted_member(
        self,
        tmp_path,
        member_client,
        tenant_a,
        admin_user,
    ):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            for classification in ("restricted_eng", "confidential"):
                doc = _asset_document_knowledge_make_doc(
                    tenant_a,
                    owner=admin_user,
                    title=f"Secret {classification}",
                    access_classification=classification,
                    status="draft",
                    file=SimpleUploadedFile(
                        f"{classification}.pdf", b"%PDF-1.4 secret", content_type="application/pdf"
                    ),
                )
                for url in (
                    reverse("assets:asset_document_detail", kwargs={"pk": doc.pk}),
                    reverse("assets:asset_document_download", kwargs={"pk": doc.pk}),
                    reverse("assets:asset_document_edit", kwargs={"pk": doc.pk}),
                ):
                    assert member_client.get(url).status_code == 404

                for url, payload in (
                    (
                        reverse("assets:asset_document_edit", kwargs={"pk": doc.pk}),
                        _asset_document_knowledge_doc_payload(title="Tamper"),
                    ),
                    (reverse("assets:asset_document_checkout", kwargs={"pk": doc.pk}), {}),
                    (reverse("assets:asset_document_checkin", kwargs={"pk": doc.pk}), {}),
                    (reverse("assets:asset_document_submit_review", kwargs={"pk": doc.pk}), {}),
                    (reverse("assets:asset_document_create_revision", kwargs={"pk": doc.pk}), {}),
                ):
                    assert member_client.post(url, data=payload).status_code == 404

                doc.refresh_from_db()
                assert doc.title == f"Secret {classification}"
                assert doc.status == "draft"
                assert doc.checked_out_by is None

    def test_asset_document_knowledge_linked_sop_and_kb_redact_restricted_document_link(
        self,
        client_a,
        member_client,
        tenant_a,
        admin_user,
        member_user,
    ):
        restricted_doc = _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title="Classified P&ID Redaction Target",
            access_classification="restricted_eng",
            status="approved",
        )
        sop = _asset_document_knowledge_make_sop(
            tenant_a,
            author=admin_user,
            primary_document=restricted_doc,
        )
        art = _asset_document_knowledge_make_article(
            tenant_a,
            author=admin_user,
            related_document=restricted_doc,
        )

        doc_detail_url = reverse("assets:asset_document_detail", kwargs={"pk": restricted_doc.pk})

        for detail_url in (
            reverse("assets:asset_operating_procedure_detail", kwargs={"pk": sop.pk}),
            reverse("assets:asset_knowledge_article_detail", kwargs={"pk": art.pk}),
        ):
            member_html = member_client.get(detail_url).content.decode("utf-8")
            assert "Restricted Document" in member_html
            assert doc_detail_url not in member_html
            assert restricted_doc.title not in member_html

            admin_html = client_a.get(detail_url).content.decode("utf-8")
            assert "Restricted Document" not in admin_html
            assert doc_detail_url in admin_html

        # If member is assigned as reviewer, link becomes visible
        restricted_doc.reviewer = member_user
        restricted_doc.save(update_fields=["reviewer", "updated_at"])
        reviewer_sop_html = member_client.get(
            reverse("assets:asset_operating_procedure_detail", kwargs={"pk": sop.pk})
        ).content.decode("utf-8")
        assert "Restricted Document" not in reviewer_sop_html
        assert doc_detail_url in reviewer_sop_html

    def test_asset_document_knowledge_owner_reviewer_and_admin_retain_access_to_restricted_docs(
        self,
        tmp_path,
        client_a,
        member_client,
        tenant_a,
        admin_user,
        member_user,
    ):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            owned_doc = _asset_document_knowledge_make_doc(
                tenant_a,
                owner=member_user,
                title="Member Owned Restricted Doc",
                access_classification="restricted_eng",
                status="draft",
                file=SimpleUploadedFile("owned.pdf", b"%PDF-1.4 owned", content_type="application/pdf"),
            )
            reviewed_doc = _asset_document_knowledge_make_doc(
                tenant_a,
                owner=admin_user,
                reviewer=member_user,
                title="Member Reviewed Confidential Doc",
                access_classification="confidential",
                status="in_review",
                file=SimpleUploadedFile("reviewed.pdf", b"%PDF-1.4 reviewed", content_type="application/pdf"),
            )

            for doc in (owned_doc, reviewed_doc):
                assert member_client.get(reverse("assets:asset_document_detail", kwargs={"pk": doc.pk})).status_code == 200
                dl_member = member_client.get(reverse("assets:asset_document_download", kwargs={"pk": doc.pk}))
                assert dl_member.status_code == 200
                dl_member.close()

                assert client_a.get(reverse("assets:asset_document_detail", kwargs={"pk": doc.pk})).status_code == 200
                dl_admin = client_a.get(reverse("assets:asset_document_download", kwargs={"pk": doc.pk}))
                assert dl_admin.status_code == 200
                dl_admin.close()

            list_html = member_client.get(reverse("assets:asset_document_list")).content.decode("utf-8")
            assert owned_doc.title in list_html
            assert reviewed_doc.title in list_html


# =====================================================================
# 5. Document Checkout Ownership Lock
# =====================================================================


class TestAssetDocumentKnowledgeCheckoutLock:
    def test_asset_document_knowledge_checkout_lock_blocks_other_member_and_hides_ui_actions(
        self,
        member_client,
        tenant_a,
        admin_user,
    ):
        locked_doc = _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title="Admin Checked Out Draft",
            access_classification="public_floor",
            status="draft",
            checked_out_by=admin_user,
            checked_out_at=timezone.now(),
        )
        edit_url = reverse("assets:asset_document_edit", kwargs={"pk": locked_doc.pk})
        detail_url = reverse("assets:asset_document_detail", kwargs={"pk": locked_doc.pk})
        checkin_url = reverse("assets:asset_document_checkin", kwargs={"pk": locked_doc.pk})

        # Blocked from edit (GET & POST), submit_review, checkin, checkout
        res_edit_get = member_client.get(edit_url)
        assert res_edit_get.status_code == 302
        assert res_edit_get["Location"] == detail_url

        res_edit_post = member_client.post(
            edit_url,
            data=_asset_document_knowledge_doc_payload(title="Bypass Lock Edit"),
        )
        assert res_edit_post.status_code == 302

        assert member_client.post(
            reverse("assets:asset_document_submit_review", kwargs={"pk": locked_doc.pk})
        ).status_code == 302
        assert member_client.post(checkin_url).status_code == 302
        assert member_client.post(
            reverse("assets:asset_document_checkout", kwargs={"pk": locked_doc.pk})
        ).status_code == 302

        locked_doc.refresh_from_db()
        assert locked_doc.title == "Admin Checked Out Draft"
        assert locked_doc.status == "draft"
        assert locked_doc.checked_out_by == admin_user

        # Edit icon and Check-In button hidden in list, changes, and detail HTML for member
        for html_url in (
            reverse("assets:asset_document_list"),
            reverse("assets:asset_document_change_list"),
            detail_url,
        ):
            html = member_client.get(html_url).content.decode("utf-8")
            assert edit_url not in html, f"Edit URL leaked for locked doc at {html_url}"
            assert checkin_url not in html, f"Checkin URL leaked for locked doc at {html_url}"

    def test_asset_document_knowledge_approve_release_respects_checkout_lock_and_admin_checkin_override(
        self,
        client_a,
        tenant_a,
        member_user,
        admin_user,
    ):
        doc_member_lock = _asset_document_knowledge_make_doc(
            tenant_a,
            owner=member_user,
            status="in_review",
            checked_out_by=member_user,
            checked_out_at=timezone.now(),
        )
        approve_url = reverse("assets:asset_document_approve_release", kwargs={"pk": doc_member_lock.pk})
        checkin_url = reverse("assets:asset_document_checkin", kwargs={"pk": doc_member_lock.pk})

        # Admin cannot approve while checked out by another user
        res_blocked = client_a.post(approve_url)
        assert res_blocked.status_code == 302
        doc_member_lock.refresh_from_db()
        assert doc_member_lock.status == "in_review"
        assert doc_member_lock.checked_out_by == member_user

        # Admin can override check-in, then approve & release
        res_checkin = client_a.post(checkin_url)
        assert res_checkin.status_code == 302
        doc_member_lock.refresh_from_db()
        assert doc_member_lock.checked_out_by is None

        res_approved = client_a.post(approve_url)
        assert res_approved.status_code == 302
        doc_member_lock.refresh_from_db()
        assert doc_member_lock.status == "approved"
        assert doc_member_lock.approved_by == admin_user


# =====================================================================
# 6. POST-Only Method Enforcement & Mass Assignment Resistance
# =====================================================================


class TestAssetDocumentKnowledgeMethodAndMassAssignment:
    def test_asset_document_knowledge_post_only_endpoints_return_405_on_get(
        self,
        client_a,
        adk_document_draft_a,
        adk_procedure_draft_a,
        adk_certification_pending_a,
        adk_article_draft_a,
    ):
        for url in _asset_document_knowledge_post_only_urls(
            adk_document_draft_a,
            adk_procedure_draft_a,
            adk_certification_pending_a,
            adk_article_draft_a,
        ):
            res = client_a.get(url)
            assert res.status_code == 405, f"Expected 405 on GET {url}, got {res.status_code}"

    def test_asset_document_knowledge_forged_system_fields_ignored_on_create_and_edit(
        self,
        client_a,
        tenant_a,
        tenant_b,
        admin_b,
        vendor_party_a,
    ):
        forged_common = {
            "tenant": str(tenant_b.pk),
            "owner": str(admin_b.pk),
            "author": str(admin_b.pk),
            "approved_by": str(admin_b.pk),
            "reviewed_by": str(admin_b.pk),
            "checked_out_by": str(admin_b.pk),
            "revision_sequence": "99",
            "is_current_revision": "False",
            "helpful_votes": "999",
            "view_count": "9999",
            "sop_acknowledged": "True",
        }

        res_doc = client_a.post(
            reverse("assets:asset_document_create"),
            data=_asset_document_knowledge_doc_payload(status="approved", **forged_common),
        )
        assert res_doc.status_code == 302
        doc = AssetDocument.objects.order_by("-pk").first()
        assert doc.tenant == tenant_a
        assert doc.status == "draft"
        assert doc.approved_by is None
        assert doc.checked_out_by is None
        assert doc.revision_sequence == 1
        assert doc.is_current_revision is True

        res_sop = client_a.post(
            reverse("assets:asset_operating_procedure_create"),
            data=_asset_document_knowledge_sop_payload(status="active", **forged_common),
        )
        assert res_sop.status_code == 302
        sop = AssetOperatingProcedure.objects.order_by("-pk").first()
        assert sop.tenant == tenant_a
        assert sop.status == "draft"
        assert sop.approved_by is None

        res_cert = client_a.post(
            reverse("assets:asset_operator_certification_create"),
            data=_asset_document_knowledge_cert_payload(
                operator_party=vendor_party_a, status="active", **forged_common
            ),
        )
        assert res_cert.status_code == 302
        cert = AssetOperatorCertification.objects.order_by("-pk").first()
        assert cert.tenant == tenant_a
        assert cert.status == "pending"
        assert cert.sop_acknowledged is False

        res_art = client_a.post(
            reverse("assets:asset_knowledge_article_create"),
            data=_asset_document_knowledge_article_payload(status="published", **forged_common),
        )
        assert res_art.status_code == 302
        art = AssetKnowledgeArticle.objects.order_by("-pk").first()
        assert art.tenant == tenant_a
        assert art.status == "draft"
        assert art.reviewed_by is None
        assert art.helpful_votes == 0
        assert art.view_count == 0


# =====================================================================
# 7. File Upload & Download Hardening
# =====================================================================


class TestAssetDocumentKnowledgeFileHardening:
    @pytest.mark.parametrize(
        "filename,content_type",
        [
            ("xss.svg", "image/svg+xml"),
            ("payload.html", "text/html"),
            ("malware.exe", "application/octet-stream"),
        ],
    )
    def test_asset_document_knowledge_rejects_unsafe_extensions_across_all_forms_and_views(
        self,
        tmp_path,
        client_a,
        tenant_a,
        vendor_party_a,
        filename,
        content_type,
    ):
        bad_file = lambda: SimpleUploadedFile(filename, b"<svg onload=alert(1)>", content_type=content_type)
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            doc_form = AssetDocumentForm(
                data=_asset_document_knowledge_doc_payload(),
                files={"file": bad_file()},
                tenant=tenant_a,
            )
            assert not doc_form.is_valid()
            assert "file" in doc_form.errors

            sop_form = AssetOperatingProcedureForm(
                data=_asset_document_knowledge_sop_payload(),
                files={"attachment": bad_file()},
                tenant=tenant_a,
            )
            assert not sop_form.is_valid()
            assert "attachment" in sop_form.errors

            cert_form = AssetOperatorCertificationForm(
                data=_asset_document_knowledge_cert_payload(operator_party=vendor_party_a),
                files={"certificate_file": bad_file()},
                tenant=tenant_a,
            )
            assert not cert_form.is_valid()
            assert "certificate_file" in cert_form.errors

            art_form = AssetKnowledgeArticleForm(
                data=_asset_document_knowledge_article_payload(),
                files={"attachment": bad_file()},
                tenant=tenant_a,
            )
            assert not art_form.is_valid()
            assert "attachment" in art_form.errors

            # Also verify view create POST rejects unsafe upload without creating record
            doc_count = AssetDocument.objects.count()
            res = client_a.post(
                reverse("assets:asset_document_create"),
                data={**_asset_document_knowledge_doc_payload(), "file": bad_file()},
            )
            assert res.status_code == 200
            assert AssetDocument.objects.count() == doc_count

    def test_asset_document_knowledge_rejects_oversized_upload_over_20mb(
        self,
        tmp_path,
        client_a,
        tenant_a,
        vendor_party_a,
    ):
        oversized = SimpleUploadedFile(
            "huge_manual.pdf",
            b"0" * (MAX_UPLOAD_BYTES + 1),
            content_type="application/pdf",
        )
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            form = AssetDocumentForm(
                data=_asset_document_knowledge_doc_payload(),
                files={"file": oversized},
                tenant=tenant_a,
            )
            assert not form.is_valid()
            assert "file" in form.errors

            cert_form = AssetOperatorCertificationForm(
                data=_asset_document_knowledge_cert_payload(operator_party=vendor_party_a),
                files={"certificate_file": SimpleUploadedFile("huge_cert.pdf", b"0" * (MAX_UPLOAD_BYTES + 1), content_type="application/pdf")},
                tenant=tenant_a,
            )
            assert not cert_form.is_valid()
            assert "certificate_file" in cert_form.errors

            doc_count = AssetDocument.objects.count()
            res = client_a.post(
                reverse("assets:asset_document_create"),
                data={
                    **_asset_document_knowledge_doc_payload(),
                    "file": SimpleUploadedFile(
                        "huge_view.pdf",
                        b"0" * (MAX_UPLOAD_BYTES + 1),
                        content_type="application/pdf",
                    ),
                },
            )
            assert res.status_code == 200
            assert AssetDocument.objects.count() == doc_count

    def test_asset_document_knowledge_downloads_enforce_attachment_nosniff_and_sanitized_filename(
        self,
        tmp_path,
        client_a,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            doc = _asset_document_knowledge_make_doc(
                tenant_a,
                owner=admin_user,
                file=SimpleUploadedFile("manual.pdf", b"%PDF-1.4 doc", content_type="application/pdf"),
            )
            doc.original_filename = '../../evil\r\n"spec;file.pdf'
            doc.save(update_fields=["original_filename", "updated_at"])

            sop = _asset_document_knowledge_make_sop(
                tenant_a,
                author=admin_user,
                attachment=SimpleUploadedFile("sop.pdf", b"%PDF-1.4 sop", content_type="application/pdf"),
            )
            sop.original_filename = 'bad\n"sop;sheet.pdf'
            sop.save(update_fields=["original_filename", "updated_at"])

            cert = _asset_document_knowledge_make_cert(
                tenant_a,
                operator_party=vendor_party_a,
                operator_user=admin_user,
                certificate_file=SimpleUploadedFile("cert.pdf", b"%PDF-1.4 cert", content_type="application/pdf"),
            )
            cert.original_filename = '..\\..\\cert\r"name.pdf'
            cert.save(update_fields=["original_filename", "updated_at"])

            art = _asset_document_knowledge_make_article(
                tenant_a,
                author=admin_user,
                attachment=SimpleUploadedFile("rca.pdf", b"%PDF-1.4 rca", content_type="application/pdf"),
            )
            art.original_filename = 'dir/sub\\rca"evidence;1.pdf'
            art.save(update_fields=["original_filename", "updated_at"])

            for dl_url in (
                reverse("assets:asset_document_download", kwargs={"pk": doc.pk}),
                reverse("assets:asset_operating_procedure_download", kwargs={"pk": sop.pk}),
                reverse("assets:asset_operator_certification_download", kwargs={"pk": cert.pk}),
                reverse("assets:asset_knowledge_article_download", kwargs={"pk": art.pk}),
            ):
                res = client_a.get(dl_url)
                try:
                    assert res.status_code == 200
                    assert res["X-Content-Type-Options"] == "nosniff"
                    disposition = res["Content-Disposition"]
                    assert disposition.startswith("attachment;")
                    assert "\r" not in disposition
                    assert "\n" not in disposition
                    assert ".." not in disposition
                    assert ";" not in disposition.split("filename=", 1)[1]
                finally:
                    res.close()

    def test_asset_document_knowledge_edit_forms_use_file_input_without_currently_media_href(
        self,
        tmp_path,
        client_a,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            doc = _asset_document_knowledge_make_doc(
                tenant_a,
                owner=admin_user,
                status="draft",
                file=SimpleUploadedFile("manual.pdf", b"%PDF-1.4 doc", content_type="application/pdf"),
            )
            sop = _asset_document_knowledge_make_sop(
                tenant_a,
                author=admin_user,
                status="draft",
                attachment=SimpleUploadedFile("sop.pdf", b"%PDF-1.4 sop", content_type="application/pdf"),
            )
            cert = _asset_document_knowledge_make_cert(
                tenant_a,
                operator_party=vendor_party_a,
                operator_user=admin_user,
                status="pending",
                certificate_file=SimpleUploadedFile("cert.pdf", b"%PDF-1.4 cert", content_type="application/pdf"),
            )
            art = _asset_document_knowledge_make_article(
                tenant_a,
                author=admin_user,
                status="draft",
                attachment=SimpleUploadedFile("rca.pdf", b"%PDF-1.4 rca", content_type="application/pdf"),
            )

            for edit_url in (
                reverse("assets:asset_document_edit", kwargs={"pk": doc.pk}),
                reverse("assets:asset_operating_procedure_edit", kwargs={"pk": sop.pk}),
                reverse("assets:asset_operator_certification_edit", kwargs={"pk": cert.pk}),
                reverse("assets:asset_knowledge_article_edit", kwargs={"pk": art.pk}),
            ):
                html = client_a.get(edit_url).content.decode("utf-8")
                assert 'type="file"' in html
                assert "Currently:" not in html
                assert 'href="/media/' not in html


# =====================================================================
# 8. Stored XSS Escaping, CSV Formula Injection & AuditLog
# =====================================================================


class TestAssetDocumentKnowledgeXSSCSVAndAudit:
    def test_asset_document_knowledge_stored_xss_escaped_across_html_views(
        self,
        client_a,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        xss_script = "<script>alert(1)</script>"
        xss_img = "<img src=x onerror=alert(1)>"

        doc = _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title=f"Doc {xss_script}",
            tag_code=xss_img,
            description=xss_img,
            redline_summary=xss_script,
            status="draft",
        )
        sop = _asset_document_knowledge_make_sop(
            tenant_a,
            author=admin_user,
            title=f"SOP {xss_script}",
            required_ppe=xss_img,
            hazard_warnings=xss_script,
            status="draft",
        )
        cert = _asset_document_knowledge_make_cert(
            tenant_a,
            operator_party=vendor_party_a,
            operator_user=admin_user,
            title=f"Cert {xss_script}",
            qualification_code=xss_img,
            notes=xss_script,
            status="pending",
        )
        art = _asset_document_knowledge_make_article(
            tenant_a,
            author=admin_user,
            title=f"KB {xss_script}",
            symptom_problem=xss_img,
            tags=f"pump,{xss_img}",
            status="draft",
        )

        urls = [
            reverse("assets:asset_document_list"),
            reverse("assets:asset_document_change_list"),
            reverse("assets:asset_document_detail", kwargs={"pk": doc.pk}),
            reverse("assets:asset_operating_procedure_list"),
            reverse("assets:asset_operating_procedure_detail", kwargs={"pk": sop.pk}),
            reverse("assets:asset_operating_procedure_print", kwargs={"pk": sop.pk}),
            reverse("assets:asset_operator_certification_list"),
            reverse("assets:asset_operator_certification_detail", kwargs={"pk": cert.pk}),
            reverse("assets:asset_knowledge_article_list"),
            reverse("assets:asset_knowledge_article_detail", kwargs={"pk": art.pk}),
        ]
        for url in urls:
            html = client_a.get(url).content.decode("utf-8")
            assert xss_script not in html, f"Raw <script> XSS unescaped at {url}"
            assert xss_img not in html, f"Raw <img> XSS unescaped at {url}"
            assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    def test_asset_document_knowledge_csv_formula_injection_neutralized(
        self,
        client_a,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        formula_payloads = [
            "=CMD|'/C calc'!A0",
            "+SUM(1,2)",
            "-2+3",
            "@SUM(1+1)*cmd|' /C calc'!A0",
            "\t=1+1",
            "\r=1+1",
            " =HYPERLINK(\"http://evil.test\")",
        ]
        for idx, payload in enumerate(formula_payloads):
            _asset_document_knowledge_make_doc(
                tenant_a,
                owner=admin_user,
                title=payload,
                change_request_ref=f"ECR-{idx}",
                status="draft",
            )
            _asset_document_knowledge_make_sop(
                tenant_a,
                author=admin_user,
                title=payload,
                status="draft",
            )
            _asset_document_knowledge_make_cert(
                tenant_a,
                operator_party=vendor_party_a,
                operator_user=admin_user,
                title=payload,
                qualification_code=payload,
                status="pending",
            )
            _asset_document_knowledge_make_article(
                tenant_a,
                author=admin_user,
                title=payload,
                tags=payload,
                status="draft",
            )

        export_urls = [
            (reverse("assets:asset_document_export_csv"), 1),
            (reverse("assets:asset_operating_procedure_export_csv"), 1),
            (reverse("assets:asset_operator_certification_export_csv"), 1),
            (reverse("assets:asset_knowledge_article_export_csv"), 1),
        ]
        for url, title_col in export_urls:
            res = client_a.get(url)
            assert res.status_code == 200
            assert res["Content-Disposition"].startswith("attachment;")
            assert res["X-Content-Type-Options"] == "nosniff"
            rows = list(csv.reader(io.StringIO(res.content.decode("utf-8"))))
            assert len(rows) >= len(formula_payloads) + 1
            exported_titles = [r[title_col] for r in rows[1:]]
            for payload in formula_payloads:
                expected_cell = f"'{payload}"
                assert expected_cell in exported_titles, f"Payload {payload!r} not neutralized in {url}"
                assert payload not in exported_titles, f"Unescaped formula {payload!r} found in {url}"

    def test_asset_document_knowledge_audit_logs_recorded_for_mutations_and_workflows(
        self,
        client_a,
        tenant_a,
        admin_user,
        vendor_party_a,
    ):
        # AssetDocument lifecycle: create -> update -> checkout -> checkin -> review -> approve -> archive
        res_doc = client_a.post(
            reverse("assets:asset_document_create"),
            data=_asset_document_knowledge_doc_payload(title="Audit Doc"),
        )
        assert res_doc.status_code == 302
        doc = AssetDocument.objects.get(tenant=tenant_a, title="Audit Doc")
        client_a.post(
            reverse("assets:asset_document_edit", kwargs={"pk": doc.pk}),
            data=_asset_document_knowledge_doc_payload(title="Audit Doc v2"),
        )
        client_a.post(reverse("assets:asset_document_checkout", kwargs={"pk": doc.pk}))
        client_a.post(reverse("assets:asset_document_checkin", kwargs={"pk": doc.pk}))
        client_a.post(reverse("assets:asset_document_submit_review", kwargs={"pk": doc.pk}))
        client_a.post(reverse("assets:asset_document_approve_release", kwargs={"pk": doc.pk}))
        client_a.post(reverse("assets:asset_document_create_revision", kwargs={"pk": doc.pk}))
        client_a.post(reverse("assets:asset_document_archive", kwargs={"pk": doc.pk}))

        doc_ct = ContentType.objects.get_for_model(AssetDocument)
        doc_actions = set(
            AuditLog.objects.filter(
                tenant=tenant_a, user=admin_user, content_type=doc_ct, object_id=doc.pk
            ).values_list("action", flat=True)
        )
        assert {"create", "update", "checkout", "checkin", "review", "approve", "archive"} <= doc_actions

        # Draft document delete writes AuditLog
        doc_del = _asset_document_knowledge_make_doc(tenant_a, owner=admin_user, status="draft")
        doc_del_pk = doc_del.pk
        client_a.post(reverse("assets:asset_document_delete", kwargs={"pk": doc_del_pk}))
        assert AuditLog.objects.filter(
            tenant=tenant_a, user=admin_user, content_type=doc_ct, object_id=doc_del_pk, action="delete"
        ).exists()

        # SOP lifecycle: create -> review -> activate -> retire
        client_a.post(
            reverse("assets:asset_operating_procedure_create"),
            data=_asset_document_knowledge_sop_payload(title="Audit SOP"),
        )
        sop = AssetOperatingProcedure.objects.get(tenant=tenant_a, title="Audit SOP")
        client_a.post(reverse("assets:asset_operating_procedure_submit_review", kwargs={"pk": sop.pk}))
        client_a.post(reverse("assets:asset_operating_procedure_activate", kwargs={"pk": sop.pk}))
        client_a.post(reverse("assets:asset_operating_procedure_retire", kwargs={"pk": sop.pk}))
        sop_ct = ContentType.objects.get_for_model(AssetOperatingProcedure)
        sop_actions = set(
            AuditLog.objects.filter(
                tenant=tenant_a, user=admin_user, content_type=sop_ct, object_id=sop.pk
            ).values_list("action", flat=True)
        )
        assert {"create", "review", "activate", "retire"} <= sop_actions

        # Certification lifecycle: create -> verify -> ack_sop -> renew -> revoke
        client_a.post(
            reverse("assets:asset_operator_certification_create"),
            data=_asset_document_knowledge_cert_payload(
                operator_party=vendor_party_a, operator_user=admin_user, title="Audit Cert"
            ),
        )
        cert = AssetOperatorCertification.objects.get(tenant=tenant_a, title="Audit Cert")
        client_a.post(reverse("assets:asset_operator_certification_verify_activate", kwargs={"pk": cert.pk}))
        client_a.post(reverse("assets:asset_operator_certification_acknowledge_sop", kwargs={"pk": cert.pk}))
        client_a.post(reverse("assets:asset_operator_certification_renew", kwargs={"pk": cert.pk}))
        client_a.post(reverse("assets:asset_operator_certification_revoke", kwargs={"pk": cert.pk}))
        cert_ct = ContentType.objects.get_for_model(AssetOperatorCertification)
        cert_actions = set(
            AuditLog.objects.filter(
                tenant=tenant_a, user=admin_user, content_type=cert_ct, object_id=cert.pk
            ).values_list("action", flat=True)
        )
        assert {"create", "verify", "ack_sop", "renew", "revoke"} <= cert_actions

        # KB Article lifecycle: create -> review -> publish -> helpful -> retire
        client_a.post(
            reverse("assets:asset_knowledge_article_create"),
            data=_asset_document_knowledge_article_payload(title="Audit KB"),
        )
        art = AssetKnowledgeArticle.objects.get(tenant=tenant_a, title="Audit KB")
        client_a.post(reverse("assets:asset_knowledge_article_submit_review", kwargs={"pk": art.pk}))
        client_a.post(reverse("assets:asset_knowledge_article_publish", kwargs={"pk": art.pk}))
        client_a.post(reverse("assets:asset_knowledge_article_mark_helpful", kwargs={"pk": art.pk}))
        client_a.post(reverse("assets:asset_knowledge_article_retire", kwargs={"pk": art.pk}))
        art_ct = ContentType.objects.get_for_model(AssetKnowledgeArticle)
        art_actions = set(
            AuditLog.objects.filter(
                tenant=tenant_a, user=admin_user, content_type=art_ct, object_id=art.pk
            ).values_list("action", flat=True)
        )
        assert {"create", "review", "publish", "helpful", "retire"} <= art_actions
