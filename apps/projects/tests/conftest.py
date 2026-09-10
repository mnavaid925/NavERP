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
