"""CRM models package — split from the former monolithic apps/crm/models.py.

One sub-package per CRM sub-module (1.1-1.12), one module per entity (mirrors apps/crm/views/ and
apps/crm/forms/). This __init__ re-exports every model, choice list and helper, so
``from apps.crm.models import Lead`` (admin.py, analytics.py, seed_crm.py, every test) is unchanged.
"""
# Re-export the shared base/toolkit so the package namespace matches the pre-split models.py, which
# incidentally exposed everything it imported (e.g. ``TenantNumbered``, ``next_number``).
from ._base import *  # noqa: F401,F403

# 1.1 Core Data Management
from .CoreData.Leads import (
    Lead,
)
from .CoreData.Accounts import (
    INDUSTRY_CHOICES,
    AccountProfile,
)
from .CoreData.Contacts import (
    ContactProfile,
)

# 1.2 Sales Force Automation
from .SalesForceAutomation.Opportunities import (
    Opportunity,
    OpportunitySplit,
)
from .SalesForceAutomation.Territories import (
    Territory,
)
from .SalesForceAutomation.Products import (
    Product,
)
from .SalesForceAutomation.PriceBooks import (
    PriceBook,
)
from .SalesForceAutomation.Quotes import (
    Quote,
    QuoteLine,
)
from .SalesForceAutomation.SalesQuotas import (
    SalesQuota,
)

# 1.3 Marketing Automation
from .MarketingAutomation.Campaigns import (
    Campaign,
    CampaignMember,
)
from .MarketingAutomation.EmailTemplates import (
    EmailTemplate,
)
from .MarketingAutomation.EmailCampaigns import (
    EmailCampaign,
)
from .MarketingAutomation.LandingPages import (
    LandingPage,
)
from .MarketingAutomation.FormSubmissions import (
    FormSubmission,
)

# 1.4 Customer Service & Support
from .CustomerService.Cases import (
    Case,
    CaseComment,
)
from .CustomerService.KnowledgeBase import (
    KnowledgeArticle,
)
from .CustomerService.SlaPolicies import (
    SlaPolicy,
)
from .CustomerService.KbCategories import (
    KbCategory,
)
from .CustomerService.CustomerPortalAccess import (
    CustomerPortalAccess,
)

# 1.5 Activity & Communication Management
from .ActivityManagement.Tasks import (
    CrmTask,
)
from .ActivityManagement.CalendarEvents import (
    CalendarEvent,
    EventAttendee,
)
from .ActivityManagement.CommunicationLogs import (
    CommunicationLog,
)

# 1.6 Analytics & Reporting
from .AnalyticsReporting._choices import (
    ANALYTICS_RANGE_CHOICES,
    DASHBOARD_LAYOUT_CHOICES,
    WIDGET_CHART_CHOICES,
    WIDGET_SIZE_CHOICES,
    WIDGET_METRIC_CHOICES,
    REPORT_TYPE_CHOICES,
    REPORT_GROUP_CHOICES,
)
from .AnalyticsReporting.Dashboards import (
    AnalyticsDashboard,
)
from .AnalyticsReporting.Widgets import (
    DashboardWidget,
)
from .AnalyticsReporting.Reports import (
    AnalyticsReport,
)
from .AnalyticsReporting.Snapshots import (
    ReportSnapshot,
)

# 1.7 Finance & Billing Management
from .FinanceBilling.Expenses import (
    Expense,
)
from .FinanceBilling.DealInvoices import (
    DealInvoice,
)
from .FinanceBilling.PaymentReceipts import (
    PaymentReceipt,
)

# 1.8 Project & Delivery Management
from .ProjectDelivery.Projects import (
    CrmProject,
)
from .ProjectDelivery.Milestones import (
    CrmMilestone,
)
from .ProjectDelivery.Timesheets import (
    Timesheet,
)
from .ProjectDelivery.ResourceAllocation import (
    ResourceAllocation,
)

# 1.9 Document & Contract Management
from .DocumentContract.DocTemplates import (
    DocTemplate,
)
from .DocumentContract.Contracts import (
    ContractDocument,
    SignerRecord,
)
from .DocumentContract.DocumentVersions import (
    DocumentVersion,
)

# 1.10 Automation & Workflow Engine
from .AutomationWorkflow.WorkflowRules import (
    WorkflowRule,
)
from .AutomationWorkflow.WorkflowLogs import (
    WorkflowLog,
)
from .AutomationWorkflow.Approvals import (
    ApprovalRequest,
)
from .AutomationWorkflow.Webhooks import (
    Webhook,
    WebhookDelivery,
)

# 1.11 Customer Success & Retention
from .CustomerSuccess.OnboardingPlans import (
    OnboardingPlan,
    OnboardingStep,
)
from .CustomerSuccess.OnboardingTemplates import (
    OnboardingTemplate,
    OnboardingTemplateStep,
)
from .CustomerSuccess.HealthScores import (
    HealthScoreConfig,
    HealthScore,
    HealthScoreHistory,
    compute_health_score,
)
from .CustomerSuccess.Surveys import (
    Survey,
)

# 1.12 Inventory & Vendor Management
from .InventoryVendor.ProductStock import (
    ProductStock,
)
from .InventoryVendor.PurchaseOrders import (
    PurchaseOrder,
    PurchaseOrderLine,
)
from .InventoryVendor.PartnerPortalAccess import (
    PartnerPortalAccess,
)
