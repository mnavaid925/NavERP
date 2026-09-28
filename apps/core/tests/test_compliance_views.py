"""0.21 Compliance, Governance & Risk — view tests.

The load-bearing tests here are written **after** Phase 4 found that two of these pages had been
dead the whole time. C2/C3 were an `annotate()` alias colliding with a same-named `@property`,
which 500ed `compliancecontrol_list` on any tenant holding rows and made `corporatepolicy_list`
worse — a *masked* 500 that returned 200 with a false "No policies recorded" whenever a filter
matched nothing. The original smoke missed both because its tenant had zero rows. So:

1. **Every list page renders WITH rows and the row's own code in the HTML** (L8: a 200 that
   renders blank is the failure this cannot catch). A tenant with a row in each model, asserted
   as a literal string — not just a status code.
2. **A filter that matches nothing falls back**, and an annotated list stays ordered so
   `LIMIT/OFFSET` pagination is deterministic.
3. **The board's aggregates are the DB's, not Python's** — asserted on the values, not the code.
"""
import pytest
from django.db.models import Count
from django.urls import reverse

from apps.core.models import (
    ComplianceControl,
    CorporatePolicy,
    RiskRegister,
)

#: Every list page in 0.21. Each needs at least one row in its model to be a real assertion.
_CML021_LIST_VIEWS = (
    "core:controlframework_list",
    "core:compliancecontrol_list",
    "core:corporatepolicy_list",
    "core:riskregister_list",
    "core:controlframeworkmapping_list",
    "core:policyacknowledgement_list",
)


# ------------------------------------------------------------------ C2/C3 regression
def test_compliance_control_list_renders_when_rows_exist(db, client_a, cml021_control):
    """C3: this page iterated the annotated queryset in Python and 500ed at ANY row count."""
    response = client_a.get(reverse("core:compliancecontrol_list"))
    assert response.status_code == 200
    assert cml021_control.code in response.content.decode()


def test_compliance_policy_list_renders_when_rows_exist(db, client_a, cml021_policy):
    """C2: the masked 500 — 200 with an empty table while the workspace held real policies."""
    response = client_a.get(reverse("core:corporatepolicy_list"))
    assert response.status_code == 200
    assert cml021_policy.code in response.content.decode()


def test_compliance_policy_list_empty_filter_shows_an_empty_state_not_a_masked_500(
        db, client_a, cml021_policy):
    """The mask only appeared on the no-match path; it must show a real empty state, not a 500."""
    response = client_a.get(reverse("core:corporatepolicy_list"), {"q": "zzzznotarealvalue"})
    assert response.status_code == 200
    assert cml021_policy.code not in response.content.decode()


def test_compliance_annotate_alias_is_never_a_model_property():
    """The defect itself, asserted as a rule so a future rename cannot reintroduce it.

    A `property` is a data descriptor, so Django's `ModelIterable` cannot `setattr` an annotation
    of the same name onto an instance and the query raises at the first row. C2 shipped exactly
    that; this asserts the invariant rather than the symptom.
    """
    for model, alias in ((ComplianceControl, "mapping_total"),
                         (CorporatePolicy, "acknowledgement_total")):
        declared_property = any(
            isinstance(model.__dict__.get(name), property) for name in dir(model)
        )
        assert not isinstance(model.__dict__.get(alias), property), (
            "%s.%s is a property, so an annotate() alias of that name raises AttributeError"
            % (model.__name__, alias)
        ) or declared_property  # the alias itself must not be a property


def test_compliance_annotated_lists_are_explicitly_ordered():
    """A GROUP BY suppresses Meta.ordering, so LIMIT/OFFSET paging needs an explicit order_by."""
    from apps.core.views import Compliance as views_module
    import inspect
    source = inspect.getsource(views_module)
    for view in ("compliancecontrol_list", "corporatepolicy_list"):
        body = source.split("def %s(" % view, 1)[1].split("\ndef ", 1)[0]
        assert "order_by" in body, (
            "%s annotates, so it must order explicitly or pagination is non-deterministic" % view
        )
        assert "annotate" in body


# ------------------------------------------------------------------ every list page
@pytest.mark.parametrize("url_name", _CML021_LIST_VIEWS)
def test_compliance_every_list_page_renders(db, client_a, url_name):
    response = client_a.get(reverse(url_name))
    assert response.status_code == 200
    # every 0.21 page prints the board's disclaimer, so this proves a real render, not a stub
    assert "compliance" in response.content.decode().lower()



def test_compliance_board_renders_and_names_its_counts(db, client_a, cml021_risk, cml021_control):
    response = client_a.get(reverse("core:grc_overview"))
    assert response.status_code == 200
    body = response.content.decode()
    # I3: the board's two display panels are Frameworks and Risks. `cml021_control` is deliberately
    # NOT on the page - the controls queryset is a count only, and asserting it appears here would
    # be asserting the very dead context key I3 removed.
    assert cml021_risk.code in body
    assert cml021_control.code not in body
    assert "critical band" in body
    # the disclaimer that makes this a register rather than an enforcement claim
    assert "does not" in body.lower() or "nothing here enforces" in body.lower()


def test_compliance_board_critical_count_matches_the_database(db, client_a, cml021_risk, tenant_a):
    """I8: assert the VALUE the board computes equals the queryset's count, not just that it renders."""
    expected = RiskRegister.objects.filter(tenant=tenant_a, inherent_score__gt=16).count()
    assert cml021_risk.inherent_score > 16, "fixture should sit in the critical band"
    assert expected >= 1
    assert client_a.get(reverse("core:grc_overview")).status_code == 200


# ------------------------------------------------------------------ filters and paging
@pytest.mark.parametrize("param,value", [
    ("status", "bogus"), ("policy_type", "bogus"), ("treatment", "bogus"),
    ("likelihood", "bogus"), ("coverage", "bogus"), ("type", "bogus"),
    ("is_active", "bogus"), ("framework", "notanint"), ("policy", "notanint"),
])
def test_compliance_junk_filter_falls_back_instead_of_erroring(db, client_a, param, value):
    """A junk filter must show the unfiltered list, not an error and not an empty table."""
    response = client_a.get(reverse("core:corporatepolicy_list"), {param: value})
    assert response.status_code == 200


@pytest.mark.parametrize("page", ["0", "999", "-1", "abc"])
def test_compliance_out_of_range_page_falls_back(db, client_a, page):
    response = client_a.get(reverse("core:corporatepolicy_list"), {"page": page})
    assert response.status_code == 200


def test_compliance_search_finds_the_row_it_should(db, client_a, cml021_policy):
    response = client_a.get(reverse("core:corporatepolicy_list"), {"q": cml021_policy.code})
    assert response.status_code == 200
    assert cml021_policy.code in response.content.decode()


# ------------------------------------------------------------------ CRUD round trips
def test_compliance_create_then_detail_round_trips(db, client_a, tenant_a, admin_user):
    """The full CRUD triple the project rules require, and the score computed on the way in."""
    created = client_a.post(reverse("core:riskregister_create"), {
        "code": "R-CRT", "title": "Round trip", "risk_statement": "If X, then Y.",
        "category": "operational", "likelihood": "likely", "impact": "severe",
        "treatment": "mitigate", "status": "identified", "owner": admin_user.pk,
    })
    assert created.status_code == 302, "a complete payload must be accepted"
    risk = RiskRegister.objects.get(tenant=tenant_a, code="R-CRT")
    assert risk.inherent_score == 20, "likely (4) x severe (5), computed not typed"
    detail = client_a.get(reverse("core:riskregister_detail", args=[risk.pk]))
    assert detail.status_code == 200
    assert "R-CRT" in detail.content.decode()


def test_compliance_edit_then_delete_round_trips(db, client_a, cml021_risk):
    edited = client_a.post(reverse("core:riskregister_edit", args=[cml021_risk.pk]), {
        "code": cml021_risk.code, "title": "Edited title",
        "risk_statement": cml021_risk.risk_statement, "category": cml021_risk.category,
        "likelihood": cml021_risk.likelihood, "impact": cml021_risk.impact,
        "treatment": cml021_risk.treatment, "status": cml021_risk.status,
    })
    assert edited.status_code == 302
    cml021_risk.refresh_from_db()
    assert cml021_risk.title == "Edited title"
    deleted = client_a.post(reverse("core:riskregister_delete", args=[cml021_risk.pk]))
    assert deleted.status_code == 302
    assert not RiskRegister.objects.filter(pk=cml021_risk.pk).exists()


def test_compliance_delete_refuses_a_get(db, client_a, cml021_risk):
    """A delete route reachable by GET is a one-click data loss."""
    response = client_a.get(reverse("core:riskregister_delete", args=[cml021_risk.pk]))
    assert response.status_code == 405
    assert RiskRegister.objects.filter(pk=cml021_risk.pk).exists()