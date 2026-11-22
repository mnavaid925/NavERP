"""Model unit tests for Sub-module 13.1: Document Creation & Authoring."""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.core.models import OrgUnit, Party
from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection


@pytest.mark.django_db
def test_document_authoring_template_model(tenant_a, admin_user):
    """Test DocumentTemplate creation, prefix DTMPL-, and __str__."""
    tmpl = DocumentTemplate.objects.create(
        tenant=tenant_a,
        name="Security Policy Template",
        template_type="policy",
        category="security",
        content="<p>Security rules</p>",
        owner=admin_user,
    )
    assert tmpl.number.startswith("DTMPL-")
    assert str(tmpl) == f"{tmpl.number} - Security Policy Template"
    assert tmpl.is_active is True
    assert tmpl.is_locked is False


@pytest.mark.django_db
def test_document_authoring_template_cross_tenant_owner_rejection(tenant_a, tenant_b, admin_b):
    """DocumentTemplate.clean() rejects owner belonging to a different tenant."""
    tmpl = DocumentTemplate(
        tenant=tenant_a,
        name="Cross-tenant Owner Template",
        template_type="sop",
        owner=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        tmpl.clean()
    assert "owner" in exc.value.error_dict


@pytest.mark.django_db
def test_document_authoring_template_section_model(tenant_a, document_template):
    """Test TemplateSection creation, prefix DSEC-, ordering, and __str__."""
    sec = TemplateSection.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Revision History Section",
        section_type="audit_log",
        content="Document change history table.",
        order=20,
    )
    assert sec.number.startswith("DSEC-")
    assert str(sec) == f"{sec.number} - Revision History Section ({document_template.name})"
    assert sec.is_locked is False
    assert sec.is_mandatory is False


@pytest.mark.django_db
def test_document_authoring_template_section_cross_tenant_template_rejection(tenant_a, tenant_b, admin_b):
    """TemplateSection.clean() rejects parent template belonging to a different tenant."""
    other_tmpl = DocumentTemplate.objects.create(
        tenant=tenant_b,
        name="Globex Template",
        template_type="sop",
        owner=admin_b,
    )
    sec = TemplateSection(
        tenant=tenant_a,
        template=other_tmpl,
        title="Cross Section",
    )
    with pytest.raises(ValidationError) as exc:
        sec.clean()
    assert "template" in exc.value.error_dict


@pytest.mark.django_db
def test_document_authoring_draft_model(tenant_a, admin_user, document_template):
    """Test DocumentDraft creation, prefix DDFT-, default status, and __str__."""
    draft = DocumentDraft.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Sterilization Manual",
        document_type="work_instruction",
        content="<p>Autoclave instructions.</p>",
        author=admin_user,
    )
    assert draft.number.startswith("DDFT-")
    assert str(draft) == f"{draft.number} - Sterilization Manual (v0.1)"
    assert draft.status == "draft"
    assert draft.sync_status == "synced"
    assert draft.content_format == "html"
    assert draft.is_collaboration_locked is False


@pytest.mark.django_db
def test_document_authoring_draft_cross_tenant_rejection(tenant_a, tenant_b, admin_b):
    """DocumentDraft.clean() rejects foreign tenant template, department, or party."""
    other_tmpl = DocumentTemplate.objects.create(
        tenant=tenant_b,
        name="Foreign Template",
        template_type="sop",
        owner=admin_b,
    )
    other_org = OrgUnit.objects.create(tenant=tenant_b, name="Foreign Dept", code="FD")
    other_party = Party.objects.create(tenant=tenant_b, name="Foreign Supplier")

    draft1 = DocumentDraft(tenant=tenant_a, title="Draft 1", template=other_tmpl)
    with pytest.raises(ValidationError) as exc1:
        draft1.clean()
    assert "template" in exc1.value.error_dict

    draft2 = DocumentDraft(tenant=tenant_a, title="Draft 2", department=other_org)
    with pytest.raises(ValidationError) as exc2:
        draft2.clean()
    assert "department" in exc2.value.error_dict

    draft3 = DocumentDraft(tenant=tenant_a, title="Draft 3", related_party=other_party)
    with pytest.raises(ValidationError) as exc3:
        draft3.clean()
    assert "related_party" in exc3.value.error_dict


@pytest.mark.django_db
def test_document_authoring_collaboration_model(tenant_a, member_user, document_draft):
    """Test DraftCollaboration creation, prefix DCMT-, and __str__."""
    collab = DraftCollaboration.objects.create(
        tenant=tenant_a,
        draft=document_draft,
        author=member_user,
        entry_type="critique",
        comment_text="Consider rewording safety risk paragraph.",
    )
    assert collab.number.startswith("DCMT-")
    assert str(collab) == f"{collab.number} - critique by {member_user.username} on {document_draft.number}"
    assert collab.status == "open"


@pytest.mark.django_db
def test_document_authoring_collaboration_cross_tenant_rejection(tenant_a, tenant_b, admin_b, document_template):
    """DraftCollaboration.clean() rejects draft belonging to a different tenant."""
    other_draft = DocumentDraft.objects.create(
        tenant=tenant_b,
        title="Other Draft",
        document_type="sop",
        author=admin_b,
    )
    collab = DraftCollaboration(
        tenant=tenant_a,
        draft=other_draft,
        comment_text="Test comment",
    )
    with pytest.raises(ValidationError) as exc:
        collab.clean()
    assert "draft" in exc.value.error_dict
