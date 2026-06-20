"""Forms for the advanced accounting sub-modules 2.6–2.15. All extend ``TenantModelForm`` so FK
dropdowns auto-scope to the tenant. System/derived fields (``number``, ``*_journal_entry``,
``accumulated_depreciation``, ``net_pay``, ``gain_loss``, ``api_key_*``, ``last_*``) are
``editable=False`` on the model and simply omitted here; ``status`` is omitted where a workflow
action owns it (disposal/posting)."""
from apps.core.forms import TenantModelForm

from .models_advanced import (
    AssetDisposal,
    Budget,
    BudgetLine,
    CostAllocation,
    FixedAsset,
    IntegrationConfig,
    IntercompanyTransaction,
    InternalControl,
    JobCostEntry,
    PayrollRun,
    Project,
    ScheduledReport,
    TaxCode,
    TaxReturn,
)


class FixedAssetForm(TenantModelForm):
    class Meta:
        model = FixedAsset
        fields = ["name", "category", "acquisition_cost", "salvage_value", "useful_life_months",
                  "method", "in_service_date", "status", "asset_account", "accumulated_account",
                  "expense_account", "custodian", "location", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 'disposed' is reached only via the AssetDisposal posting action, never by hand.
        self.fields["status"].choices = [c for c in FixedAsset.STATUS_CHOICES if c[0] != "disposed"]


class AssetDisposalForm(TenantModelForm):
    class Meta:
        model = AssetDisposal
        fields = ["asset", "disposal_date", "proceeds", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant, status="active")


class CostAllocationForm(TenantModelForm):
    class Meta:
        model = CostAllocation
        fields = ["description", "allocation_date", "amount", "source_account", "target_account",
                  "target_org_unit"]


class PayrollRunForm(TenantModelForm):
    class Meta:
        model = PayrollRun
        # net_pay is derived in save(); status/journal_entry owned by the post action.
        fields = ["period_start", "period_end", "pay_date", "headcount", "gross_wages",
                  "employee_tax", "employer_tax", "benefits", "deductions"]


class ProjectForm(TenantModelForm):
    class Meta:
        model = Project
        fields = ["name", "client", "org_unit", "billing_method", "budget_amount", "start_date",
                  "end_date", "status", "notes"]


class JobCostEntryForm(TenantModelForm):
    class Meta:
        model = JobCostEntry
        fields = ["project", "entry_date", "kind", "amount", "gl_account", "description"]


class IntercompanyTransactionForm(TenantModelForm):
    class Meta:
        model = IntercompanyTransaction
        fields = ["description", "transaction_date", "amount", "from_org_unit", "to_org_unit",
                  "due_from_account", "due_to_account", "eliminated"]


class TaxCodeForm(TenantModelForm):
    class Meta:
        model = TaxCode
        fields = ["name", "jurisdiction", "tax_type", "rate_pct", "payable_account", "is_active"]


class TaxReturnForm(TenantModelForm):
    class Meta:
        model = TaxReturn
        fields = ["tax_code", "period_start", "period_end", "taxable_amount", "tax_due", "status",
                  "filed_date", "due_date", "notes"]


class ScheduledReportForm(TenantModelForm):
    class Meta:
        model = ScheduledReport
        fields = ["name", "report_type", "frequency", "recipients", "is_active"]


class BudgetForm(TenantModelForm):
    class Meta:
        model = Budget
        fields = ["name", "fiscal_period", "version", "status", "notes"]


class BudgetLineForm(TenantModelForm):
    class Meta:
        model = BudgetLine
        fields = ["budget", "gl_account", "org_unit", "amount"]


class InternalControlForm(TenantModelForm):
    class Meta:
        model = InternalControl
        fields = ["code", "name", "control_type", "frequency", "risk_level", "owner",
                  "last_tested_date", "last_result", "status", "description"]


class IntegrationConfigForm(TenantModelForm):
    class Meta:
        model = IntegrationConfig
        # api_key_prefix/hash are write-once via the rotate action (never on this form, L20/L25).
        fields = ["name", "provider", "category", "status", "is_active", "notes"]
