"""Procurement 6.17 Risk & Compliance Management - view / CRUD integration flows.

Everything here drives the real URLconf, the real views and the real templates. The lanes next
door already cover the models (``test_riskcompliance_models.py``) and the forms
(``test_riskcompliance_forms.py``); security, permissions and cross-tenant IDOR are a separate
lane again and are deliberately NOT in this file.

What this lane is actually for, in priority order:

1. **Rendered rows, not status codes.** A wrong context key or a mis-typed row-dict key returns
   **200** and renders a grid of em-dashes (L8 / L41 S1). Every register and every board here is
   asserted on a seeded record's own identifier reaching the HTML, and every page whose context
   is a list of dicts has its key set pinned AND one real value chased into the markup.
2. **The write paths and the state machines**, driven over HTTP as a logged-in tenant admin and
   asserted on the resulting ROW STATE rather than on the redirect.
3. **Valid filter values return the right ROWS** (L44) - each closed-vocabulary value, each FK
   filter and each declared search field.
4. **Query budgets** on the four registers/boards the performance pass fixed, built with the row
   shape that HIDES the N+1 when it is absent (all ``reviewed_by`` set, all ``resolved_by`` set,
   all ``exempt``) so a regression cannot slip back in unnoticed.
5. **Pagination** with a deliberate TIE on the primary sort column - the exact shape of the
   ``_policy_qs`` ordering defect that was found and fixed.
6. **CSV export** parsed with ``csv.reader``, not string-matched.

House rules followed here: every reference date derives from ``timezone.localdate()`` /
``timezone.now()`` and never ``date.today()`` (L16); every assertion states an expected VALUE or
COUNT rather than truthiness; every URL goes through ``reverse("procurement:<name>")``.

Every test is ``test_riskcompliance_*`` and every module-level helper ``_riskcompliance_*`` so
the sibling 6.17 lanes and any later sub-module appending nearby cannot shadow them (L41 S2 /
L47).
"""
import csv
import datetime
import io
from decimal import Decimal

import pytest

from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party, PartyRole
from apps.procurement.models import (
    ComplianceScreening,
    FraudAlert,
    PolicyAttestation,
    ProcurementPolicy,
    ScreeningHit,
    SupplierRiskSignal,
)

pytestmark = pytest.mark.django_db


# ================================================================== helpers

def _riskcompliance_today():
    """The one date basis for every window here - never ``date.today()`` (L16)."""
    return timezone.localdate()


def _riskcompliance_days(count):
    return datetime.timedelta(days=count)


def _riskcompliance_html(response):
    return response.content.decode()


def _riskcompliance_pks(response):
    return [obj.pk for obj in response.context["object_list"]]


def _riskcompliance_messages(response):
    """Works on a 302 too - the storage hangs off the request, not the context."""
    return [str(message) for message in get_messages(response.wsgi_request)]


def _riskcompliance_templates(response):
    return [name for name in (t.name for t in response.templates) if name]


def _riskcompliance_key_sets(rows):
    """The distinct key sets across every row-dict in ``rows`` - one entry when they agree."""
    return {frozenset(row) for row in rows}


def _riskcompliance_count_queries(client, url, params=None):
    """Queries for ONE GET of ``url``, the whole request/response cycle included.

    Used alongside ``django_assert_max_num_queries`` rather than instead of it. The ceiling says
    "this page is cheap"; comparing two counts taken at DIFFERENT ROW COUNTS says "and its cost
    does not grow with the table", which is the actual N+1 property and is immune to every fixed
    overhead in the stack - including the three-query session write
    (``SAVEPOINT`` / ``UPDATE django_session`` / ``RELEASE``) that
    ``apps.core.middleware`` performs on every authenticated request when it stamps
    ``_last_activity``.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as captured:
        response = client.get(url, params or {})
    assert response.status_code == 200
    return len(captured)


# -- master data ---------------------------------------------------------------------------------

def _riskcompliance_supplier(party, role="supplier"):
    """Give a ``core.Party`` the role the 6.17 dropdowns and boards narrow on.

    ``_screenable_parties`` / ``_monitorable_parties`` / ``_suppliers`` all filter
    ``roles__role__in=("supplier", "vendor")``, so a bare Party is invisible to every one of them.
    The shared conftest parties deliberately carry no role, so each board test opts in here.
    """
    PartyRole.objects.create(tenant=party.tenant, party=party, role=role, status="active")
    return party


def _riskcompliance_party_named(tenant, name, kind="organization"):
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _riskcompliance_person(tenant, email, username):
    from apps.accounts.models import User

    return User.objects.create_user(email=email, username=username, password="TestPass123!",
                                    tenant=tenant, is_tenant_admin=False)


# -- 6.17 rows -----------------------------------------------------------------------------------

def _riskcompliance_new_screening(tenant, party, user=None, **overrides):
    """One ``ComplianceScreening``, always ``pending_review`` (``status`` is editable=False)."""
    fields = dict(
        tenant=tenant, party=party, list_source="csl_consolidated", checkpoint="onboarding",
        method="manual_lookup", screened_on=_riskcompliance_today(),
        list_as_of=_riskcompliance_today() - _riskcompliance_days(1),
        reference="CSL-VIEWS-0001", result="clear", match_threshold=85,
        threshold_rationale="Default fuzzy threshold.", screened_by=user, notes="")
    fields.update(overrides)
    return ComplianceScreening.objects.create(**fields)


def _riskcompliance_new_hit(screening, matched_name, score=90, **overrides):
    fields = dict(screening=screening, matched_name=matched_name, matched_list="ofac_sdn",
                  match_score=score, match_type="name", entry_reference="SDN-00001",
                  program="UKRAINE-EO13662", country="Cyprus", remarks="")
    fields.update(overrides)
    return ScreeningHit.objects.create(**fields)


def _riskcompliance_new_signal(tenant, party, metric="fhr", value="82.00",
                               provider="rapidratings", days_ago=0, user=None, **overrides):
    observed = _riskcompliance_today() - _riskcompliance_days(days_ago)
    fields = dict(tenant=tenant, party=party, provider=provider, metric=metric,
                  value=Decimal(value), observed_on=observed,
                  next_refresh_on=observed + _riskcompliance_days(90),
                  source_ref="Provider report page 2.", captured_by=user, notes="")
    fields.update(overrides)
    return SupplierRiskSignal.objects.create(**fields)


def _riskcompliance_new_alert(tenant, vendor, rule="new_vendor_rush", severity="medium",
                              amount="1000.00", **overrides):
    fields = dict(tenant=tenant, vendor=vendor, rule=rule, severity=severity,
                  document_date=_riskcompliance_today() - _riskcompliance_days(3),
                  amount=Decimal(amount), detail="Raised by hand for a view test.",
                  matched_on="")
    fields.update(overrides)
    return FraudAlert.objects.create(**fields)


def _riskcompliance_new_policy(tenant, title, user=None, published=True, requires_ack=True,
                               **overrides):
    fields = dict(tenant=tenant, title=title, policy_type="supplier_code_of_conduct",
                  summary="What buyers and suppliers are held to.", body="Read it.",
                  version_number="1.0", status="draft",
                  effective_from=_riskcompliance_today() - _riskcompliance_days(7),
                  requires_acknowledgment=requires_ack, owner=user, created_by=user)
    fields.update(overrides)
    policy = ProcurementPolicy.objects.create(**fields)
    if published:
        policy.status = "published"
        policy.published_at = timezone.now()
        policy.save(update_fields=["status", "published_at", "updated_at"])
    return policy


def _riskcompliance_new_attestation(policy, user, due_in_days=10):
    return PolicyAttestation.objects.create(
        tenant=policy.tenant, policy=policy, user=user,
        due_on=_riskcompliance_today() + _riskcompliance_days(due_in_days))


def _riskcompliance_new_audit_row(tenant, user, action="update", target="Screening SCR-00001"):
    """One ``core.AuditLog`` row the PROCUREMENT trail actually shows.

    ``procurement_activity_qs`` narrows to ``content_type__app_label="procurement"`` (plus a
    named subset of scm), so a row with a NULL content type is invisible on the trail page - the
    conftest seal fixture builds exactly that shape on purpose, and this helper builds the other.
    """
    return AuditLog.objects.create(
        tenant=tenant, user=user, action=action, target=target,
        content_type=ContentType.objects.get_for_model(ComplianceScreening), object_id=1,
        changes={"note": ["before", "after"]})


# ================================================================== screening register

def test_riskcompliance_screening_list_renders_the_seeded_row_and_its_context(
        client_a, riskcompliance_screening_open, riskcompliance_screening_cleared):
    resp = client_a.get(reverse("procurement:screening_list"))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert "procurement/riskcompliance/screening/list.html" in _riskcompliance_templates(resp)
    # The row REACHED the page - not merely a 200 over a grid of em-dashes (L8).
    assert riskcompliance_screening_open.number in html
    assert riskcompliance_screening_cleared.number in html
    assert "Northwind Components Ltd" in html

    assert set(_riskcompliance_pks(resp)) == {riskcompliance_screening_open.pk,
                                              riskcompliance_screening_cleared.pk}
    assert len(resp.context["list_source_choices"]) == 13
    assert len(resp.context["checkpoint_choices"]) == 6
    assert len(resp.context["result_choices"]) == 4
    assert len(resp.context["status_choices"]) == 4
    assert resp.context["stats"] == {"pending": 1, "blocked": 0, "rescreen_due": 0,
                                     "open_hits": 2}
    assert resp.context["is_admin"] is True
    assert resp.context["retention_note"] == ComplianceScreening.RETENTION_NOTE


def test_riskcompliance_screening_list_search_matches_each_declared_field(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    by_reference = _riskcompliance_new_screening(
        tenant_a, riskcompliance_party_a, admin_user, reference="CSL-SEARCH-777")
    by_note = _riskcompliance_new_screening(
        tenant_a, riskcompliance_party_a, admin_user, reference="CSL-OTHER-001",
        notes="Escalated by the treasury desk")
    url = reverse("procurement:screening_list")

    assert _riskcompliance_pks(client_a.get(url, {"q": "CSL-SEARCH-777"})) == [by_reference.pk]
    assert _riskcompliance_pks(client_a.get(url, {"q": "treasury desk"})) == [by_note.pk]
    assert _riskcompliance_pks(client_a.get(url, {"q": by_reference.number})) == [by_reference.pk]
    assert set(_riskcompliance_pks(client_a.get(url, {"q": "Northwind"}))) == {
        by_reference.pk, by_note.pk}


def test_riskcompliance_screening_list_each_valid_filter_value_returns_its_rows(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    other_party = _riskcompliance_party_named(tenant_a, "Contoso Fasteners")
    onboarding = _riskcompliance_new_screening(
        tenant_a, riskcompliance_party_a, admin_user, checkpoint="onboarding",
        list_source="csl_consolidated", result="clear", reference="F-1")
    pre_award = _riskcompliance_new_screening(
        tenant_a, other_party, admin_user, checkpoint="pre_award",
        list_source="eu_consolidated", result="potential_match", reference="F-2")
    url = reverse("procurement:screening_list")

    assert _riskcompliance_pks(client_a.get(url, {"checkpoint": "onboarding"})) == [onboarding.pk]
    assert _riskcompliance_pks(client_a.get(url, {"checkpoint": "pre_award"})) == [pre_award.pk]
    assert _riskcompliance_pks(
        client_a.get(url, {"list_source": "csl_consolidated"})) == [onboarding.pk]
    assert _riskcompliance_pks(
        client_a.get(url, {"list_source": "eu_consolidated"})) == [pre_award.pk]
    assert _riskcompliance_pks(client_a.get(url, {"result": "clear"})) == [onboarding.pk]
    assert _riskcompliance_pks(
        client_a.get(url, {"result": "potential_match"})) == [pre_award.pk]
    # Both are pending_review - status only ever moves through a decision verb.
    assert set(_riskcompliance_pks(client_a.get(url, {"status": "pending_review"}))) == {
        onboarding.pk, pre_award.pk}
    assert _riskcompliance_pks(client_a.get(url, {"status": "cleared"})) == []
    assert _riskcompliance_pks(
        client_a.get(url, {"party": str(other_party.pk)})) == [pre_award.pk]


def test_riskcompliance_screening_list_paginates_with_a_tie_on_the_sort_column(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    """20 rows all screened on the SAME day - the tie a partial ordering loses rows on."""
    same_day = _riskcompliance_today()
    made = [_riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                          screened_on=same_day, reference=f"TIE-{index:03d}")
            for index in range(20)]
    url = reverse("procurement:screening_list")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert len(_riskcompliance_pks(page_one)) == 15
    assert len(_riskcompliance_pks(page_two)) == 5
    seen = _riskcompliance_pks(page_one) + _riskcompliance_pks(page_two)
    assert len(seen) == 20
    assert len(set(seen)) == 20
    assert set(seen) == {row.pk for row in made}


def test_riskcompliance_screening_detail_renders_hits_and_the_allowed_verbs(
        client_a, riskcompliance_screening_open, riskcompliance_hit_open):
    resp = client_a.get(reverse("procurement:screening_detail",
                                args=[riskcompliance_screening_open.pk]))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert riskcompliance_screening_open.number in html
    assert "NORTHWIND COMPONENTS LLC" in html
    assert len(resp.context["hits"]) == 2
    assert len(resp.context["open_hits"]) == 2
    # Clear is WITHHELD while a hit is open; escalate and block remain.
    assert [action["key"] for action in resp.context["allowed_actions"]] == ["escalate", "block"]
    assert resp.context["blocking_suspensions"] == []
    assert len(resp.context["disposition_choices"]) == 3
    assert resp.context["is_admin"] is True


def test_riskcompliance_screening_detail_offers_clear_once_every_hit_is_disposed(
        client_a, riskcompliance_screening_disposed):
    resp = client_a.get(reverse("procurement:screening_detail",
                                args=[riskcompliance_screening_disposed.pk]))

    assert resp.status_code == 200
    assert len(resp.context["open_hits"]) == 0
    assert [action["key"] for action in resp.context["allowed_actions"]] == [
        "clear", "escalate", "block"]


def test_riskcompliance_screening_create_post_saves_against_the_request_tenant(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    # The form's ``party`` field narrows to suppliers/vendors, so the role is a precondition.
    _riskcompliance_supplier(riskcompliance_party_a)
    today = _riskcompliance_today()
    resp = client_a.post(reverse("procurement:screening_create"), {
        "party": str(riskcompliance_party_a.pk),
        "list_source": "ofac_sdn",
        "checkpoint": "pre_po",
        "method": "manual_lookup",
        "screened_on": today.isoformat(),
        "list_as_of": (today - _riskcompliance_days(1)).isoformat(),
        "reference": "CSL-CREATE-0001",
        "result": "clear",
        "match_threshold": "90",
        "threshold_rationale": "House threshold.",
        "notes": "",
    })

    saved = ComplianceScreening.objects.get(reference="CSL-CREATE-0001")
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:screening_detail", args=[saved.pk])
    assert saved.tenant_id == tenant_a.pk
    assert saved.status == "pending_review"
    # screened_by is stamped from the session, never from the payload.
    assert saved.screened_by_id == admin_user.pk
    assert saved.number.startswith("SCR-")


def test_riskcompliance_screening_edit_post_updates_a_pending_row(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    _riskcompliance_supplier(riskcompliance_party_a)
    screening = _riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                              reference="CSL-EDIT-0001")
    today = _riskcompliance_today()

    resp = client_a.post(reverse("procurement:screening_edit", args=[screening.pk]), {
        "party": str(riskcompliance_party_a.pk),
        "list_source": "bis_dpl",
        "checkpoint": "pre_payment",
        "method": "file_upload",
        "screened_on": today.isoformat(),
        "list_as_of": (today - _riskcompliance_days(2)).isoformat(),
        "reference": "CSL-EDIT-0002",
        "result": "potential_match",
        "match_threshold": "80",
        "threshold_rationale": "Lowered for a fuzzy name.",
        "notes": "Amended.",
    })
    screening.refresh_from_db()

    assert resp.status_code == 302
    assert screening.reference == "CSL-EDIT-0002"
    assert screening.list_source == "bis_dpl"
    assert screening.match_threshold == 80


def test_riskcompliance_screening_edit_is_refused_once_decided(
        client_a, riskcompliance_screening_cleared):
    resp = client_a.get(reverse("procurement:screening_edit",
                                args=[riskcompliance_screening_cleared.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:screening_detail",
                                       args=[riskcompliance_screening_cleared.pk])
    assert any("cannot be edited" in message for message in _riskcompliance_messages(resp))


def test_riskcompliance_screening_delete_is_post_only_and_get_deletes_nothing(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    screening = _riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                              reference="CSL-DEL-0001")
    url = reverse("procurement:screening_delete", args=[screening.pk])

    got = client_a.get(url)
    assert got.status_code == 405
    assert ComplianceScreening.objects.filter(pk=screening.pk).count() == 1

    posted = client_a.post(url)
    assert posted.status_code == 302
    assert posted["Location"] == reverse("procurement:screening_list")
    assert ComplianceScreening.objects.filter(pk=screening.pk).count() == 0


# ================================================================== the three decision verbs

def test_riskcompliance_screening_clear_is_refused_while_a_hit_is_open(
        client_a, riskcompliance_screening_open):
    resp = client_a.post(reverse("procurement:screening_clear",
                                 args=[riskcompliance_screening_open.pk]),
                         {"note": "Looks fine to me."})
    riskcompliance_screening_open.refresh_from_db()

    assert resp.status_code == 302
    assert riskcompliance_screening_open.status == "pending_review"
    assert riskcompliance_screening_open.decided_by_id is None
    assert riskcompliance_screening_open.decided_at is None
    messages = _riskcompliance_messages(resp)
    assert any("2 unadjudicated hit(s)" in message for message in messages)


def test_riskcompliance_screening_clear_succeeds_once_every_hit_is_disposed(
        client_a, admin_user, riskcompliance_screening_disposed):
    resp = client_a.post(reverse("procurement:screening_clear",
                                 args=[riskcompliance_screening_disposed.pk]),
                         {"note": "Both hits are false positives."})
    riskcompliance_screening_disposed.refresh_from_db()

    assert resp.status_code == 302
    assert riskcompliance_screening_disposed.status == "cleared"
    assert riskcompliance_screening_disposed.decided_by_id == admin_user.pk
    assert riskcompliance_screening_disposed.decided_at is not None
    # clear() back-fills the re-screen date so the supplier lands on the board rather than
    # quietly falling out of scope.
    assert riskcompliance_screening_disposed.next_rescreen_on == (
        riskcompliance_screening_disposed.screened_on
        + _riskcompliance_days(ComplianceScreening.DEFAULT_RESCREEN_DAYS))


def test_riskcompliance_screening_escalate_moves_the_row_and_requires_a_note(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    screening = _riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                              reference="CSL-ESC-0001")
    url = reverse("procurement:screening_escalate", args=[screening.pk])

    blank = client_a.post(url, {"note": "   "})
    screening.refresh_from_db()
    assert blank.status_code == 302
    assert screening.status == "pending_review"
    assert any("Say why this screening is being escalated." in message
               for message in _riskcompliance_messages(blank))

    ok = client_a.post(url, {"note": "Legal wants to look at the Cyprus address."})
    screening.refresh_from_db()
    assert ok.status_code == 302
    assert screening.status == "escalated"
    assert screening.decided_by_id == admin_user.pk


def test_riskcompliance_screening_block_stamps_the_suspension_link(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    from apps.procurement.models import VendorSuspension

    screening = _riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                              reference="CSL-BLK-0001",
                                              result="confirmed_match")
    suspension = VendorSuspension.objects.create(
        tenant=tenant_a, supplier=riskcompliance_party_a, kind="suspension",
        reason_category="other", reason="Confirmed SDN match.",
        starts_on=_riskcompliance_today())

    resp = client_a.post(reverse("procurement:screening_block", args=[screening.pk]), {
        "note": "Confirmed SDN match - no further spend.",
        "suspension": str(suspension.pk),
    })
    screening.refresh_from_db()

    assert resp.status_code == 302
    assert screening.status == "blocked"
    assert screening.suspension_id == suspension.pk
    assert any(f"Linked to suspension {suspension.number}." in message
               for message in _riskcompliance_messages(resp))


def test_riskcompliance_screening_block_refuses_a_suspension_for_another_supplier(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    """An absent prerequisite is REJECTED, never dropped so the block lands unexplained (L35)."""
    from apps.procurement.models import VendorSuspension

    other = _riskcompliance_party_named(tenant_a, "Contoso Fasteners")
    screening = _riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                              reference="CSL-BLK-0002")
    foreign = VendorSuspension.objects.create(
        tenant=tenant_a, supplier=other, kind="suspension", reason_category="other",
        reason="Nothing to do with the screened party.", starts_on=_riskcompliance_today())

    resp = client_a.post(reverse("procurement:screening_block", args=[screening.pk]), {
        "note": "Block it.",
        "suspension": str(foreign.pk),
    })
    screening.refresh_from_db()

    assert resp.status_code == 302
    assert screening.status == "pending_review"
    assert screening.suspension_id is None
    assert any("not on file for this supplier" in message
               for message in _riskcompliance_messages(resp))


# ================================================================== the re-screening board

def test_riskcompliance_screening_rescreen_board_rows_carry_the_pinned_keys(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    """Three suppliers, three states: never screened, overdue, and comfortably in date."""
    _riskcompliance_supplier(riskcompliance_party_a)
    overdue_party = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Contoso Fasteners"))
    fresh_party = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Fabrikam Bearings"))

    overdue = _riskcompliance_new_screening(
        tenant_a, overdue_party, admin_user, reference="CSL-BRD-0001",
        next_rescreen_on=_riskcompliance_today() - _riskcompliance_days(5))
    overdue.clear(admin_user, "Nothing returned.")
    fresh = _riskcompliance_new_screening(
        tenant_a, fresh_party, admin_user, reference="CSL-BRD-0002",
        next_rescreen_on=_riskcompliance_today() + _riskcompliance_days(200))
    fresh.clear(admin_user, "Nothing returned.")

    resp = client_a.get(reverse("procurement:screening_rescreen_board"))
    html = _riskcompliance_html(resp)
    rows = resp.context["rows"]

    assert resp.status_code == 200
    assert "procurement/riskcompliance/rescreening_due.html" in _riskcompliance_templates(resp)
    assert _riskcompliance_key_sets(rows) == {frozenset(
        {"party", "screening", "due_on", "days", "state", "state_label", "state_css",
         "sort_on"})}
    assert [row["state"] for row in rows] == ["never", "overdue"]
    assert rows[0]["party"].pk == riskcompliance_party_a.pk
    assert rows[1]["party"].pk == overdue_party.pk
    assert rows[1]["screening"].pk == overdue.pk
    assert rows[1]["days"] == 5
    assert resp.context["stats"] == {"overdue": 2, "due_soon": 0, "total": 3}
    assert resp.context["today"] == _riskcompliance_today()
    assert resp.context["is_admin"] is True
    # A real value from a row reaches the markup - not a grid of em-dashes (L8).
    assert "Contoso Fasteners" in html
    assert "Northwind Components Ltd" in html
    assert "Fabrikam Bearings" not in html


def test_riskcompliance_screening_rescreen_board_counts_a_due_soon_supplier(
        client_a, admin_user, tenant_a):
    soon_party = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Tailspin Alloys"))
    soon = _riskcompliance_new_screening(
        tenant_a, soon_party, admin_user, reference="CSL-BRD-0003",
        next_rescreen_on=_riskcompliance_today() + _riskcompliance_days(10))
    soon.clear(admin_user, "Nothing returned.")

    resp = client_a.get(reverse("procurement:screening_rescreen_board"))

    assert resp.status_code == 200
    assert [row["state"] for row in resp.context["rows"]] == ["due_soon"]
    assert resp.context["rows"][0]["days"] == -10
    assert resp.context["stats"] == {"overdue": 0, "due_soon": 1, "total": 1}
    assert soon.number in _riskcompliance_html(resp)


# ================================================================== screening hits

def test_riskcompliance_screeninghit_list_renders_rows_and_its_context(
        client_a, riskcompliance_screening_open, riskcompliance_screening_disposed):
    resp = client_a.get(reverse("procurement:screeninghit_list"))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert "procurement/riskcompliance/screeninghit/list.html" in _riskcompliance_templates(resp)
    assert len(_riskcompliance_pks(resp)) == 4
    assert "NORTHWIND COMPONENTS LLC" in html
    assert "NORTHWIND CHEMICALS PLC" in html
    assert len(resp.context["disposition_choices"]) == 4
    assert len(resp.context["match_type_choices"]) == 5
    assert len(resp.context["list_source_choices"]) == 13
    assert [screening.pk for screening in resp.context["screenings"]] == sorted(
        [riskcompliance_screening_open.pk, riskcompliance_screening_disposed.pk], reverse=True)
    assert resp.context["stats"] == {"open": 2, "true_match": 0, "false_positive": 2}
    assert resp.context["is_admin"] is True


def test_riskcompliance_screeninghit_list_each_valid_filter_value_returns_its_rows(
        client_a, riskcompliance_screening_open, riskcompliance_screening_disposed,
        riskcompliance_hit_open):
    url = reverse("procurement:screeninghit_list")
    open_pks = set(riskcompliance_screening_open.hits.values_list("pk", flat=True))
    disposed_pks = set(riskcompliance_screening_disposed.hits.values_list("pk", flat=True))

    assert set(_riskcompliance_pks(client_a.get(url, {"disposition": "open"}))) == open_pks
    assert set(_riskcompliance_pks(
        client_a.get(url, {"disposition": "false_positive"}))) == disposed_pks
    assert _riskcompliance_pks(client_a.get(url, {"disposition": "true_match"})) == []
    # Two of the four hits are alias matches, one per screening.
    assert len(_riskcompliance_pks(client_a.get(url, {"match_type": "alias"}))) == 2
    assert len(_riskcompliance_pks(client_a.get(url, {"match_type": "name"}))) == 2
    assert set(_riskcompliance_pks(
        client_a.get(url, {"screening": str(riskcompliance_screening_open.pk)}))) == open_pks
    assert _riskcompliance_pks(
        client_a.get(url, {"matched_list": "eu_consolidated"})) == [
            riskcompliance_screening_open.hits.get(matched_list="eu_consolidated").pk]
    assert _riskcompliance_pks(
        client_a.get(url, {"q": "Komponenty"})) == [
            riskcompliance_screening_open.hits.get(match_type="alias").pk]
    assert set(_riskcompliance_pks(client_a.get(url, {"min_score": "91"}))) == {
        riskcompliance_hit_open.pk,
        riskcompliance_screening_disposed.hits.get(match_score=91).pk}


def test_riskcompliance_screeninghit_detail_renders_the_parent_and_the_picker(
        client_a, riskcompliance_hit_open, riskcompliance_screening_open):
    resp = client_a.get(reverse("procurement:screeninghit_detail",
                                args=[riskcompliance_hit_open.pk]))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert resp.context["screening"].pk == riskcompliance_screening_open.pk
    assert [value for value, _label in resp.context["allowed_dispositions"]] == [
        "false_positive", "true_match", "cleared_with_licence"]
    assert riskcompliance_hit_open.matched_name in html
    assert riskcompliance_screening_open.number in html


def test_riskcompliance_screeninghit_detail_offers_no_verb_once_adjudicated(
        client_a, riskcompliance_hit_disposed):
    resp = client_a.get(reverse("procurement:screeninghit_detail",
                                args=[riskcompliance_hit_disposed.pk]))

    assert resp.status_code == 200
    assert resp.context["allowed_dispositions"] == []


def test_riskcompliance_screeninghit_create_files_the_hit_and_recounts_the_parent(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    screening = _riskcompliance_new_screening(tenant_a, riskcompliance_party_a, admin_user,
                                              reference="CSL-HIT-0001")

    resp = client_a.post(reverse("procurement:screeninghit_create", args=[screening.pk]), {
        "matched_name": "NORTHWIND HOLDINGS SA",
        "matched_list": "eu_consolidated",
        "match_score": "93",
        "match_type": "alias",
        "entry_reference": "EU-4471",
        "program": "SYRIA",
        "country": "Malta",
        "remarks": "Returned on the alias search.",
    })
    screening.refresh_from_db()
    hit = ScreeningHit.objects.get(matched_name="NORTHWIND HOLDINGS SA")

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:screeninghit_detail", args=[hit.pk])
    # The parent comes from the URL-resolved object, never from the payload.
    assert hit.screening_id == screening.pk
    assert hit.disposition == "open"
    assert screening.hit_count == 1
    assert screening.open_hit_count == 1


def test_riskcompliance_screeninghit_cannot_be_added_to_a_decided_screening(
        client_a, riskcompliance_screening_cleared):
    """A review fix, locked in: an open hit under a decided screening invalidates the decision."""
    url = reverse("procurement:screeninghit_create",
                  args=[riskcompliance_screening_cleared.pk])

    got = client_a.get(url)
    assert got.status_code == 302
    assert got["Location"] == reverse("procurement:screening_detail",
                                      args=[riskcompliance_screening_cleared.pk])
    assert any("cannot be added to a decided screening" in message
               for message in _riskcompliance_messages(got))

    posted = client_a.post(url, {
        "matched_name": "SHOULD NEVER LAND", "matched_list": "ofac_sdn", "match_score": "99",
        "match_type": "name", "entry_reference": "", "program": "", "country": "",
        "remarks": ""})
    assert posted.status_code == 302
    assert ScreeningHit.objects.filter(matched_name="SHOULD NEVER LAND").count() == 0


def test_riskcompliance_screeninghit_cannot_be_deleted_from_a_decided_screening(
        client_a, riskcompliance_screening_blocked):
    """The other half of the same review fix - the evidence a block was reasoned against."""
    hit = riskcompliance_screening_blocked.hits.get()

    resp = client_a.post(reverse("procurement:screeninghit_delete", args=[hit.pk]))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:screening_detail",
                                       args=[riskcompliance_screening_blocked.pk])
    assert ScreeningHit.objects.filter(pk=hit.pk).count() == 1
    assert any("cannot be deleted" in message for message in _riskcompliance_messages(resp))


def test_riskcompliance_screeninghit_delete_removes_a_live_hit_and_recounts(
        client_a, riskcompliance_screening_open, riskcompliance_hit_open):
    url = reverse("procurement:screeninghit_delete", args=[riskcompliance_hit_open.pk])

    got = client_a.get(url)
    assert got.status_code == 405
    assert ScreeningHit.objects.filter(pk=riskcompliance_hit_open.pk).count() == 1

    posted = client_a.post(url)
    riskcompliance_screening_open.refresh_from_db()
    assert posted.status_code == 302
    assert ScreeningHit.objects.filter(pk=riskcompliance_hit_open.pk).count() == 0
    assert riskcompliance_screening_open.hit_count == 1
    assert riskcompliance_screening_open.open_hit_count == 1


def test_riskcompliance_screeninghit_dispose_stamps_the_row_and_unlocks_clear(
        client_a, admin_user, riskcompliance_screening_open):
    hits = list(riskcompliance_screening_open.hits.order_by("-match_score", "id"))

    first = client_a.post(reverse("procurement:screeninghit_dispose", args=[hits[0].pk]), {
        "disposition": "false_positive",
        "disposition_note": "Different address and tax id.",
    })
    hits[0].refresh_from_db()
    assert first.status_code == 302
    assert hits[0].disposition == "false_positive"
    assert hits[0].disposed_by_id == admin_user.pk
    assert hits[0].disposed_at is not None
    assert not any("can be cleared" in message for message in _riskcompliance_messages(first))

    second = client_a.post(reverse("procurement:screeninghit_dispose", args=[hits[1].pk]), {
        "disposition": "cleared_with_licence",
        "disposition_note": "Covered by the general licence.",
    })
    riskcompliance_screening_open.refresh_from_db()
    assert second.status_code == 302
    assert riskcompliance_screening_open.open_hit_count == 0
    assert any("it can be cleared" in message for message in _riskcompliance_messages(second))


def test_riskcompliance_screeninghit_dispose_refuses_a_second_adjudication(
        client_a, riskcompliance_hit_disposed):
    resp = client_a.post(reverse("procurement:screeninghit_dispose",
                                 args=[riskcompliance_hit_disposed.pk]), {
        "disposition": "true_match",
        "disposition_note": "Changed my mind.",
    })
    riskcompliance_hit_disposed.refresh_from_db()

    assert resp.status_code == 302
    assert riskcompliance_hit_disposed.disposition == "false_positive"
    assert any("cannot be re-opened" in message for message in _riskcompliance_messages(resp))


def test_riskcompliance_screeninghit_dispose_refuses_a_blank_note(
        client_a, riskcompliance_hit_open):
    resp = client_a.post(reverse("procurement:screeninghit_dispose",
                                 args=[riskcompliance_hit_open.pk]),
                         {"disposition": "false_positive", "disposition_note": ""})
    riskcompliance_hit_open.refresh_from_db()

    assert resp.status_code == 302
    assert riskcompliance_hit_open.disposition == "open"
    assert len(_riskcompliance_messages(resp)) == 1


# ================================================================== risk-signal register

def test_riskcompliance_risksignal_list_renders_the_seeded_rows_and_its_context(
        client_a, riskcompliance_signal_fhr, riskcompliance_signal_ser):
    resp = client_a.get(reverse("procurement:risksignal_list"))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert "procurement/riskcompliance/risksignal/list.html" in _riskcompliance_templates(resp)
    assert riskcompliance_signal_fhr.number in html
    assert riskcompliance_signal_ser.number in html
    assert "Northwind Components Ltd" in html
    # fhr + the SER pair (the ser fixture brings its own predecessor).
    assert len(_riskcompliance_pks(resp)) == 3
    assert len(resp.context["provider_choices"]) == 9
    assert len(resp.context["metric_choices"]) == 13
    assert len(resp.context["band_choices"]) == 5
    assert len(resp.context["trend_choices"]) == 4
    assert len(resp.context["review_status_choices"]) == 4
    assert resp.context["stats"] == {"critical": 1, "deteriorating": 1, "unreviewed": 3,
                                     "refresh_due": 0}
    assert resp.context["is_admin"] is True


def test_riskcompliance_risksignal_list_each_valid_filter_value_returns_its_rows(
        client_a, riskcompliance_signal_fhr, riskcompliance_signal_ser,
        riskcompliance_signal_series):
    url = reverse("procurement:risksignal_list")
    ser_pks = {riskcompliance_signal_ser.pk, riskcompliance_signal_series.pk}

    assert _riskcompliance_pks(
        client_a.get(url, {"provider": "rapidratings"})) == [riskcompliance_signal_fhr.pk]
    assert set(_riskcompliance_pks(client_a.get(url, {"provider": "dnb"}))) == ser_pks
    assert _riskcompliance_pks(client_a.get(url, {"metric": "fhr"})) == [
        riskcompliance_signal_fhr.pk]
    assert set(_riskcompliance_pks(client_a.get(url, {"metric": "ser_rating"}))) == ser_pks
    assert _riskcompliance_pks(client_a.get(url, {"band": "low"})) == [
        riskcompliance_signal_fhr.pk]
    assert _riskcompliance_pks(client_a.get(url, {"band": "critical"})) == [
        riskcompliance_signal_ser.pk]
    assert _riskcompliance_pks(client_a.get(url, {"band": "watch"})) == [
        riskcompliance_signal_series.pk]
    assert _riskcompliance_pks(client_a.get(url, {"trend": "deteriorated"})) == [
        riskcompliance_signal_ser.pk]
    assert len(_riskcompliance_pks(client_a.get(url, {"trend": "new"}))) == 2
    assert len(_riskcompliance_pks(client_a.get(url, {"review_status": "new"}))) == 3
    assert _riskcompliance_pks(client_a.get(url, {"review_status": "actioned"})) == []
    assert len(_riskcompliance_pks(client_a.get(
        url, {"party": str(riskcompliance_signal_fhr.party_id)}))) == 3


def test_riskcompliance_risksignal_list_search_matches_each_declared_field(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    by_source = _riskcompliance_new_signal(tenant_a, riskcompliance_party_a, user=admin_user,
                                           source_ref="Creditsafe bulletin 4471")
    by_note = _riskcompliance_new_signal(tenant_a, riskcompliance_party_a, metric="paydex",
                                         value="60.00", provider="dnb",
                                         notes="Watched by the treasury desk")
    url = reverse("procurement:risksignal_list")

    assert _riskcompliance_pks(client_a.get(url, {"q": "bulletin 4471"})) == [by_source.pk]
    assert _riskcompliance_pks(client_a.get(url, {"q": "treasury desk"})) == [by_note.pk]
    assert _riskcompliance_pks(client_a.get(url, {"q": by_note.number})) == [by_note.pk]
    assert len(_riskcompliance_pks(client_a.get(url, {"q": "Northwind"}))) == 2


def test_riskcompliance_risksignal_list_query_budget_with_every_row_reviewed(
        client_a, tenant_a, riskcompliance_party_a, admin_user,
        django_assert_max_num_queries):
    """15 signals ALL with ``reviewed_by`` set - an unreviewed row hides the N+1 entirely.

    The list template names the reviewer on every reviewed row, so a missing
    ``select_related("reviewed_by")`` costs one query PER ROW - and only on rows that HAVE a
    reviewer, which is why every row here has one.
    """
    url = reverse("procurement:risksignal_list")

    def build(count, offset=0):
        for index in range(offset, offset + count):
            signal = _riskcompliance_new_signal(
                tenant_a, riskcompliance_party_a, metric="paydex", value=f"{50 + index}.00",
                provider="dnb", days_ago=index, user=admin_user)
            signal.mark_reviewed(admin_user, "Read.")

    build(3)
    three_rows = _riskcompliance_count_queries(client_a, url)
    build(12, offset=3)

    # 11 = 8 page/auth reads + the 3-query session write every authenticated request makes.
    with django_assert_max_num_queries(11):
        resp = client_a.get(url)

    assert resp.status_code == 200
    assert len(_riskcompliance_pks(resp)) == 15
    assert {signal.reviewed_by_id for signal in resp.context["object_list"]} == {admin_user.pk}
    # Five times the rows, the SAME number of queries - the N+1 property itself.
    assert _riskcompliance_count_queries(client_a, url) == three_rows


def test_riskcompliance_risksignal_list_paginates_with_a_tie_on_the_sort_column(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    same_day = _riskcompliance_today()
    made = [_riskcompliance_new_signal(tenant_a, riskcompliance_party_a, metric="paydex",
                                       value=f"{40 + index}.00", provider="dnb",
                                       user=admin_user, observed_on=same_day,
                                       source_ref=f"TIE-{index:03d}")
            for index in range(18)]
    url = reverse("procurement:risksignal_list")

    page_one = client_a.get(url)
    page_two = client_a.get(url, {"page": "2"})
    past_end = client_a.get(url, {"page": "999"})

    assert len(_riskcompliance_pks(page_one)) == 15
    assert len(_riskcompliance_pks(page_two)) == 3
    seen = _riskcompliance_pks(page_one) + _riskcompliance_pks(page_two)
    assert len(set(seen)) == 18
    assert set(seen) == {signal.pk for signal in made}
    # Page past the end is guarded, never a 500 (L9).
    assert past_end.status_code == 200
    assert len(_riskcompliance_pks(past_end)) == 3


def test_riskcompliance_risksignal_detail_renders_the_series_and_the_scale(
        client_a, riskcompliance_signal_ser, riskcompliance_signal_series):
    resp = client_a.get(reverse("procurement:risksignal_detail",
                                args=[riskcompliance_signal_ser.pk]))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert [row.pk for row in resp.context["series"]] == [riskcompliance_signal_ser.pk,
                                                          riskcompliance_signal_series.pk]
    assert resp.context["scale"]["higher_is_better"] is False
    assert resp.context["breaches_minimum"] is True
    assert resp.context["minimum_acceptable"] == Decimal("5")
    assert resp.context["assessment"] is None
    assert resp.context["alert"] is None
    assert riskcompliance_signal_ser.number in html
    assert riskcompliance_signal_series.number in html


def test_riskcompliance_risksignal_create_post_saves_and_derives_the_band(
        client_a, tenant_a, riskcompliance_party_a):
    _riskcompliance_supplier(riskcompliance_party_a)
    today = _riskcompliance_today()

    resp = client_a.post(reverse("procurement:risksignal_create"), {
        "party": str(riskcompliance_party_a.pk),
        "provider": "dnb",
        "metric": "ser_rating",
        "observed_on": today.isoformat(),
        "value": "8.00",
        "next_refresh_on": (today + _riskcompliance_days(90)).isoformat(),
        "source_ref": "D&B report, page 1.",
        "notes": "",
    })
    saved = SupplierRiskSignal.objects.get(source_ref="D&B report, page 1.")

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:risksignal_detail", args=[saved.pk])
    assert saved.tenant_id == tenant_a.pk
    # Derived by save(), never posted: SER 8 on a 1-9 higher-is-worse scale.
    assert saved.risk_position == Decimal("87.50")
    assert saved.band == "critical"
    assert saved.trend == "new"
    assert saved.review_status == "new"
    assert saved.number.startswith("SRS-")


def test_riskcompliance_risksignal_edit_post_updates_and_redecides_the_band(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    _riskcompliance_supplier(riskcompliance_party_a)
    signal = _riskcompliance_new_signal(tenant_a, riskcompliance_party_a, metric="fhr",
                                        value="82.00", provider="rapidratings", user=admin_user)
    today = _riskcompliance_today()

    resp = client_a.post(reverse("procurement:risksignal_edit", args=[signal.pk]), {
        "party": str(riskcompliance_party_a.pk),
        "provider": "rapidratings",
        "metric": "fhr",
        "observed_on": today.isoformat(),
        "value": "12.00",
        "next_refresh_on": (today + _riskcompliance_days(30)).isoformat(),
        "source_ref": "Amended after a re-read.",
        "notes": "",
    })
    signal.refresh_from_db()

    assert resp.status_code == 302
    assert signal.value == Decimal("12.00")
    # 12 on a 1-100 higher-is-BETTER scale flips to a risk position of 88.89.
    assert signal.band == "critical"


def test_riskcompliance_risksignal_review_moves_the_row_for_each_action(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    signal = _riskcompliance_new_signal(tenant_a, riskcompliance_party_a, metric="paydex",
                                        value="55.00", provider="dnb", user=admin_user)
    url = reverse("procurement:risksignal_review", args=[signal.pk])

    junk = client_a.post(url, {"action": "obliterate", "review_note": "x"})
    signal.refresh_from_db()
    assert junk.status_code == 302
    assert signal.review_status == "new"
    assert any("Choose whether to mark this signal" in message
               for message in _riskcompliance_messages(junk))

    reviewed = client_a.post(url, {"action": "reviewed", "review_note": ""})
    signal.refresh_from_db()
    assert reviewed.status_code == 302
    assert signal.review_status == "reviewed"
    assert signal.reviewed_by_id == admin_user.pk
    assert signal.reviewed_at is not None

    no_note = client_a.post(url, {"action": "actioned", "review_note": "  "})
    signal.refresh_from_db()
    assert no_note.status_code == 302
    assert signal.review_status == "reviewed"
    assert any("Record what was done about this signal." in message
               for message in _riskcompliance_messages(no_note))

    actioned = client_a.post(url, {"action": "actioned",
                                   "review_note": "Escalated to the category manager."})
    signal.refresh_from_db()
    assert actioned.status_code == 302
    assert signal.review_status == "actioned"
    assert signal.review_note == "Escalated to the category manager."


def test_riskcompliance_risksignal_review_refuses_a_terminal_row(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    signal = _riskcompliance_new_signal(tenant_a, riskcompliance_party_a, metric="paydex",
                                        value="55.00", provider="dnb", user=admin_user)
    signal.dismiss(admin_user, "Not material.")

    resp = client_a.post(reverse("procurement:risksignal_review", args=[signal.pk]),
                         {"action": "reviewed", "review_note": ""})
    signal.refresh_from_db()

    assert resp.status_code == 302
    assert signal.review_status == "dismissed"
    assert any("cannot be marked reviewed from dismissed" in message
               for message in _riskcompliance_messages(resp))


# ================================================================== the refresh board

def test_riskcompliance_risksignal_refresh_board_rows_carry_the_pinned_keys(
        client_a, admin_user, tenant_a, riskcompliance_party_a):
    _riskcompliance_supplier(riskcompliance_party_a)
    never_party = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Contoso Fasteners"))
    fresh_party = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Fabrikam Bearings"))

    overdue = _riskcompliance_new_signal(
        tenant_a, riskcompliance_party_a, metric="fhr", value="70.00",
        provider="rapidratings", days_ago=100, user=admin_user,
        next_refresh_on=_riskcompliance_today() - _riskcompliance_days(4))
    _riskcompliance_new_signal(
        tenant_a, fresh_party, metric="fhr", value="90.00", provider="rapidratings",
        days_ago=1, user=admin_user,
        next_refresh_on=_riskcompliance_today() + _riskcompliance_days(200))

    resp = client_a.get(reverse("procurement:risksignal_refresh_board"))
    html = _riskcompliance_html(resp)
    rows = resp.context["rows"]

    assert resp.status_code == 200
    assert "procurement/riskcompliance/risk_refresh_due.html" in _riskcompliance_templates(resp)
    assert _riskcompliance_key_sets(rows) == {frozenset(
        {"party", "signal", "provider_label", "metric_label", "observed_on", "due_on", "days",
         "age_days", "state", "state_label", "state_css", "sort_on"})}
    assert [row["state"] for row in rows] == ["never", "overdue"]
    assert rows[0]["party"].pk == never_party.pk
    assert rows[0]["signal"] is None
    assert rows[1]["signal"].pk == overdue.pk
    assert rows[1]["days"] == 4
    assert rows[1]["age_days"] == 100
    assert rows[1]["provider_label"] == "RapidRatings"
    assert resp.context["stats"] == {"overdue": 1, "due_soon": 0, "stale": 1}
    assert resp.context["today"] == _riskcompliance_today()
    assert resp.context["is_admin"] is True
    assert "Contoso Fasteners" in html
    assert overdue.number in html
    assert "Fabrikam Bearings" not in html


def test_riskcompliance_risksignal_refresh_board_query_budget(
        client_a, admin_user, tenant_a, django_assert_max_num_queries):
    """Guards the ``parties_by_id`` rewrite: no per-row Party lookup may come back."""
    url = reverse("procurement:risksignal_refresh_board")

    def build(count, offset=0):
        for index in range(offset, offset + count):
            party = _riskcompliance_supplier(
                _riskcompliance_party_named(tenant_a, f"Board Supplier {index:02d}"))
            _riskcompliance_new_signal(
                tenant_a, party, metric="fhr", value="70.00", provider="rapidratings",
                days_ago=10, user=admin_user,
                next_refresh_on=_riskcompliance_today() - _riskcompliance_days(index + 1))

    build(3)
    three_rows = _riskcompliance_count_queries(client_a, url)
    build(9, offset=3)

    # 9 = 6 page/auth reads + the 3-query session write every authenticated request makes.
    with django_assert_max_num_queries(9):
        resp = client_a.get(url)

    assert resp.status_code == 200
    assert len(resp.context["rows"]) == 12
    assert {row["state"] for row in resp.context["rows"]} == {"overdue"}
    # Four times the rows, the SAME number of queries: the board reads its Party objects out of
    # ``parties_by_id`` and never off the ``.only()``-narrowed signal.
    assert _riskcompliance_count_queries(client_a, url) == three_rows


def test_riskcompliance_risksignal_refresh_board_marks_a_stale_observation(
        client_a, admin_user, tenant_a):
    party = _riskcompliance_supplier(_riskcompliance_party_named(tenant_a, "Tailspin Alloys"))
    stale_days = SupplierRiskSignal.STALE_AFTER_DAYS + 10
    stale = _riskcompliance_new_signal(
        tenant_a, party, metric="fhr", value="70.00", provider="rapidratings",
        days_ago=stale_days, user=admin_user,
        next_refresh_on=_riskcompliance_today() + _riskcompliance_days(120))

    resp = client_a.get(reverse("procurement:risksignal_refresh_board"))

    assert resp.status_code == 200
    assert [row["state"] for row in resp.context["rows"]] == ["stale"]
    assert resp.context["rows"][0]["age_days"] == stale_days
    assert resp.context["stats"] == {"overdue": 0, "due_soon": 0, "stale": 1}
    assert stale.number in _riskcompliance_html(resp)


# ================================================================== fraud register

def test_riskcompliance_fraudalert_list_renders_the_seeded_rows_and_its_context(
        client_a, riskcompliance_fraud_open, riskcompliance_fraud_resolved):
    resp = client_a.get(reverse("procurement:fraudalert_list"))
    html = _riskcompliance_html(resp)

    assert resp.status_code == 200
    assert "procurement/riskcompliance/fraudalert/list.html" in _riskcompliance_templates(resp)
    assert riskcompliance_fraud_open.number in html
    assert riskcompliance_fraud_resolved.number in html
    assert "Northwind Components Ltd" in html
    assert set(_riskcompliance_pks(resp)) == {riskcompliance_fraud_open.pk,
                                              riskcompliance_fraud_resolved.pk}
    assert len(resp.context["rule_choices"]) == 6
    assert len(resp.context["status_choices"]) == 5
    assert len(resp.context["severity_choices"]) == 3
    assert resp.context["stats"] == {"open": 1, "investigating": 0, "confirmed": 1, "high": 0}
    assert resp.context["is_admin"] is True


def test_riskcompliance_fraudalert_list_each_valid_filter_value_returns_its_rows(
        client_a, tenant_a, riskcompliance_party_a, admin_user,
        riskcompliance_fraud_open, riskcompliance_fraud_resolved):
    _riskcompliance_supplier(riskcompliance_party_a)
    other = _riskcompliance_supplier(_riskcompliance_party_named(tenant_a, "Contoso Fasteners"))
    self_approval = _riskcompliance_new_alert(tenant_a, other, rule="self_approval",
                                              severity="high", amount="2500.00")
    url = reverse("procurement:fraudalert_list")

    assert _riskcompliance_pks(client_a.get(url, {"rule": "new_vendor_rush"})) == [
        riskcompliance_fraud_open.pk]
    assert _riskcompliance_pks(client_a.get(url, {"rule": "self_approval"})) == [
        self_approval.pk]
    assert _riskcompliance_pks(client_a.get(url, {"rule": "vendor_employee_match"})) == [
        riskcompliance_fraud_resolved.pk]
    assert set(_riskcompliance_pks(client_a.get(url, {"status": "open"}))) == {
        riskcompliance_fraud_open.pk, self_approval.pk}
    assert _riskcompliance_pks(client_a.get(url, {"status": "substantiated"})) == [
        riskcompliance_fraud_resolved.pk]
    assert _riskcompliance_pks(client_a.get(url, {"status": "investigating"})) == []
    assert _riskcompliance_pks(client_a.get(url, {"severity": "medium"})) == [
        riskcompliance_fraud_open.pk]
    assert set(_riskcompliance_pks(client_a.get(url, {"severity": "high"}))) == {
        self_approval.pk, riskcompliance_fraud_resolved.pk}
    assert _riskcompliance_pks(client_a.get(url, {"severity": "low"})) == []
    assert _riskcompliance_pks(client_a.get(url, {"vendor": str(other.pk)})) == [
        self_approval.pk]
    assert set(_riskcompliance_pks(
        client_a.get(url, {"assigned_to": str(admin_user.pk)}))) == {
            riskcompliance_fraud_open.pk, riskcompliance_fraud_resolved.pk}


def test_riskcompliance_fraudalert_list_search_matches_each_declared_field(
        client_a, tenant_a, riskcompliance_party_a):
    by_detail = _riskcompliance_new_alert(tenant_a, riskcompliance_party_a,
                                          detail="Split into four requisitions on one day.")
    by_matched_on = _riskcompliance_new_alert(tenant_a, riskcompliance_party_a,
                                              rule="duplicate_vendor",
                                              matched_on="tax id ending 4471")
    url = reverse("procurement:fraudalert_list")

    assert _riskcompliance_pks(client_a.get(url, {"q": "four requisitions"})) == [by_detail.pk]
    assert _riskcompliance_pks(client_a.get(url, {"q": "ending 4471"})) == [by_matched_on.pk]
    assert _riskcompliance_pks(client_a.get(url, {"q": by_detail.number})) == [by_detail.pk]
    assert len(_riskcompliance_pks(client_a.get(url, {"q": "Northwind"}))) == 2


def test_riskcompliance_fraudalert_list_query_budget_with_every_row_disposed(
        client_a, tenant_a, riskcompliance_party_a, admin_user, django_assert_max_num_queries):
    """15 alerts ALL disposed - ``resolved_by`` is non-null on every row, which is the hop."""
    url = reverse("procurement:fraudalert_list")

    def build(count, offset=0):
        for index in range(offset, offset + count):
            alert = _riskcompliance_new_alert(
                tenant_a, riskcompliance_party_a, rule="backdated_po",
                amount=f"{1000 + index}.00", matched_on=f"row {index:02d}")
            alert.unsubstantiate(admin_user, "Checked and closed.")

    build(3)
    three_rows = _riskcompliance_count_queries(client_a, url)
    build(12, offset=3)

    # 12 = 9 page/auth reads (this register offers TWO dropdowns, vendors and users) + the
    # 3-query session write every authenticated request makes.
    with django_assert_max_num_queries(12):
        resp = client_a.get(url)

    assert resp.status_code == 200
    assert len(_riskcompliance_pks(resp)) == 15
    assert {alert.resolved_by_id for alert in resp.context["object_list"]} == {admin_user.pk}
    assert _riskcompliance_count_queries(client_a, url) == three_rows


def test_riskcompliance_fraudalert_detail_sources_carry_the_pinned_keys(
        client_a, riskcompliance_fraud_resolved):
    resp = client_a.get(reverse("procurement:fraudalert_detail",
                                args=[riskcompliance_fraud_resolved.pk]))
    html = _riskcompliance_html(resp)
    sources = resp.context["sources"]

    assert resp.status_code == 200
    assert _riskcompliance_key_sets(sources) == {frozenset({"label", "value", "url"})}
    assert [row["label"] for row in sources] == ["Supplier", "Employee"]
    assert [row["value"] for row in sources] == ["Northwind Components Ltd", "R. Okonkwo"]
    assert all(row["url"].startswith("/") for row in sources)
    # A real source value reaches the markup rather than a row of em-dashes (L8).
    assert "R. Okonkwo" in html
    assert riskcompliance_fraud_resolved.number in html
    # Terminal: no disposition button is offered.
    assert resp.context["allowed_actions"] == []
    assert resp.context["blocking_suspensions"] == []


def test_riskcompliance_fraudalert_detail_offers_every_verb_on_an_open_alert(
        client_a, riskcompliance_fraud_open):
    resp = client_a.get(reverse("procurement:fraudalert_detail",
                                args=[riskcompliance_fraud_open.pk]))
    actions = resp.context["allowed_actions"]

    assert resp.status_code == 200
    assert _riskcompliance_key_sets(actions) == {frozenset(
        {"key", "label", "css", "icon", "note_required"})}
    assert [action["key"] for action in actions] == [
        "investigate", "substantiate", "unsubstantiate", "refer"]
    assert [action["note_required"] for action in actions] == [False, True, True, True]
    assert [row["label"] for row in resp.context["sources"]] == ["Supplier"]


def test_riskcompliance_fraudalert_create_post_saves_and_derives_the_dedupe_key(
        client_a, tenant_a, riskcompliance_party_a, admin_user):
    _riskcompliance_supplier(riskcompliance_party_a)
    today = _riskcompliance_today()

    resp = client_a.post(reverse("procurement:fraudalert_create"), {
        "rule": "new_vendor_rush",
        "severity": "high",
        "document_date": today.isoformat(),
        "amount": "48000.00",
        "detail": "First order is 48,000.00 six days after approval.",
        "matched_on": "",
        "assigned_to": str(admin_user.pk),
        "vendor": str(riskcompliance_party_a.pk),
    })
    saved = FraudAlert.objects.get(amount=Decimal("48000.00"))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:fraudalert_detail", args=[saved.pk])
    assert saved.tenant_id == tenant_a.pk
    assert saved.status == "open"
    assert saved.dedupe_key == f"nvrush:{riskcompliance_party_a.pk}"
    assert saved.number.startswith("FRD-")


def test_riskcompliance_fraudalert_disposition_walks_the_state_machine(
        client_a, admin_user, riskcompliance_fraud_open):
    url = reverse("procurement:fraudalert_disposition", args=[riskcompliance_fraud_open.pk])

    no_note = client_a.post(url, {"action": "substantiate", "resolution_note": "   "})
    riskcompliance_fraud_open.refresh_from_db()
    assert no_note.status_code == 302
    assert riskcompliance_fraud_open.status == "open"
    assert len(_riskcompliance_messages(no_note)) == 1

    took_it = client_a.post(url, {"action": "investigate", "resolution_note": ""})
    riskcompliance_fraud_open.refresh_from_db()
    assert took_it.status_code == 302
    assert riskcompliance_fraud_open.status == "investigating"

    closed = client_a.post(url, {"action": "substantiate",
                                 "resolution_note": "Confirmed with the category manager."})
    riskcompliance_fraud_open.refresh_from_db()
    assert closed.status_code == 302
    assert riskcompliance_fraud_open.status == "substantiated"
    assert riskcompliance_fraud_open.resolved_by_id == admin_user.pk
    assert riskcompliance_fraud_open.resolved_at is not None
    assert riskcompliance_fraud_open.resolution_note == "Confirmed with the category manager."


def test_riskcompliance_fraudalert_disposition_cannot_reopen_a_disposed_alert(
        client_a, riskcompliance_fraud_resolved):
    resp = client_a.post(
        reverse("procurement:fraudalert_disposition", args=[riskcompliance_fraud_resolved.pk]),
        {"action": "investigate", "resolution_note": ""})
    riskcompliance_fraud_resolved.refresh_from_db()

    assert resp.status_code == 302
    assert riskcompliance_fraud_resolved.status == "substantiated"
    assert any("cannot be investigated from substantiated" in message
               for message in _riskcompliance_messages(resp))


def test_riskcompliance_fraudalert_delete_is_post_only_and_refuses_a_disposed_row(
        client_a, tenant_a, riskcompliance_party_a, riskcompliance_fraud_resolved):
    live = _riskcompliance_new_alert(tenant_a, riskcompliance_party_a, rule="backdated_po",
                                     matched_on="delete me")
    live_url = reverse("procurement:fraudalert_delete", args=[live.pk])

    got = client_a.get(live_url)
    assert got.status_code == 405
    assert FraudAlert.objects.filter(pk=live.pk).count() == 1

    posted = client_a.post(live_url)
    assert posted.status_code == 302
    assert posted["Location"] == reverse("procurement:fraudalert_list")
    assert FraudAlert.objects.filter(pk=live.pk).count() == 0

    terminal = client_a.post(
        reverse("procurement:fraudalert_delete", args=[riskcompliance_fraud_resolved.pk]))
    assert terminal.status_code == 302
    assert FraudAlert.objects.filter(pk=riskcompliance_fraud_resolved.pk).count() == 1


# ================================================================== the fraud scan

def test_riskcompliance_fraud_scan_get_renders_the_read_only_half(client_a):
    resp = client_a.get(reverse("procurement:fraud_scan"))

    assert resp.status_code == 200
    assert "procurement/riskcompliance/fraud_scan.html" in _riskcompliance_templates(resp)
    # "Not run yet" and "ran and found nothing" are different facts on a fraud page.
    assert resp.context["results"] is None
    assert len(resp.context["rule_labels"]) == 6
    assert resp.context["skipped_groups"] == []
    assert resp.context["capped"] == []
    assert resp.context["not_buildable_note"] == FraudAlert.NOT_BUILDABLE_NOTE
    assert resp.context["is_admin"] is True
    assert len(resp.context["scan_limits"]) >= 1


def test_riskcompliance_fraud_scan_post_raises_alerts_then_a_second_post_raises_zero(
        client_a, tenant_a):
    """Idempotence, over HTTP: the interesting number on the second run is the ZERO."""
    first = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Contoso Fasteners Ltd"))
    second = _riskcompliance_supplier(
        _riskcompliance_party_named(tenant_a, "Contoso Fasteners (UK)"))
    Party.objects.filter(pk__in=[first.pk, second.pk]).update(tax_id="GB-99887766")

    today = _riskcompliance_today()
    payload = {"start": (today - _riskcompliance_days(30)).isoformat(),
               "end": (today + _riskcompliance_days(1)).isoformat(),
               "rules": ["duplicate_vendor"]}
    url = reverse("procurement:fraud_scan")

    run_one = client_a.post(url, payload, follow=True)
    assert run_one.status_code == 200
    assert run_one.context["results"] == {"duplicate_vendor": 1}
    assert FraudAlert.objects.filter(tenant=tenant_a, rule="duplicate_vendor").count() == 1
    raised = FraudAlert.objects.get(tenant=tenant_a, rule="duplicate_vendor")
    assert raised.vendor_id == min(first.pk, second.pk)
    assert raised.related_party_id == max(first.pk, second.pk)
    assert raised.dedupe_key == f"dupven:{min(first.pk, second.pk)}:{max(first.pk, second.pk)}:tax_id"
    assert "1 new fraud alert(s) raised." in _riskcompliance_html(run_one)

    run_two = client_a.post(url, payload, follow=True)
    assert run_two.status_code == 200
    assert run_two.context["results"] == {"duplicate_vendor": 0}
    assert FraudAlert.objects.filter(tenant=tenant_a, rule="duplicate_vendor").count() == 1
    assert "raised nothing new" in _riskcompliance_html(run_two)


def test_riskcompliance_fraud_scan_post_with_a_backwards_window_is_refused(
        client_a, tenant_a):
    today = _riskcompliance_today()
    resp = client_a.post(reverse("procurement:fraud_scan"), {
        "start": today.isoformat(),
        "end": (today - _riskcompliance_days(5)).isoformat(),
    })

    assert resp.status_code == 200
    assert resp.context["results"] is None
    assert resp.context["form"].errors
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 0


# ================================================================== the fraud board

def test_riskcompliance_fraud_board_rows_carry_the_pinned_keys(
        client_a, riskcompliance_fraud_open, riskcompliance_fraud_resolved):
    resp = client_a.get(reverse("procurement:fraud_board"))
    html = _riskcompliance_html(resp)
    by_rule = resp.context["by_rule"]
    by_severity = resp.context["by_severity"]
    ageing = resp.context["ageing"]

    assert resp.status_code == 200
    assert "procurement/riskcompliance/fraud_board.html" in _riskcompliance_templates(resp)

    assert _riskcompliance_key_sets(by_rule) == {frozenset(
        {"rule", "label", "open", "total", "high", "amount", "url"})}
    assert len(by_rule) == 6  # every rule appears, including the empty ones
    rules = {row["rule"]: row for row in by_rule}
    assert rules["new_vendor_rush"]["open"] == 1
    assert rules["new_vendor_rush"]["total"] == 1
    assert rules["new_vendor_rush"]["amount"] == Decimal("48000.00")
    assert rules["vendor_employee_match"]["open"] == 0
    assert rules["vendor_employee_match"]["total"] == 1
    # No OPEN alert under this rule carries an amount - NULL, never a claimed 0.00.
    assert rules["vendor_employee_match"]["amount"] is None
    assert rules["self_approval"]["total"] == 0
    assert rules["new_vendor_rush"]["url"].endswith("?rule=new_vendor_rush")

    assert _riskcompliance_key_sets(by_severity) == {frozenset(
        {"severity", "label", "css", "open", "total", "url"})}
    assert [row["severity"] for row in by_severity] == ["high", "medium", "low"]
    severities = {row["severity"]: row for row in by_severity}
    assert severities["medium"]["open"] == 1
    assert severities["high"]["open"] == 0
    assert severities["high"]["total"] == 1

    assert _riskcompliance_key_sets(ageing) == {frozenset(
        {"key", "label", "count", "css"})}
    # The one open alert is 3 days old, so exactly one bucket holds it and the rest are empty.
    assert sum(row["count"] for row in ageing) == 1

    assert resp.context["stats"] == {"total": 2, "open": 1, "investigating": 0,
                                     "confirmed": 1, "high": 0}
    assert resp.context["citation_invoice_url"] == reverse(
        "procurement:supplierinvoice_duplicates")
    assert resp.context["citation_maverick_url"] == reverse("procurement:maverick_dashboard")
    # A real label from a row-dict reaches the markup (L8).
    assert "New supplier with immediate high-value spend" in html
