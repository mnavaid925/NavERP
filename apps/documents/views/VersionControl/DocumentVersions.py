import difflib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.VersionControl.DocumentVersions import DocumentVersionForm
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_version_list(request):
    qs = documents_scope(
        DocumentVersion.objects.select_related("document", "author", "branch").defer("extracted_text"),
        request,
    )

    doc_id = request.GET.get("document", "").strip()
    if doc_id and doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    v_type = request.GET.get("version_type", "").strip()
    if v_type:
        qs = qs.filter(version_type=v_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    is_official = request.GET.get("is_official", "").strip()
    if is_official == "1":
        qs = qs.filter(is_official=True)
    elif is_official == "0":
        qs = qs.filter(is_official=False)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(version_label__icontains=q)
            | Q(number__icontains=q)
            | Q(change_summary__icontains=q)
            | Q(file_name__icontains=q)
            | Q(document__title__icontains=q)
        )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    documents = Document.objects.filter(tenant=request.tenant).order_by("title")

    context = {
        "page_obj": page_obj,
        "versions": page_obj.object_list,
        "documents": documents,
        "version_type_choices": DocumentVersion.VERSION_TYPE_CHOICES,
        "status_choices": DocumentVersion.STATUS_CHOICES,
    }
    return render(request, "documents/version_control/document_version/list.html", context)


@login_required
def document_version_detail(request, pk):
    version = documents_object(
        request,
        DocumentVersion,
        pk,
        select_related=("document", "author", "branch", "restored_from_version"),
    )

    predecessor = (
        DocumentVersion.objects.filter(
            tenant=request.tenant,
            document=version.document,
            created_at__lt=version.created_at,
        )
        .order_by("-created_at")
        .first()
    )

    context = {
        "version": version,
        "obj": version,
        "document": version.document,
        "predecessor": predecessor,
    }
    return render(request, "documents/version_control/document_version/detail.html", context)


@login_required
def document_version_create(request):
    doc_id = request.GET.get("document", "").strip()
    initial = {}
    if doc_id and doc_id.isdigit():
        doc = documents_scope(Document.objects.all(), request).filter(pk=int(doc_id)).first()
        if doc:
            initial["document"] = doc
            # Auto-suggest next version label
            initial["version_label"] = f"{doc.current_version_no}.{doc.versions.count() + 1}"

    if request.method == "POST":
        form = DocumentVersionForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            ver = form.save(commit=False)
            ver.tenant = request.tenant
            if not ver.author_id:
                ver.author = request.user
            ver.save()

            # If marked official, update document current version pointer
            if ver.is_official:
                doc = ver.document
                doc.current_version_label = ver.version_label
                doc.current_version_no = ver.major_number
                doc.save(update_fields=["current_version_label", "current_version_no", "updated_at"])

            write_audit_log(request.user, ver, "create", tenant=request.tenant)
            messages.success(request, f"Version v{ver.version_label} added to {ver.document.number}.")
            return redirect("documents:document_version_detail", pk=ver.pk)
    else:
        form = DocumentVersionForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "version": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "documents/version_control/document_version/form.html", context)


@login_required
def document_version_edit(request, pk):
    version = documents_object(request, DocumentVersion, pk)
    if request.method == "POST":
        form = DocumentVersionForm(request.POST, request.FILES, instance=version, tenant=request.tenant)
        if form.is_valid():
            ver = form.save()
            write_audit_log(request.user, ver, "update", tenant=request.tenant)
            messages.success(request, f"Version v{ver.version_label} updated.")
            return redirect("documents:document_version_detail", pk=ver.pk)
    else:
        form = DocumentVersionForm(instance=version, tenant=request.tenant)

    context = {
        "form": form,
        "version": version,
        "obj": version,
        "is_edit": True,
    }
    return render(request, "documents/version_control/document_version/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def document_version_delete(request, pk):
    version = documents_object(request, DocumentVersion, pk)
    doc_pk = version.document_id
    label = version.version_label
    write_audit_log(request.user, version, "delete", tenant=request.tenant)
    version.delete()
    messages.success(request, f"Version v{label} deleted.")
    return redirect("documents:document_detail", pk=doc_pk)


@login_required
def document_version_compare(request):
    doc_id = request.GET.get("document", "").strip()
    va_id = request.GET.get("version_a", "").strip()
    vb_id = request.GET.get("version_b", "").strip()

    document = None
    versions = DocumentVersion.objects.none()
    version_a = None
    version_b = None
    diff_html = ""
    metadata_diff = {}
    diff_stats = {"lines_added": 0, "lines_removed": 0, "metadata_changes": 0}

    documents = Document.objects.filter(tenant=request.tenant).order_by("title")

    if doc_id and doc_id.isdigit():
        document = documents_scope(Document.objects.all(), request).filter(pk=int(doc_id)).first()
        if document:
            versions = document.versions.select_related("author").order_by("-created_at")

    if document and versions.exists():
        if va_id and va_id.isdigit():
            version_a = versions.filter(pk=int(va_id)).first()
        if vb_id and vb_id.isdigit():
            version_b = versions.filter(pk=int(vb_id)).first()

        # Defaults if not explicitly selected
        if not version_a and versions.count() >= 2:
            version_a = versions[1]  # older
        elif not version_a and versions.count() >= 1:
            version_a = versions[0]

        if not version_b and versions.count() >= 1:
            version_b = versions[0]  # newer

    if version_a and version_b:
        text_a = (version_a.extracted_text or f"(No text content recorded for version {version_a.version_label})").splitlines()
        text_b = (version_b.extracted_text or f"(No text content recorded for version {version_b.version_label})").splitlines()

        label_a = escape(version_a.version_label)
        label_b = escape(version_b.version_label)
        html_diff = difflib.HtmlDiff(wrapcolumn=80)
        diff_html = html_diff.make_table(
            text_a,
            text_b,
            fromdesc=f"Base: v{label_a} ({version_a.created_at.strftime('%Y-%m-%d %H:%M')})",
            todesc=f"Comparison: v{label_b} ({version_b.created_at.strftime('%Y-%m-%d %H:%M')})",
            context=True,
            numlines=3,
        )

        # Quick diff statistics
        matcher = difflib.SequenceMatcher(None, text_a, text_b)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                diff_stats["lines_added"] += (j2 - j1)
            elif tag == "delete":
                diff_stats["lines_removed"] += (i2 - i1)
            elif tag == "replace":
                diff_stats["lines_removed"] += (i2 - i1)
                diff_stats["lines_added"] += (j2 - j1)

        # Metadata delta comparison
        meta_fields = [
            ("Version Type", version_a.get_version_type_display(), version_b.get_version_type_display()),
            ("File Name", version_a.file_name or "—", version_b.file_name or "—"),
            ("File Size", f"{version_a.file_size} bytes", f"{version_b.file_size} bytes"),
            ("Status", version_a.get_status_display(), version_b.get_status_display()),
            ("Is Official", "Yes" if version_a.is_official else "No", "Yes" if version_b.is_official else "No"),
            ("Author", str(version_a.author) if version_a.author else "—", str(version_b.author) if version_b.author else "—"),
            ("Change Summary", version_a.change_summary or "—", version_b.change_summary or "—"),
            ("SHA-256 Digest", version_a.file_hash[:16] + "..." if version_a.file_hash else "—", version_b.file_hash[:16] + "..." if version_b.file_hash else "—"),
        ]

        for label, val_a, val_b in meta_fields:
            changed = (val_a != val_b)
            if changed:
                diff_stats["metadata_changes"] += 1
            metadata_diff[label] = {
                "val_a": val_a,
                "val_b": val_b,
                "changed": changed,
            }

    context = {
        "document": document,
        "documents": documents,
        "versions": versions,
        "version_a": version_a,
        "version_b": version_b,
        "diff_html": diff_html,
        "metadata_diff": metadata_diff,
        "diff_stats": diff_stats,
    }
    return render(request, "documents/version_control/document_version/compare.html", context)


@login_required
@require_POST
def document_version_rollback(request, pk):
    target_version = documents_object(request, DocumentVersion, pk)
    document = target_version.document

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    if document.owner and document.owner != request.user and not is_admin:
        messages.error(request, "Only the document owner or a tenant administrator can roll back versions.")
        return redirect("documents:document_detail", pk=document.pk)

    if document.is_locked:
        locked_by_str = getattr(document.locked_by, "username", "another user")
        messages.error(
            request,
            f"Document '{document.number}' is currently checked out by {locked_by_str} and cannot be rolled back.",
        )
        return redirect("documents:document_detail", pk=document.pk)

    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk, tenant=request.tenant)
        if doc.is_locked:
            locked_by_str = getattr(doc.locked_by, "username", "another user")
            messages.error(
                request,
                f"Document '{doc.number}' is currently checked out by {locked_by_str} and cannot be rolled back.",
            )
            return redirect("documents:document_detail", pk=doc.pk)

        # Calculate new major version number forward
        new_major = doc.current_version_no + 1
        new_label = f"{new_major}.0"

        new_version = DocumentVersion.objects.create(
            tenant=request.tenant,
            document=doc,
            version_label=new_label,
            major_number=new_major,
            minor_number=0,
            patch_number=0,
            version_type="rollback",
            file=target_version.file,
            file_name=target_version.file_name,
            file_size=target_version.file_size,
            file_hash=target_version.file_hash,
            mime_type=target_version.mime_type,
            extracted_text=target_version.extracted_text,
            change_summary=f"Point-in-time restoration from historical version v{target_version.version_label}",
            is_official=True,
            status="approved",
            author=request.user,
            restored_from_version=target_version,
        )

        doc.current_version_label = new_label
        doc.current_version_no = new_major
        doc.save(update_fields=["current_version_label", "current_version_no", "updated_at"])

        write_audit_log(request.user, new_version, "rollback", tenant=request.tenant)

    messages.success(
        request,
        f"Document '{doc.title}' rolled back to content of v{target_version.version_label}. Published forward as new official revision v{new_label}.",
    )
    return redirect("documents:document_detail", pk=doc.pk)
