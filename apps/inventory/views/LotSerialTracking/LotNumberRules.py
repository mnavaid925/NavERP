"""Inventory 5.8 Lot & Serial Number Tracking — LotNumberRule views.

CRUD over the numbering patterns plus the one bespoke surface, ``lot_generate``: the
one-click mint that resolves an item's rule and creates the next ``scm.LotSerial``
through the model service. The view owns the HTTP contract only — refusals (no rule,
untracked item, kind mismatch) are the model's ValidationErrors surfaced as flash
messages, never 500s.
"""
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import GenerateLotForm, LotNumberRuleForm
from apps.inventory.models import LotNumberRule
from apps.scm.models import Item, LotSerial


def _scoped(tenant):
    """Tenant-scoped queryset with the join every list/detail page renders."""
    return (LotNumberRule.objects.filter(tenant=tenant)
            .select_related("item"))


def _tracked_items(tenant):
    if tenant is None:
        return Item.objects.none()
    return (Item.objects.filter(tenant=tenant, tracking__in=("lot", "serial"))
            .select_related("uom").order_by("sku"))


@login_required
def lotrule_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/lottrack/lotrule/list.html",
        search_fields=["name", "prefix", "item__sku", "item__name", "notes"],
        filters=[("kind", "kind", False), ("active", "is_active", False)],
        extra_context={
            "kind_choices": LotNumberRule.KIND_CHOICES,
            "tracked_count": _tracked_items(request.tenant).count(),
        },
    )


@login_required
def lotrule_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    # What this rule has actually minted for its item — read off the SPINE's rows
    # (numbers are unique per tenant+item there), newest first.
    recent_lots = LotSerial.objects.none()
    if obj.item_id:
        recent_lots = (LotSerial.objects.filter(tenant=obj.tenant_id, item=obj.item)
                       .order_by("-id")[:10])
    return render(request, "inventory/lottrack/lotrule/detail.html", {
        "obj": obj,
        # A representative next number under this pattern — a preview only, it
        # reserves nothing.
        "sample": obj.sample_number(),
        "recent_lots": recent_lots.select_related("item"),
    })


@login_required
def lotrule_create(request):
    return crud_create(
        request, form_class=LotNumberRuleForm,
        template="inventory/lottrack/lotrule/form.html",
        success_url="inventory:lotrule_list",
    )


@login_required
def lotrule_edit(request, pk):
    return crud_edit(
        request, model=LotNumberRule, pk=pk, form_class=LotNumberRuleForm,
        template="inventory/lottrack/lotrule/form.html",
        success_url="inventory:lotrule_list",
    )


@login_required
@require_POST
def lotrule_delete(request, pk):
    return crud_delete(request, model=LotNumberRule, pk=pk,
                       success_url="inventory:lotrule_list")


@login_required
def lot_generate(request):
    """Mint the next batch number for a tracked item under its resolved rule.

    GET renders the picker with every active rule's live sample; POST runs the model
    service. A missing rule is EXPECTED traffic on a workspace that never set one up,
    so it lands as a flash pointing at the rule list rather than an error page.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before generating numbers.")
        return redirect("dashboard:home")

    rules = (_scoped(request.tenant).filter(is_active=True))
    preview = [(rule, rule.sample_number()) for rule in rules]

    if request.method == "POST":
        form = GenerateLotForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            item = form.cleaned_data["item"]
            rule = LotNumberRule.resolve(request.tenant, item)
            if rule is None:
                messages.error(
                    request,
                    f"No active numbering rule covers {item.sku} — add one (or a "
                    "tenant default) first.")
                return redirect("inventory:lotrule_create")
            try:
                lot = rule.generate(
                    request.user, item,
                    expiry_date=form.cleaned_data.get("expiry_date") or None,
                    notes=form.cleaned_data.get("notes") or "")
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                write_audit_log(request.user, lot, "generate_lot", {"rule": rule.name})
                messages.success(
                    request,
                    f"Generated {lot.number} for {item.sku} via “{rule.name}”.")
                return redirect("scm:lotserial_detail", pk=lot.pk)
    else:
        form = GenerateLotForm(tenant=request.tenant)

    return render(request, "inventory/lottrack/generate.html", {
        "form": form,
        "preview": preview,
        "tracked_count": _tracked_items(request.tenant).count(),
    })
