"""Tests for HRM 3.25 Personal Information (Self-Service) views: ``EmergencyContact`` CRUD (direct
self-edit — no admin gate), ``EmployeeBankAccount``/``FamilyMember`` CRUD (admin-gated writes, but
self-scoped read for the owning employee) + the bank verify/reject workflow, the
``EmployeeInfoChangeRequest`` maker-checker create/edit/delete/cancel/approve/reject flow (all 3
request types, the self-approval block, the reject-requires-a-note guard, and the apply() error
being surfaced as a message instead of a 500), and the ``my_info``/``my_info_edit`` self-service hub.
client_a is the tenant admin (mirrors test_trainingadmin_views.py conventions)."""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _client_for(party, tenant, *, email, username, is_admin=False):
    """Build a logged-in Client for a User linked to the given Party (mirrors the training-admin
    trio's convention)."""
    from apps.accounts.models import User
    user = User.objects.create_user(
        email=email, username=username, password="TestPass123!",
        tenant=tenant, is_tenant_admin=is_admin,
    )
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


def _emergency_contact_post_data(**overrides):
    data = {
        "name": "Jane Doe", "relationship": "Friend", "phone": "+1-555-0000",
        "alt_phone": "", "email": "", "address": "", "is_primary": "", "priority_order": "1",
        "notes": "",
    }
    data.update(overrides)
    return data


def _bank_account_post_data(**overrides):
    data = {
        "bank_name": "Second Bank", "account_holder_name": "Alice Smith",
        "account_number": "5566778899001122", "routing_number": "DEMO0002",
        "account_type": "checking", "is_salary_account": "", "split_percentage": "",
        "status": "active", "notes": "",
    }
    data.update(overrides)
    return data


def _family_member_post_data(**overrides):
    data = {
        "name": "New Member", "relationship": "child", "date_of_birth": "",
        "gender": "", "occupation": "", "phone": "", "is_dependent": "",
        "is_minor": "", "guardian_name": "", "guardian_relationship": "",
        "is_nominee": "", "nominee_percentage": "", "notes": "",
    }
    data.update(overrides)
    return data


def _profile_field_post_data(**overrides):
    data = {"request_type": "profile_field", "field_name": "date_of_birth",
            "new_value": "1991-01-01", "reason": ""}
    data.update(overrides)
    return data


def _bank_change_post_data(**overrides):
    data = {
        "request_type": "bank", "existing_account": "", "bank_name": "Requested Bank",
        "account_holder_name": "Alice Smith", "account_number": "4444555566667777",
        "routing_number": "DEMO4444", "account_type": "checking", "split_percentage": "", "reason": "",
    }
    data.update(overrides)
    return data


def _family_change_post_data(**overrides):
    data = {
        "request_type": "family", "existing_member": "", "name": "Requested Kid",
        "relationship": "child", "date_of_birth": "", "gender": "", "occupation": "", "phone": "",
        "is_dependent": "", "is_minor": "", "guardian_name": "", "guardian_relationship": "",
        "is_nominee": "", "nominee_percentage": "", "reason": "",
    }
    data.update(overrides)
    return data


# ================================================================ EmergencyContact (direct self-edit)
class TestEmergencyContactListView:
    def test_list_200(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert emergency_contact_a.pk in pks

    def test_list_filter_by_is_primary(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_list"), {"is_primary": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert emergency_contact_a.pk in pks

    def test_list_search_by_name(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_list"), {"q": "Carol"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert emergency_contact_a.pk in pks

    def test_list_has_choices_context_for_admin(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_list"))
        assert resp.context["is_admin"] is True
        assert "employees" in resp.context

    def test_bad_page_does_not_500(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_list"), {"page": "999"})
        assert resp.status_code == 200

    def test_list_query_count_bounded(self, client_a, emergency_contact_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:emergencycontact_list"))


class TestEmergencyContactCreateView:
    def test_get_200_for_self_scoped_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ec_self@acme.com", username="ec_self_acme")
        resp = c.get(reverse("hrm:emergencycontact_create"))
        assert resp.status_code == 200

    def test_post_creates_for_self(self, tenant_a, employee_a):
        from apps.hrm.models import EmergencyContact
        c = _client_for(employee_a.party, tenant_a, email="ec_self2@acme.com", username="ec_self2_acme")
        resp = c.post(reverse("hrm:emergencycontact_create"), _emergency_contact_post_data())
        assert resp.status_code == 302
        ec = EmergencyContact.objects.filter(tenant=tenant_a, employee=employee_a, name="Jane Doe").first()
        assert ec is not None
        assert ec.tenant_id == tenant_a.pk

    def test_get_200_for_admin_with_employee_param(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:emergencycontact_create") + f"?employee={employee_a.pk}")
        assert resp.status_code == 200

    def test_post_creates_for_admin_targeting_employee(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import EmergencyContact
        resp = client_a.post(
            reverse("hrm:emergencycontact_create"),
            _emergency_contact_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        ec = EmergencyContact.objects.filter(tenant=tenant_a, employee=employee_a, name="Jane Doe").first()
        assert ec is not None

    def test_admin_without_employee_target_redirects_with_no_create(self, client_a, tenant_a):
        from apps.hrm.models import EmergencyContact
        resp = client_a.post(reverse("hrm:emergencycontact_create"), _emergency_contact_post_data())
        assert resp.status_code == 302
        assert not EmergencyContact.objects.filter(tenant=tenant_a, name="Jane Doe").exists()

    def test_form_has_no_employee_or_tenant_field(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ec_form@acme.com", username="ec_form_acme")
        resp = c.get(reverse("hrm:emergencycontact_create"))
        fields = resp.context["form"].fields
        assert "employee" not in fields
        assert "tenant" not in fields


class TestEmergencyContactDetailEditDelete:
    def test_detail_200_for_owner(self, tenant_a, employee_a, emergency_contact_a):
        c = _client_for(employee_a.party, tenant_a, email="ec_det@acme.com", username="ec_det_acme")
        resp = c.get(reverse("hrm:emergencycontact_detail", args=[emergency_contact_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_detail", args=[emergency_contact_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_for_owner(self, tenant_a, employee_a, emergency_contact_a):
        c = _client_for(employee_a.party, tenant_a, email="ec_edit@acme.com", username="ec_edit_acme")
        resp = c.get(reverse("hrm:emergencycontact_edit", args=[emergency_contact_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_for_owner(self, tenant_a, employee_a, emergency_contact_a):
        c = _client_for(employee_a.party, tenant_a, email="ec_edit2@acme.com", username="ec_edit2_acme")
        resp = c.post(
            reverse("hrm:emergencycontact_edit", args=[emergency_contact_a.pk]),
            _emergency_contact_post_data(name="Renamed Contact"))
        assert resp.status_code == 302
        emergency_contact_a.refresh_from_db()
        assert emergency_contact_a.name == "Renamed Contact"

    def test_delete_post_removes_for_owner(self, tenant_a, employee_a, emergency_contact_a):
        from apps.hrm.models import EmergencyContact
        c = _client_for(employee_a.party, tenant_a, email="ec_del@acme.com", username="ec_del_acme")
        pk = emergency_contact_a.pk
        resp = c.post(reverse("hrm:emergencycontact_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmergencyContact.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, emergency_contact_a):
        resp = client_a.get(reverse("hrm:emergencycontact_delete", args=[emergency_contact_a.pk]))
        assert resp.status_code == 405


# ================================================================ EmployeeBankAccount (admin-gated writes)
class TestEmployeeBankAccountListView:
    def test_list_200(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, bank_account_a):
        c = _client_for(employee_a.party, tenant_a, email="ba_list@acme.com", username="ba_list_acme")
        resp = c.get(reverse("hrm:employeebankaccount_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert bank_account_a.pk in pks

    def test_list_filter_by_verification_status(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"), {"verification_status": "pending"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert bank_account_a.pk in pks

    def test_list_filter_by_account_type(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"), {"account_type": "checking"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert bank_account_a.pk in pks

    def test_list_has_choices_context(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"))
        assert "verification_status_choices" in resp.context
        assert "account_type_choices" in resp.context
        assert "status_choices" in resp.context
        assert "employees" in resp.context

    def test_list_never_leaks_raw_account_number(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"))
        assert bank_account_a.account_number.encode() not in resp.content
        assert b"\xe2\x80\xa2\xe2\x80\xa2\xe2\x80\xa2\xe2\x80\xa21122" in resp.content  # ••••1122

    def test_list_query_count_bounded(self, client_a, bank_account_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:employeebankaccount_list"))


class TestEmployeeBankAccountDetailView:
    def test_detail_200_for_owner_read_only(self, tenant_a, employee_a, bank_account_a):
        c = _client_for(employee_a.party, tenant_a, email="ba_det@acme.com", username="ba_det_acme")
        resp = c.get(reverse("hrm:employeebankaccount_detail", args=[bank_account_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_detail", args=[bank_account_a.pk]))
        assert resp.status_code == 200

    def test_detail_never_leaks_raw_account_or_routing_number(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_detail", args=[bank_account_a.pk]))
        assert bank_account_a.account_number.encode() not in resp.content
        assert bank_account_a.routing_number.encode() not in resp.content


class TestEmployeeBankAccountAdminGating:
    def test_create_get_403_for_non_admin_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="ba_create_na@acme.com", username="ba_create_na_acme")
        resp = c.get(reverse("hrm:employeebankaccount_create") + f"?employee={employee_a.pk}")
        assert resp.status_code == 403

    def test_create_post_403_for_non_admin_no_row_created(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeBankAccount
        c = _client_for(employee_a.party, tenant_a, email="ba_create_na2@acme.com", username="ba_create_na2_acme")
        resp = c.post(reverse("hrm:employeebankaccount_create"), _bank_account_post_data())
        assert resp.status_code == 403
        assert not EmployeeBankAccount.objects.filter(tenant=tenant_a, bank_name="Second Bank").exists()

    def test_create_allowed_for_admin(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import EmployeeBankAccount
        resp = client_a.post(
            reverse("hrm:employeebankaccount_create"),
            _bank_account_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        acct = EmployeeBankAccount.objects.filter(tenant=tenant_a, employee=employee_a, bank_name="Second Bank").first()
        assert acct is not None

    def test_edit_get_403_for_non_admin(self, tenant_a, employee_a, bank_account_a):
        c = _client_for(employee_a.party, tenant_a, email="ba_edit_na@acme.com", username="ba_edit_na_acme")
        resp = c.get(reverse("hrm:employeebankaccount_edit", args=[bank_account_a.pk]))
        assert resp.status_code == 403

    def test_edit_post_403_for_non_admin_no_change(self, tenant_a, employee_a, bank_account_a):
        original = bank_account_a.bank_name
        c = _client_for(employee_a.party, tenant_a, email="ba_edit_na2@acme.com", username="ba_edit_na2_acme")
        resp = c.post(
            reverse("hrm:employeebankaccount_edit", args=[bank_account_a.pk]),
            _bank_account_post_data(bank_name="Hacked Bank"))
        assert resp.status_code == 403
        bank_account_a.refresh_from_db()
        assert bank_account_a.bank_name == original

    def test_edit_allowed_for_admin(self, client_a, bank_account_a):
        resp = client_a.post(
            reverse("hrm:employeebankaccount_edit", args=[bank_account_a.pk]),
            _bank_account_post_data(bank_name="Renamed By Admin"))
        assert resp.status_code == 302
        bank_account_a.refresh_from_db()
        assert bank_account_a.bank_name == "Renamed By Admin"

    def test_delete_403_for_non_admin(self, tenant_a, employee_a, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount
        c = _client_for(employee_a.party, tenant_a, email="ba_del_na@acme.com", username="ba_del_na_acme")
        resp = c.post(reverse("hrm:employeebankaccount_delete", args=[bank_account_a.pk]))
        assert resp.status_code == 403
        assert EmployeeBankAccount.objects.filter(pk=bank_account_a.pk).exists()

    def test_delete_allowed_for_admin(self, client_a, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount
        pk = bank_account_a.pk
        resp = client_a.post(reverse("hrm:employeebankaccount_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeBankAccount.objects.filter(pk=pk).exists()

    def test_verify_403_for_non_admin(self, tenant_a, employee_a, bank_account_a):
        c = _client_for(employee_a.party, tenant_a, email="ba_ver_na@acme.com", username="ba_ver_na_acme")
        resp = c.post(reverse("hrm:employeebankaccount_verify", args=[bank_account_a.pk]))
        assert resp.status_code == 403
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "pending"

    def test_verify_allowed_for_admin_sets_verified(self, client_a, bank_account_a):
        resp = client_a.post(reverse("hrm:employeebankaccount_verify", args=[bank_account_a.pk]))
        assert resp.status_code == 302
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "verified"

    def test_verify_blocked_when_not_pending(self, client_a, bank_account_a):
        bank_account_a.verification_status = "verified"
        bank_account_a.save(update_fields=["verification_status"])
        client_a.post(reverse("hrm:employeebankaccount_verify", args=[bank_account_a.pk]))
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "verified"  # unchanged, no error

    def test_reject_403_for_non_admin(self, tenant_a, employee_a, bank_account_a):
        c = _client_for(employee_a.party, tenant_a, email="ba_rej_na@acme.com", username="ba_rej_na_acme")
        resp = c.post(reverse("hrm:employeebankaccount_reject", args=[bank_account_a.pk]))
        assert resp.status_code == 403
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "pending"

    def test_reject_allowed_for_admin_sets_rejected(self, client_a, bank_account_a):
        resp = client_a.post(reverse("hrm:employeebankaccount_reject", args=[bank_account_a.pk]))
        assert resp.status_code == 302
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "rejected"

    def test_reject_blocked_when_already_rejected(self, client_a, bank_account_a):
        bank_account_a.verification_status = "rejected"
        bank_account_a.save(update_fields=["verification_status"])
        client_a.post(reverse("hrm:employeebankaccount_reject", args=[bank_account_a.pk]))
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "rejected"  # unchanged, no error

    def test_delete_get_not_allowed(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_delete", args=[bank_account_a.pk]))
        assert resp.status_code == 405


# ================================================================ FamilyMember (admin-gated writes)
class TestFamilyMemberListView:
    def test_list_200(self, client_a, family_member_a):
        resp = client_a.get(reverse("hrm:familymember_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, family_member_a):
        c = _client_for(employee_a.party, tenant_a, email="fm_list@acme.com", username="fm_list_acme")
        resp = c.get(reverse("hrm:familymember_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert family_member_a.pk in pks

    def test_list_filter_by_relationship(self, client_a, family_member_a):
        resp = client_a.get(reverse("hrm:familymember_list"), {"relationship": "spouse"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert family_member_a.pk in pks

    def test_list_filter_by_is_dependent(self, client_a, family_member_a):
        resp = client_a.get(reverse("hrm:familymember_list"), {"is_dependent": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert family_member_a.pk in pks

    def test_list_has_choices_context(self, client_a, family_member_a):
        resp = client_a.get(reverse("hrm:familymember_list"))
        assert "relationship_choices" in resp.context
        assert "employees" in resp.context

    def test_list_query_count_bounded(self, client_a, family_member_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:familymember_list"))


class TestFamilyMemberDetailView:
    def test_detail_200_for_owner_read_only(self, tenant_a, employee_a, family_member_a):
        c = _client_for(employee_a.party, tenant_a, email="fm_det@acme.com", username="fm_det_acme")
        resp = c.get(reverse("hrm:familymember_detail", args=[family_member_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, family_member_a):
        resp = client_a.get(reverse("hrm:familymember_detail", args=[family_member_a.pk]))
        assert resp.status_code == 200


class TestFamilyMemberAdminGating:
    def test_create_get_403_for_non_admin(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="fm_create_na@acme.com", username="fm_create_na_acme")
        resp = c.get(reverse("hrm:familymember_create") + f"?employee={employee_a.pk}")
        assert resp.status_code == 403

    def test_create_post_403_for_non_admin_no_row_created(self, tenant_a, employee_a):
        from apps.hrm.models import FamilyMember
        c = _client_for(employee_a.party, tenant_a, email="fm_create_na2@acme.com", username="fm_create_na2_acme")
        resp = c.post(reverse("hrm:familymember_create"), _family_member_post_data())
        assert resp.status_code == 403
        assert not FamilyMember.objects.filter(tenant=tenant_a, name="New Member").exists()

    def test_create_allowed_for_admin(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import FamilyMember
        resp = client_a.post(
            reverse("hrm:familymember_create"),
            _family_member_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert FamilyMember.objects.filter(tenant=tenant_a, employee=employee_a, name="New Member").exists()

    def test_edit_get_403_for_non_admin(self, tenant_a, employee_a, family_member_a):
        c = _client_for(employee_a.party, tenant_a, email="fm_edit_na@acme.com", username="fm_edit_na_acme")
        resp = c.get(reverse("hrm:familymember_edit", args=[family_member_a.pk]))
        assert resp.status_code == 403

    def test_edit_allowed_for_admin(self, client_a, family_member_a):
        resp = client_a.post(
            reverse("hrm:familymember_edit", args=[family_member_a.pk]),
            _family_member_post_data(name="Renamed By Admin"))
        assert resp.status_code == 302
        family_member_a.refresh_from_db()
        assert family_member_a.name == "Renamed By Admin"

    def test_delete_403_for_non_admin(self, tenant_a, employee_a, family_member_a):
        from apps.hrm.models import FamilyMember
        c = _client_for(employee_a.party, tenant_a, email="fm_del_na@acme.com", username="fm_del_na_acme")
        resp = c.post(reverse("hrm:familymember_delete", args=[family_member_a.pk]))
        assert resp.status_code == 403
        assert FamilyMember.objects.filter(pk=family_member_a.pk).exists()

    def test_delete_allowed_for_admin(self, client_a, family_member_a):
        from apps.hrm.models import FamilyMember
        pk = family_member_a.pk
        resp = client_a.post(reverse("hrm:familymember_delete", args=[pk]))
        assert resp.status_code == 302
        assert not FamilyMember.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, family_member_a):
        resp = client_a.get(reverse("hrm:familymember_delete", args=[family_member_a.pk]))
        assert resp.status_code == 405


# ================================================================ EmployeeInfoChangeRequest (maker-checker)
class TestChangeRequestListView:
    def test_list_200(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_list"))
        assert resp.status_code == 200

    def test_list_shows_own_for_self_scoped_employee(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_list@acme.com", username="cr_list_acme")
        resp = c.get(reverse("hrm:changerequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert change_request_a.pk in pks

    def test_list_filter_by_status(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_list"), {"status": "pending"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert change_request_a.pk in pks

    def test_list_filter_by_request_type(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_list"), {"request_type": "profile_field"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert change_request_a.pk in pks

    def test_list_search_by_number(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_list"), {"q": change_request_a.number})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert change_request_a.pk in pks

    def test_list_has_choices_context(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_list"))
        assert "status_choices" in resp.context
        assert "request_type_choices" in resp.context
        assert "employees" in resp.context

    def test_list_query_count_bounded(self, client_a, change_request_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:changerequest_list"))


class TestChangeRequestCreateView:
    def test_get_200_default_profile_field_type_for_self(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_create@acme.com", username="cr_create_acme")
        resp = c.get(reverse("hrm:changerequest_create"))
        assert resp.status_code == 200
        assert resp.context["request_type"] == "profile_field"

    def test_post_profile_field_creates_pending_request_for_self(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="cr_create2@acme.com", username="cr_create2_acme")
        resp = c.post(reverse("hrm:changerequest_create"), _profile_field_post_data())
        assert resp.status_code == 302
        cr = EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert cr is not None
        assert cr.status == "pending"
        assert cr.number.startswith("ICR-")
        assert cr.tenant_id == tenant_a.pk

    def test_post_bank_type_creates_pending_request_new_row(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="cr_create3@acme.com", username="cr_create3_acme")
        resp = c.post(reverse("hrm:changerequest_create"), _bank_change_post_data())
        assert resp.status_code == 302
        cr = EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a, request_type="bank").first()
        assert cr is not None
        assert cr.object_id is None  # proposes a NEW row, not yet applied

    def test_post_bank_type_edit_of_existing_account(self, tenant_a, employee_a, bank_account_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="cr_create4@acme.com", username="cr_create4_acme")
        resp = c.post(
            reverse("hrm:changerequest_create"),
            _bank_change_post_data(existing_account=str(bank_account_a.pk)))
        assert resp.status_code == 302
        cr = EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a, request_type="bank").first()
        assert cr.object_id == bank_account_a.pk

    def test_post_family_type_creates_pending_request_new_row(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="cr_create5@acme.com", username="cr_create5_acme")
        resp = c.post(reverse("hrm:changerequest_create"), _family_change_post_data())
        assert resp.status_code == 302
        cr = EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a, request_type="family").first()
        assert cr is not None
        assert cr.object_id is None

    def test_get_200_for_admin_with_employee_param(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:changerequest_create") + f"?employee={employee_a.pk}")
        assert resp.status_code == 200

    def test_post_creates_by_admin_for_target_employee(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        resp = client_a.post(
            reverse("hrm:changerequest_create"),
            _profile_field_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_admin_without_employee_target_redirects_with_no_create(self, client_a, tenant_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        resp = client_a.post(reverse("hrm:changerequest_create"), _profile_field_post_data())
        assert resp.status_code == 302
        assert not EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a).exists()

    def test_post_invalid_date_value_shows_form_errors_no_object_created(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="cr_create6@acme.com", username="cr_create6_acme")
        resp = c.post(reverse("hrm:changerequest_create"), _profile_field_post_data(new_value="not-a-date"))
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()
        assert not EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_form_has_no_status_number_reviewer_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_create7@acme.com", username="cr_create7_acme")
        resp = c.get(reverse("hrm:changerequest_create"))
        fields = resp.context["form"].fields
        assert "status" not in fields
        assert "number" not in fields
        assert "reviewed_by" not in fields
        assert "tenant" not in fields


class TestChangeRequestDetailEditDeleteCancel:
    def test_detail_200_for_owner(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_det@acme.com", username="cr_det_acme")
        resp = c.get(reverse("hrm:changerequest_detail", args=[change_request_a.pk]))
        assert resp.status_code == 200

    def test_detail_200_for_admin(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_detail", args=[change_request_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_detail", args=[change_request_a.pk]))
        assert "obj" in resp.context
        assert "diffs" in resp.context
        assert "is_admin" in resp.context
        assert "can_manage" in resp.context
        assert "is_own" in resp.context

    def test_edit_get_200_for_owner_when_pending(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_edit@acme.com", username="cr_edit_acme")
        resp = c.get(reverse("hrm:changerequest_edit", args=[change_request_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_not_pending(self, tenant_a, employee_a, change_request_a):
        change_request_a.status = "rejected"
        change_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="cr_edit2@acme.com", username="cr_edit2_acme")
        resp = c.get(reverse("hrm:changerequest_edit", args=[change_request_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:changerequest_detail", args=[change_request_a.pk])

    def test_edit_post_updates_field_changes_when_pending(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_edit3@acme.com", username="cr_edit3_acme")
        resp = c.post(
            reverse("hrm:changerequest_edit", args=[change_request_a.pk]),
            _profile_field_post_data(field_name="national_id", new_value="ZZ9999999"))
        assert resp.status_code == 302
        change_request_a.refresh_from_db()
        assert change_request_a.field_changes["national_id"]["new"] == "ZZ9999999"

    def test_delete_post_removes_when_pending_by_owner(self, tenant_a, employee_a, change_request_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        pk = change_request_a.pk
        c = _client_for(employee_a.party, tenant_a, email="cr_del@acme.com", username="cr_del_acme")
        resp = c.post(reverse("hrm:changerequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeInfoChangeRequest.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_not_pending(self, tenant_a, employee_a, change_request_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        change_request_a.status = "approved"
        change_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="cr_del2@acme.com", username="cr_del2_acme")
        resp = c.post(reverse("hrm:changerequest_delete", args=[change_request_a.pk]))
        assert resp.status_code == 302
        assert EmployeeInfoChangeRequest.objects.filter(pk=change_request_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_delete", args=[change_request_a.pk]))
        assert resp.status_code == 405

    def test_cancel_post_by_owner_sets_cancelled(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_cancel@acme.com", username="cr_cancel_acme")
        resp = c.post(reverse("hrm:changerequest_cancel", args=[change_request_a.pk]))
        assert resp.status_code == 302
        change_request_a.refresh_from_db()
        assert change_request_a.status == "cancelled"

    def test_cancel_blocked_when_not_pending(self, tenant_a, employee_a, change_request_a):
        change_request_a.status = "rejected"
        change_request_a.save(update_fields=["status"])
        c = _client_for(employee_a.party, tenant_a, email="cr_cancel2@acme.com", username="cr_cancel2_acme")
        c.post(reverse("hrm:changerequest_cancel", args=[change_request_a.pk]))
        change_request_a.refresh_from_db()
        assert change_request_a.status == "rejected"  # unchanged

    def test_cancel_get_not_allowed(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_cancel", args=[change_request_a.pk]))
        assert resp.status_code == 405


class TestChangeRequestApprove:
    def test_approve_by_admin_applies_and_sets_approved(self, client_a, tenant_a, employee_a, change_request_a):
        resp = client_a.post(reverse("hrm:changerequest_approve", args=[change_request_a.pk]))
        assert resp.status_code == 302
        change_request_a.refresh_from_db()
        assert change_request_a.status == "approved"
        employee_a.refresh_from_db()
        assert employee_a.national_id == "AB1234567"

    def test_approve_403_for_non_admin(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_appr_na@acme.com", username="cr_appr_na_acme")
        resp = c.post(reverse("hrm:changerequest_approve", args=[change_request_a.pk]))
        assert resp.status_code == 403
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"

    def test_approve_blocked_when_admin_is_the_maker(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            request_type="profile_field", requested_by=admin_user,
            field_changes={"national_id": {"old": "", "new": "SELFMADE1"}})
        c = Client()
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:changerequest_approve", args=[cr.pk]))
        assert resp.status_code == 302
        cr.refresh_from_db()
        assert cr.status == "pending"

    def test_approve_blocked_when_admin_is_the_subject_employee(self, tenant_a, employee_a):
        from apps.accounts.models import User
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        admin_emp = User.objects.create_user(
            email="admin_emp@acme.com", username="admin_emp_acme", password="TestPass123!",
            tenant=tenant_a, is_tenant_admin=True)
        admin_emp.party = employee_a.party
        admin_emp.save(update_fields=["party"])
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            request_type="profile_field",
            field_changes={"national_id": {"old": "", "new": "SUBJECT1"}})
        c = Client()
        c.force_login(admin_emp)
        resp = c.post(reverse("hrm:changerequest_approve", args=[cr.pk]))
        assert resp.status_code == 302
        cr.refresh_from_db()
        assert cr.status == "pending"

    def test_approve_blocked_when_not_pending(self, client_a, change_request_a):
        change_request_a.status = "rejected"
        change_request_a.save(update_fields=["status"])
        client_a.post(reverse("hrm:changerequest_approve", args=[change_request_a.pk]))
        change_request_a.refresh_from_db()
        assert change_request_a.status == "rejected"  # unchanged

    def test_approve_surfaces_apply_error_and_leaves_pending_on_lost_update(
        self, client_a, employee_a, change_request_a
    ):
        employee_a.national_id = "DRIFTED"
        employee_a.save(update_fields=["national_id"])
        resp = client_a.post(reverse("hrm:changerequest_approve", args=[change_request_a.pk]))
        assert resp.status_code == 302  # no 500 — the ValidationError is caught and messaged
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"
        employee_a.refresh_from_db()
        assert employee_a.national_id == "DRIFTED"

    def test_approve_get_not_allowed(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_approve", args=[change_request_a.pk]))
        assert resp.status_code == 405


class TestChangeRequestReject:
    def test_reject_requires_non_blank_decision_note(self, client_a, change_request_a):
        resp = client_a.post(reverse("hrm:changerequest_reject", args=[change_request_a.pk]), {"decision_note": ""})
        assert resp.status_code == 302
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"

    def test_reject_with_note_sets_rejected(self, client_a, change_request_a):
        resp = client_a.post(
            reverse("hrm:changerequest_reject", args=[change_request_a.pk]), {"decision_note": "Not needed"})
        assert resp.status_code == 302
        change_request_a.refresh_from_db()
        assert change_request_a.status == "rejected"
        assert change_request_a.decision_note == "Not needed"

    def test_reject_403_for_non_admin(self, tenant_a, employee_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="cr_rej_na@acme.com", username="cr_rej_na_acme")
        resp = c.post(reverse("hrm:changerequest_reject", args=[change_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"

    def test_reject_blocked_for_own_request_maker(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            request_type="profile_field", requested_by=admin_user,
            field_changes={"national_id": {"old": "", "new": "X"}})
        c = Client()
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:changerequest_reject", args=[cr.pk]), {"decision_note": "no"})
        assert resp.status_code == 302
        cr.refresh_from_db()
        assert cr.status == "pending"

    def test_reject_blocked_when_not_pending(self, client_a, change_request_a):
        change_request_a.status = "approved"
        change_request_a.save(update_fields=["status"])
        client_a.post(
            reverse("hrm:changerequest_reject", args=[change_request_a.pk]), {"decision_note": "too late"})
        change_request_a.refresh_from_db()
        assert change_request_a.status == "approved"  # unchanged

    def test_reject_get_not_allowed(self, client_a, change_request_a):
        resp = client_a.get(reverse("hrm:changerequest_reject", args=[change_request_a.pk]))
        assert resp.status_code == 405


# ================================================================ My Info hub
class TestMyInfo:
    def test_200_for_linked_employee(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="myinfo@acme.com", username="myinfo_acme")
        resp = c.get(reverse("hrm:my_info"))
        assert resp.status_code == 200

    def test_redirect_for_user_without_linked_profile(self, client_a):
        resp = client_a.get(reverse("hrm:my_info"))
        assert resp.status_code == 302

    def test_context_keys(self, tenant_a, employee_a, emergency_contact_a, bank_account_a, family_member_a, change_request_a):
        c = _client_for(employee_a.party, tenant_a, email="myinfo2@acme.com", username="myinfo2_acme")
        resp = c.get(reverse("hrm:my_info"))
        assert "profile" in resp.context
        assert "emergency_contacts" in resp.context
        assert "bank_accounts" in resp.context
        assert "family_members" in resp.context
        assert "my_requests" in resp.context
        assert emergency_contact_a in resp.context["emergency_contacts"]

    def test_anonymous_redirected(self, client):
        resp = client.get(reverse("hrm:my_info"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestMyInfoEdit:
    def test_get_200(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="myinfoedit@acme.com", username="myinfoedit_acme")
        resp = c.get(reverse("hrm:my_info_edit"))
        assert resp.status_code == 200

    def test_post_updates_contact_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="myinfoedit2@acme.com", username="myinfoedit2_acme")
        resp = c.post(reverse("hrm:my_info_edit"), {
            "current_address": "123 New St", "permanent_address": "456 Old St",
            "personal_email": "alice.new@example.com", "mobile": "+1-555-9999",
        })
        assert resp.status_code == 302
        employee_a.refresh_from_db()
        assert employee_a.current_address == "123 New St"
        assert employee_a.personal_email == "alice.new@example.com"

    def test_form_has_no_sensitive_fields(self, tenant_a, employee_a):
        c = _client_for(employee_a.party, tenant_a, email="myinfoedit3@acme.com", username="myinfoedit3_acme")
        resp = c.get(reverse("hrm:my_info_edit"))
        fields = resp.context["form"].fields
        assert "national_id" not in fields
        assert "date_of_birth" not in fields
        assert "bank_account" not in fields
        assert "passport_number" not in fields

    def test_redirect_for_user_without_linked_profile(self, client_a):
        resp = client_a.get(reverse("hrm:my_info_edit"))
        assert resp.status_code == 302

    def test_anonymous_redirected(self, client):
        resp = client.get(reverse("hrm:my_info_edit"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
