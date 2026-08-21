"""Procurement 6.1 - form boundary.

A narrowed ``<select>`` is UX, not an authorization boundary: every tenant-scoped FK these forms
render must re-check the crafted-POST case as a FIELD ERROR, and the quick-requisition decimals
must refuse values the scm columns could never store before the driver turns them into a 500.
"""
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.procurement.forms import (ProcurementAlertForm, QuickRequisitionForm,
                                    WidgetToggleForm)
from apps.procurement.models import WidgetPreference

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ ProcurementAlertForm


class TestAlertFormContract:
    def test_status_and_stamps_are_never_form_fields(self):
        """Status advances through acknowledge/resolve verbs only - it cannot be typed."""
        fields = set(ProcurementAlertForm().fields)
        assert "status" not in fields
        for stamp in ("created_by", "acknowledged_by", "acknowledged_at",
                      "resolved_by", "resolved_at", "raised_at"):
            assert stamp not in fields

    def test_create_valid_alert(self, tenant_a, admin_user):
        form = ProcurementAlertForm(
            {"kind": "task", "severity": "info", "title": "Chase quote",
             "message": "", "link_url": "/scm/requisitions/", "due_at": "",
             "assigned_to": admin_user.pk},
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        # The FORM does not stamp tenant - that is the view's job (crud_create parity).
        assert obj.tenant_id is None
        obj.tenant = tenant_a
        obj.save()
        assert obj.kind == "task"


class TestAlertFormScoping:
    def test_assigned_to_queryset_is_tenant_scoped(self, tenant_a, tenant_b,
                                                   admin_user, admin_b):
        form = ProcurementAlertForm(tenant=tenant_a)
        pks = set(form.fields["assigned_to"].queryset.values_list("pk", flat=True))
        assert admin_user.pk in pks
        assert admin_b.pk not in pks

    def test_crafted_foreign_assignee_is_a_field_error(self, tenant_a, admin_b):
        """Hand-posting another workspace's user pk must render an error, not silently pass.

        The scoped queryset rejects it first ("valid choice"); _reject_foreign is the
        second layer underneath for any path that widens the queryset.
        """
        form = ProcurementAlertForm(
            {"kind": "task", "severity": "info", "title": "x", "message": "",
             "link_url": "", "due_at": "", "assigned_to": admin_b.pk},
            tenant=tenant_a)
        assert not form.is_valid()
        assert "assigned_to" in form.errors

    def test_off_site_link_renders_as_field_error(self, tenant_a):
        form = ProcurementAlertForm(
            {"kind": "task", "severity": "info", "title": "x", "message": "",
             "link_url": "https://evil.com", "due_at": "", "assigned_to": ""},
            tenant=tenant_a)
        assert not form.is_valid()
        assert "link_url" in form.errors


# ------------------------------------------------------------------ QuickRequisitionForm


class TestQuickRequisitionForm:
    def _data(self, **overrides):
        data = {"title": "Printer paper - monthly", "item_description": "A4 80gsm box",
                "quantity": "2", "estimated_unit_price": "24.90", "uom_hint": "box",
                "sku_hint": "", "currency": "", "gl_account": "", "org_unit": "",
                "required_by": "", "justification": ""}
        data.update(overrides)
        return {k: v for k, v in data.items() if v is not None}

    def test_requires_title_and_description(self, tenant_a):
        form = QuickRequisitionForm({"quantity": "1"}, tenant=tenant_a)
        assert not form.is_valid()
        assert "title" in form.errors and "item_description" in form.errors

    def test_happy_path_minimal(self, gl_expense_a, org_unit_a, usd, tenant_a):
        form = QuickRequisitionForm(self._data(
            gl_account=str(gl_expense_a.pk), org_unit=str(org_unit_a.pk),
            currency=str(usd.pk)), tenant=tenant_a)
        assert form.is_valid(), form.errors
        cleaned = form.cleaned_data
        assert cleaned["quantity"] == Decimal("2")
        # The view derives estimated_total from these; the form never sees a total at all.

    def test_quantity_column_ceiling_cr5(self, tenant_a):
        """Decimal(14,4) column: 10^11 integer digits cannot be stored - refuse at the form."""
        form = QuickRequisitionForm(self._data(quantity="100000000000"), tenant=tenant_a)
        assert not form.is_valid()
        assert "quantity" in form.errors

    def test_quantity_zero_rejected(self, tenant_a):
        form = QuickRequisitionForm(self._data(quantity="0"), tenant=tenant_a)
        assert not form.is_valid()

    def test_unit_price_negative_and_oversized_rejected(self, tenant_a):
        assert not QuickRequisitionForm(
            self._data(estimated_unit_price="-1"), tenant=tenant_a).is_valid()
        assert not QuickRequisitionForm(
            self._data(estimated_unit_price="1000000000000000"), tenant=tenant_a).is_valid()

    def test_querysets_empty_without_tenant(self, db, gl_expense_a):
        """No tenant means no choices - a superuser cannot pick another workspace's rows."""
        form = QuickRequisitionForm(tenant=None)
        assert form.fields["gl_account"].queryset.count() == 0
        assert form.fields["org_unit"].queryset.count() == 0

    def test_gl_accounts_scoped_and_active_only(self, tenant_a, gl_expense_a, db):
        from apps.accounting.models import GLAccount
        inactive = GLAccount.objects.create(tenant=tenant_a, code="5999",
                                            name="Closed Account",
                                            account_type="expense", is_active=False)
        form = QuickRequisitionForm(tenant=tenant_a)
        qs = form.fields["gl_account"].queryset
        assert gl_expense_a in qs and inactive not in qs

    def test_crafted_foreign_gl_account_error(self, tenant_a, gl_expense_b):
        form = QuickRequisitionForm(self._data(gl_account=str(gl_expense_b.pk)),
                                    tenant=tenant_a)
        assert not form.is_valid()
        assert "gl_account" in form.errors

    def test_crafted_foreign_org_unit_error(self, tenant_a, org_unit_b):
        form = QuickRequisitionForm(self._data(org_unit=str(org_unit_b.pk)),
                                    tenant=tenant_a)
        assert not form.is_valid()
        assert "org_unit" in form.errors


# ------------------------------------------------------------------ WidgetToggleForm


class TestWidgetToggleForm:
    def test_valid_subset(self):
        form = WidgetToggleForm({"widgets": ["approvals", "spend"]})
        assert form.is_valid(), form.errors
        assert set(form.cleaned_data["widgets"]) == {"approvals", "spend"}

    def test_empty_means_hide_everything(self):
        form = WidgetToggleForm({})
        assert form.is_valid()
        assert form.cleaned_data["widgets"] == []

    def test_unknown_key_rejected(self):
        form = WidgetToggleForm({"widgets": ["approvals", "nonsense"]})
        assert not form.is_valid()
        assert "widgets" in form.errors

    def test_choices_come_from_the_model_registry(self):
        """The form can never offer a key the model does not know."""
        assert [value for value, _ in WidgetToggleForm().fields["widgets"].choices] == \
            list(WidgetPreference.WIDGETS)

    def test_initial_visible_kwarg(self):
        form = WidgetToggleForm(initial_visible=["alerts"])
        assert form.fields["widgets"].initial == ["alerts"]
