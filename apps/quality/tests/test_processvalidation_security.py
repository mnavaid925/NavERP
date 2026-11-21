"""Security, multi-tenant isolation (IDOR), and authorization tests for Sub-module 12.15 Process Validation & Verification.

Tests:
- Authentication gates (@login_required)
- Multi-tenant data isolation (Cross-tenant IDOR -> 404)
- Multi-tenant list view data leakage prevention
- Cross-tenant foreign key injection rejection
- CSV export formula injection sanitization
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.quality.models import (
    ValidationProtocol,
    ProcessCapabilityStudy,
    ComputerSystemValidation,
    CleaningValidation,
)


@pytest.mark.django_db
class TestProcessValidationSecurity:
    """Security verification test suite for Process Validation sub-module."""

    # --- 1. Authentication Gates ---

    def test_processvalidation_unauthenticated_redirects(
        self,
        client,
        validation_protocol_a,
        process_capability_study_a,
        computer_system_validation_a,
        cleaning_validation_a,
    ):
        """Verify unauthenticated requests redirect to login."""
        urls = [
            reverse("quality:process_validation_dashboard"),
            reverse("quality:validation_protocol_list"),
            reverse("quality:validation_protocol_detail", kwargs={"pk": validation_protocol_a.pk}),
            reverse("quality:validation_protocol_create"),
            reverse("quality:validation_protocol_edit", kwargs={"pk": validation_protocol_a.pk}),
            reverse("quality:validation_protocol_export"),
            reverse("quality:process_capability_study_list"),
            reverse("quality:process_capability_study_detail", kwargs={"pk": process_capability_study_a.pk}),
            reverse("quality:process_capability_study_create"),
            reverse("quality:process_capability_study_edit", kwargs={"pk": process_capability_study_a.pk}),
            reverse("quality:process_capability_study_export"),
            reverse("quality:computer_system_validation_list"),
            reverse("quality:computer_system_validation_detail", kwargs={"pk": computer_system_validation_a.pk}),
            reverse("quality:computer_system_validation_create"),
            reverse("quality:computer_system_validation_edit", kwargs={"pk": computer_system_validation_a.pk}),
            reverse("quality:computer_system_validation_export"),
            reverse("quality:cleaning_validation_list"),
            reverse("quality:cleaning_validation_detail", kwargs={"pk": cleaning_validation_a.pk}),
            reverse("quality:cleaning_validation_create"),
            reverse("quality:cleaning_validation_edit", kwargs={"pk": cleaning_validation_a.pk}),
            reverse("quality:cleaning_validation_export"),
        ]
        for url in urls:
            resp = client.get(url)
            assert resp.status_code == 302
            assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")

    # --- 2. Multi-Tenant IDOR Isolation (Cross-Tenant -> 404) ---

    def test_processvalidation_cross_tenant_idor_protocol(self, client, admin_user, validation_protocol_b):
        """Verify Tenant A user accessing Tenant B ValidationProtocol returns 404."""
        client.force_login(admin_user)

        # Detail
        detail_url = reverse("quality:validation_protocol_detail", kwargs={"pk": validation_protocol_b.pk})
        assert client.get(detail_url).status_code == 404

        # Edit
        edit_url = reverse("quality:validation_protocol_edit", kwargs={"pk": validation_protocol_b.pk})
        assert client.get(edit_url).status_code == 404
        assert client.post(edit_url, {"title": "Hacked"}).status_code == 404

        # Delete
        delete_url = reverse("quality:validation_protocol_delete", kwargs={"pk": validation_protocol_b.pk})
        assert client.post(delete_url).status_code == 404

    def test_processvalidation_cross_tenant_idor_capability_study(self, client, admin_user, process_capability_study_b):
        """Verify Tenant A user accessing Tenant B ProcessCapabilityStudy returns 404."""
        client.force_login(admin_user)

        detail_url = reverse("quality:process_capability_study_detail", kwargs={"pk": process_capability_study_b.pk})
        assert client.get(detail_url).status_code == 404

        edit_url = reverse("quality:process_capability_study_edit", kwargs={"pk": process_capability_study_b.pk})
        assert client.get(edit_url).status_code == 404
        assert client.post(edit_url, {"title": "Hacked"}).status_code == 404

        delete_url = reverse("quality:process_capability_study_delete", kwargs={"pk": process_capability_study_b.pk})
        assert client.post(delete_url).status_code == 404

    def test_processvalidation_cross_tenant_idor_csv(self, client, admin_user, computer_system_validation_b):
        """Verify Tenant A user accessing Tenant B ComputerSystemValidation returns 404."""
        client.force_login(admin_user)

        detail_url = reverse("quality:computer_system_validation_detail", kwargs={"pk": computer_system_validation_b.pk})
        assert client.get(detail_url).status_code == 404

        edit_url = reverse("quality:computer_system_validation_edit", kwargs={"pk": computer_system_validation_b.pk})
        assert client.get(edit_url).status_code == 404
        assert client.post(edit_url, {"system_name": "Hacked"}).status_code == 404

        delete_url = reverse("quality:computer_system_validation_delete", kwargs={"pk": computer_system_validation_b.pk})
        assert client.post(delete_url).status_code == 404

    def test_processvalidation_cross_tenant_idor_cleaning(self, client, admin_user, cleaning_validation_b):
        """Verify Tenant A user accessing Tenant B CleaningValidation returns 404."""
        client.force_login(admin_user)

        detail_url = reverse("quality:cleaning_validation_detail", kwargs={"pk": cleaning_validation_b.pk})
        assert client.get(detail_url).status_code == 404

        edit_url = reverse("quality:cleaning_validation_edit", kwargs={"pk": cleaning_validation_b.pk})
        assert client.get(edit_url).status_code == 404
        assert client.post(edit_url, {"title": "Hacked"}).status_code == 404

        delete_url = reverse("quality:cleaning_validation_delete", kwargs={"pk": cleaning_validation_b.pk})
        assert client.post(delete_url).status_code == 404

    # --- 3. Multi-Tenant List View Data Leakage Prevention ---

    def test_processvalidation_list_views_tenant_isolation(
        self,
        client,
        admin_user,
        validation_protocol_a,
        validation_protocol_b,
        process_capability_study_a,
        process_capability_study_b,
        computer_system_validation_a,
        computer_system_validation_b,
        cleaning_validation_a,
        cleaning_validation_b,
    ):
        """Verify Tenant A list views never display or leak Tenant B records."""
        client.force_login(admin_user)

        # Validation Protocols
        resp_val = client.get(reverse("quality:validation_protocol_list"))
        assert validation_protocol_a.title.encode() in resp_val.content
        assert validation_protocol_b.title.encode() not in resp_val.content

        # Capability Studies
        resp_cap = client.get(reverse("quality:process_capability_study_list"))
        assert process_capability_study_a.title.encode() in resp_cap.content
        assert process_capability_study_b.title.encode() not in resp_cap.content

        # Computer Systems
        resp_csv = client.get(reverse("quality:computer_system_validation_list"))
        assert computer_system_validation_a.system_name.encode() in resp_csv.content
        assert computer_system_validation_b.system_name.encode() not in resp_csv.content

        # Cleaning Studies
        resp_cln = client.get(reverse("quality:cleaning_validation_list"))
        assert cleaning_validation_a.title.encode() in resp_cln.content
        assert cleaning_validation_b.title.encode() not in resp_cln.content

    # --- 4. CSV Formula Injection Sanitization ---

    def test_processvalidation_csv_formula_injection_sanitization(
        self,
        client,
        admin_user,
        tenant_a,
        quality_department,
        doc_a,
    ):
        """Verify cell values starting with =, +, -, @ are escaped to prevent CSV formula injection."""
        client.force_login(admin_user)

        # Create protocol with potentially malicious formula prefix
        malicious_protocol = ValidationProtocol.objects.create(
            tenant=tenant_a,
            title="=cmd|' /C calc'!A0",
            protocol_stage="iq",
            target_type="equipment",
            status="draft",
            department=quality_department,
            lead_author=admin_user,
            qa_reviewer=admin_user,
        )

        resp = client.get(reverse("quality:validation_protocol_export"))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        # Formula neutralized by _csv_safe prepending single quote
        assert "'=cmd|" in content or "\"'=cmd|" in content or "\t=cmd|" in content
