from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_scope


@login_required
def secure_viewer(request, pk=None):
    """
    Sandboxed zero-download secure viewer console with active forensic watermark,
    anti-screen capture blur, right-click disabling, and keyboard interceptors.
    """
    docs_qs = documents_scope(Document.objects.all(), request).order_by("-updated_at")

    document = None
    if pk:
        document = get_object_or_404(docs_qs, pk=pk)
    else:
        document = docs_qs.first()

    version = None
    watermark_policy = None
    drm_policy = None
    watermark_text = ""
    screen_shield = True
    allow_copy = False
    allow_print = False
    allow_download = False

    ip_addr = request.META.get("REMOTE_ADDR", "127.0.0.1")

    if document:
        version = document.versions.order_by("-version_number").first()

        # Find matching DRM policy
        drm_policy = DocumentDrmPolicy.objects.filter(
            tenant=request.tenant,
            is_active=True,
            is_revoked=False,
        ).filter(
            target_document=document
        ).first()

        if not drm_policy:
            drm_policy = DocumentDrmPolicy.objects.filter(
                tenant=request.tenant,
                is_active=True,
                is_revoked=False,
                classification=document.classification,
            ).first()

        if drm_policy:
            screen_shield = drm_policy.screen_shield_enabled
            allow_copy = drm_policy.allow_copy_paste
            allow_print = drm_policy.allow_print
            allow_download = drm_policy.allow_download

        # Find matching watermark policy
        watermark_policy = WatermarkPolicy.objects.filter(
            tenant=request.tenant,
            is_active=True,
        ).filter(
            classification__in=["all", document.classification]
        ).order_by("priority").first()

        if watermark_policy:
            watermark_text = watermark_policy.render_watermark(
                user=request.user,
                document=document,
                ip_address=ip_addr,
            )
        else:
            ts = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
            watermark_text = f"{document.get_classification_display().upper()} | {request.user.get_full_name() or request.user.username} | {ip_addr} | {ts}"

        write_audit_log(request.user, document, "view", tenant=request.tenant)

    context = {
        "document": document,
        "version": version,
        "watermark_policy": watermark_policy,
        "drm_policy": drm_policy,
        "watermark_text": watermark_text,
        "screen_shield": screen_shield,
        "allow_copy": allow_copy,
        "allow_print": allow_print,
        "allow_download": allow_download,
        "available_documents": docs_qs[:25],
    }
    return render(
        request,
        "documents/security_access_control/secure_viewer.html",
        context,
    )
