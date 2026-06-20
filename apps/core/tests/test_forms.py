"""Tests for core forms: required fields, exclusions, tenant scoping."""
import pytest

from apps.core.forms import (
    ActivityForm,
    AddressForm,
    ContactMethodForm,
    EmploymentForm,
    OrgUnitForm,
    PartyForm,
    PartyRelationshipForm,
    PartyRoleForm,
)

pytestmark = pytest.mark.django_db


class TestPartyForm:
    def test_valid_form(self, tenant_a):
        form = PartyForm({"kind": "person", "name": "John Doe", "tax_id": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        form = PartyForm({"kind": "person", "name": "", "tax_id": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        form = PartyForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_created_at_not_a_form_field(self, tenant_a):
        form = PartyForm(tenant=tenant_a)
        assert "created_at" not in form.fields


class TestOrgUnitForm:
    def test_valid_form(self, tenant_a):
        form = OrgUnitForm({"kind": "department", "name": "Engineering", "parent": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        form = OrgUnitForm({"kind": "department", "name": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        form = OrgUnitForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestAddressForm:
    def test_valid_form(self, tenant_a, party_a):
        form = AddressForm({
            "party": party_a.pk,
            "kind": "billing",
            "line1": "123 Main St",
            "city": "Springfield",
            "country": "US",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_line1_required(self, tenant_a, party_a):
        form = AddressForm({
            "party": party_a.pk,
            "kind": "billing",
            "line1": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "line1" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        form = AddressForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestContactMethodForm:
    def test_valid_form(self, tenant_a, party_a):
        form = ContactMethodForm({
            "party": party_a.pk,
            "kind": "email",
            "value": "test@example.com",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_value_required(self, tenant_a, party_a):
        form = ContactMethodForm({
            "party": party_a.pk,
            "kind": "email",
            "value": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "value" in form.errors


class TestActivityForm:
    def test_valid_form(self, tenant_a, admin_user):
        form = ActivityForm({
            "owner": admin_user.pk,
            "party": "",
            "kind": "task",
            "subject": "Test task",
            "status": "open",
            "due_at": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_subject_required(self, tenant_a):
        form = ActivityForm({
            "kind": "task",
            "subject": "",
            "status": "open",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "subject" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        form = ActivityForm(tenant=tenant_a)
        assert "tenant" not in form.fields


class TestPartyRoleForm:
    def test_valid_form(self, tenant_a, party_a):
        form = PartyRoleForm({
            "party": party_a.pk,
            "role": "customer",
            "status": "active",
            "start_date": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_role_required(self, tenant_a, party_a):
        form = PartyRoleForm({
            "party": party_a.pk,
            "role": "",
            "status": "active",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "role" in form.errors

    def test_tenant_scopes_party_choices(self, tenant_a, tenant_b, party_a, party_b):
        """Form scoped to tenant_a must not list tenant_b parties."""
        form = PartyRoleForm(tenant=tenant_a)
        party_pks = list(form.fields["party"].queryset.values_list("pk", flat=True))
        assert party_a.pk in party_pks
        assert party_b.pk not in party_pks
