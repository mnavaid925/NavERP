from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetProcurement.AssetTags import AssetTagForm
from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
from apps.assets.models.AssetProcurement.AssetTags import AssetTag
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def asset_tag_list(request):
    """List asset tags with format, status filters, search, and pagination."""
    queryset = assets_scope(AssetTag.objects.all(), request).select_related(
        "operational_asset", "capitalization", "affixed_by", "verified_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(tag_code__icontains=q)
            | Q(physical_placement__icontains=q)
            | Q(notes__icontains=q)
            | Q(scanner_device_id__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        queryset = queryset.filter(status=status)

    fmt = request.GET.get("format", "").strip()
    if fmt:
        queryset = queryset.filter(tag_format=fmt)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "tags": page_obj,
        "page_obj": page_obj,
        "status_choices": AssetTag.STATUS_CHOICES,
        "format_choices": AssetTag.TAG_FORMAT_CHOICES,
    }
    return render(request, "assets/asset_procurement/asset_tag/list.html", context)


@login_required
def asset_tag_detail(request, pk):
    """Display comprehensive details of an asset tag record."""
    tag = assets_object(
        request,
        AssetTag,
        pk,
        select_related=(
            "operational_asset",
            "capitalization",
            "affixed_by",
            "verified_by",
        ),
    )
    return render(
        request,
        "assets/asset_procurement/asset_tag/detail.html",
        {"tag": tag},
    )


@login_required
def asset_tag_create(request):
    """Issue a new machine-readable asset tag."""
    initial = {}
    cap_pk = request.GET.get("capitalization", "").strip()
    if cap_pk and cap_pk.isdigit():
        cap = assets_scope(AssetCapitalization.objects.all(), request).filter(pk=int(cap_pk)).first()
        if cap:
            initial["capitalization"] = cap
            if cap.operational_asset:
                initial["operational_asset"] = cap.operational_asset
            initial["tag_code"] = f"AST-{cap.number.replace('ACAP-', '')}"

    if request.method == "POST":
        form = AssetTagForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.tenant = request.tenant
            tag.save()
            write_audit_log(
                request.user,
                tag,
                "create",
                changes={"details": f"Issued asset tag {tag.tag_code} ({tag.number})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Tag {tag.tag_code} created successfully.")
            return redirect("assets:asset_tag_detail", pk=tag.pk)
    else:
        form = AssetTagForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_tag/form.html",
        {"form": form, "tag": None, "is_edit": False},
    )


@login_required
def asset_tag_edit(request, pk):
    """Update details of an asset tag record."""
    tag = assets_object(request, AssetTag, pk)

    if request.method == "POST":
        form = AssetTagForm(request.POST, instance=tag, tenant=request.tenant)
        if form.is_valid():
            t = form.save()
            write_audit_log(
                request.user,
                t,
                "update",
                changes={"details": f"Updated asset tag {t.tag_code}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Tag {t.tag_code} updated successfully.")
            return redirect("assets:asset_tag_detail", pk=t.pk)
    else:
        form = AssetTagForm(instance=tag, tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_tag/form.html",
        {"form": form, "tag": tag, "is_edit": True},
    )


@login_required
@require_POST
def asset_tag_delete(request, pk):
    """Delete an asset tag record."""
    tag = assets_object(request, AssetTag, pk)
    if tag.status not in ("pending_print", "printed", "damaged_reissued"):
        messages.error(request, f"Tag {tag.tag_code} cannot be deleted in status '{tag.get_status_display()}'.")
        return redirect("assets:asset_tag_detail", pk=tag.pk)
    code = tag.tag_code
    write_audit_log(
        request.user,
        tag,
        "delete",
        changes={"details": f"Deleted asset tag {code}"},
        tenant=request.tenant,
    )
    tag.delete()
    messages.success(request, f"Asset Tag {code} was deleted.")
    return redirect("assets:asset_tag_list")


@login_required
@require_POST
def asset_tag_mark_printed(request, pk):
    """Mark an asset tag as printed."""
    tag = assets_object(request, AssetTag, pk)
    if not tag.can_mark_printed():
        messages.error(request, f"Tag {tag.tag_code} cannot be marked printed from state '{tag.get_status_display()}'.")
        return redirect("assets:asset_tag_detail", pk=tag.pk)

    with transaction.atomic():
        tag.status = "printed"
        tag.save(update_fields=["status", "updated_at"])

        write_audit_log(
            request.user,
            tag,
            "update",
            changes={"action": "mark_printed", "details": f"Marked asset tag {tag.tag_code} as printed"},
            tenant=request.tenant,
        )
    messages.success(request, f"Asset Tag {tag.tag_code} marked as printed.")
    return redirect("assets:asset_tag_detail", pk=tag.pk)


@login_required
@require_POST
def asset_tag_affix(request, pk):
    """Confirm physical affixation of the tag to the machine or chassis."""
    tag = assets_object(request, AssetTag, pk)
    if not tag.can_affix():
        messages.error(request, f"Tag {tag.tag_code} cannot be affixed from state '{tag.get_status_display()}'.")
        return redirect("assets:asset_tag_detail", pk=tag.pk)

    with transaction.atomic():
        placement = request.POST.get("physical_placement", "").strip()
        if placement:
            tag.physical_placement = placement

        tag.status = "affixed"
        tag.affixed_by = request.user
        tag.affixed_at = timezone.now()
        tag.save(update_fields=["status", "physical_placement", "affixed_by", "affixed_at", "updated_at"])

        write_audit_log(
            request.user,
            tag,
            "update",
            changes={"action": "affix_tag", "details": f"Affixed asset tag {tag.tag_code} to equipment"},
            tenant=request.tenant,
        )
    messages.success(request, f"Asset Tag {tag.tag_code} confirmed affixed to physical asset.")
    return redirect("assets:asset_tag_detail", pk=tag.pk)


@login_required
@require_POST
def asset_tag_verify(request, pk):
    """Record optical barcode / RFID scanner audit verification."""
    tag = assets_object(request, AssetTag, pk)
    if not tag.can_verify():
        messages.error(request, f"Tag {tag.tag_code} cannot be verified from state '{tag.get_status_display()}'.")
        return redirect("assets:asset_tag_detail", pk=tag.pk)

    with transaction.atomic():
        device_id = request.POST.get("scanner_device_id", "").strip()
        if device_id:
            tag.scanner_device_id = device_id

        tag.status = "verified"
        tag.is_verified = True
        tag.verified_by = request.user
        tag.verified_at = timezone.now()
        tag.save(update_fields=["status", "is_verified", "scanner_device_id", "verified_by", "verified_at", "updated_at"])

        write_audit_log(
            request.user,
            tag,
            "update",
            changes={"action": "verify_tag", "details": f"Verified asset tag {tag.tag_code} with scanner {tag.scanner_device_id or 'standard'}"},
            tenant=request.tenant,
        )
    messages.success(request, f"Asset Tag {tag.tag_code} successfully verified by scanner.")
    return redirect("assets:asset_tag_detail", pk=tag.pk)


@login_required
def asset_tag_print_label(request, pk):
    """Render a clean, high-contrast printable asset label with QR/barcode representation."""
    tag = assets_object(
        request,
        AssetTag,
        pk,
        select_related=("operational_asset", "operational_asset__location", "capitalization"),
    )
    return render(
        request,
        "assets/asset_procurement/asset_tag/print_label.html",
        {"tag": tag},
    )
