"""Tests for HRM 3.15 Statutory Compliance views: StatutoryConfig (singleton detail/edit),
StatutoryStateRule CRUD, EmployeeStatutoryIdentifier CRUD (+ masking in templates),
StatutoryReturn CRUD + generate/mark_filed/mark_paid workflow + compliance calendar."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ StatutoryConfig
class TestStatutoryConfigViews:
    def test_detail_200_creates_singleton_lazily(self, client_a, tenant_a):
        from apps.hrm.models import StatutoryConfig
        resp = client_a.get(reverse("hrm:statutoryconfig_detail"))
        assert resp.status_code == 200
        assert StatutoryConfig.objects.filter(tenant=tenant_a).exists()

    def test_detail_context_obj(self, client_a, statutory_config_a):
        resp = client_a.get(reverse("hrm:statutoryconfig_detail"))
        assert resp.context["obj"].pk == statutory_config_a.pk

    def test_edit_get_200_for_tenant_admin(self, client_a, statutory_config_a):
        resp = client_a.get(reverse("hrm:statutoryconfig_edit"))
        assert resp.status_code == 200

    def test_edit_post_updates_by_tenant_admin(self, client_a, statutory_config_a, tenant_a):
        from apps.hrm.models import StatutoryConfig
        resp = client_a.post(reverse("hrm:statutoryconfig_edit"), {
            "pf_establishment_code": "KN/BLR/1234567",
            "pf_wage_ceiling": "15000.00",
            "pf_employee_rate": "12.00",
            "pf_employer_rate": "12.00",
            "esi_employer_code": "",
            "esi_wage_ceiling": "21000.00",
            "esi_employee_rate": "0.75",
            "esi_employer_rate": "3.25",
            "pt_default_state": "Karnataka",
            "tan_number": "BLRT12345A",
            "tds_circle_address": "",
            "pan_of_deductor": "AAACX1234C",
            "is_lwf_applicable": "on",
        })
        assert resp.status_code == 302
        config = StatutoryConfig.for_tenant(tenant_a)
        assert config.pf_establishment_code == "KN/BLR/1234567"
        assert config.tan_number == "BLRT12345A"
        assert config.is_lwf_applicable is True

    def test_edit_get_403_for_non_admin(self, member_client, statutory_config_a):
        resp = member_client.get(reverse("hrm:statutoryconfig_edit"))
        assert resp.status_code == 403

    def test_edit_post_403_for_non_admin(self, member_client, statutory_config_a, tenant_a):
        from apps.hrm.models import StatutoryConfig
        resp = member_client.post(reverse("hrm:statutoryconfig_edit"), {
            "pf_establishment_code": "SNEAKY",
            "pf_wage_ceiling": "15000.00", "pf_employee_rate": "12.00", "pf_employer_rate": "12.00",
            "esi_wage_ceiling": "21000.00", "esi_employee_rate": "0.75", "esi_employer_rate": "3.25",
        })
        assert resp.status_code == 403
        config = StatutoryConfig.for_tenant(tenant_a)
        assert config.pf_establishment_code != "SNEAKY"


# ================================================================ StatutoryStateRule CRUD
class TestStatutoryStateRuleListView:
    def test_list_200(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pt_rule_a.pk in pks

    def test_list_filter_by_scheme(self, client_a, pt_rule_a, lwf_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"), {"scheme": "lwf"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lwf_rule_a.pk in pks
        assert pt_rule_a.pk not in pks

    def test_list_filter_by_state(self, client_a, pt_rule_a, lwf_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"), {"state": "Maharashtra"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lwf_rule_a.pk in pks
        assert pt_rule_a.pk not in pks

    def test_list_search_by_state(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"), {"q": "Karnataka"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pt_rule_a.pk in pks

    def test_list_has_scheme_and_state_choices(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"))
        assert "scheme_choices" in resp.context
        assert "state_choices" in resp.context


class TestStatutoryStateRuleCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_create"))
        assert resp.status_code == 200

    def test_post_creates_pt_rule(self, client_a, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        resp = client_a.post(reverse("hrm:statutorystaterule_create"), {
            "state": "Kerala", "scheme": "pt",
            "income_from": "10000", "income_to": "15000", "pt_monthly_amount": "150",
            "effective_from": "2026-01-01",
        })
        assert resp.status_code == 302
        rule = StatutoryStateRule.objects.filter(tenant=tenant_a, state="Kerala").first()
        assert rule is not None
        assert rule.tenant_id == tenant_a.pk

    def test_post_creates_lwf_rule(self, client_a, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        resp = client_a.post(reverse("hrm:statutorystaterule_create"), {
            "state": "Gujarat", "scheme": "lwf",
            "lwf_employee_contribution": "6", "lwf_employer_contribution": "18",
            "lwf_periodicity": "annual", "effective_from": "2026-01-01",
        })
        assert resp.status_code == 302
        rule = StatutoryStateRule.objects.filter(tenant=tenant_a, state="Gujarat").first()
        assert rule is not None

    def test_post_pt_missing_amount_rejected(self, client_a, tenant_a):
        from apps.hrm.models import StatutoryStateRule
        resp = client_a.post(reverse("hrm:statutorystaterule_create"), {
            "state": "Kerala", "scheme": "pt",
            "income_from": "10000", "income_to": "15000",
            "effective_from": "2026-01-01",
        })
        assert resp.status_code == 200  # re-rendered with form errors
        assert not StatutoryStateRule.objects.filter(tenant=tenant_a, state="Kerala").exists()

    def test_post_second_active_lwf_same_state_via_create_view_is_rejected(
        self, client_a, tenant_a, lwf_rule_a,
    ):
        """A second active LWF rule for the same (tenant, state) is rejected on CREATE via the view.
        ``StatutoryStateRule.clean()``'s active-LWF guard reads ``self.tenant_id``, which is None at
        create-time validation (``crud_create`` sets ``obj.tenant`` only after ``form.is_valid()``), so
        that guard alone would be silently skipped on create. ``StatutoryStateRuleForm.clean()`` closes
        that gap (self.tenant IS available on the form), mirroring the ``StatutoryReturnForm.clean()``
        duplicate-guard pattern. The model.clean() guard still covers the edit path (instance carries a
        real tenant)."""
        from apps.hrm.models import StatutoryStateRule
        before = StatutoryStateRule.objects.filter(
            tenant=tenant_a, state="Maharashtra", scheme="lwf", is_active=True).count()
        resp = client_a.post(reverse("hrm:statutorystaterule_create"), {
            "state": "Maharashtra", "scheme": "lwf",
            "lwf_employee_contribution": "15", "lwf_employer_contribution": "40",
            "lwf_periodicity": "annual", "is_active": "on", "effective_from": "2026-01-01",
        })
        assert resp.status_code == 200  # form re-renders with the validation error, no redirect
        after = StatutoryStateRule.objects.filter(
            tenant=tenant_a, state="Maharashtra", scheme="lwf", is_active=True).count()
        assert after == before  # no second active LWF rule was created


class TestStatutoryStateRuleDetailEditDelete:
    def test_detail_200(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_detail", args=[pt_rule_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_edit", args=[pt_rule_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, pt_rule_a):
        resp = client_a.post(reverse("hrm:statutorystaterule_edit", args=[pt_rule_a.pk]), {
            "state": "Karnataka", "scheme": "pt",
            "income_from": "15000", "income_to": "20000", "pt_monthly_amount": "300",
            "effective_from": "2026-01-01",
        })
        assert resp.status_code == 302
        pt_rule_a.refresh_from_db()
        assert pt_rule_a.pt_monthly_amount == Decimal("300")

    def test_delete_post_removes(self, client_a, pt_rule_a):
        from apps.hrm.models import StatutoryStateRule
        pk = pt_rule_a.pk
        resp = client_a.post(reverse("hrm:statutorystaterule_delete", args=[pk]))
        assert resp.status_code == 302
        assert not StatutoryStateRule.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, pt_rule_a):
        resp = client_a.get(reverse("hrm:statutorystaterule_delete", args=[pt_rule_a.pk]))
        assert resp.status_code == 405


# ================================================================ EmployeeStatutoryIdentifier CRUD
class TestEmployeeStatutoryIdentifierListView:
    def test_list_200(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert statutory_identifier_a.pk in pks

    def test_list_masks_uan_not_full_value(self, client_a, statutory_identifier_a):
        """Security: the rendered list HTML must show the masked value, never the raw UAN."""
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"))
        content = resp.content.decode()
        assert statutory_identifier_a.uan_number not in content
        assert statutory_identifier_a.masked_uan_number() in content

    def test_list_filter_by_pt_state(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"), {"pt_state": "Karnataka"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert statutory_identifier_a.pk in pks

    def test_list_has_state_choices(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"))
        assert "state_choices" in resp.context


class TestEmployeeStatutoryIdentifierCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import EmployeeStatutoryIdentifier
        resp = client_a.post(reverse("hrm:employeestatutoryidentifier_create"), {
            "employee": employee_a.pk, "uan_number": "111122223333",
            "pf_number": "KN/BLR/000999", "esi_number": "3111111111",
            "pt_state": "Karnataka", "is_pf_applicable": "on", "is_esi_applicable": "on",
        })
        assert resp.status_code == 302
        ident = EmployeeStatutoryIdentifier.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert ident is not None
        assert ident.tenant_id == tenant_a.pk

    def test_create_form_excludes_employees_with_existing_identifier(
        self, client_a, employee_a, statutory_identifier_a,
    ):
        """employee_a already has statutory_identifier_a — the create form must not offer it again
        (OneToOne collision guard)."""
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_create"))
        form = resp.context["form"]
        assert employee_a.pk not in form.fields["employee"].queryset.values_list("pk", flat=True)


class TestEmployeeStatutoryIdentifierDetailEditDelete:
    def test_detail_200(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_detail", args=[statutory_identifier_a.pk]))
        assert resp.status_code == 200

    def test_detail_masks_uan_not_full_value(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_detail", args=[statutory_identifier_a.pk]))
        content = resp.content.decode()
        assert statutory_identifier_a.uan_number not in content
        assert statutory_identifier_a.masked_uan_number() in content
        assert statutory_identifier_a.pf_number not in content
        assert statutory_identifier_a.esi_number not in content

    def test_edit_get_200(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_edit", args=[statutory_identifier_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, statutory_identifier_a):
        resp = client_a.post(
            reverse("hrm:employeestatutoryidentifier_edit", args=[statutory_identifier_a.pk]), {
                "employee": statutory_identifier_a.employee_id,
                "uan_number": "999988887777", "pf_number": statutory_identifier_a.pf_number,
                "esi_number": statutory_identifier_a.esi_number, "pt_state": "Karnataka",
                "is_pf_applicable": "on", "is_esi_applicable": "on",
            })
        assert resp.status_code == 302
        statutory_identifier_a.refresh_from_db()
        assert statutory_identifier_a.uan_number == "999988887777"

    def test_delete_post_removes(self, client_a, statutory_identifier_a):
        from apps.hrm.models import EmployeeStatutoryIdentifier
        pk = statutory_identifier_a.pk
        resp = client_a.post(reverse("hrm:employeestatutoryidentifier_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeStatutoryIdentifier.objects.filter(pk=pk).exists()

    def test_delete_get_not_allowed(self, client_a, statutory_identifier_a):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_delete", args=[statutory_identifier_a.pk]))
        assert resp.status_code == 405


# ================================================================ StatutoryReturn CRUD
class TestStatutoryReturnListView:
    def test_list_200(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_statutory_return_a.pk in pks

    def test_list_filter_by_scheme(self, client_a, tenant_a, pending_statutory_return_a):
        from apps.hrm.models import StatutoryReturn
        pt_return = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pt", period_type="monthly",
            period_start=datetime.date(2026, 5, 1), period_end=datetime.date(2026, 5, 31),
        )
        resp = client_a.get(reverse("hrm:statutoryreturn_list"), {"scheme": "pt"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pt_return.pk in pks
        assert pending_statutory_return_a.pk not in pks

    def test_list_filter_by_status(self, client_a, tenant_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_list"), {"status": "filed"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_statutory_return_a.pk not in pks

    def test_list_has_choices_context(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_list"))
        assert "scheme_choices" in resp.context
        assert "status_choices" in resp.context
        assert "period_type_choices" in resp.context


class TestStatutoryReturnCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, draft_cycle_a):
        from apps.hrm.models import StatutoryReturn
        resp = client_a.post(reverse("hrm:statutoryreturn_create"), {
            "scheme": "esi", "period_type": "monthly",
            "period_start": "2026-06-01", "period_end": "2026-06-30",
            "cycle": draft_cycle_a.pk, "due_date": "2026-07-15", "notes": "",
        })
        assert resp.status_code == 302
        ret = StatutoryReturn.objects.filter(tenant=tenant_a, scheme="esi").first()
        assert ret is not None
        assert ret.number.startswith("SCR-")
        assert ret.tenant_id == tenant_a.pk


class TestStatutoryReturnFormDuplicateGuard:
    """Explicit form-level duplicate guard tests (code-reviewer-requested)."""

    def test_second_org_level_return_same_scheme_period_rejected(
        self, client_a, pending_statutory_return_a, draft_cycle_a,
    ):
        resp = client_a.post(reverse("hrm:statutoryreturn_create"), {
            "scheme": pending_statutory_return_a.scheme, "period_type": "monthly",
            "period_start": pending_statutory_return_a.period_start.isoformat(),
            "period_end": pending_statutory_return_a.period_end.isoformat(),
            "cycle": draft_cycle_a.pk, "due_date": "2026-07-20", "notes": "",
        })
        assert resp.status_code == 200
        assert not resp.context["form"].is_valid()

    def test_different_period_start_validates(self, client_a, pending_statutory_return_a):
        resp = client_a.post(reverse("hrm:statutoryreturn_create"), {
            "scheme": pending_statutory_return_a.scheme, "period_type": "monthly",
            "period_start": "2026-07-01", "period_end": "2026-07-31",
            "due_date": "2026-08-15", "notes": "",
        })
        assert resp.status_code == 302

    def test_per_employee_returns_for_different_employees_do_not_collide(
        self, client_a, tenant_a, employee_a, employee_a2,
    ):
        from apps.hrm.models import StatutoryReturn
        StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="tds_form16", period_type="annual",
            period_start=datetime.date(2026, 4, 1), period_end=datetime.date(2027, 3, 31),
            employee=employee_a,
        )
        resp = client_a.post(reverse("hrm:statutoryreturn_create"), {
            "scheme": "tds_form16", "period_type": "annual",
            "period_start": "2026-04-01", "period_end": "2027-03-31",
            "employee": employee_a2.pk, "due_date": "2027-05-31", "notes": "",
        })
        assert resp.status_code == 302
        assert StatutoryReturn.objects.filter(
            tenant=tenant_a, scheme="tds_form16", employee=employee_a2).exists()

    def test_editing_existing_return_does_not_clash_with_itself(self, client_a, pending_statutory_return_a):
        resp = client_a.post(
            reverse("hrm:statutoryreturn_edit", args=[pending_statutory_return_a.pk]), {
                "scheme": pending_statutory_return_a.scheme, "period_type": "monthly",
                "period_start": pending_statutory_return_a.period_start.isoformat(),
                "period_end": pending_statutory_return_a.period_end.isoformat(),
                "due_date": "2026-07-20", "notes": "Updated",
            })
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.notes == "Updated"


class TestStatutoryReturnDetailEditDelete:
    def test_detail_200(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_detail", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_when_pending(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_edit", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_blocked_when_filed(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        resp = client_a.get(reverse("hrm:statutoryreturn_edit", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:statutoryreturn_detail", args=[pending_statutory_return_a.pk])

    def test_delete_post_removes_when_pending(self, client_a, pending_statutory_return_a):
        from apps.hrm.models import StatutoryReturn
        pk = pending_statutory_return_a.pk
        resp = client_a.post(reverse("hrm:statutoryreturn_delete", args=[pk]))
        assert resp.status_code == 302
        assert not StatutoryReturn.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_filed(self, client_a, pending_statutory_return_a):
        from apps.hrm.models import StatutoryReturn
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_delete", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:statutoryreturn_detail", args=[pending_statutory_return_a.pk])
        assert StatutoryReturn.objects.filter(pk=pending_statutory_return_a.pk).exists()

    def test_delete_get_not_allowed(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_delete", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 405


# ================================================================ StatutoryReturn workflow actions
class TestStatutoryReturnGenerateView:
    def test_generate_reaggregates_totals(
        self, client_a, tenant_a, draft_cycle_a, payslip_with_pf_a,
    ):
        from apps.hrm.models import StatutoryReturn
        ret = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="pf", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            cycle=draft_cycle_a,
        )
        resp = client_a.post(reverse("hrm:statutoryreturn_generate", args=[ret.pk]))
        assert resp.status_code == 302
        ret.refresh_from_db()
        assert ret.employee_contribution_total == Decimal("100.00")
        assert ret.employer_contribution_total == Decimal("100.00")
        assert ret.headcount == 1

    def test_generate_blocked_when_filed(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_generate", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:statutoryreturn_detail", args=[pending_statutory_return_a.pk])

    def test_generate_get_not_allowed(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_generate", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 405

    def test_generate_403_for_non_admin(self, member_client, pending_statutory_return_a):
        resp = member_client.post(reverse("hrm:statutoryreturn_generate", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403


class TestStatutoryReturnMarkFiledView:
    def test_mark_filed_pending_to_filed(self, client_a, pending_statutory_return_a):
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_filed", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "filed"
        assert pending_statutory_return_a.filed_on is not None

    def test_mark_filed_blocked_when_already_filed(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_filed", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "filed"

    def test_mark_filed_403_for_non_admin(self, member_client, pending_statutory_return_a):
        resp = member_client.post(reverse("hrm:statutoryreturn_mark_filed", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "pending"

    def test_mark_filed_get_not_allowed(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_mark_filed", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 405


class TestStatutoryReturnMarkPaidView:
    def test_mark_paid_before_due_date_is_paid(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.due_date = datetime.date(2099, 1, 1)
        pending_statutory_return_a.save(update_fields=["due_date", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]),
                              {"payment_reference": "TXN123"})
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "paid"
        assert pending_statutory_return_a.payment_reference == "TXN123"
        assert pending_statutory_return_a.paid_on is not None

    def test_mark_paid_after_due_date_is_late(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.due_date = datetime.date(2020, 1, 1)  # long past
        pending_statutory_return_a.save(update_fields=["due_date", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "late"

    def test_mark_paid_from_filed_status(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.status = "filed"
        pending_statutory_return_a.due_date = datetime.date(2099, 1, 1)
        pending_statutory_return_a.save(update_fields=["status", "due_date", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "paid"

    def test_mark_paid_blocked_when_already_paid(self, client_a, pending_statutory_return_a):
        pending_statutory_return_a.status = "paid"
        pending_statutory_return_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 302
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "paid"

    def test_mark_paid_403_for_non_admin(self, member_client, pending_statutory_return_a):
        resp = member_client.post(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403
        pending_statutory_return_a.refresh_from_db()
        assert pending_statutory_return_a.status == "pending"

    def test_mark_paid_get_not_allowed(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 405


# ================================================================ Compliance calendar
class TestStatutoryComplianceCalendarView:
    def test_calendar_200(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"))
        assert resp.status_code == 200

    def test_calendar_has_bucket_list(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"))
        assert "bucket_list" in resp.context
        labels = [b["label"] for b in resp.context["bucket_list"]]
        assert labels == ["Overdue", "Pending", "Filed", "Settled"]

    def test_calendar_buckets_pending_return(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"))
        pending_bucket = next(b for b in resp.context["bucket_list"] if b["label"] == "Pending")
        assert pending_statutory_return_a in pending_bucket["rows"]

    def test_calendar_buckets_overdue_return(self, client_a, tenant_a, draft_cycle_a):
        from apps.hrm.models import StatutoryReturn
        overdue = StatutoryReturn.objects.create(
            tenant=tenant_a, scheme="esi", period_type="monthly",
            period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
            due_date=datetime.date(2020, 1, 1),
        )
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"))
        overdue_bucket = next(b for b in resp.context["bucket_list"] if b["label"] == "Overdue")
        assert overdue in overdue_bucket["rows"]

    def test_calendar_filter_by_scheme(self, client_a, tenant_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"), {"scheme": "pt"})
        for bucket in resp.context["bucket_list"]:
            assert pending_statutory_return_a not in bucket["rows"]

    def test_calendar_has_choices_context(self, client_a, pending_statutory_return_a):
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"))
        assert "scheme_choices" in resp.context
        assert "status_choices" in resp.context


# ================================================================ Bounded queries (N+1 guard)
class TestStatutoryQueryCount:
    def test_statutoryreturn_list_bounded_queries(
        self, client_a, tenant_a, draft_cycle_a, django_assert_max_num_queries,
    ):
        from apps.hrm.models import StatutoryReturn
        for i in range(5):
            StatutoryReturn.objects.create(
                tenant=tenant_a, scheme="pf", period_type="monthly",
                period_start=datetime.date(2026, i + 1, 1),
                period_end=datetime.date(2026, i + 1, 28),
                due_date=datetime.date(2026, i + 1, 28),
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:statutoryreturn_list"))

    def test_compliance_calendar_bounded_queries(
        self, client_a, tenant_a, draft_cycle_a, django_assert_max_num_queries,
    ):
        from apps.hrm.models import StatutoryReturn
        for i in range(5):
            StatutoryReturn.objects.create(
                tenant=tenant_a, scheme="pf", period_type="monthly",
                period_start=datetime.date(2026, i + 1, 1),
                period_end=datetime.date(2026, i + 1, 28),
                due_date=datetime.date(2026, i + 1, 28),
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:statutory_compliance_calendar"))
