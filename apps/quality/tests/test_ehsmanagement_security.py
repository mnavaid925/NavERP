"""Security, multi-tenant isolation (IDOR), and authorization tests for Sub-module 12.16: Environmental, Health & Safety (EHS).

Tests:
- Authentication gates (@login_required redirect to login)
- Multi-tenant data isolation (Cross-tenant IDOR -> 404 across detail, update, delete, actions)
- HTTP method restrictions (@require_POST -> 405 on GET)
- Administrative authorization gates (regular user deletion restrictions)
- Statutory preservation guards (OSHA recordable incident and active TSDF manifest deletion prevention)
- Audit logging verification on mutating endpoints
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial
from apps.quality.models.EhsManagement.SafetyIncidents import SafetyIncident
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLog
from apps.quality.models.EhsManagement.WasteDisposalManifests import WasteDisposalManifest


# ==============================================================================
# Unauthenticated Access Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_unauthenticated_redirects(client, hazardous_material_a, safety_incident_a, environmental_monitoring_log_a, waste_disposal_manifest_a):
    """Verify unauthenticated requests redirect to login."""
    urls = [
        reverse("quality:ehs_dashboard"),
        reverse("quality:ehs_dashboard_export"),
        reverse("quality:hazardous_material_list"),
        reverse("quality:hazardous_material_create"),
        reverse("quality:hazardous_material_export"),
        reverse("quality:hazardous_material_detail", kwargs={"pk": hazardous_material_a.pk}),
        reverse("quality:hazardous_material_update", kwargs={"pk": hazardous_material_a.pk}),
        reverse("quality:hazardous_material_delete", kwargs={"pk": hazardous_material_a.pk}),
        reverse("quality:hazardous_material_label", kwargs={"pk": hazardous_material_a.pk}),
        reverse("quality:safety_incident_list"),
        reverse("quality:safety_incident_create"),
        reverse("quality:safety_incident_export"),
        reverse("quality:safety_incident_detail", kwargs={"pk": safety_incident_a.pk}),
        reverse("quality:safety_incident_update", kwargs={"pk": safety_incident_a.pk}),
        reverse("quality:safety_incident_delete", kwargs={"pk": safety_incident_a.pk}),
        reverse("quality:safety_incident_investigate", kwargs={"pk": safety_incident_a.pk}),
        reverse("quality:environmental_monitoring_log_list"),
        reverse("quality:environmental_monitoring_log_create"),
        reverse("quality:environmental_monitoring_log_export"),
        reverse("quality:environmental_monitoring_log_detail", kwargs={"pk": environmental_monitoring_log_a.pk}),
        reverse("quality:environmental_monitoring_log_update", kwargs={"pk": environmental_monitoring_log_a.pk}),
        reverse("quality:environmental_monitoring_log_delete", kwargs={"pk": environmental_monitoring_log_a.pk}),
        reverse("quality:environmental_monitoring_log_evaluate", kwargs={"pk": environmental_monitoring_log_a.pk}),
        reverse("quality:waste_disposal_manifest_list"),
        reverse("quality:waste_disposal_manifest_create"),
        reverse("quality:waste_disposal_manifest_export"),
        reverse("quality:waste_disposal_manifest_detail", kwargs={"pk": waste_disposal_manifest_a.pk}),
        reverse("quality:waste_disposal_manifest_update", kwargs={"pk": waste_disposal_manifest_a.pk}),
        reverse("quality:waste_disposal_manifest_delete", kwargs={"pk": waste_disposal_manifest_a.pk}),
        reverse("quality:waste_disposal_manifest_certify", kwargs={"pk": waste_disposal_manifest_a.pk}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 for {url}, got {resp.status_code}"
        assert "/login" in resp.headers.get("Location", "") or "/accounts/login" in resp.headers.get("Location", "")


# ==============================================================================
# Multi-Tenant Isolation (IDOR) Tests
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_cross_tenant_idor_hazardous_material(client_a, hazardous_material_b):
    """Verify Tenant A user accessing Tenant B HazardousMaterial returns 404."""
    assert client_a.get(reverse("quality:hazardous_material_detail", kwargs={"pk": hazardous_material_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:hazardous_material_update", kwargs={"pk": hazardous_material_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:hazardous_material_label", kwargs={"pk": hazardous_material_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:hazardous_material_delete", kwargs={"pk": hazardous_material_b.pk})).status_code == 404


@pytest.mark.django_db
def test_ehsmanagement_cross_tenant_idor_safety_incident(client_a, safety_incident_b):
    """Verify Tenant A user accessing Tenant B SafetyIncident returns 404."""
    assert client_a.get(reverse("quality:safety_incident_detail", kwargs={"pk": safety_incident_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:safety_incident_update", kwargs={"pk": safety_incident_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:safety_incident_delete", kwargs={"pk": safety_incident_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:safety_incident_investigate", kwargs={"pk": safety_incident_b.pk})).status_code == 404


@pytest.mark.django_db
def test_ehsmanagement_cross_tenant_idor_environmental_log(client_a, environmental_monitoring_log_b):
    """Verify Tenant A user accessing Tenant B EnvironmentalMonitoringLog returns 404."""
    assert client_a.get(reverse("quality:environmental_monitoring_log_detail", kwargs={"pk": environmental_monitoring_log_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:environmental_monitoring_log_update", kwargs={"pk": environmental_monitoring_log_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:environmental_monitoring_log_delete", kwargs={"pk": environmental_monitoring_log_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:environmental_monitoring_log_evaluate", kwargs={"pk": environmental_monitoring_log_b.pk})).status_code == 404


@pytest.mark.django_db
def test_ehsmanagement_cross_tenant_idor_waste_manifest(client_a, waste_disposal_manifest_b):
    """Verify Tenant A user accessing Tenant B WasteDisposalManifest returns 404."""
    assert client_a.get(reverse("quality:waste_disposal_manifest_detail", kwargs={"pk": waste_disposal_manifest_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:waste_disposal_manifest_update", kwargs={"pk": waste_disposal_manifest_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:waste_disposal_manifest_delete", kwargs={"pk": waste_disposal_manifest_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:waste_disposal_manifest_certify", kwargs={"pk": waste_disposal_manifest_b.pk})).status_code == 404


# ==============================================================================
# HTTP Method Enforcement (@require_POST -> 405)
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_http_method_guards(client_a, hazardous_material_a, safety_incident_a, environmental_monitoring_log_a, waste_disposal_manifest_a):
    """Verify GET requests to mutating action/delete endpoints are rejected with 405 Method Not Allowed."""
    post_only_urls = [
        reverse("quality:hazardous_material_delete", kwargs={"pk": hazardous_material_a.pk}),
        reverse("quality:safety_incident_delete", kwargs={"pk": safety_incident_a.pk}),
        reverse("quality:safety_incident_investigate", kwargs={"pk": safety_incident_a.pk}),
        reverse("quality:environmental_monitoring_log_delete", kwargs={"pk": environmental_monitoring_log_a.pk}),
        reverse("quality:environmental_monitoring_log_evaluate", kwargs={"pk": environmental_monitoring_log_a.pk}),
        reverse("quality:waste_disposal_manifest_delete", kwargs={"pk": waste_disposal_manifest_a.pk}),
        reverse("quality:waste_disposal_manifest_certify", kwargs={"pk": waste_disposal_manifest_a.pk}),
    ]
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET to {url}, got {resp.status_code}"


# ==============================================================================
# Role-Based Authorization & Deletion Guards
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_regular_user_cannot_delete_safety_incident(member_client, safety_incident_a):
    """Verify non-admin user cannot delete safety incidents (admin-only)."""
    url = reverse("quality:safety_incident_delete", kwargs={"pk": safety_incident_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    assert SafetyIncident.objects.filter(pk=safety_incident_a.pk).exists()


@pytest.mark.django_db
def test_ehsmanagement_regular_user_cannot_delete_waste_manifest(member_client, waste_disposal_manifest_a):
    """Verify non-admin user cannot delete waste disposal manifests (admin-only)."""
    url = reverse("quality:waste_disposal_manifest_delete", kwargs={"pk": waste_disposal_manifest_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    assert WasteDisposalManifest.objects.filter(pk=waste_disposal_manifest_a.pk).exists()


@pytest.mark.django_db
def test_ehsmanagement_regular_user_cannot_delete_excursion_log(member_client, environmental_monitoring_log_a):
    """Verify non-admin user cannot delete environmental excursion logs."""
    environmental_monitoring_log_a.evaluation_status = "action_exceeded"
    environmental_monitoring_log_a.save()

    url = reverse("quality:environmental_monitoring_log_delete", kwargs={"pk": environmental_monitoring_log_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 302
    assert EnvironmentalMonitoringLog.objects.filter(pk=environmental_monitoring_log_a.pk).exists()


@pytest.mark.django_db
def test_ehsmanagement_admin_cannot_delete_active_manifest(client_a, waste_disposal_manifest_a):
    """Verify active TSDF waste disposal manifest cannot be deleted once shipped."""
    waste_disposal_manifest_a.status = "in_transit"
    waste_disposal_manifest_a.save()

    url = reverse("quality:waste_disposal_manifest_delete", kwargs={"pk": waste_disposal_manifest_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert WasteDisposalManifest.objects.filter(pk=waste_disposal_manifest_a.pk).exists()


# ==============================================================================
# Audit Logging Verification
# ==============================================================================


@pytest.mark.django_db
def test_ehsmanagement_audit_logging_on_mutations(client_a, hazardous_material_a):
    """Verify mutating views record entries in core.AuditLog."""
    initial_count = AuditLog.objects.filter(action="update").count()

    url = reverse("quality:hazardous_material_update", kwargs={"pk": hazardous_material_a.pk})
    post_data = {
        "material_name": "Audit Logged Material Name",
        "trade_name": hazardous_material_a.trade_name,
        "physical_state": hazardous_material_a.physical_state,
        "ghs_signal_word": hazardous_material_a.ghs_signal_word,
        "nfpa_health": 1,
        "nfpa_flammability": 2,
        "nfpa_instability": 0,
        "nfpa_special_hazard": "none",
        "maximum_storage_quantity": "500.00",
        "quantity_uom": "L",
        "supplier": str(hazardous_material_a.supplier.pk),
        "org_unit": str(hazardous_material_a.org_unit.pk),
        "managed_by": str(hazardous_material_a.managed_by.pk),
        "status": "active",
    }
    client_a.post(url, post_data)

    new_count = AuditLog.objects.filter(action="update").count()
    assert new_count > initial_count
