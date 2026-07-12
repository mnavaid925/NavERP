"""Tests for HRM 3.27 Communication Hub models: ``Announcement`` [ANN-], ``Survey`` [SUR-] +
``SurveyResponse`` (no auto-number, ``unique_together (survey, employee)`` respond-once),
``Suggestion`` [SUG-] (clones the 3.26 request lifecycle) — auto-number prefixes, ``__str__``,
default statuses/choices, ``Announcement.clean()``'s audience/target matching rule,
``unique_together (tenant, number)``, the ``(tenant, employee, status)`` / ``(tenant, status)``
indexes, and that each Meta/CRUD form excludes the workflow-owned/system fields. Mirrors
test_requests_models.py conventions."""
import json

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

pytestmark = pytest.mark.django_db


# ================================================================ Announcement
class TestAnnouncementModel:
    def test_number_prefix_ann(self, announcement_a):
        assert announcement_a.number.startswith("ANN-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, admin_user):
        from apps.hrm.models import Announcement
        a1 = Announcement.objects.create(tenant=tenant_a, title="A", body="a", author=admin_user)
        a2 = Announcement.objects.create(tenant=tenant_a, title="B", body="b", author=admin_user)
        assert a1.number != a2.number
        assert a1.number.startswith("ANN-")
        assert a2.number.startswith("ANN-")

    def test_unique_together_tenant_number(self, tenant_a, announcement_a):
        from apps.hrm.models import Announcement
        with pytest.raises(IntegrityError):
            Announcement.objects.create(
                tenant=tenant_a, number=announcement_a.number, title="dup", body="dup")

    def test_default_status_draft(self, announcement_a):
        assert announcement_a.status == "draft"

    def test_default_category_general(self, announcement_a):
        assert announcement_a.category == "general"

    def test_default_audience_type_all(self, announcement_a):
        assert announcement_a.audience_type == "all"

    def test_default_is_pinned_false(self, announcement_a):
        assert announcement_a.is_pinned is False

    def test_default_published_at_and_expires_at_none(self, announcement_a):
        assert announcement_a.published_at is None
        assert announcement_a.expires_at is None

    def test_status_choices(self):
        from apps.hrm.models import Announcement
        values = [v for v, _ in Announcement.STATUS_CHOICES]
        assert values == ["draft", "published", "archived"]

    def test_audience_type_choices(self):
        from apps.hrm.models import Announcement
        values = [v for v, _ in Announcement.AUDIENCE_TYPE_CHOICES]
        assert values == ["all", "department", "designation"]

    def test_published_at_not_editable(self):
        from apps.hrm.models import Announcement
        assert Announcement._meta.get_field("published_at").editable is False

    def test_author_not_editable(self):
        from apps.hrm.models import Announcement
        assert Announcement._meta.get_field("author").editable is False

    def test_str_contains_number_and_title(self, announcement_a):
        s = str(announcement_a)
        assert announcement_a.number in s
        assert "Office Closure Notice" in s

    def test_str_falls_back_to_title_when_no_number(self, tenant_a):
        from apps.hrm.models import Announcement
        ann = Announcement(tenant=tenant_a, title="Untitled Draft", body="x")
        assert str(ann) == "Untitled Draft"

    def test_tenant_scoping(self, announcement_a, tenant_a):
        assert announcement_a.tenant_id == tenant_a.pk

    def test_clean_raises_when_department_audience_missing_target(self, tenant_a):
        from apps.hrm.models import Announcement
        ann = Announcement(tenant=tenant_a, title="X", body="Y", audience_type="department")
        with pytest.raises(ValidationError) as exc:
            ann.full_clean(exclude=["number"])
        assert "target_department" in exc.value.message_dict

    def test_clean_passes_when_department_audience_has_target(self, tenant_a, dept_a):
        from apps.hrm.models import Announcement
        ann = Announcement(tenant=tenant_a, title="X", body="Y",
                            audience_type="department", target_department=dept_a)
        ann.full_clean(exclude=["number"])  # must not raise

    def test_clean_raises_when_designation_audience_missing_target(self, tenant_a):
        from apps.hrm.models import Announcement
        ann = Announcement(tenant=tenant_a, title="X", body="Y", audience_type="designation")
        with pytest.raises(ValidationError) as exc:
            ann.full_clean(exclude=["number"])
        assert "target_designation" in exc.value.message_dict

    def test_clean_passes_when_designation_audience_has_target(self, tenant_a, designation_a):
        from apps.hrm.models import Announcement
        ann = Announcement(tenant=tenant_a, title="X", body="Y",
                            audience_type="designation", target_designation=designation_a)
        ann.full_clean(exclude=["number"])  # must not raise

    def test_clean_passes_for_audience_all_without_targets(self, tenant_a):
        from apps.hrm.models import Announcement
        ann = Announcement(tenant=tenant_a, title="X", body="Y", audience_type="all")
        ann.full_clean(exclude=["number"])  # must not raise

    def test_tenant_status_index_exists(self):
        from apps.hrm.models import Announcement
        idx_fields = [tuple(idx.fields) for idx in Announcement._meta.indexes]
        assert ("tenant", "status") in idx_fields


# ================================================================ Survey
class TestSurveyModel:
    def test_number_prefix_sur(self, survey_a):
        assert survey_a.number.startswith("SUR-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, admin_user, survey_questions):
        from apps.hrm.models import Survey
        s1 = Survey.objects.create(tenant=tenant_a, title="A", questions=survey_questions, author=admin_user)
        s2 = Survey.objects.create(tenant=tenant_a, title="B", questions=survey_questions, author=admin_user)
        assert s1.number != s2.number
        assert s1.number.startswith("SUR-")
        assert s2.number.startswith("SUR-")

    def test_unique_together_tenant_number(self, tenant_a, survey_a):
        from apps.hrm.models import Survey
        with pytest.raises(IntegrityError):
            Survey.objects.create(tenant=tenant_a, number=survey_a.number, title="dup")

    def test_default_status_draft(self, survey_a):
        assert survey_a.status == "draft"

    def test_default_is_anonymous_false(self, survey_a):
        assert survey_a.is_anonymous is False

    def test_default_questions_empty_list(self, tenant_a, admin_user):
        from apps.hrm.models import Survey
        s = Survey.objects.create(tenant=tenant_a, title="No Questions Yet", author=admin_user)
        assert s.questions == []

    def test_status_choices(self):
        from apps.hrm.models import Survey
        values = [v for v, _ in Survey.STATUS_CHOICES]
        assert values == ["draft", "open", "closed"]

    def test_str_contains_number_and_title(self, survey_a):
        s = str(survey_a)
        assert survey_a.number in s
        assert "Engagement Pulse Q3" in s

    def test_str_falls_back_to_title_when_no_number(self, tenant_a):
        from apps.hrm.models import Survey
        s = Survey(tenant=tenant_a, title="Draft Survey")
        assert str(s) == "Draft Survey"

    def test_tenant_scoping(self, survey_a, tenant_a):
        assert survey_a.tenant_id == tenant_a.pk

    def test_tenant_status_index_exists(self):
        from apps.hrm.models import Survey
        idx_fields = [tuple(idx.fields) for idx in Survey._meta.indexes]
        assert ("tenant", "status") in idx_fields


# ================================================================ SurveyResponse
class TestSurveyResponseModel:
    def test_str(self, survey_response_a):
        s = str(survey_response_a)
        assert str(survey_response_a.survey) in s
        assert str(survey_response_a.employee) in s

    def test_unique_together_survey_employee_blocks_second_response(
        self, tenant_a, open_survey_a, employee_a, survey_response_a
    ):
        from apps.hrm.models import SurveyResponse
        with pytest.raises(IntegrityError):
            SurveyResponse.objects.create(
                tenant=tenant_a, survey=open_survey_a, employee=employee_a, answers={"0": "5"})

    def test_different_employee_can_respond_to_same_survey(
        self, tenant_a, open_survey_a, employee_a2, survey_response_a
    ):
        from apps.hrm.models import SurveyResponse
        second = SurveyResponse.objects.create(
            tenant=tenant_a, survey=open_survey_a, employee=employee_a2, answers={"0": "3"})
        assert second.pk != survey_response_a.pk

    def test_submitted_at_auto_now_add(self, survey_response_a):
        assert survey_response_a.submitted_at is not None

    def test_no_number_field(self, survey_response_a):
        assert not hasattr(survey_response_a, "number")

    def test_tenant_scoping(self, survey_response_a, tenant_a):
        assert survey_response_a.tenant_id == tenant_a.pk

    def test_tenant_survey_index_exists(self):
        from apps.hrm.models import SurveyResponse
        idx_fields = [tuple(idx.fields) for idx in SurveyResponse._meta.indexes]
        assert ("tenant", "survey") in idx_fields

    def test_tenant_employee_index_exists(self):
        from apps.hrm.models import SurveyResponse
        idx_fields = [tuple(idx.fields) for idx in SurveyResponse._meta.indexes]
        assert ("tenant", "employee") in idx_fields


# ================================================================ Suggestion
class TestSuggestionModel:
    def test_number_prefix_sug(self, suggestion_a):
        assert suggestion_a.number.startswith("SUG-")

    def test_number_assigned_once_per_tenant_sequence(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import Suggestion
        s1 = Suggestion.objects.create(tenant=tenant_a, employee=employee_a, title="A", body="a")
        s2 = Suggestion.objects.create(tenant=tenant_a, employee=employee_a2, title="B", body="b")
        assert s1.number != s2.number
        assert s1.number.startswith("SUG-")
        assert s2.number.startswith("SUG-")

    def test_unique_together_tenant_number(self, tenant_a, suggestion_a):
        from apps.hrm.models import Suggestion
        with pytest.raises(IntegrityError):
            Suggestion.objects.create(
                tenant=tenant_a, number=suggestion_a.number, employee=suggestion_a.employee,
                title="dup", body="dup")

    def test_default_status_draft(self, suggestion_a):
        assert suggestion_a.status == "draft"

    def test_default_category_other(self, tenant_a, employee_a):
        from apps.hrm.models import Suggestion
        s = Suggestion.objects.create(tenant=tenant_a, employee=employee_a, title="X", body="y")
        assert s.category == "other"

    def test_default_is_anonymous_false(self, suggestion_a):
        assert suggestion_a.is_anonymous is False

    def test_open_statuses(self):
        from apps.hrm.models import Suggestion
        assert Suggestion.OPEN_STATUSES == ("draft", "pending")

    def test_status_choices_include_implemented_tail_state(self):
        from apps.hrm.models import Suggestion
        values = [v for v, _ in Suggestion.STATUS_CHOICES]
        assert values == ["draft", "pending", "approved", "rejected", "cancelled", "implemented"]

    def test_approved_label_is_accepted(self):
        from apps.hrm.models import Suggestion
        labels = dict(Suggestion.STATUS_CHOICES)
        assert labels["approved"] == "Accepted"

    def test_default_approver_and_approved_at_none(self, suggestion_a):
        assert suggestion_a.approver_id is None
        assert suggestion_a.approved_at is None

    def test_default_implemented_at_none_and_notes_blank(self, suggestion_a):
        assert suggestion_a.implemented_at is None
        assert suggestion_a.decision_note == ""
        assert suggestion_a.implementation_note == ""

    def test_implemented_at_not_editable(self):
        from apps.hrm.models import Suggestion
        assert Suggestion._meta.get_field("implemented_at").editable is False

    def test_str_contains_number_employee_and_title(self, suggestion_a):
        s = str(suggestion_a)
        assert suggestion_a.number in s
        assert "Alice Smith" in s
        assert "Add a bike rack" in s

    def test_str_falls_back_to_title_when_no_number(self, tenant_a, employee_a):
        from apps.hrm.models import Suggestion
        s = Suggestion(tenant=tenant_a, employee=employee_a, title="A Draft Idea")
        assert str(s) == "A Draft Idea"

    def test_tenant_scoping(self, suggestion_a, tenant_a):
        assert suggestion_a.tenant_id == tenant_a.pk

    def test_tenant_employee_status_index_exists(self):
        from apps.hrm.models import Suggestion
        idx_fields = [tuple(idx.fields) for idx in Suggestion._meta.indexes]
        assert ("tenant", "employee", "status") in idx_fields

    def test_tenant_status_index_exists(self):
        from apps.hrm.models import Suggestion
        idx_fields = [tuple(idx.fields) for idx in Suggestion._meta.indexes]
        assert ("tenant", "status") in idx_fields


# ================================================================ Forms exclude workflow/system fields
class TestAnnouncementFormFields:
    def test_form_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import AnnouncementForm
        fields = AnnouncementForm(tenant=None).fields
        for excluded in ("tenant", "number", "status", "published_at", "author"):
            assert excluded not in fields

    def test_form_declares_the_admin_editable_subset(self):
        from apps.hrm.forms import AnnouncementForm
        fields = AnnouncementForm(tenant=None).fields
        for included in ("title", "body", "category", "audience_type",
                          "target_department", "target_designation", "is_pinned", "expires_at"):
            assert included in fields

    def test_clean_raises_when_department_audience_missing_target(self, tenant_a):
        from apps.hrm.forms import AnnouncementForm
        form = AnnouncementForm(
            {"title": "X", "body": "Y", "category": "general", "audience_type": "department"},
            tenant=tenant_a)
        assert form.is_valid() is False
        assert "target_department" in form.errors

    def test_clean_raises_when_designation_audience_missing_target(self, tenant_a):
        from apps.hrm.forms import AnnouncementForm
        form = AnnouncementForm(
            {"title": "X", "body": "Y", "category": "general", "audience_type": "designation"},
            tenant=tenant_a)
        assert form.is_valid() is False
        assert "target_designation" in form.errors

    def test_valid_for_audience_all(self, tenant_a):
        from apps.hrm.forms import AnnouncementForm
        form = AnnouncementForm(
            {"title": "X", "body": "Y", "category": "general", "audience_type": "all"}, tenant=tenant_a)
        assert form.is_valid() is True, form.errors


class TestSurveyFormFields:
    def test_form_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import SurveyForm
        fields = SurveyForm(tenant=None).fields
        for excluded in ("tenant", "number", "status", "author"):
            assert excluded not in fields

    def test_form_declares_the_admin_editable_subset(self):
        from apps.hrm.forms import SurveyForm
        fields = SurveyForm(tenant=None).fields
        for included in ("title", "description", "questions", "is_anonymous", "opens_at", "closes_at"):
            assert included in fields

    def _data(self, questions, **overrides):
        data = {"title": "Survey", "description": "", "questions": json.dumps(questions),
                "opens_at": "", "closes_at": ""}
        data.update(overrides)
        return data

    def test_clean_questions_rejects_non_list(self, tenant_a):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(self._data({"text": "not a list"}), tenant=tenant_a)
        assert form.is_valid() is False
        assert "questions" in form.errors

    def test_clean_questions_rejects_empty_list(self, tenant_a):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(self._data([]), tenant=tenant_a)
        assert form.is_valid() is False
        assert "questions" in form.errors

    def test_clean_questions_rejects_missing_text(self, tenant_a):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(self._data([{"type": "text"}]), tenant=tenant_a)
        assert form.is_valid() is False
        assert "questions" in form.errors

    def test_clean_questions_rejects_bad_type(self, tenant_a):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(self._data([{"text": "Q1", "type": "essay"}]), tenant=tenant_a)
        assert form.is_valid() is False
        assert "questions" in form.errors

    def test_clean_questions_rejects_single_choice_without_options(self, tenant_a):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(self._data([{"text": "Q1", "type": "single_choice"}]), tenant=tenant_a)
        assert form.is_valid() is False
        assert "questions" in form.errors

    def test_clean_questions_rejects_single_choice_with_empty_options_list(self, tenant_a):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(
            self._data([{"text": "Q1", "type": "single_choice", "options": []}]), tenant=tenant_a)
        assert form.is_valid() is False
        assert "questions" in form.errors

    def test_clean_questions_accepts_valid_list(self, tenant_a, survey_questions):
        from apps.hrm.forms import SurveyForm
        form = SurveyForm(self._data(survey_questions), tenant=tenant_a)
        assert form.is_valid() is True, form.errors


class TestSuggestionFormFields:
    def test_form_excludes_workflow_and_system_fields(self):
        from apps.hrm.forms import SuggestionForm
        fields = SuggestionForm(tenant=None).fields
        for excluded in ("tenant", "employee", "number", "status", "approver", "approved_at",
                         "decision_note", "implementation_note", "implemented_at"):
            assert excluded not in fields

    def test_form_declares_the_employee_editable_subset(self):
        from apps.hrm.forms import SuggestionForm
        fields = SuggestionForm(tenant=None).fields
        for included in ("title", "body", "category", "is_anonymous"):
            assert included in fields
