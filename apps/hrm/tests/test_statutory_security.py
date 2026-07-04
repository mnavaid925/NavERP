"""Security tests for HRM 3.15 Statutory Compliance: cross-tenant IDOR (StatutoryReturn,
StatutoryStateRule, EmployeeStatutoryIdentifier), list isolation, anonymous-blocked, CSRF
enforcement on delete/generate/mark_* POST-only routes."""
import datetime

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ StatutoryStateRule IDOR
class TestStatutoryStateRuleIDOR:
    def test_detail_cross_tenant_404(self, client_a, state_rule_b):
        resp = client_a.get(reverse("hrm:statutorystaterule_detail", args=[state_rule_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, state_rule_b):
        resp = client_a.get(reverse("hrm:statutorystaterule_edit", args=[state_rule_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, state_rule_b):
        resp = client_a.post(reverse("hrm:statutorystaterule_edit", args=[state_rule_b.pk]), {
            "state": "Karnataka", "scheme": "pt",
            "income_from": "15000", "income_to": "20000", "pt_monthly_amount": "999",
            "effective_from": "2026-01-01",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, state_rule_b):
        resp = client_a.post(reverse("hrm:statutorystaterule_delete", args=[state_rule_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_rules(self, client_a, pt_rule_a, state_rule_b):
        resp = client_a.get(reverse("hrm:statutorystaterule_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pt_rule_a.pk in pks
        assert state_rule_b.pk not in pks


# ================================================================ EmployeeStatutoryIdentifier IDOR
class TestEmployeeStatutoryIdentifierIDOR:
    def test_detail_cross_tenant_404(self, client_a, statutory_identifier_b):
        resp = client_a.get(
            reverse("hrm:employeestatutoryidentifier_detail", args=[statutory_identifier_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, statutory_identifier_b):
        resp = client_a.get(
            reverse("hrm:employeestatutoryidentifier_edit", args=[statutory_identifier_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, statutory_identifier_b):
        resp = client_a.post(
            reverse("hrm:employeestatutoryidentifier_edit", args=[statutory_identifier_b.pk]), {
                "employee": statutory_identifier_b.employee_id,
                "uan_number": "000000000000", "pf_number": "", "esi_number": "",
                "pt_state": "Maharashtra", "is_pf_applicable": "on", "is_esi_applicable": "on",
            })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, statutory_identifier_b):
        resp = client_a.post(
            reverse("hrm:employeestatutoryidentifier_delete", args=[statutory_identifier_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_identifiers(self, client_a, statutory_identifier_a, statutory_identifier_b):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert statutory_identifier_a.pk in pks
        assert statutory_identifier_b.pk not in pks

    def test_list_never_leaks_b_uan_in_html(self, client_a, statutory_identifier_a, statutory_identifier_b):
        resp = client_a.get(reverse("hrm:employeestatutoryidentifier_list"))
        content = resp.content.decode()
        assert statutory_identifier_b.uan_number not in content


# ================================================================ StatutoryReturn IDOR
class TestStatutoryReturnIDOR:
    def test_detail_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.get(reverse("hrm:statutoryreturn_detail", args=[statutory_return_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.get(reverse("hrm:statutoryreturn_edit", args=[statutory_return_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.post(reverse("hrm:statutoryreturn_edit", args=[statutory_return_b.pk]), {
            "scheme": "pf", "period_type": "monthly",
            "period_start": "2026-06-01", "period_end": "2026-06-30",
            "due_date": "2026-07-15", "notes": "hacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.post(reverse("hrm:statutoryreturn_delete", args=[statutory_return_b.pk]))
        assert resp.status_code == 404

    def test_generate_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.post(reverse("hrm:statutoryreturn_generate", args=[statutory_return_b.pk]))
        assert resp.status_code == 404

    def test_mark_filed_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_filed", args=[statutory_return_b.pk]))
        assert resp.status_code == 404

    def test_mark_paid_cross_tenant_404(self, client_a, statutory_return_b):
        resp = client_a.post(reverse("hrm:statutoryreturn_mark_paid", args=[statutory_return_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_returns(self, client_a, pending_statutory_return_a, statutory_return_b):
        resp = client_a.get(reverse("hrm:statutoryreturn_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_statutory_return_a.pk in pks
        assert statutory_return_b.pk not in pks

    def test_cross_tenant_actions_do_not_mutate_b_row(self, client_a, statutory_return_b):
        """The 404 responses above must not have side-effected tenant_b's row at all."""
        original_status = statutory_return_b.status
        client_a.post(reverse("hrm:statutoryreturn_mark_filed", args=[statutory_return_b.pk]))
        client_a.post(reverse("hrm:statutoryreturn_generate", args=[statutory_return_b.pk]))
        statutory_return_b.refresh_from_db()
        assert statutory_return_b.status == original_status


# ================================================================ Compliance calendar isolation
class TestStatutoryComplianceCalendarIsolation:
    def test_calendar_excludes_b_returns(self, client_a, pending_statutory_return_a, statutory_return_b):
        resp = client_a.get(reverse("hrm:statutory_compliance_calendar"))
        all_rows = [r for bucket in resp.context["bucket_list"] for r in bucket["rows"]]
        pks = [r.pk for r in all_rows]
        assert pending_statutory_return_a.pk in pks
        assert statutory_return_b.pk not in pks


# ================================================================ StatutoryConfig tenant isolation
class TestStatutoryConfigIsolation:
    def test_each_tenant_sees_only_its_own_config(self, client_a, client_b, statutory_config_a, statutory_config_b):
        statutory_config_a.pf_establishment_code = "ACME-PF-001"
        statutory_config_a.save(update_fields=["pf_establishment_code", "updated_at"])
        statutory_config_b.pf_establishment_code = "GLOBEX-PF-999"
        statutory_config_b.save(update_fields=["pf_establishment_code", "updated_at"])

        resp_a = client_a.get(reverse("hrm:statutoryconfig_detail"))
        assert resp_a.context["obj"].pf_establishment_code == "ACME-PF-001"

        resp_b = client_b.get(reverse("hrm:statutoryconfig_detail"))
        assert resp_b.context["obj"].pf_establishment_code == "GLOBEX-PF-999"


# ================================================================ Anonymous user -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:statutoryconfig_detail", []),
        ("hrm:statutorystaterule_list", []),
        ("hrm:employeestatutoryidentifier_list", []),
        ("hrm:statutoryreturn_list", []),
        ("hrm:statutory_compliance_calendar", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_redirected_on_detail_pages(self, client, pt_rule_a, statutory_identifier_a,
                                             pending_statutory_return_a):
        for url_name, pk in [
            ("hrm:statutorystaterule_detail", pt_rule_a.pk),
            ("hrm:employeestatutoryidentifier_detail", statutory_identifier_a.pk),
            ("hrm:statutoryreturn_detail", pending_statutory_return_a.pk),
        ]:
            resp = client.get(reverse(url_name, args=[pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_post_only_actions(self, client, pending_statutory_return_a):
        for url_name in ("hrm:statutoryreturn_generate", "hrm:statutoryreturn_mark_filed",
                          "hrm:statutoryreturn_mark_paid", "hrm:statutoryreturn_delete"):
            resp = client.post(reverse(url_name, args=[pending_statutory_return_a.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]


# ================================================================ AuthZ — tenant-admin-only actions
class TestStatutoryAdminOnlyActions:
    """@tenant_admin_required gates statutoryconfig_edit + the StatutoryReturn workflow actions —
    a plain (non-admin) tenant member must get 403."""

    def test_non_admin_403_on_statutoryconfig_edit(self, member_client, statutory_config_a):
        resp = member_client.post(reverse("hrm:statutoryconfig_edit"), {
            "pf_establishment_code": "HACKED",
            "pf_wage_ceiling": "15000.00", "pf_employee_rate": "12.00", "pf_employer_rate": "12.00",
            "esi_wage_ceiling": "21000.00", "esi_employee_rate": "0.75", "esi_employer_rate": "3.25",
        })
        assert resp.status_code == 403

    def test_non_admin_403_on_statutoryreturn_generate(self, member_client, pending_statutory_return_a):
        resp = member_client.post(
            reverse("hrm:statutoryreturn_generate", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_statutoryreturn_mark_filed(self, member_client, pending_statutory_return_a):
        resp = member_client.post(
            reverse("hrm:statutoryreturn_mark_filed", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_403_on_statutoryreturn_mark_paid(self, member_client, pending_statutory_return_a):
        resp = member_client.post(
            reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_can_still_view_statutoryreturn_list(self, member_client, pending_statutory_return_a):
        """Plain @login_required reads (list/detail) stay open to non-admin tenant members."""
        resp = member_client.get(reverse("hrm:statutoryreturn_list"))
        assert resp.status_code == 200


# ================================================================ CSRF enforcement
class TestStatutoryCSRFEnforcement:
    def test_statutorystaterule_delete_enforces_csrf(self, admin_user, pt_rule_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:statutorystaterule_delete", args=[pt_rule_a.pk]))
        assert resp.status_code == 403

    def test_employeestatutoryidentifier_delete_enforces_csrf(self, admin_user, statutory_identifier_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:employeestatutoryidentifier_delete", args=[statutory_identifier_a.pk]))
        assert resp.status_code == 403

    def test_statutoryreturn_delete_enforces_csrf(self, admin_user, pending_statutory_return_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:statutoryreturn_delete", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_statutoryreturn_generate_enforces_csrf(self, admin_user, pending_statutory_return_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:statutoryreturn_generate", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_statutoryreturn_mark_filed_enforces_csrf(self, admin_user, pending_statutory_return_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:statutoryreturn_mark_filed", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_statutoryreturn_mark_paid_enforces_csrf(self, admin_user, pending_statutory_return_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:statutoryreturn_mark_paid", args=[pending_statutory_return_a.pk]))
        assert resp.status_code == 403

    def test_statutoryconfig_edit_enforces_csrf(self, admin_user, statutory_config_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:statutoryconfig_edit"), {
            "pf_establishment_code": "X",
            "pf_wage_ceiling": "15000.00", "pf_employee_rate": "12.00", "pf_employer_rate": "12.00",
            "esi_wage_ceiling": "21000.00", "esi_employee_rate": "0.75", "esi_employer_rate": "3.25",
        })
        assert resp.status_code == 403
