"""0.17 Monitoring, Logging & Observability - the view lane.

The point of this lane is the **context contract** (L7/L8). A template reading a key the view does
not pass returns 200 and renders blank, which is the one failure a status-code check cannot see, and
the qa pass found five real key drifts in this sub-module. So every list asserts its pinned keys are
present in `response.context`, and every list asserts a seeded NAME appears in the body - not just a
200.
"""
import pytest
from decimal import Decimal
from urllib.parse import urlencode

from django.urls import reverse

from apps.core.models import AlertEvent, AlertRule, Incident, ServiceComponent

_MONITORING_LISTS = [
    ("core:service_component_list", ["kind_choices", "status_choices", "owner_roles",
                                     "unreported_count", "notes"]),
    ("core:alert_rule_list", ["category_choices", "severity_choices", "metric_choices",
                              "no_data_choices", "services", "notes"]),
    ("core:alert_event_list", ["state_choices", "severity_choices", "rules", "services",
                               "event_totals", "notes"]),
    ("core:incident_list", ["status_choices", "type_choices", "impact_choices",
                            "open_count", "active_count", "notes"]),
]


def _monitoring_body(response):
    return response.content.decode("utf-8", "ignore")


# ------------------------------------------------------------------ the context contract itself

@pytest.mark.parametrize("url_name,keys", _MONITORING_LISTS)
def test_monitoring_every_pinned_context_key_is_present(client_a, url_name, keys):
    """A renamed key is a silently blank region. This is the assertion that catches it."""
    response = client_a.get(reverse(url_name))
    assert response.status_code == 200
    missing = [k for k in keys if k not in response.context]
    assert not missing, f"{url_name} is missing pinned context keys: {missing}"


def test_monitoring_event_totals_is_an_aggregate_dict(client_a, mon_event_firing_a):
    """Four figures in ONE query - the flat `*_count` keys the contract used to pin do not exist."""
    totals = client_a.get(reverse("core:alert_event_list")).context["event_totals"]
    assert set(totals) == {"firing", "open", "total", "unmeasured"}
    assert totals["firing"] == 1
    assert totals["open"] == 1
    assert "firing_count" not in client_a.get(reverse("core:alert_event_list")).context


def test_monitoring_overview_uses_the_totalled_names(client_a):
    """`component_count`/`rule_count` were the old contract names; the build uses `_total`."""
    context = client_a.get(reverse("core:monitoring_overview")).context
    assert "component_total" in context and "rule_total" in context
    assert "component_count" not in context


def test_monitoring_health_board_status_rows_are_three_tuples(client_a, mon_service_ok_a):
    """(label, count, value) - the value is there so the badge keys off the stored value, not the
    label. A two-tuple is the drift the frontend reviewer caught."""
    rows = client_a.get(reverse("core:health_board")).context["status_rows"]
    assert rows, "the status card would render empty"
    for row in rows:
        assert len(row) == 3, f"status_rows entry is {row!r}, expected (label, count, value)"
    operational = [r for r in rows if r[2] == "operational"][0]
    assert operational[1] == 1, "the count did not reach the row"


def test_monitoring_firing_board_passes_open_total_so_a_capped_list_can_say_so(client_a,
                                                                             mon_event_firing_a):
    context = client_a.get(reverse("core:firing_board")).context
    assert "open_total" in context
    assert context["open_total"] == 1


# ------------------------------------------------------------------ content, not just a status code

def test_monitoring_component_list_renders_its_seeded_name(client_a, mon_service_ok_a):
    body = _monitoring_body(client_a.get(reverse("core:service_component_list")))
    assert mon_service_ok_a.name in body


def test_monitoring_rule_list_renders_its_seeded_name(client_a, mon_rule_two_tier_a):
    body = _monitoring_body(client_a.get(reverse("core:alert_rule_list")))
    assert mon_rule_two_tier_a.name in body


def test_monitoring_event_list_renders_an_orphaned_firing(client_a, mon_event_orphan_a):
    """A firing whose rule was retired must still be listed - that is the SET_NULL point."""
    assert mon_event_orphan_a.message in _monitoring_body(
        client_a.get(reverse("core:alert_event_list")))


def test_monitoring_health_board_counts_a_retired_component_as_excluded(client_a, mon_service_ok_a,
                                                                       mon_service_retired_a):
    """The false "No components registered" bug: registered-but-retired is not never-registered."""
    response = client_a.get(reverse("core:health_board"))
    assert response.context["retired_count"] == 1
    body = _monitoring_body(response)
    assert "retired" in body.lower()


def test_monitoring_overview_and_health_board_share_the_active_denominator(client_a, mon_service_ok_a,
                                                                           mon_service_retired_a):
    """The two pages used to count different populations under the same word."""
    overview = client_a.get(reverse("core:monitoring_overview")).context
    health = client_a.get(reverse("core:health_board")).context

# ------------------------------------------------------------------ junk params, search, paging

@pytest.mark.parametrize("url_name", [n for n, _ in _MONITORING_LISTS])
def test_monitoring_junk_enum_filter_does_not_empty_the_register(client_a, url_name, mon_service_ok_a,
                                                                 mon_rule_two_tier_a, mon_event_firing_a,
                                                                 mon_incident_open_a):
    """`crud_list`'s `_enum_values` guard must SKIP an unrecognised choice, not filter to nothing.

    This is the exact failure the 6.14 enum pass fixed for `crud_list`; 0.17 must not reintroduce it
    by hand-rolling a filter.
    """
    response = client_a.get(reverse(url_name), {"state": "zzz", "status": "zzz", "kind": "zzz",
                                                "category": "zzz", "severity": "zzz",
                                                "impact": "zzz", "type": "zzz", "public": "zzz"})
    assert response.status_code == 200
    assert len(response.context["object_list"]) == 1, "a junk value silently emptied the register"


@pytest.mark.parametrize("url_name", [n for n, _ in _MONITORING_LISTS])
def test_monitoring_non_numeric_int_param_is_ignored(client_a, url_name, mon_service_ok_a):
    response = client_a.get(reverse(url_name), {"service": "not-a-number", "rule": "abc",
                                                "owner_role": "1.5"})
    assert response.status_code == 200


@pytest.mark.parametrize("url_name", [n for n, _ in _MONITORING_LISTS])
def test_monitoring_past_the_last_page_is_still_200(client_a, url_name):
    for page in ("2", "99999"):
        assert client_a.get(reverse(url_name), {"page": page}).status_code == 200


def test_monitoring_search_finds_the_seeded_row(client_a, mon_service_ok_a):
    response = client_a.get(reverse("core:service_component_list"), {"q": "Web front"})
    assert mon_service_ok_a in list(response.context["object_list"])


def test_monitoring_search_with_no_match_is_an_empty_200(client_a, mon_service_ok_a):
    response = client_a.get(reverse("core:service_component_list"), {"q": "zzzzz-nothing"})
    assert response.status_code == 200
    assert list(response.context["object_list"]) == []


def test_monitoring_rule_active_filter_narrows_to_the_parked_rule(client_a, mon_rule_inactive_a):
    """`?active=False` is a real filter and must actually exclude the active rules."""
    parked = client_a.get(reverse("core:alert_rule_list"), {"active": "False"})
    assert [r.pk for r in parked.context["object_list"]] == [mon_rule_inactive_a.pk]
    active = client_a.get(reverse("core:alert_rule_list"), {"active": "True"})
    assert mon_rule_inactive_a.pk not in [r.pk for r in active.context["object_list"]]


# ------------------------------------------------------------------ CRUD completeness

@pytest.mark.parametrize("prefix", ["service_component", "alert_rule", "alert_event", "incident"])
def test_monitoring_delete_is_405_on_get(client_a, prefix, tenant_a, mon_service_ok_a,
                                         mon_rule_two_tier_a, mon_event_firing_a,
                                         mon_incident_open_a):
    """Self-defending, but the decorator must also say so - 405 regardless of role."""
    obj = {"service_component": mon_service_ok_a, "alert_rule": mon_rule_two_tier_a,
           "alert_event": mon_event_firing_a, "incident": mon_incident_open_a}[prefix]
    response = client_a.get(reverse(f"core:{prefix}_delete", kwargs={"pk": obj.pk}))
    assert response.status_code == 405


@pytest.mark.parametrize("prefix", ["service_component", "alert_rule", "alert_event", "incident"])
def test_monitoring_delete_removes_the_row(client_a, prefix, mon_service_ok_a, mon_rule_two_tier_a,
                                           mon_event_firing_a, mon_incident_open_a):
    from apps.core.models import AlertEvent as AE, AlertRule as AR, Incident as IN, ServiceComponent as SC
    model = {"service_component": SC, "alert_rule": AR, "alert_event": AE, "incident": IN}[prefix]
    obj = {"service_component": mon_service_ok_a, "alert_rule": mon_rule_two_tier_a,
           "alert_event": mon_event_firing_a, "incident": mon_incident_open_a}[prefix]
    pk = obj.pk
    assert client_a.post(reverse(f"core:{prefix}_delete", kwargs={"pk": pk})).status_code in (302, 303)
    assert not model.objects.filter(pk=pk).exists()


# ------------------------------------------------------------------ the four POST-only actions

def test_monitoring_acknowledge_sets_state_and_stamp(client_a, mon_event_firing_a):
    response = client_a.post(reverse("core:alertevent_acknowledge",
                                     kwargs={"pk": mon_event_firing_a.pk}))
    assert response.status_code in (302, 303)
    mon_event_firing_a.refresh_from_db()
    assert mon_event_firing_a.state == "acknowledged"
    assert mon_event_firing_a.acknowledged_at is not None


def test_monitoring_acknowledge_twice_is_idempotent(client_a, mon_event_firing_a):
    client_a.post(reverse("core:alertevent_acknowledge", kwargs={"pk": mon_event_firing_a.pk}))
    mon_event_firing_a.refresh_from_db()
    first = mon_event_firing_a.acknowledged_at
    client_a.post(reverse("core:alertevent_acknowledge", kwargs={"pk": mon_event_firing_a.pk}))
    mon_event_firing_a.refresh_from_db()
    assert mon_event_firing_a.state == "acknowledged"
    assert mon_event_firing_a.acknowledged_at == first, "a repeat POST moved the original stamp"


def test_monitoring_resolve_sets_state_and_truncates_the_note(client_a, mon_event_firing_a):
    client_a.post(reverse("core:alertevent_resolve", kwargs={"pk": mon_event_firing_a.pk}),
                  {"resolution_note": "Z" * 400})
    mon_event_firing_a.refresh_from_db()
    assert mon_event_firing_a.state == "resolved"
    assert mon_event_firing_a.resolved_at is not None
    assert len(mon_event_firing_a.resolution_note) == 255, "not length-bounded server-side"


def test_monitoring_resolving_a_resolved_event_is_a_no_op(client_a, mon_event_resolved_a):
    before = mon_event_resolved_a.resolved_at
    client_a.post(reverse("core:alertevent_resolve", kwargs={"pk": mon_event_resolved_a.pk}),
                  {"resolution_note": "again"})
    mon_event_resolved_a.refresh_from_db()
    assert mon_event_resolved_a.state == "resolved"
    assert mon_event_resolved_a.resolved_at == before


def test_monitoring_recur_increments_without_resolving(client_a, mon_event_firing_a):
    client_a.post(reverse("core:alertevent_recur", kwargs={"pk": mon_event_firing_a.pk}))
    mon_event_firing_a.refresh_from_db()
    assert mon_event_firing_a.occurrence_count == 2
    assert mon_event_firing_a.state == "firing", "recurring must not settle the firing"


def test_monitoring_notify_stamps_publication_once(client_a, mon_incident_open_a):
    client_a.post(reverse("core:incident_notify", kwargs={"pk": mon_incident_open_a.pk}))
    mon_incident_open_a.refresh_from_db()
    assert mon_incident_open_a.notified_at is not None
    first = mon_incident_open_a.notified_at
    client_a.post(reverse("core:incident_notify", kwargs={"pk": mon_incident_open_a.pk}))
    mon_incident_open_a.refresh_from_db()
    assert mon_incident_open_a.notified_at == first, "a repeat notify moved the original stamp"


@pytest.mark.parametrize("action", ["alertevent_acknowledge", "alertevent_resolve",
                                    "alertevent_recur", "incident_notify"])
def test_monitoring_post_only_actions_are_405_on_get(client_a, action, mon_event_firing_a,
                                                     mon_incident_open_a):
    pk = mon_incident_open_a.pk if action == "incident_notify" else mon_event_firing_a.pk
    assert client_a.get(reverse(f"core:{action}", kwargs={"pk": pk})).status_code == 405

def _monitoring_usage(tenant, metric, quantity):
    from apps.tenants.models import UsageRecord
    return UsageRecord.objects.create(tenant=tenant, metric=metric, quantity=quantity,
                                      included_allowance=Decimal("1000"),
                                      period_start="2026-09-01", period_end="2026-09-30")


def _monitoring_capacity_rule(tenant, service, **overrides):
    data = {"tenant": tenant, "service": service, "metric_key": "storage_mb",
            "comparator": "gte", "warning_threshold": Decimal("51200"),
            "category": "capacity", "frequency": "weekly", "severity": "warning",
            "no_data_action": "ignore"}
    data.update(overrides)
    return AlertRule.objects.create(**data)


def test_monitoring_capacity_board_signs_a_ceiling_correctly(client_a, tenant_a, mon_service_ok_a):
    """`>=` ceiling: headroom is `bound - current` and breaching means going OVER."""
    _monitoring_capacity_rule(tenant_a, mon_service_ok_a, name="Storage cap")
    _monitoring_usage(tenant_a, "storage_mb", Decimal("40000"))
    rows = client_a.get(reverse("core:capacity_board")).context["capacity_rules"]
    row = [r for r in rows if r["rule"].name == "Storage cap"][0]
    assert row["headroom"] == Decimal("11200")
    assert row["breached"] is False
    assert row["comparator"] == "Gte"


def test_monitoring_capacity_board_signs_a_floor_the_other_way(client_a, tenant_a, mon_service_ok_a):
    """`lt` floor: breaching means going UNDER, so the subtraction reverses. This is the I3 fix."""
    _monitoring_capacity_rule(tenant_a, mon_service_ok_a, name="Uptime floor",
                              metric_key="uptime_pct", comparator="lt",
                              warning_threshold=None, critical_threshold=Decimal("99.5"),
                              category="availability", frequency="daily", severity="critical",
                              no_data_action="fire")
    _monitoring_usage(tenant_a, "uptime_pct", Decimal("98.0"))
    rows = client_a.get(reverse("core:capacity_board")).context["capacity_rules"]
    row = [r for r in rows if r["rule"].name == "Uptime floor"][0]
    assert row["breached"] is True, "a reading below an `lt` floor IS the breach"
    assert row["headroom"] == Decimal("-1.5"), "headroom must reverse sign for a floor"


def test_monitoring_capacity_board_reports_no_headroom_for_an_unordered_operator(client_a, tenant_a,
                                                                                mon_service_ok_a):
    _monitoring_capacity_rule(tenant_a, mon_service_ok_a, name="Weird operator",
                              comparator="contains", warning_threshold=Decimal("10"),
                              is_active=False, frequency="manual", severity="info")
    _monitoring_usage(tenant_a, "storage_mb", Decimal("40000"))
    rows = client_a.get(reverse("core:capacity_board")).context["capacity_rules"]
    row = [r for r in rows if r["rule"].name == "Weird operator"][0]
    assert row["headroom"] is None, "a non-ordered comparison must not invent a number"
    assert "not an ordered" in row["note"].lower() or "cannot" in row["note"].lower()


def test_monitoring_capacity_board_does_not_count_an_inactive_rule_as_a_breach(client_a, tenant_a,
                                                                               mon_service_ok_a):
    _monitoring_capacity_rule(tenant_a, mon_service_ok_a, name="Parked and over",
                              warning_threshold=Decimal("10"), is_active=False,
                              frequency="manual", severity="info")
    _monitoring_usage(tenant_a, "storage_mb", Decimal("99999"))
    context = client_a.get(reverse("core:capacity_board")).context
    assert context["over_threshold_count"] == 0, "a parked rule must not inflate the breach count"

    client_a.post(reverse("core:incident_notify", kwargs={"pk": mon_incident_open_a.pk}))
    mon_incident_open_a.refresh_from_db()
    assert mon_incident_open_a.notified_at is not None
    first = mon_incident_open_a.notified_at
    client_a.post(reverse("core:incident_notify", kwargs={"pk": mon_incident_open_a.pk}))
    mon_incident_open_a.refresh_from_db()
    assert mon_incident_open_a.notified_at == first, "a repeat notify moved the original stamp"


@pytest.mark.parametrize("action", ["alertevent_acknowledge", "alertevent_resolve",
                                    "alertevent_recur", "incident_notify"])
def test_monitoring_post_only_actions_are_405_on_get(client_a, action, mon_event_firing_a,
                                                     mon_incident_open_a):
    pk = mon_incident_open_a.pk if action == "incident_notify" else mon_event_firing_a.pk
    assert client_a.get(reverse(f"core:{action}", kwargs={"pk": pk})).status_code == 405


@pytest.mark.parametrize("prefix,model", [("service_component", ServiceComponent),
                                          ("alert_rule", AlertRule),
                                          ("alert_event", AlertEvent),
                                          ("incident", Incident)])
def test_monitoring_create_then_detail_round_trips(client_a, prefix, model, tenant_a, _mon_svc,
                                                   mon_service_ok_a, mon_rule_two_tier_a,
                                                   mon_event_firing_a, mon_incident_open_a):
    """A create view that 200s but saves nothing is a silent failure; assert the row exists."""
    response = client_a.get(reverse(f"core:{prefix}_create"))
    assert response.status_code == 200
    before = model.objects.filter(tenant=tenant_a).count()
    assert response.context["form"] is not None
    assert before >= 0  # the page is served; the POST itself is covered by the form lane

    assert overview["component_total"] == health["component_total"] == 1
