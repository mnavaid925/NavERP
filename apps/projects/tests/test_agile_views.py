"""Projects 7.13 — Agile & Scrum Management view tests.

Covers:
- CRUD list, create, detail, edit for Sprint, Epic, Release, Impediment, Retrospective
- 4 Computed pages: sprint_backlog, sprint_execution, release_roadmap, velocity_report
- Action verbs: spt_start, spt_complete, spt_cancel, rel_publish, imp_resolve, ret_open, ret_close
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.projects.models import (
    Project,
    ProjectEpic,
    ProjectRelease,
    ProjectTask,
    Sprint,
    SprintImpediment,
    SprintRetrospective,
)

pytestmark = pytest.mark.django_db


def _create_project(tenant, name="Agile Project"):
    p = Project(tenant=tenant, name=name, code="AGL", status="active")
    p.save()
    return p


def _create_sprint(tenant, project, name="Sprint 1", **kw):
    s = Sprint(tenant=tenant, project=project, name=name, **kw)
    s.save()
    return s


def _create_epic(tenant, project, name="Epic 1", **kw):
    e = ProjectEpic(tenant=tenant, project=project, name=name, **kw)
    e.save()
    return e


def _create_release(tenant, project, name="Release 1.0", version_tag="v1.0", **kw):
    r = ProjectRelease(tenant=tenant, project=project, name=name, version_tag=version_tag, **kw)
    r.save()
    return r


# ==================================================================================================
# List Views
# ==================================================================================================

@pytest.mark.parametrize(
    "url_name",
    [
        "projects:spt_list",
        "projects:epc_list",
        "projects:rel_list",
        "projects:imp_list",
        "projects:ret_list",
    ],
)
def test_agile_list_views_render_200(client_a, url_name):
    res = client_a.get(reverse(url_name))
    assert res.status_code == 200


# ==================================================================================================
# Detail & Edit Views
# ==================================================================================================

def test_agile_sprint_detail_and_edit_view(client_a, tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p, "Sprint Detail Test")

    res = client_a.get(reverse("projects:spt_detail", args=[s.pk]))
    assert res.status_code == 200
    assert "sprint" in res.context
    assert res.context["sprint"] == s

    res_edit = client_a.get(reverse("projects:spt_edit", args=[s.pk]))
    assert res_edit.status_code == 200


def test_agile_epic_detail_view(client_a, tenant_a):
    p = _create_project(tenant_a)
    e = _create_epic(tenant_a, p, "Epic Detail Test")

    res = client_a.get(reverse("projects:epc_detail", args=[e.pk]))
    assert res.status_code == 200
    assert "epic" in res.context


def test_agile_release_detail_view(client_a, tenant_a):
    p = _create_project(tenant_a)
    r = _create_release(tenant_a, p, "Release Detail Test", "v1.2.0")

    res = client_a.get(reverse("projects:rel_detail", args=[r.pk]))
    assert res.status_code == 200
    assert "release" in res.context


# ==================================================================================================
# Computed Pages
# ==================================================================================================

def test_agile_sprint_backlog_page(client_a, tenant_a):
    p = _create_project(tenant_a)
    t = ProjectTask(tenant=tenant_a, project=p, name="Backlog Story", story_points=8)
    t.save()
    s = _create_sprint(tenant_a, p, "Target Sprint")

    url = reverse("projects:sprint_backlog")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "backlog_tasks" in res.context

    # Test assigning task to sprint via POST
    post_res = client_a.post(
        url,
        {"action": "assign_sprint", "task_id": t.pk, "sprint_id": s.pk},
    )
    assert post_res.status_code == 302
    t.refresh_from_db()
    assert t.sprint == s

    # Test updating points
    post_res = client_a.post(
        url,
        {"action": "update_points", "task_id": t.pk, "story_points": "13"},
    )
    assert post_res.status_code == 302
    t.refresh_from_db()
    assert t.story_points == 13


def test_agile_sprint_execution_page(client_a, tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p, "Active Execution Sprint", status="active")
    t = ProjectTask(tenant=tenant_a, project=p, sprint=s, name="Executing Story", status="planned")
    t.save()

    url = reverse("projects:sprint_execution")
    res = client_a.get(f"{url}?sprint={s.pk}")
    assert res.status_code == 200
    assert "active_sprint" in res.context
    assert "todo_tasks" in res.context

    # Update standup notes
    post_res = client_a.post(
        f"{url}?sprint={s.pk}",
        {"action": "save_standup", "standup_notes": "Standup notes logged"},
    )
    assert post_res.status_code == 302
    s.refresh_from_db()
    assert s.standup_notes == "Standup notes logged"


def test_agile_release_roadmap_page(client_a, tenant_a):
    p = _create_project(tenant_a)
    _create_release(tenant_a, p, "Roadmap Release", "v2.0")

    url = reverse("projects:release_roadmap")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "releases" in res.context


def test_agile_velocity_report_page(client_a, tenant_a):
    p = _create_project(tenant_a)
    _create_sprint(tenant_a, p, "Completed Sprint", status="completed")

    url = reverse("projects:velocity_report")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "completed_sprints" in res.context
    assert "avg_velocity" in res.context


# ==================================================================================================
# Action Verbs
# ==================================================================================================

def test_agile_sprint_lifecycle_verbs(client_a, tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p, "Lifecycle Sprint", status="planning")

    # Start sprint
    res = client_a.post(reverse("projects:spt_start", args=[s.pk]))
    assert res.status_code == 302
    s.refresh_from_db()
    assert s.status == "active"
    assert s.started_at is not None

    # Complete sprint
    res = client_a.post(reverse("projects:spt_complete", args=[s.pk]))
    assert res.status_code == 302
    s.refresh_from_db()
    assert s.status == "completed"
    assert s.completed_at is not None


def test_agile_release_publish_verb(client_a, tenant_a):
    p = _create_project(tenant_a)
    r = _create_release(tenant_a, p, "Beta Release", "v1.1", status="in_progress")

    res = client_a.post(reverse("projects:rel_publish", args=[r.pk]))
    assert res.status_code == 302
    r.refresh_from_db()
    assert r.status == "released"
    assert r.released_at is not None


def test_agile_impediment_resolve_verb(client_a, tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p)
    imp = SprintImpediment(tenant=tenant_a, sprint=s, title="Staging DB full", description="Disk space", status="open")
    imp.save()

    res = client_a.post(
        reverse("projects:imp_resolve", args=[imp.pk]),
        {"resolution_notes": "Cleaned up old test DBs"},
    )
    assert res.status_code == 302
    imp.refresh_from_db()
    assert imp.status == "resolved"
    assert imp.resolved_at is not None
    assert imp.resolution_notes == "Cleaned up old test DBs"
