from django.test import Client
from django.urls import reverse

from apps.core.models import CustomFieldValue
from apps.projects.models import Project
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import ProjectCustomField
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSetting
from apps.projects.models.MasterDataConfiguration.ProjectTeams import ProjectTeam
from apps.projects.models.MasterDataConfiguration.ProjectTemplates import ProjectTemplate
from apps.projects.tests.masterdataconfiguration_helpers import (
    _masterdataconfiguration_custom_field,
    _masterdataconfiguration_custom_field_payload,
    _masterdataconfiguration_instantiate_payload,
    _masterdataconfiguration_locale,
    _masterdataconfiguration_locale_payload,
    _masterdataconfiguration_project,
    _masterdataconfiguration_team,
    _masterdataconfiguration_team_member,
    _masterdataconfiguration_template,
    _masterdataconfiguration_template_payload,
)


def _masterdataconfiguration_client(user, enforce_csrf=False):
    client = Client(enforce_csrf_checks=enforce_csrf)
    client.force_login(user)
    return client


def test_masterdataconfiguration_security_member_cannot_mutate_configuration(
    db,
    tenant_a,
    member_user,
):
    template = _masterdataconfiguration_template(tenant_a, member_user)
    field = _masterdataconfiguration_custom_field(tenant_a)
    team = _masterdataconfiguration_team(tenant_a, member_user)
    member = _masterdataconfiguration_team_member(tenant_a, team, member_user)
    locale = _masterdataconfiguration_locale(
        tenant_a,
        _masterdataconfiguration_project(tenant_a, member_user),
    )
    client = _masterdataconfiguration_client(member_user)
    requests = [
        ("projects:ptm_create", None, _masterdataconfiguration_template_payload()),
        ("projects:ptm_edit", {"pk": template.pk}, _masterdataconfiguration_template_payload(name="Changed")),
        ("projects:pcf_create", None, _masterdataconfiguration_custom_field_payload(field_key="blocked")),
        ("projects:pcf_edit", {"pk": field.pk}, _masterdataconfiguration_custom_field_payload(label="Changed")),
        ("projects:pcf_toggle_active", {"pk": field.pk}, {}),
        ("projects:pte_create", None, {"name": "Blocked", "team_type": "matrix"}),
        ("projects:pte_edit", {"pk": team.pk}, {"name": "Changed", "team_type": "matrix"}),
        ("projects:pte_add_member", {"pk": team.pk}, {"user": member_user.pk, "allocation_percentage": 10}),
        ("projects:pte_remove_member", {"team_pk": team.pk, "pk": member.pk}, {}),
        ("projects:pls_create", None, _masterdataconfiguration_locale_payload(name="Blocked")),
        ("projects:pls_edit", {"pk": locale.pk}, _masterdataconfiguration_locale_payload(name="Changed")),
        ("projects:pls_set_default", {"pk": locale.pk}, {}),
    ]

    for name, kwargs, payload in requests:
        response = client.post(reverse(name, kwargs=kwargs), payload)
        assert response.status_code == 403, (name, response.status_code)


def test_masterdataconfiguration_security_member_can_instantiate_active_template(
    db,
    tenant_a,
    member_user,
):
    template = _masterdataconfiguration_template(tenant_a, member_user)
    client = _masterdataconfiguration_client(member_user)
    response = client.post(
        reverse("projects:ptm_instantiate", kwargs={"pk": template.pk}),
        _masterdataconfiguration_instantiate_payload(),
    )

    assert response.status_code == 302
    project = Project.objects.get(name="Instantiated project")
    assert project.status == "draft"


def test_masterdataconfiguration_security_post_only_get_is_405_for_member(
    db,
    tenant_a,
    member_user,
):
    template = _masterdataconfiguration_template(tenant_a, member_user)
    field = _masterdataconfiguration_custom_field(tenant_a)
    team = _masterdataconfiguration_team(tenant_a, member_user)
    locale = _masterdataconfiguration_locale(tenant_a)
    client = _masterdataconfiguration_client(member_user)
    routes = [
        ("projects:ptm_delete", {"pk": template.pk}),
        ("projects:pcf_delete", {"pk": field.pk}),
        ("projects:pcf_toggle_active", {"pk": field.pk}),
        ("projects:pte_delete", {"pk": team.pk}),
        ("projects:pls_delete", {"pk": locale.pk}),
        ("projects:pls_set_default", {"pk": locale.pk}),
    ]

    for name, kwargs in routes:
        assert client.get(reverse(name, kwargs=kwargs)).status_code == 405


def test_masterdataconfiguration_security_csrf_is_enforced(
    db,
    tenant_a,
    admin_user,
):
    field = _masterdataconfiguration_custom_field(tenant_a)
    client = _masterdataconfiguration_client(admin_user, enforce_csrf=True)
    response = client.post(reverse("projects:pcf_delete", kwargs={"pk": field.pk}))

    assert response.status_code == 403
    assert ProjectCustomField.objects.filter(pk=field.pk).exists()


def test_masterdataconfiguration_security_cross_tenant_object_and_post_idor(
    db,
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    template = _masterdataconfiguration_template(tenant_b, admin_b)
    field = _masterdataconfiguration_custom_field(tenant_b)
    team = _masterdataconfiguration_team(tenant_b, admin_b)
    locale = _masterdataconfiguration_locale(tenant_b)
    client = _masterdataconfiguration_client(admin_user)
    for name, kwargs in [
        ("projects:ptm_detail", {"pk": template.pk}),
        ("projects:ptm_edit", {"pk": template.pk}),
        ("projects:pcf_detail", {"pk": field.pk}),
        ("projects:pte_detail", {"pk": team.pk}),
        ("projects:pls_detail", {"pk": locale.pk}),
    ]:
        assert client.get(reverse(name, kwargs=kwargs)).status_code == 404
    assert client.post(
        reverse("projects:ptm_delete", kwargs={"pk": template.pk})
    ).status_code == 404
    assert ProjectTemplate.objects.filter(pk=template.pk).exists()
    assert ProjectCustomField.objects.filter(pk=field.pk).exists()
    assert ProjectTeam.objects.filter(pk=team.pk).exists()
    assert ProjectLocaleSetting.objects.filter(pk=locale.pk).exists()


def test_masterdataconfiguration_security_tenantless_create_guard(
    db,
    tenant_a,
):
    from apps.accounts.models import User
    user = User.objects.create_superuser(
        username="mdc-drifter",
        email="mdc-drifter@example.com",
        password="TestPass123!",
        tenant=None,
    )
    client = _masterdataconfiguration_client(user)

    for name in (
        "projects:ptm_create",
        "projects:pcf_create",
        "projects:pte_create",
        "projects:pls_create",
    ):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url == reverse("dashboard:home")
    assert ProjectTemplate.objects.count() == 0
    assert ProjectCustomField.objects.count() == 0
    assert ProjectTeam.objects.count() == 0
    assert ProjectLocaleSetting.objects.count() == 0


def test_masterdataconfiguration_security_cross_tenant_fk_is_form_error(
    db,
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    from apps.core.models import OrgUnit
    foreign_org = OrgUnit.objects.create(tenant=tenant_b, name="Foreign unit", kind="department")
    foreign_project = _masterdataconfiguration_project(tenant_b, admin_b)
    client = _masterdataconfiguration_client(admin_user)
    team_response = client.post(
        reverse("projects:pte_create"),
        {
            "name": "Rejected team",
            "team_type": "matrix",
            "org_unit": foreign_org.pk,
        },
    )
    locale_response = client.post(
        reverse("projects:pls_create"),
        _masterdataconfiguration_locale_payload(
            name="Rejected locale",
            project=foreign_project.pk,
        ),
    )

    assert team_response.status_code == 200
    assert locale_response.status_code == 200
    assert not ProjectTeam.objects.filter(name="Rejected team").exists()
    assert not ProjectLocaleSetting.objects.filter(name="Rejected locale").exists()


def test_masterdataconfiguration_security_custom_value_cannot_cross_tenant(
    db,
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    foreign_definition = _masterdataconfiguration_custom_field(
        tenant_b,
        field_key="foreign_secret",
        name="Foreign secret",
        label="Foreign secret",
    )
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    from apps.projects.forms import ProjectForm
    form = ProjectForm(
        {
            "name": "Isolation project",
            "methodology": "hybrid",
            "custom_foreign_secret": "blocked",
        },
        tenant=tenant_a,
    )

    assert form.is_valid(), form.errors
    assert "custom_foreign_secret" not in form.fields
    assert not CustomFieldValue.objects.filter(definition__field_key="foreign_secret").exists()
    assert foreign_definition.tenant_id == tenant_b.pk
    assert project.tenant_id == tenant_a.pk


def test_masterdataconfiguration_security_hostile_json_and_numeric_filters(
    db,
    tenant_a,
    admin_user,
):
    client = _masterdataconfiguration_client(admin_user)
    recursive = "[" * 5000 + "]" * 5000
    response = client.post(
        reverse("projects:ptm_create"),
        _masterdataconfiguration_template_payload(
            workflow_config_raw=recursive,
        ),
    )
    assert response.status_code == 200
    assert not ProjectTemplate.objects.filter(name="Created template").exists()
    assert client.get(reverse("projects:pte_list"), {"org_unit": "²"}).status_code == 200
    assert client.get(reverse("projects:pls_list"), {"language": "²"}).status_code == 200
    assert client.get(reverse("projects:pls_list"), {"currency": "9" * 5000}).status_code == 200


def test_masterdataconfiguration_security_locale_default_rejects_project_and_inactive(
    db,
    tenant_a,
    admin_user,
):
    project = _masterdataconfiguration_project(tenant_a, admin_user)
    project_override = _masterdataconfiguration_locale(tenant_a, project)
    inactive = _masterdataconfiguration_locale(
        tenant_a,
        None,
        name="Inactive",
        code="INACTIVE",
        is_active=False,
    )
    client = _masterdataconfiguration_client(admin_user)
    project_response = client.post(
        reverse("projects:pls_set_default", kwargs={"pk": project_override.pk})
    )
    inactive_response = client.post(
        reverse("projects:pls_set_default", kwargs={"pk": inactive.pk})
    )

    project_override.refresh_from_db()
    inactive.refresh_from_db()
    assert project_response.status_code == 302
    assert inactive_response.status_code == 302
    assert project_override.is_default is False
    assert inactive.is_default is False


def test_masterdataconfiguration_security_confirmation_does_not_interpolate_values(
    db,
    tenant_a,
    admin_user,
):
    _masterdataconfiguration_custom_field(
        tenant_a,
        field_key="xss_probe",
        name="xss');alert(1);//",
        label="xss');alert(1);//",
    )
    client = _masterdataconfiguration_client(admin_user)
    content = client.get(reverse("projects:pcf_list")).content.decode()

    assert "onsubmit=\"return confirm('Delete this custom field definition?" in content
    assert "onsubmit=\"return confirm('Delete custom field xss" not in content
