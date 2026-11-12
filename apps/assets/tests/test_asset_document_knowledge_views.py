"""
View, workflow, filter, pagination, CSV export, file download, print, superuser,
and query-budget tests for Sub-module 11.16: Asset Document & Knowledge Management.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import (
    AssetDocument,
    AssetIncidentReport,
    AssetKnowledgeArticle,
    AssetOperatingProcedure,
    AssetOperatorCertification,
)
from apps.core.models import Party
from apps.hrm.models import EmployeeProfile

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_asset_document_knowledge_*)
# =====================================================================


def _asset_document_knowledge_messages(response):
    """Return queued Django flash message strings for a response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _asset_document_knowledge_superuser_client():
    """Create and authenticate a tenant-less platform superuser (tenant=None)."""
    su = User.objects.create_superuser(
        email="platform_super_11_16_views@naverp.test",
        username="platform_super_11_16_views",
        password="TestPass123!",
        tenant=None,
    )
    client = Client()
    client.force_login(su)
    return client


def _asset_document_knowledge_doc_post_data(**overrides):
    data = {
        "title": "Cooling Tower #1 Operations & Service Manual",
        "document_class": "manual",
        "access_classification": "internal_tech",
        "tag_code": "CT-001-MAN",
        "manufacturer_ref": "BAC FXV-300",
        "document_language": "en",
        "storage_location_ref": "Vault Rack A-12",
        "revision_label": "Rev A",
        "change_type": "new_issue",
        "change_request_ref": "ECR-2026-101",
        "redline_summary": "Initial controlled release.",
        "spec_delta_notes": "Max head pressure 280 PSI.",
        "effective_date": timezone.localdate().isoformat(),
        "expiry_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
        "retention_years": "10",
        "description": "Controlled cooling tower manual.",
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_sop_post_data(**overrides):
    data = {
        "title": "Cooling Tower Fan Drive LOTO Procedure",
        "procedure_type": "loto_isolation",
        "safety_level": "high_hazard_loto",
        "revision_label": "Rev 1.0",
        "purpose_scope": "Isolate 480V fan motor prior to belt replacement.",
        "hazard_warnings": "Stored rotational energy & 480V arc-flash.",
        "required_ppe": "Arc-flash visor, Class 0 insulated gloves",
        "loto_required": "on",
        "loto_isolation_points": json.dumps(
            [
                {
                    "energy_source": "Electrical 480V",
                    "tag_id": "MCC-CT1",
                    "isolation_point": "Main Disconnect",
                    "lock_device": "Red Padlock + Tag",
                    "verification_step": "Verify 0V phase-to-phase",
                }
            ]
        ),
        "procedure_steps": json.dumps(
            [
                {
                    "step_no": 1,
                    "title": "Shut down fan VFD",
                    "instruction": "Press local STOP and wait for coast-down.",
                    "expected_reading": "0 RPM",
                }
            ]
        ),
        "required_qualification_code": "LOTO-HV-01",
        "estimated_duration_minutes": "45",
        "review_cycle_months": "12",
        "effective_date": timezone.localdate().isoformat(),
        "next_review_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_cert_post_data(operator_party=None, operator_user=None, **overrides):
    data = {
        "title": "High-Voltage LOTO Authorized Operator",
        "qualification_code": "LOTO-HV-01",
        "qualification_type": "loto_authorized",
        "proficiency_level": "qualified_operator",
        "issuing_authority": "EHS Safety Academy",
        "certificate_reference": "CERT-2026-9901",
        "issued_date": timezone.localdate().isoformat(),
        "expires_on": (timezone.localdate() + timedelta(days=180)).isoformat(),
        "renewal_lead_days": "30",
        "training_hours": "16.00",
        "assessment_score": "94.50",
        "notes": "Completed hands-on LOTO verification.",
    }
    if operator_party is not None:
        data["operator_party"] = str(operator_party.pk)
    if operator_user is not None:
        data["operator_user"] = str(operator_user.pk)
    data.update(overrides)
    return data


def _asset_document_knowledge_article_post_data(**overrides):
    data = {
        "title": "Cooling Tower Gearbox Seal Failure RCA",
        "article_type": "rca_post_incident",
        "rca_methodology": "five_whys",
        "severity": "high",
        "symptom_problem": "Oil sight-glass turned milky after monsoon storm.",
        "root_cause_summary": "Damaged breather desiccant allowed moisture ingress.",
        "five_whys": json.dumps(
            [
                {
                    "why_level": 1,
                    "question": "Why did oil emulsify?",
                    "answer": "Water entered gearbox.",
                }
            ]
        ),
        "contributing_factors": json.dumps(
            {"machine": "Cracked breather housing", "method": "Quarterly check missed"}
        ),
        "remedy_corrective_action": "Flush gearbox oil and replace desiccant breather.",
        "preventive_lessons": "Add breather inspection to monthly PM checklist.",
        "downtime_hours_impacted": "6.50",
        "recurrence_count": "1",
        "tags": "gearbox,cooling-tower,moisture",
        "incident_occurred_on": timezone.localdate().isoformat(),
    }
    data.update(overrides)
    return data


def _asset_document_knowledge_make_doc(tenant, owner=None, **overrides):
    defaults = {
        "tenant": tenant,
        "title": "Controlled Asset Document",
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
        "title": "Controlled Asset SOP",
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
        "title": "Operator Safety Credential",
        "qualification_code": "QUAL-01",
        "qualification_type": "equipment_operator",
        "proficiency_level": "qualified_operator",
        "issued_date": timezone.localdate() - timedelta(days=10),
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
        "title": "Reliability Lessons Learned Note",
        "article_type": "lessons_learned",
        "rca_methodology": "five_whys",
        "severity": "medium",
        "symptom_problem": "Intermittent pressure drop observed on pump discharge.",
        "status": "draft",
        "author": author,
    }
    defaults.update(overrides)
    art = AssetKnowledgeArticle(**defaults)
    art.save()
    return art


def _asset_document_knowledge_parse_csv(response):
    """Decode CSV response body and return parsed rows (header + data)."""
    body = response.content.decode("utf-8")
    return list(csv.reader(io.StringIO(body)))


# =====================================================================
# 1. Overview Page (/assets/) 11.16 KPIs & Links
# =====================================================================


def test_asset_document_knowledge_overview_renders_kpis_and_links(
    client_a,
    tenant_a,
    adk_document_a,
    adk_document_draft_a,
    adk_procedure_a,
    adk_procedure_draft_a,
    adk_certification_a,
    adk_certification_pending_a,
    adk_article_a,
    adk_article_draft_a,
    vendor_party_a,
):
    # Add an expiring certification so expiring_certifications >= 1
    _asset_document_knowledge_make_cert(
        tenant_a,
        operator_party=vendor_party_a,
        title="Expiring LOTO Cert",
        status="expiring_soon",
        expires_on=timezone.localdate() + timedelta(days=5),
    )

    resp = client_a.get(reverse("assets:overview"))
    assert resp.status_code == 200
    kpis = resp.context["kpis"]
    assert kpis["total_documents"] == 2
    assert kpis["approved_documents"] == 1
    assert kpis["total_procedures"] == 2
    assert kpis["active_procedures"] == 1
    assert kpis["total_certifications"] == 3
    assert kpis["expiring_certifications"] == 1
    assert kpis["total_kb_articles"] == 2
    assert kpis["published_kb_articles"] == 1

    html = resp.content.decode()
    assert reverse("assets:asset_document_list") in html
    assert reverse("assets:asset_operating_procedure_list") in html
    assert reverse("assets:asset_operator_certification_list") in html
    assert reverse("assets:asset_knowledge_article_list") in html
    assert "Document Repository" in html
    assert "SOPs &amp; LOTO Checklists" in html
    assert "Operator Certifications" in html
    assert "Lessons Learned &amp; RCA" in html


# =====================================================================
# 2. All 5 List & Queue Pages (Context, Filters, Junk, Pagination, Empty)
# =====================================================================


def test_asset_document_knowledge_document_list_filters_junk_pagination_empty(
    client_a,
    tenant_a,
    admin_user,
    operational_asset_a,
    category_root_a,
    org_unit_a,
    adk_document_a,
    adk_document_draft_a,
    adk_document_b,
):
    url = reverse("assets:asset_document_list")

    # Baseline 200 + exact context vars + table markup
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<table class="table"' in html
    for key in (
        "documents",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "approved_count",
        "in_review_count",
        "expiring_soon_count",
        "checked_out_count",
        "draft_count",
        "class_choices",
        "classification_choices",
        "change_type_choices",
        "status_choices",
        "assets_list",
        "categories",
        "org_units",
        "search_query",
    ):
        assert key in resp.context
    assert resp.context["total_count"] == 2
    assert resp.context["approved_count"] == 1
    assert resp.context["draft_count"] == 1
    assert adk_document_a.number in html
    assert adk_document_b.title not in html
    assert adk_document_b not in list(resp.context["documents"])

    # Search q + choice & FK filters + request.GET re-selection in HTML
    resp_filtered = client_a.get(
        url,
        {
            "q": "Lathe",
            "document_class": "manual",
            "access_classification": "public_floor",
            "change_type": "new_issue",
            "status": "approved",
            "operational_asset": str(operational_asset_a.pk),
            "asset_category": str(category_root_a.pk),
            "org_unit": str(org_unit_a.pk),
        },
    )
    assert resp_filtered.status_code == 200
    fhtml = resp_filtered.content.decode()
    assert list(resp_filtered.context["documents"]) == [adk_document_a]
    assert f'<option value="manual" selected>' in fhtml
    assert f'<option value="public_floor" selected>' in fhtml
    assert f'<option value="new_issue" selected>' in fhtml
    assert f'<option value="approved" selected>' in fhtml
    assert f'<option value="{operational_asset_a.pk}" selected>' in fhtml
    assert f'<option value="{category_root_a.pk}" selected>' in fhtml
    assert f'<option value="{org_unit_a.pk}" selected>' in fhtml

    # Invalid choice & junk/5000-digit FK parameters must return 200 (never 500)
    for bad_params in (
        {"status": "bogus"},
        {"operational_asset": "abc"},
        {"operational_asset": "99999999999999999999999"},
        {"operational_asset": "9" * 5000},
        {"asset_category": "9" * 5000},
        {"org_unit": "9" * 5000},
    ):
        junk_resp = client_a.get(url, bad_params)
        assert junk_resp.status_code == 200
    assert client_a.get(url, {"status": "bogus"}).context["paginator"].count == 2

    # Empty state when 0 matches
    empty_resp = client_a.get(url, {"q": "__nonexistent_doc_11_16__"})
    assert empty_resp.status_code == 200
    assert "No Asset Documents Found" in empty_resp.content.decode()

    # Pagination page 2 preserving query params (total 17 draft docs -> page 2 has 2)
    for idx in range(16):
        _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title=f"Paginated Draft Doc {idx:02d}",
            status="draft",
            document_class="datasheet",
        )
    p1 = client_a.get(url, {"status": "draft", "q": "Paginated"})
    assert p1.status_code == 200
    assert p1.context["is_paginated"] is True
    assert "status=draft" in p1.content.decode()
    assert "q=Paginated" in p1.content.decode()

    p2 = client_a.get(url, {"page": "2", "status": "draft", "q": "Paginated"})
    assert p2.status_code == 200
    assert p2.context["page_obj"].number == 2
    assert len(list(p2.context["documents"])) == 1
    p2_html = p2.content.decode()
    assert "?page=1&q=Paginated&status=draft" in p2_html or (
        "page=1" in p2_html and "status=draft" in p2_html and "q=Paginated" in p2_html
    )


def test_asset_document_knowledge_document_change_list_filters_junk_pagination_empty(
    client_a,
    tenant_a,
    admin_user,
    operational_asset_a,
    adk_document_a,
    adk_document_draft_a,
):
    url = reverse("assets:asset_document_change_list")

    # Baseline approved rev-1 new_issue doc is excluded; draft doc is included
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<table class="table"' in html
    docs = list(resp.context["documents"])
    assert adk_document_draft_a in docs
    assert adk_document_a not in docs
    for key in (
        "documents",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "in_review_count",
        "checked_out_count",
        "draft_count",
        "class_choices",
        "change_type_choices",
        "status_choices",
        "assets_list",
        "search_query",
    ):
        assert key in resp.context

    # Filters + re-selection
    resp_f = client_a.get(
        url,
        {
            "q": "Hydraulic",
            "change_type": "drawing_redline",
            "status": "draft",
            "document_class": "schematic_pid",
            "operational_asset": str(operational_asset_a.pk),
        },
    )
    assert resp_f.status_code == 200
    assert list(resp_f.context["documents"]) == [adk_document_draft_a]
    fhtml = resp_f.content.decode()
    assert '<option value="drawing_redline" selected>' in fhtml
    assert '<option value="draft" selected>' in fhtml
    assert '<option value="schematic_pid" selected>' in fhtml
    assert f'<option value="{operational_asset_a.pk}" selected>' in fhtml

    # Junk & 5000-digit params + invalid status
    for bad_params in (
        {"status": "bogus"},
        {"operational_asset": "abc"},
        {"operational_asset": "99999999999999999999999"},
        {"operational_asset": "9" * 5000},
    ):
        assert client_a.get(url, bad_params).status_code == 200

    # Empty state
    empty_resp = client_a.get(url, {"q": "__no_change_match__"})
    assert empty_resp.status_code == 200
    assert "No Active Document Changes Found" in empty_resp.content.decode()

    # Pagination page 2 preserving query params
    for idx in range(16):
        _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title=f"Change Queue Draft {idx:02d}",
            status="draft",
            change_type="spec_update",
        )
    p2 = client_a.get(url, {"page": "2", "status": "draft", "change_type": "spec_update"})
    assert p2.status_code == 200
    assert p2.context["page_obj"].number == 2
    assert len(list(p2.context["documents"])) == 1
    p2_html = p2.content.decode()
    assert "page=1" in p2_html
    assert "change_type=spec_update" in p2_html
    assert "status=draft" in p2_html


def test_asset_document_knowledge_procedure_list_filters_junk_pagination_empty(
    client_a,
    tenant_a,
    admin_user,
    operational_asset_a,
    category_root_a,
    adk_procedure_a,
    adk_procedure_draft_a,
    adk_procedure_b,
):
    url = reverse("assets:asset_operating_procedure_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<table class="table"' in html
    for key in (
        "procedures",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "active_count",
        "loto_count",
        "overdue_review_count",
        "type_choices",
        "safety_choices",
        "status_choices",
        "assets_list",
        "categories",
        "search_query",
    ):
        assert key in resp.context
    assert adk_procedure_a.number in html
    assert adk_procedure_b.title not in html
    assert adk_procedure_b not in list(resp.context["procedures"])

    # Filters + loto_only + re-selection
    resp_f = client_a.get(
        url,
        {
            "q": "LOTO-01",
            "procedure_type": "loto_isolation",
            "safety_level": "high_hazard_loto",
            "status": "active",
            "operational_asset": str(operational_asset_a.pk),
            "asset_category": str(category_root_a.pk),
            "loto_only": "1",
        },
    )
    assert resp_f.status_code == 200
    assert list(resp_f.context["procedures"]) == [adk_procedure_a]
    fhtml = resp_f.content.decode()
    assert '<option value="loto_isolation" selected>' in fhtml
    assert '<option value="high_hazard_loto" selected>' in fhtml
    assert '<option value="active" selected>' in fhtml
    assert f'<option value="{operational_asset_a.pk}" selected>' in fhtml
    assert f'<option value="{category_root_a.pk}" selected>' in fhtml
    assert '<option value="1" selected>' in fhtml

    # Junk & 5000-digit params + invalid status
    for bad_params in (
        {"status": "bogus"},
        {"operational_asset": "abc"},
        {"operational_asset": "99999999999999999999999"},
        {"operational_asset": "9" * 5000},
        {"asset_category": "9" * 5000},
    ):
        assert client_a.get(url, bad_params).status_code == 200

    # Empty state
    empty_resp = client_a.get(url, {"q": "__no_sop_match__"})
    assert empty_resp.status_code == 200
    assert "No Operating Procedures Found" in empty_resp.content.decode()

    # Pagination page 2 preserving query params
    for idx in range(16):
        _asset_document_knowledge_make_sop(
            tenant_a,
            author=admin_user,
            title=f"Paginated SOP {idx:02d}",
            loto_required=True,
            status="draft",
        )
    p2 = client_a.get(url, {"page": "2", "status": "draft", "loto_only": "1"})
    assert p2.status_code == 200
    assert p2.context["page_obj"].number == 2
    assert len(list(p2.context["procedures"])) == 1
    p2_html = p2.content.decode()
    assert "page=1" in p2_html
    assert "status=draft" in p2_html
    assert "loto_only=1" in p2_html


def test_asset_document_knowledge_certification_list_filters_junk_pagination_empty(
    client_a,
    tenant_a,
    vendor_party_a,
    operational_asset_a,
    adk_procedure_a,
    adk_certification_a,
    adk_certification_pending_a,
    adk_certification_b,
):
    url = reverse("assets:asset_operator_certification_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<table class="table"' in html
    for key in (
        "certifications",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "active_count",
        "expiring_soon_count",
        "expired_count",
        "qualification_type_choices",
        "proficiency_choices",
        "status_choices",
        "assets_list",
        "procedures",
        "can_manage",
        "search_query",
    ):
        assert key in resp.context
    assert adk_certification_a.number in html
    assert adk_certification_b.title not in html
    assert adk_certification_b not in list(resp.context["certifications"])

    # Filters + re-selection
    resp_f = client_a.get(
        url,
        {
            "q": "LOTO-01",
            "qualification_type": "loto_authorized",
            "proficiency_level": "qualified_operator",
            "status": "active",
            "operational_asset": str(operational_asset_a.pk),
            "operating_procedure": str(adk_procedure_a.pk),
        },
    )
    assert resp_f.status_code == 200
    assert list(resp_f.context["certifications"]) == [adk_certification_a]
    fhtml = resp_f.content.decode()
    assert '<option value="loto_authorized" selected>' in fhtml
    assert '<option value="qualified_operator" selected>' in fhtml
    assert '<option value="active" selected>' in fhtml
    assert f'<option value="{operational_asset_a.pk}" selected>' in fhtml
    assert f'<option value="{adk_procedure_a.pk}" selected>' in fhtml

    # Junk & 5000-digit params + invalid status
    for bad_params in (
        {"status": "bogus"},
        {"operational_asset": "abc"},
        {"operational_asset": "99999999999999999999999"},
        {"operational_asset": "9" * 5000},
        {"operating_procedure": "9" * 5000},
    ):
        assert client_a.get(url, bad_params).status_code == 200

    # Empty state
    empty_resp = client_a.get(url, {"q": "__no_cert_match__"})
    assert empty_resp.status_code == 200
    assert "No Operator Certifications Found" in empty_resp.content.decode()

    # Pagination page 2 preserving query params
    for idx in range(16):
        _asset_document_knowledge_make_cert(
            tenant_a,
            operator_party=vendor_party_a,
            title=f"Paginated Cert {idx:02d}",
            status="pending",
            qualification_type="equipment_operator",
        )
    p2 = client_a.get(url, {"page": "2", "status": "pending", "q": "Paginated"})
    assert p2.status_code == 200
    assert p2.context["page_obj"].number == 2
    assert len(list(p2.context["certifications"])) == 1
    p2_html = p2.content.decode()
    assert "page=1" in p2_html
    assert "q=Paginated" in p2_html
    assert "status=pending" in p2_html


def test_asset_document_knowledge_article_list_filters_junk_pagination_empty(
    client_a,
    tenant_a,
    admin_user,
    operational_asset_a,
    failure_mode_a,
    adk_article_a,
    adk_article_draft_a,
    adk_article_b,
):
    url = reverse("assets:asset_knowledge_article_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<table class="table"' in html
    for key in (
        "articles",
        "paginator",
        "page_obj",
        "is_paginated",
        "total_count",
        "published_count",
        "critical_high_count",
        "total_downtime_hours",
        "article_type_choices",
        "rca_choices",
        "severity_choices",
        "status_choices",
        "assets_list",
        "failure_modes",
        "search_query",
    ):
        assert key in resp.context
    assert adk_article_a.number in html
    assert adk_article_b.title not in html
    assert adk_article_b not in list(resp.context["articles"])

    # Filters + re-selection
    resp_f = client_a.get(
        url,
        {
            "q": "spindle",
            "article_type": "rca_post_incident",
            "rca_methodology": "five_whys",
            "severity": "high",
            "status": "published",
            "operational_asset": str(operational_asset_a.pk),
            "failure_mode": str(failure_mode_a.pk),
        },
    )
    assert resp_f.status_code == 200
    assert list(resp_f.context["articles"]) == [adk_article_a]
    fhtml = resp_f.content.decode()
    assert '<option value="rca_post_incident" selected>' in fhtml
    assert '<option value="five_whys" selected>' in fhtml
    assert '<option value="high" selected>' in fhtml
    assert '<option value="published" selected>' in fhtml
    assert f'<option value="{operational_asset_a.pk}" selected>' in fhtml
    assert f'<option value="{failure_mode_a.pk}" selected>' in fhtml

    # Junk & 5000-digit params + invalid status
    for bad_params in (
        {"status": "bogus"},
        {"operational_asset": "abc"},
        {"operational_asset": "99999999999999999999999"},
        {"operational_asset": "9" * 5000},
        {"failure_mode": "9" * 5000},
    ):
        assert client_a.get(url, bad_params).status_code == 200

    # Empty state
    empty_resp = client_a.get(url, {"q": "__no_kb_match__"})
    assert empty_resp.status_code == 200
    assert "No Knowledge Articles Found" in empty_resp.content.decode()

    # Pagination page 2 preserving query params
    for idx in range(16):
        _asset_document_knowledge_make_article(
            tenant_a,
            author=admin_user,
            title=f"Paginated KB {idx:02d}",
            status="draft",
            severity="low",
        )
    p2 = client_a.get(url, {"page": "2", "status": "draft", "severity": "low"})
    assert p2.status_code == 200
    assert p2.context["page_obj"].number == 2
    assert len(list(p2.context["articles"])) == 1
    p2_html = p2.content.decode()
    assert "page=1" in p2_html
    assert "severity=low" in p2_html
    assert "status=draft" in p2_html


# =====================================================================
# 3. All 4 CSV Exports (Headers, scope=changes, Formula Neutralization)
# =====================================================================


def test_asset_document_knowledge_all_csv_exports_headers_scope_and_formula_neutralization(
    client_a,
    tenant_a,
    admin_user,
    vendor_party_a,
    adk_document_a,
    adk_document_draft_a,
):
    # Create formula-injection-laced records across all 4 entities covering =, +, -, @, \t, leading whitespace
    doc_eq = _asset_document_knowledge_make_doc(
        tenant_a,
        owner=admin_user,
        title="=CMD('calc')",
        change_request_ref="  +ECR-1",
    )
    sop_plus = _asset_document_knowledge_make_sop(
        tenant_a,
        author=admin_user,
        title="+1+1",
        revision_label="-Rev1",
    )
    cert_at = _asset_document_knowledge_make_cert(
        tenant_a,
        operator_party=vendor_party_a,
        title="@SUM(1,2)",
        qualification_code="\tTAB-CODE",
    )
    art_ws = _asset_document_knowledge_make_article(
        tenant_a,
        author=admin_user,
        title="  =HYPERLINK(\"http://evil\")",
        tags="-tag1,@tag2",
    )

    # 1. Document CSV export (full vs scope=changes)
    doc_csv_resp = client_a.get(reverse("assets:asset_document_export_csv"))
    assert doc_csv_resp.status_code == 200
    assert "text/csv" in doc_csv_resp["Content-Type"]
    assert doc_csv_resp["Content-Disposition"].startswith('attachment; filename="')
    assert doc_csv_resp["X-Content-Type-Options"] == "nosniff"
    doc_rows = _asset_document_knowledge_parse_csv(doc_csv_resp)
    doc_numbers = {row[0]: row for row in doc_rows[1:]}
    assert adk_document_a.number in doc_numbers
    assert adk_document_draft_a.number in doc_numbers
    assert doc_numbers[doc_eq.number][1] == "'=CMD('calc')"
    assert doc_numbers[doc_eq.number][7] == "'  +ECR-1"

    # scope=changes must exclude baseline non-queue doc (adk_document_a)
    chg_csv_resp = client_a.get(reverse("assets:asset_document_export_csv"), {"scope": "changes"})
    assert chg_csv_resp.status_code == 200
    assert chg_csv_resp["X-Content-Type-Options"] == "nosniff"
    chg_numbers = {row[0] for row in _asset_document_knowledge_parse_csv(chg_csv_resp)[1:]}
    assert adk_document_a.number not in chg_numbers
    assert adk_document_draft_a.number in chg_numbers
    assert doc_eq.number in chg_numbers

    # 2. SOP CSV export
    sop_csv_resp = client_a.get(reverse("assets:asset_operating_procedure_export_csv"))
    assert sop_csv_resp.status_code == 200
    assert sop_csv_resp["Content-Disposition"].startswith('attachment; filename="')
    assert sop_csv_resp["X-Content-Type-Options"] == "nosniff"
    sop_rows = {row[0]: row for row in _asset_document_knowledge_parse_csv(sop_csv_resp)[1:]}
    assert sop_rows[sop_plus.number][1] == "'+1+1"
    assert sop_rows[sop_plus.number][4] == "'-Rev1"

    # 3. Certification CSV export
    cert_csv_resp = client_a.get(reverse("assets:asset_operator_certification_export_csv"))
    assert cert_csv_resp.status_code == 200
    assert cert_csv_resp["Content-Disposition"].startswith('attachment; filename="')
    assert cert_csv_resp["X-Content-Type-Options"] == "nosniff"
    cert_rows = {row[0]: row for row in _asset_document_knowledge_parse_csv(cert_csv_resp)[1:]}
    assert cert_rows[cert_at.number][1] == "'@SUM(1,2)"
    assert cert_rows[cert_at.number][3] == "'\tTAB-CODE"

    # 4. Knowledge Article CSV export
    kb_csv_resp = client_a.get(reverse("assets:asset_knowledge_article_export_csv"))
    assert kb_csv_resp.status_code == 200
    assert kb_csv_resp["Content-Disposition"].startswith('attachment; filename="')
    assert kb_csv_resp["X-Content-Type-Options"] == "nosniff"
    kb_rows = {row[0]: row for row in _asset_document_knowledge_parse_csv(kb_csv_resp)[1:]}
    assert kb_rows[art_ws.number][1] == "'  =HYPERLINK(\"http://evil\")"
    assert kb_rows[art_ws.number][11] == "'-tag1,@tag2"


# =====================================================================
# 4. CRUD, File Download, Print, and Lock Guards across all 4 Entities
# =====================================================================


def test_asset_document_knowledge_document_crud_download_and_locks(
    client_a, tenant_a, admin_user, adk_document_a, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)

    # Create GET & POST with uploaded file
    get_create = client_a.get(reverse("assets:asset_document_create"))
    assert get_create.status_code == 200
    assert get_create.context["is_edit"] is False

    upload = SimpleUploadedFile("chiller_manual.pdf", b"%PDF-1.4\nhello", content_type="application/pdf")
    post_create = client_a.post(
        reverse("assets:asset_document_create"),
        data=_asset_document_knowledge_doc_post_data(file=upload),
    )
    assert post_create.status_code == 302
    created = AssetDocument.objects.get(tenant=tenant_a, title="Cooling Tower #1 Operations & Service Manual")
    assert created.status == "draft"
    assert created.owner == admin_user
    assert created.is_current_revision is True
    assert created.revision_sequence == 1
    assert created.original_filename == "chiller_manual.pdf"
    assert created.file_size_bytes == len(b"%PDF-1.4\nhello")
    assert len(created.file_checksum) == 64

    # Detail
    detail_resp = client_a.get(reverse("assets:asset_document_detail", args=[created.pk]))
    assert detail_resp.status_code == 200
    assert detail_resp.context["document"] == created
    assert detail_resp.context["can_edit"] is True
    assert detail_resp.context["can_approve"] is True

    # Download with attachment + nosniff
    dl_resp = client_a.get(reverse("assets:asset_document_download", args=[created.pk]))
    assert dl_resp.status_code == 200
    assert dl_resp["Content-Disposition"].startswith("attachment;")
    assert dl_resp["X-Content-Type-Options"] == "nosniff"
    b"".join(dl_resp.streaming_content)
    dl_resp.close()

    # Missing stored file on disk -> 404
    os.remove(created.file.path)
    missing_resp = client_a.get(reverse("assets:asset_document_download", args=[created.pk]))
    assert missing_resp.status_code == 404

    # No-file record download -> 404
    assert client_a.get(reverse("assets:asset_document_download", args=[adk_document_a.pk])).status_code == 404

    # Edit: setting supersedes updates is_current_revision=False and revision_sequence>=2; clearing restores True/1
    edit_url = reverse("assets:asset_document_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    resp_edit_sub = client_a.post(
        edit_url,
        data=_asset_document_knowledge_doc_post_data(
            title="Cooling Tower #1 Operations Rev B",
            supersedes=str(adk_document_a.pk),
            revision_label="Rev B",
        ),
    )
    assert resp_edit_sub.status_code == 302
    created.refresh_from_db()
    assert created.supersedes_id == adk_document_a.pk
    assert created.is_current_revision is False
    assert created.revision_sequence == 2

    resp_edit_clear = client_a.post(
        edit_url,
        data=_asset_document_knowledge_doc_post_data(
            title="Cooling Tower #1 Operations Rev A",
            supersedes="",
            revision_label="Rev A",
        ),
    )
    assert resp_edit_clear.status_code == 302
    created.refresh_from_db()
    assert created.supersedes_id is None
    assert created.is_current_revision is True
    assert created.revision_sequence == 1

    # Locked document (approved) cannot be edited or deleted
    assert client_a.get(reverse("assets:asset_document_edit", args=[adk_document_a.pk])).status_code == 302
    assert (
        client_a.post(
            reverse("assets:asset_document_edit", args=[adk_document_a.pk]),
            data=_asset_document_knowledge_doc_post_data(title="Tampered"),
        ).status_code
        == 302
    )
    adk_document_a.refresh_from_db()
    assert adk_document_a.title != "Tampered"
    del_locked = client_a.post(reverse("assets:asset_document_delete", args=[adk_document_a.pk]))
    assert del_locked.status_code == 302
    assert AssetDocument.objects.filter(pk=adk_document_a.pk).exists()

    # Delete is POST-only; POST deletes unlocked draft
    del_url = reverse("assets:asset_document_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    del_ok = client_a.post(del_url)
    assert del_ok.status_code == 302
    assert not AssetDocument.objects.filter(pk=created.pk).exists()


def test_asset_document_knowledge_procedure_crud_print_download_and_locks(
    client_a, tenant_a, admin_user, adk_procedure_a, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)

    # Create GET & POST with attachment
    assert client_a.get(reverse("assets:asset_operating_procedure_create")).status_code == 200
    upload = SimpleUploadedFile("loto_diagram.pdf", b"%PDF-1.4\nloto", content_type="application/pdf")
    post_create = client_a.post(
        reverse("assets:asset_operating_procedure_create"),
        data=_asset_document_knowledge_sop_post_data(attachment=upload),
    )
    assert post_create.status_code == 302
    created = AssetOperatingProcedure.objects.get(tenant=tenant_a, title="Cooling Tower Fan Drive LOTO Procedure")
    assert created.status == "draft"
    assert created.author == admin_user
    assert created.step_count == 1
    assert created.isolation_point_count == 1

    # Detail & Print
    detail_resp = client_a.get(reverse("assets:asset_operating_procedure_detail", args=[created.pk]))
    assert detail_resp.status_code == 200
    assert detail_resp.context["can_edit"] is True

    print_resp = client_a.get(reverse("assets:asset_operating_procedure_print", args=[created.pk]))
    assert print_resp.status_code == 200
    phtml = print_resp.content.decode()
    assert "@media print" in phtml
    assert created.number in phtml
    assert "MCC-CT1" in phtml
    assert "Shut down fan VFD" in phtml

    # Download & missing file -> 404
    dl_resp = client_a.get(reverse("assets:asset_operating_procedure_download", args=[created.pk]))
    assert dl_resp.status_code == 200
    assert dl_resp["Content-Disposition"].startswith("attachment;")
    assert dl_resp["X-Content-Type-Options"] == "nosniff"
    b"".join(dl_resp.streaming_content)
    dl_resp.close()

    os.remove(created.attachment.path)
    assert client_a.get(reverse("assets:asset_operating_procedure_download", args=[created.pk])).status_code == 404

    # Edit draft SOP
    edit_url = reverse("assets:asset_operating_procedure_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    assert (
        client_a.post(
            edit_url,
            data=_asset_document_knowledge_sop_post_data(title="Cooling Tower Fan Drive LOTO v2"),
        ).status_code
        == 302
    )
    created.refresh_from_db()
    assert created.title == "Cooling Tower Fan Drive LOTO v2"

    # Locked (active) SOP cannot be edited or deleted
    assert client_a.get(reverse("assets:asset_operating_procedure_edit", args=[adk_procedure_a.pk])).status_code == 302
    assert client_a.post(reverse("assets:asset_operating_procedure_delete", args=[adk_procedure_a.pk])).status_code == 302
    assert AssetOperatingProcedure.objects.filter(pk=adk_procedure_a.pk).exists()

    # Delete POST-only
    del_url = reverse("assets:asset_operating_procedure_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    assert client_a.post(del_url).status_code == 302
    assert not AssetOperatingProcedure.objects.filter(pk=created.pk).exists()


def test_asset_document_knowledge_certification_crud_download_and_locks(
    client_a, tenant_a, vendor_party_a, admin_user, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)

    # Create GET & POST with certificate_file
    assert client_a.get(reverse("assets:asset_operator_certification_create")).status_code == 200
    upload = SimpleUploadedFile("loto_cert.png", b"\x89PNG\r\n\x1a\ncert", content_type="image/png")
    post_create = client_a.post(
        reverse("assets:asset_operator_certification_create"),
        data=_asset_document_knowledge_cert_post_data(
            operator_party=vendor_party_a,
            operator_user=admin_user,
            certificate_file=upload,
        ),
    )
    assert post_create.status_code == 302
    created = AssetOperatorCertification.objects.get(tenant=tenant_a, title="High-Voltage LOTO Authorized Operator")
    assert created.status == "pending"

    # Detail
    detail_resp = client_a.get(reverse("assets:asset_operator_certification_detail", args=[created.pk]))
    assert detail_resp.status_code == 200
    assert detail_resp.context["can_verify"] is True
    assert detail_resp.context["can_edit"] is True

    # Download & missing file -> 404
    dl_resp = client_a.get(reverse("assets:asset_operator_certification_download", args=[created.pk]))
    assert dl_resp.status_code == 200
    assert dl_resp["Content-Disposition"].startswith("attachment;")
    assert dl_resp["X-Content-Type-Options"] == "nosniff"
    b"".join(dl_resp.streaming_content)
    dl_resp.close()

    os.remove(created.certificate_file.path)
    assert client_a.get(reverse("assets:asset_operator_certification_download", args=[created.pk])).status_code == 404

    # Edit pending certification
    edit_url = reverse("assets:asset_operator_certification_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    assert (
        client_a.post(
            edit_url,
            data=_asset_document_knowledge_cert_post_data(
                operator_party=vendor_party_a,
                operator_user=admin_user,
                title="High-Voltage LOTO Authorized Operator Updated",
            ),
        ).status_code
        == 302
    )
    created.refresh_from_db()
    assert created.title == "High-Voltage LOTO Authorized Operator Updated"

    # Locked (revoked) certification cannot be edited or deleted
    revoked_cert = _asset_document_knowledge_make_cert(
        tenant_a, operator_party=vendor_party_a, title="Revoked Cert", status="revoked"
    )
    assert client_a.get(reverse("assets:asset_operator_certification_edit", args=[revoked_cert.pk])).status_code == 302
    assert client_a.post(reverse("assets:asset_operator_certification_delete", args=[revoked_cert.pk])).status_code == 302
    assert AssetOperatorCertification.objects.filter(pk=revoked_cert.pk).exists()

    # Delete POST-only for pending cert
    del_url = reverse("assets:asset_operator_certification_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    assert client_a.post(del_url).status_code == 302
    assert not AssetOperatorCertification.objects.filter(pk=created.pk).exists()


def test_asset_document_knowledge_article_crud_download_and_locks(
    client_a, tenant_a, admin_user, adk_article_a, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)

    # Create GET & POST with attachment
    assert client_a.get(reverse("assets:asset_knowledge_article_create")).status_code == 200
    upload = SimpleUploadedFile("rca_evidence.pdf", b"%PDF-1.4\nrca", content_type="application/pdf")
    post_create = client_a.post(
        reverse("assets:asset_knowledge_article_create"),
        data=_asset_document_knowledge_article_post_data(attachment=upload),
    )
    assert post_create.status_code == 302
    created = AssetKnowledgeArticle.objects.get(tenant=tenant_a, title="Cooling Tower Gearbox Seal Failure RCA")
    assert created.status == "draft"
    assert created.author == admin_user

    # Detail
    detail_resp = client_a.get(reverse("assets:asset_knowledge_article_detail", args=[created.pk]))
    assert detail_resp.status_code == 200
    assert detail_resp.context["can_edit"] is True
    assert detail_resp.context["can_publish"] is True

    # Download & missing file -> 404
    dl_resp = client_a.get(reverse("assets:asset_knowledge_article_download", args=[created.pk]))
    assert dl_resp.status_code == 200
    assert dl_resp["Content-Disposition"].startswith("attachment;")
    assert dl_resp["X-Content-Type-Options"] == "nosniff"
    b"".join(dl_resp.streaming_content)
    dl_resp.close()

    os.remove(created.attachment.path)
    assert client_a.get(reverse("assets:asset_knowledge_article_download", args=[created.pk])).status_code == 404

    # Edit draft article
    edit_url = reverse("assets:asset_knowledge_article_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    assert (
        client_a.post(
            edit_url,
            data=_asset_document_knowledge_article_post_data(title="Cooling Tower Gearbox Seal Failure RCA v2"),
        ).status_code
        == 302
    )
    created.refresh_from_db()
    assert created.title == "Cooling Tower Gearbox Seal Failure RCA v2"

    # Locked (published) article cannot be edited or deleted
    assert client_a.get(reverse("assets:asset_knowledge_article_edit", args=[adk_article_a.pk])).status_code == 302
    assert client_a.post(reverse("assets:asset_knowledge_article_delete", args=[adk_article_a.pk])).status_code == 302
    assert AssetKnowledgeArticle.objects.filter(pk=adk_article_a.pk).exists()

    # Delete POST-only
    del_url = reverse("assets:asset_knowledge_article_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    assert client_a.post(del_url).status_code == 302
    assert not AssetKnowledgeArticle.objects.filter(pk=created.pk).exists()


# =====================================================================
# 5. All Workflow Transitions across all 4 Entities
# =====================================================================


def test_asset_document_knowledge_document_workflows(
    client_a, member_client, tenant_a, admin_user, member_user, adk_document_a
):
    # Create revision from approved adk_document_a
    rev_resp = client_a.post(reverse("assets:asset_document_create_revision", args=[adk_document_a.pk]))
    assert rev_resp.status_code == 302
    rev_b = AssetDocument.objects.get(tenant=tenant_a, supersedes=adk_document_a)
    assert rev_b.status == "draft"
    assert rev_b.revision_label == "Rev B"
    assert rev_b.revision_sequence == 2
    assert rev_b.is_current_revision is False

    # Checkout by member_user; another non-admin cannot checkin, member can checkin
    assert member_client.post(reverse("assets:asset_document_checkout", args=[rev_b.pk])).status_code == 302
    rev_b.refresh_from_db()
    assert rev_b.checked_out_by == member_user

    # Non-owner admin cannot approve while checked out by member_user
    client_a.post(reverse("assets:asset_document_approve_release", args=[rev_b.pk]))
    rev_b.refresh_from_db()
    assert rev_b.status == "draft"

    # Member checks in
    assert member_client.post(reverse("assets:asset_document_checkin", args=[rev_b.pk])).status_code == 302
    rev_b.refresh_from_db()
    assert rev_b.checked_out_by is None

    # Submit review -> return to draft -> submit review -> approve & release
    assert client_a.post(reverse("assets:asset_document_submit_review", args=[rev_b.pk])).status_code == 302
    rev_b.refresh_from_db()
    assert rev_b.status == "in_review"

    assert client_a.post(reverse("assets:asset_document_return_to_draft", args=[rev_b.pk])).status_code == 302
    rev_b.refresh_from_db()
    assert rev_b.status == "draft"

    client_a.post(reverse("assets:asset_document_submit_review", args=[rev_b.pk]))
    assert client_a.post(reverse("assets:asset_document_approve_release", args=[rev_b.pk])).status_code == 302
    rev_b.refresh_from_db()
    adk_document_a.refresh_from_db()
    assert rev_b.status == "approved"
    assert rev_b.is_current_revision is True
    assert rev_b.approved_by == admin_user
    assert adk_document_a.status == "superseded"
    assert adk_document_a.is_current_revision is False

    # Archive rev_b; archived doc cannot spawn new revision
    assert client_a.post(reverse("assets:asset_document_archive", args=[rev_b.pk])).status_code == 302
    rev_b.refresh_from_db()
    assert rev_b.status == "archived"
    assert rev_b.is_current_revision is False
    before_count = AssetDocument.objects.filter(tenant=tenant_a).count()
    client_a.post(reverse("assets:asset_document_create_revision", args=[rev_b.pk]))
    assert AssetDocument.objects.filter(tenant=tenant_a).count() == before_count


def test_asset_document_knowledge_procedure_workflows(client_a, tenant_a, admin_user, adk_procedure_a):
    # Clone revision from active adk_procedure_a
    clone_resp = client_a.post(reverse("assets:asset_operating_procedure_clone_revision", args=[adk_procedure_a.pk]))
    assert clone_resp.status_code == 302
    rev2 = AssetOperatingProcedure.objects.get(tenant=tenant_a, supersedes=adk_procedure_a)
    assert rev2.status == "draft"
    assert rev2.revision_label == "Rev 2.0"

    # Submit for safety review -> Activate (supersedes adk_procedure_a)
    assert client_a.post(reverse("assets:asset_operating_procedure_submit_review", args=[rev2.pk])).status_code == 302
    rev2.refresh_from_db()
    assert rev2.status == "under_review"

    assert client_a.post(reverse("assets:asset_operating_procedure_activate", args=[rev2.pk])).status_code == 302
    rev2.refresh_from_db()
    adk_procedure_a.refresh_from_db()
    assert rev2.status == "active"
    assert rev2.approved_by == admin_user
    assert rev2.effective_date is not None
    assert rev2.next_review_date is not None
    assert adk_procedure_a.status == "superseded"

    # Retire rev2; retired SOP cannot be cloned
    assert client_a.post(reverse("assets:asset_operating_procedure_retire", args=[rev2.pk])).status_code == 302
    rev2.refresh_from_db()
    assert rev2.status == "retired"
    before_count = AssetOperatingProcedure.objects.filter(tenant=tenant_a).count()
    client_a.post(reverse("assets:asset_operating_procedure_clone_revision", args=[rev2.pk]))
    assert AssetOperatingProcedure.objects.filter(tenant=tenant_a).count() == before_count


def test_asset_document_knowledge_certification_workflows_and_refresh_alerts(
    client_a, member_client, tenant_a, vendor_party_a, adk_certification_pending_a
):
    # Verify & activate pending cert (member_user is operator_user)
    assert (
        client_a.post(
            reverse("assets:asset_operator_certification_verify_activate", args=[adk_certification_pending_a.pk])
        ).status_code
        == 302
    )
    adk_certification_pending_a.refresh_from_db()
    assert adk_certification_pending_a.status == "active"
    assert adk_certification_pending_a.last_assessed_date is not None

    # Assigned operator (member_user) acknowledges linked SOP
    assert (
        member_client.post(
            reverse("assets:asset_operator_certification_acknowledge_sop", args=[adk_certification_pending_a.pk])
        ).status_code
        == 302
    )
    adk_certification_pending_a.refresh_from_db()
    assert adk_certification_pending_a.sop_acknowledged is True
    assert adk_certification_pending_a.sop_acknowledged_at is not None

    # Renew extends expires_on by 1 year
    prev_expiry = adk_certification_pending_a.expires_on
    assert (
        client_a.post(
            reverse("assets:asset_operator_certification_renew", args=[adk_certification_pending_a.pk])
        ).status_code
        == 302
    )
    adk_certification_pending_a.refresh_from_db()
    assert adk_certification_pending_a.expires_on.year == prev_expiry.year + 1
    assert adk_certification_pending_a.status == "active"

    # Bulk refresh_alerts transitions stale statuses accurately and skips pending/revoked
    today = timezone.localdate()
    c_to_expiring = _asset_document_knowledge_make_cert(
        tenant_a,
        operator_party=vendor_party_a,
        title="Should become expiring_soon",
        status="active",
        expires_on=today + timedelta(days=10),
        renewal_lead_days=30,
    )
    c_to_expired = _asset_document_knowledge_make_cert(
        tenant_a,
        operator_party=vendor_party_a,
        title="Should become expired",
        status="expiring_soon",
        expires_on=today - timedelta(days=2),
        renewal_lead_days=30,
    )
    c_pending_untouched = _asset_document_knowledge_make_cert(
        tenant_a,
        operator_party=vendor_party_a,
        title="Pending stays pending",
        status="pending",
        expires_on=today - timedelta(days=5),
    )
    refresh_resp = client_a.post(reverse("assets:asset_operator_certification_refresh_alerts"))
    assert refresh_resp.status_code == 302
    c_to_expiring.refresh_from_db()
    c_to_expired.refresh_from_db()
    c_pending_untouched.refresh_from_db()
    assert c_to_expiring.status == "expiring_soon"
    assert c_to_expired.status == "expired"
    assert c_pending_untouched.status == "pending"

    # Revoke
    assert (
        client_a.post(
            reverse("assets:asset_operator_certification_revoke", args=[adk_certification_pending_a.pk])
        ).status_code
        == 302
    )
    adk_certification_pending_a.refresh_from_db()
    assert adk_certification_pending_a.status == "revoked"


def test_asset_document_knowledge_article_workflows(client_a, admin_user, adk_article_draft_a):
    # Detail increments view_count
    assert adk_article_draft_a.view_count == 0
    assert client_a.get(reverse("assets:asset_knowledge_article_detail", args=[adk_article_draft_a.pk])).status_code == 200
    adk_article_draft_a.refresh_from_db()
    assert adk_article_draft_a.view_count == 1

    # Submit review -> Publish -> Mark helpful -> Retire
    assert (
        client_a.post(
            reverse("assets:asset_knowledge_article_submit_review", args=[adk_article_draft_a.pk])
        ).status_code
        == 302
    )
    adk_article_draft_a.refresh_from_db()
    assert adk_article_draft_a.status == "peer_review"

    assert (
        client_a.post(
            reverse("assets:asset_knowledge_article_publish", args=[adk_article_draft_a.pk])
        ).status_code
        == 302
    )
    adk_article_draft_a.refresh_from_db()
    assert adk_article_draft_a.status == "published"
    assert adk_article_draft_a.reviewed_by == admin_user
    assert adk_article_draft_a.published_at is not None

    assert (
        client_a.post(
            reverse("assets:asset_knowledge_article_mark_helpful", args=[adk_article_draft_a.pk])
        ).status_code
        == 302
    )
    adk_article_draft_a.refresh_from_db()
    assert adk_article_draft_a.helpful_votes == 1

    assert (
        client_a.post(
            reverse("assets:asset_knowledge_article_retire", args=[adk_article_draft_a.pk])
        ).status_code
        == 302
    )
    adk_article_draft_a.refresh_from_db()
    assert adk_article_draft_a.status == "retired"


# =====================================================================
# 6. Superuser (tenant=None) Safe List Rendering & Fail-Closed Redirects
# =====================================================================


def test_asset_document_knowledge_superuser_tenant_none_safe_lists_and_redirects(
    adk_document_a,
    adk_procedure_a,
    adk_certification_a,
    adk_article_a,
    vendor_party_a,
):
    su_client = _asset_document_knowledge_superuser_client()

    # All 5 list/queue pages render 200 OK with 0 tenant records leaked
    for url_name, ctx_key in (
        ("assets:asset_document_list", "documents"),
        ("assets:asset_document_change_list", "documents"),
        ("assets:asset_operating_procedure_list", "procedures"),
        ("assets:asset_operator_certification_list", "certifications"),
        ("assets:asset_knowledge_article_list", "articles"),
    ):
        resp = su_client.get(reverse(url_name))
        assert resp.status_code == 200
        assert len(list(resp.context[ctx_key])) == 0

    # All 4 create GET & POST redirect cleanly to list without creating records
    create_cases = [
        (
            "assets:asset_document_create",
            "assets:asset_document_list",
            _asset_document_knowledge_doc_post_data(title="SU Doc"),
            AssetDocument,
        ),
        (
            "assets:asset_operating_procedure_create",
            "assets:asset_operating_procedure_list",
            _asset_document_knowledge_sop_post_data(title="SU SOP"),
            AssetOperatingProcedure,
        ),
        (
            "assets:asset_operator_certification_create",
            "assets:asset_operator_certification_list",
            _asset_document_knowledge_cert_post_data(operator_party=vendor_party_a, title="SU Cert"),
            AssetOperatorCertification,
        ),
        (
            "assets:asset_knowledge_article_create",
            "assets:asset_knowledge_article_list",
            _asset_document_knowledge_article_post_data(title="SU Article"),
            AssetKnowledgeArticle,
        ),
    ]
    for create_name, list_name, payload, model_cls in create_cases:
        before = model_cls.objects.count()
        get_resp = su_client.get(reverse(create_name))
        assert get_resp.status_code == 302
        assert get_resp["Location"] == reverse(list_name)
        assert "Select a tenant workspace" in " ".join(_asset_document_knowledge_messages(get_resp))

        post_resp = su_client.post(reverse(create_name), data=payload)
        assert post_resp.status_code == 302
        assert post_resp["Location"] == reverse(list_name)
        assert model_cls.objects.count() == before

    # refresh_alerts redirects cleanly for tenant=None superuser
    ref_resp = su_client.post(reverse("assets:asset_operator_certification_refresh_alerts"))
    assert ref_resp.status_code == 302
    assert ref_resp["Location"] == reverse("assets:asset_operator_certification_list")
    assert "Select a tenant workspace" in " ".join(_asset_document_knowledge_messages(ref_resp))


# =====================================================================
# 7. Query-Budget Tests (django_assert_max_num_queries)
# =====================================================================


def test_asset_document_knowledge_sop_print_constant_queries_across_supersedes_depth(
    client_a, tenant_a, admin_user, django_assert_max_num_queries
):
    # Depth 1 SOP
    sop_d1 = _asset_document_knowledge_make_sop(tenant_a, author=admin_user, title="SOP Depth 1")
    # Depth 8 supersedes chain
    prev = sop_d1
    for i in range(2, 9):
        prev = _asset_document_knowledge_make_sop(
            tenant_a, author=admin_user, title=f"SOP Depth {i}", supersedes=prev
        )
    sop_d8 = prev

    # Warm session/auth before capturing query counts
    client_a.get(reverse("assets:asset_operating_procedure_print", args=[sop_d1.pk]))

    with CaptureQueriesContext(connection) as ctx_d1:
        with django_assert_max_num_queries(10):
            r1 = client_a.get(reverse("assets:asset_operating_procedure_print", args=[sop_d1.pk]))
            assert r1.status_code == 200

    with CaptureQueriesContext(connection) as ctx_d8:
        with django_assert_max_num_queries(10):
            r8 = client_a.get(reverse("assets:asset_operating_procedure_print", args=[sop_d8.pk]))
            assert r8.status_code == 200

    assert len(ctx_d8) == len(ctx_d1)


def test_asset_document_knowledge_certification_list_detail_flat_with_employees(
    client_a, tenant_a, django_assert_max_num_queries
):
    certs = []
    for i in range(8):
        party = Party.objects.create(tenant=tenant_a, name=f"Operator Employee {i}", kind="person")
        emp = EmployeeProfile.objects.create(tenant=tenant_a, party=party, employee_type="full_time")
        certs.append(
            _asset_document_knowledge_make_cert(
                tenant_a,
                employee_profile=emp,
                title=f"Emp Cert {i}",
                status="active",
            )
        )

    # Warm session
    client_a.get(reverse("assets:asset_operator_certification_list"))

    with django_assert_max_num_queries(14):
        list_resp = client_a.get(reverse("assets:asset_operator_certification_list"))
        assert list_resp.status_code == 200
        html = list_resp.content.decode()
        assert "Operator Employee 0" in html
        assert "Operator Employee 7" in html

    with django_assert_max_num_queries(10):
        detail_resp = client_a.get(reverse("assets:asset_operator_certification_detail", args=[certs[0].pk]))
        assert detail_resp.status_code == 200
        assert "Operator Employee 0" in detail_resp.content.decode()


def test_asset_document_knowledge_article_detail_and_form_flat_with_incidents(
    client_a, tenant_a, operational_asset_a, location_a, admin_user, django_assert_max_num_queries
):
    incidents = []
    for i in range(8):
        incidents.append(
            AssetIncidentReport.objects.create(
                tenant=tenant_a,
                title=f"Bearing Surge Incident {i}",
                asset=operational_asset_a,
                incident_type="damaged_beyond_repair",
                severity="medium",
                incident_date=timezone.localdate(),
                last_known_location=location_a,
                reported_by=admin_user,
                incident_description="Surge check",
                status="reported",
            )
        )

    art = _asset_document_knowledge_make_article(
        tenant_a,
        author=admin_user,
        incident_report=incidents[0],
        title="KB Linked Incident Article",
    )

    # Warm session
    client_a.get(reverse("assets:asset_knowledge_article_list"))

    with django_assert_max_num_queries(12):
        detail_resp = client_a.get(reverse("assets:asset_knowledge_article_detail", args=[art.pk]))
        assert detail_resp.status_code == 200

    with django_assert_max_num_queries(22):
        form_resp = client_a.get(reverse("assets:asset_knowledge_article_create"))
        assert form_resp.status_code == 200
        assert "Bearing Surge Incident 7" in form_resp.content.decode()


def test_asset_document_knowledge_document_list_single_aggregate_kpis(
    client_a, tenant_a, admin_user, django_assert_max_num_queries
):
    _asset_document_knowledge_make_doc(tenant_a, owner=admin_user, title="KPI Doc Baseline", status="approved")
    # Warm session
    client_a.get(reverse("assets:asset_document_list"))

    with CaptureQueriesContext(connection) as ctx_small:
        with django_assert_max_num_queries(14):
            r1 = client_a.get(reverse("assets:asset_document_list"))
            assert r1.status_code == 200

    for i in range(12):
        _asset_document_knowledge_make_doc(
            tenant_a,
            owner=admin_user,
            title=f"KPI Doc Extra {i}",
            status="in_review" if i % 2 == 0 else "draft",
            expiry_date=timezone.localdate() + timedelta(days=10),
            checked_out_by=admin_user if i % 3 == 0 else None,
        )

    with CaptureQueriesContext(connection) as ctx_many:
        with django_assert_max_num_queries(14):
            r2 = client_a.get(reverse("assets:asset_document_list"))
            assert r2.status_code == 200
            assert r2.context["total_count"] == 13

    assert len(ctx_many) == len(ctx_small)


def test_asset_document_knowledge_refresh_alerts_uses_bulk_update(
    client_a, tenant_a, vendor_party_a, django_assert_max_num_queries
):
    today = timezone.localdate()
    for i in range(2):
        _asset_document_knowledge_make_cert(
            tenant_a,
            operator_party=vendor_party_a,
            title=f"Bulk Refresh Seed {i}",
            status="active",
            expires_on=today - timedelta(days=1),
            renewal_lead_days=30,
        )

    # Warm session
    client_a.get(reverse("assets:asset_operator_certification_list"))

    with CaptureQueriesContext(connection) as ctx_small:
        with django_assert_max_num_queries(14):
            resp_small = client_a.post(reverse("assets:asset_operator_certification_refresh_alerts"))
            assert resp_small.status_code == 302

    for i in range(15):
        _asset_document_knowledge_make_cert(
            tenant_a,
            operator_party=vendor_party_a,
            title=f"Bulk Refresh Cert {i}",
            status="active",
            expires_on=today - timedelta(days=1) if i % 2 == 0 else today + timedelta(days=5),
            renewal_lead_days=30,
        )

    with CaptureQueriesContext(connection) as ctx_many:
        with django_assert_max_num_queries(14):
            resp = client_a.post(reverse("assets:asset_operator_certification_refresh_alerts"))
            assert resp.status_code == 302

    assert len(ctx_many) == len(ctx_small)
    assert AssetOperatorCertification.objects.filter(tenant=tenant_a, status="expired").count() == 10
    assert AssetOperatorCertification.objects.filter(tenant=tenant_a, status="expiring_soon").count() == 7
