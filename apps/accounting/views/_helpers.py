"""Cross-cutting private helpers for the accounting views package.

These are used by MORE THAN ONE sub-module, so they live here rather than in an entity module:
tenant guard, GL posting + period guards, document-status recompute, journal reversal, cash
position, AR/AP aging, and the account-balance roll-up behind the financial statements.
``views/__init__`` re-exports ``_cash_position`` / ``_aging`` / ``_account_balances`` because the
test-suite imports them directly.
"""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    BankAccount,
    BankTransaction,
    FiscalPeriod,
    GLAccount,
    JournalEntry,
    JournalLine,
    ZERO,
)


# --------------------------------------------------------------------------- helpers
def _need_tenant(request):
    """True (and flashes) when there is no active tenant workspace to write into."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return True
    return False


def _first_account(tenant, account_type, code_prefix=None):
    qs = GLAccount.objects.filter(tenant=tenant, account_type=account_type, is_active=True)
    if code_prefix:
        hit = qs.filter(code__startswith=code_prefix).first()
        if hit:
            return hit
    return qs.first()


def _open_period(tenant):
    return FiscalPeriod.objects.filter(tenant=tenant, status="open").order_by("-start_date").first()


def _recompute_doc_status(*docs):
    """Refresh the payment-derived status (partial/paid) of any Invoice/Bill passed (skips None)."""
    for doc in docs:
        if doc is not None:
            doc.recompute_payment_status()


def _reverse_journal_entry(tenant, user, original):
    """Post a balanced reversal of a posted ``JournalEntry`` (debits/credits swapped) and mark the
    original ``void``. The single point of truth for voiding any posted GL entry (manual JE *or* the
    JE behind a payment) so the ledger always stays balanced. Caller wraps this in atomic()."""
    reversal = JournalEntry.objects.create(
        tenant=tenant, entry_type="reversal", status="posted",
        fiscal_period=original.fiscal_period if (original.fiscal_period and original.fiscal_period.is_open) else _open_period(tenant),
        entry_date=timezone.localdate(), description=f"Reversal of {original.number}",
        reversal_of=original, created_by=user, approved_by=user, posted_at=timezone.now(),
    )
    for ln in original.lines.all():
        JournalLine.objects.create(
            entry=reversal, gl_account=ln.gl_account, debit=ln.credit, credit=ln.debit,
            description=f"Reversal: {ln.description}", party=ln.party, org_unit=ln.org_unit,
            currency=ln.currency,
        )
    original.status = "void"
    original.save(update_fields=["status", "updated_at"])
    return reversal


# ============================================================== 2.1 Dashboard + reports
def _cash_position(tenant):
    """Current cash = Σ(bank opening balances) + net (credit − debit) of all bank transactions.
    Two queries (no N+1): one grouped movement aggregate keyed by account + the opening balances."""
    banks = list(BankAccount.objects.filter(tenant=tenant))
    net_by_bank = {
        r["bank_account_id"]: (r["credit"] or ZERO) - (r["debit"] or ZERO)
        for r in BankTransaction.objects.filter(tenant=tenant).values("bank_account_id")
        .annotate(credit=Sum("amount", filter=Q(direction="credit")),
                  debit=Sum("amount", filter=Q(direction="debit")))
    }
    return sum(((b.opening_balance or ZERO) + net_by_bank.get(b.pk, ZERO) for b in banks), ZERO)


def _aging(rows, due_attr, today):
    """Bucket a list of documents by overdue age and group by party. Returns (party_rows, totals)."""
    buckets = ("current", "d1_30", "d31_60", "d61_90", "d90_plus")
    by_party = {}
    totals = {b: ZERO for b in buckets}
    totals["total"] = ZERO
    for doc in rows:
        due = getattr(doc, due_attr)
        # `paid_agg` is annotated on the queryset by the caller (perf-review C-2) so this loop
        # issues NO per-document aggregate query.
        amount = (doc.total or ZERO) - (doc.paid_agg or ZERO)
        if amount <= ZERO:
            continue
        days = (today - due).days if due else 0
        if days <= 0:
            b = "current"
        elif days <= 30:
            b = "d1_30"
        elif days <= 60:
            b = "d31_60"
        elif days <= 90:
            b = "d61_90"
        else:
            b = "d90_plus"
        name = doc.party.name
        prow = by_party.setdefault(name, {k: ZERO for k in buckets} | {"total": ZERO, "party": name})
        prow[b] += amount
        prow["total"] += amount
        totals[b] += amount
        totals["total"] += amount
    return sorted(by_party.values(), key=lambda r: r["party"]), totals


# --------------------------------------------------------------------------- posting helper
def _post_journal_entry(tenant, user, description, legs, *, reference="", entry_type="manual", date=None):
    """Create a posted, balanced JournalEntry. ``legs`` = [(gl_account, debit, credit, party, org_unit)].
    Returns the JE, or None when legs are empty / don't balance (caller handles the skip)."""
    legs = [l for l in legs if (l[1] or ZERO) or (l[2] or ZERO)]
    if not legs:
        return None
    debit = sum((l[1] or ZERO for l in legs), ZERO)
    credit = sum((l[2] or ZERO for l in legs), ZERO)
    if debit != credit or debit <= ZERO:
        return None
    je = JournalEntry.objects.create(
        tenant=tenant, entry_type=entry_type, status="posted", fiscal_period=_open_period(tenant),
        entry_date=date or timezone.localdate(), description=description[:255], reference=reference[:100],
        created_by=user, approved_by=user, posted_at=timezone.now(),
    )
    for gl, d, c, party, org in legs:
        JournalLine.objects.create(entry=je, gl_account=gl, debit=d or ZERO, credit=c or ZERO,
                                   description=description[:255], party=party, org_unit=org)
    return je


# ===================================================== 2.12 Reporting & Compliance
def _account_balances(tenant):
    """Return per-account balances grouped from a single posted-line aggregate (no per-account query)."""
    rows = (JournalLine.objects.filter(entry__tenant=tenant, entry__status="posted")
            .values("gl_account__code", "gl_account__name", "gl_account__account_type",
                    "gl_account__normal_balance")
            .annotate(d=Sum("debit"), c=Sum("credit")).order_by("gl_account__code"))
    out = []
    for r in rows:
        debit, credit = r["d"] or ZERO, r["c"] or ZERO
        signed = (debit - credit) if r["gl_account__normal_balance"] == "debit" else (credit - debit)
        out.append({"code": r["gl_account__code"], "name": r["gl_account__name"],
                    "type": r["gl_account__account_type"], "balance": signed})
    return out
