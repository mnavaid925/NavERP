"""tenants — LicenseAssignment views (0.19, the seat register) + the reclaim verb.

`get_user_model` is imported from `django.contrib.auth` explicitly HERE and nowhere else: it is
needed only by this module, and `views/_common.py` is shared with 0.1/0.6/0.7 where every addition is
a re-read (L43). The rest of the toolkit still comes from `views/_common` — never a second import
path, which is how a decorator order drifts.
"""
from django.contrib.auth import get_user_model

from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    LicenseAssignment,
)
from apps.tenants.forms import (
    LicenseAssignmentForm,
)


def accounts_user_queryset(request):
    """Seat candidates: this tenant's users only.

    `accounts.User.tenant` is NULLABLE (the superuser `admin` has tenant=None by design), so an
    unfiltered queryset would offer the superuser as a seat holder — and every count on the board
    would then disagree with the register. `TenantModelForm` does this scoping for the FORM; the
    list filter and the board read the model, so they do it themselves.
    """
    return get_user_model().objects.filter(tenant=request.tenant).order_by("email")


@tenant_admin_required
def licenseassignment_list(request):
    qs = (LicenseAssignment.objects.filter(tenant=request.tenant)
          .select_related("user", "subscription"))
    return crud_list(
        request, qs, "tenants/licenseassignment/list.html",
        # `notes` is in `search_fields` per contract §3.5 — the model gained the `notes` column under
        # [RULING] 11 (see the note in `forms/LicenseAssignment.py`).
        search_fields=["module_slug", "notes"],
        filters=[("status", "status", False),
                 ("source", "assignment_source", False),
                 ("user", "user_id", True),
                 ("module", "module_slug", False)],
        extra_context={
            "status_choices": LicenseAssignment.STATUS_CHOICES,
            "source_choices": LicenseAssignment.SOURCE_CHOICES,
            "user_choices": accounts_user_queryset(request),
            # A ValuesListQuerySet, NOT a list of objects: `module_slug` is a plain CharField, so
            # there is no object to render — `{% for slug in module_choices %}<option value="{{ slug }}">`
            # is the shape. DERIVED FROM THE ROWS THAT EXIST rather than from
            # `core.ModuleAccessScope`, so the dropdown can never offer a module nobody holds a seat
            # in. Pointing it at ModuleAccessScope would be the longer list, but that couples a seat
            # filter to a table owned by 0.6, and the research explicitly declines a second
            # per-module switch.
            "module_choices": LicenseAssignment.objects
                                   .filter(tenant=request.tenant)
                                   .exclude(module_slug="")
                                   .values_list("module_slug", flat=True)
                                   .distinct().order_by("module_slug"),
        },
    )


@tenant_admin_required
def licenseassignment_create(request):
    return crud_create(request, form_class=LicenseAssignmentForm,
                       template="tenants/licenseassignment/form.html",
                       success_url="tenants:licenseassignment_list")


@tenant_admin_required
def licenseassignment_detail(request, pk):
    # I9: `select_related("user", "subscription")` because the template walks BOTH FKs - the
    # Holder row renders `obj.user` and the subscription row renders `obj.subscription.pk` and
    # `obj.subscription.get_plan_display` inside an {% if %} branch. The list view already does
    # this; the detail view did not, so it ran 5 queries where 2 suffice.
    # `subscription` is NULLABLE, so this is a LEFT OUTER JOIN and costs nothing extra.
    obj = get_object_or_404(
        LicenseAssignment.objects.select_related("user", "subscription"),
        pk=pk, tenant=request.tenant,
    )
    # The board's seat roll-up for THIS tenant - a real roll-up off grouped queries, not a
    # tautological total. Reused from `Boards` rather than re-queried here (read the PRODUCER of the
    # rows, not the view that forwards them). I5 narrowed it to `user__tenant` on ONE queryset,
    # which also took it from three queries to two.
    from apps.tenants.views.Boards import _seat_summary
    # ONE fetch, then render — the `usagerecord_detail` house pattern, not `crud_detail` (which
    # re-fetches the row by pk, costing a second query for one page).
    return render(
        request, "tenants/licenseassignment/detail.html",
        {"obj": obj, "seat_summary": _seat_summary(request.tenant)},
    )


@tenant_admin_required
def licenseassignment_edit(request, pk):
    """A NON-ACTIVE seat cannot be edited, and the VIEW enforces it — not the template.

    I6: the detail template hides Edit for a non-active seat, but hiding a button does not stop
    a direct POST to this URL, and a seat's `status` is the SOLE writer's field
    (`licenseassignment_reclaim`). Editing a reclaimed seat would rewrite its `module_slug`,
    `notes` or `subscription` after the fact — the audit trail would show a reclaimed seat whose
    commercial terms were edited afterwards, which is precisely what the one-writer discipline
    exists to prevent.

    The guard runs on BOTH methods, and before `crud_edit` fetches anything, so a GET on a
    non-active seat is refused the same way a POST is. It redirects rather than 403s: the caller
    is a tenant admin who followed a stale link, not an attacker, and the detail page states
    why the seat is frozen.
    """
    obj = get_object_or_404(LicenseAssignment, pk=pk, tenant=request.tenant)
    if not obj.is_reclaimable:
        messages.info(request, "That seat is not active, so it cannot be edited.")
        return redirect("tenants:licenseassignment_detail", pk=obj.pk)
    return crud_edit(request, model=LicenseAssignment, pk=pk, form_class=LicenseAssignmentForm,
                     template="tenants/licenseassignment/form.html",
                     success_url="tenants:licenseassignment_list")



@require_POST
@tenant_admin_required
def licenseassignment_delete(request, pk):
    """`require_POST` OUTSIDE the role gate — 405 for a wrong method regardless of role. See
    `entitlementfeature_delete` for the full decorator-order rationale."""
    return crud_delete(request, model=LicenseAssignment, pk=pk,
                       success_url="tenants:licenseassignment_list")


@require_POST
@tenant_admin_required
def licenseassignment_reclaim(request, pk):
    """The SOLE writer of `status`, `reclaimed_on` and `reclaim_reason` ([RULING] 5).

    All three are off `LicenseAssignmentForm`, and this is the only code in the repository permitted
    to write them. A seat is created `active` (the model default); its status changes only here.

    This does NOT disable anybody's login. Seat auto-deprovisioning is decline #3 of the ten — there
    is no identity sync in NavERP, so reclaiming a seat records a commercial fact and nothing more.
    """
    obj = get_object_or_404(LicenseAssignment, pk=pk, tenant=request.tenant)
    # Idempotence guard, the `usagerecord_mark_billed` shape: without it a double-click stamps two
    # different `reclaimed_on` values.
    if obj.status != "active":
        messages.info(request, "That seat is not active.")
        return redirect("tenants:licenseassignment_detail", pk=obj.pk)

    obj.status = "reclaimed"
    obj.reclaimed_on = timezone.now()
    # The reason belongs to the ACT, so it is read from the POST here and never from the form.
    obj.reclaim_reason = request.POST.get("reason", "")[:200]
    # `update_fields` is mandatory: it makes the verb's write surface auditable by reading the code.
    obj.save(update_fields=["status", "reclaimed_on", "reclaim_reason"])
    # AuditLog.action is varchar(10), so the 28-char verb CANNOT go in `action` — it goes in
    # `changes` (L41).
    write_audit_log(request.user, obj, "update", changes={
        "verb": "licenseassignment_reclaim",
        "status": "reclaimed",
        "reclaim_reason": obj.reclaim_reason,
    })
    messages.success(request, "Seat reclaimed.")
    # The detail page, not the list, so the operator sees the stamped evidence they just created.
    return redirect("tenants:licenseassignment_detail", pk=obj.pk)
