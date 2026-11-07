import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.bi.forms.EmbeddedMobileBi.KioskWallboardDisplays import KioskWallboardDisplayForm
from apps.bi.models.EmbeddedMobileBi.KioskWallboardDisplays import KioskWallboardDisplay
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def kiosk_wallboard_display_list(request):
    qs = bi_scope(KioskWallboardDisplay.objects.all(), request).select_related("created_by")

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        dark=Count("id", filter=Q(theme__in=["dark_oled", "dark_navy"])),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    dark_count = counts["dark"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(kiosk_slug__icontains=q)
            | Q(location_description__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    theme = request.GET.get("theme", "").strip()
    if theme:
        qs = qs.filter(theme=theme)

    display_schedule = request.GET.get("schedule", "").strip()
    if display_schedule:
        qs = qs.filter(display_schedule=display_schedule)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "displays": page_obj,
        "kiosk_wallboard_displays": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "dark_count": dark_count,
        "status_choices": KioskWallboardDisplay.STATUS_CHOICES,
        "theme_choices": KioskWallboardDisplay.WALLBOARD_THEME_CHOICES,
        "schedule_choices": KioskWallboardDisplay.DISPLAY_SCHEDULE_CHOICES,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/kioskwallboarddisplay/list.html",
        context,
    )


@login_required
@tenant_admin_required
def kiosk_wallboard_display_create(request):
    if request.method == "POST":
        form = KioskWallboardDisplayForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                display = form.save(commit=False)
                display.tenant = request.tenant
                display.created_by = request.user
                display.save()
                write_audit_log(
                    request,
                    action="CREATE",
                    instance=display,
                    description=f"Created kiosk wallboard display {display.number} ({display.name})",
                )
            messages.success(request, f"Display '{display.name}' created successfully.")
            return redirect("bi:kiosk_wallboard_display_detail", pk=display.pk)
    else:
        form = KioskWallboardDisplayForm(tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/kioskwallboarddisplay/form.html",
        {"form": form, "title": "New Kiosk & Wallboard Display"},
    )


@login_required
def kiosk_wallboard_display_detail(request, pk):
    display = bi_object(
        request,
        KioskWallboardDisplay,
        pk,
        select_related=("created_by",),
    )

    playlist_items = display.playlist_items if isinstance(display.playlist_items, list) else []
    operating_hours = display.operating_hours_json if isinstance(display.operating_hours_json, dict) else {}

    context = {
        "display": display,
        "playlist_items": playlist_items,
        "operating_hours": operating_hours,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/kioskwallboarddisplay/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def kiosk_wallboard_display_edit(request, pk):
    display = bi_object(request, KioskWallboardDisplay, pk)

    if request.method == "POST":
        form = KioskWallboardDisplayForm(request.POST, instance=display, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                display = form.save()
                write_audit_log(
                    request,
                    action="UPDATE",
                    instance=display,
                    description=f"Updated kiosk wallboard display {display.number}",
                )
            messages.success(request, f"Display '{display.name}' updated successfully.")
            return redirect("bi:kiosk_wallboard_display_detail", pk=display.pk)
    else:
        form = KioskWallboardDisplayForm(instance=display, tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/kioskwallboarddisplay/form.html",
        {"form": form, "display": display, "title": f"Edit {display.name}"},
    )


@login_required
@tenant_admin_required
@require_POST
def kiosk_wallboard_display_delete(request, pk):
    display = bi_object(request, KioskWallboardDisplay, pk)
    with transaction.atomic():
        write_audit_log(
            request,
            action="DELETE",
            instance=display,
            description=f"Deleted kiosk wallboard display {display.number}",
        )
        display.delete()
    messages.success(request, "Display deleted.")
    return redirect("bi:kiosk_wallboard_display_list")


def kiosk_wallboard_display_player(request, pk):
    # Allow authenticated tenant users or public access if configured
    if request.user.is_authenticated and hasattr(request, "tenant") and request.tenant:
        display = bi_object(request, KioskWallboardDisplay, pk)
    else:
        # Public kiosk mode check
        passcode = request.GET.get("passcode", "").strip()
        try:
            display = KioskWallboardDisplay.objects.get(pk=pk, is_public_kiosk=True)
            if display.access_passcode and display.access_passcode != passcode:
                raise Http404("Invalid kiosk passcode.")
        except KioskWallboardDisplay.DoesNotExist:
            raise Http404("Kiosk display not found or public access disabled.")

    playlist_items = display.playlist_items if isinstance(display.playlist_items, list) else []
    if not playlist_items:
        # Default fallback slide
        playlist_items = [
            {
                "type": "dashboard",
                "title": display.name,
                "duration_seconds": display.default_slide_duration_seconds,
            }
        ]

    context = {
        "display": display,
        "playlist_items": playlist_items,
        "playlist_json": json.dumps(playlist_items),
    }
    return render(
        request,
        "bi/embedded_mobile_bi/kioskwallboarddisplay/player.html",
        context,
    )


@csrf_exempt
def kiosk_wallboard_display_heartbeat(request, pk):
    # Public or internal heartbeat endpoint
    try:
        display = KioskWallboardDisplay.objects.get(pk=pk)
    except KioskWallboardDisplay.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Display not found"}, status=404)

    ip_address = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()

    user_agent = request.META.get("HTTP_USER_AGENT", "")
    display.record_heartbeat(ip_address=ip_address, user_agent=user_agent)

    return JsonResponse(
        {
            "status": "ok",
            "display_number": display.number,
            "last_heartbeat_at": display.last_heartbeat_at.isoformat() if display.last_heartbeat_at else None,
        }
    )
