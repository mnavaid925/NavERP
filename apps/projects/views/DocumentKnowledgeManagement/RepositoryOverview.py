"""Projects 7.10 — ``doc_repository``: the repository OVERVIEW (a computed page, no table).

The landing page for the sub-module: six stat tiles (documents, folders, in review, retention due,
held, archived) computed in ONE view pass, plus the two shelf links that keep the shelves honest —
7.9's share register (which points at ``core.Document``) and this repository's own register.

Every figure here is a single aggregated COUNT over a tenant-scoped queryset, computed on read.
Nothing is stored, because a stored tile goes stale the instant a document is approved (the 7.4 EVM
/ 7.5 simulation / 7.6 / 7.8 / 7.9 rulings).
"""
from django.db.models import Count

from apps.projects.models import DocumentTemplate, KnowledgeEntry, ProjectDocument, ProjectFolder
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, redirect, render
from apps.projects.views._helpers import projects


@login_required
def doc_repository(request):
    tenant = request.tenant
    if tenant is None:
        return redirect("dashboard:home")
    # `extracted_text` is DEFERRED on the base queryset: this page reads counts and a ten-row
    # recent shelf, and no tile renders the search copy — which can hold `EXTRACT_MAX_CHARS`
    # characters per row. The retention tile below narrows further with its own `.only(...)`.
    documents = ProjectDocument.objects.filter(tenant=tenant).defer("extracted_text")
    figures = {
        "document_count": documents.count(),
        "folder_count": ProjectFolder.objects.filter(tenant=tenant).count(),
        "in_review": documents.filter(status="in_review").count(),
        "expected": documents.filter(status="expected").count(),
        "retention_due": sum(1 for row in documents.only("retention_months", "created_at")
                             if row.is_retention_due),
        "held": documents.filter(is_legal_hold=True).count(),
        "archived": documents.filter(is_archived=True).count(),
        "approved": documents.filter(status="approved").count(),
        "template_count": DocumentTemplate.objects.filter(tenant=tenant).count(),
        "knowledge_count": KnowledgeEntry.objects.filter(tenant=tenant).count(),
    }
    recent = (documents.select_related("project", "folder", "owner")
              .order_by("-created_at", "-id")[:10])
    # ONE grouped query, not one COUNT per doc-type choice: the loop this replaces issued eleven
    # round-trips for a single figure. `DOC_TYPE_CHOICES` still supplies the label AND the order —
    # the dict keeps only the types that have rows, which is the template's contract.
    labels = dict(ProjectDocument.DOC_TYPE_CHOICES)
    tally = dict(documents.values_list("document_type")
                 .annotate(n=Count("pk")).values_list("document_type", "n"))
    by_type = {labels[value]: tally[value]
               for value, _label in ProjectDocument.DOC_TYPE_CHOICES
               if tally.get(value)}
    return render(request, "projects/documentknowledge/overview.html", {
        "figures": figures,
        "recent_documents": recent,
        "by_type": by_type,
        "projects": projects(tenant),
    })
