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
