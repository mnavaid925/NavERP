"""View unit tests for Sub-module 10.10 Self-Service & Ad-Hoc Analytics.

Endpoints tested:
- AdHocQuery CRUD, composer, execute, export
- AdHocCalculatedField CRUD, validate
- DataBlendDefinition CRUD, preview
- SavedAnalysisView CRUD, explore, share, clone
"""
import json
import pytest
from django.urls import reverse

from apps.bi.models import (
    AdHocCalculatedField,
    AdHocQuery,
    DataBlendDefinition,
    SavedAnalysisView,
)


# ---------------------------------------------------------------------------
# AdHocQuery View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_query_list_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "queries" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert adhoc_query_a.name in resp.content.decode()


@pytest.mark.django_db
def test_selfserviceanalytics_query_list_filter(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_list")
    resp = client_a.get(url, {"status": "active", "source_type": "semantic_model"})
    assert resp.status_code == 200
    assert len(resp.context["queries"]) >= 1


@pytest.mark.django_db
def test_selfserviceanalytics_query_create_view(client_a, tenant_a):
    url = reverse("bi:ad_hoc_query_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    data = {
        "name": "New Regional Performance",
        "source_type": "semantic_model",
        "visualization_type": "bar_chart",
        "row_limit": 300,
        "status": "draft",
    }
    resp_post = client_a.post(url, data)
    assert resp_post.status_code == 302
    created = AdHocQuery.objects.filter(tenant=tenant_a, slug="new-regional-performance").first()
    assert created is not None
    assert created.row_limit == 300


@pytest.mark.django_db
def test_selfserviceanalytics_query_detail_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_detail", kwargs={"pk": adhoc_query_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["query"] == adhoc_query_a
    assert "calculated_fields" in resp.context
    assert "saved_views" in resp.context


@pytest.mark.django_db
def test_selfserviceanalytics_query_edit_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_edit", kwargs={"pk": adhoc_query_a.pk})
    resp = client_a.post(
        url,
        {
            "name": "Updated Acme Query Title",
            "source_type": adhoc_query_a.source_type,
            "visualization_type": adhoc_query_a.visualization_type,
            "row_limit": 150,
            "status": "active",
        },
    )
    assert resp.status_code == 302
    adhoc_query_a.refresh_from_db()
    assert adhoc_query_a.name == "Updated Acme Query Title"
    assert adhoc_query_a.row_limit == 150


@pytest.mark.django_db
def test_selfserviceanalytics_query_composer_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_composer", kwargs={"pk": adhoc_query_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["query"] == adhoc_query_a


@pytest.mark.django_db
def test_selfserviceanalytics_query_execute_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_execute", kwargs={"pk": adhoc_query_a.pk})
    # GET is rejected with 405 (must be POST)
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST succeeds with JSON result
    resp_post = client_a.post(url)
    assert resp_post.status_code == 200
    payload = json.loads(resp_post.content.decode())
    assert payload["status"] == "success"
    assert "columns" in payload
    assert "rows" in payload


@pytest.mark.django_db
def test_selfserviceanalytics_query_export_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_export", kwargs={"pk": adhoc_query_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "attachment;" in resp["Content-Disposition"]


@pytest.mark.django_db
def test_selfserviceanalytics_query_delete_view(client_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_query_delete", kwargs={"pk": adhoc_query_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not AdHocQuery.objects.filter(pk=adhoc_query_a.pk).exists()


# ---------------------------------------------------------------------------
# AdHocCalculatedField View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_list_view(client_a, adhoc_calculated_field_a):
    url = reverse("bi:ad_hoc_calculated_field_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "calculated_fields" in resp.context


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_create_view(client_a, tenant_a, adhoc_query_a):
    url = reverse("bi:ad_hoc_calculated_field_create")
    data = {
        "query": adhoc_query_a.pk,
        "display_label": "Tax Adjusted Margin",
        "formula_expression": "[revenue] * 0.85",
        "return_type": "currency",
        "aggregation_mode": "formula",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    created = AdHocCalculatedField.objects.filter(tenant=tenant_a, field_name="tax_adjusted_margin").first()
    assert created is not None


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_validate_view(client_a):
    url = reverse("bi:ad_hoc_calculated_field_validate")
    resp_valid = client_a.get(url, {"formula": "([rev] - [cost]) / [rev]"})
    assert resp_valid.status_code == 200
    data_valid = json.loads(resp_valid.content.decode())
    assert data_valid["valid"] is True

    resp_invalid = client_a.get(url, {"formula": "[rev - [cost]"})
    assert resp_invalid.status_code == 200
    data_invalid = json.loads(resp_invalid.content.decode())
    assert data_invalid["valid"] is False


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_delete_view(client_a, adhoc_calculated_field_a):
    url = reverse("bi:ad_hoc_calculated_field_delete", kwargs={"pk": adhoc_calculated_field_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not AdHocCalculatedField.objects.filter(pk=adhoc_calculated_field_a.pk).exists()


# ---------------------------------------------------------------------------
# DataBlendDefinition View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_list_view(client_a, data_blend_definition_a):
    url = reverse("bi:data_blend_definition_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "blends" in resp.context
    assert data_blend_definition_a in resp.context["blends"]
    assert data_blend_definition_a.slug in resp.content.decode()


@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_create_view(client_a, tenant_a):
    url = reverse("bi:data_blend_definition_create")
    data = {
        "name": "Customer Support Tickets Blend",
        "primary_source_type": "semantic_model",
        "secondary_source_type": "warehouse_table",
        "join_type": "left_outer",
        "cardinality": "many_to_one",
        "collision_resolution": "prefix_secondary",
        "join_keys_mapping_json": '[{"primary": "cust_id", "secondary": "id"}]',
        "status": "active",
    }
    resp = client_a.post(url, data)
    assert resp.status_code == 302
    created = DataBlendDefinition.objects.filter(tenant=tenant_a, slug="customer-support-tickets-blend").first()
    assert created is not None


@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_preview_view(client_a, data_blend_definition_a):
    url = reverse("bi:data_blend_definition_preview", kwargs={"pk": data_blend_definition_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["blend"] == data_blend_definition_a


@pytest.mark.django_db
def test_selfserviceanalytics_data_blend_delete_view(client_a, data_blend_definition_a):
    url = reverse("bi:data_blend_definition_delete", kwargs={"pk": data_blend_definition_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not DataBlendDefinition.objects.filter(pk=data_blend_definition_a.pk).exists()


# ---------------------------------------------------------------------------
# SavedAnalysisView View Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_list_view(client_a, saved_analysis_view_a):
    url = reverse("bi:saved_analysis_view_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "views" in resp.context
    assert saved_analysis_view_a.name in resp.content.decode()


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_detail_view(client_a, saved_analysis_view_a):
    url = reverse("bi:saved_analysis_view_detail", kwargs={"pk": saved_analysis_view_a.pk})
    initial_views = saved_analysis_view_a.view_count
    resp = client_a.get(url)
    assert resp.status_code == 200
    saved_analysis_view_a.refresh_from_db()
    assert saved_analysis_view_a.view_count == initial_views + 1


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_explore_view(client_a, saved_analysis_view_a):
    url = reverse("bi:saved_analysis_view_explore", kwargs={"pk": saved_analysis_view_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["view_obj"] == saved_analysis_view_a


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_share_view(client_a, saved_analysis_view_a):
    url = reverse("bi:saved_analysis_view_share", kwargs={"pk": saved_analysis_view_a.pk})
    resp = client_a.post(url, {"sharing_scope": "team"})
    assert resp.status_code == 302
    saved_analysis_view_a.refresh_from_db()
    assert saved_analysis_view_a.sharing_scope == "team"


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_clone_view(client_a, saved_analysis_view_a):
    url = reverse("bi:saved_analysis_view_clone", kwargs={"pk": saved_analysis_view_a.pk})
    # GET is rejected with 405 (requires POST)
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # Clone first time
    resp_post_1 = client_a.post(url)
    assert resp_post_1.status_code == 302

    # Clone second time (verifies slug collision de-duplication fix)
    resp_post_2 = client_a.post(url)
    assert resp_post_2.status_code == 302

    # Assert multiple clones exist with unique slugs
    clones = SavedAnalysisView.objects.filter(parent_view=saved_analysis_view_a)
    assert clones.count() == 2
    slugs = set(c.slug for c in clones)
    assert len(slugs) == 2


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_delete_view(client_a, saved_analysis_view_a):
    url = reverse("bi:saved_analysis_view_delete", kwargs={"pk": saved_analysis_view_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not SavedAnalysisView.objects.filter(pk=saved_analysis_view_a.pk).exists()
