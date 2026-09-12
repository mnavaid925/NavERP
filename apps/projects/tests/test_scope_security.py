"""Projects 7.7 Scope & Requirements Management — SECURITY tests (Phase 6, step 5 of 6).

The FINAL test module and the access-control lane: who may touch what, from the URL side — the
shape a crafted request actually takes, not the shape the templates offer. It is the regression net
for exactly the surface the 7.7 review probed, so every item on that review's "Guarantees verified
CLEAN" list is a test here rather than a footnote.

* **Tenant isolation / IDOR.** Every ``<int:pk>`` route — all four ``*_detail`` and ``*_edit``
  (GET), the four deletes and all sixteen verbs (POST) — 404s on another workspace's row, and the
  ``scope_matrix`` ``?project=`` ignores a foreign pk. The ordering rule is pinned too: a tenant-B
  MEMBER on a tenant-A pk gets **404 (scope) before 403 (role)** — scope hides the row before role
  is ever consulted, so neither failure leaks the other's existence.
* **Method guards — BOTH actors.** GET on every POST-only route (4 deletes + 16 verbs) is a **405
  for an admin AND for a member**. The admin-only version of this test is precisely what let the
  review's **C2** ship in 7.4: ``@tenant_admin_required`` sat *outside* ``@require_POST``, so a
  member's GET answered **403** where the method should be refused outright for everyone (a
  privilege oracle). 7.7's fix moved the role check innermost; this test would have caught it, so
  it probes both actors and says so.
* **Role gating.** The eight admin-gated verbs (``req_approve``/``req_reject``/``req_verify``,
  ``scr_review``/``scr_approve``/``scr_reject``, ``svr_reject``/``svr_waive``) 403 a member having
  **written nothing** — status unchanged, no ``*_by``/``*_at`` stamped **and no ``AuditLog`` row**,
  because a refusal that still logs is a refusal that lies. The same gate then passes for an admin.
  The login-only verbs are run successfully by a member BY DESIGN: widening a gate by accident is
  as much a defect as narrowing one.
* **CSRF and anonymity.** A POST without a token → 403 (deletes included); an anonymous GET on any
  route → redirect to login; a tenant-less user's registers render empty and their creates bounce
  to the dashboard.
* **Mass assignment.** Every ``*_edit`` and ``*_create`` ignores smuggled lifecycle columns
  (``status``, the evidence stamps, ``number``, ``tenant``, ``created_by`` …) — a member cannot
  mint their own approval evidence through a form, and the number is still minted by the system.
* **Cross-tenant crafted FKs.** A POST carrying another workspace's ``project`` / ``wbs_node`` /
  ``requirement`` / ``risk`` / ``parent`` / ``source_party`` / ``owner`` / ``requested_by`` /
  ``inspected_by`` pk re-renders with a field error and creates no row.
* **Evidence immutability.** A locked row (verified / realized / retired / violated / implemented /
  decided) refuses both ``*_edit`` and ``*_delete`` through the view.
* **XSS.** A crafted ``<script>`` payload renders escaped in both the list and the detail.
* **Audit integrity.** Every verb's ``AuditLog.action`` fits the ``varchar(10)`` column and its
  ``changes`` payload records a real transition (``from != to`` — a self-transition audit row
  would be a lie).

Naming (mandatory): every test is ``test_scope_*``, every module-level helper ``_scope_*``.
Scope: permissions and isolation. Page content, context keys and state machines belong to the
other three lanes.
"""
import pytest
from django.test import Client
from django.urls import reverse

from apps.core.models import AuditLog
from apps.projects.models import (
    Requirement,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
)
from apps.projects.tests.conftest import (
    _scope_change,
    _scope_item,
    _scope_requirement,
    _scope_verification,
)

# ----------------------------------------------------------------------------------------------
# Route tables — the pk routes the probes walk, grouped by the verb's role gate (test contract §3)
# ----------------------------------------------------------------------------------------------

# GET routes: detail + edit, all four entities.
_PK_GET_ROUTES = [
    ("req_detail", "req"), ("req_edit", "req"),
    ("sci_detail", "sci"), ("sci_edit", "sci"),
    ("scr_detail", "scr"), ("scr_edit", "scr"),
    ("svr_detail", "svr"), ("svr_edit", "svr"),
]

# ---- the 16 lifecycle verbs, POST-only -------------------------------------------------------
#: Login-only verbs: a member runs them (the contract's deliberate widening).
_LOGIN_ONLY_VERBS = [
    ("req_submit", "req"), ("req_implement", "req"),
    ("sci_validate", "sci"), ("sci_realize", "sci"), ("sci_retire", "sci"),
    ("scr_submit", "scr"), ("scr_implement", "scr"),
    ("svr_accept", "svr"),
]
#: Admin-gated verbs: a member GETs 405 and POSTs 403.
_ADMIN_VERBS = [
    ("req_approve", "req"), ("req_reject", "req"), ("req_verify", "req"),
    ("scr_review", "scr"), ("scr_approve", "scr"), ("scr_reject", "scr"),
    ("svr_reject", "svr"), ("svr_waive", "svr"),
]
#: The four deletes — POST-only, login-only.
_DELETES = [("req_delete", "req"), ("sci_delete", "sci"),
            ("scr_delete", "scr"), ("svr_delete", "svr")]

_ALL_VERBS = _LOGIN_ONLY_VERBS + _ADMIN_VERBS
_PK_POST_ROUTES = _ALL_VERBS + _DELETES

_LIST_ROUTES = ["req_list", "sci_list", "scr_list", "svr_list", "scope_matrix"]
_CREATE_ROUTES = ["req_create", "sci_create", "scr_create", "svr_create"]

#: The eight admin-gated verbs' action literals must fit ``AuditLog.action`` (varchar(10)).
_ACTION_ALLOW_LIST = {"create", "update", "delete", "submit", "approve", "reject",
                      "implement", "verify", "realize", "retire",
                      "review", "accept", "waive"}

#: Every column the review found OFF the model forms (L20/L22). A smuggled POST value must change
#: nothing; the number is minted by the system, never accepted from the request.
_FORBIDDEN_FIELDS = {
    "status": "verified",
    "approved_by": "1", "approved_at": "2020-01-01T00:00:00Z",
    "verified_by": "1", "verified_at": "2020-01-01T00:00:00Z",
    "acceptance_status": "accepted",
    "decision_note": "smuggled decision",
    "rejection_reason": "smuggled rejection",
    "verification_note": "smuggled verification",
    "outcome": "smuggled outcome",
    "closed_at": "2020-01-01T00:00:00Z",
    "number": "REQ-99999",
    "tenant": "999999", "created_by": "1",
    "decided_by": "1", "decided_at": "2020-01-01T00:00:00Z",
    "implemented_at": "2020-01-01T00:00:00Z",
    "accepted_by": "1", "accepted_at": "2020-01-01T00:00:00Z",
}


# ----------------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------------

def _scope_member_b(tenant_b):
    """A NON-admin member of tenant B. Separates the two refusals: a tenant-B member on a tenant-A
    pk must 404 on scope, never 403 on role (the load-bearing ordering)."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="scope-member@globex.com", username="member_globex_scope",
        password="TestPass123!", tenant=tenant_b, is_tenant_admin=False)


def _scope_audit_count(model, pk):
    """How many ``AuditLog`` rows name ``model``'s row ``pk`` — the write-lies probe's counter."""
    from django.contrib.contenttypes.models import ContentType
    return AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(model), object_id=pk).count()


def _scope_requirement_payload(project, **extra):
    """A valid ``RequirementForm`` POST body (every required field present)."""
    payload = {
        "project": project.pk, "parent": "", "wbs_node": "",
        "title": "A crafted requirement", "description": "The capability to be delivered.",
        "requirement_type": "functional", "elicitation_method": "interview",
        "elicitation_note": "", "source_party": "", "priority": "must",
        "acceptance_criteria": "", "version": "1.0", "verification_method": "test",
        "owner": "", "requested_by": "",
    }
    payload.update(extra)
    return payload


def _scope_item_payload(project, **extra):
    """A valid ``ScopeItemForm`` POST body."""
    payload = {
        "project": project.pk, "requirement": "", "item_type": "assumption",
        "statement": "A crafted registry statement", "description": "",
        "impact_area": "scope", "owner": "",
        "identified_date": "2026-01-01", "review_date": "",
    }
    payload.update(extra)
    return payload


def _scope_change_payload(project, **extra):
    """A valid ``ScopeChangeForm`` POST body."""
    payload = {
        "project": project.pk, "requirement": "", "risk": "",
        "title": "A crafted change", "description": "The change to be weighed.",
        "justification": "", "source": "internal", "priority": "medium",
        "schedule_impact_days": "", "cost_impact": "0.00", "quality_impact": "none",
        "quality_note": "", "requested_by": "",
    }
    payload.update(extra)
    return payload


def _scope_verification_payload(project, **extra):
    """A valid ``ScopeVerificationForm`` POST body."""
    payload = {
        "project": project.pk, "wbs_node": "", "requirement": "",
        "deliverable": "A crafted deliverable", "method": "inspection", "result": "pass",
        "inspected_by": "", "inspection_date": "2026-01-01", "findings": "",
    }
    payload.update(extra)
    return payload


#: ``*_edit`` route -> (model, valid payload builder). Each fixture row is unlocked (draft / open /
#: draft / pending) so the edit view is actually reachable and the mass-assignment probe tests the
#: FORM, not the lock.
_EDIT_PROBES = {
    "req_edit": (Requirement, _scope_requirement_payload, "scope_requirement_draft"),
    "sci_edit": (ScopeItem, _scope_item_payload, "scope_item_open"),
    "scr_edit": (ScopeChangeRequest, _scope_change_payload, "scope_change_draft"),
    "svr_edit": (ScopeVerification, _scope_verification_payload, "scope_verification_pending"),
}

#: ``*_create`` route -> (model, valid payload builder). Row count proves nothing was written.
_CREATE_PROBES = {
    "req_create": (Requirement, _scope_requirement_payload),
    "sci_create": (ScopeItem, _scope_item_payload),
    "scr_create": (ScopeChangeRequest, _scope_change_payload),
    "svr_create": (ScopeVerification, _scope_verification_payload),
}

#: Locked rows and the model they belong to — the evidence-immutability probe (test contract §3).
_LOCKED_ROWS = [
    (Requirement, "scope_requirement_verified", "req_edit", "req_delete", "req_detail"),
    (ScopeItem, "scope_item_realized", "sci_edit", "sci_delete", "sci_detail"),
    (ScopeItem, "scope_item_violated", "sci_edit", "sci_delete", "sci_detail"),
    (ScopeChangeRequest, "scope_change_implemented", "scr_edit", "scr_delete", "scr_detail"),
    (ScopeVerification, "scope_verification_accepted", "svr_edit", "svr_delete", "svr_detail"),
]


# ==============================================================================================
# IDOR — tenant A admin on a tenant-B pk is 404 on every pk route
# ==============================================================================================

def test_scope_idor_get_404_on_every_pk_route(scope_admin_client, scope_requirement_b,
                                              scope_item_b, scope_change_b, scope_verification_b):
    """Admin A probes every tenant-B read route → 404 — the register never leaks a row."""
    rows = {"req": scope_requirement_b, "sci": scope_item_b,
            "scr": scope_change_b, "svr": scope_verification_b}
    for route, tag in _PK_GET_ROUTES:
        response = scope_admin_client.get(reverse(f"projects:{route}", args=[rows[tag].pk]))
        assert response.status_code == 404, (route, rows[tag].pk)


def test_scope_idor_post_404_on_every_verb_and_delete(scope_admin_client, scope_requirement_b,
                                                      scope_item_b, scope_change_b,
                                                      scope_verification_b):
    """All 16 verbs and all 4 deletes refuse a cross-tenant pk identically — a 404-on-POST, not the
    405 a GET would meet: the tenant filter is genuinely in the write path. Every probed row
    survives untouched."""
    rows = {"req": scope_requirement_b, "sci": scope_item_b,
            "scr": scope_change_b, "svr": scope_verification_b}
    payload = {"reason": "x", "note": "x", "decision_note": "x", "outcome": "x"}
    for route, tag in _PK_POST_ROUTES:
        response = scope_admin_client.post(reverse(f"projects:{route}", args=[rows[tag].pk]),
                                           payload)
        assert response.status_code == 404, (route, rows[tag].pk)
    assert Requirement.objects.filter(pk=scope_requirement_b.pk).exists()
    assert ScopeItem.objects.filter(pk=scope_item_b.pk).exists()
    assert ScopeChangeRequest.objects.filter(pk=scope_change_b.pk).exists()
    assert ScopeVerification.objects.filter(pk=scope_verification_b.pk).exists()


def test_scope_matrix_ignores_a_foreign_project_pk(scope_admin_client, scope_project_b,
                                                   scope_matrix_project_a,
                                                   scope_matrix_req_traced_approved):
    """``?project=<tenant-B pk>`` is not a leak: the view's tenant filter resolves nothing, so the
    page falls back to the tenant-wide view and renders no tenant-B data."""
    response = scope_admin_client.get(reverse("projects:scope_matrix"),
                                      {"project": scope_project_b.pk})
    assert response.status_code == 200
    assert response.context["project"] is None


def test_scope_tenant_b_member_on_tenant_a_pk_is_404_not_403(tenant_a, tenant_b,
                                                            scope_requirement_submitted):
    """A foreign-workspace MEMBER gets the same 404 an admin gets — scope hides the row before role
    is even consulted (the load-bearing ordering; no existence leak either way)."""
    client = Client()
    client.force_login(_scope_member_b(tenant_b))
    assert client.get(reverse("projects:req_detail",
                              args=[scope_requirement_submitted.pk])).status_code == 404


def test_scope_tenant_b_member_on_tenant_a_admin_verb_is_403_role_first(tenant_a, tenant_b,
                                                                        scope_requirement_submitted):
    """On an ADMIN-gated verb the role gate is the OUTERMOST check (post-C2), so a foreign member
    is refused on ROLE before the view body ever looks the row up.

    The distinction is deliberate and pinned by the contract §3: the 404-before-403 ordering rule
    holds on the non-gated routes (where the tenant filter is the only guard), but on the eight
    admin-gated verbs a member must see 403 (POST) / 405 (GET) *before* any lookup — the gate is
    about the actor, not the row. What matters for isolation is that a tenant-A member probing a
    tenant-B admin verb is ALSO 403 regardless of whether the pk exists, so the gate never confirms
    a foreign row's existence either way."""
    client = Client()
    client.force_login(_scope_member_b(tenant_b))
    response = client.post(reverse("projects:req_approve",
                                   args=[scope_requirement_submitted.pk]))
    assert response.status_code == 403


def test_scope_tenant_b_admin_cannot_read_or_delete_tenant_a_rows(client_b,
                                                                  scope_requirement_submitted):
    """A tenant-B ADMIN is still a foreigner: 404 on read and on delete."""
    pk = scope_requirement_submitted.pk
    assert client_b.get(reverse("projects:req_detail", args=[pk])).status_code == 404
    assert client_b.post(reverse("projects:req_delete", args=[pk])).status_code == 404


# ==============================================================================================
# Method guards — GET on every POST-only route is 405 for BOTH actors
# ==============================================================================================

def _scope_verb_rows(scope_requirement_draft, scope_requirement_submitted,
                     scope_requirement_approved, scope_requirement_implemented,
                     scope_item_open, scope_item_validated,
                     scope_change_draft, scope_change_submitted, scope_change_approved,
                     scope_verification_pending):
    """A row in the right source state for every POST-only route, keyed by url name. The method
    guard is answered before the state gate, so any row would do — but a valid one proves the 405
    is the method talking, not a state refusal misfiled as one."""
    return {
        "req_delete": scope_requirement_draft, "req_submit": scope_requirement_draft,
        "req_approve": scope_requirement_submitted, "req_reject": scope_requirement_submitted,
        "req_implement": scope_requirement_approved, "req_verify": scope_requirement_implemented,
        "sci_delete": scope_item_open, "sci_validate": scope_item_open,
        "sci_realize": scope_item_open, "sci_retire": scope_item_validated,
        "scr_delete": scope_change_draft, "scr_submit": scope_change_draft,
        "scr_review": scope_change_submitted, "scr_approve": scope_change_submitted,
        "scr_reject": scope_change_submitted, "scr_implement": scope_change_approved,
        "svr_delete": scope_verification_pending, "svr_accept": scope_verification_pending,
        "svr_reject": scope_verification_pending, "svr_waive": scope_verification_pending,
    }


def test_scope_get_on_every_post_only_route_is_405_for_an_admin(
        scope_admin_client, scope_requirement_draft, scope_requirement_submitted,
        scope_requirement_approved, scope_requirement_implemented, scope_item_open,
        scope_item_validated, scope_change_draft, scope_change_submitted, scope_change_approved,
        scope_verification_pending):
    """GET on all 20 POST-only routes → 405 as the ADMIN. Kept as its own assertion so the diff
    against the member test below is exactly the C2 regression net."""
    rows = _scope_verb_rows(scope_requirement_draft, scope_requirement_submitted,
                            scope_requirement_approved, scope_requirement_implemented,
                            scope_item_open, scope_item_validated, scope_change_draft,
                            scope_change_submitted, scope_change_approved,
                            scope_verification_pending)
    for route, row in rows.items():
        response = scope_admin_client.get(reverse(f"projects:{route}", args=[row.pk]))
        assert response.status_code == 405, route


def test_scope_get_on_every_post_only_route_is_405_for_a_member(
        scope_member_client, scope_requirement_draft, scope_requirement_submitted,
        scope_requirement_approved, scope_requirement_implemented, scope_item_open,
        scope_item_validated, scope_change_draft, scope_change_submitted, scope_change_approved,
        scope_verification_pending):
    """GET on all 20 POST-only routes → **405 as the MEMBER too**.

    This is the C2 regression net. 7.4 carries the identical decorator order — ``@tenant_admin_
    required`` OUTSIDE ``@require_POST`` — and its ``test_cost_security.py`` only GETs as the
    ADMIN, so its 405 assertion passed while the member path answered **403**: a wrong-method
    request leaking a role signal it had no business disclosing (a privilege oracle). 7.7's fix
    moved the role check innermost; the method guard must therefore fire for every actor before
    the role check is reached, and this test asserts exactly that. An admin-only version of this
    test is what let the bug ship.
    """
    rows = _scope_verb_rows(scope_requirement_draft, scope_requirement_submitted,
                            scope_requirement_approved, scope_requirement_implemented,
                            scope_item_open, scope_item_validated, scope_change_draft,
                            scope_change_submitted, scope_change_approved,
                            scope_verification_pending)
    for route, row in rows.items():
        response = scope_member_client.get(reverse(f"projects:{route}", args=[row.pk]))
        assert response.status_code == 405, route


def test_scope_unsupported_method_on_a_post_only_route_is_405(scope_admin_client,
                                                              scope_requirement_draft):
    """The method guard covers every non-POST verb, not just GET: a PUT/DELETE on a POST-only route
    is refused the same way. The registers and the matrix are plain GET views (``@login_required``
    only, no ``@require_POST``), so they are intentionally *not* asserted here — only the POST-only
    verb/delete surface carries the guard."""
    pk = scope_requirement_draft.pk
    assert scope_admin_client.put(reverse("projects:req_delete", args=[pk])).status_code == 405
    assert scope_admin_client.delete(reverse("projects:req_approve",
                                             args=[pk])).status_code == 405


# ==============================================================================================
# Role gating — the eight admin verbs 403 a member having written nothing
# ==============================================================================================

def test_scope_member_approve_requirement_403_writes_nothing_no_audit(scope_member_client,
                                                                      scope_requirement_submitted):
    """``req_approve`` as a member: 403, the row is byte-identical, and NO audit row was written —
    the smuggled evidence never landed and the refusee left no trace in the trail."""
    before = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    audits_before = _scope_audit_count(Requirement, before.pk)
    response = scope_member_client.post(reverse("projects:req_approve", args=[before.pk]))
    after = Requirement.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.status, after.approved_by, after.approved_at) == \
           (before.status, before.approved_by, before.approved_at)
    assert _scope_audit_count(Requirement, before.pk) == audits_before


def test_scope_member_reject_requirement_403_writes_nothing_no_audit(scope_member_client,
                                                                    scope_requirement_submitted):
    before = Requirement.objects.get(pk=scope_requirement_submitted.pk)
    audits_before = _scope_audit_count(Requirement, before.pk)
    response = scope_member_client.post(reverse("projects:req_reject", args=[before.pk]),
                                        {"reason": "member override"})
    after = Requirement.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.status, after.rejection_reason) == (before.status, before.rejection_reason)
    assert _scope_audit_count(Requirement, before.pk) == audits_before


def test_scope_member_verify_requirement_403_writes_nothing_no_audit(scope_member_client,
                                                                    scope_requirement_implemented):
    before = Requirement.objects.get(pk=scope_requirement_implemented.pk)
    audits_before = _scope_audit_count(Requirement, before.pk)
    response = scope_member_client.post(reverse("projects:req_verify", args=[before.pk]),
                                        {"note": "member verification"})
    after = Requirement.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.status, after.verified_by, after.verified_at, after.verification_note) == \
           (before.status, before.verified_by, before.verified_at, before.verification_note)
    assert _scope_audit_count(Requirement, before.pk) == audits_before


def test_scope_member_review_change_403_writes_nothing_no_audit(scope_member_client,
                                                                scope_change_submitted):
    before = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    audits_before = _scope_audit_count(ScopeChangeRequest, before.pk)
    response = scope_member_client.post(reverse("projects:scr_review", args=[before.pk]))
    after = ScopeChangeRequest.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert after.status == before.status
    assert _scope_audit_count(ScopeChangeRequest, before.pk) == audits_before


def test_scope_member_approve_change_403_writes_nothing_no_audit(scope_member_client,
                                                                 scope_change_submitted):
    before = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    audits_before = _scope_audit_count(ScopeChangeRequest, before.pk)
    response = scope_member_client.post(reverse("projects:scr_approve", args=[before.pk]))
    after = ScopeChangeRequest.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.status, after.decided_by, after.decided_at) == \
           (before.status, before.decided_by, before.decided_at)
    assert _scope_audit_count(ScopeChangeRequest, before.pk) == audits_before


def test_scope_member_reject_change_403_writes_nothing_no_audit(scope_member_client,
                                                                scope_change_submitted):
    before = ScopeChangeRequest.objects.get(pk=scope_change_submitted.pk)
    audits_before = _scope_audit_count(ScopeChangeRequest, before.pk)
    response = scope_member_client.post(reverse("projects:scr_reject", args=[before.pk]),
                                        {"decision_note": "member decision"})
    after = ScopeChangeRequest.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.status, after.decision_note) == (before.status, before.decision_note)
    assert _scope_audit_count(ScopeChangeRequest, before.pk) == audits_before


def test_scope_member_reject_verification_403_writes_nothing_no_audit(scope_member_client,
                                                                      scope_verification_pending):
    before = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    audits_before = _scope_audit_count(ScopeVerification, before.pk)
    response = scope_member_client.post(reverse("projects:svr_reject", args=[before.pk]),
                                        {"note": "member rejection"})
    after = ScopeVerification.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.acceptance_status, after.accepted_by, after.accepted_at) == \
           (before.acceptance_status, before.accepted_by, before.accepted_at)
    assert _scope_audit_count(ScopeVerification, before.pk) == audits_before


def test_scope_member_waive_verification_403_writes_nothing_no_audit(scope_member_client,
                                                                     scope_verification_pending):
    before = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    audits_before = _scope_audit_count(ScopeVerification, before.pk)
    response = scope_member_client.post(reverse("projects:svr_waive", args=[before.pk]))
    after = ScopeVerification.objects.get(pk=before.pk)
    assert response.status_code == 403
    assert (after.acceptance_status, after.accepted_by) == \
           (before.acceptance_status, before.accepted_by)
    assert _scope_audit_count(ScopeVerification, before.pk) == audits_before


def test_scope_admin_passes_every_admin_gate(scope_admin_client, scope_requirement_submitted,
                                             scope_requirement_implemented, scope_change_submitted,
                                             scope_change_under_review,
                                             scope_verification_pending):
    """The same gates that 403 a member let the admin through — the refusal above is about role,
    not a broken route. Each verb moves the row and redirects to its detail page."""
    cases = [
        (Requirement, scope_requirement_submitted, "req_approve", {}),
        (ScopeChangeRequest, scope_change_submitted, "scr_review", {}),
        (ScopeChangeRequest, scope_change_under_review, "scr_approve", {}),
        (ScopeVerification, scope_verification_pending, "svr_waive", {}),
    ]
    for model, row, route, payload in cases:
        response = scope_admin_client.post(reverse(f"projects:{route}", args=[row.pk]), payload)
        assert response.status_code == 302, route
        row.refresh_from_db()
    # The reject verbs need a written reason; each also passes for an admin.
    reason_cases = [
        (scope_requirement_submitted, "req_reject", {"reason": "Not this quarter."}),
        (scope_requirement_implemented, "req_verify", {"note": "Confirmed."}),
        (scope_verification_pending, "svr_reject", {"note": "Incomplete pack."}),
    ]
    for row, route, payload in reason_cases:
        response = scope_admin_client.post(reverse(f"projects:{route}", args=[row.pk]), payload)
        assert response.status_code == 302, route


def test_scope_member_runs_every_login_only_verb(scope_member_client, scope_requirement_draft,
                                                 scope_requirement_approved, scope_item_open,
                                                 scope_item_validated, scope_change_draft,
                                                 scope_change_approved,
                                                 scope_verification_pending):
    """The eight login-only verbs are member verbs BY DESIGN — widening a gate by accident would be
    as much a defect as narrowing one, so pin them explicitly."""
    cases = [
        (Requirement, scope_requirement_draft, "req_submit", {}, "submitted"),
        (Requirement, scope_requirement_approved, "req_implement", {}, "implemented"),
        (ScopeItem, scope_item_open, "sci_validate", {}, "validated"),
        (ScopeItem, scope_item_validated, "sci_realize", {"outcome": "It came to pass."}, "realized"),
        (ScopeChangeRequest, scope_change_draft, "scr_submit", {}, "submitted"),
        (ScopeChangeRequest, scope_change_approved, "scr_implement", {}, "implemented"),
    ]
    for model, row, route, payload, expected in cases:
        response = scope_member_client.post(reverse(f"projects:{route}", args=[row.pk]), payload)
        assert response.status_code == 302, route
        row.refresh_from_db()
        assert row.status == expected, route
    # ``sci_retire`` and ``svr_accept`` need their own rows (one verb per state).
    retire_row = scope_item_open
    response = scope_member_client.post(reverse("projects:sci_retire", args=[retire_row.pk]),
                                        {"outcome": "The boundary moved."})
    assert response.status_code == 302
    retire_row.refresh_from_db()
    assert retire_row.status == "retired"

    response = scope_member_client.post(reverse("projects:svr_accept",
                                                args=[scope_verification_pending.pk]))
    assert response.status_code == 302
    scope_verification_pending.refresh_from_db()
    assert scope_verification_pending.acceptance_status == "accepted"


def test_scope_member_reads_every_register_and_detail(scope_member_client, scope_requirement_draft,
                                                      scope_item_open, scope_change_draft,
                                                      scope_verification_pending):
    """Read access is login-wide inside the workspace — CRUD is not admin-gated."""
    for route in _LIST_ROUTES:
        assert scope_member_client.get(reverse(f"projects:{route}")).status_code == 200, route
    reads = [("req_detail", scope_requirement_draft.pk),
             ("sci_detail", scope_item_open.pk),
             ("scr_detail", scope_change_draft.pk),
             ("svr_detail", scope_verification_pending.pk)]
    for route, pk in reads:
        assert scope_member_client.get(reverse(f"projects:{route}", args=[pk])).status_code == 200


# ==============================================================================================
# CSRF — a POST without a token is 403, deletes included
# ==============================================================================================

def test_scope_post_without_csrf_token_403s_on_create(scope_csrf_client, scope_project_a):
    response = scope_csrf_client.post(reverse("projects:req_create"),
                                      _scope_requirement_payload(scope_project_a))
    assert response.status_code == 403
    assert not Requirement.objects.filter(title="A crafted requirement").exists()


@pytest.mark.parametrize("route,fixture_name", [
    ("req_delete", "scope_requirement_draft"),
    ("sci_delete", "scope_item_open"),
    ("scr_delete", "scope_change_draft"),
    ("svr_delete", "scope_verification_pending"),
])
def test_scope_post_without_csrf_token_403s_on_delete(route, fixture_name, scope_csrf_client,
                                                      request):
    """The deletes are POST-only and must reject a token-less POST too — the destructive routes are
    where a CSRF gap would hurt most."""
    row = request.getfixturevalue(fixture_name)
    response = scope_csrf_client.post(reverse(f"projects:{route}", args=[row.pk]))
    assert response.status_code == 403
    assert type(row).objects.filter(pk=row.pk).exists()


def test_scope_post_without_csrf_token_403s_on_a_verb(scope_csrf_client,
                                                      scope_requirement_submitted):
    response = scope_csrf_client.post(reverse("projects:req_approve",
                                              args=[scope_requirement_submitted.pk]))
    assert response.status_code == 403
    scope_requirement_submitted.refresh_from_db()
    assert scope_requirement_submitted.status == "submitted"


# ==============================================================================================
# Anonymous access — nothing at all without a login
# ==============================================================================================

@pytest.mark.parametrize("route", _LIST_ROUTES + _CREATE_ROUTES)
def test_scope_anonymous_get_redirects_to_login(route, scope_anon_client):
    response = scope_anon_client.get(reverse(f"projects:{route}"))
    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.parametrize("route,fixture_name", [
    ("req_detail", "scope_requirement_draft"),
    ("sci_detail", "scope_item_open"),
    ("scr_detail", "scope_change_draft"),
    ("svr_detail", "scope_verification_pending"),
])
def test_scope_anonymous_detail_and_verb_redirects_to_login(route, fixture_name,
                                                            scope_anon_client, request):
    row = request.getfixturevalue(fixture_name)
    assert scope_anon_client.get(reverse(f"projects:{route}", args=[row.pk])).status_code == 302


def test_scope_anonymous_posts_redirect_to_login(scope_anon_client, scope_requirement_draft,
                                                 scope_item_open, scope_change_draft,
                                                 scope_verification_pending):
    """Every POST-only route is ``@login_required`` at the outermost layer — anonymous POSTs 302 to
    login before any method/role/scope check."""
    rows = _scope_verb_rows(scope_requirement_draft, scope_requirement_draft,
                            scope_requirement_draft, scope_requirement_draft,
                            scope_item_open, scope_item_open, scope_change_draft,
                            scope_change_draft, scope_change_draft, scope_verification_pending)
    for route, row in rows.items():
        response = scope_anon_client.post(reverse(f"projects:{route}", args=[row.pk]))
        assert response.status_code == 302, route
        assert "login" in response.url


# ==============================================================================================
# Mass assignment — smuggled lifecycle columns are ignored; the number is system-minted
# ==============================================================================================

def _scope_assert_untouched(row, before_snapshot):
    """Re-read the row and assert every snapshotted lifecycle column is unchanged."""
    row.refresh_from_db()
    for field, value in before_snapshot.items():
        assert getattr(row, field) == value, field


def test_scope_req_edit_ignores_smuggled_lifecycle_fields(scope_admin_client,
                                                          scope_requirement_draft,
                                                          scope_project_a):
    """A member/edit POST cannot promote the row or mint approval evidence: every forbidden column
    is off the form, so the saved row keeps its real values and its system-minted number."""
    before = Requirement.objects.get(pk=scope_requirement_draft.pk)
    snapshot = {f: getattr(before, f) for f in
                ("status", "approved_by_id", "approved_at", "verified_by_id", "verified_at",
                 "rejection_reason", "number", "tenant_id", "created_by_id")}
    response = scope_admin_client.post(
        reverse("projects:req_edit", args=[before.pk]),
        _scope_requirement_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    _scope_assert_untouched(before, snapshot)


def test_scope_sci_edit_ignores_smuggled_lifecycle_fields(scope_admin_client, scope_item_open,
                                                          scope_project_a):
    before = ScopeItem.objects.get(pk=scope_item_open.pk)
    snapshot = {f: getattr(before, f) for f in
                ("status", "outcome", "closed_at", "number", "tenant_id", "created_by_id")}
    response = scope_admin_client.post(
        reverse("projects:sci_edit", args=[before.pk]),
        _scope_item_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    _scope_assert_untouched(before, snapshot)


def test_scope_scr_edit_ignores_smuggled_lifecycle_fields(scope_admin_client, scope_change_draft,
                                                          scope_project_a):
    before = ScopeChangeRequest.objects.get(pk=scope_change_draft.pk)
    snapshot = {f: getattr(before, f) for f in
                ("status", "decision_note", "decided_by_id", "decided_at", "implemented_at",
                 "number", "tenant_id", "created_by_id")}
    response = scope_admin_client.post(
        reverse("projects:scr_edit", args=[before.pk]),
        _scope_change_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    _scope_assert_untouched(before, snapshot)


def test_scope_svr_edit_ignores_smuggled_lifecycle_fields(scope_admin_client,
                                                          scope_verification_pending,
                                                          scope_project_a):
    before = ScopeVerification.objects.get(pk=scope_verification_pending.pk)
    snapshot = {f: getattr(before, f) for f in
                ("acceptance_status", "decision_note", "accepted_by_id", "accepted_at",
                 "number", "tenant_id", "created_by_id")}
    response = scope_admin_client.post(
        reverse("projects:svr_edit", args=[before.pk]),
        _scope_verification_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    _scope_assert_untouched(before, snapshot)


def test_scope_req_create_mints_its_own_number_and_ignores_smuggling(scope_admin_client,
                                                                    scope_project_a):
    """On CREATE the number is minted by the system; a smuggled ``number`` and the smuggled
    evidence columns are all ignored, and the row lands in ``draft`` with no approval stamp."""
    response = scope_admin_client.post(
        reverse("projects:req_create"),
        _scope_requirement_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    obj = Requirement.objects.get(title="A crafted requirement")
    assert obj.number.startswith("REQ-") and obj.number != "REQ-99999"
    assert obj.status == "draft"
    assert obj.approved_by_id is None and obj.approved_at is None
    assert obj.verified_by_id is None and obj.verified_at is None


def test_scope_sci_create_mints_its_own_number_and_ignores_smuggling(scope_admin_client,
                                                                    scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:sci_create"),
        _scope_item_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    obj = ScopeItem.objects.get(statement="A crafted registry statement")
    assert obj.number.startswith("SCI-")
    assert obj.status == "open" and obj.outcome == "" and obj.closed_at is None


def test_scope_scr_create_mints_its_own_number_and_ignores_smuggling(scope_admin_client,
                                                                     scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:scr_create"),
        _scope_change_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    obj = ScopeChangeRequest.objects.get(title="A crafted change")
    assert obj.number.startswith("SCR-")
    assert obj.status == "draft"
    assert obj.decided_by_id is None and obj.decided_at is None and obj.implemented_at is None


def test_scope_svr_create_mints_its_own_number_and_ignores_smuggling(scope_admin_client,
                                                                     scope_project_a):
    response = scope_admin_client.post(
        reverse("projects:svr_create"),
        _scope_verification_payload(scope_project_a, **_FORBIDDEN_FIELDS))
    assert response.status_code == 302
    obj = ScopeVerification.objects.get(deliverable="A crafted deliverable")
    assert obj.number.startswith("SVR-")
    assert obj.acceptance_status == "pending"
    assert obj.accepted_by_id is None and obj.accepted_at is None


# ==============================================================================================
# Cross-tenant crafted FKs — a foreign pk is a field error, never a created row
# ==============================================================================================

def test_scope_req_create_rejects_a_foreign_project_pk(scope_admin_client, scope_project_b):
    """The narrowed queryset refuses first: the response re-renders with a ``project`` field error
    and no row is created."""
    before = Requirement.objects.count()
    response = scope_admin_client.post(
        reverse("projects:req_create"),
        _scope_requirement_payload(scope_project_b))
    assert response.status_code == 200
    assert "project" in response.context["form"].errors
    assert Requirement.objects.count() == before


def test_scope_req_create_rejects_a_foreign_wbs_and_party(scope_admin_client, scope_project_a,
                                                          scope_wbs_b, scope_party_b):
    """A valid project with a tenant-B ``wbs_node`` / ``source_party`` re-renders with the field in
    error and creates nothing."""
    before = Requirement.objects.count()
    response = scope_admin_client.post(
        reverse("projects:req_create"),
        _scope_requirement_payload(scope_project_a, wbs_node=scope_wbs_b.pk,
                                   source_party=scope_party_b.pk))
    assert response.status_code == 200
    errors = response.context["form"].errors
    assert "wbs_node" in errors or "source_party" in errors
    assert Requirement.objects.count() == before


def test_scope_sci_create_rejects_a_foreign_requirement_pk(scope_admin_client, scope_project_a,
                                                           scope_requirement_b):
    before = ScopeItem.objects.count()
    response = scope_admin_client.post(
        reverse("projects:sci_create"),
        _scope_item_payload(scope_project_a, requirement=scope_requirement_b.pk))
    assert response.status_code == 200
    assert "requirement" in response.context["form"].errors
    assert ScopeItem.objects.count() == before


def test_scope_scr_create_rejects_a_foreign_requirement_pk(scope_admin_client, scope_project_a,
                                                           scope_requirement_b):
    before = ScopeChangeRequest.objects.count()
    response = scope_admin_client.post(
        reverse("projects:scr_create"),
        _scope_change_payload(scope_project_a, requirement=scope_requirement_b.pk))
    assert response.status_code == 200
    assert "requirement" in response.context["form"].errors
    assert ScopeChangeRequest.objects.count() == before


def test_scope_svr_create_rejects_a_foreign_requirement_and_wbs(scope_admin_client,
                                                                scope_project_a,
                                                                scope_requirement_b, scope_wbs_b):
    before = ScopeVerification.objects.count()
    response = scope_admin_client.post(
        reverse("projects:svr_create"),
        _scope_verification_payload(scope_project_a, requirement=scope_requirement_b.pk,
                                    wbs_node=scope_wbs_b.pk))
    assert response.status_code == 200
    errors = response.context["form"].errors
    assert "requirement" in errors or "wbs_node" in errors
    assert ScopeVerification.objects.count() == before


# ==============================================================================================
# Evidence immutability — a locked row refuses both edit and delete
# ==============================================================================================

@pytest.mark.parametrize("model,fixture_name,edit_route,delete_route,detail_route", _LOCKED_ROWS)
def test_scope_locked_row_refuses_edit(model, fixture_name, edit_route, delete_route,
                                       detail_route, scope_admin_client, request):
    """A locked row's ``*_edit`` POST is refused with a redirect to detail; the field the smuggled
    form tried to rewrite is unchanged. The lock is enforced in the VIEW, not just hidden by a
    missing button."""
    row = request.getfixturevalue(fixture_name)
    if model is Requirement:
        probe_field = "title"
    elif model is ScopeItem:
        probe_field = "statement"
    elif model is ScopeChangeRequest:
        probe_field = "title"
    else:
        probe_field = "deliverable"
    original = getattr(row, probe_field)
    response = scope_admin_client.post(
        reverse(f"projects:{edit_route}", args=[row.pk]),
        {probe_field: "rewritten by a locked-row edit"})
    assert response.status_code == 302
    row.refresh_from_db()
    assert getattr(row, probe_field) == original
    assert model.objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize("model,fixture_name,edit_route,delete_route,detail_route", _LOCKED_ROWS)
def test_scope_locked_row_refuses_delete(model, fixture_name, edit_route, delete_route,
                                         detail_route, scope_admin_client, request):
    """The destructive half: a locked row's ``*_delete`` POST does not delete it."""
    row = request.getfixturevalue(fixture_name)
    response = scope_admin_client.post(reverse(f"projects:{delete_route}", args=[row.pk]))
    assert response.status_code == 302
    assert model.objects.filter(pk=row.pk).exists()


# ==============================================================================================
# XSS — a crafted script payload renders escaped in list AND detail
# ==============================================================================================

_XSS = "<script>alert(1)</script>"


def test_scope_requirement_xss_is_escaped_in_list_and_detail(scope_admin_client, tenant_a,
                                                             scope_project_a):
    """A requirement whose title carries a script tag renders ``&lt;script&gt;`` — the raw tag must
    not survive into the HTML, and there is no ``|safe`` leaking it through."""
    obj = _scope_requirement(tenant_a, scope_project_a, title=_XSS,
                             description="payload probe")
    list_html = scope_admin_client.get(reverse("projects:req_list")).content.decode()
    detail_html = scope_admin_client.get(
        reverse("projects:req_detail", args=[obj.pk])).content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in list_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail_html
    assert _XSS not in list_html
    assert _XSS not in detail_html


def test_scope_scope_item_xss_is_escaped_in_list_and_detail(scope_admin_client, tenant_a,
                                                            scope_project_a):
    """The same probe for ``ScopeItem.statement`` — the registry's free-text column."""
    obj = _scope_item(tenant_a, scope_project_a, statement=_XSS, description="payload probe")
    list_html = scope_admin_client.get(reverse("projects:sci_list")).content.decode()
    detail_html = scope_admin_client.get(
        reverse("projects:sci_detail", args=[obj.pk])).content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in list_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail_html
    assert _XSS not in list_html
    assert _XSS not in detail_html


def test_scope_verification_deliverable_xss_is_escaped(scope_admin_client, tenant_a,
                                                       scope_project_a):
    """And for ``ScopeVerification.deliverable``."""
    obj = _scope_verification(tenant_a, scope_project_a, deliverable=_XSS)
    list_html = scope_admin_client.get(reverse("projects:svr_list")).content.decode()
    detail_html = scope_admin_client.get(
        reverse("projects:svr_detail", args=[obj.pk])).content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in list_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail_html
    assert _XSS not in list_html
    assert _XSS not in detail_html


def test_scope_mass_assignment_cannot_inject_inline_html(scope_admin_client, tenant_a,
                                                         scope_project_a):
    """A create POST whose body carries a script payload stores it as text and re-renders it
    escaped on the detail page — the payload is data, not markup."""
    response = scope_admin_client.post(
        reverse("projects:req_create"),
        _scope_requirement_payload(scope_project_a, title=_XSS))
    assert response.status_code == 302
    obj = Requirement.objects.get(title=_XSS)
    detail_html = scope_admin_client.get(
        reverse("projects:req_detail", args=[obj.pk])).content.decode()
    assert _XSS not in detail_html
    assert "&lt;script&gt;" in detail_html


# ==============================================================================================
# Tenant-less workspace — empty registers, bounced creates, a 0-safe matrix
# ==============================================================================================

def test_scope_tenant_less_registers_render_empty(scope_tenantless_client):
    """A ``tenant=None`` user sees every register render 200 EMPTY — no rows, no crash — and the
    matrix renders 200 on its 0-safe branch."""
    for route in ["req_list", "sci_list", "scr_list", "svr_list"]:
        response = scope_tenantless_client.get(reverse(f"projects:{route}"))
        assert response.status_code == 200, route
        assert not response.context["object_list"], route
    matrix = scope_tenantless_client.get(reverse("projects:scope_matrix"))
    assert matrix.status_code == 200
    assert matrix.context["matrix_rows"] == []


def test_scope_tenant_less_creates_bounce_to_dashboard(scope_tenantless_client):
    """Every create guards ``request.tenant is None`` on its first branch and redirects away."""
    for route in _CREATE_ROUTES:
        response = scope_tenantless_client.post(reverse(f"projects:{route}"), {})
        assert response.status_code == 302, route
        assert response.url == reverse("dashboard:home")


# ==============================================================================================
# Audit integrity — the action fits the column and the payload records a real transition
# ==============================================================================================

def _scope_latest_action(scope_admin_client, row, route, payload):
    """Run a verb as the admin and return the ``AuditLog`` row it wrote for ``row``."""
    from django.contrib.contenttypes.models import ContentType
    response = scope_admin_client.post(reverse(f"projects:{route}", args=[row.pk]), payload)
    assert response.status_code == 302, route
    return AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(row.__class__),
        object_id=row.pk).order_by("-at").first()


def test_scope_requirement_verb_audit_action_and_transition(scope_admin_client,
                                                            scope_requirement_submitted):
    """``req_approve``'s audit row: action fits ``varchar(10)`` and the payload carries
    ``{"verb","from","to"}`` with ``from != to`` (a self-transition would be a lie)."""
    row = scope_requirement_submitted
    log = _scope_latest_action(scope_admin_client, row, "req_approve", {})
    assert log is not None
    assert log.action in _ACTION_ALLOW_LIST and len(log.action) <= 10
    assert log.changes["verb"] == "approve"
    assert log.changes["from"] == "submitted"
    assert log.changes["to"] == "approved"
    assert log.changes["from"] != log.changes["to"]


def test_scope_scope_item_verb_audit_action_and_transition(scope_admin_client, scope_item_open):
    """``sci_validate``'s audit row: the store keeps the small action vocabulary (``submit``) while
    ``changes`` carries the real verb (``validate``)."""
    log = _scope_latest_action(scope_admin_client, scope_item_open, "sci_validate", {})
    assert log is not None
    assert log.action in _ACTION_ALLOW_LIST and len(log.action) <= 10
    assert log.changes["verb"] == "validate"
    assert log.changes["from"] == "open"
    assert log.changes["to"] == "validated"
    assert log.changes["from"] != log.changes["to"]


def test_scope_change_verb_audit_action_and_transition(scope_admin_client,
                                                       scope_change_submitted):
    log = _scope_latest_action(scope_admin_client, scope_change_submitted, "scr_approve", {})
    assert log is not None
    assert log.action == "approve" and len(log.action) <= 10
    assert log.changes["verb"] == "approve"
    assert log.changes["from"] == "submitted"
    assert log.changes["to"] == "approved"
    assert log.changes["from"] != log.changes["to"]


def test_scope_verification_verb_audit_action_and_transition(scope_admin_client,
                                                             scope_verification_pending):
    log = _scope_latest_action(scope_admin_client, scope_verification_pending, "svr_accept", {})
    assert log is not None
    assert log.action == "accept" and len(log.action) <= 10
    assert log.changes["verb"] == "accept"
    assert log.changes["from"] == "pending"
    assert log.changes["to"] == "accepted"
    assert log.changes["from"] != log.changes["to"]
