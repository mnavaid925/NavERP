"""Security and access control tests for Sub-module 10.10 Self-Service & Ad-Hoc Analytics.

Security controls tested:
- @login_required on all routes (redirects anonymous requests to login)
- Cross-tenant IDOR isolation (accessing foreign tenant object returns 404)
- Intra-tenant authorization on personal saved analysis views
- HTTP method restrictions (@require_POST on delete, clone, and execute views)
- CSV formula injection escaping
"""
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.bi.models import (
    AdHocCalculatedField,
    AdHocQuery,
    DataBlendDefinition,
    SavedAnalysisView,
)


# ---------------------------------------------------------------------------
# Anonymous Authentication Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_anon_redirects(client, adhoc_query_a, adhoc_calculated_field_a, data_blend_definition_a, saved_analysis_view_a):
    urls = [
        reverse("bi:ad_hoc_query_list"),
        reverse("bi:ad_hoc_query_create"),
        reverse("bi:ad_hoc_query_detail", kwargs={"pk": adhoc_query_a.pk}),
        reverse("bi:ad_hoc_query_edit", kwargs={"pk": adhoc_query_a.pk}),
        reverse("bi:ad_hoc_query_composer", kwargs={"pk": adhoc_query_a.pk}),
        reverse("bi:ad_hoc_query_export", kwargs={"pk": adhoc_query_a.pk}),
        reverse("bi:ad_hoc_calculated_field_list"),
        reverse("bi:ad_hoc_calculated_field_create"),
        reverse("bi:ad_hoc_calculated_field_detail", kwargs={"pk": adhoc_calculated_field_a.pk}),
        reverse("bi:data_blend_definition_list"),
        reverse("bi:data_blend_definition_create"),
        reverse("bi:data_blend_definition_detail", kwargs={"pk": data_blend_definition_a.pk}),
        reverse("bi:data_blend_definition_preview", kwargs={"pk": data_blend_definition_a.pk}),
        reverse("bi:saved_analysis_view_list"),
        reverse("bi:saved_analysis_view_create"),
        reverse("bi:saved_analysis_view_detail", kwargs={"pk": saved_analysis_view_a.pk}),
        reverse("bi:saved_analysis_view_explore", kwargs={"pk": saved_analysis_view_a.pk}),
        reverse("bi:saved_analysis_view_share", kwargs={"pk": saved_analysis_view_a.pk}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"URL {url} did not redirect anonymous user"
        assert "/login/" in resp["Location"]


# ---------------------------------------------------------------------------
# Cross-Tenant IDOR Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_query_idor_404(client_a, adhoc_query_b):
    # Tenant A user accessing Tenant B query endpoints
    detail_url = reverse("bi:ad_hoc_query_detail", kwargs={"pk": adhoc_query_b.pk})
    edit_url = reverse("bi:ad_hoc_query_edit", kwargs={"pk": adhoc_query_b.pk})
    composer_url = reverse("bi:ad_hoc_query_composer", kwargs={"pk": adhoc_query_b.pk})
    execute_url = reverse("bi:ad_hoc_query_execute", kwargs={"pk": adhoc_query_b.pk})
    export_url = reverse("bi:ad_hoc_query_export", kwargs={"pk": adhoc_query_b.pk})
    delete_url = reverse("bi:ad_hoc_query_delete", kwargs={"pk": adhoc_query_b.pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.get(composer_url).status_code == 404
    assert client_a.post(execute_url).status_code == 404
    assert client_a.get(export_url).status_code == 404
    assert client_a.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_selfserviceanalytics_calc_field_idor_404(client_a, adhoc_calculated_field_b):
    detail_url = reverse("bi:ad_hoc_calculated_field_detail", kwargs={"pk": adhoc_calculated_field_b.pk})
    edit_url = reverse("bi:ad_hoc_calculated_field_edit", kwargs={"pk": adhoc_calculated_field_b.pk})
    delete_url = reverse("bi:ad_hoc_calculated_field_delete", kwargs={"pk": adhoc_calculated_field_b.pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_selfserviceanalytics_blend_idor_404(client_a, data_blend_definition_b):
    detail_url = reverse("bi:data_blend_definition_detail", kwargs={"pk": data_blend_definition_b.pk})
    edit_url = reverse("bi:data_blend_definition_edit", kwargs={"pk": data_blend_definition_b.pk})
    preview_url = reverse("bi:data_blend_definition_preview", kwargs={"pk": data_blend_definition_b.pk})
    delete_url = reverse("bi:data_blend_definition_delete", kwargs={"pk": data_blend_definition_b.pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.get(preview_url).status_code == 404
    assert client_a.post(delete_url).status_code == 404


@pytest.mark.django_db
def test_selfserviceanalytics_saved_view_idor_404(client_a, saved_analysis_view_b):
    detail_url = reverse("bi:saved_analysis_view_detail", kwargs={"pk": saved_analysis_view_b.pk})
    edit_url = reverse("bi:saved_analysis_view_edit", kwargs={"pk": saved_analysis_view_b.pk})
    explore_url = reverse("bi:saved_analysis_view_explore", kwargs={"pk": saved_analysis_view_b.pk})
    share_url = reverse("bi:saved_analysis_view_share", kwargs={"pk": saved_analysis_view_b.pk})
    clone_url = reverse("bi:saved_analysis_view_clone", kwargs={"pk": saved_analysis_view_b.pk})
    delete_url = reverse("bi:saved_analysis_view_delete", kwargs={"pk": saved_analysis_view_b.pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.get(explore_url).status_code == 404
    assert client_a.get(share_url).status_code == 404
    assert client_a.post(clone_url).status_code == 404
    assert client_a.post(delete_url).status_code == 404


# ---------------------------------------------------------------------------
# Intra-Tenant Personal View Authorization Tests (Finding I2)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_personal_view_isolation(client, tenant_a, adhoc_query_a, admin_user):
    user_owner = User.objects.create_user(
        email="owner@acme.com",
        username="owner_acme",
        password="PassWord123!",
        tenant=tenant_a,
    )
    user_other = User.objects.create_user(
        email="other@acme.com",
        username="other_acme",
        password="PassWord123!",
        tenant=tenant_a,
    )
    personal_view = SavedAnalysisView.objects.create(
        tenant=tenant_a,
        query=adhoc_query_a,
        name="Owner Confidential View",
        slug="owner-confidential-view",
        sharing_scope="personal",
        created_by=user_owner,
    )

    # User other cannot view personal view
    client.force_login(user_other)
    detail_url = reverse("bi:saved_analysis_view_detail", kwargs={"pk": personal_view.pk})
    explore_url = reverse("bi:saved_analysis_view_explore", kwargs={"pk": personal_view.pk})
    edit_url = reverse("bi:saved_analysis_view_edit", kwargs={"pk": personal_view.pk})
    delete_url = reverse("bi:saved_analysis_view_delete", kwargs={"pk": personal_view.pk})
    clone_url = reverse("bi:saved_analysis_view_clone", kwargs={"pk": personal_view.pk})

    assert client.get(detail_url).status_code == 403
    assert client.get(explore_url).status_code == 403
    assert client.get(edit_url).status_code == 403
    assert client.post(delete_url).status_code == 403
    assert client.post(clone_url).status_code == 403

    # Owner can access
    client.force_login(user_owner)
    assert client.get(detail_url).status_code == 200
    assert client.get(explore_url).status_code == 200

    # Tenant admin can access
    client.force_login(admin_user)
    assert client.get(detail_url).status_code == 200
    assert client.get(explore_url).status_code == 200


# ---------------------------------------------------------------------------
# Method Restrictions & CSV Injection Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_selfserviceanalytics_require_post_enforcement(client_a, adhoc_query_a, adhoc_calculated_field_a, data_blend_definition_a, saved_analysis_view_a):
    post_only_urls = [
        reverse("bi:ad_hoc_query_delete", kwargs={"pk": adhoc_query_a.pk}),
        reverse("bi:ad_hoc_query_execute", kwargs={"pk": adhoc_query_a.pk}),
        reverse("bi:ad_hoc_calculated_field_delete", kwargs={"pk": adhoc_calculated_field_a.pk}),
        reverse("bi:data_blend_definition_delete", kwargs={"pk": data_blend_definition_a.pk}),
        reverse("bi:saved_analysis_view_delete", kwargs={"pk": saved_analysis_view_a.pk}),
        reverse("bi:saved_analysis_view_clone", kwargs={"pk": saved_analysis_view_a.pk}),
    ]
    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 on GET for {url}"


@pytest.mark.django_db
def test_selfserviceanalytics_csv_formula_injection_defense(client_a, tenant_a, admin_user):
    # Query with formula injection attempts in field labels
    q = AdHocQuery.objects.create(
        tenant=tenant_a,
        name="Malicious CSV Query",
        slug="malicious-csv-query",
        fields_config_json=[
            {"field": "formula_1", "label": "=1+1", "type": "string"},
            {"field": "formula_2", "label": "+cmd|' /C calc'!A0", "type": "string"},
            {"field": "formula_3", "label": "@SUM(1,2)", "type": "string"},
        ],
        created_by=admin_user,
    )
    url = reverse("bi:ad_hoc_query_export", kwargs={"pk": q.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    csv_text = resp.content.decode()
    # Ensure unsafe prefixes are sanitized with single quote
    assert "'=1+1" in csv_text
    assert "'+cmd" in csv_text
    assert "'@SUM" in csv_text
