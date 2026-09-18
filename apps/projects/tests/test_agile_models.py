"""Projects 7.13 — Agile & Scrum Management model tests.

Covers:
- Sprint [SPT-]
- ProjectEpic [EPC-]
- ProjectRelease [REL-]
- SprintImpediment [IMP-]
- SprintRetrospective [RET-]
- In-place ProjectTask extensions (story_points, sprint, epic, release, is_in_backlog)
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

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

_NUMBERED_MODELS = [
    (Sprint, "SPT"),
    (ProjectEpic, "EPC"),
    (ProjectRelease, "REL"),
    (SprintImpediment, "IMP"),
    (SprintRetrospective, "RET"),
]


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
# Numbering & Prefixes
# ==================================================================================================

@pytest.mark.parametrize("model,prefix", _NUMBERED_MODELS)
def test_agile_number_prefix_is_pinned(model, prefix):
    assert model.NUMBER_PREFIX == prefix


def test_agile_sprint_numbers_are_per_tenant_not_global(tenant_a, tenant_b):
    p_a = _create_project(tenant_a, "Proj A")
    p_b = _create_project(tenant_b, "Proj B")
    s_a = _create_sprint(tenant_a, p_a, "Sprint A")
    s_b = _create_sprint(tenant_b, p_b, "Sprint B")
    assert s_a.number == s_b.number
    assert s_a.tenant != s_b.tenant


def test_agile_sprint_number_mints_sequentially(tenant_a):
    p_a = _create_project(tenant_a)
    s1 = _create_sprint(tenant_a, p_a, "Sprint 1")
    s2 = _create_sprint(tenant_a, p_a, "Sprint 2")
    n1 = int(s1.number.split("-")[1])
    n2 = int(s2.number.split("-")[1])
    assert n2 == n1 + 1


# ==================================================================================================
# ProjectTask Agile In-Place Extensions
# ==================================================================================================

def test_agile_project_task_backlog_property(tenant_a):
    p = _create_project(tenant_a)
    t = ProjectTask(tenant=tenant_a, project=p, name="Backlog Task", story_points=5)
    t.save()
    assert t.is_in_backlog is True
    assert t.sprint is None

    s = _create_sprint(tenant_a, p, "Sprint 1")
    t.sprint = s
    t.save()
    assert t.is_in_backlog is False


def test_agile_project_task_story_points_validation(tenant_a):
    p = _create_project(tenant_a)
    t = ProjectTask(tenant=tenant_a, project=p, name="Invalid Points Task", story_points=150)
    with pytest.raises(ValidationError):
        t.full_clean()


# ==================================================================================================
# Sprint Derived Properties
# ==================================================================================================

def test_agile_sprint_derived_progress_and_points(tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p, "Sprint Alpha", committed_points=20)

    t1 = ProjectTask(tenant=tenant_a, project=p, sprint=s, name="Task 1", story_points=8, status="done")
    t1.save()
    t2 = ProjectTask(tenant=tenant_a, project=p, sprint=s, name="Task 2", story_points=12, status="in_progress")
    t2.save()

    assert s.total_points == 20
    assert s.completed_points == 8
    assert s.remaining_points == 12
    assert s.completion_rate == 40
    assert s.task_count == 2
    assert s.completed_task_count == 1


def test_agile_sprint_overdue_flag(tenant_a):
    p = _create_project(tenant_a)
    today = timezone.localdate()
    yesterday = today - timezone.timedelta(days=1)
    s = _create_sprint(tenant_a, p, "Active Late Sprint", status="active", end_date=yesterday)
    assert s.is_overdue is True

    s_done = _create_sprint(tenant_a, p, "Done Late Sprint", status="completed", end_date=yesterday)
    assert s_done.is_overdue is False


# ==================================================================================================
# ProjectEpic Derived Properties
# ==================================================================================================

def test_agile_epic_derived_rollups(tenant_a):
    p = _create_project(tenant_a)
    e = _create_epic(tenant_a, p, "Checkout Epic")

    t1 = ProjectTask(tenant=tenant_a, project=p, epic=e, name="Story 1", story_points=5, status="done")
    t1.save()
    t2 = ProjectTask(tenant=tenant_a, project=p, epic=e, name="Story 2", story_points=15, status="in_progress")
    t2.save()

    assert e.total_points == 20
    assert e.completed_points == 5
    assert e.progress_percent == 25
    assert e.task_count == 2
    assert e.done_task_count == 1
    assert str(e) == f"{e.number} — Checkout Epic"


# ==================================================================================================
# ProjectRelease Derived Properties
# ==================================================================================================

def test_agile_release_derived_rollups(tenant_a):
    p = _create_project(tenant_a)
    r = _create_release(tenant_a, p, "v1.0 Release", version_tag="v1.0.0")

    t1 = ProjectTask(tenant=tenant_a, project=p, release=r, name="Release Story 1", status="done")
    t1.save()
    t2 = ProjectTask(tenant=tenant_a, project=p, release=r, name="Release Story 2", status="planned")
    t2.save()

    assert r.total_stories == 2
    assert r.completed_stories == 1
    assert r.progress_percent == 50
    assert str(r) == f"{r.number} — v1.0 Release (v1.0.0)"


# ==================================================================================================
# SprintImpediment & SprintRetrospective
# ==================================================================================================

def test_agile_sprint_impediment_lifecycle(tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p, "Sprint Blocked")
    imp = SprintImpediment(
        tenant=tenant_a,
        sprint=s,
        title="CI Runner Out of Memory",
        description="Build worker dying on test suite run",
        severity="critical",
        status="open",
    )
    imp.save()
    assert imp.status == "open"
    assert str(imp) == f"{imp.number} — CI Runner Out of Memory [critical]"


def test_agile_sprint_retrospective_score_validation(tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p, "Sprint Retro")
    ret = SprintRetrospective(
        tenant=tenant_a,
        sprint=s,
        sentiment_score=Decimal("6.0"),
    )
    with pytest.raises(ValidationError):
        ret.full_clean()
