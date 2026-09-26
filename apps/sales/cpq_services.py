"""CPQ calculation, approval evaluation, revision cloning, and order conversion services."""
import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError


def _dec(val, places=2):
    """Quantize to decimal places."""
    if val is None:
        val = Decimal("0")
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    pattern = Decimal("0." + "0" * places) if places > 0 else Decimal("1")
    return val.quantize(pattern, rounding=ROUND_HALF_UP)


def cpq_recalc_quote_totals(quote, save=True):
    """Recompute all quote line metrics and aggregate quote header totals.
    
    Excludes non-selected optional add-ons from pricing.
    Applies header discount factor across subtotal and tax.
    Syncs total to primary Opportunity if is_primary is set.
    """
    lines = list(quote.lines.select_related("product", "item", "tax_code").all())
    
    subtotal_sum = Decimal("0")
    tax_sum = Decimal("0")
    cost_sum = Decimal("0")
    
    for line in lines:
        qty = Decimal(str(line.quantity or 0))
        list_price = Decimal(str(line.list_price or 0))
        discount_pct = Decimal(str(line.discount_pct or 0))
        unit_cost = Decimal(str(line.unit_cost or 0))
        tax_pct = Decimal(str(line.tax_pct or 0))
        
        # Calculate unit_price if discount_pct > 0 and unit_price matches list_price or 0
        if discount_pct > 0 and (line.unit_price == list_price or line.unit_price == 0):
            line.unit_price = _dec(list_price * (Decimal("100") - discount_pct) / Decimal("100"))
        elif line.unit_price == 0 and list_price > 0 and discount_pct == 0:
            line.unit_price = list_price
            
        unit_price = Decimal(str(line.unit_price or 0))
        
        # Line subtotal before header discount
        line_subtotal = _dec(qty * unit_price)
        line_tax = _dec(line_subtotal * tax_pct / Decimal("100"))
        line_cost = _dec(qty * unit_cost)
        line_total = line_subtotal + line_tax
        line_margin = line_subtotal - line_cost
        margin_pct = _dec((line_margin / line_subtotal * Decimal("100")) if line_subtotal > Decimal("0") else Decimal("0"))
        
        line.line_subtotal = line_subtotal
        line.line_tax = line_tax
        line.line_total = line_total
        line.line_cost = line_cost
        line.line_margin = line_margin
        line.margin_pct = margin_pct
        
        if save:
            line.save(update_fields=[
                "unit_price", "line_subtotal", "line_tax", "line_total",
                "line_cost", "line_margin", "margin_pct", "updated_at"
            ])
            
        # Only include selected items in quote header totals
        if not (line.is_optional and not line.is_selected):
            subtotal_sum += line_subtotal
            tax_sum += line_tax
            cost_sum += line_cost

    # Apply header discount factor
    header_disc_pct = Decimal(str(quote.header_discount_pct or 0))
    disc_factor = (Decimal("100") - header_disc_pct) / Decimal("100")
    
    quote.subtotal = _dec(subtotal_sum)
    quote.discount_total = _dec(subtotal_sum * header_disc_pct / Decimal("100"))
    discounted_subtotal = quote.subtotal - quote.discount_total
    
    quote.tax_total = _dec(tax_sum * disc_factor)
    quote.total = _dec(discounted_subtotal + quote.tax_total)
    quote.cost_total = _dec(cost_sum)
    quote.margin_total = _dec(discounted_subtotal - quote.cost_total)
    quote.margin_pct = _dec((quote.margin_total / discounted_subtotal * Decimal("100")) if discounted_subtotal > Decimal("0") else Decimal("0"))
    
    if save:
        quote.save(update_fields=[
            "subtotal", "discount_total", "tax_total", "total",
            "cost_total", "margin_total", "margin_pct", "updated_at"
        ])
        
    # Sync primary quote to Opportunity if configured
    if quote.is_primary and quote.opportunity_id:
        opp = quote.opportunity
        opp.amount = quote.total
        if quote.currency_id:
            opp.currency = quote.currency
        opp.save(update_fields=["amount", "currency", "updated_at"])
        
    return quote


def cpq_evaluate_approval(quote):
    """Evaluate active QuoteApprovalRules against the given quote.
    
    Returns:
        (requires_approval: bool, matched_rule: QuoteApprovalRule or None, reason: str)
    """
    from apps.sales.models.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule
    
    rules = QuoteApprovalRule.objects.filter(tenant=quote.tenant, is_active=True).order_by("priority", "id")
    
    # Recalculate first to ensure fresh margins and discounts
    cpq_recalc_quote_totals(quote, save=True)
    
    for rule in rules:
        triggered, reason = rule.evaluate(quote)
        if triggered:
            return True, rule, reason
            
    return False, None, "Within standard pricing thresholds"


@transaction.atomic
def cpq_create_revision(quote, user=None):
    """Create a new version/revision of a CPQQuote.
    
    Marks the current quote as 'superseded'.
    Increments revision_number, maintains quote_group_id, clones all lines.
    """
    from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
    from apps.sales.models.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine
    
    old_status = quote.status
    if quote.status not in ["converted"]:
        quote.status = "superseded"
        quote.save(update_fields=["status", "updated_at"])
        
    new_quote = CPQQuote.objects.create(
        tenant=quote.tenant,
        name=f"{quote.name} (Rev {quote.revision_number + 1})",
        opportunity=quote.opportunity,
        account=quote.account,
        contact=quote.contact,
        price_book=quote.price_book,
        currency=quote.currency,
        status="draft",
        approval_status="not_required",
        valid_until=quote.valid_until,
        quote_group_id=quote.quote_group_id,
        revision_number=quote.revision_number + 1,
        revision_of=quote,
        is_primary=quote.is_primary,
        header_discount_pct=quote.header_discount_pct,
        proposal_template=quote.proposal_template,
        terms_and_conditions=quote.terms_and_conditions,
        notes=quote.notes,
        owner=user or quote.owner,
    )
    
    # If new quote is primary, set old quote is_primary to False
    if new_quote.is_primary:
        CPQQuote.objects.filter(
            tenant=quote.tenant,
            quote_group_id=quote.quote_group_id,
            is_primary=True
        ).exclude(pk=new_quote.pk).update(is_primary=False)
        
    # Map old lines to new lines to preserve hierarchy
    old_to_new_line = {}
    
    # 1. Clone parent/standalone lines first
    parents = quote.lines.filter(parent_line__isnull=True).order_by("sequence", "id")
    for parent in parents:
        new_parent = CPQQuoteLine.objects.create(
            tenant=new_quote.tenant,
            quote=new_quote,
            parent_line=None,
            line_type=parent.line_type,
            product=parent.product,
            item=parent.item,
            uom=parent.uom,
            description=parent.description,
            quantity=parent.quantity,
            list_price=parent.list_price,
            discount_pct=parent.discount_pct,
            unit_price=parent.unit_price,
            tax_code=parent.tax_code,
            tax_pct=parent.tax_pct,
            unit_cost=parent.unit_cost,
            is_optional=parent.is_optional,
            is_selected=parent.is_selected,
            sequence=parent.sequence,
        )
        old_to_new_line[parent.id] = new_parent

    # 2. Clone child components
    children = quote.lines.filter(parent_line__isnull=False).order_by("sequence", "id")
    for child in children:
        parent_mapped = old_to_new_line.get(child.parent_line_id)
        new_child = CPQQuoteLine.objects.create(
            tenant=new_quote.tenant,
            quote=new_quote,
            parent_line=parent_mapped,
            line_type=child.line_type,
            product=child.product,
            item=child.item,
            uom=child.uom,
            description=child.description,
            quantity=child.quantity,
            list_price=child.list_price,
            discount_pct=child.discount_pct,
            unit_price=child.unit_price,
            tax_code=child.tax_code,
            tax_pct=child.tax_pct,
            unit_cost=child.unit_cost,
            is_optional=child.is_optional,
            is_selected=child.is_selected,
            sequence=child.sequence,
        )
        old_to_new_line[child.id] = new_child

    cpq_recalc_quote_totals(new_quote, save=True)
    return new_quote


def cpq_compare_quote_versions(quote_a, quote_b):
    """Compare two revisions of a quote family side-by-side.
    
    Returns a dict with header deltas and line comparisons.
    """
    subtotal_delta = quote_b.subtotal - quote_a.subtotal
    total_delta = quote_b.total - quote_a.total
    margin_delta = quote_b.margin_pct - quote_a.margin_pct
    
    # Map lines by description/product for diffing
    lines_a = {ln.description: ln for ln in quote_a.lines.all()}
    lines_b = {ln.description: ln for ln in quote_b.lines.all()}
    
    all_keys = sorted(set(lines_a.keys()).union(lines_b.keys()))
    line_diffs = []
    
    for key in all_keys:
        la = lines_a.get(key)
        lb = lines_b.get(key)
        
        status = "unchanged"
        qty_delta = Decimal("0")
        price_delta = Decimal("0")
        total_line_delta = Decimal("0")
        
        if la and not lb:
            status = "removed"
        elif lb and not la:
            status = "added"
        else:
            qty_delta = lb.quantity - la.quantity
            price_delta = lb.unit_price - la.unit_price
            total_line_delta = lb.line_total - la.line_total
            if qty_delta != 0 or price_delta != 0 or la.discount_pct != lb.discount_pct:
                status = "modified"
                
        line_diffs.append({
            "description": key,
            "status": status,
            "line_a": la,
            "line_b": lb,
            "qty_delta": qty_delta,
            "price_delta": price_delta,
            "total_delta": total_line_delta,
        })
        
    return {
        "quote_a": quote_a,
        "quote_b": quote_b,
        "subtotal_delta": subtotal_delta,
        "total_delta": total_delta,
        "margin_delta": margin_delta,
        "line_diffs": line_diffs,
    }


def cpq_render_proposal_html(quote):
    """Generate branded proposal HTML content snapshot for customer viewing and PDF/print."""
    branding = getattr(quote.tenant, "branding", None)
    company_name = quote.tenant.name
    currency_code = quote.currency.code if quote.currency else "USD"
    
    lines_html = []
    for line in quote.lines.filter(is_selected=True).order_by("sequence", "id"):
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;↳ " if line.parent_line else ""
        lines_html.append(f"""
        <tr>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px;">
                {indent}<strong>{line.description}</strong>
                {' <span style="font-size:11px; background:#eff6ff; color:#1d4ed8; padding:2px 6px; border-radius:4px;">Bundle</span>' if line.line_type == 'bundle_parent' else ''}
            </td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-size: 14px;">
                {line.quantity}
            </td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-size: 14px;">
                {currency_code} {line.unit_price:,.2f}
            </td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-size: 14px; color: #64748b;">
                {line.discount_pct}%
            </td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-size: 14px; font-weight: 600;">
                {currency_code} {line.line_total:,.2f}
            </td>
        </tr>
        """)
        
    proposal_html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; color: #0f172a; padding: 24px; line-height: 1.5;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #2563eb; padding-bottom: 20px; margin-bottom: 24px;">
            <div>
                <h1 style="font-size: 26px; margin: 0 0 6px 0; color: #1e3a8a;">COMMERCIAL PROPOSAL</h1>
                <p style="font-size: 15px; margin: 0; color: #475569;">Proposal Reference: <strong>{quote.number}</strong> (Rev {quote.revision_number})</p>
                <p style="font-size: 13px; margin: 4px 0 0 0; color: #64748b;">Date: {quote.created_at.strftime('%B %d, %Y')}</p>
                <p style="font-size: 13px; margin: 2px 0 0 0; color: #64748b;">Valid Until: {quote.valid_until.strftime('%B %d, %Y') if quote.valid_until else '30 Days from issue'}</p>
            </div>
            <div style="text-align: right;">
                <h2 style="font-size: 18px; margin: 0; color: #0f172a;">{company_name}</h2>
                <p style="font-size: 13px; margin: 4px 0 0 0; color: #475569;">Prepared by: {quote.owner.get_full_name() if quote.owner else 'Sales Team'}</p>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 28px;">
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                <h3 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin: 0 0 8px 0;">Customer Information</h3>
                <p style="font-size: 15px; font-weight: 600; margin: 0 0 4px 0;">{quote.account.name if quote.account else 'Valued Customer'}</p>
                <p style="font-size: 13px; margin: 0; color: #475569;">Attention: {quote.contact.name if quote.contact else 'Purchasing Department'}</p>
            </div>
            <div style="background: #f8fafc; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0;">
                <h3 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin: 0 0 8px 0;">Deal Summary</h3>
                <p style="font-size: 15px; font-weight: 600; margin: 0 0 4px 0;">{quote.name}</p>
                <p style="font-size: 13px; margin: 0; color: #475569;">Opportunity: {quote.opportunity.name if quote.opportunity else 'N/A'}</p>
            </div>
        </div>

        <div style="margin-bottom: 28px;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="background: #f1f5f9; color: #475569; font-size: 12px; text-transform: uppercase;">
                        <th style="padding: 10px 12px; border-bottom: 2px solid #cbd5e1;">Item / Description</th>
                        <th style="padding: 10px 12px; border-bottom: 2px solid #cbd5e1; text-align: right;">Qty</th>
                        <th style="padding: 10px 12px; border-bottom: 2px solid #cbd5e1; text-align: right;">Unit Price</th>
                        <th style="padding: 10px 12px; border-bottom: 2px solid #cbd5e1; text-align: right;">Discount</th>
                        <th style="padding: 10px 12px; border-bottom: 2px solid #cbd5e1; text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(lines_html)}
                </tbody>
            </table>
        </div>

        <div style="display: flex; justify-content: flex-end; margin-bottom: 32px;">
            <div style="width: 320px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px;">
                    <span style="color: #64748b;">Subtotal:</span>
                    <span style="font-weight: 500;">{currency_code} {quote.subtotal:,.2f}</span>
                </div>
                {f'''<div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; color: #b91c1c;">
                    <span>Header Discount ({quote.header_discount_pct}%):</span>
                    <span>-{currency_code} {quote.discount_total:,.2f}</span>
                </div>''' if quote.discount_total > 0 else ''}
                <div style="display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 14px;">
                    <span style="color: #64748b;">Estimated Taxes:</span>
                    <span style="font-weight: 500;">{currency_code} {quote.tax_total:,.2f}</span>
                </div>
                <div style="display: flex; justify-content: space-between; border-top: 2px solid #cbd5e1; padding-top: 12px; font-size: 18px; font-weight: 700; color: #1e3a8a;">
                    <span>Total Investment:</span>
                    <span>{currency_code} {quote.total:,.2f}</span>
                </div>
            </div>
        </div>

        {f'''<div style="margin-bottom: 24px; padding: 16px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h4 style="font-size: 13px; text-transform: uppercase; color: #475569; margin: 0 0 6px 0;">Terms & Conditions</h4>
            <div style="font-size: 13px; color: #64748b; white-space: pre-line;">{quote.terms_and_conditions}</div>
        </div>''' if quote.terms_and_conditions else ''}

        {f'''<div style="border: 2px dashed #10b981; background: #ecfdf5; border-radius: 8px; padding: 16px; margin-top: 24px;">
            <p style="margin: 0; font-size: 14px; color: #065f46; font-weight: 600;">✓ Digitally Accepted & Signed</p>
            <p style="margin: 4px 0 0 0; font-size: 12px; color: #047857;">Signed by: {quote.signer_name} ({quote.signer_title}) on {quote.signed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if quote.signed_at else ''}</p>
        </div>''' if quote.signed_at else ''}
    </div>
    """
    quote.proposal_rendered_content = proposal_html
    quote.save(update_fields=["proposal_rendered_content", "updated_at"])
    return proposal_html


@transaction.atomic
def cpq_convert_to_sales_order(quote, user=None):
    """Convert an accepted/approved CPQQuote to an SCM SalesOrder.
    
    Creates scm.SalesOrder and scm.SalesOrderLine items.
    Links the created order back to quote.converted_order.
    Transitions quote.status to 'converted'.
    """
    from apps.scm.models.OrderManagement.SalesOrders import SalesOrder, SalesOrderLine
    from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
    
    if quote.converted_order_id:
        raise ValidationError(f"Quote {quote.number} has already been converted to Order {quote.converted_order.number}.")
        
    if quote.status not in ["approved", "presented", "accepted"]:
        raise ValidationError(f"Quote must be approved, presented, or accepted before conversion (current status: {quote.get_status_display()}).")
        
    if not quote.account:
        raise ValidationError(f"Quote {quote.number} cannot be converted without an associated account (customer).")

    # Create the SCM SalesOrder
    order = SalesOrder.objects.create(
        tenant=quote.tenant,
        customer=quote.account,
        order_date=timezone.localdate(),
        currency=quote.currency,
        status="draft",
        subtotal=quote.subtotal,
        tax_total=quote.tax_total,
        total=quote.total,
        notes=f"Converted from CPQ Quote {quote.number} (Rev {quote.revision_number}). {quote.notes}".strip(),
    )
    
    # Create line items
    for idx, q_line in enumerate(quote.lines.filter(is_selected=True).order_by("sequence", "id"), start=1):
        SalesOrderLine.objects.create(
            sales_order=order,
            item=q_line.item,
            description=q_line.description,
            quantity_ordered=q_line.quantity,
            unit_price=q_line.unit_price,
            discount_pct=q_line.discount_pct,
            tax_pct=q_line.tax_pct,
        )
        
    quote.converted_order = order
    quote.status = "converted"
    quote.save(update_fields=["converted_order", "status", "updated_at"])
    
    # If quote was linked to CRM opportunity, advance opportunity stage if possible
    if quote.opportunity_id:
        opp = quote.opportunity
        opp.stage = "closed_won"
        opp.save(update_fields=["stage", "updated_at"])
        
    return order
