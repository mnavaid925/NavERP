from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.CollaborationSharing.DocumentShares import DocumentShareForm
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_share_list(request):
    base_qs = documents_scope(DocumentShare.objects.all(), request).select_related(
        "document", "shared_by", "shared_with_user", "shared_with_org_unit"
    )

    total_count = base_qs.count()
    active_count = base_qs.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).count()
    expired_count = base_qs.filter(expires_at__lte=timezone.now()).count()
    revoked_count = base_qs.filter(is_active=False).count()

    qs = base_qs
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(document__title__icontains=q)
            | Q(shared_with_email__icontains=q)
            | Q(shared_with_user__first_name__icontains=q)
            | Q(shared_with_user__username__icontains=q)
        )

    current_share_type = request.GET.get("share_type", "").strip()
    if current_share_type:
        qs = qs.filter(share_type=current_share_type)

    current_access_level = request.GET.get("access_level", "").strip()
    if current_access_level:
        qs = qs.filter(access_level=current_access_level)

    current_status = request.GET.get("status", "").strip()
    now = timezone.now()
    if current_status == "active":
        qs = qs.filter(is_active=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    elif current_status == "expired":
        qs = qs.filter(expires_at__lte=now)
    elif current_status == "revoked":
        qs = qs.filter(is_active=False)

    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    status_choices = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    context = {
        "page_obj": page_obj,
        "shares": page_obj.object_list,
        "share_type_choices": DocumentShare.SHARE_TYPE_CHOICES,
        "access_level_choices": DocumentShare.ACCESS_LEVEL_CHOICES,
        "status_choices": status_choices,
        "total_count": total_count,
        "active_count": active_count,
        "expired_count": expired_count,
        "revoked_count": revoked_count,
        "q": q,
        "current_share_type": current_share_type,
        "current_access_level": current_access_level,
        "current_status": current_status,
    }
    return render(request, "documents/collaboration_sharing/document_share/list.html", context)


@login_required
def document_share_detail(request, pk):
    share = documents_object(
        request,
        DocumentShare,
        pk,
        select_related=["document", "folder", "version", "shared_by", "shared_with_user", "shared_with_org_unit", "revoked_by"],
    )

    share_url = request.build_absolute_uri(
        reverse("documents:public_share_preview", kwargs={"share_token": share.share_token})
    )

    activities = DocumentActivity.objects.filter(
        tenant=request.tenant,
        document=share.document,
        action_type__in=["document_shared", "share_revoked", "link_accessed", "file_downloaded"],
    ).order_by("-created_at")[:10]

    context = {
        "share": share,
        "share_url": share_url,
        "activities": activities,
    }
    return render(request, "documents/collaboration_sharing/document_share/detail.html", context)


@login_required
def document_share_create(request):
    if request.method == "POST":
        form = DocumentShareForm(request.POST, tenant=request.tenant, user=request.user)
        if form.is_valid():
            share = form.save(commit=False)
            share.tenant = request.tenant
            share.save()
            form.save_m2m()
            write_audit_log(request.user, share, "create", tenant=request.tenant)

            # Record collaboration activity
            DocumentActivity.objects.create(
                tenant=request.tenant,
                document=share.document,
                actor=request.user,
                target_user=share.shared_with_user,
                action_type="document_shared",
                summary=f"Shared '{share.document.title}' via {share.get_share_type_display()} ({share.get_access_level_display()})",
                notification_channel="in_app",
            )

            messages.success(request, f"Document share {share.number} created successfully.")
            return redirect("documents:document_share_detail", pk=share.pk)
    else:
        initial = {}
        doc_id = request.GET.get("document")
        if doc_id and doc_id.isdigit():
            initial["document"] = int(doc_id)
        form = DocumentShareForm(initial=initial, tenant=request.tenant, user=request.user)

    context = {
        "form": form,
        "share": None,
        "is_edit": False,
    }
    return render(request, "documents/collaboration_sharing/document_share/form.html", context)


@login_required
def document_share_edit(request, pk):
    share = documents_object(request, DocumentShare, pk)
    if request.method == "POST":
        form = DocumentShareForm(request.POST, instance=share, tenant=request.tenant, user=request.user)
        if form.is_valid():
            share = form.save()
            write_audit_log(request.user, share, "update", tenant=request.tenant)
            messages.success(request, f"Document share {share.number} updated successfully.")
            return redirect("documents:document_share_detail", pk=share.pk)
    else:
        form = DocumentShareForm(instance=share, tenant=request.tenant, user=request.user)

    context = {
        "form": form,
        "share": share,
        "is_edit": True,
    }
    return render(request, "documents/collaboration_sharing/document_share/form.html", context)


@login_required
@require_POST
def document_share_delete(request, pk):
    share = documents_object(request, DocumentShare, pk)
    share_number = share.number
    write_audit_log(request.user, share, "delete", tenant=request.tenant)
    share.delete()
    messages.success(request, f"Document share {share_number} deleted successfully.")
    return redirect("documents:document_share_list")


@login_required
@require_POST
def document_share_revoke(request, pk):
    share = documents_object(request, DocumentShare, pk)
    share.revoke(request.user)
    write_audit_log(request.user, share, "revoke", tenant=request.tenant)

    DocumentActivity.objects.create(
        tenant=request.tenant,
        document=share.document,
        actor=request.user,
        target_user=share.shared_with_user,
        action_type="share_revoked",
        summary=f"Revoked share link {share.number} for '{share.document.title}'",
        notification_channel="in_app",
    )

    messages.warning(request, f"Document share {share.number} has been revoked.")
    return redirect("documents:document_share_detail", pk=share.pk)
