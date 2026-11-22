from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.VersionControl.DocumentLocks import (
    CheckinForm,
    CheckoutForm,
    ForceUnlockForm,
)
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentLocks import DocumentLock
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_lock_list(request):
    qs = documents_scope(
        DocumentLock.objects.select_related("document", "base_version", "locked_by", "unlocked_by").defer(
            "base_version__extracted_text"
        ),
        request,
    )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    else:
        # Default to active locks first
        pass

    lock_type = request.GET.get("lock_type", "").strip()
    if lock_type:
        qs = qs.filter(lock_type=lock_type)

    doc_id = request.GET.get("document", "").strip()
    if doc_id and doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(checkout_note__icontains=q)
            | Q(document__title__icontains=q)
            | Q(locked_by__username__icontains=q)
        )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    documents = Document.objects.filter(tenant=request.tenant).only("id", "title", "number").order_by("title")

    context = {
        "page_obj": page_obj,
        "locks": page_obj.object_list,
        "status_choices": DocumentLock.STATUS_CHOICES,
        "lock_type_choices": DocumentLock.LOCK_TYPE_CHOICES,
        "documents": documents,
    }
    return render(request, "documents/version_control/document_lock/list.html", context)


@login_required
def document_lock_detail(request, pk):
    lock = documents_object(
        request,
        DocumentLock,
        pk,
        select_related=("document", "base_version", "locked_by", "unlocked_by"),
    )

    context = {
        "lock": lock,
        "obj": lock,
        "document": lock.document,
    }
    return render(request, "documents/version_control/document_lock/detail.html", context)


@login_required
def document_checkout(request, doc_pk):
    document = documents_object(request, Document, doc_pk)

    if document.is_locked:
        locked_by_str = getattr(document.locked_by, "username", "another user")
        messages.error(request, f"Document '{document.number}' is already checked out by {locked_by_str}.")
        return redirect("documents:document_detail", pk=document.pk)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            hours = form.cleaned_data.get("expires_in_hours") or 24
            expires_at = timezone.now() + timedelta(hours=hours)

            with transaction.atomic():
                document = Document.objects.select_for_update().get(pk=doc_pk, tenant=request.tenant)
                if document.is_locked:
                    locked_by_str = getattr(document.locked_by, "username", "another user")
                    messages.error(request, f"Document '{document.number}' is already checked out by {locked_by_str}.")
                    return redirect("documents:document_detail", pk=document.pk)

                base_version = document.versions.order_by("-created_at").first()
                if not base_version:
                    base_version = DocumentVersion.objects.create(
                        tenant=request.tenant,
                        document=document,
                        version_label=document.current_version_label or "1.0",
                        major_number=document.current_version_no or 1,
                        minor_number=0,
                        patch_number=0,
                        version_type="major",
                        file_name=f"{document.slug or 'doc'}_v1.0.txt",
                        extracted_text=document.description or document.title,
                        change_summary="Initial document baseline version",
                        is_official=True,
                        status="approved",
                        author=document.owner or request.user,
                    )

                lock = DocumentLock.objects.create(
                    tenant=request.tenant,
                    document=document,
                    base_version=base_version,
                    locked_by=request.user,
                    lock_type=form.cleaned_data["lock_type"],
                    checkout_note=form.cleaned_data.get("checkout_note", ""),
                    expires_at=expires_at,
                    status="active",
                )
                document.is_locked = True
                document.locked_by = request.user
                document.locked_at = timezone.now()
                document.save(update_fields=["is_locked", "locked_by", "locked_at", "updated_at"])

            write_audit_log(request.user, lock, "checkout", tenant=request.tenant)
            messages.success(request, f"Document '{document.number}' successfully checked out.")
            return redirect("documents:document_detail", pk=document.pk)
    else:
        form = CheckoutForm()

    base_version = document.versions.order_by("-created_at").first()
    context = {
        "form": form,
        "document": document,
        "base_version": base_version,
    }
    return render(request, "documents/version_control/document_lock/checkout_modal.html", context)


@login_required
def document_checkin(request, doc_pk):
    document = documents_object(request, Document, doc_pk)
    lock = document.locks.filter(status="active").first()

    if not lock:
        messages.error(request, f"Document '{document.number}' is not currently checked out.")
        return redirect("documents:document_detail", pk=document.pk)

    if lock.locked_by != request.user and not request.user.is_superuser:
        locked_by_str = getattr(lock.locked_by, "username", "another user")
        messages.error(request, f"You do not hold the active lock on this document (locked by {locked_by_str}).")
        return redirect("documents:document_detail", pk=document.pk)

    base = lock.base_version

    if request.method == "POST":
        form = CheckinForm(request.POST, request.FILES)
        if form.is_valid():
            intent = form.cleaned_data["increment_intent"]
            summary = form.cleaned_data["change_summary"]
            file = form.cleaned_data.get("file")
            extracted_text = form.cleaned_data.get("extracted_text", "")
            is_official = form.cleaned_data.get("is_official", True)

            # Auto calculate version label
            if intent == "major":
                major = base.major_number + 1
                minor = 0
                patch = 0
                label = f"{major}.0"
            elif intent == "patch":
                major = base.major_number
                minor = base.minor_number
                patch = base.patch_number + 1
                label = f"{major}.{minor}.{patch}"
            else:  # minor
                major = base.major_number
                minor = base.minor_number + 1
                patch = 0
                label = f"{major}.{minor}"

            with transaction.atomic():
                new_ver = DocumentVersion.objects.create(
                    tenant=request.tenant,
                    document=document,
                    version_label=label,
                    major_number=major,
                    minor_number=minor,
                    patch_number=patch,
                    version_type=intent,
                    file=file or base.file,
                    file_name=file.name if file else base.file_name,
                    extracted_text=extracted_text or base.extracted_text,
                    change_summary=summary,
                    is_official=is_official,
                    status="approved",
                    author=request.user,
                )

                lock.status = "checked_in"
                lock.unlocked_at = timezone.now()
                lock.unlocked_by = request.user
                lock.save(update_fields=["status", "unlocked_at", "unlocked_by", "updated_at"])

                document.is_locked = False
                document.locked_by = None
                document.locked_at = None
                if is_official:
                    document.current_version_label = label
                    document.current_version_no = major
                document.save(
                    update_fields=[
                        "is_locked",
                        "locked_by",
                        "locked_at",
                        "current_version_label",
                        "current_version_no",
                        "updated_at",
                    ]
                )

            write_audit_log(request.user, new_ver, "checkin", tenant=request.tenant)
            messages.success(request, f"Document '{document.number}' checked in as v{label}.")
            return redirect("documents:document_detail", pk=document.pk)
    else:
        form = CheckinForm(
            initial={
                "extracted_text": base.extracted_text if base else "",
            }
        )

    context = {
        "form": form,
        "document": document,
        "lock": lock,
        "base_version": base,
    }
    return render(request, "documents/version_control/document_lock/checkin_modal.html", context)


@login_required
@require_POST
def document_discard_checkout(request, doc_pk):
    document = documents_object(request, Document, doc_pk)
    lock = document.locks.filter(status="active").first()

    if not lock:
        messages.error(request, "No active lock found for this document.")
        return redirect("documents:document_detail", pk=document.pk)

    if lock.locked_by != request.user and not request.user.is_superuser:
        messages.error(request, "You cannot discard a lock held by another author.")
        return redirect("documents:document_detail", pk=document.pk)

    with transaction.atomic():
        lock.status = "discarded"
        lock.unlocked_at = timezone.now()
        lock.unlocked_by = request.user
        lock.save(update_fields=["status", "unlocked_at", "unlocked_by", "updated_at"])

        document.is_locked = False
        document.locked_by = None
        document.locked_at = None
        document.save(update_fields=["is_locked", "locked_by", "locked_at", "updated_at"])

    write_audit_log(request.user, lock, "discard", tenant=request.tenant)
    messages.info(request, f"Check-out on document '{document.number}' cancelled. Staged edits discarded.")
    return redirect("documents:document_detail", pk=document.pk)


@tenant_admin_required
def document_force_unlock(request, pk):
    lock = documents_object(request, DocumentLock, pk)
    document = lock.document

    if lock.status != "active":
        messages.info(request, "This lock is no longer active.")
        return redirect("documents:document_detail", pk=document.pk)

    if request.method == "POST":
        form = ForceUnlockForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data["override_reason"]

            with transaction.atomic():
                lock.status = "force_unlocked"
                lock.unlocked_at = timezone.now()
                lock.unlocked_by = request.user
                lock.override_reason = reason
                lock.save(update_fields=["status", "unlocked_at", "unlocked_by", "override_reason", "updated_at"])

                document.is_locked = False
                document.locked_by = None
                document.locked_at = None
                document.save(update_fields=["is_locked", "locked_by", "locked_at", "updated_at"])

            write_audit_log(request.user, lock, "unlock", tenant=request.tenant)
            messages.warning(
                request,
                f"Lock on document '{document.number}' forcibly broken. Administrative justification logged.",
            )
            return redirect("documents:document_detail", pk=document.pk)
    else:
        form = ForceUnlockForm()

    context = {
        "form": form,
        "lock": lock,
        "document": document,
    }
    return render(request, "documents/version_control/document_lock/force_unlock.html", context)
