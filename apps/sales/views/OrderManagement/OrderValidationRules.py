"""Sales 8.6 — CRUD views for the typed order-validation rule set.

Deliberately thin. ``OrderValidationRule.evaluate()`` does the thinking on the model and these
views do the four ordinary jobs around it: tenant-scope the queryset, read the filters BEFORE
paginating, pass every context key the templates read, and write the audit row.

Three rules govern every view here:

* **Tenant scope, always.** ``filter(tenant=request.tenant)``, never ``.objects.all()``. The
  tenantless superuser (``request.tenant is None``) therefore sees empty lists BY DESIGN.
* **Junk in, ignored out (L11).** ``?rule_type=nonsense`` narrows nothing rather than raising,
  and ``?party=`` goes through ``as_db_int`` so a 40-digit value is skipped instead of
  overflowing the driver. A filter that filters nothing is a much better failure than a 500 on
  a URL somebody typed into the address bar.
* **Audit on every mutation.** ``write_audit_log`` is POSITIONAL — ``(user, obj, action,
  changes, tenant)`` — and the instance is the SECOND argument. Transposing it raises on every
  POST, so it is spelled out the same way in all three write paths.

``evaluate`` is never called from here. Showing what a rule WOULD do to an order is the
validation board's job (8.6's ``order_validate``), and that board belongs to the entity that
owns the holds — this file must not grow a second opinion about whether an order passes.
"""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.sales.forms.OrderManagement.OrderValidationRules import OrderValidationRuleForm
from apps.sales.models.OrderManagement.OrderValidationRules import OrderValidationRule
from apps.sales.views._common import *  # noqa: F401,F403  (login_required, get_object_or_404, ...)


LIST_TEMPLATE = "sales/ordermanagement/ordervalidationrule/list.html"
DETAIL_TEMPLATE = "sales/ordermanagement/ordervalidationrule/detail.html"
FORM_TEMPLATE = "sales/ordermanagement/ordervalidationrule/form.html"

#: Rows per page. Matches the shared pagination partial's expectation of ``page_obj``.
PAGE_SIZE = 15

#: The ``?is_active=`` chip. Any value outside this set is ignored (L11) rather than treated
#: as False, which would silently hide every rule in the register.
IS_ACTIVE_CHOICES = (("true", "Active Only"), ("false", "Inactive Only"))


def _rule_queryset(request):
    """The tenant-scoped rule register. One place, so no view can forget the filter."""
    return OrderValidationRule.objects.filter(tenant=request.tenant).select_related("party")


def _recent_orders(request, rule):
    """The 10 most recent orders this rule would be evaluated against.

    For a customer-scoped rule that is the customer's own orders; for a blank (workspace-wide)
    rule it is the tenant's most recent orders, which is the honest answer — there is no
    narrower set. Read-only: 8.6 never writes an ``scm.SalesOrder`` here.
    """
    from apps.scm.models import SalesOrder

    orders = SalesOrder.objects.filter(tenant=request.tenant).select_related("customer")
    if rule.party_id:
        orders = orders.filter(customer_id=rule.party_id)
    return orders[:10]


def _raised_holds_page(request, rule):
    """The holds this rule has raised, newest first, as a Page of 15.

    Resolved through the reverse accessor rather than by naming ``OrderHold``, so this module
    compiles and runs while that model is still being built in the same sub-module. A rule
    whose reverse relation is not registered yet gets an empty Page, which renders the same
    "none raised" state a rule that genuinely has raised none already shows.
    """
    holds = getattr(rule, "raised_holds", None)
    queryset = holds.select_related("sales_order") if hasattr(holds, "select_related") else []
    return paginate(request, queryset, PAGE_SIZE)


@login_required
@tenant_admin_required
def order_validation_rule_list(request):
    """The rule register: search, five filters, a stats strip and an Actions column."""
    base_queryset = OrderValidationRule.objects.filter(tenant=request.tenant)
    queryset = _rule_queryset(request)

    q = request.GET.get("q", "").strip()[:200]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q) | Q(number__icontains=q) | Q(description__icontains=q)
        )

    # Each choice filter is checked against the ALLOWED VALUES before it filters. An unknown
    # value narrows nothing and is echoed back blank, so the dropdown and the result set can
    # never disagree — the L11 "junk ignored, not 500" rule, applied to a choice column.
    rule_type = request.GET.get("rule_type", "").strip()
    if rule_type in dict(OrderValidationRule.RULE_TYPE_CHOICES):
        queryset = queryset.filter(rule_type=rule_type)
    else:
        rule_type = ""

    severity = request.GET.get("severity", "").strip()
    if severity in dict(OrderValidationRule.SEVERITY_CHOICES):
        queryset = queryset.filter(severity=severity)
    else:
        severity = ""

    active_on = request.GET.get("active_on", "").strip()
    if active_on in dict(OrderValidationRule.ACTIVE_ON_CHOICES):
        queryset = queryset.filter(active_on=active_on)
    else:
        active_on = ""

    # A FK filter is trusted only after as_db_int: ``?party=abc``, ``?party=²`` and a
    # 40-digit value are all skipped rather than raised on. Zero is skipped too — it is not a
    # pk, and filtering on it would return an empty page that reads as "this workspace has no
    # rules", which is a lie.
    party_filter = request.GET.get("party", "").strip()
    party_pk = as_db_int(party_filter)
    if party_pk:
        queryset = queryset.filter(party_id=party_pk)
    else:
        party_filter = ""

    is_active = request.GET.get("is_active", "").strip().lower()
    if is_active == "true":
        queryset = queryset.filter(is_active=True)
    elif is_active == "false":
        queryset = queryset.filter(is_active=False)
    else:
        is_active = ""

    # Filters are read BEFORE pagination, so the page count reflects what is on screen.
    page_obj = paginate(request, queryset, PAGE_SIZE)

    # Stats describe the WHOLE tenant register, not the filtered page — a stats strip that
    # changes when you search is a stats strip nobody trusts. Counts, one grouped query.
    by_type = {
        row["rule_type"]: row["n"]
        for row in base_queryset.values("rule_type").annotate(n=Count("id"))
    }
    stats = base_queryset.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        blocking=Count(
            "id",
            filter=Q(is_active=True, severity__in=OrderValidationRule.BLOCKING_SEVERITIES),
        ),
    )
    stats["by_type"] = by_type

    return render(request, LIST_TEMPLATE, {
        "rules": page_obj,
        # The shared pagination partial reads ``page_obj``; it is an ALIAS of the very same
        # Page, never a second paginator run over the same queryset.
        "page_obj": page_obj,
        "q": q,
        "rule_type": rule_type,
        "severity": severity,
        "active_on": active_on,
        "party": party_filter,
        "is_active": is_active,
        "rule_type_choices": OrderValidationRule.RULE_TYPE_CHOICES,
        "severity_choices": OrderValidationRule.SEVERITY_CHOICES,
        "active_on_choices": OrderValidationRule.ACTIVE_ON_CHOICES,
        "is_active_choices": IS_ACTIVE_CHOICES,
        "parties": Party.objects.filter(tenant=request.tenant).order_by("name"),
        "stats": stats,
    })


def _form_context(form, is_edit, obj=None):
    """The form view's context. ``obj`` is the edit-mode object var on BOTH create and edit —
    ``None`` on create — so the shared form template never has to branch on which one it got."""
    return {"form": form, "obj": obj, "is_edit": is_edit}


@login_required
@tenant_admin_required
def order_validation_rule_create(request):
    if request.method == "POST":
        form = OrderValidationRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request.user,
                rule,
                "create",
                {
                    "action": "create_order_validation_rule",
                    "number": rule.number,
                    "name": rule.name,
                    "rule_type": rule.rule_type,
                    "severity": rule.severity,
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Validation rule {rule.number} created.")
            return redirect("sales:order_validation_rule_detail", pk=rule.pk)
    else:
        form = OrderValidationRuleForm(tenant=request.tenant)
    return render(request, FORM_TEMPLATE, _form_context(form, False, None))


@login_required
@tenant_admin_required
def order_validation_rule_detail(request, pk):
    rule = get_object_or_404(_rule_queryset(request), pk=pk)
    page_obj = _raised_holds_page(request, rule)
    return render(request, DETAIL_TEMPLATE, {
        "rule": rule,
        "raised_holds": page_obj,
        # ALIAS of the raised-holds Page for the shared pagination partial. On this page that
        # is the only paginated collection, so the two cannot drift apart.
        "page_obj": page_obj,
        "recent_orders": _recent_orders(request, rule),
    })


@login_required
@tenant_admin_required
def order_validation_rule_edit(request, pk):
    rule = get_object_or_404(_rule_queryset(request), pk=pk)
    if request.method == "POST":
        form = OrderValidationRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request.user,
                rule,
                "update",
                {
                    "action": "update_order_validation_rule",
                    "number": rule.number,
                    "name": rule.name,
                    "rule_type": rule.rule_type,
                    "severity": rule.severity,
                    "is_active": rule.is_active,
                    "changed": sorted(form.changed_data),
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Validation rule {rule.number} updated.")
            return redirect("sales:order_validation_rule_detail", pk=rule.pk)
    else:
        form = OrderValidationRuleForm(instance=rule, tenant=request.tenant)
    return render(request, FORM_TEMPLATE, _form_context(form, True, rule))


@require_POST
@login_required
@tenant_admin_required
def order_validation_rule_delete(request, pk):
    rule = get_object_or_404(_rule_queryset(request), pk=pk)
    # The number is captured BEFORE the row goes, because after ``delete()`` there is no pk
    # left to stamp the audit row with.
    number = rule.number
    write_audit_log(
        request.user,
        rule,
        "delete",
        {"action": "delete_order_validation_rule", "number": number, "name": rule.name},
        tenant=request.tenant,
    )
    rule.delete()
    messages.success(request, f"Validation rule {number} deleted.")
    return redirect("sales:order_validation_rule_list")
