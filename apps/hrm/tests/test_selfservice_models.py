"""Tests for HRM 3.25 Personal Information (Self-Service) models: ``EmergencyContact``/
``EmployeeBankAccount`` auto-demote-on-save (one ``is_primary``/``is_salary_account`` per employee),
``EmployeeBankAccount`` masking (``masked_account_number``/``masked_routing_number`` — never the raw
value, not even in ``__str__``), ``FamilyMember.clean()`` (a minor requires a guardian name), and
``EmployeeInfoChangeRequest`` — the ``ICR-`` maker-checker workflow: ``clean()`` anti-tamper
(profile-field requests may only target the requester's own profile; bank/family edits may only
target the requester's own existing row) and ``apply(user)`` across all 3 request types x both the
object_id-None (propose-a-new-row) and object_id-set (propose-an-edit) paths, the ``legal_name``
special case (writes ``core.Party.name``, not an ``EmployeeProfile`` column), and the lost-update
guard (a stale stored ``old`` snapshot blocks an edit-path apply() without touching the target; a
new-row apply() has nothing to compare, so it skips the guard). Also covers the 3.25 change-request
sub-forms (``ProfileFieldChangeForm``/``FamilyMemberChangeForm``). Mirrors
test_trainingadmin_models.py conventions."""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ EmergencyContact
class TestEmergencyContactModel:
    def test_default_is_primary_false(self, tenant_a, employee_a):
        from apps.hrm.models import EmergencyContact
        ec = EmergencyContact.objects.create(tenant=tenant_a, employee=employee_a, name="Bob", phone="555-0001")
        assert ec.is_primary is False

    def test_auto_demote_primary_on_second_primary_save(self, tenant_a, employee_a, emergency_contact_a):
        from apps.hrm.models import EmergencyContact
        assert emergency_contact_a.is_primary is True
        second = EmergencyContact.objects.create(
            tenant=tenant_a, employee=employee_a, name="Second Contact", phone="555-0002", is_primary=True)
        emergency_contact_a.refresh_from_db()
        assert emergency_contact_a.is_primary is False
        assert second.is_primary is True

    def test_auto_demote_scoped_per_employee(self, tenant_a, employee_a, employee_a2, emergency_contact_a):
        """A primary contact for a DIFFERENT employee must not be demoted."""
        from apps.hrm.models import EmergencyContact
        other = EmergencyContact.objects.create(
            tenant=tenant_a, employee=employee_a2, name="Other Primary", phone="555-0003", is_primary=True)
        emergency_contact_a.refresh_from_db()
        assert emergency_contact_a.is_primary is True  # untouched — different employee
        assert other.is_primary is True

    def test_non_primary_save_does_not_demote_existing_primary(self, tenant_a, employee_a, emergency_contact_a):
        from apps.hrm.models import EmergencyContact
        EmergencyContact.objects.create(
            tenant=tenant_a, employee=employee_a, name="Non Primary", phone="555-0004", is_primary=False)
        emergency_contact_a.refresh_from_db()
        assert emergency_contact_a.is_primary is True

    def test_str_contains_name_relationship_and_employee(self, emergency_contact_a):
        s = str(emergency_contact_a)
        assert "Carol White" in s
        assert "Sibling" in s
        assert "Alice Smith" in s


# ================================================================ EmployeeBankAccount
class TestEmployeeBankAccountModel:
    def test_default_verification_status_pending(self, bank_account_a):
        assert bank_account_a.verification_status == "pending"

    def test_default_status_active(self, bank_account_a):
        assert bank_account_a.status == "active"

    def test_default_is_salary_account_false(self, bank_account_a):
        assert bank_account_a.is_salary_account is False

    def test_auto_demote_salary_account_on_second_save(self, tenant_a, employee_a, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount
        bank_account_a.is_salary_account = True
        bank_account_a.save()
        second = EmployeeBankAccount.objects.create(
            tenant=tenant_a, employee=employee_a, bank_name="Second Bank",
            account_holder_name="Alice Smith", account_number="1231231231231234",
            is_salary_account=True,
        )
        bank_account_a.refresh_from_db()
        assert bank_account_a.is_salary_account is False
        assert second.is_salary_account is True

    def test_auto_demote_scoped_per_employee(self, tenant_a, employee_a, employee_a2, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount
        bank_account_a.is_salary_account = True
        bank_account_a.save()
        other = EmployeeBankAccount.objects.create(
            tenant=tenant_a, employee=employee_a2, bank_name="Other Bank",
            account_holder_name="Carol White", account_number="4564564564564567",
            is_salary_account=True,
        )
        bank_account_a.refresh_from_db()
        assert bank_account_a.is_salary_account is True  # untouched — different employee
        assert other.is_salary_account is True

    # -------------------------------------------------- masking
    def test_masked_account_number_shows_only_last4(self, bank_account_a):
        assert bank_account_a.masked_account_number() == "••••1122"

    def test_masked_routing_number_shows_only_last4(self, bank_account_a):
        assert bank_account_a.masked_routing_number() == "••••8877"

    def test_masked_never_returns_raw_value(self, bank_account_a):
        masked = bank_account_a.masked_account_number()
        assert bank_account_a.account_number not in masked
        assert masked != bank_account_a.account_number

    def test_masked_short_value_hides_all_digits(self):
        from apps.hrm.models import EmployeeBankAccount
        assert EmployeeBankAccount._mask_last4("12") == "••••"

    def test_masked_blank_value_returns_empty_string(self):
        from apps.hrm.models import EmployeeBankAccount
        assert EmployeeBankAccount._mask_last4("") == ""
        assert EmployeeBankAccount._mask_last4(None) == ""

    def test_masked_routing_number_blank_returns_empty(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeBankAccount
        acct = EmployeeBankAccount.objects.create(
            tenant=tenant_a, employee=employee_a, bank_name="No Routing Bank",
            account_holder_name="Alice Smith", account_number="1111222233334444", routing_number="")
        assert acct.masked_routing_number() == ""

    def test_str_never_contains_raw_account_number(self, bank_account_a):
        s = str(bank_account_a)
        assert bank_account_a.account_number not in s
        assert "First Bank" in s
        assert "••••1122" in s

    def test_str_contains_employee(self, bank_account_a):
        assert "Alice Smith" in str(bank_account_a)


# ================================================================ FamilyMember
class TestFamilyMemberModel:
    def test_default_is_minor_and_is_dependent_false(self, tenant_a, employee_a):
        from apps.hrm.models import FamilyMember
        fm = FamilyMember.objects.create(tenant=tenant_a, employee=employee_a, name="Kid")
        assert fm.is_minor is False
        assert fm.is_dependent is False

    def test_clean_minor_without_guardian_raises(self, tenant_a, employee_a):
        from apps.hrm.models import FamilyMember
        fm = FamilyMember(tenant=tenant_a, employee=employee_a, name="Minor Kid",
                          relationship="child", is_minor=True, guardian_name="")
        with pytest.raises(ValidationError) as exc:
            fm.clean()
        assert "guardian_name" in exc.value.message_dict

    def test_clean_minor_with_guardian_valid(self, tenant_a, employee_a):
        from apps.hrm.models import FamilyMember
        fm = FamilyMember(tenant=tenant_a, employee=employee_a, name="Minor Kid",
                          relationship="child", is_minor=True, guardian_name="Alice Smith")
        fm.clean()  # must not raise

    def test_clean_non_minor_without_guardian_valid(self, family_member_a):
        family_member_a.clean()  # must not raise — not a minor

    def test_str_contains_name_relationship_display_and_employee(self, family_member_a):
        s = str(family_member_a)
        assert "John Smith" in s
        assert "Spouse" in s
        assert "Alice Smith" in s


# ================================================================ EmployeeInfoChangeRequest — basics
class TestEmployeeInfoChangeRequestModel:
    def test_number_prefix_icr(self, change_request_a):
        assert change_request_a.number.startswith("ICR-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        c1 = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            field_changes={"national_id": {"old": "", "new": "A1"}})
        c2 = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a2, content_type=ct, object_id=employee_a2.pk,
            field_changes={"national_id": {"old": "", "new": "A2"}})
        assert c1.number != c2.number
        assert c1.number.startswith("ICR-")
        assert c2.number.startswith("ICR-")

    def test_unique_together_tenant_number(self, tenant_a, change_request_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        with pytest.raises(IntegrityError):
            EmployeeInfoChangeRequest.objects.create(
                tenant=tenant_a, number=change_request_a.number, employee=change_request_a.employee,
                field_changes={"national_id": {"old": "", "new": "dup"}})

    def test_default_status_pending(self, change_request_a):
        assert change_request_a.status == "pending"

    def test_default_request_type_profile_field(self, change_request_a):
        assert change_request_a.request_type == "profile_field"

    def test_default_reviewed_by_and_at_none(self, change_request_a):
        assert change_request_a.reviewed_by_id is None
        assert change_request_a.reviewed_at is None

    def test_str_contains_number_type_and_employee(self, change_request_a):
        s = str(change_request_a)
        assert change_request_a.number in s
        assert "Profile Field" in s
        assert "Alice Smith" in s

    def test_str_falls_back_to_request_type_when_no_number(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        cr = EmployeeInfoChangeRequest(tenant=tenant_a, employee=employee_a, request_type="bank")
        assert str(cr) == "Bank Account"


# ================================================================ EmployeeInfoChangeRequest.clean() — anti-tamper
class TestEmployeeInfoChangeRequestCleanAntiTamper:
    def test_clean_field_changes_empty_dict_raises(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        cr = EmployeeInfoChangeRequest(tenant=tenant_a, employee=employee_a, field_changes={})
        with pytest.raises(ValidationError) as exc:
            cr.clean()
        assert "field_changes" in exc.value.message_dict

    def test_clean_field_changes_non_dict_raises(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest
        cr = EmployeeInfoChangeRequest(tenant=tenant_a, employee=employee_a, field_changes="not-a-dict")
        with pytest.raises(ValidationError) as exc:
            cr.clean()
        assert "field_changes" in exc.value.message_dict

    def test_clean_profile_field_wrong_content_type_raises(self, tenant_a, employee_a, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a, request_type="profile_field",
            content_type=ct, object_id=employee_a.pk,
            field_changes={"legal_name": {"old": "Alice Smith", "new": "Hacked"}})
        with pytest.raises(ValidationError):
            cr.clean()

    def test_clean_profile_field_wrong_object_id_raises(self, tenant_a, employee_a, employee_a2):
        """A profile_field request whose object_id points at ANOTHER employee's profile is tampering."""
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a, request_type="profile_field",
            content_type=ct, object_id=employee_a2.pk,
            field_changes={"legal_name": {"old": "Alice Smith", "new": "Hacked"}})
        with pytest.raises(ValidationError):
            cr.clean()

    def test_clean_profile_field_own_profile_valid(self, tenant_a, employee_a):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a, request_type="profile_field",
            content_type=ct, object_id=employee_a.pk,
            field_changes={"legal_name": {"old": "Alice Smith", "new": "Legit Change"}})
        cr.clean()  # must not raise

    def test_clean_profile_field_no_content_type_valid(self, tenant_a, employee_a):
        """No content_type set at all (not yet resolved) — the anti-tamper check is skipped."""
        from apps.hrm.models import EmployeeInfoChangeRequest
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a, request_type="profile_field",
            field_changes={"legal_name": {"old": "Alice Smith", "new": "Legit"}})
        cr.clean()  # must not raise

    def test_clean_bank_object_id_wrong_employee_raises(self, tenant_a, employee_a2, bank_account_a):
        """bank_account_a belongs to employee_a; a request from employee_a2 targeting it is tampering."""
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a2, request_type="bank",
            content_type=ct, object_id=bank_account_a.pk,
            field_changes={"bank_name": {"old": bank_account_a.bank_name, "new": "Hacked Bank"}})
        with pytest.raises(ValidationError):
            cr.clean()

    def test_clean_bank_object_id_matching_employee_valid(self, tenant_a, employee_a, bank_account_a):
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a, request_type="bank",
            content_type=ct, object_id=bank_account_a.pk,
            field_changes={"bank_name": {"old": bank_account_a.bank_name, "new": "Renamed"}})
        cr.clean()  # must not raise — own row

    def test_clean_bank_object_id_none_skips_ownership_check(self, tenant_a, employee_a):
        """No existing target (a proposed NEW row) — nothing to mismatch, so clean() passes."""
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a, request_type="bank",
            content_type=ct, object_id=None,
            field_changes={"bank_name": {"old": None, "new": "New Bank"}})
        cr.clean()  # must not raise

    def test_clean_family_object_id_wrong_employee_raises(self, tenant_a, employee_a2, family_member_a):
        """family_member_a belongs to employee_a; a request from employee_a2 targeting it is tampering."""
        from apps.hrm.models import EmployeeInfoChangeRequest, FamilyMember
        ct = ContentType.objects.get_for_model(FamilyMember)
        cr = EmployeeInfoChangeRequest(
            tenant=tenant_a, employee=employee_a2, request_type="family",
            content_type=ct, object_id=family_member_a.pk,
            field_changes={"name": {"old": family_member_a.name, "new": "Hacked Name"}})
        with pytest.raises(ValidationError):
            cr.clean()


# ================================================================ EmployeeInfoChangeRequest.apply()
class TestEmployeeInfoChangeRequestApply:
    # -------------------------------------------------- profile_field
    def test_apply_profile_field_object_id_set_writes_employee_field(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            request_type="profile_field",
            field_changes={"national_id_type": {"old": employee_a.national_id_type, "new": "Aadhaar"}})
        cr.apply(admin_user)
        employee_a.refresh_from_db()
        assert employee_a.national_id_type == "Aadhaar"

    def test_apply_profile_field_object_id_none_still_writes_employee_field(self, tenant_a, employee_a, admin_user):
        """profile_field's apply() always resolves the target as ``self.employee`` regardless of
        object_id — proving object_id is irrelevant for THIS request type's target resolution."""
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=None,
            request_type="profile_field",
            field_changes={"passport_number": {"old": employee_a.passport_number, "new": "P1234567"}})
        cr.apply(admin_user)
        employee_a.refresh_from_db()
        assert employee_a.passport_number == "P1234567"

    def test_apply_profile_field_legal_name_writes_party_name(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        assert not hasattr(EmployeeProfile, "legal_name")
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            request_type="profile_field",
            field_changes={"legal_name": {"old": employee_a.party.name, "new": "Alice Renamed"}})
        cr.apply(admin_user)
        employee_a.party.refresh_from_db()
        assert employee_a.party.name == "Alice Renamed"

    # -------------------------------------------------- bank
    def test_apply_bank_object_id_none_creates_new_row_and_backfills_object_id(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=None,
            request_type="bank",
            field_changes={
                "bank_name": {"old": None, "new": "Brand New Bank"},
                "account_holder_name": {"old": None, "new": "Alice Smith"},
                "account_number": {"old": None, "new": "2222333344445555"},
                "routing_number": {"old": None, "new": "DEMO2222"},
                "account_type": {"old": None, "new": "savings"},
                "split_percentage": {"old": None, "new": None},
            })
        assert EmployeeBankAccount.objects.filter(tenant=tenant_a, employee=employee_a).count() == 0
        cr.apply(admin_user)
        cr.refresh_from_db()
        assert cr.object_id is not None
        new_acct = EmployeeBankAccount.objects.get(pk=cr.object_id)
        assert new_acct.bank_name == "Brand New Bank"
        assert new_acct.employee_id == employee_a.pk
        assert new_acct.tenant_id == tenant_a.pk

    def test_apply_bank_object_id_set_edits_existing_row(self, tenant_a, employee_a, bank_account_a, admin_user):
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=bank_account_a.pk,
            request_type="bank",
            field_changes={
                "bank_name": {"old": bank_account_a.bank_name, "new": "Renamed Bank"},
                "account_holder_name": {"old": bank_account_a.account_holder_name, "new": bank_account_a.account_holder_name},
                "account_number": {"old": bank_account_a.account_number, "new": bank_account_a.account_number},
                "routing_number": {"old": bank_account_a.routing_number, "new": bank_account_a.routing_number},
                "account_type": {"old": bank_account_a.account_type, "new": bank_account_a.account_type},
                "split_percentage": {"old": None, "new": None},
            })
        cr.apply(admin_user)
        bank_account_a.refresh_from_db()
        assert bank_account_a.bank_name == "Renamed Bank"
        assert EmployeeBankAccount.objects.filter(tenant=tenant_a, employee=employee_a).count() == 1

    # -------------------------------------------------- family
    def test_apply_family_object_id_none_creates_new_row_and_backfills_object_id(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, FamilyMember
        ct = ContentType.objects.get_for_model(FamilyMember)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=None,
            request_type="family",
            field_changes={
                "name": {"old": None, "new": "New Baby"},
                "relationship": {"old": None, "new": "child"},
                "is_dependent": {"old": None, "new": True},
                "is_minor": {"old": None, "new": False},
            })
        cr.apply(admin_user)
        cr.refresh_from_db()
        assert cr.object_id is not None
        new_member = FamilyMember.objects.get(pk=cr.object_id)
        assert new_member.name == "New Baby"
        assert new_member.employee_id == employee_a.pk
        assert new_member.is_dependent is True

    def test_apply_family_object_id_set_edits_existing_row(self, tenant_a, employee_a, family_member_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, FamilyMember
        ct = ContentType.objects.get_for_model(FamilyMember)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=family_member_a.pk,
            request_type="family",
            field_changes={
                "name": {"old": family_member_a.name, "new": "John Renamed"},
                "relationship": {"old": family_member_a.relationship, "new": family_member_a.relationship},
            })
        cr.apply(admin_user)
        family_member_a.refresh_from_db()
        assert family_member_a.name == "John Renamed"
        assert FamilyMember.objects.filter(tenant=tenant_a, employee=employee_a).count() == 1

    # -------------------------------------------------- status/reviewer bookkeeping
    def test_apply_sets_status_approved_reviewed_by_and_reviewed_at(self, change_request_a, admin_user):
        assert change_request_a.status == "pending"
        change_request_a.apply(admin_user)
        change_request_a.refresh_from_db()
        assert change_request_a.status == "approved"
        assert change_request_a.reviewed_by_id == admin_user.pk
        assert change_request_a.reviewed_at is not None

    # -------------------------------------------------- lost-update guard
    def test_apply_lost_update_guard_raises_and_does_not_overwrite(self, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
        ct = ContentType.objects.get_for_model(EmployeeProfile)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
            request_type="profile_field",
            field_changes={"national_id": {"old": "", "new": "AB1111111"}})
        # The live value drifts away from the stored "old" snapshot before the request is reviewed.
        employee_a.national_id = "DRIFTED-VALUE"
        employee_a.save(update_fields=["national_id"])

        with pytest.raises(ValidationError):
            cr.apply(admin_user)

        employee_a.refresh_from_db()
        assert employee_a.national_id == "DRIFTED-VALUE"  # NOT overwritten
        cr.refresh_from_db()
        assert cr.status == "pending"  # unchanged

    def test_apply_new_row_skips_lost_update_guard(self, tenant_a, employee_a, admin_user):
        """A propose-a-new-row request (object_id=None) has no existing target to compare against —
        even a nonsensical stored "old" must not block it."""
        from apps.hrm.models import EmployeeBankAccount, EmployeeInfoChangeRequest
        ct = ContentType.objects.get_for_model(EmployeeBankAccount)
        cr = EmployeeInfoChangeRequest.objects.create(
            tenant=tenant_a, employee=employee_a, content_type=ct, object_id=None,
            request_type="bank",
            field_changes={
                "bank_name": {"old": "THIS-NEVER-EXISTED", "new": "Fresh Bank"},
                "account_holder_name": {"old": None, "new": "Alice Smith"},
                "account_number": {"old": None, "new": "3333444455556666"},
                "routing_number": {"old": None, "new": ""},
                "account_type": {"old": None, "new": "checking"},
                "split_percentage": {"old": None, "new": None},
            })
        cr.apply(admin_user)  # must not raise
        cr.refresh_from_db()
        assert cr.status == "approved"
        assert EmployeeBankAccount.objects.get(pk=cr.object_id).bank_name == "Fresh Bank"


# ================================================================ Forms: ProfileFieldChangeForm
class TestProfileFieldChangeForm:
    def test_date_field_with_non_date_value_invalid(self):
        from apps.hrm.forms import ProfileFieldChangeForm
        form = ProfileFieldChangeForm({"field_name": "date_of_birth", "new_value": "not-a-date", "reason": ""})
        assert form.is_valid() is False
        assert "new_value" in form.errors

    def test_date_field_with_valid_date_valid(self):
        from apps.hrm.forms import ProfileFieldChangeForm
        form = ProfileFieldChangeForm({"field_name": "date_of_birth", "new_value": "1990-05-15", "reason": ""})
        assert form.is_valid() is True, form.errors

    def test_passport_expiry_date_field_non_date_invalid(self):
        from apps.hrm.forms import ProfileFieldChangeForm
        form = ProfileFieldChangeForm({"field_name": "passport_expiry", "new_value": "31/12/2030", "reason": ""})
        assert form.is_valid() is False
        assert "new_value" in form.errors

    def test_national_id_over_max_length_invalid(self):
        from apps.hrm.forms import ProfileFieldChangeForm
        form = ProfileFieldChangeForm({"field_name": "national_id", "new_value": "A" * 101, "reason": ""})
        assert form.is_valid() is False
        assert "new_value" in form.errors

    def test_national_id_within_max_length_valid(self):
        from apps.hrm.forms import ProfileFieldChangeForm
        form = ProfileFieldChangeForm({"field_name": "national_id", "new_value": "A" * 100, "reason": ""})
        assert form.is_valid() is True, form.errors

    def test_non_date_non_length_capped_field_free_text_valid(self):
        from apps.hrm.forms import ProfileFieldChangeForm
        form = ProfileFieldChangeForm({"field_name": "national_id_type", "new_value": "Passport", "reason": ""})
        assert form.is_valid() is True, form.errors


# ================================================================ Forms: FamilyMemberChangeForm
class TestFamilyMemberChangeFormClean:
    def _data(self, **overrides):
        data = {
            "existing_member": "", "name": "New Kid", "relationship": "child",
            "date_of_birth": "", "gender": "", "occupation": "", "phone": "",
            "is_dependent": "", "is_minor": "on", "guardian_name": "",
            "guardian_relationship": "", "is_nominee": "", "nominee_percentage": "", "reason": "",
        }
        data.update(overrides)
        return data

    def test_minor_without_guardian_invalid(self):
        from apps.hrm.forms import FamilyMemberChangeForm
        form = FamilyMemberChangeForm(self._data())
        assert form.is_valid() is False
        assert "guardian_name" in form.errors

    def test_minor_with_guardian_valid(self):
        from apps.hrm.forms import FamilyMemberChangeForm
        form = FamilyMemberChangeForm(self._data(guardian_name="Jane Guardian"))
        assert form.is_valid() is True, form.errors

    def test_non_minor_without_guardian_valid(self):
        from apps.hrm.forms import FamilyMemberChangeForm
        form = FamilyMemberChangeForm(self._data(is_minor=""))
        assert form.is_valid() is True, form.errors
