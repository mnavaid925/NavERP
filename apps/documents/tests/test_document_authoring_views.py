"""View tests for Sub-module 13.1: Document Creation & Authoring."""
import json
import pytest
from django.urls import reverse

from apps.core.models import Document as CoreDocument
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection


@pytest.mark.django_db
def test_document_authoring_template_crud_views(client_a, tenant_a, document_template):
    """Test template list, detail, create, edit, instantiate, and delete."""
    # List
    res = client_a.get(reverse("documents:template_list"))
    assert res.status_code == 200
    assert document_template.name in res.content.decode()

    # Detail
    res = client_a.get(reverse("documents:template_detail", args=[document_template.pk]))
    assert res.status_code == 200
    assert document_template.number in res.content.decode()

    # Create
    create_url = reverse("documents:template_create")
    post_data = {
        "name": "Audit Checklist Template",
        "template_type": "policy",
        "category": "quality",
        "content": "<p>Item 1: Verification</p>",
        "version": "1.0",
        "is_active": True,
    }
    res = client_a.post(create_url, post_data)
    assert res.status_code == 302
    created = DocumentTemplate.objects.get(name="Audit Checklist Template", tenant=tenant_a)

    # Edit
    edit_url = reverse("documents:template_edit", args=[created.pk])
    res = client_a.post(edit_url, {**post_data, "name": "Audit Checklist Template Rev A"})
    assert res.status_code == 302
    created.refresh_from_db()
    assert created.name == "Audit Checklist Template Rev A"

    # Instantiate
    inst_url = reverse("documents:template_instantiate", args=[created.pk])
    res = client_a.post(inst_url)
    assert res.status_code == 302
    instantiated_draft = DocumentDraft.objects.filter(template=created, tenant=tenant_a).first()
    assert instantiated_draft is not None
    assert instantiated_draft.word_count > 0

    # Delete
    del_url = reverse("documents:template_delete", args=[created.pk])
    res = client_a.post(del_url)
    assert res.status_code == 302
    assert not DocumentTemplate.objects.filter(pk=created.pk).exists()


@pytest.mark.django_db
def test_document_authoring_template_section_views(client_a, tenant_a, document_template, template_section):
    """Test section list, detail, create, edit, delete."""
    # List
    res = client_a.get(reverse("documents:template_section_list"))
    assert res.status_code == 200
    assert template_section.title in res.content.decode()

    # Detail
    res = client_a.get(reverse("documents:template_section_detail", args=[template_section.pk]))
    assert res.status_code == 200
    assert template_section.number in res.content.decode()

    # Create
    post_data = {
        "template": document_template.pk,
        "title": "Confidentiality Warning",
        "section_type": "header",
        "content": "STRICTLY CONFIDENTIAL",
        "order": 1,
    }
    res = client_a.post(reverse("documents:template_section_create"), post_data)
    assert res.status_code == 302
    new_sec = TemplateSection.objects.get(title="Confidentiality Warning", tenant=tenant_a)

    # Edit
    res = client_a.post(reverse("documents:template_section_edit", args=[new_sec.pk]), {**post_data, "title": "Confidentiality Notice"})
    assert res.status_code == 302
    new_sec.refresh_from_db()
    assert new_sec.title == "Confidentiality Notice"

    # Delete
    res = client_a.post(reverse("documents:template_section_delete", args=[new_sec.pk]))
    assert res.status_code == 302
    assert not TemplateSection.objects.filter(pk=new_sec.pk).exists()


@pytest.mark.django_db
def test_document_authoring_draft_canvas_and_autosave(client_a, tenant_a, document_draft):
    """Test draft authoring canvas rendering and asynchronous autosave endpoint."""
    # Canvas
    res = client_a.get(reverse("documents:draft_canvas", args=[document_draft.pk]))
    assert res.status_code == 200
    assert "draft-editor" in res.content.decode()

    # Autosave
    autosave_url = reverse("documents:draft_autosave", args=[document_draft.pk])
    new_content = "<h2>Scope Update</h2><p>Calibrating sensor transducers in laboratory room 401.</p>"
    res = client_a.post(autosave_url, {"content": new_content})
    assert res.status_code == 200
    payload = json.loads(res.content.decode())
    assert payload["status"] == "saved"
    assert payload["word_count"] > 0

    document_draft.refresh_from_db()
    assert document_draft.content == new_content
    assert document_draft.word_count == payload["word_count"]


@pytest.mark.django_db
def test_document_authoring_draft_compare_view(client_a, tenant_a, document_draft):
    """Test draft compare view computing diff against parent template."""
    res = client_a.get(reverse("documents:draft_compare", args=[document_draft.pk]))
    assert res.status_code == 200
    content = res.content.decode()
    assert "Redline Visual Comparison" in content
    assert "Template Baseline Removed" in content


@pytest.mark.django_db
def test_document_authoring_draft_promote_to_core_document(client_a, tenant_a, document_draft):
    """Test promoting an approved draft into an official core.Document record."""
    promote_url = reverse("documents:draft_promote", args=[document_draft.pk])
    res = client_a.post(promote_url)
    assert res.status_code == 302

    document_draft.refresh_from_db()
    assert document_draft.status == "promoted"
    assert document_draft.promoted_document is not None

    promoted_doc = document_draft.promoted_document
    assert promoted_doc.name == document_draft.title
    assert promoted_doc.classification == "internal"
    assert promoted_doc.file.name.endswith(".html")


@pytest.mark.django_db
def test_document_authoring_collaboration_workflow(client_a, tenant_a, document_draft, draft_collaboration):
    """Test collaboration comment listing, resolution accept, and rejection."""
    # List
    res = client_a.get(reverse("documents:collaboration_list"))
    assert res.status_code == 200
    assert draft_collaboration.comment_text in res.content.decode()

    # Detail
    res = client_a.get(reverse("documents:collaboration_detail", args=[draft_collaboration.pk]))
    assert res.status_code == 200
    assert draft_collaboration.number in res.content.decode()

    # Resolve Accept
    resolve_url = reverse("documents:collaboration_resolve", args=[draft_collaboration.pk])
    res = client_a.post(resolve_url, {"action": "accept"})
    assert res.status_code == 302

    draft_collaboration.refresh_from_db()
    assert draft_collaboration.status == "accepted"

    document_draft.refresh_from_db()
    assert "temperature-controlled testing suite" in document_draft.content
