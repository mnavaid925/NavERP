"""Security tests for HRM 3.26 Request Management (Self-Service): anonymous redirect-to-login,
cross-tenant IDOR (404) on ``DocumentRequest``/``IdCardRequest``/``AssetRequest`` detail/edit/delete/
workflow actions (+ list isolation, + the row survives the attempt, + the fulfill/issue actions never
create a side-effect row for a cross-tenant target), cross-EMPLOYEE IDOR within the SAME tenant (a
non-admin employee is denied another employee's row — detail is 403, and edit/delete redirect to the
"your own records" path even when the target row is in a DECIDED status, proving the ownership gate
runs BEFORE the open-status gate), approve/reject/fulfill/issue are tenant-admin-only, tenant is
always server-set (never smuggled via POST data, and blocked outright when request.tenant is None),
and CSRF enforcement on the POST-only actions. Mirrors test_selfservice_security.py conventions;
client_a is the tenant admin."""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

# (url_prefix, own-tenant fixture name, other-tenant fixture name) — the three 3.26 request models
# share an identical CRUD/workflow URL shape (list/create/detail/edit/delete/submit/cancel/approve/
# reject), so the common matrix tests are parametrized across all three via ``request.getfixturevalue``.
REQUEST_TYPES = [
    ("documentrequest", "document_request_a", "document_request_b"),
    ("idcardrequest", "idcard_request_a", "idcard_request_b"),
    ("assetrequest", "asset_request_a", "asset_request_b"),
]


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


def _document_request_post_data(**overrides):
    data = {
        "document_type": "experience_letter", "purpose": "Needed for a home-loan application.",
        "addressed_to": "", "copies": "1", "delivery_method": "soft_copy", "needed_by": "",
    }
    data.update(overrides)
    return data


def _idcard_request_post_data(**overrides):
    data = {
        "request_type": "new", "reason_type": "first_issue",
        "reason": "First-time badge issuance.", "delivery_location": "",
    }
    data.update(overrides)
    return data


def _asset_request_post_data(**overrides):
    data = {
        "asset_category": "laptop", "asset_name": "Dell XPS 13",
        "justification": "Current laptop is out of warranty.", "priority": "normal", "needed_by": "",
    }
    data.update(overrides)
    return data


_POST_DATA_BUILDERS = {
    "documentrequest": _document_request_post_data,
    "idcardrequest": _idcard_request_post_data,
    "assetrequest": _asset_request_post_data,
}
_CREATE_URLS = {
    "documentrequest": "hrm:documentrequest_create",
    "idcardrequest": "hrm:idcardrequest_create",
    "assetrequest": "hrm:assetrequest_create",
}


# ================================================================ Anonymous -> redirect to login
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name", [
        "hrm:documentrequest_list", "hrm:documentrequest_create",
        "hrm:idcardrequest_list", "hrm:idcardrequest_create",
        "hrm:assetrequest_list", "hrm:assetrequest_create",
        "hrm:my_requests",
    ])
    def test_anon_redirected_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_anon_redirected_on_detail_and_edit_pages(self, client, request, url_prefix, fixture_a, fixture_b):
        obj = request.getfixturevalue(fixture_a)
        for action in ("detail", "edit"):
            resp = client.get(reverse(f"hrm:{url_prefix}_{action}", args=[obj.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_anon_blocked_on_post_only_actions(self, client, request, url_prefix, fixture_a, fixture_b):
        obj = request.getfixturevalue(fixture_a)
        for action in ("delete", "submit", "cancel", "approve", "reject"):
            resp = client.post(reverse(f"hrm:{url_prefix}_{action}", args=[obj.pk]))
            assert resp.status_code == 302
            assert "login" in resp["Location"]

    def test_anon_blocked_on_documentrequest_fulfill(self, client, document_request_a):
        resp = client.post(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_idcardrequest_issue(self, client, idcard_request_a):
        resp = client.post(reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_blocked_on_assetrequest_fulfill(self, client, asset_request_a):
        resp = client.post(reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ Cross-tenant IDOR (404)
class TestCrossTenantIDOR:
    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_detail_cross_tenant_404(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_b = request.getfixturevalue(fixture_b)
        resp = client_a.get(reverse(f"hrm:{url_prefix}_detail", args=[obj_b.pk]))
        assert resp.status_code == 404

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_edit_get_cross_tenant_404(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_b = request.getfixturevalue(fixture_b)
        resp = client_a.get(reverse(f"hrm:{url_prefix}_edit", args=[obj_b.pk]))
        assert resp.status_code == 404

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_edit_post_cross_tenant_404_does_not_mutate(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_b = request.getfixturevalue(fixture_b)
        original = obj_b.number
        resp = client_a.post(reverse(f"hrm:{url_prefix}_edit", args=[obj_b.pk]), _POST_DATA_BUILDERS[url_prefix]())
        assert resp.status_code == 404
        obj_b.refresh_from_db()
        assert obj_b.number == original

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_delete_cross_tenant_404_row_survives(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_b = request.getfixturevalue(fixture_b)
        model = type(obj_b)
        resp = client_a.post(reverse(f"hrm:{url_prefix}_delete", args=[obj_b.pk]))
        assert resp.status_code == 404
        assert model.objects.filter(pk=obj_b.pk).exists()

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_submit_cancel_cross_tenant_404_status_unchanged(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_b = request.getfixturevalue(fixture_b)
        original_status = obj_b.status
        for action in ("submit", "cancel"):
            resp = client_a.post(reverse(f"hrm:{url_prefix}_{action}", args=[obj_b.pk]))
            assert resp.status_code == 404
        obj_b.refresh_from_db()
        assert obj_b.status == original_status

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_approve_reject_cross_tenant_404_status_unchanged(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_b = request.getfixturevalue(fixture_b)
        obj_b.status = "pending"
        obj_b.save(update_fields=["status"])
        resp = client_a.post(reverse(f"hrm:{url_prefix}_approve", args=[obj_b.pk]))
        assert resp.status_code == 404
        resp = client_a.post(reverse(f"hrm:{url_prefix}_reject", args=[obj_b.pk]), {"decision_note": "no"})
        assert resp.status_code == 404
        obj_b.refresh_from_db()
        assert obj_b.status == "pending"

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_list_excludes_b_rows(self, client_a, request, url_prefix, fixture_a, fixture_b):
        obj_a = request.getfixturevalue(fixture_a)
        obj_b = request.getfixturevalue(fixture_b)
        resp = client_a.get(reverse(f"hrm:{url_prefix}_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert obj_a.pk in pks
        assert obj_b.pk not in pks

    def test_documentrequest_fulfill_cross_tenant_404(self, client_a, document_request_b):
        document_request_b.status = "approved"
        document_request_b.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:documentrequest_fulfill", args=[document_request_b.pk]))
        assert resp.status_code == 404
        document_request_b.refresh_from_db()
        assert document_request_b.status == "approved"

    def test_idcardrequest_issue_cross_tenant_404(self, client_a, idcard_request_b):
        idcard_request_b.status = "approved"
        idcard_request_b.save(update_fields=["status"])
        resp = client_a.post(
            reverse("hrm:idcardrequest_issue", args=[idcard_request_b.pk]), {"card_number": "HACKED"})
        assert resp.status_code == 404
        idcard_request_b.refresh_from_db()
        assert idcard_request_b.status == "approved"
        assert idcard_request_b.card_number == ""

    def test_assetrequest_fulfill_cross_tenant_404_creates_no_allocation(self, client_a, asset_request_b):
        from apps.hrm.models import AssetAllocation
        asset_request_b.status = "approved"
        asset_request_b.save(update_fields=["status"])
        before = AssetAllocation.objects.count()
        resp = client_a.post(reverse("hrm:assetrequest_fulfill", args=[asset_request_b.pk]))
        assert resp.status_code == 404
        asset_request_b.refresh_from_db()
        assert asset_request_b.status == "approved"
        assert asset_request_b.allocation_id is None
        assert AssetAllocation.objects.count() == before

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_create_cross_tenant_target_employee_ignored(self, client_a, request, url_prefix, fixture_a, fixture_b):
        """An admin trying to target a Tenant-B employee via ?employee=<b_pk> on the create form is
        silently ignored (``_ss_child_create`` filters the lookup by ``tenant=request.tenant``), so
        the admin's own tenant-less default is used instead — the row NEVER lands on tenant_b."""
        obj_b = request.getfixturevalue(fixture_b)
        model = type(obj_b)
        before = model.objects.filter(tenant=obj_b.tenant).count()
        resp = client_a.post(
            reverse(_CREATE_URLS[url_prefix]),
            _POST_DATA_BUILDERS[url_prefix](employee_pk=str(obj_b.employee_id)))
        assert resp.status_code == 302
        assert model.objects.filter(tenant=obj_b.tenant).count() == before


# ================================================================ Cross-EMPLOYEE IDOR (same tenant)
class TestCrossEmployeeIDOR:
    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_detail_403_for_other_employee(self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b):
        obj_a = request.getfixturevalue(fixture_a)
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_det@acme.com",
                        username=f"ce_{url_prefix}_det_acme")
        resp = c.get(reverse(f"hrm:{url_prefix}_detail", args=[obj_a.pk]))
        assert resp.status_code == 403

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_edit_get_redirects_to_detail_for_other_employee_when_open(
        self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b
    ):
        obj_a = request.getfixturevalue(fixture_a)  # draft — an OPEN status
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_edit@acme.com",
                        username=f"ce_{url_prefix}_edit_acme")
        resp = c.get(reverse(f"hrm:{url_prefix}_edit", args=[obj_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse(f"hrm:{url_prefix}_detail", args=[obj_a.pk])

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_edit_get_redirects_to_detail_for_other_employee_even_when_decided(
        self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b
    ):
        """Ownership is checked BEFORE the open-status branch (_hr_request_edit): a non-owner gets the
        SAME 'your own records' redirect to detail even when the row is in a DECIDED (non-open) status
        — proving the ownership gate runs first rather than leaking a status-based response."""
        obj_a = request.getfixturevalue(fixture_a)
        obj_a.status = "rejected"
        obj_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_edit2@acme.com",
                        username=f"ce_{url_prefix}_edit2_acme")
        resp = c.get(reverse(f"hrm:{url_prefix}_edit", args=[obj_a.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse(f"hrm:{url_prefix}_detail", args=[obj_a.pk])

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_edit_post_does_not_mutate_for_other_employee(
        self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b
    ):
        obj_a = request.getfixturevalue(fixture_a)
        original_number = obj_a.number
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_edit3@acme.com",
                        username=f"ce_{url_prefix}_edit3_acme")
        c.post(reverse(f"hrm:{url_prefix}_edit", args=[obj_a.pk]), _POST_DATA_BUILDERS[url_prefix]())
        obj_a.refresh_from_db()
        assert obj_a.number == original_number

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_delete_redirects_and_row_survives_for_other_employee_regardless_of_status(
        self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b
    ):
        obj_a = request.getfixturevalue(fixture_a)
        obj_a.status = "approved"  # a NON-open status — ownership must still gate first
        obj_a.save(update_fields=["status"])
        model = type(obj_a)
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_del@acme.com",
                        username=f"ce_{url_prefix}_del_acme")
        resp = c.post(reverse(f"hrm:{url_prefix}_delete", args=[obj_a.pk]))
        assert resp.status_code == 302
        assert model.objects.filter(pk=obj_a.pk).exists()

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_submit_redirects_and_status_unchanged_for_other_employee(
        self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b
    ):
        obj_a = request.getfixturevalue(fixture_a)
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_sub@acme.com",
                        username=f"ce_{url_prefix}_sub_acme")
        resp = c.post(reverse(f"hrm:{url_prefix}_submit", args=[obj_a.pk]))
        assert resp.status_code == 302
        obj_a.refresh_from_db()
        assert obj_a.status == "draft"  # unchanged

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_list_hides_other_employee_rows(self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b):
        obj_a = request.getfixturevalue(fixture_a)
        c = _client_for(employee_a2.party, tenant_a, email=f"ce_{url_prefix}_list@acme.com",
                        username=f"ce_{url_prefix}_list_acme")
        resp = c.get(reverse(f"hrm:{url_prefix}_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert obj_a.pk not in pks


# ================================================================ Approve/Reject/Fulfill/Issue are tenant-admin-only
class TestReviewActionsAdminOnly:
    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_approve_403_for_non_admin(self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b):
        obj_a = request.getfixturevalue(fixture_a)
        obj_a.status = "pending"
        obj_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email=f"na_{url_prefix}_appr@acme.com",
                        username=f"na_{url_prefix}_appr_acme")
        resp = c.post(reverse(f"hrm:{url_prefix}_approve", args=[obj_a.pk]))
        assert resp.status_code == 403
        obj_a.refresh_from_db()
        assert obj_a.status == "pending"

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_reject_403_for_non_admin(self, tenant_a, employee_a2, request, url_prefix, fixture_a, fixture_b):
        obj_a = request.getfixturevalue(fixture_a)
        obj_a.status = "pending"
        obj_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email=f"na_{url_prefix}_rej@acme.com",
                        username=f"na_{url_prefix}_rej_acme")
        resp = c.post(reverse(f"hrm:{url_prefix}_reject", args=[obj_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        obj_a.refresh_from_db()
        assert obj_a.status == "pending"

    def test_documentrequest_fulfill_403_for_non_admin(self, tenant_a, employee_a2, document_request_a):
        document_request_a.status = "approved"
        document_request_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="na_docreq_fulfill@acme.com",
                        username="na_docreq_fulfill_acme")
        resp = c.post(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]))
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "approved"

    def test_idcardrequest_issue_403_for_non_admin(self, tenant_a, employee_a2, idcard_request_a):
        idcard_request_a.status = "approved"
        idcard_request_a.save(update_fields=["status"])
        c = _client_for(employee_a2.party, tenant_a, email="na_idreq_issue@acme.com",
                        username="na_idreq_issue_acme")
        resp = c.post(
            reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]), {"card_number": "X1"})
        assert resp.status_code == 403
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "approved"
        assert idcard_request_a.card_number == ""

    def test_assetrequest_fulfill_403_for_non_admin_creates_no_allocation(
        self, tenant_a, employee_a2, asset_request_a
    ):
        from apps.hrm.models import AssetAllocation
        asset_request_a.status = "approved"
        asset_request_a.save(update_fields=["status"])
        before = AssetAllocation.objects.count()
        c = _client_for(employee_a2.party, tenant_a, email="na_astreq_fulfill@acme.com",
                        username="na_astreq_fulfill_acme")
        resp = c.post(reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]))
        assert resp.status_code == 403
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "approved"
        assert AssetAllocation.objects.count() == before


# ================================================================ Tenant is server-set, never smuggled
class TestTenantServerSet:
    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_create_ignores_smuggled_tenant(self, tenant_a, tenant_b, employee_a, url_prefix, fixture_a, fixture_b):
        model_map = {"documentrequest": "DocumentRequest", "idcardrequest": "IdCardRequest",
                    "assetrequest": "AssetRequest"}
        import apps.hrm.models as hrm_models
        model = getattr(hrm_models, model_map[url_prefix])
        c = _client_for(employee_a.party, tenant_a, email=f"tss_{url_prefix}@acme.com",
                        username=f"tss_{url_prefix}_acme")
        resp = c.post(reverse(_CREATE_URLS[url_prefix]), _POST_DATA_BUILDERS[url_prefix](tenant=tenant_b.pk))
        assert resp.status_code == 302
        obj = model.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    @pytest.mark.parametrize("url_prefix,fixture_a,fixture_b", REQUEST_TYPES)
    def test_create_blocked_when_request_tenant_is_none(self, employee_a, url_prefix, fixture_a, fixture_b):
        from apps.accounts.models import User
        model_map = {"documentrequest": "DocumentRequest", "idcardrequest": "IdCardRequest",
                    "assetrequest": "AssetRequest"}
        import apps.hrm.models as hrm_models
        model = getattr(hrm_models, model_map[url_prefix])
        tenantless = User.objects.create_user(
            email=f"notenant_{url_prefix}@example.com", username=f"notenant_{url_prefix}_user",
            password="TestPass123!", tenant=None, is_tenant_admin=False)
        tenantless.party = employee_a.party
        tenantless.save(update_fields=["party"])
        c = Client()
        c.force_login(tenantless)
        resp = c.post(reverse(_CREATE_URLS[url_prefix]), _POST_DATA_BUILDERS[url_prefix]())
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert not model.objects.filter(employee=employee_a).exists()


# ================================================================ CSRF enforcement
class TestCSRFEnforcement:
    def test_documentrequest_delete_enforces_csrf(self, tenant_a, employee_a, document_request_a):
        from apps.hrm.models import DocumentRequest
        c = _client_for(employee_a.party, tenant_a, email="csrf_dr_del@acme.com", username="csrf_dr_del_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:documentrequest_delete", args=[document_request_a.pk]))
        assert resp.status_code == 403
        assert DocumentRequest.objects.filter(pk=document_request_a.pk).exists()

    def test_documentrequest_create_enforces_csrf(self, tenant_a, employee_a):
        from apps.hrm.models import DocumentRequest
        c = _client_for(employee_a.party, tenant_a, email="csrf_dr_create@acme.com", username="csrf_dr_create_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:documentrequest_create"), _document_request_post_data())
        assert resp.status_code == 403
        assert not DocumentRequest.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_documentrequest_approve_enforces_csrf(self, admin_user, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:documentrequest_approve", args=[document_request_a.pk]))
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_documentrequest_reject_enforces_csrf(self, admin_user, document_request_a):
        document_request_a.status = "pending"
        document_request_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:documentrequest_reject", args=[document_request_a.pk]), {"decision_note": "no"})
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "pending"

    def test_documentrequest_fulfill_enforces_csrf(self, admin_user, document_request_a):
        document_request_a.status = "approved"
        document_request_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:documentrequest_fulfill", args=[document_request_a.pk]))
        assert resp.status_code == 403
        document_request_a.refresh_from_db()
        assert document_request_a.status == "approved"

    def test_idcardrequest_delete_enforces_csrf(self, tenant_a, employee_a, idcard_request_a):
        from apps.hrm.models import IdCardRequest
        c = _client_for(employee_a.party, tenant_a, email="csrf_ir_del@acme.com", username="csrf_ir_del_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:idcardrequest_delete", args=[idcard_request_a.pk]))
        assert resp.status_code == 403
        assert IdCardRequest.objects.filter(pk=idcard_request_a.pk).exists()

    def test_idcardrequest_issue_enforces_csrf(self, admin_user, idcard_request_a):
        idcard_request_a.status = "approved"
        idcard_request_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:idcardrequest_issue", args=[idcard_request_a.pk]), {"card_number": "X1"})
        assert resp.status_code == 403
        idcard_request_a.refresh_from_db()
        assert idcard_request_a.status == "approved"
        assert idcard_request_a.card_number == ""

    def test_assetrequest_delete_enforces_csrf(self, tenant_a, employee_a, asset_request_a):
        from apps.hrm.models import AssetRequest
        c = _client_for(employee_a.party, tenant_a, email="csrf_ar_del@acme.com", username="csrf_ar_del_acme")
        c.handler.enforce_csrf_checks = True
        resp = c.post(reverse("hrm:assetrequest_delete", args=[asset_request_a.pk]))
        assert resp.status_code == 403
        assert AssetRequest.objects.filter(pk=asset_request_a.pk).exists()

    def test_assetrequest_fulfill_enforces_csrf_creates_no_allocation(self, admin_user, asset_request_a):
        from apps.hrm.models import AssetAllocation
        asset_request_a.status = "approved"
        asset_request_a.save(update_fields=["status"])
        before = AssetAllocation.objects.count()
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:assetrequest_fulfill", args=[asset_request_a.pk]))
        assert resp.status_code == 403
        asset_request_a.refresh_from_db()
        assert asset_request_a.status == "approved"
        assert AssetAllocation.objects.count() == before
