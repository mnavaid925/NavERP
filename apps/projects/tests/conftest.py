"""Projects app test fixtures — 7.1 Project Initiation & Charter (subslug ``projectinitiation``).

Reuses the shared ROOT conftest (``tenant_a``, ``tenant_b``, ``admin_user``, ``member_user``,
``admin_b``, ``client_a``, ``client_b``, ``member_client``) and adds only the domain records 7.1
needs: the core-spine rows its FKs point at, plus one fixture per interesting lifecycle state of
``ProjectRequest`` / ``Project`` / ``ProjectStakeholder`` / ``ProjectKickoff``.

**Naming rule (mandatory, and the reason every name below is so long).** Module 7 will keep
appending sub-modules to this same package. Every module-level helper here is ``_projectinitiation_*``
and every fixture ``projectinitiation_*``, so 7.2's fixtures cannot shadow 7.1's. Test functions
follow the same rule: ``test_projectinitiation_*``.

**Importing the factories.** The ``_projectinitiation_*`` helpers are plain functions, so a test
module pulls them in directly — the established peer pattern
(``apps/procurement/tests/test_dk_views.py``)::

    from apps.projects.tests.conftest import (
        _projectinitiation_project, _projectinitiation_request,
    )

**Numbering.** Every factory constructs the instance and calls ``.save()``, because
``TenantNumbered.save()`` is where ``number`` (``PRQ-00001`` / ``PRJ-`` / ``PST-`` / ``PKO-``) is
allocated through ``apps.core.utils.next_number``. ``bulk_create`` bypasses ``save()`` entirely and
would ship every row with an empty number — never use it here.

**Determinism (L16).** ``USE_TZ`` is True, so every date derives from ``timezone.localdate()`` and
every datetime from ``timezone.now()`` — the same basis ``Project.is_overdue`` and the views use.
``datetime.date.today()`` would flake for the hours either side of local midnight.

**Ownership.** Phase 6 step 1 owns this file. Steps 2-5 (``test_projectinitiation_models.py`` /
``_forms`` / ``_views`` / ``_security``) must not edit it; a shared-file change would need the whole
app suite re-run unfiltered (L47).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone


#: ``apps.core.crud.crud_list``'s default ``per_page``. Every 7.1 register uses the default, so a
#: pagination test needs ``PAGE_SIZE + 1`` rows to get a second page — hard-coding 15 in four test
#: modules is how that drifts when the default changes.
PROJECTINITIATION_PAGE_SIZE = 15


def _projectinitiation_today():
    """Today on the SAME basis the app uses (``Project.is_overdue`` → ``timezone.localdate()``)."""
    return timezone.localdate()


# ==================================================================================================
# Core-spine records the 7.1 FKs point at
# ==================================================================================================

@pytest.fixture
def projectinitiation_org_unit_a(db, tenant_a):
    """Tenant A's OrgUnit — the ``org_unit`` FK on both ProjectRequest and Project."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, name="Acme Delivery", kind="department")


@pytest.fixture
def projectinitiation_org_unit_b(db, tenant_b):
    """Tenant B's OrgUnit. A POST carrying this pk as tenant A must be REJECTED as a field error
    (``ProjectRequestForm.clean`` / ``ProjectForm.clean`` → ``_reject_foreign``), never saved."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_b, name="Globex Delivery", kind="department")


@pytest.fixture
def projectinitiation_party_a(db, tenant_a):
    """Tenant A organisation Party — a request's external ``requester_party`` and a project's
    ``client``."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Northwind Retail")


@pytest.fixture
def projectinitiation_person_a(db, tenant_a):
    """A SECOND tenant A Party, a person this time.

    ``ProjectStakeholder`` is unique on ``(tenant, project, party, raci_scope)``, so the duplicate
    test needs two distinct parties in one workspace to prove the constraint binds on the party and
    not on the row count.
    """
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="person", name="Dana Okafor")


@pytest.fixture
def projectinitiation_party_b(db, tenant_b):
    """Tenant B Party — the crafted-POST value for ``client`` / ``requester_party`` / the
    stakeholder's ``party``."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Holdings")


@pytest.fixture
def projectinitiation_document_a(db, tenant_a):
    """Tenant A ``core.Document`` — ``Project.charter_document`` (the signed charter; 7.1 ships NO
    second attachment store). ``file`` is a bare storage path: FileField accepts a string without
    touching the filesystem, so no upload is needed."""
    from apps.core.models import Document
    return Document.objects.create(
        tenant=tenant_a, name="Signed charter.pdf",
        file="documents/2026/09/signed-charter.pdf", classification="internal")


@pytest.fixture
def projectinitiation_document_b(db, tenant_b):
    """Tenant B document — the crafted-POST value for ``ProjectForm.charter_document``."""
    from apps.core.models import Document
    return Document.objects.create(
        tenant=tenant_b, name="Globex charter.pdf",
        file="documents/2026/09/globex-charter.pdf", classification="internal")


@pytest.fixture
def projectinitiation_currency(db):
    """USD. ``accounting.Currency`` is GLOBAL — it has NO ``tenant`` column (L29), so it is the one
    FK on ``ProjectRequestForm`` that ``_reject_foreign`` must never be handed (comparing
    ``currency.tenant_id`` would raise AttributeError) and the one ``TenantModelForm`` leaves
    unscoped. ``get_or_create`` because ``code`` is globally unique across the whole suite."""
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(
        code="USD", defaults={"name": "US Dollar", "symbol": "$"})
    return obj


@pytest.fixture
def projectinitiation_opportunity_a(db, tenant_a, projectinitiation_party_a):
    """Tenant A ``crm.Opportunity`` — a request's ``source_opportunity`` provenance."""
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant_a, name="Northwind scorecard rollout", account=projectinitiation_party_a,
        stage="qualification", amount=Decimal("75000.00"), probability=40)


@pytest.fixture
def projectinitiation_opportunity_b(db, tenant_b, projectinitiation_party_b):
    """Tenant B opportunity — the crafted-POST value for ``source_opportunity``."""
    from apps.crm.models import Opportunity
    return Opportunity.objects.create(
        tenant=tenant_b, name="Globex renewal", account=projectinitiation_party_b,
        stage="proposal", amount=Decimal("40000.00"), probability=60)


# ==================================================================================================
# Extra actors (the root conftest covers admin_user / member_user / admin_b and their clients)
# ==================================================================================================

@pytest.fixture
def projectinitiation_member_b(db, tenant_b):
    """A NON-admin member of tenant B. Lets a security test separate the two refusals: a tenant-B
    member hitting a tenant-A pk must 404 on scope, not 403 on role."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="member@globex.com", username="member_globex", password="TestPass123!",
        tenant=tenant_b, is_tenant_admin=False)


@pytest.fixture
def projectinitiation_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape, and also any member of a
    deleted tenant (``User.tenant`` is SET_NULL).

    Every 7.1 create view guards this on its FIRST line and redirects to ``dashboard:home`` rather
    than rendering a form whose FK dropdowns ``TenantModelForm`` never scoped.
    """
    from apps.accounts.models import User
    return User.objects.create_user(
        email="drifter@example.com", username="drifter", password="TestPass123!", tenant=None)


@pytest.fixture
def projectinitiation_tenantless_client(db, projectinitiation_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers render empty; creates redirect away."""
    client = Client()
    client.force_login(projectinitiation_tenantless_user)
    return client


@pytest.fixture
def projectinitiation_anon_client(db):
    """Unauthenticated — every 7.1 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def projectinitiation_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints ``number``
# ==================================================================================================

def _projectinitiation_request(tenant, **overrides):
    """A ``ProjectRequest`` in ``draft`` unless overridden.

    Every field the form and the register touch is populated with something non-trivial, so a
    search / filter / ``__str__`` assertion has real text to match. Pass ``status=...`` (and, for a
    decided row, ``decision`` + ``decided_by`` + ``decided_at``) to place it anywhere in the
    lifecycle — the model has no transition guard, the VIEWS do, which is exactly what lets a test
    park a row in a state and then assert the verb's refusal.

    Economics default to cost 120000 / benefit 300000 / risk ``medium`` →
    ``roi_pct`` 150.00, ``risk_adjusted_benefit`` 255000.00, ``risk_adjusted_roi_pct`` 112.50.
    """
    from apps.projects.models import ProjectRequest
    today = _projectinitiation_today()
    fields = dict(
        tenant=tenant,
        title="Replace the depot scheduling spreadsheet",
        description="The depot still schedules 40 vans from one shared workbook.",
        request_type="new_project",
        source="internal",
        priority="high",
        strategic_alignment=4,
        estimated_cost=Decimal("120000.00"),
        estimated_benefit=Decimal("300000.00"),
        risk_rating="medium",
        feasibility="feasible",
        feasibility_notes="Feasible once the depot Wi-Fi refresh lands.",
        alternatives_considered="1) Buy a routing SaaS. 2) Do nothing (rejected).",
        required_resources="One analyst, one developer, two months.",
        target_start_date=today + datetime.timedelta(days=30),
        target_end_date=today + datetime.timedelta(days=210),
        status="draft",
    )
    fields.update(overrides)
    # Construct + save(), never bulk_create: TenantNumbered.save() is where `number` is allocated.
    obj = ProjectRequest(**fields)
    obj.save()
    return obj


def _projectinitiation_project(tenant, **overrides):
    """A ``Project`` with ``status="draft"`` / ``charter_status="draft"`` unless overridden.

    ``end_date`` is 180 days out, so ``is_overdue`` is False by default; pass an ``end_date`` in the
    past to exercise the True branch (and remember ``completed``/``cancelled`` suppress it).
    """
    from apps.projects.models import Project
    today = _projectinitiation_today()
    fields = dict(
        tenant=tenant,
        name="Depot scheduling replacement",
        code="DSR-01",
        description="Retire the shared workbook.",
        methodology="hybrid",
        in_scope="Van scheduling, driver rostering.",
        out_of_scope="Vehicle maintenance planning.",
        objectives="One scheduling system of record.",
        success_criteria="Zero spreadsheet-based schedules after go-live.",
        assumptions="The depot Wi-Fi refresh completes first.",
        constraints="No downtime during the peak season.",
        risk_summary="Driver adoption is the main risk.",
        start_date=today + datetime.timedelta(days=30),
        end_date=today + datetime.timedelta(days=180),
        status="draft",
        charter_status="draft",
    )
    fields.update(overrides)
    obj = Project(**fields)
    obj.save()
    return obj


def _projectinitiation_stakeholder(project, party=None, user=None, **overrides):
    """A ``ProjectStakeholder`` on ``project``; ``tenant`` is taken FROM the project.

    ``ProjectStakeholder.clean()`` requires a ``party`` OR a ``user`` — and ``.save()`` does not run
    ``clean()``, so a row with neither would save happily and identify nobody. When the caller gives
    neither, this mints a fresh ``core.Party`` in the project's tenant, which also keeps the
    ``(tenant, project, party, raci_scope)`` unique_together satisfied when filling a page.

    Defaults: ``influence="high"``, ``interest="high"`` → ``engagement_strategy ==
    "manage_closely"``, and ``attending_kickoff=False`` (opt in explicitly — the kickoff
    ``attendee_total`` annotation counts exactly the rows that set it True).
    """
    from apps.core.models import Party
    from apps.projects.models import ProjectStakeholder
    if party is None and user is None:
        seq = ProjectStakeholder.objects.filter(tenant=project.tenant_id).count() + 1
        party = Party.objects.create(
            tenant=project.tenant, kind="person", name=f"Stakeholder {seq:02d}")
    fields = dict(
        tenant=project.tenant,
        project=project,
        party=party,
        user=user,
        stakeholder_type="sponsor",
        raci_role="a",
        raci_scope="charter approval",
        influence="high",
        interest="high",
        comms_preference="email",
        comms_frequency="weekly",
        attending_kickoff=False,
        notes="Signs the charter.",
    )
    fields.update(overrides)
    obj = ProjectStakeholder(**fields)
    obj.save()
    return obj


def _projectinitiation_kickoff(project, **overrides):
    """A ``ProjectKickoff`` on ``project``; ``tenant`` is taken FROM the project.

    ``unique_together = ("tenant", "project")`` — ONE kickoff per project, so every kickoff fixture
    below builds its own project rather than sharing one. ``meeting_date`` defaults to 7 days out
    (``pko_schedule`` refuses a kickoff without one); pass ``meeting_date=None`` for that refusal.
    """
    from apps.projects.models import ProjectKickoff
    fields = dict(
        tenant=project.tenant,
        project=project,
        meeting_date=timezone.now() + datetime.timedelta(days=7),
        location_or_link="Depot boardroom / meet.example.com/kickoff",
        agenda_template="standard",
        agenda="Charter walkthrough, roles, milestones, Q&A.",
        attendee_summary="Two external partner reps not on the register.",
        onboarding_notes="Laptops, VPN, repo access.",
        status="planned",
        notes="Catering booked.",
    )
    fields.update(overrides)
    obj = ProjectKickoff(**fields)
    obj.save()
    return obj


def _projectinitiation_activity(project, **overrides):
    """A ``core.Activity`` GFK'd to ``project`` — the onboarding checklist 7.1 deliberately did NOT
    give its own table. ``pko_detail`` renders these as its ``activities`` context key."""
    from django.contrib.contenttypes.models import ContentType
    from apps.core.models import Activity
    from apps.projects.models import Project
    fields = dict(
        tenant=project.tenant,
        kind="task",
        subject="Grant repository access",
        status="open",
        content_type=ContentType.objects.get_for_model(Project),
        object_id=project.pk,
        due_at=timezone.now() + datetime.timedelta(days=3),
    )
    fields.update(overrides)
    return Activity.objects.create(**fields)


# -- bulk fills (pagination / N+1 / search) ---------------------------------------------------------
#
# Loops over the factories rather than bulk_create for the reason spelled out at the top of this
# file: bulk_create skips save(), and save() is where `number` is minted.

def _projectinitiation_fill_requests(tenant, count, **overrides):
    """``count`` requests with distinct titles (``Backlog request 01`` …). Returns the list."""
    return [
        _projectinitiation_request(tenant, title=f"Backlog request {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _projectinitiation_fill_projects(tenant, count, **overrides):
    """``count`` projects with distinct names (``Backlog project 01`` …). Returns the list."""
    return [
        _projectinitiation_project(tenant, name=f"Backlog project {i:02d}",
                                   code=f"BLP-{i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _projectinitiation_fill_stakeholders(project, count, **overrides):
    """``count`` stakeholders on ONE project, each with its own auto-minted party."""
    return [
        _projectinitiation_stakeholder(project, raci_scope=f"scope {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _projectinitiation_fill_kickoffs(tenant, count, **overrides):
    """``count`` kickoffs — and ``count`` projects to hang them on, because ``(tenant, project)`` is
    unique. Returns the kickoff list; each kickoff's project is reachable as ``k.project``."""
    return [
        _projectinitiation_kickoff(
            _projectinitiation_project(tenant, name=f"Kickoff host {i:02d}", code=f"KHP-{i:02d}"),
            **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# ProjectRequest — one fixture per lifecycle state the verbs branch on
# ==================================================================================================

@pytest.fixture
def projectinitiation_request_draft(db, tenant_a, admin_user, projectinitiation_org_unit_a,
                                    projectinitiation_party_a, projectinitiation_currency):
    """``draft`` — nothing decided, nothing submitted.

    The one state where ``prq_edit`` is open (no ``decided_at``) and ``prq_submit`` is allowed.
    ``prq_approve`` / ``prq_reject`` must REFUSE it: ``DECISION_STATUSES`` is
    ``("submitted", "screening", "assessment")``, so a never-submitted draft cannot be decided
    (L35 — the absent-prerequisite case must be rejected, not fall through to approval).
    ``prq_return_for_information`` refuses it too ("a draft request cannot be sent back").
    """
    return _projectinitiation_request(
        tenant_a, org_unit=projectinitiation_org_unit_a, requester_party=projectinitiation_party_a,
        currency=projectinitiation_currency, requested_by=admin_user,
        assigned_reviewer=admin_user, assigned_approver=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_submitted(db, tenant_a, admin_user, projectinitiation_org_unit_a,
                                        projectinitiation_currency):
    """``submitted`` with ``submitted_at`` stamped — in ``DECISION_STATUSES``.

    The happy path for ``prq_approve`` / ``prq_reject`` / ``prq_return_for_information``, and still
    editable (no ``decided_at``).
    """
    return _projectinitiation_request(
        tenant_a, title="Customer portal self-service returns", status="submitted",
        submitted_at=timezone.now() - datetime.timedelta(days=2),
        org_unit=projectinitiation_org_unit_a, currency=projectinitiation_currency,
        requested_by=admin_user, assigned_approver=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_screening(db, tenant_a, admin_user):
    """``screening`` — the SECOND member of ``DECISION_STATUSES``.

    Exists so a test proves the gate is the tuple and not a hard-coded ``== "submitted"``.
    """
    return _projectinitiation_request(
        tenant_a, title="Replace legacy nightly batch export", status="screening",
        request_type="change_request", priority="medium",
        submitted_at=timezone.now() - datetime.timedelta(days=5),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_needs_information(db, tenant_a, admin_user):
    """``needs_information`` with the question recorded and NO decision stamps.

    Two contracts meet here: ``prq_submit`` accepts it as a source (re-submission after a send-back
    is the normal path), and ``prq_edit`` is OPEN again because the send-back cleared
    ``decided_at`` — that clearing IS the reopen path. ``prq_return_for_information`` must refuse a
    second send-back ("already waiting on information").
    """
    return _projectinitiation_request(
        tenant_a, title="Consolidate two regional warehouses", status="needs_information",
        priority="critical", estimated_cost=Decimal("640000.00"),
        estimated_benefit=Decimal("900000.00"),
        information_requested="Lease break costs for both sites.",
        submitted_at=timezone.now() - datetime.timedelta(days=9),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_approved(db, tenant_a, admin_user, projectinitiation_org_unit_a,
                                       projectinitiation_party_a):
    """``approved`` + ``decision="go"`` + decision stamps, NOT yet converted.

    The only state ``prq_convert`` accepts. Also the ``prq_edit`` LOCK case: the lock follows
    ``decided_at``, not a status list, so this row must redirect to detail with an error instead of
    rendering the form. ``org_unit`` / ``requester_party`` / ``assigned_approver`` are populated
    because ``convert_to_project()`` copies them onto the new ``Project``.
    """
    return _projectinitiation_request(
        tenant_a, title="Supplier scorecard rollout", status="approved", decision="go",
        strategic_alignment=5, estimated_cost=Decimal("55000.00"),
        estimated_benefit=Decimal("175000.00"),
        decided_by=admin_user, decided_at=timezone.now() - datetime.timedelta(days=1),
        submitted_at=timezone.now() - datetime.timedelta(days=6),
        org_unit=projectinitiation_org_unit_a, requester_party=projectinitiation_party_a,
        assigned_approver=admin_user, requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_rejected(db, tenant_a, admin_user):
    """``rejected`` + ``decision="no_go"`` + a stated ``rejection_reason``.

    ``prq_reject`` must answer "already rejected" (info, no re-stamp) and ``prq_edit`` is locked by
    the ``decided_at`` stamp.
    """
    return _projectinitiation_request(
        tenant_a, title="In-house fleet telematics build", status="rejected", decision="no_go",
        priority="low", feasibility="not_feasible", risk_rating="high",
        estimated_cost=Decimal("320000.00"), estimated_benefit=Decimal("140000.00"),
        rejection_reason="Negative ROI and three mature vendors already do this better.",
        decided_by=admin_user, decided_at=timezone.now() - datetime.timedelta(days=3),
        submitted_at=timezone.now() - datetime.timedelta(days=8),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_deferred(db, tenant_a, admin_user):
    """``deferred`` — outside ``DECISION_STATUSES``, so approve/reject must refuse it, and it is
    NOT ``converted``, so ``prq_edit`` is still open (no decision stamp)."""
    return _projectinitiation_request(
        tenant_a, title="Blockchain provenance pilot", status="deferred", request_type="idea",
        priority="low", estimated_cost=Decimal("90000.00"), estimated_benefit=Decimal("0.00"),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_request_converted(db, projectinitiation_request_approved, admin_user):
    """An approved request run through the REAL ``convert_to_project()``.

    Nothing here hand-stamps ``converted_project``: the compare-and-swap inside
    ``transaction.atomic()`` is the thing under test everywhere else, so the fixture must not route
    around it. After this, ``status == "converted"``, ``converted_project`` is set, and the new
    project is reachable as ``fixture.converted_project`` (also as ``project.request`` from the
    other side). ``prq_convert`` must now answer "already converted", and ``prq_edit`` is locked
    twice over (``decided_at`` AND ``status == "converted"``).
    """
    project = projectinitiation_request_approved.convert_to_project(user=admin_user)
    assert project is not None, "convert_to_project() refused an approved request — precondition broken"
    projectinitiation_request_approved.refresh_from_db()
    return projectinitiation_request_approved


@pytest.fixture
def projectinitiation_request_b(db, tenant_b, admin_b, projectinitiation_org_unit_b):
    """Tenant B's request. As tenant A: 404 on detail/edit/delete and on all five verbs, and it must
    never appear in tenant A's register."""
    return _projectinitiation_request(
        tenant_b, title="Globex only request", status="submitted",
        org_unit=projectinitiation_org_unit_b, requested_by=admin_b, created_by=admin_b,
        submitted_at=timezone.now() - datetime.timedelta(days=1))


# ==================================================================================================
# Project — one fixture per charter/status combination the verbs branch on
# ==================================================================================================

@pytest.fixture
def projectinitiation_project_draft(db, tenant_a, admin_user, member_user,
                                    projectinitiation_org_unit_a, projectinitiation_party_a,
                                    projectinitiation_document_a):
    """``status="draft"`` / ``charter_status="draft"`` — freshly authored.

    ``prj_edit`` is open, ``prj_submit_charter`` accepts it, and ``prj_approve_charter`` must
    REFUSE it ("Submit the charter before approving it") — the L35 absent-prerequisite case.
    """
    return _projectinitiation_project(
        tenant_a, org_unit=projectinitiation_org_unit_a, client=projectinitiation_party_a,
        charter_document=projectinitiation_document_a, executive_sponsor=admin_user,
        project_manager=member_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_project_charter_submitted(db, tenant_a, admin_user,
                                                projectinitiation_org_unit_a):
    """``charter_status="submitted"``, project still ``draft``.

    The only state ``prj_approve_charter`` accepts; approving it also walks ``status`` draft →
    ``chartered``. ``prj_submit_charter`` must answer "already submitted or approved".
    """
    return _projectinitiation_project(
        tenant_a, name="Supplier scorecard rollout", code="SSR-01",
        charter_status="submitted", org_unit=projectinitiation_org_unit_a,
        executive_sponsor=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_project_charter_approved(db, tenant_a, admin_user,
                                               projectinitiation_org_unit_a):
    """``charter_status="approved"`` + approval stamps, ``status="chartered"``.

    Two contracts: ``prj_edit`` is LOCKED (an approved charter is evidence — the view redirects to
    detail with an error before ``crud_edit`` ever runs), and it is the ONLY project shape on which
    ``pko_complete`` may finish a kickoff.
    """
    return _projectinitiation_project(
        tenant_a, name="Second shift at the northern plant", code="SSN-01",
        status="chartered", charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=2),
        org_unit=projectinitiation_org_unit_a, executive_sponsor=admin_user, created_by=admin_user)


@pytest.fixture
def projectinitiation_project_charter_rejected(db, tenant_a, admin_user):
    """``charter_status="rejected"`` — a RESERVED choice no 7.1 verb sets, but which
    ``prj_submit_charter`` explicitly accepts as a source so a rejected charter can be resubmitted.

    Constructed directly for exactly that reason: there is no verb to reach it through.
    """
    return _projectinitiation_project(
        tenant_a, name="Rejected charter project", code="RCP-01",
        charter_status="rejected", created_by=admin_user)


@pytest.fixture
def projectinitiation_project_cancelled(db, tenant_a, admin_user):
    """``status="cancelled"`` — in ``TERMINAL_STATUSES``, charter still ``draft``.

    BOTH charter verbs must refuse it on the status gate BEFORE they look at ``charter_status``:
    without that, a cancelled project could be walked to a green "Approved" charter with a fresh
    approval stamp.
    """
    return _projectinitiation_project(
        tenant_a, name="Cancelled depot pilot", code="CDP-01", status="cancelled",
        created_by=admin_user)


@pytest.fixture
def projectinitiation_project_overdue(db, tenant_a, admin_user):
    """``end_date`` 5 days in the PAST and ``status="active"`` → ``is_overdue`` is True.

    Dates come from ``timezone.localdate()``, the same basis ``is_overdue`` compares against (L16).
    Pair it with ``projectinitiation_project_draft`` (end date in the future → False) and with a
    completed/cancelled copy (terminal → False even when the date has passed).
    """
    today = _projectinitiation_today()
    return _projectinitiation_project(
        tenant_a, name="Overdue rollout", code="OVR-01", status="active",
        charter_status="approved", start_date=today - datetime.timedelta(days=120),
        end_date=today - datetime.timedelta(days=5), created_by=admin_user)


@pytest.fixture
def projectinitiation_project_b(db, tenant_b, admin_b, projectinitiation_org_unit_b,
                                projectinitiation_party_b):
    """Tenant B's project. As tenant A: 404 on detail/edit/delete/both charter verbs, absent from
    tenant A's register, and refused as a crafted ``project`` FK on the stakeholder and kickoff
    forms."""
    return _projectinitiation_project(
        tenant_b, name="Globex only project", code="GBX-01",
        org_unit=projectinitiation_org_unit_b, client=projectinitiation_party_b,
        executive_sponsor=admin_b, created_by=admin_b)


# ==================================================================================================
# ProjectStakeholder
# ==================================================================================================

@pytest.fixture
def projectinitiation_stakeholder_a(db, projectinitiation_project_draft, projectinitiation_party_a):
    """Sponsor, RACI ``a``, scope "charter approval", influence/interest both ``high`` →
    ``engagement_strategy == "manage_closely"``, and ``attending_kickoff=True``."""
    return _projectinitiation_stakeholder(
        projectinitiation_project_draft, party=projectinitiation_party_a,
        attending_kickoff=True)


@pytest.fixture
def projectinitiation_stakeholder_monitor(db, projectinitiation_project_draft,
                                          projectinitiation_person_a):
    """The OTHER quadrant: influence ``medium`` / interest ``low`` → ``"monitor"``.

    ``medium`` maps to the LOW side on both axes — deliberate and documented on the property, and
    the reason this fixture exists rather than a second ``high`` row.
    """
    return _projectinitiation_stakeholder(
        projectinitiation_project_draft, party=projectinitiation_person_a,
        stakeholder_type="subject_matter_expert", raci_role="c", raci_scope="data migration",
        influence="medium", interest="low", comms_preference="written_report",
        comms_frequency="monthly")


@pytest.fixture
def projectinitiation_stakeholder_user_only(db, projectinitiation_project_draft, member_user):
    """``user`` set, ``party`` NULL — the second half of the "name a party OR a user" rule.

    Its ``__str__`` falls through to the user, and the ``(tenant, project, party, raci_scope)``
    unique_together does NOT bind on it (SQL treats every NULL as distinct), which is precisely why
    ``ProjectStakeholder.clean()`` carries the check too.
    """
    return _projectinitiation_stakeholder(
        projectinitiation_project_draft, user=member_user, stakeholder_type="team_member",
        raci_role="r", raci_scope="delivery", influence="low", interest="high")


@pytest.fixture
def projectinitiation_stakeholder_b(db, projectinitiation_project_b, projectinitiation_party_b):
    """Tenant B's stakeholder — 404 as tenant A, absent from tenant A's register."""
    return _projectinitiation_stakeholder(
        projectinitiation_project_b, party=projectinitiation_party_b)


# ==================================================================================================
# ProjectKickoff — one kickoff per project (``unique_together = ("tenant", "project")``),
# so every fixture below builds its OWN project.
# ==================================================================================================

@pytest.fixture
def projectinitiation_kickoff_planned(db, projectinitiation_project_draft):
    """``planned`` WITH a meeting date — the one shape ``pko_schedule`` accepts.

    ``pko_mark_held`` must refuse it ("Schedule the kickoff before marking it held") — ``planned``
    is deliberately NOT an allowed source, or the "set a meeting date first" requirement could be
    skipped. Hangs off ``projectinitiation_project_draft`` so a test can assert the project's status
    is untouched by a refused verb.
    """
    return _projectinitiation_kickoff(projectinitiation_project_draft)


@pytest.fixture
def projectinitiation_kickoff_undated(db, tenant_a, admin_user):
    """``planned`` and ``meeting_date=None`` — ``pko_schedule`` must refuse it with "Set a meeting
    date before scheduling the kickoff", not schedule a ceremony with no date."""
    project = _projectinitiation_project(
        tenant_a, name="Undated kickoff host", code="UKH-01", created_by=admin_user)
    return _projectinitiation_kickoff(project, meeting_date=None)


@pytest.fixture
def projectinitiation_kickoff_scheduled(db, tenant_a, admin_user):
    """``scheduled`` on a ``chartered`` project whose charter is only ``submitted``.

    The one state ``pko_mark_held`` accepts (and holding it walks the project ``chartered`` →
    ``kickoff``). ``pko_mark_baseline_set`` must still REFUSE it: a merely scheduled ceremony has
    not happened, and the stamp attests who accepted the baseline AT it.
    """
    project = _projectinitiation_project(
        tenant_a, name="Scheduled kickoff host", code="SKH-01", status="chartered",
        charter_status="submitted", created_by=admin_user)
    return _projectinitiation_kickoff(project, status="scheduled")


@pytest.fixture
def projectinitiation_kickoff_held(db, tenant_a, admin_user):
    """``held``, but on a project whose ``charter_status`` is still ``draft``.

    The L35 case for ``pko_complete``: the kickoff prerequisite is met and the CHARTER one is not,
    so completing must be refused ("Approve the charter before completing the kickoff") rather than
    landing an ``active`` project on an unapproved charter — which would route straight around the
    ``@tenant_admin_required`` on ``prj_approve_charter``. ``pko_mark_baseline_set`` DOES accept
    this one.
    """
    project = _projectinitiation_project(
        tenant_a, name="Held kickoff host", code="HKH-01", status="kickoff",
        charter_status="draft", created_by=admin_user)
    return _projectinitiation_kickoff(project, status="held")


@pytest.fixture
def projectinitiation_kickoff_ready_to_complete(db, tenant_a, admin_user):
    """``held`` on a project whose charter IS ``approved`` — the happy path for ``pko_complete``.

    Completing stamps ``completed_at`` and walks the project ``kickoff`` → ``active``.
    """
    project = _projectinitiation_project(
        tenant_a, name="Completable kickoff host", code="CKH-01", status="kickoff",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=1), created_by=admin_user)
    return _projectinitiation_kickoff(project, status="held")


@pytest.fixture
def projectinitiation_kickoff_completed(db, tenant_a, admin_user):
    """``completed`` with ``completed_at`` stamped, on an ``active`` project.

    Terminal: ``pko_schedule`` / ``pko_mark_held`` / ``pko_complete`` must each answer with an
    already-past-that-point message and change nothing.
    """
    project = _projectinitiation_project(
        tenant_a, name="Completed kickoff host", code="XKH-01", status="active",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=10), created_by=admin_user)
    return _projectinitiation_kickoff(
        project, status="completed", meeting_date=timezone.now() - datetime.timedelta(days=5),
        completed_at=timezone.now() - datetime.timedelta(days=4))


@pytest.fixture
def projectinitiation_kickoff_baselined(db, tenant_a, admin_user):
    """``held`` with the baseline ALREADY acknowledged.

    ``pko_mark_baseline_set`` must refuse to re-stamp: the acknowledgement is evidence of who
    accepted the baseline and when, so a second click must not overwrite the first.
    """
    project = _projectinitiation_project(
        tenant_a, name="Baselined kickoff host", code="BKH-01", status="kickoff",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=6), created_by=admin_user)
    return _projectinitiation_kickoff(
        project, status="held", baseline_acknowledged_by=admin_user,
        baseline_acknowledged_at=timezone.now() - datetime.timedelta(days=1))


@pytest.fixture
def projectinitiation_kickoff_with_attendees(db, tenant_a, admin_user, member_user):
    """A ``scheduled`` kickoff whose project carries THREE stakeholders, exactly TWO attending.

    Pins the ``attendee_total`` annotation (``pko_list`` and ``prj_detail``) and the
    ``attendee_count`` property to the same expected value of **2** — the annotation deliberately
    uses a DIFFERENT name because ``attendee_count`` is a property (a data descriptor), and
    annotating over it raises "AttributeError: can't set attribute".
    """
    project = _projectinitiation_project(
        tenant_a, name="Attendee kickoff host", code="AKH-01", created_by=admin_user)
    _projectinitiation_stakeholder(project, raci_scope="scope a", attending_kickoff=True)
    _projectinitiation_stakeholder(project, user=member_user, raci_scope="scope b",
                                   attending_kickoff=True)
    _projectinitiation_stakeholder(project, raci_scope="scope c", attending_kickoff=False)
    return _projectinitiation_kickoff(project, status="scheduled")


@pytest.fixture
def projectinitiation_kickoff_b(db, projectinitiation_project_b):
    """Tenant B's kickoff — 404 as tenant A on detail/edit/delete and on all four ceremony verbs."""
    return _projectinitiation_kickoff(projectinitiation_project_b)


@pytest.fixture
def projectinitiation_activity_a(db, projectinitiation_project_draft):
    """One ``core.Activity`` GFK'd to tenant A's draft project — the ``activities`` block on the
    kickoff detail page."""
    return _projectinitiation_activity(projectinitiation_project_draft)


# ==================================================================================================
# 7.2 Project Planning & Scheduling (subslug ``planning``) — OWNED BY PHASE 6 STEP 1
#
# Same rules as the 7.1 block above, prefixed ``planning_`` / ``_planning_`` so the two lanes can
# never shadow each other. See ``.claude/tasks/test-contract-projects-7.2.md`` for the test
# contract these fixtures serve (test files: test_planning_models/_forms/_views/_security.py).
#
# * Factories construct + ``.save()`` — ``TenantNumbered.save()`` is where ``TSK-/DEP-/MST-/BSL-``
#   numbers are minted; ``bulk_create`` would ship empty numbers and is never used here.
# * Determinism (L16): every date derives from ``_planning_today()`` (``timezone.localdate()``),
#   the same basis ``ProjectMilestone.is_late`` and the achievement stamp use.
# * Projects reuse the 7.1 FACTORY ``_projectinitiation_project`` (function import, NOT the 7.1
#   fixtures — the planning lane must not depend on 7.1's fixture rows). Host projects are ACTIVE
#   with an approved charter, the lifecycle stage a plan actually lives in.
# * The admin client for 7.2 is the ROOT conftest's ``client_a`` — exactly as 7.1, which defines
#   no admin-client fixture of its own either. No ``planning_client`` exists on purpose.
# * Tests NEVER touch ``management/commands/seed_projects.py`` (the demo seed) — every test builds
#   exactly the rows it asserts on from the factories below.
# ==================================================================================================

#: ``apps.core.crud.crud_list``'s default ``per_page`` — every 7.2 register uses the default, so a
#: pagination test needs ``PLANNING_PAGE_SIZE + 1`` rows for a second page (same rationale as
#: ``PROJECTINITIATION_PAGE_SIZE`` above).
PLANNING_PAGE_SIZE = 15


def _planning_today():
    """Today on the SAME basis the 7.2 code uses (``is_late`` / ``freeze_snapshot`` →
    ``timezone.localdate()``)."""
    return timezone.localdate()


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints TSK-/DEP-/MST-/BSL-
# ==================================================================================================

def _planning_task(tenant, project, parent=None, **overrides):
    """A ``ProjectTask`` work package on ``project``; ``parent=None`` roots it.

    Defaults: ``node_type="work_package"``, ``status="planned"``, ``estimation_method="bottom_up"``,
    ``confidence="medium"``, ``sequence=0``, a distinct per-tenant ``name`` ("Work package NN"),
    ``planned_start=today`` / ``planned_end=today+4`` (``duration_days == 5``) and
    ``effort_hours=40.00``. Pass ``node_type="deliverable"`` for a rollup node and ``sequence=``
    wherever sibling order matters (the tree and the critical-path tie-breaks read it).
    """
    from apps.projects.models import ProjectTask
    today = _planning_today()
    seq = ProjectTask.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        parent=parent,
        node_type="work_package",
        name=f"Work package {seq:02d}",
        description="A schedulable leaf of the work breakdown structure.",
        status="planned",
        planned_start=today,
        planned_end=today + datetime.timedelta(days=4),
        effort_hours=Decimal("40.00"),
        estimation_method="bottom_up",
        confidence="medium",
        sequence=0,
    )
    fields.update(overrides)
    obj = ProjectTask(**fields)
    obj.save()
    return obj


def _planning_dependency(tenant, predecessor, successor, **overrides):
    """A ``TaskDependency`` edge predecessor → successor (``finish_to_start``, ``lag_days=0``).

    Both endpoints must belong to ONE project — ``clean()`` refuses self-links and cross-project /
    cross-tenant pairs, so a malformed call raises at build time instead of seeding bad data.
    """
    from apps.projects.models import TaskDependency
    fields = dict(
        tenant=tenant,
        predecessor=predecessor,
        successor=successor,
        link_type="finish_to_start",
        lag_days=0,
        note="",
    )
    fields.update(overrides)
    obj = TaskDependency(**fields)
    # ``clean()`` (NOT ``full_clean()`` — that would fail on the still-unminted blank ``number``)
    # so a self-link or cross-project pair surfaces at build time instead of seeding bad data.
    obj.clean()
    obj.save()
    return obj


def _planning_milestone(tenant, project, **overrides):
    """A ``ProjectMilestone`` on ``project``: ``status="planned"``, ``target_date=today+30``,
    ``is_phase_gate=False``, a distinct per-tenant ``name`` ("Milestone NN").

    Pass ``status="achieved"`` to let ``save()`` stamp ``actual_date`` itself — the stamping is the
    model's job and the factory must not pre-empt it.
    """
    from apps.projects.models import ProjectMilestone
    seq = ProjectMilestone.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        anchor_task=None,
        name=f"Milestone {seq:02d}",
        description="A date that matters.",
        target_date=_planning_today() + datetime.timedelta(days=30),
        is_phase_gate=False,
        entry_criteria="",
        exit_criteria="",
        status="planned",
    )
    fields.update(overrides)
    obj = ProjectMilestone(**fields)
    obj.save()
    return obj


def _planning_baseline(tenant, project, **overrides):
    """A ``ScheduleBaseline`` on ``project`` — ``what_if`` by default, so NOT frozen and NOT
    active (the editable working-copy shape every verb accepts).

    ``baseline_type="baseline"`` + ``is_active=True`` builds the project's managed baseline;
    snapshot columns are left empty — filling them by hand would fake the freeze ``bsl_promote``
    performs, and the views/tests must observe the REAL ``freeze_snapshot()`` output.
    """
    from apps.projects.models import ScheduleBaseline
    seq = ScheduleBaseline.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        name=f"What-if {seq:02d}",
        baseline_type="what_if",
        is_active=False,
        strategy_note="",
        note="",
    )
    fields.update(overrides)
    obj = ScheduleBaseline(**fields)
    obj.save()
    return obj


def _planning_wbs_tree(tenant, project):
    """A 2-deliverable × 2-work-package WBS on ``project``; returns named tasks in a dict.

    Keys: ``d1`` / ``d2`` (``node_type="deliverable"``, undated and effort-less on purpose — their
    rollups must come from the children) and ``wp11`` / ``wp12`` / ``wp21`` / ``wp22``. Sibling
    order is explicit: d1 (seq 1) ← wp11 (seq 1) + wp12 (seq 2); d2 (seq 2) ← wp21 (seq 1) +
    wp22 (seq 2) — so the tree view must code them 1 / 1.1 / 1.2 / 2 / 2.1 / 2.2.

    Windows: wp11 today→today+2 (3 days, 24.00h), wp12 today+3→today+4 (2 days, 16.00h), wp21
    today→today (1 day, 8.00h), wp22 today+1→today+2 (2 days, 8.00h). Deliverable rollups: d1 →
    start today / end today+4 / 40.00h / count 2; d2 → start today / end today+2 / 16.00h / count 2.
    """
    d1 = _planning_task(tenant, project, node_type="deliverable", name="Deliverable One",
                        sequence=1, planned_start=None, planned_end=None, effort_hours=None)
    d2 = _planning_task(tenant, project, node_type="deliverable", name="Deliverable Two",
                        sequence=2, planned_start=None, planned_end=None, effort_hours=None)
    today = _planning_today()
    wp11 = _planning_task(tenant, project, parent=d1, name="Survey", sequence=1,
                          planned_start=today, planned_end=today + datetime.timedelta(days=2),
                          effort_hours=Decimal("24.00"))
    wp12 = _planning_task(tenant, project, parent=d1, name="Build", sequence=2,
                          planned_start=today + datetime.timedelta(days=3),
                          planned_end=today + datetime.timedelta(days=4),
                          effort_hours=Decimal("16.00"))
    wp21 = _planning_task(tenant, project, parent=d2, name="Pilot", sequence=1,
                          planned_start=today, planned_end=today,
                          effort_hours=Decimal("8.00"))
    wp22 = _planning_task(tenant, project, parent=d2, name="Rollout", sequence=2,
                          planned_start=today + datetime.timedelta(days=1),
                          planned_end=today + datetime.timedelta(days=2),
                          effort_hours=Decimal("8.00"))
    return {"d1": d1, "d2": d2, "wp11": wp11, "wp12": wp12, "wp21": wp21, "wp22": wp22}


def _planning_fill_tasks(tenant, project, count, **overrides):
    """``count`` root work packages on ONE project with distinct names (``Backlog task 01`` …).
    Returns the list."""
    return [
        _planning_task(tenant, project, name=f"Backlog task {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# Fixtures — host projects, one row per interesting state, the 7.2 client set
# ==================================================================================================

@pytest.fixture
def planning_project_a(db, tenant_a, admin_user):
    """Tenant A's ACTIVE planning host (charter approved — the stage a plan lives in).

    Built through the 7.1 factory; every 7.2 row hangs off this or ``planning_project_b``.
    """
    return _projectinitiation_project(
        tenant_a, name="Planning host Alpha", code="PLA-01", status="active",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        created_by=admin_user)


@pytest.fixture
def planning_project_b(db, tenant_b, admin_b):
    """Tenant B's ACTIVE planning host — the cross-tenant target every 404/foreign-FK test needs."""
    return _projectinitiation_project(
        tenant_b, name="Planning host Beta", code="PLB-01", status="active",
        charter_status="approved", charter_approved_by=admin_b,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        created_by=admin_b)


@pytest.fixture
def planning_task_a(db, planning_project_a):
    """A default tenant A work package — the detail/edit/delete round-trip subject."""
    return _planning_task(planning_project_a.tenant, planning_project_a)


@pytest.fixture
def planning_task_b(db, planning_project_b):
    """Tenant B's work package — 404 as tenant A on detail/edit/delete, absent from A's register,
    refused as a crafted ``parent`` / ``anchor_task`` / dependency-endpoint FK."""
    return _planning_task(planning_project_b.tenant, planning_project_b)


@pytest.fixture
def planning_dependency_a(db, planning_project_a):
    """A ``finish_to_start`` edge between two factory tasks on project A; the endpoints are
    reachable as ``.predecessor`` / ``.successor``."""
    tenant = planning_project_a.tenant
    return _planning_dependency(
        tenant,
        _planning_task(tenant, planning_project_a),
        _planning_task(tenant, planning_project_a))


@pytest.fixture
def planning_dependency_b(db, planning_project_b):
    """Tenant B's dependency — 404 as tenant A on detail/edit/delete."""
    tenant = planning_project_b.tenant
    return _planning_dependency(
        tenant,
        _planning_task(tenant, planning_project_b),
        _planning_task(tenant, planning_project_b))


@pytest.fixture
def planning_milestone_a(db, planning_project_a):
    """A ``planned`` tenant A milestone — the ``mst_achieve`` happy path / the member I4 page."""
    return _planning_milestone(planning_project_a.tenant, planning_project_a)


@pytest.fixture
def planning_milestone_b(db, planning_project_b):
    """Tenant B's milestone — 404 as tenant A on detail/edit/delete and on ``mst_achieve``."""
    return _planning_milestone(planning_project_b.tenant, planning_project_b)


@pytest.fixture
def planning_baseline_whatif_a(db, planning_project_a):
    """An editable ``what_if`` scenario — ``bsl_promote``'s happy-path row, and the shape the
    frozen-row refusals must NOT trigger on."""
    return _planning_baseline(planning_project_a.tenant, planning_project_a)


@pytest.fixture
def planning_baseline_frozen_a(db, planning_project_a):
    """A ``baseline``-typed row that is NOT active — frozen (``bsl_edit``/``bsl_delete`` refuse
    it) and yet a valid ``bsl_activate`` target."""
    return _planning_baseline(planning_project_a.tenant, planning_project_a,
                              name="Frozen baseline", baseline_type="baseline")


@pytest.fixture
def planning_baseline_active_a(db, planning_project_a):
    """The project's managed baseline: ``baseline`` type, ``is_active=True`` — what activate and
    promote must TAKE OVER FROM, and what edit/delete refuse twice over."""
    return _planning_baseline(planning_project_a.tenant, planning_project_a,
                              name="Active baseline", baseline_type="baseline", is_active=True)


@pytest.fixture
def planning_baseline_b(db, planning_project_b):
    """Tenant B's what-if — 404 as tenant A on detail/edit/delete and on both baseline verbs."""
    return _planning_baseline(planning_project_b.tenant, planning_project_b)


# ==================================================================================================
# Extra actors + clients (mirror the 7.1 set one-for-one, with distinct identities)
# ==================================================================================================

@pytest.fixture
def planning_member_b(db, tenant_b):
    """A NON-admin member of tenant B (the admin_b-shaped member). Separates the two refusals on
    the admin-gated verbs: a tenant-B member hitting a tenant-A pk must 404 on scope, never 403 on
    role — and a tenant-A member (root ``member_user``) must 403 before any lookup."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="planning-member@globex.com", username="member_globex_plan",
        password="TestPass123!", tenant=tenant_b, is_tenant_admin=False)


@pytest.fixture
def planning_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape. The four 7.2 create views guard
    this on their FIRST line and redirect to ``dashboard:home``; the registers render empty."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="planning-drifter@example.com", username="planning_drifter",
        password="TestPass123!", tenant=None)


@pytest.fixture
def planning_tenantless_client(db, planning_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers render empty; creates redirect away."""
    client = Client()
    client.force_login(planning_tenantless_user)
    return client


@pytest.fixture
def planning_anon_client(db):
    """Unauthenticated — every 7.2 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def planning_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


@pytest.fixture
def planning_wbs_tree_a(db, planning_project_a):
    """The 2-deliverable × 2-work-package tree (see ``_planning_wbs_tree``) on project A — the
    tree-view, WBS-code, rollup and critical-chain tests all hang off this one dict."""
    return _planning_wbs_tree(planning_project_a.tenant, planning_project_a)


# ==================================================================================================
# 7.3 Resource Management (subslug ``resource``) — OWNED BY PHASE 6 STEP 1
#
# Same rules as the 7.1/7.2 blocks above, prefixed ``resource_`` / ``_resource_`` so no later
# sub-module can shadow them (test files: test_resource_models/_forms/_views/_security.py). See
# ``.claude/tasks/test-contract-projects-7.3.md`` for the test contract these fixtures serve.
#
# * Factories construct + ``.save()`` — ``TenantNumbered.save()`` is where ``RSP-/RAL-/RTE-``
#   numbers are minted; ``bulk_create`` would ship empty numbers and is never used here.
# * Determinism (L16): every date derives from ``_resource_today()`` (``timezone.localdate()``)
#   and every datetime from ``timezone.now()`` — the same basis ``ResourceAllocation.is_live`` and
#   the capacity/actuals windows use.
# * Projects / requests reuse the 7.1 FACTORIES ``_projectinitiation_project`` /
#   ``_projectinitiation_request`` (function imports, NOT the 7.1 fixtures — lanes never depend on
#   each other's fixture rows). The host project is ACTIVE with an approved charter.
# * The admin client for 7.3 is the ROOT conftest's ``client_a`` — exactly as 7.1/7.2, which define
#   no admin-client fixture of their own either. No ``resource_client`` exists on purpose.
# * Tests NEVER touch ``management/commands/seed_projects.py`` (the demo seed) — every test builds
#   exactly the rows it asserts on from the factories below. The seeder's post-M4 figures (its
#   RAL-00001 at 48h/wk so the over-allocation alert fires on the DEMO tenant) are demo data, not
#   test data; board expectations are computed from these fixture rows via ``planned_hours``.
# ==================================================================================================

#: ``apps.core.crud.crud_list``'s default ``per_page`` — every 7.3 register uses the default, so a
#: pagination test needs ``RESOURCE_PAGE_SIZE + 1`` rows for a second page (same rationale as
#: ``PROJECTINITIATION_PAGE_SIZE`` / ``PLANNING_PAGE_SIZE`` above).
RESOURCE_PAGE_SIZE = 15


def _resource_today():
    """Today on the SAME basis the 7.3 code uses (``is_live`` / the capacity horizon →
    ``timezone.localdate()``)."""
    return timezone.localdate()


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints RSP-/RAL-/RTE-
# ==================================================================================================

def _resource_profile(tenant, employee=None, party=None, **overrides):
    """A ``ResourceProfile`` pool row; auto-mints the identity when neither is given.

    With neither ``employee`` nor ``party`` this mints a fresh person ``core.Party`` — a row that
    identifies nobody is bad seed data even though ``save()`` never runs ``clean()`` (the
    exactly-one-of rule is re-checked by tests via ``full_clean()``). ``resource_type`` defaults
    to ``contractor`` for a party-keyed row and ``internal`` for an employee-keyed one (override
    freely — the model pins the choices, not the pairing). ``weekly_capacity_hours`` stays the
    model default 40.00 unless overridden; pass ``Decimal("24.00")`` for a part-timer denominator.
    """
    from apps.core.models import Party
    from apps.projects.models import ResourceProfile
    seq = ResourceProfile.objects.filter(tenant=tenant).count() + 1
    if employee is None and party is None:
        party = Party.objects.create(tenant=tenant, kind="person", name=f"Resource {seq:02d}")
    fields = dict(
        tenant=tenant,
        employee=employee,
        party=party,
        resource_type="internal" if employee is not None else "contractor",
        default_role=f"Role {seq:02d}",
        skill_summary="Python, Django",
        weekly_capacity_hours=Decimal("40.00"),
        utilization_target_pct=80,
        status="active",
        notes="",
    )
    fields.update(overrides)
    obj = ResourceProfile(**fields)
    obj.save()
    return obj


def _resource_allocation(tenant, **overrides):
    """A ``ResourceAllocation`` booking: by default a NAMED-shape ``soft`` one (nothing attached).

    Defaults: ``role_name="Backend developer"``, ``allocation_unit="hours_per_week"`` with
    ``hours_per_week=Decimal("16.00")`` (the ONLY magnitude set — the model clean's
    one-magnitude rule), ``booking_status="soft"`` over the live window ``today-7..today+35``,
    and ``project`` / ``project_request`` / ``project_task`` / ``resource`` all None — pass them
    explicitly (``clean()`` refuses a both-null attach, but ``save()`` never runs ``clean()``).
    Pass ``booking_status=...`` to park the row in any verb state, and never set a second
    magnitude. ``requested_by`` is left to the caller — the create view stamps it, fixtures pass
    it where provenance matters.
    """
    from apps.projects.models import ResourceAllocation
    today = _resource_today()
    fields = dict(
        tenant=tenant,
        project=None,
        project_request=None,
        project_task=None,
        resource=None,
        role_name="Backend developer",
        skill_requirements="Python, Django",
        allocation_unit="hours_per_week",
        hours_per_week=Decimal("16.00"),
        pct_capacity=None,
        total_hours=None,
        start_date=today - datetime.timedelta(days=7),
        end_date=today + datetime.timedelta(days=35),
        booking_status="soft",
        notes="",
    )
    fields.update(overrides)
    obj = ResourceAllocation(**fields)
    obj.save()
    return obj


def _resource_entry(tenant, resource, **overrides):
    """A ``ResourceTimeEntry`` draft day-row on ``resource``; ``tenant`` is passed explicitly.

    Defaults: ``entry_date=today`` (the current ISO week — the default actuals window),
    ``hours=Decimal("6.00")``, ``status="draft"``, ``project=None``. ``save()`` never runs
    ``clean()`` and nothing else writes the audit fields, so an ``approved`` / ``rejected`` row is
    only honest when the caller sets ``submitted_at`` + ``approved_by`` + ``approved_at``
    (``decision_note`` for ``rejected``) explicitly — the fixtures below always do.
    """
    from apps.projects.models import ResourceTimeEntry
    fields = dict(
        tenant=tenant,
        resource=resource,
        project=None,
        project_task=None,
        entry_date=_resource_today(),
        hours=Decimal("6.00"),
        task_description="Project implementation work",
        status="draft",
        decision_note="",
        notes="",
    )
    fields.update(overrides)
    obj = ResourceTimeEntry(**fields)
    obj.save()
    return obj


# -- bulk fills (pagination / N+1 / search) ---------------------------------------------------------
#
# Loops over the factories rather than bulk_create for the reason spelled out at the top of this
# file: bulk_create skips save(), and save() is where `number` is minted.

def _resource_fill_profiles(tenant, count, **overrides):
    """``count`` party-keyed pool rows with distinct roles (``Backlog role 01`` …). Returns the list."""
    return [
        _resource_profile(tenant, default_role=f"Backlog role {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _resource_fill_allocations(tenant, count, **overrides):
    """``count`` bookings with distinct roles (``Backlog booking 01`` …). Returns the list."""
    return [
        _resource_allocation(tenant, role_name=f"Backlog booking {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _resource_fill_entries(tenant, resource, count, **overrides):
    """``count`` draft entries on ONE resource, dates walking back a day per row (distinct
    descriptions ``Backlog entry 01`` …). Returns the list."""
    return [
        _resource_entry(
            tenant, resource,
            entry_date=_resource_today() - datetime.timedelta(days=i - 1),
            task_description=f"Backlog entry {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# Tenants / actors — thin aliases over the ROOT conftest (reuse, never redefine)
# ==================================================================================================

@pytest.fixture
def resource_tenant(db, tenant_a):
    """Tenant A — the 7.3 lane's workspace. An alias of the root ``tenant_a``; tests must never
    depend on the demo seeder's workspace."""
    return tenant_a


@pytest.fixture
def resource_tenant_b(db, tenant_b):
    """Tenant B — the cross-tenant target every IDOR / foreign-FK test needs."""
    return tenant_b


@pytest.fixture
def resource_admin(db, admin_user):
    """Tenant A's tenant admin — alias of the root ``admin_user``: the actor every admin-gated
    verb (assign/substitute/approve/reject/approve_week) succeeds for."""
    return admin_user


@pytest.fixture
def resource_member(db, member_user):
    """Tenant A's plain member — alias of the root ``member_user``: 403 on the admin-gated verbs,
    full run on the member-level ones (commit/complete/cancel/submit)."""
    return member_user


@pytest.fixture
def resource_member_b(db, resource_tenant_b):
    """A NON-admin member of tenant B (the admin_b-shaped member). Separates the two refusals on
    the admin-gated verbs: a tenant-B member hitting a tenant-A pk must 404 on scope, never 403
    on role — and a tenant-A member (root ``member_user``) must 403 before any lookup."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="resource-member@globex.com", username="member_globex_res",
        password="TestPass123!", tenant=resource_tenant_b, is_tenant_admin=False)


@pytest.fixture
def resource_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape. The three 7.3 create views
    guard this on their FIRST line and redirect to ``dashboard:home``; registers render empty."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="resource-drifter@example.com", username="resource_drifter",
        password="TestPass123!", tenant=None)


@pytest.fixture
def resource_tenantless_client(db, resource_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers render empty; creates redirect away."""
    client = Client()
    client.force_login(resource_tenantless_user)
    return client


@pytest.fixture
def resource_anon_client(db):
    """Unauthenticated — every 7.3 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def resource_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


# ==================================================================================================
# Core-spine records the 7.3 FKs point at
# ==================================================================================================

@pytest.fixture
def resource_org_unit_a(db, resource_tenant):
    """Tenant A OrgUnit — the pool register's ``org_unit`` lens and a resource's home team."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=resource_tenant, name="Resource Operations",
                                  kind="department")


@pytest.fixture
def resource_org_unit_b(db, resource_tenant_b):
    """Tenant B OrgUnit — the crafted-POST value for ``ResourceProfileForm.org_unit``."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=resource_tenant_b, name="Globex Resource Operations",
                                  kind="department")


@pytest.fixture
def resource_party_a(db, resource_tenant):
    """Tenant A person Party — the external identity behind ``resource_profile_contractor``."""
    from apps.core.models import Party
    return Party.objects.create(tenant=resource_tenant, kind="person", name="Priya Raman")


@pytest.fixture
def resource_party_b(db, resource_tenant_b):
    """Tenant B organization Party — the crafted-POST value for ``ResourceProfileForm.party``."""
    from apps.core.models import Party
    return Party.objects.create(tenant=resource_tenant_b, kind="organization",
                                name="Globex Contractors")


@pytest.fixture
def resource_employee_a(db, resource_tenant):
    """An ``hrm.EmployeeProfile`` in tenant A, on its OWN person Party (the OneToOne forbids
    sharing) — the internal-staff identity behind ``resource_profile_internal``. Built with
    ``.save()`` so its ``EMP-`` number is minted too."""
    from apps.core.models import Party
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=resource_tenant, kind="person", name="Alex Rivera")
    obj = EmployeeProfile(tenant=resource_tenant, party=party)
    obj.save()
    return obj


@pytest.fixture
def resource_project(db, resource_tenant, resource_admin):
    """Tenant A's ACTIVE chartered host project — every allocation/entry hangs off this one or the
    tenant-B twin. Built through the 7.1 FACTORY (function import, not a 7.1 fixture)."""
    return _projectinitiation_project(
        resource_tenant, name="Resource host Alpha", code="RSA-01", status="active",
        charter_status="approved", charter_approved_by=resource_admin,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        created_by=resource_admin)


@pytest.fixture
def resource_project_b(db, resource_tenant_b, admin_b):
    """Tenant B's active host — 404 as tenant A on detail/edit/delete, absent from A's registers,
    refused as a crafted ``project`` FK on all three forms."""
    return _projectinitiation_project(
        resource_tenant_b, name="Resource host Beta", code="RSB-01", status="active",
        charter_status="approved", charter_approved_by=admin_b,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        created_by=admin_b)


@pytest.fixture
def resource_request(db, resource_tenant, resource_admin):
    """An APPROVED, UNCONVERTED ``ProjectRequest`` — the pipeline-demand anchor a placeholder
    booking points at while there is no project yet (the ``project_request`` FK). Built through
    the 7.1 factory; ``convert_to_project()`` is never called, so it stays demand."""
    return _projectinitiation_request(
        resource_tenant, title="Pipeline: customer data platform", status="approved",
        decision="go", decided_by=resource_admin,
        decided_at=timezone.now() - datetime.timedelta(days=1),
        submitted_at=timezone.now() - datetime.timedelta(days=6),
        requested_by=resource_admin, created_by=resource_admin)


# ==================================================================================================
# ResourceProfile — the pool rows the booking forms and the board point at
# ==================================================================================================

@pytest.fixture
def resource_profile_internal(db, resource_tenant, resource_employee_a, resource_org_unit_a):
    """The EMPLOYEE-keyed pool row (40h, active, org-unit'd, "Data engineer") — one half of the
    exactly-one-of rule, the approval queue's person (``rte_approve_week``) and the resource side
    of the actuals-to-plan pairing."""
    return _resource_profile(
        resource_tenant, employee=resource_employee_a, resource_type="internal",
        default_role="Data engineer", skill_summary="Python, Django, Airflow",
        org_unit=resource_org_unit_a)


@pytest.fixture
def resource_profile_contractor(db, resource_tenant, resource_party_a):
    """The PARTY-keyed contractor row — the other half of the exactly-one-of rule, with the
    engagement window (``available_from`` today−30 / ``available_to`` today+90) and 40h."""
    today = _resource_today()
    return _resource_profile(
        resource_tenant, party=resource_party_a, resource_type="contractor",
        default_role="QA contractor", skill_summary="Playwright, pytest",
        available_from=today - datetime.timedelta(days=30),
        available_to=today + datetime.timedelta(days=90))


@pytest.fixture
def resource_profile_minimal(db, resource_tenant):
    """The minimal party-keyed row: a **24h/wk** part-timer denominator with no org unit, no
    engagement window and an empty skill summary. ``resource_allocation_soft_pct``'s % of Capacity
    booking divides by this row's 24.00, so pct math has a small, honest denominator."""
    return _resource_profile(resource_tenant, weekly_capacity_hours=Decimal("24.00"),
                             default_role="Support", skill_summary="")


@pytest.fixture
def resource_profile_b(db, resource_tenant_b):
    """Tenant B's pool row — 404 as tenant A on detail/edit/delete, absent from A's register, and
    refused as a crafted ``resource`` / ``employee`` / ``party`` FK."""
    return _resource_profile(resource_tenant_b)


# ==================================================================================================
# ResourceAllocation — one row per verb-branching state (all requested_by resource_admin)
# ==================================================================================================

@pytest.fixture
def resource_allocation_named_firm(db, resource_tenant, resource_admin, resource_project,
                                   resource_profile_contractor):
    """FIRM + named (contractor, 12h/wk) on the host project, window today−14..today+28 →
    ``is_live`` True. ``ral_assign`` must refuse it ("already names a resource — use Substitute").
    """
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_contractor,
        role_name="QA contractor", skill_requirements="Playwright",
        hours_per_week=Decimal("12.00"), booking_status="firm",
        start_date=_resource_today() - datetime.timedelta(days=14),
        end_date=_resource_today() + datetime.timedelta(days=28),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_named_soft(db, resource_tenant, resource_admin, resource_project,
                                   resource_profile_internal):
    """SOFT + named (internal, 16h/wk) on the host project over the factory's live window
    (today−7..today+35). The happy-path row for ``ral_substitute`` and the soft→firm
    ``ral_commit``; also the PLAN side of the actuals-to-plan row — the approved internal entry's
    planned 16.00h over the current ISO week is THIS booking's ``planned_hours``, computed in the
    test from the model."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_internal,
        role_name="Data engineer", skill_requirements="Python, Airflow",
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_soft_pct(db, resource_tenant, resource_admin, resource_project,
                                 resource_profile_minimal):
    """SOFT + named on the 24h part-timer with ``allocation_unit="pct_capacity"`` /
    ``pct_capacity=50`` — the unit-2 booking: a full week of it plans 50% × 24h = 12.00h (assert
    via ``planned_hours``, never hardcode). ``hours_per_week`` stays None."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_minimal,
        role_name="Support engineer", skill_requirements="",
        allocation_unit="pct_capacity", hours_per_week=None, pct_capacity=50,
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_placeholder_requested(db, resource_tenant, resource_admin,
                                              resource_project):
    """PLACEHOLDER (``resource=None``) in ``requested`` on the host project (today+7..today+49) —
    ``ral_assign``'s happy path (assign names it and walks it to soft) and the requested→soft
    ``ral_commit`` path; a gap row (``is_gap``) on the demand board."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=None,
        role_name="Data engineer", skill_requirements="Python, Airflow",
        booking_status="requested",
        start_date=_resource_today() + datetime.timedelta(days=7),
        end_date=_resource_today() + datetime.timedelta(days=49),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_placeholder_soft(db, resource_tenant, resource_admin, resource_project):
    """A SOFT placeholder (``resource=None``, window today−21..today+21) — the as-built
    ``ral_commit`` refusal case: a soft placeholder cannot be firmed ("Assign a resource before
    committing a placeholder to firm"), while ``ral_assign`` still accepts it as a source. Also
    the proof a placeholder can be ``is_live`` (soft + current window)."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=None,
        role_name="QA analyst", skill_requirements="",
        booking_status="soft",
        start_date=_resource_today() - datetime.timedelta(days=21),
        end_date=_resource_today() + datetime.timedelta(days=21),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_request_placeholder(db, resource_tenant, resource_admin,
                                            resource_request):
    """A REQUEST-linked placeholder — ``project=None``, ``project_request=resource_request``,
    ``requested`` (today+14..today+70). The demand lens' pipeline row
    (``demand_url_name == "projects:prq_detail"``) and the proof a booking can hang off a request
    alone (the model clean's attach guard accepts exactly one of the two)."""
    return _resource_allocation(
        resource_tenant, project=None, project_request=resource_request, resource=None,
        role_name="Backend developer", skill_requirements="Django",
        booking_status="requested",
        start_date=_resource_today() + datetime.timedelta(days=14),
        end_date=_resource_today() + datetime.timedelta(days=70),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_completed(db, resource_tenant, resource_admin, resource_project,
                                  resource_profile_internal):
    """COMPLETED past booking (today−90..today−30) — ``ral_complete``/``ral_cancel`` refuse it and
    ``is_live`` is False. NOTE: ``planned_hours()`` itself still counts completed rows (only
    cancelled/released short-circuit) — it is the board QUERIES that exclude completed, so a test
    of the method must not conflate the two."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_internal,
        role_name="Data engineer", skill_requirements="Airflow",
        booking_status="completed",
        start_date=_resource_today() - datetime.timedelta(days=90),
        end_date=_resource_today() - datetime.timedelta(days=30),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_cancelled(db, resource_tenant, resource_admin, resource_project,
                                  resource_profile_contractor):
    """CANCELLED mid-flight booking (window today−21..today+21, still 'current') — the proof a
    window match is not enough: ``planned_hours`` returns ZERO for it, and ``ral_cancel`` answers
    "already cancelled" with info and no change."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_contractor,
        role_name="QA contractor", skill_requirements="",
        hours_per_week=Decimal("12.00"), booking_status="cancelled",
        start_date=_resource_today() - datetime.timedelta(days=21),
        end_date=_resource_today() + datetime.timedelta(days=21),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_released(db, resource_tenant, resource_admin, resource_project,
                                 resource_profile_internal):
    """The RELEASED half of the substitution chain (named internal, 10h/wk,
    today−28..today+28). ``planned_hours`` returns ZERO for it — the successor already carries
    the demand, and counting both would double it."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_internal,
        role_name="Data engineer", skill_requirements="Python",
        hours_per_week=Decimal("10.00"), booking_status="released",
        start_date=_resource_today() - datetime.timedelta(days=28),
        end_date=_resource_today() + datetime.timedelta(days=28),
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_successor(db, resource_tenant, resource_admin, resource_project,
                                  resource_profile_contractor, resource_allocation_released):
    """The FIRM successor ``ral_substitute`` would have produced: named contractor, the SAME
    window and magnitude as the released row, ``substitute_of=resource_allocation_released``.
    Hand-built (not driven through the verb) so model/detail tests get the chain without an HTTP
    round-trip — the verb itself is proven by driving ``ral_substitute`` on
    ``resource_allocation_named_soft``; ``ral_detail`` of the released row must surface this row
    as its ``successor`` context key."""
    return _resource_allocation(
        resource_tenant, project=resource_project, resource=resource_profile_contractor,
        role_name=resource_allocation_released.role_name,
        skill_requirements=resource_allocation_released.skill_requirements,
        hours_per_week=resource_allocation_released.hours_per_week,
        booking_status="firm",
        start_date=resource_allocation_released.start_date,
        end_date=resource_allocation_released.end_date,
        substitute_of=resource_allocation_released,
        requested_by=resource_admin)


@pytest.fixture
def resource_allocation_b(db, resource_tenant_b, admin_b, resource_project_b,
                          resource_profile_b):
    """Tenant B's allocation — 404 as tenant A on detail/edit/delete and on all five verbs."""
    return _resource_allocation(
        resource_tenant_b, project=resource_project_b, resource=resource_profile_b,
        role_name="Globex booking", booking_status="soft", requested_by=admin_b)


# ==================================================================================================
# ResourceTimeEntry — one row per status, stamps set honestly (nothing auto-stamps them)
# ==================================================================================================

@pytest.fixture
def resource_entry_draft(db, resource_tenant, resource_profile_internal, resource_project):
    """A ``draft`` day-entry (today, 6.00h, host project) — ``rte_submit``'s happy path; no stamps
    at all."""
    return _resource_entry(resource_tenant, resource_profile_internal, project=resource_project)


@pytest.fixture
def resource_entry_submitted(db, resource_tenant, resource_profile_internal, resource_project):
    """A ``submitted`` entry (today, 6.00h) with ONLY ``submitted_at`` stamped (now − 2h) — the
    approval queue: ``rte_approve`` / ``rte_reject`` happy path and the ``rte_approve_week`` bulk
    target. Its ISO week is the CURRENT one — compute year/week from the row
    (``fixture.iso_year`` / ``fixture.iso_week``), never hardcode."""
    return _resource_entry(
        resource_tenant, resource_profile_internal, project=resource_project, status="submitted",
        submitted_at=timezone.now() - datetime.timedelta(hours=2))


@pytest.fixture
def resource_entry_approved(db, resource_tenant, resource_admin, resource_profile_internal,
                            resource_project):
    """An ``approved`` entry (today, 6.00h) with the stamps set honestly — ``submitted_at``
    (now − 1d), then ``approved_by`` = the admin and ``approved_at`` (now − 2h). Pairs with
    ``resource_allocation_named_soft`` (same internal resource + host project) so the actuals
    section has one real row: actual 6.00 against planned = that booking's ``planned_hours`` over
    the current ISO week."""
    return _resource_entry(
        resource_tenant, resource_profile_internal, project=resource_project, status="approved",
        submitted_at=timezone.now() - datetime.timedelta(days=1),
        approved_by=resource_admin, approved_at=timezone.now() - datetime.timedelta(hours=2))


@pytest.fixture
def resource_entry_rejected(db, resource_tenant, resource_admin, resource_profile_internal,
                            resource_project):
    """A ``rejected`` entry (today, 8.00h) with the full honest stamp set — ``submitted_at``, then
    ``approved_by``/``approved_at`` (the reject verb stamps the decision too), plus the
    ``decision_note`` reason. The edit/delete LOCK row: both verbs must refuse it."""
    return _resource_entry(
        resource_tenant, resource_profile_internal, project=resource_project, status="rejected",
        hours=Decimal("8.00"),
        submitted_at=timezone.now() - datetime.timedelta(days=2),
        approved_by=resource_admin, approved_at=timezone.now() - datetime.timedelta(days=1),
        decision_note="Client call overran — re-log the extra hour under support.")


@pytest.fixture
def resource_entry_approved_nonproject(db, resource_tenant, resource_admin,
                                       resource_profile_contractor):
    """An APPROVED entry with ``project=None`` ("Internal training", 4.00h) — the actuals
    section's Non-project-time row: renders with ``project is None`` and planned 0.00 (no live
    booking pairs a contractor with 'no project')."""
    return _resource_entry(
        resource_tenant, resource_profile_contractor, project=None, status="approved",
        hours=Decimal("4.00"), task_description="Internal training",
        submitted_at=timezone.now() - datetime.timedelta(days=1),
        approved_by=resource_admin, approved_at=timezone.now() - datetime.timedelta(hours=3))


@pytest.fixture
def resource_entry_b(db, resource_tenant_b, resource_profile_b, resource_project_b):
    """Tenant B's entry — 404 as tenant A on detail/edit/delete and on submit/approve/reject."""
    return _resource_entry(resource_tenant_b, resource_profile_b, project=resource_project_b)


# ==================================================================================================
# 7.4 Cost & Budget Management (subslug ``cost``) — OWNED BY PHASE 6 STEP 1
#
# Same rules as the 7.1/7.2/7.3 blocks above, prefixed ``cost_`` / ``_cost_`` so no lane can shadow
# another (test files: test_cost_models/_forms/_views/_security.py). See
# ``.claude/tasks/test-contract-projects-7.4.md`` for the test contract these fixtures serve —
# it pins the EXACT EVM figures the default amounts below produce (bac 300 / PV fraction 0.5 /
# ev 150 / ac 100 → cpi 1.50, tcpi 0.75): the amounts are chosen so every ratio is exact, and the
# four test writers assert those numbers instead of re-deriving them.
#
# * Factories construct + ``.save()`` — ``TenantNumbered.save()`` is where ``BVR-/CCA-/PBL-/PEX-``
#   numbers are minted; ``bulk_create`` would ship empty numbers and is never used here.
# * Determinism (L16): every date derives from ``_cost_today()`` (``timezone.localdate()``) — the
#   SAME basis ``CostControlAccount._pv_fraction`` reads, so the anchored window
#   today−4 .. today+4 yields the exact fraction 4/8 = 0.5 for as long as the test runs on one
#   local day, which is the whole suite's existing assumption.
# * Spine reuse: projects come from the 7.1 FACTORY ``_projectinitiation_project`` and WBS work
#   packages from the 7.2 FACTORY ``_planning_task`` (function imports, NOT those lanes' fixtures —
#   lanes never depend on each other's fixture rows).
# * ``cost_*`` rows ARE LANDED MONEY: every revision/CA/line/expense fixture on project_a feeds the
#   shared EVM panel of ``cost_control_account_a``. A verb that mutates one of them
#   (``bvr_activate`` re-baselines; ``pex_post``/``pex_void`` move ac) changes the pinned figures —
#   the contract note's mutation matrix lists the post-verb values, and ``bac``/``ac``/
#   ``committed``/``active_revision`` are ``cached_property``: RE-FETCH the CA before re-reading
#   metrics after any mutation.
# * The admin client for 7.4 is the ROOT conftest's ``client_a`` (aliased ``cost_admin_client``)
#   and the member client the root ``member_client`` (aliased ``cost_member_client``) — exactly as
#   7.1/7.2/7.3, which define no clients of their own either; the aliases exist only so the 7.4
#   contract can pin the names its four test modules import.
# * Tests NEVER touch ``management/commands/seed_projects.py`` (the demo seed) — every test builds
#   exactly the rows it asserts on from the factories below.
# ==================================================================================================

#: ``apps.core.crud.crud_list``'s default ``per_page`` — every 7.4 register uses the default, so a
#: pagination test needs ``COST_PAGE_SIZE + 1`` rows for a second page (same rationale as
#: ``PROJECTINITIATION_PAGE_SIZE`` / ``PLANNING_PAGE_SIZE`` / ``RESOURCE_PAGE_SIZE`` above).
COST_PAGE_SIZE = 15


def _cost_today():
    """Today on the SAME basis the 7.4 code uses (``CostControlAccount._pv_fraction`` →
    ``timezone.localdate()``)."""
    return timezone.localdate()


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints BVR-/CCA-/PBL-/PEX-
# ==================================================================================================

def _cost_revision(tenant, project, no=0, status="draft", activate=False, **overrides):
    """A ``BudgetRevision`` on ``project`` — ``no`` is ``revision_no`` (UNIQUE per
    ``(tenant, project)``; the lifecycle fixtures occupy 0–5 on project A, so fills start at 10).

    Defaults: ``status="draft"``, a distinct per-tenant ``title`` ("Budget revision NN"), a filled
    ``reason``, currency None (pass ``cost_currency`` — the form's single unscoped FK, L29).
    ``activate=True`` stamps the re-baseline the way ``bvr_activate`` would: it sets
    ``activated_at=now()`` and defaults ``status`` to ``"approved"`` (an explicit ``status=`` /
    ``activated_at=`` kwarg still wins) — a hand-stamped baseline is exactly what the EVM fixtures
    need, because driving the verb inside a fixture would route around the thing under test.
    """
    from apps.projects.models import BudgetRevision
    seq = BudgetRevision.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        revision_no=no,
        title=f"Budget revision {seq:02d}",
        currency=None,
        status=status,
        reason="Reprice the labor line after the rate review.",
        impact_note="",
        schedule_impact_note="",
        requested_by=None,
        requested_at=None,
        decided_by=None,
        decided_at=None,
        decision_notes="",
        activated_at=None,
        created_by=None,
    )
    if activate:
        fields["status"] = "approved"
        fields["activated_at"] = timezone.now()
    fields.update(overrides)
    obj = BudgetRevision(**fields)
    obj.save()
    return obj


def _cost_control_account(tenant, project, code, **overrides):
    """A ``CostControlAccount`` on ``project`` with the caller's ``code`` (UNIQUE per
    ``(tenant, project)`` — the tenant's own CA id, e.g. "CA-1.2").

    Defaults: ``status="active"``, ``percent_complete=0``, ``contingency=0``, NO wbs anchor and NO
    gl account — an unanchored CA derives PV from the PROJECT window, which is the fallback branch
    the no-anchor fixture exists to exercise. ``clean()`` runs before ``save()`` (the
    ``_planning_dependency`` precedent) so a mis-anchored call raises at build time.
    """
    from apps.projects.models import CostControlAccount
    seq = CostControlAccount.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        name=f"Control account {seq:02d}",
        code=code,
        wbs_node=None,
        gl_account=None,
        contingency=Decimal("0.00"),
        percent_complete=Decimal("0.00"),
        status="active",
        note="",
    )
    fields.update(overrides)
    obj = CostControlAccount(**fields)
    obj.clean()
    obj.save()
    return obj


def _cost_budget_line(tenant, revision, project, category="labor", amount="100.00", **overrides):
    """A ``ProjectBudgetLine`` inside ``revision`` (``project`` denormalised — ``clean()`` pins it
    to the revision's project, and the optional wbs/control_account to it too, so a mismatched
    call raises at build time instead of seeding bad data).

    Defaults: ``category="labor"``, ``amount=100.00`` (str or Decimal), no wbs_node, no
    control_account, no gl_account. Lines on the ACTIVE revision move ``bac`` — fill lines onto
    throwaway revisions, or expect the pinned EVM figures to move with you.
    """
    from apps.projects.models import ProjectBudgetLine
    fields = dict(
        tenant=tenant,
        budget_revision=revision,
        project=project,
        category=category,
        wbs_node=None,
        control_account=None,
        gl_account=None,
        amount=Decimal(amount),
        note="",
    )
    fields.update(overrides)
    obj = ProjectBudgetLine(**fields)
    obj.clean()
    obj.save()
    return obj


def _cost_expense(tenant, project, control_account, entry_type="actual", amount="50.00",
                  status="draft", **overrides):
    """A ``ProjectExpense`` against ``control_account`` (REQUIRED, non-nullable) on ``project``.

    Defaults: ``entry_type="actual"``, ``amount=50.00`` (str or Decimal), ``status="draft"``
    (drafts burn nothing — the EVM-safe shape), ``entry_date=today`` (REQUIRED column — the
    burn-trend dimension), ``source_kind="manual"``. Only POSTED ``actual``/``accrual`` rows count
    into ``ac`` and only POSTED ``commitment`` rows into ``committed`` — pass
    ``status="posted"`` deliberately. ``clean()`` runs before ``save()`` (same-project guard).
    """
    from apps.projects.models import ProjectExpense
    fields = dict(
        tenant=tenant,
        project=project,
        control_account=control_account,
        wbs_node=None,
        entry_type=entry_type,
        source_kind="manual",
        source_number="",
        vendor=None,
        gl_account=None,
        currency=None,
        amount=Decimal(amount),
        entry_date=_cost_today(),
        status=status,
        description="",
        created_by=None,
    )
    fields.update(overrides)
    obj = ProjectExpense(**fields)
    obj.clean()
    obj.save()
    return obj


# -- bulk fills (pagination / search / burn-trend) ---------------------------------------------------
#
# Loops over the factories rather than bulk_create for the reason spelled out at the top of this
# file: bulk_create skips save(), and save() is where `number` is minted.

def _cost_fill_revisions(tenant, project, count, start_no=10, **overrides):
    """``count`` revisions with DISTINCT ``revision_no`` (``start_no`` upward — 10 clears the
    lifecycle fixtures' 0–5) and distinct titles (``Backlog revision 01`` …). Returns the list."""
    return [
        _cost_revision(tenant, project, no=start_no + i - 1,
                       title=f"Backlog revision {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _cost_fill_lines(tenant, revision, project, count, **overrides):
    """``count`` lines on ONE revision, 100.00 each, cycling ``CATEGORY_CHOICES`` in order — so
    ``category_totals`` is deterministic (2 labor lines ⇒ 200.00). Returns the list."""
    from apps.projects.models import ProjectBudgetLine
    categories = [value for value, _label in ProjectBudgetLine.CATEGORY_CHOICES]
    return [
        _cost_budget_line(
            tenant, revision, project, category=categories[(i - 1) % len(categories)],
            note=f"Backlog line {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _cost_fill_expenses(tenant, project, control_account, count, **overrides):
    """``count`` DRAFT expenses (drafts burn nothing — the pinned EVM figures survive a fill),
    dates walking back a day per row, distinct descriptions (``Backlog expense 01`` …). Returns
    the list; pass ``status="posted"`` explicitly when a burn-trend test needs real money."""
    return [
        _cost_expense(
            tenant, project, control_account,
            entry_date=_cost_today() - datetime.timedelta(days=i - 1),
            description=f"Backlog expense {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# Core-spine records the 7.4 FKs point at
# ==================================================================================================

@pytest.fixture
def cost_currency(db):
    """USD. ``accounting.Currency`` is GLOBAL — it has NO ``tenant`` column (L29), so it is the one
    FK on the 7.4 forms that ``_reject_foreign`` must never be handed and the one ``TenantModelForm``
    leaves unscoped. ``get_or_create`` because ``code`` is globally unique across the whole suite
    (the 7.1 fixture returns the SAME row — that is the point of a global table)."""
    from apps.accounting.models import Currency
    obj, _ = Currency.objects.get_or_create(
        code="USD", defaults={"name": "US Dollar", "symbol": "$"})
    return obj


@pytest.fixture
def cost_gl_account_a(db, tenant_a):
    """Tenant A expense ``GLAccount`` — the ledger LENS on CAs/lines/expenses (PROTECT; never a
    posting target, Ruling 6). ``normal_balance`` is derived in ``save()`` — never set it."""
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_a, code="5100", name="Project delivery expense", account_type="expense")


@pytest.fixture
def cost_gl_account_b(db, tenant_b):
    """Tenant B GL account — the crafted-POST value for ``gl_account`` on all three forms that
    carry one (the target model has a ``tenant`` column, so the narrowed queryset refuses it
    first; assert the FIELD error, never its wording)."""
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant_b, code="5100", name="Globex project expense", account_type="expense")


@pytest.fixture
def cost_party_a(db, tenant_a):
    """Tenant A organization Party — the ``vendor`` on ``cost_expense_posted``."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Raven Supply Co")


@pytest.fixture
def cost_party_b(db, tenant_b):
    """Tenant B organization Party — the crafted-POST value for ``ProjectExpenseForm.vendor``."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Vendors")


@pytest.fixture
def cost_project_a(db, tenant_a, admin_user):
    """Tenant A's ACTIVE host — every 7.4 row hangs off this one or the tenant-B twin. Window
    today−30 .. today+150: an UNANCHORED CA on it derives PV from these dates (fraction 30/180 —
    never assert that ratio; anchor CAs to ``cost_wbs_node_a`` for the exact 0.5)."""
    return _projectinitiation_project(
        tenant_a, name="Cost host Alpha", code="CST-01", status="active",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        start_date=_cost_today() - datetime.timedelta(days=30),
        end_date=_cost_today() + datetime.timedelta(days=150),
        created_by=admin_user)


@pytest.fixture
def cost_project_b(db, tenant_b, admin_b):
    """Tenant B's host, status ``draft`` (the contract's pinned shape). Its factory window starts
    today+30, so an UNANCHORED CA here sits BEFORE its window: PV fraction 0 → ``pv`` 0.00 and
    ``spi`` None — the pre-window edge case. 404 as tenant A everywhere, absent from A's
    registers, refused as a crafted ``project`` FK."""
    return _projectinitiation_project(
        tenant_b, name="Cost host Beta", code="CSB-01", status="draft", created_by=admin_b)


@pytest.fixture
def cost_wbs_node_a(db, cost_project_a):
    """Work package spanning TODAY: planned today−4 .. today+4 (8-day window, 4 elapsed) so the
    linear PV fraction is EXACTLY 0.5 — any CA anchored here reads ``pv == bac / 2`` and
    ``spi == 1.00``. Built through the 7.2 FACTORY (function import, not a 7.2 fixture)."""
    return _planning_task(
        cost_project_a.tenant, cost_project_a, name="Cost anchor work package",
        planned_start=_cost_today() - datetime.timedelta(days=4),
        planned_end=_cost_today() + datetime.timedelta(days=4),
        effort_hours=Decimal("80.00"))


@pytest.fixture
def cost_wbs_node_b(db, cost_project_b):
    """Tenant B's work package — the crafted-POST value for ``wbs_node`` on all four forms. Default
    7.2-factory window (today .. today+4 → PV fraction 0, today <= start)."""
    return _planning_task(cost_project_b.tenant, cost_project_b,
                          name="Globex cost work package")


# ==================================================================================================
# Extra actors + clients (aliases over the ROOT conftest — reuse, never redefine)
# ==================================================================================================

@pytest.fixture
def cost_member(db, member_user):
    """Tenant A's plain member — alias of the root ``member_user``: 403 on the admin-gated verbs
    (``bvr_approve``/``bvr_reject``/``bvr_activate``/``pex_void``), full run on the member-level
    ones (``bvr_submit``, ``pex_post``, all CRUD pages)."""
    return member_user


@pytest.fixture
def cost_member_b(db, tenant_b):
    """A NON-admin member of tenant B (the admin_b-shaped member). Separates the two refusals on
    the admin-gated verbs: a tenant-B member hitting a tenant-A pk must 404 on scope, never 403 on
    role — and a tenant-A member (root ``member_user``) must 403 before any lookup."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="cost-member@globex.com", username="member_globex_cost",
        password="TestPass123!", tenant=tenant_b, is_tenant_admin=False)


@pytest.fixture
def cost_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape. The four 7.4 create views guard
    this on their FIRST line and redirect to ``dashboard:home``; the registers render empty."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="cost-drifter@example.com", username="cost_drifter",
        password="TestPass123!", tenant=None)


@pytest.fixture
def cost_tenantless_client(db, cost_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers render empty; creates redirect away."""
    client = Client()
    client.force_login(cost_tenantless_user)
    return client


@pytest.fixture
def cost_anon_client(db):
    """Unauthenticated — every 7.4 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def cost_admin_client(db, client_a):
    """Tenant A admin logged in — alias of the root ``client_a`` (7.1/7.2/7.3 define no admin
    client of their own either; this alias exists so the 7.4 contract can pin the name)."""
    return client_a


@pytest.fixture
def cost_member_client(db, member_client):
    """Tenant A member logged in — alias of the root ``member_client``. For tenant-B ADMIN
    requests use the root ``client_b`` (no alias needed)."""
    return member_client


@pytest.fixture
def cost_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


# ==================================================================================================
# BudgetRevision — one fixture per lifecycle state the four verbs branch on
# (all on cost_project_a except ``_b``; distinct revision_no 0–5 — UNIQUE per (tenant, project))
# ==================================================================================================

@pytest.fixture
def cost_revision_activated(db, tenant_a, admin_user, cost_project_a, cost_currency):
    """THE BASELINE: revision_no 0, ``status="approved"`` AND ``activated_at`` stamped (now−1d,
    decided stamps honest) — the one approved+activated row on project_a, so it IS
    ``cost_control_account_a.active_revision``. ``is_locked`` → ``bvr_edit``/``bvr_delete`` (and
    its lines' ``pbl_edit``/``pbl_delete``) refuse it. ``amount_delta`` reads 0.00 (it compares
    against itself)."""
    return _cost_revision(
        tenant_a, cost_project_a, no=0, status="approved", activate=True,
        title="Original baseline plan", currency=cost_currency,
        requested_by=admin_user, requested_at=timezone.now() - datetime.timedelta(days=3),
        decided_by=admin_user, decided_at=timezone.now() - datetime.timedelta(days=2),
        activated_at=timezone.now() - datetime.timedelta(days=1),
        created_by=admin_user)


@pytest.fixture
def cost_revision_pending(db, tenant_a, admin_user, cost_project_a, cost_currency):
    """``pending_approval``, revision_no 1, ``requested_at`` stamped (now−1d), NO decision stamps —
    the happy path for BOTH ``bvr_approve`` and ``bvr_reject``; ``bvr_submit`` must answer
    "already …" and write nothing."""
    return _cost_revision(
        tenant_a, cost_project_a, no=1, status="pending_approval",
        title="Add a contingency reserve", currency=cost_currency,
        requested_by=admin_user, requested_at=timezone.now() - datetime.timedelta(days=1),
        created_by=admin_user)


@pytest.fixture
def cost_revision_approved(db, tenant_a, admin_user, cost_project_a, cost_currency):
    """``approved`` WITHOUT ``activated_at`` (approve does NOT activate), revision_no 3 — the only
    ``bvr_activate`` happy path. Excluded from ``active_revision`` until activated, so it never
    moves bac/amount_delta on its own; ``is_locked`` → edit/delete refuse it."""
    return _cost_revision(
        tenant_a, cost_project_a, no=3, status="approved",
        title="Vendor price escalation", currency=cost_currency,
        requested_by=admin_user, requested_at=timezone.now() - datetime.timedelta(days=4),
        decided_by=admin_user, decided_at=timezone.now() - datetime.timedelta(days=3),
        created_by=admin_user)


@pytest.fixture
def cost_revision_draft(db, tenant_a, admin_user, cost_project_a, cost_currency):
    """``draft``, revision_no 2 — the ONLY state ``bvr_submit`` accepts, and the one revision
    shape (with ``rejected``) where ``bvr_edit``/``bvr_delete`` stay OPEN (not ``is_locked``).
    Carries ``cost_budget_line_draft`` (100.00 material)."""
    return _cost_revision(
        tenant_a, cost_project_a, no=2, status="draft",
        title="Scope addition: mobile app", currency=cost_currency,
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def cost_revision_rejected(db, tenant_a, admin_user, cost_project_a, cost_currency):
    """``rejected`` + ``decision_notes`` (written only by ``bvr_reject``) + decided stamps,
    revision_no 4. NOT ``is_locked`` (only approved/superseded lock) → ``bvr_edit`` is still OPEN
    on it; ``bvr_reject`` must answer "already rejected" without re-stamping."""
    return _cost_revision(
        tenant_a, cost_project_a, no=4, status="rejected",
        title="In-house telemetry build", currency=cost_currency,
        requested_by=admin_user, requested_at=timezone.now() - datetime.timedelta(days=6),
        decided_by=admin_user, decided_at=timezone.now() - datetime.timedelta(days=5),
        decision_notes="Negative ROI; the vendor route is cheaper.",
        created_by=admin_user)


@pytest.fixture
def cost_revision_superseded(db, tenant_a, admin_user, cost_project_a, cost_currency):
    """``superseded`` with ``activated_at`` KEPT as history (now−9d — exactly what
    ``bvr_activate`` leaves behind when it supersedes), revision_no 5. ``is_locked`` → edit/delete
    refuse; ``status`` excludes it from ``active_revision``, so it never moves bac/amount_delta."""
    return _cost_revision(
        tenant_a, cost_project_a, no=5, status="superseded",
        title="Superseded first draft of the baseline", currency=cost_currency,
        requested_by=admin_user, requested_at=timezone.now() - datetime.timedelta(days=10),
        decided_by=admin_user, decided_at=timezone.now() - datetime.timedelta(days=9),
        activated_at=timezone.now() - datetime.timedelta(days=9),
        created_by=admin_user)


@pytest.fixture
def cost_revision_b(db, tenant_b, admin_b, cost_project_b, cost_currency):
    """Tenant B's revision (``draft``, revision_no 0 on ITS project) — 404 as tenant A on
    detail/edit/delete and on all four verbs; absent from tenant A's register."""
    return _cost_revision(
        tenant_b, cost_project_b, no=0, currency=cost_currency,
        requested_by=admin_b, created_by=admin_b)


# ==================================================================================================
# CostControlAccount — the EVM lens rows (expectations pinned in the contract note)
# ==================================================================================================

@pytest.fixture
def cost_control_account_a(db, tenant_a, cost_project_a, cost_wbs_node_a):
    """THE EVM fixture: on project_a, anchored to ``cost_wbs_node_a``, ``status="active"``,
    ``percent_complete=50.00``, ``contingency=25.00``. With ``cost_budget_line_a`` (300.00 on the
    ACTIVATED revision) mapped here and ``cost_expense_posted`` (100.00 posted actual): bac 300 /
    ev 150 / pv 150 / ac 100 / cpi 1.50 / tcpi 0.75 / health "under" — the FULL table lives in
    ``.claude/tasks/test-contract-projects-7.4.md`` §3. Assert those numbers, never re-derive."""
    return _cost_control_account(
        tenant_a, cost_project_a, "CA-1.0", name="Delivery control account",
        wbs_node=cost_wbs_node_a, percent_complete=Decimal("50.00"),
        contingency=Decimal("25.00"), status="active",
        note="Anchored to the cost work package.")


@pytest.fixture
def cost_control_account_b(db, tenant_b, cost_project_b):
    """Tenant B's CA — 404 as tenant A. Deliberately UNANCHORED with NO lines and only a DRAFT
    expense: every EVM figure is 0/None (bac 0, pv 0, cpi None, spi None, tcpi None — both
    denominators are 0) yet health still reads "under"/badge-green — the zero-rows edge."""
    return _cost_control_account(
        tenant_b, cost_project_b, "CA-B.1", name="Globex control account", status="planning")


# ==================================================================================================
# ProjectBudgetLine — the rows the sub-module rolls up from
# ==================================================================================================

@pytest.fixture
def cost_budget_line_a(db, tenant_a, cost_revision_activated, cost_project_a,
                       cost_control_account_a, cost_wbs_node_a):
    """The 300.00 LABOR line on the ACTIVATED revision, mapped to control_account_a +
    wbs_node_a — the row that MAKES bac 300.00. Its parent revision ``is_locked`` →
    ``pbl_edit``/``pbl_delete`` must REFUSE it (the I1 close-out ruling): frozen-refusal row AND
    EVM anchor in one."""
    return _cost_budget_line(
        tenant_a, cost_revision_activated, cost_project_a, category="labor",
        amount="300.00", wbs_node=cost_wbs_node_a, control_account=cost_control_account_a,
        note="Baseline delivery labor.")


@pytest.fixture
def cost_budget_line_draft(db, tenant_a, cost_revision_draft, cost_project_a):
    """100.00 MATERIAL line on the DRAFT revision — parent not locked → the ``pbl_edit``/
    ``pbl_delete`` happy-path row. Never moves bac (bac sums only the ACTIVE revision's lines);
    it IS the +100.00 in ``cost_revision_draft.amount_delta`` when the baseline is in play."""
    return _cost_budget_line(
        tenant_a, cost_revision_draft, cost_project_a, category="material",
        amount="100.00", note="Draft line — freely editable.")


# ==================================================================================================
# ProjectExpense — the cost evidence (only POSTED actual/accrual rows burn budget)
# ==================================================================================================

@pytest.fixture
def cost_expense_posted(db, tenant_a, admin_user, cost_project_a, cost_control_account_a,
                        cost_wbs_node_a, cost_party_a, cost_gl_account_a, cost_currency):
    """100.00 POSTED actual on control_account_a (entry_date today, vendor + GL + currency set,
    ``source_number="PO-00042"`` soft reference) — the ONLY default row that burns money: it makes
    ac 100.00. ``pex_void``'s happy path; ``pex_edit``/``pex_delete`` refuse it (posted evidence)."""
    return _cost_expense(
        tenant_a, cost_project_a, cost_control_account_a, entry_type="actual",
        amount="100.00", status="posted", wbs_node=cost_wbs_node_a, vendor=cost_party_a,
        gl_account=cost_gl_account_a, currency=cost_currency, created_by=admin_user,
        source_number="PO-00042", description="Sprint hardware order")


@pytest.fixture
def cost_expense_draft(db, tenant_a, admin_user, cost_project_a, cost_control_account_a):
    """50.00 DRAFT actual on control_account_a — burns nothing (drafts never burn). The happy path
    for ``pex_post`` AND for ``pex_edit``/``pex_delete`` (drafts are not locked)."""
    return _cost_expense(
        tenant_a, cost_project_a, cost_control_account_a, entry_type="actual",
        amount="50.00", status="draft", created_by=admin_user,
        description="Pending tools order")


@pytest.fixture
def cost_expense_void(db, tenant_a, admin_user, cost_project_a, cost_control_account_a):
    """75.00 VOID actual (entry_date today−2) on control_account_a — stays visible, counts
    nothing: ``pex_edit``/``pex_delete`` refuse it, ``pex_void`` answers "already void"."""
    return _cost_expense(
        tenant_a, cost_project_a, cost_control_account_a, entry_type="actual",
        amount="75.00", status="void", created_by=admin_user,
        entry_date=_cost_today() - datetime.timedelta(days=2),
        description="Cancelled rig rental (voided)")


@pytest.fixture
def cost_expense_b(db, tenant_b, admin_b, cost_project_b, cost_control_account_b):
    """Tenant B's expense (60.00 draft) — 404 as tenant A on detail/edit/delete and on both
    verbs; absent from tenant A's register."""
    return _cost_expense(
        tenant_b, cost_project_b, cost_control_account_b, entry_type="actual",
        amount="60.00", status="draft", created_by=admin_b, description="Globex expense")


# ==================================================================================================
# 7.5 Risk & Issue Management (subslug ``risk``)
# --------------------------------------------------------------------------------------------------
# Fixtures for ``test_risk_models.py`` / ``test_risk_forms.py`` / ``test_risk_views.py`` /
# ``test_risk_security.py``. The frozen test contract is
# ``.claude/tasks/test-contract-projects-7.5.md``; the build contract
# (``.claude/tasks/contract-projects-7.5.md``) §2–§6 pins every name the code answers to.
#
# * Everything scored is DERIVED, never stored (``score``/``severity_band``/``emv``/``residual_*``/
#   ``is_overdue``/``age_days``). The fixtures pin the INPUT columns (probability, impact,
#   cost_impact, status, dates — the per-row field table in the test contract); the test modules
#   assert the derived figures from them.
# * Factories construct + ``.save()`` so ``TenantNumbered.save()`` mints RSK-/RRA-/ISS-/ESC-
#   numbers. ``bulk_create`` would ship every row numberless — never use it here.
# * Each of the four severity bands and each lifecycle status owns exactly one default tenant-A
#   row (plus the simulation set on its own project), so the ``?band=``/``?top=`` lenses, the
#   state-machine verbs and the two computed boards each have a deterministic row to read. Pulling
#   MORE fixtures moves the composed counts — recompute expectations from the pulled rows (the
#   contract's field table), never from memory.
# * Determinism (L16): every date basis is ``_risk_today()`` (``timezone.localdate()``) and every
#   datetime ``timezone.now()`` — the same clock ``is_review_overdue``/``age_days`` and the lenses
#   read. ``datetime.date.today()`` would flake either side of local midnight.
# * Tests NEVER touch ``management/commands/seed_projects.py`` (the demo seed) — every test builds
#   exactly the rows it asserts on from the factories below.
# ==================================================================================================

#: ``apps.core.crud.crud_list``'s default ``per_page`` — every 7.5 register uses the default, so a
#: pagination test needs ``RISK_PAGE_SIZE + 1`` rows for a second page (same rationale as
#: ``COST_PAGE_SIZE`` above).
RISK_PAGE_SIZE = 15


def _risk_today():
    """Today on the SAME basis the 7.5 code uses (``is_review_overdue`` / ``age_days`` / the
    ``?overdue=``/``?review_due=`` lenses all read ``timezone.localdate()``)."""
    return timezone.localdate()


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints RSK-/RRA-/ISS-/ESC-
# ==================================================================================================

def _risk_project(tenant, **overrides):
    """An ACTIVE host ``Project`` for 7.5 rows (built through the 7.1 FACTORY — function import,
    not a 7.1 fixture; the ``cost_project_a`` precedent).

    Defaults: ``status="active"``, ``charter_status="approved"``, window today−30 .. today+150, a
    distinct per-tenant name/code ("Risk host NN" / "RHP-NN"). The board lenses work per project,
    so a test that wants an isolated register builds a throwaway project here instead of sharing
    the lifecycle rows' host.
    """
    from apps.projects.models import Project
    seq = Project.objects.filter(tenant=tenant).count() + 1
    # Defaults merge with (never collide with) the caller's overrides — the fixture passes
    # ``name=``/``code=`` of its own, so a straight ``**overrides`` splat would raise
    # ``TypeError: got multiple values for keyword argument 'name'``.
    fields = dict(
        name=f"Risk host {seq:02d}",
        code=f"RHP-{seq:02d}",
        status="active",
        charter_status="approved",
        start_date=_risk_today() - datetime.timedelta(days=30),
        end_date=_risk_today() + datetime.timedelta(days=150),
    )
    fields.update(overrides)
    return _projectinitiation_project(tenant, **fields)


def _risk(tenant, project, **overrides):
    """A ``ProjectRisk`` on ``project`` with defaults for every required field.

    Defaults: ``probability=2`` / ``impact=2`` (score 4 → the MEDIUM band), ``status="identified"``,
    ``cost_impact=0.00`` (so ``emv`` is 0.00 and the row stays OUT of the Monte Carlo population —
    the population is ``cost_impact > 0`` AND status not realized/closed), ``category="other"``,
    ``risk_type="threat"``, ``response_strategy="mitigate"``, ``identified_date=today``,
    ``review_date=None``, a distinct per-tenant ``title`` ("Risk NN"). Pass explicit
    ``probability=``/``impact=`` to place a row in a chosen band (see the contract's field table).
    ``clean()`` runs before ``save()`` (the 7.4 factory precedent) so a cross-project
    ``wbs_node``/``contingency_account`` raises at build time instead of seeding bad data.
    """
    from apps.projects.models import ProjectRisk
    seq = ProjectRisk.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        title=f"Risk {seq:02d}",
        description="Vendor delivery could slip the integration window.",
        cause="The vendor single-sources the module.",
        effect="Go-live slips by one sprint.",
        category="other",
        risk_type="threat",
        probability=2,
        impact=2,
        cost_impact=Decimal("0.00"),
        schedule_impact_days=None,
        response_strategy="mitigate",
        response_note="",
        trigger="",
        contingency_plan="",
        status="identified",
        owner=None,
        identified_by=None,
        identified_date=_risk_today(),
        review_date=None,
        residual_probability=None,
        residual_impact=None,
        contingency_account=None,
        lessons_learned="",
        closed_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = ProjectRisk(**fields)
    obj.clean()
    obj.save()
    return obj


def _risk_action(risk, **overrides):
    """A ``RiskResponseAction`` on ``risk`` (``tenant`` taken FROM the risk).

    Defaults: ``status="planned"`` (edit/delete OPEN; ``is_locked`` is only ``completed``),
    ``strategy="mitigate"``, ``due_date=None`` (NOT overdue), ``cost=0.00``, a distinct per-tenant
    ``title`` ("Response action NN"). Pass ``due_date=_risk_today() - timedelta(days=3)`` for the
    overdue lens and ``status="completed"`` (+ ``completed_at``) for the frozen row.
    """
    from apps.projects.models import RiskResponseAction
    seq = RiskResponseAction.objects.filter(tenant=risk.tenant_id).count() + 1
    fields = dict(
        tenant=risk.tenant,
        risk=risk,
        title=f"Response action {seq:02d}",
        description="Ship the fallback integration path.",
        strategy="mitigate",
        owner=None,
        due_date=None,
        cost=Decimal("0.00"),
        trigger="",
        status="planned",
        residual_probability=None,
        residual_impact=None,
        completed_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = RiskResponseAction(**fields)
    obj.save()
    return obj


def _risk_issue(tenant, project, **overrides):
    """A ``ProjectIssue`` on ``project`` with defaults for every required field.

    Defaults: ``status="open"`` (edit/delete OPEN; ``is_locked`` is resolved/closed),
    ``issue_type="issue"``, ``severity="medium"``, ``escalation_level=0`` (NOT in the
    ``?escalated=1`` lens), ``identified_date=today``, ``due_date=None`` (NOT overdue),
    ``risk=None``, a distinct per-tenant ``title`` ("Issue NN"). ``clean()`` runs before
    ``save()`` — a cross-project ``wbs_node``/``risk`` raises at build time.
    """
    from apps.projects.models import ProjectIssue
    seq = ProjectIssue.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        risk=None,
        title=f"Issue {seq:02d}",
        description="The shared integration environment is down.",
        issue_type="issue",
        severity="medium",
        status="open",
        owner=None,
        raised_by=None,
        identified_date=_risk_today(),
        due_date=None,
        escalation_level=0,
        escalated_to=None,
        escalated_at=None,
        root_cause="",
        resolution_note="",
        resolved_by=None,
        resolved_at=None,
        lessons_learned="",
        created_by=None,
    )
    fields.update(overrides)
    obj = ProjectIssue(**fields)
    obj.clean()
    obj.save()
    return obj


def _risk_escalation(issue, **overrides):
    """An ``IssueEscalation`` on ``issue`` (``tenant`` taken FROM the issue).

    Defaults: ``level=1``, ``reason`` filled (the model REQUIRES it), ``target_role=""``,
    ``target_user=None``, ``escalated_by=None``, ``outcome=""``. ``escalated_at`` is
    ``auto_now_add`` — it is stamped on INSERT and any override is ignored; do not pass it.
    """
    from apps.projects.models import IssueEscalation
    seq = IssueEscalation.objects.filter(tenant=issue.tenant_id).count() + 1
    fields = dict(
        tenant=issue.tenant,
        issue=issue,
        level=1,
        target_role="",
        target_user=None,
        reason=f"Escalation {seq:02d}: the blocker needs a decision above the delivery team.",
        escalated_by=None,
        resolved_at=None,
        outcome="",
        created_by=None,
    )
    fields.update(overrides)
    obj = IssueEscalation(**fields)
    obj.save()
    return obj


# -- bulk fills (pagination / search / the register cap) ---------------------------------------------
#
# Loops over the factories rather than bulk_create for the reason spelled out at the top of this
# file: bulk_create skips save(), and save() is where `number` is minted.

def _risk_fill_risks(tenant, project, count, **overrides):
    """``count`` LOW-band backlog risks on ONE project — ``probability=1`` / ``impact=1`` (score 1,
    never above tolerance), ``cost_impact=0`` (never in the simulation population),
    ``review_date=None`` (never in the review queue), ``identified_date=today``,
    distinct titles ("Backlog risk 01" …). Returns the list; overrides
    land on EVERY row (pass ``identified_date=`` offsets for burndown spreads)."""
    return [
        _risk(tenant, project, title=f"Backlog risk {i:02d}",
              probability=1, impact=1, **overrides)
        for i in range(1, count + 1)
    ]


def _risk_fill_issues(tenant, project, count, **overrides):
    """``count`` OPEN backlog issues on ONE project — ``due_date=None`` (never overdue),
    ``escalation_level=0`` (never in the escalated queue), ``identified_date=today``, distinct
    titles ("Backlog issue 01" …). Returns the list; overrides land on EVERY row."""
    return [
        _risk_issue(tenant, project, title=f"Backlog issue {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# Core-spine records the 7.5 FKs point at
# ==================================================================================================

@pytest.fixture
def risk_project_a(db, tenant_a, admin_user):
    """Tenant A's ACTIVE host — every default 7.5 row hangs off this one or the tenant-B twin
    (window today−30 .. today+150; the boards' ``?project=`` lens scopes to it)."""
    return _risk_project(
        tenant_a, name="Risk host Alpha", code="RHA-01",
        charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        created_by=admin_user)


@pytest.fixture
def risk_project_b(db, tenant_b, admin_b):
    """Tenant B's host — 404 as tenant A everywhere; absent from tenant A's registers; the
    crafted-POST value for ``project`` on all three ModelForms that carry it."""
    return _risk_project(tenant_b, name="Risk host Beta", code="RHB-01", created_by=admin_b)


@pytest.fixture
def risk_wbs_node_a(db, risk_project_a):
    """Tenant A work package — the VALID ``wbs_node`` anchor for a risk/issue on
    ``risk_project_a`` (the same-project ``clean()`` branch) and the ``?``-less detail render."""
    return _planning_task(risk_project_a.tenant, risk_project_a, name="Risk work package")


@pytest.fixture
def risk_wbs_node_b(db, risk_project_b):
    """Tenant B's work package — the crafted-POST value for ``wbs_node`` on the risk and issue
    forms, and the cross-project node for the same-project ``clean()`` refusal tests."""
    return _planning_task(risk_project_b.tenant, risk_project_b,
                          name="Globex risk work package")


# ==================================================================================================
# Extra actors + clients (aliases over the ROOT conftest — reuse, never redefine)
# ==================================================================================================

@pytest.fixture
def risk_member(db, member_user):
    """Tenant A's plain member — alias of the root ``member_user``: 403 on the admin-gated verbs
    (``iss_escalate``, ``rsk_reopen`` and — the I9 fix — ``esc_create``/``esc_edit``/
    ``esc_delete``), full run on the login-only ones (realize/close, complete, resolve/close and
    all CRUD pages, deletes included — deletes are NOT admin-gated in 7.5)."""
    return member_user


@pytest.fixture
def risk_member_b(db, tenant_b):
    """A NON-admin member of tenant B. Separates the two refusals on the admin-gated verbs: a
    tenant-B member hitting a tenant-A pk must 404 on scope, never 403 on role — and a tenant-A
    member (root ``member_user``) must 403 before any lookup."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="risk-member@globex.com", username="member_globex_risk",
        password="TestPass123!", tenant=tenant_b, is_tenant_admin=False)


@pytest.fixture
def risk_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape. The four 7.5 create views guard
    this on their first branch and redirect to ``dashboard:home``; the registers and both computed
    boards render EMPTY BY DESIGN (no 500, the 0-safe branches hold)."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="risk-drifter@example.com", username="risk_drifter",
        password="TestPass123!", tenant=None)


@pytest.fixture
def risk_tenantless_client(db, risk_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers render empty; creates redirect away."""
    client = Client()
    client.force_login(risk_tenantless_user)
    return client


@pytest.fixture
def risk_anon_client(db):
    """Unauthenticated — every 7.5 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def risk_admin_client(db, client_a):
    """Tenant A admin logged in — alias of the root ``client_a`` (7.1–7.4 define no admin client
    of their own either; the alias exists so the 7.5 contract can pin the name). Runs the admin
    happy paths AND every IDOR-404 probe."""
    return client_a


@pytest.fixture
def risk_member_client(db, member_client):
    """Tenant A member logged in — alias of the root ``member_client``. For tenant-B ADMIN
    requests use the root ``client_b`` (no alias needed)."""
    return member_client


@pytest.fixture
def risk_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


# ==================================================================================================
# ProjectRisk — one fixture per severity band and lifecycle state
# (all on risk_project_a except ``_b``; the per-row field table lives in the test contract §3)
# ==================================================================================================

@pytest.fixture
def risk_low(db, tenant_a, risk_project_a, admin_user):
    """THE LOW band row: p=1 × i=2 → score 2, ``status="identified"``. The ``?band=low`` lens row
    and the ``rsk_edit``/``rsk_delete``/``rsk_realize`` happy-path row."""
    return _risk(tenant_a, risk_project_a, title="Sensor lead time slips",
                 description="A long-lead sensor pushes the integration window out.",
                 category="technical", probability=1, impact=2, created_by=admin_user)


@pytest.fixture
def risk_medium(db, tenant_a, risk_project_a, admin_user):
    """THE MEDIUM band row: p=2 × i=2 → score 4, ``status="assessing"``. The ``?band=medium``
    lens row and the ``rsk_close``/``rsk_realize`` happy path (severity maps to ``medium``)."""
    return _risk(tenant_a, risk_project_a, title="Key-person dependency",
                 description="One engineer holds all the integration knowledge.",
                 category="resource", probability=2, impact=2, status="assessing",
                 created_by=admin_user)


@pytest.fixture
def risk_high(db, tenant_a, risk_project_a, admin_user):
    """THE HIGH band row: p=3 × i=3 → score 9, ``status="response_planned"``. In
    ``TOLERANCE_BANDS`` → counts into ``above_tolerance_count``; owns the three response-action
    fixtures (``risk_action_*``)."""
    return _risk(tenant_a, risk_project_a, title="Integration API instability",
                 description="The vendor API breaks on every minor release.",
                 category="external", probability=3, impact=3, status="response_planned",
                 created_by=admin_user)


@pytest.fixture
def risk_critical(db, tenant_a, risk_project_a, admin_user):
    """THE CRITICAL band row: p=4 × i=5 → score 20, ``status="monitoring"``. FIRST in the
    ``?top=1`` ordering and in ``top_risks``; ``?band=critical`` row; above tolerance."""
    return _risk(tenant_a, risk_project_a, title="Core vendor insolvency",
                 description="The vendor enters administration mid-delivery.",
                 category="external", probability=4, impact=5, status="monitoring",
                 created_by=admin_user)


@pytest.fixture
def risk_overdue(db, tenant_a, risk_project_a, admin_user):
    """THE overdue row: ``review_date=today−3`` while ``status="identified"`` →
    ``is_review_overdue`` True. The ``?review_due=1``/``?overdue=1`` lens row and the monitoring
    board's ``review_queue`` entry (p=2 × i=3 → medium band)."""
    return _risk(tenant_a, risk_project_a, title="Regulatory sign-off drifts",
                 description="The compliance review date keeps sliding.",
                 category="compliance", probability=2, impact=3,
                 review_date=_risk_today() - datetime.timedelta(days=3),
                 created_by=admin_user)


@pytest.fixture
def risk_realized(db, tenant_a, risk_project_a, admin_user):
    """THE realized row: p=4 × i=4 → score 16 (critical band), ``cost_impact=25000.00`` →
    ``emv`` 17500.00. ``is_locked`` → edit/delete REFUSE it; realize answers "already realized"
    and writes nothing; close is still allowed FROM it. Pull ``risk_realized_issue`` for the
    linked-issue invariant pair (risk → its minted issue)."""
    return _risk(tenant_a, risk_project_a, title="Data migration corrupted",
                 description="The cutover script mangled the legacy dates.",
                 category="technical", probability=4, impact=4,
                 cost_impact=Decimal("25000.00"), status="realized",
                 identified_date=_risk_today() - datetime.timedelta(days=65),
                 created_by=admin_user)


@pytest.fixture
def risk_closed(db, tenant_a, risk_project_a, admin_user):
    """THE closed row: p=3 × i=4 → score 12 (high band), ``cost_impact=12000.00`` → ``emv``
    6000.00, ``closed_at`` stamped (now−2d), ``lessons_learned`` set (the monitoring lessons lens'
    Risk half) and residual 2×2 (residual_score 4 → medium; ``residual_emv`` 240.00 — the only
    residual row by default). ``is_locked`` → edit/delete refuse; realize REFUSES (closed);
    ``rsk_reopen``'s only happy path (→ monitoring, ``closed_at`` cleared)."""
    return _risk(tenant_a, risk_project_a, title="Requirements churn",
                 description="Scope statements keep being rewritten after sign-off.",
                 category="organizational", probability=3, impact=4,
                 cost_impact=Decimal("12000.00"), status="closed",
                 residual_probability=2, residual_impact=2,
                 lessons_learned="Validate sign-off authority before baselining scope.",
                 closed_at=timezone.now() - datetime.timedelta(days=2),
                 identified_date=_risk_today() - datetime.timedelta(days=130),
                 created_by=admin_user)


@pytest.fixture
def risk_b(db, tenant_b, risk_project_b, admin_b):
    """Tenant B's risk (the factory-default identified/medium shape) — 404 as tenant A on
    detail/edit/delete and on all five verbs; absent from tenant A's register; the crafted-POST
    value for ``risk`` on the action and issue forms."""
    return _risk(tenant_b, risk_project_b, title="Globex vendor delay",
                 created_by=admin_b)


# ==================================================================================================
# ProjectIssue — one fixture per lifecycle state the three verbs branch on
# ==================================================================================================

@pytest.fixture
def risk_issue_open(db, tenant_a, risk_project_a, admin_user):
    """THE open issue (``identified_date`` today−5) — the happy path for ``iss_edit``/
    ``iss_delete``/``iss_resolve`` and for ``iss_escalate`` (level 0 → 1). ``due_date=None`` →
    NOT overdue; ``escalation_level=0`` → NOT in the ``?escalated=1`` lens."""
    return _risk_issue(tenant_a, risk_project_a, title="Integration environment down",
                       description="The shared environment has been unreachable since Monday.",
                       identified_date=_risk_today() - datetime.timedelta(days=5),
                       created_by=admin_user)


@pytest.fixture
def risk_issue_overdue(db, tenant_a, risk_project_a, admin_user):
    """THE overdue issue: ``status="blocked"`` (still open) with ``due_date=today−2`` →
    ``is_overdue`` True. The issue log's ``?overdue=1`` lens row; ``iss_close`` must REFUSE it
    (only a resolved row closes); ``age_days`` reads 20."""
    return _risk_issue(tenant_a, risk_project_a, title="Blocked on legal review",
                       description="Contract language is stuck with legal.",
                       status="blocked", due_date=_risk_today() - datetime.timedelta(days=2),
                       identified_date=_risk_today() - datetime.timedelta(days=20),
                       created_by=admin_user)


@pytest.fixture
def risk_issue_escalated(db, tenant_a, risk_project_a, admin_user):
    """THE escalated issue: ``status="in_progress"``, ``escalation_level=2``,
    ``escalated_to=admin_user``, ``escalated_at`` stamped (now−1h) — WITH its backing
    ``IssueEscalation`` row (level 2, target_role "Programme manager", target_user admin_user,
    escalated_by admin_user) so the trail and the level agree, the shape ``iss_escalate`` leaves
    behind (the I1 atomic pair). The ``?escalated=1`` lens row and the escalation register's only
    default tenant-A row."""
    issue = _risk_issue(tenant_a, risk_project_a, title="Payment gateway outage",
                        description="Checkout has been failing for two hours.",
                        status="in_progress", escalation_level=2, escalated_to=admin_user,
                        escalated_at=timezone.now() - datetime.timedelta(hours=1),
                        identified_date=_risk_today() - datetime.timedelta(days=8),
                        created_by=admin_user)
    _risk_escalation(issue, level=2, target_role="Programme manager", target_user=admin_user,
                     reason="Needs a budget decision above the project team.",
                     escalated_by=admin_user, created_by=admin_user)
    return issue


@pytest.fixture
def risk_issue_resolved(db, tenant_a, risk_project_a, admin_user):
    """THE resolved issue: root_cause + resolution_note + ``resolved_by``/``resolved_at`` (now−1d)
    + ``lessons_learned`` set. ``iss_close``'s ONLY happy path; ``iss_resolve`` answers "already
    resolved"; edit/delete REFUSE it (locked). Past ``due_date`` (today−5) yet NOT overdue —
    ``is_open`` is False, pinning the overdue lens' status guard. The lessons lens' newest Issue
    half row."""
    return _risk_issue(tenant_a, risk_project_a, title="License server flapping",
                       description="Designers keep losing their seats.",
                       status="resolved", root_cause="Expired TLS certificate on the daemon.",
                       resolution_note="Certificate renewed and expiry monitoring added.",
                       resolved_by=admin_user,
                       resolved_at=timezone.now() - datetime.timedelta(days=1),
                       lessons_learned="Certificate expiry belongs in the ops calendar.",
                       due_date=_risk_today() - datetime.timedelta(days=5),
                       identified_date=_risk_today() - datetime.timedelta(days=10),
                       created_by=admin_user)


@pytest.fixture
def risk_issue_closed(db, tenant_a, risk_project_a, admin_user):
    """THE closed issue: full resolved stamps (``resolved_at`` now−3d) + ``status="closed"`` +
    ``lessons_learned``. Resolve/escalate/close all refuse it (frozen evidence); the lessons
    lens' oldest Issue half row."""
    return _risk_issue(tenant_a, risk_project_a, title="Duplicate invoice entries",
                       description="Two entries appeared for one delivery.",
                       status="closed", root_cause="Retry logic double-posted the webhook.",
                       resolution_note="Webhook handler made idempotent.",
                       resolved_by=admin_user,
                       resolved_at=timezone.now() - datetime.timedelta(days=3),
                       lessons_learned="Every webhook handler needs an idempotency key.",
                       identified_date=_risk_today() - datetime.timedelta(days=15),
                       created_by=admin_user)


@pytest.fixture
def risk_issue_b(db, tenant_b, risk_project_b, admin_b):
    """Tenant B's issue (open) — 404 as tenant A on detail/edit/delete and on all three verbs;
    absent from tenant A's register; the crafted-POST value for ``issue`` on the escalation
    form."""
    return _risk_issue(tenant_b, risk_project_b, title="Globex environment outage",
                       created_by=admin_b)


# ==================================================================================================
# RiskResponseAction — the response plan's rows (hang off risk_high)
# ==================================================================================================

@pytest.fixture
def risk_action_open(db, tenant_a, risk_high, admin_user):
    """THE planned action (on ``risk_high``, cost 2500.00) — the happy path for ``rra_edit``/
    ``rra_delete``/``rra_complete``. ``due_date=None`` → NOT overdue."""
    return _risk_action(risk_high, title="Stand up fallback integration",
                        description="Prebuild the queue-based fallback path.",
                        cost=Decimal("2500.00"), created_by=admin_user)


@pytest.fixture
def risk_action_overdue(db, tenant_a, risk_high, admin_user):
    """THE overdue action: ``status="in_progress"`` (still live) with ``due_date=today−3`` →
    ``is_overdue`` True. The action register's ``?overdue=1`` lens row."""
    return _risk_action(risk_high, title="Migrate vendor contract",
                        status="in_progress",
                        due_date=_risk_today() - datetime.timedelta(days=3),
                        created_by=admin_user)


@pytest.fixture
def risk_action_completed(db, tenant_a, risk_high, admin_user):
    """THE completed action: ``status="completed"`` + ``completed_at`` (now−1d). ``is_locked`` →
    edit/delete REFUSE it; ``rra_complete`` answers "already completed" and writes nothing."""
    return _risk_action(risk_high, title="Renegotiate the SLA",
                        status="completed",
                        completed_at=timezone.now() - datetime.timedelta(days=1),
                        created_by=admin_user)


@pytest.fixture
def risk_action_b(db, tenant_b, risk_b, admin_b):
    """Tenant B's action (planned, on ``risk_b``) — 404 as tenant A on detail/edit/delete and on
    the complete verb; absent from tenant A's register."""
    return _risk_action(risk_b, title="Globex contingency drill", created_by=admin_b)


@pytest.fixture
def risk_escalation_b(db, tenant_b, risk_issue_b, admin_b):
    """Tenant B's escalation row (level 1, on ``risk_issue_b``) — 404 as tenant A on detail/edit
    and on the delete verb; absent from tenant A's register."""
    return _risk_escalation(risk_issue_b, level=1, reason="Vendor response overdue.",
                            escalated_by=admin_b, created_by=admin_b)


# ==================================================================================================
# The Monte Carlo set — a dedicated project so ``?project=<sim>`` isolates the population
# (the analysis board's POST population = register rows with cost_impact > 0 and status NOT
# realized/closed, drawn in **id-ascending** order — replay it in-test with random.Random(seed))
# ==================================================================================================

@pytest.fixture
def risk_sim_project(db, tenant_a, admin_user):
    """The simulation board's dedicated tenant-A project — simulation tests select
    ``?project=<this pk>``, so none of the lifecycle rows above can enter the population."""
    return _risk_project(tenant_a, name="Risk simulation host", code="RSH-01",
                         created_by=admin_user)


@pytest.fixture
def risk_sim_high(db, tenant_a, risk_sim_project, admin_user):
    """Population row 1: p=5 (90% per ``PROBABILITY_PCT``), ``cost_impact=1000.00``,
    identified → IN the Monte Carlo population (p×i = 20, critical)."""
    return _risk(tenant_a, risk_sim_project, title="Cloud cost overrun",
                 description="Autoscaling outruns the reserved capacity.",
                 category="cost", probability=5, impact=4,
                 cost_impact=Decimal("1000.00"), created_by=admin_user)


@pytest.fixture
def risk_sim_rare(db, tenant_a, risk_sim_project, admin_user):
    """Population row 2: p=1 (10%), ``cost_impact=500.00``, identified → IN the population
    (p×i = 1, low). The rare-but-expensive tail the percentile table exists for."""
    return _risk(tenant_a, risk_sim_project, title="Data centre outage",
                 description="A region loss stops fulfilment for days.",
                 category="external", probability=1, impact=1,
                 cost_impact=Decimal("500.00"), created_by=admin_user)


@pytest.fixture
def risk_sim_realized(db, tenant_a, risk_sim_project, admin_user):
    """EXCLUDED from the population (status realized — a realized cost is actual spend, not
    uncertainty) but still IN the register/matrix/EMV table (emv 8100.00). Proves the status
    exclusion branch."""
    return _risk(tenant_a, risk_sim_project, title="Legacy ETL failure",
                 description="The cutover happened; the bill is real.",
                 category="technical", probability=5, impact=5,
                 cost_impact=Decimal("9000.00"), status="realized", created_by=admin_user)


@pytest.fixture
def risk_sim_zero_cost(db, tenant_a, risk_sim_project, admin_user):
    """EXCLUDED from the population (``cost_impact=0`` — nothing to sample) but IN the register
    and the matrix (p×i = 6, medium). Proves the cost exclusion branch."""
    return _risk(tenant_a, risk_sim_project, title="Reputation drag",
                 description="Public perception dips after the outage.",
                 category="organizational", probability=3, impact=2,
                 cost_impact=Decimal("0.00"), created_by=admin_user)


@pytest.fixture
def risk_baseline(db, tenant_a, admin_user, risk_sim_project):
    """THE 7.4 cost baseline on ``risk_sim_project`` — an approved+ACTIVATED ``BudgetRevision``
    (revision_no 0, the ``bvr_activate`` shape) carrying one 400.00 cost line, so the analysis
    board scoped to the sim project reads ``baseline_total = 400.00`` and a POST simulation gets
    ``overrun_probability`` (the % of samples > 400.00) and ``contingency_delta`` (p80 − 400.00).
    Built through the 7.4 FACTORIES (same-module function calls, not 7.4 fixtures — the
    ``cost_wbs_node_a`` uses-``_planning_task`` precedent). ``risk_project_a`` never has a
    baseline, so the no-baseline edge (``baseline``/``baseline_total`` None,
    ``overrun_probability`` None) stays testable there."""
    revision = _cost_revision(tenant_a, risk_sim_project, no=0, activate=True,
                              title="Simulation baseline", reason="P80 sizing input.",
                              requested_by=admin_user, created_by=admin_user)
    _cost_budget_line(tenant_a, revision, risk_sim_project, category="cost",
                      amount="400.00", note="Contingency sizing baseline.")
    return revision


# ==================================================================================================
# 7.6 Quality Management (subslug ``quality``)
# --------------------------------------------------------------------------------------------------
# Fixtures for ``test_quality_models.py`` / ``test_quality_forms.py`` / ``test_quality_views.py`` /
# ``test_quality_security.py``. The frozen test contract is
# ``.claude/tasks/test-contract-projects-7.6.md``; the build contract
# (``.claude/tasks/contract-projects-7.6.md``) §2–§6 pins every name the code answers to.
#
# * Everything board-worthy is DERIVED, never stored (``is_review_overdue``/``is_locked``/
#   ``is_improvement_overdue``/``is_overdue``/``age_days``/``is_open``/``defect_count``, plus both
#   computed pages' maturity/acceptance figures). The fixtures pin the INPUT columns (status,
#   dates, review_type, result, usage_decision, severity — the per-row field table in the test
#   contract); the test modules assert the derived figures from them.
# * Factories construct + ``.save()`` so ``TenantNumbered.save()`` mints QPL-/QRV-/QCI-/QDF-
#   numbers. ``bulk_create`` would ship every row numberless — never use it here.
# * Every lifecycle status owns exactly one default tenant-A row, and the discriminating choice
#   values the registers and boards lens on (review_type, inspection result, acceptance decision,
#   defect severity, the improvement statuses that owe work and the one that does not) each own
#   one — so every ``?filter=``/``?kind=``/``?overdue=`` lens, the ten verbs and both computed
#   pages have a deterministic row to read. Pulling MORE fixtures moves the composed figures —
#   recompute expectations from the pulled rows (the test contract's §3 tables), never from memory.
# * Determinism (L16): every date basis is ``_quality_today()`` (``timezone.localdate()``) and
#   every datetime ``timezone.now()`` — the same clock the ``is_*`` properties, ``age_days`` and
#   the lenses read. ``datetime.date.today()`` would flake either side of local midnight.
# * Spine reuse: host projects come from the 7.1 FACTORY ``_projectinitiation_project`` and WBS
#   deliverable nodes from the 7.2 FACTORY ``_planning_task`` (function imports, NOT those lanes'
#   fixtures — lanes never depend on each other's fixture rows); the defect→issue bridge row is
#   built with the 7.5 FACTORY ``_risk_issue`` (same-module call, the ``risk_baseline`` precedent).
# * Tests NEVER touch ``management/commands/seed_projects.py`` (the demo seed) — every test builds
#   exactly the rows it asserts on from the factories below.
# ==================================================================================================

#: ``apps.core.crud.crud_list``'s default ``per_page`` — every 7.6 register uses the default, so a
#: pagination test needs ``QUALITY_PAGE_SIZE + 1`` rows for a second page (same rationale as
#: ``RISK_PAGE_SIZE`` above).
QUALITY_PAGE_SIZE = 15


def _quality_today():
    """Today on the SAME basis the 7.6 code uses (``is_review_overdue`` /
    ``is_improvement_overdue`` / ``is_overdue`` / ``age_days`` and the ``?overdue=`` lenses all
    read ``timezone.localdate()``)."""
    return timezone.localdate()


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints QPL-/QRV-/QCI-/QDF-
# ==================================================================================================

def _quality_project(tenant, **overrides):
    """An ACTIVE host ``Project`` for 7.6 rows (built through the 7.1 FACTORY — function import,
    not a 7.1 fixture; the ``risk_project`` precedent).

    Defaults: ``status="active"``, ``charter_status="approved"``, window today−30 .. today+150, a
    distinct per-tenant name/code ("Quality host NN" / "QHP-NN"). Both computed boards lens per
    project, so a test that wants an isolated register (or a no-rows maturity edge) builds a
    throwaway project here instead of sharing the lifecycle rows' host.
    """
    from apps.projects.models import Project
    seq = Project.objects.filter(tenant=tenant).count() + 1
    # Merge defaults into ``overrides`` (the ``_projectinitiation_project`` idiom) — re-declaring
    # them as explicit kwargs collides with any caller override of the same name.
    overrides.setdefault("name", f"Quality host {seq:02d}")
    overrides.setdefault("code", f"QHP-{seq:02d}")
    overrides.setdefault("status", "active")
    overrides.setdefault("charter_status", "approved")
    overrides.setdefault("start_date", _quality_today() - datetime.timedelta(days=30))
    overrides.setdefault("end_date", _quality_today() + datetime.timedelta(days=150))
    return _projectinitiation_project(tenant, **overrides)


def _quality_wbs_node(tenant, project, **overrides):
    """A ``ProjectTask`` DELIVERABLE node under ``project`` — the node kind 7.6 inspects and the
    acceptance board keys its rows on (``node_type="deliverable"``; built through the 7.2 FACTORY,
    the ``cost_wbs_node_a`` precedent).

    Undated and effort-less by default (a bare deliverable's rollups come from its children — the
    ``_planning_wbs_tree`` shape); pass ``planned_start=``/``planned_end=``/``effort_hours=``
    when a test needs a scheduled node. A distinct per-tenant name ("Quality deliverable NN").
    """
    from apps.projects.models import ProjectTask
    seq = ProjectTask.objects.filter(tenant=tenant).count() + 1
    return _planning_task(
        tenant, project,
        node_type="deliverable",
        name=f"Quality deliverable {seq:02d}",
        planned_start=None,
        planned_end=None,
        effort_hours=None,
        **overrides,
    )


def _quality_plan(tenant, project, **overrides):
    """A ``QualityPlan`` on ``project`` — ``draft`` unless overridden.

    Defaults: ``verification_method="inspection"``, ``acceptance_criteria`` filled (REQUIRED — a
    plan with no criteria cannot be inspected against), ``planned_review_date=None`` (never in
    the ``?review_due=1`` lens), no wbs/risk/owner and NO approval stamps (the verb's evidence).
    ``clean()`` runs before ``save()`` (the ``_risk`` precedent) so a cross-project
    ``wbs_node``/``source_risk`` raises at build time instead of seeding bad data.
    """
    from apps.projects.models import QualityPlan
    seq = QualityPlan.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        source_risk=None,
        title=f"Quality plan {seq:02d}",
        description="The acceptance criteria the deliverable is measured against.",
        acceptance_criteria="Zero critical defects on the acceptance inspection.",
        verification_method="inspection",
        standard_reference="ISO 9001:2015 cl. 8.5",
        regulatory_requirement="",
        owner=None,
        status="draft",
        planned_review_date=None,
        approved_by=None,
        approved_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = QualityPlan(**fields)
    obj.clean()
    obj.save()
    return obj


def _quality_review(tenant, project, **overrides):
    """A ``QualityReview`` on ``project`` — a planned ``methodology_review`` unless overridden.

    Defaults: ``review_date=today``, ``maturity_score=None`` (never in the maturity aggregate),
    ``improvement_status="n_a"`` with no action/owner/due date (never overdue, never in
    ``improvement_open_count``), no ``closed_at`` stamp. Pass ``review_type=``/
    ``improvement_*=`` to place the row in either family (assurance: methodology_review /
    compliance_check / gate_review; improvement: kaizen_event / retrospective /
    maturity_assessment). ``clean()`` runs before ``save()`` — a cross-project
    ``wbs_node``/``quality_plan`` raises at build time.
    """
    from apps.projects.models import QualityReview
    seq = QualityReview.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        quality_plan=None,
        title=f"Quality review {seq:02d}",
        scope="The delivery process for the current stage.",
        review_type="methodology_review",
        checklist="Process followed; evidence recorded; sign-offs present.",
        findings="",
        reviewer=None,
        review_date=_quality_today(),
        status="planned",
        maturity_score=None,
        improvement_action="",
        improvement_owner=None,
        improvement_due_date=None,
        improvement_status="n_a",
        closed_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = QualityReview(**fields)
    obj.clean()
    obj.save()
    return obj


def _quality_inspection(tenant, project, **overrides):
    """A ``DeliverableInspection`` on ``project`` — planned/pending and undecided unless
    overridden.

    Defaults: ``inspection_type="review"`` (NOT acceptance — never in the queue),
    ``result="pending"``, ``usage_decision="pending"``, no dates (never overdue), no acceptor
    stamps (``qci_accept``'s evidence) and no milestone. ``clean()`` runs before ``save()`` — a
    cross-project ``wbs_node``/``quality_plan``/``milestone`` raises at build time.
    """
    from apps.projects.models import DeliverableInspection
    seq = DeliverableInspection.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        quality_plan=None,
        milestone=None,
        title=f"Quality inspection {seq:02d}",
        description="The protocol the inspection follows.",
        inspection_type="review",
        planned_date=None,
        inspected_date=None,
        inspector=None,
        result="pending",
        usage_decision="pending",
        findings="",
        accepted_by=None,
        accepted_by_party=None,
        accepted_at=None,
        acceptance_note="",
        status="planned",
        created_by=None,
    )
    fields.update(overrides)
    obj = DeliverableInspection(**fields)
    obj.clean()
    obj.save()
    return obj


def _quality_defect(tenant, project, **overrides):
    """A ``QualityDefect`` on ``project`` — an open minor punch item unless overridden.

    Defaults: ``description`` filled (REQUIRED), ``defect_category="other"``,
    ``severity="minor"``, ``disposition="open"``, ``status="open"``, ``identified_date=today``,
    ``due_date=None`` (never overdue), no resolution stamps and NO issue bridge
    (``project_issue`` is written only by ``qdf_raise_issue`` / the 7.5 factory). ``clean()``
    runs before ``save()`` — a cross-project ``wbs_node``/``quality_plan``/``inspection`` raises
    at build time.
    """
    from apps.projects.models import QualityDefect
    seq = QualityDefect.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        quality_plan=None,
        inspection=None,
        project_issue=None,
        title=f"Quality defect {seq:02d}",
        description="The output does not meet the acceptance criterion.",
        defect_category="other",
        severity="minor",
        disposition="open",
        status="open",
        owner=None,
        identified_date=_quality_today(),
        due_date=None,
        root_cause="",
        resolution_note="",
        resolved_by=None,
        resolved_at=None,
        lessons_learned="",
        created_by=None,
    )
    fields.update(overrides)
    obj = QualityDefect(**fields)
    obj.clean()
    obj.save()
    return obj


# -- bulk fills (pagination / search / the registers) ------------------------------------------------
#
# Loops over the factories rather than bulk_create for the reason spelled out at the top of this
# file: bulk_create skips save(), and save() is where `number` is minted.

def _quality_fill_plans(tenant, project, count, **overrides):
    """``count`` DRAFT backlog plans on ONE project — ``planned_review_date=None`` (never in the
    ``?review_due=1``/``?overdue=1`` lens), distinct titles ("Backlog plan 01" …). Returns the
    list; overrides land on EVERY row."""
    return [
        _quality_plan(tenant, project, title=f"Backlog plan {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _quality_fill_reviews(tenant, project, count, **overrides):
    """``count`` planned methodology reviews on ONE project — ``maturity_score=None`` (never in
    the maturity aggregate), ``improvement_status="n_a"`` with no due date (never overdue, never
    in ``improvement_open_count``), distinct titles ("Backlog review 01" …). Returns the list."""
    return [
        _quality_review(tenant, project, title=f"Backlog review {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _quality_fill_inspections(tenant, project, count, **overrides):
    """``count`` planned/pending ``review``-typed inspections on ONE project — ``planned_date=
    None`` (never overdue) and ``inspection_type="review"`` (never in the acceptance queue),
    distinct titles ("Backlog inspection 01" …). Returns the list."""
    return [
        _quality_inspection(tenant, project, title=f"Backlog inspection {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _quality_fill_defects(tenant, project, count, **overrides):
    """``count`` OPEN backlog defects on ONE project — ``due_date=None`` (never overdue),
    ``identified_date=today`` (deliberate: fills DO land in the improvement trend's current-month
    bucket), ``severity="minor"``, distinct titles ("Backlog defect 01" …). Returns the list."""
    return [
        _quality_defect(tenant, project, title=f"Backlog defect {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# Core-spine records the 7.6 FKs point at
# ==================================================================================================

@pytest.fixture
def quality_project_a(db, tenant_a, admin_user):
    """Tenant A's ACTIVE host — every default 7.6 row hangs off this one or the tenant-B twin
    (window today−30 .. today+150; both computed boards scope to it via ``?project=``)."""
    return _quality_project(
        tenant_a, name="Quality host Alpha", code="QHA-01",
        charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        created_by=admin_user)


@pytest.fixture
def quality_project_b(db, tenant_b, admin_b):
    """Tenant B's host — 404 as tenant A everywhere; absent from tenant A's registers; the
    crafted-POST value for ``project`` on all four ModelForms."""
    return _quality_project(tenant_b, name="Quality host Beta", code="QHB-01",
                            created_by=admin_b)


@pytest.fixture
def quality_wbs_node_a(db, quality_project_a):
    """Tenant A's deliverable node — the VALID ``wbs_node`` anchor (the same-project ``clean()``
    branch) and the acceptance board's ONE default row: exactly one deliverable node, one
    anchored plan, one anchored inspection and one anchored open defect hang off it (the §3.2
    table in the test contract)."""
    return _quality_wbs_node(quality_project_a.tenant, quality_project_a)


@pytest.fixture
def quality_wbs_node_b(db, quality_project_b):
    """Tenant B's deliverable node — the crafted-POST value for ``wbs_node`` on all four forms,
    and the cross-project node for the same-project ``clean()`` refusal tests."""
    return _quality_wbs_node(quality_project_b.tenant, quality_project_b)


@pytest.fixture
def quality_milestone_a(db, quality_project_a):
    """A tenant A ``ProjectMilestone`` (7.2 FACTORY) — the inspection form's same-project
    ``milestone`` FK value (7.2's gate, not re-declared)."""
    return _planning_milestone(quality_project_a.tenant, quality_project_a,
                               name="Quality gate milestone")


@pytest.fixture
def quality_milestone_b(db, quality_project_b):
    """Tenant B's milestone — the crafted-POST value for ``milestone`` on
    ``DeliverableInspectionForm`` (the narrowed queryset refuses it first; assert the FIELD
    error)."""
    return _planning_milestone(quality_project_b.tenant, quality_project_b,
                               name="Globex quality gate milestone")


@pytest.fixture
def quality_client_party_a(db, tenant_a):
    """Tenant A organization Party — the ``accepted_by_party`` on ``quality_inspection_accepted``
    and the ``qci_accept`` happy path's acceptor. ``clients(tenant)`` is ALL tenant parties (a
    Party has no project scope), so any kind passes the dropdown."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization",
                                name="Meridian Retail Co")


@pytest.fixture
def quality_client_party_b(db, tenant_b):
    """Tenant B organization Party — the crafted-POST value for ``accepted_by_party``. The
    ``InspectionAcceptanceForm`` queryset refuses it first (assert the FIELD error); the view's
    ``party.tenant_id`` re-check behind it stays the defence-in-depth layer."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization",
                                name="Globex Customers")


# ==================================================================================================
# Extra actors + clients (aliases over the ROOT conftest — reuse, never redefine)
# ==================================================================================================

@pytest.fixture
def quality_member(db, member_user):
    """Tenant A's plain member — alias of the root ``member_user``: 405 (GET) then 403 (POST) on
    the ONE admin-gated verb ``qpl_supersede`` (the M2 decorator order), full run on every
    login-gated verb and all CRUD pages."""
    return member_user


@pytest.fixture
def quality_member_b(db, tenant_b):
    """A NON-admin member of tenant B. Separates the two refusals on the admin-gated verb: a
    tenant-B member hitting a tenant-A pk must 404 on scope, never 403 on role — and a tenant-A
    member (root ``member_user``) must 403 before any lookup."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="quality-member@globex.com", username="member_globex_quality",
        password="TestPass123!", tenant=tenant_b, is_tenant_admin=False)


@pytest.fixture
def quality_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape. The four 7.6 create views
    guard this on their first branch and redirect to ``dashboard:home``; the registers and both
    computed pages render EMPTY BY DESIGN (the boards are 0-safe)."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="quality-drifter@example.com", username="quality_drifter",
        password="TestPass123!", tenant=None)


@pytest.fixture
def quality_tenantless_client(db, quality_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers render empty; creates redirect away."""
    client = Client()
    client.force_login(quality_tenantless_user)
    return client


@pytest.fixture
def quality_anon_client(db):
    """Unauthenticated — every 7.6 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def quality_admin_client(db, client_a):
    """Tenant A admin logged in — alias of the root ``client_a`` (7.1–7.5 define no admin client
    of their own either; the alias exists so the 7.6 contract can pin the name). Runs the admin
    happy paths AND every IDOR-404 probe."""
    return client_a


@pytest.fixture
def quality_member_client(db, member_client):
    """Tenant A member logged in — alias of the root ``member_client``. For tenant-B ADMIN
    requests use the root ``client_b`` (no alias needed)."""
    return member_client


@pytest.fixture
def quality_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


# ==================================================================================================
# QualityPlan — one fixture per status the two verbs branch on (all on quality_project_a except _b)
# ==================================================================================================

@pytest.fixture
def quality_plan_draft(db, tenant_a, quality_project_a, admin_user):
    """``draft`` — nothing approved. The ``qpl_approve`` happy path and an ``is_locked`` False
    row: ``qpl_edit``/``qpl_delete`` stay OPEN. ``planned_review_date=None`` → never in the
    ``?review_due=1`` lens."""
    return _quality_plan(tenant_a, quality_project_a,
                         title="Depot sensor acceptance criteria", created_by=admin_user)


@pytest.fixture
def quality_plan_active(db, tenant_a, quality_project_a, quality_wbs_node_a, admin_user):
    """``active`` + approval stamps (``approved_by``=admin, ``approved_at`` now−1d) — the shape
    ``qpl_approve`` leaves. Anchored to ``quality_wbs_node_a`` so the acceptance board's
    deliverable row carries a plan (``plan_status`` "active"); the ``qpl_supersede`` happy path
    (NOT locked — an active plan is still editable)."""
    return _quality_plan(tenant_a, quality_project_a,
                         title="Integration testing standard",
                         wbs_node=quality_wbs_node_a, status="active",
                         approved_by=admin_user,
                         approved_at=timezone.now() - datetime.timedelta(days=1),
                         created_by=admin_user)


@pytest.fixture
def quality_plan_superseded(db, tenant_a, quality_project_a, admin_user):
    """``superseded`` + approval stamps — ``is_locked`` → ``qpl_edit``/``qpl_delete`` REFUSE it;
    ``qpl_supersede`` answers "Only an active plan can be superseded"."""
    return _quality_plan(tenant_a, quality_project_a,
                         title="Retired v1 acceptance criteria",
                         status="superseded", approved_by=admin_user,
                         approved_at=timezone.now() - datetime.timedelta(days=14),
                         created_by=admin_user)


@pytest.fixture
def quality_plan_closed(db, tenant_a, quality_project_a, admin_user):
    """``closed`` — the SECOND locked status, so the lock is provably the tuple and not a
    hard-coded ``== "superseded"``. Edit/delete refuse it too."""
    return _quality_plan(tenant_a, quality_project_a, title="Archived pilot criteria",
                         status="closed", approved_by=admin_user,
                         approved_at=timezone.now() - datetime.timedelta(days=30),
                         created_by=admin_user)


@pytest.fixture
def quality_plan_review_overdue(db, tenant_a, quality_project_a, admin_user):
    """THE overdue row: ``planned_review_date=today−3`` while still ``draft`` →
    ``is_review_overdue`` True. The ``?review_due=1``/``?overdue=1`` lens row (contract §4.1)."""
    return _quality_plan(tenant_a, quality_project_a,
                         title="Compliance criteria pending review",
                         planned_review_date=_quality_today() - datetime.timedelta(days=3),
                         created_by=admin_user)


@pytest.fixture
def quality_plan_b(db, tenant_b, quality_project_b, admin_b):
    """Tenant B's plan — 404 as tenant A on detail/edit/delete and on both verbs; absent from
    tenant A's register; the crafted-POST value for ``quality_plan`` on the review/inspection/
    defect forms."""
    return _quality_plan(tenant_b, quality_project_b, title="Globex acceptance criteria",
                         created_by=admin_b)


# ==================================================================================================
# QualityReview — one per status plus the family / improvement-lens rows
# ==================================================================================================

@pytest.fixture
def quality_review_planned(db, tenant_a, quality_project_a, admin_user):
    """``planned`` ``methodology_review`` (review_date today) — the ``qrv_report`` happy path AND
    the ``?kind=assurance`` family row. ``qrv_close`` must REFUSE it (nothing to retire yet)."""
    return _quality_review(tenant_a, quality_project_a, title="Sprint methodology review",
                           scope="How the delivery team runs its sprints.",
                           created_by=admin_user)


@pytest.fixture
def quality_review_in_progress(db, tenant_a, quality_project_a, admin_user):
    """``in_progress`` ``compliance_check`` — the SECOND legal ``qrv_report`` source (the
    close-out amendment: a review reports from ``planned`` OR ``in_progress``)."""
    return _quality_review(tenant_a, quality_project_a, title="ISO 9001 compliance check",
                           review_type="compliance_check", status="in_progress",
                           created_by=admin_user)


@pytest.fixture
def quality_review_reported(db, tenant_a, quality_project_a, admin_user):
    """``reported`` ``gate_review`` with findings recorded — the ONLY ``qrv_close`` happy path;
    ``qrv_report`` must answer "already" and write nothing."""
    return _quality_review(tenant_a, quality_project_a, title="Stage-gate readiness review",
                           review_type="gate_review", status="reported",
                           findings="Two sign-off artefacts were missing at the gate.",
                           created_by=admin_user)


@pytest.fixture
def quality_review_closed(db, tenant_a, quality_project_a, admin_user):
    """``closed`` + ``closed_at`` (now−1d) — ``is_locked`` → edit/delete REFUSE it; report and
    close both answer "already"."""
    return _quality_review(tenant_a, quality_project_a, title="Closed methodology review",
                           status="closed",
                           findings="Process followed; no nonconformities.",
                           closed_at=timezone.now() - datetime.timedelta(days=1),
                           created_by=admin_user)


@pytest.fixture
def quality_review_cancelled(db, tenant_a, quality_project_a, admin_user):
    """``cancelled`` — the second locked status; a cancelled review can still carry findings but
    nothing may be written to it."""
    return _quality_review(tenant_a, quality_project_a, title="Cancelled compliance check",
                           review_type="compliance_check", status="cancelled",
                           created_by=admin_user)


@pytest.fixture
def quality_review_improvement(db, tenant_a, quality_project_a, admin_user):
    """THE improvement-family row: ``retrospective`` with a PLANNED improvement action
    (``improvement_action`` set, ``improvement_owner``=admin, ``improvement_due_date=today+7``,
    ``improvement_status="planned"``). The ``?kind=improvement`` lens row, an improvement-board
    row, and one of the two rows in ``improvement_open_count``."""
    return _quality_review(tenant_a, quality_project_a, title="Sprint 12 retrospective",
                           review_type="retrospective",
                           improvement_action="Automate the regression pack before sprint 14.",
                           improvement_owner=admin_user,
                           improvement_due_date=_quality_today() + datetime.timedelta(days=7),
                           improvement_status="planned",
                           created_by=admin_user)


@pytest.fixture
def quality_review_improvement_overdue(db, tenant_a, quality_project_a, admin_user):
    """THE overdue row: ``kaizen_event`` with ``improvement_due_date=today−3`` while
    ``improvement_status="in_progress"`` → ``is_improvement_overdue`` True. The register's
    ``?overdue=1`` lens row and the second ``improvement_open_count`` row."""
    return _quality_review(tenant_a, quality_project_a, title="Deployment kaizen event",
                           review_type="kaizen_event",
                           improvement_action="Split the deploy pipeline's test stage.",
                           improvement_status="in_progress",
                           improvement_due_date=_quality_today() - datetime.timedelta(days=3),
                           created_by=admin_user)


@pytest.fixture
def quality_review_improvement_done(db, tenant_a, quality_project_a, admin_user):
    """THE finished action: ``retrospective`` with ``improvement_status="done"`` and
    ``improvement_due_date=today−7`` — completed on time, so ``is_improvement_overdue`` is False
    and ``improvement_open_count`` EXCLUDES it while ``improvement_rows`` still shows it: the
    boundary the overdue row contrasts with."""
    return _quality_review(tenant_a, quality_project_a, title="Retro with a finished action",
                           review_type="retrospective",
                           improvement_action="Add the acceptance checklist to the template.",
                           improvement_status="done",
                           improvement_due_date=_quality_today() - datetime.timedelta(days=7),
                           created_by=admin_user)


@pytest.fixture
def quality_review_maturity(db, tenant_a, quality_project_a, admin_user):
    """THE scored row: ``maturity_assessment`` with ``maturity_score=4`` — the default set's ONLY
    ``maturity_score`` (``reviews_scored`` 1, avg 4.0), the 60% half of the improvement page's
    computed maturity (3.0 / "Defined" / badge-info, pinned §3.1 of the test contract)."""
    return _quality_review(tenant_a, quality_project_a, title="Q3 maturity assessment",
                           review_type="maturity_assessment", maturity_score=4,
                           created_by=admin_user)


@pytest.fixture
def quality_review_b(db, tenant_b, quality_project_b, admin_b):
    """Tenant B's review — 404 as tenant A on detail/edit/delete and on both verbs; absent from
    tenant A's register."""
    return _quality_review(tenant_b, quality_project_b, title="Globex methodology review",
                           created_by=admin_b)


# ==================================================================================================
# DeliverableInspection — one per status and per result, every row an honest verb-output shape
# ==================================================================================================

@pytest.fixture
def quality_inspection_planned(db, tenant_a, quality_project_a, admin_user):
    """``planned``/``pending`` with ``planned_date=today+7`` — the ``qci_record`` happy path and
    an unlocked row: ``qci_edit``/``qci_delete`` stay OPEN. Never overdue."""
    return _quality_inspection(tenant_a, quality_project_a,
                               title="Sensor batch first-article",
                               planned_date=_quality_today() + datetime.timedelta(days=7),
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_in_progress(db, tenant_a, quality_project_a, admin_user):
    """The recorded-undecided shape ``qci_record`` leaves: result ``pass``,
    ``inspected_date=today−1``, status ``in_progress``, decision still ``pending``. The
    decide-later happy path for a NON-acceptance row (``qci_accept``/``qci_reject`` both take
    it)."""
    return _quality_inspection(tenant_a, quality_project_a, title="Harness continuity test",
                               inspection_type="testing",
                               planned_date=_quality_today() - datetime.timedelta(days=1),
                               inspected_date=_quality_today() - datetime.timedelta(days=1),
                               result="pass", status="in_progress", created_by=admin_user)


@pytest.fixture
def quality_inspection_on_hold(db, tenant_a, quality_project_a, admin_user):
    """``on_hold`` — hand-built: no verb writes this status, it is pure vocabulary. NOT locked
    (edit/delete open) and a legal ``qci_record`` source (on_hold → in_progress)."""
    return _quality_inspection(tenant_a, quality_project_a, title="Paused walkthrough",
                               status="on_hold",
                               planned_date=_quality_today() + datetime.timedelta(days=7),
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_conditional(db, tenant_a, quality_project_a, admin_user):
    """Result ``conditional``, recorded today−1, undecided — the punch-list state a conditional
    acceptance resolves from. ``conditional_count`` does NOT read this row (it counts
    ``usage_decision="accept_with_deviation"``)."""
    return _quality_inspection(tenant_a, quality_project_a, title="Panel surface inspection",
                               inspected_date=_quality_today() - datetime.timedelta(days=1),
                               result="conditional", status="in_progress",
                               findings="Two scratches within the repair limit.",
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_not_applicable(db, tenant_a, quality_project_a, admin_user):
    """Result ``not_applicable`` — the longest choice value (the fields.E009 width note) with a
    default row of its own."""
    return _quality_inspection(tenant_a, quality_project_a, title="Skipped dimensional check",
                               inspected_date=_quality_today() - datetime.timedelta(days=1),
                               result="not_applicable", status="in_progress",
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_cancelled(db, tenant_a, quality_project_a, admin_user):
    """``cancelled`` before execution — ``is_locked`` (terminal status) → edit/delete refuse."""
    return _quality_inspection(tenant_a, quality_project_a, title="Withdrawn demonstration",
                               inspection_type="demonstration", status="cancelled",
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_accepted(db, tenant_a, quality_project_a, quality_wbs_node_a,
                                quality_client_party_a, admin_user):
    """The shape ``qci_accept`` leaves: status ``passed``, result ``pass``,
    ``usage_decision="accept"``, accepted_by/at (now−1d), ``accepted_by_party`` set, an
    ``acceptance_note``. Anchored to ``quality_wbs_node_a`` — the acceptance board's latest
    inspection (state "accepted"/badge-green, pinned §3.2). Locked."""
    return _quality_inspection(
        tenant_a, quality_project_a, title="Final acceptance inspection",
        inspection_type="acceptance", wbs_node=quality_wbs_node_a,
        planned_date=_quality_today() - datetime.timedelta(days=2),
        inspected_date=_quality_today() - datetime.timedelta(days=2),
        result="pass", usage_decision="accept", status="passed",
        accepted_by=admin_user, accepted_by_party=quality_client_party_a,
        accepted_at=timezone.now() - datetime.timedelta(days=1),
        acceptance_note="Signed off against the plan's criteria.",
        created_by=admin_user)


@pytest.fixture
def quality_inspection_rejected(db, tenant_a, quality_project_a, admin_user):
    """The shape ``qci_reject`` leaves: result ``fail``, ``usage_decision="reject"``, status
    ``failed``, NO acceptor stamps (the reject verb writes only the decision + status). Locked."""
    return _quality_inspection(tenant_a, quality_project_a, title="Failed weld inspection",
                               inspection_type="testing",
                               planned_date=_quality_today() - datetime.timedelta(days=2),
                               inspected_date=_quality_today() - datetime.timedelta(days=2),
                               result="fail", usage_decision="reject", status="failed",
                               findings="Porosity beyond the acceptance limit.",
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_acceptance_pending(db, tenant_a, quality_project_a, admin_user):
    """THE acceptance-queue row: ``inspection_type="acceptance"`` with the result ALREADY
    recorded (``qci_accept``/``qci_reject`` refuse a pending-result row first) and the decision
    still ``pending``. The queue's default row (``acceptance_queue_count`` 1) and the decision
    verbs' happy path."""
    return _quality_inspection(tenant_a, quality_project_a,
                               title="Customer sign-off inspection",
                               inspection_type="acceptance",
                               planned_date=_quality_today() + datetime.timedelta(days=3),
                               inspected_date=_quality_today() - datetime.timedelta(days=1),
                               result="pass", status="in_progress",
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_overdue(db, tenant_a, quality_project_a, admin_user):
    """THE overdue row: ``planned_date=today−3`` while never executed (``inspected_date`` None)
    and still ``planned`` → ``is_overdue`` True. The ``?overdue=1`` lens row."""
    return _quality_inspection(tenant_a, quality_project_a, title="Slipped walkthrough",
                               inspection_type="walkthrough",
                               planned_date=_quality_today() - datetime.timedelta(days=3),
                               created_by=admin_user)


@pytest.fixture
def quality_inspection_b(db, tenant_b, quality_project_b, admin_b):
    """Tenant B's inspection — 404 as tenant A on detail/edit/delete and on all three verbs;
    absent from tenant A's register; the crafted-POST value for ``inspection`` on the defect
    form."""
    return _quality_inspection(tenant_b, quality_project_b, title="Globex inspection",
                               created_by=admin_b)


# ==================================================================================================
# QualityDefect — one per status and per severity, plus the overdue and bridge rows
# ==================================================================================================

@pytest.fixture
def quality_defect_open(db, tenant_a, quality_project_a, quality_wbs_node_a, admin_user):
    """THE live row: status ``open``, severity ``major``, identified today−2 (``age_days`` 2),
    anchored to ``quality_wbs_node_a`` (the acceptance board's ``open_defects`` 1). The happy
    path for ``qdf_resolve`` AND ``qdf_raise_issue``; edit/delete OPEN."""
    return _quality_defect(tenant_a, quality_project_a, title="Sensor housing dimension drift",
                           severity="major", wbs_node=quality_wbs_node_a,
                           identified_date=_quality_today() - datetime.timedelta(days=2),
                           created_by=admin_user)


@pytest.fixture
def quality_defect_in_progress(db, tenant_a, quality_project_a, admin_user):
    """Status ``in_progress``, severity ``critical`` — the other live status ``qdf_resolve``
    accepts (resolve is legal from open AND in_progress). Still ``is_open``."""
    return _quality_defect(tenant_a, quality_project_a, title="Firmware fails safety check",
                           severity="critical", status="in_progress", disposition="rework",
                           identified_date=_quality_today() - datetime.timedelta(days=5),
                           created_by=admin_user)


@pytest.fixture
def quality_defect_resolved(db, tenant_a, quality_project_a, admin_user):
    """THE resolved row: severity ``minor`` + root_cause/resolution_note + resolved_by/at
    (now−1d). The ONLY ``qdf_close`` happy path; ``qdf_resolve`` answers "already"; edit/delete
    REFUSE it (locked). Counts into ``defects_closed`` — a dispositioned defect plates the
    closure rate even before the close runs."""
    return _quality_defect(tenant_a, quality_project_a, title="Label printed on wrong stock",
                           severity="minor", status="resolved", disposition="repair",
                           root_cause="The print template defaulted to the old stock code.",
                           resolution_note="Template fixed and re-deployed; labels reprinted.",
                           resolved_by=admin_user,
                           resolved_at=timezone.now() - datetime.timedelta(days=1),
                           identified_date=_quality_today() - datetime.timedelta(days=10),
                           created_by=admin_user)


@pytest.fixture
def quality_defect_closed(db, tenant_a, quality_project_a, admin_user):
    """THE closed row: full resolver stamps (now−3d) + ``status="closed"`` +
    ``lessons_learned``. Locked; the improvement page's ONLY default lessons row
    (``lessons_count`` 1)."""
    return _quality_defect(tenant_a, quality_project_a, title="Packing list mismatch",
                           severity="minor", status="closed", disposition="accept_as_is",
                           root_cause="Two SKUs shared one barcode range.",
                           resolution_note="Barcode ranges re-issued.",
                           resolved_by=admin_user,
                           resolved_at=timezone.now() - datetime.timedelta(days=3),
                           lessons_learned="Audit barcode ranges whenever a new SKU family lands.",
                           identified_date=_quality_today() - datetime.timedelta(days=15),
                           created_by=admin_user)


@pytest.fixture
def quality_defect_cancelled(db, tenant_a, quality_project_a, admin_user):
    """``cancelled`` with severity ``observation`` — locks like the QRV/QCI siblings (the M1
    amendment: no edit, no delete, no resolve stamps, no issue bridge) and covers the fourth
    severity value."""
    return _quality_defect(tenant_a, quality_project_a, title="Cosmetic mark within tolerance",
                           severity="observation", status="cancelled",
                           created_by=admin_user)


@pytest.fixture
def quality_defect_overdue(db, tenant_a, quality_project_a, admin_user):
    """THE overdue row: ``due_date=today−2`` while status ``open`` (identified today−20 →
    ``age_days`` 20) → ``is_overdue`` True. The ``?overdue=1`` lens row."""
    return _quality_defect(tenant_a, quality_project_a, title="Documentation missing revision",
                           defect_category="documentation", severity="minor",
                           due_date=_quality_today() - datetime.timedelta(days=2),
                           identified_date=_quality_today() - datetime.timedelta(days=20),
                           created_by=admin_user)


@pytest.fixture
def quality_defect_bridged(db, tenant_a, quality_project_a, admin_user):
    """THE bridge row: ``project_issue`` SET — built through the 7.5 FACTORY ``_risk_issue``
    (same-module function call, NOT a 7.5 fixture row; the ``risk_baseline`` precedent). Still
    ``open`` (raising an issue does not disposition the defect), so ``qdf_raise_issue`` must
    answer "already raised issue ISS-…" (info) on it."""
    issue = _risk_issue(tenant_a, quality_project_a,
                        title="Sensor housing dimension drift escalated",
                        severity="high", created_by=admin_user)
    return _quality_defect(tenant_a, quality_project_a,
                           title="Housing drift needs RAID tracking",
                           severity="major", project_issue=issue,
                           identified_date=_quality_today() - datetime.timedelta(days=3),
                           created_by=admin_user)


@pytest.fixture
def quality_defect_b(db, tenant_b, quality_project_b, admin_b):
    """Tenant B's defect — 404 as tenant A on detail/edit/delete and on all three verbs; absent
    from tenant A's register."""
    return _quality_defect(tenant_b, quality_project_b, title="Globex cosmetic defect",
                           created_by=admin_b)


# ==================================================================================================
# 7.7 Scope & Requirements Management (subslug ``scope``) — OWNED BY PHASE 6 STEP 1
#
# Same rules as the 7.1–7.6 blocks above, prefixed ``scope_`` / ``_scope_`` so no lane can shadow
# another (test files: test_scope_models/_forms/_views/_security.py). See
# ``.claude/tasks/test-contract-projects-7.7.md`` for the test contract these fixtures serve — it
# pins the EXACT ``scope_matrix`` figures the matrix fixtures below produce (coverage 2/4 traced →
# 50.0% / creep 40000-60000-10000 over three month buckets → creep_max 60000.00, bars 66.7-100.0-
# 16.7): the rows are chosen so every figure is exact, and the four test writers assert those
# numbers instead of re-deriving them.
#
# * POST-FIX truth. This block pins the code AFTER the 7.7 fix pass: C1 added ScopeItem's
#   ``violated`` state (``is_locked`` = realized|retired|violated), C2 reordered the eight
#   admin-gated verbs to ``@login_required`` / ``@require_POST`` / ``@tenant_admin_required``
#   (member GET → 405, member POST → 403), I3 tightened ``sci_retire`` to ``is_open`` only and I2
#   settled ``elicitation_method`` at max_length 20.
# * Factories construct + ``.save()`` — ``TenantNumbered.save()`` is where ``REQ-/SCI-/SCR-/SVR-``
#   numbers are minted; ``bulk_create`` would ship empty numbers and is never used here.
# * Determinism (L16): every date derives from ``_scope_today()`` (``timezone.localdate()``) and
#   every datetime from ``timezone.now()`` — the SAME basis ``ScopeItem.is_review_overdue`` and the
#   matrix's overdue counter read. The creep fixtures stamp ``decided_at`` on the FIRST OF A MONTH
#   (see ``_scope_month_start``) so their three buckets stay three buckets whatever day the suite
#   runs on.
# * Spine reuse: projects come from the 7.1 FACTORY ``_projectinitiation_project`` and WBS work
#   packages from the 7.2 FACTORY ``_planning_task`` (function imports, NOT those lanes' fixtures —
#   lanes never depend on each other's fixture rows).
# * The matrix fixtures live on their OWN project (``scope_matrix_project_a``) so ``?project=``
#   isolates them: the lifecycle rows on ``scope_project_a`` cannot move the pinned figures, and a
#   pagination fill cannot either (the fills are inert — untraced, review-date-less, impact-free).
# * The admin client for 7.7 is the ROOT conftest's ``client_a`` (aliased ``scope_admin_client``)
#   and the member client the root ``member_client`` (aliased ``scope_member_client``) — exactly as
#   7.1–7.6, which define no clients of their own either; the aliases exist only so the 7.7 contract
#   can pin the names its four test modules import.
# * Tests NEVER touch ``management/commands/seed_projects.py`` (the demo seed) — every test builds
#   exactly the rows it asserts on from the factories below.
# ==================================================================================================

#: ``apps.core.crud.crud_list``'s default ``per_page`` — every 7.7 register uses the default, so a
#: pagination test needs ``SCOPE_PAGE_SIZE + 1`` (16) rows for a second page (same rationale as
#: ``COST_PAGE_SIZE`` / ``QUALITY_PAGE_SIZE`` above).
SCOPE_PAGE_SIZE = 15


def _scope_today():
    """Today on the SAME basis the 7.7 code uses (``ScopeItem.is_review_overdue`` and the matrix's
    ``overdue_items`` counter both read ``timezone.localdate()``)."""
    return timezone.localdate()


def _scope_month_start(months_back=0):
    """The FIRST day of the month ``months_back`` months before this one — the creep fixtures'
    bucket anchor.

    ``scope_matrix`` buckets approved/implemented changes by the month of ``decided_at``. Stamping
    ``decided_at=today - 70d`` would put two fixtures in the same bucket whenever the suite runs
    near a month boundary, collapsing the three-month board the pinned figures describe. Anchoring
    each fixture to a month START (this month, last month, the month before) makes the three periods
    deterministic on any run date while staying inside the L16 ``timezone`` basis.
    """
    year, month = _scope_today().year, _scope_today().month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return datetime.date(year, month, 1)


# ==================================================================================================
# Factories — construct + ``.save()`` so TenantNumbered mints REQ-/SCI-/SCR-/SVR-
# ==================================================================================================

def _scope_requirement(tenant, project, status="draft", **overrides):
    """A ``Requirement`` [REQ-] on ``project``.

    Defaults: ``status="draft"``, distinct title ("Requirement NN") + filled description,
    ``requirement_type="functional"``, ``priority="must"``, ``verification_method="test"``,
    ``elicitation_method="interview"``, ``version="1.0"`` — and **``wbs_node=None``** (UNTRACED by
    default: the coverage gap the matrix's ``untraced`` panel and ``?untraced=1`` lens exist to
    find). ``parent``/``owner``/``source_party`` are None and ``acceptance_criteria`` is blank.

    ``clean()`` runs before ``save()`` (the ``_quality_plan`` precedent) so a ``wbs_node`` or
    ``parent`` belonging to another project raises at build time instead of seeding bad data. The
    lifecycle/stamp columns (``rejection_reason``, ``approved_by``/``approved_at``,
    ``verified_by``/``verified_at``, ``verification_note``) are left untouched so a fixture in a
    given state can assert the verb's evidence columns are exactly what the verb wrote.
    """
    from apps.projects.models import Requirement
    seq = Requirement.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        parent=None,
        wbs_node=None,
        title=f"Requirement {seq:02d}",
        description="The capability the solution must provide.",
        requirement_type="functional",
        elicitation_method="interview",
        elicitation_note="",
        source_party=None,
        priority="must",
        acceptance_criteria="",
        version="1.0",
        verification_method="test",
        status=status,
        owner=None,
        requested_by=None,
        rejection_reason="",
        approved_by=None,
        approved_at=None,
        verified_by=None,
        verified_at=None,
        verification_note="",
        created_by=None,
    )
    fields.update(overrides)
    obj = Requirement(**fields)
    obj.clean()
    obj.save()
    return obj


def _scope_item(tenant, project, item_type="assumption", status="open", **overrides):
    """A ``ScopeItem`` [SCI-] on ``project`` — an assumption/open row unless overridden.

    Defaults: ``item_type="assumption"``, ``status="open"``, distinct statement ("Scope item NN"),
    ``impact_area="scope"``, ``identified_date=today``, ``review_date=None`` (never in the overdue
    lens), no ``requirement``, no ``owner`` and no verb-written ``outcome``/``closed_at``.

    ``clean()`` runs before ``save()`` — a cross-project ``requirement`` raises at build time. Pass
    ``item_type="in_scope"`` / ``"out_of_scope"`` for a boundary row, or a closed status
    (``realized``/``retired``/``violated``) for a locked row.
    """
    from apps.projects.models import ScopeItem
    seq = ScopeItem.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        requirement=None,
        item_type=item_type,
        statement=f"Scope item {seq:02d}",
        description="",
        impact_area="scope",
        status=status,
        owner=None,
        identified_date=_scope_today(),
        review_date=None,
        outcome="",
        closed_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = ScopeItem(**fields)
    obj.clean()
    obj.save()
    return obj


def _scope_change(tenant, project, status="draft", **overrides):
    """A ``ScopeChangeRequest`` [SCR-] on ``project`` — a zero-impact DRAFT by default.

    Defaults: ``status="draft"``, distinct title ("Scope change NN") + filled description,
    ``source="internal"``, ``priority="medium"``, ``schedule_impact_days=None``,
    ``cost_impact=Decimal("0")``, ``quality_impact="none"``, no ``requirement``/``risk``, no
    ``requested_by`` and no decision stamps. A zero-impact draft is deliberately NOT high-impact
    (``is_high_impact`` False) and NOT in the creep population.

    ``clean()`` runs before ``save()`` — a cross-project ``requirement``/``risk`` raises at build
    time. Pass ``decided_at=``/``implemented_at=`` when a fixture must land in a creep bucket (the
    view buckets on ``decided_at or created_at``).
    """
    from apps.projects.models import ScopeChangeRequest
    seq = ScopeChangeRequest.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        requirement=None,
        risk=None,
        title=f"Scope change {seq:02d}",
        description="The scope change the board is asked to weigh.",
        justification="",
        source="internal",
        priority="medium",
        schedule_impact_days=None,
        cost_impact=Decimal("0"),
        quality_impact="none",
        quality_note="",
        status=status,
        decision_note="",
        requested_by=None,
        decided_by=None,
        decided_at=None,
        implemented_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = ScopeChangeRequest(**fields)
    obj.clean()
    obj.save()
    return obj


def _scope_verification(tenant, project, acceptance_status="pending", **overrides):
    """A ``ScopeVerification`` [SVR-] on ``project`` — a pending, passing inspection by default.

    Defaults: ``acceptance_status="pending"`` (unlocked), ``method="inspection"``, ``result="pass"``,
    distinct deliverable ("Deliverable NN"), ``inspection_date=today``, no ``wbs_node``/
    ``requirement``/``inspected_by``, blank findings and no acceptance stamps.

    ``clean()`` runs before ``save()`` — a cross-project ``wbs_node``/``requirement`` raises at
    build time. ``is_locked`` is True for any non-pending status, so an accepted/rejected/waived
    fixture is frozen evidence.
    """
    from apps.projects.models import ScopeVerification
    seq = ScopeVerification.objects.filter(tenant=tenant).count() + 1
    fields = dict(
        tenant=tenant,
        project=project,
        wbs_node=None,
        requirement=None,
        deliverable=f"Deliverable {seq:02d}",
        method="inspection",
        result="pass",
        acceptance_status=acceptance_status,
        inspected_by=None,
        inspection_date=_scope_today(),
        findings="",
        decision_note="",
        accepted_by=None,
        accepted_at=None,
        created_by=None,
    )
    fields.update(overrides)
    obj = ScopeVerification(**fields)
    obj.clean()
    obj.save()
    return obj


# -- bulk fills (pagination / search / the registers) -----------------------------------------------
#
# Loops over the factories rather than bulk_create for the reason spelled out at the top of this
# file: bulk_create skips save(), and save() is where `number` is minted. Every fill row is INERT
# (untraced requirement, review-date-less open item, impact-free draft change) so a pagination test
# that pulls 16 rows does not move the pinned matrix figures.

def _scope_fill_requirements(tenant, project, count, **overrides):
    """``count`` UNTRACED draft requirements on ONE project — ``wbs_node=None`` (never in the
    coverage numerator), ``status="draft"``, distinct titles ("Backlog requirement 01" …).
    Returns the list; overrides land on EVERY row."""
    return [
        _scope_requirement(tenant, project, title=f"Backlog requirement {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _scope_fill_items(tenant, project, count, **overrides):
    """``count`` open assumption rows on ONE project — ``review_date=None`` (never in the overdue
    lens), distinct statements ("Backlog item 01" …). Returns the list; overrides land on every
    row (pass ``item_type=`` to fill a different slice)."""
    return [
        _scope_item(tenant, project, statement=f"Backlog item {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


def _scope_fill_changes(tenant, project, count, **overrides):
    """``count`` zero-impact DRAFT changes on ONE project — never high-impact and never in the creep
    population, distinct titles ("Backlog change 01" …). Returns the list; overrides land on every
    row."""
    return [
        _scope_change(tenant, project, title=f"Backlog change {i:02d}", **overrides)
        for i in range(1, count + 1)
    ]


# ==================================================================================================
# Core-spine records the 7.7 FKs point at
# ==================================================================================================

@pytest.fixture
def scope_party_a(db, tenant_a):
    """Tenant A organisation Party — the ``Requirement.source_party`` ("who asked for it") and the
    party the change/verification filter dropdowns offer. ``core.Party`` is the shared spine row 7.7
    reuses (7.1's ``ProjectStakeholder`` owns the RACI register; 7.7 declares no party table)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="organization", name="Field Ops Directorate")


@pytest.fixture
def scope_party_b(db, tenant_b):
    """Tenant B organisation Party — the crafted-POST value for ``source_party`` on
    ``RequirementForm`` (the narrowed queryset refuses it first; assert the FIELD error)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="organization", name="Globex Customers")


@pytest.fixture
def scope_project_a(db, tenant_a, admin_user):
    """Tenant A's ACTIVE host — every default 7.7 lifecycle row hangs off this one or the tenant-B
    twin. Window today−30 .. today+150, so a work package can span today and ``is_overdue`` is
    False."""
    return _projectinitiation_project(
        tenant_a, name="Scope host Alpha", code="SCP-01", status="active",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        start_date=_scope_today() - datetime.timedelta(days=30),
        end_date=_scope_today() + datetime.timedelta(days=150),
        created_by=admin_user)


@pytest.fixture
def scope_project_b(db, tenant_b, admin_b):
    """Tenant B's host — 404 as tenant A everywhere; absent from tenant A's registers; the
    crafted-POST value for ``project`` on all four ModelForms."""
    return _projectinitiation_project(
        tenant_b, name="Scope host Beta", code="SCB-01", status="active",
        charter_status="approved", created_by=admin_b)


@pytest.fixture
def scope_wbs_a(db, scope_project_a):
    """A tenant A work package on ``scope_project_a`` — the VALID ``wbs_node`` anchor (the
    same-project ``clean()`` branch) and a matrix column. Built through the 7.2 FACTORY (function
    import, not a 7.2 fixture)."""
    return _planning_task(scope_project_a.tenant, scope_project_a,
                          name="Scope traceability work package")


@pytest.fixture
def scope_wbs_a2(db, scope_project_a):
    """A SECOND tenant A work package on ``scope_project_a`` — so the matrix has ≥2 columns and the
    ``cells`` list shape is provable. ``sequence=1`` keeps its column order after ``scope_wbs_a``."""
    return _planning_task(scope_project_a.tenant, scope_project_a,
                          name="Scope second work package", sequence=1)


@pytest.fixture
def scope_wbs_b(db, scope_project_b):
    """Tenant B's work package — the crafted-POST value for ``wbs_node`` on the requirement and
    verification forms, and the cross-project node for the same-project ``clean()`` refusal
    tests."""
    return _planning_task(scope_project_b.tenant, scope_project_b,
                          name="Globex scope work package")


# ==================================================================================================
# Extra actors + clients (aliases over the ROOT conftest — reuse, never redefine)
# ==================================================================================================

@pytest.fixture
def scope_tenantless_user(db):
    """A logged-in user with ``tenant=None`` — the superuser shape. The four 7.7 create views guard
    this on their first branch and redirect to ``dashboard:home``; the registers and the matrix
    render EMPTY BY DESIGN (the matrix is 0-safe)."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="scope-drifter@example.com", username="scope_drifter",
        password="TestPass123!", tenant=None)


@pytest.fixture
def scope_tenantless_client(db, scope_tenantless_user):
    """Logged in, ``request.tenant is None``. Registers and the matrix render empty; creates
    redirect away."""
    client = Client()
    client.force_login(scope_tenantless_user)
    return client


@pytest.fixture
def scope_anon_client(db):
    """Unauthenticated — every 7.7 view is ``@login_required``, so each must redirect to login."""
    return Client()


@pytest.fixture
def scope_admin_client(db, client_a):
    """Tenant A admin logged in — alias of the root ``client_a`` (7.1–7.6 define no admin client of
    their own either; the alias exists so the 7.7 contract can pin the name). Runs the admin happy
    paths AND every IDOR-404 probe."""
    return client_a


@pytest.fixture
def scope_member_client(db, member_client):
    """Tenant A member logged in — alias of the root ``member_client``. On the eight admin-gated
    verbs a GET is 405 and a POST is 403. For tenant-B ADMIN requests use the root ``client_b``
    (no alias needed)."""
    return member_client


@pytest.fixture
def scope_csrf_client(db, admin_user):
    """Tenant A admin on a client that ENFORCES CSRF. A POST without a token must be 403."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    return client


# ==================================================================================================
# Requirement — one fixture per lifecycle state the five verbs branch on
# (all on scope_project_a except ``_b``; the verb/gate table is the test contract §3)
# ==================================================================================================

@pytest.fixture
def scope_requirement_draft(db, tenant_a, scope_project_a, admin_user):
    """``draft`` — nothing approved, nothing traced. The ``req_submit`` happy path (draft →
    submitted) and an unlocked row: ``req_edit``/``req_delete`` stay OPEN. Being untraced, it is
    also a ``?untraced=1``/``?pending=1`` lens row. ``req_approve``/``req_reject``/``req_verify``
    must REFUSE it (wrong source state); ``req_implement`` must REFUSE it (not approved)."""
    return _scope_requirement(tenant_a, scope_project_a,
                              title="Capture the delivery evidence pack",
                              created_by=admin_user)


@pytest.fixture
def scope_requirement_submitted(db, tenant_a, scope_project_a, admin_user):
    """``submitted`` — the requirement gate's queue row. The ONLY happy path for
    ``req_approve`` (→ approved) and ``req_reject`` (→ rejected, ``rejection_reason`` required).
    ``req_submit`` must REFUSE it (already submitted); ``req_verify`` must REFUSE it (not
    implemented)."""
    return _scope_requirement(tenant_a, scope_project_a, status="submitted",
                              title="Expose the delivery API to partners",
                              created_by=admin_user)


@pytest.fixture
def scope_requirement_approved(db, tenant_a, scope_project_a, scope_wbs_a, admin_user):
    """``approved`` + the approval evidence pair (``approved_by``=admin, ``approved_at`` now−1d) —
    the shape ``req_approve`` leaves. The ONLY ``req_implement`` happy path (approved →
    implemented) and a ``?unverified`` row in the matrix's ``unverified`` panel. Traced (anchored to
    ``scope_wbs_a``) so it is NOT in ``?untraced=1``. ``req_approve`` must refuse it (not
    submitted)."""
    return _scope_requirement(
        tenant_a, scope_project_a, status="approved", wbs_node=scope_wbs_a,
        title="Automate the nightly reconciliation",
        approved_by=admin_user,
        approved_at=timezone.now() - datetime.timedelta(days=1),
        created_by=admin_user)


@pytest.fixture
def scope_requirement_implemented(db, tenant_a, scope_project_a, admin_user):
    """``implemented`` — the shape ``req_implement`` leaves. The ONLY ``req_verify`` happy path
    (implemented → verified, admin-gated). ``req_implement`` must REFUSE it (already implemented)."""
    return _scope_requirement(
        tenant_a, scope_project_a, status="implemented",
        title="Publish the partner onboarding runbook",
        approved_by=admin_user,
        approved_at=timezone.now() - datetime.timedelta(days=3),
        created_by=admin_user)


@pytest.fixture
def scope_requirement_verified(db, tenant_a, scope_project_a, scope_wbs_a, admin_user):
    """``verified`` + the FULL evidence (approval pair AND ``verified_by``/``verified_at`` now−1d,
    ``verification_note`` set). ``is_locked`` → ``req_edit``/``req_delete`` REFUSE it; every verb
    refuses it. A ``?verified=1`` lens row and a coverage-``verified`` row."""
    return _scope_requirement(
        tenant_a, scope_project_a, status="verified", wbs_node=scope_wbs_a,
        title="Zero-touch invoice matching",
        approved_by=admin_user,
        approved_at=timezone.now() - datetime.timedelta(days=6),
        verified_by=admin_user,
        verified_at=timezone.now() - datetime.timedelta(days=1),
        verification_note="Confirmed against the accepted acceptance test pack.",
        created_by=admin_user)


@pytest.fixture
def scope_requirement_rejected(db, tenant_a, scope_project_a, admin_user):
    """``rejected`` with ``rejection_reason`` set and NO approval evidence — the shape ``req_reject``
    leaves. The SECOND legal ``req_submit`` source (a rejected row can be re-submitted, which clears
    the reason). NOT locked (``is_locked`` is only ``verified``), so edit/delete stay OPEN.
    ``req_approve`` must refuse it."""
    return _scope_requirement(
        tenant_a, scope_project_a, status="rejected",
        title="Retire the legacy scheduling UI",
        rejection_reason="The migration cost was not justified this quarter.",
        created_by=admin_user)


@pytest.fixture
def scope_requirement_b(db, tenant_b, scope_project_b, admin_b):
    """Tenant B's requirement — 404 as tenant A on detail/edit/delete and on all five verbs; absent
    from tenant A's registers and from the ``?project=`` matrix; the crafted-POST value for
    ``requirement`` on the change and verification forms."""
    return _scope_requirement(tenant_b, scope_project_b,
                              title="Globex requirement", created_by=admin_b)


# ==================================================================================================
# ScopeItem — one fixture per status the three verbs branch on
# (post-C1 the set includes ``violated``; ``is_locked`` = realized|retired|violated)
# ==================================================================================================

@pytest.fixture
def scope_item_open(db, tenant_a, scope_project_a, admin_user):
    """``open`` assumption — the ONLY ``sci_validate`` happy path (open → validated) and a legal
    ``sci_realize``/``sci_retire`` source. An ``?open=1`` lens row; edit/delete OPEN.
    ``review_date=None`` → never overdue."""
    return _scope_item(tenant_a, scope_project_a, item_type="assumption", status="open",
                       statement="The depot Wi-Fi refresh completes before go-live.",
                       identified_date=_scope_today() - datetime.timedelta(days=5),
                       created_by=admin_user)


@pytest.fixture
def scope_item_validated(db, tenant_a, scope_project_a, admin_user):
    """``validated`` assumption — the shape ``sci_validate`` leaves. A legal
    ``sci_realize``/``sci_retire`` source (``is_open`` True) and the SECOND ``?open=1`` row.
    ``sci_validate`` must REFUSE it (already validated, not ``open``)."""
    return _scope_item(tenant_a, scope_project_a, item_type="assumption", status="validated",
                       statement="The vendor supports the target API version.",
                       identified_date=_scope_today() - datetime.timedelta(days=8),
                       created_by=admin_user)


@pytest.fixture
def scope_item_realized(db, tenant_a, scope_project_a, admin_user):
    """``realized`` with ``outcome`` + ``closed_at`` (now−1d) — the shape ``sci_realize`` leaves.
    ``is_locked`` → edit/delete REFUSE it; ``sci_realize`` answers "only an open or validated row";
    **``sci_retire`` REFUSES it (the I3 fix — a realized row is NOT ``is_open``)**."""
    return _scope_item(tenant_a, scope_project_a, item_type="constraint", status="realized",
                       statement="No downtime during the peak trading window.",
                       outcome="The cutover ran inside the maintenance window.",
                       closed_at=timezone.now() - datetime.timedelta(days=1),
                       identified_date=_scope_today() - datetime.timedelta(days=20),
                       created_by=admin_user)


@pytest.fixture
def scope_item_violated(db, tenant_a, scope_project_a, admin_user):
    """``violated`` — the C1 state: an assumption that failed / a constraint that broke. Now that
    the choice exists the row is creatable, **IS locked** (edit/delete refuse it) and **is NOT
    ``is_open``** (so no lifecycle verb takes it). No verb writes this status — it is vocabulary a
    test hand-builds, like 7.5's ``on_hold``."""
    return _scope_item(tenant_a, scope_project_a, item_type="assumption", status="violated",
                       statement="The legacy data imports cleanly on the first attempt.",
                       outcome="Three months of records needed manual repair.",
                       closed_at=timezone.now() - datetime.timedelta(days=4),
                       identified_date=_scope_today() - datetime.timedelta(days=30),
                       created_by=admin_user)


@pytest.fixture
def scope_item_b(db, tenant_b, scope_project_b, admin_b):
    """Tenant B's scope item — 404 as tenant A on detail/edit/delete and on all three verbs; absent
    from tenant A's registers; the crafted-POST value for the ``requirement`` FK on
    ``ScopeItemForm``."""
    return _scope_item(tenant_b, scope_project_b, statement="Globex scope item",
                       created_by=admin_b)


# ==================================================================================================
# ScopeChangeRequest — one fixture per status the five verbs branch on, plus both sides of the
# high-impact threshold (HIGH_COST 50000 / HIGH_SCHEDULE_DAYS 10 / quality_impact "high")
# ==================================================================================================

@pytest.fixture
def scope_change_draft(db, tenant_a, scope_project_a, admin_user):
    """``draft``, zero impact — the ONLY ``scr_submit`` happy path (draft → submitted) and an
    unlocked row: ``scr_edit``/``scr_delete`` stay OPEN. The default ``_scope_change`` shape, so it
    is NOT high-impact and NOT in the creep population."""
    return _scope_change(tenant_a, scope_project_a, status="draft",
                         title="Add a second approval step to onboarding",
                         created_by=admin_user)


@pytest.fixture
def scope_change_submitted(db, tenant_a, scope_project_a, admin_user):
    """``submitted`` — the board's queue row. A happy path for ``scr_review`` (→ under_review) AND
    for ``scr_approve`` (→ approved) / ``scr_reject`` (→ rejected). ``scr_submit`` must REFUSE it."""
    return _scope_change(tenant_a, scope_project_a, status="submitted",
                         title="Extend the pilot to the northern depot",
                         justification="Operations wants the same tooling across sites.",
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_under_review(db, tenant_a, scope_project_a, admin_user):
    """``under_review`` — the shape ``scr_review`` leaves. A happy path for ``scr_approve`` /
    ``scr_reject`` but NOT for ``scr_review`` (already under review)."""
    return _scope_change(tenant_a, scope_project_a, status="under_review",
                         title="Re-sequence the integration milestone",
                         justification="The vendor's release slipped a fortnight.",
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_approved(db, tenant_a, scope_project_a, admin_user):
    """``approved`` + the decision pair (``decided_by``=admin, ``decided_at`` now−1d) — the shape
    ``scr_approve`` leaves. The ONLY ``scr_implement`` happy path (approved → implemented);
    ``scr_review``/``scr_approve``/``scr_reject`` must all REFUSE it."""
    return _scope_change(tenant_a, scope_project_a, status="approved",
                         title="Buy the additional integration licences",
                         cost_impact=Decimal("12000.00"), priority="high",
                         decided_by=admin_user,
                         decided_at=timezone.now() - datetime.timedelta(days=1),
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_rejected(db, tenant_a, scope_project_a, admin_user):
    """``rejected`` with ``decision_note`` stored + the decision pair — the shape ``scr_reject``
    leaves. NOT locked (``is_locked`` is only ``implemented``), so edit/delete stay OPEN. All five
    verbs refuse it."""
    return _scope_change(tenant_a, scope_project_a, status="rejected",
                         title="Replace the reporting engine mid-flight",
                         decision_note="Too late in the delivery cycle to absorb the risk.",
                         decided_by=admin_user,
                         decided_at=timezone.now() - datetime.timedelta(days=2),
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_implemented(db, tenant_a, scope_project_a, admin_user):
    """``implemented`` with the decision pair AND ``implemented_at`` (now−1d) — the shape
    ``scr_implement`` leaves. ``is_locked`` → edit/delete REFUSE it; every verb refuses it."""
    return _scope_change(tenant_a, scope_project_a, status="implemented",
                         title="Move the batch window to 02:00",
                         cost_impact=Decimal("5000.00"),
                         decided_by=admin_user,
                         decided_at=timezone.now() - datetime.timedelta(days=5),
                         implemented_at=timezone.now() - datetime.timedelta(days=1),
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_high_impact(db, tenant_a, scope_project_a, admin_user):
    """HIGH-IMPACT row: ``cost_impact=60000.00`` — **crosses ``HIGH_COST`` (50000)** so
    ``is_high_impact`` is True and the ``?high_impact=1`` lens includes it. The mid-band cost row
    the pinned creep figure's largest bucket (60000.00 → ``bar_pct`` 100.0) is built from on the
    matrix project; this fixture is the lifecycle-side copy for the register/lens tests."""
    return _scope_change(tenant_a, scope_project_a, status="submitted",
                         title="Rebuild the checkout integration",
                         cost_impact=Decimal("60000.00"), priority="critical",
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_sub_threshold(db, tenant_a, scope_project_a, admin_user):
    """THE BOUNDARY row: ``cost_impact=49999.99`` (one cent under ``HIGH_COST``),
    ``schedule_impact_days=9`` (one day under ``HIGH_SCHEDULE_DAYS``) and
    ``quality_impact="medium"`` — so ``is_high_impact`` is **False** and the ``?high_impact=1`` lens
    EXCLUDES it. The companion to ``scope_change_high_impact``: together they pin all three
    thresholds."""
    return _scope_change(tenant_a, scope_project_a, status="submitted",
                         title="Trim the reporting backlog",
                         cost_impact=Decimal("49999.99"), schedule_impact_days=9,
                         quality_impact="medium",
                         requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_change_b(db, tenant_b, scope_project_b, admin_b):
    """Tenant B's change — 404 as tenant A on detail/edit/delete and on all five verbs; absent from
    tenant A's registers and the ``?project=`` matrix; the crafted-POST value for the ``requirement``
    FK on ``ScopeChangeForm``."""
    return _scope_change(tenant_b, scope_project_b, title="Globex scope change",
                         created_by=admin_b)


# ==================================================================================================
# ScopeVerification — one fixture per acceptance decision the three verbs branch on
# ==================================================================================================

@pytest.fixture
def scope_verification_pending(db, tenant_a, scope_project_a, admin_user):
    """``pending`` with the result already recorded — the ONLY happy path for ``svr_accept``,
    ``svr_reject`` AND ``svr_waive`` (all three take a pending row). A ``?pending=1`` queue row and
    an unlocked row: edit/delete stay OPEN."""
    return _scope_verification(tenant_a, scope_project_a, acceptance_status="pending",
                               deliverable="Partner onboarding runbook",
                               method="review", result="conditional",
                               inspected_by=admin_user,
                               inspection_date=_scope_today() - datetime.timedelta(days=1),
                               findings="Two screenshots need re-capturing.",
                               created_by=admin_user)


@pytest.fixture
def scope_verification_accepted(db, tenant_a, scope_project_a, admin_user):
    """``accepted`` with ``accepted_by``/``accepted_at`` (now−1d) and a ``decision_note`` — the
    shape ``svr_accept`` leaves. ``is_locked`` → edit/delete REFUSE it; ``svr_accept`` answers the
    already-decided no-op; ``svr_reject``/``svr_waive`` refuse it too."""
    return _scope_verification(tenant_a, scope_project_a, acceptance_status="accepted",
                               deliverable="Reconciliation report pack",
                               result="pass",
                               accepted_by=admin_user,
                               accepted_at=timezone.now() - datetime.timedelta(days=1),
                               decision_note="Signed off against the acceptance criteria.",
                               created_by=admin_user)


@pytest.fixture
def scope_verification_rejected(db, tenant_a, scope_project_a, admin_user):
    """``rejected`` with the mandatory ``decision_note`` and the stamps — the shape ``svr_reject``
    leaves. Locked. ``svr_accept``/``svr_waive`` REFUSE it."""
    return _scope_verification(tenant_a, scope_project_a, acceptance_status="rejected",
                               deliverable="Legacy migration dry run",
                               result="fail",
                               accepted_by=admin_user,
                               accepted_at=timezone.now() - datetime.timedelta(days=2),
                               decision_note="Rejected: the exception report was incomplete.",
                               created_by=admin_user)


@pytest.fixture
def scope_verification_waived(db, tenant_a, scope_project_a, admin_user):
    """``waived`` with the stamps but NO decision note — the shape ``svr_waive`` leaves (waiving
    writes the decision and the evidence, not a narrative). Locked; ``is_accepted`` is True (waived
    counts as cleared) while the pending row is not."""
    return _scope_verification(tenant_a, scope_project_a, acceptance_status="waived",
                               deliverable="Interim data export tool",
                               result="conditional",
                               accepted_by=admin_user,
                               accepted_at=timezone.now() - datetime.timedelta(days=3),
                               created_by=admin_user)


@pytest.fixture
def scope_verification_b(db, tenant_b, scope_project_b, admin_b):
    """Tenant B's verification — 404 as tenant A on detail/edit/delete and on all three verbs;
    absent from tenant A's registers and the ``?project=`` matrix; the crafted-POST value for the
    ``requirement`` FK on ``ScopeVerificationForm``."""
    return _scope_verification(tenant_b, scope_project_b,
                               deliverable="Globex inspection", created_by=admin_b)


# ==================================================================================================
# THE MATRIX SET — a dedicated project so ``?project=`` isolates the pinned figures
# (test contract §4: coverage 2/4 tracked, creep 40000→60000→10000 across three month buckets)
#
# Every row here lives on ``scope_matrix_project_a`` and NOTHING else does, so the figures the test
# contract pins are auditable: the numbers move only if a test deliberately pulls one of these
# fixtures. The creep fixtures anchor ``decided_at`` to a month START (``_scope_month_start``) so
# the three buckets stay three buckets on any run date.
# ==================================================================================================

@pytest.fixture
def scope_matrix_project_a(db, tenant_a, admin_user):
    """The matrix board's dedicated tenant A project — matrix tests select ``?project=<this pk>``,
    so none of the lifecycle rows on ``scope_project_a`` can enter the figures."""
    return _projectinitiation_project(
        tenant_a, name="Scope matrix host", code="SMX-01", status="active",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=7),
        start_date=_scope_today() - datetime.timedelta(days=30),
        end_date=_scope_today() + datetime.timedelta(days=150),
        created_by=admin_user)


@pytest.fixture
def scope_wbs_m1(db, scope_matrix_project_a):
    """Matrix COLUMN 1 (``sequence=0``) — the work package ``scope_matrix_req_traced_approved``
    names as its deliverer."""
    return _planning_task(scope_matrix_project_a.tenant, scope_matrix_project_a,
                          name="Matrix work package one", sequence=0)


@pytest.fixture
def scope_wbs_m2(db, scope_matrix_project_a):
    """Matrix COLUMN 2 (``sequence=1``) — the work package the verified requirement names."""
    return _planning_task(scope_matrix_project_a.tenant, scope_matrix_project_a,
                          name="Matrix work package two", sequence=1)


@pytest.fixture
def scope_matrix_req_traced_approved(db, tenant_a, scope_matrix_project_a, scope_wbs_m1,
                                     admin_user):
    """Matrix row A: ``functional``/``must``, TRACED to ``scope_wbs_m1``, ``approved``. Cell
    ``[True, False]``; counts into ``traced`` and into ``unverified`` (an approved row that was
    never verified — coverage ``verified`` does NOT count it)."""
    return _scope_requirement(
        tenant_a, scope_matrix_project_a, status="approved", wbs_node=scope_wbs_m1,
        title="Matrix traced approved", requirement_type="functional", priority="must",
        approved_by=admin_user,
        approved_at=timezone.now() - datetime.timedelta(days=4),
        created_by=admin_user)


@pytest.fixture
def scope_matrix_req_untraced_draft(db, tenant_a, scope_matrix_project_a, admin_user):
    """Matrix row B: ``functional``/``should``, UNTRACED (no ``wbs_node``), ``draft``. Cell
    ``[False, False]``; counts into ``untraced`` and NOT into ``unverified`` (draft is not
    approved/implemented)."""
    return _scope_requirement(
        tenant_a, scope_matrix_project_a, status="draft",
        title="Matrix untraced draft", requirement_type="functional", priority="should",
        created_by=admin_user)


@pytest.fixture
def scope_matrix_req_traced_implemented_verified(db, tenant_a, scope_matrix_project_a, scope_wbs_m2,
                                                 admin_user):
    """Matrix row C: ``technical``/``must``, TRACED to ``scope_wbs_m2``, ``verified``. Cell
    ``[False, True]``; the ONLY row in coverage ``verified`` and the only row with a non-zero
    ``verification_count`` (2 — see the two verification fixtures) / ``verified_count`` (1)."""
    return _scope_requirement(
        tenant_a, scope_matrix_project_a, status="verified", wbs_node=scope_wbs_m2,
        title="Matrix traced verified", requirement_type="technical", priority="must",
        approved_by=admin_user,
        approved_at=timezone.now() - datetime.timedelta(days=9),
        verified_by=admin_user,
        verified_at=timezone.now() - datetime.timedelta(days=1),
        created_by=admin_user)


@pytest.fixture
def scope_matrix_req_untraced_approved(db, tenant_a, scope_matrix_project_a, admin_user):
    """Matrix row D: ``business``/``could``, UNTRACED, ``approved``. Cell ``[False, False]``;
    counts into ``untraced`` AND into ``unverified`` (the second approved row)."""
    return _scope_requirement(
        tenant_a, scope_matrix_project_a, status="approved",
        title="Matrix untraced approved", requirement_type="business", priority="could",
        approved_by=admin_user,
        approved_at=timezone.now() - datetime.timedelta(days=2),
        created_by=admin_user)


@pytest.fixture
def scope_matrix_ver_accepted(db, tenant_a, scope_matrix_project_a,
                              scope_matrix_req_traced_implemented_verified, admin_user):
    """The verified row's ACCEPTED inspection — contributes 1 to its ``verification_count`` and 1 to
    its ``verified_count`` (accepted is in the ``(accepted, waived)`` filter)."""
    return _scope_verification(
        tenant_a, scope_matrix_project_a, acceptance_status="accepted",
        requirement=scope_matrix_req_traced_implemented_verified,
        deliverable="Matrix accepted deliverable", result="pass",
        accepted_by=admin_user,
        accepted_at=timezone.now() - datetime.timedelta(days=1),
        created_by=admin_user)


@pytest.fixture
def scope_matrix_ver_pending(db, tenant_a, scope_matrix_project_a,
                             scope_matrix_req_traced_implemented_verified, admin_user):
    """The verified row's PENDING inspection — contributes 1 to its ``verification_count`` but 0 to
    ``verified_count`` ('pending' is not accepted/waived). The pair proves the two counters
    disagree."""
    return _scope_verification(
        tenant_a, scope_matrix_project_a, acceptance_status="pending",
        requirement=scope_matrix_req_traced_implemented_verified,
        deliverable="Matrix pending deliverable", result="pass",
        created_by=admin_user)


@pytest.fixture
def scope_matrix_ver_orphan(db, tenant_a, scope_matrix_project_a, admin_user):
    """An ACCEPTED inspection with NO requirement — the row that proves the per-requirement counts
    are keyed on ``requirement_id``: it adds nothing to any ``matrix_rows`` entry even though it is
    accepted."""
    return _scope_verification(
        tenant_a, scope_matrix_project_a, acceptance_status="accepted",
        deliverable="Matrix orphan deliverable", result="pass",
        accepted_by=admin_user,
        accepted_at=timezone.now() - datetime.timedelta(days=1),
        created_by=admin_user)


@pytest.fixture
def scope_matrix_change_m1(db, tenant_a, scope_matrix_project_a, admin_user):
    """Creep bucket P0 (two months back): ``approved``, ``cost_impact=40000.00``, 0 days, no
    quality impact — NOT high-impact. Contributes ``count`` 1 / ``cost_total`` 40000.00 to its
    month; its bar is ``40000 / 60000 × 100`` = 66.7."""
    return _scope_change(
        tenant_a, scope_matrix_project_a, status="approved",
        title="Matrix change M1", cost_impact=Decimal("40000.00"),
        decided_by=admin_user,
        decided_at=timezone.now().replace(
            year=_scope_month_start(2).year, month=_scope_month_start(2).month, day=1,
            hour=12, minute=0, second=0, microsecond=0),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_matrix_change_m2(db, tenant_a, scope_matrix_project_a, admin_user):
    """Creep bucket P1 (last month): ``implemented``, ``cost_impact=60000.00``, 0 days —
    HIGH-IMPACT (crosses ``HIGH_COST``). Contributes ``count`` 1 / ``cost_total`` 60000.00; it is
    the LARGEST bucket, so ``creep_max`` is 60000.00 and its bar is 100.0."""
    return _scope_change(
        tenant_a, scope_matrix_project_a, status="implemented",
        title="Matrix change M2", cost_impact=Decimal("60000.00"), priority="critical",
        decided_by=admin_user,
        decided_at=timezone.now().replace(
            year=_scope_month_start(1).year, month=_scope_month_start(1).month, day=1,
            hour=12, minute=0, second=0, microsecond=0),
        implemented_at=timezone.now() - datetime.timedelta(days=2),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_matrix_change_m3(db, tenant_a, scope_matrix_project_a, admin_user):
    """Creep bucket P2 (this month): ``approved``, ``cost_impact=10000.00``,
    ``schedule_impact_days=12`` — HIGH-IMPACT (crosses ``HIGH_SCHEDULE_DAYS``). Contributes
    ``count`` 1 / ``cost_total`` 10000.00 / ``schedule_days`` 12; its bar is
    ``10000 / 60000 × 100`` = 16.7."""
    return _scope_change(
        tenant_a, scope_matrix_project_a, status="approved",
        title="Matrix change M3", cost_impact=Decimal("10000.00"), schedule_impact_days=12,
        quality_impact="low",
        decided_by=admin_user,
        decided_at=timezone.now().replace(
            year=_scope_month_start(0).year, month=_scope_month_start(0).month, day=1,
            hour=12, minute=0, second=0, microsecond=0),
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_matrix_change_low(db, tenant_a, scope_matrix_project_a, admin_user):
    """The creep-panel CONTROL: a ``draft`` with ``cost_impact=999999.00`` and
    ``quality_impact="high"``. It is materially huge yet **NOT in the creep population** (the panel
    reads ``status``, not impact) and never moves ``creep_max`` — while the ``?high_impact=1`` lens
    on ``scr_list`` DOES include it (that lens reads the columns)."""
    return _scope_change(
        tenant_a, scope_matrix_project_a, status="draft",
        title="Matrix change low", cost_impact=Decimal("999999.00"),
        schedule_impact_days=99, quality_impact="high",
        requested_by=admin_user, created_by=admin_user)


@pytest.fixture
def scope_matrix_item_in_scope(db, tenant_a, scope_matrix_project_a, admin_user):
    """A boundary row: ``in_scope``/``open``. Counts into ``items``, ``boundaries`` and
    ``open_items``; NOT into ``overdue_items`` (no review date)."""
    return _scope_item(tenant_a, scope_matrix_project_a, item_type="in_scope", status="open",
                       statement="Matrix in-scope statement", created_by=admin_user)


@pytest.fixture
def scope_matrix_item_out_of_scope(db, tenant_a, scope_matrix_project_a, admin_user):
    """The second boundary row: ``out_of_scope``/``open``. Counts into ``items``, ``boundaries``
    and ``open_items``."""
    return _scope_item(tenant_a, scope_matrix_project_a, item_type="out_of_scope", status="open",
                       statement="Matrix out-of-scope statement", created_by=admin_user)


@pytest.fixture
def scope_matrix_item_constraint_validated_overdue(db, tenant_a, scope_matrix_project_a, admin_user):
    """The ONLY overdue row: ``constraint``/``validated`` with ``review_date=today−3`` →
    ``is_review_overdue`` True, so it is the 1 in ``overdue_items``; being ``validated`` it is
    ``is_open`` and counts in ``open_items``, and as a constraint it counts in ``constraints`` but
    NOT in ``boundaries``."""
    return _scope_item(tenant_a, scope_matrix_project_a, item_type="constraint",
                       status="validated",
                       statement="Matrix constraint statement",
                       review_date=_scope_today() - datetime.timedelta(days=3),
                       identified_date=_scope_today() - datetime.timedelta(days=10),
                       created_by=admin_user)


@pytest.fixture
def scope_matrix_item_assumption(db, tenant_a, scope_matrix_project_a, admin_user):
    """``assumption``/``open`` — counts into ``items``, ``assumptions`` and ``open_items``, the one
    row the ``assumptions`` counter reads."""
    return _scope_item(tenant_a, scope_matrix_project_a, item_type="assumption", status="open",
                       statement="Matrix assumption statement", created_by=admin_user)


@pytest.fixture
def scope_matrix_item_dependency_realized(db, tenant_a, scope_matrix_project_a, admin_user):
    """``dependency``/``realized`` — counts into ``items`` ONLY. Being non-``is_open`` it is excluded
    from ``open_items`` (this is the row that proves ``open_items`` is not a bare ``count()``), and
    a dependency is not a boundary, constraint or assumption."""
    return _scope_item(tenant_a, scope_matrix_project_a, item_type="dependency", status="realized",
                       statement="Matrix dependency statement",
                       outcome="The dependency was satisfied.",
                       closed_at=timezone.now() - datetime.timedelta(days=2),
                       identified_date=_scope_today() - datetime.timedelta(days=15),
                       created_by=admin_user)
