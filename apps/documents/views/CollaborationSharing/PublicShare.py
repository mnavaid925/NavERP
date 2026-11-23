from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.documents.models.ApprovalWorkflow.DocumentReviewComments import DocumentReviewComment
from apps.documents.models.CollaborationSharing.DocumentActivities import DocumentActivity
from apps.documents.models.CollaborationSharing.DocumentShares import DocumentShare
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion


def public_share_preview(request, share_token):
    """Guest-facing web preview endpoint for document shares with password challenge and permission gating."""
    share = get_object_or_404(
        DocumentShare.objects.select_related("document", "folder", "version", "shared_by"),
        share_token=share_token,
    )

    if not share.is_valid:
        raise Http404("This share link has expired, been revoked, or reached its usage limit.")

    password_required = share.has_password
    password_error = None
    session_key = f"share_auth_{share.share_token}"

    if password_required:
        if request.session.get(session_key) == True:
            password_required = False
        elif request.method == "POST":
            submitted_password = request.POST.get("password", "")
            if share.check_password(submitted_password):
                request.session[session_key] = True
                password_required = False
            else:
                password_error = "Incorrect password. Please verify and try again."

    if not password_required and request.method == "GET":
        share.record_access()

        guest_identifier = request.META.get("REMOTE_ADDR") or "External Guest"
        DocumentActivity.objects.create(
            tenant=share.tenant,
            document=share.document,
            guest_name=guest_identifier,
            action_type="link_accessed",
            summary=f"Public share link {share.number} was accessed from IP {guest_identifier}",
            notification_channel="none",
        )

    version = share.version
    if not version and share.document:
        version = DocumentVersion.objects.filter(
            tenant=share.tenant,
            document=share.document,
        ).order_by("-created_at").first()

    annotations = []
    if share.include_annotations and not password_required:
        annotations = DocumentReviewComment.objects.filter(
            tenant=share.tenant,
            document=share.document,
        ).select_related("author").order_by("page_number", "-created_at")

    context = {
        "share": share,
        "document": share.document,
        "version": version,
        "password_required": password_required,
        "password_error": password_error,
        "can_download": share.allow_download,
        "can_print": share.allow_print,
        "can_comment": share.access_level in ("comment", "edit"),
        "can_edit": share.access_level == "edit",
        "annotations": annotations,
    }
    return render(request, "documents/collaboration_sharing/public_share_preview.html", context)


def public_share_download(request, share_token):
    """File download handler enforcing download prevention flags and logging access."""
    share = get_object_or_404(
        DocumentShare.objects.select_related("document", "version"),
        share_token=share_token,
    )

    if not share.is_valid:
        raise Http404("This share link is no longer valid.")

    if not share.allow_download:
        return HttpResponseForbidden("File downloading has been disabled by the document owner.")

    session_key = f"share_auth_{share.share_token}"
    if share.has_password and not request.session.get(session_key):
        return HttpResponseForbidden("Password authentication required before downloading.")

    version = share.version
    if not version:
        version = DocumentVersion.objects.filter(
            tenant=share.tenant,
            document=share.document,
        ).order_by("-created_at").first()

    if not version:
        raise Http404("No document file revision available for download.")

    guest_identifier = request.META.get("REMOTE_ADDR") or "External Guest"
    DocumentActivity.objects.create(
        tenant=share.tenant,
        document=share.document,
        guest_name=guest_identifier,
        action_type="file_downloaded",
        summary=f"Document '{share.document.title}' ({version.number}) downloaded via share {share.number}",
        notification_channel="in_app",
    )

    content = version.extracted_text or f"Document: {share.document.title}\nVersion: {version.number}"
    response = HttpResponse(content, content_type=version.mime_type or "text/plain")
    filename = f"{share.document.slug or 'document'}_{version.number}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
