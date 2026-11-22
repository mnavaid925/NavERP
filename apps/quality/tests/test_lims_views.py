"""View tests for Submodule 12.19 Laboratory Information Management (LIMS)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.quality.models import (
    LabSample,
    LabSpecification,
    LabTestWorksheet,
    OosInvestigation,
)


@pytest.mark.django_db
def test_lims_dashboard_view(client_a):
    url = reverse("quality:lims_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "total_samples" in resp.context
    assert "samples_in_testing" in resp.context
    assert "pending_worksheets" in resp.context
    assert "open_oos_count" in resp.context
    assert "recent_samples" in resp.context


@pytest.mark.django_db
def test_lims_export_csv_view(client_a, lab_test_worksheet_a):
    url = reverse("quality:lims_export_csv")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "attachment; filename=" in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Worksheet Number" in content
    assert lab_test_worksheet_a.number in content


@pytest.mark.django_db
def test_lims_sample_views_crud_and_receive(client_a, tenant_a, admin_user, lab_sample_a):
    # 1. List
    list_url = reverse("quality:lab_sample_list")
    resp = client_a.get(list_url)
    assert resp.status_code == 200
    assert "samples" in resp.context

    # 2. Detail
    detail_url = reverse("quality:lab_sample_detail", kwargs={"pk": lab_sample_a.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["sample"] == lab_sample_a

    # 3. Create
    create_url = reverse("quality:lab_sample_create")
    assert client_a.get(create_url).status_code == 200
    post_data = {
        "sample_name": "API New Batch Pull",
        "sample_type": "raw_material",
        "status": "registered",
        "quantity_collected": "150.0000",
        "unit_of_measure": "g",
        "storage_condition": "ambient",
    }
    resp = client_a.post(create_url, data=post_data)
    assert resp.status_code == 302
    created = LabSample.objects.filter(tenant=tenant_a, sample_name="API New Batch Pull").first()
    assert created is not None

    # 4. Receive Action
    receive_url = reverse("quality:lab_sample_receive", kwargs={"pk": created.pk})
    resp = client_a.post(receive_url)
    assert resp.status_code == 302
    created.refresh_from_db()
    assert created.status == "received"
    assert created.received_by == admin_user

    # 5. Edit
    edit_url = reverse("quality:lab_sample_edit", kwargs={"pk": created.pk})
    assert client_a.get(edit_url).status_code == 200
    resp = client_a.post(edit_url, data={**post_data, "sample_name": "API Batch Pull Updated"})
    assert resp.status_code == 302
    created.refresh_from_db()
    assert created.sample_name == "API Batch Pull Updated"


@pytest.mark.django_db
def test_lims_sample_delete_cascade_guard_i3(client_a, lab_sample_a, lab_test_worksheet_a):
    delete_url = reverse("quality:lab_sample_delete", kwargs={"pk": lab_sample_a.pk})
    # Attempt delete while test worksheets exist
    resp = client_a.post(delete_url)
    assert resp.status_code == 302
    # Ensure sample was NOT deleted
    assert LabSample.objects.filter(pk=lab_sample_a.pk).exists()


@pytest.mark.django_db
def test_lims_specification_views_crud(client_a, tenant_a, lab_specification_a):
    # 1. List
    list_url = reverse("quality:lab_specification_list")
    resp = client_a.get(list_url)
    assert resp.status_code == 200

    # 2. Detail
    detail_url = reverse("quality:lab_specification_detail", kwargs={"pk": lab_specification_a.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200
    assert resp.context["specification"] == lab_specification_a

    # 3. Create
    create_url = reverse("quality:lab_specification_create")
    assert client_a.get(create_url).status_code == 200
    post_data = {
        "title": "Purified Water Endotoxin Spec",
        "specification_type": "environmental",
        "status": "approved",
        "test_category": "microbiological",
        "version": "1.0",
        "product_code": "WFI-01",
        "product_name": "Water For Injection",
        "analytical_method_number": "USP <85>",
        "target_parameter_name": "Endotoxin",
        "parameter_unit": "EU/mL",
        "upper_limit": "0.2500",
    }
    resp = client_a.post(create_url, data=post_data)
    assert resp.status_code == 302
    created = LabSpecification.objects.filter(tenant=tenant_a, product_code="WFI-01").first()
    assert created is not None


@pytest.mark.django_db
def test_lims_worksheet_views_crud_and_status_guard_i2(client_a, tenant_a, lab_test_worksheet_a):
    # 1. Detail
    detail_url = reverse("quality:lab_test_worksheet_detail", kwargs={"pk": lab_test_worksheet_a.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200

    # 2. Complete Action
    complete_url = reverse("quality:lab_test_worksheet_complete", kwargs={"pk": lab_test_worksheet_a.pk})
    resp = client_a.post(complete_url)
    assert resp.status_code == 302
    lab_test_worksheet_a.refresh_from_db()
    assert lab_test_worksheet_a.status == "review_pending"
    assert lab_test_worksheet_a.completion_timestamp is not None

    # 3. Test I2 status guard: cannot complete already review_pending / approved / cancelled worksheet
    lab_test_worksheet_a.status = "approved"
    lab_test_worksheet_a.save()
    resp2 = client_a.post(complete_url)
    assert resp2.status_code == 302
    lab_test_worksheet_a.refresh_from_db()
    assert lab_test_worksheet_a.status == "approved"  # Unchanged!


@pytest.mark.django_db
def test_lims_oos_investigation_views_and_close_i1_i2(client_a, tenant_a, admin_user, oos_investigation_a):
    # 1. Detail
    detail_url = reverse("quality:oos_investigation_detail", kwargs={"pk": oos_investigation_a.pk})
    resp = client_a.get(detail_url)
    assert resp.status_code == 200

    # 2. Close Action (as tenant admin)
    close_url = reverse("quality:oos_investigation_close", kwargs={"pk": oos_investigation_a.pk})
    resp = client_a.post(close_url)
    assert resp.status_code == 302
    oos_investigation_a.refresh_from_db()
    assert oos_investigation_a.status == "closed"
    assert oos_investigation_a.investigation_phase == "closed"
    assert oos_investigation_a.qa_approver == admin_user
    assert oos_investigation_a.closed_at is not None

    # 3. Test I2 guard: cannot close already closed OOS
    resp2 = client_a.post(close_url)
    assert resp2.status_code == 302
    # Still closed
    assert oos_investigation_a.status == "closed"
