"""Tests for the seed_hrm management command: idempotency and Party reuse."""
import datetime
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


class TestSeedHRM:
    """Verify seed_hrm is idempotent and reuses core Party persons."""

    def _run_seeder(self, flush=False):
        """Run the seed_hrm management command via Django's call_command."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("seed_hrm", flush=flush, stdout=out, stderr=out)
        return out.getvalue()

    def test_seeder_creates_employees(self, tenant_a):
        from apps.hrm.models import EmployeeProfile
        self._run_seeder()
        assert EmployeeProfile.objects.filter(tenant=tenant_a).exists()

    def test_seeder_creates_leave_types(self, tenant_a):
        from apps.hrm.models import LeaveType
        self._run_seeder()
        assert LeaveType.objects.filter(tenant=tenant_a).count() >= 3

    def test_seeder_creates_shifts(self, tenant_a):
        from apps.hrm.models import Shift
        self._run_seeder()
        assert Shift.objects.filter(tenant=tenant_a).count() >= 2

    def test_seeder_creates_public_holidays(self, tenant_a):
        from apps.hrm.models import PublicHoliday
        self._run_seeder()
        assert PublicHoliday.objects.filter(tenant=tenant_a).count() >= 3

    def test_seeder_creates_attendance_records(self, tenant_a):
        from apps.hrm.models import AttendanceRecord
        self._run_seeder()
        assert AttendanceRecord.objects.filter(tenant=tenant_a).exists()

    def test_seeder_is_idempotent_employee_count(self, tenant_a):
        """Running the seeder twice must not create duplicate rows."""
        from apps.hrm.models import EmployeeProfile
        self._run_seeder()
        count1 = EmployeeProfile.objects.filter(tenant=tenant_a).count()
        self._run_seeder()  # second run — should be skipped
        count2 = EmployeeProfile.objects.filter(tenant=tenant_a).count()
        assert count1 == count2

    def test_seeder_is_idempotent_leave_type_count(self, tenant_a):
        from apps.hrm.models import LeaveType
        self._run_seeder()
        c1 = LeaveType.objects.filter(tenant=tenant_a).count()
        self._run_seeder()
        c2 = LeaveType.objects.filter(tenant=tenant_a).count()
        assert c1 == c2

    def test_seeder_is_idempotent_shift_count(self, tenant_a):
        from apps.hrm.models import Shift
        self._run_seeder()
        c1 = Shift.objects.filter(tenant=tenant_a).count()
        self._run_seeder()
        c2 = Shift.objects.filter(tenant=tenant_a).count()
        assert c1 == c2

    def test_seeder_reuses_existing_party_persons(self, tenant_a):
        """If person Parties already exist, seeder must NOT create new Party duplicates."""
        from apps.core.models import Party
        # Pre-create 5 persons so seeder can reuse them
        names = ["Alice Alpha", "Bob Beta", "Carol Gamma", "Dan Delta", "Eve Epsilon"]
        for name in names:
            Party.objects.create(tenant=tenant_a, kind="person", name=name)
        count_before = Party.objects.filter(tenant=tenant_a, kind="person").count()

        self._run_seeder()

        # Exclude candidate-role persons: 3.6 candidates are genuinely new applicants (not existing
        # staff), so the candidate seeder DOES mint fresh person Parties for them — by design. This
        # test asserts the *employee* seeding reuses the existing persons rather than duplicating them.
        count_after = (Party.objects.filter(tenant=tenant_a, kind="person")
                       .exclude(roles__role="candidate").count())
        # The seeder should have reused the existing persons and added AT MOST 0 new ones
        # (it needs at least 4, we pre-created 5 so no new persons needed)
        assert count_after == count_before

    def test_seeder_second_run_outputs_skip_notice(self, tenant_a):
        """Second run should log a 'data already exists' notice."""
        self._run_seeder()
        output = self._run_seeder()
        assert "already exists" in output.lower() or "use --flush" in output.lower()

    def test_seeder_flush_recreates_employees(self, tenant_a):
        """--flush should wipe and re-seed, keeping same count."""
        from apps.hrm.models import EmployeeProfile
        self._run_seeder()
        count1 = EmployeeProfile.objects.filter(tenant=tenant_a).count()
        self._run_seeder(flush=True)
        count2 = EmployeeProfile.objects.filter(tenant=tenant_a).count()
        assert count2 == count1

    def test_seeder_employee_numbers_start_at_emp_00001(self, tenant_a):
        """After seeding, at least one employee should have EMP-00001."""
        from apps.hrm.models import EmployeeProfile
        self._run_seeder()
        assert EmployeeProfile.objects.filter(tenant=tenant_a, number="EMP-00001").exists()

    def test_seeder_creates_workforce_planning_data(self, tenant_a):
        """3.40 — _seed_workforce lays down a plan (with lines), scenarios and a skills inventory."""
        from apps.hrm.models import (EmployeeSkill, WorkforcePlan, WorkforcePlanLine,
                                     WorkforceScenario)
        self._run_seeder()
        assert WorkforcePlan.objects.filter(tenant=tenant_a).exists()
        assert WorkforcePlanLine.objects.filter(tenant=tenant_a).count() >= 1
        assert WorkforceScenario.objects.filter(tenant=tenant_a, is_baseline=True).exists()
        assert EmployeeSkill.objects.filter(tenant=tenant_a, is_critical_skill=True).exists()

    def test_seeder_flush_recreates_workforce_data(self, tenant_a):
        """--flush must tear the 3.40 rows down (nothing PROTECTs a flushed master) and rebuild them
        with a stable count — a regression guard for the _seed_tenant teardown ordering."""
        from apps.hrm.models import WorkforcePlanLine
        self._run_seeder()
        count1 = WorkforcePlanLine.objects.filter(tenant=tenant_a).count()
        self._run_seeder(flush=True)
        count2 = WorkforcePlanLine.objects.filter(tenant=tenant_a).count()
        assert count1 == count2 and count1 >= 1

    def test_seeder_creates_engagement_data(self, tenant_a):
        """3.41 — _seed_engagement lays down action plans, a wellbeing catalog, participations + FWAs."""
        from apps.hrm.models import (FlexibleWorkArrangement, SurveyActionPlan,
                                     WellbeingParticipation, WellbeingProgram)
        self._run_seeder()
        assert SurveyActionPlan.objects.filter(tenant=tenant_a).count() >= 1
        assert WellbeingProgram.objects.filter(tenant=tenant_a).count() >= 1
        assert WellbeingParticipation.objects.filter(tenant=tenant_a).exists()
        assert FlexibleWorkArrangement.objects.filter(tenant=tenant_a).exists()

    def test_seeder_forces_eap_program_confidential(self, tenant_a):
        """The seeded EAP program is created is_confidential=False — the model's save() must force True."""
        from apps.hrm.models import WellbeingProgram
        self._run_seeder()
        eap = WellbeingProgram.objects.filter(tenant=tenant_a, program_type="eap_counseling").first()
        assert eap is not None and eap.is_confidential is True

    def test_seeder_flush_recreates_engagement_data(self, tenant_a):
        """--flush validates the 3.41 teardown ordering (SurveyActionPlan.owner + participation.employee
        are PROTECT against EmployeeProfile) — no ProtectedError, stable count."""
        from apps.hrm.models import WellbeingProgram
        self._run_seeder()
        count1 = WellbeingProgram.objects.filter(tenant=tenant_a).count()
        self._run_seeder(flush=True)
        count2 = WellbeingProgram.objects.filter(tenant=tenant_a).count()
        assert count1 == count2 and count1 >= 1

    def test_seeder_does_not_disturb_3_27_surveys(self, tenant_a):
        """_seed_engagement adds its OWN closed survey — 3.27's Q3 pulse + draft culture survey stay."""
        from apps.hrm.models import Survey
        self._run_seeder()
        assert Survey.objects.filter(tenant=tenant_a, title="Q3 Employee Engagement Pulse").exists()
        assert Survey.objects.filter(tenant=tenant_a, title="H1 Engagement Pulse (closed)").exists()
