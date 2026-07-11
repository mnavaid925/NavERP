"""Security tests for HRM 3.25 Personal Information (Self-Service): anonymous redirect-to-login,
cross-tenant IDOR (404) on ``EmergencyContact``/``EmployeeBankAccount``/``FamilyMember``/
``EmployeeInfoChangeRequest`` detail/edit/delete + workflow actions (+ list isolation, + the row
survives the attempt), cross-EMPLOYEE IDOR within the SAME tenant (a non-admin employee is denied
another employee's rows; ``_ss_scope`` hides them from the list), masked-PII response bodies (the
bank list/detail and the change-request bank-diff never render the raw account/routing number),
tenant is always server-set (never smuggled via POST data, and blocked outright when
request.tenant is None), and CSRF enforcement on the POST-only actions. Mirrors
test_trainingadmin_security.py conventions; client_a is the tenant admin."""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _client_for(party, tenant, *, email, username, is_admin=False):
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


# ================================================================ Anonymous -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name", [
        "hrm:emergencycontact_list", "hrm:emergencycontact_create",
        "hrm:employeebankaccount_list", "hrm:employeebankaccount_create",
        "hrm:familymember_list", "hrm:familymember_create",
        "hrm:changerequest_list", "hrm:changerequest_create",
        "hrm:my_info", "hrm:my_info_edit",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_and_edit_pages(
        self, client, emergency_contact_a, bank_account_a, family_member_a, change_request_a
    ):
        for url_name, pk in [
            ("hrm:emergencycontact_detail", emergency_contact_a.pk),
            ("hrm:emergencycontact_edit", emergency_contact_a.pk),
            ("hrm:employeebankaccount_detail", bank_account_a.pk),
            ("hrm:employeebankaccount_edit", bank_account_a.pk),
            ("hrm:familymember_detail", family_member_a.pk),
            ("hrm:familymember_edit", family_member_a.pk),
            ("hrm:changerequest_detail", change_request_a.pk),
            ("hrm:changerequest_edit", change_request_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_delete(
        self, client, emergency_contact_a, bank_account_a, family_member_a, change_request_a
    ):
        for url_name, pk in [
            ("hrm:emergencycontact_delete", emergency_contact_a.pk),
            ("hrm:employeebankaccount_delete", bank_account_a.pk),
            ("hrm:familymember_delete", family_member_a.pk),
            ("hrm:changerequest_delete", change_request_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_workflow_actions(self, client, bank_account_a, change_request_a):
        for url_name, pk in [
            ("hrm:employeebankaccount_verify", bank_account_a.pk),
            ("hrm:employeebankaccount_reject", bank_account_a.pk),
            ("hrm:changerequest_cancel", change_request_a.pk),
            ("hrm:changerequest_approve", change_request_a.pk),
            ("hrm:changerequest_reject", change_request_a.pk),
        ]:
            resp = client.post(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ Cross-tenant IDOR: EmergencyContact
class TestEmergencyContactIDOR:
    def test_detail_cross_tenant_404(self, client_a, emergency_contact_b):
        resp = client_a.get(reverse("hrm:emergencycontact_detail", args=[emergency_contact_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, emergency_contact_b):
        resp = client_a.get(reverse("hrm:emergencycontact_edit", args=[emergency_contact_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, emergency_contact_b):
        resp = client_a.post(
            reverse("hrm:emergencycontact_edit", args=[emergency_contact_b.pk]),
            _emergency_contact_post_data(name="hacked"))
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, emergency_contact_b):
        original = emergency_contact_b.name
        client_a.post(
            reverse("hrm:emergencycontact_edit", args=[emergency_contact_b.pk]),
            _emergency_contact_post_data(name="hacked"))
        emergency_contact_b.refresh_from_db()
        assert emergency_contact_b.name == original

    def test_delete_cross_tenant_404(self, client_a, emergency_contact_b):
        from apps.hrm.models import EmergencyContact
        resp = client_a.post(reverse("hrm:emergencycontact_delete", args=[emergency_contact_b.pk]))
        assert resp.status_code == 404
        assert EmergencyContact.objects.filter(pk=emergency_contact_b.pk).exists()

    def test_list_excludes_b_rows(self, client_a, emergency_contact_a, emergency_contact_b):
        resp = client_a.get(reverse("hrm:emergencycontact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert emergency_contact_a.pk in pks
        assert emergency_contact_b.pk not in pks


# ================================================================ Cross-tenant IDOR: EmployeeBankAccount
class TestEmployeeBankAccountIDOR:
    def test_detail_cross_tenant_404(self, client_a, bank_account_b):
        resp = client_a.get(reverse("hrm:employeebankaccount_detail", args=[bank_account_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, bank_account_b):
        resp = client_a.get(reverse("hrm:employeebankaccount_edit", args=[bank_account_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, bank_account_b):
        resp = client_a.post(
            reverse("hrm:employeebankaccount_edit", args=[bank_account_b.pk]),
            _bank_account_post_data(bank_name="hacked"))
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, bank_account_b):
        original = bank_account_b.bank_name
        client_a.post(
            reverse("hrm:employeebankaccount_edit", args=[bank_account_b.pk]),
            _bank_account_post_data(bank_name="hacked"))
        bank_account_b.refresh_from_db()
        assert bank_account_b.bank_name == original

    def test_delete_cross_tenant_404(self, client_a, bank_account_b):
        from apps.hrm.models import EmployeeBankAccount
        resp = client_a.post(reverse("hrm:employeebankaccount_delete", args=[bank_account_b.pk]))
        assert resp.status_code == 404
        assert EmployeeBankAccount.objects.filter(pk=bank_account_b.pk).exists()

    def test_verify_cross_tenant_404(self, client_a, bank_account_b):
        resp = client_a.post(reverse("hrm:employeebankaccount_verify", args=[bank_account_b.pk]))
        assert resp.status_code == 404
        bank_account_b.refresh_from_db()
        assert bank_account_b.verification_status == "pending"

    def test_reject_cross_tenant_404(self, client_a, bank_account_b):
        resp = client_a.post(reverse("hrm:employeebankaccount_reject", args=[bank_account_b.pk]))
        assert resp.status_code == 404
        bank_account_b.refresh_from_db()
        assert bank_account_b.verification_status == "pending"

    def test_list_excludes_b_rows(self, client_a, bank_account_a, bank_account_b):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert bank_account_a.pk in pks
        assert bank_account_b.pk not in pks


# ================================================================ Cross-tenant IDOR: FamilyMember
class TestFamilyMemberIDOR:
    def test_detail_cross_tenant_404(self, client_a, family_member_b):
        resp = client_a.get(reverse("hrm:familymember_detail", args=[family_member_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, family_member_b):
        resp = client_a.get(reverse("hrm:familymember_edit", args=[family_member_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, family_member_b):
        resp = client_a.post(
            reverse("hrm:familymember_edit", args=[family_member_b.pk]),
            _family_member_post_data(name="hacked"))
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, family_member_b):
        original = family_member_b.name
        client_a.post(
            reverse("hrm:familymember_edit", args=[family_member_b.pk]),
            _family_member_post_data(name="hacked"))
        family_member_b.refresh_from_db()
        assert family_member_b.name == original

    def test_delete_cross_tenant_404(self, client_a, family_member_b):
        from apps.hrm.models import FamilyMember
        resp = client_a.post(reverse("hrm:familymember_delete", args=[family_member_b.pk]))
        assert resp.status_code == 404
        assert FamilyMember.objects.filter(pk=family_member_b.pk).exists()

    def test_list_excludes_b_rows(self, client_a, family_member_a, family_member_b):
        resp = client_a.get(reverse("hrm:familymember_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert family_member_a.pk in pks
        assert family_member_b.pk not in pks


# ================================================================ Cross-tenant IDOR: EmployeeInfoChangeRequest
class TestChangeRequestIDOR:
    def test_detail_cross_tenant_404(self, client_a, change_request_b):
        resp = client_a.get(reverse("hrm:changerequest_detail", args=[change_request_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, change_request_b):
        resp = client_a.get(reverse("hrm:changerequest_edit", args=[change_request_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, change_request_b):
        resp = client_a.post(
            reverse("hrm:changerequest_edit", args=[change_request_b.pk]),
            _profile_field_post_data(new_value="1999-09-09"))
        assert resp.status_code == 404

    def test_cross_tenant_edit_does_not_mutate_b_row(self, client_a, change_request_b):
        import copy
        original = copy.deepcopy(change_request_b.field_changes)
        client_a.post(
            reverse("hrm:changerequest_edit", args=[change_request_b.pk]),
            _profile_field_post_data(new_value="1999-09-09"))
        change_request_b.refresh_from_db()
        assert change_request_b.field_changes == original

    def test_delete_cross_tenant_404(self, client_a, change_request_b):
        from apps.hrm.models import EmployeeInfoChangeRequest
        resp = client_a.post(reverse("hrm:changerequest_delete", args=[change_request_b.pk]))
        assert resp.status_code == 404
        assert EmployeeInfoChangeRequest.objects.filter(pk=change_request_b.pk).exists()

    def test_cancel_cross_tenant_404(self, client_a, change_request_b):
        resp = client_a.post(reverse("hrm:changerequest_cancel", args=[change_request_b.pk]))
        assert resp.status_code == 404
        change_request_b.refresh_from_db()
        assert change_request_b.status == "pending"

    def test_approve_cross_tenant_404(self, client_a, change_request_b):
        resp = client_a.post(reverse("hrm:changerequest_approve", args=[change_request_b.pk]))
        assert resp.status_code == 404
        change_request_b.refresh_from_db()
        assert change_request_b.status == "pending"

    def test_reject_cross_tenant_404(self, client_a, change_request_b):
        resp = client_a.post(
            reverse("hrm:changerequest_reject", args=[change_request_b.pk]), {"decision_note": "no"})
        assert resp.status_code == 404
        change_request_b.refresh_from_db()
        assert change_request_b.status == "pending"

    def test_list_excludes_b_rows(self, client_a, change_request_a, change_request_b):
        resp = client_a.get(reverse("hrm:changerequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert change_request_a.pk in pks
        assert change_request_b.pk not in pks


# ================================================================ Cross-EMPLOYEE IDOR (same tenant)
class TestCrossEmployeeIDOR:
    def test_emergencycontact_detail_403_for_other_employee(self, tenant_a, employee_a2, emergency_contact_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_ec_det@acme.com", username="ce_ec_det_acme")
        resp = c.get(reverse("hrm:emergencycontact_detail", args=[emergency_contact_a.pk]))
        assert resp.status_code == 403

    def test_emergencycontact_edit_get_redirects_for_other_employee(self, tenant_a, employee_a2, emergency_contact_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_ec_edit@acme.com", username="ce_ec_edit_acme")
        resp = c.get(reverse("hrm:emergencycontact_edit", args=[emergency_contact_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:emergencycontact_detail", args=[emergency_contact_a.pk])

    def test_emergencycontact_edit_post_does_not_mutate_for_other_employee(
        self, tenant_a, employee_a2, emergency_contact_a
    ):
        original = emergency_contact_a.name
        c = _client_for(employee_a2.party, tenant_a, email="ce_ec_edit2@acme.com", username="ce_ec_edit2_acme")
        c.post(
            reverse("hrm:emergencycontact_edit", args=[emergency_contact_a.pk]),
            _emergency_contact_post_data(name="hacked"))
        emergency_contact_a.refresh_from_db()
        assert emergency_contact_a.name == original

    def test_emergencycontact_delete_redirects_and_row_survives_for_other_employee(
        self, tenant_a, employee_a2, emergency_contact_a
    ):
        from apps.hrm.models import EmergencyContact
        c = _client_for(employee_a2.party, tenant_a, email="ce_ec_del@acme.com", username="ce_ec_del_acme")
        resp = c.post(reverse("hrm:emergencycontact_delete", args=[emergency_contact_a.pk]))
        assert resp.status_code == 302
        assert EmergencyContact.objects.filter(pk=emergency_contact_a.pk).exists()

    def test_emergencycontact_list_hides_other_employee_rows(self, tenant_a, employee_a2, emergency_contact_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_ec_list@acme.com", username="ce_ec_list_acme")
        resp = c.get(reverse("hrm:emergencycontact_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert emergency_contact_a.pk not in pks

    def test_bankaccount_detail_403_for_other_employee(self, tenant_a, employee_a2, bank_account_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_ba_det@acme.com", username="ce_ba_det_acme")
        resp = c.get(reverse("hrm:employeebankaccount_detail", args=[bank_account_a.pk]))
        assert resp.status_code == 403

    def test_bankaccount_list_hides_other_employee_rows(self, tenant_a, employee_a2, bank_account_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_ba_list@acme.com", username="ce_ba_list_acme")
        resp = c.get(reverse("hrm:employeebankaccount_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert bank_account_a.pk not in pks

    def test_familymember_detail_403_for_other_employee(self, tenant_a, employee_a2, family_member_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_fm_det@acme.com", username="ce_fm_det_acme")
        resp = c.get(reverse("hrm:familymember_detail", args=[family_member_a.pk]))
        assert resp.status_code == 403

    def test_familymember_list_hides_other_employee_rows(self, tenant_a, employee_a2, family_member_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_fm_list@acme.com", username="ce_fm_list_acme")
        resp = c.get(reverse("hrm:familymember_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert family_member_a.pk not in pks

    def test_changerequest_detail_403_for_other_employee(self, tenant_a, employee_a2, change_request_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_cr_det@acme.com", username="ce_cr_det_acme")
        resp = c.get(reverse("hrm:changerequest_detail", args=[change_request_a.pk]))
        assert resp.status_code == 403

    def test_changerequest_edit_get_redirects_for_other_employee(self, tenant_a, employee_a2, change_request_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_cr_edit@acme.com", username="ce_cr_edit_acme")
        resp = c.get(reverse("hrm:changerequest_edit", args=[change_request_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("hrm:changerequest_detail", args=[change_request_a.pk])

    def test_changerequest_delete_redirects_and_row_survives_for_other_employee(
        self, tenant_a, employee_a2, change_request_a
    ):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a2.party, tenant_a, email="ce_cr_del@acme.com", username="ce_cr_del_acme")
        resp = c.post(reverse("hrm:changerequest_delete", args=[change_request_a.pk]))
        assert resp.status_code == 302
        assert EmployeeInfoChangeRequest.objects.filter(pk=change_request_a.pk).exists()

    def test_changerequest_cancel_redirects_and_status_unchanged_for_other_employee(
        self, tenant_a, employee_a2, change_request_a
    ):
        c = _client_for(employee_a2.party, tenant_a, email="ce_cr_cancel@acme.com", username="ce_cr_cancel_acme")
        resp = c.post(reverse("hrm:changerequest_cancel", args=[change_request_a.pk]))
        assert resp.status_code == 302
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"  # unchanged

    def test_changerequest_list_hides_other_employee_rows(self, tenant_a, employee_a2, change_request_a):
        c = _client_for(employee_a2.party, tenant_a, email="ce_cr_list@acme.com", username="ce_cr_list_acme")
        resp = c.get(reverse("hrm:changerequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert change_request_a.pk not in pks


# ================================================================ Masked PII — response bodies never leak raw values
class TestMaskedPII:
    def test_bankaccount_list_never_leaks_raw_account_number(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_list"))
        assert bank_account_a.account_number.encode() not in resp.content

    def test_bankaccount_detail_never_leaks_raw_account_or_routing_number(self, client_a, bank_account_a):
        resp = client_a.get(reverse("hrm:employeebankaccount_detail", args=[bank_account_a.pk]))
        assert bank_account_a.account_number.encode() not in resp.content
        assert bank_account_a.routing_number.encode() not in resp.content

    def test_changerequest_detail_bank_diff_never_leaks_raw_account_or_routing_number(
        self, client_a, tenant_a, employee_a
    ):
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=None,
            request_type="bank",
            field_changes={
                "bank_name": {"old": None, "new": "Diff Bank"},
                "account_holder_name": {"old": None, "new": "Alice Smith"},
                "account_number": {"old": None, "new": "9911992299339944"},
                "routing_number": {"old": None, "new": "DEMO9911"},
                "account_type": {"old": None, "new": "checking"},
                "split_percentage": {"old": None, "new": None},
            })
        resp = client_a.get(reverse("hrm:changerequest_detail", args=[cr.pk]))
        assert b"9911992299339944" not in resp.content
        assert b"DEMO9911" not in resp.content
        assert "••••9944".encode() in resp.content

    def test_changerequest_detail_bank_diff_masks_old_value_too(self, client_a, tenant_a, employee_a, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=bank_account_a.pk,
            request_type="bank",
            field_changes={
                "account_number": {"old": bank_account_a.account_number, "new": "1234567890123456"},
            })
        resp = client_a.get(reverse("hrm:changerequest_detail", args=[cr.pk]))
        assert bank_account_a.account_number.encode() not in resp.content
        assert b"1234567890123456" not in resp.content


# ================================================================ Tenant is server-set, never smuggled
class TestTenantServerSet:
    def test_emergencycontact_create_ignores_smuggled_tenant(self, tenant_a, tenant_b, employee_a):
        from apps.hrm.models import EmergencyContact
        c = _client_for(employee_a.party, tenant_a, email="tss_ec@acme.com", username="tss_ec_acme")
        resp = c.post(reverse("hrm:emergencycontact_create"), _emergency_contact_post_data(tenant=tenant_b.pk))
        assert resp.status_code == 302
        ec = EmergencyContact.objects.get(tenant=tenant_a, employee=employee_a, name="Jane Doe")
        assert ec.tenant_id == tenant_a.pk

    def test_bankaccount_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, employee_a):
        from apps.hrm.models import EmployeeBankAccount
        resp = client_a.post(
            reverse("hrm:employeebankaccount_create"),
            _bank_account_post_data(employee_pk=str(employee_a.pk), tenant=tenant_b.pk))
        assert resp.status_code == 302
        acct = EmployeeBankAccount.objects.get(tenant=tenant_a, employee=employee_a, bank_name="Second Bank")
        assert acct.tenant_id == tenant_a.pk

    def test_familymember_create_ignores_smuggled_tenant(self, client_a, tenant_a, tenant_b, employee_a):
        from apps.hrm.models import FamilyMember
        resp = client_a.post(
            reverse("hrm:familymember_create"),
            _family_member_post_data(employee_pk=str(employee_a.pk), tenant=tenant_b.pk))
        assert resp.status_code == 302
        fm = FamilyMember.objects.get(tenant=tenant_a, employee=employee_a, name="New Member")
        assert fm.tenant_id == tenant_a.pk

    def test_changerequest_create_ignores_smuggled_tenant(self, tenant_a, tenant_b, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="tss_cr@acme.com", username="tss_cr_acme")
        resp = c.post(reverse("hrm:changerequest_create"), _profile_field_post_data(tenant=tenant_b.pk))
        assert resp.status_code == 302
        cr = EmployeeInfoChangeRequest.objects.get(tenant=tenant_a, employee=employee_a)
        assert cr.tenant_id == tenant_a.pk

    def test_emergencycontact_create_blocked_when_request_tenant_is_none(self, employee_a):
        from apps.accounts.models import User
        from apps.hrm.models import EmergencyContact
        tenantless = User.objects.create_user(
            email="notenant_ec@example.com", username="notenant_ec_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False)
        tenantless.party = employee_a.party
        tenantless.save(update_fields=["party"])
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:emergencycontact_create"), _emergency_contact_post_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not EmergencyContact.objects.filter(name="Jane Doe").exists()

    def test_bankaccount_create_blocked_when_tenantless_but_admin_flagged(self, employee_a):
        """Even a tenant-less user WITH is_tenant_admin=True (passing @tenant_admin_required) is
        still blocked by _ss_child_create's own request.tenant is None guard — no orphan row."""
        from apps.accounts.models import User
        from apps.hrm.models import EmployeeBankAccount
        tenantless_admin = User.objects.create_user(
            email="notenant_ba_admin@example.com", username="notenant_ba_admin_user",
            password="TestPass123!", tenant=None, is_tenant_admin=True)
        c = Client()
        c.force_login(tenantless_admin)
        resp = c.post(
            reverse("hrm:employeebankaccount_create"),
            _bank_account_post_data(employee_pk=str(employee_a.pk)))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not EmployeeBankAccount.objects.filter(bank_name="Second Bank").exists()

    def test_changerequest_create_blocked_when_request_tenant_is_none(self, employee_a):
        from apps.accounts.models import User
        from apps.hrm.models import EmployeeInfoChangeRequest
        tenantless = User.objects.create_user(
            email="notenant_cr@example.com", username="notenant_cr_user", password="TestPass123!",
            tenant=None, is_tenant_admin=False)
        tenantless.party = employee_a.party
        tenantless.save(update_fields=["party"])
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse("hrm:changerequest_create"), _profile_field_post_data())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not EmployeeInfoChangeRequest.objects.filter(employee=employee_a).exists()


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_emergencycontact_delete_enforces_csrf(self, tenant_a, employee_a, emergency_contact_a):
        from apps.hrm.models import EmergencyContact
        c = _client_for(employee_a.party, tenant_a, email="csrf_ec@acme.com", username="csrf_ec_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:emergencycontact_delete", args=[emergency_contact_a.pk]))
        assert resp.status_code == 403
        assert EmergencyContact.objects.filter(pk=emergency_contact_a.pk).exists()

    def test_bankaccount_delete_enforces_csrf(self, admin_user, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:employeebankaccount_delete", args=[bank_account_a.pk]))
        assert resp.status_code == 403
        assert EmployeeBankAccount.objects.filter(pk=bank_account_a.pk).exists()

    def test_bankaccount_verify_enforces_csrf(self, admin_user, bank_account_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:employeebankaccount_verify", args=[bank_account_a.pk]))
        assert resp.status_code == 403
        bank_account_a.refresh_from_db()
        assert bank_account_a.verification_status == "pending"

    def test_familymember_delete_enforces_csrf(self, admin_user, family_member_a):
        from apps.hrm.models import FamilyMember
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:familymember_delete", args=[family_member_a.pk]))
        assert resp.status_code == 403
        assert FamilyMember.objects.filter(pk=family_member_a.pk).exists()

    def test_changerequest_approve_enforces_csrf(self, admin_user, change_request_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:changerequest_approve", args=[change_request_a.pk]))
        assert resp.status_code == 403
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"

    def test_changerequest_reject_enforces_csrf(self, admin_user, change_request_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:changerequest_reject", args=[change_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        change_request_a.refresh_from_db()
        assert change_request_a.status == "pending"

    def test_changerequest_create_enforces_csrf(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        c = _client_for(employee_a.party, tenant_a, email="csrf_cr@acme.com", username="csrf_cr_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:changerequest_create"), _profile_field_post_data())
        assert resp.status_code == 403
        assert not EmployeeInfoChangeRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()
