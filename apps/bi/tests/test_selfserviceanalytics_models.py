"""Unit tests for Sub-module 10.10 Self-Service & Ad-Hoc Analytics models.

Models covered:
- AdHocQuery (BAHQ)
- AdHocCalculatedField (BACF)
- DataBlendDefinition (BBLD)
- SavedAnalysisView (BSAV)
"""
import pytest
from django.db import IntegrityError, transaction

from apps.bi.models import (
    AdHocCalculatedField,
    AdHocQuery,
    DataBlendDefinition,
    SavedAnalysisView,
)

_SELFSERVICEANALYTICS_VALID_BADGES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
}


def _selfserviceanalytics_assert_valid_badge(badge):
    """Helper to verify badge is in valid color-named badge classes and not purple."""
    assert badge in _SELFSERVICEANALYTICS_VALID_BADGES
    assert badge != "badge-purple"


# ---------------------------------------------------------------------------
# AdHocQuery Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_query_creation(adhoc_query_a):
    assert adhoc_query_a.pk is not None
    assert adhoc_query_a.number.startswith("BAHQ-")
    assert str(adhoc_query_a) == f"{adhoc_query_a.name} ({adhoc_query_a.number})"
    assert adhoc_query_a.status == "active"
    assert adhoc_query_a.source_type == "semantic_model"


@pytest.mark.django_db
def test_selfserviceanalytics_query_slug_uniqueness(tenant_a, admin_user):
    AdHocQuery.objects.create(
        tenant=tenant_a,
        name="Unique Query",
        slug="unique-query",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AdHocQuery.objects.create(
                tenant=tenant_a,
                name="Another Unique Query",
                slug="unique-query",
                created_by=admin_user,
            )


@pytest.mark.django_db
def test_selfserviceanalytics_query_cross_tenant_slug(tenant_a, tenant_b, admin_user, admin_user_b):
    q_a = AdHocQuery.objects.create(
        tenant=tenant_a,
        name="Shared Slug",
        slug="shared-slug",
        created_by=admin_user,
    )
    q_b = AdHocQuery.objects.create(
        tenant=tenant_b,
        name="Shared Slug",
        slug="shared-slug",
        created_by=admin_user_b,
    )
    assert q_a.slug == q_b.slug
    assert q_a.tenant != q_b.tenant


# ---------------------------------------------------------------------------
# AdHocCalculatedField Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_creation(adhoc_calculated_field_a):
    assert adhoc_calculated_field_a.pk is not None
    assert adhoc_calculated_field_a.number.startswith("BACF-")
    assert str(adhoc_calculated_field_a) == f"{adhoc_calculated_field_a.display_label} ({adhoc_calculated_field_a.number})"
    assert adhoc_calculated_field_a.is_valid is True


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_badge_palette(adhoc_calculated_field_a):
    badge = adhoc_calculated_field_a.badge_return_type
    _selfserviceanalytics_assert_valid_badge(badge)
    adhoc_calculated_field_a.return_type = "percentage"
    _selfserviceanalytics_assert_valid_badge(adhoc_calculated_field_a.badge_return_type)
    _selfserviceanalytics_assert_valid_badge(adhoc_calculated_field_a.badge_mode)


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_unique_per_query(tenant_a, adhoc_query_a, adhoc_calculated_field_a):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AdHocCalculatedField.objects.create(
                tenant=tenant_a,
                query=adhoc_query_a,
                field_name=adhoc_calculated_field_a.field_name,
                display_label="Duplicate Profit Margin",
                formula_expression="[revenue] - [cost]",
            )


# ---------------------------------------------------------------------------
# DataBlendDefinition Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_creation(data_blend_definition_a):
    assert data_blend_definition_a.pk is not None
    assert data_blend_definition_a.number.startswith("BBLD-")
    assert str(data_blend_definition_a) == f"{data_blend_definition_a.name} ({data_blend_definition_a.number})"
    assert data_blend_definition_a.join_type == "left_outer"


@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_badge_palette(data_blend_definition_a):
    _selfserviceanalytics_assert_valid_badge(data_blend_definition_a.badge_join)
    _selfserviceanalytics_assert_valid_badge(data_blend_definition_a.badge_status)

    data_blend_definition_a.join_type = "full_outer"
    _selfserviceanalytics_assert_valid_badge(data_blend_definition_a.badge_join)


@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_slug_uniqueness(tenant_a, admin_user):
    DataBlendDefinition.objects.create(
        tenant=tenant_a,
        name="Unique Blend",
        slug="unique-blend",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DataBlendDefinition.objects.create(
                tenant=tenant_a,
                name="Duplicate Blend",
                slug="unique-blend",
                created_by=admin_user,
            )


# ---------------------------------------------------------------------------
# SavedAnalysisView Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_creation(saved_analysis_view_a):
    assert saved_analysis_view_a.pk is not None
    assert saved_analysis_view_a.number.startswith("BSAV-")
    assert str(saved_analysis_view_a) == f"{saved_analysis_view_a.name} ({saved_analysis_view_a.number})"
    assert saved_analysis_view_a.sharing_scope == "tenant_public"
    assert saved_analysis_view_a.view_count == 0


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_badge_scope(saved_analysis_view_a):
    _selfserviceanalytics_assert_valid_badge(saved_analysis_view_a.badge_scope)
    saved_analysis_view_a.sharing_scope = "personal"
    _selfserviceanalytics_assert_valid_badge(saved_analysis_view_a.badge_scope)
    saved_analysis_view_a.sharing_scope = "team"
    _selfserviceanalytics_assert_valid_badge(saved_analysis_view_a.badge_scope)


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_increment_count(saved_analysis_view_a):
    assert saved_analysis_view_a.view_count == 0
    saved_analysis_view_a.view_count += 1
    saved_analysis_view_a.save(update_fields=["view_count"])
    saved_analysis_view_a.refresh_from_db()
    assert saved_analysis_view_a.view_count == 1
