"""Security and multi-tenancy IDOR tests for Sub-module 13.1: Document Creation & Authoring."""
import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection


@pytest.mark.django_db
def test_document_authoring_unauthenticated_access_redirects_login(document_template, document_draft):
    """Anonymous requests to authoring endpoints are redirected to login."""
    anon_client = Client()

    res = anon_client.get(reverse("documents:template_list"))
    assert res.status_code == 302
    assert "/login/" in res.url

    res = anon_client.get(reverse("documents:draft_canvas", args=[document_draft.pk]))
    assert res.status_code == 302
    assert "/login/" in res.url


@pytest.mark.django_db
def test_document_authoring_cross_tenant_idor_protection(client_b, tenant_a, document_template, template_section, document_draft, draft_collaboration):
    """Tenant B client receives HTTP 404 when accessing Tenant A documents objects."""
    # Template
    res = client_b.get(reverse("documents:template_detail", args=[document_template.pk]))
    assert res.status_code == 404

    res = client_b.post(reverse("documents:template_edit", args=[document_template.pk]), {"name": "Hacked"})
    assert res.status_code == 404

    res = client_b.post(reverse("documents:template_instantiate", args=[document_template.pk]))
    assert res.status_code == 404

    res = client_b.post(reverse("documents:template_delete", args=[document_template.pk]))
    assert res.status_code == 404

    # Template Section
    res = client_b.get(reverse("documents:template_section_detail", args=[template_section.pk]))
    assert res.status_code == 404

    res = client_b.post(reverse("documents:template_section_edit", args=[template_section.pk]), {"title": "Hacked"})
    assert res.status_code == 404

    res = client_b.post(reverse("documents:template_section_delete", args=[template_section.pk]))
    assert res.status_code == 404

    # Draft
    res = client_b.get(reverse("documents:draft_detail", args=[document_draft.pk]))
    assert res.status_code == 404

    res = client_b.get(reverse("documents:draft_canvas", args=[document_draft.pk]))
    assert res.status_code == 404

    res = client_b.post(reverse("documents:draft_autosave", args=[document_draft.pk]), {"content": "Hacked content"})
    assert res.status_code == 404

    res = client_b.post(reverse("documents:draft_promote", args=[document_draft.pk]))
    assert res.status_code == 404

    # Collaboration
    res = client_b.get(reverse("documents:collaboration_detail", args=[draft_collaboration.pk]))
    assert res.status_code == 404

    res = client_b.post(reverse("documents:collaboration_resolve", args=[draft_collaboration.pk]), {"action": "accept"})
    assert res.status_code == 404


@pytest.mark.django_db
def test_document_authoring_http_method_restrictions(client_a, document_template, document_draft, draft_collaboration):
    """GET requests to POST-only endpoints return 405 Method Not Allowed."""
    # Draft autosave requires POST
    res = client_a.get(reverse("documents:draft_autosave", args=[document_draft.pk]))
    assert res.status_code == 405

    # Draft promote requires POST
    res = client_a.get(reverse("documents:draft_promote", args=[document_draft.pk]))
    assert res.status_code == 405

    # Template instantiate requires POST
    res = client_a.get(reverse("documents:template_instantiate", args=[document_template.pk]))
    assert res.status_code == 405

    # Collaboration resolve requires POST
    res = client_a.get(reverse("documents:collaboration_resolve", args=[draft_collaboration.pk]))
    assert res.status_code == 405


@pytest.mark.django_db
def test_document_authoring_locked_template_non_admin_protection(member_client, document_template, template_section):
    """Non-admin users cannot edit or delete locked templates or sections."""
    document_template.is_locked = True
    document_template.save()

    template_section.is_locked = True
    template_section.save()

    # Attempt template edit as non-admin
    res = member_client.post(
        reverse("documents:template_edit", args=[document_template.pk]),
        {"name": "Attempted Edit", "template_type": "sop", "content": "x"},
    )
    assert res.status_code == 302
    document_template.refresh_from_db()
    assert document_template.name != "Attempted Edit"

    # Attempt template section edit as non-admin
    res = member_client.post(
        reverse("documents:template_section_edit", args=[template_section.pk]),
        {"title": "Attempted Title Edit", "section_type": "boilerplate_clause", "order": 1},
    )
    assert res.status_code == 302
    template_section.refresh_from_db()
    assert template_section.title != "Attempted Title Edit"


@pytest.mark.django_db
def test_document_authoring_collaboration_author_permission(tenant_a, member_user, document_draft, draft_collaboration):
    """Non-author non-admin user cannot edit or delete someone else's collaboration comment."""
    other_member = User.objects.create_user(
        email="other@acme.com",
        username="other_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=False,
    )
    other_client = Client()
    other_client.force_login(other_member)

    # Attempt edit
    res = other_client.post(
        reverse("documents:collaboration_edit", args=[draft_collaboration.pk]),
        {"comment_text": "Overwritten comment", "entry_type": "suggestion"},
    )
    assert res.status_code == 302
    draft_collaboration.refresh_from_db()
    assert draft_collaboration.comment_text != "Overwritten comment"

    # Attempt delete
    res = other_client.post(reverse("documents:collaboration_delete", args=[draft_collaboration.pk]))
    assert res.status_code == 302
    assert DraftCollaboration.objects.filter(pk=draft_collaboration.pk).exists()
