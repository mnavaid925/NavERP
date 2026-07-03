"""Tests for HRM 3.12 Holiday Management completion: HolidayPolicy.for_employee() resolver,
FloatingHolidayElection quota enforcement + policy auto-resolve, and PublicHoliday.category."""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ PublicHoliday.category
class TestPublicHolidayCategory:
    def test_default_is_national(self, holiday_a):
        assert holiday_a.category == "national"

    def test_get_category_display(self, tenant_a):
        from apps.hrm.models import PublicHoliday
        h = PublicHoliday.objects.create(
            tenant=tenant_a, date=datetime.date(2026, 8, 14), name="Regional Day",
            category="regional",
        )
        assert h.get_category_display() == "Regional"

    def test_all_category_choices_display(self, tenant_a):
        from apps.hrm.models import PublicHoliday
        expected = {
            "national": "National", "regional": "Regional",
            "company": "Company", "observance": "Observance",
        }
        for i, (value, label) in enumerate(expected.items()):
            h = PublicHoliday.objects.create(
                tenant=tenant_a, date=datetime.date(2026, 1, i + 1), name=f"H{i}",
                category=value,
            )
            assert h.get_category_display() == label


# ================================================================ HolidayPolicy.for_employee()
class TestHolidayPolicyForEmployee:
    def test_returns_none_when_no_policies(self, employee_a):
        from apps.hrm.models import HolidayPolicy
        assert HolidayPolicy.for_employee(employee_a) is None

    def test_returns_none_for_none_employee(self):
        from apps.hrm.models import HolidayPolicy
        assert HolidayPolicy.for_employee(None) is None

    def test_falls_back_to_default_policy(self, tenant_a, employee_a, default_holiday_policy_a):
        from apps.hrm.models import HolidayPolicy
        resolved = HolidayPolicy.for_employee(employee_a)
        assert resolved == default_holiday_policy_a

    def test_specific_employee_type_policy_beats_default(
        self, tenant_a, employee_a, default_holiday_policy_a
    ):
        """employee_a is full_time — a full_time-scoped policy must outrank the company default."""
        from apps.hrm.models import HolidayPolicy
        specific = HolidayPolicy.objects.create(
            tenant=tenant_a, name="Full Time Policy", employee_type="full_time",
            floating_holiday_quota=3,
        )
        resolved = HolidayPolicy.for_employee(employee_a)
        assert resolved == specific

    def test_non_matching_employee_type_policy_disqualified(
        self, tenant_a, employee_a, default_holiday_policy_a
    ):
        """employee_a is full_time — a part_time-scoped policy must NOT match; falls back to default."""
        from apps.hrm.models import HolidayPolicy
        HolidayPolicy.objects.create(
            tenant=tenant_a, name="Part Time Policy", employee_type="part_time",
            floating_holiday_quota=5,
        )
        resolved = HolidayPolicy.for_employee(employee_a)
        assert resolved == default_holiday_policy_a

    def test_more_specific_scope_wins_over_single_field_match(
        self, tenant_a, employee_a, dept_a, default_holiday_policy_a
    ):
        """A policy matching employee_type AND org_unit outranks one matching only employee_type."""
        from apps.hrm.models import HolidayPolicy
        single_match = HolidayPolicy.objects.create(
            tenant=tenant_a, name="Type Only", employee_type="full_time",
            floating_holiday_quota=2,
        )
        double_match = HolidayPolicy.objects.create(
            tenant=tenant_a, name="Type + Org Unit", employee_type="full_time",
            org_unit=dept_a, floating_holiday_quota=4,
        )
        resolved = HolidayPolicy.for_employee(employee_a)
        assert resolved == double_match
        assert resolved != single_match

    def test_designation_scope_disqualifies_non_matching(self, tenant_a, employee_a, designation_b):
        """A policy scoped to a designation the employee doesn't hold must not match (designation_b
        belongs to a different tenant/designation than employee_a's designation_a)."""
        from apps.hrm.models import HolidayPolicy, Designation
        other_desig = Designation.objects.create(tenant=tenant_a, name="Manager", grade="L5")
        HolidayPolicy.objects.create(
            tenant=tenant_a, name="Manager Only", designation=other_desig,
            floating_holiday_quota=10,
        )
        assert HolidayPolicy.for_employee(employee_a) is None

    def test_location_contains_match(self, tenant_a, tenant_b, person_a, employment_a, designation_a):
        from apps.hrm.models import HolidayPolicy, EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a, employment=employment_a, designation=designation_a,
            employee_type="full_time", work_location="New York — HQ Floor 3",
        )
        policy = HolidayPolicy.objects.create(
            tenant=tenant_a, name="NY Policy", location="new york", floating_holiday_quota=2,
        )
        assert HolidayPolicy.for_employee(emp) == policy

    def test_location_non_match_disqualifies(self, tenant_a, person_a, employment_a, designation_a):
        from apps.hrm.models import HolidayPolicy, EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a, employment=employment_a, designation=designation_a,
            employee_type="full_time", work_location="Chicago",
        )
        HolidayPolicy.objects.create(
            tenant=tenant_a, name="NY Policy", location="new york", floating_holiday_quota=2,
        )
        assert HolidayPolicy.for_employee(emp) is None

    def test_inactive_policy_ignored(self, tenant_a, employee_a):
        from apps.hrm.models import HolidayPolicy
        HolidayPolicy.objects.create(
            tenant=tenant_a, name="Inactive Default", is_default=True,
            floating_holiday_quota=1, is_active=False,
        )
        assert HolidayPolicy.for_employee(employee_a) is None

    def test_tenant_isolation_policy_b_not_returned_for_employee_a(
        self, tenant_a, employee_a, holiday_policy_b
    ):
        """A tenant_b policy must never resolve for a tenant_a employee, even though it's a
        company-wide default (holiday_policy_b.is_default=True)."""
        from apps.hrm.models import HolidayPolicy
        assert HolidayPolicy.for_employee(employee_a) is None

    def test_tie_breaks_toward_default(self, tenant_a, employee_a):
        """Two policies with equal specificity score (both all-wildcard) — the default wins the tie."""
        from apps.hrm.models import HolidayPolicy
        non_default = HolidayPolicy.objects.create(
            tenant=tenant_a, name="A Wildcard Policy", floating_holiday_quota=1,
        )
        default = HolidayPolicy.objects.create(
            tenant=tenant_a, name="Z Company Default", is_default=True, floating_holiday_quota=1,
        )
        resolved = HolidayPolicy.for_employee(employee_a)
        assert resolved == default
        assert resolved != non_default


# ================================================================ HolidayPolicy misc
class TestHolidayPolicyModel:
    def test_str(self, default_holiday_policy_a):
        assert str(default_holiday_policy_a) == "Company Default"

    def test_unique_together(self, tenant_a, default_holiday_policy_a):
        from apps.hrm.models import HolidayPolicy
        with pytest.raises(IntegrityError):
            HolidayPolicy.objects.create(tenant=tenant_a, name="Company Default")

    def test_defaults(self, tenant_a):
        from apps.hrm.models import HolidayPolicy
        p = HolidayPolicy.objects.create(tenant=tenant_a, name="Bare Policy")
        assert p.is_default is False
        assert p.is_active is True
        assert p.floating_holiday_quota == 0
        assert p.holidays.count() == 0


# ================================================================ FloatingHolidayElection.clean()
class TestFloatingHolidayElectionClean:
    def test_non_optional_holiday_rejected(self, tenant_a, employee_a, holiday_a):
        """holiday_a is is_optional=False — electing it must raise ValidationError({'holiday': ...})."""
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection(tenant=tenant_a, employee=employee_a, holiday=holiday_a)
        with pytest.raises(ValidationError) as exc:
            election.clean()
        assert "holiday" in exc.value.message_dict

    def test_optional_holiday_within_quota_passes(
        self, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a
    ):
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection(tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a)
        election.clean()  # must not raise (quota=1, 0 taken so far)
        assert election.policy_id == default_holiday_policy_a.pk

    def test_exceeding_quota_raises(
        self, tenant_a, employee_a, optional_holiday_a, optional_holiday_a2, default_holiday_policy_a
    ):
        """quota=1; employee already has 1 pending election in that year -> a 2nd raises."""
        from apps.hrm.models import FloatingHolidayElection
        FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="pending",
        )
        second = FloatingHolidayElection(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a2,
        )
        with pytest.raises(ValidationError) as exc:
            second.clean()
        assert "holiday" in exc.value.message_dict

    def test_second_election_different_year_not_blocked(
        self, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a
    ):
        """quota=1 in the optional_holiday_a year; a floating holiday in a DIFFERENT year is not
        counted against that year's quota."""
        from apps.hrm.models import FloatingHolidayElection, PublicHoliday
        FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="pending",
        )
        next_year_holiday = PublicHoliday.objects.create(
            tenant=tenant_a, date=datetime.date(2027, 10, 20), name="Diwali 2027", is_optional=True,
        )
        second = FloatingHolidayElection(
            tenant=tenant_a, employee=employee_a, holiday=next_year_holiday,
        )
        second.clean()  # must not raise — different year

    def test_rejected_election_does_not_count_toward_quota(
        self, tenant_a, employee_a, optional_holiday_a, optional_holiday_a2, default_holiday_policy_a
    ):
        from apps.hrm.models import FloatingHolidayElection
        FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="rejected",
        )
        second = FloatingHolidayElection(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a2,
        )
        second.clean()  # must not raise — the rejected election is excluded from the quota count

    def test_quota_is_tenant_scoped(
        self, tenant_a, tenant_b, employee_a, employee_b, optional_holiday_a, optional_holiday_b,
        default_holiday_policy_a, holiday_policy_b,
    ):
        """An identical election already recorded in tenant_b must not consume tenant_a's quota."""
        from apps.hrm.models import FloatingHolidayElection
        FloatingHolidayElection.objects.create(
            tenant=tenant_b, employee=employee_b, holiday=optional_holiday_b, status="pending",
        )
        election = FloatingHolidayElection(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a,
        )
        election.clean()  # must not raise — tenant_b's election is invisible to tenant_a's quota count

    def test_quota_derives_tenant_from_employee_when_tenant_blank(
        self, tenant_a, employee_a, optional_holiday_a, optional_holiday_a2, default_holiday_policy_a
    ):
        """Mirrors the ModelForm create flow: tenant isn't set on the instance yet when clean() runs
        (the view assigns it after is_valid()) — clean() must derive tenant_id from employee.tenant_id
        so the quota count still filters correctly instead of silently passing on tenant_id=None."""
        from apps.hrm.models import FloatingHolidayElection
        FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="pending",
        )
        second = FloatingHolidayElection(employee=employee_a, holiday=optional_holiday_a2)  # tenant NOT set
        with pytest.raises(ValidationError):
            second.clean()

    def test_unique_together_tenant_employee_holiday(
        self, tenant_a, employee_a, optional_holiday_a
    ):
        from apps.hrm.models import FloatingHolidayElection
        FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a,
        )
        with pytest.raises(IntegrityError):
            FloatingHolidayElection.objects.create(
                tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a,
            )


# ================================================================ FloatingHolidayElection.save()
class TestFloatingHolidayElectionSave:
    def test_auto_resolves_policy_when_blank(
        self, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a
    ):
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a,
        )
        assert election.policy_id == default_holiday_policy_a.pk

    def test_respects_explicitly_set_policy(
        self, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a
    ):
        from apps.hrm.models import FloatingHolidayElection, HolidayPolicy
        other_policy = HolidayPolicy.objects.create(
            tenant=tenant_a, name="Explicit Policy", floating_holiday_quota=5,
        )
        election = FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, policy=other_policy,
        )
        assert election.policy_id == other_policy.pk

    def test_save_without_matching_policy_leaves_policy_none(self, tenant_a, employee_a, optional_holiday_a):
        """No HolidayPolicy exists at all -> for_employee() returns None -> policy stays None."""
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a,
        )
        assert election.policy_id is None

    def test_str(self, pending_election_a):
        s = str(pending_election_a)
        assert "Pending" in s
