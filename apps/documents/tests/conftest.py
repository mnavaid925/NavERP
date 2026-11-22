"""Shared fixtures for apps.documents test suite (Module 13: Document Management System)."""
import pytest

from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.DraftCollaborations import DraftCollaboration
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection


@pytest.fixture
def document_template(db, tenant_a, admin_user):
    """Fixture providing a baseline active DocumentTemplate in tenant_a."""
    return DocumentTemplate.objects.create(
        tenant=tenant_a,
        name="Standard Operating Procedure Template",
        template_type="sop",
        category="quality",
        content="<h2>Document Scope</h2><p>Standard quality process procedure.</p>",
        owner=admin_user,
        is_active=True,
        is_locked=False,
    )


@pytest.fixture
def template_section(db, tenant_a, document_template):
    """Fixture providing a TemplateSection belonging to document_template."""
    return TemplateSection.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Quality Assurance Clause",
        section_type="boilerplate",
        content="All actions must strictly comply with current Good Manufacturing Practices (cGMP).",
        order=10,
        is_locked=False,
        is_mandatory=True,
    )


@pytest.fixture
def document_draft(db, tenant_a, admin_user, document_template):
    """Fixture providing an active working DocumentDraft in tenant_a."""
    return DocumentDraft.objects.create(
        tenant=tenant_a,
        template=document_template,
        title="Lab Calibration Procedure",
        document_type="sop",
        draft_version="0.1",
        content="<h2>Scope</h2><p>Equipment calibration in testing suite.</p>",
        word_count=7,
        status="draft",
        author=admin_user,
        is_collaboration_locked=False,
    )


@pytest.fixture
def draft_collaboration(db, tenant_a, member_user, document_draft):
    """Fixture providing an open DraftCollaboration feedback note on document_draft."""
    return DraftCollaboration.objects.create(
        tenant=tenant_a,
        draft=document_draft,
        author=member_user,
        entry_type="suggestion",
        comment_text="Ensure to include environmental temperature tolerances.",
        selected_text="testing suite",
        replacement_text="temperature-controlled testing suite",
        status="open",
    )
