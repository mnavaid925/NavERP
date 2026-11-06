"""Security and multi-tenant isolation tests for Sub-module 10.8 Dashboards & Visualization.

Verifies:
- Cross-tenant IDOR protection (404 on all 19 object endpoints for foreign tenant objects)
- Tenant list isolation (no cross-tenant leakage in querysets)
- Cross-user bookmark privacy and sharing boundaries
- Unpublished draft dashboard access gates
- Visual canvas builder authorization gates
- Unauthenticated access redirects to login
"""
import json
import pytest
from django.urls import reverse
from apps.accounts.models import User


# ---------------------------------------------------------------------------
# 1. Cross-Tenant IDOR Protection (Tenant A accessing Tenant B -> 404)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_dashboard_idor_protection(client_a, bi_dashboard_b):
    """Assert Tenant A cannot access Tenant B dashboard endpoints (all return 404)."""
    pk = bi_dashboard_b.pk
    detail_url = reverse("bi:bi_dashboard_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:bi_dashboard_edit", kwargs={"pk": pk})
    del_url = reverse("bi:bi_dashboard_delete", kwargs={"pk": pk})
    pub_url = reverse("bi:bi_dashboard_publish", kwargs={"pk": pk})
    dupl_url = reverse("bi:bi_dashboard_duplicate", kwargs={"pk": pk})
    canvas_url = reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": pk})
    builder_url = reverse("bi:bi_dashboard_canvas_builder", kwargs={"pk": pk})
    kiosk_url = reverse("bi:bi_dashboard_kiosk_view", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404
    assert client_a.post(pub_url).status_code == 404
    assert client_a.get(dupl_url).status_code == 404
    assert client_a.post(dupl_url, {"new_title": "IDOR Clone"}).status_code == 404
    assert client_a.get(canvas_url).status_code == 404
    assert client_a.get(builder_url).status_code == 404
    assert client_a.get(kiosk_url).status_code == 404


@pytest.mark.django_db
def test_dashboards_widget_idor_protection(client_a, bi_widget_b):
    """Assert Tenant A cannot access Tenant B widget endpoints (all return 404)."""
    pk = bi_widget_b.pk
    detail_url = reverse("bi:bi_dashboard_widget_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:bi_dashboard_widget_edit", kwargs={"pk": pk})
    del_url = reverse("bi:bi_dashboard_widget_delete", kwargs={"pk": pk})
    data_url = reverse("bi:bi_dashboard_widget_data", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404
    assert client_a.get(data_url).status_code == 404


@pytest.mark.django_db
def test_dashboards_bookmark_idor_protection(client_a, bi_bookmark_b):
    """Assert Tenant A cannot access Tenant B bookmark endpoints (all return 404)."""
    pk = bi_bookmark_b.pk
    detail_url = reverse("bi:bi_dashboard_bookmark_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:bi_dashboard_bookmark_edit", kwargs={"pk": pk})
    del_url = reverse("bi:bi_dashboard_bookmark_delete", kwargs={"pk": pk})
    apply_url = reverse("bi:bi_dashboard_bookmark_apply", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404
    assert client_a.get(apply_url).status_code == 404


@pytest.mark.django_db
def test_dashboards_filter_idor_protection(client_a, bi_filter_b):
    """Assert Tenant A cannot access Tenant B filter endpoints (all return 404)."""
    pk = bi_filter_b.pk
    detail_url = reverse("bi:bi_dashboard_filter_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:bi_dashboard_filter_edit", kwargs={"pk": pk})
    del_url = reverse("bi:bi_dashboard_filter_delete", kwargs={"pk": pk})

    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.post(del_url).status_code == 404


# ---------------------------------------------------------------------------
# 2. Tenant List Isolation (No Data Leakage in Querysets)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_tenant_list_isolation(
    client_a,
    bi_dashboard_a,
    bi_dashboard_b,
    bi_widget_a,
    bi_widget_b,
    bi_bookmark_a,
    bi_bookmark_b,
    bi_filter_a,
    bi_filter_b,
):
    """Assert Tenant A list views contain only Tenant A objects and none from Tenant B."""
    # Dashboards list
    resp_dash = client_a.get(reverse("bi:bi_dashboard_list"))
    assert resp_dash.status_code == 200
    content_dash = resp_dash.content.decode("utf-8")
    assert bi_dashboard_a.title in content_dash
    assert bi_dashboard_b.title not in content_dash

    # Widgets list
    resp_wid = client_a.get(reverse("bi:bi_dashboard_widget_list"))
    assert resp_wid.status_code == 200
    content_wid = resp_wid.content.decode("utf-8")
    assert bi_widget_a.title in content_wid
    assert bi_widget_b.title not in content_wid

    # Bookmarks list
    resp_bm = client_a.get(reverse("bi:bi_dashboard_bookmark_list"))
    assert resp_bm.status_code == 200
    content_bm = resp_bm.content.decode("utf-8")
    assert bi_bookmark_a.name in content_bm
    assert bi_bookmark_b.name not in content_bm

    # Filters list
    resp_fil = client_a.get(reverse("bi:bi_dashboard_filter_list"))
    assert resp_fil.status_code == 200
    content_fil = resp_fil.content.decode("utf-8")
    assert bi_filter_a.filter_label in content_fil
    assert bi_filter_b.filter_label not in content_fil


# ---------------------------------------------------------------------------
# 3. Privacy, Authorization & Draft Gates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_draft_dashboard_access_restriction(client, tenant_a, bi_dashboard_draft_a):
    """Assert non-admin regular user cannot view unpublished draft dashboard (I6)."""
    regular_user = User.objects.create_user(
        email="staff@acme.com",
        username="staff_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )
    client.force_login(regular_user)

    url_canvas = reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bi_dashboard_draft_a.pk})
    resp = client.get(url_canvas)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_dashboards_canvas_builder_authorization_restriction(client, tenant_a, bi_dashboard_a):
    """Assert non-admin regular user cannot access visual builder or mutate positions (I4)."""
    regular_user = User.objects.create_user(
        email="analyst@acme.com",
        username="analyst_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )
    client.force_login(regular_user)

    url_builder = reverse("bi:bi_dashboard_canvas_builder", kwargs={"pk": bi_dashboard_a.pk})
    assert client.get(url_builder).status_code == 403

    resp_post = client.post(
        url_builder,
        data=json.dumps({"positions": []}),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert resp_post.status_code == 403


@pytest.mark.django_db
def test_dashboards_private_bookmark_cross_user_isolation(
    client, tenant_a, bi_dashboard_a, admin_user
):
    """Assert private bookmark of User 1 is not accessible/applicable by User 2 (I5)."""
    from apps.bi.models import BiDashboardBookmark

    user_2 = User.objects.create_user(
        email="user2@acme.com",
        username="user2_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )
    private_bm = BiDashboardBookmark.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        name="Private Financial Deepdive",
        is_shared=False,  # Private to admin_user
    )

    client.force_login(user_2)
    # Applying private bookmark belonging to admin_user must return 403 for user_2
    url_apply = reverse("bi:bi_dashboard_bookmark_apply", kwargs={"pk": private_bm.pk})
    resp = client.get(url_apply)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. Unauthenticated Access Protection
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_unauthenticated_redirect(anon_client, bi_dashboard_a):
    """Assert unauthenticated requests redirect to login."""
    urls = [
        reverse("bi:bi_dashboard_list"),
        reverse("bi:bi_dashboard_create"),
        reverse("bi:bi_dashboard_detail", kwargs={"pk": bi_dashboard_a.pk}),
        reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bi_dashboard_a.pk}),
        reverse("bi:bi_dashboard_widget_list"),
        reverse("bi:bi_dashboard_bookmark_list"),
        reverse("bi:bi_dashboard_filter_list"),
    ]
    for url in urls:
        resp = anon_client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url
