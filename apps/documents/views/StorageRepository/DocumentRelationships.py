import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.StorageRepository.DocumentRelationships import DocumentRelationshipForm
from apps.documents.models.StorageRepository.DocumentRelationships import DocumentRelationship
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope


@login_required
def relationship_list(request):
    qs = documents_scope(
        DocumentRelationship.objects.select_related(
            "source_document",
            "target_document",
            "created_by",
        ),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(source_document__title__icontains=q)
            | Q(source_document__number__icontains=q)
            | Q(target_document__title__icontains=q)
            | Q(target_document__number__icontains=q)
            | Q(description__icontains=q)
        )

    relationship_type = request.GET.get("relationship_type", "").strip()
    if relationship_type:
        qs = qs.filter(relationship_type=relationship_type)

    total_count = qs.count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "relationships": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "relationship_type": relationship_type,
        "type_choices": DocumentRelationship.RELATIONSHIP_TYPE_CHOICES,
        "total_count": total_count,
    }
    return render(request, "documents/storage_repository/document_relationship/list.html", context)


@login_required
def relationship_graph(request):
    relationships = documents_scope(
        DocumentRelationship.objects.select_related("source_document", "target_document"),
        request,
    )

    # Build node and link collections for visual D3 / network graph
    node_set = set()
    links = []

    for rel in relationships:
        s_id = rel.source_document.number
        t_id = rel.target_document.number
        node_set.add((s_id, rel.source_document.title, rel.source_document.classification))
        node_set.add((t_id, rel.target_document.title, rel.target_document.classification))
        links.append({
            "source": s_id,
            "target": t_id,
            "type": rel.get_relationship_type_display(),
            "is_bidirectional": rel.is_bidirectional,
        })

    nodes = [{"id": n[0], "title": n[1], "classification": n[2]} for n in node_set]

    context = {
        "relationships": relationships,
        "nodes_json": json.dumps(nodes),
        "links_json": json.dumps(links),
    }
    return render(request, "documents/storage_repository/document_relationship/graph.html", context)


@login_required
def relationship_create(request):
    initial = {}
    source_pk = request.GET.get("source")
    if source_pk and source_pk.isdigit():
        initial["source_document"] = int(source_pk)

    if request.method == "POST":
        form = DocumentRelationshipForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rel = form.save(commit=False)
            rel.tenant = request.tenant
            rel.created_by = request.user
            rel.save()
            write_audit_log(request.user, rel, "link", tenant=request.tenant)
            messages.success(request, f"Relationship link created between '{rel.source_document.title}' and '{rel.target_document.title}'.")
            return redirect("documents:relationship_detail", pk=rel.pk)
    else:
        form = DocumentRelationshipForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "title": "Create Document Relationship Link",
    }
    return render(request, "documents/storage_repository/document_relationship/form.html", context)


@login_required
def relationship_detail(request, pk):
    relationship = documents_object(
        request,
        DocumentRelationship,
        pk,
        select_related=("source_document", "target_document", "created_by"),
    )

    context = {
        "relationship": relationship,
        "source_doc": relationship.source_document,
        "target_doc": relationship.target_document,
    }
    return render(request, "documents/storage_repository/document_relationship/detail.html", context)


@login_required
def relationship_edit(request, pk):
    relationship = documents_object(request, DocumentRelationship, pk)
    if request.method == "POST":
        form = DocumentRelationshipForm(request.POST, instance=relationship, tenant=request.tenant)
        if form.is_valid():
            rel = form.save()
            write_audit_log(request.user, rel, "update", tenant=request.tenant)
            messages.success(request, "Relationship link updated successfully.")
            return redirect("documents:relationship_detail", pk=rel.pk)
    else:
        form = DocumentRelationshipForm(instance=relationship, tenant=request.tenant)

    context = {
        "form": form,
        "relationship": relationship,
        "is_edit": True,
        "title": f"Edit Relationship — {relationship.number}",
    }
    return render(request, "documents/storage_repository/document_relationship/form.html", context)


@require_POST
@login_required
def relationship_delete(request, pk):
    relationship = documents_object(request, DocumentRelationship, pk)
    write_audit_log(request.user, relationship, "unlink", tenant=request.tenant)
    relationship.delete()
    messages.success(request, "Document relationship link removed.")
    return redirect("documents:relationship_list")
