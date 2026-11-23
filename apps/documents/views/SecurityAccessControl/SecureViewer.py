from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Employment
from apps.core.utils import write_audit_log
from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
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

    doc_id_param = request.GET.get("doc_id", "").strip()
    if not pk and doc_id_param.isdigit():
        pk = int(doc_id_param)

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
    has_read_permission = False
    is_drm_revoked = False

    if document:
        # Check read permission: superuser, tenant admin, document owner, or active ACL grant
        is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
        is_owner = (document.owner_id == request.user.id)
        has_read_permission = is_admin or is_owner

        if not has_read_permission:
            user_party = getattr(request.user, "party", None)
            user_emp = (
                Employment.objects.filter(tenant=request.tenant, party=user_party).order_by("-id").first()
                if user_party
                else None
            )
            user_dept = user_emp.org_unit if user_emp else None

            now = timezone.now()
            q_target = Q(document=document)
            if document.folder_id:
                q_target |= Q(folder_id=document.folder_id)

            has_read_permission = DocumentAccessPermission.objects.filter(
                tenant=request.tenant,
                is_active=True,
                can_read=True,
            ).filter(q_target).filter(
                Q(grantee_type="tenant_wide")
                | Q(grantee_type="user", user=request.user)
                | (Q(grantee_type="org_unit", org_unit=user_dept) if user_dept else Q(pk__in=[]))
            ).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=now),
                Q(valid_until__isnull=True) | Q(valid_until__gte=now),
            ).exists()

        # Find matching DRM policy (both specific document and classification)
        drm_policy = DocumentDrmPolicy.objects.filter(
            tenant=request.tenant,
            is_active=True,
            target_document=document,
        ).first()

        if not drm_policy:
            drm_policy = DocumentDrmPolicy.objects.filter(
                tenant=request.tenant,
                is_active=True,
                target_document__isnull=True,
                classification=document.classification,
            ).first()

        if drm_policy and drm_policy.is_revoked:
            is_drm_revoked = True

        if drm_policy and not is_drm_revoked:
            screen_shield = drm_policy.screen_shield_enabled
            allow_copy = drm_policy.allow_copy_paste
            allow_print = drm_policy.allow_print
            allow_download = drm_policy.allow_download

        version = document.versions.order_by("-created_at").first()

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

        if not has_read_permission:
            write_audit_log(request.user, document, "view_denied", tenant=request.tenant)
        elif is_drm_revoked:
            write_audit_log(request.user, document, "view_revoked", tenant=request.tenant)
        else:
            write_audit_log(request.user, document, "view", tenant=request.tenant)

    context = {
        "document": document,
        "version": version,
        "watermark_policy": watermark_policy,
        "drm_policy": drm_policy,
        "has_read_permission": has_read_permission,
        "is_drm_revoked": is_drm_revoked,
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
