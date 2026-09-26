"""0.17 Monitoring, Logging & Observability - the security lane.

The whole point of a multi-tenant ERP is that one workspace cannot see or touch another's rows. This
lane is the automated form of that claim: every object-touching route is exercised as a FOREIGN
tenant and must refuse, and every route is exercised as a non-admin member and must be forbidden.
"""
import pytest
from decimal import Decimal

from django.urls import reverse, NoReverseMatch

from apps.core.models import AlertEvent, AlertRule, Incident, ServiceComponent

#: Every 0.17 route, as (url_name, needs_pk). The inventory itself is the first assertion -
#: a route that quietly disappears would otherwise stop being tested.
_MONITORING_ROUTES = [
    ("core:monitoring_overview", False), ("core:health_board", False),
    ("core:firing_board", False), ("core:capacity_board", False),
    ("core:service_component_list", False), ("core:service_component_create", False),
    ("core:alert_rule_list", False), ("core:alert_rule_create", False),
    ("core:alert_event_list", False), ("core:alert_event_create", False),
    ("core:incident_list", False), ("core:incident_create", False),
    ("core:service_component_detail", True), ("core:service_component_edit", True),
    ("core:service_component_delete", True),
    ("core:alert_rule_detail", True), ("core:alert_rule_edit", True), ("core:alert_rule_delete", True),
    ("core:alert_event_detail", True), ("core:alert_event_edit", True), ("core:alert_event_delete", True),
    ("core:incident_detail", True), ("core:incident_edit", True), ("core:incident_delete", True),
    ("core:alertevent_acknowledge", True), ("core:alertevent_resolve", True),
    ("core:alertevent_recur", True), ("core:incident_notify", True),
]

_MONITORING_FOREIGN_OBJECTS = [
    ("service_component_detail", "service_component"), ("service_component_edit", "service_component"),
    ("alert_rule_detail", "alert_rule"), ("alert_rule_edit", "alert_rule"),
    ("alert_event_detail", "alert_event"), ("alert_event_edit", "alert_event"),
    ("incident_detail", "incident"), ("incident_edit", "incident"),
]


def _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b):
    """One object of each kind belonging to tenant B, for tenant A to try to reach."""
    service = ServiceComponent.objects.create(
        tenant=tenant_b, name="Globex web", code="gw", kind="web_service")
    rule = AlertRule.objects.create(
        tenant=tenant_b, service=service, name="Globex rule", metric_key="cpu_pct",
        comparator="gte", warning_threshold=Decimal("90"), frequency="hourly",
        severity="warning", category="capacity", no_data_action="ignore")
    return {"service_component": service, "alert_rule": rule,
            "alert_event": mon_event_b, "incident": mon_incident_b}


# ------------------------------------------------------------------ the route inventory

def test_monitoring_the_url_inventory_is_complete(client_a):
    """28 routes is the contract. If one is renamed, this fails instead of the test quietly
    covering one fewer route."""
    resolvable = 0
    for name, needs_pk in _MONITORING_ROUTES:
        try:
            reverse(name, kwargs={"pk": 1} if needs_pk else None)
            resolvable += 1
        except NoReverseMatch:
            pass
    assert resolvable == 28, f"only {resolvable}/28 0.17 url names reverse"


# ------------------------------------------------------------------ cross-tenant reads and writes

@pytest.mark.parametrize("action,kind", _MONITORING_FOREIGN_OBJECTS)
def test_monitoring_tenant_b_objects_are_404_for_tenant_a(client_a, tenant_b, action, kind,
                                                           mon_event_b, mon_incident_b):
    """A cross-tenant GET is a 404, never a 200 with somebody else's row on it."""
    foreign = _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b)[kind]
    assert client_a.get(reverse(f"core:{action}", kwargs={"pk": foreign.pk})).status_code == 404


@pytest.mark.parametrize("action,kind", [("alertevent_acknowledge", "alert_event"),
                                         ("alertevent_resolve", "alert_event"),
                                         ("alertevent_recur", "alert_event"),
                                         ("incident_notify", "incident")])
def test_monitoring_tenant_b_cannot_be_moved_by_tenant_a(client_a, tenant_b, action, kind,
                                                         mon_event_b, mon_incident_b):
    """A cross-tenant POST must change NOTHING, not merely refuse."""
    foreign = _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b)[kind]
    model = type(foreign)
    before = model.objects.get(pk=foreign.pk)
    response = client_a.post(reverse(f"core:{action}", kwargs={"pk": foreign.pk}))
    assert response.status_code in (403, 404)
    after = model.objects.get(pk=foreign.pk)
    for field in ("state", "occurrence_count", "notified_at", "resolved_at", "acknowledged_at"):
        assert getattr(after, field) == getattr(before, field), f"{field} moved on a foreign row"


@pytest.mark.parametrize("prefix", ["service_component", "alert_rule", "alert_event", "incident"])
def test_monitoring_tenant_b_cannot_be_deleted_by_tenant_a(client_a, tenant_b, prefix,
                                                           mon_event_b, mon_incident_b):
    foreign = _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b)[prefix]
    model = {"service_component": ServiceComponent, "alert_rule": AlertRule,
             "alert_event": AlertEvent, "incident": Incident}[prefix]
    response = client_a.post(reverse(f"core:{prefix}_delete", kwargs={"pk": foreign.pk}))
    assert response.status_code in (403, 404)
    assert model.objects.filter(pk=foreign.pk).exists(), "a foreign row was deleted"


@pytest.mark.parametrize("board", ["monitoring_overview", "health_board", "firing_board",
                                   "capacity_board"])
def test_monitoring_boards_show_no_other_tenants_data(client_a, tenant_b, board, mon_event_b,
                                                      mon_incident_b):
    """A count or a roll-up that includes another workspace is still a leak."""
    _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b)
    body = client_a.get(reverse(f"core:{board}")).content.decode("utf-8", "ignore")
    assert "Globex" not in body


@pytest.mark.parametrize("url_name", ["core:service_component_list", "core:alert_rule_list",
                                      "core:alert_event_list", "core:incident_list"])
def test_monitoring_lists_exclude_other_tenants(client_a, tenant_b, url_name, mon_event_b,
                                                mon_incident_b):
    foreign = _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b)
    pks = {o.pk for o in foreign.values()}
    listed = client_a.get(reverse(url_name)).context["object_list"]
    assert not (pks & {o.pk for o in listed}), "a foreign row appeared in the list"


# ------------------------------------------------------------------ authorization

@pytest.mark.parametrize("name,needs_pk", _MONITORING_ROUTES)
def test_monitoring_anonymous_is_redirected_not_served(client, db, name, needs_pk):
    """Never a 200. A monitoring board is privileged workspace state."""
    url = reverse(name, kwargs={"pk": 1} if needs_pk else None)
    response = client.get(url)
    assert response.status_code in (302, 403)
    assert "/login" in response.get("Location", "") or response.status_code == 403


@pytest.mark.parametrize("name,needs_pk", _MONITORING_ROUTES)
def test_monitoring_a_tenant_member_is_forbidden_on_every_route(member_client, db, name, needs_pk):
    """0.17 is platform administration, so EVERY route is admin-gated - not just the writes."""
    url = reverse(name, kwargs={"pk": 1} if needs_pk else None)
    assert member_client.get(url).status_code == 403, f"{name} is reachable by a non-admin member"


def test_monitoring_every_route_carries_the_tenant_admin_gate():
    """Read the source rather than infer it: one ungated view is a silent hole."""
    import io
    text = io.open("apps/core/views/Monitoring.py", encoding="utf-8").read()
    defs = text.count("\ndef ") + text.startswith("def ")
    gated = text.count("@tenant_admin_required")
    assert gated >= defs, f"{defs} view functions but only {gated} carry @tenant_admin_required"


def test_monitoring_exactly_eight_views_are_post_only():
    """4 deletes + 4 lifecycle actions. More would mean a GET can mutate."""
    import io
    text = io.open("apps/core/views/Monitoring.py", encoding="utf-8").read()
    assert text.count("@require_POST") == 8, text.count("@require_POST")


# ------------------------------------------------------------------ mass assignment

def test_monitoring_a_crafted_post_cannot_set_tenant_or_a_stamp(client_a, tenant_b, mon_event_firing_a,
                                                                 mon_rule_two_tier_a, mon_service_ok_a):
    """The explicit `Meta.fields` lists are the guard; this proves they hold."""
    fired_before = mon_event_firing_a.fired_at
    response = client_a.post(reverse("core:alert_event_edit", kwargs={"pk": mon_event_firing_a.pk}), {
        "message": "Crafted", "state": "resolved", "severity_at_fire": "info",
        "rule": mon_rule_two_tier_a.pk, "service": mon_service_ok_a.pk,
        "fired_at": "2020-01-01 00:00", "occurrence_count": "99", "evidence": "",
        "first_seen_at": "2019-01-01 00:00", "last_seen_at": "2019-01-01 00:00",
        "muted_until": "", "created_at": "",
        "tenant": tenant_b.pk, "tenant_id": tenant_b.pk, "is_active": "on",
        "acknowledged_at": "2019-01-01", "resolved_at": "2019-01-01",
    })
    assert response.status_code in (302, 303)
    mon_event_firing_a.refresh_from_db()
    assert mon_event_firing_a.tenant_id != tenant_b.pk, "the tenant was reassigned by a POST"
    assert mon_event_firing_a.fired_at == fired_before, "a system stamp was settable by a user"
    assert mon_event_firing_a.resolved_at is None, "resolved_at was settable by a user"

    """A cross-tenant POST must change NOTHING, not merely refuse."""
    foreign = _monitoring_foreign(tenant_b, mon_event_b, mon_incident_b)[kind]
    model = type(foreign)
    before = model.objects.get(pk=foreign.pk)
    response = client_a.post(reverse(f"core:{action}", kwargs={"pk": foreign.pk}))
    assert response.status_code in (403, 404)
    after = model.objects.get(pk=foreign.pk)
    for field in ("state", "occurrence_count", "notified_at", "resolved_at", "acknowledged_at"):
        assert getattr(after, field) == getattr(before, field), f"{field} moved on a foreign row"
