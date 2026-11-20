"""Unit tests for Sub-module 12.13: Customer Complaint Handling Forms."""
from datetime import timedelta
import pytest
from django.utils import timezone

from apps.quality.forms.CustomerComplaints.CustomerComplaints import (
    CustomerComplaintForm,
    ComplaintTriageForm,
)
from apps.quality.forms.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigationForm
from apps.quality.forms.CustomerComplaints.RegulatoryReports import RegulatoryReportForm
from apps.quality.forms.CustomerComplaints.FieldActions import FieldActionForm


@pytest.mark.django_db
def test_customercomplaints_complaint_form_valid(tenant_a, customer_party_a, admin_user):
    today = timezone.now().date()
    data = {
        "title": "Loose Luer Lock Fitting",
        "intake_channel": "email",
        "customer": customer_party_a.pk,
        "complainant_name": "Clinic Nurse Sarah",
        "item_code": "SYR-20ML",
        "item_name": "Standard Syringe 20mL",
        "date_received": today - timedelta(days=1),
        "problem_description": "Fittings exhibited thread play resulting in slow priming leakage.",
        "severity": "minor_cosmetic",
        "validity": "valid_complaint",
        "reportability": "exempt",
        "sample_return_status": "not_requested",
        "investigation_required": True,
        "assigned_to": admin_user.pk,
    }
    form = CustomerComplaintForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk is not None
    assert obj.status == "intake_received"


@pytest.mark.django_db
def test_customercomplaints_complaint_form_temporal_validation(tenant_a, customer_party_a):
    today = timezone.now().date()
    # Future date_received
    data = {
        "title": "Future Event Complaint",
        "intake_channel": "phone",
        "customer": customer_party_a.pk,
        "date_received": today + timedelta(days=2),
        "problem_description": "Test description",
    }
    form = CustomerComplaintForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "date_received" in form.errors

    # Occurrence after received
    data["date_received"] = today - timedelta(days=2)
    data["date_of_occurrence"] = today - timedelta(days=1)
    form = CustomerComplaintForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "date_of_occurrence" in form.errors


@pytest.mark.django_db
def test_customercomplaints_complaint_form_justifications_required(tenant_a, customer_party_a):
    today = timezone.now().date()
    # Non-reportable without justification
    data = {
        "title": "Unjustified Non-Reportable",
        "intake_channel": "phone",
        "customer": customer_party_a.pk,
        "date_received": today,
        "problem_description": "Testing justification validation",
        "reportability": "non_reportable",
        "non_reportable_justification": "",
    }
    form = CustomerComplaintForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "non_reportable_justification" in form.errors

    # No investigation without rationale
    data["reportability"] = "exempt"
    data["investigation_required"] = False
    data["no_investigation_rationale"] = ""
    form = CustomerComplaintForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "no_investigation_rationale" in form.errors


@pytest.mark.django_db
def test_customercomplaints_triage_form_valid(tenant_a, customer_complaint_a, admin_user):
    data = {
        "validity": "valid_complaint",
        "severity": "critical_safety",
        "reportability": "reportable_event",
        "complaint_category": "Electronics Failure",
        "investigation_required": True,
        "assigned_to": admin_user.pk,
        "triage_notes": "Immediate safety triage completed.",
    }
    form = ComplaintTriageForm(data=data, instance=customer_complaint_a, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_customercomplaints_investigation_form_capa_requirement(tenant_a, customer_complaint_a, admin_user):
    today = timezone.now().date()
    data = {
        "complaint": customer_complaint_a.pk,
        "lead_investigator": admin_user.pk,
        "target_completion_date": today + timedelta(days=7),
        "analytical_method": "electrical_functional",
        "dhr_quantity_produced": 500,
        "root_cause_category": "component_defect",
        "capa_required": True,
        "investigation_conclusion": "",  # Empty conclusion without linked CAPA/NCR
    }
    form = ComplaintInvestigationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "investigation_conclusion" in form.errors

    data["investigation_conclusion"] = "Escalated to engineering CAPA-2026-09."
    form = ComplaintInvestigationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_customercomplaints_investigation_form_immutable_complaint_on_edit(tenant_a, complaint_investigation_a, customer_complaint_b):
    """Parent complaint cannot be reassigned during investigation edit."""
    form = ComplaintInvestigationForm(
        data={
            "complaint": customer_complaint_b.pk,
            "lead_investigator": complaint_investigation_a.lead_investigator.pk,
            "target_completion_date": timezone.now().date(),
            "analytical_method": "chemical_spectroscopy",
            "dhr_quantity_produced": 200,
            "root_cause_category": "design_flaw",
        },
        instance=complaint_investigation_a,
        tenant=tenant_a,
    )
    # Disabled fields are preserved by clean_complaint
    assert form.fields["complaint"].disabled is True
    assert form.is_valid(), form.errors
    assert form.cleaned_data["complaint"] == complaint_investigation_a.complaint


@pytest.mark.django_db
def test_customercomplaints_regulatory_report_form_statutory_due_date_mandated(tenant_a, customer_complaint_a, admin_user):
    data = {
        "complaint": customer_complaint_a.pk,
        "agency": "fda_cdrh",
        "report_type": "initial_report",
        "timeline_category": "30_day_standard_mdr",
        "statutory_due_date": "",  # Missing due date
        "event_summary": "Medical adverse event narrative",
        "prepared_by": admin_user.pk,
    }
    form = RegulatoryReportForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "statutory_due_date" in form.errors


@pytest.mark.django_db
def test_customercomplaints_field_action_form_valid(tenant_a, customer_complaint_a, admin_user):
    today = timezone.now().date()
    data = {
        "title": "Class I Voluntary Device Recall",
        "action_type": "recall_removal",
        "recall_class": "class_i_critical",
        "initiating_complaint": customer_complaint_a.pk,
        "coordinator": admin_user.pk,
        "initiation_date": today,
        "affected_product_code": "PUMP-4000",
        "affected_product_name": "Infusion Pro Plus",
        "affected_lot_numbers": "LOT-2026-X1, LOT-2026-X2",
        "reason_for_action": "Potential firmware lockout leading to unintended infusion rate.",
        "total_units_distributed": 100,
        "consignees_targeted": 50,
        "consignees_notified": 45,
        "consignees_responded": 40,
        "units_quarantined_field": 10,
        "units_recovered_destroyed": 5,
    }
    form = FieldActionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_customercomplaints_field_action_form_reconciliation_exceeded(tenant_a, customer_complaint_a, admin_user):
    today = timezone.now().date()
    data = {
        "title": "Class I Voluntary Device Recall",
        "action_type": "recall_removal",
        "recall_class": "class_i_critical",
        "initiating_complaint": customer_complaint_a.pk,
        "coordinator": admin_user.pk,
        "initiation_date": today,
        "affected_product_code": "PUMP-4000",
        "affected_product_name": "Infusion Pro Plus",
        "affected_lot_numbers": "LOT-2026-X1",
        "reason_for_action": "Testing reconciliation bounds",
        "total_units_distributed": 50,
        "consignees_targeted": 10,
        "consignees_notified": 10,
        "units_quarantined_field": 40,
        "units_recovered_destroyed": 20,  # 40 + 20 = 60 > 50
    }
    form = FieldActionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "units_recovered_destroyed" in form.errors
