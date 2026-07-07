"""Bounded-query (N+1) guards for HRM 3.21 Performance Improvement list/detail views — mirrors
TestFeedbackQueryCount in test_feedback_views.py. Flat query count as rows grow on pip_list/
warningletter_list/coachingnote_list; warningletter_detail's prior_warnings must not scale with
warning-letter history depth."""
import datetime

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestPIPListQueryCount:
    def test_pip_list_bounded_queries_flat(
        self, client_a, tenant_a, employee_a, employee_a2, django_assert_max_num_queries
    ):
        from apps.hrm.models import PerformanceImprovementPlan
        for i in range(8):
            PerformanceImprovementPlan.objects.create(
                tenant=tenant_a, subject=employee_a, manager=employee_a2,
                performance_issue=f"Issue {i}", expected_standards="x", improvement_goals="x",
                measurement_criteria="x",
                start_date=datetime.date(2026, 1, i + 1), end_date=datetime.date(2026, 4, i + 1),
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:pip_list"))


class TestWarningLetterListQueryCount:
    def test_warningletter_list_bounded_queries_flat(
        self, client_a, tenant_a, employee_a, employee_a2, django_assert_max_num_queries
    ):
        from apps.hrm.models import WarningLetter
        for i in range(8):
            WarningLetter.objects.create(
                tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
                incident_date=datetime.date(2026, 1, i + 1), description=f"Incident {i}",
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:warningletter_list"))


class TestCoachingNoteListQueryCount:
    def test_coachingnote_list_bounded_queries_flat(
        self, client_a, tenant_a, employee_a, employee_a2, django_assert_max_num_queries
    ):
        from apps.hrm.models import CoachingNote
        for i in range(8):
            CoachingNote.objects.create(
                tenant=tenant_a, employee=employee_a, coach=employee_a2, content=f"Note {i}",
            )
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:coachingnote_list"))


class TestWarningLetterDetailPriorWarningsQueryCount:
    def test_prior_warnings_query_count_does_not_scale_with_history_depth(
        self, client_a, tenant_a, employee_a, employee_a2, django_assert_max_num_queries
    ):
        """warningletter_detail's prior_warnings context is DB-limited (``prior[:10]``) — the query
        count against a deep history (20 earlier letters) must be the same fixed shape as a shallow
        one, not grow per prior row."""
        from apps.hrm.models import WarningLetter
        for i in range(20):
            WarningLetter.objects.create(
                tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
                incident_date=datetime.date(2026, 1, i + 1), description=f"Prior incident {i}",
                status="issued",
            )
        latest = WarningLetter.objects.create(
            tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
            incident_date=datetime.date(2026, 6, 1), description="Latest incident", status="issued",
        )
        with django_assert_max_num_queries(12):
            resp = client_a.get(reverse("hrm:warningletter_detail", args=[latest.pk]))
        assert len(resp.context["prior_warnings"]) == 10  # capped at 10, not all 20
