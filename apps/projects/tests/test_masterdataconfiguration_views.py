from django.test import Client
from django.urls import reverse

from apps.projects.models import Project, ProjectMilestone, ProjectTask
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import ProjectCustomField
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate
from apps.projects.tests.masterdataconfiguration_helpers import (
    _masterdataconfiguration_custom_field,
    _masterdataconfiguration_custom_field_payload,
    _masterdataconfiguration_custom_value,
    _masterdataconfiguration_instantiate_payload,
    _masterdataconfiguration_locale,
    _masterdataconfiguration_locale_payload,
    _masterdataconfiguration_project,
    _masterdataconfiguration_project_payload,
    _masterdataconfiguration_risk_payload,
    _masterdataconfiguration_team,
    _masterdataconfiguration_team_member,
    _masterdataconfiguration_template,
    _masterdataconfiguration_template_payload,
)


def _masterdataconfiguration_client(user):
    client = Client()
    client.force_login(user)
    return client


def test_masterdataconfiguration_views_all_routes_and_get_contract(db, tenant_a, admin_user):
    template = _masterdataconfiguration_template(tenant_a, admin_user)
    field = _masterdataconfiguration_custom_field(tenant_a)
    team = _masterdataconfiguration_team(tenant_a, admin_user)
    member = _masterdataconfiguration_team_member(tenant_a, team, admin_user)
    locale = _masterdataconfiguration_locale(
        tenant_a,
        _masterdataconfiguration_project(tenant_a, admin_user),
    )
    client = _masterdataconfiguration_client(admin_user)
    get_routes = [
        ("projects:ptm_list", None),
        ("projects:ptm_create", None),
        ("projects:ptm_detail", {"pk": template.pk}),
        ("projects:ptm_edit", {"pk": template.pk}),
        ("projects:ptm_instantiate", {"pk": template.pk}),
        ("projects:pcf_list", None),
        ("projects:pcf_create", None),
        ("projects:pcf_detail", {"pk": field.pk}),
        ("projects:pcf_edit", {"pk": field.pk}),
        ("projects:pte_list", None),
        ("projects:pte_create", None),
        ("projects:pte_detail", {"pk": team.pk}),
        ("projects:pte_edit", {"pk": team.pk}),
        ("projects:pls_list", None),
        ("projects:pls_create", None),
        ("projects:pls_detail", {"pk": locale.pk}),
        ("projects:pls_edit", {"pk": locale.pk}),
        ("projects:configuration_hub", None),
    ]
    post_only = [
        ("projects:ptm_delete", {"pk": template.pk}),
        ("projects:pcf_delete", {"pk": field.pk}),
        ("projects:pcf_toggle_active", {"pk": field.pk}),
        ("projects:pte_delete", {"pk": team.pk}),
        ("projects:pte_add_member", {"pk": team.pk}),
        ("projects:pte_remove_member", {"team_pk": team.pk, "pk": member.pk}),
        ("projects:pls_delete", {"pk": locale.pk}),
        ("projects:pls_set_default", {"pk": locale.pk}),
    ]

    for name, kwargs in get_routes:
        response = client.get(reverse(name, kwargs=kwargs))
        assert response.status_code == 200, (name, response.status_code)
    for name, kwargs in post_only:
        response = client.get(reverse(name, kwargs=kwargs))
        assert response.status_code == 405, (name, response.status_code)


def test_masterdataconfiguration_views_template_create_filter_and_content(db, tenant_a, admin_user):
    client = _masterdataconfiguration_client(admin_user)
    response = client.post(
        reverse("projects:ptm_create"),
        _masterdataconfiguration_template_payload(),
    )

    assert response.status_code == 302
    template = ProjectTemplate.objects.get(name="Created template")
    listing = client.get(
        reverse("projects:ptm_list"),
        {"methodology": "agile", "category": "software", "complexity": "small", "q": "Created"},
    )
    assert listing.status_code == 200
    assert template.number in listing.content.decode()
    assert "Created template" in listing.content.decode()


def test_masterdataconfiguration_views_custom_field_create_and_toggle(db, tenant_a, admin_user):
    client = _masterdataconfiguration_client(admin_user)
    response = client.post(
        reverse("projects:pcf_create"),
        _masterdataconfiguration_custom_field_payload(field_key="view_code", name="View code", label="View code"),
    )

    assert response.status_code == 302
    field = ProjectCustomField.objects.get(field_key="view_code")
    assert field.is_active is True
    toggled = client.post(reverse("projects:pcf_toggle_active", kwargs={"pk": field.pk}))
    assert toggled.status_code == 302
    field.refresh_from_db()
    assert field.is_active is False


def test_masterdataconfiguration_views_team_membership_departure_and_pagination(db, tenant_a, admin_user, member_user):
    team = _masterdataconfiguration_team(tenant_a, admin_user, name="Paged team", code="PAGED")
    member = _masterdataconfiguration_team_member(tenant_a, team, member_user)
    client = _masterdataconfiguration_client(admin_user)
    page = client.get(reverse("projects:pte_list"), {"team_type": "cross_functional", "page": 1})

    assert page.status_code == 200
    assert "Paged team" in page.content.decode()
    departure = client.post(
        reverse("projects:pte_remove_member", kwargs={"team_pk": team.pk, "pk": member.pk})
    )
    assert departure.status_code == 302
    member.refresh_from_db()
    assert member.left_date is not None
    detail = client.get(reverse("projects:pte_detail", kwargs={"pk": team.pk}))
    assert "Historical Membership" in detail.content.decode()


def test_masterdataconfiguration_views_locale_create_and_filters(db, tenant_a, admin_user):
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    client = _masterdataconfiguration_client(admin_user)
    payload = _masterdataconfiguration_locale_payload(
        name="View locale",
        code="VIEW-LOCALE",
        project=str(project.pk),
    )
    response = client.post(reverse("projects:pls_create"), payload)

    assert response.status_code == 302
    listing = client.get(reverse("projects:pls_list"), {"q": "View locale", "is_active": "active"})
    assert listing.status_code == 200
    assert "View locale" in listing.content.decode()


def test_masterdataconfiguration_views_instantiation_creates_draft_wbs(db, tenant_a, admin_user):
    template = _masterdataconfiguration_template(tenant_a, admin_user)
    client = _masterdataconfiguration_client(admin_user)
    response = client.post(
        reverse("projects:ptm_instantiate", kwargs={"pk": template.pk}),
        _masterdataconfiguration_instantiate_payload(),
    )

    assert response.status_code == 302
    project = Project.objects.get(name="Instantiated project")
    assert project.status == "draft"
    assert ProjectTask.objects.filter(project=project).count() == 4
    assert ProjectMilestone.objects.filter(project=project).count() == 1
    detail = client.get(response.url)
    assert detail.status_code == 200
    assert "draft" in detail.content.decode().lower()


def test_masterdataconfiguration_views_custom_value_panel_on_project(db, tenant_a, admin_user):
    definition = _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="panel_code",
        name="Panel code",
        label="Panel code",
    )
    client = _masterdataconfiguration_client(admin_user)
    response = client.post(
        reverse("projects:prj_create"),
        _masterdataconfiguration_project_payload({"panel_code": "PANEL-42"}),
    )

    assert response.status_code == 302
    project = Project.objects.get(name="Custom project")
    assert _masterdataconfiguration_custom_value(definition, project, "panel_code").value == "PANEL-42"
    detail = client.get(reverse("projects:prj_detail", kwargs={"pk": project.pk}))
    assert detail.status_code == 200
    content = detail.content.decode()
    assert "Panel code" in content
    assert "PANEL-42" in content


def test_masterdataconfiguration_views_hub_content(db, tenant_a, admin_user):
    template = _masterdataconfiguration_template(tenant_a, admin_user)
    team = _masterdataconfiguration_team(tenant_a, admin_user)
    _masterdataconfiguration_custom_field(tenant_a)
    client = _masterdataconfiguration_client(admin_user)
    response = client.get(reverse("projects:configuration_hub"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Master Data &amp; Configuration Hub" in content
    assert template.name in content
    assert team.name in content


def test_masterdataconfiguration_views_member_controls_hidden_but_instantiation_visible(
    db,
    tenant_a,
    member_user,
):
    template = _masterdataconfiguration_template(tenant_a, member_user)
    client = _masterdataconfiguration_client(member_user)
    listing = client.get(reverse("projects:ptm_list"))
    content = listing.content.decode()

    assert listing.status_code == 200
    assert "New Template" not in content
    assert "Instantiate Project" in content
    assert client.get(reverse("projects:ptm_instantiate", kwargs={"pk": template.pk})).status_code == 200


def test_masterdataconfiguration_views_pagination_page_two(db, tenant_a, admin_user):
    for index in range(16):
        _masterdataconfiguration_template(
            tenant_a,
            admin_user,
            name=f"Paged template {index:02d}",
            code=f"PAGED-{index:02d}",
        )
    client = _masterdataconfiguration_client(admin_user)
    response = client.get(reverse("projects:ptm_list"), {"page": 2})

    assert response.status_code == 200
    assert "Paged template" in response.content.decode()
