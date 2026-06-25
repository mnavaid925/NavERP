"""Tests for HRM 3.2 Organizational Structure:
JobGrade, Designation (enhanced), DepartmentProfile, CostCenterProfile,
org_chart view, company_setup view, and the seed_hrm _seed_org_structure method.

Covers: model invariants, form validation, view CRUD, multi-tenant IDOR, delete
guards, org-chart cycle safety, and seeder idempotency.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ============================================================ shared helpers
def _run_seeder(flush=False):
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    call_command("seed_hrm", flush=flush, stdout=out, stderr=out)
    return out.getvalue()


# ============================================================ org-structure fixtures
@pytest.fixture
def job_grade_a(db, tenant_a):
    from apps.hrm.models import JobGrade
    return JobGrade.objects.create(
        tenant=tenant_a, name="G1 — Junior", level_order=1,
        description="Entry-level", is_active=True,
    )


@pytest.fixture
def job_grade_a2(db, tenant_a):
    """A second (higher) grade for tenant_a — used in ordering / band tests."""
    from apps.hrm.models import JobGrade
    return JobGrade.objects.create(
        tenant=tenant_a, name="G3 — Senior", level_order=3,
        description="Senior IC", is_active=True,
    )


@pytest.fixture
def job_grade_b(db, tenant_b):
    from apps.hrm.models import JobGrade
    return JobGrade.objects.create(
        tenant=tenant_b, name="B1 — Junior", level_order=1,
    )


@pytest.fixture
def designation_with_grade(db, tenant_a, job_grade_a):
    """A Designation whose grade field is linked to a JobGrade (not just free-text)."""
    from apps.hrm.models import Designation
    return Designation.objects.create(
        tenant=tenant_a,
        name="Junior Developer",
        job_grade=job_grade_a,
        grade="",
        min_salary=Decimal("50000"),
        mid_salary=Decimal("65000"),
        max_salary=Decimal("80000"),
        budgeted_headcount=5,
    )


@pytest.fixture
def cc_unit_a(db, tenant_a):
    """An OrgUnit of kind=cost_center for tenant_a."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, kind="cost_center", name="Engineering CC")


@pytest.fixture
def cc_unit_b(db, tenant_b):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_b, kind="cost_center", name="Engineering CC B")


@pytest.fixture
def dept_profile_a(db, tenant_a, dept_a):
    """A DepartmentProfile for dept_a (tenant_a), no head / CC yet."""
    from apps.hrm.models import DepartmentProfile
    return DepartmentProfile.objects.create(
        tenant=tenant_a, org_unit=dept_a, code="ENG",
        description="Engineering dept.", is_active=True,
    )


@pytest.fixture
def dept_profile_b(db, tenant_b, dept_b):
    from apps.hrm.models import DepartmentProfile
    return DepartmentProfile.objects.create(
        tenant=tenant_b, org_unit=dept_b, code="ENGB", is_active=True,
    )


@pytest.fixture
def cc_profile_a(db, tenant_a, cc_unit_a):
    from apps.hrm.models import CostCenterProfile
    return CostCenterProfile.objects.create(
        tenant=tenant_a, org_unit=cc_unit_a, code="ENGC",
        budget_annual=Decimal("500000"), budget_year=2026, is_active=True,
    )


@pytest.fixture
def cc_profile_b(db, tenant_b, cc_unit_b):
    from apps.hrm.models import CostCenterProfile
    return CostCenterProfile.objects.create(
        tenant=tenant_b, org_unit=cc_unit_b, code="ENGCB", is_active=True,
    )


# ============================================================ 1. Model invariants
class TestJobGradeModel:
    def test_str_includes_name_and_level(self, job_grade_a):
        s = str(job_grade_a)
        assert "G1 — Junior" in s
        assert "L1" in s

    def test_str_format(self, job_grade_a):
        assert str(job_grade_a) == "G1 — Junior (L1)"

    def test_ordering_by_level_order(self, tenant_a, job_grade_a, job_grade_a2):
        from apps.hrm.models import JobGrade
        grades = list(JobGrade.objects.filter(tenant=tenant_a).values_list("level_order", flat=True))
        assert grades == sorted(grades)

    def test_unique_together_tenant_name(self, tenant_a, job_grade_a):
        from apps.hrm.models import JobGrade
        with pytest.raises(IntegrityError):
            JobGrade.objects.create(tenant=tenant_a, name="G1 — Junior", level_order=99)

    def test_is_active_default_true(self, tenant_a):
        from apps.hrm.models import JobGrade
        g = JobGrade.objects.create(tenant=tenant_a, name="G99", level_order=99)
        assert g.is_active is True

    def test_level_order_default_one(self, tenant_a):
        from apps.hrm.models import JobGrade
        g = JobGrade.objects.create(tenant=tenant_a, name="G98")
        assert g.level_order == 1


class TestDesignationEnhancedModel:
    def test_str_prefers_job_grade_name_over_free_text(self, designation_with_grade, job_grade_a):
        """__str__ should use job_grade.name, not the free-text `grade` field."""
        s = str(designation_with_grade)
        assert "Junior Developer" in s
        # Job grade name must appear, NOT a stale free-text grade
        assert "G1 — Junior" in s

    def test_str_falls_back_to_free_text_grade(self, tenant_a):
        """When no JobGrade FK is set, __str__ uses the free-text `grade` field."""
        from apps.hrm.models import Designation
        d = Designation.objects.create(tenant=tenant_a, name="Analyst", grade="L5")
        assert "L5" in str(d)

    def test_str_no_grade_at_all(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation.objects.create(tenant=tenant_a, name="Solo Role", grade="")
        assert str(d) == "Solo Role"

    def test_clean_band_min_gt_max_raises(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(
            tenant=tenant_a, name="Bad Band",
            min_salary=Decimal("100000"), max_salary=Decimal("50000"),
        )
        with pytest.raises(ValidationError) as exc:
            d.clean()
        assert "max_salary" in exc.value.message_dict

    def test_clean_band_mid_lt_min_raises(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(
            tenant=tenant_a, name="Mid Low",
            min_salary=Decimal("60000"),
            mid_salary=Decimal("55000"),
            max_salary=Decimal("90000"),
        )
        with pytest.raises(ValidationError) as exc:
            d.clean()
        assert "mid_salary" in exc.value.message_dict

    def test_clean_band_mid_gt_max_raises(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(
            tenant=tenant_a, name="Mid High",
            min_salary=Decimal("60000"),
            mid_salary=Decimal("95000"),
            max_salary=Decimal("90000"),
        )
        with pytest.raises(ValidationError) as exc:
            d.clean()
        assert "mid_salary" in exc.value.message_dict

    def test_clean_valid_band_passes(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(
            tenant=tenant_a, name="Good Band",
            min_salary=Decimal("60000"),
            mid_salary=Decimal("75000"),
            max_salary=Decimal("90000"),
        )
        d.clean()  # must not raise

    def test_clean_none_values_pass(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(tenant=tenant_a, name="No Band")
        d.clean()  # must not raise

    def test_budgeted_headcount_optional(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation.objects.create(tenant=tenant_a, name="HC None")
        assert d.budgeted_headcount is None

    def test_job_grade_fk_set_null_on_grade_delete(self, tenant_a, designation_with_grade, job_grade_a):
        """Deleting a JobGrade must SET_NULL on linked Designations (not cascade)."""
        pk = designation_with_grade.pk
        job_grade_a.delete()
        from apps.hrm.models import Designation
        d = Designation.objects.get(pk=pk)
        assert d.job_grade_id is None


class TestDepartmentProfileModel:
    def test_str_with_code(self, dept_profile_a):
        assert "Engineering" in str(dept_profile_a)
        assert "ENG" in str(dept_profile_a)

    def test_str_without_code(self, tenant_a, dept_a):
        from apps.hrm.models import DepartmentProfile
        dp = DepartmentProfile.objects.create(tenant=tenant_a, org_unit=dept_a, code="")
        assert str(dp) == dept_a.name

    def test_clean_rejects_non_department_org_unit(self, tenant_a, cc_unit_a):
        """org_unit whose kind != 'department' must raise ValidationError."""
        from apps.hrm.models import DepartmentProfile
        dp = DepartmentProfile(tenant=tenant_a, org_unit=cc_unit_a)
        with pytest.raises(ValidationError) as exc:
            dp.clean()
        assert "org_unit" in exc.value.message_dict

    def test_clean_accepts_department_org_unit(self, tenant_a, dept_a):
        from apps.hrm.models import DepartmentProfile
        dp = DepartmentProfile(tenant=tenant_a, org_unit=dept_a)
        dp.clean()  # must not raise

    def test_one_to_one_uniqueness(self, tenant_a, dept_a, dept_profile_a):
        """Creating a second DepartmentProfile for the same org_unit must be rejected."""
        from apps.hrm.models import DepartmentProfile
        with pytest.raises(IntegrityError):
            DepartmentProfile.objects.create(tenant=tenant_a, org_unit=dept_a, code="DUP")


class TestCostCenterProfileModel:
    def test_str_with_code(self, cc_profile_a, cc_unit_a):
        s = str(cc_profile_a)
        assert "Engineering CC" in s
        assert "ENGC" in s

    def test_clean_rejects_non_cost_center_org_unit(self, tenant_a, dept_a):
        """org_unit whose kind != 'cost_center' must raise ValidationError."""
        from apps.hrm.models import CostCenterProfile
        ccp = CostCenterProfile(tenant=tenant_a, org_unit=dept_a)
        with pytest.raises(ValidationError) as exc:
            ccp.clean()
        assert "org_unit" in exc.value.message_dict

    def test_clean_accepts_cost_center_org_unit(self, tenant_a, cc_unit_a):
        from apps.hrm.models import CostCenterProfile
        ccp = CostCenterProfile(tenant=tenant_a, org_unit=cc_unit_a)
        ccp.clean()  # must not raise

    def test_one_to_one_uniqueness(self, tenant_a, cc_unit_a, cc_profile_a):
        """Creating a second CostCenterProfile for the same org_unit must be rejected."""
        from apps.hrm.models import CostCenterProfile
        with pytest.raises(IntegrityError):
            CostCenterProfile.objects.create(tenant=tenant_a, org_unit=cc_unit_a, code="DUP")


# ============================================================ 2. Form validation
class TestDepartmentProfileForm:
    def test_org_unit_queryset_scoped_to_dept_kind(self, tenant_a, dept_a, cc_unit_a):
        """Form must only offer OrgUnits of kind=department for the tenant."""
        from apps.hrm.forms import DepartmentProfileForm
        form = DepartmentProfileForm(tenant=tenant_a)
        qs = form.fields["org_unit"].queryset
        assert dept_a in qs
        assert cc_unit_a not in qs  # cost_center kind excluded

    def test_org_unit_scoped_to_own_tenant(self, tenant_a, tenant_b, dept_a, dept_b):
        """Form must not offer another tenant's departments."""
        from apps.hrm.forms import DepartmentProfileForm
        form = DepartmentProfileForm(tenant=tenant_a)
        qs = form.fields["org_unit"].queryset
        assert dept_a in qs
        assert dept_b not in qs

    def test_head_queryset_scoped_to_tenant(self, tenant_a, employee_a, employee_b):
        """head queryset must only include employee profiles of the form's tenant."""
        from apps.hrm.forms import DepartmentProfileForm
        form = DepartmentProfileForm(tenant=tenant_a)
        qs = form.fields["head"].queryset
        assert employee_a in qs
        assert employee_b not in qs

    def test_cost_center_queryset_scoped_to_tenant(self, tenant_a, cc_unit_a, cc_unit_b):
        """cost_center queryset must only include cost-center OrgUnits of this tenant."""
        from apps.hrm.forms import DepartmentProfileForm
        form = DepartmentProfileForm(tenant=tenant_a)
        qs = form.fields["cost_center"].queryset
        assert cc_unit_a in qs
        assert cc_unit_b not in qs

    def test_submit_other_tenant_org_unit_invalid(self, tenant_a, dept_b):
        """Submitting another tenant's org_unit pk via POST must be rejected (not in queryset)."""
        from apps.hrm.forms import DepartmentProfileForm
        data = {"org_unit": str(dept_b.pk), "code": "X", "is_active": True}
        form = DepartmentProfileForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "org_unit" in form.errors

    def test_tenant_not_a_form_field(self):
        from apps.hrm.forms import DepartmentProfileForm
        form = DepartmentProfileForm(tenant=None)
        assert "tenant" not in form.fields

    def test_org_unit_unique_restriction_in_form(self, tenant_a, dept_a, dept_profile_a):
        """If dept_a already has a profile, the org_unit field queryset excludes it
        for a new (non-instance) form."""
        from apps.hrm.forms import DepartmentProfileForm
        form = DepartmentProfileForm(tenant=tenant_a)
        # dept_a already has a profile, so it should be excluded from new-instance form
        assert dept_a not in form.fields["org_unit"].queryset


class TestCostCenterProfileForm:
    def test_org_unit_queryset_scoped_to_cc_kind(self, tenant_a, cc_unit_a, dept_a):
        from apps.hrm.forms import CostCenterProfileForm
        form = CostCenterProfileForm(tenant=tenant_a)
        qs = form.fields["org_unit"].queryset
        assert cc_unit_a in qs
        assert dept_a not in qs

    def test_org_unit_scoped_to_own_tenant(self, tenant_a, cc_unit_a, cc_unit_b):
        from apps.hrm.forms import CostCenterProfileForm
        form = CostCenterProfileForm(tenant=tenant_a)
        qs = form.fields["org_unit"].queryset
        assert cc_unit_a in qs
        assert cc_unit_b not in qs

    def test_owner_queryset_scoped_to_tenant(self, tenant_a, employee_a, employee_b):
        from apps.hrm.forms import CostCenterProfileForm
        form = CostCenterProfileForm(tenant=tenant_a)
        qs = form.fields["owner"].queryset
        assert employee_a in qs
        assert employee_b not in qs

    def test_submit_other_tenant_org_unit_invalid(self, tenant_a, cc_unit_b):
        from apps.hrm.forms import CostCenterProfileForm
        data = {"org_unit": str(cc_unit_b.pk), "code": "X", "is_active": True}
        form = CostCenterProfileForm(data=data, tenant=tenant_a)
        assert not form.is_valid()
        assert "org_unit" in form.errors

    def test_tenant_not_a_form_field(self):
        from apps.hrm.forms import CostCenterProfileForm
        form = CostCenterProfileForm(tenant=None)
        assert "tenant" not in form.fields


class TestDesignationForm:
    def test_job_grade_field_present(self, tenant_a, job_grade_a):
        from apps.hrm.forms import DesignationForm
        form = DesignationForm(tenant=tenant_a)
        assert "job_grade" in form.fields

    def test_mid_salary_field_present(self, tenant_a):
        from apps.hrm.forms import DesignationForm
        form = DesignationForm(tenant=tenant_a)
        assert "mid_salary" in form.fields

    def test_budgeted_headcount_field_present(self, tenant_a):
        from apps.hrm.forms import DesignationForm
        form = DesignationForm(tenant=tenant_a)
        assert "budgeted_headcount" in form.fields

    def test_job_grade_queryset_active_only(self, tenant_a, job_grade_a):
        """Inactive grades must be excluded from the job_grade field."""
        from apps.hrm.models import JobGrade
        from apps.hrm.forms import DesignationForm
        inactive = JobGrade.objects.create(
            tenant=tenant_a, name="Inactive Grade", level_order=99, is_active=False
        )
        form = DesignationForm(tenant=tenant_a)
        qs = form.fields["job_grade"].queryset
        assert job_grade_a in qs
        assert inactive not in qs

    def test_job_grade_queryset_tenant_scoped(self, tenant_a, tenant_b, job_grade_a, job_grade_b):
        from apps.hrm.forms import DesignationForm
        form = DesignationForm(tenant=tenant_a)
        qs = form.fields["job_grade"].queryset
        assert job_grade_a in qs
        assert job_grade_b not in qs

    def test_tenant_not_a_form_field(self):
        from apps.hrm.forms import DesignationForm
        form = DesignationForm(tenant=None)
        assert "tenant" not in form.fields


# ============================================================ 3. View / CRUD integration
class TestJobGradeViews:
    def test_list_200(self, client_a, job_grade_a):
        resp = client_a.get(reverse("hrm:jobgrade_list"))
        assert resp.status_code == 200

    def test_list_shows_own_tenant(self, client_a, job_grade_a):
        resp = client_a.get(reverse("hrm:jobgrade_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert job_grade_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, job_grade_a, job_grade_b):
        resp = client_a.get(reverse("hrm:jobgrade_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert job_grade_b.pk not in pks

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:jobgrade_create"))
        assert resp.status_code == 200

    def test_create_post_saves_with_tenant(self, client_a, tenant_a):
        from apps.hrm.models import JobGrade
        resp = client_a.post(reverse("hrm:jobgrade_create"), {
            "name": "G2 — Mid",
            "level_order": "2",
            "description": "Mid-level",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert JobGrade.objects.filter(tenant=tenant_a, name="G2 — Mid").exists()

    def test_create_post_tenant_cannot_be_spoofed(self, client_a, tenant_a, tenant_b):
        """Even if the form includes a tenant field override, the row belongs to tenant_a."""
        from apps.hrm.models import JobGrade
        client_a.post(reverse("hrm:jobgrade_create"), {
            "name": "Spoof Grade",
            "level_order": "1",
            "tenant": str(tenant_b.pk),  # attempt spoof
            "is_active": "on",
        })
        assert not JobGrade.objects.filter(tenant=tenant_b, name="Spoof Grade").exists()
        assert JobGrade.objects.filter(tenant=tenant_a, name="Spoof Grade").exists()

    def test_detail_200(self, client_a, job_grade_a):
        resp = client_a.get(reverse("hrm:jobgrade_detail", args=[job_grade_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, job_grade_a):
        resp = client_a.get(reverse("hrm:jobgrade_detail", args=[job_grade_a.pk]))
        assert resp.context["obj"].pk == job_grade_a.pk

    def test_edit_get_200(self, client_a, job_grade_a):
        resp = client_a.get(reverse("hrm:jobgrade_edit", args=[job_grade_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, job_grade_a):
        from apps.hrm.models import JobGrade
        resp = client_a.post(reverse("hrm:jobgrade_edit", args=[job_grade_a.pk]), {
            "name": "G1 — Junior",
            "level_order": "1",
            "description": "Updated description",
            "is_active": "on",
        })
        assert resp.status_code == 302
        job_grade_a.refresh_from_db()
        assert job_grade_a.description == "Updated description"

    def test_delete_post_removes(self, client_a, job_grade_a):
        from apps.hrm.models import JobGrade
        pk = job_grade_a.pk
        resp = client_a.post(reverse("hrm:jobgrade_delete", args=[pk]))
        assert resp.status_code == 302
        assert not JobGrade.objects.filter(pk=pk).exists()

    def test_anon_list_redirect(self, client):
        resp = client.get(reverse("hrm:jobgrade_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestDepartmentViews:
    def test_list_200(self, client_a, dept_profile_a):
        resp = client_a.get(reverse("hrm:department_list"))
        assert resp.status_code == 200

    def test_list_shows_own_tenant(self, client_a, dept_profile_a):
        resp = client_a.get(reverse("hrm:department_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert dept_profile_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, dept_profile_a, dept_profile_b):
        resp = client_a.get(reverse("hrm:department_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert dept_profile_b.pk not in pks

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:department_create"))
        assert resp.status_code == 200

    def test_create_post_saves_with_tenant(self, client_a, tenant_a, dept_a, dept_profile_a):
        """Create a second OrgUnit and profile for it."""
        from apps.core.models import OrgUnit
        from apps.hrm.models import DepartmentProfile
        unit = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="HR Dept")
        resp = client_a.post(reverse("hrm:department_create"), {
            "org_unit": str(unit.pk),
            "code": "HR",
            "description": "Human Resources",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert DepartmentProfile.objects.filter(tenant=tenant_a, org_unit=unit).exists()

    def test_detail_200(self, client_a, dept_profile_a):
        resp = client_a.get(reverse("hrm:department_detail", args=[dept_profile_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, dept_profile_a):
        resp = client_a.get(reverse("hrm:department_detail", args=[dept_profile_a.pk]))
        assert resp.context["obj"].pk == dept_profile_a.pk

    def test_edit_get_200(self, client_a, dept_profile_a):
        resp = client_a.get(reverse("hrm:department_edit", args=[dept_profile_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_code(self, client_a, tenant_a, dept_a, dept_profile_a):
        resp = client_a.post(reverse("hrm:department_edit", args=[dept_profile_a.pk]), {
            "org_unit": str(dept_a.pk),
            "code": "ENGX",
            "description": "Updated",
            "is_active": "on",
        })
        assert resp.status_code == 302
        dept_profile_a.refresh_from_db()
        assert dept_profile_a.code == "ENGX"

    def test_delete_post_removes(self, client_a, dept_profile_a):
        from apps.hrm.models import DepartmentProfile
        pk = dept_profile_a.pk
        resp = client_a.post(reverse("hrm:department_delete", args=[pk]))
        assert resp.status_code == 302
        assert not DepartmentProfile.objects.filter(pk=pk).exists()

    def test_anon_list_redirect(self, client):
        resp = client.get(reverse("hrm:department_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCostCenterViews:
    def test_list_200(self, client_a, cc_profile_a):
        resp = client_a.get(reverse("hrm:costcenter_list"))
        assert resp.status_code == 200

    def test_list_shows_own_tenant(self, client_a, cc_profile_a):
        resp = client_a.get(reverse("hrm:costcenter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert cc_profile_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, cc_profile_a, cc_profile_b):
        resp = client_a.get(reverse("hrm:costcenter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert cc_profile_b.pk not in pks

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:costcenter_create"))
        assert resp.status_code == 200

    def test_create_post_saves_with_tenant(self, client_a, tenant_a):
        from apps.core.models import OrgUnit
        from apps.hrm.models import CostCenterProfile
        unit = OrgUnit.objects.create(tenant=tenant_a, kind="cost_center", name="Ops CC")
        resp = client_a.post(reverse("hrm:costcenter_create"), {
            "org_unit": str(unit.pk),
            "code": "OPSC",
            "description": "Operations CC",
            "budget_annual": "500000",
            "budget_year": "2026",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert CostCenterProfile.objects.filter(tenant=tenant_a, org_unit=unit).exists()

    def test_detail_200(self, client_a, cc_profile_a):
        resp = client_a.get(reverse("hrm:costcenter_detail", args=[cc_profile_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_obj(self, client_a, cc_profile_a):
        resp = client_a.get(reverse("hrm:costcenter_detail", args=[cc_profile_a.pk]))
        assert resp.context["obj"].pk == cc_profile_a.pk

    def test_edit_get_200(self, client_a, cc_profile_a):
        resp = client_a.get(reverse("hrm:costcenter_edit", args=[cc_profile_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_code(self, client_a, tenant_a, cc_unit_a, cc_profile_a):
        resp = client_a.post(reverse("hrm:costcenter_edit", args=[cc_profile_a.pk]), {
            "org_unit": str(cc_unit_a.pk),
            "code": "ENGC2",
            "description": "Updated CC",
            "budget_annual": "600000",
            "budget_year": "2026",
            "is_active": "on",
        })
        assert resp.status_code == 302
        cc_profile_a.refresh_from_db()
        assert cc_profile_a.code == "ENGC2"

    def test_delete_post_removes(self, client_a, cc_profile_a):
        from apps.hrm.models import CostCenterProfile
        pk = cc_profile_a.pk
        resp = client_a.post(reverse("hrm:costcenter_delete", args=[pk]))
        assert resp.status_code == 302
        assert not CostCenterProfile.objects.filter(pk=pk).exists()

    def test_anon_list_redirect(self, client):
        resp = client.get(reverse("hrm:costcenter_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestOrgChartView:
    def test_reporting_view_200(self, client_a):
        resp = client_a.get(reverse("hrm:org_chart") + "?view=reporting")
        assert resp.status_code == 200

    def test_department_view_200(self, client_a):
        resp = client_a.get(reverse("hrm:org_chart") + "?view=department")
        assert resp.status_code == 200

    def test_default_mode_is_reporting(self, client_a):
        resp = client_a.get(reverse("hrm:org_chart"))
        assert resp.context["view_mode"] == "reporting"

    def test_department_mode_from_param(self, client_a):
        resp = client_a.get(reverse("hrm:org_chart") + "?view=department")
        assert resp.context["view_mode"] == "department"

    def test_context_keys_present(self, client_a):
        resp = client_a.get(reverse("hrm:org_chart"))
        for key in ("tree_nodes", "dept_groups", "view_mode", "total", "capped"):
            assert key in resp.context

    def test_anon_redirect(self, client):
        resp = client.get(reverse("hrm:org_chart"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestCompanySetupView:
    def test_company_setup_200(self, client_a):
        resp = client_a.get(reverse("hrm:company_setup"))
        assert resp.status_code == 200

    def test_company_setup_context_keys(self, client_a):
        resp = client_a.get(reverse("hrm:company_setup"))
        for key in ("company_unit", "branding", "departments", "cost_centers"):
            assert key in resp.context

    def test_anon_redirect(self, client):
        resp = client.get(reverse("hrm:company_setup"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================ 3. Delete guards
class TestJobGradeDeleteGuard:
    def test_delete_blocked_when_designation_references_grade(
        self, client_a, tenant_a, job_grade_a, dept_a
    ):
        """jobgrade_delete must redirect with an error (not delete) when a Designation uses the grade."""
        from apps.hrm.models import Designation
        Designation.objects.create(
            tenant=tenant_a, name="Uses Grade", job_grade=job_grade_a,
        )
        resp = client_a.post(reverse("hrm:jobgrade_delete", args=[job_grade_a.pk]))
        # Should redirect back to the detail (not to the list after deletion)
        assert resp.status_code == 302
        # Grade must still exist
        from apps.hrm.models import JobGrade
        assert JobGrade.objects.filter(pk=job_grade_a.pk).exists()

    def test_delete_redirects_to_detail_when_blocked(self, client_a, tenant_a, job_grade_a):
        """Blocked delete must redirect to the grade detail page."""
        from apps.hrm.models import Designation
        Designation.objects.create(tenant=tenant_a, name="Blocks Grade", job_grade=job_grade_a)
        resp = client_a.post(reverse("hrm:jobgrade_delete", args=[job_grade_a.pk]))
        assert "job-grades" in resp["Location"] and str(job_grade_a.pk) in resp["Location"]


class TestDepartmentDeleteGuard:
    def test_delete_blocked_when_active_employment_in_org_unit(
        self, client_a, dept_profile_a, employment_a
    ):
        """department_delete must refuse when an active Employment is in the OrgUnit."""
        from apps.hrm.models import DepartmentProfile
        pk = dept_profile_a.pk
        resp = client_a.post(reverse("hrm:department_delete", args=[pk]))
        assert resp.status_code == 302
        # Profile must still exist
        assert DepartmentProfile.objects.filter(pk=pk).exists()


class TestCostCenterDeleteGuard:
    def test_delete_blocked_when_department_mapped(
        self, client_a, cc_profile_a, dept_a, dept_profile_a, tenant_a
    ):
        """costcenter_delete must refuse when a DepartmentProfile maps to this CC."""
        from apps.hrm.models import DepartmentProfile, CostCenterProfile
        # Map the existing dept_profile to this cost center
        dept_profile_a.cost_center = cc_profile_a.org_unit
        dept_profile_a.save()

        pk = cc_profile_a.pk
        resp = client_a.post(reverse("hrm:costcenter_delete", args=[pk]))
        assert resp.status_code == 302
        # Profile must still exist
        assert CostCenterProfile.objects.filter(pk=pk).exists()


# ============================================================ 4. Org-chart correctness
class TestOrgChartCycleSafety:
    def test_mutual_managers_no_infinite_loop(self, client_a, tenant_a, person_a, person_a2):
        """Two employees who manage each other must not cause RecursionError / infinite loop.
        The view must return 200 and both employees appear exactly once in tree_nodes."""
        from apps.core.models import Employment, Party
        from apps.hrm.models import EmployeeProfile, Designation

        dept = __import__("apps.core.models", fromlist=["OrgUnit"]).OrgUnit.objects.create(
            tenant=tenant_a, kind="department", name="CycleDept"
        )

        # emp1's manager = person_a2 (emp2's party); emp2's manager = person_a (emp1's party)
        emp1_employment = Employment.objects.create(
            tenant=tenant_a, party=person_a, org_unit=dept,
            manager=person_a2,  # person_a2 is the manager
            status="active",
        )
        emp2_employment = Employment.objects.create(
            tenant=tenant_a, party=person_a2, org_unit=dept,
            manager=person_a,   # person_a is the manager (cycle!)
            status="active",
        )
        emp1 = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a, employment=emp1_employment,
        )
        emp2 = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employment=emp2_employment,
        )

        resp = client_a.get(reverse("hrm:org_chart"))
        assert resp.status_code == 200

        tree_nodes = resp.context["tree_nodes"]
        emp_pks = [node["emp"].pk for node in tree_nodes]
        # Both employees must appear exactly once
        assert emp_pks.count(emp1.pk) == 1
        assert emp_pks.count(emp2.pk) == 1

    def test_terminated_employees_excluded(self, client_a, tenant_a, person_a):
        """Employees with terminated employment must not appear on the org chart."""
        from apps.core.models import Employment
        from apps.hrm.models import EmployeeProfile

        dept = __import__("apps.core.models", fromlist=["OrgUnit"]).OrgUnit.objects.create(
            tenant=tenant_a, kind="department", name="TerminationDept"
        )
        emp_empl = Employment.objects.create(
            tenant=tenant_a, party=person_a, org_unit=dept, status="terminated"
        )
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a, employment=emp_empl,
        )

        resp = client_a.get(reverse("hrm:org_chart"))
        assert resp.status_code == 200
        tree_pks = [node["emp"].pk for node in resp.context["tree_nodes"]]
        assert emp.pk not in tree_pks


# ============================================================ 5. Multi-tenant IDOR
class TestJobGradeIDOR:
    def test_detail_cross_tenant_404(self, client_a, job_grade_b):
        resp = client_a.get(reverse("hrm:jobgrade_detail", args=[job_grade_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, job_grade_b):
        resp = client_a.get(reverse("hrm:jobgrade_edit", args=[job_grade_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, job_grade_b):
        resp = client_a.post(reverse("hrm:jobgrade_edit", args=[job_grade_b.pk]), {
            "name": "Hijacked",
            "level_order": "1",
            "is_active": "on",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, job_grade_b):
        resp = client_a.post(reverse("hrm:jobgrade_delete", args=[job_grade_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_grades(self, client_a, job_grade_a, job_grade_b):
        resp = client_a.get(reverse("hrm:jobgrade_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert job_grade_a.pk in pks
        assert job_grade_b.pk not in pks


class TestDepartmentProfileIDOR:
    def test_detail_cross_tenant_404(self, client_a, dept_profile_b):
        resp = client_a.get(reverse("hrm:department_detail", args=[dept_profile_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, dept_profile_b):
        resp = client_a.get(reverse("hrm:department_edit", args=[dept_profile_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, dept_profile_b):
        resp = client_a.post(reverse("hrm:department_delete", args=[dept_profile_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_profiles(self, client_a, dept_profile_a, dept_profile_b):
        resp = client_a.get(reverse("hrm:department_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert dept_profile_a.pk in pks
        assert dept_profile_b.pk not in pks


class TestCostCenterProfileIDOR:
    def test_detail_cross_tenant_404(self, client_a, cc_profile_b):
        resp = client_a.get(reverse("hrm:costcenter_detail", args=[cc_profile_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, cc_profile_b):
        resp = client_a.get(reverse("hrm:costcenter_edit", args=[cc_profile_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, cc_profile_b):
        resp = client_a.post(reverse("hrm:costcenter_delete", args=[cc_profile_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_profiles(self, client_a, cc_profile_a, cc_profile_b):
        resp = client_a.get(reverse("hrm:costcenter_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert cc_profile_a.pk in pks
        assert cc_profile_b.pk not in pks


class TestDesignationOrg32IDOR:
    """IDOR for the enhanced Designation (new job_grade FK, org-structure context)."""

    def _make_desig_b(self, tenant_b):
        from apps.hrm.models import Designation
        return Designation.objects.create(tenant=tenant_b, name="Tenant B Role", grade="B1")

    def test_detail_cross_tenant_404(self, client_a, tenant_b):
        desig_b = self._make_desig_b(tenant_b)
        resp = client_a.get(reverse("hrm:designation_detail", args=[desig_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, tenant_b):
        desig_b = self._make_desig_b(tenant_b)
        resp = client_a.get(reverse("hrm:designation_edit", args=[desig_b.pk]))
        assert resp.status_code == 404


# ============================================================ 6. Seeder idempotency
class TestSeedOrgStructureIdempotency:
    def test_job_grades_created(self, tenant_a):
        from apps.hrm.models import JobGrade
        _run_seeder()
        assert JobGrade.objects.filter(tenant=tenant_a).count() == 5

    def test_double_run_yields_same_grade_count(self, tenant_a):
        from apps.hrm.models import JobGrade
        _run_seeder()
        c1 = JobGrade.objects.filter(tenant=tenant_a).count()
        _run_seeder()
        c2 = JobGrade.objects.filter(tenant=tenant_a).count()
        assert c1 == c2, f"Second run duplicated job grades: {c1} → {c2}"

    def test_exactly_5_job_grades_after_double_run(self, tenant_a):
        """Must be exactly 5, not 10 after two runs."""
        from apps.hrm.models import JobGrade
        _run_seeder()
        _run_seeder()
        assert JobGrade.objects.filter(tenant=tenant_a).count() == 5

    def test_cost_center_org_units_created(self, tenant_a):
        from apps.core.models import OrgUnit
        _run_seeder()
        assert OrgUnit.objects.filter(tenant=tenant_a, kind="cost_center").count() == 2

    def test_cost_center_profiles_created(self, tenant_a):
        from apps.hrm.models import CostCenterProfile
        _run_seeder()
        assert CostCenterProfile.objects.filter(tenant=tenant_a).count() == 2

    def test_double_run_yields_same_cc_profile_count(self, tenant_a):
        from apps.hrm.models import CostCenterProfile
        _run_seeder()
        c1 = CostCenterProfile.objects.filter(tenant=tenant_a).count()
        _run_seeder()
        c2 = CostCenterProfile.objects.filter(tenant=tenant_a).count()
        assert c1 == c2

    def test_department_profiles_created(self, tenant_a):
        """After seeding, at least one DepartmentProfile must exist for each dept OrgUnit."""
        from apps.core.models import OrgUnit
        from apps.hrm.models import DepartmentProfile
        _run_seeder()
        dept_count = OrgUnit.objects.filter(tenant=tenant_a, kind="department").count()
        prof_count = DepartmentProfile.objects.filter(tenant=tenant_a).count()
        # Every existing department OrgUnit should have a profile
        assert prof_count == dept_count

    def test_double_run_yields_same_dept_profile_count(self, tenant_a):
        from apps.hrm.models import DepartmentProfile
        _run_seeder()
        c1 = DepartmentProfile.objects.filter(tenant=tenant_a).count()
        _run_seeder()
        c2 = DepartmentProfile.objects.filter(tenant=tenant_a).count()
        assert c1 == c2

    def test_designation_grade_linked_after_seed(self, tenant_a):
        """After seeding, at least one Designation must have a non-null job_grade."""
        from apps.hrm.models import Designation
        _run_seeder()
        assert Designation.objects.filter(
            tenant=tenant_a, job_grade__isnull=False
        ).exists()


# ============================================================ 7. Query budget
class TestQueryBudget:
    @pytest.mark.django_db
    def test_costcenter_detail_bounded_queries(self, client_a, cc_profile_a, django_assert_max_num_queries):
        """costcenter_detail should not cause excessive queries (no N+1 on mapped departments)."""
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("hrm:costcenter_detail", args=[cc_profile_a.pk]))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_jobgrade_detail_bounded_queries(self, client_a, job_grade_a, django_assert_max_num_queries):
        """jobgrade_detail should not hit unbounded queries."""
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("hrm:jobgrade_detail", args=[job_grade_a.pk]))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_department_detail_bounded_queries(self, client_a, dept_profile_a, django_assert_max_num_queries):
        """department_detail should not cause excessive queries."""
        with django_assert_max_num_queries(15):
            resp = client_a.get(reverse("hrm:department_detail", args=[dept_profile_a.pk]))
        assert resp.status_code == 200
