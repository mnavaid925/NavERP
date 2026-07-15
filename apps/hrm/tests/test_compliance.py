"""Tests for HRM 3.39 Compliance & Legal: ``EmploymentContract`` (``CTR-``, computed expiry) +
``HRPolicy`` (``POL-``, versioned, publish→bulk-acknowledge) + ``PolicyAcknowledgment`` (self-service) +
``Grievance`` (``GRV-``, CONFIDENTIAL own-vs-admin + anonymity masking + investigation workflow) +
``ComplianceRegister`` (``CMP-``, computed overdue).

Disciplinary Actions needs no model here — that bullet reuses the 3.21 ``WarningLetter``.
"""
import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

# Must match the models' own basis (timezone.localdate()), not the raw system date — otherwise the
# computed day counts are off by one whenever the project TZ and the system TZ straddle midnight.
TODAY = timezone.localdate()


def _client_for(party, tenant, *, email, username, is_admin=False):
    from apps.accounts.models import User
    user = User.objects.create_user(email=email, username=username, password="TestPass123!",
                                    tenant=tenant, is_tenant_admin=is_admin)
    user.party = party
    user.save(update_fields=["party"])
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def own_client(tenant_a, employee_a):
    """A non-admin employee (the complainant / policy reader)."""
    return _client_for(employee_a.party, tenant_a, email="own@acme.com", username="own_acme")


@pytest.fixture
def other_client(tenant_a, employee_a2):
    """A DIFFERENT non-admin employee (must not see employee_a's grievances)."""
    return _client_for(employee_a2.party, tenant_a, email="other@acme.com", username="other_acme")


@pytest.fixture
def contract_a(db, tenant_a, employee_a, designation_a):
    from apps.hrm.models import EmploymentContract
    return EmploymentContract.objects.create(
        tenant=tenant_a, employee=employee_a, contract_type="fixed_term",
        start_date=TODAY - datetime.timedelta(days=300), end_date=TODAY + datetime.timedelta(days=45),
        designation=designation_a, status="active")


@pytest.fixture
def policy_a(db, tenant_a):
    from apps.hrm.models import HRPolicy
    return HRPolicy.objects.create(
        tenant=tenant_a, title="Code of Conduct", version_number="1.0", category="code_of_conduct",
        status="draft", body="Act with integrity.", requires_acknowledgment=True)


@pytest.fixture
def grievance_a(db, tenant_a, employee_a):
    from apps.hrm.models import Grievance
    return Grievance.objects.create(
        tenant=tenant_a, employee=employee_a, subject="Unsafe walkway", description="Unlit and slippery.",
        category="safety", severity="high", status="open", filed_on=TODAY)


@pytest.fixture
def anon_grievance_a(db, tenant_a, employee_a):
    from apps.hrm.models import Grievance
    return Grievance.objects.create(
        tenant=tenant_a, employee=employee_a, subject="Inappropriate remarks", description="Repeated.",
        category="harassment", severity="critical", status="open", is_anonymous=True, filed_on=TODAY)


@pytest.fixture
def register_a(db, tenant_a):
    from apps.hrm.models import ComplianceRegister
    return ComplianceRegister.objects.create(
        tenant=tenant_a, title="Wage register", register_type="wage_register",
        jurisdiction="Karnataka", due_date=TODAY - datetime.timedelta(days=10), status="pending")


# ---- tenant_b (IDOR) ----
@pytest.fixture
def policy_b(db, tenant_b):
    from apps.hrm.models import HRPolicy
    return HRPolicy.objects.create(tenant=tenant_b, title="B Policy", version_number="1.0",
                                   status="published")


@pytest.fixture
def grievance_b(db, tenant_b, employee_b):
    from apps.hrm.models import Grievance
    return Grievance.objects.create(tenant=tenant_b, employee=employee_b, subject="B", description="x",
                                    status="open")


@pytest.fixture
def contract_b(db, tenant_b, employee_b):
    """An EmploymentContract belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import EmploymentContract
    return EmploymentContract.objects.create(
        tenant=tenant_b, employee=employee_b, contract_type="permanent",
        start_date=TODAY - datetime.timedelta(days=100), status="active")


@pytest.fixture
def register_b(db, tenant_b):
    """A ComplianceRegister record belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ComplianceRegister
    return ComplianceRegister.objects.create(
        tenant=tenant_b, title="B Register", register_type="wage_register", status="pending")


# ============================================================ Models (computed)
def test_contract_autonumber_and_expiry(contract_a):
    assert contract_a.number.startswith("CTR-")
    assert contract_a.days_to_expiry == 45
    assert contract_a.is_expiring_soon is True
    assert contract_a.is_expired is False


def test_contract_open_ended_has_no_expiry(tenant_a, employee_a):
    from apps.hrm.models import EmploymentContract
    c = EmploymentContract.objects.create(tenant=tenant_a, employee=employee_a,
                                          contract_type="permanent", start_date=TODAY, status="active")
    assert c.days_to_expiry is None and c.is_expiring_soon is False


def test_register_overdue_computed(register_a):
    from apps.hrm.models import ComplianceRegister
    assert register_a.number.startswith("CMP-")
    assert register_a.is_overdue is True
    # Filing it clears the overdue flag.
    ComplianceRegister.objects.filter(pk=register_a.pk).update(status="filed", filed_on=TODAY)
    assert ComplianceRegister.objects.get(pk=register_a.pk).is_overdue is False


def test_policy_autonumber_and_ack_rate(policy_a):
    assert policy_a.number.startswith("POL-")
    assert policy_a.acknowledgment_rate == 0  # nobody targeted yet


# ============================================================ Publish -> bulk acknowledge
def test_publish_raises_acknowledgments_and_is_idempotent(client_a, tenant_a, policy_a,
                                                          employee_a, employee_a2):
    from apps.hrm.models import HRPolicy, PolicyAcknowledgment
    resp = client_a.post(reverse("hrm:hrpolicy_publish", args=[policy_a.pk]))
    assert resp.status_code == 302
    p = HRPolicy.objects.get(pk=policy_a.pk)
    assert p.status == "published" and p.published_at is not None
    # One pending acknowledgment per employee in the tenant.
    acks = PolicyAcknowledgment.objects.filter(tenant=tenant_a, policy=p)
    assert acks.count() >= 2
    assert set(acks.values_list("status", flat=True)) == {"pending"}
    # Re-publishing an already-published policy is rejected (no duplicate rows).
    before = acks.count()
    client_a.post(reverse("hrm:hrpolicy_publish", args=[policy_a.pk]))
    assert PolicyAcknowledgment.objects.filter(tenant=tenant_a, policy=p).count() == before


def test_employee_acknowledges_own_policy(client_a, own_client, tenant_a, policy_a, employee_a):
    from apps.hrm.models import HRPolicy, PolicyAcknowledgment
    client_a.post(reverse("hrm:hrpolicy_publish", args=[policy_a.pk]))
    ack = PolicyAcknowledgment.objects.get(tenant=tenant_a, policy=policy_a, employee=employee_a)
    resp = own_client.post(reverse("hrm:policyacknowledgment_acknowledge", args=[ack.pk]))
    assert resp.status_code == 302
    ack.refresh_from_db()
    assert ack.status == "acknowledged" and ack.acknowledged_at is not None
    assert HRPolicy.objects.get(pk=policy_a.pk).acknowledgment_rate > 0


def test_cannot_acknowledge_someone_elses_policy(client_a, other_client, tenant_a, policy_a, employee_a):
    """Another employee must not be able to acknowledge on your behalf."""
    from apps.hrm.models import PolicyAcknowledgment
    client_a.post(reverse("hrm:hrpolicy_publish", args=[policy_a.pk]))
    ack = PolicyAcknowledgment.objects.get(tenant=tenant_a, policy=policy_a, employee=employee_a)
    other_client.post(reverse("hrm:policyacknowledgment_acknowledge", args=[ack.pk]))
    ack.refresh_from_db()
    assert ack.status == "pending"  # unchanged


def test_unpublished_policy_hidden_from_employees(own_client, policy_a):
    assert own_client.get(reverse("hrm:hrpolicy_detail", args=[policy_a.pk])).status_code == 403
    resp = own_client.get(reverse("hrm:hrpolicy_list"))
    assert policy_a.number.encode() not in resp.content


def test_policy_duplicate_version_shows_form_error(client_a, policy_a):
    """unique_together(tenant, title, version_number) — guarded in clean(), no 500."""
    from apps.hrm.models import HRPolicy
    before = HRPolicy.objects.filter(tenant=policy_a.tenant).count()
    resp = client_a.post(reverse("hrm:hrpolicy_create"), {
        "title": policy_a.title, "version_number": policy_a.version_number,
        "category": "other", "status": "draft", "requires_acknowledgment": "on"})
    assert resp.status_code == 200
    assert HRPolicy.objects.filter(tenant=policy_a.tenant).count() == before


# ============================================================ Grievance: confidentiality + workflow
def test_grievance_own_scoping(other_client, grievance_a):
    """A different employee must not see someone else's grievance."""
    resp = other_client.get(reverse("hrm:grievance_list"))
    assert resp.status_code == 200
    assert grievance_a.number.encode() not in resp.content
    assert other_client.get(reverse("hrm:grievance_detail", args=[grievance_a.pk])).status_code == 403


def test_anonymous_grievance_masks_complainant_from_non_admin(own_client, client_a, anon_grievance_a,
                                                              employee_a):
    """is_anonymous hides the complainant from non-admins; HR admins still see it (to investigate)."""
    name = employee_a.party.name.encode()
    # The complainant themselves views it — the page must not print their name as the complainant.
    resp = own_client.get(reverse("hrm:grievance_detail", args=[anon_grievance_a.pk]))
    assert resp.status_code == 200
    assert b"Anonymous" in resp.content
    # The HR admin CAN see the name (needed for the investigation).
    admin_resp = client_a.get(reverse("hrm:grievance_detail", args=[anon_grievance_a.pk]))
    assert admin_resp.status_code == 200
    assert name in admin_resp.content


def test_grievance_investigation_workflow(client_a, grievance_a, employee_a2):
    from apps.hrm.models import Grievance
    client_a.post(reverse("hrm:grievance_assign", args=[grievance_a.pk]),
                  {"investigator": employee_a2.pk})
    g = Grievance.objects.get(pk=grievance_a.pk)
    assert g.status == "investigating" and g.assigned_investigator_id == employee_a2.pk
    # Resolve requires a note.
    client_a.post(reverse("hrm:grievance_resolve", args=[grievance_a.pk]), {})
    g.refresh_from_db()
    assert g.status == "investigating"  # rejected — no note
    client_a.post(reverse("hrm:grievance_resolve", args=[grievance_a.pk]), {"resolution": "Fixed lighting."})
    g.refresh_from_db()
    assert g.status == "resolved" and g.resolved_at is not None
    client_a.post(reverse("hrm:grievance_close", args=[grievance_a.pk]))
    g.refresh_from_db()
    assert g.status == "closed"


def test_complainant_can_withdraw_own_grievance(own_client, grievance_a):
    from apps.hrm.models import Grievance
    resp = own_client.post(reverse("hrm:grievance_withdraw", args=[grievance_a.pk]))
    assert resp.status_code == 302
    assert Grievance.objects.get(pk=grievance_a.pk).status == "withdrawn"


def test_non_admin_cannot_drive_grievance_workflow(own_client, grievance_a, employee_a2):
    """Assign/resolve/close are HR-only."""
    from apps.hrm.models import Grievance
    assert own_client.post(reverse("hrm:grievance_assign", args=[grievance_a.pk]),
                           {"investigator": employee_a2.pk}).status_code == 403
    assert own_client.post(reverse("hrm:grievance_resolve", args=[grievance_a.pk]),
                           {"resolution": "x"}).status_code == 403
    assert Grievance.objects.get(pk=grievance_a.pk).status == "open"


# ============================================================ Views / access control / IDOR
def test_lists_render(client_a, contract_a, policy_a, grievance_a, register_a):
    for name in ["employmentcontract_list", "hrpolicy_list", "policyacknowledgment_list",
                 "grievance_list", "complianceregister_list"]:
        assert client_a.get(reverse(f"hrm:{name}")).status_code == 200


def test_expiring_and_overdue_deep_links(client_a, contract_a, register_a):
    resp = client_a.get(reverse("hrm:employmentcontract_list") + "?expiring=1")
    assert resp.status_code == 200 and contract_a.number.encode() in resp.content
    resp = client_a.get(reverse("hrm:complianceregister_list") + "?overdue=1")
    assert resp.status_code == 200 and register_a.number.encode() in resp.content


def test_non_admin_blocked_from_admin_only_surfaces(own_client, contract_a, register_a):
    """Contracts and the compliance register are HR-only; policies are readable by all."""
    assert own_client.get(reverse("hrm:employmentcontract_list")).status_code == 403
    assert own_client.get(reverse("hrm:complianceregister_list")).status_code == 403
    assert own_client.get(reverse("hrm:hrpolicy_list")).status_code == 200  # published policies readable


def test_anonymous_redirected(client, policy_a):
    resp = client.get(reverse("hrm:grievance_list"))
    assert resp.status_code == 302 and "/login" in resp.url


def test_multitenant_idor_404(client_a, policy_b, grievance_b):
    assert client_a.get(reverse("hrm:hrpolicy_detail", args=[policy_b.pk])).status_code == 404
    assert client_a.get(reverse("hrm:grievance_detail", args=[grievance_b.pk])).status_code == 404


def _query_count(client, url):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


def test_policy_list_and_detail_query_counts_are_flat(client_a, tenant_a, employee_a, employee_a2):
    """hrpolicy_list/detail annotate the acknowledgment counts — without that, each of the three
    properties fires its own COUNT (per row on the list, up to 4x on the detail)."""
    from apps.hrm.models import HRPolicy, PolicyAcknowledgment
    list_url = reverse("hrm:hrpolicy_list")

    def _policy_with_acks(i):
        p = HRPolicy.objects.create(tenant=tenant_a, title=f"P{i}", version_number="1.0",
                                    status="published", requires_acknowledgment=True)
        for emp in (employee_a, employee_a2):
            PolicyAcknowledgment.objects.create(tenant=tenant_a, policy=p, employee=emp)
        return p

    first = _policy_with_acks(0)
    baseline = _query_count(client_a, list_url)
    for i in range(1, 5):
        _policy_with_acks(i)
    assert _query_count(client_a, list_url) == baseline, "hrpolicy_list regressed to an N+1"

    # The detail page must not re-COUNT per property access either.
    detail = _query_count(client_a, reverse("hrm:hrpolicy_detail", args=[first.pk]))
    assert detail <= baseline, "hrpolicy_detail is re-running the acknowledgment COUNTs"


def test_grievance_and_contract_list_query_counts_are_flat(client_a, tenant_a, employee_a,
                                                           designation_a):
    from apps.hrm.models import EmploymentContract, Grievance
    g_url, c_url = reverse("hrm:grievance_list"), reverse("hrm:employmentcontract_list")

    Grievance.objects.create(tenant=tenant_a, employee=employee_a, subject="G0", description="x")
    EmploymentContract.objects.create(tenant=tenant_a, employee=employee_a, contract_type="permanent",
                                      start_date=TODAY, designation=designation_a, status="active")
    g_base, c_base = _query_count(client_a, g_url), _query_count(client_a, c_url)
    for i in range(1, 6):
        Grievance.objects.create(tenant=tenant_a, employee=employee_a, subject=f"G{i}", description="x")
        EmploymentContract.objects.create(tenant=tenant_a, employee=employee_a,
                                          contract_type="permanent", start_date=TODAY,
                                          designation=designation_a, status="active")
    assert _query_count(client_a, g_url) == g_base, "grievance_list regressed to an N+1"
    assert _query_count(client_a, c_url) == c_base, "employmentcontract_list regressed to an N+1"


def test_hrpolicy_list_is_ordered_for_pagination(client_a, tenant_a):
    """hrpolicy_list annotates ack counts — annotate() drops Meta.ordering, so it MUST re-apply order_by
    or the paginator duplicates/skips rows (the 3.38 lesson)."""
    from apps.hrm.models import HRPolicy
    for i in range(20):
        HRPolicy.objects.create(tenant=tenant_a, title=f"Policy {i:02d}", version_number="1.0",
                                status="published")
    resp = client_a.get(reverse("hrm:hrpolicy_list"))
    assert resp.status_code == 200
    assert resp.context["page_obj"].object_list.ordered
    p1 = {o.pk for o in resp.context["object_list"]}
    p2 = {o.pk for o in client_a.get(reverse("hrm:hrpolicy_list") + "?page=2").context["object_list"]}
    assert p1 and p2 and not (p1 & p2)


# ============================================================ Full URL sweep (list/create/detail/edit)
def _all_compliance_urls(contract, policy, grievance, register, employee):
    """The 17 GET routes across the 13 compliance templates: employmentcontract/hrpolicy/grievance/
    complianceregister each get list+create+detail+edit (list/detail are their own template; create and
    edit share one form.html); policyacknowledgment is list-only (self-service, no create/edit).
    grievance_create needs ?employee=<id> because the tenant admin fixture has no linked
    EmployeeProfile (own == None) — same on-behalf-of pattern the create view documents for HR admins."""
    return [
        reverse("hrm:employmentcontract_list"),
        reverse("hrm:employmentcontract_create"),
        reverse("hrm:employmentcontract_detail", args=[contract.pk]),
        reverse("hrm:employmentcontract_edit", args=[contract.pk]),
        reverse("hrm:hrpolicy_list"),
        reverse("hrm:hrpolicy_create"),
        reverse("hrm:hrpolicy_detail", args=[policy.pk]),
        reverse("hrm:hrpolicy_edit", args=[policy.pk]),
        reverse("hrm:policyacknowledgment_list"),
        reverse("hrm:grievance_list"),
        reverse("hrm:grievance_create") + f"?employee={employee.pk}",
        reverse("hrm:grievance_detail", args=[grievance.pk]),
        reverse("hrm:grievance_edit", args=[grievance.pk]),
        reverse("hrm:complianceregister_list"),
        reverse("hrm:complianceregister_create"),
        reverse("hrm:complianceregister_detail", args=[register.pk]),
        reverse("hrm:complianceregister_edit", args=[register.pk]),
    ]


def test_full_url_sweep_get_200(client_a, contract_a, policy_a, grievance_a, register_a, employee_a):
    """Every 3.39 list/create/detail/edit GET renders (200) for a tenant admin."""
    urls = _all_compliance_urls(contract_a, policy_a, grievance_a, register_a, employee_a)
    assert len(urls) == 17
    for url in urls:
        resp = client_a.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"


def test_no_template_comment_leaks_across_compliance_pages(client_a, contract_a, policy_a, grievance_a,
                                                            register_a, employee_a):
    """None of the 13 compliance templates leak a raw ``{#`` / ``{% comment`` marker into the response
    (Django strips real comment tags before rendering — a leak here means a template broke out of the
    tag, e.g. inside a ``{% verbatim %}`` block or a string literal)."""
    urls = _all_compliance_urls(contract_a, policy_a, grievance_a, register_a, employee_a)
    seen_titles = set()
    for url in urls:
        resp = client_a.get(url)
        assert resp.status_code == 200, url
        html = resp.content.decode()
        assert "{#" not in html, f"comment leak at {url}"
        assert "{% comment" not in html, f"comment leak at {url}"
        seen_titles.add(html.split("<title>", 1)[1].split("</title>", 1)[0] if "<title>" in html else "")
    # Sanity: the pages actually rendered distinct titles (not one broken template reused everywhere).
    assert len(seen_titles) > 1


# ============================================================ Full CRUD cycles via the real web forms
def test_employmentcontract_full_crud_via_form(client_a, tenant_a, employee_a, designation_a):
    """create -> edit (WITH a document upload, exercising the FileField clean()) -> delete."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.hrm.models import EmploymentContract

    # CREATE — file-less submission.
    resp = client_a.post(reverse("hrm:employmentcontract_create"), {
        "employee": employee_a.pk, "contract_type": "permanent",
        "start_date": TODAY.isoformat(), "notice_period_days": "30",
        "designation": designation_a.pk, "status": "active"})
    assert resp.status_code == 302
    obj = EmploymentContract.objects.get(tenant=tenant_a, employee=employee_a, contract_type="permanent")
    assert obj.number.startswith("CTR-")

    # EDIT — with a document upload this time.
    doc = SimpleUploadedFile("contract.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    resp = client_a.post(reverse("hrm:employmentcontract_edit", args=[obj.pk]), {
        "employee": employee_a.pk, "contract_type": "permanent",
        "start_date": TODAY.isoformat(), "notice_period_days": "45",
        "designation": designation_a.pk, "status": "active", "document": doc})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.notice_period_days == 45
    assert obj.document.name

    # DELETE
    resp = client_a.post(reverse("hrm:employmentcontract_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not EmploymentContract.objects.filter(pk=obj.pk).exists()


def test_hrpolicy_full_crud_via_form(client_a, tenant_a):
    """create -> edit -> delete, file-less throughout."""
    from apps.hrm.models import HRPolicy

    resp = client_a.post(reverse("hrm:hrpolicy_create"), {
        "title": "Data Protection Policy", "category": "it_security", "version_number": "1.0",
        "status": "draft", "requires_acknowledgment": "on"})
    assert resp.status_code == 302
    obj = HRPolicy.objects.get(tenant=tenant_a, title="Data Protection Policy")
    assert obj.number.startswith("POL-")

    resp = client_a.post(reverse("hrm:hrpolicy_edit", args=[obj.pk]), {
        "title": "Data Protection Policy", "category": "it_security", "version_number": "1.1",
        "status": "draft", "requires_acknowledgment": "on", "summary": "Updated summary."})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.version_number == "1.1" and obj.summary == "Updated summary."

    resp = client_a.post(reverse("hrm:hrpolicy_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not HRPolicy.objects.filter(pk=obj.pk).exists()


def test_complianceregister_full_crud_via_form(client_a, tenant_a):
    """create -> edit (status -> filed, which clean() requires filed_on for) -> delete."""
    from apps.hrm.models import ComplianceRegister

    resp = client_a.post(reverse("hrm:complianceregister_create"), {
        "register_type": "muster_roll", "title": "Muster Roll - August",
        "jurisdiction": "Karnataka", "status": "pending",
        "due_date": (TODAY + datetime.timedelta(days=20)).isoformat()})
    assert resp.status_code == 302
    obj = ComplianceRegister.objects.get(tenant=tenant_a, title="Muster Roll - August")
    assert obj.number.startswith("CMP-")

    resp = client_a.post(reverse("hrm:complianceregister_edit", args=[obj.pk]), {
        "register_type": "muster_roll", "title": "Muster Roll - August",
        "jurisdiction": "Karnataka", "status": "filed",
        "due_date": (TODAY + datetime.timedelta(days=20)).isoformat(), "filed_on": TODAY.isoformat()})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.status == "filed"

    resp = client_a.post(reverse("hrm:complianceregister_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not ComplianceRegister.objects.filter(pk=obj.pk).exists()


def test_complianceregister_filed_without_filed_on_shows_form_error(client_a, tenant_a):
    """clean() rejects status=filed without filed_on — must be a 200 re-render, not a 500."""
    from apps.hrm.models import ComplianceRegister
    before = ComplianceRegister.objects.filter(tenant=tenant_a).count()
    resp = client_a.post(reverse("hrm:complianceregister_create"), {
        "register_type": "muster_roll", "title": "Missing filed_on", "status": "filed"})
    assert resp.status_code == 200
    assert ComplianceRegister.objects.filter(tenant=tenant_a).count() == before


def test_grievance_full_crud_via_form(client_a, tenant_a, employee_a):
    """An HR admin (no linked EmployeeProfile) files ON BEHALF of ?employee=<id> -> edit -> delete,
    all while the grievance stays 'open' (the only status _hr_request_edit/_hr_request_delete allow)."""
    from apps.hrm.models import Grievance

    resp = client_a.post(reverse("hrm:grievance_create") + f"?employee={employee_a.pk}", {
        "category": "safety", "severity": "medium", "subject": "Broken chair",
        "description": "The chair in row 3 is broken."})
    assert resp.status_code == 302
    obj = Grievance.objects.get(tenant=tenant_a, subject="Broken chair")
    assert obj.number.startswith("GRV-")
    assert obj.employee_id == employee_a.pk
    assert obj.status == "open"

    resp = client_a.post(reverse("hrm:grievance_edit", args=[obj.pk]), {
        "category": "safety", "severity": "high", "subject": "Broken chair - urgent",
        "description": "The chair in row 3 is broken and needs urgent replacement."})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.severity == "high" and obj.subject == "Broken chair - urgent"

    resp = client_a.post(reverse("hrm:grievance_delete", args=[obj.pk]))
    assert resp.status_code == 302
    assert not Grievance.objects.filter(pk=obj.pk).exists()


# ============================================================ Multi-tenant IDOR (extended)
def test_multitenant_idor_404_contract_register_and_lifecycle_post(client_a, contract_b, register_b,
                                                                    grievance_b):
    """A tenant-A admin gets 404 (never a leaked object) for tenant-B's contract/register detail pages,
    AND for a lifecycle-mutating POST (grievance_resolve) against a tenant-B grievance."""
    from apps.hrm.models import Grievance
    assert client_a.get(reverse("hrm:employmentcontract_detail", args=[contract_b.pk])).status_code == 404
    assert client_a.get(reverse("hrm:complianceregister_detail", args=[register_b.pk])).status_code == 404
    resp = client_a.post(reverse("hrm:grievance_resolve", args=[grievance_b.pk]), {"resolution": "x"})
    assert resp.status_code == 404
    assert Grievance.objects.get(pk=grievance_b.pk).status == "open"  # untouched
