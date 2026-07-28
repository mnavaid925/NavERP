"""POST-payload builders for SCM's real Django inline formsets, plus calendar helpers.

SCM 4.1 is the first NavERP app whose test suite drives ``BaseInlineFormSet``
subclasses through both direct instantiation and the Django test client, so the
management-form boilerplate is centralized here rather than duplicated per test.

Every line child (``PurchaseRequisitionLine``, ``PurchaseOrderLine``, ``RFQLine``,
``RFQQuoteLine``, ``GoodsReceiptLine``) declares ``related_name="lines"`` on its FK to
its parent, and ``BaseInlineFormSet.get_default_prefix()`` returns that related name —
so every one of those formsets defaults to the prefix ``"lines"``. The RFQ form view is
the one place that also carries a second, sibling formset (``RFQVendorFormSet``, whose
related_name is ``invited_vendors``) and gives both formsets EXPLICIT prefixes
(``"lines"`` and ``"vendors"``) so they don't collide in the same POST body.
"""


def management_form(prefix, total, initial=0, min_num=0, max_num=1000):
    """The 4 hidden ``<prefix>-*`` management fields every Django formset POST needs."""
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": str(min_num),
        f"{prefix}-MAX_NUM_FORMS": str(max_num),
    }


def formset_data(prefix, rows, initial=0):
    """Build a flat ``{"<prefix>-0-field": value, ...}`` POST dict for a formset.

    ``rows`` is a list of ``{field: value}`` dicts, one per form. ``None`` values are
    sent as empty strings (Django's usual "field left blank" wire format). Pass a row's
    own ``id`` key to bind it to an existing instance (inline formsets key existing rows
    by the child model's pk field, always named ``id`` here).
    """
    data = management_form(prefix, total=len(rows), initial=initial)
    for i, row in enumerate(rows):
        for field, value in row.items():
            data[f"{prefix}-{i}-{field}"] = "" if value is None else str(value)
    return data


# --------------------------------------------------------------------------------- calendar
# SCM 4.7 Demand Planning buckets a horizon by month, so its fixtures and tests need month
# arithmetic. Lesson L16: EVERY reference date here is derived from the caller's
# ``timezone.localdate()`` basis (the same basis ``generate_periods`` / ``detect_order_surge`` /
# ``expire_stale_signals`` use), NEVER ``datetime.date.today()`` — otherwise exact-date assertions
# flake for the hours around local midnight.
def month_start(value):
    """First day of ``value``'s month."""
    import datetime
    return datetime.date(value.year, value.month, 1)


def add_months(value, months):
    """First day of the month ``months`` after ``value``'s month (negative goes back)."""
    import datetime
    total = value.year * 12 + (value.month - 1) + int(months)
    year, month = divmod(total, 12)
    return datetime.date(year, month + 1, 1)


# --------------------------------------------------------------------------------- stock ledger
def seed_stock(tenant, item, location, quantity, unit_cost, reference="OPENING"):
    """Give an item real on-hand at a location by posting an inbound ``receipt`` StockMove.

    Goes through the module's own posting service rather than ``StockMove.objects.create`` so the
    item's cached ``average_cost`` is rolled forward exactly as production would — 4.8's component
    issue prices at ``average_cost or standard_cost``, so a hand-written ledger row would leave the
    two disagreeing and every costing assertion measuring the wrong thing.
    """
    from decimal import Decimal
    from apps.scm.views._helpers import _post_stock_move
    return _post_stock_move(tenant, item=item, location=location, quantity=Decimal(str(quantity)),
                            move_type="receipt", unit_cost=Decimal(str(unit_cost)),
                            reference=reference, reason="Opening balance")
