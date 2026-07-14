"""Accounting 2.5 Cash Management — BankTransactions views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _need_tenant
from apps.accounting.models import (
    BankAccount,
    BankTransaction,
)
from apps.accounting.forms import (
    BankTransactionForm,
    CsvImportForm,
)


# ============================================================ 2.5 Cash — Bank transactions
@login_required
def bank_transaction_list(request):
    return crud_list(
        request, BankTransaction.objects.filter(tenant=request.tenant).select_related("bank_account"),
        "accounting/cash/bank_transaction/list.html",
        search_fields=["description", "external_ref"],
        filters=[("bank_account", "bank_account_id", True), ("direction", "direction", False),
                 ("status", "status", False)],
        extra_context={"bank_accounts": BankAccount.objects.filter(tenant=request.tenant),
                       "direction_choices": BankTransaction.DIRECTION_CHOICES,
                       "status_choices": BankTransaction.STATUS_CHOICES},
    )


@login_required
def bank_transaction_create(request):
    return crud_create(request, form_class=BankTransactionForm, template="accounting/cash/bank_transaction/form.html",
                       success_url="accounting:bank_transaction_list")


@login_required
def bank_transaction_detail(request, pk):
    obj = get_object_or_404(BankTransaction.objects.select_related("bank_account"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/cash/bank_transaction/detail.html", {
        "obj": obj,
        "match": obj.matches.select_related("payment", "journal_line", "matched_by").first(),
    })


@login_required
def bank_transaction_edit(request, pk):
    return crud_edit(request, model=BankTransaction, pk=pk, form_class=BankTransactionForm,
                     template="accounting/cash/bank_transaction/form.html", success_url="accounting:bank_transaction_list")


@login_required
@require_POST
def bank_transaction_delete(request, pk):
    return crud_delete(request, model=BankTransaction, pk=pk, success_url="accounting:bank_transaction_list")


@login_required
def bank_transaction_import_csv(request):
    """Import bank-statement rows from a CSV (columns: date, description, amount, direction).
    Idempotent on ``external_ref`` when supplied. POST-only mutation; GET shows the upload form."""
    if request.method == "POST":
        if _need_tenant(request):
            return redirect("accounting:bank_transaction_list")
        form = CsvImportForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            bank_account = form.cleaned_data["bank_account"]
            # Defense-in-depth: the form already scopes the choices to the tenant, but re-assert
            # ownership of the resolved account before writing (security review M2).
            if bank_account.tenant_id != request.tenant.pk:
                raise PermissionDenied
            upload = form.cleaned_data["csv_file"]
            created = skipped = 0
            try:
                text = upload.read().decode("utf-8-sig", errors="replace")
            except Exception:
                messages.error(request, "Could not read the uploaded file.")
                return redirect("accounting:bank_transaction_import_csv")
            reader = csv.DictReader(io.StringIO(text))
            # Dedupe against existing external_refs in ONE query (not a per-row .exists()), build
            # the rows in memory, then a single atomic bulk_create (perf-review I-7).
            existing_refs = set(
                BankTransaction.objects.filter(tenant=request.tenant, bank_account=bank_account)
                .exclude(external_ref="").values_list("external_ref", flat=True)
            )
            to_create, seen_refs = [], set()
            for row in reader:
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                raw_date = row.get("date", "")
                desc = row.get("description", "")
                try:
                    amount = Decimal(row.get("amount", "0") or "0")
                except (InvalidOperation, TypeError):
                    skipped += 1
                    continue
                direction = row.get("direction", "").lower()
                if direction not in ("credit", "debit"):
                    direction = "credit" if amount >= 0 else "debit"
                ext = (row.get("external_ref", "") or row.get("reference", ""))[:255]
                if ext and (ext in existing_refs or ext in seen_refs):
                    skipped += 1
                    continue
                parsed_date = None
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        parsed_date = timezone.datetime.strptime(raw_date, fmt).date()
                        break
                    except (ValueError, TypeError):
                        continue
                if parsed_date is None:
                    skipped += 1
                    continue
                if ext:
                    seen_refs.add(ext)
                to_create.append(BankTransaction(
                    tenant=request.tenant, bank_account=bank_account, transaction_date=parsed_date,
                    description=desc[:512] or "(imported)", amount=abs(amount), direction=direction,
                    source="csv_import", external_ref=ext,
                ))
            with transaction.atomic():
                BankTransaction.objects.bulk_create(to_create)
            messages.success(request, f"Imported {len(to_create)} transaction(s); skipped {skipped}.")
            return redirect("accounting:bank_transaction_list")
    else:
        form = CsvImportForm(tenant=request.tenant)
    return render(request, "accounting/cash/bank_transaction/import.html", {"form": form})
