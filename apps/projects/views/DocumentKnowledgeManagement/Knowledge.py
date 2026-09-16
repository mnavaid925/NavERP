"""Projects 7.10 — KnowledgeEntry views: the insight library (bullet 4) and its search page.

Two lists, one register: ``kne_list`` is the browsable register (kind/status lenses, featured shelf
first) and ``kne_search`` is the full-text page over title/summary/body/tags with the honest empty
state (Ruling 6 — a lesson with no body matches on title/tags only, and the page says so).

``kne_use`` increments ``usage_count`` with an atomic ``F("usage_count") + 1`` — never a
read-modify-write, so two people pressing "use this" in the same second both count.
``kne_publish`` is the ONE writer that moves a row between ``draft`` and ``published``; retiring is
an edit, because it is metadata, not a state machine with evidence attached.
"""
from django.db.models import F, Q

from apps.core.crud import as_db_int, paginate
from apps.projects.forms import KnowledgeEntryForm
from apps.projects.models import KnowledgeEntry
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import (get_object_or_404, login_required, messages,
                                         redirect, render, require_POST, tenant_admin_required,
                                         write_audit_log)
from apps.projects.views._helpers import projects


@login_required
def kne_list(request):
    qs = (KnowledgeEntry.objects.filter(tenant=request.tenant)
          .select_related("source_project", "document", "owner"))
    return crud_list(
        request, qs, "projects/documentknowledge/knowledgeentry/list.html",
        search_fields=["number", "title", "summary", "tags"],
        filters=[("kind", "kind", False), ("status", "status", False),
                 ("project", "source_project_id", True), ("is_featured", "is_featured", False)],
        extra_context={
            "projects": projects(request.tenant),
            "kind_choices": KnowledgeEntry.KIND_CHOICES,
            "status_choices": KnowledgeEntry.STATUS_CHOICES,
        },
    )


@login_required
def kne_search(request):
    """The knowledge search page: title/summary/body/tags/category, from ONE character of query.

    ``body`` is prose the user wrote (not a stored file copy), so the 4+-character rule that governs
    the document register's ``extracted_text`` sweep does not apply here — but the page still says
    plainly which fields it searched, so an empty result is never a mystery.
    """
    raw = (request.GET.get("q") or "").strip()
    qs = KnowledgeEntry.objects.filter(tenant=request.tenant).select_related(
        "source_project", "document", "owner")
    searched = ["title", "summary", "body", "tags", "category"]
    if raw:
        cond = Q()
        for field in searched:
            cond |= Q(**{f"{field}__icontains": raw})
        qs = qs.filter(cond)
    # The kind lens is applied here rather than left to the template: a dropdown that renders and
    # then filters nothing is worse than no dropdown at all. Unknown values are IGNORED, not matched
    # (the L11 rule crud_list applies) — `?kind=nope` must fall back to the whole library rather
    # than silently emptying the page.
    kind_filter = request.GET.get("kind", "").strip()
    valid_kinds = {value for value, _label in KnowledgeEntry.KIND_CHOICES}
    if kind_filter and kind_filter in valid_kinds:
        qs = qs.filter(kind=kind_filter)
    else:
        kind_filter = ""
    return render(request, "projects/documentknowledge/knowledgeentry/search.html", {
        # `crud.paginate`, not a private copy: it is the helper that stamps `page.window`, and
        # `partials/pagination.html`'s number loop iterates `page_obj.window` — a local
        # `Paginator(...).get_page(...)` renders Prev/Next and no page numbers at all.
        "rows": paginate(request, qs),
        "total_count": qs.count(),
        "q": raw,
        "searched_fields": searched,
        "kind_choices": KnowledgeEntry.KIND_CHOICES,
        "kind_filter": kind_filter,
    })


@login_required
def kne_detail(request, pk):
    obj = get_object_or_404(KnowledgeEntry, pk=pk, tenant=request.tenant)
    return render(request, "projects/documentknowledge/knowledgeentry/detail.html", {"obj": obj})


@login_required
def kne_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = KnowledgeEntryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Knowledge entry {obj.number} created.")
            return redirect("projects:kne_detail", pk=obj.pk)
    else:
        form = KnowledgeEntryForm(tenant=request.tenant, initial={
            "source_project": as_db_int(request.GET.get("project", "")),
        })
    return render(request, "projects/documentknowledge/knowledgeentry/form.html",
                  {"form": form, "is_edit": False})


@login_required
def kne_edit(request, pk):
    obj = get_object_or_404(KnowledgeEntry, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = KnowledgeEntryForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, f"Knowledge entry {obj.number} updated.")
            return redirect("projects:kne_detail", pk=obj.pk)
    else:
        form = KnowledgeEntryForm(instance=obj, tenant=request.tenant)
    return render(request, "projects/documentknowledge/knowledgeentry/form.html",
                  {"form": form, "is_edit": True, "obj": obj})


@login_required
def kne_delete(request, pk):
    obj = get_object_or_404(KnowledgeEntry, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        number, title = obj.number, obj.title
        write_audit_log(request.user, obj, "delete", changes={"verb": "kne_delete", "title": title})
        obj.delete()
        messages.success(request, f"Knowledge entry {number} ({title}) deleted.")
        return redirect("projects:kne_list")
    return render(request, "projects/documentknowledge/knowledgeentry/delete.html", {"obj": obj})


@login_required
@require_POST
def kne_use(request, pk):
    """Count a reuse. Atomic on purpose — a read-modify-write silently drops concurrent presses."""
    obj = get_object_or_404(KnowledgeEntry, pk=pk, tenant=request.tenant)
    KnowledgeEntry.objects.filter(pk=obj.pk, tenant=request.tenant).update(
        usage_count=F("usage_count") + 1)
    obj.refresh_from_db(fields=["usage_count"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "kne_use", "to": obj.usage_count})
    messages.success(request, f"Noted — {obj.title} has now been used {obj.usage_count} time(s).")
    return redirect("projects:kne_detail", pk=obj.pk)


@login_required
@require_POST
@tenant_admin_required
def kne_publish(request, pk):
    """Toggle draft/published. THE one writer of that transition (retiring stays an edit).

    Admin-gated: publishing to the shared library is a curation decision, not a personal one.
    """
    obj = get_object_or_404(KnowledgeEntry, pk=pk, tenant=request.tenant)
    if obj.status == "retired":
        messages.error(request, f"{obj.number} is retired — edit it back to draft before "
                                f"publishing it again.")
        return redirect("projects:kne_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "draft" if previous == "published" else "published"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    changes={"verb": "kne_publish", "from": previous, "to": obj.status})
    messages.success(request, f"Knowledge entry {obj.number} is now {obj.get_status_display()}.")
    return redirect("projects:kne_detail", pk=obj.pk)