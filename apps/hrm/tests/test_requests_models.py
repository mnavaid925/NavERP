"""Tests for HRM 3.26 Request Management (Self-Service) models: ``DocumentRequest`` [DOCREQ-],
``IdCardRequest`` [IDREQ-], ``AssetRequest`` [ASSETREQ-] — auto-number prefixes, ``__str__``,
default ``status='draft'``, ``OPEN_STATUSES``, the ``(tenant, employee, status)`` index,
``unique_together (tenant, number)``, ``DocumentRequest.copies``' ``MinValueValidator(1)``, and that
each Meta/CRUD form excludes the workflow-owned/system fields. Mirrors test_selfservice_models.py
conventions."""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ DocumentRequest
class TestDocumentRequestModel:
    def test_number_prefix_docreq(self, document_request_a):
        assert document_request_a.number.startswith("DOCREQ-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import DocumentRequest
        d1 = DocumentRequest.objects.create(tenant=tenant_a, employee=employee_a, purpose="A letter")
        d2 = DocumentRequest.objects.create(tenant=tenant_a, employee=employee_a2, purpose="B letter")
        assert d1.number != d2.number
        assert d1.number.startswith("DOCREQ-")
        assert d2.number.startswith("DOCREQ-")

    def test_unique_together_tenant_number(self, tenant_a, document_request_a):
        from apps.hrm.models import DocumentRequest
        with pytest.raises(IntegrityError):
            DocumentRequest.objects.create(
                tenant=tenant_a, number=document_request_a.number, employee=document_request_a.employee,
                purpose="dup")

    def test_default_status_draft(self, document_request_a):
        assert document_request_a.status == "draft"

    def test_default_document_type_experience_letter(self, document_request_a):
        assert document_request_a.document_type == "experience_letter"

    def test_default_delivery_method_soft_copy(self, document_request_a):
        assert document_request_a.delivery_method == "soft_copy"

    def test_default_copies_is_one(self, document_request_a):
        assert document_request_a.copies == 1

    def test_open_statuses(self):
        from apps.hrm.models import DocumentRequest
        assert DocumentRequest.OPEN_STATUSES == ("draft", "pending")

    def test_status_choices_include_fulfilled_tail_state(self):
        from apps.hrm.models import DocumentRequest
        values = [v for v, _ in DocumentRequest.STATUS_CHOICES]
        assert values == ["draft", "pending", "approved", "rejected", "cancelled", "fulfilled"]

    def test_default_approver_and_approved_at_none(self, document_request_a):
        assert document_request_a.approver_id is None
        assert document_request_a.approved_at is None

    def test_default_fulfilled_at_and_output_file_blank(self, document_request_a):
        assert document_request_a.fulfilled_at is None
        assert not document_request_a.output_file

    def test_str_contains_number_employee_and_type(self, document_request_a):
        s = str(document_request_a)
        assert document_request_a.number in s
        assert "Alice Smith" in s

    def test_str_falls_back_to_document_type_display_when_no_number(self, tenant_a, employee_a):
        from apps.hrm.models import DocumentRequest
        dr = DocumentRequest(tenant=tenant_a, employee=employee_a, document_type="salary_certificate")
        assert str(dr) == "Salary Certificate"

    def test_tenant_scoping(self, document_request_a, tenant_a):
        assert document_request_a.tenant_id == tenant_a.pk

    def test_copies_min_value_validator_rejects_zero(self, tenant_a, employee_a):
        from apps.hrm.models import DocumentRequest
        dr = DocumentRequest(tenant=tenant_a, employee=employee_a, purpose="Needed", copies=0)
        with pytest.raises(ValidationError) as exc:
            dr.full_clean(exclude=["number"])
        assert "copies" in exc.value.message_dict

    def test_copies_min_value_validator_accepts_one(self, tenant_a, employee_a):
        from apps.hrm.models import DocumentRequest
        dr = DocumentRequest(tenant=tenant_a, employee=employee_a, purpose="Needed", copies=1)
        dr.full_clean(exclude=["number"])  # must not raise

    def test_tenant_employee_status_index_exists(self):
        from apps.hrm.models import DocumentRequest
        idx_fields = [tuple(idx.fields) for idx in DocumentRequest._meta.indexes]
        assert ("tenant", "employee", "status") in idx_fields

    def test_tenant_status_index_exists(self):
        from apps.hrm.models import DocumentRequest
        idx_fields = [tuple(idx.fields) for idx in DocumentRequest._meta.indexes]
        assert ("tenant", "status") in idx_fields


# ================================================================ IdCardRequest
class TestIdCardRequestModel:
    def test_number_prefix_idreq(self, idcard_request_a):
        assert idcard_request_a.number.startswith("IDREQ-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import IdCardRequest
        i1 = IdCardRequest.objects.create(tenant=tenant_a, employee=employee_a, reason="A")
        i2 = IdCardRequest.objects.create(tenant=tenant_a, employee=employee_a2, reason="B")
        assert i1.number != i2.number
        assert i1.number.startswith("IDREQ-")
        assert i2.number.startswith("IDREQ-")

    def test_unique_together_tenant_number(self, tenant_a, idcard_request_a):
        from apps.hrm.models import IdCardRequest
        with pytest.raises(IntegrityError):
            IdCardRequest.objects.create(
                tenant=tenant_a, number=idcard_request_a.number, employee=idcard_request_a.employee,
                reason="dup")

    def test_default_status_draft(self, idcard_request_a):
        assert idcard_request_a.status == "draft"

    def test_default_request_type_new(self, idcard_request_a):
        assert idcard_request_a.request_type == "new"

    def test_default_reason_type_first_issue(self, idcard_request_a):
        assert idcard_request_a.reason_type == "first_issue"

    def test_open_statuses(self):
        from apps.hrm.models import IdCardRequest
        assert IdCardRequest.OPEN_STATUSES == ("draft", "pending")

    def test_status_choices_include_issued_tail_state(self):
        from apps.hrm.models import IdCardRequest
        values = [v for v, _ in IdCardRequest.STATUS_CHOICES]
        assert values == ["draft", "pending", "approved", "rejected", "cancelled", "issued"]

    def test_default_card_number_blank_and_issued_at_none(self, idcard_request_a):
        assert idcard_request_a.card_number == ""
        assert idcard_request_a.issued_at is None

    def test_str_contains_number_employee_and_type(self, idcard_request_a):
        s = str(idcard_request_a)
        assert idcard_request_a.number in s
        assert "Alice Smith" in s

    def test_str_falls_back_to_request_type_display_when_no_number(self, tenant_a, employee_a):
        from apps.hrm.models import IdCardRequest
        ir = IdCardRequest(tenant=tenant_a, employee=employee_a, request_type="renewal")
        assert str(ir) == "Renewal"

    def test_tenant_scoping(self, idcard_request_a, tenant_a):
        assert idcard_request_a.tenant_id == tenant_a.pk

    def test_tenant_employee_status_index_exists(self):
        from apps.hrm.models import IdCardRequest
        idx_fields = [tuple(idx.fields) for idx in IdCardRequest._meta.indexes]
        assert ("tenant", "employee", "status") in idx_fields

    def test_tenant_status_index_exists(self):
        from apps.hrm.models import IdCardRequest
        idx_fields = [tuple(idx.fields) for idx in IdCardRequest._meta.indexes]
        assert ("tenant", "status") in idx_fields


# ================================================================ AssetRequest
class TestAssetRequestModel:
    def test_number_prefix_assetreq(self, asset_request_a):
        assert asset_request_a.number.startswith("ASSETREQ-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import AssetRequest
        a1 = AssetRequest.objects.create(tenant=tenant_a, employee=employee_a, asset_name="A", justification="x")
        a2 = AssetRequest.objects.create(tenant=tenant_a, employee=employee_a2, asset_name="B", justification="y")
        assert a1.number != a2.number
        assert a1.number.startswith("ASSETREQ-")
        assert a2.number.startswith("ASSETREQ-")

    def test_unique_together_tenant_number(self, tenant_a, asset_request_a):
        from apps.hrm.models import AssetRequest
        with pytest.raises(IntegrityError):
            AssetRequest.objects.create(
                tenant=tenant_a, number=asset_request_a.number, employee=asset_request_a.employee,
                asset_name="dup", justification="dup")

    def test_default_status_draft(self, asset_request_a):
        assert asset_request_a.status == "draft"

    def test_default_asset_category_other(self, tenant_a, employee_a):
        from apps.hrm.models import AssetRequest
        ar = AssetRequest.objects.create(tenant=tenant_a, employee=employee_a, asset_name="Widget", justification="x")
        assert ar.asset_category == "other"

    def test_default_priority_normal(self, asset_request_a):
        assert asset_request_a.priority == "normal"

    def test_open_statuses(self):
        from apps.hrm.models import AssetRequest
        assert AssetRequest.OPEN_STATUSES == ("draft", "pending")

    def test_status_choices_include_fulfilled_tail_state(self):
        from apps.hrm.models import AssetRequest
        values = [v for v, _ in AssetRequest.STATUS_CHOICES]
        assert values == ["draft", "pending", "approved", "rejected", "cancelled", "fulfilled"]

    def test_default_allocation_none(self, asset_request_a):
        assert asset_request_a.allocation_id is None

    def test_asset_category_choices_reuse_asset_allocation_verbatim(self):
        from apps.hrm.models import AssetAllocation, AssetRequest
        field = AssetRequest._meta.get_field("asset_category")
        assert list(field.choices) == list(AssetAllocation.ASSET_CATEGORY_CHOICES)

    def test_str_contains_number_employee_and_asset_name(self, asset_request_a):
        s = str(asset_request_a)
        assert asset_request_a.number in s
        assert "Alice Smith" in s
        assert "Dell XPS 13" in s

    def test_str_falls_back_to_asset_name_when_no_number(self, tenant_a, employee_a):
        from apps.hrm.models import AssetRequest
        ar = AssetRequest(tenant=tenant_a, employee=employee_a, asset_name="Standing Desk")
        assert str(ar) == "Standing Desk"

    def test_tenant_scoping(self, asset_request_a, tenant_a):
        assert asset_request_a.tenant_id == tenant_a.pk

    def test_tenant_employee_status_index_exists(self):
        from apps.hrm.models import AssetRequest
        idx_fields = [tuple(idx.fields) for idx in AssetRequest._meta.indexes]
        assert ("tenant", "employee", "status") in idx_fields

    def test_tenant_status_index_exists(self):
        from apps.hrm.models import AssetRequest
        idx_fields = [tuple(idx.fields) for idx in AssetRequest._meta.indexes]
        assert ("tenant", "status") in idx_fields


# ================================================================ Forms exclude workflow/system fields
class TestDocumentRequestFormFields:
    def test_form_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import DocumentRequestForm
        fields = DocumentRequestForm(tenant=None).fields
        for excluded in ("tenant", "employee", "number", "status", "approver", "approved_at",
                         "decision_note", "fulfilled_at", "output_file"):
            assert excluded not in fields

    def test_form_declares_the_employee_editable_subset(self):
        from apps.hrm.forms import DocumentRequestForm
        fields = DocumentRequestForm(tenant=None).fields
        for included in ("document_type", "purpose", "addressed_to", "copies", "delivery_method", "needed_by"):
            assert included in fields


class TestIdCardRequestFormFields:
    def test_form_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import IdCardRequestForm
        fields = IdCardRequestForm(tenant=None).fields
        for excluded in ("tenant", "employee", "number", "status", "approver", "approved_at",
                         "decision_note", "card_number", "issued_at"):
            assert excluded not in fields

    def test_form_declares_the_employee_editable_subset(self):
        from apps.hrm.forms import IdCardRequestForm
        fields = IdCardRequestForm(tenant=None).fields
        for included in ("request_type", "reason_type", "reason", "delivery_location"):
            assert included in fields


class TestAssetRequestFormFields:
    def test_form_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import AssetRequestForm
        fields = AssetRequestForm(tenant=None).fields
        for excluded in ("tenant", "employee", "number", "status", "approver", "approved_at",
                         "decision_note", "allocation"):
            assert excluded not in fields

    def test_form_declares_the_employee_editable_subset(self):
        from apps.hrm.forms import AssetRequestForm
        fields = AssetRequestForm(tenant=None).fields
        for included in ("asset_category", "asset_name", "justification", "priority", "needed_by"):
            assert included in fields


class TestDocumentFulfillFormFields:
    def test_output_file_optional(self):
        from apps.hrm.forms import DocumentFulfillForm
        form = DocumentFulfillForm({})
        assert form.is_valid() is True, form.errors
