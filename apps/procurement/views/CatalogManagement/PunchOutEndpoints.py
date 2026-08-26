"""Procurement 6.9 Catalog Management — PunchOutEndpoint views.

The endpoint register (search + protocol/enabled filters + one-aggregate stats), the detail
page that shows the shared secret as a fixed placeholder — NEVER its value — a hand-rolled
form handler whose EDIT path controls exactly what reaches the audit trail, and the POST-only
"test" verb that records the session attempt without executing any handshake.
"""
from django.db.models import Count, Q

from apps.core.crud import crud_delete, crud_list
from apps.procurement.forms.CatalogManagement.PunchOutEndpoints import PunchOutEndpointForm
from apps.procurement.models.CatalogManagement.PunchOutEndpoints import PunchOutEndpoint
from apps.procurement.views._common import *  # noqa: F401,F403


def _redacted_changes(form):
    """``{field: new_value}`` of changed fields for the audit trail.

    Same shape as ``apps.core.crud._changed()``, but ``shared_secret`` is SKIPPED entirely
    rather than redacted to a placeholder: core's ``_SENSITIVE_AUDIT_FIELDS`` does not list
    this field name, and since the demo column stores plaintext verbatim no trace of it may
    reach the immutable AuditLog — not even as a marker string. (Belt-and-braces: the edit
    form pops the field, so it cannot appear in ``changed_data`` anyway.)
    """
    out = {}
    for name in getattr(form, "changed_data", []):
        if name == "shared_secret":
            continue
        out[name] = str(form.cleaned_data.get(name))[:200]
    return out


# -- register + detail -----------------------------------------------------------------------------


@login_required
def punchout_endpoint_list(request):
    qs = (PunchOutEndpoint.objects.filter(tenant=request.tenant)
          .select_related("party"))
    return crud_list(
        request, qs, "procurement/catalogmanagement/punchoutendpoint/list.html",
        search_fields=["name", "party__name", "punchout_url"],
        filters=[("protocol", "protocol", False), ("enabled", "enabled", False)],
        extra_context={
            "protocol_choices": PunchOutEndpoint.PROTOCOL_CHOICES,
            # ONE aggregate query for all three figures.
            "stats": PunchOutEndpoint.objects.filter(tenant=request.tenant).aggregate(
                total=Count("id"),
                enabled=Count("id", filter=Q(enabled=True)),
                cxml=Count("id", filter=Q(protocol="cxml")),
            ),
        },
    )


@login_required
def punchout_endpoint_detail(request, pk):
    obj = get_object_or_404(PunchOutEndpoint.objects.select_related("party"),
                            pk=pk, tenant=request.tenant)
    return render(request, "procurement/catalogmanagement/punchoutendpoint/detail.html",
                  {"obj": obj})


# -- create / edit ---------------------------------------------------------------------------------


@login_required
def punchout_endpoint_create(request):
    return _endpoint_form(request, instance=None)


@login_required
def punchout_endpoint_edit(request, pk):
    obj = get_object_or_404(PunchOutEndpoint, pk=pk, tenant=request.tenant)
    return _endpoint_form(request, instance=obj)


def _endpoint_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating endpoints.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = PunchOutEndpointForm(request.POST, request.FILES, instance=instance,
                                    tenant=request.tenant)
        if form.is_valid():
            endpoint = form.save(commit=False)
            endpoint.tenant = request.tenant
            endpoint.save()
            if is_edit:
                # Manual logging instead of crud_edit so THIS code decides what lands in the
                # audit trail: changed fields with the write-only secret excluded outright.
                write_audit_log(request.user, endpoint, "update",
                                changes=_redacted_changes(form))
            else:
                write_audit_log(request.user, endpoint, "create")
            messages.success(request,
                             f"Endpoint {endpoint.number or endpoint.name} saved.")
            return redirect("procurement:punchout_endpoint_detail", pk=endpoint.pk)
    else:
        form = PunchOutEndpointForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/catalogmanagement/punchoutendpoint/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def punchout_endpoint_delete(request, pk):
    return crud_delete(request, model=PunchOutEndpoint, pk=pk,
                       success_url="procurement:punchout_endpoint_list")


# -- actions ---------------------------------------------------------------------------------------


@login_required
@require_POST
def punchout_endpoint_test(request, pk):
    """"Test connection" records the attempt only — executing a real cXML/OCI handshake is
    deferred; the stamp is evidence of intent, not proof of connectivity."""
    obj = get_object_or_404(PunchOutEndpoint, pk=pk, tenant=request.tenant)
    obj.record_session()
    write_audit_log(request.user, obj, "test")
    messages.success(request, "Handshake execution is deferred; session timestamp recorded.")
    return redirect("procurement:punchout_endpoint_detail", pk=obj.pk)
