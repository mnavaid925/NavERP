from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonymForm
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_search_synonym_list(request):
    qs = documents_scope(DocumentSearchSynonym.objects.all(), request).select_related("created_by")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(term__icontains=q) | Q(synonyms__icontains=q) | Q(number__icontains=q))

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    status = request.GET.get("status", "").strip()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    language = request.GET.get("language", "").strip()
    if language:
        qs = qs.filter(language=language)

    total_count = qs.count()
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    status_choices = [("active", "Active"), ("inactive", "Inactive")]

    return render(
        request,
        "documents/search_discovery/document_search_synonym/list.html",
        {
            "page_obj": page_obj,
            "search_synonyms": page_obj.object_list,
            "total_count": total_count,
            "category_choices": DocumentSearchSynonym.CATEGORY_CHOICES,
            "status_choices": status_choices,
        },
    )


@login_required
def document_search_synonym_detail(request, pk):
    search_synonym = documents_object(
        request,
        DocumentSearchSynonym,
        pk,
        select_related=("created_by",),
    )
    expanded_terms_list = search_synonym.get_all_terms()

    return render(
        request,
        "documents/search_discovery/document_search_synonym/detail.html",
        {
            "search_synonym": search_synonym,
            "expanded_terms_list": expanded_terms_list,
        },
    )


@login_required
def document_search_synonym_create(request):
    if request.method == "POST":
        form = DocumentSearchSynonymForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            synonym = form.save(commit=False)
            synonym.tenant = request.tenant
            synonym.created_by = request.user
            synonym.save()
            write_audit_log(request.user, synonym, "create", tenant=request.tenant)
            messages.success(request, f"Search synonym '{synonym.term}' created successfully.")
            return redirect("documents:document_search_synonym_detail", pk=synonym.pk)
    else:
        initial = {}
        term = request.GET.get("term", "").strip()
        if term:
            initial["term"] = term
        form = DocumentSearchSynonymForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "documents/search_discovery/document_search_synonym/form.html",
        {
            "form": form,
            "search_synonym": None,
            "is_edit": False,
        },
    )


@login_required
def document_search_synonym_edit(request, pk):
    search_synonym = documents_object(request, DocumentSearchSynonym, pk)

    if search_synonym.created_by != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to edit this search synonym.")

    if request.method == "POST":
        form = DocumentSearchSynonymForm(request.POST, instance=search_synonym, tenant=request.tenant)
        if form.is_valid():
            search_synonym = form.save()
            write_audit_log(request.user, search_synonym, "update", tenant=request.tenant)
            messages.success(request, f"Search synonym '{search_synonym.term}' updated successfully.")
            return redirect("documents:document_search_synonym_detail", pk=search_synonym.pk)
    else:
        form = DocumentSearchSynonymForm(instance=search_synonym, tenant=request.tenant)

    return render(
        request,
        "documents/search_discovery/document_search_synonym/form.html",
        {
            "form": form,
            "search_synonym": search_synonym,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def document_search_synonym_delete(request, pk):
    search_synonym = documents_object(request, DocumentSearchSynonym, pk)

    if search_synonym.created_by != request.user and not getattr(request.user, "is_tenant_admin", False):
        return HttpResponseForbidden("You do not have permission to delete this search synonym.")

    term = search_synonym.term
    write_audit_log(request.user, search_synonym, "delete", tenant=request.tenant)
    search_synonym.delete()
    messages.success(request, f"Search synonym rule '{term}' deleted.")
    return redirect("documents:document_search_synonym_list")
