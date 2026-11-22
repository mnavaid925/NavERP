"""Form unit tests for Sub-module 13.1: Document Creation & Authoring."""
import pytest

from apps.core.models import OrgUnit, Party
from apps.documents.forms.DocumentAuthoring.DocumentDrafts import DocumentDraftForm
from apps.documents.forms.DocumentAuthoring.DocumentTemplates import DocumentTemplateForm
from apps.documents.forms.DocumentAuthoring.DraftCollaborations import DraftCollaborationForm
from apps.documents.forms.DocumentAuthoring.TemplateSections import TemplateSectionForm
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate


@pytest.mark.django_db
def test_document_authoring_template_form_valid(tenant_a, admin_user):
    """Test valid submission of DocumentTemplateForm with tenant scoping."""
    dept = OrgUnit.objects.create(tenant=tenant_a, name="Quality Dept", code="QD")
    data = {
        "name": "Manufacturing SOP Template",
        "template_type": "sop",
        "category": "operations",
        "description": "Standard assembly procedures.",
        "content": "<p>Assembly steps.</p>",
        "target_org_unit": dept.pk,
        "owner": admin_user.pk,
        "is_active": True,
        "is_locked": False,
    }
    form = DocumentTemplateForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    saved = form.save(commit=False)
    saved.tenant = tenant_a
    saved.save()
    assert saved.name == "Manufacturing SOP Template"
    assert saved.owner == admin_user


@pytest.mark.django_db
def test_document_authoring_template_form_cross_tenant_owner_rejected(tenant_a, tenant_b, admin_b):
    """DocumentTemplateForm rejects owner belonging to another tenant."""
    data = {
        "name": "Hacked Owner Template",
        "template_type": "sop",
        "category": "general",
        "content": "<p>Content</p>",
        "owner": admin_b.pk,
    }
    form = DocumentTemplateForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


@pytest.mark.django_db
def test_document_authoring_template_section_form_valid(tenant_a, document_template):
    """Test valid submission of TemplateSectionForm."""
    data = {
        "template": document_template.pk,
        "title": "Safety & Compliance Clause",
        "section_type": "boilerplate_clause",
        "content": "Safety helmets mandatory in warehouse.",
        "order": 15,
        "is_locked": False,
        "is_mandatory": True,
    }
    form = TemplateSectionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    section = form.save(commit=False)
    section.tenant = tenant_a
    section.save()
    assert section.title == "Safety & Compliance Clause"
    assert section.template == document_template


@pytest.mark.django_db
def test_document_authoring_template_section_form_cross_tenant_template_rejected(tenant_a, tenant_b, admin_b):
    """TemplateSectionForm rejects template belonging to another tenant."""
    other_tmpl = DocumentTemplate.objects.create(
        tenant=tenant_b,
        name="Foreign Template",
        template_type="sop",
        owner=admin_b,
    )
    data = {
        "template": other_tmpl.pk,
        "title": "Injected Section",
        "section_type": "boilerplate_clause",
        "order": 10,
    }
    form = TemplateSectionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "template" in form.errors


@pytest.mark.django_db
def test_document_authoring_draft_form_valid(tenant_a, admin_user, document_template):
    """Test valid submission of DocumentDraftForm."""
    dept = OrgUnit.objects.create(tenant=tenant_a, name="Ops Dept", code="OD")
    party = Party.objects.create(tenant=tenant_a, name="Acme Supplier Ltd")
    data = {
        "title": "Quarterly Maintenance Guide",
        "document_type": "sop",
        "template": document_template.pk,
        "draft_version": "0.2",
        "content": "<p>Maintenance routine instructions.</p>",
        "content_format": "html",
        "department": dept.pk,
        "related_party": party.pk,
        "is_collaboration_locked": False,
    }
    form = DocumentDraftForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    draft = form.save(commit=False)
    draft.tenant = tenant_a
    draft.author = admin_user
    draft.save()
    assert draft.title == "Quarterly Maintenance Guide"


@pytest.mark.django_db
def test_document_authoring_draft_form_rejects_promoted_mutation(tenant_a, admin_user, document_template):
    """DocumentDraftForm rejects editing an instance when status is promoted or discarded."""
    draft = DocumentDraft.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Promoted Draft",
        document_type="sop",
        status="promoted",
        author=admin_user,
    )
    data = {
        "title": "Attempted Edit on Promoted",
        "document_type": "sop",
        "draft_version": "0.1",
        "content": "Updated content",
        "content_format": "html",
    }
    form = DocumentDraftForm(data=data, instance=draft, tenant=tenant_a)
    assert not form.is_valid()
    assert "Cannot modify draft" in str(form.errors)


@pytest.mark.django_db
def test_document_authoring_collaboration_form_valid(tenant_a, member_user, document_draft):
    """Test valid submission of DraftCollaborationForm."""
    data = {
        "entry_type": "suggestion",
        "comment_text": "Please adjust tolerance limits.",
        "selected_text": "tolerance ±5%",
        "replacement_text": "tolerance ±2%",
    }
    form = DraftCollaborationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    collab = form.save(commit=False)
    collab.tenant = tenant_a
    collab.draft = document_draft
    collab.author = member_user
    collab.save()
    assert collab.entry_type == "suggestion"
    assert collab.replacement_text == "tolerance ±2%"
