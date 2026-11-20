"""Unit tests for Sub-module 12.13: Customer Complaint Handling Models."""
from datetime import timedelta
import pytest
from django.db import models
from django.utils import timezone

from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigation
from apps.quality.models.CustomerComplaints.RegulatoryReports import RegulatoryReport
from apps.quality.models.CustomerComplaints.FieldActions import FieldAction


@pytest.mark.django_db
def test_customercomplaints_complaint_creation_and_autonumber(tenant_a, customer_party_a, admin_user):
    today = timezone.now().date()
    complaint = CustomerComplaint.objects.create(
        tenant=tenant_a,
        title="Syringe Plunger Binding During Manual Injection",
        customer=customer_party_a,
        complainant_name="Nurse Practitioner Davis",
        item_code="SYR-50ML-01",
        item_name="Precision Syringe 50mL Luer-Lock",
        date_received=today - timedelta(days=2),
        problem_description="Plunger required excessive manual force causing medication push delay.",
        severity="minor_cosmetic",
        assigned_to=admin_user,
    )
    assert complaint.pk is not None
    assert complaint.number.startswith("QCMP-")
    assert str(complaint) == f"{complaint.number} - Syringe Plunger Binding During Manual Injection"
    assert complaint.status == "intake_received"
    assert complaint.days_open == 2
    assert complaint.has_active_regulatory_report is False


@pytest.mark.django_db
def test_customercomplaints_complaint_days_open_when_closed(customer_complaint_a, admin_user):
    today = timezone.now().date()
    customer_complaint_a.status = "closed"
    customer_complaint_a.closed_by = admin_user
    customer_complaint_a.closed_at = timezone.now() - timedelta(days=1)
    customer_complaint_a.save()

    # Closed at yesterday - date_received 5 days ago = 4 days
    assert customer_complaint_a.days_open == 4


@pytest.mark.django_db
def test_customercomplaints_investigation_properties_and_str(complaint_investigation_a):
    assert complaint_investigation_a.number.startswith("QCIN-")
    assert str(complaint_investigation_a) == f"{complaint_investigation_a.number} - Complaint Investigation"
    assert complaint_investigation_a.is_overdue is False

    # Test overdue calculation
    complaint_investigation_a.target_completion_date = timezone.now().date() - timedelta(days=2)
    assert complaint_investigation_a.is_overdue is True

    # Approved investigations are never overdue
    complaint_investigation_a.status = "approved"
    assert complaint_investigation_a.is_overdue is False


@pytest.mark.django_db
def test_customercomplaints_regulatory_report_properties_and_str(regulatory_report_a):
    assert regulatory_report_a.number.startswith("QRPT-")
    assert "FDA CDRH" in str(regulatory_report_a)
    assert regulatory_report_a.days_until_due == 25
    assert regulatory_report_a.is_overdue is False
    assert regulatory_report_a.urgency_badge_css == "badge-info"

    # Test overdue urgency (< 0 days)
    regulatory_report_a.statutory_due_date = timezone.now().date() - timedelta(days=1)
    assert regulatory_report_a.is_overdue is True
    assert regulatory_report_a.urgency_badge_css == "badge-red"

    # Test critical urgency (<= 3 days)
    regulatory_report_a.statutory_due_date = timezone.now().date() + timedelta(days=2)
    assert regulatory_report_a.urgency_badge_css == "badge-red"

    # Test near deadline urgency (4 to 7 days)
    regulatory_report_a.statutory_due_date = timezone.now().date() + timedelta(days=5)
    assert regulatory_report_a.urgency_badge_css == "badge-amber"


@pytest.mark.django_db
def test_customercomplaints_field_action_reconciliation_rates(field_action_a):
    assert field_action_a.number.startswith("QFMA-")
    assert str(field_action_a) == f"{field_action_a.number} - Class II Recall: Infusion Pro Plus 4000 Display PCB"

    # (120 quarantined + 185 recovered) / 500 = 305 / 500 = 61%
    assert field_action_a.reconciliation_rate == 61

    # 38 responded / 45 notified = 84%
    assert field_action_a.consignee_response_rate == 84

    # Test closed state
    field_action_a.status = "closed_terminated"
    assert field_action_a.status == "closed_terminated"


@pytest.mark.django_db
def test_customercomplaints_protect_fk_on_cascade_delete(customer_complaint_a, complaint_investigation_a, regulatory_report_a):
    """Statutory vigilance reports and investigations are protected from deletion cascade."""
    with pytest.raises(models.ProtectedError):
        customer_complaint_a.delete()
