"""Projects 7.10 — DocumentTemplate views: the standards library (bullet 2).

A small, quiet CRUD over a tenant-wide register — no project lens, because a standard belongs to
the PMO and not to one project (the model docstring carries the reasoning). ``dtm_publish`` is the
ONE writer of ``is_active``: retiring keeps the row readable but takes it off the "start from this"
list, and restoring goes through the SAME verb + audit (the 7.9 ``dsh_revoke`` idiom).

The register offers no "generate a document from this template" affordance and no page claims one:
merging project data into a standard is an authoring engine (Module 13.1), and the closest honest
verb this pass ships is the download link on the detail page.
"""
from apps.core.crud import as_db_int
from apps.projects.forms import DocumentTemplateForm
from apps.projects.models import DocumentTemplate
from apps.projects.models.DocumentKnowledgeManagement.Documents import purge_stored_files
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, tenant_admin_required,
                                         write_audit_log)


@login_required
def dtm_list(request):
    qs = DocumentTemplate.objects.filter(tenant=request.tenant).select_related("owner")
    return crud_list(
        request, qs, "projects/documentknowledge/documenttemplate/list.html",
        search_fields=["number", "name", "description", "version"],
        filters=[("category", "category", False), ("is_active", "is_active", False),
                 ("document_type", "document_type", False)],
        extra_context={"category_choices": DocumentTemplate.CATEGORY_CHOICES},
    )


@login_required
def dtm_detail(request, pk):
    obj = get_object_or_404(DocumentTemplate, pk=pk, tenant=request.tenant)
    return render(request, "projects/documentknowledge/documenttemplate/detail.html", {"obj": obj})


@login_required
def dtm_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = DocumentTemplateForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Standard {obj.number} created.")
            return redirect("projects:dtm_detail", pk=obj.pk)
    else:
        form = DocumentTemplateForm(tenant=request.tenant)
    return render(request, "projects/documentknowledge/documenttemplate/form.html",
                  {"form": form, "is_edit": False})


@login_required
def dtm_edit(request, pk):
    obj = get_object_or_404(DocumentTemplate, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = DocumentTemplateForm(request.POST, request.FILES, instance=obj,
                                    tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, f"Standard {obj.number} updated.")
            return redirect("projects:dtm_detail", pk=obj.pk)
    else:
        form = DocumentTemplateForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/documentknowledge/documenttemplate/form.html",
                  {"form": form, "is_edit": True, "obj": obj})


@login_required
def dtm_delete(request, pk):
    obj = get_object_or_404(DocumentTemplate, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        number, name = obj.number, obj.name
        file_name = obj.file.name if obj.file else ""
        write_audit_log(request.user, obj, "delete",
                        changes={"verb": "dtm_delete", "name": name})
        obj.delete()
        purge_stored_files(DocumentTemplate, [file_name])
        messages.success(request, f"Standard {number} ({name}) deleted.")
        return redirect("projects:dtm_list")
    return render(request, "projects/documentknowledge/documenttemplate/delete.html", {"obj": obj})


@login_required
@require_POST
@tenant_admin_required
def dtm_publish(request, pk):
    """Toggle publish/retire. THE one writer of ``is_active``.

    Admin-gated: a standard is a PMO artefact, so publishing or retiring one is a house-rule
    decision rather than a member's filing act.
    """
    obj = get_object_or_404(DocumentTemplate, pk=pk, tenant=request.tenant)
    previous = obj.is_active
    obj.is_active = not previous
    obj.save(update_fields=["is_active", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "dtm_publish", "from": previous, "to": obj.is_active})
    if obj.is_active:
        messages.success(request, f"Standard {obj.number} published — it is on the "
                                  f"\"start from this\" list again.")
    else:
        messages.success(request, f"Standard {obj.number} retired — it stays readable but leaves "
                                  f"the active list.")
    return redirect("projects:dtm_detail", pk=obj.pk)