"""POST-payload builders for SCM's real Django inline formsets.

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
