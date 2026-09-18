"""Projects 7.13 — Agile & Scrum Management form tests.

Covers:
- SprintForm
- ProjectEpicForm
- ProjectReleaseForm
- SprintImpedimentForm
- SprintRetrospectiveForm
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.projects.forms.AgileScrumManagement import (
    ProjectEpicForm,
    ProjectReleaseForm,
    SprintForm,
    SprintImpedimentForm,
    SprintRetrospectiveForm,
)
from apps.projects.models import (
    Project,
    ProjectEpic,
    ProjectRelease,
    Sprint,
    SprintImpediment,
    SprintRetrospective,
)

pytestmark = pytest.mark.django_db


def _create_project(tenant, name="Agile Project"):
    p = Project(tenant=tenant, name=name, code="AGL", status="active")
    p.save()
    return p


def _create_sprint(tenant, project, name="Sprint 1"):
    s = Sprint(tenant=tenant, project=project, name=name)
    s.save()
    return s


# ==================================================================================================
# SprintForm
# ==================================================================================================

def test_agile_sprint_form_valid(tenant_a):
    p = _create_project(tenant_a)
    form = SprintForm(
        data={
            "project": p.pk,
            "name": "Sprint 1",
            "goal": "Deliver auth spike",
            "status": "planning",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.name == "Sprint 1"
    assert obj.tenant == tenant_a


def test_agile_sprint_form_rejects_cross_tenant_project(tenant_a, tenant_b):
    p_b = _create_project(tenant_b)
    form = SprintForm(
        data={
            "project": p_b.pk,
            "name": "Cross Tenant Sprint",
            "status": "planning",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "project" in form.errors


# ==================================================================================================
# ProjectEpicForm
# ==================================================================================================

def test_agile_epic_form_valid(tenant_a):
    p = _create_project(tenant_a)
    form = ProjectEpicForm(
        data={
            "project": p.pk,
            "name": "Checkout Modernization",
            "status": "in_progress",
            "color_code": "#3b82f6",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.name == "Checkout Modernization"


def test_agile_epic_form_color_code_validation(tenant_a):
    p = _create_project(tenant_a)
    form = ProjectEpicForm(
        data={
            "project": p.pk,
            "name": "Bad Color Epic",
            "status": "draft",
            "color_code": "not-a-color",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "color_code" in form.errors


# ==================================================================================================
# ProjectReleaseForm
# ==================================================================================================

def test_agile_release_form_valid(tenant_a):
    p = _create_project(tenant_a)
    form = ProjectReleaseForm(
        data={
            "project": p.pk,
            "name": "v1.0 Release",
            "version_tag": "v1.0.0",
            "status": "unreleased",
            "feature_flags": "CHECKOUT_V2=true",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.version_tag == "v1.0.0"


# ==================================================================================================
# SprintImpedimentForm
# ==================================================================================================

def test_agile_impediment_form_valid(tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p)
    form = SprintImpedimentForm(
        data={
            "sprint": s.pk,
            "title": "Build cluster down",
            "description": "Docker daemon failing",
            "severity": "critical",
            "status": "open",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.severity == "critical"


def test_agile_impediment_form_rejects_cross_tenant_sprint(tenant_a, tenant_b):
    p_b = _create_project(tenant_b)
    s_b = _create_sprint(tenant_b, p_b)
    form = SprintImpedimentForm(
        data={
            "sprint": s_b.pk,
            "title": "Cross Tenant Impediment",
            "description": "Exploit attempt",
            "severity": "high",
            "status": "open",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "sprint" in form.errors


# ==================================================================================================
# SprintRetrospectiveForm
# ==================================================================================================

def test_agile_retrospective_form_valid(tenant_a):
    p = _create_project(tenant_a)
    s = _create_sprint(tenant_a, p)
    form = SprintRetrospectiveForm(
        data={
            "sprint": s.pk,
            "conducted_date": str(timezone.localdate()),
            "status": "open",
            "sentiment_score": "4.5",
            "what_went_well": "Delivered features ahead of time",
            "what_needs_improvement": "More unit test coverage needed",
            "action_items": "Set up CI gate",
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.sentiment_score == Decimal("4.5")
