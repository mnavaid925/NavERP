"""Inventory 5.14 Barcode & RFID Integration — BarcodeLabel CRUD + print/render views."""
from io import BytesIO

import barcode
import qrcode
import qrcode.image.svg  # noqa: F401 — registers the SVG image factory on qrcode.image
from barcode.errors import BarcodeError, NumberOfDigitsError
from barcode.writer import SVGWriter
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import Http404, HttpResponse

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import BarcodeLabelForm
from apps.inventory.models import BarcodeLabel
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def barcodelabel_list(request):
    """List warehouse barcode labels with search, status/kind filters and KPI strip."""
    qs = (
        BarcodeLabel.objects.filter(tenant=request.tenant)
        .select_related("item", "location", "lot_serial")
    )

    # Search & filters — junk GET values (status=zzz) fall back to ""
    # instead of echoing back into context and rendering a silently empty register.
    valid_statuses = dict(BarcodeLabel.STATUS_CHOICES)
    valid_kinds = dict(BarcodeLabel.LABEL_KIND_CHOICES)

    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    label_kind = request.GET.get("label_kind", "").strip()
    if label_kind and label_kind not in valid_kinds:
        label_kind = ""
    if label_kind:
        qs = qs.filter(label_kind=label_kind)

    # KPIs across the tenant's full label register — one grouped query, not four COUNTs
    status_counts = {
        row["status"]: row["n"]
        for row in BarcodeLabel.objects.filter(tenant=request.tenant)
        .values("status")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(status_counts.values()),
        "printed": status_counts.get("printed", 0),
        "draft": status_counts.get("draft", 0),
        "void": status_counts.get("void", 0),
    }

    return crud_list(
        request,
        qs,
        "inventory/barcode/barcodelabel/list.html",
        search_fields=["number", "payload", "target_ref", "pallet_ref", "item__sku", "location__code"],
        filters=(),
        extra_context={
            "stats": stats,
            "status_choices": BarcodeLabel.STATUS_CHOICES,
            "status": status,
            "kind_choices": BarcodeLabel.LABEL_KIND_CHOICES,
            "label_kind": label_kind,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def barcodelabel_detail(request, pk):
    """View full label definition."""
    return crud_detail(
        request,
        model=BarcodeLabel,
        pk=pk,
        template="inventory/barcode/barcodelabel/detail.html",
        select_related=("item", "location", "lot_serial", "printed_by"),
        extra_context={
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def barcodelabel_create(request):
    """Register a new barcode label."""
    return crud_create(
        request,
        form_class=BarcodeLabelForm,
        template="inventory/barcode/barcodelabel/form.html",
        success_url="inventory:barcodelabel_list",
    )


@tenant_admin_required
def barcodelabel_edit(request, pk):
    """Edit an existing barcode label."""
    return crud_edit(
        request,
        model=BarcodeLabel,
        pk=pk,
        form_class=BarcodeLabelForm,
        template="inventory/barcode/barcodelabel/form.html",
        success_url="inventory:barcodelabel_list",
    )


@tenant_admin_required
@require_POST
def barcodelabel_delete(request, pk):
    """Delete a barcode label record."""
    return crud_delete(
        request,
        model=BarcodeLabel,
        pk=pk,
        success_url="inventory:barcodelabel_list",
    )


@tenant_admin_required
@require_POST
def barcodelabel_void(request, pk):
    """Pull a label out of circulation — mirrors the RFID tag lifecycle actions."""
    obj = get_object_or_404(
        BarcodeLabel.objects.filter(tenant=request.tenant), pk=pk
    )
    try:
        obj.void()
    except ValidationError as e:
        messages.error(request, "; ".join(e.messages))
        return redirect("inventory:barcodelabel_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "update", {"action": "void"})
    messages.success(request, f"Barcode Label {obj.number} voided.")
    return redirect("inventory:barcodelabel_detail", pk=obj.pk)


@tenant_admin_required
def barcodelabel_print(request, pk):
    """GET renders the printable label copies; POST stamps + flips the label to printed.

    The whole surface is admin-gated: the GET page is a write-surface preview and the POST
    mutates status/printed_at — both belong behind the same gate as every other label write."""
    obj = get_object_or_404(
        BarcodeLabel.objects.filter(tenant=request.tenant)
        .select_related("item", "location", "lot_serial"),
        pk=pk,
    )

    if request.method == "POST":
        try:
            obj.print()
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
            return redirect("inventory:barcodelabel_detail", pk=obj.pk)
        write_audit_log(request.user, obj, "update", {"action": "print"})
        messages.success(request, f"Barcode Label {obj.number} printed ({obj.copies} copies).")
        return redirect("inventory:barcodelabel_detail", pk=obj.pk)

    return render(
        request,
        "inventory/barcode/barcodelabel/print.html",
        {
            "obj": obj,
            "copies_range": range(obj.copies),
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


# WARNING: payload echoes into SVG text nodes — python-barcode/qrcode XML-escape their own
# output, do NOT bypass them by hand-building SVG strings from payload.
@login_required
def barcodelabel_render(request, pk):
    """Render the label's payload inline as an SVG barcode / QR image."""
    obj = get_object_or_404(
        BarcodeLabel.objects.filter(tenant=request.tenant)
        .select_related("item", "location", "lot_serial"),
        pk=pk,
    )
    if obj.status == "void":
        raise Http404("Voided labels are not rendered.")

    buf = BytesIO()

    if obj.symbology == "qr":
        img = qrcode.QRCode(box_size=6, border=2, image_factory=qrcode.image.svg.SvgPathImage)
        img.add_data(obj.payload)
        img.make(fit=True)
        img.make_image().save(buf)
        return HttpResponse(buf.getvalue(), content_type="image/svg+xml")

    name_map = {"code39": "code39", "code128": "code128", "ean13": "ean13"}
    try:
        bc = barcode.get(name_map[obj.symbology], obj.payload, writer=SVGWriter())
        bc.write(buf)
        svg = buf.getvalue()
    # NOTE: KeyError is caught deliberately — python-barcode's Code39 checksums the code
    # BEFORE validating it, so an out-of-alphabet character surfaces as a bare KeyError,
    # not as IllegalCharacterError.
    except (NumberOfDigitsError, BarcodeError, KeyError):
        # CHOSEN FALLBACK: a STATIC SVG error card (not a code128 re-render) — EAN-13 demands a
        # 12/13-digit payload and Code 39 forbids lowercase, so we surface the problem to the
        # operator instead of silently swapping symbologies on the scanner floor. The card text
        # below is static; the payload is never echoed into it.
        buf.write(
            b'<svg xmlns="http://www.w3.org/2000/svg" width="260" height="64">'
            b'<rect width="100%" height="100%" fill="#fef2f2" stroke="#dc2626"/>'
            b'<text x="14" y="28" font-family="monospace" font-size="13" fill="#b91c1c">'
            b'Payload not valid for this symbology</text>'
            b'<text x="14" y="48" font-family="monospace" font-size="12" fill="#7f1d1d">'
            b'(EAN-13 needs 12/13 digits)</text>'
            b"</svg>"
        )
        svg = buf.getvalue()

    return HttpResponse(svg, content_type="image/svg+xml")
