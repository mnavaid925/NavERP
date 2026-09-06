"""Procurement 6.17 Risk & Compliance Management - security, permissions and isolation.

The defensive lane of the 6.17 suite. The models / forms / views lanes next door cover what the
sub-module DOES; this file only ever asks what it REFUSES, and it asserts the refusal twice: the
status code, and then the row itself, unchanged. A 403 that still mutated is the bug, and a status
code on its own cannot see it.

Nine sections:

1. **Cross-tenant IDOR** - every ``<int:pk>`` route in 6.17 aimed at another workspace's row
   returns **404**, never 200 and never 500, and the foreign row survives byte-identical.
   ``ScreeningHit`` gets its own pass because it is the sharp one: **it has no tenant column at
   all**, so its only scope is ``screening__tenant`` and a view resolving a hit by pk alone leaks
   across workspaces.
2. **Register isolation** - no 6.17 register, board or export ever contains the other
   workspace's rows.
3. **Permission gates** - every ``@tenant_admin_required`` verb and every in-view admin check is
   refused for a non-admin member of the SAME workspace, with the row asserted unchanged after
   each refusal - paired with the L32 staff-reachability property, that the same user still
   reaches all five ``LIVE_LINKS["6.17"]`` destinations plus ``policy_mine`` with a **200 and
   content**, never a redirect.
4. **``attestation_sign`` is owner-only** - the module's sharpest rule, driven over HTTP: the
   owner signs; a peer, a tenant administrator, a workspace superuser and the tenant-less
   superuser are all refused, and after each refusal ``status`` / ``acknowledged_at`` /
   ``acknowledgement_note`` are all still exactly what they were. An administrator able to sign
   for somebody else would forge exactly the evidence this ledger exists to hold.
5. **POST-only verbs** - a GET on any mutating route is **405** and mutates nothing.
6. **CSRF** - with ``Client(enforce_csrf_checks=True)`` a POST with no token is rejected on at
   least one verb per entity, and the row is untouched.
7. **Junk and hostile input** (L11 / L35) - junk FK pks (``abc``, the Unicode superscript that
   ``isdigit()`` accepts and ``int()`` does not, a 20-digit over-range value, ``0``), junk enum
   tokens, junk pages, junk dates and a 5000-character search term all return **200, never
   500** - and a junk enum is IGNORED rather than matched, falling back to the unfiltered
   register instead of silently emptying it (L44). Non-finite posted decimals (``NaN`` /
   ``Infinity`` / ``1e400``) land as FIELD ERRORS, never a 500 (L35).
8. **XSS / escaping** - a stored ``<script>`` tag and an apostrophe in every free-text field that
   renders (``matched_name``, ``matched_on``, ``detail``, ``notes``, ``remarks``, ``source_ref``,
   the seal ``note``) reach the page escaped. The apostrophe matters because ``confirm()``
   handlers live on these pages (L42).
9. **CSV injection + the tenant-less user** - every ``audit_trail_export`` cell opening ``=``,
   ``+``, ``-`` or ``@`` is neutralised, and the audit-trail views REFUSE a tenant-less superuser
   rather than filtering ``tenant=None`` - ``core.AuditLog.tenant`` is nullable, so that filter
   would return every unattributed audit row in the installation.

House rules: every reference date derives from ``timezone.localdate()`` / ``timezone.now()`` and
never ``date.today()`` (L16); every URL goes through ``reverse("procurement:<name>")``; the
multi-route sweeps use ``Client(raise_request_exception=False)`` so one 500 collects into the
failure list instead of aborting the pass.

Every test is ``test_riskcompliance_*`` and every module-level helper ``_riskcompliance_*`` so the
sibling 6.17 lanes and any later sub-module appending nearby cannot shadow them (L41 S2 / L47).
"""
import csv
import datetime
import io
from decimal import Decimal

import pytest

from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, PartyRole
from apps.procurement.models import (
    AuditSeal,
    ComplianceScreening,
    FraudAlert,
    PolicyAttestation,
    ProcurementAlert,
    ProcurementPolicy,
    ScreeningHit,
    SupplierRiskSignal,
)

pytestmark = pytest.mark.django_db


# ==================================================================================== helpers
#
# Every name below is ``_riskcompliance_*``-prefixed. An unprefixed module-level helper rebinds
# whatever an earlier sub-module bound for the WHOLE file, silently, and for every call site
# written above it (L41 S2 / L47).

def _riskcompliance_today():
    """The date basis the 6.17 views themselves use. Never ``date.today()`` (L16)."""
    return timezone.localdate()


def _riskcompliance_days(count):
    return datetime.timedelta(days=count)


def _riskcompliance_html(response):
    return response.content.decode()


def _riskcompliance_messages(response):
    """Every message on the response's request, as a list of strings."""
    return [str(message) for message in get_messages(response.wsgi_request)]


def _riskcompliance_sweep_client(user):
    """A client that RETURNS the 500 instead of re-raising it.

    Used for every multi-route sweep so one broken route collects into the failure list with its
    url name attached, rather than aborting the pass and hiding the routes behind it.
    """
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client


def _riskcompliance_login(user):
    client = Client()
    client.force_login(user)
    return client


def _riskcompliance_new_user(tenant, email, username, is_admin=False):
    """A tenant user. ``email`` is the REQUIRED first argument - the manager is email-primary."""
    from apps.accounts.models import User

    return User.objects.create_user(email=email, username=username, password="TestPass123!",
                                    tenant=tenant, is_tenant_admin=is_admin)


def _riskcompliance_new_superuser(tenant=None, email="root@naverp.test", username="root_naverp"):
    """A superuser. ``tenant=None`` is the real ``admin`` shape; a tenant may be attached.

    Both matter here: the tenant-less one is what section 9 locks the audit-trail guard against,
    and the tenant-attached one is the sharper ``attestation_sign`` case - a superuser INSIDE the
    workspace, who still may not sign somebody else's row.
    """
    from apps.accounts.models import User

    user = User.objects.create_user(email=email, username=username, password="TestPass123!",
                                    tenant=tenant, is_tenant_admin=True)
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=["is_superuser", "is_staff"])
    return user


def _riskcompliance_role(party, role="supplier"):
    """Give a ``core.Party`` the role every 6.17 dropdown and board narrows on.

    ``_screenable_parties`` / ``_monitorable_parties`` / ``_suppliers`` all filter
    ``roles__role__in=("supplier", "vendor")``, so a bare Party is invisible to all of them.
    """
    PartyRole.objects.create(tenant=party.tenant, party=party, role=role, status="active")
    return party


def _riskcompliance_snapshot(obj, *fields):
    """``{field: value}`` re-read from the database - the "unchanged" baseline."""
    obj.refresh_from_db()
    return {name: getattr(obj, name) for name in fields}


def _riskcompliance_assert_unchanged(obj, before):
    """Re-read ``obj`` and assert every snapshotted column is still exactly what it was."""
    obj.refresh_from_db()
    for name, value in before.items():
        assert getattr(obj, name) == value, (
            f"{obj.__class__.__name__}.{name} changed on a refused request: "
            f"{value!r} -> {getattr(obj, name)!r}")


# -- rows the shared conftest does not mint ----------------------------------------------------

def _riskcompliance_hit_for(screening, matched_name="GLOBEX OFFSHORE TRADING", score=94):
    """One ``ScreeningHit``. **No tenant column exists** - the parent screening IS the scope."""
    return ScreeningHit.objects.create(
        screening=screening, matched_name=matched_name, matched_list="ofac_sdn",
        match_score=score, match_type="name", entry_reference="SDN-88120",
        program="CYBER2", country="Cyprus", remarks="Returned by the consolidated search.")


def _riskcompliance_signal_for(tenant, party, user=None, value="7.00", metric="ser_rating",
                               **overrides):
    observed = _riskcompliance_today() - _riskcompliance_days(2)
    fields = dict(
        tenant=tenant, party=party, provider="dnb", metric=metric, value=Decimal(value),
        observed_on=observed, next_refresh_on=observed + _riskcompliance_days(90),
        source_ref="Provider report page 2.", captured_by=user, notes="")
    fields.update(overrides)
    return SupplierRiskSignal.objects.create(**fields)


def _riskcompliance_alert_for(tenant, vendor, user=None, rule="new_vendor_rush", **overrides):
    fields = dict(
        tenant=tenant, vendor=vendor, rule=rule, severity="medium",
        document_date=_riskcompliance_today() - _riskcompliance_days(3),
        amount=Decimal("48000.00"),
        detail="First order is 48,000.00 against a 25,000.00 bar.",
        matched_on="", assigned_to=user)
    fields.update(overrides)
    return FraudAlert.objects.create(**fields)


def _riskcompliance_policy_for(tenant, title, user=None, published=True, requires_ack=True):
    policy = ProcurementPolicy.objects.create(
        tenant=tenant, title=title, policy_type="supplier_code_of_conduct",
        summary="What buyers and suppliers are held to.", body="Read it, then acknowledge it.",
        version_number="1.0", status="draft",
        effective_from=_riskcompliance_today() - _riskcompliance_days(7),
        requires_acknowledgment=requires_ack, owner=user, created_by=user)
    if published:
        # The same two-column stamp 6.19's own publish action makes; the model has no verb.
        policy.status = "published"
        policy.published_at = timezone.now()
        policy.save(update_fields=["status", "published_at", "updated_at"])
    return policy


def _riskcompliance_attestation_for(policy, user, due_in_days=10):
    return PolicyAttestation.objects.create(
        tenant=policy.tenant, policy=policy, user=user,
        due_on=_riskcompliance_today() + _riskcompliance_days(due_in_days))


def _riskcompliance_audit_row(tenant, user, target="Screening SCR-00001", action="update",
                              changes=None):
    """One ``core.AuditLog`` row that the 6.17 audit register actually shows.

    ``procurement_activity_qs`` narrows to ``content_type__app_label="procurement"`` (plus a
    handful of scm models), so an audit row with NO content type never reaches the page. The
    content type is stamped here for exactly that reason.
    """
    return AuditLog.objects.create(
        tenant=tenant, user=user, action=action, target=target,
        content_type=ContentType.objects.get_for_model(ComplianceScreening),
        object_id=1, changes=changes if changes is not None else {"name": ["a", "b"]})


def _riskcompliance_seal_for(tenant, user, note="Month-end seal."):
    _riskcompliance_audit_row(tenant, user, target="Screening for the seal range")
    seal, _message = AuditSeal.seal_now(tenant, user, note=note)
    assert seal is not None, "seal_now() refused a non-empty range - precondition broken"
    return seal


# -- POST payload builders ---------------------------------------------------------------------

def _riskcompliance_screening_payload(party_pk, **overrides):
    payload = {
        "party": str(party_pk), "list_source": "csl_consolidated", "checkpoint": "onboarding",
        "method": "manual_lookup", "screened_on": _riskcompliance_today().isoformat(),
        "list_as_of": (_riskcompliance_today() - _riskcompliance_days(1)).isoformat(),
        "reference": "CSL-CRAFTED-1", "result": "clear", "match_threshold": "85",
        "threshold_rationale": "ITA CSL default fuzzy threshold.",
        "next_rescreen_on": "", "evidence": "", "notes": ""}
    payload.update(overrides)
    return payload


def _riskcompliance_signal_payload(party_pk, **overrides):
    payload = {
        "party": str(party_pk), "provider": "dnb", "metric": "ser_rating",
        "observed_on": _riskcompliance_today().isoformat(), "value": "5.00",
        "next_refresh_on": "", "source_ref": "Report page 2.", "evidence": "", "notes": ""}
    payload.update(overrides)
    return payload


def _riskcompliance_alert_payload(vendor_pk, **overrides):
    payload = {
        "rule": "new_vendor_rush", "severity": "medium",
        "document_date": _riskcompliance_today().isoformat(), "amount": "48000.00",
        "detail": "Crafted alert.", "matched_on": "", "assigned_to": "",
        "vendor": str(vendor_pk), "related_party": "", "requisition": "", "purchase_order": "",
        "supplier_invoice": "", "approval": "", "screening": ""}
    payload.update(overrides)
    return payload


def _riskcompliance_hit_payload(**overrides):
    payload = {
        "matched_name": "NORTHWIND COMPONENTS LLC", "matched_list": "ofac_sdn",
        "match_score": "90", "match_type": "name", "entry_reference": "SDN-1",
        "program": "UKRAINE-EO13662", "country": "Cyprus", "remarks": "Crafted hit."}
    payload.update(overrides)
    return payload


def _riskcompliance_dispose_payload(**overrides):
    payload = {"disposition": "false_positive",
               "disposition_note": "Different registered address and tax id."}
    payload.update(overrides)
    return payload


# -- route sweeps ------------------------------------------------------------------------------

def _riskcompliance_sweep(client, cases, expected=404):
    """Drive every ``(url_name, args, method, data)`` case and collect the mismatches.

    Returns ``[(url_name, status_code), ...]`` for every case whose status was not ``expected``,
    so one failure names every offending route at once instead of one per re-run.
    """
    failures = []
    for url_name, args, method, data in cases:
        url = reverse(f"procurement:{url_name}", args=args)
        response = (client.post(url, data or {}) if method == "post" else client.get(url))
        if response.status_code != expected:
            failures.append((url_name, response.status_code))
    return failures


# ================================================================= 1. cross-tenant IDOR
#
# Logged in as tenant A's administrator, every ``<int:pk>`` route in 6.17 pointed at a tenant-B
# row must return 404 - never 200 (a read across the boundary) and never 500 (a guard that
# crashed instead of refusing). The sweeps use ``raise_request_exception=False`` so a 500 is
# collected with its url name rather than aborting the pass.

def test_riskcompliance_foreign_screening_pk_is_404_on_every_route(
        admin_user, tenant_b, riskcompliance_screening_b):
    """All nine screening routes refuse tenant B's screening, and it survives untouched.

    ``escalate`` and ``block`` read their note BEFORE resolving the pk, so a real note rides
    along - otherwise the refusal under test would be the missing-note one and the tenant guard
    would never be reached.
    """
    client = _riskcompliance_sweep_client(admin_user)
    pk = riskcompliance_screening_b.pk
    before = _riskcompliance_snapshot(riskcompliance_screening_b, "status", "result",
                                      "decided_at", "decision_note")

    failures = _riskcompliance_sweep(client, [
        ("screening_detail", [pk], "get", None),
        ("screening_edit", [pk], "get", None),
        ("screening_edit", [pk], "post", _riskcompliance_screening_payload(
            riskcompliance_screening_b.party_id)),
        ("screening_delete", [pk], "post", {}),
        ("screening_clear", [pk], "post", {"note": "Nothing returned above the threshold."}),
        ("screening_escalate", [pk], "post", {"note": "Referred for a compliance decision."}),
        ("screening_block", [pk], "post", {"note": "Confirmed SDN match."}),
        ("screeninghit_create", [pk], "get", None),
        ("screeninghit_create", [pk], "post", _riskcompliance_hit_payload()),
    ])

    assert failures == [], f"cross-tenant screening routes did not 404: {failures}"
    assert ComplianceScreening.objects.filter(pk=pk, tenant=tenant_b).exists()
    _riskcompliance_assert_unchanged(riskcompliance_screening_b, before)
    assert riskcompliance_screening_b.hits.count() == 0


def test_riskcompliance_foreign_screeninghit_pk_is_404_on_every_route(
        admin_user, riskcompliance_screening_b):
    """**The tenant-less entity.** ``ScreeningHit`` carries no ``tenant`` column at all.

    Its only scope is ``screening__tenant``, so a view that resolves a hit by pk alone - or that
    joins on the hit's own (non-existent) tenant - leaks across workspaces silently. All four
    routes must 404 for a tenant-B hit, and the hit must survive the delete and the dispose.
    """
    client = _riskcompliance_sweep_client(admin_user)
    hit_b = _riskcompliance_hit_for(riskcompliance_screening_b)
    before = _riskcompliance_snapshot(hit_b, "disposition", "matched_name", "disposition_note",
                                      "disposed_at")

    failures = _riskcompliance_sweep(client, [
        ("screeninghit_detail", [hit_b.pk], "get", None),
        ("screeninghit_edit", [hit_b.pk], "get", None),
        ("screeninghit_edit", [hit_b.pk], "post", _riskcompliance_hit_payload()),
        ("screeninghit_delete", [hit_b.pk], "post", {}),
        ("screeninghit_dispose", [hit_b.pk], "post", _riskcompliance_dispose_payload()),
    ])

    assert failures == [], f"a tenant-less ScreeningHit leaked across workspaces: {failures}"
    assert ScreeningHit.objects.filter(pk=hit_b.pk).exists()
    _riskcompliance_assert_unchanged(hit_b, before)


def test_riskcompliance_foreign_risksignal_pk_is_404_on_every_route(
        admin_user, tenant_b, riskcompliance_party_b, admin_b):
    """Detail, edit, delete and the review verb all refuse tenant B's observation."""
    client = _riskcompliance_sweep_client(admin_user)
    signal_b = _riskcompliance_signal_for(tenant_b, riskcompliance_party_b, admin_b)
    before = _riskcompliance_snapshot(signal_b, "review_status", "value", "review_note",
                                      "reviewed_at")

    failures = _riskcompliance_sweep(client, [
        ("risksignal_detail", [signal_b.pk], "get", None),
        ("risksignal_edit", [signal_b.pk], "get", None),
        ("risksignal_edit", [signal_b.pk], "post",
         _riskcompliance_signal_payload(riskcompliance_party_b.pk)),
        ("risksignal_delete", [signal_b.pk], "post", {}),
        ("risksignal_review", [signal_b.pk], "post",
         {"action": "reviewed", "review_note": "Looked at."}),
    ])

    assert failures == [], f"cross-tenant risk-signal routes did not 404: {failures}"
    assert SupplierRiskSignal.objects.filter(pk=signal_b.pk, tenant=tenant_b).exists()
    _riskcompliance_assert_unchanged(signal_b, before)


def test_riskcompliance_foreign_fraudalert_pk_is_404_on_every_route(
        admin_user, tenant_b, riskcompliance_party_b, admin_b):
    """Detail, edit, delete and the disposition verb all refuse tenant B's accusation."""
    client = _riskcompliance_sweep_client(admin_user)
    alert_b = _riskcompliance_alert_for(tenant_b, riskcompliance_party_b, admin_b)
    before = _riskcompliance_snapshot(alert_b, "status", "severity", "resolution_note",
                                      "resolved_at")

    failures = _riskcompliance_sweep(client, [
        ("fraudalert_detail", [alert_b.pk], "get", None),
        ("fraudalert_edit", [alert_b.pk], "get", None),
        ("fraudalert_edit", [alert_b.pk], "post",
         _riskcompliance_alert_payload(riskcompliance_party_b.pk)),
        ("fraudalert_delete", [alert_b.pk], "post", {}),
        ("fraudalert_disposition", [alert_b.pk], "post",
         {"action": "substantiate", "resolution_note": "Confirmed with HR."}),
    ])

    assert failures == [], f"cross-tenant fraud-alert routes did not 404: {failures}"
    assert FraudAlert.objects.filter(pk=alert_b.pk, tenant=tenant_b).exists()
    _riskcompliance_assert_unchanged(alert_b, before)


def test_riskcompliance_foreign_attestation_pk_is_404_on_every_route(
        admin_user, tenant_b, admin_b):
    """Detail, edit, delete, **sign** and exempt all refuse tenant B's sign-off row.

    ``attestation_sign`` matters most here: a signature applied across a workspace boundary would
    be a forged one, attributed to somebody who never saw the policy.
    """
    client = _riskcompliance_sweep_client(admin_user)
    policy_b = _riskcompliance_policy_for(tenant_b, "Globex Code of Conduct", admin_b)
    attestation_b = _riskcompliance_attestation_for(policy_b, admin_b)
    before = _riskcompliance_snapshot(attestation_b, "status", "acknowledged_at",
                                      "acknowledgement_note", "exempt_reason", "due_on")

    failures = _riskcompliance_sweep(client, [
        ("policyattestation_detail", [attestation_b.pk], "get", None),
        ("policyattestation_edit", [attestation_b.pk], "get", None),
        ("policyattestation_edit", [attestation_b.pk], "post",
         {"policy": str(policy_b.pk), "user": str(admin_b.pk),
          "due_on": _riskcompliance_today().isoformat()}),
        ("policyattestation_delete", [attestation_b.pk], "post", {}),
        ("attestation_sign", [attestation_b.pk], "post", {"note": "Read in full."}),
        ("attestation_exempt", [attestation_b.pk], "post", {"reason": "On long-term leave."}),
    ])

    assert failures == [], f"cross-tenant attestation routes did not 404: {failures}"
    assert PolicyAttestation.objects.filter(pk=attestation_b.pk, tenant=tenant_b).exists()
    _riskcompliance_assert_unchanged(attestation_b, before)


def test_riskcompliance_foreign_policy_pk_is_404_on_detail_and_raise(
        admin_user, tenant_a, tenant_b, admin_b):
    """6.17's read of a 6.19 policy, and its one write verb, both stop at the boundary.

    ``policy_raise_attestations`` is the dangerous one: it MINTS rows. Raising a roster against
    another workspace's policy would put tenant A's staff on the hook for a rule they have never
    seen - so the attestation count in BOTH workspaces is asserted afterwards.
    """
    client = _riskcompliance_sweep_client(admin_user)
    policy_b = _riskcompliance_policy_for(tenant_b, "Globex Code of Conduct", admin_b)

    failures = _riskcompliance_sweep(client, [
        ("policy_detail", [policy_b.pk], "get", None),
        ("policy_raise_attestations", [policy_b.pk], "post", {}),
        ("policy_raise_attestations", [policy_b.pk], "post", {"due_days": "30"}),
    ])

    assert failures == [], f"cross-tenant policy routes did not 404: {failures}"
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == 0
    assert PolicyAttestation.objects.filter(tenant=tenant_b).count() == 0


def test_riskcompliance_foreign_auditseal_pk_is_404_on_detail_and_verify(
        admin_user, tenant_b, admin_b):
    """The seal register is evidence about ONE workspace; detail and verify both refuse B's.

    ``auditseal_verify`` re-hashes a whole range and stamps three columns on the row, so an
    unscoped one would let a stranger both read another workspace's digest and write to its row.
    """
    client = _riskcompliance_sweep_client(admin_user)
    seal_b = _riskcompliance_seal_for(tenant_b, admin_b, note="Globex month-end seal.")
    before = _riskcompliance_snapshot(seal_b, "digest", "chain_digest", "last_verify_ok",
                                      "last_verified_at", "row_count")

    failures = _riskcompliance_sweep(client, [
        ("auditseal_detail", [seal_b.pk], "get", None),
        ("auditseal_verify", [seal_b.pk], "post", {}),
    ])

    assert failures == [], f"cross-tenant audit-seal routes did not 404: {failures}"
    _riskcompliance_assert_unchanged(seal_b, before)


def test_riskcompliance_each_workspace_still_reaches_its_own_rows(
        client_a, client_b, riskcompliance_screening_open, riskcompliance_screening_b):
    """The L44 pair: the guard narrows ONLY across the boundary.

    Without this, a view that 404s on everything would pass every isolation test above while
    being completely broken.
    """
    assert client_a.get(reverse(
        "procurement:screening_detail", args=[riskcompliance_screening_open.pk])
    ).status_code == 200
    assert client_b.get(reverse(
        "procurement:screening_detail", args=[riskcompliance_screening_b.pk])
    ).status_code == 200


# ================================================================= 2. register isolation

def test_riskcompliance_registers_never_contain_foreign_rows(
        client_a, tenant_b, riskcompliance_screening_open, riskcompliance_screening_b,
        riskcompliance_party_b, admin_b, riskcompliance_signal_fhr, riskcompliance_fraud_open,
        riskcompliance_attestation_pending):
    """Not one 6.17 register, board or feed leaks a tenant-B identifier into tenant A's page.

    Asserted on the foreign row's own text rather than on a count, because both workspaces number
    from 1 (SCR-00001 exists twice) and a count assertion cannot tell a leaked row from a local
    one.
    """
    hit_b = _riskcompliance_hit_for(riskcompliance_screening_b, "GLOBEX SANCTIONED ENTITY")
    _riskcompliance_signal_for(tenant_b, riskcompliance_party_b, admin_b)
    _riskcompliance_alert_for(tenant_b, riskcompliance_party_b, admin_b)
    policy_b = _riskcompliance_policy_for(tenant_b, "Globex Code of Conduct", admin_b)
    _riskcompliance_attestation_for(policy_b, admin_b)
    _riskcompliance_audit_row(tenant_b, admin_b, target="Globex screening SCR-GBX")
    seal_b = _riskcompliance_seal_for(tenant_b, admin_b, note="Globex month-end seal.")

    foreign_marks = (
        riskcompliance_screening_b.reference,      # CSL-GBX-0004
        hit_b.matched_name,                        # GLOBEX SANCTIONED ENTITY
        riskcompliance_party_b.name,               # Globex Offshore Trading
        policy_b.title,                            # Globex Code of Conduct
        "Globex screening SCR-GBX",                # the audit target
        seal_b.note,                               # Globex month-end seal.
    )

    for url_name in ("screening_list", "screeninghit_list", "risksignal_list",
                     "fraudalert_list", "policyattestation_list", "policy_list",
                     "audit_trail", "auditseal_list", "screening_rescreen_board",
                     "risksignal_refresh_board", "fraud_board", "policy_overdue_board",
                     "policy_mine", "fraud_scan"):
        response = client_a.get(reverse(f"procurement:{url_name}"))
        assert response.status_code == 200, url_name
        html = _riskcompliance_html(response)
        for mark in foreign_marks:
            assert mark not in html, f"{url_name} leaked {mark!r} from tenant B"


def test_riskcompliance_audit_trail_export_never_contains_foreign_rows(
        client_a, tenant_a, tenant_b, admin_user, admin_b):
    """The CSV walks the SAME queryset as the page, so the boundary must hold there too."""
    _riskcompliance_audit_row(tenant_a, admin_user, target="Acme screening SCR-00001")
    _riskcompliance_audit_row(tenant_b, admin_b, target="Globex screening SCR-GBX")

    response = client_a.get(reverse("procurement:audit_trail_export"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Acme screening SCR-00001" in body      # L44 pair: A's own row IS exported
    assert "Globex screening SCR-GBX" not in body


# ================================================================= 3. permission gates
#
# ``@tenant_admin_required`` raises ``PermissionDenied`` -> 403. Two of the admin checks are made
# INSIDE the view instead (``fraud_scan`` POST and ``policy_overdue_board`` POST), because the
# read half of both pages is open to everybody; those refuse with a redirect and an error
# message. Both shapes are asserted here, and both are followed by an unchanged-row assertion:
# a 403 that still mutated is the bug, and the status code alone cannot see it.

def test_riskcompliance_member_cannot_use_the_screening_admin_verbs(
        riskcompliance_member_a, riskcompliance_screening_open, riskcompliance_screening_disposed,
        riskcompliance_hit_open):
    """The five screening/hit verbs an ordinary member must not have, and the rows afterwards.

    ``screening_clear`` is aimed at the DISPOSED screening on purpose - the one row an
    administrator could legitimately clear - so the refusal under test is the permission gate and
    not the open-hits gate that would have refused an admin too.
    """
    client = _riskcompliance_sweep_client(riskcompliance_member_a)
    open_before = _riskcompliance_snapshot(riskcompliance_screening_open, "status",
                                           "decided_at", "decision_note")
    disposed_before = _riskcompliance_snapshot(riskcompliance_screening_disposed, "status",
                                               "decided_at", "next_rescreen_on")
    hit_before = _riskcompliance_snapshot(riskcompliance_hit_open, "disposition",
                                          "disposition_note", "disposed_at")

    failures = _riskcompliance_sweep(client, [
        ("screening_clear", [riskcompliance_screening_disposed.pk], "post",
         {"note": "Every hit is adjudicated."}),
        ("screening_escalate", [riskcompliance_screening_open.pk], "post",
         {"note": "Referred for a compliance decision."}),
        ("screening_block", [riskcompliance_screening_open.pk], "post",
         {"note": "Confirmed SDN match."}),
        ("screening_delete", [riskcompliance_screening_open.pk], "post", {}),
        ("screeninghit_delete", [riskcompliance_hit_open.pk], "post", {}),
        ("screeninghit_dispose", [riskcompliance_hit_open.pk], "post",
         _riskcompliance_dispose_payload()),
    ], expected=403)

    assert failures == [], f"a non-admin reached an admin-gated screening verb: {failures}"
    _riskcompliance_assert_unchanged(riskcompliance_screening_open, open_before)
    _riskcompliance_assert_unchanged(riskcompliance_screening_disposed, disposed_before)
    _riskcompliance_assert_unchanged(riskcompliance_hit_open, hit_before)
    assert ComplianceScreening.objects.filter(pk=riskcompliance_screening_open.pk).exists()
    assert ScreeningHit.objects.filter(pk=riskcompliance_hit_open.pk).exists()
    # ...and the parent's derived counters were not quietly recomputed against a deleted hit.
    riskcompliance_screening_open.refresh_from_db()
    assert riskcompliance_screening_open.open_hit_count == 2


def test_riskcompliance_member_cannot_delete_or_dispose_signals_and_alerts(
        riskcompliance_member_a, riskcompliance_signal_fhr, riskcompliance_fraud_open):
    """Deleting an observation, or closing an accusation, is administrator work."""
    client = _riskcompliance_sweep_client(riskcompliance_member_a)
    signal_before = _riskcompliance_snapshot(riskcompliance_signal_fhr, "review_status", "value")
    alert_before = _riskcompliance_snapshot(riskcompliance_fraud_open, "status",
                                            "resolution_note", "resolved_at")

    failures = _riskcompliance_sweep(client, [
        ("risksignal_delete", [riskcompliance_signal_fhr.pk], "post", {}),
        ("fraudalert_delete", [riskcompliance_fraud_open.pk], "post", {}),
        ("fraudalert_disposition", [riskcompliance_fraud_open.pk], "post",
         {"action": "substantiate", "resolution_note": "Confirmed with HR."}),
    ], expected=403)

    assert failures == [], f"a non-admin reached an admin-gated verb: {failures}"
    assert SupplierRiskSignal.objects.filter(pk=riskcompliance_signal_fhr.pk).exists()
    assert FraudAlert.objects.filter(pk=riskcompliance_fraud_open.pk).exists()
    _riskcompliance_assert_unchanged(riskcompliance_signal_fhr, signal_before)
    _riskcompliance_assert_unchanged(riskcompliance_fraud_open, alert_before)


def test_riskcompliance_member_cannot_edit_exempt_or_delete_an_attestation(
        riskcompliance_member_a, riskcompliance_attestation_pending,
        riskcompliance_policy_published, tenant_a):
    """Even the OWNER of the row cannot edit it, exempt themselves from it, or delete it.

    ``policyattestation_edit`` was ungated before the review pass; the gate is asserted on both
    the GET (the pre-filled form itself) and the POST. ``attestation_exempt`` is the sharper one:
    the exemption is the only legitimate way out of a stated obligation, so a member excusing
    THEMSELVES would empty the ledger of the one thing it holds.
    """
    client = _riskcompliance_sweep_client(riskcompliance_member_a)
    row = riskcompliance_attestation_pending
    assert row.user_id == riskcompliance_member_a.pk       # the refusals below are on the OWNER
    before = _riskcompliance_snapshot(row, "status", "due_on", "exempt_reason", "exempted_by_id",
                                      "exempted_at", "acknowledged_at")
    seal_count = AuditSeal.objects.filter(tenant=tenant_a).count()
    attestation_count = PolicyAttestation.objects.filter(tenant=tenant_a).count()

    failures = _riskcompliance_sweep(client, [
        ("policyattestation_edit", [row.pk], "get", None),
        ("policyattestation_edit", [row.pk], "post",
         {"policy": str(riskcompliance_policy_published.pk),
          "user": str(riskcompliance_member_a.pk),
          "due_on": (_riskcompliance_today() + _riskcompliance_days(365)).isoformat()}),
        ("policyattestation_delete", [row.pk], "post", {}),
        ("attestation_exempt", [row.pk], "post", {"reason": "I would rather not."}),
        ("policy_raise_attestations", [riskcompliance_policy_published.pk], "post", {}),
        ("auditseal_create", [], "post", {"note": "Sealed by a non-admin."}),
    ], expected=403)

    assert failures == [], f"a non-admin reached an admin-gated attestation verb: {failures}"
    assert PolicyAttestation.objects.filter(pk=row.pk).exists()
    _riskcompliance_assert_unchanged(row, before)
    # The roster was not raised and the trail was not sealed.
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == attestation_count
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == seal_count


def test_riskcompliance_member_post_to_fraud_scan_is_refused_and_raises_nothing(
        riskcompliance_member_a, tenant_a, riskcompliance_party_a):
    """``fraud_scan`` checks the admin flag INSIDE the view, so the refusal is a redirect.

    The read-only half of the page stays visible to everybody by design, which is why this one
    cannot be a decorator - and why the assertion that matters is that no alert was raised, not
    the status code.
    """
    _riskcompliance_role(riskcompliance_party_a)
    client = _riskcompliance_login(riskcompliance_member_a)
    url = reverse("procurement:fraud_scan")
    before = FraudAlert.objects.filter(tenant=tenant_a).count()

    response = client.post(url, {
        "start": (_riskcompliance_today() - _riskcompliance_days(30)).isoformat(),
        "end": _riskcompliance_today().isoformat(),
    })

    assert response.status_code == 302
    assert response["Location"] == url
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == before
    assert any("administrator" in message for message in _riskcompliance_messages(response))
    # L44 pair: the READ half of the same page is still open to this user.
    assert client.get(url).status_code == 200


def test_riskcompliance_member_post_to_overdue_board_chases_nobody(
        riskcompliance_member_a, tenant_a, riskcompliance_attestation_overdue):
    """Same shape next door: seeing who is late is ordinary work, chasing them is not."""
    client = _riskcompliance_login(riskcompliance_member_a)
    url = reverse("procurement:policy_overdue_board")
    before = ProcurementAlert.objects.filter(tenant=tenant_a).count()

    response = client.post(url, {})

    assert response.status_code == 302
    assert response["Location"] == url
    assert ProcurementAlert.objects.filter(tenant=tenant_a).count() == before
    riskcompliance_attestation_overdue.refresh_from_db()
    assert riskcompliance_attestation_overdue.alert_id is None
    assert any("administrator" in message for message in _riskcompliance_messages(response))
    assert client.get(url).status_code == 200


def test_riskcompliance_member_still_reaches_every_read_surface(
        riskcompliance_member_a, riskcompliance_screening_open, riskcompliance_signal_fhr,
        riskcompliance_fraud_open, riskcompliance_attestation_pending,
        riskcompliance_policy_published, tenant_a, admin_user):
    """L32: the gates narrow the WRITES, never the reads.

    All five ``LIVE_LINKS["6.17"]`` destinations plus ``policy_mine`` return 200 WITH content for
    an ordinary member - not a redirect, not an empty shell. A compliance register only an
    administrator can open is a register nobody reads.
    """
    _riskcompliance_audit_row(tenant_a, admin_user, target="Acme screening SCR-00001")
    client = _riskcompliance_sweep_client(riskcompliance_member_a)

    surfaces = {
        "screening_list": riskcompliance_screening_open.number,
        "risksignal_list": riskcompliance_signal_fhr.number,
        "audit_trail": "Acme screening SCR-00001",
        "fraudalert_list": riskcompliance_fraud_open.number,
        "policy_list": riskcompliance_policy_published.title,
        "policy_mine": riskcompliance_policy_published.title,
    }

    for url_name, expected_text in surfaces.items():
        response = client.get(reverse(f"procurement:{url_name}"))
        assert response.status_code == 200, f"{url_name} -> {response.status_code}"
        assert expected_text in _riskcompliance_html(response), (
            f"{url_name} returned 200 but rendered none of its own rows (L8)")


def test_riskcompliance_anonymous_is_redirected_to_login_on_every_route(
        riskcompliance_screening_open, riskcompliance_hit_open, riskcompliance_signal_fhr,
        riskcompliance_fraud_open, riskcompliance_attestation_pending,
        riskcompliance_policy_published, riskcompliance_seal):
    """Not one 6.17 route - register, board, detail, form or verb - answers an anonymous caller."""
    client = Client(raise_request_exception=False)
    screening_pk = riskcompliance_screening_open.pk
    hit_pk = riskcompliance_hit_open.pk

    cases = [
        ("screening_list", [], "get", None),
        ("screening_create", [], "get", None),
        ("screening_detail", [screening_pk], "get", None),
        ("screening_edit", [screening_pk], "get", None),
        ("screening_delete", [screening_pk], "post", {}),
        ("screening_clear", [screening_pk], "post", {"note": "x"}),
        ("screening_escalate", [screening_pk], "post", {"note": "x"}),
        ("screening_block", [screening_pk], "post", {"note": "x"}),
        ("screening_rescreen_board", [], "get", None),
        ("screeninghit_list", [], "get", None),
        ("screeninghit_create", [screening_pk], "get", None),
        ("screeninghit_detail", [hit_pk], "get", None),
        ("screeninghit_edit", [hit_pk], "get", None),
        ("screeninghit_delete", [hit_pk], "post", {}),
        ("screeninghit_dispose", [hit_pk], "post", _riskcompliance_dispose_payload()),
        ("risksignal_list", [], "get", None),
        ("risksignal_create", [], "get", None),
        ("risksignal_detail", [riskcompliance_signal_fhr.pk], "get", None),
        ("risksignal_edit", [riskcompliance_signal_fhr.pk], "get", None),
        ("risksignal_delete", [riskcompliance_signal_fhr.pk], "post", {}),
        ("risksignal_review", [riskcompliance_signal_fhr.pk], "post", {"action": "reviewed"}),
        ("risksignal_refresh_board", [], "get", None),
        ("fraudalert_list", [], "get", None),
        ("fraudalert_create", [], "get", None),
        ("fraudalert_detail", [riskcompliance_fraud_open.pk], "get", None),
        ("fraudalert_edit", [riskcompliance_fraud_open.pk], "get", None),
        ("fraudalert_delete", [riskcompliance_fraud_open.pk], "post", {}),
        ("fraudalert_disposition", [riskcompliance_fraud_open.pk], "post",
         {"action": "investigate"}),
        ("fraud_scan", [], "get", None),
        ("fraud_board", [], "get", None),
        ("policyattestation_list", [], "get", None),
        ("policyattestation_create", [], "get", None),
        ("policyattestation_detail", [riskcompliance_attestation_pending.pk], "get", None),
        ("policyattestation_edit", [riskcompliance_attestation_pending.pk], "get", None),
        ("policyattestation_delete", [riskcompliance_attestation_pending.pk], "post", {}),
        ("attestation_sign", [riskcompliance_attestation_pending.pk], "post", {"note": "x"}),
        ("attestation_exempt", [riskcompliance_attestation_pending.pk], "post", {"reason": "x"}),
        ("policy_list", [], "get", None),
        ("policy_detail", [riskcompliance_policy_published.pk], "get", None),
        ("policy_raise_attestations", [riskcompliance_policy_published.pk], "post", {}),
        ("policy_mine", [], "get", None),
        ("policy_overdue_board", [], "get", None),
        ("audit_trail", [], "get", None),
        ("audit_trail_export", [], "get", None),
        ("auditseal_list", [], "get", None),
        ("auditseal_create", [], "post", {"note": "x"}),
        ("auditseal_detail", [riskcompliance_seal.pk], "get", None),
        ("auditseal_verify", [riskcompliance_seal.pk], "post", {}),
    ]

    failures = []
    for url_name, args, method, data in cases:
        url = reverse(f"procurement:{url_name}", args=args)
        response = client.post(url, data or {}) if method == "post" else client.get(url)
        if response.status_code != 302 or "/login" not in response["Location"]:
            failures.append((url_name, response.status_code,
                             response.get("Location", "")))

    assert failures == [], f"routes that answered an anonymous caller: {failures}"
    # Nothing an anonymous POST touched actually moved.
    riskcompliance_attestation_pending.refresh_from_db()
    assert riskcompliance_attestation_pending.status == "pending"
    assert ScreeningHit.objects.filter(pk=hit_pk, disposition="open").exists()


# ================================================================= 4. attestation_sign is owner-only
#
# The sharpest rule in the sub-module, and the one worth four separate refusals. A signature is
# only evidence if the person named on it applied it themselves - so ``attestation_sign`` is
# deliberately NOT ``@tenant_admin_required``, in BOTH directions: an ordinary member must be able
# to sign their own row, and nobody at all may sign somebody else's. Each refusal below is
# followed by an assertion that ``status``, ``acknowledged_at`` and ``acknowledgement_note`` are
# still exactly what they were - a refusal that redirected but still stamped is the bug.

_RISKCOMPLIANCE_SIGN_COLUMNS = ("status", "acknowledged_at", "acknowledgement_note")


def test_riskcompliance_attestation_sign_succeeds_for_its_own_owner(
        riskcompliance_member_a, riskcompliance_attestation_pending):
    """The positive half (L44): the person named on the row signs it, and it lands.

    Without this, a view that refused everybody would pass every refusal test below while making
    the ledger impossible to fill in.
    """
    row = riskcompliance_attestation_pending
    client = _riskcompliance_login(riskcompliance_member_a)

    response = client.post(reverse("procurement:attestation_sign", args=[row.pk]),
                           {"note": "Read in full and accepted."})

    assert response.status_code == 302
    assert response["Location"] == reverse("procurement:policyattestation_detail", args=[row.pk])
    row.refresh_from_db()
    assert row.status == "acknowledged"
    assert row.acknowledged_at is not None
    assert row.acknowledgement_note == "Read in full and accepted."


def test_riskcompliance_attestation_sign_refuses_a_peer_in_the_same_workspace(
        tenant_a, riskcompliance_attestation_pending):
    """A colleague cannot sign it. The row is owed by one named person and only by them."""
    row = riskcompliance_attestation_pending
    peer = _riskcompliance_new_user(tenant_a, "peer.buyer@acme.com", "peer_buyer_acme")
    before = _riskcompliance_snapshot(row, *_RISKCOMPLIANCE_SIGN_COLUMNS)
    client = _riskcompliance_login(peer)

    response = client.post(reverse("procurement:attestation_sign", args=[row.pk]),
                           {"note": "Signing this for a colleague."})

    assert response.status_code == 302
    _riskcompliance_assert_unchanged(row, before)
    assert row.status == "pending"
    assert row.acknowledged_at is None
    assert row.acknowledgement_note == ""
    assert any("Only the person named on a sign-off" in message
               for message in _riskcompliance_messages(response))


def test_riskcompliance_attestation_sign_refuses_the_tenant_administrator(
        admin_user, client_a, riskcompliance_attestation_pending):
    """**A tenant administrator cannot sign for somebody else** - the whole point of the ledger.

    An administrator who could apply a subordinate's signature would be forging exactly the
    evidence the ledger exists to hold, and no audit could ever tell the two apart afterwards.
    The legitimate administrative answer is an EXEMPTION, which says something different and says
    so on the record.
    """
    row = riskcompliance_attestation_pending
    assert admin_user.is_tenant_admin is True
    assert row.user_id != admin_user.pk
    before = _riskcompliance_snapshot(row, *_RISKCOMPLIANCE_SIGN_COLUMNS)

    response = client_a.post(reverse("procurement:attestation_sign", args=[row.pk]),
                             {"note": "Signed on their behalf."})

    assert response.status_code == 302
    _riskcompliance_assert_unchanged(row, before)
    assert row.status == "pending"
    assert row.acknowledged_at is None
    assert row.acknowledgement_note == ""
    assert any("that includes administrators" in message
               for message in _riskcompliance_messages(response))


def test_riskcompliance_attestation_sign_refuses_a_superuser_inside_the_workspace(
        tenant_a, riskcompliance_attestation_pending):
    """The sharper superuser case: one ATTACHED to the workspace, so no tenant guard fires.

    ``request.tenant`` resolves, the pk resolves, and the only thing standing between this
    account and a forged signature is the ownership check itself.
    """
    row = riskcompliance_attestation_pending
    root = _riskcompliance_new_superuser(tenant=tenant_a, email="root.acme@naverp.test",
                                         username="root_acme")
    before = _riskcompliance_snapshot(row, *_RISKCOMPLIANCE_SIGN_COLUMNS)
    client = _riskcompliance_login(root)

    response = client.post(reverse("procurement:attestation_sign", args=[row.pk]),
                           {"note": "Root said so."})

    assert response.status_code == 302
    _riskcompliance_assert_unchanged(row, before)
    assert row.status == "pending"
    assert row.acknowledged_at is None
    assert row.acknowledgement_note == ""


def test_riskcompliance_attestation_sign_refuses_the_tenantless_superuser(
        riskcompliance_attestation_pending):
    """The real ``admin`` shape - ``tenant=None`` - is stopped by the workspace guard first."""
    row = riskcompliance_attestation_pending
    root = _riskcompliance_new_superuser()
    assert root.tenant_id is None
    before = _riskcompliance_snapshot(row, *_RISKCOMPLIANCE_SIGN_COLUMNS)
    client = _riskcompliance_login(root)

    response = client.post(reverse("procurement:attestation_sign", args=[row.pk]),
                           {"note": "Root said so."})

    assert response.status_code == 302
    assert response["Location"] == reverse("dashboard:home")
    _riskcompliance_assert_unchanged(row, before)
    assert row.status == "pending"


def test_riskcompliance_a_signed_attestation_cannot_be_signed_again(
        riskcompliance_member_a, riskcompliance_attestation_signed, admin_user):
    """Terminal means terminal: even its owner cannot re-sign, and the stamps do not move.

    ``riskcompliance_attestation_signed`` is owned by ``admin_user`` and was signed through the
    real ``acknowledge()`` verb, so this is the owner's own second press.
    """
    row = riskcompliance_attestation_signed
    before = _riskcompliance_snapshot(row, *_RISKCOMPLIANCE_SIGN_COLUMNS)
    client = _riskcompliance_login(admin_user)

    response = client.post(reverse("procurement:attestation_sign", args=[row.pk]),
                           {"note": "Signing it a second time."})

    assert response.status_code == 302
    _riskcompliance_assert_unchanged(row, before)
    assert row.acknowledgement_note == "Read in full and accepted."


# ================================================================= 5. POST-only verbs

def test_riskcompliance_get_on_every_mutating_verb_is_405_and_mutates_nothing(
        admin_user, riskcompliance_screening_open, riskcompliance_screening_disposed,
        riskcompliance_hit_open, riskcompliance_signal_fhr, riskcompliance_fraud_open,
        riskcompliance_attestation_pending, riskcompliance_policy_published,
        riskcompliance_seal, tenant_a):
    """Sixteen ``@require_POST`` routes, driven as the ADMIN so the gate is reached.

    Driven as an administrator on purpose: ``@tenant_admin_required`` sits OUTSIDE
    ``@require_POST``, so a non-admin GET would be refused 403 by the permission gate and this
    test would never reach the method check it exists for.
    """
    client = _riskcompliance_sweep_client(admin_user)
    screening_before = _riskcompliance_snapshot(riskcompliance_screening_open, "status")
    disposed_before = _riskcompliance_snapshot(riskcompliance_screening_disposed, "status")
    hit_before = _riskcompliance_snapshot(riskcompliance_hit_open, "disposition")
    signal_before = _riskcompliance_snapshot(riskcompliance_signal_fhr, "review_status")
    alert_before = _riskcompliance_snapshot(riskcompliance_fraud_open, "status")
    attestation_before = _riskcompliance_snapshot(riskcompliance_attestation_pending, "status")
    seal_before = _riskcompliance_snapshot(riskcompliance_seal, "last_verify_ok",
                                           "last_verified_at")
    seal_count = AuditSeal.objects.filter(tenant=tenant_a).count()
    attestation_count = PolicyAttestation.objects.filter(tenant=tenant_a).count()

    failures = _riskcompliance_sweep(client, [
        ("screening_delete", [riskcompliance_screening_open.pk], "get", None),
        ("screening_clear", [riskcompliance_screening_disposed.pk], "get", None),
        ("screening_escalate", [riskcompliance_screening_open.pk], "get", None),
        ("screening_block", [riskcompliance_screening_open.pk], "get", None),
        ("screeninghit_delete", [riskcompliance_hit_open.pk], "get", None),
        ("screeninghit_dispose", [riskcompliance_hit_open.pk], "get", None),
        ("risksignal_delete", [riskcompliance_signal_fhr.pk], "get", None),
        ("risksignal_review", [riskcompliance_signal_fhr.pk], "get", None),
        ("fraudalert_delete", [riskcompliance_fraud_open.pk], "get", None),
        ("fraudalert_disposition", [riskcompliance_fraud_open.pk], "get", None),
        ("policyattestation_delete", [riskcompliance_attestation_pending.pk], "get", None),
        ("attestation_sign", [riskcompliance_attestation_pending.pk], "get", None),
        ("attestation_exempt", [riskcompliance_attestation_pending.pk], "get", None),
        ("policy_raise_attestations", [riskcompliance_policy_published.pk], "get", None),
        ("auditseal_create", [], "get", None),
        ("auditseal_verify", [riskcompliance_seal.pk], "get", None),
    ], expected=405)

    assert failures == [], f"a mutating verb answered a GET: {failures}"

    # Nothing moved, nothing was created, nothing was destroyed.
    _riskcompliance_assert_unchanged(riskcompliance_screening_open, screening_before)
    _riskcompliance_assert_unchanged(riskcompliance_screening_disposed, disposed_before)
    _riskcompliance_assert_unchanged(riskcompliance_hit_open, hit_before)
    _riskcompliance_assert_unchanged(riskcompliance_signal_fhr, signal_before)
    _riskcompliance_assert_unchanged(riskcompliance_fraud_open, alert_before)
    _riskcompliance_assert_unchanged(riskcompliance_attestation_pending, attestation_before)
    _riskcompliance_assert_unchanged(riskcompliance_seal, seal_before)
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == seal_count
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == attestation_count
    assert ComplianceScreening.objects.filter(pk=riskcompliance_screening_open.pk).exists()
    assert ScreeningHit.objects.filter(pk=riskcompliance_hit_open.pk).exists()
    assert SupplierRiskSignal.objects.filter(pk=riskcompliance_signal_fhr.pk).exists()
    assert FraudAlert.objects.filter(pk=riskcompliance_fraud_open.pk).exists()


# ================================================================= 6. CSRF

def test_riskcompliance_post_without_a_csrf_token_is_rejected_on_every_entity(
        admin_user, riskcompliance_screening_open, riskcompliance_hit_open,
        riskcompliance_signal_fhr, riskcompliance_fraud_open,
        riskcompliance_attestation_signed, riskcompliance_policy_published,
        riskcompliance_seal, tenant_a):
    """One mutating verb per entity, posted with no token, under ``enforce_csrf_checks=True``.

    ``force_login`` authenticates the session but supplies no CSRF cookie or form token, which is
    exactly the shape of a cross-site POST from a page the workspace does not control.
    """
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)

    screening_before = _riskcompliance_snapshot(riskcompliance_screening_open, "status")
    hit_before = _riskcompliance_snapshot(riskcompliance_hit_open, "disposition")
    signal_before = _riskcompliance_snapshot(riskcompliance_signal_fhr, "review_status")
    alert_before = _riskcompliance_snapshot(riskcompliance_fraud_open, "status")
    attestation_before = _riskcompliance_snapshot(riskcompliance_attestation_signed, "status")
    seal_count = AuditSeal.objects.filter(tenant=tenant_a).count()
    attestation_count = PolicyAttestation.objects.filter(tenant=tenant_a).count()

    failures = _riskcompliance_sweep(client, [
        ("screening_delete", [riskcompliance_screening_open.pk], "post", {}),
        ("screeninghit_dispose", [riskcompliance_hit_open.pk], "post",
         _riskcompliance_dispose_payload()),
        ("risksignal_review", [riskcompliance_signal_fhr.pk], "post",
         {"action": "reviewed", "review_note": "Looked at."}),
        ("fraudalert_disposition", [riskcompliance_fraud_open.pk], "post",
         {"action": "substantiate", "resolution_note": "Confirmed."}),
        ("attestation_sign", [riskcompliance_attestation_signed.pk], "post", {"note": "x"}),
        ("policy_raise_attestations", [riskcompliance_policy_published.pk], "post", {}),
        ("auditseal_create", [], "post", {"note": "Sealed without a token."}),
    ], expected=403)

    assert failures == [], f"a mutating verb accepted a POST with no CSRF token: {failures}"

    _riskcompliance_assert_unchanged(riskcompliance_screening_open, screening_before)
    _riskcompliance_assert_unchanged(riskcompliance_hit_open, hit_before)
    _riskcompliance_assert_unchanged(riskcompliance_signal_fhr, signal_before)
    _riskcompliance_assert_unchanged(riskcompliance_fraud_open, alert_before)
    _riskcompliance_assert_unchanged(riskcompliance_attestation_signed, attestation_before)
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == seal_count
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == attestation_count
    assert ComplianceScreening.objects.filter(pk=riskcompliance_screening_open.pk).exists()


def test_riskcompliance_create_forms_also_reject_a_tokenless_post(
        admin_user, tenant_a, riskcompliance_party_a):
    """The CRUD create routes are covered too - a forged POST must not mint a compliance record."""
    _riskcompliance_role(riskcompliance_party_a)
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)

    failures = _riskcompliance_sweep(client, [
        ("screening_create", [], "post",
         _riskcompliance_screening_payload(riskcompliance_party_a.pk)),
        ("risksignal_create", [], "post",
         _riskcompliance_signal_payload(riskcompliance_party_a.pk)),
        ("fraudalert_create", [], "post",
         _riskcompliance_alert_payload(riskcompliance_party_a.pk)),
    ], expected=403)

    assert failures == [], f"a create route accepted a POST with no CSRF token: {failures}"
    assert ComplianceScreening.objects.filter(tenant=tenant_a).count() == 0
    assert SupplierRiskSignal.objects.filter(tenant=tenant_a).count() == 0
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 0


# ================================================================= 7. junk and hostile input
#
# L11: every one of these is a URL somebody can type into the address bar, and every one of them
# has 500'd somewhere in this codebase before. The three shapes that matter are all here:
#
#   "abc"                    - not a number at all
#   the Unicode superscript  - ``isdigit()`` says True, ``int()`` raises. ``as_db_int`` uses
#                              ``isdecimal()``, which is the difference.
#   20 digits                - decimal, converts cleanly, and then dies inside the database
#                              driver on a BIGINT column
#   "0"                      - decimal and in range, but an AutoField starts at 1, so it can only
#                              ever empty the register
#
# ``raise_request_exception=False`` collects a 500 with the parameter that caused it instead of
# aborting the sweep at the first one.

_RISKCOMPLIANCE_SUPERSCRIPT_TWO = "²"

#: Every junk pk shape, for whichever FK filter the page under test offers.
_RISKCOMPLIANCE_JUNK_PKS = ("abc", _RISKCOMPLIANCE_SUPERSCRIPT_TWO, "99999999999999999999", "0",
                            "-1", "1.5", "null", "%27")

#: Junk pagination, junk dates and an oversized search box - the same on every page.
_RISKCOMPLIANCE_JUNK_COMMON = (
    {"page": "abc"},
    {"page": "-1"},
    {"page": "0"},
    {"page": "99999"},
    {"page": "2"},
    {"q": "x" * 5000},
    {"q": "<script>alert(1)</script>"},
    {"q": "%' OR '1'='1"},
)


def _riskcompliance_junk_params(int_filters=(), enum_filters=(), date_filters=()):
    """Every hostile query string worth firing at one list page, as ``[{param: value}, ...]``."""
    cases = list(_RISKCOMPLIANCE_JUNK_COMMON)
    for param in int_filters:
        cases.extend({param: junk} for junk in _RISKCOMPLIANCE_JUNK_PKS)
    for param in enum_filters:
        cases.extend([{param: "not_a_real_choice"}, {param: _RISKCOMPLIANCE_SUPERSCRIPT_TWO},
                      {param: "'; DROP TABLE x; --"}])
    for param in date_filters:
        cases.extend([{param: "lastweek"}, {param: "9999-99-99"}, {param: "0000-00-00"},
                      {param: "2026-13-45"}, {param: "-1"}])
    return cases


def _riskcompliance_junk_sweep(client, url_name, cases):
    """Fire every case at one page and collect ``(params, status)`` for anything that is not 200."""
    url = reverse(f"procurement:{url_name}")
    failures = []
    for params in cases:
        response = client.get(url, params)
        if response.status_code != 200:
            failures.append((params, response.status_code))
    return failures


def test_riskcompliance_screening_register_survives_every_junk_param(
        admin_user, riskcompliance_screening_open):
    """``screening_list``: junk pk, junk enum, junk page, oversized search - 200, never 500."""
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(
        int_filters=("party",),
        enum_filters=("list_source", "checkpoint", "result", "status"))
    assert _riskcompliance_junk_sweep(client, "screening_list", cases) == []


def test_riskcompliance_screeninghit_queue_survives_every_junk_param(
        admin_user, riskcompliance_hit_open):
    """``screeninghit_list``: ``min_score`` is a ``__gte`` and not a pk, so 0 must still filter."""
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(
        int_filters=("screening", "min_score"),
        enum_filters=("disposition", "matched_list", "match_type"))
    assert _riskcompliance_junk_sweep(client, "screeninghit_list", cases) == []


def test_riskcompliance_risksignal_register_survives_every_junk_param(
        admin_user, riskcompliance_signal_ser):
    """``risksignal_list``: five closed vocabularies and one FK, all hostile."""
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(
        int_filters=("party",),
        enum_filters=("provider", "metric", "band", "trend", "review_status"))
    assert _riskcompliance_junk_sweep(client, "risksignal_list", cases) == []


def test_riskcompliance_fraudalert_register_survives_every_junk_param(
        admin_user, riskcompliance_fraud_open, riskcompliance_fraud_resolved):
    """``fraudalert_list``: two FK filters (``vendor``, ``assigned_to``) and three enums."""
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(
        int_filters=("vendor", "assigned_to"),
        enum_filters=("rule", "status", "severity"))
    assert _riskcompliance_junk_sweep(client, "fraudalert_list", cases) == []


def test_riskcompliance_attestation_ledger_survives_every_junk_param(
        admin_user, riskcompliance_attestation_pending, riskcompliance_attestation_overdue):
    """``policyattestation_list``: ``policy`` and ``user`` are both FK filters."""
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(int_filters=("policy", "user"),
                                        enum_filters=("status",))
    assert _riskcompliance_junk_sweep(client, "policyattestation_list", cases) == []


def test_riskcompliance_policy_register_survives_every_junk_param(
        admin_user, riskcompliance_policy_published, riskcompliance_policy_draft):
    """``policy_list``: the org-unit scope filter is the FK, ``category`` the 6.19 vocabulary."""
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(int_filters=("org_unit",),
                                        enum_filters=("category", "status"))
    assert _riskcompliance_junk_sweep(client, "policy_list", cases) == []


def test_riskcompliance_audit_trail_survives_every_junk_param(admin_user, tenant_a):
    """``audit_trail``: three FK-ish int params, one enum and TWO free-text date boxes.

    ``object_id`` is the interesting one - it is a ``BigIntegerField`` that takes an id from
    another table, so a 20-digit value reaches the driver unless ``as_db_int`` stops it first.
    """
    _riskcompliance_audit_row(tenant_a, admin_user)
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(
        int_filters=("content_type", "user", "object_id"),
        enum_filters=("action",),
        date_filters=("date_from", "date_to"))
    assert _riskcompliance_junk_sweep(client, "audit_trail", cases) == []


def test_riskcompliance_audit_trail_export_survives_every_junk_param(admin_user, tenant_a):
    """The export shares ``_filtered_trail`` with the page, so it must survive the same input."""
    _riskcompliance_audit_row(tenant_a, admin_user)
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(
        int_filters=("content_type", "user", "object_id"),
        enum_filters=("action",),
        date_filters=("date_from", "date_to"))
    assert _riskcompliance_junk_sweep(client, "audit_trail_export", cases) == []


def test_riskcompliance_boards_and_seal_register_survive_junk_params(
        admin_user, tenant_a, riskcompliance_party_a, riskcompliance_signal_fhr,
        riskcompliance_fraud_open, riskcompliance_attestation_overdue, riskcompliance_seal):
    """The six computed pages take no filters of their own - and must ignore invented ones."""
    _riskcompliance_role(riskcompliance_party_a)
    client = _riskcompliance_sweep_client(admin_user)
    cases = _riskcompliance_junk_params(int_filters=("party", "vendor"),
                                        enum_filters=("status", "band"),
                                        date_filters=("date_from",))
    for url_name in ("screening_rescreen_board", "risksignal_refresh_board", "fraud_board",
                     "policy_overdue_board", "policy_mine", "auditseal_list", "fraud_scan"):
        failures = _riskcompliance_junk_sweep(client, url_name, cases)
        assert failures == [], f"{url_name} did not survive junk params: {failures}"


def test_riskcompliance_a_junk_enum_is_ignored_rather_than_matched(
        client_a, riskcompliance_screening_open, riskcompliance_screening_cleared,
        riskcompliance_signal_fhr, riskcompliance_fraud_open):
    """L44's other half: a guard that EMPTIES the register is as broken as one that 500s.

    An unrecognised token is validated against the model's own CHOICES and dropped, so the page
    falls back to the unfiltered register while the ``<select>`` still reads "Any". A stale
    bookmark must not silently hide every row.
    """
    baseline_screenings = {row.pk for row in client_a.get(
        reverse("procurement:screening_list")).context["object_list"]}
    assert len(baseline_screenings) == 2

    for params in ({"result": "not_a_result"}, {"status": "not_a_status"},
                   {"checkpoint": "not_a_checkpoint"}, {"list_source": "not_a_source"}):
        response = client_a.get(reverse("procurement:screening_list"), params)
        assert response.status_code == 200
        assert {row.pk for row in response.context["object_list"]} == baseline_screenings, params

    # ...and the same on the two other closed-vocabulary registers.
    response = client_a.get(reverse("procurement:risksignal_list"), {"band": "not_a_band"})
    assert {row.pk for row in response.context["object_list"]} == {riskcompliance_signal_fhr.pk}
    response = client_a.get(reverse("procurement:fraudalert_list"), {"rule": "not_a_rule"})
    assert {row.pk for row in response.context["object_list"]} == {riskcompliance_fraud_open.pk}

    # L44 pair: a REAL value does narrow, so the guard has not simply disabled the feature.
    response = client_a.get(reverse("procurement:screening_list"), {"status": "cleared"})
    assert {row.pk for row in response.context["object_list"]} == {
        riskcompliance_screening_cleared.pk}


def test_riskcompliance_a_junk_fk_filter_does_not_silently_empty_the_register(
        client_a, riskcompliance_screening_open, riskcompliance_party_a):
    """``?party=abc`` skips the filter; ``?party=<a real pk>`` applies it (L11 + L44)."""
    url = reverse("procurement:screening_list")

    for junk in _RISKCOMPLIANCE_JUNK_PKS:
        response = client_a.get(url, {"party": junk})
        assert response.status_code == 200, junk
        assert {row.pk for row in response.context["object_list"]} == {
            riskcompliance_screening_open.pk}, junk

    response = client_a.get(url, {"party": str(riskcompliance_party_a.pk)})
    assert {row.pk for row in response.context["object_list"]} == {
        riskcompliance_screening_open.pk}


def test_riskcompliance_page_past_the_end_falls_back_to_the_last_page(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    """L9: ``?page=99999`` and ``?page=2`` on a register with more rows than fit on one page.

    Seventeen screenings against a page size of 15, so page 2 is real and page 99999 is not.
    """
    for index in range(17):
        ComplianceScreening.objects.create(
            tenant=tenant_a, party=riskcompliance_party_a, list_source="csl_consolidated",
            checkpoint="onboarding", method="manual_lookup",
            screened_on=_riskcompliance_today(),
            list_as_of=_riskcompliance_today() - _riskcompliance_days(1),
            reference=f"CSL-PAGE-{index:04d}", result="clear", match_threshold=85,
            threshold_rationale="Default fuzzy threshold.", screened_by=admin_user)

    url = reverse("procurement:screening_list")
    page_one = client_a.get(url)
    assert page_one.status_code == 200
    assert len(page_one.context["object_list"]) == 15

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(page_two.context["object_list"]) == 2

    past_end = client_a.get(url, {"page": "99999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == past_end.context["page_obj"].paginator.num_pages

    junk_page = client_a.get(url, {"page": "abc"})
    assert junk_page.status_code == 200
    assert junk_page.context["page_obj"].number == 1


# -- L35: non-finite posted numbers --------------------------------------------------------------
#
# ``Decimal("NaN")`` and ``Decimal("Infinity")`` PARSE fine and then raise ``InvalidOperation`` on
# the first ``<`` comparison, which is how a 500 hides behind a value that looked like a number.
# Every posted number in 6.17 must land as a FIELD ERROR instead, with nothing saved.

_RISKCOMPLIANCE_HOSTILE_NUMBERS = ("NaN", "nan", "Infinity", "-Infinity", "inf", "1e400",
                                   "not-a-number", "", "1,000", "0x10")


def test_riskcompliance_risksignal_value_rejects_every_non_finite_number(
        admin_user, tenant_a, riskcompliance_party_a):
    """``SupplierRiskSignal.value`` feeds the scale comparison that ``NaN`` explodes inside."""
    _riskcompliance_role(riskcompliance_party_a)
    url = reverse("procurement:risksignal_create")
    client = _riskcompliance_sweep_client(admin_user)

    for hostile in _RISKCOMPLIANCE_HOSTILE_NUMBERS + ("999999999999999.99", "-4"):
        response = client.post(url, _riskcompliance_signal_payload(
            riskcompliance_party_a.pk, value=hostile))
        assert response.status_code == 200, f"{hostile!r} -> {response.status_code}"
        assert response.context["form"].errors, f"{hostile!r} was accepted as a value"

    assert SupplierRiskSignal.objects.filter(tenant=tenant_a).count() == 0

    # L44 pair: a real in-scale value saves.
    response = client.post(url, _riskcompliance_signal_payload(riskcompliance_party_a.pk,
                                                              value="5.00"))
    assert response.status_code == 302
    assert SupplierRiskSignal.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_fraudalert_amount_rejects_every_non_finite_number(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    """``FraudAlert.amount`` is ``max_digits=18``; over-range and non-finite both stop at the form."""
    _riskcompliance_role(riskcompliance_party_a)
    client = _riskcompliance_sweep_client(admin_user)
    url = reverse("procurement:fraudalert_create")

    for hostile in ("NaN", "Infinity", "-Infinity", "1e400", "not-a-number", "1,000",
                    "99999999999999999999.99"):
        response = client.post(url, _riskcompliance_alert_payload(
            riskcompliance_party_a.pk, amount=hostile))
        assert response.status_code == 200, f"{hostile!r} -> {response.status_code}"
        assert response.context["form"].errors, f"{hostile!r} was accepted as an amount"

    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 0

    response = client.post(url, _riskcompliance_alert_payload(riskcompliance_party_a.pk,
                                                              amount="48000.00"))
    assert response.status_code == 302
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_hit_match_score_rejects_hostile_numbers(
        admin_user, riskcompliance_screening_open):
    """``match_score`` is a 0-100 ``PositiveSmallIntegerField``; every other shape is refused."""
    client = _riskcompliance_sweep_client(admin_user)
    url = reverse("procurement:screeninghit_create", args=[riskcompliance_screening_open.pk])
    before = riskcompliance_screening_open.hits.count()

    for hostile in ("NaN", "Infinity", "1e400", "-1", "101", "999999999999", "abc",
                    _RISKCOMPLIANCE_SUPERSCRIPT_TWO):
        response = client.post(url, _riskcompliance_hit_payload(match_score=hostile))
        assert response.status_code == 200, f"{hostile!r} -> {response.status_code}"
        assert response.context["form"].errors, f"{hostile!r} was accepted as a match score"

    riskcompliance_screening_open.refresh_from_db()
    assert riskcompliance_screening_open.hits.count() == before


def test_riskcompliance_screening_match_threshold_rejects_hostile_numbers(
        admin_user, tenant_a, riskcompliance_party_a):
    """The adjudication threshold is the number the whole screening is judged against."""
    _riskcompliance_role(riskcompliance_party_a)
    client = _riskcompliance_sweep_client(admin_user)
    url = reverse("procurement:screening_create")

    for hostile in ("NaN", "Infinity", "1e400", "-5", "101", "99999999999999999999", "abc"):
        response = client.post(url, _riskcompliance_screening_payload(
            riskcompliance_party_a.pk, match_threshold=hostile))
        assert response.status_code == 200, f"{hostile!r} -> {response.status_code}"
        assert response.context["form"].errors, f"{hostile!r} was accepted as a threshold"

    assert ComplianceScreening.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_raise_attestations_due_days_refuses_junk_without_500(
        client_a, tenant_a, riskcompliance_policy_published, riskcompliance_member_a):
    """``due_days`` is hand-parsed from a POST body, so it goes through ``as_db_int`` (L11).

    Junk, a superscript, an over-range value and one past ``MAX_DUE_DAYS`` are all REPORTED and
    then ignored - the roster is still raised, on the standard window, rather than the request
    dying or silently recording a nonsense deadline.
    """
    url = reverse("procurement:policy_raise_attestations",
                  args=[riskcompliance_policy_published.pk])

    # A non-admin cannot reach it at all - everything below runs as the administrator.
    member_client = _riskcompliance_sweep_client(riskcompliance_member_a)
    assert member_client.post(url, {"due_days": "abc"}).status_code == 403

    for hostile in ("abc", _RISKCOMPLIANCE_SUPERSCRIPT_TWO, "99999999999999999999", "-30",
                    "400", "NaN", "Infinity", "1e400", "30.5"):
        response = client_a.post(url, {"due_days": hostile})
        assert response.status_code == 302, f"{hostile!r} -> {response.status_code}"
        raised = PolicyAttestation.objects.filter(
            tenant=tenant_a, policy=riskcompliance_policy_published)
        assert raised.exists(), f"{hostile!r} aborted the roster entirely"
        # The fallback window, never a deadline derived from the junk.
        for row in raised:
            assert row.due_on is not None
            assert row.due_on >= _riskcompliance_today()
        raised.delete()


# ================================================================= 7b. crafted cross-tenant FKs
#
# A narrowed ``<select>`` is presentation, not an authorization gate - a crafted POST never goes
# near it. Every tenant-scoped FK on every 6.17 create form is re-checked in ``clean()``, and the
# assertion below is that the foreign pk lands as a FIELD ERROR with nothing saved.

def test_riskcompliance_crafted_foreign_party_is_rejected_by_every_create_form(
        admin_user, tenant_a, riskcompliance_party_a, riskcompliance_party_b):
    """Tenant B's party in ``party`` / ``vendor`` is refused on all three registers."""
    _riskcompliance_role(riskcompliance_party_a)
    _riskcompliance_role(riskcompliance_party_b)
    client = _riskcompliance_sweep_client(admin_user)

    cases = (
        ("screening_create", "party",
         _riskcompliance_screening_payload(riskcompliance_party_b.pk)),
        ("risksignal_create", "party",
         _riskcompliance_signal_payload(riskcompliance_party_b.pk)),
        ("fraudalert_create", "vendor",
         _riskcompliance_alert_payload(riskcompliance_party_b.pk)),
    )
    for url_name, field, payload in cases:
        response = client.post(reverse(f"procurement:{url_name}"), payload)
        assert response.status_code == 200, f"{url_name} -> {response.status_code}"
        assert field in response.context["form"].errors, (
            f"{url_name} accepted tenant B's pk in {field}")

    assert ComplianceScreening.objects.count() == 0
    assert SupplierRiskSignal.objects.count() == 0
    assert FraudAlert.objects.count() == 0


def test_riskcompliance_crafted_foreign_policy_and_user_are_rejected_on_the_ledger(
        admin_user, tenant_a, tenant_b, admin_b, riskcompliance_member_a,
        riskcompliance_policy_published):
    """An attestation must not be raised against another workspace's policy or person."""
    client = _riskcompliance_sweep_client(admin_user)
    policy_b = _riskcompliance_policy_for(tenant_b, "Globex Code of Conduct", admin_b)
    url = reverse("procurement:policyattestation_create")
    due = (_riskcompliance_today() + _riskcompliance_days(10)).isoformat()

    foreign_policy = client.post(url, {"policy": str(policy_b.pk),
                                       "user": str(riskcompliance_member_a.pk), "due_on": due})
    assert foreign_policy.status_code == 200
    assert "policy" in foreign_policy.context["form"].errors

    foreign_user = client.post(url, {"policy": str(riskcompliance_policy_published.pk),
                                     "user": str(admin_b.pk), "due_on": due})
    assert foreign_user.status_code == 200
    assert "user" in foreign_user.context["form"].errors

    assert PolicyAttestation.objects.count() == 0

    # L44 pair: the same POST with both pks from THIS workspace does save.
    ok = client.post(url, {"policy": str(riskcompliance_policy_published.pk),
                           "user": str(riskcompliance_member_a.pk), "due_on": due})
    assert ok.status_code == 302
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_screening_block_refuses_a_suspension_it_cannot_resolve(
        client_a, riskcompliance_screening_open, riskcompliance_screening_disposed):
    """``screening_block`` resolves its optional suspension scoped to tenant AND to this party.

    A pk that does not resolve ABORTS the whole POST rather than being silently dropped: a block
    linked to nothing would be a decision with no stated basis. The screening must still be
    ``pending_review`` afterwards - the L35 shape, where an absent prerequisite must be REJECTED
    and never fall through to the approval.
    """
    before = _riskcompliance_snapshot(riskcompliance_screening_open, "status", "suspension_id",
                                      "decided_at", "decision_note")
    url = reverse("procurement:screening_block", args=[riskcompliance_screening_open.pk])

    # A well-formed pk that resolves to nothing ABORTS the whole POST: the screening is still
    # undecided and nothing was linked.
    response = client_a.post(url, {"note": "Confirmed SDN match.", "suspension": "999999"})
    assert response.status_code == 302
    _riskcompliance_assert_unchanged(riskcompliance_screening_open, before)
    assert riskcompliance_screening_open.status == "pending_review"
    assert any("not on file for this supplier" in message
               for message in _riskcompliance_messages(response))

    # ...and with no note at all nothing is decided either, whatever the suspension said.
    third = client_a.post(url, {"note": "   ", "suspension": "999999"})
    assert third.status_code == 302
    _riskcompliance_assert_unchanged(riskcompliance_screening_open, before)

    # An UNPARSEABLE pk is a different statement: ``as_db_int`` reads "abc" / a superscript / a
    # 20-digit value as "no suspension was named at all", so the block is recorded UNLINKED
    # rather than aborted. Pinned here because the two shapes diverge - what matters either way
    # is that no link is ever forged and the note is still required.
    second = client_a.post(
        reverse("procurement:screening_block", args=[riskcompliance_screening_disposed.pk]),
        {"note": "Confirmed SDN match.", "suspension": "abc"})
    assert second.status_code == 302
    riskcompliance_screening_disposed.refresh_from_db()
    assert riskcompliance_screening_disposed.status == "blocked"
    assert riskcompliance_screening_disposed.suspension_id is None


# ================================================================= 8. XSS / escaping

_RISKCOMPLIANCE_XSS = "<script>alert(1)</script>"
_RISKCOMPLIANCE_QUOTE = "O'Brien & Sons \"Ltd\""


def _riskcompliance_assert_escaped(response, url_name):
    """The raw tag never reaches the page, and the escaped one proves the field DID render."""
    assert response.status_code == 200, f"{url_name} -> {response.status_code}"
    html = _riskcompliance_html(response)
    assert _RISKCOMPLIANCE_XSS not in html, f"{url_name} rendered a raw <script> tag"
    assert "<script>alert" not in html, f"{url_name} rendered a raw <script> tag"
    assert "&lt;script&gt;" in html, (
        f"{url_name} returned 200 but never rendered the field under test - "
        f"the escaping assertion above would have been vacuous (L8)")
    # The apostrophe matters because confirm() handlers live on these pages (L42).
    assert "O'Brien" not in html, f"{url_name} rendered a raw apostrophe"
    assert "O&#x27;Brien" in html, f"{url_name} did not render the apostrophe field"


def test_riskcompliance_screening_and_hit_free_text_is_escaped(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    """``notes`` on the screening and ``matched_name`` / ``remarks`` on the hit."""
    screening = ComplianceScreening.objects.create(
        tenant=tenant_a, party=riskcompliance_party_a, list_source="csl_consolidated",
        checkpoint="onboarding", method="manual_lookup", screened_on=_riskcompliance_today(),
        list_as_of=_riskcompliance_today() - _riskcompliance_days(1),
        reference="CSL-XSS-0001", result="potential_match", match_threshold=85,
        threshold_rationale="Default fuzzy threshold.", screened_by=admin_user,
        notes=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}")
    hit = ScreeningHit.objects.create(
        screening=screening, matched_name=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}",
        matched_list="ofac_sdn", match_score=96, match_type="name",
        remarks=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}")

    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:screening_detail", args=[screening.pk])),
        "screening_detail")
    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:screeninghit_detail", args=[hit.pk])),
        "screeninghit_detail")
    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:screeninghit_list")), "screeninghit_list")


def test_riskcompliance_risksignal_free_text_is_escaped(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    """``source_ref`` and ``notes`` - both typed by hand off a provider report."""
    signal = _riskcompliance_signal_for(
        tenant_a, riskcompliance_party_a, admin_user,
        source_ref=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}",
        notes=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}")

    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:risksignal_detail", args=[signal.pk])),
        "risksignal_detail")


def test_riskcompliance_fraudalert_free_text_is_escaped(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    """``detail`` and ``matched_on`` - the sentence the rule wrote and the masked attribute."""
    alert = _riskcompliance_alert_for(
        tenant_a, riskcompliance_party_a, admin_user,
        detail=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}",
        matched_on=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}")

    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:fraudalert_detail", args=[alert.pk])),
        "fraudalert_detail")
    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:fraudalert_list")), "fraudalert_list")


def test_riskcompliance_auditseal_note_and_trail_target_are_escaped(
        client_a, tenant_a, admin_user):
    """The seal ``note`` and the audit ``target``, on the two pages an auditor actually opens."""
    _riskcompliance_audit_row(tenant_a, admin_user,
                              target=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}")
    seal = _riskcompliance_seal_for(tenant_a, admin_user,
                                    note=f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}")

    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:audit_trail")), "audit_trail")
    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:auditseal_detail", args=[seal.pk])),
        "auditseal_detail")
    # The seal REGISTER prints the number, the covered range and the digest - never the note
    # (it appears there only as a search placeholder), so only the negative half applies: there
    # is no rendered field on that page for the escaped-presence assertion to chase.
    register = client_a.get(reverse("procurement:auditseal_list"))
    assert register.status_code == 200
    assert _RISKCOMPLIANCE_XSS not in _riskcompliance_html(register)


def test_riskcompliance_attestation_notes_are_escaped(
        client_a, riskcompliance_attestation_pending, riskcompliance_member_a):
    """The acknowledgement note is typed by the signer and rendered back on the detail page."""
    row = riskcompliance_attestation_pending
    signer = _riskcompliance_login(riskcompliance_member_a)
    signer.post(reverse("procurement:attestation_sign", args=[row.pk]),
                {"note": f"{_RISKCOMPLIANCE_XSS} {_RISKCOMPLIANCE_QUOTE}"})
    row.refresh_from_db()
    assert row.status == "acknowledged"

    _riskcompliance_assert_escaped(
        client_a.get(reverse("procurement:policyattestation_detail", args=[row.pk])),
        "policyattestation_detail")


def test_riskcompliance_a_hostile_search_term_is_echoed_escaped(
        client_a, riskcompliance_screening_open):
    """``q`` is echoed back into the filter bar's ``value=`` attribute on every register."""
    for url_name in ("screening_list", "screeninghit_list", "risksignal_list", "fraudalert_list",
                     "policyattestation_list", "policy_list", "audit_trail"):
        response = client_a.get(reverse(f"procurement:{url_name}"),
                                {"q": f'{_RISKCOMPLIANCE_XSS}" autofocus onfocus="alert(1)'})
        assert response.status_code == 200, url_name
        html = _riskcompliance_html(response)
        assert _RISKCOMPLIANCE_XSS not in html, f"{url_name} echoed a raw <script> tag"
        assert 'onfocus="alert(1)' not in html, f"{url_name} broke out of the value attribute"


# ================================================================= 9a. CSV injection

def test_riskcompliance_audit_trail_export_neutralises_formula_cells(
        client_a, tenant_a, admin_user):
    """Excel EXECUTES a cell that opens ``=``, ``+``, ``-`` or ``@`` - including behind a TAB.

    Every cell in the export goes through ``csv_safe``, which prefixes an apostrophe and changes
    nothing else. Parsed with ``csv.reader`` rather than string-matched, so the assertion is
    about the CELL and not about a substring that happened to appear somewhere in the file.
    """
    hostile_targets = ["=cmd|'/c calc'!A1", "+1+1", "-2+3", "@SUM(1+1)", "\t=1+1", "\r=1+1"]
    for target in hostile_targets:
        _riskcompliance_audit_row(tenant_a, admin_user, target=target)
    # The user label is user-authored too, and lands in its own column.
    formula_user = _riskcompliance_new_user(tenant_a, "calc@acme.com", "calc_acme")
    formula_user.first_name = "=cmd|'/c calc'!A1"
    formula_user.last_name = "Payload"
    formula_user.save(update_fields=["first_name", "last_name"])
    _riskcompliance_audit_row(tenant_a, formula_user, target="A plain target")

    response = client_a.get(reverse("procurement:audit_trail_export"))
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"

    rows = list(csv.reader(io.StringIO(response.content.decode())))
    assert rows[0][0] == "Entry"

    dangerous = ("=", "+", "-", "@", "\t", "\r")
    offenders = [(index, cell) for index, row in enumerate(rows) for cell in row
                 if cell[:1] in dangerous]
    assert offenders == [], f"un-neutralised formula cells reached the CSV: {offenders}"

    # ...and the neutralised values are all still THERE - escaping must not drop data.
    body = response.content.decode()
    for target in hostile_targets:
        assert f"'{target}" in body, f"{target!r} was dropped rather than neutralised"
    assert "'=cmd|'/c calc'!A1 Payload" in body


def test_riskcompliance_export_rows_match_the_page_after_a_junk_filter(
        client_a, tenant_a, admin_user):
    """One implementation behind both, so a junk filter must narrow neither - or both."""
    _riskcompliance_audit_row(tenant_a, admin_user, target="Acme screening SCR-00001")

    page = client_a.get(reverse("procurement:audit_trail"), {"user": "abc", "action": "junk"})
    export = client_a.get(reverse("procurement:audit_trail_export"),
                          {"user": "abc", "action": "junk"})

    assert page.status_code == 200
    assert export.status_code == 200
    assert "Acme screening SCR-00001" in _riskcompliance_html(page)
    assert "Acme screening SCR-00001" in export.content.decode()


# ================================================================= 9b. the tenant-less user

def test_riskcompliance_audit_views_refuse_a_tenantless_superuser(tenant_a, admin_user):
    """``core.AuditLog.tenant`` is NULLABLE, so ``filter(tenant=None)`` is not an empty queryset.

    It is every unattributed audit row in the installation - a cross-workspace read on the one
    register that exists to prove who did what. The guard is therefore a REFUSAL with a sentence
    rather than the house "renders empty" convention, and this test exists to keep it that way.
    """
    _riskcompliance_audit_row(tenant_a, admin_user, target="Acme screening SCR-00001")
    # An unattributed row - exactly what a ``tenant=None`` filter would hand back.
    AuditLog.objects.create(
        tenant=None, user=None, action="delete", target="UNATTRIBUTED - another workspace",
        content_type=ContentType.objects.get_for_model(ComplianceScreening), object_id=1)

    root = _riskcompliance_new_superuser()
    assert root.tenant_id is None
    client = _riskcompliance_sweep_client(root)

    for url_name in ("audit_trail", "audit_trail_export"):
        response = client.get(reverse(f"procurement:{url_name}"))
        assert response.status_code == 302, f"{url_name} -> {response.status_code}"
        assert response["Location"] == reverse("dashboard:home"), url_name
        assert any("Select a tenant workspace" in message
                   for message in _riskcompliance_messages(response)), url_name

    # Following the redirect must not render either row anywhere either.
    landing = client.get(reverse("procurement:audit_trail"), follow=True)
    html = _riskcompliance_html(landing)
    assert "UNATTRIBUTED - another workspace" not in html
    assert "Acme screening SCR-00001" not in html


def test_riskcompliance_tenantless_superuser_cannot_seal_or_sign_anything(tenant_a, admin_user):
    """The same guard on the write verbs: no workspace, no seal, no exemption, no roster."""
    seal = _riskcompliance_seal_for(tenant_a, admin_user)
    policy = _riskcompliance_policy_for(tenant_a, "Acme Code of Conduct", admin_user)
    attestation = _riskcompliance_attestation_for(policy, admin_user)
    seal_count = AuditSeal.objects.count()
    attestation_count = PolicyAttestation.objects.count()
    before = _riskcompliance_snapshot(seal, "last_verify_ok", "last_verified_at")

    root = _riskcompliance_new_superuser()
    client = _riskcompliance_sweep_client(root)

    failures = _riskcompliance_sweep(client, [
        ("auditseal_create", [], "post", {"note": "Sealed by nobody's workspace."}),
        ("auditseal_verify", [seal.pk], "post", {}),
        ("attestation_exempt", [attestation.pk], "post", {"reason": "Root said so."}),
        ("attestation_sign", [attestation.pk], "post", {"note": "Root said so."}),
    ], expected=302)

    assert failures == [], f"a tenant-less write verb did not redirect: {failures}"
    assert AuditSeal.objects.count() == seal_count
    assert PolicyAttestation.objects.count() == attestation_count
    _riskcompliance_assert_unchanged(seal, before)
    attestation.refresh_from_db()
    assert attestation.status == "pending"
    assert attestation.exempt_reason == ""


def test_riskcompliance_tenantless_superuser_is_refused_by_every_6_17_register(
        tenant_a, riskcompliance_screening_open, riskcompliance_signal_fhr,
        riskcompliance_fraud_open, riskcompliance_attestation_pending,
        riskcompliance_policy_published, riskcompliance_seal):
    """Every 6.17 register refuses a tenant-less user outright rather than rendering empty.

    Stronger than the app-wide "renders empty" convention and deliberately so: an empty
    compliance register is indistinguishable from a workspace with nothing to answer for, and on
    THESE pages that difference is the whole point. Each one redirects to the dashboard with a
    sentence, and no row from any workspace reaches the response.
    """
    root = _riskcompliance_new_superuser()
    assert root.tenant_id is None
    client = _riskcompliance_sweep_client(root)

    marks = (riskcompliance_screening_open.number, riskcompliance_signal_fhr.number,
             riskcompliance_fraud_open.number, riskcompliance_policy_published.title,
             riskcompliance_seal.number)

    for url_name in ("screening_list", "screeninghit_list", "risksignal_list", "fraudalert_list",
                     "policyattestation_list", "policy_list", "policy_overdue_board",
                     "auditseal_list", "audit_trail", "screening_rescreen_board",
                     "risksignal_refresh_board", "fraud_board", "fraud_scan"):
        response = client.get(reverse(f"procurement:{url_name}"))
        assert response.status_code == 302, f"{url_name} -> {response.status_code}"
        assert response["Location"] == reverse("dashboard:home"), url_name
        html = _riskcompliance_html(client.get(reverse(f"procurement:{url_name}"), follow=True))
        for mark in marks:
            assert mark not in html, f"{url_name} leaked {mark!r} to a tenant-less user"

    # ``policy_mine`` is the ONE documented exception (L32): it answers "what do I personally
    # owe", so bouncing somebody off it would read as "you owe nothing". It renders 200 for every
    # logged-in user - and for this one the isolation assertion is the EMPTY roster, because the
    # page is scoped by ``user=request.user`` as well as by tenant.
    mine = client.get(reverse("procurement:policy_mine"))
    assert mine.status_code == 200
    assert mine.context["rows"] == []
    assert mine.context["stats"] == {"pending": 0, "overdue": 0, "signed": 0}
    mine_html = _riskcompliance_html(mine)
    for mark in marks:
        assert mark not in mine_html, f"policy_mine leaked {mark!r} to a tenant-less user"


# ================================================================= 10. oversized free text
#
# Every one of these fields arrives from a browser and lands in a bounded column. An uncapped
# value is not an XSS - it is a 500 from the database driver on a route anybody can POST to, and
# on this module that route is an evidence-writing one.

def test_riskcompliance_an_oversized_sign_off_note_is_capped_not_fatal(
        riskcompliance_member_a, riskcompliance_attestation_pending):
    """``attestation_sign`` truncates at ``MAX_NOTE_LENGTH`` rather than 500ing on the insert."""
    row = riskcompliance_attestation_pending
    client = _riskcompliance_sweep_client(riskcompliance_member_a)

    response = client.post(reverse("procurement:attestation_sign", args=[row.pk]),
                           {"note": "z" * 20000})

    assert response.status_code == 302
    row.refresh_from_db()
    assert row.status == "acknowledged"
    assert len(row.acknowledgement_note) <= 2000
    assert row.acknowledgement_note == "z" * len(row.acknowledgement_note)


def test_riskcompliance_an_oversized_exemption_reason_is_refused_not_fatal(
        client_a, riskcompliance_attestation_pending):
    """``exempt_reason`` is a ``CharField(255)``; an over-long one is a MESSAGE, not a 500.

    Refused rather than silently truncated, and rightly: an exemption cut off half way through a
    sentence is the one record nobody can reconstruct months later.
    """
    row = riskcompliance_attestation_pending
    before = _riskcompliance_snapshot(row, "status", "exempt_reason", "exempted_at")

    response = client_a.post(reverse("procurement:attestation_exempt", args=[row.pk]),
                             {"reason": "z" * 20000})

    assert response.status_code == 302
    _riskcompliance_assert_unchanged(row, before)
    assert row.status == "pending"
    assert any("Shorten it" in message for message in _riskcompliance_messages(response))

    # L44 pair: a reason of a sane length is accepted.
    ok = client_a.post(reverse("procurement:attestation_exempt", args=[row.pk]),
                       {"reason": "On long-term leave until March."})
    assert ok.status_code == 302
    row.refresh_from_db()
    assert row.status == "exempt"
    assert row.exempt_reason == "On long-term leave until March."


def test_riskcompliance_an_oversized_seal_note_is_refused_and_seals_nothing(
        client_a, tenant_a, admin_user):
    """``AuditSealForm`` validates the note; a refused form must not mint a chain link."""
    _riskcompliance_audit_row(tenant_a, admin_user)
    before = AuditSeal.objects.filter(tenant=tenant_a).count()

    response = client_a.post(reverse("procurement:auditseal_create"), {"note": "z" * 20000})

    assert response.status_code == 302
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == before
    assert _riskcompliance_messages(response) != []

    # L44 pair: a sane note seals the range.
    ok = client_a.post(reverse("procurement:auditseal_create"), {"note": "Month-end close."})
    assert ok.status_code == 302
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == before + 1


def test_riskcompliance_a_junk_review_action_is_refused_and_moves_nothing(
        client_a, riskcompliance_signal_fhr):
    """L35: an unrecognised POSTed action must be REJECTED, never fall through to a decision.

    The action is checked BEFORE the note, so a junk action with no note gets the accurate
    message rather than a misleading one about the missing note - and the signal stays new.
    """
    row = riskcompliance_signal_fhr
    before = _riskcompliance_snapshot(row, "review_status", "review_note", "reviewed_at",
                                      "reviewed_by_id")
    url = reverse("procurement:risksignal_review", args=[row.pk])

    # NB "reviewed " is deliberately NOT in this list: the view strips the POSTed value before
    # matching it, so a stray space is tolerated on purpose. Case is not - "REVIEWED" is junk.
    for junk in ("", "approve", "REVIEWED", "actioned; dismissed", "reviewed,actioned",
                 _RISKCOMPLIANCE_SUPERSCRIPT_TWO):
        response = client_a.post(url, {"action": junk, "review_note": "x"})
        assert response.status_code == 302, f"{junk!r} -> {response.status_code}"
        _riskcompliance_assert_unchanged(row, before)

    # ...and a terminal action with NO note is refused too - a closure with no stated reasoning
    # is indistinguishable from a signal nobody looked at.
    response = client_a.post(url, {"action": "dismissed", "review_note": "   "})
    assert response.status_code == 302
    _riskcompliance_assert_unchanged(row, before)

    # L44 pair: the real action, with the note it requires, does move the row.
    ok = client_a.post(url, {"action": "actioned", "review_note": "Escalated to category."})
    assert ok.status_code == 302
    row.refresh_from_db()
    assert row.review_status == "actioned"


def test_riskcompliance_a_junk_disposition_is_refused_and_moves_nothing(
        client_a, riskcompliance_hit_open, riskcompliance_fraud_open):
    """The same L35 shape on the two adjudication verbs: no note, no unknown value, no fallthrough.

    ``open`` is the value to watch on the hit picker - it is a real ``DISPOSITION_CHOICES`` member
    and must still be refused here, because the picker offers only the TERMINAL ones. A form that
    accepted it would let somebody "adjudicate" a hit back to undecided.
    """
    hit_before = _riskcompliance_snapshot(riskcompliance_hit_open, "disposition",
                                          "disposition_note", "disposed_at")
    alert_before = _riskcompliance_snapshot(riskcompliance_fraud_open, "status",
                                            "resolution_note", "resolved_at")
    hit_url = reverse("procurement:screeninghit_dispose", args=[riskcompliance_hit_open.pk])
    alert_url = reverse("procurement:fraudalert_disposition",
                        args=[riskcompliance_fraud_open.pk])

    for payload in ({"disposition": "open", "disposition_note": "Back to undecided."},
                    {"disposition": "not_a_value", "disposition_note": "x"},
                    {"disposition": "true_match", "disposition_note": "   "},
                    {"disposition_note": "No disposition at all."},
                    {}):
        response = client_a.post(hit_url, payload)
        assert response.status_code == 302, payload
        _riskcompliance_assert_unchanged(riskcompliance_hit_open, hit_before)

    for payload in ({"action": "not_a_value", "resolution_note": "x"},
                    {"action": "substantiate", "resolution_note": "  "},
                    {"resolution_note": "No action at all."},
                    {}):
        response = client_a.post(alert_url, payload)
        assert response.status_code == 302, payload
        _riskcompliance_assert_unchanged(riskcompliance_fraud_open, alert_before)

    # L44 pair: both verbs still work when the POST is a real one.
    assert client_a.post(hit_url, _riskcompliance_dispose_payload()).status_code == 302
    riskcompliance_hit_open.refresh_from_db()
    assert riskcompliance_hit_open.disposition == "false_positive"


def test_riskcompliance_clearing_a_screening_with_open_hits_is_refused(
        client_a, riskcompliance_screening_open, riskcompliance_screening_disposed):
    """L35 again, and the gate that matters most here: no clearance over an unadjudicated hit.

    The refusal is made by ASKING THE DATABASE (``hits.filter(disposition="open").exists()``),
    not by reading the ``open_hit_count`` badge - a stale counter must never unlock a clearance.
    This test forces the two apart by corrupting the badge to zero and asserting the gate still
    holds.
    """
    ComplianceScreening.objects.filter(pk=riskcompliance_screening_open.pk).update(
        open_hit_count=0, hit_count=0)
    before = _riskcompliance_snapshot(riskcompliance_screening_open, "status", "decided_at")

    response = client_a.post(
        reverse("procurement:screening_clear", args=[riskcompliance_screening_open.pk]),
        {"note": "Looks fine to me."})

    assert response.status_code == 302
    _riskcompliance_assert_unchanged(riskcompliance_screening_open, before)
    assert riskcompliance_screening_open.status == "pending_review"

    # L44 pair: the screening whose hits ARE all adjudicated does clear.
    ok = client_a.post(
        reverse("procurement:screening_clear", args=[riskcompliance_screening_disposed.pk]),
        {"note": "Every hit adjudicated as a false positive."})
    assert ok.status_code == 302
    riskcompliance_screening_disposed.refresh_from_db()
    assert riskcompliance_screening_disposed.status == "cleared"
