"""Projects 7.10 — ProjectFolder views: the folder tree, its CRUD and the archive Toggle.

The register IS the tree: ``pfd_list`` fetches every folder of the tenant (folders are few — they
are organisation, not data), decorates them IN MEMORY with the depth, the full path and the document
count, orders them depth-first by ``sequence``/``name`` and paginates the decorated rows. A stored
path or count would go stale the instant a parent moved or a document was approved (the 7.2 WBS
ruling), so nothing here writes one.

``?project=`` is the tree's lens (an int-FK lookup, ``as_db_int``-guarded, skipped on ``0``); a
plain search narrows by ``name`` and ``description`` across the whole tree — and it runs over the
DECORATED tree, so a nested match keeps its ancestors as context rows and is findable at all.
"""
from apps.core.crud import as_db_int
from apps.projects.forms import ProjectFolderForm
from apps.projects.models import ProjectDocument, ProjectFolder
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, timezone,
                                         write_audit_log)
from apps.projects.views._helpers import projects


def _decorate(tenant, rows):
    """Depth-first decorated rows: ``obj``/``depth``/``path``/``doc_count``, all computed in memory.

    ``rows`` is the tenant's (already lens-filtered) folder queryset. Two queries total: one for the
    folders (done by the caller) and one grouped count for the documents — never one COUNT per row,
    and never a stored column.
    """
    by_parent, by_pk = {}, {}
    for folder in rows:
        by_parent.setdefault(folder.parent_id, []).append(folder)
        by_pk[folder.pk] = folder

    counters = {}
    if rows:
        for folder_id in (ProjectDocument.objects.filter(tenant=tenant,
                                                         folder_id__in=[f.pk for f in rows])
                          .values_list("folder_id", flat=True)):
            counters[folder_id] = counters.get(folder_id, 0) + 1

    decorated = []

    def walk(parent_id, depth, ancestors):
        if depth > 20:
            return
        for folder in sorted(by_parent.get(parent_id, []),
                             key=lambda f: (f.sequence, f.name.lower(), -f.pk)):
            decorated.append({
                "obj": folder,
                "depth": depth,
                "path": " / ".join([a.name for a in ancestors] + [folder.name]),
                "doc_count": counters.get(folder.pk, 0),
            })
            walk(folder.pk, depth + 1, ancestors + [folder])

    walk(None, 0, [])
    return decorated


def _narrow(decorated, needle):
    """The rows to render for a search: the matches, plus their ancestors and descendants.

    A flat filter over the folder rows kept ONLY the matches and ``_decorate`` then walked from
    ``parent_id is None``, so a match whose parent had been filtered out was unreachable —
    ``?q=Yankee`` for ``Zulu > Yankee > Xray`` rendered nothing at all. The tree is decorated in
    FULL first and this keeps the ancestors as context rows (so a nested match is not indented under
    nothing) and the descendants (so a matching parent still shows its branch). The parent map is
    built from the already-loaded ``parent_id`` values, so this costs no queries.
    """
    parent_of = {row["obj"].pk: row["obj"].parent_id for row in decorated}
    hit = {row["obj"].pk for row in decorated
           if needle in (row["obj"].name or "").lower()
           or needle in (row["obj"].description or "").lower()}
    if not hit:
        return [], 0
    keep = set()
    for pk in parent_of:
        node = pk
        while node is not None:
            if node in hit:
                keep.add(pk)
                break
            node = parent_of.get(node)
    for pk in hit:
        node = parent_of.get(pk)
        while node is not None:
            keep.add(node)
            node = parent_of.get(node)
    return [row for row in decorated if row["obj"].pk in keep], len(hit)


@login_required
def pfd_list(request):
    rows = list(ProjectFolder.objects.filter(tenant=request.tenant)
                .select_related("project", "parent"))
    project_filter = as_db_int(request.GET.get("project", ""))
    if project_filter:
        rows = [row for row in rows if row.project_id == project_filter]
    decorated = _decorate(request.tenant, rows)
    total = len(rows)
    needle = (request.GET.get("q") or "").strip().lower()
    if needle:
        decorated, total = _narrow(decorated, needle)
    return render(request, "projects/documentknowledge/projectfolder/list.html", {
        "rows": decorated,
        "total_count": total,
        "projects": projects(request.tenant),
        "project_filter": project_filter,
        "q": request.GET.get("q", ""),
    })


@login_required
def pfd_detail(request, pk):
    obj = get_object_or_404(ProjectFolder, pk=pk, tenant=request.tenant)
    children = (ProjectFolder.objects.filter(tenant=request.tenant, parent=obj)
                .order_by("sequence", "name", "-id"))
    # `extracted_text` is DEFERRED: the folder page lists a document's number, title, status and
    # owner — never its search copy, which can hold `EXTRACT_MAX_CHARS` characters per row.
    documents = (ProjectDocument.objects.filter(tenant=request.tenant, folder=obj)
                 .select_related("project", "owner").defer("extracted_text")
                 .order_by("-created_at", "-id")[:50])
    return render(request, "projects/documentknowledge/projectfolder/detail.html", {
        "obj": obj,
        "children": children,
        "documents": documents,
        "document_total": ProjectDocument.objects.filter(
            tenant=request.tenant, folder=obj).count(),
    })


@login_required
def pfd_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectFolderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Folder {obj.number} created.")
            return redirect("projects:pfd_detail", pk=obj.pk)
    else:
        form = ProjectFolderForm(tenant=request.tenant, initial={
            "project": as_db_int(request.GET.get("project", "")),
            "parent": as_db_int(request.GET.get("parent", "")),
        })
    return render(request, "projects/documentknowledge/projectfolder/form.html",
                  {"form": form, "is_edit": False})


@login_required
def pfd_edit(request, pk):
    obj = get_object_or_404(ProjectFolder, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = ProjectFolderForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, f"Folder {obj.number} updated.")
            return redirect("projects:pfd_detail", pk=obj.pk)
    else:
        form = ProjectFolderForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/documentknowledge/projectfolder/form.html",
                  {"form": form, "is_edit": True, "obj": obj})


@login_required
def pfd_delete(request, pk):
    obj = get_object_or_404(ProjectFolder, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        held = ProjectDocument.objects.filter(tenant=request.tenant, folder=obj).count()
        children = ProjectFolder.objects.filter(tenant=request.tenant, parent=obj).count()
        if held or children:
            messages.error(
                request,
                f"{obj.number} still holds {held} document(s) and {children} sub-folder(s) — move "
                f"or delete them first.")
            return redirect("projects:pfd_detail", pk=obj.pk)
        number, name = obj.number, obj.name
        write_audit_log(request.user, obj, "delete", changes={"verb": "pfd_delete", "name": name})
        obj.delete()
        messages.success(request, f"Folder {number} ({name}) deleted.")
        return redirect("projects:pfd_list")
    return render(request, "projects/documentknowledge/projectfolder/delete.html", {"obj": obj})


@login_required
@require_POST
def pfd_archive(request, pk):
    """Toggle the archive state. THE one writer of ``is_archived`` + both stamps."""
    obj = get_object_or_404(ProjectFolder, pk=pk, tenant=request.tenant)
    previous = obj.is_archived
    if previous:
        obj.is_archived = False
        obj.archived_by = None
        obj.archived_at = None
    else:
        obj.is_archived = True
        obj.archived_by = request.user
        obj.archived_at = timezone.now()
    obj.save(update_fields=["is_archived", "archived_by", "archived_at", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "pfd_archive", "from": previous, "to": obj.is_archived})
    if obj.is_archived:
        messages.success(request, f"Folder {obj.number} archived — its documents stay readable "
                                  f"through the archive lens.")
    else:
        messages.success(request, f"Folder {obj.number} restored to the live tree.")
    return redirect("projects:pfd_detail", pk=obj.pk)